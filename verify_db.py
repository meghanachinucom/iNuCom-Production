import os
import sqlite3
from werkzeug.security import check_password_hash

def verify_db():
    db_path = "production.db"
    
    if not os.path.exists(db_path):
        print("Error: production.db does not exist yet!")
        return False
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    required_tables = [
        "users", "projects", "chapters", "files", "file_pipeline", "teams", 
        "daily_assignments", "eod_validations", "attendance", "leaves", 
        "permissions", "points", "monthly_targets", "holidays", "approvals", "activity_log"
    ]
    
    print("\n--- TABLE CHECK ---")
    missing_tables = []
    for table in required_tables:
        if table in tables:
            print(f"[OK] Table '{table}' exists.")
        else:
            print(f"[FAIL] Table '{table}' is missing!")
            missing_tables.append(table)
            
    if missing_tables:
        print(f"Error: Missing tables: {missing_tables}")
        conn.close()
        return False
        
    # Check users count and check password hash of 'vasu'
    cursor.execute("SELECT COUNT(*) FROM users;")
    user_count = cursor.fetchone()[0]
    print(f"\nTotal users in DB: {user_count} (Expected: 28)")
    
    cursor.execute("SELECT name, username, password_hash, role, must_change_password FROM users WHERE username='vasu';")
    user = cursor.fetchone()
    if user:
        name, username, pwd_hash, role, must_change = user
        print(f"\nFound user '{username}':")
        print(f"  Name: {name}")
        print(f"  Role: {role}")
        print(f"  Must Change Password: {must_change} (Expected: 1)")
        
        pwd_ok = check_password_hash(pwd_hash, "inucom@123")
        print(f"  Password validation for 'inucom@123': {'[OK]' if pwd_ok else '[FAIL]'}")
        
        if not pwd_ok or must_change != 1:
            conn.close()
            return False
    else:
        print("Error: User 'vasu' not found!")
        conn.close()
        return False
        
    print("\nAll database checks passed successfully!")
    conn.close()
    return True

if __name__ == "__main__":
    verify_db()
