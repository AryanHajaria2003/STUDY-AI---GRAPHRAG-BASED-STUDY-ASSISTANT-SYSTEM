
from .neo4j_connection import driver


def get_subjects(document_id):
    query = """
    MATCH (d:Document {document_id: $document_id})
          -[:CONTAINS]->(s:Subject)
    RETURN s.name AS subject
    ORDER BY subject
    """

    with driver.session() as session:
        return [
            record["subject"]
            for record in session.run(query, document_id=document_id)
        ]


def retrieve_subject(subject, document_id):
    query = """
    MATCH (d:Document {document_id: $document_id})
          -[:CONTAINS]->(s:Subject)
    WHERE toLower(s.name) = toLower($subject)

    OPTIONAL MATCH (s)-[:HAS_UNIT]->(u:Unit)
    OPTIONAL MATCH (u)-[:CONTAINS]->(t:Topic)
    OPTIONAL MATCH (t)-[:HAS_CONCEPT]->(c:Concept)
    OPTIONAL MATCH (c)-[:MENTIONED_IN]->(ch:Chunk)

    RETURN
        s.name AS subject,
        u.name AS unit,
        u.title AS unit_title,
        t.name AS topic,
        collect(DISTINCT c.name) AS concepts,
        collect(DISTINCT {
            text: ch.text,
            pages: ch.page_numbers
        }) AS chunks

    ORDER BY unit, topic
    """

    with driver.session() as session:
        records = list(session.run(
            query,
            subject=subject,
            document_id=document_id
        ))

    if not records:
        return None

    result = {
        "document_id": document_id,
        "subject": records[0]["subject"],
        "units": {}
    }

    for record in records:
        unit = record["unit"]

        if not unit:
            continue

        if unit not in result["units"]:
            result["units"][unit] = {
                "title": record["unit_title"],
                "topics": []
            }

        if record["topic"]:
            chunks = [
                chunk for chunk in record["chunks"]
                if chunk["text"]
            ]

            result["units"][unit]["topics"].append({
                "name": record["topic"],
                "concepts": [
                    concept for concept in record["concepts"]
                    if concept
                ],
                "chunks": chunks
            })

    return result


if __name__ == "__main__":
    try:
        document_id = input("Enter Document ID: ").strip()

        subjects = get_subjects(document_id)

        print("\nAvailable Subjects:")
        for subject in subjects:
            print("-", subject)

        selected = input("\nEnter subject name: ").strip()

        data = retrieve_subject(selected, document_id)

        if not data:
            print("Subject not found in this document.")
        else:
            print("\nRetrieved Subject:", data["subject"])

            for unit, details in data["units"].items():
                print(f"\n{unit}: {details['title'] or ''}")

                for topic in details["topics"]:
                    print("  Topic:", topic["name"])
                    print("  Concepts:", topic["concepts"])
                    print("  Source chunks:", len(topic["chunks"]))

    finally:
        driver.close()
