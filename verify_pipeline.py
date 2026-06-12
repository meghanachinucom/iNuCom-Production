import sqlite3

def verify_pipeline():
    conn = sqlite3.connect("production.db")
    cursor = conn.cursor()
    
    # Check if files have content_released_at column
    try:
        cursor.execute("SELECT name, content_released_at FROM files LIMIT 1;")
        res = cursor.fetchone()
        print("[OK] Column 'content_released_at' is present in files table.")
    except Exception as e:
        print(f"[FAIL] Column 'content_released_at' check failed: {e}")
        conn.close()
        return False
        
    # Check if Foundation World project exists
    cursor.execute("SELECT id FROM projects WHERE name='Foundation World';")
    proj = cursor.fetchone()
    if proj:
        print("[OK] Project 'Foundation World' exists.")
        proj_id = proj[0]
        
        # Check chapters
        cursor.execute("SELECT id, name FROM chapters WHERE project_id=?;", (proj_id,))
        chapters = {row[1]: row[0] for row in cursor.fetchall()}
        
        if 'ch_12' in chapters and 'ch_13' in chapters:
            print("[OK] Chapters 'ch_12' and 'ch_13' exist.")
            
            # Check file count
            cursor.execute("SELECT COUNT(*) FROM files WHERE chapter_id=?;", (chapters['ch_12'],))
            cnt12 = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM files WHERE chapter_id=?;", (chapters['ch_13'],))
            cnt13 = cursor.fetchone()[0]
            
            print(f"[OK] Chapter 12 has {cnt12} files (Expected: 8).")
            print(f"[OK] Chapter 13 has {cnt13} files (Expected: 8).")
            
            if cnt12 == 8 and cnt13 == 8:
                # Check a specific file's pipeline
                cursor.execute("SELECT id FROM files WHERE name='FW_12_04_TowerMDL';")
                f = cursor.fetchone()
                if f:
                    file_id = f[0]
                    cursor.execute("SELECT step_name, status, assigned_to FROM file_pipeline WHERE file_id=?;", (file_id,))
                    steps = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
                    
                    print(f"\nPipeline status details for 'FW_12_04_TowerMDL':")
                    for step in ['Content', 'Modeling', 'Texturing', 'Rig', 'Animation']:
                        if step in steps:
                            status, assigned = steps[step]
                            print(f"  {step}: status='{status}', assigned='{assigned}'")
                        else:
                            print(f"  [FAIL] Step '{step}' missing in pipeline!")
                            conn.close()
                            return False
                else:
                    print("[FAIL] File 'FW_12_04_TowerMDL' not found!")
                    conn.close()
                    return False
            else:
                print(f"[FAIL] Expected 8 files per chapter, found {cnt12} and {cnt13}.")
                conn.close()
                return False
        else:
            print("[FAIL] Chapters 'ch_12' or 'ch_13' missing!")
            conn.close()
            return False
    else:
        print("[FAIL] Project 'Foundation World' not found!")
        conn.close()
        return False
        
    conn.close()
    return True

if __name__ == "__main__":
    verify_pipeline()
