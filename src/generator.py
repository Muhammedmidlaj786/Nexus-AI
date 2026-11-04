import os
import re
from pathlib import Path

from dotenv import load_dotenv


# =========================================================
# LOAD ENVIRONMENT
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


# =========================================================
# MODEL CONFIGURATION
# =========================================================

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash",
).strip()

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile",
).strip()

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3.5-lightning:free",
).strip()


# =========================================================
# CLIENTS
# =========================================================

gemini_client = None
groq_client = None
openrouter_client = None

LAST_PROVIDER = "Not used"


# =========================================================
# GET LAST PROVIDER
# =========================================================

def get_last_provider():
    """Return the provider that generated the latest answer."""

    return LAST_PROVIDER


# =========================================================
# INITIALIZE API CLIENTS
# =========================================================

# Gemini
try:

    from google import genai

    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if gemini_api_key:

        gemini_client = genai.Client(
            api_key=gemini_api_key,
        )

except Exception as error:

    print("Gemini initialization failed:", error)


# Groq and OpenRouter use the OpenAI-compatible client.
try:

    from openai import OpenAI

    groq_api_key = os.getenv("GROQ_API_KEY")

    if groq_api_key:

        groq_client = OpenAI(
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    if openrouter_api_key:

        openrouter_client = OpenAI(
            api_key=openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )

except Exception as error:

    print(
        "OpenAI-compatible client initialization failed:",
        error,
    )


print(
    "Gemini configured:",
    bool(gemini_client and GEMINI_MODEL),
)

print(
    "Groq configured:",
    bool(groq_client and GROQ_MODEL),
)

print(
    "OpenRouter configured:",
    bool(openrouter_client and OPENROUTER_MODEL),
)


# =========================================================
# CONVERSATION HISTORY
# =========================================================

def build_conversation_context(conversation_history):
    """Convert recent conversation messages into readable context."""

    if not conversation_history:
        return "No previous conversation."

    recent_messages = conversation_history[-8:]

    lines = []

    for message in recent_messages:

        role = message.get("role", "")
        content = message.get("content", "").strip()

        if role not in ("user", "assistant") or not content:
            continue

        label = "User" if role == "user" else "Assistant"

        lines.append(
            f"{label}: {content}"
        )

    return "\n".join(lines) or "No previous conversation."


# =========================================================
# LOCAL EXTRACTIVE FALLBACK
# =========================================================

def extractive_answer(
    question,
    chunks,
    conversation_history=None,
):
    """
    Return the most relevant sentence(s) from retrieved chunks.

    This is a local fallback and does not call an LLM.
    """

    if not chunks:
        return "I couldn't find relevant information in the document."

    stop_words = {
        "the", "a", "an", "is", "are", "was", "were",
        "do", "does", "did", "what", "when", "where",
        "who", "how", "why", "can", "could", "should",
        "would", "will", "to", "of", "in", "on", "for",
        "and", "or", "with", "about", "my", "me", "we",
        "they", "their", "it", "this", "that", "i", "you",
        "from", "there", "then", "have", "has", "had",
        "please", "tell", "answer",
    }

    def tokenize(text):

        words = re.findall(
            r"\b[a-zA-Z0-9]+\b",
            text.lower(),
        )

        return {
            word
            for word in words
            if word not in stop_words
        }

    previous_user_questions = [
        message.get("content", "")
        for message in (conversation_history or [])
        if message.get("role") == "user"
    ]

    search_text = question

    # Use previous question to help with short follow-ups.
    if (
        previous_user_questions
        and len(tokenize(question)) <= 5
    ):

        search_text += " " + previous_user_questions[-1]

    question_words = tokenize(search_text)

    candidates = []

    for chunk in chunks:

        chunk_text = chunk.get("text", "")

        sentences = re.split(
            r"(?<=[.!?])\s+",
            chunk_text,
        )

        for sentence in sentences:

            sentence = sentence.strip()

            if not sentence:
                continue

            sentence_words = tokenize(sentence)

            if not sentence_words:
                continue

            overlap = question_words.intersection(
                sentence_words,
            )

            overlap_score = (
                len(overlap) / max(len(question_words), 1)
            )

            chunk_score = float(
                chunk.get("score", 0)
            )

            combined_score = (
                overlap_score * 0.8
                + chunk_score * 0.2
            )

            candidates.append(
                {
                    "sentence": sentence,
                    "score": combined_score,
                    "page": chunk.get("page", "?"),
                }
            )

    if not candidates:
        return "I couldn't find relevant information in the document."

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    best_candidate = candidates[0]

    # Avoid returning unrelated text.
    if best_candidate["score"] < 0.10:
        return "I couldn't find relevant information in the document."

    selected = [best_candidate]

    for candidate in candidates[1:]:

        if candidate["sentence"] == best_candidate["sentence"]:
            continue

        if candidate["score"] < max(
            best_candidate["score"] * 0.65,
            0.12,
        ):
            continue

        selected.append(candidate)
        break

    selected.sort(
        key=lambda item: str(item["page"]),
    )

    answer_text = " ".join(
        item["sentence"]
        for item in selected
    )

    source_pages = sorted(
        set(
            str(item["page"])
            for item in selected
        )
    )

    page_text = ", ".join(
        f"Page {page}"
        for page in source_pages
    )

    return (
        f"{answer_text}\n\n"
        f"Source: {page_text}\n"
        "Answer generated from retrieved document text."
    )


# =========================================================
# COMMON LLM GENERATION WITH FALLBACK
# =========================================================

def generate_with_fallback(
    question,
    retrieved_chunks,
    document_name,
    conversation_history=None,
):
    """
    Provider order:
        1. Gemini
        2. Groq
        3. OpenRouter
        4. Local extractive fallback
    """

    global LAST_PROVIDER

    LAST_PROVIDER = "Not used"

    if not retrieved_chunks:

        LAST_PROVIDER = "No relevant sources"

        return "I couldn't find relevant information in the document."

    # -----------------------------------------------------
    # PREPARE DOCUMENT CONTEXT
    # -----------------------------------------------------

    context = "\n\n".join(
        f"Page {chunk.get('page', '?')}:\n"
        f"{chunk.get('text', '')}"
        for chunk in retrieved_chunks
    )

    history_context = build_conversation_context(
        conversation_history,
    )

    # -----------------------------------------------------
    # PROMPT
    # -----------------------------------------------------

    prompt = f"""
You are an enterprise AI assistant answering questions from documents.

Use ONLY the document context provided below.

Rules:
- Do not invent or assume information.
- Do not use outside knowledge.
- Interpret follow-up questions using conversation history.
- If the document does not specify something, say so clearly.
- Give ONE clear, concise, direct answer.
- Do not provide multiple alternative answers.
- Cite the relevant page number immediately after factual claims.
- Use citations in this format: [Page 2].
- Only cite pages that support the claim.
- Do not list all retrieved pages automatically.
- If the answer is not supported by the context, state that it is not specified.

Conversation history:
{history_context}

Document name:
{document_name}

Document context:
{context}

Current user question:
{question}

Answer:
"""

    # -----------------------------------------------------
    # CONFIGURED PROVIDERS
    # -----------------------------------------------------

    providers = []

    if gemini_client and GEMINI_MODEL:
        providers.append(("Gemini", "gemini"))

    if groq_client and GROQ_MODEL:
        providers.append(("Groq", "groq"))

    if openrouter_client and OPENROUTER_MODEL:
        providers.append(("OpenRouter", "openrouter"))

    # -----------------------------------------------------
    # TRY EACH PROVIDER
    # -----------------------------------------------------

    for provider_name, provider_type in providers:

        try:

            print(
                f"Trying answer provider: {provider_name}"
            )

            if provider_type == "gemini":

                response = gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )

                answer = response.text

            elif provider_type == "groq":

                response = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    temperature=0.1,
                )

                answer = response.choices[0].message.content

            elif provider_type == "openrouter":

                response = openrouter_client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    temperature=0.1,
                )

                answer = response.choices[0].message.content

            else:
                continue

            if not answer or not answer.strip():

                raise ValueError(
                    f"{provider_name} returned an empty response."
                )

            LAST_PROVIDER = provider_name

            print(
                f"Answer generated by: {LAST_PROVIDER}"
            )

            return answer.strip()

        except Exception as error:

            print(
                f"{provider_name} failed:",
                error,
            )

    # -----------------------------------------------------
    # ALL APIs FAILED
    # -----------------------------------------------------

    print(
        "All APIs failed. Using local extractive fallback."
    )

    LAST_PROVIDER = "Local extractive fallback"

    return extractive_answer(
        question,
        retrieved_chunks,
        conversation_history,
    )


# =========================================================
# HANDBOOK ANSWER FUNCTION
# =========================================================

def generate_answer(
    question,
    retrieved_chunks=None,
    conversation_history=None,
    user_role="Employee",
    user_department="All",
):
    """
    Generate an answer using handbook chunks.

    If retrieved_chunks are provided by app.py, use them
    directly. They should already be permission-filtered.

    If retrieved_chunks is None, this function retrieves
    chunks using the supplied role and department.
    """

    if retrieved_chunks is None:

        from retriever import retrieve_documents

        retrieved_chunks = retrieve_documents(
            question,
            top_k=3,
            user_role=user_role,
            user_department=user_department,
        )

        # Apply relevance threshold only when retrieving here.
        retrieved_chunks = [
            chunk
            for chunk in retrieved_chunks
            if chunk.get("score", 0) >= 0.50
        ]

    return generate_with_fallback(
        question,
        retrieved_chunks,
        "Employee Handbook",
        conversation_history,
    )


# =========================================================
# UPLOADED DOCUMENT ANSWER FUNCTION
# =========================================================

def generate_answer_from_context(
    question,
    retrieved_chunks,
    document_name,
    conversation_history=None,
):
    """
    Generate an answer using chunks supplied by the app.

    Access control for uploaded documents must be enforced
    before these chunks are passed into this function.
    """

    return generate_with_fallback(
        question,
        retrieved_chunks,
        document_name,
        conversation_history,
    )


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    test_question = (
        "What are the expectations and rules "
        "for employees working remotely?"
    )

    answer = generate_answer(
        test_question,
        user_role="Employee",
        user_department="HR",
    )

    print("\nQuestion:", test_question)
    print("\nAnswer:", answer)
    print("\nProvider:", get_last_provider())