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

        # 1. SQLCipher encryption, WAL mode, 11 stages, Lighting & Rendering merge
        plain = sqlite3.connect(_TEST_DB)
        try:
            plain.execute("SELECT count(*) FROM users;").fetchone()
            raise AssertionError("Plain sqlite3 should NOT read encrypted DB!")
        except sqlite3.DatabaseError:
            pass
        finally:
            plain.close()

        conn = open_encrypted_connection(_TEST_DB)
        assert conn.execute("PRAGMA journal_mode;").fetchone()[0].lower() == "wal"
        stages = [r["stage_name"] for r in conn.execute("SELECT stage_name FROM pipeline_stages ORDER BY stage_order ASC").fetchall()]
        assert len(stages) == 11, f"Expected 11 stages, got {len(stages)}: {stages}"
        assert "Lighting & Rendering" in stages
        assert "Lighting" not in stages and "Rendering" not in stages
        lr_members = {r["username"]: (r["name"], r["role"]) for r in conn.execute("SELECT username, name, role FROM users WHERE team = 'Lighting & Rendering'").fetchall()}
        assert lr_members.get("pavan")[1] == "Lead"
        assert lr_members.get("abhilasha") == ("Abhilasha", "Artist")
        conn.close()
        print("[PASS] 1. SQLCipher encryption, 11 merged stages, and Lighting & Rendering (Pavan + Abhilasha) verified.")

        # 2. Removed routes return 404 + Activity Log hidden from UI
        client_admin = app.test_client()
        _login(client_admin, "vasu")
        for dead_route in [
            "/attendance", "/leaves", "/holidays", "/team-approvals",
            "/system-approvals", "/hr/comp-off", "/compensation",
            "/activity-log", "/lead/pre-assign-work", "/assignment/validate", "/self-log-work",
        ]:
            r = client_admin.get(dead_route)
            assert r.status_code == 404, f"Expected 404 for {dead_route}, got {r.status_code}"

        # Ensure Activity Log is not in sidebar for Admin, HR, Lead, Artist
        for uname in ["vasu", "meghana", "pooja", "prabhas"]:
            c_u = app.test_client()
            _login(c_u, uname)
            r_pipe = c_u.get("/pipeline/assets")
            assert r_pipe.status_code == 200, f"Asset Pipeline not accessible for {uname}"
            assert b"Activity Log" not in r_pipe.data, f"Activity Log still visible for {uname}"
            r_sc = c_u.get("/pipeline/scenes")
            assert r_sc.status_code == 200, f"Scene Pipeline not accessible for {uname}"
        print("[PASS] 2. Activity Log hidden from all UI roles, obsolete routes return 404, and Pipelines visible to all roles.")

        # 3. HR & Content Team Lead can add Project + Upload Assets & Scene Names template
        client_hr = app.test_client()
        _login(client_hr, "meghana")
        csrf_hr = _extract_csrf(client_hr.get("/upload-project").data)
        r_proj = client_hr.post(
            "/project/add",
            data={"csrf_token": csrf_hr, "name": "HR_New_Project", "project_type": "Standard", "description": "Test"},
            headers={"Referer": "/upload-project"},
            follow_redirects=True,
        )
        assert r_proj.status_code == 200
        assert b"HR_New_Project" in r_proj.data

        # Content Lead downloads Assets & Scene Names template and uploads new Asset + Scene
        client_a = app.test_client()
        _login(client_a, "pooja")
        r_tpl = client_a.get("/upload-project/template/download")
        assert r_tpl.status_code == 200
        wb_as = openpyxl.load_workbook(io.BytesIO(r_tpl.data))
        ws_as = wb_as.active
        ws_as.cell(row=2, column=1, value="HR_New_Project")
        ws_as.cell(row=2, column=2, value="Asset")
        ws_as.cell(row=2, column=3, value="Ch1")
        ws_as.cell(row=2, column=4, value="New_Turbine_Asset")
        ws_as.cell(row=3, column=1, value="HR_New_Project")
        ws_as.cell(row=3, column=2, value="Scene")
        ws_as.cell(row=3, column=3, value="Ch1")
        ws_as.cell(row=3, column=4, value="New_Turbine_sc_01")
        buf_as = io.BytesIO()
        wb_as.save(buf_as)
        buf_as.seek(0)

        csrf_up = _extract_csrf(client_a.get("/upload-project").data)
        r_up_as = client_a.post(
            "/upload-project",
            data={"csrf_token": csrf_up, "file": (buf_as, "assets_scenes.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"Registered 2 new file(s)" in r_up_as.data
        assert b"New_Turbine_Asset" in client_a.get("/pipeline/assets").data
        assert b"New_Turbine_sc_01" in client_a.get("/pipeline/scenes").data
        print("[PASS] 3. HR & Content Lead Project creation + Assets & Scene Names Excel upload verified.")

        # 4. Team A download -> Approved handoff to Team B -> Team B Retake (Take 1)
        r_dl = client_a.get("/team/template/download")
        wb = openpyxl.load_workbook(io.BytesIO(r_dl.data))
        ws = wb.active
        ws.cell(row=2, column=1, value="HR_New_Project / Ch1")
        ws.cell(row=2, column=2, value="EV_Hero_Car_v01")
        ws.cell(row=2, column=3, value="High Complexity")
        ws.cell(row=2, column=4, value=50)
        ws.cell(row=2, column=5, value=4.5)
        ws.cell(row=2, column=6, value="Prabhas")
        ws.cell(row=2, column=7, value="Approved")
        ws.cell(row=2, column=8, value="")
        ws.cell(row=2, column=9, value="Approved for Modeling")
        buf_a = io.BytesIO()
        wb.save(buf_a)
        buf_a.seek(0)

        csrf_a = _extract_csrf(client_a.get("/team/upload").data)
        r_prev = client_a.post(
            "/team/upload",
            data={"csrf_token": csrf_a, "action": "preview", "excel_file": (buf_a, "content_daily.xlsx")},
            content_type="multipart/form-data",
        )
        csrf_a2 = _extract_csrf(r_prev.data)
        r_conf = client_a.post("/team/upload", data={"csrf_token": csrf_a2, "action": "confirm"}, follow_redirects=True)
        assert b"Upload committed for Content" in r_conf.data

        client_b = app.test_client()
        _login(client_b, "amit")
        # Status-filtered popup API scoped to Modeling
        r_popup = client_b.get("/api/files/by-status?status=Yet%20to%20Start")
        assert r_popup.status_code == 200
        popup_names = [f["file_name"] for f in r_popup.get_json()["files"]]
        assert "EV_Hero_Car_v01" in popup_names

        # Team B marks Retake Take 1
        wb_b = openpyxl.load_workbook(io.BytesIO(client_b.get("/team/template/download").data))
        ws_b = wb_b.active
        assert ws_b.cell(row=2, column=2).value == "EV_Hero_Car_v01"
        ws_b.cell(row=2, column=6, value="Raveendra. K")
        ws_b.cell(row=2, column=7, value="Retake")
        ws_b.cell(row=2, column=8, value="Take 1")
        ws_b.cell(row=2, column=9, value="Missing wheel blueprint")
        buf_b = io.BytesIO()
        wb_b.save(buf_b)
        buf_b.seek(0)

        csrf_b = _extract_csrf(client_b.get("/team/upload").data)
        r_prev_b = client_b.post(
            "/team/upload",
            data={"csrf_token": csrf_b, "action": "preview", "excel_file": (buf_b, "modeling_retake.xlsx")},
            content_type="multipart/form-data",
        )
        csrf_b2 = _extract_csrf(r_prev_b.data)
        r_conf_b = client_b.post("/team/upload", data={"csrf_token": csrf_b2, "action": "confirm"}, follow_redirects=True)
        assert b"1 sent for rework" in r_conf_b.data
        print("[PASS] 4. Sequential handoff, Status-Filtered Popup API, and Retake (Take 1) verified.")

        # 5. Artist Work, Points & Evidence Report (Admin & HR) + Compliance + Backup
        for c_rep in (client_admin, client_hr):
            r_ar = c_rep.get("/artist-reports")
            assert r_ar.status_code == 200
            assert b"Prabhas" in r_ar.data and b"content_daily.xlsx" in r_ar.data
            r_xl = c_rep.get("/artist-reports/export")
            assert r_xl.status_code == 200
            xl_wb = openpyxl.load_workbook(io.BytesIO(r_xl.data))
            assert "Artist Summary" in xl_wb.sheetnames
            assert "Detailed Work & Evidence" in xl_wb.sheetnames

        conn = open_encrypted_connection(_TEST_DB)
        assert conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0] > 0, "Backend activity_log should still record rows!"
        conn.close()

        bak_path = create_encrypted_backup(_TEST_DB, _BACKUP_DIR, os.environ["DB_PASSWORD"], keep_days=30)
        assert os.path.exists(bak_path)
        print("[PASS] 5. Artist Work & Evidence Excel report, silent activity_log, and encrypted backup verified.")

        print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    finally:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    run_tests()
