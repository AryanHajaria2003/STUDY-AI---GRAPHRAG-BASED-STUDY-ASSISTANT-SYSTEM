
import pymupdf

doc = pymupdf.open("data3/mca(syllabus).pdf")

for page_number, page in enumerate(doc, start=1):
    text = page.get_text("text")

    if len(text.strip()) < 30:
        print(f"Page {page_number}: Possible scanned page")
    else:
        print(f"Page {page_number}: Text extracted")
        
print(doc.metadata)
print("Total pages:", len(doc))

