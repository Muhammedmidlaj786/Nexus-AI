
from document_loader import extract_text_from_pdf
from chunker import chunk_text


def process_pdf(pdf_path):
    documents = extract_text_from_pdf(pdf_path)

    all_chunks = []
    global_chunk_number = 1

    for document in documents:
        chunks = chunk_text(
            document["text"],
            chunk_size=500,
            overlap=100
        )

        for chunk in chunks:
            all_chunks.append({
                "chunk_id": global_chunk_number,
                "page": document["page"],
                "text": chunk
            })

            global_chunk_number += 1

    return all_chunks


if __name__ == "__main__":
    pdf_path = "data/raw/employee_policy.pdf"

    chunks = process_pdf(pdf_path)

    print("Total chunks created:", len(chunks))

    for chunk in chunks[:3]:
        print("\n--- Chunk ---")
        print("Chunk ID:", chunk["chunk_id"])
        print("Page:", chunk["page"])
        print(chunk["text"])
