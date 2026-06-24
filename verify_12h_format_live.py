"""
Verification of 12-hour format rendering on dashboard and attendance pages.
Tests via HTTP against the running Flask server on port 5000.
"""
import requests
import sqlite3
import re
import sys

BASE = "http://127.0.0.1:5000"
DB   = "production.db"

# Clear today's attendance for test user prabhas to start fresh
try:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username='prabhas'")
    uid = c.fetchone()[0]
    c.execute("DELETE FROM attendance WHERE user_id=? AND date=date('now')", (uid,))
    c.execute("UPDATE users SET must_change_password=0 WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    print("[INFO] Cleared today's attendance for 'prabhas' to ensure clean start.")
except Exception as e:
    print(f"[FAIL] Pre-configuring database failed: {e}")
    sys.exit(1)

def session_for(username, password):
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"username": username, "password": password}, allow_redirects=True)
    if "/login" in r.url:
        raise RuntimeError(f"Login failed for {username}: landed at {r.url}")
    return s

try:
    s = session_for("prabhas", "inucom@123")
except Exception as e:
    print(f"[FAIL] Could not log in session for prabhas: {e}")
    sys.exit(1)

results = []

def check(name, condition):
    icon = "[PASS]" if condition else "[FAIL]"
    results.append(condition)
    print(f"  {icon} {name}")

# Step 1: Check clock widget when not checked in
print("\n--- Clock In Verification ---")
r = s.get(f"{BASE}/dashboard")
check("Dashboard loads successfully", r.status_code == 200)
check("Shows Not Checked In status", "Not Checked In" in r.text)

# Step 2: Clock In
# We POST to /attendance/clock-in with custom time for deterministic check (e.g. 09:30:00 -> 9:30 AM)
print("Clocking in at 09:30...")
r_in = s.post(f"{BASE}/attendance/clock-in", data={
    "custom_time": "09:30:00"
}, allow_redirects=True)
check("Clock-in response is 200", r_in.status_code == 200)

# Verify Dashboard shows 9:30 AM
r = s.get(f"{BASE}/dashboard")
check("Dashboard shows checked in message with 12h format", "Checked In: <strong class=\"ml-1\">9:30 AM</strong>" in r.text)

# Verify Attendance page shows 9:30 AM
r_att = s.get(f"{BASE}/attendance")
check("Attendance page shows checked in message with 12h format", "Checked In at <strong>9:30 AM</strong>" in r_att.text)

# Step 3: Clock Out
print("\n--- Clock Out Verification ---")
# We POST to /attendance/clock-out with custom time for deterministic check (e.g. 19:15:00 -> 7:15 PM)
print("Clocking out at 19:15...")
r_out = s.post(f"{BASE}/attendance/clock-out", data={
    "custom_time": "19:15:00"
}, allow_redirects=True)
check("Clock-out response is 200", r_out.status_code == 200)

# Verify Dashboard shows 7:15 PM
r = s.get(f"{BASE}/dashboard")
check("Dashboard shows clocked out message with 12h format", "Clocked Out: <strong class=\"ml-1\">7:15 PM</strong>" in r.text)

# Verify Attendance page shows 7:15 PM
r_att = s.get(f"{BASE}/attendance")
check("Attendance page Completed box shows In: 9:30 AM", "Checked In: <strong>9:30 AM</strong>" in r_att.text)
check("Attendance page Completed box shows Out: 7:15 PM", "Checked Out: <strong>7:15 PM</strong>" in r_att.text)

# Step 4: Verify profile Shift hours is formatted as 12-hour
print("\n--- Shift Hours Profile Verification ---")
r = s.get(f"{BASE}/dashboard?view=pipeline")
check("Profile Shift Hours displays formatted shift", "9:30 AM - 7:00 PM" in r.text)

# Summary
print("\n--- Summary ---")
if all(results):
    print("[PASS] All 12-hour format verification checks passed!")
    sys.exit(0)
else:
    print("[FAIL] Some 12-hour format verification checks failed.")
    sys.exit(1)
