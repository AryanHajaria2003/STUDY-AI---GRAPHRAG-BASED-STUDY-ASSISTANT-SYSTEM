import hashlib
import re
import time
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from Backend.document_processing import process_document
from Backend.semantic_chunking import semantic_chunking
from Backend.entity_extraction import extract_entities
from Backend.neo4j_connection import driver

UNIT_PATTERN = re.compile(
    r"^\s*UNIT\s+([IVXLCDM]+|\d+)\s*:?\s*(.*?)\s*$",
    re.IGNORECASE
)

PAPER_PATTERN = re.compile(
    r"^\s*Paper\s*:\s*(.+?)\s*$",
    re.IGNORECASE
)

STOP_PATTERN = re.compile(
    r"^(text books?|reference books?|suggested readings|field work|"
    r"note\s*:|course outcomes|instructions to paper setters|"
    r"maximum marks|nues paper)\b",
    re.IGNORECASE
)

STOP_CONCEPTS = {
    "introduction", "basic", "basics", "overview",
    "harmony", "application", "development",
    "fundamentals", "delhi", "mca", "student",
    "students", "paper", "unit", "course",
    "syllabus", "university", "concept", "concepts"
}

GRAPH_LABELS = ["Concept", "Chunk", "Topic", "Unit", "Subject"]

# Schema (constraints/indexes) only needs to be created once per process.
_SCHEMA_READY = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(value):
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def stable_id(*parts):
    raw = "|".join(normalize(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_content_id(file_path):
    """Document id based on file CONTENT (not on the random temp filename),
    so re-uploading the same syllabus replaces its old graph instead of
    leaving duplicates behind."""
    digest = hashlib.sha256()

    with open(file_path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def entity_pages(entity):
    return sorted({
        int(p) for p in entity.get("page_numbers", [])
        if str(p).isdigit()
    })


def build_unit_sections(pages):
    sections = {}
    current_subject = None
    current_unit = None

    for page in pages:
        page_number = int(page["page_number"])

        for raw_line in page["text"].splitlines():
            line = raw_line.strip()

            if not line:
                continue

            paper_match = PAPER_PATTERN.match(line)

            if paper_match:
                current_subject = paper_match.group(1).strip()
                current_unit = None
                continue

            if not current_subject:
                continue

            unit_match = UNIT_PATTERN.match(line)

            if unit_match:
                unit_number = unit_match.group(1).upper()
                current_unit = f"Unit {unit_number}"

                key = (
                    normalize(current_subject),
                    normalize(current_unit)
                )

                sections.setdefault(key, {
                    "subject": current_subject,
                    "unit": current_unit,
                    "pages": []
                })

                sections[key]["pages"].append({
                    "page_number": page_number,
                    "text": line
                })
                continue

            if STOP_PATTERN.match(line):
                current_unit = None
                continue

            if current_unit:
                key = (
                    normalize(current_subject),
                    normalize(current_unit)
                )

                sections[key]["pages"].append({
                    "page_number": page_number,
                    "text": line
                })

    for section in sections.values():
        combined = {}

        for item in section["pages"]:
            number = item["page_number"]
            combined.setdefault(number, []).append(item["text"])

        section["pages"] = [
            {
                "page_number": number,
                "text": "\n".join(lines)
            }
            for number, lines in sorted(combined.items())
        ]

    return sections


def concept_candidates(topic_name):
    parts = re.split(
        r"\s+(?:and|&)\s+|[,;/]",
        topic_name,
        flags=re.IGNORECASE
    )

    candidates = []

    for part in parts:
        phrase = re.sub(r"\s+", " ", part).strip(" .:-")
        key = normalize(phrase)
        words = key.split()

        if not phrase or key in STOP_CONCEPTS:
            continue

        if len(words) == 1 and not (
            phrase.isupper() and 2 <= len(phrase) <= 8
        ):
            continue

        if len(words) > 7 or len(phrase) < 3:
            continue

        candidates.append((key, phrase))

    full_key = normalize(topic_name)

    if (
        len(full_key.split()) >= 2
        and full_key not in STOP_CONCEPTS
        and not any(k == full_key for k, _ in candidates)
    ):
        candidates.insert(0, (full_key, topic_name.strip()))

    return list(dict(candidates).items())


def phrase_in_text(phrase, text):
    """Original (slow) helper, kept for compatibility with other modules."""
    words = [
        re.escape(word)
        for word in normalize(phrase).split()
    ]

    if not words:
        return False

    pattern = r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)"
    return re.search(pattern, normalize(text)) is not None


@lru_cache(maxsize=4096)
def _phrase_regex(normalized_phrase):
    words = [re.escape(word) for word in normalized_phrase.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)")


def phrase_in_normalized_text(phrase, normalized_text):
    """Same result as phrase_in_text, but the chunk text is normalized once
    up front, the regex is cached, and a cheap substring test runs first."""
    normalized_phrase = normalize(phrase)

    if not normalized_phrase:
        return False

    if normalized_phrase not in normalized_text:
        return False

    return _phrase_regex(normalized_phrase).search(normalized_text) is not None


def run_batches(tx, query, rows, batch_size=500, **params):
    """Send many rows to Neo4j with one UNWIND query per batch instead of
    one network round trip per row."""
    for start in range(0, len(rows), batch_size):
        tx.run(
            query,
            rows=rows[start:start + batch_size],
            **params
        ).consume()


# ---------------------------------------------------------------------------
# Neo4j schema / cleanup
# ---------------------------------------------------------------------------

def create_constraints(session):
    global _SCHEMA_READY

    if _SCHEMA_READY:
        return

    queries = [
        "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (n:Document) REQUIRE n.document_id IS UNIQUE",
        "CREATE CONSTRAINT subject_id_unique IF NOT EXISTS FOR (n:Subject) REQUIRE n.subject_id IS UNIQUE",
        "CREATE CONSTRAINT unit_id_unique IF NOT EXISTS FOR (n:Unit) REQUIRE n.unit_id IS UNIQUE",
        "CREATE CONSTRAINT topic_id_unique IF NOT EXISTS FOR (n:Topic) REQUIRE n.topic_id IS UNIQUE",
        "CREATE CONSTRAINT concept_id_unique IF NOT EXISTS FOR (n:Concept) REQUIRE n.concept_id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (n:Chunk) REQUIRE n.chunk_id IS UNIQUE",
        # Indexes so that "delete / look up everything for a document_id"
        # does not scan the whole database.
        "CREATE INDEX subject_document_idx IF NOT EXISTS FOR (n:Subject) ON (n.document_id)",
        "CREATE INDEX unit_document_idx IF NOT EXISTS FOR (n:Unit) ON (n.document_id)",
        "CREATE INDEX topic_document_idx IF NOT EXISTS FOR (n:Topic) ON (n.document_id)",
        "CREATE INDEX concept_document_idx IF NOT EXISTS FOR (n:Concept) ON (n.document_id)",
        "CREATE INDEX chunk_document_idx IF NOT EXISTS FOR (n:Chunk) ON (n.document_id)"
    ]

    for query in queries:
        session.run(query).consume()

    _SCHEMA_READY = True


def clear_document_graph(tx, document_id):
    # One label at a time so Neo4j can use the document_id indexes
    # (the old "MATCH (n) WHERE n.document_id" scanned every node).
    for label in GRAPH_LABELS:
        tx.run(
            f"MATCH (n:{label} {{document_id: $document_id}}) "
            f"DETACH DELETE n",
            document_id=document_id
        ).consume()

    tx.run(
        "MATCH (n:Document {document_id: $document_id}) DETACH DELETE n",
        document_id=document_id
    ).consume()


# ---------------------------------------------------------------------------
# Graph construction (batched)
# ---------------------------------------------------------------------------

def construct_graph(tx, metadata, entities, pages, progress=print):
    document_id = metadata["document_id"]
    stage_start = time.time()

    sections = build_unit_sections(pages)

    tx.run("""
        MERGE (d:Document {document_id: $id})
        SET d.filename = $filename,
            d.title = $title,
            d.total_pages = $total_pages
    """,
        id=document_id,
        filename=metadata["filename"],
        title=metadata["title"],
        total_pages=metadata["total_pages"]
    ).consume()

    # ---- Subjects ---------------------------------------------------------
    subject_ids = {}
    subject_rows = []

    for entity in entities:
        if entity["type"] != "Subject":
            continue

        name = entity["name"]
        subject_id = stable_id(document_id, "Subject", name)
        subject_ids[normalize(name)] = subject_id

        subject_rows.append({
            "id": subject_id,
            "name": name,
            "code": entity.get("code"),
            "pages": entity_pages(entity)
        })

    run_batches(tx, """
        MATCH (d:Document {document_id: $doc})
        UNWIND $rows AS row
        MERGE (s:Subject {subject_id: row.id})
        SET s.name = row.name,
            s.code = row.code,
            s.page_numbers = row.pages,
            s.document_id = $doc
        MERGE (d)-[:CONTAINS]->(s)
    """, subject_rows, doc=document_id)

    # ---- Units ------------------------------------------------------------
    unit_ids = {}
    unit_rows = []

    for entity in entities:
        if entity["type"] != "Unit":
            continue

        subject = entity.get("subject")
        subject_id = subject_ids.get(normalize(subject))

        if not subject_id:
            continue

        unit_name = entity["name"]
        key = (normalize(subject), normalize(unit_name))
        unit_id = stable_id(document_id, subject, unit_name)
        unit_ids[key] = unit_id

        unit_rows.append({
            "subject_id": subject_id,
            "unit_id": unit_id,
            "name": unit_name,
            "title": entity.get("title"),
            "pages": entity_pages(entity)
        })

    run_batches(tx, """
        UNWIND $rows AS row
        MATCH (s:Subject {subject_id: row.subject_id})
        MERGE (u:Unit {unit_id: row.unit_id})
        SET u.name = row.name,
            u.title = row.title,
            u.page_numbers = row.pages,
            u.document_id = $doc
        MERGE (s)-[:HAS_UNIT]->(u)
    """, unit_rows, doc=document_id)

    # ---- Topics -----------------------------------------------------------
    topic_records = []
    topic_rows = []

    for entity in entities:
        if entity["type"] != "Topic":
            continue

        subject = entity.get("subject")
        unit = entity.get("unit")

        subject_id = subject_ids.get(normalize(subject))
        unit_id = unit_ids.get(
            (normalize(subject), normalize(unit))
        )

        if not subject_id or not unit_id:
            continue

        topic_id = stable_id(
            document_id, subject, unit, "Topic", entity["name"]
        )

        pages_list = entity_pages(entity)

        topic_records.append({
            "id": topic_id,
            "name": entity["name"],
            "subject_id": subject_id,
            "unit_id": unit_id,
            "pages": pages_list
        })

        topic_rows.append({
            "unit_id": unit_id,
            "topic_id": topic_id,
            "name": entity["name"],
            "pages": pages_list,
            "subject_id": subject_id
        })

    run_batches(tx, """
        UNWIND $rows AS row
        MATCH (u:Unit {unit_id: row.unit_id})
        MERGE (t:Topic {topic_id: row.topic_id})
        SET t.name = row.name,
            t.page_numbers = row.pages,
            t.document_id = $doc,
            t.subject_id = row.subject_id,
            t.unit_id = row.unit_id
        MERGE (u)-[:CONTAINS]->(t)
    """, topic_rows, doc=document_id)

    progress(
        f"Subjects/units/topics written: {len(subject_rows)} / "
        f"{len(unit_rows)} / {len(topic_rows)} "
        f"({time.time() - stage_start:.1f}s)"
    )

    # ---- Chunks -----------------------------------------------------------
    stage_start = time.time()

    chunk_records = []
    chunk_rows = []
    chunk_count = 0

    total_sections = len(sections)

    for position, (key, section) in enumerate(sections.items(), start=1):
        unit_id = unit_ids.get(key)
        subject_id = subject_ids.get(key[0])

        if not unit_id or not subject_id:
            continue

        progress(
            f"Chunking section {position}/{total_sections}: "
            f"{section['subject']} - {section['unit']}"
        )

        chunks = semantic_chunking(section["pages"])

        for index, chunk in enumerate(chunks, start=1):
            text = chunk["text"]
            chunk_pages = sorted(set(chunk.get("page_numbers", [])))

            chunk_id = stable_id(
                document_id, key[0], key[1],
                "Chunk", index, normalize(text)
            )

            chunk_rows.append({
                "id": chunk_id,
                "text": text,
                "pages": chunk_pages,
                "index": index,
                "subject_id": subject_id,
                "unit_id": unit_id
            })

            chunk_records.append({
                "id": chunk_id,
                "norm_text": normalize(text),   # normalized ONCE
                "pages": set(chunk_pages),
                "subject_id": subject_id,
                "unit_id": unit_id
            })

            chunk_count += 1

    run_batches(tx, """
        MATCH (d:Document {document_id: $doc})
        UNWIND $rows AS row
        MERGE (ch:Chunk {chunk_id: row.id})
        SET ch.text = row.text,
            ch.page_numbers = row.pages,
            ch.chunk_index = row.index,
            ch.subject_id = row.subject_id,
            ch.unit_id = row.unit_id,
            ch.document_id = $doc
        MERGE (d)-[:HAS_CHUNK]->(ch)
    """, chunk_rows, batch_size=200, doc=document_id)

    progress(
        f"{chunk_count} chunks written ({time.time() - stage_start:.1f}s)"
    )

    # ---- Concepts + links -------------------------------------------------
    stage_start = time.time()

    chunks_by_unit = defaultdict(list)

    for chunk in chunk_records:
        chunks_by_unit[(chunk["subject_id"], chunk["unit_id"])].append(chunk)

    concept_rows = {}   # concept_id -> row (deduplicated)
    link_rows = {}      # (concept_id, chunk_id) -> row (deduplicated)

    for topic in topic_records:
        topic_pages = set(topic["pages"])

        if not topic_pages:
            continue

        candidate_chunks = [
            chunk
            for chunk in chunks_by_unit.get(
                (topic["subject_id"], topic["unit_id"]), []
            )
            if chunk["pages"] & topic_pages
        ]

        if not candidate_chunks:
            continue

        for canonical, display_name in concept_candidates(topic["name"]):

            matching_chunks = [
                chunk for chunk in candidate_chunks
                if phrase_in_normalized_text(
                    display_name, chunk["norm_text"]
                )
            ]

            if not matching_chunks:
                continue

            concept_id = stable_id(
                document_id, topic["id"], "Concept", canonical
            )

            concept_rows[concept_id] = {
                "topic_id": topic["id"],
                "concept_id": concept_id,
                "name": display_name,
                "normalized": canonical,
                "subject_id": topic["subject_id"],
                "unit_id": topic["unit_id"]
            }

            for chunk in matching_chunks:
                link_rows[(concept_id, chunk["id"])] = {
                    "concept_id": concept_id,
                    "chunk_id": chunk["id"]
                }

    concept_list = list(concept_rows.values())
    link_list = list(link_rows.values())

    run_batches(tx, """
        UNWIND $rows AS row
        MATCH (t:Topic {topic_id: row.topic_id})
        MERGE (c:Concept {concept_id: row.concept_id})
        SET c.name = row.name,
            c.normalized_name = row.normalized,
            c.document_id = $doc,
            c.subject_id = row.subject_id,
            c.unit_id = row.unit_id,
            c.topic_id = row.topic_id,
            c.extraction_method = 'topic_phrase'
        MERGE (t)-[:HAS_CONCEPT]->(c)
    """, concept_list, doc=document_id)

    run_batches(tx, """
        UNWIND $rows AS row
        MATCH (c:Concept {concept_id: row.concept_id})
        MATCH (ch:Chunk {chunk_id: row.chunk_id})
        MERGE (c)-[:MENTIONED_IN]->(ch)
    """, link_list, batch_size=1000)

    progress(
        f"{len(concept_list)} concepts / {len(link_list)} links written "
        f"({time.time() - stage_start:.1f}s)"
    )

    return chunk_count, len(concept_list), len(link_list)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def process_uploaded_file(file_path, progress=print):
    """Process an uploaded syllabus and build its knowledge graph.

    `progress` is any callable that accepts a string. Pass `st.write` from
    Streamlit (inside `st.status`) to see each stage live.
    """
    file_path = Path(file_path).resolve()

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    if file_path.suffix.lower() not in {
        ".pdf", ".png", ".jpg", ".jpeg"
    }:
        raise ValueError("Only PDF, PNG and JPG files are supported.")

    total_start = time.time()
    progress(f"Processing: {file_path.name}")

    # Fail fast (instead of hanging) if Neo4j is unreachable or paused.
    progress("Checking Neo4j connection...")
    stage_start = time.time()
    driver.verify_connectivity()
    progress(f"Neo4j reachable ({time.time() - stage_start:.1f}s)")

    document_id = file_content_id(file_path)

    progress("Reading document (text extraction / OCR)...")
    stage_start = time.time()
    document = process_document(file_path)
    pages = document["pages"]
    progress(
        f"Read {len(pages)} pages ({time.time() - stage_start:.1f}s)"
    )

    progress("Extracting subjects, units and topics...")
    stage_start = time.time()
    entities = extract_entities(pages)
    progress(
        f"Extracted {len(entities)} entities "
        f"({time.time() - stage_start:.1f}s)"
    )

    metadata = document["metadata"]
    metadata["document_id"] = document_id

    if not any(e["type"] == "Subject" for e in entities):
        raise ValueError(
            "No subjects found. Check whether the uploaded syllabus "
            "contains recognizable Paper headings."
        )

    progress("Writing knowledge graph to Neo4j...")
    stage_start = time.time()

    with driver.session() as session:
        create_constraints(session)

        session.execute_write(
            clear_document_graph, document_id
        )

        counts = session.execute_write(
            construct_graph, metadata, entities, pages, progress
        )

    progress(
        f"Neo4j write finished ({time.time() - stage_start:.1f}s). "
        f"Total time: {time.time() - total_start:.1f}s"
    )

    return {
        "document_id": document_id,
        "filename": file_path.name,
        "subjects": [
            e["name"] for e in entities
            if e["type"] == "Subject"
        ],
        "chunks": counts[0],
        "concepts": counts[1],
        "links": counts[2]
    }


def process_uploaded_pdf(pdf_path):
    return process_uploaded_file(pdf_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python complete_graph_build.py <file_path>")
        sys.exit(1)

    try:
        result = process_uploaded_file(sys.argv[1])

        print("\nGraph construction completed.")
        print("Document ID:", result["document_id"])
        print("Subjects:", len(result["subjects"]))
        print("Chunks:", result["chunks"])
        print("Concepts:", result["concepts"])

        for subject in result["subjects"]:
            print("-", subject)

    finally:
        driver.close()
