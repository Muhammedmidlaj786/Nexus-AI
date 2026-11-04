
import re


# Detect numbered handbook headings, such as:
# 5. Remote Work, Hybrid Work, and Office Conduct
# 5.2 Remote-work expectations
SECTION_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)*\.?)\s+(.+?)\s*$",
    re.MULTILINE
)


def split_into_sections(text):
    """
    Split document text using numbered section headings.
    Ignore short heading-only fragments, such as table-of-contents entries.
    """

    matches = list(SECTION_PATTERN.finditer(text))

    if not matches:
        return [text.strip()] if text.strip() else []

    sections = []

    # Preserve text before the first heading, if it contains enough content.
    preamble = text[:matches[0].start()].strip()

    if len(preamble.split()) >= 20:
        sections.append(preamble)

    for i, match in enumerate(matches):
        start = match.start()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        section = text[start:end].strip()

        # Skip short fragments, usually table-of-contents entries.
        if len(section.split()) >= 20:
            sections.append(section)

    return sections


def chunk_text(text, chunk_size=500, overlap=100):
    """
    Split text into topic-based sections.
    Split long sections into smaller overlapping chunks.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size - 1")

    sections = split_into_sections(text)

    chunks = []
    step = chunk_size - overlap

    for section in sections:
        words = section.split()

        if len(words) <= chunk_size:
            chunks.append(" ".join(words))
            continue

        start = 0

        while start < len(words):
            end = start + chunk_size
            chunk = " ".join(words[start:end])

            chunks.append(chunk)

            if end >= len(words):
                break

            start += step

    return chunks


if __name__ == "__main__":
    sample_text = """
    5. Remote Work, Hybrid Work, and Office Conduct
    This is a sample introductory paragraph with enough words to
    demonstrate section-aware chunking and how the content is grouped.

    5.1 Eligibility and approval
    Employees must obtain approval through the designated process
    and follow the agreed work location and schedule.

    5.2 Remote-work expectations
    Employees working remotely should maintain a suitable work
    environment and protect confidential information.
    """

    chunks = chunk_text(sample_text, chunk_size=30, overlap=5)

    for i, chunk in enumerate(chunks, start=1):
        print(f"\nChunk {i}:")
        print(chunk)
