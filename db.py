"""
Encrypted SQLite (SQLCipher) connection and transaction helpers.
"""
import os
import sqlcipher3


def get_db_password() -> str:
    """Return DB_PASSWORD from environment or raise RuntimeError if missing."""
    pwd = os.environ.get("DB_PASSWORD", "").strip()
    if not pwd:
        raise RuntimeError(
            "DB_PASSWORD environment variable is required to open the encrypted database."
        )
    return pwd


def open_encrypted_connection(db_path: str, password: str | None = None) -> sqlcipher3.Connection:
    """
    Open a SQLCipher connection with WAL mode, synchronous=FULL,
    busy_timeout=5000, and foreign_keys=ON.
    """
    pwd = password if password is not None else get_db_password()
    if not pwd:
        raise RuntimeError("DB_PASSWORD cannot be empty.")

    conn = sqlcipher3.connect(db_path, timeout=30.0, check_same_thread=False)
    # Escape single quotes in password for PRAGMA key
    escaped_pwd = pwd.replace("'", "''")
    conn.execute(f"PRAGMA key = '{escaped_pwd}';")
    # Verify the key works immediately (raises DatabaseError on wrong password for existing DB)
    conn.execute("SELECT count(*) FROM sqlite_master;").fetchone()
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=FULL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlcipher3.Row
    return conn
