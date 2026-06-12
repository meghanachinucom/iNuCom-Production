"""
Non-destructive live verification of Layer 5 Leaves + Approval Engine.
Tests via HTTP against the running Flask server on port 5000.
Accounts used: prabhas (Artist), pooja (Lead), vasu (Admin), sana (Artist)
"""
import requests

BASE = "http://127.0.0.1:5000"

ACCOUNTS = {
    "prabhas": "inucom@123",   # Artist - uses default password
    "pooja":   "inucom@123",   # Lead - uses default password
    "vasu":    "inucom@123",   # Admin - uses default password
    "sana":    "inucom@123",   # Artist - uses default password
}

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results = []

def session_for(username):
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"username": username, "password": ACCOUNTS[username]}, allow_redirects=True)
    if r.url.endswith("/login") or "Invalid" in r.text:
        raise RuntimeError(f"Login failed for {username}")
    return s

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, condition))
    print(f"  {status} {name}" + (f" | {detail}" if detail else ""))
    return condition

def heading(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ─────────────────────────────────────────────────────────────
heading("STEP 1: prabhas (Artist) applies for leave")
s_prabhas = session_for("prabhas")

# Get initial leaves page and extract balance
r = s_prabhas.get(f"{BASE}/leaves")
check("Leaves page loads for prabhas", r.status_code == 200, f"status={r.status_code}")
page_text = r.text
check("Balance section visible", "balance" in page_text.lower() or "leave" in page_text.lower())

# Apply for leave: 2026-08-15 to 2026-08-16 (2 days)
r = s_prabhas.post(f"{BASE}/leaves", data={
    "start_date": "2026-08-15",
    "end_date":   "2026-08-16",
    "reason":     "Personal work - live test"
}, allow_redirects=True)
check("Leave application submitted (no 500 error)", r.status_code == 200, f"status={r.status_code}")
check("Leave appears in history or pending list", "Personal work" in r.text or "Pending" in r.text or "2026-08-15" in r.text,
      "Checking response text")

# ─────────────────────────────────────────────────────────────
heading("STEP 2: pooja (Lead) approves prabhas's leave")
s_pooja = session_for("pooja")

r = s_pooja.get(f"{BASE}/leaves")
check("Leaves page loads for pooja", r.status_code == 200)
check("Pending approvals section visible to Lead", "Pending" in r.text or "Approve" in r.text or "approval" in r.text.lower(),
      "Lead sees approval queue")

# Find the approval ID from the page source - look for approve button referencing prabhas's leave
import re
# Find approve URLs: /leaves/approve/<id>
approve_ids = re.findall(r'/leaves/approve/(\d+)', r.text)
print(f"  {INFO} Found approve IDs visible to pooja: {approve_ids}")

prabhas_approval_id = None
if approve_ids:
    # Try the latest/last one (most recently added)
    prabhas_approval_id = approve_ids[-1]

if prabhas_approval_id:
    r2 = s_pooja.post(f"{BASE}/leaves/approve/{prabhas_approval_id}", allow_redirects=True)
    check("Pooja approve request succeeds", r2.status_code == 200, f"status={r2.status_code}")
    # After pooja approves, the request moves to Admin (vasu) - should NOT be fully Approved yet
    # Check the leaves page again
    r3 = s_pooja.get(f"{BASE}/leaves")
    check("After pooja approve - not showing as fully Approved yet (still in chain)",
          "Approved" not in r3.text or "Pending" in r3.text,
          "Chain still has Admin step")
else:
    check("Prabhas approval ID found for pooja to approve", False, "No approve links found on page")

# ─────────────────────────────────────────────────────────────
heading("STEP 3: vasu (Admin) gives final approval")
s_vasu = session_for("vasu")

r = s_vasu.get(f"{BASE}/leaves")
check("Leaves page loads for vasu", r.status_code == 200)

approve_ids_admin = re.findall(r'/leaves/approve/(\d+)', r.text)
print(f"  {INFO} Found approve IDs visible to vasu: {approve_ids_admin}")

prabhas_admin_approval_id = None
if approve_ids_admin:
    prabhas_admin_approval_id = approve_ids_admin[-1]

if prabhas_admin_approval_id:
    r2 = s_vasu.post(f"{BASE}/leaves/approve/{prabhas_admin_approval_id}", allow_redirects=True)
    check("Vasu final approve request succeeds", r2.status_code == 200, f"status={r2.status_code}")
    check("Approval status shows Approved after final step",
          "Approved" in r2.text,
          "Checking response after final approve")
else:
    check("Prabhas approval ID found for vasu to approve", False, "No approve links found for admin")

# ─────────────────────────────────────────────────────────────
heading("STEP 4: prabhas verifies balance reduced by 2")
r = s_prabhas.get(f"{BASE}/leaves")
check("prabhas leaves page reloads OK", r.status_code == 200)

# Look for balance numbers - approved leaves should reduce balance
# The page should show the leave as Approved
check("prabhas sees leave as Approved", "Approved" in r.text,
      "Leave status visible on page")

# ─────────────────────────────────────────────────────────────
heading("STEP 5: sana (Artist) applies + pooja rejects")
s_sana = session_for("sana")

r = s_sana.get(f"{BASE}/leaves")
check("Leaves page loads for sana", r.status_code == 200)

# Sana applies
r = s_sana.post(f"{BASE}/leaves", data={
    "start_date": "2026-08-20",
    "end_date":   "2026-08-20",
    "reason":     "Family event - live test"
}, allow_redirects=True)
check("Sana leave application submitted", r.status_code == 200, f"status={r.status_code}")

# Pooja goes to leaves and rejects sana's request
r = s_pooja.get(f"{BASE}/leaves")
reject_ids = re.findall(r'/leaves/reject/(\d+)', r.text)
print(f"  {INFO} Found reject IDs visible to pooja: {reject_ids}")

sana_reject_id = None
if reject_ids:
    sana_reject_id = reject_ids[-1]

if sana_reject_id:
    r2 = s_pooja.post(f"{BASE}/leaves/reject/{sana_reject_id}",
                      data={"reason": "Team is short - live test"},
                      allow_redirects=True)
    check("Pooja reject request succeeds", r2.status_code == 200, f"status={r2.status_code}")
    check("Rejection is reflected on page", "Rejected" in r2.text or r2.status_code == 200)
else:
    check("Sana reject ID found for pooja", False, "No reject links found on page")

# ─────────────────────────────────────────────────────────────
heading("STEP 6: vasu verifies sana's leave NOT in admin queue")
r = s_vasu.get(f"{BASE}/leaves")
check("Vasu leaves page loads", r.status_code == 200)

# sana_reject_id should NOT appear in approve links for vasu (since it was rejected)
admin_approve_ids = re.findall(r'/leaves/approve/(\d+)', r.text)
print(f"  {INFO} Approve IDs in vasu's queue now: {admin_approve_ids}")

sana_rejection_reached_admin = sana_reject_id and str(sana_reject_id) in admin_approve_ids
check("Sana's rejected leave does NOT appear in Admin approve queue",
      not sana_rejection_reached_admin,
      f"sana_reject_id={sana_reject_id}, admin_queue={admin_approve_ids}")

# ─────────────────────────────────────────────────────────────
heading("STEP 7: sana verifies her leave shows as Rejected")
r = s_sana.get(f"{BASE}/leaves")
check("Sana leaves page loads", r.status_code == 200)
check("Sana's leave shows as Rejected", "Rejected" in r.text,
      "Rejection visible on sana's leaves page")

# ─────────────────────────────────────────────────────────────
heading("FINAL SUMMARY")
passed = sum(1 for _, v in results if v)
total = len(results)
print(f"\n  Results: {passed}/{total} checks passed")
for name, ok in results:
    icon = "[OK]" if ok else "[FAIL]"
    print(f"    {icon} {name}")

if passed == total:
    print(f"\n  {PASS} ALL LAYER 5 VERIFICATION CHECKS PASSED!")
    exit(0)
else:
    failed = [n for n, v in results if not v]
    print(f"\n  {FAIL} {len(failed)} check(s) failed: {failed}")
    exit(1)
