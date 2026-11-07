# admin_database.py
import os

import sqlite3

from pathlib import Path

from datetime import datetime
# =========================================================# DATABASE CONFIGURATION# =========================================================
BASE_DIR = Path(__file__).resolve().parent



DB_PATH = Path(

    os.getenv(

        "DATABASE_PATH",

        str(BASE_DIR / "enterprise.db"),

    )

)
# =========================================================# DATABASE CONNECTION# =========================================================
def get_connection():

    """

    Return a connection to the Nexus AI enterprise database.

    """



    DB_PATH.parent.mkdir(parents=True, exist_ok=True)



    conn = sqlite3.connect(str(DB_PATH))

    conn.row_factory = sqlite3.Row



    return conn





def _current_timestamp():

    """

    Return the current timestamp in SQLite-compatible format.

    """



    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")





def _get_table_columns(conn, table_name):

    """

    Return the column names for a table.

    """



    rows = conn.execute(

        f"PRAGMA table_info({table_name})"

    ).fetchall()



    return {

        row["name"]

        for row in rows

    }
# =========================================================# INITIALIZE / MIGRATE DATABASE TABLES# =========================================================
def initialize_admin_tables():

    """

    Create required tables and add missing optional columns.



    This also supports databases created by earlier versions

    of Nexus AI.

    """



    conn = get_connection()

    cursor = conn.cursor()



    try:
# -------------------------------------------------# DOCUMENTS# -------------------------------------------------
        cursor.execute("""

            CREATE TABLE IF NOT EXISTS documents (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                filename TEXT NOT NULL,

                uploaded_by TEXT NOT NULL DEFAULT 'Unknown',

                department TEXT DEFAULT 'All',

                access_level TEXT DEFAULT 'Employee',

                file_type TEXT DEFAULT 'PDF',

                uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                version INTEGER DEFAULT 1,

                status TEXT DEFAULT 'Active'

            )

        """)



        document_columns = _get_table_columns(

            conn,

            "documents",

        )
# Add optional columns to older databases.
        document_migrations = {

            "uploaded_by": (

                "TEXT NOT NULL DEFAULT 'Unknown'"

            ),

            "department": "TEXT DEFAULT 'All'",

            "access_level": "TEXT DEFAULT 'Employee'",

            "file_type": "TEXT DEFAULT 'PDF'",
"version": "INTEGER DEFAULT 1",

            "status": "TEXT DEFAULT 'Active'",

        }



        for column, definition in document_migrations.items():

            if column not in document_columns:

                cursor.execute(

                    f"""

                    ALTER TABLE documents

                    ADD COLUMN {column} {definition}

                    """

                )

        # SQLite cannot add NOT NULL with CURRENT_TIMESTAMP default to an existing table.
        if "uploaded_at" not in document_columns:
            cursor.execute("ALTER TABLE documents ADD COLUMN uploaded_at TEXT")
            cursor.execute("UPDATE documents SET uploaded_at = CURRENT_TIMESTAMP WHERE uploaded_at IS NULL OR uploaded_at = ''")
            document_columns.add("uploaded_at")
# -------------------------------------------------# QUERY ANALYTICS# -------------------------------------------------
        cursor.execute("""

            CREATE TABLE IF NOT EXISTS query_analytics (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                username TEXT NOT NULL DEFAULT 'Unknown',

                query TEXT NOT NULL,

                provider TEXT DEFAULT 'Unknown',

                response_time REAL DEFAULT 0,

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

            )

        """)



        query_columns = _get_table_columns(

            conn,

            "query_analytics",

        )



        query_migrations = {

            "username": "TEXT NOT NULL DEFAULT 'Unknown'",

            "provider": "TEXT DEFAULT 'Unknown'",

            "response_time": "REAL DEFAULT 0",

            "created_at": (

                "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"

            ),

        }



        for column, definition in query_migrations.items():

            if column not in query_columns:

                cursor.execute(

                    f"""

                    ALTER TABLE query_analytics

                    ADD COLUMN {column} {definition}

                    """

                )
# -------------------------------------------------# ADMIN AUDIT LOGS# -------------------------------------------------
        cursor.execute("""

            CREATE TABLE IF NOT EXISTS admin_audit_logs (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                username TEXT NOT NULL DEFAULT 'Unknown',

                action TEXT NOT NULL,

                details TEXT DEFAULT '',

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

            )

        """)



        audit_columns = _get_table_columns(

            conn,

            "admin_audit_logs",

        )



        audit_migrations = {

            "username": "TEXT NOT NULL DEFAULT 'Unknown'",

            "details": "TEXT DEFAULT ''",

            "created_at": (

                "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"

            ),

        }



        for column, definition in audit_migrations.items():

            if column not in audit_columns:

                cursor.execute(

                    f"""

                    ALTER TABLE admin_audit_logs

                    ADD COLUMN {column} {definition}

                    """

                )



        conn.commit()



    finally:

        conn.close()
# =========================================================# ADD DOCUMENT# =========================================================
def add_document(

    filename,

    uploaded_by="Unknown",

    department="All",

    access_level="Employee",

    file_type="PDF",

):

    """

    Register an uploaded document in the database.



    Returns:

        The newly created document ID.

    """



    initialize_admin_tables()



    conn = get_connection()



    try:

        columns = _get_table_columns(

            conn,

            "documents",

        )



        values = {

            "filename": filename,

            "uploaded_by": uploaded_by or "Unknown",

            "department": department or "All",

            "access_level": access_level or "Employee",

            "file_type": file_type or "PDF",

            "uploaded_at": _current_timestamp(),

            "version": 1,

            "status": "Active",

        }
# Insert only columns present in the actual database.
        insert_values = {

            column: value

            for column, value in values.items()

            if column in columns

        }



        column_names = ", ".join(

            insert_values.keys()

        )



        placeholders = ", ".join(

            ["?"] * len(insert_values)

        )



        sql = f"""

            INSERT INTO documents (

                {column_names}

            )

            VALUES (

                {placeholders}

            )

        """



        cursor = conn.execute(

            sql,

            tuple(insert_values.values()),

        )



        document_id = cursor.lastrowid



        conn.commit()



        return document_id



    finally:

        conn.close()
# =========================================================# GET DOCUMENTS# =========================================================
def get_documents():

    """

    Return all registered documents, newest first.

    """



    initialize_admin_tables()



    conn = get_connection()



    try:

        rows = conn.execute("""

            SELECT *

            FROM documents

            ORDER BY uploaded_at DESC

        """).fetchall()



        return [

            dict(row)

            for row in rows

        ]



    finally:

        conn.close()
# Compatibility alias for newer code.
def get_all_documents():

    return get_documents()
# =========================================================# UPDATE DOCUMENT ACCESS# =========================================================
def update_document_access(

    document_id,

    department,

    access_level,

):

    """

    Update the department and access level of a document.

    """



    initialize_admin_tables()



    conn = get_connection()



    try:

        cursor = conn.execute("""

            UPDATE documents

            SET department = ?,

                access_level = ?

            WHERE id = ?

        """, (

            department,

            access_level,

            document_id,

        ))



        conn.commit()



        return cursor.rowcount > 0



    finally:

        conn.close()
# =========================================================# DEACTIVATE DOCUMENT# =========================================================
def deactivate_document(document_id):

    """

    Mark a document as inactive.

    """



    initialize_admin_tables()



    conn = get_connection()



    try:

        cursor = conn.execute("""

            UPDATE documents

            SET status = 'Inactive'

            WHERE id = ?

        """, (document_id,))



        conn.commit()



        return cursor.rowcount > 0



    finally:

        conn.close()
# =========================================================# RECORD QUERY ANALYTICS# =========================================================
def record_query(

    username,

    query,

    provider="Unknown",

    response_time=0,

):

    """

    Save a user query and its response time.



    Returns:

        The newly created analytics record ID.

    """



    initialize_admin_tables()



    conn = get_connection()



    try:

        columns = _get_table_columns(

            conn,

            "query_analytics",

        )



        values = {

            "username": username or "Unknown",

            "query": query,

            "provider": provider or "Unknown",

            "response_time": float(

                response_time or 0

            ),

            "created_at": _current_timestamp(),

        }



        insert_values = {

            column: value

            for column, value in values.items()

            if column in columns

        }



        column_names = ", ".join(

            insert_values.keys()

        )



        placeholders = ", ".join(

            ["?"] * len(insert_values)

        )



        sql = f"""

            INSERT INTO query_analytics (

                {column_names}

            )

            VALUES (

                {placeholders}

            )

        """



        cursor = conn.execute(

            sql,

            tuple(insert_values.values()),

        )



        query_id = cursor.lastrowid



        conn.commit()



        return query_id



    finally:

        conn.close()
# =========================================================# GET QUERY ANALYTICS# =========================================================
def get_query_analytics():

    """

    Return all query analytics, newest first.

    """



    initialize_admin_tables()



    conn = get_connection()



    try:

        rows = conn.execute("""

            SELECT *

            FROM query_analytics

            ORDER BY created_at DESC

        """).fetchall()



        return [

            dict(row)

            for row in rows

        ]



    finally:

        conn.close()
# Compatibility alias for newer code.
def get_all_queries(limit=500):

    initialize_admin_tables()



    conn = get_connection()



    try:

        rows = conn.execute("""

            SELECT *

            FROM query_analytics

            ORDER BY created_at DESC

            LIMIT ?

        """, (limit,)).fetchall()



        return [

            dict(row)

            for row in rows

        ]



    finally:

        conn.close()
# =========================================================# ADD AUDIT LOG# =========================================================
def add_audit_log(

    username,

    action,

    details="",

):

    """

    Add an administrative audit log.

    """



    initialize_admin_tables()



    conn = get_connection()



    try:

        conn.execute("""

            INSERT INTO admin_audit_logs (

                username,

                action,

                details,

                created_at

            )

            VALUES (?, ?, ?, ?)

        """, (

            username or "Unknown",

            action,

            details or "",

            _current_timestamp(),

        ))



        conn.commit()



    finally:

        conn.close()
# Compatibility alias.
def record_audit_log(

    username,

    action,

    details="",

):

    return add_audit_log(

        username,

        action,

        details,

    )
# =========================================================# GET AUDIT LOGS# =========================================================
def get_audit_logs():

    """

    Return all audit logs, newest first.

    """



    initialize_admin_tables()



    conn = get_connection()



    try:

        rows = conn.execute("""

            SELECT *

            FROM admin_audit_logs

            ORDER BY created_at DESC

        """).fetchall()



        return [

            dict(row)

            for row in rows

        ]



    finally:

        conn.close()
# =========================================================# GET DASHBOARD STATISTICS# =========================================================
def get_dashboard_stats():

    """

    Return document and query totals from enterprise.db.



    Registered users are read from the authentication

    database using database.get_all_users().

    """



    initialize_admin_tables()



    conn = get_connection()



    try:

        documents = conn.execute("""

            SELECT COUNT(*)

            FROM documents

            WHERE status = 'Active'

        """).fetchone()[0]



        queries = conn.execute("""

            SELECT COUNT(*)

            FROM query_analytics

        """).fetchone()[0]



    finally:

        conn.close()
# User accounts are stored in the authentication database.
    total_users = 0



    try:

        from database import get_all_users



        users = get_all_users() or []



        total_users = len(users)



    except Exception as error:

        print(

            "Could not retrieve registered users:",

            repr(error),

        )



    return {

        "documents": documents,

        "queries": queries,

        "users": total_users,
# Compatibility keys used by the newer Admin Panel.
        "total_documents": documents,

        "total_queries": queries,

        "total_users": total_users,

    }
# =========================================================# GET USERS# =========================================================
def get_users():

    """

    Return users from the authentication database.



    Avoids querying a nonexistent users table in enterprise.db.

    """



    try:

        from database import get_all_users



        return get_all_users() or []



    except Exception as error:

        print(

            "Could not retrieve users:",

            repr(error),

        )



        return []
# =========================================================# INITIALIZE WHEN RUN DIRECTLY# =========================================================
if __name__ == "__main__":



    initialize_admin_tables()



    print("Nexus AI admin database initialized.")

    print(f"Database path: {DB_PATH}")



    print(

        "Dashboard statistics:",

        get_dashboard_stats(),

    )