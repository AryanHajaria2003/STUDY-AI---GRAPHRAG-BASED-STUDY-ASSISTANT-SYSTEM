from document_processing import process_pdf

document = process_pdf("data3/mca(syllabus).pdf")

for page in document["pages"]:
    if page["page_number"] in [8, 9, 10, 63, 64]:
        print(f"\n{'=' * 30} PAGE {page['page_number']} {'=' * 30}")
        print(page["text"])
        