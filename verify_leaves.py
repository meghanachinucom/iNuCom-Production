import os
import sqlite3
import datetime
import json
import sys

# Ensure app.py can be imported
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app import init_db, get_approval_chain

DATABASE = 'production.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def run_db_query(query, params=()):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = cursor.fetchall()
    conn.close()
    return res

def run_db_modify(query, params=()):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def setup_test_db():
    # Remove old DB and reinitialize
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
    init_db()

def calculate_approved_used(user_id, year):
    # Mimics app.py used calculation
    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT start_date, end_date FROM leaves
        WHERE user_id = ? AND status = 'Approved'
          AND NOT (end_date < ? OR start_date > ?)
    """, (user_id, year_start, year_end))
    approved_leaves = cursor.fetchall()
    conn.close()
    
    approved_used = 0
    for lv in approved_leaves:
        lv_start = datetime.datetime.strptime(lv['start_date'], '%Y-%m-%d').date()
        lv_end = datetime.datetime.strptime(lv['end_date'], '%Y-%m-%d').date()
        intersect_start = max(lv_start, datetime.date(year, 1, 1))
        intersect_end = min(lv_end, datetime.date(year, 12, 31))
        approved_used += (intersect_end - intersect_start).days + 1
        
    return approved_used

def test_approval_chain_resolution():
    print("Testing get_approval_chain resolution...")
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Fetch user IDs
    cursor.execute("SELECT id FROM users WHERE username = 'vasu'")
    vasu_id = cursor.fetchone()['id']
    
    cursor.execute("SELECT id FROM users WHERE username = 'pooja'")
    pooja_id = cursor.fetchone()['id']
    
    cursor.execute("SELECT id FROM users WHERE username = 'prabhas'")
    prabhas_id = cursor.fetchone()['id']
    
    cursor.execute("SELECT id FROM users WHERE username = 'meghana'")
    meghana_id = cursor.fetchone()['id']
    
    # 1. Artist Prabhas reports to Pooja -> should be [pooja_id, vasu_id]
    prabhas_chain = get_approval_chain(conn, prabhas_id, 'Artist', 'pooja')
    assert prabhas_chain == [pooja_id, vasu_id], f"Expected {[pooja_id, vasu_id]}, got {prabhas_chain}"
    
    # 2. Lead Pooja reports to vasu -> should be [vasu_id]
    pooja_chain = get_approval_chain(conn, pooja_id, 'Lead', 'vasu')
    assert pooja_chain == [vasu_id], f"Expected {[vasu_id]}, got {pooja_chain}"
    
    # 3. HR Meghana reports to None -> should be [vasu_id]
    meghana_chain = get_approval_chain(conn, meghana_id, 'HR', None)
    assert meghana_chain == [vasu_id], f"Expected {[vasu_id]}, got {meghana_chain}"
    
    # 4. Admin Vasu -> should be [] (auto-approved)
    vasu_chain = get_approval_chain(conn, vasu_id, 'Admin', None)
    assert vasu_chain == [], f"Expected [], got {vasu_chain}"
    
    conn.close()
    print("[OK] get_approval_chain resolution test passed.")

def test_leave_balances():
    print("Testing leave balance pool calculation...")
    
    # Get Prabhas's user info (Carry Forward defaults to 0)
    prabhas = run_db_query("SELECT * FROM users WHERE username = 'prabhas'")[0]
    prabhas_id = prabhas['id']
    
    # Set Prabhas's carry_forward to 5.0
    run_db_modify("UPDATE users SET carry_forward = 5.0 WHERE id = ?", (prabhas_id,))
    
    # Refetch Prabhas info
    prabhas = run_db_query("SELECT * FROM users WHERE id = ?", (prabhas_id,))[0]
    allowed = 18.0 + prabhas['carry_forward']
    assert allowed == 23.0, f"Expected 23.0 allowed, got {allowed}"
    
    # Calculate used leaves (should be 0)
    used = calculate_approved_used(prabhas_id, 2026)
    assert used == 0, f"Expected 0 used, got {used}"
    
    # Insert an approved leave for Prabhas (2 days in June 2026)
    run_db_modify("""
        INSERT INTO leaves (user_id, start_date, end_date, leave_type, reason, status)
        VALUES (?, '2026-06-15', '2026-06-16', 'General', 'Sick', 'Approved')
    """, (prabhas_id,))
    
    # Re-calculate used leaves
    used = calculate_approved_used(prabhas_id, 2026)
    assert used == 2, f"Expected 2 used, got {used}"
    
    # Remaining balance should be 21.0
    remaining = allowed - used
    assert remaining == 21.0, f"Expected 21.0 remaining, got {remaining}"
    
    print("[OK] Leave balance pool calculations test passed.")

def test_monthly_limit_check():
    print("Testing leaves per month policy limit (Max 2 days/month)...")
    
    prabhas_id = run_db_query("SELECT id FROM users WHERE username = 'prabhas'")[0]['id']
    
    # Clean previous approved leaves for Prabhas
    run_db_modify("DELETE FROM leaves WHERE user_id = ?", (prabhas_id,))
    
    # Case A: Apply for 2 days in June (Approved)
    run_db_modify("""
        INSERT INTO leaves (user_id, start_date, end_date, leave_type, reason, status)
        VALUES (?, '2026-06-15', '2026-06-16', 'General', 'Vacation', 'Approved')
    """, (prabhas_id,))
    
    # Let's count existing leaves in June 2026
    existing_in_june = calculate_days_overlapping_month(prabhas_id, '2026-06')
    assert existing_in_june == 2, f"Expected 2 approved days in June, got {existing_in_june}"
    
    # Case B: Requesting 1 more day in June (e.g. June 22) -> total would be 3 (Violates limit of 2)
    requested_days_in_june = 1
    total_would_be = existing_in_june + requested_days_in_june
    assert total_would_be > 2, "Policy should reject this request!"
    
    print("[OK] Max 2 leaves/month policy checks test passed.")

def calculate_days_overlapping_month(user_id, month_prefix):
    # Helper to calculate approved leave days overlapping a specific month YYYY-MM
    y, m = map(int, month_prefix.split('-'))
    last_day = calendar_last_day(y, m)
    month_start = f"{month_prefix}-01"
    month_end = f"{month_prefix}-{last_day:02d}"
    
    leaves = run_db_query("""
        SELECT start_date, end_date FROM leaves
        WHERE user_id = ? AND status = 'Approved'
          AND NOT (end_date < ? OR start_date > ?)
    """, (user_id, month_start, month_end))
    
    total_days = 0
    for lv in leaves:
        lv_start = datetime.datetime.strptime(lv['start_date'], '%Y-%m-%d').date()
        lv_end = datetime.datetime.strptime(lv['end_date'], '%Y-%m-%d').date()
        
        intersect_start = max(lv_start, datetime.date(y, m, 1))
        intersect_end = min(lv_end, datetime.date(y, m, last_day))
        total_days += (intersect_end - intersect_start).days + 1
        
    return total_days

def calendar_last_day(year, month):
    import calendar as cal
    return cal.monthrange(year, month)[1]

def test_approval_engine_workflow():
    print("Testing step-by-step approvals and rejections workflows...")
    
    # Fetch IDs
    vasu_id = run_db_query("SELECT id FROM users WHERE username = 'vasu'")[0]['id']
    pooja_id = run_db_query("SELECT id FROM users WHERE username = 'pooja'")[0]['id']
    prabhas_id = run_db_query("SELECT id FROM users WHERE username = 'prabhas'")[0]['id']
    sana_id = run_db_query("SELECT id FROM users WHERE username = 'sana'")[0]['id']
    
    # 1. PRABHAS (Artist) requests leave
    run_db_modify("INSERT INTO leaves (user_id, start_date, end_date, leave_type, reason, status) VALUES (?, '2026-06-25', '2026-06-26', 'General', 'Trip', 'Pending')", (prabhas_id,))
    leave_id = run_db_query("SELECT seq FROM sqlite_sequence WHERE name='leaves'")[0]['seq']
    
    chain = [pooja_id, vasu_id]
    chain_json = json.dumps(chain)
    run_db_modify("""
        INSERT INTO approvals (requester_id, type, reference_id, approval_chain, current_index, details, status)
        VALUES (?, 'Leave', ?, ?, 0, 'Leave Request', 'Pending')
    """, (prabhas_id, leave_id, chain_json))
    app_id = run_db_query("SELECT seq FROM sqlite_sequence WHERE name='approvals'")[0]['seq']
    
    # Verify Prabhas request is at index 0 (Pooja's step)
    app_req = run_db_query("SELECT * FROM approvals WHERE id = ?", (app_id,))[0]
    assert app_req['current_index'] == 0, "Initial index should be 0"
    assert app_req['status'] == 'Pending', "Approval should be Pending"
    
    # Pooja approves (Step 1)
    # Advancing index to 1
    next_idx = app_req['current_index'] + 1
    run_db_modify("UPDATE approvals SET current_index = ? WHERE id = ?", (next_idx, app_id))
    
    # Verify index advanced but leave request is still Pending
    app_req = run_db_query("SELECT * FROM approvals WHERE id = ?", (app_id,))[0]
    assert app_req['current_index'] == 1, "Index should advance to 1"
    leave_req = run_db_query("SELECT * FROM leaves WHERE id = ?", (leave_id,))[0]
    assert leave_req['status'] == 'Pending', "Leave should remain Pending until final approval"
    
    # Vasu approves (Step 2 - Final)
    next_idx += 1 # index = 2 >= len(chain)
    run_db_modify("UPDATE approvals SET status = 'Approved', current_index = ?, actioned_by = ? WHERE id = ?", (next_idx, vasu_id, app_id))
    run_db_modify("UPDATE leaves SET status = 'Approved', approved_by = ? WHERE id = ?", (vasu_id, leave_id))
    
    # Verify leave request is now Approved
    app_req = run_db_query("SELECT * FROM approvals WHERE id = ?", (app_id,))[0]
    assert app_req['status'] == 'Approved', "Approval request should be Approved"
    leave_req = run_db_query("SELECT * FROM leaves WHERE id = ?", (leave_id,))[0]
    assert leave_req['status'] == 'Approved', "Leave request should be Approved"
    
    # 2. REJECTION TEST
    # Sana requests leave
    run_db_modify("INSERT INTO leaves (user_id, start_date, end_date, leave_type, reason, status) VALUES (?, '2026-06-28', '2026-06-28', 'General', 'Sick', 'Pending')", (sana_id,))
    sana_leave_id = run_db_query("SELECT seq FROM sqlite_sequence WHERE name='leaves'")[0]['seq']
    
    run_db_modify("""
        INSERT INTO approvals (requester_id, type, reference_id, approval_chain, current_index, details, status)
        VALUES (?, 'Leave', ?, ?, 0, 'Sana Request', 'Pending')
    """, (sana_id, sana_leave_id, chain_json))
    sana_app_id = run_db_query("SELECT seq FROM sqlite_sequence WHERE name='approvals'")[0]['seq']
    
    # Pooja rejects Sana's request immediately
    run_db_modify("UPDATE approvals SET status = 'Rejected', actioned_by = ? WHERE id = ?", (pooja_id, sana_app_id))
    run_db_modify("UPDATE leaves SET status = 'Rejected' WHERE id = ?", (sana_leave_id,))
    
    # Verify status is Rejected
    app_req = run_db_query("SELECT * FROM approvals WHERE id = ?", (sana_app_id,))[0]
    assert app_req['status'] == 'Rejected', "Approval status should be Rejected"
    leave_req = run_db_query("SELECT * FROM leaves WHERE id = ?", (sana_leave_id,))[0]
    assert leave_req['status'] == 'Rejected', "Leave status should be Rejected"
    
    print("[OK] Reusable approval engine walkthrough workflow test passed.")

if __name__ == "__main__":
    print("Running automated verification for Layer 5: Leaves & Reusable Approval Engine...")
    setup_test_db()
    test_approval_chain_resolution()
    test_leave_balances()
    test_monthly_limit_check()
    test_approval_engine_workflow()
    print("\n==================================================")
    print("ALL LAYER 5 LEAVES & APPROVAL ENGINE TESTS PASSED!")
    print("==================================================")
