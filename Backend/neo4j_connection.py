
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "123456789"

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)

def verify_connection():
    driver.verify_connectivity()
    print("Neo4j connection successful!")

if __name__ == "__main__":
    verify_connection()
    driver.close()
