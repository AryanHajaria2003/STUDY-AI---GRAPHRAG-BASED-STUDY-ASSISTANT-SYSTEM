
import os
import streamlit as st
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# Cloud credentials from Streamlit Secrets
# Local credentials from .env
try:
    URI = st.secrets["NEO4J_URI"]
    USERNAME = st.secrets["NEO4J_USERNAME"]
    PASSWORD = st.secrets["NEO4J_PASSWORD"]
except Exception:
    URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    PASSWORD = os.getenv("NEO4J_PASSWORD", "")

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
