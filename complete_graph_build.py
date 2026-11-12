
import hashlib
import re
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


def normalize(value):
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def stable_id(*parts):
    raw = "|".join(normalize(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
    words = [
        re.escape(word)
        for word in normalize(phrase).split()
    ]

    if not words:
        return False

    pattern = r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)"
    return re.search(pattern, normalize(text)) is not None


def create_constraints(session):
    queries = [
        "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (n:Document) REQUIRE n.document_id IS UNIQUE",
        "CREATE CONSTRAINT subject_id_unique IF NOT EXISTS FOR (n:Subject) REQUIRE n.subject_id IS UNIQUE",
        "CREATE CONSTRAINT unit_id_unique IF NOT EXISTS FOR (n:Unit) REQUIRE n.unit_id IS UNIQUE",
        "CREATE CONSTRAINT topic_id_unique IF NOT EXISTS FOR (n:Topic) REQUIRE n.topic_id IS UNIQUE",
        "CREATE CONSTRAINT concept_id_unique IF NOT EXISTS FOR (n:Concept) REQUIRE n.concept_id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (n:Chunk) REQUIRE n.chunk_id IS UNIQUE"
    ]

    for query in queries:
        session.run(query)


def clear_document_graph(tx, document_id):
    tx.run("""
        MATCH (n)
        WHERE n.document_id = $document_id
        DETACH DELETE n
    """, document_id=document_id)


def construct_graph(tx, metadata, entities, pages):
    document_id = metadata["document_id"]
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
    )

    subject_ids = {}
    unit_ids = {}
    topic_records = []

    for entity in entities:
        if entity["type"] != "Subject":
            continue

        name = entity["name"]
        subject_id = stable_id(document_id, "Subject", name)
        subject_ids[normalize(name)] = subject_id

        tx.run("""
            MATCH (d:Document {document_id: $doc})
            MERGE (s:Subject {subject_id: $id})
            SET s.name = $name,
                s.code = $code,
                s.page_numbers = $pages,
                s.document_id = $doc
            MERGE (d)-[:CONTAINS]->(s)
        """,
            doc=document_id,
            id=subject_id,
            name=name,
            code=entity.get("code"),
            pages=entity_pages(entity)
        )

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

        tx.run("""
            MATCH (s:Subject {subject_id: $subject_id})
            MERGE (u:Unit {unit_id: $unit_id})
            SET u.name = $name,
                u.title = $title,
                u.page_numbers = $pages,
                u.document_id = $doc
            MERGE (s)-[:HAS_UNIT]->(u)
        """,
            subject_id=subject_id,
            unit_id=unit_id,
            name=unit_name,
            title=entity.get("title"),
            pages=entity_pages(entity),
            doc=document_id
        )

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

        topic = {
            "id": topic_id,
            "name": entity["name"],
            "subject_id": subject_id,
            "unit_id": unit_id,
            "pages": entity_pages(entity)
        }

        topic_records.append(topic)

        tx.run("""
            MATCH (u:Unit {unit_id: $unit_id})
            MERGE (t:Topic {topic_id: $topic_id})
            SET t.name = $name,
                t.page_numbers = $pages,
                t.document_id = $doc,
                t.subject_id = $subject_id,
                t.unit_id = $unit_id
            MERGE (u)-[:CONTAINS]->(t)
        """,
            unit_id=unit_id,
            topic_id=topic_id,
            name=entity["name"],
            pages=topic["pages"],
            doc=document_id,
            subject_id=subject_id
        )

    chunk_records = []
    chunk_count = 0

    for key, section in sections.items():
        unit_id = unit_ids.get(key)
        subject_id = subject_ids.get(key[0])

        if not unit_id or not subject_id:
            continue

        chunks = semantic_chunking(section["pages"])

        for index, chunk in enumerate(chunks, start=1):
            text = chunk["text"]
            chunk_pages = sorted(set(chunk.get("page_numbers", [])))

            chunk_id = stable_id(
                document_id, key[0], key[1],
                "Chunk", index, normalize(text)
            )

            tx.run("""
                MATCH (d:Document {document_id: $doc})
                MERGE (ch:Chunk {chunk_id: $id})
                SET ch.text = $text,
                    ch.page_numbers = $pages,
                    ch.chunk_index = $index,
                    ch.subject_id = $subject_id,
                    ch.unit_id = $unit_id,
                    ch.document_id = $doc
                MERGE (d)-[:HAS_CHUNK]->(ch)
            """,
                doc=document_id,
                id=chunk_id,
                text=text,
                pages=chunk_pages,
                index=index,
                subject_id=subject_id,
                unit_id=unit_id
            )

            chunk_records.append({
                "id": chunk_id,
                "text": text,
                "pages": set(chunk_pages),
                "subject_id": subject_id,
                "unit_id": unit_id
            })

            chunk_count += 1

    concept_count = 0
    link_count = 0

    for topic in topic_records:
        for canonical, display_name in concept_candidates(topic["name"]):

            matching_chunks = [
                chunk for chunk in chunk_records
                if chunk["subject_id"] == topic["subject_id"]
                and chunk["unit_id"] == topic["unit_id"]
                and chunk["pages"] & set(topic["pages"])
                and phrase_in_text(display_name, chunk["text"])
            ]

            if not matching_chunks:
                continue

            concept_id = stable_id(
                document_id, topic["id"], "Concept", canonical
            )

            tx.run("""
                MATCH (t:Topic {topic_id: $topic_id})
                MERGE (c:Concept {concept_id: $concept_id})
                SET c.name = $name,
                    c.normalized_name = $normalized,
                    c.document_id = $doc,
                    c.subject_id = $subject_id,
                    c.unit_id = $unit_id,
                    c.topic_id = $topic_id,
                    c.extraction_method = 'topic_phrase'
                MERGE (t)-[:HAS_CONCEPT]->(c)
            """,
                topic_id=topic["id"],
                concept_id=concept_id,
                name=display_name,
                normalized=canonical,
                doc=document_id,
                subject_id=topic["subject_id"],
                unit_id=topic["unit_id"]
            )

            concept_count += 1

            for chunk in matching_chunks:
                tx.run("""
                    MATCH (c:Concept {concept_id: $concept_id})
                    MATCH (ch:Chunk {chunk_id: $chunk_id})
                    MERGE (c)-[:MENTIONED_IN]->(ch)
                """,
                    concept_id=concept_id,
                    chunk_id=chunk["id"]
                )

                link_count += 1

    return chunk_count, concept_count, link_count


def process_uploaded_file(file_path):
    file_path = Path(file_path).resolve()

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    if file_path.suffix.lower() not in {
        ".pdf", ".png", ".jpg", ".jpeg"
    }:
        raise ValueError("Only PDF, PNG and JPG files are supported.")

    print(f"Processing: {file_path.name}")

    document = process_document(file_path)
    pages = document["pages"]
    entities = extract_entities(pages)

    document_id = stable_id(str(file_path))
    metadata = document["metadata"]
    metadata["document_id"] = document_id

    if not any(e["type"] == "Subject" for e in entities):
        raise ValueError(
            "No subjects found. Check whether the uploaded syllabus "
            "contains recognizable Paper headings."
        )

    with driver.session() as session:
        create_constraints(session)

        session.execute_write(
            clear_document_graph, document_id
        )

        counts = session.execute_write(
            construct_graph, metadata, entities, pages
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
