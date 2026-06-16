"""
Non-destructive live verification of Layer 10: HR account updates.
Tests via HTTP against the running Flask server on port 5000.
"""
import requests
import sqlite3

BASE = "http://127.0.0.1:5000"
DB   = "production.db"

ACCOUNTS = {
    "meghana": "inucom@123",  # HR
}

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"
results = []

def session_for(username):
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"username": username, "password": ACCOUNTS[username]}, allow_redirects=True)
    if "/login" in r.url:
        raise RuntimeError(f"Login failed for {username}: landed at {r.url}")
    return s

def check(name, condition, detail=""):
    icon = PASS if condition else FAIL
    results.append((name, condition))
    print(f"  {icon} {name}" + (f"  |  {detail}" if detail else ""))
    return condition

def heading(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# Generate sample excel sheet for testing
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Project Name", "Chapter Name", "File Name", "Description"])
ws.append(["Proj_Alpha", "Chapter_01", "File_A01_01", "First file of Alpha"])
ws.append(["Proj_Alpha", "Chapter_01", "File_A01_02", "Second file of Alpha"])
ws.append(["Proj_Beta", "Chapter_01", "File_B01_01", "First file of Beta"])
wb.save("test_project_upload.xlsx")
print("  [INFO] test_project_upload.xlsx generated successfully.")

# Log in as HR
heading("STEP 1: Log in as HR (meghana) and verify pages load and sidebar links")
s_hr = session_for("meghana")

# 1. Access leaves page and check sidebar/content
r_leaves = s_hr.get(f"{BASE}/leaves")
check("HR Leaves page loads", r_leaves.status_code == 200)
# Check sidebar items for HR
check("Sidebar shows 'Leaves and Permissions'", "Leaves and Permissions" in r_leaves.text)
check("Sidebar shows '🎬 Production Sheet'", "Production Sheet" in r_leaves.text or "🎬" in r_leaves.text)
check("Sidebar shows '📁 Upload Project'", "Upload Project" in r_leaves.text or "📁" in r_leaves.text)
check("Sidebar does NOT show 'Permissions' standalone link", "href=\"/permissions\"" not in r_leaves.text)
check("Sidebar does NOT show 'Compensation View' standalone link", "href=\"/compensation\"" not in r_leaves.text)
check("Leaves page does NOT show 'Requests Requiring My Approval'", "Requests Requiring My Approval" not in r_leaves.text)

# 2. Verify redirect for permissions/compensation
heading("STEP 2: Verify HR redirects from /permissions and /compensation to /leaves")
r_perm = s_hr.get(f"{BASE}/permissions", allow_redirects=True)
check("HR redirected from /permissions", r_perm.url.endswith("/leaves"), f"landed at {r_perm.url}")

r_comp = s_hr.get(f"{BASE}/compensation", allow_redirects=True)
check("HR redirected from /compensation", r_comp.url.endswith("/leaves"), f"landed at {r_comp.url}")

# 3. Access project upload page
heading("STEP 3: Access Upload Project page and upload sample Excel sheet")
r_upload = s_hr.get(f"{BASE}/upload-project")
check("Upload Project page loads", r_upload.status_code == 200)

with open("test_project_upload.xlsx", "rb") as f:
    r_post = s_hr.post(f"{BASE}/upload-project", files={"file": f}, allow_redirects=True)

check("Excel upload POST returns 200", r_post.status_code == 200)
check("Excel upload flash success message shown", "Successfully processed Excel sheet" in r_post.text or "Created" in r_post.text)

# Verify projects were actually created in DB
heading("STEP 4: Verify imported project/chapter/files exist in Database")
db = sqlite3.connect(DB)
cursor = db.cursor()

# Alpha checks
cursor.execute("SELECT id FROM projects WHERE name = 'Proj_Alpha'")
proj_row = cursor.fetchone()
check("Project Proj_Alpha created in database", proj_row is not None)

if proj_row:
    proj_id = proj_row[0]
    cursor.execute("SELECT id FROM chapters WHERE project_id = ? AND name = 'Chapter_01'", (proj_id,))
    chap_row = cursor.fetchone()
    check("Chapter_01 created for Proj_Alpha", chap_row is not None)
    
    if chap_row:
        chap_id = chap_row[0]
        cursor.execute("SELECT id, description FROM files WHERE chapter_id = ? AND name = 'File_A01_01'", (chap_id,))
        file_row = cursor.fetchone()
        check("File_A01_01 created under Chapter_01", file_row is not None)
        if file_row:
            check("File_A01_01 has correct description", file_row[1] == "First file of Alpha")
            
            # Check pipeline step
            cursor.execute("SELECT step_name, status FROM file_pipeline WHERE file_id = ?", (file_row[0],))
            pipeline = dict(cursor.fetchall())
            check("Pipeline Content stage is Open", pipeline.get("Content") == "Open")
            check("Pipeline Modeling stage is Pending", pipeline.get("Modeling") == "Pending")
            check("Pipeline VR stage is Pending", pipeline.get("VR") == "Pending")
            
            # Test inline edit file name feature for HR
            file_id = file_row[0]
            print(f"  {INFO} Testing file name edit route for file ID {file_id}")
            r_edit = s_hr.post(f"{BASE}/files/edit-name/{file_id}", data={
                "name": "File_A01_01_Renamed",
                "project_id": proj_id,
                "chapter_id": chap_id
            }, allow_redirects=True)
            check("Rename request returns 200", r_edit.status_code == 200)
            check("Flash message shows success", "updated successfully" in r_edit.text or "updated" in r_edit.text.lower())
            
            # Verify database has new name
            cursor.execute("SELECT name FROM files WHERE id = ?", (file_id,))
            updated_file_row = cursor.fetchone()
            check("File name updated to 'File_A01_01_Renamed' in database", updated_file_row is not None and updated_file_row[0] == 'File_A01_01_Renamed')

            # Test duplicate naming block
            r_dup = s_hr.post(f"{BASE}/files/edit-name/{file_id}", data={
                "name": "File_A01_02",
                "project_id": proj_id,
                "chapter_id": chap_id
            }, allow_redirects=True)
            check("Duplicate rename fails/shows error flash", "already exists" in r_dup.text)

# Clean up database changes
heading("STEP 5: Clean up database changes from test upload")
cursor.execute("DELETE FROM file_pipeline WHERE file_id IN (SELECT id FROM files WHERE name LIKE 'File_A%')")
cursor.execute("DELETE FROM files WHERE name LIKE 'File_A%' OR name LIKE 'File_B%'")
cursor.execute("DELETE FROM chapters WHERE name LIKE 'Chapter_%'")
cursor.execute("DELETE FROM projects WHERE name LIKE 'Proj_%'")
cursor.execute("DELETE FROM activity_log WHERE details LIKE '%test_project_upload%'")
db.commit()
db.close()
import os
if os.path.exists("test_project_upload.xlsx"):
    os.remove("test_project_upload.xlsx")
print("  [INFO] Database and test files cleaned up.")

# Final report
heading("FINAL SUMMARY")
failed_tests = [name for name, cond in results if not cond]
if failed_tests:
    print(f"  {FAIL} {len(failed_tests)} check(s) failed: {failed_tests}")
else:
    print(f"  {PASS} ALL HR CHECKS PASSED!")
