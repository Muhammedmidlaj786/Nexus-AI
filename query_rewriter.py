import re


FOLLOW_UP_PHRASES = [
    "what about",
    "how about",
    "and what",
    "what if",
    "does that",
    "is that",
    "can i",
    "what are its",
    "how does it",
    "what is the",
]


def rewrite_query(question, messages, max_history=4):
    """
    Expand a follow-up question using recent conversation history.
    This is a simple local heuristic, not an LLM-based rewrite.
    """

    question = question.strip()

    if not messages:
        return question

    recent_messages = messages[-max_history:]

    previous_user_questions = [
        message["content"]
        for message in recent_messages
        if message.get("role") == "user"
    ]

    if not previous_user_questions:
        return question

    question_lower = question.lower()

    is_follow_up = (
        len(question.split()) <= 10
        or any(phrase in question_lower for phrase in FOLLOW_UP_PHRASES)
    )

    if not is_follow_up:
        return question

    previous_context = " ".join(previous_user_questions)

    return f"{previous_context}. Follow-up question: {question}"