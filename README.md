# Study AI – GraphRAG Based Study Assistant System

Study AI is an AI-powered study assistant that uses **Graph Retrieval-Augmented Generation (GraphRAG)** to generate personalized study plans from uploaded syllabuses.

## Features

- Upload syllabus documents in PDF or image format.
- Extract text using OCR and document processing.
- Create semantic chunks from extracted content.
- Build a knowledge graph using Neo4j.
- Retrieve syllabus information using graph-based retrieval.
- Generate study plans using Groq LLM.

## Study Plan Includes

1. Suggested Prerequisites
2. Learning Roadmap
3. Important Topics

## Technology Stack

| Category | Technology | Purpose |
|---|---|---|
| Programming Language | Python 3.12 | Core development and backend implementation |
| Frontend Framework | Streamlit | Interactive user interface and syllabus upload |
| Graph Database | Neo4j | Knowledge graph storage and relationship management |
| Query Language | Cypher | Querying and retrieving graph data |
| Large Language Model | Groq API | AI-powered study plan generation |
| OCR Engine | Tesseract OCR | Extracting text from syllabus images and scanned PDFs |
| PDF Processing | PyMuPDF | Extracting and processing text from PDF documents |
| Semantic Chunking | Sentence Transformers | Generating semantic embeddings and supporting meaningful text segmentation |
| Graph Retrieval | GraphRAG | Context-aware retrieval using knowledge graph relationships |
| Environment Management | Python Virtual Environment | Managing project dependencies |
| Configuration Management | Python dotenv | Managing API keys and environment variables |

## Project Structure

```text
Graph_RG/
├── Main.py
├── complete_graph_build.py
├── answer_generation.py
├── Backend/
├── tests/
├── utilities/
├── data3/
├── storage/
├── requirements.txt
├── .gitignore
└── README.md
```

## Installation

1. Clone the repository.

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure your `.env` file with your Groq API key and Neo4j credentials.

4. Start the application:

```bash
streamlit run Main.py
```

## Requirements

- Python 3.12
- Neo4j Desktop
- Groq API Key
- Tesseract OCR

## Live Application

**[Open Study AI](https://study-ai---graphrag-based-study-assistant-system-aryan-hajaria.streamlit.app/)**

## Author

**Aryan Hajaria**

---

*Study AI – GraphRAG Based Study Assistant System*
