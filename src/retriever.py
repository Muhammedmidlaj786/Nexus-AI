import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


# =========================================================
# PATHS
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INDEX_PATH = PROJECT_ROOT / "data" / "vector_store" / "handbook.index"
METADATA_PATH = PROJECT_ROOT / "data" / "vector_store" / "chunks.json"


# =========================================================
# LOAD EMBEDDING MODEL
# =========================================================

model = SentenceTransformer("all-MiniLM-L6-v2")


# =========================================================
# LOAD FAISS INDEX
# =========================================================

if not INDEX_PATH.exists():
    raise FileNotFoundError(
        f"FAISS index not found: {INDEX_PATH}"
    )

index = faiss.read_index(str(INDEX_PATH))


# =========================================================
# LOAD CHUNK METADATA
# =========================================================

if not METADATA_PATH.exists():
    raise FileNotFoundError(
        f"Chunk metadata not found: {METADATA_PATH}"
    )

with open(METADATA_PATH, "r", encoding="utf-8") as file:
    chunks = json.load(file)


# =========================================================
# ACCESS CONTROL
# =========================================================

def can_access_chunk(
    chunk,
    user_role="Employee",
    user_department="All",
):
    """
    Determine whether a user can access a document chunk.

    Expected metadata:
        document_id
        department
        access_level

    Legacy chunks without permission metadata are Admin-only.
    """

    user_role = str(user_role or "Employee").strip().lower()
    user_department = str(user_department or "All").strip().lower()

    # Default legacy documents to Admin-only.
    access_level = str(
        chunk.get("access_level", "Admin")
    ).strip().lower()

    department = str(
        chunk.get("department", "Restricted")
    ).strip().lower()

    # Admins can access all documents.
    if user_role == "admin":
        return True

    # Admin-only documents are unavailable to employees.
    if access_level == "admin":
        return False

    # Unknown access levels should not be exposed.
    if access_level != "employee":
        return False

    # Documents assigned to All are shared with employees.
    if department == "all":
        return True

    # Department-specific access.
    return department == user_department


# =========================================================
# RETRIEVE DOCUMENTS
# =========================================================

def retrieve_documents(
    query,
    top_k=3,
    user_role="Employee",
    user_department="All",
):
    """
    Retrieve relevant chunks the current user is permitted
    to access.

    Access filtering is applied before returning chunk text.
    """

    if not query or not query.strip():
        return []

    if index.ntotal == 0:
        return []

    if top_k <= 0:
        return []

    # -----------------------------------------------------
    # CREATE QUERY EMBEDDING
    # -----------------------------------------------------

    query_embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype=np.float32,
    )

    # -----------------------------------------------------
    # SEARCH FAISS
    # -----------------------------------------------------
    # Search all vectors so unauthorized chunks do not push
    # relevant authorized chunks out of the search results.
    # -----------------------------------------------------

    search_count = index.ntotal

    scores, indices = index.search(
        query_embedding,
        search_count,
    )

    results = []

    # -----------------------------------------------------
    # FILTER RESULTS BY PERMISSION
    # -----------------------------------------------------

    for score, idx in zip(scores[0], indices[0]):

        if idx == -1:
            continue

        if idx < 0 or idx >= len(chunks):
            continue

        chunk = chunks[idx]

        # Permission check happens before chunk text is returned.
        if not can_access_chunk(
            chunk,
            user_role=user_role,
            user_department=user_department,
        ):
            continue

        results.append(
            {
                "score": float(score),
                "page": chunk.get("page"),
                "text": chunk.get("text", ""),
                "document_id": chunk.get("document_id"),
                "filename": chunk.get(
                    "filename",
                    "Employee Handbook",
                ),
                "department": chunk.get(
                    "department",
                    "Restricted",
                ),
                "access_level": chunk.get(
                    "access_level",
                    "Admin",
                ),
            }
        )

        if len(results) >= top_k:
            break

    return results


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    question = (
        "How many annual leave days, sick leave days, "
        "and holidays are provided to employees?"
    )

    results = retrieve_documents(
        question,
        top_k=3,
        user_role="Employee",
        user_department="HR",
    )

    for result in results:

        print("\nPage:", result["page"])
        print("Score:", result["score"])
        print("Document:", result["filename"])
        print("Department:", result["department"])
        print("Access level:", result["access_level"])
        print("Text:", result["text"])