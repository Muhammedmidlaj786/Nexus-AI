import sys
import re
import tempfile
import uuid
from pathlib import Path

import streamlit as st


# =========================================================
# PROJECT PATH
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


# =========================================================
# IMPORT PROJECT MODULES
# =========================================================

from retriever import retrieve_documents

from generator import (
    generate_answer,
    generate_answer_from_context,
    extractive_answer,
    get_last_provider,
)

from uploaded_document_store import (
    build_uploaded_store,
    retrieve_from_uploaded_store,
)

from query_rewriter import rewrite_query

from auth import (
    initialize_auth_state,
    show_auth_page,
    logout,
    show_admin_user_management,
    show_admin_audit_logs,
)

from admin_panel import show_admin_panel


# =========================================================
# STREAMLIT CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Nexus AI | Knowledge Assistant",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CUSTOM UI
# =========================================================

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: Inter, -apple-system, BlinkMacSystemFont,
                     "Segoe UI", sans-serif;
    }

    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2rem;
        max-width: 1250px;
    }

    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(128,128,128,0.20);
    }

    section[data-testid="stSidebar"] > div {
        padding-top: 1.5rem;
    }

    .brand-title {
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: -0.8px;
        margin-bottom: 0;
    }

    .brand-accent {
        color: #8B5CF6;
    }

    .brand-caption {
        opacity: 0.65;
        font-size: 0.85rem;
        margin-top: 0.15rem;
    }

    .main-heading {
        font-size: 2.4rem;
        font-weight: 800;
        letter-spacing: -1.2px;
        line-height: 1.15;
        margin-bottom: 0.5rem;
    }

    .main-subheading {
        opacity: 0.7;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }

    div[data-testid="stChatMessage"] {
        border-radius: 18px;
        padding: 1rem 1.1rem;
    }

    div[data-testid="stChatInput"] {
        border-radius: 18px;
    }

    .stButton > button {
        border-radius: 12px;
        min-height: 2.6rem;
        transition: all 0.15s ease;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px;
    }

    .status-ready {
        color: #10B981;
        font-weight: 600;
    }

    .small-muted {
        opacity: 0.65;
        font-size: 0.82rem;
    }

    [data-testid="stDecoration"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# INITIALIZE AUTHENTICATION
# =========================================================

initialize_auth_state()

if not st.session_state.get("authenticated", False):
    show_auth_page()
    st.stop()


# =========================================================
# CURRENT USER
# =========================================================

current_user = st.session_state.current_user

user_name = current_user.get("full_name", "User")
user_email = current_user.get("email", "")
user_role = current_user.get("role", "Employee")
user_department = current_user.get("department", "All")

# Normalize values
user_role = str(user_role).strip().title()
user_department = str(user_department).strip()

if not user_department:
    user_department = "All"


# =========================================================
# SESSION STATE
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "uploaded_index" not in st.session_state:
    st.session_state.uploaded_index = None

if "uploaded_chunks" not in st.session_state:
    st.session_state.uploaded_chunks = None

if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None

if "uploaded_document_id" not in st.session_state:
    st.session_state.uploaded_document_id = None

if "uploaded_department" not in st.session_state:
    st.session_state.uploaded_department = None

if "uploaded_access_level" not in st.session_state:
    st.session_state.uploaded_access_level = None

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        """
        <div class="brand-title">
            Nexus <span class="brand-accent">AI</span>
        </div>
        <div class="brand-caption">
            Enterprise Knowledge Assistant
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown("### Workspace")

    if st.button("＋ New conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    st.markdown("### Knowledge source")

    # Admins can choose document classification.
    if user_role == "Admin":

        upload_department = st.selectbox(
            "Document department",
            [
                "All",
                "HR",
                "Finance",
                "IT",
                "Engineering",
                "Sales",
                "Operations",
                "Management",
            ],
            help="Choose which department can access this document.",
        )

        upload_access_level = st.selectbox(
            "Access level",
            ["Employee", "Admin"],
            help=(
                "Employee documents can be accessed by eligible employees. "
                "Admin documents are restricted to administrators."
            ),
        )

    else:
        # Employees cannot select their own access classification.
        upload_department = user_department
        upload_access_level = "Employee"

        st.caption(f"Department: {user_department}")
        st.caption("Access level: Employee")

    uploaded_file = st.file_uploader(
        "Upload a PDF",
        type=["pdf"],
        help="Upload a PDF to query its contents.",
    )

    if st.session_state.uploaded_file_name:

        st.success(
            f"Active document: {st.session_state.uploaded_file_name}"
        )

        st.caption(
            f"Department: {st.session_state.uploaded_department}"
        )

        st.caption(
            f"Access level: {st.session_state.uploaded_access_level}"
        )

        if st.button(
            "Remove uploaded document",
            use_container_width=True,
        ):
            st.session_state.uploaded_index = None
            st.session_state.uploaded_chunks = None
            st.session_state.uploaded_file_name = None
            st.session_state.uploaded_document_id = None
            st.session_state.uploaded_department = None
            st.session_state.uploaded_access_level = None
            st.session_state.messages = []
            st.rerun()

    st.divider()

    st.markdown("### Account")
    st.markdown(f"**{user_name}**")
    st.caption(user_email)
    st.caption(f"Role: {user_role}")
    st.caption(f"Department: {user_department}")

    if user_role == "Admin":

        st.divider()
        st.markdown("### Administration")

        admin_page = st.radio(
            "Admin tools",
            [
                "Knowledge Chat",
                "Admin Panel",
                "User Management",
                "Audit Logs",
            ],
            label_visibility="collapsed",
        )

    else:
        admin_page = "Knowledge Chat"

    st.divider()

    if st.button("Log out", use_container_width=True):
        logout()
        st.rerun()


# =========================================================
# PROCESS UPLOADED PDF
# =========================================================

if uploaded_file is not None:

    should_process = (
        st.session_state.uploaded_file_name != uploaded_file.name
        or st.session_state.uploaded_department != upload_department
        or st.session_state.uploaded_access_level != upload_access_level
    )

    if should_process:

        temp_pdf_path = None

        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf",
            ) as temp_file:

                temp_file.write(uploaded_file.getvalue())
                temp_pdf_path = temp_file.name

            document_id = str(uuid.uuid4())

            with st.spinner("Processing uploaded PDF..."):

                index, chunks = build_uploaded_store(
                    temp_pdf_path,
                    document_id=document_id,
                    department=upload_department,
                    access_level=upload_access_level,
                )

            st.session_state.uploaded_index = index
            st.session_state.uploaded_chunks = chunks
            st.session_state.uploaded_file_name = uploaded_file.name
            st.session_state.uploaded_document_id = document_id
            st.session_state.uploaded_department = upload_department
            st.session_state.uploaded_access_level = upload_access_level

            st.session_state.messages = []

            st.success(
                f"Processed {uploaded_file.name} — "
                f"{len(chunks)} chunks created."
            )

        except Exception as error:

            st.error("Could not process this PDF.")
            st.exception(error)

        finally:

            if temp_pdf_path and Path(temp_pdf_path).exists():
                try:
                    Path(temp_pdf_path).unlink()
                except OSError:
                    pass


# =========================================================
# ADMIN PAGES
# =========================================================

if user_role == "Admin" and admin_page == "Admin Panel":

    st.markdown(
        '<div class="main-heading">Admin Panel</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subheading">'
        'Manage your Nexus AI workspace.'
        '</div>',
        unsafe_allow_html=True,
    )

    show_admin_panel()
    st.stop()


if user_role == "Admin" and admin_page == "User Management":

    st.markdown(
        '<div class="main-heading">User management</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subheading">'
        'Manage workspace users and their roles.'
        '</div>',
        unsafe_allow_html=True,
    )

    show_admin_user_management()
    st.stop()


if user_role == "Admin" and admin_page == "Audit Logs":

    st.markdown(
        '<div class="main-heading">Audit logs</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subheading">'
        'Review recent user and account activity.'
        '</div>',
        unsafe_allow_html=True,
    )

    show_admin_audit_logs()
    st.stop()


# =========================================================
# MAIN CHAT HEADER
# =========================================================

st.markdown(
    """
    <div class="main-heading">
        Your company knowledge,
        <br>
        <span class="brand-accent">one conversation away.</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="main-subheading">
        Ask questions and get answers grounded in your documents.
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SPLIT MULTIPLE QUESTIONS
# =========================================================

def split_questions(text):

    """
    Split a message into individual questions using new lines.

    Also supports:
    1. First question
    2. Second question
    """

    questions = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        # Remove numbered lists and bullet points.
        line = re.sub(
            r"^\s*(?:\d+[.)]\s*|[-*]\s*)",
            "",
            line,
        ).strip()

        if line:
            questions.append(line)

    return questions


# =========================================================
# RETRIEVE DOCUMENT SOURCES
# =========================================================

def retrieve_sources(search_query):

    try:

        # ---------------------------------------------
        # Uploaded PDF retrieval
        # ---------------------------------------------

        if st.session_state.uploaded_index is not None:

            sources = retrieve_from_uploaded_store(
                search_query,
                st.session_state.uploaded_index,
                st.session_state.uploaded_chunks,
                top_k=3,
                user_role=user_role,
                user_department=user_department,
            )

            document_name = st.session_state.uploaded_file_name

        # ---------------------------------------------
        # Default employee handbook retrieval
        # ---------------------------------------------

        else:

            sources = retrieve_documents(
                search_query,
                top_k=3,
                user_role=user_role,
                user_department=user_department,
            )

            sources = [
                source
                for source in sources
                if source.get("score", 0) >= 0.50
            ]

            document_name = "Employee Handbook"

        return sources, document_name

    except Exception as error:

        print("Retrieval error:", error)

        return [], "Document"


# =========================================================
# GENERATE ANSWER
# =========================================================

def get_answer(
    question,
    sources,
    document_name,
    conversation_history,
):

    try:

        # ---------------------------------------------
        # Uploaded PDF
        # Sources have already been access-filtered.
        # ---------------------------------------------

        if st.session_state.uploaded_index is not None:

            answer = generate_answer_from_context(
                question,
                sources,
                document_name,
                conversation_history,
            )

        # ---------------------------------------------
        # Default employee handbook
        # ---------------------------------------------

        else:

            answer = generate_answer(
                question,
                retrieved_chunks=sources,
                conversation_history=conversation_history,
                user_role=user_role,
                user_department=user_department,
            )

        return answer

    except Exception as error:

        print("Generation error:", error)

        # Emergency local fallback.
        answer = extractive_answer(
            question,
            sources,
            conversation_history,
        )

        return (
            answer
            + "\n\n"
            + "_The AI providers encountered an error. "
            "This answer was extracted from retrieved document text._"
        )


# =========================================================
# DISPLAY CHAT HISTORY
# =========================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])

        # Show provider for assistant messages.
        if (
            message["role"] == "assistant"
            and message.get("provider")
        ):

            st.caption(
                f"✦ Generated by: {message['provider']}"
            )

        # Show sources.
        if (
            message["role"] == "assistant"
            and message.get("sources")
        ):

            with st.expander("📄 View retrieved sources"):

                for i, source in enumerate(
                    message["sources"],
                    start=1,
                ):

                    st.markdown(
                        f"**Source {i} — Page "
                        f"{source.get('page', '?')}**  \n"
                        f"Relevance score: "
                        f"`{source.get('score', 0):.3f}`"
                    )

                    st.write(source.get("text", ""))

                    st.divider()


# =========================================================
# SUGGESTED QUESTIONS
# =========================================================

if not st.session_state.messages:

    st.markdown("#### Get started with a question")

    suggestions = [
        "What is the leave policy?",
        "What are the employee benefits?",
        "How do I request time off?",
    ]

    cols = st.columns(3)

    for i, suggestion in enumerate(suggestions):

        with cols[i]:

            if st.button(
                suggestion,
                use_container_width=True,
                key=f"suggestion_{i}",
            ):

                st.session_state.pending_question = suggestion
                st.rerun()


# =========================================================
# CHAT INPUT
# =========================================================

pending_question = st.session_state.pop(
    "pending_question",
    None,
)

user_input = st.chat_input(
    "Ask about your company's documents..."
)

if pending_question:
    user_input = pending_question


# =========================================================
# PROCESS USER QUESTIONS
# =========================================================

if user_input:

    questions = split_questions(user_input)

    if not questions:

        st.warning("Please enter at least one question.")

    else:

        for question in questions:

            # Save conversation history before current question.
            conversation_history = (
                st.session_state.messages.copy()
            )

            # ---------------------------------------------
            # Rewrite question for better retrieval
            # ---------------------------------------------

            try:

                search_query = rewrite_query(
                    question,
                    conversation_history,
                )

            except Exception as error:

                print("Query rewriting error:", error)
                search_query = question

            # ---------------------------------------------
            # Save original user question
            # ---------------------------------------------

            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": question,
                }
            )

            with st.chat_message("user"):
                st.markdown(question)

            # ---------------------------------------------
            # Assistant response
            # ---------------------------------------------

            with st.chat_message("assistant"):

                # Retrieve document sources.
                with st.spinner("Searching your knowledge base..."):

                    sources, document_name = retrieve_sources(
                        search_query
                    )

                # Show retrieved sources.
                if sources:

                    with st.expander(
                        "📄 Retrieved document sources",
                        expanded=False,
                    ):

                        for i, source in enumerate(
                            sources,
                            start=1,
                        ):

                            st.markdown(
                                f"**Source {i} — Page "
                                f"{source.get('page', '?')}**  \n"
                                f"Relevance score: "
                                f"`{source.get('score', 0):.3f}`"
                            )

                            st.write(source.get("text", ""))
                            st.divider()

                else:

                    st.warning(
                        "No relevant document sources were found."
                    )

                # Generate answer.
                with st.spinner("Generating answer..."):

                    answer = get_answer(
                        question,
                        sources,
                        document_name,
                        conversation_history,
                    )

                # Get provider.
                provider_name = get_last_provider()

                st.markdown(answer)

                st.caption(
                    f"✦ Generated by: {provider_name}"
                )

            # ---------------------------------------------
            # Save assistant response and metadata
            # ---------------------------------------------

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "provider": provider_name,
                }
            )


# =========================================================
# CLEAR CONVERSATION
# =========================================================

if st.session_state.messages:

    st.divider()

    if st.button("Clear conversation"):

        st.session_state.messages = []
        st.rerun()