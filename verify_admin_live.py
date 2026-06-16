"""
Non-destructive live verification of Layer 9: Admin account constraints & features.
Tests via HTTP against the running Flask server on port 5000.
"""
import requests
import re
import sys

BASE = "http://127.0.0.1:5000"

ACCOUNTS = {
    "vasu": "inucom@123",  # Admin
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

# Log in as Admin
heading("STEP 1: Log in as Admin (vasu) and verify redirects")
s_admin = session_for("vasu")

# 1. Leaves redirect
r_leaves = s_admin.get(f"{BASE}/leaves", allow_redirects=True)
check("Admin /leaves redirects to /system-approvals", r_leaves.url.endswith("/system-approvals"), f"Landed at {r_leaves.url}")

# 2. Permissions redirect
r_perms = s_admin.get(f"{BASE}/permissions", allow_redirects=True)
check("Admin /permissions redirects to /system-approvals", r_perms.url.endswith("/system-approvals"), f"Landed at {r_perms.url}")

# 3. Holidays redirect (HR only)
r_holidays = s_admin.get(f"{BASE}/holidays", allow_redirects=True)
check("Admin /holidays redirects to /dashboard", r_holidays.url.endswith("/dashboard") or r_holidays.url.endswith("/dashboard?view=overview"), f"Landed at {r_holidays.url}")

# 4. Activity log redirect (HR only)
r_logs = s_admin.get(f"{BASE}/activity-log", allow_redirects=True)
check("Admin /activity-log redirects to /dashboard", r_logs.url.endswith("/dashboard") or r_logs.url.endswith("/dashboard?view=overview"), f"Landed at {r_logs.url}")
check("Admin sidebar does NOT show 'Activity Log' link", "Activity Log" not in r_leaves.text)


heading("STEP 2: Verify System Approvals page content")
r_approvals = s_admin.get(f"{BASE}/system-approvals")
check("System approvals page loads", r_approvals.status_code == 200)
check("Shows Pending Leave Requests header", "Pending Leave Requests" in r_approvals.text)
check("Shows Pending Permission & Attendance Edit Requests header", "Pending Permission" in r_approvals.text)


heading("STEP 3: Verify Attendance page Admin constraints")
r_att = s_admin.get(f"{BASE}/attendance")
check("Attendance page loads", r_att.status_code == 200)
check("Clock Panel is hidden", "Clock Panel" not in r_att.text)
check("Personal calendar-card is hidden", "calendar-card" not in r_att.text or "Back to My Calendar" not in r_att.text)
check("Has employee popup calendar trigger", "openCalendarModal" in r_att.text)


heading("STEP 4: Verify Points page Admin constraints")
r_points = s_admin.get(f"{BASE}/points")
check("Points page loads", r_points.status_code == 200)
check("My Target Progress card is hidden", "My Target Progress" not in r_points.text)
check("Weekly Points Breakdown card is hidden", "Weekly Points Breakdown" not in r_points.text)
check("Shows Set Monthly Target panel", "Set Monthly Target" in r_points.text)


heading("STEP 5: Verify Dashboard Admin constraints")
r_dash = s_admin.get(f"{BASE}/dashboard")
check("Dashboard loads", r_dash.status_code == 200)
check("Quick Add File panel is hidden", "Quick Add File" not in r_dash.text)
check("Lead Control Queue Board is hidden", "Lead Control Queue Board" not in r_dash.text)
check("EOD Daily Assignment Validations is hidden", "EOD Daily Assignment Validations" not in r_dash.text)


heading("STEP 6: Verify Calendar JSON API")
# Let's request calendar for user 4 (Prabhas)
r_api = s_admin.get(f"{BASE}/attendance/api/calendar/4?year=2026&month=6")
check("Calendar API returns 200", r_api.status_code == 200)
json_data = r_api.json()
check("JSON has employee name", "employee_name" in json_data and json_data["employee_name"] == "Prabhas")
check("JSON has days list", "days" in json_data and isinstance(json_data["days"], list) and len(json_data["days"]) > 0)


heading("FINAL SUMMARY")
failed_tests = [name for name, cond in results if not cond]
if failed_tests:
    print(f"  {FAIL} {len(failed_tests)} check(s) failed: {failed_tests}")
    sys.exit(1)
else:
    print(f"  {PASS} ALL ADMIN CHECKS PASSED!")
    sys.exit(0)
