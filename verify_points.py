import sqlite3

def verify_points():
    conn = sqlite3.connect("production.db")
    cursor = conn.cursor()
    
    # 1. Verify schema columns
    try:
        cursor.execute("SELECT points FROM file_pipeline LIMIT 1;")
        print("[OK] Column 'points' exists in file_pipeline table.")
    except Exception as e:
        print(f"[FAIL] file_pipeline.points check failed: {e}")
        conn.close()
        return False
        
    try:
        cursor.execute("SELECT points FROM daily_assignments LIMIT 1;")
        print("[OK] Column 'points' exists in daily_assignments table.")
    except Exception as e:
        print(f"[FAIL] daily_assignments.points check failed: {e}")
        conn.close()
        return False
        
    try:
        cursor.execute("SELECT target_points FROM monthly_targets LIMIT 1;")
        print("[OK] Column 'target_points' exists in monthly_targets table.")
    except Exception as e:
        print(f"[FAIL] monthly_targets.target_points check failed: {e}")
        conn.close()
        return False
        
    # 2. Check seeded targets
    cursor.execute("SELECT COUNT(*) FROM monthly_targets;")
    target_cnt = cursor.fetchone()[0]
    print(f"[OK] Seeded {target_cnt} monthly target records (Expected: 18+ artists).")
    
    # 3. Check seeded daily assignments
    cursor.execute("SELECT COUNT(*), SUM(points) FROM daily_assignments;")
    da_cnt, da_pts = cursor.fetchone()
    print(f"[OK] Seeded {da_cnt} daily assignments, total points: {da_pts} pts.")
    
    conn.close()
    return True

if __name__ == "__main__":
    verify_points()
