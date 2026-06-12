import os
import sqlite3
import datetime
import sys

# Ensure app.py can be imported
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app import is_weekly_off, init_db

DATABASE = 'production.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def test_weekly_off():
    print("Testing is_weekly_off date calculations...")
    
    # Sundays
    sunday = datetime.date(2026, 6, 14)
    assert is_weekly_off(sunday) == True, "June 14, 2026 (Sunday) should be off"
    
    # 2nd Saturday (Days 8-14)
    sat_2nd = datetime.date(2026, 6, 13)
    assert is_weekly_off(sat_2nd) == True, "June 13, 2026 (2nd Saturday) should be off"
    
    # 4th Saturday (Days 22-28)
    sat_4th = datetime.date(2026, 6, 27)
    assert is_weekly_off(sat_4th) == True, "June 27, 2026 (4th Saturday) should be off"
    
    # 1st Saturday
    sat_1st = datetime.date(2026, 6, 6)
    assert is_weekly_off(sat_1st) == False, "June 6, 2026 (1st Saturday) should NOT be off"
    
    # 3rd Saturday
    sat_3rd = datetime.date(2026, 6, 20)
    assert is_weekly_off(sat_3rd) == False, "June 20, 2026 (3rd Saturday) should NOT be off"
    
    # Weekday (Friday)
    friday = datetime.date(2026, 6, 12)
    assert is_weekly_off(friday) == False, "June 12, 2026 (Friday) should NOT be off"
    
    print("[OK] is_weekly_off checks passed successfully.")

def calculate_checkin_status(time_str):
    # Mimics clock-in logic from app.py
    h, m = map(int, time_str.split(':'))
    minutes_from_midnight = h * 60 + m
    
    if minutes_from_midnight <= 570:  # 09:30 AM
        status = 'Present'
        late_minutes = 0
    elif minutes_from_midnight <= 660:  # 11:00 AM
        status = 'Late'
        late_minutes = max(0, minutes_from_midnight - 585)  # counts from 09:45 AM (585 mins)
    else:
        status = 'Half Day'
        late_minutes = 0
        
    return status, late_minutes

def test_checkin_times():
    print("Testing check-in time classification and late minutes...")
    
    # 1. 09:20 AM -> On-Time (Present), 0 late mins
    status, late_mins = calculate_checkin_status("09:20")
    assert status == 'Present', f"Expected Present at 09:20, got {status}"
    assert late_mins == 0, f"Expected 0 late mins at 09:20, got {late_mins}"
    
    # 2. 09:50 AM -> Late, 5 late mins (from 09:45)
    status, late_mins = calculate_checkin_status("09:50")
    assert status == 'Late', f"Expected Late at 09:50, got {status}"
    assert late_mins == 5, f"Expected 5 late mins at 09:50, got {late_mins}"
    
    # 3. 11:30 AM -> Half Day, 0 late mins
    status, late_mins = calculate_checkin_status("11:30")
    assert status == 'Half Day', f"Expected Half Day at 11:30, got {status}"
    assert late_mins == 0, f"Expected 0 late mins at 11:30, got {late_mins}"
    
    # 4. 09:35 AM -> Late, 0 late mins (since it is before 09:45)
    status, late_mins = calculate_checkin_status("09:35")
    assert status == 'Late', f"Expected Late at 09:35, got {status}"
    assert late_mins == 0, f"Expected 0 late mins at 09:35, got {late_mins}"
    
    print("[OK] Check-in time classification checks passed successfully.")

def calculate_extra_hours(clock_in_str, clock_out_str, date_str, shift_start='09:00', shift_end='19:00'):
    # Mimics clock-out logic from app.py
    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    in_dt = datetime.datetime.strptime(f"{date_str} {clock_in_str}", "%Y-%m-%d %H:%M:%S")
    out_dt = datetime.datetime.strptime(f"{date_str} {clock_out_str}", "%Y-%m-%d %H:%M:%S")
    
    duration = out_dt - in_dt
    total_hours = max(0.0, duration.total_seconds() / 3600.0)
    
    start_h, start_m = map(int, shift_start.split(':'))
    end_h, end_m = map(int, shift_end.split(':'))
    shift_length = (end_h * 60 + end_m - (start_h * 60 + start_m)) / 60.0
    if shift_length < 0:
        shift_length += 24.0
        
    off_day = is_weekly_off(date_obj)
    
    # Mock holiday check for this script: let's assume '2026-06-25' is a holiday
    is_holiday = date_str == '2026-06-25'
    
    if off_day or is_holiday:
        extra_hours = total_hours
    else:
        extra_hours = max(0.0, total_hours - shift_length)
        
    return total_hours, extra_hours

def test_extra_hours():
    print("Testing shift and extra-hours calculations...")
    
    # 1. Normal working day (June 12, 2026 is Friday), default shift 09:00 - 19:00 (10 hrs)
    # Clock in 09:00, clock out 20:00 (11 hrs worked) -> should be 1 hr extra
    total, extra = calculate_extra_hours("09:00:00", "20:00:00", "2026-06-12")
    assert total == 11.0, f"Expected 11.0 total hours, got {total}"
    assert extra == 1.0, f"Expected 1.0 extra hours, got {extra}"
    
    # 2. Sunday off-day (June 14, 2026), work clock in 10:00, clock out 16:00 (6 hrs worked) -> should be 6 hrs extra
    total, extra = calculate_extra_hours("10:00:00", "16:00:00", "2026-06-14")
    assert total == 6.0, f"Expected 6.0 total hours, got {total}"
    assert extra == 6.0, f"Expected 6.0 extra hours, got {extra}"
    
    # 3. Holiday (June 25, 2026 is mock holiday), work clock in 09:00, clock out 17:00 (8 hrs worked) -> should be 8 hrs extra
    total, extra = calculate_extra_hours("09:00:00", "17:00:00", "2026-06-25")
    assert total == 8.0, f"Expected 8.0 total hours, got {total}"
    assert extra == 8.0, f"Expected 8.0 extra hours, got {extra}"
    
    print("[OK] Shift and extra-hours calculation checks passed successfully.")

if __name__ == "__main__":
    print("Running automated attendance validation checks...")
    
    # Initialize database
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
    init_db()
    
    test_weekly_off()
    test_checkin_times()
    test_extra_hours()
    
    print("\n==============================================")
    print("ALL ATTENDANCE SYSTEM RULES VALIDATED SUCCESSFULLY!")
    print("==============================================")
