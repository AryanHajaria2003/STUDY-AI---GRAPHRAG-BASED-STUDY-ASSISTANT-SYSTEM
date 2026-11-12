from neo4j_connection import driver


QUERIES = {
    "node_counts": """
        MATCH (n)
        RETURN labels(n) AS NodeType, count(n) AS Total
        ORDER BY NodeType
    """,
    "relationship_counts": """
        MATCH ()-[r]->()
        RETURN type(r) AS Relationship, count(r) AS Total
        ORDER BY Relationship
    """,
    "chunks_missing_document": """
        MATCH (ch:Chunk)
        WHERE NOT (:Document)-[:HAS_CHUNK]->(ch)
        RETURN count(ch) AS Total
    """,
    "concepts_missing_chunks": """
        MATCH (c:Concept)
        WHERE NOT (c)-[:MENTIONED_IN]->(:Chunk)
        RETURN count(c) AS Total
    """,
    "cross_scope_concept_chunk_links": """
        MATCH (c:Concept)-[:MENTIONED_IN]->(ch:Chunk)
        WHERE c.document_id <> ch.document_id
           OR c.subject_id <> ch.subject_id
           OR c.unit_id <> ch.unit_id
        RETURN count(*) AS InvalidLinks
    """,
    "cross_scope_topic_concept_links": """
        MATCH (t:Topic)-[:HAS_CONCEPT]->(c:Concept)
        WHERE c.document_id <> t.document_id
           OR c.subject_id <> t.subject_id
           OR c.unit_id <> t.unit_id
        RETURN count(*) AS InvalidLinks
    """,
    "sample_paths": """
        MATCH (s:Subject)-[:HAS_UNIT]->(u:Unit)
              -[:CONTAINS]->(t:Topic)
              -[:HAS_CONCEPT]->(c:Concept)
              -[:MENTIONED_IN]->(ch:Chunk)
        RETURN s.name AS Subject, u.name AS Unit, t.name AS Topic,
               c.name AS Concept, ch.page_numbers AS Pages,
               substring(ch.text, 0, 180) AS ChunkText
        LIMIT 20
    """,
}


def main():
    with driver.session() as session:
        for name, query in QUERIES.items():
            print(f"\\n--- {name} ---")
            for record in session.run(query):
                print(record.data())


if __name__ == "__main__":
    try:
        main()
    finally:
        driver.close()
