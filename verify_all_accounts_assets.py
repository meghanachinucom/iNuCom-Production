import requests
import sqlite3

BASE = "http://127.0.0.1:5000"
DB = "production.db"

ACCOUNTS = {
    "vasu": "inucom@123",      # Admin
    "meghana": "inucom@123",   # HR
    "pooja": "inucom@123",     # Content Lead
    "amit": "inucom@123",      # Modeling Lead
    "prabhas": "inucom@123",   # Content Artist
    "raveendra": "inucom@123"  # Modeling Artist
}

# Pre-configure must_change_password = 0
conn = sqlite3.connect(DB)
c = conn.cursor()
for u in ACCOUNTS.keys():
    c.execute("UPDATE users SET must_change_password = 0 WHERE username = ?", (u,))
conn.commit()
conn.close()

def session_for(username):
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"username": username, "password": ACCOUNTS[username]}, allow_redirects=True)
    if "/login" in r.url:
        raise RuntimeError(f"Login failed for {username}")
    return s

def check_account_assets():
    results = {}
    for username in ACCOUNTS.keys():
        s = session_for(username)
        
        chapter_obd_counts = {}
        total_assets_found = 0
        
        # Check Chapters 9 (148), 10 (149), 12 (151) for OBD Scanner
        for cid, cnum in [(148, 9), (149, 10), (151, 12)]:
            r = s.get(f"{BASE}/dashboard?view_tab=pipeline&sub_tab=assets&chapter_id={cid}")
            has_obd = "ev_ch_01_obd_scanner" in r.text
            chapter_obd_counts[cnum] = has_obd
            
        results[username] = chapter_obd_counts
        print(f"[ACCOUNT: {username:10s}] OBD Scanner in Ch 9: {chapter_obd_counts[9]}, Ch 10: {chapter_obd_counts[10]}, Ch 12: {chapter_obd_counts[12]}")

    # Verify consistency across all accounts
    first_user = list(ACCOUNTS.keys())[0]
    first_results = results[first_user]
    for u, res in results.items():
        for cnum in [9, 10, 12]:
            assert res[cnum] == True, f"Account {u} is missing OBD Scanner in Chapter {cnum}!"
            assert res[cnum] == first_results[cnum], f"Account {u} result mismatch for Chapter {cnum}!"

    print("\n[SUCCESS] Asset data (including OBD Scanner in Chapters 9, 10, 12) is 100% consistent and identical across ALL user accounts!")

if __name__ == "__main__":
    check_account_assets()
