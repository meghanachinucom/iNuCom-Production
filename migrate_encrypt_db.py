"""
Standalone CLI utility to encrypt an existing plain SQLite database into a
SQLCipher-encrypted database using DB_PASSWORD from the environment.

Usage:
    set DB_PASSWORD=your-strong-password
    python migrate_encrypt_db.py --source production.db --output production.encrypted.db
    # Or in-place (creates a .plain.bak backup before replacing):
    python migrate_encrypt_db.py --source production.db --in-place
"""
import argparse
import os
import shutil
import sqlite3
import sys

from dotenv import load_dotenv
import sqlcipher3


def encrypt_database(source_path: str, output_path: str, password: str, in_place: bool = False) -> None:
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source database not found: {source_path}")
    if not password:
        raise ValueError("DB_PASSWORD environment variable is required.")

    # Verify source is readable as plain SQLite
    plain_conn = sqlite3.connect(source_path)
    try:
        plain_conn.execute("SELECT count(*) FROM sqlite_master;").fetchone()
    except sqlite3.DatabaseError as exc:
        plain_conn.close()
        raise RuntimeError(
            f"Source '{source_path}' is not a valid unencrypted SQLite database (maybe already encrypted?): {exc}"
        ) from exc
    plain_conn.close()

    target_tmp = f"{output_path}.tmp"
    if os.path.exists(target_tmp):
        os.remove(target_tmp)

    # Use SQLCipher sqlcipher_export() via ATTACH DATABASE
    escaped_pwd = password.replace("'", "''")
    conn = sqlcipher3.connect(source_path)
    try:
        conn.execute(f"ATTACH DATABASE '{target_tmp}' AS encrypted KEY '{escaped_pwd}';")
        conn.execute("SELECT sqlcipher_export('encrypted');")
        conn.execute("DETACH DATABASE encrypted;")
    finally:
        conn.close()

    # Verify the newly encrypted DB opens with the password
    verify_conn = sqlcipher3.connect(target_tmp)
    try:
        verify_conn.execute(f"PRAGMA key = '{escaped_pwd}';")
        count = verify_conn.execute("SELECT count(*) FROM sqlite_master;").fetchone()[0]
        print(f"Verified encrypted database ({count} schema objects).")
    finally:
        verify_conn.close()

    if in_place:
        bak_path = f"{source_path}.plain.bak"
        shutil.copy2(source_path, bak_path)
        shutil.move(target_tmp, source_path)
        print(f"Encrypted in-place: '{source_path}' (plain backup saved at '{bak_path}').")
    else:
        if os.path.exists(output_path):
            os.remove(output_path)
        shutil.move(target_tmp, output_path)
        print(f"Encrypted database written to '{output_path}'.")


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Encrypt a plain SQLite database with SQLCipher.")
    parser.add_argument("--source", default=os.environ.get("DATABASE_PATH", "production.db"), help="Path to plain SQLite DB")
    parser.add_argument("--output", default="production.encrypted.db", help="Path for encrypted output DB")
    parser.add_argument("--in-place", action="store_true", help="Replace source DB after creating .plain.bak")
    args = parser.parse_args()

    password = os.environ.get("DB_PASSWORD", "").strip()
    if not password:
        print("ERROR: DB_PASSWORD environment variable is not set.", file=sys.stderr)
        return 1

    encrypt_database(args.source, args.output, password, in_place=args.in_place)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
