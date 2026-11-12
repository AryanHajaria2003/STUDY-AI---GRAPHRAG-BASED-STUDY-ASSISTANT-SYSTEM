from document_processing import process_pdf

result = process_pdf("data3/mca(syllabus).pdf")

print("Metadata:")
print(result["metadata"])

print("\nTotal pages processed:", len(result["pages"]))

print("\nFirst page text:")
print(result["pages"][0]["text"])