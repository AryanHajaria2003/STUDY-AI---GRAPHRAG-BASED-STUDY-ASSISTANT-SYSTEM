
import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer("all-MiniLM-L6-v2")


def split_long_text(text, max_words):
    words = text.split()
    return [
        " ".join(words[i:i + max_words])
        for i in range(0, len(words), max_words)
    ]


def semantic_chunking(pages, threshold=0.50, min_words=80, max_words=250):
    segments = []

    # Extract sentences and preserve page numbers
    for page in pages:
        text = page["text"].strip()

        if not text:
            continue

        sentences = re.split(r'(?<=[.!?])\s+', text)

        for sentence in sentences:
            sentence = sentence.strip()

            if not sentence:
                continue

            # Split unusually long sentences
            parts = split_long_text(sentence, max_words)

            for part in parts:
                segments.append({
                    "text": part,
                    "page": page["page_number"]
                })

    if not segments:
        return []

    # Generate embeddings for all segments
    texts = [segment["text"] for segment in segments]
    embeddings = model.encode(texts)

    chunks = []
    current_text = []
    current_pages = set()
    current_words = 0

    def save_chunk():
        nonlocal current_text, current_pages, current_words

        if current_text:
            chunks.append({
                "text": " ".join(current_text),
                "page_numbers": sorted(current_pages)
            })

        current_text = []
        current_pages = set()
        current_words = 0

    # Group semantically related segments
    for i, segment in enumerate(segments):
        text = segment["text"]
        word_count = len(text.split())

        if current_text:
            similarity = cosine_similarity(
                [embeddings[i - 1]],
                [embeddings[i]]
            )[0][0]

            topic_changed = similarity < threshold
            size_exceeded = current_words + word_count > max_words

            if size_exceeded or (
                topic_changed and current_words >= min_words
            ):
                save_chunk()

        current_text.append(text)
        current_pages.add(segment["page"])
        current_words += word_count

    save_chunk()

    # Merge small chunks with an adjacent chunk when possible
    i = 0

    while i < len(chunks):
        word_count = len(chunks[i]["text"].split())

        if word_count < min_words and len(chunks) > 1:
            if i > 0:
                previous_words = len(chunks[i - 1]["text"].split())

                if previous_words + word_count <= max_words:
                    chunks[i - 1]["text"] += " " + chunks[i]["text"]
                    chunks[i - 1]["page_numbers"] = sorted(
                        set(chunks[i - 1]["page_numbers"] +
                            chunks[i]["page_numbers"])
                    )
                    chunks.pop(i)
                    continue

            if i + 1 < len(chunks):
                next_words = len(chunks[i + 1]["text"].split())

                if next_words + word_count <= max_words:
                    chunks[i + 1]["text"] = (
                        chunks[i]["text"] + " " + chunks[i + 1]["text"]
                    )
                    chunks[i + 1]["page_numbers"] = sorted(
                        set(chunks[i]["page_numbers"] +
                            chunks[i + 1]["page_numbers"])
                    )
                    chunks.pop(i)
                    continue

        i += 1

    return chunks


if __name__ == "__main__":
    from document_processing import process_pdf

    document = process_pdf("data3/mca(syllabus).pdf")
    chunks = semantic_chunking(document["pages"])

    print("Total pages:", len(document["pages"]))
    print("Total chunks:", len(chunks))

    for i, chunk in enumerate(chunks[:10], start=1):
        print(f"\nChunk {i}")
        print("Pages:", chunk["page_numbers"])
        print("Word count:", len(chunk["text"].split()))
        print("Text:", chunk["text"][:300])
