"""
Automated encrypted SQLite/SQLCipher online backup utility with retention pruning.

Usage:
    python backup_db.py
    python backup_db.py --keep-days 30
"""
import argparse
import datetime
import os
import sys

from dotenv import load_dotenv
from db import get_db_password, open_encrypted_connection


def create_encrypted_backup(
    db_path: str,
    backup_dir: str,
    password: str,
    keep_days: int = 30,
) -> str:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"production_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    src_conn = open_encrypted_connection(db_path, password=password)
    dst_conn = open_encrypted_connection(backup_path, password=password)
    try:
        src_conn.backup(dst_conn)
        dst_conn.commit()
    finally:
        dst_conn.close()
        src_conn.close()

    prune_old_backups(backup_dir, keep_days=keep_days)
    return backup_path


def prune_old_backups(backup_dir: str, keep_days: int = 30) -> int:
    if keep_days <= 0 or not os.path.isdir(backup_dir):
        return 0
    cutoff = datetime.datetime.now() - datetime.timedelta(days=keep_days)
    removed = 0
    for fname in os.listdir(backup_dir):
        if not (fname.startswith("production_backup_") and fname.endswith(".db")):
            continue
        fpath = os.path.join(backup_dir, fname)
        try:
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime < cutoff:
                os.remove(fpath)
                removed += 1
        except OSError:
            pass
    return removed


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Create an encrypted backup of the SQLCipher database.")
    parser.add_argument("--db", default=os.environ.get("DATABASE_PATH", "production.db"))
    parser.add_argument("--backup-dir", default=os.environ.get("BACKUP_DIR", "./backups"))
    parser.add_argument("--keep-days", type=int, default=30)
    args = parser.parse_args()

    try:
        password = get_db_password()
        out_path = create_encrypted_backup(args.db, args.backup_dir, password, keep_days=args.keep_days)
        print(f"Encrypted backup created: {out_path}")
        return 0
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
