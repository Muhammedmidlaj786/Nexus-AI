
import fitz  # PyMuPDF
from pathlib import Path


def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF and return it page by page."""

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    documents = []

    with fitz.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf)}")

        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()

            if not text:
                print(f"Warning: Page {page_number} contains no extractable text.")
                continue

            documents.append({
                "page": page_number,
                "text": text
            })

    return documents


if __name__ == "__main__":
    pdf_path = "data/raw/employee_policy.pdf"

    documents = extract_text_from_pdf(pdf_path)

    print(f"\nSuccessfully extracted {len(documents)} pages.")

    for document in documents:
        print(f"\n--- Page {document['page']} ---")
        print(document["text"][:500])
