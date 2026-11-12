
from document_processing import process_pdf
from entity_extraction import extract_entities


def extract_relationships(entities):
    relationships = []
    seen = set()

    for entity in entities:
        subject = entity.get("subject")
        unit = entity.get("unit")

        if entity["type"] == "Unit" and subject:
            relationship = {
                "source_type": "Subject",
                "source": subject,
                "relationship": "HAS_UNIT",
                "target_type": "Unit",
                "target": entity["name"],
                "subject": subject
            }

        elif entity["type"] == "Topic" and subject and unit:
            relationship = {
                "source_type": "Unit",
                "source": unit,
                "relationship": "CONTAINS",
                "target_type": "Topic",
                "target": entity["name"],
                "subject": subject
            }

        else:
            continue

        key = (
            relationship["subject"],
            relationship["source"],
            relationship["relationship"],
            relationship["target"]
        )

        if key not in seen:
            seen.add(key)
            relationships.append(relationship)

    return relationships


if __name__ == "__main__":
    document = process_pdf("data3/mca(syllabus).pdf")
    entities = extract_entities(document["pages"])

    relationships = extract_relationships(entities)

    print("Total entities:", len(entities))
    print("Total relationships:", len(relationships))

    for relationship in relationships[:20]:
        print(relationship)
