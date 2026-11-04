# admin_database.py

import os
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = os.getenv(
    "DATABASE_PATH",
    str(Path(__file__).parent / "enterprise.db")
)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_admin_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            uploaded_by TEXT NOT NULL,
            department TEXT DEFAULT 'All',
            access_level TEXT DEFAULT 'Employee',
            file_type TEXT,
            uploaded_at TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Active'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            query TEXT NOT NULL,
            provider TEXT,
            response_time REAL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def add_audit_log(username, action, details=""):
    conn = get_connection()
    conn.execute("""
        INSERT INTO admin_audit_logs
        (username, action, details, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        username,
        action,
        details,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()


def add_document(
    filename,
    uploaded_by,
    department="All",
    access_level="Employee",
    file_type=""
):
    conn = get_connection()

    conn.execute("""
        INSERT INTO documents
        (filename, uploaded_by, department, access_level,
         file_type, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        filename,
        uploaded_by,
        department,
        access_level,
        file_type,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def record_query(username, query, provider="", response_time=0):
    conn = get_connection()

    conn.execute("""
        INSERT INTO query_analytics
        (username, query, provider, response_time, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        username,
        query,
        provider,
        response_time,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def get_dashboard_stats():
    conn = get_connection()
    cursor = conn.cursor()

    documents = cursor.execute("""
        SELECT COUNT(*) FROM documents WHERE status = 'Active'
    """).fetchone()[0]

    queries = cursor.execute("""
        SELECT COUNT(*) FROM query_analytics
    """).fetchone()[0]

    users = cursor.execute("""
        SELECT COUNT(*) FROM users
    """).fetchone()[0]

    conn.close()

    return {
        "documents": documents,
        "queries": queries,
        "users": users
    }


def get_documents():
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM documents
        ORDER BY uploaded_at DESC
    """).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_users():
    conn = get_connection()
    rows = conn.execute("""
        SELECT username, role, status
        FROM users
        ORDER BY username
    """).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_query_analytics():
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM query_analytics
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_audit_logs():
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM admin_audit_logs
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_document_access(document_id, department, access_level):
    conn = get_connection()

    conn.execute("""
        UPDATE documents
        SET department = ?, access_level = ?
        WHERE id = ?
    """, (department, access_level, document_id))

    conn.commit()
    conn.close()


def deactivate_document(document_id):
    conn = get_connection()

    conn.execute("""
        UPDATE documents
        SET status = 'Inactive'
        WHERE id = ?
    """, (document_id,))

    conn.commit()
    conn.close()