import os
import sqlite3
import hashlib
import hmac
import secrets
from pathlib import Path
from datetime import datetime, timezone


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "app.db"

ROLES = ("Admin", "Manager", "Employee")
DEPARTMENTS = (
    "Unassigned",
    "HR",
    "Finance",
    "IT",
    "Engineering",
    "Sales",
    "Operations",
    "Management",
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =========================================================
# PASSWORD HASHING
# =========================================================

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256; return salt and hash."""
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310_000,
    )
    return f"{salt.hex()}:{password_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against its stored hash."""
    try:
        salt_hex, hash_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            310_000,
        )
        return hmac.compare_digest(actual_hash, expected_hash)
    except (ValueError, TypeError, AttributeError):
        return False


# =========================================================
# INITIALIZE DATABASE + SAFE MIGRATION
# =========================================================

def initialize_database():
    """Create tables and add the department column to older databases."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Employee',
                department TEXT NOT NULL DEFAULT 'Unassigned',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email TEXT,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
                    ON DELETE SET NULL
            )
        """)

        # Existing app.db files may have been created before departments existed.
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "department" not in columns:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN department TEXT NOT NULL DEFAULT 'Unassigned'
            """)

        conn.commit()
    finally:
        conn.close()


# =========================================================
# AUDIT LOGGING
# =========================================================

def log_action(user_id, email, action, details=""):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO audit_logs (
                user_id, email, action, details, created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            email,
            action,
            details,
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
    finally:
        conn.close()


# =========================================================
# USER CREATION
# =========================================================

def create_user(
    full_name: str,
    email: str,
    password: str,
    role: str = "Employee",
    department: str = "Unassigned",
):
    """
    Create a user.
    Public signup should use Employee and Unassigned; admins can assign
    department and role through the admin controls.
    """
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    department = (department or "Unassigned").strip()

    if not full_name:
        return False, "Full name is required."
    if not email:
        return False, "Email is required."
    if not isinstance(password, str) or len(password) < 8:
        return False, "Password must contain at least 8 characters."
    if role not in ROLES:
        return False, "Invalid user role."
    if department not in DEPARTMENTS:
        return False, "Invalid department."

    password_hash = hash_password(password)
    conn = get_connection()

    try:
        cursor = conn.execute("""
            INSERT INTO users (
                full_name, email, password_hash, role, department,
                is_active, created_at
            )
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (
            full_name,
            email,
            password_hash,
            role,
            department,
            datetime.now(timezone.utc).isoformat(),
        ))

        user_id = cursor.lastrowid
        conn.commit()

        log_action(
            user_id,
            email,
            "USER_CREATED",
            f"Account created with role {role} in department {department}",
        )
        return True, "Account created successfully."

    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    finally:
        conn.close()


# =========================================================
# AUTHENTICATE USER
# =========================================================

def authenticate_user(email: str, password: str):
    email = (email or "").strip().lower()
    conn = get_connection()

    try:
        user = conn.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """, (email,)).fetchone()

        if not user or not user["is_active"]:
            return None
        if not verify_password(password, user["password_hash"]):
            return None

        user_data = {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"],
            "department": user["department"] or "Unassigned",
            "is_active": bool(user["is_active"]),
        }

        log_action(
            user["id"],
            user["email"],
            "LOGIN",
            "Successful login",
        )
        return user_data
    finally:
        conn.close()


# =========================================================
# CREATE INITIAL ADMIN
# =========================================================

def create_initial_admin():
    """Create the first admin from ADMIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD."""
    admin_name = os.getenv("ADMIN_NAME", "").strip()
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "")

    if not admin_name or not admin_email or not admin_password:
        return

    conn = get_connection()
    try:
        admin_exists = conn.execute("""
            SELECT id
            FROM users
            WHERE role = 'Admin'
            LIMIT 1
        """).fetchone()
    finally:
        conn.close()

    if admin_exists:
        return

    create_user(
        full_name=admin_name,
        email=admin_email,
        password=admin_password,
        role="Admin",
        department="Management",
    )


# =========================================================
# LIST USERS
# =========================================================

def get_all_users():
    conn = get_connection()
    try:
        users = conn.execute("""
            SELECT
                id, full_name, email, role, department,
                is_active, created_at
            FROM users
            ORDER BY created_at DESC
        """).fetchall()
        return [dict(user) for user in users]
    finally:
        conn.close()


# =========================================================
# UPDATE USER ROLE
# =========================================================

def update_user_role(user_id: int, new_role: str):
    if new_role not in ROLES:
        return False, "Invalid role."

    conn = get_connection()
    try:
        user = conn.execute("""
            SELECT id, email, role
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        if not user:
            return False, "User not found."

        # Prevent accidental removal of the last active Admin.
        if user["role"] == "Admin" and new_role != "Admin":
            admin_count = conn.execute("""
                SELECT COUNT(*) AS count
                FROM users
                WHERE role = 'Admin' AND is_active = 1
            """).fetchone()["count"]

            if admin_count <= 1:
                return False, "You cannot demote the last active Admin."

        conn.execute("""
            UPDATE users
            SET role = ?
            WHERE id = ?
        """, (new_role, user_id))
        conn.commit()

        log_action(
            user_id,
            user["email"],
            "ROLE_UPDATED",
            f"Role changed from {user['role']} to {new_role}",
        )
        return True, "User role updated."
    finally:
        conn.close()


# =========================================================
# UPDATE USER DEPARTMENT
# =========================================================

def update_user_department(user_id: int, new_department: str):
    if new_department not in DEPARTMENTS:
        return False, "Invalid department."

    conn = get_connection()
    try:
        user = conn.execute("""
            SELECT id, email, department
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        if not user:
            return False, "User not found."

        old_department = user["department"] or "Unassigned"
        if old_department == new_department:
            return True, "Department is already set to this value."

        conn.execute("""
            UPDATE users
            SET department = ?
            WHERE id = ?
        """, (new_department, user_id))
        conn.commit()

        log_action(
            user_id,
            user["email"],
            "DEPARTMENT_UPDATED",
            f"Department changed from {old_department} to {new_department}",
        )
        return True, "User department updated."
    finally:
        conn.close()


# =========================================================
# ACTIVATE / DEACTIVATE USER
# =========================================================

def update_user_status(user_id: int, is_active: bool):
    conn = get_connection()
    try:
        user = conn.execute("""
            SELECT id, email, role, is_active
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        if not user:
            return False, "User not found."

        if user["role"] == "Admin" and not is_active and user["is_active"]:
            admin_count = conn.execute("""
                SELECT COUNT(*) AS count
                FROM users
                WHERE role = 'Admin' AND is_active = 1
            """).fetchone()["count"]

            if admin_count <= 1:
                return False, "You cannot deactivate the last active Admin."

        conn.execute("""
            UPDATE users
            SET is_active = ?
            WHERE id = ?
        """, (1 if is_active else 0, user_id))
        conn.commit()

        log_action(
            user_id,
            user["email"],
            "USER_STATUS_UPDATED",
            "Account activated" if is_active else "Account deactivated",
        )
        return True, "User status updated."
    finally:
        conn.close()


# =========================================================
# AUDIT LOGS
# =========================================================

def get_audit_logs(limit=200):
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                id, user_id, email, action, details, created_at
            FROM audit_logs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# =========================================================
# DATABASE INITIALIZATION ON IMPORT
# =========================================================

initialize_database()
create_initial_admin()
