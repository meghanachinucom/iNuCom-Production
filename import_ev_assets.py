import sqlite3

DB_PATH = "production.db"

EV_ASSETS_DATA = {
    140: [ # Chapter 01
        ("ev_tesla_model_03", "Done", "Done", "Done"),
        ("ev_technician", "Done", "Done", "Done"),
        ("ev_ch_01_service_center_layout", "Done", "Done", "Done"),
        ("ev_ch_01_multimeter", "Done", "Done", "Done"),
        ("ev_ch_01_oem_manual", "Done", "Done", "Done"),
        ("ev_ch_01_pad", "Done", "Done", "Done"),
        ("ev_ch_01_pen", "Done", "Done", "Done"),
        ("ev_ch_01_damaged_gloves", "Done", "Wip", "Done"),
        ("ev_ch_01_dustbin", "Done", "Done", "Done"),
        ("ev_ch_01_car_key", "Done", "Done", "Done"),
    ],
    141: [ # Chapter 02
        ("ev_ch_02_battery", "Done", "Done", "Done"),
        ("ev_tesla_model_03", "Done", "Done", "Done"),
        ("ev_ch_02_battery_pack", "Done", "Done", "Done"),
        ("ev_ch_02_battery_module", "Done", "Done", "Done"),
        ("ev_ch_02_battery_cell", "Done", "Done", "Done"),
        ("ev_ch_02_li_ion_batteries", "Done", "Done", "Done"),
        ("ev_technician", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (inverter)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (dc-dc converter)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (on-board charger)", "Done", "Done", "Done"),
        ("ev_ch_02_ni_ion_batteries", "Done", "Done", "Done"),
        ("ev_ch_02_tab", "Done", "Done", "Done"),
        ("ev_level 3_highway_charge_station", "Done", "Wip", "Wip"),
    ],
    142: [ # Chapter 03
        ("ev_ch_02_battery_pack", "Done", "Done", "Done"),
        ("ev_ch_02_battery_cell", "Done", "Done", "Done"),
        ("ev_ch_02_battery_module", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (bms)", "Done", "Yts", "Yts"),
        ("ev_tesla_model_03 (cooling system)", "Done", "Done", "Done"),
    ],
    143: [ # Chapter 04
        ("ev_tesla_model_03 (power electronics, motor,HV battery, auxilary battery, electric motor)", "Done", "Done", "Done"),
        ("ev_ch_04_electric_motor", "Done", "Done", "Done"),
        ("ev_ch_04_permanant_magnetic_motor", "Done", "Done", "Done"),
        ("ev_ch_01_oem_manual", "Done", "Done", "Done"),
    ],
    144: [ # Chapter 05
        ("ev_ch_05_igbt", "Done", "Done", "Yts"),
    ],
    145: [ # Chapter 06
        ("ev_tesla_model_03 (power electronics, motor,HV battery, auxilary battery, electric motor)", "Done", "Done", "Done"),
    ],
    146: [ # Chapter 07
        ("ev_level 3_highway_charge_station", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (power electronics, motor,HV battery, auxilary battery, electric motor)", "Done", "Done", "Done"),
        ("ev_technician", "Done", "Done", "Done"),
        ("ev_ch_02_tab", "Done", "Done", "Done"),
        ("ev_ch_01_oem_manual", "Done", "Done", "Done"),
        ("ev_ch_01_pad", "Done", "Done", "Done"),
        ("ev_ch_01_pen", "Done", "Done", "Done"),
        ("ev_level 02_charging station", "Done", "Yts", "Yts"),
        ("ev_level_01_home_charging_set", "Done", "Yts", "Yts"),
    ],
    147: [ # Chapter 08
        ("ev_tesla_model_03 (power electronics, motor,HV battery, auxilary battery, electric motor)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (thermal management system)", "Done", "Done", "Done"),
        ("ev_ch_08_coolant_can", "Yts", "Yts", "Yts"),
        ("ev_tesla_model_03 (heat exchanger)", "Done", "Done", "Done"),
    ],
    148: [ # Chapter 09
        ("ev_ch_01_obd_scanner", "Done", "Done", "Done"),
        ("ev_technician", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (power electronics, motor,HV battery, auxilary battery, electric motor)", "Done", "Done", "Done"),
    ],
    149: [ # Chapter 10
        ("ev_tesla_model_03 (power electronics, motor,HV battery, auxilary battery, electric motor)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (hydraulic friction braking)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (electric motor)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (break control module)", "Done", "Done", "Done"),
        ("ev_ch_01_obd_scanner", "Done", "Done", "Done"),
        ("ev_ch_01_service_center_layout", "Done", "Done", "Done"),
    ],
    150: [ # Chapter 11
        ("ev_tesla_model_03 (power electronics, motor,HV battery, auxilary battery, electric motor)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (Advanced Driver Assistance Systems)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (all sensors)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (Radar Sensor)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (Camera-Based System)", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (LiDAR)", "Done", "Done", "Done"),
    ],
    151: [ # Chapter 12
        ("ev_technician", "Done", "Done", "Done"),
        ("ev_tesla_model_03 (power electronics, motor,HV battery, auxilary battery, electric motor)", "Done", "Done", "Done"),
        ("ev_ch_01_pad", "Done", "Done", "Done"),
        ("ev_ch_01_pen", "Done", "Done", "Done"),
        ("ev_ch_01_obd_scanner", "Done", "Done", "Done"),
        ("ev_ch_01_toolbox", "Done", "Done", "Done"),
        ("ev_ch_01_tools_on_table", "Done", "Done", "Done"),
    ]
}

PIPELINE_STAGES = [
    'Reference', 'Explanation', 'Modeling', 'Texturing', 'Rig', 
    'Voice Over', 'Narration', 'Storyboards', 'Scene-wise Assets', 
    'Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering', '3D Comp & Motion Graphics'
]

def import_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    chapter_ids = list(EV_ASSETS_DATA.keys())
    placeholders = ','.join('?' for _ in chapter_ids)

    # Delete existing asset files for EV Project Chapters 1..12
    c.execute(f"""
        SELECT id FROM files 
        WHERE chapter_id IN ({placeholders}) 
          AND file_type = 'Asset'
    """, chapter_ids)
    old_asset_ids = [row[0] for row in c.fetchall()]

    print(f"[INFO] Found {len(old_asset_ids)} old asset files to delete in EV Project Chapters 1..12.")

    if old_asset_ids:
        fp_placeholders = ','.join('?' for _ in old_asset_ids)
        c.execute(f"DELETE FROM file_pipeline WHERE file_id IN ({fp_placeholders})", old_asset_ids)
        c.execute(f"DELETE FROM files WHERE id IN ({fp_placeholders})", old_asset_ids)
        print(f"[INFO] Deleted old asset files and their file_pipeline rows.")

    total_assets_created = 0

    for chap_id, assets in EV_ASSETS_DATA.items():
        for asset_name, mdl_st, tex_st, rig_st in assets:
            c.execute("""
                INSERT INTO files (chapter_id, name, description, status, file_type, is_comp_ai, comp_ai_artist_id, assigned_to)
                VALUES (?, ?, ?, 'Done', 'Asset', 0, NULL, NULL)
            """, (chap_id, asset_name, f"EV Asset File {asset_name}"))
            
            file_id = c.lastrowid
            total_assets_created += 1

            # Populate file_pipeline rows for all 15 stages
            for stage in PIPELINE_STAGES:
                if stage in ['Voice Over', 'Narration', 'Storyboards', 'Scene-wise Assets']:
                    st = 'Done'
                elif stage == 'Modeling':
                    st = mdl_st.capitalize()
                elif stage == 'Texturing':
                    st = tex_st.capitalize()
                elif stage == 'Rig':
                    st = rig_st.capitalize()
                else:
                    st = 'Done'

                c.execute("""
                    INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points, remarks)
                    VALUES (?, ?, ?, NULL, 50, NULL)
                """, (file_id, stage, st))

    conn.commit()
    conn.close()
    print(f"[SUCCESS] Successfully imported {total_assets_created} asset files for EV Project Chapters 1..12 without '_rig' suffix!")

if __name__ == "__main__":
    import_data()
