import requests
import re

BASE = "http://127.0.0.1:5000"
ACCOUNTS = {
    "vasu": "inucom@123",      # Admin
    "meghana": "inucom@123",   # HR
    "pooja": "inucom@123",     # Lead
    "prabhas": "inucom@123",   # Artist
}

def check_account_notif(username):
    s = requests.Session()
    # Login
    r = s.post(f"{BASE}/login", data={"username": username, "password": ACCOUNTS[username]}, allow_redirects=True)
    if "/login" in r.url:
        print(f"[FAIL] Login failed for {username}")
        return False
    
    # Get notifications page
    r_notif = s.get(f"{BASE}/notifications")
    if r_notif.status_code != 200:
        print(f"[FAIL] Notifications page returned status {r_notif.status_code} for {username}")
        return False
        
    html = r_notif.text
    
    # Check that it has the sidebar, headers, and the main card is not constrained
    if "notif-page-list" not in html:
        print(f"[FAIL] notif-page-list class missing from notifications page of {username}")
        return False
        
    # Let's count how many times 'class="notif-list"' appears. 
    # It should appear exactly once (in the header dropdown), and the main page container should be notif-page-list.
    notif_list_count = html.count('class="notif-list"')
    if notif_list_count != 1:
        print(f"[FAIL] Expected exactly 1 occurrence of class=\"notif-list\" (in header dropdown) but found {notif_list_count} for {username}")
        # Let's inspect where it appears
        return False

    print(f"[PASS] {username} notifications page verified successfully.")
    return True

def main():
    success = True
    for user in ACCOUNTS:
        if not check_account_notif(user):
            success = False
            
    if success:
        print("\nAll accounts notifications page verification PASSED!")
    else:
        print("\nSome verification checks FAILED!")

if __name__ == "__main__":
    main()
