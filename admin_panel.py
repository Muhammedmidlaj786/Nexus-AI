import sqlite3

import pandas as pd

import streamlit as st

from admin_database import (

    initialize_admin_tables,

    get_dashboard_stats,

    get_all_documents,

    get_all_queries,

    get_audit_logs,

    record_audit_log,

    get_connection,

)

from database import (

    get_all_users,

    update_user_role,

    update_user_department,

    update_user_status,

    DEPARTMENTS,

    ROLES,

)

# =========================================================

# DOCUMENT TABLE COMPATIBILITY

# =========================================================

def _ensure_document_status_column():

    """

    Add a status column if the existing documents table

    was created by an earlier version of admin_database.py.

    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(documents)")

    columns = [row["name"] for row in cursor.fetchall()]

    if "status" not in columns:

        cursor.execute(

            """

            ALTER TABLE documents

            ADD COLUMN status TEXT DEFAULT 'Active'

            """

        )

    connection.commit()

    connection.close()

def _update_document_access(document_id, department, access_level):

    """

    Update the department and access level for a document.

    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(

        """

        UPDATE documents

        SET department = ?, access_level = ?

        WHERE id = ?

        """,

        (department, access_level, document_id),

    )

    connection.commit()

    updated = cursor.rowcount > 0

    connection.close()

    return updated

def _deactivate_document(document_id):

    """

    Mark a document as inactive in the database.

    """

    _ensure_document_status_column()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(

        """

        UPDATE documents

        SET status = 'Inactive'

        WHERE id = ?

        """,

        (document_id,),

    )

    connection.commit()

    updated = cursor.rowcount > 0

    connection.close()

    return updated

# =========================================================

# CURRENT USER

# =========================================================

def _get_current_user():

    """

    Return the authenticated user as a dictionary.

    Supports older session-state structures.

    """

    current_user = st.session_state.get("current_user")

    if isinstance(current_user, dict):

        return current_user

    return {

        "id": st.session_state.get("user_id"),

        "full_name": st.session_state.get("username", "Admin"),

        "email": st.session_state.get("email", ""),

        "role": st.session_state.get("role", ""),

        "department": st.session_state.get(

            "department",

            "Unassigned",

        ),

    }

# =========================================================

# ADMIN ACCESS GUARD

# =========================================================

def _admin_access_guard():

    """

    Ensure the current user is authenticated and an Admin.

    """

    if not st.session_state.get("authenticated", False):

        st.error("Please log in first.")

        st.stop()

    user = _get_current_user()

    role = str(

        user.get("role")

        or st.session_state.get("role")

        or ""

    ).strip()

    if role.casefold() != "admin":

        st.error(

            "You do not have permission to access the Admin Panel."

        )

        st.stop()

    return user

# =========================================================

# AUDIT LOG HELPER

# =========================================================

def _write_audit_log(username, action, details=""):

    """

    Write an audit log using the current admin_database API.

    """

    try:

        record_audit_log(

            username=username,

            action=action,

            details=details,

        )

    except Exception as error:

        print("Audit log error:", error)

# =========================================================

# OVERVIEW

# =========================================================

def _show_overview():

    st.subheader("System Overview")

    stats = get_dashboard_stats() or {}

    # Handle the keys returned by the current admin_database.py.
    total_users = stats.get(

        "total_users",

        stats.get("users", 0),

    )

    total_documents = stats.get(

        "total_documents",

        stats.get("documents", 0),

    )

    total_queries = stats.get(

        "total_queries",

        stats.get("queries", 0),

    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Registered Users", total_users)

    col2.metric("Active Documents", total_documents)

    col3.metric("Total Queries", total_queries)

    st.divider()

    st.subheader("Recent System Activity")

    logs = get_audit_logs() or []

    if logs:

        st.dataframe(

            pd.DataFrame(logs).head(10),

            use_container_width=True,

            hide_index=True,

        )

    else:

        st.info("No activity has been recorded yet.")

# =========================================================

# USER MANAGEMENT

# =========================================================

def _show_user_management(admin_user):

    st.subheader("User Management")

    users = get_all_users() or []

    if not users:

        st.info("No users found.")

        return

    st.dataframe(

        pd.DataFrame(users),

        use_container_width=True,

        hide_index=True,

    )

    st.divider()

    st.subheader("Update User")

    admin_id = admin_user.get("id")

    editable_users = [

        user

        for user in users

        if user.get("id") != admin_id

    ]

    if not editable_users:

        st.info("There are no other users to manage.")

        return

    selected_user = st.selectbox(

        "Select user",

        editable_users,

        format_func=lambda user: (

            f"{user.get('full_name', 'Unknown')} — "

            f"{user.get('email', '')}"

        ),

        key="admin_selected_user",

    )

    col1, col2 = st.columns(2)

    # -----------------------------------------------------
    # ROLE
    # -----------------------------------------------------
    with col1:

        current_role = selected_user.get(

            "role",

            "Employee",

        )

        role_options = list(ROLES)

        if current_role not in role_options:

            role_options.append(current_role)

        new_role = st.selectbox(

            "Role",

            role_options,

            index=role_options.index(current_role),

            key=f"role_{selected_user['id']}",

        )

        if st.button(

            "Save role",

            key="save_role",

            type="primary",

        ):

            success, message = update_user_role(

                selected_user["id"],

                new_role,

            )

            if success:

                _write_audit_log(

                    admin_user.get("full_name", "Admin"),

                    "ROLE_UPDATED",

                    (

                        f"{selected_user.get('email')} "

                        f"role set to {new_role}"

                    ),

                )

                st.success(message)

                st.rerun()

            else:

                st.error(message)

    # -----------------------------------------------------
    # DEPARTMENT
    # -----------------------------------------------------
    with col2:

        current_department = (

            selected_user.get("department")

            or "Unassigned"

        )

        department_options = list(DEPARTMENTS)

        if current_department not in department_options:

            department_options.append(current_department)

        new_department = st.selectbox(

            "Department",

            department_options,

            index=department_options.index(current_department),

            key=f"department_{selected_user['id']}",

        )

        if st.button(

            "Save department",

            key="save_department",

        ):

            success, message = update_user_department(

                selected_user["id"],

                new_department,

            )

            if success:

                _write_audit_log(

                    admin_user.get("full_name", "Admin"),

                    "DEPARTMENT_UPDATED",

                    (

                        f"{selected_user.get('email')} "

                        f"department set to {new_department}"

                    ),

                )

                st.success(message)

                st.rerun()

            else:

                st.error(message)

    # -----------------------------------------------------
    # ACCOUNT STATUS
    # -----------------------------------------------------
    is_active = bool(

        selected_user.get("is_active", True)

    )

    status_label = (

        "Deactivate account"

        if is_active

        else "Activate account"

    )

    if st.button(

        status_label,

        key="toggle_user_status",

    ):

        success, message = update_user_status(

            selected_user["id"],

            not is_active,

        )

        if success:

            _write_audit_log(

                admin_user.get("full_name", "Admin"),

                "USER_STATUS_UPDATED",

                (

                    f"{selected_user.get('email')}: "

                    f"{'activated' if not is_active else 'deactivated'}"

                ),

            )

            st.success(message)

            st.rerun()

        else:

            st.error(message)

# =========================================================

# DOCUMENT MANAGEMENT

# =========================================================

def _show_document_management(admin_user):

    st.subheader("Document Management")

    _ensure_document_status_column()

    documents = get_all_documents() or []

    if not documents:

        st.info(

            "No document records yet. Uploaded documents need "

            "to be registered in the admin database before "

            "they appear here."

        )

        return

    # Older records may not have a status value.
    for document in documents:

        document.setdefault("status", "Active")

    st.dataframe(

        pd.DataFrame(documents),

        use_container_width=True,

        hide_index=True,

    )

    st.divider()

    st.subheader("Manage Document Access")

    active_documents = [

        document

        for document in documents

        if str(

            document.get("status", "Active")

        ).casefold() == "active"

    ]

    if not active_documents:

        st.info("There are no active documents to manage.")

        return

    selected_doc = st.selectbox(

        "Select document",

        active_documents,

        format_func=lambda doc: (

            f"{doc.get('id')} — "

            f"{doc.get('filename', 'Document')}"

        ),

        key="admin_selected_document",

    )

    department_options = [

        "All",

        "HR",

        "Finance",

        "IT",

        "Engineering",

        "Sales",

        "Operations",

        "Management",

    ]

    current_department = selected_doc.get(

        "department",

        "All",

    )

    if current_department not in department_options:

        department_options.append(current_department)

    current_access = selected_doc.get(

        "access_level",

        "Employee",

    )

    access_options = ["Employee", "Admin"]

    if current_access not in access_options:

        access_options.append(current_access)

    department = st.selectbox(

        "Department",

        department_options,

        index=department_options.index(current_department),

        key=f"doc_department_{selected_doc.get('id')}",

    )

    access_level = st.selectbox(

        "Minimum role",

        access_options,

        index=access_options.index(current_access),

        key=f"doc_access_{selected_doc.get('id')}",

    )

    # -----------------------------------------------------
    # SAVE DOCUMENT PERMISSIONS
    # -----------------------------------------------------
    if st.button(

        "Save Document Permissions",

        key="save_doc_permissions",

    ):

        updated = _update_document_access(

            selected_doc["id"],

            department,

            access_level,

        )

        if updated:

            _write_audit_log(

                admin_user.get("full_name", "Admin"),

                "DOCUMENT_ACCESS_UPDATED",

                selected_doc.get(

                    "filename",

                    str(selected_doc["id"]),

                ),

            )

            st.success("Document permissions updated.")

            st.rerun()

        else:

            st.error(

                "Could not update document permissions."

            )

    # -----------------------------------------------------
    # DEACTIVATE DOCUMENT
    # -----------------------------------------------------
    if st.button(

        "Deactivate Document",

        key="deactivate_document",

    ):

        updated = _deactivate_document(

            selected_doc["id"]

        )

        if updated:

            _write_audit_log(

                admin_user.get("full_name", "Admin"),

                "DOCUMENT_DEACTIVATED",

                selected_doc.get(

                    "filename",

                    str(selected_doc["id"]),

                ),

            )

            st.warning("Document deactivated.")

            st.rerun()

        else:

            st.error("Could not deactivate document.")

# =========================================================

# USAGE ANALYTICS

# =========================================================

def _show_analytics():

    st.subheader("Usage Analytics")

    # Current admin_database.py calls this get_all_queries().
    analytics = get_all_queries() or []

    if not analytics:

        st.info("No query analytics available yet.")

        return

    df = pd.DataFrame(analytics)

    col1, col2 = st.columns(2)

    col1.metric("Total Queries", len(df))

    if "response_time" in df.columns:

        response_times = pd.to_numeric(

            df["response_time"],

            errors="coerce",

        )

        average = response_times.mean()

        col2.metric(

            "Average Response Time",

            (

                f"{average:.2f} sec"

                if pd.notna(average)

                else "N/A"

            ),

        )

    else:

        col2.metric("Average Response Time", "N/A")

    st.divider()

    # -----------------------------------------------------
    # QUERIES BY USER
    # -----------------------------------------------------
    if "username" in df.columns:

        st.subheader("Queries by User")

        user_counts = (

            df.groupby("username")

            .size()

            .reset_index(name="Query Count")

        )

        st.bar_chart(

            user_counts.set_index("username")

        )

    # -----------------------------------------------------
    # QUERIES BY PROVIDER
    # -----------------------------------------------------
    if "provider" in df.columns:

        st.subheader("Queries by AI Provider")

        provider_counts = (

            df.groupby("provider")

            .size()

            .reset_index(name="Query Count")

        )

        st.bar_chart(

            provider_counts.set_index("provider")

        )

    # -----------------------------------------------------
    # QUERY HISTORY
    # -----------------------------------------------------
    st.subheader("Query History")

    st.dataframe(

        df,

        use_container_width=True,

        hide_index=True,

    )

    st.download_button(

        "Export Analytics as CSV",

        data=df.to_csv(index=False).encode("utf-8"),

        file_name="query_analytics.csv",

        mime="text/csv",

    )

# =========================================================

# AUDIT LOGS

# =========================================================

def _show_audit_logs():

    st.subheader("Audit Logs")

    logs = get_audit_logs() or []

    if not logs:

        st.info("No audit logs available.")

        return

    df = pd.DataFrame(logs)

    st.dataframe(

        df,

        use_container_width=True,

        hide_index=True,

    )

    st.download_button(

        "Export Audit Logs",

        data=df.to_csv(index=False).encode("utf-8"),

        file_name="audit_logs.csv",

        mime="text/csv",

    )

# =========================================================

# MAIN ADMIN PANEL

# =========================================================

def show_admin_panel():

    """

    Main entry point called by app.py.

    """

    initialize_admin_tables()

    _ensure_document_status_column()

    admin_user = _admin_access_guard()

    st.title("🛡️ Enterprise Admin Dashboard")

    st.caption(

        "Manage users, documents, access permissions, "

        "and system activity."

    )

    page = st.sidebar.radio(

        "Admin Navigation",

        [

            "Overview",

            "User Management",

            "Document Management",

            "Analytics",

            "Audit Logs",

        ],

        key="admin_navigation",

    )

    if page == "Overview":

        _show_overview()

    elif page == "User Management":

        _show_user_management(admin_user)

    elif page == "Document Management":

        _show_document_management(admin_user)

    elif page == "Analytics":

        _show_analytics()

    elif page == "Audit Logs":

        _show_audit_logs()
