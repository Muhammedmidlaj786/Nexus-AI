
import json
from pathlib import Path

import faiss
import numpy as np

from process_documents import process_pdf
from embeddings import model


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "employee_policy.pdf"
VECTOR_DIR = PROJECT_ROOT / "data" / "vector_store"

INDEX_PATH = VECTOR_DIR / "handbook.index"
METADATA_PATH = VECTOR_DIR / "chunks.json"


def create_vector_store():
    """Create and save embeddings for all document chunks."""

    chunks = process_pdf(str(DATA_PATH))

    texts = [chunk["text"] for chunk in chunks]

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    embeddings = np.asarray(embeddings, dtype="float32")

    # Create FAISS index
    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    # Create directory
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    # Save index
    faiss.write_index(index, str(INDEX_PATH))

    # Save metadata
    with open(METADATA_PATH, "w", encoding="utf-8") as file:
        json.dump(chunks, file, ensure_ascii=False, indent=4)

    print("Vector store created successfully!")
    print("Total vectors:", index.ntotal)


if __name__ == "__main__":
    create_vector_store()
