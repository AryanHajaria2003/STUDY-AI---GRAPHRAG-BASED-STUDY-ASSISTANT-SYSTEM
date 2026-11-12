import pymupdf
from document_processing import extract_metadata

doc = pymupdf.open("data3/mca(syllabus).pdf")

metadata = extract_metadata(doc, "mca(syllabus).pdf")

print(metadata)

doc.close()
