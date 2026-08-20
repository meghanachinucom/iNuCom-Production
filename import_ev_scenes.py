import sqlite3

DB_PATH = "production.db"

# Chapter ID Map for EV Project (project_id = 13)
# Chapter 01 -> 140 ... Chapter 15 -> 154
CHAPTER_MAP = {i: 139 + i for i in range(1, 16)}

# Standard pipeline stages for Scene files
PIPELINE_STAGES = [
    'Reference', 'Explanation', 'Modeling', 'Texturing', 'Rig', 
    'Voice Over', 'Narration', 'Storyboards', 'Scene-wise Assets', 
    'Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering', '3D Comp & Motion Graphics'
]

# Exact Chapter Ranges specified by User:
# ch 1 - 01 to 40
# ch 2 - 54 to 80
# ch 3 - 89 to 114
# ch 4 - 123 to 148
# ch 5 - 157 to 183
# ch 6 - 193 to 213
# ch 7 - 222 to 243
# ch 8 - 252 to 277
# ch 9 - 287 to 309
# ch 10 - 318 to 339
# ch 11 - 348 to 368
# ch 12 - 377 to 397
# ch 13 - 407 to 452
# ch 14 - 453 to 499
# ch 15 - 500 to 550

CHAPTER_RANGES = {
    140: (1, 40),
    141: (54, 80),
    142: (89, 114),
    143: (123, 148),
    144: (157, 183),
    145: (193, 213),
    146: (222, 243),
    147: (252, 277),
    148: (287, 309),
    149: (318, 339),
    150: (348, 368),
    151: (377, 397),
    152: (407, 452),
    153: (453, 499),
    154: (500, 550),
}

# Special classification maps for known specific files
# (e.g. Reuse, Hold, 3D, Comp AI)
# Default for odd/even or Comp AI in Chapters 7,9,13,14,15
COMP_AI_SCENES_CH1 = {3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 26, 29, 30, 32, 35, 36, 37, 38}
REUSE_SCENES_CH1 = {5, 17, 23, 34}

def import_scenes():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    chapter_ids = list(CHAPTER_RANGES.keys())
    placeholders = ','.join('?' for _ in chapter_ids)

    # Delete existing scene files for EV Project Chapters 1..15
    c.execute(f"""
        SELECT id FROM files 
        WHERE chapter_id IN ({placeholders}) 
          AND file_type = 'Scene'
          AND LOWER(name) NOT LIKE '%obd_scanner%'
    """, chapter_ids)
    old_scene_ids = [row[0] for row in c.fetchall()]

    print(f"[INFO] Found {len(old_scene_ids)} old scene files to delete in EV Project Chapters 1..15.")

    if old_scene_ids:
        fp_placeholders = ','.join('?' for _ in old_scene_ids)
        c.execute(f"DELETE FROM file_pipeline WHERE file_id IN ({fp_placeholders})", old_scene_ids)
        c.execute(f"DELETE FROM files WHERE id IN ({fp_placeholders})", old_scene_ids)
        print(f"[INFO] Deleted old scene files and their file_pipeline rows.")

    total_scenes_created = 0

    for chap_id, (start_num, end_num) in CHAPTER_RANGES.items():
        chap_num = chap_id - 139
        for num in range(start_num, end_num + 1):
            # Raw scene file name: he_veh_tad_01 ... he_veh_tad_550
            if num < 10:
                scene_name = f"he_veh_tad_0{num}"
            else:
                scene_name = f"he_veh_tad_{num}"

            # Classification logic
            if chap_id == 140:
                if num in COMP_AI_SCENES_CH1:
                    file_class = "comp AI"
                elif num in REUSE_SCENES_CH1:
                    file_class = "Reuse"
                else:
                    file_class = "2D"
            elif chap_id in [146, 148, 152, 153, 154]:
                # Chapters 7, 9, 13, 14, 15 are predominantly Comp AI
                file_class = "comp AI"
            else:
                # Chapters 2, 3, 4, 5, 6, 8, 10, 11, 12 mixed 3D/Comp AI
                file_class = "comp AI" if num % 2 == 1 else "3D"

            is_comp = 1 if file_class.lower() in ['comp ai', '2d comp', 'comp'] else 0

            # Main file status calculation
            if is_comp:
                # Scene 378 or 478 (in Chapter 14 range 453..499) pending logic
                if num in [378, 478]:
                    file_status = "Pending"
                else:
                    file_status = "Done"
            elif file_class.lower() in ['reuse', 'hold']:
                file_status = "Wip"
            else:
                file_status = "Pending"

            c.execute("""
                INSERT INTO files (chapter_id, name, description, status, file_type, is_comp_ai, comp_ai_artist_id, assigned_to)
                VALUES (?, ?, ?, ?, 'Scene', ?, NULL, NULL)
            """, (chap_id, scene_name, f"EV Scene File {scene_name}", file_status, is_comp))
            
            file_id = c.lastrowid
            total_scenes_created += 1

            # Populate file_pipeline rows for all 15 stages
            for stage in PIPELINE_STAGES:
                if stage in ['Voice Over', 'Narration', 'Storyboards']:
                    st = 'Done'
                    rem = None
                elif is_comp:
                    if stage == '3D Comp & Motion Graphics':
                        st = 'Yts' if num in [378, 478] else 'Done'
                        rem = None
                    else:
                        st = 'Done'
                        rem = 'Bypassed for 2D Comp AI'
                else:
                    if file_class.lower() in ['reuse', 'hold']:
                        if stage in ['Animation', 'Rendering', '3D Comp & Motion Graphics']:
                            st = 'Wip'
                        else:
                            st = 'Done' if stage in ['Reference', 'Explanation', 'Modeling', 'Texturing', 'Rig', 'Scene-wise Assets'] else 'Yts'
                            rem = None
                    else:
                        if stage == 'Animation':
                            st = 'Yts'
                        elif stage in ['Reference', 'Explanation', 'Modeling', 'Texturing', 'Rig', 'Scene-wise Assets']:
                            st = 'Yts'
                            rem = 'Not applicable for Scene files'
                        else:
                            st = 'Yts'
                            rem = None

                c.execute("""
                    INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points, remarks)
                    VALUES (?, ?, ?, NULL, 50, ?)
                """, (file_id, stage, st, rem))

    conn.commit()
    conn.close()
    print(f"[SUCCESS] Imported {total_scenes_created} exact scene files for EV Project Chapters 1..15!")

if __name__ == "__main__":
    import_scenes()
