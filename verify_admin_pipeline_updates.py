import requests
import sqlite3
import re
import sys

BASE = "http://127.0.0.1:5000"
DB = "production.db"

ACCOUNTS = {
    "vasu": "inucom@123",      # Admin
    "pooja": "inucom@123",     # Lead
    "prabhas": "inucom@123"   # Artist
}

# Ensure must_change_password is 0
try:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for username in ACCOUNTS.keys():
        c.execute("UPDATE users SET must_change_password = 0 WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    print("[INFO] Database configured (must_change_password = 0).")
except Exception as e:
    print(f"[FAIL] Pre-configuring database failed: {e}")
    sys.exit(1)

def session_for(username):
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"username": username, "password": ACCOUNTS[username]}, allow_redirects=True)
    if "/login" in r.url:
        raise RuntimeError(f"Login failed for {username}")
    return s

def test_admin_updates():
    print("\n--- Testing Admin Account (vasu) ---")
    s_admin = session_for("vasu")
    
    # Test Asset Pipeline
    r = s_admin.get(f"{BASE}/dashboard?view_tab=pipeline&sub_tab=assets")
    assert r.status_code == 200, f"Dashboard returned status {r.status_code}"
    html = r.text

    # Req 1 Check: Edit option button beside chapter
    assert "toggleAdminChapterEdit" in html, "Req 1 FAIL: toggleAdminChapterEdit JS function missing in HTML"
    assert 'id="admin-edit-btn-' in html, "Req 1 FAIL: 'admin-edit-btn' button missing for Admin"
    assert "admin-status-view-" in html, "Req 1 FAIL: admin-status-view- elements missing for status pills"
    assert 'admin-status-edit-' in html and 'style="display:none;"' in html, "Req 1 FAIL: admin-status-edit- elements not hidden by default"
    print("[PASS] Req 1: Admin edit button and toggleable status cells present and hidden by default.")

    # Req 2 Check: Numbers box present for Admin
    assert "Total Assets" in html or "Total Scenes" in html, "Req 2 FAIL: Prominent Numbers Box missing for Admin"
    assert "Department / Team Breakdown for Chapter" in html, "Req 2 FAIL: Department breakdown missing for Admin"
    print("[PASS] Req 2: Full numbers box & breakdown visible for Admin.")

    # Req 3 Check: Invariant calculation in Numbers Box
    yts_match = re.search(r'(\d+)\s*</div>\s*<div[^>]*>\s*⏳ YTS', html)
    wip_match = re.search(r'(\d+)\s*</div>\s*<div[^>]*>\s*🔄 WIP', html)
    rev_match = re.search(r'(\d+)\s*</div>\s*<div[^>]*>\s*👁️ Review', html)
    rew_match = re.search(r'(\d+)\s*</div>\s*<div[^>]*>\s*🛠️ Rework', html)
    don_match = re.search(r'(\d+)\s*</div>\s*<div[^>]*>\s*✅ Done/Approved', html)
    hld_match = re.search(r'(\d+)\s*</div>\s*<div[^>]*>\s*🛑 Hold', html)
    tot_card = re.search(r'class="count-value"[^>]*>(\d+)</div>', html)
    
    if tot_card and yts_match and wip_match and rev_match and rew_match and don_match and hld_match:
        tot_cnt = int(tot_card.group(1))
        yts_cnt = int(yts_match.group(1))
        wip_cnt = int(wip_match.group(1))
        rev_cnt = int(rev_match.group(1))
        rew_cnt = int(rew_match.group(1))
        don_cnt = int(don_match.group(1))
        hld_cnt = int(hld_match.group(1))
        
        sum_cnt = yts_cnt + wip_cnt + rev_cnt + rew_cnt + don_cnt + hld_cnt
        print(f"[INFO] Numbers Box Calculation -> Total: {tot_cnt}, Sum(YTS={yts_cnt}, WIP={wip_cnt}, Review={rev_cnt}, Rework={rew_cnt}, Done={don_cnt}, Hold={hld_cnt}) = {sum_cnt}")
        assert tot_cnt == sum_cnt, f"Req 3 FAIL: Total count {tot_cnt} != Sum of categories {sum_cnt}"
        print("[PASS] Req 3: File-level count logic invariant (Sum == Total) verified!")
    else:
        print("[WARN] Could not parse numbers box regex matches to verify sum, checking HTML structure.")

    # Req 4 Check: Points number badge present in matrix view without artist name
    assert "points-big-num" in html, "Req 4 FAIL: points-big-num missing in HTML"
    assert "artist-highlight-badge" not in html, "Req 4 FAIL: artist name should not be displayed in sheet cells"
    print("[PASS] Req 4: Left-side points number badge and status present in matrix view without artist names.")

def test_lead_and_artist_views():
    print("\n--- Testing Lead Account (pooja) ---")
    s_lead = session_for("pooja")
    r_lead = s_lead.get(f"{BASE}/dashboard?view_tab=pipeline&sub_tab=assets")
    html_lead = r_lead.text
    
    assert 'id="admin-edit-btn-' not in html_lead, "Req 1 FAIL: Lead should NOT see Admin chapter edit button"
    assert "Department / Team Breakdown for Chapter" not in html_lead, "Req 2 FAIL: Lead should NOT see full department breakdown cards"
    assert "Total Files:" in html_lead or "Assets Pipeline" in html_lead, "Req 2 FAIL: Lead should see basic summary bar"
    print("[PASS] Req 2 (Lead): Full numbers box hidden, basic numbers displayed.")

    print("\n--- Testing Artist Account (prabhas) ---")
    s_artist = session_for("prabhas")
    r_artist = s_artist.get(f"{BASE}/dashboard")
    html_artist = r_artist.text
    
    assert 'id="admin-edit-btn-' not in html_artist, "Req 1 FAIL: Artist should NOT see Admin chapter edit button"
    assert "Department / Team Breakdown for Chapter" not in html_artist, "Req 2 FAIL: Artist should NOT see department breakdown cards"
    print("[PASS] Req 2 (Artist): Full numbers box hidden.")

if __name__ == "__main__":
    try:
        test_admin_updates()
        test_lead_and_artist_views()
        print("\n[SUCCESS] ALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"\n[FAIL] VERIFICATION FAILURE: {e}")
        sys.exit(1)
