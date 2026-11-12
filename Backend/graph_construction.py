
import hashlib
from pathlib import Path

from document_processing import process_pdf
from entity_extraction import extract_entities
from relationship_extraction import extract_relationships
from neo4j_connection import driver


PDF_PATH = "data3/mca(syllabus).pdf"


def make_id(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build_graph(tx, metadata, entities, relationships):
    document_id = metadata["document_id"]

    # Create Document
    tx.run("""
        MERGE (d:Document {document_id: $id})
        SET d.filename = $filename,
            d.title = $title,
            d.total_pages = $pages
    """,
        id=document_id,
        filename=metadata["filename"],
        title=metadata["title"],
        pages=metadata["total_pages"]
    )

    subject_ids = {}
    unit_ids = {}

    # Create Subject, Unit and Topic nodes
    for entity in entities:
        entity_type = entity["type"]
        name = entity["name"]
        subject = entity.get("subject")
        unit = entity.get("unit")

        if entity_type == "Subject":
            node_id = make_id(f"{document_id}:Subject:{name}")
            subject_ids[name] = node_id

            tx.run("""
                MATCH (d:Document {document_id: $doc_id})
                MERGE (s:Subject {subject_id: $id})
                SET s.name = $name
                MERGE (d)-[:CONTAINS]->(s)
            """, doc_id=document_id, id=node_id, name=name)

        elif entity_type == "Unit" and subject:
            subject_id = subject_ids.get(subject)

            if not subject_id:
                continue

            node_id = make_id(
                f"{document_id}:{subject}:Unit:{name}"
            )
            unit_ids[(subject, name)] = node_id

            tx.run("""
                MATCH (s:Subject {subject_id: $subject_id})
                MERGE (u:Unit {unit_id: $id})
                SET u.name = $name,
                    u.title = $title
                MERGE (s)-[:HAS_UNIT]->(u)
            """,
                subject_id=subject_id,
                id=node_id,
                name=name,
                title=entity.get("title")
            )

        elif entity_type == "Topic" and subject and unit:
            unit_id = unit_ids.get((subject, unit))

            if not unit_id:
                continue

            node_id = make_id(
                f"{document_id}:{subject}:{unit}:Topic:{name}"
            )

            tx.run("""
                MATCH (u:Unit {unit_id: $unit_id})
                MERGE (t:Topic {topic_id: $id})
                SET t.name = $name
                MERGE (u)-[:CONTAINS]->(t)
            """,
                unit_id=unit_id,
                id=node_id,
                name=name
            )

    print("Graph construction completed.")


if __name__ == "__main__":
    document = process_pdf(PDF_PATH)
    entities = extract_entities(document["pages"])
    relationships = extract_relationships(entities)

    # Use a stable ID so rerunning does not duplicate the document.
    document["metadata"]["document_id"] = make_id(
        str(Path(PDF_PATH).resolve())
    )

    with driver.session() as session:
        session.execute_write(
            build_graph,
            document["metadata"],
            entities,
            relationships
        )

    print("Entities processed:", len(entities))
    print("Relationships extracted:", len(relationships))

    driver.close()
