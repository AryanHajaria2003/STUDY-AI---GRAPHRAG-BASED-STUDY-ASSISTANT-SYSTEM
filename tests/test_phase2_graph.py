
import hashlib
import re
from pathlib import Path

import spacy

from document_processing import process_pdf
from semantic_chunking import semantic_chunking
from entity_extraction import extract_entities
from neo4j_connection import driver


PDF_PATH = "data3/mca(syllabus).pdf"


def normalize(text):
    return re.sub(r"\s+", " ", str(text)).strip().casefold()


def stable_id(*parts):
    value = "|".join(str(part) for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def clean_phrase(text):
    return re.sub(r"\s+", " ", text).strip(" \t.,:;()[]{}")


def canonicalize(phrase, nlp):
    doc = nlp(phrase)
    tokens = [
        token.lemma_.lower()
        for token in doc
        if not token.is_stop and not token.is_punct and not token.is_space
    ]
    return " ".join(tokens)


def valid_concept(phrase):
    words = phrase.split()

    if len(words) < 1 or len(words) > 6:
        return False

    if len(phrase) < 3 or len(phrase) > 80:
        return False

    if re.fullmatch(r"[\W\d_]+", phrase):
        return False

    if re.search(
        r"\b(ability to|students will|course will|this paper)\b",
        phrase,
        re.IGNORECASE
    ):
        return False

    return True


def extract_concepts(text, nlp):
    doc = nlp(text)
    concepts = {}

    for chunk in doc.noun_chunks:
        phrase = clean_phrase(chunk.text)

        if valid_concept(phrase):
            key = canonicalize(phrase, nlp)
            if key:
                concepts.setdefault(key, phrase)

    for entity in doc.ents:
        if entity.label_ in {"ORG", "PRODUCT", "WORK_OF_ART", "EVENT"}:
            phrase = clean_phrase(entity.text)

            if valid_concept(phrase):
                key = canonicalize(phrase, nlp)
                if key:
                    concepts.setdefault(key, phrase)

    return concepts


def main():
    pdf_path = Path(PDF_PATH).resolve()

    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        raise RuntimeError(
            "Install the spaCy model using:\n"
            "python -m spacy download en_core_web_sm"
        )

    document = process_pdf(str(pdf_path))
    chunks = semantic_chunking(document["pages"])
    entities = extract_entities(document["pages"])

    document_id = stable_id(str(pdf_path))

    concept_records = {}
    chunk_records = []

    # Generate exactly the same Chunk IDs as Phase 1.
    for index, chunk in enumerate(chunks, start=1):
        chunk_id = stable_id(
            document_id,
            "Chunk",
            index,
            normalize(chunk["text"])
        )

        chunk_records.append({
            "chunk_id": chunk_id,
            "text": chunk["text"],
            "pages": sorted(set(chunk.get("page_numbers", [])))
        })

        for canonical, name in extract_concepts(chunk["text"], nlp).items():
            concept_id = stable_id("Concept", canonical)

            record = concept_records.setdefault(concept_id, {
                "concept_id": concept_id,
                "name": name,
                "normalized_name": canonical,
                "chunk_ids": set(),
                "pages": set()
            })

            record["chunk_ids"].add(chunk_id)
            record["pages"].update(chunk.get("page_numbers", []))

    with driver.session() as session:

        # Confirm that Phase 1 graph exists.
        result = session.run("""
            MATCH (d:Document {document_id: $document_id})
            RETURN count(d) AS total
        """, document_id=document_id).single()

        if not result or result["total"] == 0:
            raise RuntimeError(
                "Phase 1 graph not found. Run complete_graph_build.py first."
            )

        # Remove old placeholder concepts and rebuild Topic links.
        session.run("""
            MATCH (c:Concept {extraction_method: 'topic_seed'})
            DETACH DELETE c
        """)

        session.run("""
            MATCH (:Topic)-[r:HAS_CONCEPT]->(:Concept)
            DELETE r
        """)

        # Create normalized Concept nodes.
        for record in concept_records.values():
            session.run("""
                MERGE (c:Concept {concept_id: $concept_id})
                SET c.name = $name,
                    c.normalized_name = $normalized_name,
                    c.extraction_method = 'spacy_noun_phrase',
                    c.page_numbers = $pages
            """,
                concept_id=record["concept_id"],
                name=record["name"],
                normalized_name=record["normalized_name"],
                pages=sorted(record["pages"])
            )

            # Connect Concept to the existing Chunk nodes.
            for chunk_id in record["chunk_ids"]:
                session.run("""
                    MATCH (c:Concept {concept_id: $concept_id})
                    MATCH (ch:Chunk {chunk_id: $chunk_id})
                    MERGE (c)-[:MENTIONED_IN]->(ch)
                """,
                    concept_id=record["concept_id"],
                    chunk_id=chunk_id
                )

        # Connect Topics to concepts found in their source chunks.
        topic_links = 0

        for entity in entities:
            if entity["type"] != "Topic":
                continue

            subject = entity.get("subject")
            unit = entity.get("unit")
            topic_name = clean_phrase(entity["name"])

            if not subject or not unit or not topic_name:
                continue

            # Match the exact Topic ID format used in Phase 1.
            topic_id = stable_id(
                document_id,
                subject,
                unit,
                "Topic",
                normalize(topic_name)
            )

            for chunk in chunk_records:
                if topic_name.casefold() not in chunk["text"].casefold():
                    continue

                # Only connect concepts actually mentioned in this chunk.
                for record in concept_records.values():
                    if chunk["chunk_id"] not in record["chunk_ids"]:
                        continue

                    session.run("""
                        MATCH (t:Topic {topic_id: $topic_id})
                        MATCH (c:Concept {concept_id: $concept_id})
                        MERGE (t)-[:HAS_CONCEPT]->(c)
                    """,
                        topic_id=topic_id,
                        concept_id=record["concept_id"]
                    )

                    topic_links += 1

    print("Phase 2 enrichment completed.")
    print("Concepts extracted:", len(concept_records))
    print("Concept-to-chunk links:", sum(
        len(record["chunk_ids"])
        for record in concept_records.values()
    ))
    print("Topic-to-concept links:", topic_links)


if __name__ == "__main__":
    try:
        main()
    finally:
        driver.close()
