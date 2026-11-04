import streamlit as st
import pandas as pd

from admin_database import (
    initialize_admin_tables,
    get_dashboard_stats,
    get_documents,
    get_query_analytics,
    get_audit_logs,
    update_document_access,
    deactivate_document,
    add_audit_log,
)

# Use the primary authentication database for workspace users.
# This keeps Admin Panel changes consistent with the User Management page.
from database import (
    get_all_users,
    update_user_role,
    update_user_department,
    update_user_status,
    DEPARTMENTS,
    ROLES,
)


def _get_current_user():
    """Return the authenticated user as a dictionary, supporting older session keys."""
    current_user = st.session_state.get("current_user")

    if isinstance(current_user, dict):
        return current_user

    # Compatibility fallback in case a previous auth.py version stored fields separately.
    return {
        "id": st.session_state.get("user_id"),
        "full_name": st.session_state.get("username", "Admin"),
        "email": st.session_state.get("email", ""),
        "role": st.session_state.get("role", ""),
        "department": st.session_state.get("department", "Unassigned"),
    }


def _admin_access_guard():
    """Stop access unless the user is authenticated and has the Admin role."""
    if not st.session_state.get("authenticated", False):
        st.error("Please log in first.")
        st.stop()

    user = _get_current_user()
    role = str(user.get("role") or st.session_state.get("role") or "").strip()

    if role.casefold() != "admin":
        st.error("You do not have permission to access the Admin Panel.")
        st.stop()

    return user


def _show_overview():
    st.subheader("System Overview")
    stats = get_dashboard_stats() or {}

    col1, col2, col3 = st.columns(3)
    col1.metric("Registered Users", stats.get("users", 0))
    col2.metric("Active Documents", stats.get("documents", 0))
    col3.metric("Total Queries", stats.get("queries", 0))

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
        user for user in users
        if user.get("id") != admin_id
    ]

    if not editable_users:
        st.info("There are no other users to manage.")
        return

    selected_user = st.selectbox(
        "Select user",
        editable_users,
        format_func=lambda user: (
            f"{user.get('full_name', 'Unknown')} — {user.get('email', '')}"
        ),
        key="admin_selected_user",
    )

    col1, col2 = st.columns(2)

    with col1:
        current_role = selected_user.get("role", "Employee")
        role_options = list(ROLES)
        if current_role not in role_options:
            role_options.append(current_role)

        new_role = st.selectbox(
            "Role",
            role_options,
            index=role_options.index(current_role),
            key=f"role_{selected_user['id']}",
        )

        if st.button("Save role", key="save_role", type="primary"):
            success, message = update_user_role(selected_user["id"], new_role)
            if success:
                add_audit_log(
                    admin_user.get("full_name", "Admin"),
                    "ROLE_UPDATED",
                    f"{selected_user.get('email')} role set to {new_role}",
                )
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with col2:
        current_department = selected_user.get("department") or "Unassigned"
        department_options = list(DEPARTMENTS)
        if current_department not in department_options:
            department_options.append(current_department)

        new_department = st.selectbox(
            "Department",
            department_options,
            index=department_options.index(current_department),
            key=f"department_{selected_user['id']}",
        )

        if st.button("Save department", key="save_department"):
            success, message = update_user_department(
                selected_user["id"],
                new_department,
            )
            if success:
                add_audit_log(
                    admin_user.get("full_name", "Admin"),
                    "DEPARTMENT_UPDATED",
                    f"{selected_user.get('email')} department set to {new_department}",
                )
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    is_active = bool(selected_user.get("is_active", True))
    status_label = "Deactivate account" if is_active else "Activate account"

    if st.button(status_label, key="toggle_user_status"):
        success, message = update_user_status(
            selected_user["id"],
            not is_active,
        )
        if success:
            add_audit_log(
                admin_user.get("full_name", "Admin"),
                "USER_STATUS_UPDATED",
                f"{selected_user.get('email')}: "
                f"{'activated' if not is_active else 'deactivated'}",
            )
            st.success(message)
            st.rerun()
        else:
            st.error(message)


def _show_document_management(admin_user):
    st.subheader("Document Management")
    documents = get_documents() or []

    if not documents:
        st.info(
            "No document records yet. Uploaded documents need to be registered "
            "in the admin database before they appear here."
        )
        return

    st.dataframe(
        pd.DataFrame(documents),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Manage Document Access")

    active_documents = [
        document for document in documents
        if str(document.get("status", "")).casefold() == "active"
    ]

    if not active_documents:
        st.info("There are no active documents to manage.")
        return

    selected_doc = st.selectbox(
        "Select document",
        active_documents,
        format_func=lambda doc: f"{doc.get('id')} — {doc.get('filename', 'Document')}",
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
    current_department = selected_doc.get("department", "All")
    if current_department not in department_options:
        department_options.append(current_department)

    current_access = selected_doc.get("access_level", "Employee")
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

    if st.button("Save Document Permissions", key="save_doc_permissions"):
        result = update_document_access(
            selected_doc["id"],
            department,
            access_level,
        )
        add_audit_log(
            admin_user.get("full_name", "Admin"),
            "DOCUMENT_ACCESS_UPDATED",
            selected_doc.get("filename", str(selected_doc["id"])),
        )
        if isinstance(result, tuple) and result and result[0] is False:
            st.error(result[1] if len(result) > 1 else "Could not update document access.")
        else:
            st.success("Document permissions updated.")
            st.rerun()

    if st.button("Deactivate Document", key="deactivate_document"):
        result = deactivate_document(selected_doc["id"])
        add_audit_log(
            admin_user.get("full_name", "Admin"),
            "DOCUMENT_DEACTIVATED",
            selected_doc.get("filename", str(selected_doc["id"])),
        )
        if isinstance(result, tuple) and result and result[0] is False:
            st.error(result[1] if len(result) > 1 else "Could not deactivate document.")
        else:
            st.warning("Document deactivated.")
            st.rerun()


def _show_analytics():
    st.subheader("Usage Analytics")
    analytics = get_query_analytics() or []

    if not analytics:
        st.info("No query analytics available yet.")
        return

    df = pd.DataFrame(analytics)

    col1, col2 = st.columns(2)
    col1.metric("Total Queries", len(df))

    if "response_time" in df.columns:
        response_times = pd.to_numeric(df["response_time"], errors="coerce")
        average = response_times.mean()
        col2.metric(
            "Average Response Time",
            f"{average:.2f} sec" if pd.notna(average) else "N/A",
        )
    else:
        col2.metric("Average Response Time", "N/A")

    st.divider()

    if "username" in df.columns:
        st.subheader("Queries by User")
        user_counts = df.groupby("username").size().reset_index(name="Query Count")
        st.bar_chart(user_counts.set_index("username"))

    if "provider" in df.columns:
        st.subheader("Queries by AI Provider")
        provider_counts = df.groupby("provider").size().reset_index(name="Query Count")
        st.bar_chart(provider_counts.set_index("provider"))

    st.subheader("Query History")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.download_button(
        "Export Analytics as CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="query_analytics.csv",
        mime="text/csv",
    )


def _show_audit_logs():
    st.subheader("Audit Logs")
    logs = get_audit_logs() or []

    if not logs:
        st.info("No audit logs available.")
        return

    df = pd.DataFrame(logs)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.download_button(
        "Export Audit Logs",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="audit_logs.csv",
        mime="text/csv",
    )


def show_admin_panel():
    initialize_admin_tables()
    admin_user = _admin_access_guard()

    admin_name = (
        admin_user.get("full_name")
        or admin_user.get("email")
        or "Admin"
    )

    st.title("🛡️ Enterprise Admin Dashboard")
    st.caption(
        "Manage users, documents, access permissions, and system activity."
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
