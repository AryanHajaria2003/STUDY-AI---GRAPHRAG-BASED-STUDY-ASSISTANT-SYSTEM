
from document_processing import process_pdf
from semantic_chunking import semantic_chunking

pdf_path = "data3/mca(syllabus).pdf"

# Process PDF
document = process_pdf(pdf_path)

# Generate semantic chunks
chunks = semantic_chunking(document["pages"])

print("Total pages:", len(document["pages"]))
print("Total chunks:", len(chunks))

# Display chunks containing unit information
for i, chunk in enumerate(chunks, start=1):
    text = chunk["text"]

    if "unit" in text.lower():
        print(f"\n--- Chunk {i} ---")
        print("Pages:", chunk["page_numbers"])
        print("Text:")
        print(text[:1000])
