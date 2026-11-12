# Study AI – GraphRAG Based Study Assistant System

Study AI is an AI-powered study assistant that uses Graph Retrieval-Augmented Generation (GraphRAG) to generate personalized study plans from uploaded syllabuses.

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
│
├── Main.py
├── complete_graph_build.py
├── answer_generation.py
│
├── Backend/
├── tests/
├── utilities/
├── data3/
├── storage/
│
├── requirements.txt
├── .gitignore
└── README.md
```

## Installation

1. Clone the repository:

```bash
git clone https://github.com/AryanHajaria2003/STUDY-AI---GRAPHRAG-BASED-STUDY-ASSISTANT-SYSTEM.git
```

2. Open the project directory:

```bash
cd STUDY-AI---GRAPHRAG-BASED-STUDY-ASSISTANT-SYSTEM
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure your `.env` file with your Groq API key and Neo4j credentials.

5. Start the application:

```bash
streamlit run Main.py
```

## Requirements

- Python 3.12
- Neo4j Desktop
- Groq API Key
- Tesseract OCR

## Useful Links

- [GitHub Repository](https://github.com/AryanHajaria2003/STUDY-AI---GRAPHRAG-BASED-STUDY-ASSISTANT-SYSTEM)
- [Neo4j](https://neo4j.com/)
- [Groq](https://groq.com/)
- [Streamlit](https://streamlit.io/)
- [Python](https://www.python.org/)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)

## Author

**Aryan Hajaria**

---

*Study AI – GraphRAG Based Study Assistant System*
