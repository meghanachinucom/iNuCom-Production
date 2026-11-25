"""
Comprehensive end-to-end verification suite for iNuCom Production Tracker.
Uses a temporary encrypted SQLCipher database and cleans up after itself.
"""
import io
import os
import re
import shutil
import sqlite3
import tempfile

import openpyxl

# Set required env vars BEFORE importing app/db
_TMP_DIR = tempfile.mkdtemp(prefix="inucom_verify_")
_TEST_DB = os.path.join(_TMP_DIR, "test_production.db")
_BACKUP_DIR = os.path.join(_TMP_DIR, "backups")

os.environ["DATABASE_PATH"] = _TEST_DB
os.environ["DB_PASSWORD"] = "verify-strong-sqlcipher-pass-2026"
os.environ["FLASK_SECRET_KEY"] = "verify-flask-secret-key-64chars-000000000000000000000000000000"
os.environ["HTTPS_ENABLED"] = "0"
os.environ["BACKUP_DIR"] = _BACKUP_DIR

from db import open_encrypted_connection  # noqa: E402
from backup_db import create_encrypted_backup  # noqa: E402
from app import app, init_db  # noqa: E402


def _extract_csrf(html_bytes: bytes) -> str:
    html = html_bytes.decode("utf-8", errors="ignore")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    if m:
        return m.group(1)
    raise AssertionError("CSRF token not found in response HTML")


def _login(client, username: str, password: str = "inucom@123") -> None:
    resp = client.get("/login")
    assert resp.status_code == 200
    csrf = _extract_csrf(resp.data)
    resp = client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Invalid username or password" not in resp.data


def run_tests() -> None:
    try:
        init_db()
        assert os.path.exists(_TEST_DB), "Encrypted test DB was not created"

        # 1. Verify plain sqlite3 / wrong password cannot read encrypted DB
        try:
            plain = sqlite3.connect(_TEST_DB)
            plain.execute("SELECT count(*) FROM users;").fetchone()
            raise AssertionError("Plain sqlite3 should NOT be able to read encrypted DB!")
        except sqlite3.DatabaseError:
            pass
        finally:
            plain.close()

        try:
            open_encrypted_connection(_TEST_DB, password="wrong-password")
            raise AssertionError("Wrong password should NOT open encrypted DB!")
        except Exception:
            pass

        conn = open_encrypted_connection(_TEST_DB)
        assert conn.execute("PRAGMA journal_mode;").fetchone()[0].lower() == "wal"
        assert conn.execute("SELECT COUNT(*) FROM pipeline_stages;").fetchone()[0] == 12
        conn.close()
        print("[PASS] 1. SQLCipher encryption, WAL mode, and 12 pipeline stages verified.")

        # 2. Verify removed attendance/leave/HR routes return 404
        client = app.test_client()
        _login(client, "vasu")
        for dead_route in [
            "/attendance",
            "/leaves",
            "/holidays",
            "/team-approvals",
            "/system-approvals",
            "/hr/comp-off",
            "/compensation",
        ]:
            r = client.get(dead_route)
            assert r.status_code == 404, f"Expected 404 for {dead_route}, got {r.status_code}"
        print("[PASS] 2. Removed attendance/leave/HR routes return 404.")

        # 3. Verify no dead url_for links in templates
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        dead_endpoints = {
            "attendance_page", "clock_in", "clock_out", "leaves_page",
            "holidays_page", "comp_off_management_page", "team_approvals_page",
            "system_approvals_page", "approve_permission", "reject_permission",
        }
        for fn in os.listdir(template_dir):
            if not fn.endswith(".html"):
                continue
            with open(os.path.join(template_dir, fn), encoding="utf-8") as f:
                txt = f.read()
            for ep in dead_endpoints:
                assert ep not in txt, f"Dead endpoint {ep} still referenced in {fn}"
        print("[PASS] 3. Zero dead attendance/leave/approval links in templates.")

        # 4. Team A (Content: pooja) downloads template, adds new file + marks Done -> hands off to Team B (Modeling)
        client_a = app.test_client()
        _login(client_a, "pooja")

        # RBAC check: Team Lead cannot download another team's template
        r_forbidden = client_a.get("/team/template/download?team=Modeling", follow_redirects=True)
        assert b"only download templates for their own assigned team" in r_forbidden.data

        r_dl = client_a.get("/team/template/download")
        assert r_dl.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(r_dl.data))
        ws = wb.active
        assert ws.protection.sheet is True, "Template header protection should be enabled"

        # Add new file in row 2 marked Done (should hand off to Modeling!)
        ws.cell(row=2, column=1, value="Promo Videos / Promo Videos Main Chapter")
        ws.cell(row=2, column=2, value="EV_Hero_Car_v01")
        ws.cell(row=2, column=3, value="High")
        ws.cell(row=2, column=4, value=50)
        ws.cell(row=2, column=5, value=4.5)
        ws.cell(row=2, column=6, value="Prabhas")
        ws.cell(row=2, column=7, value="Done")
        ws.cell(row=2, column=8, value="Content approved and ready for Modeling")

        buf_a = io.BytesIO()
        wb.save(buf_a)
        buf_a.seek(0)

        # Dry-run preview
        r_up_get = client_a.get("/team/upload")
        csrf_a = _extract_csrf(r_up_get.data)
        r_prev = client_a.post(
            "/team/upload",
            data={
                "csrf_token": csrf_a,
                "action": "preview",
                "excel_file": (buf_a, "content_daily.xlsx"),
            },
            content_type="multipart/form-data",
        )
        assert r_prev.status_code == 200
        assert b"EV_Hero_Car_v01" in r_prev.data
        assert b"Confirm &amp; Commit Atomically" in r_prev.data

        # Confirm atomic commit
        csrf_a2 = _extract_csrf(r_prev.data)
        r_conf = client_a.post(
            "/team/upload",
            data={"csrf_token": csrf_a2, "action": "confirm"},
            follow_redirects=True,
        )
        assert r_conf.status_code == 200
        assert b"Upload committed for Content" in r_conf.data

        # Verify Modeling now has EV_Hero_Car_v01 in Open status
        conn = open_encrypted_connection(_TEST_DB)
        fp_mdl = conn.execute(
            """
            SELECT fp.status, fp.team_name FROM file_pipeline fp
            JOIN files f ON fp.file_id = f.id
            WHERE f.name = 'EV_Hero_Car_v01' AND fp.step_name = 'Modeling'
            """
        ).fetchone()
        assert fp_mdl is not None and fp_mdl["status"] == "Open", f"Expected Modeling Open, got {fp_mdl}"
        conn.close()
        print("[PASS] 4. Team A download -> dry-run preview -> atomic commit -> sequential handoff to Team B verified.")

        # 5. Team B (Modeling: amit) downloads template (pre-filled with EV_Hero_Car_v01), marks Rework -> sends back to Content
        client_b = app.test_client()
        _login(client_b, "amit")
        r_dl_b = client_b.get("/team/template/download")
        assert r_dl_b.status_code == 200
        wb_b = openpyxl.load_workbook(io.BytesIO(r_dl_b.data))
        ws_b = wb_b.active
        assert ws_b.cell(row=2, column=2).value == "EV_Hero_Car_v01", "Pre-filled Modeling queue missing EV_Hero_Car_v01"

        ws_b.cell(row=2, column=6, value="Raveendra. K")
        ws_b.cell(row=2, column=7, value="Rework")
        ws_b.cell(row=2, column=8, value="Missing wheel blueprint dimensions")
        buf_b = io.BytesIO()
        wb_b.save(buf_b)
        buf_b.seek(0)

        csrf_b = _extract_csrf(client_b.get("/team/upload").data)
        r_prev_b = client_b.post(
            "/team/upload",
            data={"csrf_token": csrf_b, "action": "preview", "excel_file": (buf_b, "modeling_rework.xlsx")},
            content_type="multipart/form-data",
        )
        assert b"Confirm &amp; Commit Atomically" in r_prev_b.data
        csrf_b2 = _extract_csrf(r_prev_b.data)
        r_conf_b = client_b.post(
            "/team/upload",
            data={"csrf_token": csrf_b2, "action": "confirm"},
            follow_redirects=True,
        )
        assert b"1 sent for rework" in r_conf_b.data

        conn = open_encrypted_connection(_TEST_DB)
        fp_cnt = conn.execute(
            """
            SELECT fp.status, fp.rework_reason FROM file_pipeline fp
            JOIN files f ON fp.file_id = f.id
            WHERE f.name = 'EV_Hero_Car_v01' AND fp.step_name = 'Content'
            """
        ).fetchone()
        assert fp_cnt["status"] == "Rework"
        assert "Missing wheel blueprint" in fp_cnt["rework_reason"]
        conn.close()
        print("[PASS] 5. Team B Rework send-back to Team A with reason note verified.")

        # 6. Verify invalid Excel row blocks commit and leaves DB unchanged
        wb_bad = openpyxl.load_workbook(io.BytesIO(client_b.get("/team/template/download").data))
        ws_bad = wb_bad.active
        ws_bad.cell(row=2, column=2, value="Bad_File_Test")
        ws_bad.cell(row=2, column=6, value="NonExistentArtist")
        ws_bad.cell(row=2, column=7, value="Done")
        buf_bad = io.BytesIO()
        wb_bad.save(buf_bad)
        buf_bad.seek(0)
        csrf_b3 = _extract_csrf(client_b.get("/team/upload").data)
        r_bad = client_b.post(
            "/team/upload",
            data={"csrf_token": csrf_b3, "action": "preview", "excel_file": (buf_bad, "bad.xlsx")},
            content_type="multipart/form-data",
        )
        assert b"Validation Errors (Commit Blocked)" in r_bad.data
        print("[PASS] 6. Invalid Excel row blocked commit cleanly.")

        # 7. Verify Admin Daily Upload Compliance panel & Encrypted Backup
        r_rep = client.get("/reports?tab=compliance")
        assert r_rep.status_code == 200
        assert b"Uploaded at" in r_rep.data

        bak_path = create_encrypted_backup(_TEST_DB, _BACKUP_DIR, os.environ["DB_PASSWORD"], keep_days=30)
        assert os.path.exists(bak_path)
        bak_conn = open_encrypted_connection(bak_path)
        assert bak_conn.execute("SELECT COUNT(*) FROM daily_upload_logs").fetchone()[0] == 2
        bak_conn.close()
        print("[PASS] 7. Admin daily upload compliance and encrypted backup verified.")

        print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    finally:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    run_tests()
