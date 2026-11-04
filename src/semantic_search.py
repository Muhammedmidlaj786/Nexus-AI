
from sentence_transformers import util

from process_documents import process_pdf
from embeddings import model


def semantic_search(query, chunks, top_k=3):
    """Find the most relevant document chunks for a query."""

    chunk_texts = [chunk["text"] for chunk in chunks]

    # Generate embeddings for all document chunks
    chunk_embeddings = model.encode(
        chunk_texts,
        convert_to_tensor=True
    )

    # Generate embedding for the user's question
    query_embedding = model.encode(
        query,
        convert_to_tensor=True
    )

    # Calculate cosine similarity
    scores = util.cos_sim(
        query_embedding,
        chunk_embeddings
    )[0]

    # Get the top matching chunks
    top_results = scores.argsort(descending=True)[:top_k]

    results = []

    for index in top_results:
        chunk = chunks[index.item()]

        results.append({
            "chunk_id": chunk["chunk_id"],
            "page": chunk["page"],
            "text": chunk["text"],
            "score": scores[index].item()
        })

    return results


if __name__ == "__main__":
    pdf_path = "data/raw/employee_policy.pdf"

    chunks = process_pdf(pdf_path)

    query = "How do I request time off?"

    results = semantic_search(query, chunks)

    print("\nQuestion:", query)

    for result in results:
        print("\n--- Search Result ---")
        print("Chunk ID:", result["chunk_id"])
        print("Page:", result["page"])
        print("Similarity:", round(result["score"], 4))
        print(result["text"])
