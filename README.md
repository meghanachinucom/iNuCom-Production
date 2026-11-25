# iNuCom Production Tracker

A tightly secured, server-only **Work & Production File Status Tracking System** built with Flask, SQLCipher (encrypted SQLite), OpenPyXL, and Waitress.

## Key Features
- **Encrypted, Fail-Safe Database**: `production.db` is encrypted at rest using SQLCipher (`PRAGMA key`) with `WAL` mode, `synchronous=FULL`, `busy_timeout=5000`, `foreign_keys=ON`, and atomic `BEGIN IMMEDIATE` transactions.
- **Hardened Server Security**: Environment-driven `FLASK_SECRET_KEY` and `DB_PASSWORD` (fail-fast on startup if missing), CSRF protection (`Flask-WTF`), `HttpOnly`/`SameSite=Lax` cookies (`Secure` when `HTTPS_ENABLED=1`), and strict role-based access control (`Admin`, `Lead`, `Artist`).
- **Sequential Pipeline & Excel Handoffs**:
  `Content → Modeling → Texturing → Rig → Animation → FBX Export → VFX → Lighting → Rendering → 3D Comp → Motion Graphics → VR`
  - Per-team downloadable `.xlsx` templates pre-filled with `Open`, `In Progress`, and `Rework` files.
  - Dry-run validation preview before atomic commit.
  - Automatic sequential handoff to the next team when marked `Done`, and automatic `Rework` send-back to the previous team when marked `Rework`.
- **Daily Upload Compliance & Encrypted Backups**: Tracks daily Team Lead Excel uploads in `daily_upload_logs` and provides `backup_db.py` for automated encrypted backups.

---

## Setup & Configuration

1. **Create and activate a virtual environment, then install dependencies:**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   # source venv/bin/activate
   pip install -r requirements.txt
   ```
   > **Note on SQLCipher**: `requirements.txt` installs `sqlcipher3-wheels` on Windows and `sqlcipher3-binary` on Linux/macOS. If your platform lacks a prebuilt wheel, install system `libsqlcipher-dev` and `pip install sqlcipher3`.

2. **Configure environment variables:**
   Copy `.env.example` to `.env` and set strong, unique secrets (never commit `.env`):
   ```ini
   DB_PASSWORD=your-strong-database-password
   FLASK_SECRET_KEY=your-64-char-random-hex-secret
   HTTPS_ENABLED=0
   BACKUP_DIR=./backups
   DATABASE_PATH=production.db
   ```

3. **Encrypt an existing plain SQLite database (optional migration):**
   ```bash
   python migrate_encrypt_db.py --source production.db --in-place
   ```

---

## Running in Production (Server-Only via Waitress)

Launch behind Nginx/TLS:
```bash
python wsgi.py
```
By default, `wsgi.py` binds to `127.0.0.1:5000` with 8 threads. Override with `HOST`, `PORT`, and `WAITRESS_THREADS` environment variables. Set `HTTPS_ENABLED=1` when terminating TLS at Nginx.

---

## Automated Encrypted Backups

Run manually or schedule via cron / Windows Task Scheduler:
```bash
python backup_db.py --keep-days 30
```
- **Linux cron (daily at 23:00):**
  ```cron
  0 23 * * * cd /path/to/iNuCom-Production && /path/to/venv/bin/python backup_db.py --keep-days 30
  ```
- **Windows Task Scheduler:**
  Program: `C:\path\to\venv\Scripts\python.exe`
  Arguments: `backup_db.py --keep-days 30`
  Start in: `D:\path\to\iNuCom-Production`

---

## Verification

Run the end-to-end verification suite (uses a temporary encrypted database):
```bash
python verify_production_flow.py
```
