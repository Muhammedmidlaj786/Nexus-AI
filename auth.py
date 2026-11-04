
import re
import streamlit as st

from database import (
    authenticate_user,
    create_user,
    log_action,
    get_all_users,
    update_user_role,
    update_user_status,
    update_user_department,
    get_audit_logs,
)


# =========================================================
# CONSTANTS
# =========================================================

DEPARTMENTS = [
    "Unassigned",
    "HR",
    "Finance",
    "IT",
    "Engineering",
    "Sales",
    "Operations",
    "Management",
]


# =========================================================
# SESSION STATE
# =========================================================

def initialize_auth_state():

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "current_user" not in st.session_state:
        st.session_state.current_user = None

    if "auth_page" not in st.session_state:
        st.session_state.auth_page = "login"


# =========================================================
# EMAIL VALIDATION
# =========================================================

def is_valid_email(email):

    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    return re.match(pattern, email.strip()) is not None


# =========================================================
# LOGIN / REGISTRATION SCREEN
# =========================================================

def show_auth_page():

    initialize_auth_state()

    st.markdown(
        """
        <style>
        .auth-shell {
            max-width: 460px;
            margin: 3rem auto 0 auto;
            padding: 2rem;
            border: 1px solid rgba(128,128,128,0.25);
            border-radius: 22px;
            background: rgba(128,128,128,0.04);
        }

        .auth-brand {
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -1px;
            text-align: center;
            margin-bottom: 0.2rem;
        }

        .auth-subtitle {
            text-align: center;
            opacity: 0.7;
            margin-bottom: 1.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="auth-brand">'
        'Nexus <span style="color:#8B5CF6">AI</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="auth-subtitle">'
        'Your company knowledge, one conversation away.'
        '</div>',
        unsafe_allow_html=True,
    )

    login_tab, signup_tab = st.tabs(
        ["Sign in", "Create account"]
    )

    # =====================================================
    # LOGIN
    # =====================================================

    with login_tab:

        with st.form("login_form"):

            email = st.text_input(
                "Email address",
                placeholder="name@company.com",
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Sign in",
                use_container_width=True,
            )

        if submitted:

            if not email.strip() or not password:
                st.error("Please enter your email and password.")

            elif not is_valid_email(email):
                st.error("Please enter a valid email address.")

            else:

                user = authenticate_user(
                    email.strip().lower(),
                    password,
                )

                if user:

                    # Add a safe fallback for existing user records.
                    user.setdefault("department", "Unassigned")

                    st.session_state.authenticated = True
                    st.session_state.current_user = user

                    st.session_state.messages = []

                    log_action(
                        user["id"],
                        user["email"],
                        "LOGIN",
                        "User logged in",
                    )

                    st.rerun()

                else:
                    st.error(
                        "Invalid credentials or inactive account."
                    )

    # =====================================================
    # SIGNUP
    # =====================================================

    with signup_tab:

        st.caption(
            "Create an account to access your organization's knowledge."
        )

        st.info(
            "New accounts are created as Employees. "
            "An administrator will assign your department."
        )

        with st.form("signup_form"):

            full_name = st.text_input(
                "Full name",
                placeholder="Your full name",
            )

            signup_email = st.text_input(
                "Email address",
                placeholder="name@company.com",
            )

            signup_password = st.text_input(
                "Password",
                type="password",
                help="Use at least 8 characters.",
            )

            confirm_password = st.text_input(
                "Confirm password",
                type="password",
            )

            signup_submitted = st.form_submit_button(
                "Create account",
                use_container_width=True,
            )

        if signup_submitted:

            if not full_name.strip():
                st.error("Please enter your full name.")

            elif not is_valid_email(signup_email):
                st.error("Please enter a valid email address.")

            elif len(signup_password) < 8:
                st.error(
                    "Password must contain at least 8 characters."
                )

            elif signup_password != confirm_password:
                st.error("Passwords do not match.")

            else:

                success, message = create_user(
                    full_name=full_name.strip(),
                    email=signup_email.strip().lower(),
                    password=signup_password,
                    role="Employee",
                    department="Unassigned",
                )

                if success:

                    st.success(
                        "Account created! You can now sign in."
                    )

                else:
                    st.error(message)


# =========================================================
# LOGOUT
# =========================================================

def logout():

    user = st.session_state.get("current_user")

    if user:

        log_action(
            user["id"],
            user["email"],
            "LOGOUT",
            "User logged out",
        )

    st.session_state.authenticated = False
    st.session_state.current_user = None
    st.session_state.messages = []

    # Clear uploaded-document session data.
    st.session_state.uploaded_index = None
    st.session_state.uploaded_chunks = None
    st.session_state.uploaded_file_name = None
    st.session_state.uploaded_document_id = None
    st.session_state.uploaded_department = None
    st.session_state.uploaded_access_level = None

    st.rerun()


# =========================================================
# ADMIN USER MANAGEMENT
# =========================================================

def show_admin_user_management():

    st.subheader("User management")

    st.caption(
        "Manage registered users, departments, and access roles."
    )

    users = get_all_users()

    if not users:
        st.info("No users found.")
        return

    for user in users:

        with st.container(border=True):

            left, right = st.columns([3, 2])

            with left:

                st.markdown(
                    f"**{user['full_name']}**"
                )

                st.caption(user["email"])

                st.caption(
                    f"Department: "
                    f"{user.get('department', 'Unassigned')}"
                )

                st.caption(
                    "Active" if user["is_active"] else "Inactive"
                )

            with right:

                # -----------------------------------------
                # ROLE
                # -----------------------------------------

                roles = ["Employee", "Manager", "Admin"]

                current_role = user.get("role", "Employee")

                if current_role not in roles:
                    current_role = "Employee"

                selected_role = st.selectbox(
                    "Role",
                    roles,
                    index=roles.index(current_role),
                    key=f"role_{user['id']}",
                )

                if st.button(
                    "Save role",
                    key=f"save_role_{user['id']}",
                ):

                    success, message = update_user_role(
                        user["id"],
                        selected_role,
                    )

                    if success:
                        st.success(message)
                        st.rerun()

                    else:
                        st.error(message)

                # -----------------------------------------
                # DEPARTMENT
                # -----------------------------------------

                departments = DEPARTMENTS

                current_department = user.get(
                    "department",
                    "Unassigned",
                )

                if current_department not in departments:
                    current_department = "Unassigned"

                selected_department = st.selectbox(
                    "Department",
                    departments,
                    index=departments.index(current_department),
                    key=f"department_{user['id']}",
                )

                if st.button(
                    "Save department",
                    key=f"save_department_{user['id']}",
                ):

                    success, message = update_user_department(
                        user["id"],
                        selected_department,
                    )

                    if success:
                        st.success(message)
                        st.rerun()

                    else:
                        st.error(message)

                # -----------------------------------------
                # ACCOUNT STATUS
                # -----------------------------------------

                if user["is_active"]:

                    if st.button(
                        "Deactivate account",
                        key=f"deactivate_{user['id']}",
                    ):

                        success, message = update_user_status(
                            user["id"],
                            False,
                        )

                        if success:
                            st.success(message)
                            st.rerun()

                        else:
                            st.error(message)

                else:

                    if st.button(
                        "Activate account",
                        key=f"activate_{user['id']}",
                    ):

                        success, message = update_user_status(
                            user["id"],
                            True,
                        )

                        if success:
                            st.success(message)
                            st.rerun()

                        else:
                            st.error(message)


# =========================================================
# ADMIN AUDIT LOGS
# =========================================================

def show_admin_audit_logs():

    st.subheader("Audit logs")

    st.caption(
        "Recent user and account activity."
    )

    logs = get_audit_logs()

    if not logs:
        st.info("No audit activity yet.")
        return

    st.dataframe(
        logs,
        use_container_width=True,
        hide_index=True,
    )
