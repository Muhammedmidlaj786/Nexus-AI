
import faiss
import numpy as np
from pathlib import Path

from process_documents import process_pdf
from embeddings import model


# =========================================================
# ACCESS CONTROL
# =========================================================

def can_access_chunk(chunk, user_role, user_department):
    """
    Check whether a user is permitted to retrieve a chunk.

    Metadata:
        document_id
        filename
        department
        access_level
    """

    user_role = str(user_role or "Employee").strip().lower()
    user_department = str(user_department or "All").strip().lower()

    # Missing metadata is treated as restricted.
    access_level = str(
        chunk.get("access_level", "Admin")
    ).strip().lower()

    department = str(
        chunk.get("department", "Restricted")
    ).strip().lower()

    # Admin can access all uploaded documents.
    if user_role == "admin":
        return True

    # Admin-only documents are unavailable to employees.
    if access_level == "admin":
        return False

    # Shared documents are available across departments.
    if department == "all":
        return True

    # Department-specific documents.
    return department == user_department


# =========================================================
# BUILD UPLOADED DOCUMENT STORE
# =========================================================

def build_uploaded_store(
    pdf_path,
    document_id=None,
    department="All",
    access_level="Employee",
):
    """
    Process an uploaded PDF and build an in-memory FAISS index.

    Permission metadata is added to every chunk before indexing.
    """

    # Validate access level.
    access_level = str(access_level).strip().title()

    if access_level not in {"Employee", "Admin"}:
        raise ValueError(
            "Invalid access level. Use 'Employee' or 'Admin'."
        )

    # Validate department.
    department = str(department or "All").strip()

    if not department:
        department = "All"

    # Extract and chunk the uploaded PDF.
    chunks = process_pdf(pdf_path)

    if not chunks:
        raise ValueError(
            "No readable text was found in this PDF."
        )

    filename = Path(pdf_path).name

    # Add document and permission metadata to each chunk.
    for chunk in chunks:
        chunk["document_id"] = document_id
        chunk["filename"] = filename
        chunk["department"] = department
        chunk["access_level"] = access_level

    # Generate embeddings.
    texts = [chunk["text"] for chunk in chunks]

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32,
    )

    # Build FAISS index.
    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    return index, chunks


# =========================================================
# RETRIEVE FROM UPLOADED DOCUMENT STORE
# =========================================================

def retrieve_from_uploaded_store(
    question,
    index,
    chunks,
    top_k=5,
    user_role="Employee",
    user_department="All",
    max_per_page=2,
):
    """
    Search an uploaded PDF's FAISS index.

    Only return chunks accessible to the current user.
    """

    if not question or not question.strip():
        return []

    if index is None or index.ntotal == 0:
        return []

    if not chunks:
        return []

    if top_k <= 0:
        return []

    # Generate query embedding.
    query_embedding = model.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype=np.float32,
    )

    # Search the entire index, then apply access filtering.
    # This prevents restricted chunks from occupying top_k slots.
    search_count = index.ntotal

    scores, indices = index.search(
        query_embedding,
        search_count,
    )

    results = []

    for score, idx in zip(scores[0], indices[0]):

        if idx == -1:
            continue

        if idx >= len(chunks):
            continue

        chunk = chunks[idx]

        # Enforce access control before returning text.
        if not can_access_chunk(
            chunk,
            user_role,
            user_department,
        ):
            continue

        results.append({
            "score": float(score),
            "page": chunk.get("page"),
            "text": chunk.get("text", ""),
            "document_id": chunk.get("document_id"),
            "filename": chunk.get("filename", "Unknown document"),
            "department": chunk.get("department", "Restricted"),
            "access_level": chunk.get("access_level", "Admin"),
        })

        if len(results) >= top_k:
            break

    return results
