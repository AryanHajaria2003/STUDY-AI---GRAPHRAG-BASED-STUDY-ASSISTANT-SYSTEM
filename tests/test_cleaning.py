from document_processing import clean_text

sample = "Hello     World\n\n\n\nThis is a test.\x00"

result = clean_text(sample)

print(result)
