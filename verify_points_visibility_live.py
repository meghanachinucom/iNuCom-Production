"""
Verification of points visibility constraints on the production sheet (pipeline matrix grid).
Tests via HTTP against the running Flask server on port 5000.
"""
import requests
import sqlite3
import re
import sys

BASE = "http://127.0.0.1:5000"
DB   = "production.db"

ACCOUNTS = {
    "vasu": "inucom@123",      # Admin
    "meghana": "inucom@123",   # HR
    "pooja": "inucom@123",     # Lead (Content)
    "prabhas": "inucom@123",   # Artist (Content)
    "amit": "inucom@123",      # Lead (Modeling)
    "raveendra": "inucom@123"  # Artist (Modeling)
}

# 1. Update must_change_password to 0 to bypass password change redirects
try:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for username in ACCOUNTS.keys():
        c.execute("UPDATE users SET must_change_password = 0 WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    print("[INFO] Database pre-configured successfully (must_change_password set to 0 for test accounts).")
except Exception as e:
    print(f"[FAIL] Pre-configuring database failed: {e}")
    sys.exit(1)

def session_for(username):
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"username": username, "password": ACCOUNTS[username]}, allow_redirects=True)
    if "/login" in r.url:
        raise RuntimeError(f"Login failed for {username}: landed at {r.url}")
    return s

def check_points_visibility(html, username):
    # Regex to find @username and check if the next span contains points
    # Format expected when points are visible:
    # @username</span>
    # <span class="artist-badge-name" style="font-weight: 700; color: #b45309;">(XX pts)</span>
    pattern = rf"@{username}\s*<\/span>\s*<span class=\"artist-badge-name\" style=\"font-weight: 700; color: #b45309;\">\((\d+)\s*pts\)"
    match = re.search(pattern, html, re.DOTALL)
    if match:
        return True, int(match.group(1))
    return False, None

# Log in sessions
sessions = {}
for username in ACCOUNTS.keys():
    try:
        sessions[username] = session_for(username)
    except Exception as e:
        print(f"[FAIL] Could not log in session for {username}: {e}")
        sys.exit(1)

results = []

def run_test(test_user, target_artist, should_be_visible):
    s = sessions[test_user]
    # Request the pipeline view on the dashboard
    r = s.get(f"{BASE}/dashboard?view=pipeline&sub_tab=assets")
    if r.status_code != 200:
        print(f"  [FAIL] Failed to load dashboard for {test_user}")
        results.append(False)
        return

    visible, pts = check_points_visibility(r.text, target_artist)
    
    expected_str = "VISIBLE" if should_be_visible else "HIDDEN"
    actual_str = f"VISIBLE ({pts} pts)" if visible else "HIDDEN"
    
    success = (visible == should_be_visible)
    icon = "[PASS]" if success else "[FAIL]"
    
    print(f"  {icon} User '{test_user}' checking points of '{target_artist}' -> Expected: {expected_str}, Actual: {actual_str}")
    results.append(success)

print("\n--- Running Visibility Checks ---")

# 1. Admin (vasu) should see all points
run_test("vasu", "prabhas", should_be_visible=True)
run_test("vasu", "raveendra", should_be_visible=True)

# 2. HR (meghana) should see all points
run_test("meghana", "prabhas", should_be_visible=True)
run_test("meghana", "raveendra", should_be_visible=True)

# 3. Content Lead (pooja) should see Prabhas (her artist), but NOT Raveendra (modeling artist)
run_test("pooja", "prabhas", should_be_visible=True)
run_test("pooja", "raveendra", should_be_visible=False)

# 4. Modeling Lead (amit) should see Raveendra (his artist), but NOT Prabhas (content artist)
run_test("amit", "raveendra", should_be_visible=True)
run_test("amit", "prabhas", should_be_visible=False)

# 5. Artist (prabhas) should see their own points, but NOT Raveendra's points
run_test("prabhas", "prabhas", should_be_visible=True)
run_test("prabhas", "raveendra", should_be_visible=False)

# 6. Artist (raveendra) should see their own points, but NOT Prabhas's points
run_test("raveendra", "raveendra", should_be_visible=True)
run_test("raveendra", "prabhas", should_be_visible=False)

print("\n--- Summary ---")
all_ok = all(results)
if all_ok:
    print("[PASS] All visibility tests passed!")
    sys.exit(0)
else:
    print("[FAIL] Some visibility tests failed.")
    sys.exit(1)
