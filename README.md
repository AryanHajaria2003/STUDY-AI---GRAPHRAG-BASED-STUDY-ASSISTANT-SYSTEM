# Study AI – GraphRAG Based Study Assistant System

Study AI is an AI-powered study assistant that uses Graph Retrieval-Augmented Generation (GraphRAG) to generate study plans from uploaded syllabuses.

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

## Tech Stack

- **Language:** Python
- **Frontend:** Streamlit
- **Graph Database:** Neo4j
- **LLM:** Groq API
- **OCR:** Tesseract
- **Document Processing:** PyMuPDF
- **Semantic Chunking:** Sentence Transformers

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
