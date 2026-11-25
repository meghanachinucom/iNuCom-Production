"""
Production WSGI entrypoint for iNuCom Production Tracker using Waitress.
Run behind Nginx/TLS in server-only mode:
    python wsgi.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from waitress import serve  # noqa: E402
from app import app, init_db  # noqa: E402


if __name__ == "__main__":
    init_db()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    threads = int(os.environ.get("WAITRESS_THREADS", "8"))
    print(f"Starting iNuCom Production Tracker (Waitress) on {host}:{port} with {threads} threads...")
    serve(app, host=host, port=port, threads=threads)
