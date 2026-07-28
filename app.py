import os
import sqlite3
import datetime
import calendar
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'production.db'
SCHEMA_FILE = 'schema.sql'

app = Flask(__name__)
app.secret_key = 'inucom_production_tracker_secret_key_LAN_offline_2026'

@app.template_filter('strftime')
def _strftime_filter(value, fmt='%A'):
    """Format a date string (YYYY-MM-DD) with strftime."""
    try:
        return datetime.datetime.strptime(value, '%Y-%m-%d').strftime(fmt)
    except Exception:
        return value

@app.template_filter('time12')
def _time12_filter(value):
    """Convert a time string (HH:MM:SS or HH:MM) to 12-hour format (I:MM p)."""
    if not value:
        return ''
    if 'AM' in value or 'PM' in value or 'am' in value or 'pm' in value:
        return value
    try:
        t = datetime.datetime.strptime(value.split('.')[0], '%H:%M:%S')
        return t.strftime('%I:%M %p').lstrip('0')
    except Exception:
        try:
            t = datetime.datetime.strptime(value.split('.')[0], '%H:%M')
            return t.strftime('%I:%M %p').lstrip('0')
        except Exception:
            return value

# Pipeline Constants
PIPELINE_STAGES = [
    'Content',
    'Modeling',
    'Texturing',
    'Rig',
    'Animation',
    'FBX export',
    'VFX',
    'Lightning',
    'Rendering',
    '3D Comp',
    'Motion graphics',
    'VR'
]

STAGE_TEAMS = {
    'Content': 'Content',
    'Modeling': 'Modeling',
    'Texturing': 'Texturing',
    'Rig': 'Rig',
    'Animation': 'Animation',
    'FBX export': 'FBX export',
    'VFX': 'VFX',
    'Lightning': 'Lightning',
    'Rendering': 'Rendering',
    '3D Comp': '3D Comp',
    'Motion graphics': 'Motion graphics',
    'VR': 'VR'
}

SEEDED_USERS = [
    {"name": "Vasu", "username": "vasu", "role": "Admin", "team": "Management", "reports_to": None},
    {"name": "Meghana. Ch", "username": "meghana", "role": "HR", "team": "HR", "reports_to": None},
    {"name": "Pooja. L", "username": "pooja", "role": "Lead", "team": "Content", "reports_to": "vasu"},
    {"name": "Prabhas", "username": "prabhas", "role": "Artist", "team": "Content", "reports_to": "pooja"},
    {"name": "Sana", "username": "sana", "role": "Artist", "team": "Content", "reports_to": "pooja"},
    {"name": "Amit Pounikar", "username": "amit", "role": "Lead", "team": "Modeling", "reports_to": "vasu"},
    {"name": "Raveendra. K", "username": "raveendra", "role": "Artist", "team": "Modeling", "reports_to": "amit"},
    {"name": "Nagireddy. E", "username": "nagireddy", "role": "Artist", "team": "Modeling", "reports_to": "amit"},
    {"name": "Rajendra Prasad. K", "username": "rajendra", "role": "Lead", "team": "Char MDL", "reports_to": "vasu"},
    {"name": "Mahesh Goud. C", "username": "mahesh", "role": "Lead", "team": "Texturing", "reports_to": "vasu"},
    {"name": "Rattaiah. Y", "username": "rattaiah", "role": "Artist", "team": "Texturing", "reports_to": "mahesh"},
    {"name": "Sai Ravi Varma. G", "username": "sai", "role": "Lead", "team": "Rig", "reports_to": "vasu"},
    {"name": "Gowri Sandeep. M", "username": "gowri", "role": "Artist", "team": "Rig", "reports_to": "sai"},
    {"name": "Anil Boda", "username": "anilboda", "role": "Lead", "team": "Animation", "reports_to": "vasu"},
    {"name": "Ganesh Bykani", "username": "ganesh", "role": "Artist", "team": "Animation", "reports_to": "anilboda"},
    {"name": "K. Bhavani", "username": "bhavani", "role": "Artist", "team": "Animation", "reports_to": "anilboda"},
    {"name": "V. Praveen Kumar", "username": "praveen", "role": "Artist", "team": "Animation", "reports_to": "anilboda"},
    {"name": "Anil Kumar. K", "username": "anilkumar", "role": "Artist", "team": "Animation", "reports_to": "anilboda"},
    {"name": "Narayana. G", "username": "narayana", "role": "Artist", "team": "Animation", "reports_to": "anilboda"},
    {"name": "Tarun Suraram", "username": "tarun", "role": "Lead", "team": "VFX", "reports_to": "vasu"},
    {"name": "Pavan Kalyan. I", "username": "pavan", "role": "Lead", "team": "Lightning", "reports_to": "vasu"},
    {"name": "Abhilash. A", "username": "abhilash", "role": "Artist", "team": "Lightning", "reports_to": "pavan"},
    {"name": "Spandana. K", "username": "spandana", "role": "Lead", "team": "Motion graphics", "reports_to": "vasu"},
    {"name": "L. Shiva Kumar", "username": "shiva", "role": "Artist", "team": "Motion graphics", "reports_to": "spandana"},
    {"name": "Laxman. G", "username": "laxman", "role": "Artist", "team": "Motion graphics", "reports_to": "spandana"},
    {"name": "Prashanth. M", "username": "prashanth", "role": "Artist", "team": "Motion graphics", "reports_to": "spandana"},
    {"name": "Santosh Kedari", "username": "santosh", "role": "Lead", "team": "VR", "reports_to": "vasu"},
    {"name": "Agnijeet", "username": "agnijeet", "role": "Artist", "team": "VR", "reports_to": "santosh"}
]

DEMO_FILES = [
    # Chapter 12
    {"chapter_name": "ch_12", "name": "FW_12_01_Concept", "description": "Environment concept art for Foundation World", "active_stage": "Content", "status": "Open", "assigned": None},
    {"chapter_name": "ch_12", "name": "FW_12_02_HeroAsset", "description": "Main gate modeling storyboard and specs", "active_stage": "Content", "status": "In Progress", "assigned": "prabhas"},
    {"chapter_name": "ch_12", "name": "FW_12_03_Terrain", "description": "Base blockout of the landscape terrain", "active_stage": "Modeling", "status": "Open", "assigned": None, "content_released_offset": 3600},
    {"chapter_name": "ch_12", "name": "FW_12_04_TowerMDL", "description": "Watchtower low-poly model", "active_stage": "Modeling", "status": "In Progress", "assigned": "raveendra", "content_released_offset": 7200},
    {"chapter_name": "ch_12", "name": "FW_12_05_TextureRock", "description": "Cliff and rock texturing and material set", "active_stage": "Texturing", "status": "Open", "assigned": None, "content_released_offset": 10800},
    {"chapter_name": "ch_12", "name": "FW_12_06_BridgeRig", "description": "Drawbridge mechanical rigging setup", "active_stage": "Rig", "status": "In Progress", "assigned": "gowri", "content_released_offset": 14400},
    {"chapter_name": "ch_12", "name": "FW_12_07_GateAnim", "description": "Opening and closing animation of the gate", "active_stage": "Animation", "status": "Open", "assigned": None, "content_released_offset": 18000},
    {"chapter_name": "ch_12", "name": "FW_12_08_CharAnim", "description": "Guards patrol loop animation", "active_stage": "Animation", "status": "In Progress", "assigned": "ganesh", "content_released_offset": 21600},
    
    # Chapter 13
    {"chapter_name": "ch_13", "name": "FW_13_01_IntroStory", "description": "Scripting layout for Chapter 13 intro", "active_stage": "Content", "status": "Open", "assigned": None},
    {"chapter_name": "ch_13", "name": "FW_13_02_PropSketch", "description": "Prop design drawings for the market scene", "active_stage": "Content", "status": "In Progress", "assigned": "sana"},
    {"chapter_name": "ch_13", "name": "FW_13_03_MarketStall", "description": "Modeling of the market stalls", "active_stage": "Modeling", "status": "Open", "assigned": None, "content_released_offset": 3600},
    {"chapter_name": "ch_13", "name": "FW_13_04_TentMDL", "description": "Merchant tents low-poly modeling", "active_stage": "Modeling", "status": "In Progress", "assigned": "nagireddy", "content_released_offset": 7200},
    {"chapter_name": "ch_13", "name": "FW_13_05_StallTexture", "description": "Stylized texturing for the market structures", "active_stage": "Texturing", "status": "In Progress", "assigned": "rattaiah", "content_released_offset": 10800},
    {"chapter_name": "ch_13", "name": "FW_13_06_HeroWalk", "description": "Walk cycle animation for main character", "active_stage": "Animation", "status": "In Progress", "assigned": "bhavani", "content_released_offset": 14400},
    {"chapter_name": "ch_13", "name": "FW_13_07_DustFX", "description": "Wind and dust particle FX simulation", "active_stage": "VFX", "status": "Open", "assigned": None, "content_released_offset": 18000},
    {"chapter_name": "ch_13", "name": "FW_13_08_SunLight", "description": "Sunlight dynamic lighting setup", "active_stage": "Lightning", "status": "In Progress", "assigned": "abhilash", "content_released_offset": 21600}
]

WELDING_FILES = [
    {"name": "welding_angle_indicator", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_6x6_1_8_stringer_bead_on_plate", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_6x6_3_16_stringer_bead_on_plate", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_6x6_1_4_stringer_bead_on_plate", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_6x6_3_8_stringer_bead_on_plate", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_6x6_3_8_surfacing_bead_on_plate", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_6x6_1_8_puddling_bead_on_plate", "modeling_artist": None, "modeling_status": "Open", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_1_8_lap_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_10x3_3_16_lap_joint_1p", "modeling_artist": None, "modeling_status": "In Progress", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_1_4_lap_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_10x3_3_8_lap_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_10x3_1_16_t_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_10x3_1_8_t_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_10x3_3_16_t_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_10x3_1_4_t_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_10x3_3_8_t_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_10x3_1_8_corner_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Done", "rigging_status": "Done"},
    {"name": "la_10x3_3_16_corner_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_1_4_corner_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_3_8_corner_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    
    # 12 Placeholders to reach exactly 32 assets
    {"name": "la_10x3_1_8_butt_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_3_16_butt_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_1_4_butt_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_3_8_butt_joint_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_6x6_1_8_fillet_weld_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_6x6_3_16_fillet_weld_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_6x6_1_4_fillet_weld_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_6x6_3_8_fillet_weld_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_1_8_v_groove_butt_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_3_16_v_groove_butt_1p", "modeling_artist": "nagireddy", "modeling_status": "Done", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_1_4_v_groove_butt_1p", "modeling_artist": None, "modeling_status": "Open", "texturing_status": "Pending", "rigging_status": "Pending"},
    {"name": "la_10x3_3_8_v_groove_butt_1p", "modeling_artist": None, "modeling_status": "Open", "texturing_status": "Pending", "rigging_status": "Pending"}
]

SHOWCASE_FILES = [
    {"name": "sk_ch01_sc_01", "active_stage": "Motion graphics", "status": "In Progress", "assigned_username": "shiva", "points": 60},
    {"name": "sk_ch01_sc_02", "active_stage": "Motion graphics", "status": "Open", "assigned_username": "laxman", "points": 60},
    {"name": "sk_ch01_sc_03", "active_stage": "Lightning", "status": "In Progress", "assigned_username": "abhilash", "points": 80},
    {"name": "sk_ch01_sc_04", "active_stage": "VFX", "status": "In Progress", "assigned_username": "tarun", "points": 80},
    {"name": "sk_ch01_sc_05", "active_stage": "Animation", "status": "In Progress", "assigned_username": "ganesh", "points": 80},
    {"name": "sk_ch01_sc_06", "active_stage": "Rig", "status": "In Progress", "assigned_username": "gowri", "points": 80},
    {"name": "sk_ch01_sc_07", "active_stage": "Texturing", "status": "In Progress", "assigned_username": "rattaiah", "points": 50},
    {"name": "sk_ch01_sc_08", "active_stage": "Modeling", "status": "In Progress", "assigned_username": "raveendra", "points": 50},
    {"name": "sk_ch01_sc_09", "active_stage": "Modeling", "status": "Review", "assigned_username": "nagireddy", "points": 50},
    {"name": "sk_ch01_sc_10", "active_stage": "Content", "status": "In Progress", "assigned_username": "prabhas", "points": 50},
    {"name": "sk_ch01_vr_01", "active_stage": "VR", "status": "In Progress", "assigned_username": "agnijeet", "points": 100},
    {"name": "sk_ch01_vr_02", "active_stage": "VR", "status": "Open", "assigned_username": "santosh", "points": 100}
]

# Attendance off-day logic
def is_weekly_off(date_obj):
    if date_obj.weekday() == 6:  # Sunday
        return True
    if date_obj.weekday() == 5:  # Saturday
        day = date_obj.day
        if (8 <= day <= 14) or (22 <= day <= 28):
            return True
    return False

def calculate_attendance_metrics(db, user_id, date_str, clock_in_str, clock_out_str=None):
    cursor = db.cursor()
    cursor.execute("SELECT shift_start, shift_end FROM users WHERE id = ?", (user_id,))
    user_info = cursor.fetchone()
    
    if not user_info:
        return 'Absent', 0, 0, 0.0, 0.0
        
    shift_start_str = user_info['shift_start'] or '09:30'
    shift_end_str = user_info['shift_end'] or '19:00'
    
    # Parse times
    try:
        in_h, in_m = map(int, clock_in_str.split(':')[:2])
    except:
        in_h, in_m = 9, 30
        
    start_h, start_m = map(int, shift_start_str.split(':')[:2])
    end_h, end_m = map(int, shift_end_str.split(':')[:2])
    
    in_mins = in_h * 60 + in_m
    start_mins = start_h * 60 + start_m
    end_mins = end_h * 60 + end_m
    
    # Calculate late minutes
    late_minutes = 0
    status = 'Present'
    
    # Calculate if off-day or holiday
    try:
        dt_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        dt_obj = datetime.date.today()
    
    off_day = is_weekly_off(dt_obj)
    cursor.execute("SELECT COUNT(*) FROM holidays WHERE date = ?", (date_str,))
    is_holiday_flag = cursor.fetchone()[0] > 0
    
    if off_day or is_holiday_flag:
        status = 'Present'
        late_minutes = 0
    else:
        if in_mins <= start_mins:
            status = 'Present'
            late_minutes = 0
        elif in_mins <= start_mins + 90:
            status = 'Late'
            late_minutes = in_mins - start_mins
        else:
            status = 'Half Day'
            late_minutes = 0
            
    # Calculate early minutes and extra hours if clocked out
    early_minutes = 0
    total_hours = 0.0
    extra_hours = 0.0
    
    if clock_out_str:
        try:
            out_h, out_m = map(int, clock_out_str.split(':')[:2])
        except:
            out_h, out_m = 19, 0
            
        out_mins = out_h * 60 + out_m
        
        # Total hours worked
        total_mins = out_mins - in_mins
        if total_mins < 0:
            total_mins += 1440
        total_hours = total_mins / 60.0
        
        # Required shift length
        shift_length_mins = end_mins - start_mins
        if shift_length_mins < 0:
            shift_length_mins += 1440
            
        if off_day or is_holiday_flag:
            extra_hours = total_hours
            early_minutes = 0
        else:
            if out_mins < end_mins:
                early_minutes = end_mins - out_mins
            else:
                early_minutes = 0
                
            # Extra hours is total working hours beyond required shift length
            extra_hours = max(0.0, total_hours - (shift_length_mins / 60.0))
            
    return status, late_minutes, early_minutes, total_hours, extra_hours

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def recalculate_file_metadata(db, file_id):
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    
    # 1. Fetch file's current review statuses
    cursor.execute("""
        SELECT internal_lead_status, internal_content_status, final_review_status, final_approval_date 
        FROM files WHERE id = ?
    """, (file_id,))
    file_row = cursor.fetchone()
    if not file_row:
        return
        
    # 2. Query all pipeline steps for this file
    cursor.execute("""
        SELECT step_name, status, assigned_to, start_date, end_date, remarks
        FROM file_pipeline
        WHERE file_id = ?
    """, (file_id,))
    steps = [dict(r) for r in cursor.fetchall()]
    steps_map = {s['step_name']: s for s in steps}
    
    # Order stages by PIPELINE_STAGES
    ordered_steps = []
    for stage in PIPELINE_STAGES:
        if stage in steps_map:
            ordered_steps.append(steps_map[stage])
            
    # Calculate values
    # a. Assigned Artist: first step in order that is 'In Progress' or 'Open'
    active_artist_id = None
    for step in ordered_steps:
        if step['status'] in ['In Progress', 'Open']:
            active_artist_id = step['assigned_to']
            break
            
    today_str = datetime.date.today().strftime('%Y-%m-%d')

    # b. Start and End Dates
    # Auto-ensure steps that are 'In Progress' or 'Done' have a start_date set if missing
    for step in ordered_steps:
        if step['status'] in ['In Progress', 'Done'] and not step['start_date']:
            step['start_date'] = today_str
            cursor.execute("""
                UPDATE file_pipeline 
                SET start_date = ? 
                WHERE file_id = ? AND step_name = ?
            """, (today_str, file_id, step['step_name']))

    start_dates = []
    end_dates = []
    for step in ordered_steps:
        if step['start_date']:
            try:
                d = datetime.datetime.strptime(step['start_date'].strip(), '%Y-%m-%d').date()
                start_dates.append(d)
            except ValueError:
                pass
        if step['end_date']:
            try:
                d = datetime.datetime.strptime(step['end_date'].strip(), '%Y-%m-%d').date()
                end_dates.append(d)
            except ValueError:
                pass
                
    calc_start_date = min(start_dates).strftime('%Y-%m-%d') if start_dates else None
    calc_end_date = max(end_dates).strftime('%Y-%m-%d') if end_dates else None
    
    # c. Overall Status
    all_done = all(s['status'] == 'Done' for s in ordered_steps) if ordered_steps else False
    any_progress = any(s['status'] == 'In Progress' for s in ordered_steps)
    any_open = any(s['status'] == 'Open' for s in ordered_steps)
    
    if all_done and file_row['final_review_status'] == 'Approved':
        calc_status = 'Done'
    elif all_done:
        calc_status = 'Review'
    elif any_progress:
        calc_status = 'In Progress'
    elif any_open:
        calc_status = 'Open'
    else:
        calc_status = 'Pending'

    # If file is In Progress, Review, or Done, ensure calc_start_date is calculated/set
    if calc_status in ['In Progress', 'Review', 'Done'] and not calc_start_date:
        calc_start_date = today_str
        
    # If overall status is Done, calculate and set end_date automatically
    if calc_status == 'Done':
        if file_row['final_approval_date']:
            calc_end_date = file_row['final_approval_date']
        elif not calc_end_date:
            calc_end_date = datetime.date.today().strftime('%Y-%m-%d')
            
    # d. Remarks
    remarks_list = []
    for step in ordered_steps:
        if step['remarks']:
            remarks_list.append(f"{step['step_name']}: {step['remarks']}")
    calc_remarks = "\n".join(remarks_list) if remarks_list else None
    
    # Update files table
    cursor.execute("""
        UPDATE files
        SET assigned_to = ?, start_date = ?, end_date = ?, status = ?, remarks = ?
        WHERE id = ?
    """, (active_artist_id, calc_start_date, calc_end_date, calc_status, calc_remarks, file_id))
    db.commit()


def init_db():
    db_exists = os.path.exists(DATABASE)
    schema_needs_update = False
    
    if db_exists:
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT total_hours FROM attendance LIMIT 1")
            conn.close()
        except sqlite3.OperationalError:
            schema_needs_update = True
            print("Schema needs update! Re-initializing database...")

    # Runtime migration: ensure permission_requests table exists (Layer 6)
    if db_exists and not schema_needs_update:
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM permission_requests LIMIT 1")
            conn.close()
        except sqlite3.OperationalError:
            conn = sqlite3.connect(DATABASE)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS permission_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    hours REAL NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT DEFAULT 'Pending',
                    approved_by INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            conn.commit()
            conn.close()
            print("Migrated: permission_requests table created.")

        # Runtime migration: ensure permission_requests table has clock_in and clock_out columns
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT clock_in, clock_out FROM permission_requests LIMIT 1")
            conn.close()
        except sqlite3.OperationalError:
            conn = sqlite3.connect(DATABASE)
            try:
                conn.execute("ALTER TABLE permission_requests ADD COLUMN clock_in TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE permission_requests ADD COLUMN clock_out TEXT")
            except sqlite3.OperationalError:
                pass
            conn.commit()
            conn.close()
            print("Migrated: permission_requests clock_in and clock_out columns added.")

        # Runtime migration: ensure notifications table exists (Layer 10)
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM notifications LIMIT 1")
            conn.close()
        except sqlite3.OperationalError:
            conn = sqlite3.connect(DATABASE)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT,
                    link TEXT,
                    type TEXT DEFAULT 'info',
                    is_read INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.commit()
            conn.close()
            print("Migrated: notifications table created.")

        # Runtime migration: ensure notifications table has link column
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT link FROM notifications LIMIT 1")
            conn.close()
        except sqlite3.OperationalError:
            conn = sqlite3.connect(DATABASE)
            conn.execute("ALTER TABLE notifications ADD COLUMN link TEXT")
            conn.commit()
            conn.close()
            print("Migrated: notifications.link column added.")

        # Runtime migration: ensure activity_log table exists (Layer 10)
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM activity_log LIMIT 1")
            conn.close()
        except sqlite3.OperationalError:
            conn = sqlite3.connect(DATABASE)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            conn.commit()
            conn.close()
            print("Migrated: activity_log table created.")

        # Runtime migration: ensure submit_time column exists in daily_assignments (Layer 9)
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT submit_time FROM daily_assignments LIMIT 1")
            conn.close()
        except sqlite3.OperationalError:
            conn = sqlite3.connect(DATABASE)
            conn.execute("ALTER TABLE daily_assignments ADD COLUMN submit_time TEXT")
            conn.commit()
            conn.close()
            print("Migrated: daily_assignments.submit_time column added.")

        # Runtime migration: ensure all artists and leads have monthly targets for the current month
        try:
            conn = sqlite3.connect(DATABASE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            current_month = datetime.date.today().strftime('%Y-%m')
            cursor.execute("SELECT id FROM users WHERE role IN ('Artist', 'Lead')")
            u_ids = [row['id'] for row in cursor.fetchall()]
            for uid in u_ids:
                cursor.execute("SELECT id FROM monthly_targets WHERE user_id = ? AND month = ?", (uid, current_month))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO monthly_targets (user_id, month, target_points) VALUES (?, ?, ?)", (uid, current_month, 500))
            conn.commit()
            conn.close()
            print("Migrated: ensured all artists and leads have targets for the current month.")
        except Exception as e:
            print(f"Error checking/migrating monthly targets: {e}")

        # Runtime migration: ensure files table has review and metadata columns
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            new_cols = [
                ("start_date", "TEXT"),
                ("end_date", "TEXT"),
                ("remarks", "TEXT"),
                ("final_approval_date", "TEXT"),
                ("internal_lead_status", "TEXT DEFAULT 'Pending'"),
                ("internal_content_status", "TEXT DEFAULT 'Pending'"),
                ("final_review_status", "TEXT DEFAULT 'Pending'")
            ]
            for col_name, col_type in new_cols:
                try:
                    cursor.execute(f"ALTER TABLE files ADD COLUMN {col_name} {col_type}")
                    conn.commit()
                except sqlite3.OperationalError:
                    pass
            
            # Update user teams (Lighting -> Lightning, Motion Graphics -> Motion graphics)
            cursor.execute("UPDATE users SET team = 'Lightning' WHERE team = 'Lighting'")
            cursor.execute("UPDATE users SET team = 'Motion graphics' WHERE team = 'Motion Graphics'")
            conn.commit()
            
            # Migrate file pipeline stages
            # Ensure every file has all pipeline stages
            cursor.execute("SELECT id FROM files")
            files_list = cursor.fetchall()
            for f_row in files_list:
                fid = f_row[0]
                # Fetch existing stages
                cursor.execute("SELECT step_name, status, assigned_to, points, start_date, end_date, remarks FROM file_pipeline WHERE file_id = ?", (fid,))
                existing_pipeline = {r[0]: dict(zip(['status', 'assigned_to', 'points', 'start_date', 'end_date', 'remarks'], r[1:])) for r in cursor.fetchall()}
                
                # Check for old stages to migrate
                old_mapping = {
                    'Lighting/Rendering': 'Lightning',
                    'Motion Graphics/3D Comp': 'Motion graphics'
                }
                for old_st, new_st in old_mapping.items():
                    if old_st in existing_pipeline and new_st not in existing_pipeline:
                        # Copy old stage values to new stage
                        old_data = existing_pipeline[old_st]
                        cursor.execute("""
                            INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points, start_date, end_date, remarks)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (fid, new_st, old_data['status'], old_data['assigned_to'], old_data['points'], old_data['start_date'], old_data['end_date'], old_data['remarks']))
                        conn.commit()
                        existing_pipeline[new_st] = old_data
                
                # Ensure all current pipeline stages exist for this file
                for stage in PIPELINE_STAGES:
                    if stage not in existing_pipeline:
                        status = 'Open' if stage == 'Content' else 'Pending'
                        cursor.execute("""
                            INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points)
                            VALUES (?, ?, ?, NULL, 0)
                        """, (fid, stage, status))
                        conn.commit()
                        
                # Clean up old stages from database
                cursor.execute("DELETE FROM file_pipeline WHERE file_id = ? AND step_name IN ('Lighting/Rendering', 'Motion Graphics/3D Comp')", (fid,))
                conn.commit()
                
            conn.close()
            print("Migrated: file details, team names, and file pipeline stages.")
        except Exception as e:
            print(f"Error executing schema and team migration: {e}")
            
        # Runtime migration: backfill done stages with default artists and realistic dates
        try:
            conn = sqlite3.connect(DATABASE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Fetch user map for staging default artists
            cursor.execute("SELECT id, username FROM users")
            user_map = {r['username']: r['id'] for r in cursor.fetchall()}
            
            STAGE_DEFAULT_ARTISTS = {
                'Content': 'sana',
                'Modeling': 'raveendra',
                'Texturing': 'rattaiah',
                'Rig': 'gowri',
                'Animation': 'ganesh',
                'FBX export': 'ganesh',
                'VFX': 'shiva',
                'Lightning': 'abhilash',
                'Rendering': 'abhilash',
                '3D Comp': 'shiva',
                'Motion graphics': 'shiva',
                'VR': 'agnijeet'
            }
            
            cursor.execute("SELECT id, step_name, assigned_to, start_date, end_date FROM file_pipeline WHERE status = 'Done'")
            done_stages = cursor.fetchall()
            
            today = datetime.date.today()
            for stage in done_stages:
                updates = []
                params = []
                
                if not stage['assigned_to']:
                    def_username = STAGE_DEFAULT_ARTISTS.get(stage['step_name'])
                    artist_id = user_map.get(def_username)
                    if artist_id:
                        updates.append("assigned_to = ?")
                        params.append(artist_id)
                        
                if not stage['start_date']:
                    s_date = (today - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
                    updates.append("start_date = ?")
                    params.append(s_date)
                    
                if not stage['end_date']:
                    e_date = (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
                    updates.append("end_date = ?")
                    params.append(e_date)
                    
                if updates:
                    params.append(stage['id'])
                    cursor.execute(f"UPDATE file_pipeline SET {', '.join(updates)} WHERE id = ?", params)
            
            # Recalculate file metadata for all files to ensure overall start/end dates are populated
            cursor.execute("SELECT id FROM files")
            file_ids = [r[0] for r in cursor.fetchall()]
            for fid in file_ids:
                recalculate_file_metadata(conn, fid)
                
            conn.commit()
            conn.close()
            print("Migrated: backfilled artist and dates for completed pipeline stages, and recalculated metadata.")
        except Exception as e:
            print(f"Error migrating done stage details: {e}")


    if not db_exists or schema_needs_update:
        if db_exists:
            try:
                os.remove(DATABASE)
            except Exception as e:
                print(f"Error removing old database: {e}")
                
        print("Initializing database from schema...")
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        with open(SCHEMA_FILE, 'r') as f:
            conn.executescript(f.read())
        
        cursor = conn.cursor()
        
        # Seed users
        print("Seeding initial 28 user accounts...")
        default_pwd_hash = generate_password_hash("inucom@123")
        for user in SEEDED_USERS:
            # Determine shifts based on user info
            if user['username'] in ['ganesh', 'mahesh']:
                s_start, s_end = '09:00', '18:30'
            elif user['team'] == 'VR':
                s_start, s_end = '09:30', '18:30'
            else:
                s_start, s_end = '09:30', '19:00'
            cursor.execute("""
                INSERT INTO users (name, username, password_hash, role, team, reports_to, must_change_password, shift_start, shift_end)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (user['name'], user['username'], default_pwd_hash, user['role'], user['team'], user['reports_to'], s_start, s_end))
        conn.commit()
        
        # Seed demo project
        print("Seeding demo project and chapters...")
        cursor.execute("INSERT INTO projects (name, description, status) VALUES ('Foundation World', 'Core fantasy game environment', 'Active')")
        project_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO chapters (project_id, name, description, status) VALUES (?, 'ch_12', 'Chapter 12: The Outer Gates', 'Active')", (project_id,))
        ch_12_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO chapters (project_id, name, description, status) VALUES (?, 'ch_13', 'Chapter 13: The Grand Bazaar', 'Active')", (project_id,))
        ch_13_id = cursor.lastrowid
        conn.commit()
        
        # Seed demo files and pipelines
        print("Seeding demo pipeline files...")
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        
        for f_demo in DEMO_FILES:
            chap_id = ch_12_id if f_demo['chapter_name'] == 'ch_12' else ch_13_id
            
            content_released = None
            if 'content_released_offset' in f_demo:
                dt = datetime.datetime.now() - datetime.timedelta(seconds=f_demo['content_released_offset'])
                content_released = dt.strftime('%Y-%m-%d %H:%M:%S')
            elif f_demo['active_stage'] != 'Content' or f_demo['status'] == 'Done':
                dt = datetime.datetime.now() - datetime.timedelta(seconds=3600)
                content_released = dt.strftime('%Y-%m-%d %H:%M:%S')
                
            cursor.execute("""
                INSERT INTO files (chapter_id, name, description, status, content_released_at)
                VALUES (?, ?, ?, 'Pending', ?)
            """, (chap_id, f_demo['name'], f_demo['description'], content_released))
            file_id = cursor.lastrowid
            
            artist_id = None
            if f_demo['assigned']:
                cursor.execute("SELECT id FROM users WHERE username = ?", (f_demo['assigned'],))
                res = cursor.fetchone()
                if res:
                    artist_id = res[0]
            
            points_val = 50 if f_demo['active_stage'] in ['Content', 'Modeling', 'Texturing'] else 80
            
            STAGE_DEFAULT_ARTISTS = {
                'Content': 'sana',
                'Modeling': 'raveendra',
                'Texturing': 'rattaiah',
                'Rig': 'gowri',
                'Animation': 'ganesh',
                'FBX export': 'ganesh',
                'VFX': 'shiva',
                'Lightning': 'abhilash',
                'Rendering': 'abhilash',
                '3D Comp': 'shiva',
                'Motion graphics': 'shiva',
                'VR': 'agnijeet'
            }
            for stage in PIPELINE_STAGES:
                stage_start_date = None
                stage_end_date = None
                if stage == f_demo['active_stage']:
                    stage_status = f_demo['status']
                    stage_assigned = artist_id
                    stage_points = points_val
                    if stage_status == 'In Progress':
                        stage_start_date = today_str
                elif PIPELINE_STAGES.index(stage) < PIPELINE_STAGES.index(f_demo['active_stage']):
                    stage_status = 'Done'
                    def_username = STAGE_DEFAULT_ARTISTS.get(stage)
                    cursor.execute("SELECT id FROM users WHERE username = ?", (def_username,))
                    res_def = cursor.fetchone()
                    stage_assigned = res_def[0] if res_def else None
                    stage_points = points_val
                    offset = PIPELINE_STAGES.index(f_demo['active_stage']) - PIPELINE_STAGES.index(stage)
                    stage_start_date = (datetime.date.today() - datetime.timedelta(days=offset + 1)).strftime('%Y-%m-%d')
                    stage_end_date = (datetime.date.today() - datetime.timedelta(days=offset)).strftime('%Y-%m-%d')
                else:
                    stage_status = 'Pending'
                    stage_assigned = None
                    stage_points = 0
                    
                cursor.execute("""
                    INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points, start_date, end_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (file_id, stage, stage_status, stage_assigned, stage_points, stage_start_date, stage_end_date))
                
                if stage == f_demo['active_stage'] and stage_assigned and stage_status != 'Done':
                    cursor.execute("""
                        INSERT INTO daily_assignments (user_id, date, file_id, task_description, points, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (stage_assigned, today_str, file_id, f"{stage}: {f_demo['name']}", stage_points, stage_status))

        # Fetch user IDs for Nagireddy, Rattaiah, and Gowri
        cursor.execute("SELECT id FROM users WHERE username = 'nagireddy'")
        nagireddy_row = cursor.fetchone()
        nagireddy_id = nagireddy_row['id'] if nagireddy_row else None

        cursor.execute("SELECT id FROM users WHERE username = 'rattaiah'")
        rattaiah_row = cursor.fetchone()
        rattaiah_id = rattaiah_row['id'] if rattaiah_row else None

        cursor.execute("SELECT id FROM users WHERE username = 'gowri'")
        gowri_row = cursor.fetchone()
        gowri_id = gowri_row['id'] if gowri_row else None

        # Seed second project: Welding Lab
        print("Seeding Welding Lab project and chapter...")
        cursor.execute("INSERT INTO projects (name, description, status) VALUES ('Welding Lab', 'VR welding training project', 'Active')")
        welding_project_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO chapters (project_id, name, description, status) VALUES (?, 'lab_assignments', 'VR Welding Lab Assignments', 'Active')", (welding_project_id,))
        welding_chapter_id = cursor.lastrowid
        conn.commit()

        # Seed welding files
        print("Seeding welding files...")
        for idx, f_weld in enumerate(WELDING_FILES):
            file_status = 'Pending'
            dt = datetime.datetime.now() - datetime.timedelta(seconds=14400)
            content_released = dt.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                INSERT INTO files (chapter_id, name, description, status, content_released_at)
                VALUES (?, ?, ?, ?, ?)
            """, (welding_chapter_id, f_weld['name'], f"VR Asset: {f_weld['name']}", file_status, content_released))
            file_id = cursor.lastrowid

            for stage in PIPELINE_STAGES:
                stage_status = 'Pending'
                stage_assigned = None
                stage_points = 0
                stage_start_date = None
                stage_end_date = None

                if stage == 'Content':
                    stage_status = 'Done'
                    stage_points = 50
                elif stage == 'Modeling':
                    stage_status = f_weld['modeling_status']
                    stage_points = 50
                    if stage_status == 'In Progress':
                        stage_assigned = nagireddy_id
                        stage_start_date = today_str
                elif stage == 'Texturing':
                    if idx < 14:
                        stage_status = 'Done'
                    else:
                        stage_status = 'In Progress'
                        stage_assigned = rattaiah_id
                        stage_start_date = today_str
                    stage_points = 50
                elif stage == 'Rig':
                    if idx < 14:
                        stage_status = 'Done'
                    elif idx < 17:
                        stage_status = 'In Progress'
                        stage_assigned = gowri_id
                        stage_start_date = today_str
                    else:
                        stage_status = 'Pending'
                    stage_points = 80

                if stage_status == 'Done':
                    def_username = STAGE_DEFAULT_ARTISTS.get(stage)
                    cursor.execute("SELECT id FROM users WHERE username = ?", (def_username,))
                    res_def = cursor.fetchone()
                    stage_assigned = res_def[0] if res_def else None
                    stage_start_date = (datetime.date.today() - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
                    stage_end_date = (datetime.date.today() - datetime.timedelta(days=2)).strftime('%Y-%m-%d')

                cursor.execute("""
                    INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points, start_date, end_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (file_id, stage, stage_status, stage_assigned, stage_points, stage_start_date, stage_end_date))

                if stage_status == 'In Progress' and stage_assigned:
                    cursor.execute("""
                        INSERT INTO daily_assignments (user_id, date, file_id, task_description, points, status)
                        VALUES (?, ?, ?, ?, ?, 'Pending')
                    """, (stage_assigned, today_str, file_id, f"{stage}: {f_weld['name']}", stage_points))
        conn.commit()

        # Seed third project: Skill Studio VR
        print("Seeding Skill Studio VR project and chapter...")
        cursor.execute("INSERT INTO projects (name, description, status) VALUES ('Skill Studio VR', 'Flagship VR training project', 'Active')")
        ss_project_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO chapters (project_id, name, description, status) VALUES (?, 'ch_01', 'Chapter 01: Core Basics', 'Active')", (ss_project_id,))
        ss_chapter_id = cursor.lastrowid
        conn.commit()

        # Build user map
        cursor.execute("SELECT id, username FROM users")
        user_map = {r['username']: r['id'] for r in cursor.fetchall()}

        print("Seeding Skill Studio VR files...")
        dt_vr = datetime.datetime.now() - datetime.timedelta(seconds=14400)
        content_released_vr = dt_vr.strftime('%Y-%m-%d %H:%M:%S')

        for f_showcase in SHOWCASE_FILES:
            cursor.execute("""
                INSERT INTO files (chapter_id, name, description, status, content_released_at)
                VALUES (?, ?, ?, 'Pending', ?)
            """, (ss_chapter_id, f_showcase['name'], f"Showcase Asset: {f_showcase['name']}", content_released_vr))
            file_id = cursor.lastrowid

            active_idx = PIPELINE_STAGES.index(f_showcase['active_stage'])
            for idx, stage in enumerate(PIPELINE_STAGES):
                stage_status = 'Pending'
                stage_assigned = None
                stage_points = 0

                if idx < active_idx:
                    stage_status = 'Done'
                    stage_points = f_showcase['points']
                    def_username = STAGE_DEFAULT_ARTISTS.get(stage)
                    cursor.execute("SELECT id FROM users WHERE username = ?", (def_username,))
                    res_def = cursor.fetchone()
                    stage_assigned = res_def[0] if res_def else None
                    stage_start_date = (datetime.date.today() - datetime.timedelta(days=active_idx - idx + 1)).strftime('%Y-%m-%d')
                    stage_end_date = (datetime.date.today() - datetime.timedelta(days=active_idx - idx)).strftime('%Y-%m-%d')
                elif idx == active_idx:
                    if f_showcase['status'] == 'Review':
                        stage_status = 'In Progress'
                    else:
                        stage_status = 'In Progress' if f_showcase['status'] == 'In Progress' else 'Open'
                    stage_assigned = user_map.get(f_showcase['assigned_username'])
                    stage_points = f_showcase['points']
                    if stage_status == 'In Progress':
                        stage_start_date = today_str
                else:
                    stage_status = 'Pending'
                    stage_points = 0

                cursor.execute("""
                    INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points, start_date, end_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (file_id, stage, stage_status, stage_assigned, stage_points, stage_start_date, stage_end_date))

                if idx == active_idx and stage_assigned and stage_status == 'In Progress':
                    submit_time = None
                    da_status = 'Pending'
                    if f_showcase['status'] == 'Review':
                        submit_time = today_str + ' 12:00:00'
                    
                    cursor.execute("""
                        INSERT INTO daily_assignments (user_id, date, file_id, task_description, points, status, submit_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (stage_assigned, today_str, file_id, f"{stage}: {f_showcase['name']}", stage_points, da_status, submit_time))
        conn.commit()

        # Seed targets
        current_month = datetime.date.today().strftime('%Y-%m')
        cursor.execute("SELECT id FROM users WHERE role IN ('Artist', 'Lead')")
        artist_ids = [row[0] for row in cursor.fetchall()]
        for aid in artist_ids:
            cursor.execute("INSERT INTO monthly_targets (user_id, month, target_points) VALUES (?, ?, ?)", (aid, current_month, 500))
            
        # Seed some demo points
        yesterday_str = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        cursor.execute("SELECT id FROM users WHERE username = 'raveendra'")
        rav_row = cursor.fetchone()
        if rav_row:
            cursor.execute("INSERT INTO points (user_id, date, points, reason, awarded_by) VALUES (?, ?, ?, ?, ?)",
                           (rav_row[0], yesterday_str, 60, "Modeling completion: FW_12_05", 1))
            
        print("Seeding activity log...")
        cursor.execute("INSERT INTO activity_log (action, details) VALUES ('System Init', 'Database schema created and seeded with 28 user accounts and demo project.')")
        conn.commit()
        conn.close()

# Enforce auth and forced password change
@app.before_request
def enforce_auth_and_password_change():
    allowed_endpoints = ['login', 'logout', 'change_password', 'static']
    if request.endpoint in allowed_endpoints or request.endpoint is None:
        return
        
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT must_change_password FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    if user and user['must_change_password'] == 1:
        return redirect(url_for('change_password'))

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash("Please enter both username and password.", "error")
            return render_template('login.html')
            
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(username) = ?", (username,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['name'] = user['name']
            session['role'] = user['role']
            session['team'] = user['team']
            
            cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)", 
                           (user['id'], 'User Login', f"User {user['username']} logged in successfully."))
            db.commit()
            
            if user['must_change_password'] == 1:
                return redirect(url_for('change_password'))
                
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "error")
            
    return render_template('login.html')

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not new_password:
            flash("Password cannot be empty.", "error")
            return render_template('change_password.html')
            
        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template('change_password.html')
            
        if new_password == "inucom@123":
            flash("Please choose a new password. You cannot reuse the default password.", "error")
            return render_template('change_password.html')
            
        hashed_password = generate_password_hash(new_password)
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?", 
                       (hashed_password, session['user_id']))
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)", 
                       (session['user_id'], 'Password Change', f"User {session['username']} changed their default password."))
        db.commit()
        
        flash("Password changed successfully!", "success")
        return redirect(url_for('dashboard'))
        
    return render_template('change_password.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    
    # Run notifications checks
    check_and_push_eod_reminders(db, session['user_id'])
    check_and_push_morning_reminders(db, session['user_id'])
    if session['role'] == 'Admin':
        check_and_push_admin_target_alerts(db, session['user_id'])
    
    # Get user profile
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_profile = cursor.fetchone()
    
    # Check today's clock status
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    cursor.execute("SELECT * FROM attendance WHERE user_id = ? AND date = ?", (session['user_id'], today_str))
    attendance_today = cursor.fetchone()
    
    # Project & Chapter selections
    cursor.execute("SELECT * FROM projects WHERE status = 'Active'")
    projects = cursor.fetchall()
    
    project_id = request.args.get('project_id', type=int)
    chapter_id = request.args.get('chapter_id', type=int)
    
    if not project_id and projects:
        project_id = projects[0]['id']
        
    cursor.execute("SELECT * FROM chapters WHERE project_id = ? AND status = 'Active'", (project_id,))
    chapters = cursor.fetchall()
    
    selected_chapter_name = ""
    if not chapter_id and chapters:
        chapter_id = chapters[0]['id']
        selected_chapter_name = chapters[0]['name']
    elif chapter_id:
        for ch in chapters:
            if ch['id'] == chapter_id:
                selected_chapter_name = ch['name']
                break

    # Sub-tab parsing & stages split
    sub_tab = request.args.get('sub_tab', 'assets')
    if sub_tab not in ['assets', 'scenes']:
        sub_tab = 'assets'
        
    if sub_tab == 'assets':
        stages_list = ['Content', 'Modeling', 'Texturing', 'Rig']
    else:
        stages_list = ['Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering', '3D Comp', 'Motion graphics']

    active_projects_list = []
    project_chapters_map = {}
    chapter_files_map = {}
    matrix = {}
    
    view_tab = request.args.get('view', 'overview')
    if view_tab == 'pipeline' or session['role'] == 'Admin':
        if session['role'] == 'Admin' and project_id:
            active_projects_list = [p for p in projects if p['id'] == project_id]
            if not active_projects_list and projects:
                active_projects_list = [projects[0]]
        else:
            active_projects_list = projects

        for proj in active_projects_list:
            pid = proj['id']
            if session['role'] == 'Admin' and chapter_id:
                cursor.execute("SELECT * FROM chapters WHERE id = ? AND status = 'Active'", (chapter_id,))
            else:
                cursor.execute("SELECT * FROM chapters WHERE project_id = ? AND status = 'Active'", (pid,))
            chaps = cursor.fetchall()
            project_chapters_map[pid] = chaps
            for chap in chaps:
                cid = chap['id']
                cursor.execute("SELECT * FROM files WHERE chapter_id = ? ORDER BY id", (cid,))
                chapter_files_map[cid] = cursor.fetchall()
                
        cursor.execute("""
            SELECT fp.file_id, fp.step_name, fp.status, fp.points, u.name as artist_name, u.username as artist_username, u.reports_to as artist_lead
            FROM file_pipeline fp
            LEFT JOIN users u ON fp.assigned_to = u.id
        """)
        rows = cursor.fetchall()
        for row in rows:
            f_id = row['file_id']
            if f_id not in matrix:
                matrix[f_id] = {}
            matrix[f_id][row['step_name']] = {
                'status': row['status'],
                'points': row['points'],
                'artist_name': row['artist_name'],
                'artist_username': row['artist_username'],
                'artist_lead': row['artist_lead']
            }
        files = []
        for cid, flist in chapter_files_map.items():
            files.extend(flist)

    asset_stages = ['Content', 'Modeling', 'Texturing', 'Rig']
    scene_stages = ['Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering', '3D Comp', 'Motion graphics']
    active_stages = asset_stages if sub_tab == 'assets' else scene_stages

    pipeline_summary = {
        'sub_tab': sub_tab,
        'total_items': 0,
        'subtab_active_files': 0,
        'total_assets_count': 0,
        'total_scenes_count': 0,
        'total_wip': 0,
        'total_open': 0,
        'total_pending': 0,
        'total_done': 0,
        'stage_stats': {stg: {'wip': 0, 'open': 0, 'pending': 0, 'done': 0} for stg in active_stages}
    }

    if view_tab == 'pipeline' or session['role'] == 'Admin':
        if session['role'] == 'Admin' and chapter_id:
            cursor.execute("""
                SELECT COUNT(DISTINCT f.id)
                FROM files f
                JOIN file_pipeline fp ON fp.file_id = f.id
                WHERE f.chapter_id = ? AND fp.step_name IN ({}) AND fp.status IN ('In Progress', 'Open')
            """.format(','.join('?' for _ in active_stages)), [chapter_id] + active_stages)
            tot_res = cursor.fetchone()
            pipeline_summary['total_items'] = tot_res[0] if tot_res else 0
            pipeline_summary['subtab_active_files'] = pipeline_summary['total_items']

            cursor.execute("""
                SELECT fp.step_name, fp.status
                FROM file_pipeline fp
                JOIN files f ON fp.file_id = f.id
                WHERE f.chapter_id = ? AND fp.step_name IN ({})
            """.format(','.join('?' for _ in active_stages)), [chapter_id] + active_stages)
            fp_rows = cursor.fetchall()
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT f.id)
                FROM files f
                JOIN chapters c ON f.chapter_id = c.id
                JOIN projects p ON c.project_id = p.id
                JOIN file_pipeline fp ON fp.file_id = f.id
                WHERE c.status = 'Active' AND p.status = 'Active' AND fp.step_name IN ({}) AND fp.status IN ('In Progress', 'Open')
            """.format(','.join('?' for _ in active_stages)), tuple(active_stages))
            tot_res = cursor.fetchone()
            pipeline_summary['total_items'] = tot_res[0] if tot_res else 0
            pipeline_summary['subtab_active_files'] = pipeline_summary['total_items']

            cursor.execute("""
                SELECT fp.step_name, fp.status
                FROM file_pipeline fp
                JOIN files f ON fp.file_id = f.id
                JOIN chapters c ON f.chapter_id = c.id
                JOIN projects p ON c.project_id = p.id
                WHERE c.status = 'Active' AND p.status = 'Active' AND fp.step_name IN ({})
            """.format(','.join('?' for _ in active_stages)), tuple(active_stages))
            fp_rows = cursor.fetchall()

        for fp_item in fp_rows:
            stg = fp_item['step_name']
            st = fp_item['status']
            if stg in pipeline_summary['stage_stats']:
                if st == 'In Progress':
                    pipeline_summary['stage_stats'][stg]['wip'] += 1
                    pipeline_summary['total_wip'] += 1
                elif st == 'Open':
                    pipeline_summary['stage_stats'][stg]['open'] += 1
                    pipeline_summary['total_open'] += 1
                elif st == 'Pending':
                    pipeline_summary['stage_stats'][stg]['pending'] += 1
                    pipeline_summary['total_pending'] += 1
                elif st == 'Done':
                    pipeline_summary['stage_stats'][stg]['done'] += 1
                    pipeline_summary['total_done'] += 1
    else:
        files = []
        if chapter_id:
            cursor.execute("SELECT * FROM files WHERE chapter_id = ? ORDER BY id", (chapter_id,))
            files = cursor.fetchall()
            cursor.execute("""
                SELECT fp.file_id, fp.step_name, fp.status, fp.points, u.name as artist_name, u.username as artist_username, u.reports_to as artist_lead
                FROM file_pipeline fp
                JOIN files f ON fp.file_id = f.id
                LEFT JOIN users u ON fp.assigned_to = u.id
                WHERE f.chapter_id = ?
            """, (chapter_id,))
            rows = cursor.fetchall()
            for row in rows:
                f_id = row['file_id']
                if f_id not in matrix:
                    matrix[f_id] = {}
                matrix[f_id][row['step_name']] = {
                    'status': row['status'],
                    'points': row['points'],
                    'artist_name': row['artist_name'],
                    'artist_username': row['artist_username'],
                    'artist_lead': row['artist_lead']
                }
            
    lead_queue = []
    queue_stage = None
    artists = []
    
    if session['role'] in ['Lead', 'Admin']:
        if session['role'] == 'Lead':
            for stage, team in STAGE_TEAMS.items():
                if team == session['team']:
                    queue_stage = stage
                    break
        else:
            queue_stage = request.args.get('queue_stage', 'Content')
            
        if queue_stage:
            if queue_stage == 'Content':
                order_clause = "f.id ASC"
            else:
                order_clause = "f.content_released_at ASC, f.id ASC"
                
            if session['role'] == 'Lead':
                cursor.execute(f"""
                    SELECT f.id as file_id, f.name as file_name, f.description as file_desc, 
                           fp.id as pipeline_id, fp.status as step_status, fp.assigned_to as step_assigned_to,
                           fp.points, f.content_released_at, p.name as project_name, c.name as chapter_name
                    FROM file_pipeline fp
                    JOIN files f ON fp.file_id = f.id
                    JOIN chapters c ON f.chapter_id = c.id
                    JOIN projects p ON c.project_id = p.id
                    WHERE fp.step_name = ? AND fp.status IN ('Open', 'In Progress')
                    ORDER BY {order_clause}
                """, (queue_stage,))
            else:
                if chapter_id:
                    cursor.execute(f"""
                        SELECT f.id as file_id, f.name as file_name, f.description as file_desc, 
                               fp.id as pipeline_id, fp.status as step_status, fp.assigned_to as step_assigned_to,
                               fp.points, f.content_released_at, p.name as project_name, c.name as chapter_name
                        FROM file_pipeline fp
                        JOIN files f ON fp.file_id = f.id
                        JOIN chapters c ON f.chapter_id = c.id
                        JOIN projects p ON c.project_id = p.id
                        WHERE f.chapter_id = ? AND fp.step_name = ? AND fp.status IN ('Open', 'In Progress')
                        ORDER BY {order_clause}
                    """, (chapter_id, queue_stage))
                else:
                    cursor.execute(f"""
                        SELECT f.id as file_id, f.name as file_name, f.description as file_desc, 
                               fp.id as pipeline_id, fp.status as step_status, fp.assigned_to as step_assigned_to,
                               fp.points, f.content_released_at, p.name as project_name, c.name as chapter_name
                        FROM file_pipeline fp
                        JOIN files f ON fp.file_id = f.id
                        JOIN chapters c ON f.chapter_id = c.id
                        JOIN projects p ON c.project_id = p.id
                        WHERE fp.step_name = ? AND fp.status IN ('Open', 'In Progress')
                        ORDER BY {order_clause}
                    """, (queue_stage,))
            lead_queue = cursor.fetchall()
            
            if session['role'] == 'Lead':
                cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (session['team'],))
                artists = cursor.fetchall()
            else:
                target_team = STAGE_TEAMS[queue_stage]
                cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (target_team,))
                artists = cursor.fetchall()

    validation_list = []
    if session['role'] in ['Lead', 'Admin']:
        target_team = session['team'] if session['role'] == 'Lead' else STAGE_TEAMS.get(queue_stage)
        if target_team:
            cursor.execute("""
                SELECT da.id as assignment_id, da.points, da.status as assignment_status, da.task_description, da.remarks,
                       u.name as artist_name, u.username as artist_username, f.name as file_name, f.id as file_id,
                       p.name as project_name, c.name as chapter_name
                FROM daily_assignments da
                JOIN users u ON da.user_id = u.id
                JOIN files f ON da.file_id = f.id
                JOIN chapters c ON f.chapter_id = c.id
                JOIN projects p ON c.project_id = p.id
                WHERE da.date = ? AND u.team = ? AND da.status = 'Pending'
            """, (today_str, target_team))
            validation_list = cursor.fetchall()

    artist_tasks = []
    if session['role'] == 'Artist':
        cursor.execute("""
            SELECT da.id as assignment_id, da.task_description, da.points, da.status as assignment_status,
                   f.id as file_id, f.name as file_name, f.description as file_desc, 
                   fp.step_name, p.name as project_name, c.name as chapter_name
            FROM daily_assignments da
            JOIN files f ON da.file_id = f.id
            JOIN chapters c ON f.chapter_id = c.id
            JOIN projects p ON c.project_id = p.id
            JOIN file_pipeline fp ON (fp.file_id = f.id AND fp.assigned_to = da.user_id AND fp.status IN ('Open', 'In Progress'))
            WHERE da.user_id = ? AND da.date = ? AND da.status = 'Pending'
            ORDER BY p.name, c.name, f.name
        """, (session['user_id'], today_str))
        artist_tasks = cursor.fetchall()

    # DEADLINE WARNING CHECKS
    now = datetime.datetime.now()
    late_assignment_flag = False
    late_validation_flag = False
    
    if now.hour >= 10:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM file_pipeline fp
            JOIN files f ON fp.file_id = f.id
            WHERE fp.status = 'Open' AND f.chapter_id = ?
        """, (chapter_id,))
        open_count = cursor.fetchone()[0]
        if open_count > 0:
            late_assignment_flag = True
            
    if now.hour >= 18 or (now.hour == 18 and now.minute >= 30):
        if session['role'] == 'Lead':
            cursor.execute("""
                SELECT COUNT(*) FROM daily_assignments da
                JOIN users u ON da.user_id = u.id
                WHERE da.date = ? AND da.status = 'Pending' AND u.team = ?
            """, (today_str, session['team']))
            pending_cnt = cursor.fetchone()[0]
            if pending_cnt > 0:
                late_validation_flag = True

    # ─── CALCULATE ZOHO-STYLE DASHBOARD DATA ───
    import json
    view_tab = request.args.get('view', 'overview')
    
    # 1. Summary Cards calculation
    # Active Projects
    cursor.execute("SELECT COUNT(*) FROM projects WHERE status = 'Active'")
    active_projects_count = cursor.fetchone()[0]
    
    # Selected Project
    if session['role'] == 'Admin':
        selected_proj_id = request.args.get('project_id', default=0, type=int)
    else:
        selected_proj_id = request.args.get('project_id', default=project_id, type=int)
        
    # Total Files, Done, Wip counts
    if session['role'] == 'Artist':
        user_stages = [stage for stage, team in STAGE_TEAMS.items() if team == session['team']]
        placeholders = ','.join(['?'] * len(user_stages))
        
        if selected_proj_id > 0:
            cursor.execute(f"""
                SELECT COUNT(DISTINCT f.id) 
                FROM files f 
                JOIN chapters c ON f.chapter_id = c.id 
                JOIN file_pipeline fp ON f.id = fp.file_id
                WHERE c.project_id = ? AND fp.step_name IN ({placeholders}) AND (fp.assigned_to = ? OR fp.status IN ('Open', 'In Progress', 'Done'))
            """, (selected_proj_id, *user_stages, session['user_id']))
        else:
            cursor.execute(f"""
                SELECT COUNT(DISTINCT f.id) 
                FROM files f 
                JOIN file_pipeline fp ON f.id = fp.file_id
                WHERE fp.step_name IN ({placeholders}) AND (fp.assigned_to = ? OR fp.status IN ('Open', 'In Progress', 'Done'))
            """, (*user_stages, session['user_id']))
        total_files_count = cursor.fetchone()[0]

        if selected_proj_id > 0:
            cursor.execute(f"""
                SELECT COUNT(DISTINCT f.id) 
                FROM files f 
                JOIN chapters c ON f.chapter_id = c.id
                JOIN file_pipeline fp ON f.id = fp.file_id
                WHERE c.project_id = ? AND fp.step_name IN ({placeholders}) AND fp.status = 'Done'
            """, (selected_proj_id, *user_stages))
        else:
            cursor.execute(f"""
                SELECT COUNT(DISTINCT f.id) 
                FROM files f 
                JOIN file_pipeline fp ON f.id = fp.file_id
                WHERE fp.step_name IN ({placeholders}) AND fp.status = 'Done'
            """, tuple(user_stages))
        files_done_count = cursor.fetchone()[0]

        if selected_proj_id > 0:
            cursor.execute(f"""
                SELECT COUNT(DISTINCT f.id) 
                FROM files f 
                JOIN chapters c ON f.chapter_id = c.id
                JOIN file_pipeline fp ON f.id = fp.file_id
                WHERE c.project_id = ? AND fp.step_name IN ({placeholders}) AND fp.status = 'In Progress'
            """, (selected_proj_id, *user_stages))
        else:
            cursor.execute(f"""
                SELECT COUNT(DISTINCT f.id) 
                FROM files f 
                JOIN file_pipeline fp ON f.id = fp.file_id
                WHERE fp.step_name IN ({placeholders}) AND fp.status = 'In Progress'
            """, tuple(user_stages))
        files_wip_count = cursor.fetchone()[0]
    else:
        if selected_proj_id > 0:
            cursor.execute("SELECT COUNT(*) FROM files f JOIN chapters c ON f.chapter_id = c.id WHERE c.project_id = ?", (selected_proj_id,))
            total_files_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM files f JOIN chapters c ON f.chapter_id = c.id WHERE c.project_id = ? AND f.status = 'Completed'", (selected_proj_id,))
            files_done_count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(DISTINCT fp.file_id) 
                FROM file_pipeline fp 
                JOIN files f ON fp.file_id = f.id 
                JOIN chapters c ON f.chapter_id = c.id 
                WHERE c.project_id = ? AND fp.status = 'In Progress'
            """, (selected_proj_id,))
            files_wip_count = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM files")
            total_files_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM files WHERE status = 'Completed'")
            files_done_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT file_id) FROM file_pipeline WHERE status = 'In Progress'")
            files_wip_count = cursor.fetchone()[0]
        
    # Pending Approvals
    if session['role'] == 'Admin':
        cursor.execute("SELECT COUNT(*) FROM approvals WHERE status = 'Pending'")
        pending_approvals_count = cursor.fetchone()[0]
    elif session['role'] == 'Lead':
        cursor.execute("SELECT approval_chain, current_index FROM approvals WHERE status = 'Pending'")
        all_pending_aprv = cursor.fetchall()
        lead_aprv_cnt = 0
        for aprv in all_pending_aprv:
            try:
                aprv_chain = json.loads(aprv['approval_chain'])
                if aprv_chain[aprv['current_index']] == session['user_id']:
                    lead_aprv_cnt += 1
            except:
                pass
        cursor.execute("""
            SELECT COUNT(*) FROM daily_assignments da 
            JOIN users u ON da.user_id = u.id 
            WHERE da.date = ? AND u.team = ? AND da.status = 'Pending'
        """, (today_str, session['team']))
        val_cnt = cursor.fetchone()[0]
        pending_approvals_count = lead_aprv_cnt + val_cnt
    else:
        cursor.execute("SELECT COUNT(*) FROM approvals WHERE requester_id = ? AND status = 'Pending'", (session['user_id'],))
        pending_approvals_count = cursor.fetchone()[0]
        
    # Present Today ratio
    if session['role'] == 'Lead':
        cursor.execute("""
            SELECT COUNT(*) FROM attendance a 
            JOIN users u ON a.user_id = u.id 
            WHERE u.team = ? AND u.role = 'Artist' AND a.date = ? AND a.status IN ('Present', 'Late', 'Half Day')
        """, (session['team'], today_str))
        present_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE team = ? AND role = 'Artist'", (session['team'],))
        total_count = cursor.fetchone()[0]
    else:
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND status IN ('Present', 'Late', 'Half Day')", (today_str,))
        present_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE role IN ('Artist', 'Lead', 'HR')")
        total_count = cursor.fetchone()[0]
        
    attendance_ratio = f"{present_count} / {total_count}" if total_count > 0 else "0 / 0"
    if session['role'] == 'Artist':
        chart_stages = [stage for stage, team in STAGE_TEAMS.items() if team == session['team']]
        if not chart_stages:
            chart_stages = ['Animation']
    else:
        chart_stages = [
            'Content', 'Modeling', 'Texturing', 'Rig', 'Animation', 
            'FBX export', 'VFX', 'Lightning', 'Rendering', '3D Comp', 'Motion graphics'
        ]
    
    stage_completion_data = []
    stage_stats = {stage: {'Done': 0, 'Wip': 0, 'Yts': 0, 'Review': 0, 'Rtk': 0, 'Total': 0} for stage in chart_stages}
    
    if selected_proj_id > 0:
        cursor.execute("""
            SELECT fp.step_name, fp.status as fp_status, da.status as da_status, da.submit_time, da.remarks
            FROM file_pipeline fp
            JOIN files f ON fp.file_id = f.id
            JOIN chapters c ON f.chapter_id = c.id
            LEFT JOIN daily_assignments da ON (da.file_id = f.id AND da.user_id = fp.assigned_to AND da.date = ?)
            WHERE c.project_id = ?
        """, (today_str, selected_proj_id))
    else:
        cursor.execute("""
            SELECT fp.step_name, fp.status as fp_status, da.status as da_status, da.submit_time, da.remarks
            FROM file_pipeline fp
            JOIN files f ON fp.file_id = f.id
            LEFT JOIN daily_assignments da ON (da.file_id = f.id AND da.user_id = fp.assigned_to AND da.date = ?)
        """, (today_str,))
        
    for row in cursor.fetchall():
        stage = row['step_name']
        if stage in stage_stats:
            fp_status = row['fp_status']
            da_status = row['da_status']
            submit_time = row['submit_time']
            remarks = row['remarks']
            
            stage_stats[stage]['Total'] += 1
            if fp_status == 'Done':
                stage_stats[stage]['Done'] += 1
            elif fp_status == 'In Progress':
                if da_status == 'Pending':
                    if submit_time:
                        stage_stats[stage]['Review'] += 1
                    elif remarks and remarks != 'Validated Done':
                        stage_stats[stage]['Rtk'] += 1
                    else:
                        stage_stats[stage]['Wip'] += 1
                else:
                    stage_stats[stage]['Wip'] += 1
            else:
                stage_stats[stage]['Yts'] += 1
                
    for stage in chart_stages:
        stats = stage_stats[stage]
        total = stats['Total']
        pct = round((stats['Done'] / total) * 100, 1) if total > 0 else 0
        stage_completion_data.append({
            'stage': stage,
            'pct': pct,
            'Done': stats['Done'],
            'Wip': stats['Wip'],
            'Yts': stats['Yts'],
            'Review': stats['Review'],
            'Rtk': stats['Rtk']
        })
        
    overall_status_counts = {'Done': 0, 'Wip': 0, 'Yts': 0, 'Review': 0, 'Rtk': 0}
    if session['role'] == 'Artist':
        user_stages = [stage for stage, team in STAGE_TEAMS.items() if team == session['team']]
        placeholders = ','.join(['?'] * len(user_stages))
        if selected_proj_id > 0:
            cursor.execute(f"""
                SELECT fp.status as fp_status, da.status as da_status, da.submit_time, da.remarks
                FROM file_pipeline fp
                JOIN files f ON fp.file_id = f.id
                JOIN chapters c ON f.chapter_id = c.id
                LEFT JOIN daily_assignments da ON (da.file_id = fp.file_id AND da.user_id = fp.assigned_to AND da.date = ?)
                WHERE c.project_id = ? AND fp.step_name IN ({placeholders})
            """, (today_str, selected_proj_id, *user_stages))
        else:
            cursor.execute(f"""
                SELECT fp.status as fp_status, da.status as da_status, da.submit_time, da.remarks
                FROM file_pipeline fp
                LEFT JOIN daily_assignments da ON (da.file_id = fp.file_id AND da.user_id = fp.assigned_to AND da.date = ?)
                WHERE fp.step_name IN ({placeholders})
            """, (today_str, *user_stages))
        for row in cursor.fetchall():
            fp_status = row['fp_status']
            da_status = row['da_status']
            submit_time = row['submit_time']
            remarks = row['remarks']
            
            if fp_status == 'Done':
                overall_status_counts['Done'] += 1
            elif fp_status == 'In Progress':
                if da_status == 'Pending':
                    if submit_time:
                        overall_status_counts['Review'] += 1
                    elif remarks and remarks != 'Validated Done':
                        overall_status_counts['Rtk'] += 1
                    else:
                        overall_status_counts['Wip'] += 1
                else:
                    overall_status_counts['Wip'] += 1
            else:
                overall_status_counts['Yts'] += 1
    else:
        if selected_proj_id > 0:
            cursor.execute("SELECT f.id, f.status FROM files f JOIN chapters c ON f.chapter_id = c.id WHERE c.project_id = ?", (selected_proj_id,))
        else:
            cursor.execute("SELECT id, status FROM files")
            
        for file_row in cursor.fetchall():
            fid = file_row['id']
            f_status = file_row['status']
            if f_status == 'Completed':
                overall_status_counts['Done'] += 1
            else:
                cursor.execute("""
                    SELECT fp.status as fp_status, da.status as da_status, da.submit_time, da.remarks
                    FROM file_pipeline fp
                    LEFT JOIN daily_assignments da ON (da.file_id = fp.file_id AND da.user_id = fp.assigned_to AND da.date = ?)
                    WHERE fp.file_id = ? AND fp.status != 'Done'
                    ORDER BY fp.id ASC LIMIT 1
                """, (today_str, fid))
                active_step = cursor.fetchone()
                if active_step:
                    fp_status = active_step['fp_status']
                    da_status = active_step['da_status']
                    submit_time = active_step['submit_time']
                    remarks = active_step['remarks']
                    
                    if fp_status == 'In Progress':
                        if da_status == 'Pending':
                            if submit_time:
                                overall_status_counts['Review'] += 1
                            elif remarks and remarks != 'Validated Done':
                                overall_status_counts['Rtk'] += 1
                            else:
                                overall_status_counts['Wip'] += 1
                        else:
                            overall_status_counts['Wip'] += 1
                    else:
                        overall_status_counts['Yts'] += 1
                else:
                    overall_status_counts['Yts'] += 1
                    
    # Calculate file counts currently active at each stage for the selected project (for Pipeline Flow visual)
    pipeline_flow_counts = {stage: 0 for stage in PIPELINE_STAGES}
    if selected_proj_id > 0:
        cursor.execute("SELECT f.id, f.status FROM files f JOIN chapters c ON f.chapter_id = c.id WHERE c.project_id = ?", (selected_proj_id,))
    else:
        cursor.execute("SELECT id, status FROM files")
        
    for file_row in cursor.fetchall():
        fid = file_row['id']
        f_status = file_row['status']
        if f_status != 'Completed':
            cursor.execute("""
                SELECT fp.step_name 
                FROM file_pipeline fp
                WHERE fp.file_id = ? AND fp.status != 'Done'
                ORDER BY fp.id ASC LIMIT 1
            """, (fid,))
            active_step = cursor.fetchone()
            if active_step:
                step_name = active_step['step_name']
                if step_name in pipeline_flow_counts:
                    pipeline_flow_counts[step_name] += 1
 
    velocity_data = []
    try:
        today_date = datetime.datetime.strptime(today_str, '%Y-%m-%d').date()
    except:
        today_date = datetime.date.today()
        
    for i in range(5, -1, -1):
        start_w = today_date - datetime.timedelta(days=today_date.weekday() + i*7)
        end_w = start_w + datetime.timedelta(days=6)
        
        if session['role'] == 'Artist':
            cursor.execute("""
                SELECT COUNT(*) FROM daily_assignments da
                JOIN users u ON da.user_id = u.id
                WHERE da.status = 'Done' AND u.team = ? AND da.date BETWEEN ? AND ?
            """, (session['team'], start_w.strftime('%Y-%m-%d'), end_w.strftime('%Y-%m-%d')))
        elif selected_proj_id > 0:
            cursor.execute("""
                SELECT COUNT(*) FROM daily_assignments da
                JOIN files f ON da.file_id = f.id
                JOIN chapters c ON f.chapter_id = c.id
                WHERE da.status = 'Done' AND c.project_id = ? AND da.date BETWEEN ? AND ?
            """, (selected_proj_id, start_w.strftime('%Y-%m-%d'), end_w.strftime('%Y-%m-%d')))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM daily_assignments da
                WHERE da.status = 'Done' AND da.date BETWEEN ? AND ?
            """, (start_w.strftime('%Y-%m-%d'), end_w.strftime('%Y-%m-%d')))
        velocity_data.append({
            'label': f"Wk -{i}" if i > 0 else "This Wk",
            'count': cursor.fetchone()[0]
        })
        
    current_month = today_str[:7]
    performance_data = []
    if session['role'] == 'Artist':
        cursor.execute("SELECT target_points FROM monthly_targets WHERE user_id=? AND month=?", (session['user_id'], current_month))
        target_res = cursor.fetchone()
        tgt = target_res['target_points'] if target_res else 500
        
        cursor.execute("SELECT SUM(points) FROM points WHERE user_id=? AND strftime('%Y-%m', date)=?", (session['user_id'], current_month))
        earned = cursor.fetchone()[0] or 0
        performance_data.append({'name': session['name'], 'target': tgt, 'earned': earned})
    elif session['role'] == 'Lead':
        # Show self (lead) + team artists
        cursor.execute("SELECT id, name, role FROM users WHERE (team = ? AND role = 'Artist') OR id = ? ORDER BY role DESC, name", (session['team'], session['user_id']))
        for member in cursor.fetchall():
            cursor.execute("SELECT target_points FROM monthly_targets WHERE user_id=? AND month=?", (member['id'], current_month))
            target_res = cursor.fetchone()
            tgt = target_res['target_points'] if target_res else 500
            
            cursor.execute("SELECT SUM(points) FROM points WHERE user_id=? AND strftime('%Y-%m', date)=?", (member['id'], current_month))
            earned = cursor.fetchone()[0] or 0
            label = f"{member['name']} (Lead)" if member['role'] == 'Lead' else member['name']
            performance_data.append({'name': label, 'target': tgt, 'earned': earned})
    else:
        cursor.execute("SELECT id, name, team, role FROM users WHERE role IN ('Artist', 'Lead') ORDER BY team, role DESC, name")
        for member in cursor.fetchall():
            cursor.execute("SELECT target_points FROM monthly_targets WHERE user_id=? AND month=?", (member['id'], current_month))
            target_res = cursor.fetchone()
            tgt = target_res['target_points'] if target_res else 500
            
            cursor.execute("SELECT SUM(points) FROM points WHERE user_id=? AND strftime('%Y-%m', date)=?", (member['id'], current_month))
            earned = cursor.fetchone()[0] or 0
            role_tag = ' ★' if member['role'] == 'Lead' else ''
            performance_data.append({'name': f"{member['name']}{role_tag} ({member['team']})", 'target': tgt, 'earned': earned})
            
    artist_att_stats = None
    if session['role'] == 'Artist':
        month_prefix = today_str[:7]
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
                SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_days,
                SUM(CASE WHEN status = 'Half Day' THEN 1 ELSE 0 END) as half_days,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days
            FROM attendance
            WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        """, (session['user_id'], month_prefix))
        artist_att_stats = cursor.fetchone()
        
    hr_attendance_stats = None
    hr_leave_summary = None
    if session['role'] == 'HR':
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late,
                SUM(CASE WHEN status = 'Half Day' THEN 1 ELSE 0 END) as half,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent
            FROM attendance WHERE date = ?
        """, (today_str,))
        hr_attendance_stats = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) FROM leaves WHERE status = 'Pending'")
        pending_leaves_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM leaves WHERE ? BETWEEN start_date AND end_date AND status = 'Approved'", (today_str,))
        active_leaves_today = cursor.fetchone()[0]
        
        hr_leave_summary = {'pending': pending_leaves_count, 'active_today': active_leaves_today}

    recent_logs = []
    if session['role'] == 'Admin':
        cursor.execute("""
            SELECT l.action, l.timestamp, l.details, u.name as user_name 
            FROM activity_log l 
            LEFT JOIN users u ON l.user_id = u.id 
            ORDER BY l.id DESC LIMIT 15
        """)
        recent_logs = cursor.fetchall()
        
    return render_template(
        'dashboard.html', 
        user=user_profile, 
        logs=recent_logs,
        projects=projects,
        chapters=chapters,
        selected_project_id=selected_proj_id,
        selected_chapter_id=chapter_id,
        selected_chapter_name=selected_chapter_name,
        files=files,
        matrix=matrix,
        stages=stages_list,
        all_stages=PIPELINE_STAGES,
        STAGE_TEAMS=STAGE_TEAMS,
        active_projects_list=active_projects_list,
        project_chapters_map=project_chapters_map,
        chapter_files_map=chapter_files_map,
        sub_tab=sub_tab,
        lead_queue=lead_queue,
        queue_stage=queue_stage,
        artists=artists,
        artist_tasks=artist_tasks,
        validation_list=validation_list,
        late_assignment_flag=late_assignment_flag,
        late_validation_flag=late_validation_flag,
        today_str=today_str,
        attendance_today=attendance_today,
        view_tab=view_tab,
        active_projects_count=active_projects_count,
        total_files_count=total_files_count,
        files_done_count=files_done_count,
        files_wip_count=files_wip_count,
        pending_approvals_count=pending_approvals_count,
        attendance_ratio=attendance_ratio,
        stage_completion_data=stage_completion_data,
        overall_status_counts=overall_status_counts,
        velocity_data=velocity_data,
        performance_data=performance_data,
        artist_att_stats=artist_att_stats,
        hr_attendance_stats=hr_attendance_stats,
        hr_leave_summary=hr_leave_summary,
        pipeline_flow_counts=pipeline_flow_counts,
        pipeline_summary=pipeline_summary
    )

@app.route('/file/add', methods=['POST'])
def add_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session['role'] != 'Admin' and not (session['role'] == 'Lead' and session['team'] == 'Content'):
        flash("Unauthorized to add files.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    chapter_id = request.form.get('chapter_id', type=int)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    
    if not chapter_id or not name:
        flash("File name and chapter are required.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    sub_tab = request.form.get('sub_tab', 'assets')
    
    try:
        cursor.execute("""
            INSERT INTO files (chapter_id, name, description, status)
            VALUES (?, ?, ?, 'Pending')
        """, (chapter_id, name, description))
        file_id = cursor.lastrowid
        
        for stage in PIPELINE_STAGES:
            if sub_tab == 'scenes':
                status = 'Open' if stage == 'Animation' else 'Pending'
            else:
                status = 'Open' if stage == 'Content' else 'Pending'
            cursor.execute("""
                INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points)
                VALUES (?, ?, ?, NULL, 0)
            """, (file_id, stage, status))
            
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Create File', ?)",
                       (session['user_id'], f"Created file '{name}' in chapter ID {chapter_id}"))
        db.commit()
        flash(f"File '{name}' added to queue successfully.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error creating file: {e}", "error")
        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/files/edit-name/<int:file_id>', methods=['POST'])
def edit_file_name(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    flash("Unauthorized: Editing file details/names is locked. Changes must be tracked via the production flow.", "error")
    return redirect(url_for('dashboard'))

@app.route('/files/<int:file_id>/details', methods=['GET'])
def get_file_details(file_id):
    if 'user_id' not in session:
        return {'error': 'Unauthorized'}, 401
    if session['role'] not in ['Admin', 'HR', 'Lead']:
        return {'error': 'Forbidden'}, 403

    db = get_db()
    
    # Recalculate dynamic metadata on get details request
    recalculate_file_metadata(db, file_id)
    
    cursor = db.cursor()
    # Query file details
    cursor.execute("""
        SELECT f.id, f.name, f.description, f.chapter_id, f.assigned_to, f.start_date, f.end_date, f.remarks, f.final_approval_date,
               f.internal_lead_status, f.internal_content_status, f.final_review_status, f.status,
               p.name as project_name, c.name as chapter_name
        FROM files f
        JOIN chapters c ON f.chapter_id = c.id
        JOIN projects p ON c.project_id = p.id
        WHERE f.id = ?
    """, (file_id,))
    file_row = cursor.fetchone()
    if not file_row:
        return {'error': 'File not found'}, 404
        
    file_data = dict(file_row)
    
    # Fetch active artist name and username if assigned
    artist_name = ""
    artist_username = ""
    artist_lead = ""
    artist_team = ""
    if file_data['assigned_to']:
        cursor.execute("SELECT name, username, reports_to, team FROM users WHERE id = ?", (file_data['assigned_to'],))
        artist_row = cursor.fetchone()
        if artist_row:
            artist_name = artist_row['name']
            artist_username = artist_row['username']
            artist_lead = artist_row['reports_to']
            artist_team = artist_row['team']
            
    file_data['artist_name'] = artist_name
    file_data['artist_username'] = artist_username
    file_data['artist_lead'] = artist_lead
    file_data['artist_team'] = artist_team
    
    # Fetch all pipeline steps for this file
    cursor.execute("""
        SELECT fp.step_name, fp.status, fp.assigned_to, fp.points, fp.start_date, fp.end_date, fp.remarks,
               u.name as artist_name, u.username as artist_username, u.team as artist_team
        FROM file_pipeline fp
        LEFT JOIN users u ON fp.assigned_to = u.id
        WHERE fp.file_id = ?
    """, (file_id,))
    pipeline_steps = [dict(r) for r in cursor.fetchall()]
    
    # Sort steps by PIPELINE_STAGES order
    steps_map = {s['step_name']: s for s in pipeline_steps}
    sorted_steps = []
    for stage in PIPELINE_STAGES:
        if stage in steps_map:
            sorted_steps.append(steps_map[stage])
    
    # Calculate pending team and active stage for file details popup
    in_progress_step = next((s for s in sorted_steps if s['status'] == 'In Progress'), None)
    open_step = next((s for s in sorted_steps if s['status'] == 'Open'), None)
    pending_step = next((s for s in sorted_steps if s['status'] != 'Done'), None)
    
    target_step = in_progress_step or open_step or pending_step

    def resolve_team(step):
        if step and step.get('artist_team'):
            return step['artist_team']
        if step and step['step_name'] in STAGE_TEAMS:
            return STAGE_TEAMS[step['step_name']]
        return artist_team or "Content"

    if target_step:
        # Pipeline steps are still active / pending across teams
        active_stage = target_step['step_name']
        pending_team = resolve_team(target_step)
    else:
        # All pipeline steps are 'Done'! Check review workflow stages
        last_step_team = None
        if sorted_steps:
            for step in reversed(sorted_steps):
                if step.get('artist_team'):
                    last_step_team = step['artist_team']
                    break
                elif step['step_name'] in STAGE_TEAMS:
                    last_step_team = STAGE_TEAMS[step['step_name']]
                    break
        eff_team = artist_team or last_step_team or "Content"

        if file_data['internal_lead_status'] != 'Approved':
            active_stage = "Lead Review"
            pending_team = eff_team
        elif file_data['internal_content_status'] != 'Approved':
            active_stage = "Content Review"
            pending_team = "Content"
        elif file_data['final_review_status'] != 'Approved':
            active_stage = "Final Review"
            pending_team = "Management"
        else:
            # Fully approved across all teams and reviews
            active_stage = "Completed"
            pending_team = eff_team or "Management"

    file_data['pending_team'] = pending_team
    file_data['active_stage'] = active_stage

    # Fetch all artists for dropdown selection
    cursor.execute("SELECT id, name, username, team FROM users WHERE role = 'Artist' ORDER BY name")
    artists_list = [dict(r) for r in cursor.fetchall()]
    
    # Return everything including metadata about the current user and the pipeline steps
    return {
        'file': file_data,
        'pipeline_steps': sorted_steps,
        'artists': artists_list,
        'current_user': {
            'username': session['username'],
            'role': session['role'],
            'team': session['team']
        }
    }


@app.route('/files/<int:file_id>/update-details', methods=['POST'])
def update_file_details(file_id):
    if 'user_id' not in session:
        return {'error': 'Unauthorized'}, 401
    if session['role'] not in ['Admin', 'HR', 'Lead']:
        return {'error': 'Forbidden'}, 403

    db = get_db()
    cursor = db.cursor()
    
    # Get current file info
    cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    file_row = cursor.fetchone()
    if not file_row:
        return {'error': 'File not found'}, 404
        
    # Review action inputs
    lead_review_action = request.form.get('lead_review_action', '') # 'Approve', 'Reject', 'Reset'
    content_review_action = request.form.get('content_review_action', '')
    final_review_action = request.form.get('final_review_action', '')
    
    # Determine artist's lead based on currently calculated assigned artist
    assigned_to_id = file_row['assigned_to']
    artist_lead = None
    if assigned_to_id:
        cursor.execute("SELECT reports_to FROM users WHERE id = ?", (assigned_to_id,))
        artist_user_row = cursor.fetchone()
        if artist_user_row:
            artist_lead = artist_user_row['reports_to']
            
    try:
        # Review actions updates
        # 1. Respective team lead review
        if lead_review_action:
            # Respective team lead or Admin can approve/reject
            if session['role'] == 'Admin' or (session['role'] == 'Lead' and artist_lead == session['username']):
                if file_row['internal_lead_status'] != 'Approved':
                    new_lead_status = 'Approved' if lead_review_action == 'Approve' else ('Rejected' if lead_review_action == 'Reject' else 'Pending')
                    cursor.execute("UPDATE files SET internal_lead_status = ? WHERE id = ?", (new_lead_status, file_id))
                    db.commit()
                    # Log action
                    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Review Action', ?)",
                                   (session['user_id'], f"Team Lead set Lead Review for file ID {file_id} to '{new_lead_status}'"))
                    db.commit()
                
        # 2. Content lead review
        if content_review_action:
            # Pooja (Content Lead) or Admin can approve/reject
            if session['role'] == 'Admin' or (session['role'] == 'Lead' and session['username'] == 'pooja'):
                if file_row['internal_content_status'] != 'Approved':
                    new_content_status = 'Approved' if content_review_action == 'Approve' else ('Rejected' if content_review_action == 'Reject' else 'Pending')
                    cursor.execute("UPDATE files SET internal_content_status = ? WHERE id = ?", (new_content_status, file_id))
                    db.commit()
                    # Log action
                    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Review Action', ?)",
                                   (session['user_id'], f"Content Lead set Content Review for file ID {file_id} to '{new_content_status}'"))
                    db.commit()
                
        # 3. Final review
        if final_review_action:
            # Only Admin (Vasu) can approve/reject
            if session['role'] == 'Admin':
                if file_row['final_review_status'] != 'Approved':
                    new_final_status = 'Approved' if final_review_action == 'Approve' else ('Rejected' if final_review_action == 'Reject' else 'Pending')
                    
                    # If final review is approved, automatically set final_approval_date to today if not set, and set overall status to 'Done'
                    if new_final_status == 'Approved':
                        if not file_row['final_approval_date']:
                            today_str = datetime.date.today().strftime('%Y-%m-%d')
                            cursor.execute("""
                                UPDATE files 
                                SET final_review_status = ?, status = 'Done', final_approval_date = ? 
                                WHERE id = ?
                            """, (new_final_status, today_str, file_id))
                        else:
                            cursor.execute("""
                                UPDATE files 
                                SET final_review_status = ?, status = 'Done' 
                                WHERE id = ?
                            """, (new_final_status, file_id))
                    else:
                        cursor.execute("UPDATE files SET final_review_status = ? WHERE id = ?", (new_final_status, file_id))
                        
                    db.commit()
                    # Log action
                    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Review Action', ?)",
                                   (session['user_id'], f"Admin set Final Review for file ID {file_id} to '{new_final_status}'"))
                    db.commit()
                
        # Recalculate file metadata at the end to keep status in sync
        recalculate_file_metadata(db, file_id)
        
        return {'success': True}
    except Exception as e:
        db.rollback()
        return {'error': str(e)}, 500



@app.route('/file/assign', methods=['POST'])
def assign_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    file_id = request.form.get('file_id', type=int)
    step_name = request.form.get('step_name', '')
    artist_id = request.form.get('artist_id', '')
    points = request.form.get('points', type=int, default=0)
    
    if artist_id == '':
        artist_id = None
    else:
        artist_id = int(artist_id)
        
    if not file_id or not step_name:
        flash("Invalid assignment request.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    target_team = STAGE_TEAMS.get(step_name)
    if not target_team:
        flash("Invalid pipeline stage.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    if session['role'] != 'Lead' or session['team'] != target_team:
        flash("Unauthorized to assign files for this stage. Only the respective Lead can assign files.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    if artist_id:
        cursor.execute("SELECT name, team, role FROM users WHERE id = ?", (artist_id,))
        artist = cursor.fetchone()
        if not artist or artist['role'] != 'Artist' or artist['team'] != target_team:
            flash("Selected user is not an Artist of this team.", "error")
            return redirect(request.referrer or url_for('dashboard'))
        artist_name = artist['name']
        new_status = 'In Progress'
    else:
        artist_name = "Unassigned"
        new_status = 'Open'
        points = 0
        
    try:
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        if artist_id:
            cursor.execute("""
                UPDATE file_pipeline 
                SET assigned_to = ?, status = ?, points = ?, start_date = COALESCE(start_date, ?)
                WHERE file_id = ? AND step_name = ?
            """, (artist_id, new_status, points, today_str, file_id, step_name))
        else:
            cursor.execute("""
                UPDATE file_pipeline 
                SET assigned_to = ?, status = ?, points = ?
                WHERE file_id = ? AND step_name = ?
            """, (artist_id, new_status, points, file_id, step_name))
        
        cursor.execute("SELECT name, chapter_id FROM files WHERE id = ?", (file_id,))
        f_info = cursor.fetchone()
        
        if artist_id:
            cursor.execute("""
                SELECT id FROM daily_assignments 
                WHERE user_id = ? AND date = ? AND file_id = ?
            """, (artist_id, today_str, file_id))
            exist_da = cursor.fetchone()
            
            if exist_da:
                cursor.execute("""
                    UPDATE daily_assignments 
                    SET points = ?, status = 'Pending', task_description = ?
                    WHERE id = ?
                """, (points, f"{step_name}: {f_info['name']}", exist_da['id']))
            else:
                cursor.execute("""
                    INSERT INTO daily_assignments (user_id, date, file_id, task_description, points, status)
                    VALUES (?, ?, ?, ?, ?, 'Pending')
                """, (artist_id, today_str, file_id, f"{step_name}: {f_info['name']}", points))
                
        if artist_id:
            _push_notification(db, artist_id, "New task assigned", f"You have been assigned: '{f_info['name']}' ({step_name}) with {points} points.", "task", link=url_for('dashboard'))
            
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Assign File', ?)",
                       (session['user_id'], f"Assigned '{f_info['name']}' [{step_name}] to {artist_name} (Points: {points})"))
        db.commit()
        
        # Recalculate file metadata
        recalculate_file_metadata(db, file_id)
        
        flash(f"File updated: {f_info['name']} assigned to {artist_name} with {points} complexity points.", "success")

    except Exception as e:
        db.rollback()
        flash(f"Error assigning file: {e}", "error")
        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/file/status', methods=['POST'])
def update_status():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    file_id = request.form.get('file_id', type=int)
    step_name = request.form.get('step_name', '')
    status = request.form.get('status', '')
    
    if not file_id or not step_name or status not in ['In Progress', 'Done']:
        flash("Invalid status update parameters.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT fp.id, fp.status, fp.assigned_to, fp.points, f.name as file_name, f.chapter_id 
        FROM file_pipeline fp
        JOIN files f ON fp.file_id = f.id
        WHERE fp.file_id = ? AND fp.step_name = ?
    """, (file_id, step_name))
    pipeline_step = cursor.fetchone()
    
    if not pipeline_step:
        flash("Pipeline step not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    target_team = STAGE_TEAMS.get(step_name)
    
    is_assigned = (pipeline_step['assigned_to'] == session['user_id'])
    is_lead = (session['role'] == 'Lead' and session['team'] == target_team)
    is_admin = (session['role'] == 'Admin')
    
    if not (is_assigned or is_lead or is_admin):
        flash("Unauthorized to update status for this stage.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    if status == 'In Progress':
        cursor.execute("""
            UPDATE file_pipeline 
            SET status = ?, start_date = COALESCE(start_date, ?) 
            WHERE file_id = ? AND step_name = ?
        """, (status, today_str, file_id, step_name))
    elif status == 'Done':
        cursor.execute("""
            UPDATE file_pipeline 
            SET status = ?, start_date = COALESCE(start_date, ?), end_date = COALESCE(end_date, ?) 
            WHERE file_id = ? AND step_name = ?
        """, (status, today_str, today_str, file_id, step_name))
    
    submit_time_val = None
    if status == 'Done':
        submit_time_val = datetime.datetime.now().strftime('%H:%M:%S')

    cursor.execute("""
        UPDATE daily_assignments 
        SET status = 'Pending', submit_time = ?
        WHERE file_id = ? AND user_id = ? AND date = ?
    """, (submit_time_val, file_id, pipeline_step['assigned_to'], today_str))
    
    log_details = f"Artist updated status of '{pipeline_step['file_name']}' [{step_name}] to '{status}'"
    
    if status == 'Done' and not (is_lead or is_admin):
        cursor.execute("SELECT id FROM users WHERE role = 'Lead' AND team = ?", (target_team,))
        leads = cursor.fetchall()
        for lead in leads:
            _push_notification(db, lead['id'], "Validation Required", f"Artist {session['name']} marked '{pipeline_step['file_name']}' [{step_name}] Done. Please validate.", "approval", link=url_for('dashboard'))
    
    if status == 'Done' and (is_lead or is_admin):
        cursor.execute("""
            UPDATE daily_assignments 
            SET status = 'Done' 
            WHERE file_id = ? AND date = ?
        """, (file_id, today_str))
        
        cursor.execute("""
            INSERT INTO points (user_id, date, points, reason, awarded_by)
            VALUES (?, ?, ?, ?, ?)
        """, (pipeline_step['assigned_to'], today_str, pipeline_step['points'], 
              f"Completed stage: {pipeline_step['file_name']} [{step_name}]", session['user_id']))
              
        if step_name == 'Content':
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE files SET content_released_at = ? WHERE id = ?", (now_str, file_id))
            
        idx = PIPELINE_STAGES.index(step_name)
        if idx < len(PIPELINE_STAGES) - 1:
            next_stage = PIPELINE_STAGES[idx + 1]
            cursor.execute("""
                UPDATE file_pipeline 
                SET status = 'Open' 
                WHERE file_id = ? AND step_name = ? AND status = 'Pending'
            """, (file_id, next_stage))
            
            next_team = STAGE_TEAMS.get(next_stage)
            if next_team:
                cursor.execute("SELECT id FROM users WHERE team = ? AND role = 'Lead'", (next_team,))
                next_leads = cursor.fetchall()
                for nl in next_leads:
                    _push_notification(db, nl['id'], "File now open for your team", f"File '{pipeline_step['file_name']}' is now open for your stage ({next_stage}).", "info", link=url_for('dashboard'))
            
    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                   (session['user_id'], 'Pipeline Update', log_details))
    db.commit()
    
    # Recalculate file metadata
    recalculate_file_metadata(db, file_id)
    
    flash(f"Status updated for '{pipeline_step['file_name']}' [{step_name}] to '{status}'.", "success")

    return redirect(request.referrer or url_for('dashboard'))

@app.route('/assignment/validate', methods=['POST'])
def validate_assignment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    assignment_id = request.form.get('assignment_id', type=int)
    validation_status = request.form.get('validation_status', '')
    remarks = request.form.get('remarks', '').strip()
    
    if not assignment_id or validation_status not in ['Done', 'Pending']:
        flash("Invalid validation parameters.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT da.*, u.team, u.name as artist_name, f.name as file_name 
        FROM daily_assignments da
        JOIN users u ON da.user_id = u.id
        JOIN files f ON da.file_id = f.id
        WHERE da.id = ?
    """, (assignment_id,))
    da = cursor.fetchone()
    
    if not da:
        flash("Assignment record not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    if session['role'] != 'Admin' and not (session['role'] == 'Lead' and session['team'] == da['team']):
        flash("Unauthorized to validate assignments for this team.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    if validation_status == 'Done':
        cursor.execute("UPDATE daily_assignments SET status = 'Done', remarks = ? WHERE id = ?", ("Validated Done", assignment_id))
        
        cursor.execute("""
            SELECT step_name, points FROM file_pipeline 
            WHERE file_id = ? AND assigned_to = ? AND status IN ('Open', 'In Progress')
        """, (da['file_id'], da['user_id']))
        step_row = cursor.fetchone()
        
        if step_row:
            step_name = step_row['step_name']
            points_val = step_row['points']
            
            cursor.execute("""
                UPDATE file_pipeline 
                SET status = 'Done', start_date = COALESCE(start_date, ?), end_date = COALESCE(end_date, ?), remarks = NULL
                WHERE file_id = ? AND step_name = ?
            """, (today_str, today_str, da['file_id'], step_name))
            
            cursor.execute("""
                INSERT INTO points (user_id, date, points, reason, awarded_by)
                VALUES (?, ?, ?, ?, ?)
            """, (da['user_id'], today_str, points_val, f"EOD Completed: {da['file_name']} [{step_name}]", session['user_id']))
            
            if step_name == 'Content':
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("UPDATE files SET content_released_at = ? WHERE id = ?", (now_str, da['file_id']))
                
            idx = PIPELINE_STAGES.index(step_name)
            if idx < len(PIPELINE_STAGES) - 1:
                next_stage = PIPELINE_STAGES[idx + 1]
                cursor.execute("""
                    UPDATE file_pipeline SET status = 'Open' 
                    WHERE file_id = ? AND step_name = ? AND status = 'Pending'
                """, (da['file_id'], next_stage))
                
                next_team = STAGE_TEAMS.get(next_stage)
                if next_team:
                    cursor.execute("SELECT id FROM users WHERE team = ? AND role = 'Lead'", (next_team,))
                    next_leads = cursor.fetchall()
                    for nl in next_leads:
                        _push_notification(db, nl['id'], "File now open for your team", f"File '{da['file_name']}' is now open for your stage ({next_stage}).", "info", link=url_for('dashboard'))
            else:
                cursor.execute("UPDATE files SET status = 'Completed' WHERE id = ?", (da['file_id'],))
                
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'EOD Validation Done', ?)",
                       (session['user_id'], f"Validated EOD Task Done for {da['artist_name']} on '{da['file_name']}'"))
        _push_notification(db, da['user_id'], "Task Completed", f"Your task '{da['file_name']}' has been validated as Done. Points credited!", "task", link=url_for('dashboard'))
        db.commit()
        
        # Recalculate file metadata
        recalculate_file_metadata(db, da['file_id'])
        
        flash(f"Task for {da['artist_name']} validated as completed. Points credited!", "success")
        
    elif validation_status == 'Pending':
        if not remarks:
            flash("A typed reason is required to mark a task as Pending.", "error")
            return redirect(request.referrer or url_for('dashboard'))
            
        cursor.execute("UPDATE daily_assignments SET status = 'Pending', remarks = ? WHERE id = ?", (remarks, assignment_id))
        
        # Set remarks in the active step of file_pipeline
        cursor.execute("""
            SELECT step_name FROM file_pipeline 
            WHERE file_id = ? AND assigned_to = ? AND status IN ('Open', 'In Progress')
        """, (da['file_id'], da['user_id']))
        step_row = cursor.fetchone()
        if step_row:
            cursor.execute("""
                UPDATE file_pipeline SET remarks = ? 
                WHERE file_id = ? AND step_name = ?
            """, (remarks, da['file_id'], step_row['step_name']))
        
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        cursor.execute("""
            INSERT INTO daily_assignments (user_id, date, file_id, task_description, points, status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
        """, (da['user_id'], tomorrow_str, da['file_id'], da['task_description'], da['points']))
        
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'EOD Validation Pending', ?)",
                       (session['user_id'], f"Carried forward task for {da['artist_name']} on '{da['file_name']}' to tomorrow. Reason: {remarks}"))
        _push_notification(db, da['user_id'], "Task Pending", f"Your task '{da['file_name']}' has been marked Pending. Reason: {remarks}", "task", link=url_for('dashboard'))
        db.commit()
        
        # Recalculate file metadata
        recalculate_file_metadata(db, da['file_id'])
        
        flash(f"Task for {da['artist_name']} marked pending and carried forward to tomorrow.", "info")

        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/target/set', methods=['POST'])
@app.route('/points/set-target', methods=['POST'])
def set_monthly_target():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    artist_id = request.form.get('artist_id', type=int)
    target_points = request.form.get('target_points', type=int)
    month = request.form.get('month', '') or datetime.date.today().strftime('%Y-%m')
    
    if not artist_id or not target_points or not month:
        flash("Invalid target values.", "error")
        return redirect(request.referrer or url_for('work_reports_page'))
        
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT team, name, role FROM users WHERE id = ?", (artist_id,))
    artist = cursor.fetchone()
    
    if not artist:
        flash("Employee not found.", "error")
        return redirect(request.referrer or url_for('work_reports_page'))
        
    if session['role'] != 'Admin':
        if not (session['role'] == 'Lead' and session['team'] == artist['team'] and artist['role'] == 'Artist'):
            flash("Unauthorized to set target for this user.", "error")
            return redirect(request.referrer or url_for('work_reports_page'))
        
    cursor.execute("SELECT id FROM monthly_targets WHERE user_id = ? AND month = ?", (artist_id, month))
    target_row = cursor.fetchone()
    
    if target_row:
        cursor.execute("UPDATE monthly_targets SET target_points = ? WHERE id = ?", (target_points, target_row['id']))
    else:
        cursor.execute("INSERT INTO monthly_targets (user_id, month, target_points) VALUES (?, ?, ?)", (artist_id, month, target_points))
        
    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Set Target', ?)",
                   (session['user_id'], f"Set monthly target of {target_points} pts for {artist['name']} for {month}"))
    db.commit()
    
    flash(f"Monthly points target set to {target_points} for {artist['name']}.", "success")
    return redirect(request.referrer or url_for('work_reports_page'))

@app.route('/points')
def points_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'Admin':
        return redirect(url_for('work_reports_page', **request.args))
        
    db = get_db()
    cursor = db.cursor()
    
    current_month = datetime.date.today().strftime('%Y-%m')
    
    def get_user_progress(uid):
        cursor.execute("SELECT target_points FROM monthly_targets WHERE user_id = ? AND month = ?", (uid, current_month))
        target_res = cursor.fetchone()
        target = target_res['target_points'] if target_res else 500
        
        cursor.execute("""
            SELECT SUM(points) FROM points 
            WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        """, (uid, current_month))
        earned_res = cursor.fetchone()
        earned = earned_res[0] if earned_res and earned_res[0] is not None else 0
        
        pct = int((earned / target) * 100) if target > 0 else 0
        return target, earned, pct
        
    my_target, my_earned, my_pct = get_user_progress(session['user_id'])
    
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    week_days = [start_of_week + datetime.timedelta(days=i) for i in range(7)]
    
    weekly_points = []
    for day in week_days:
        day_str = day.strftime('%Y-%m-%d')
        cursor.execute("SELECT SUM(points) FROM points WHERE user_id = ? AND date = ?", (session['user_id'], day_str))
        pts = cursor.fetchone()[0]
        weekly_points.append({
            'day_name': day.strftime('%A'),
            'date': day_str,
            'points': pts if pts is not None else 0
        })
        
    team_scoreboard = []
    global_scoreboard = {}
    
    if session['role'] == 'Lead':
        cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (session['team'],))
        artists = cursor.fetchall()
        for artist in artists:
            target, earned, pct = get_user_progress(artist['id'])
            team_scoreboard.append({
                'id': artist['id'],
                'name': artist['name'],
                'username': artist['username'],
                'target': target,
                'earned': earned,
                'pct': pct
            })
            
    elif session['role'] == 'Admin':
        cursor.execute("SELECT id, name, username, team, role FROM users WHERE role IN ('Artist', 'Lead') ORDER BY team, role, name")
        all_users = cursor.fetchall()
        for u in all_users:
            team = u['team']
            if team not in global_scoreboard:
                global_scoreboard[team] = []
            target, earned, pct = get_user_progress(u['id'])
            global_scoreboard[team].append({
                'id': u['id'],
                'name': u['name'],
                'username': u['username'],
                'role': u['role'],
                'target': target,
                'earned': earned,
                'pct': pct
            })
            
    target_artists = []
    if session['role'] == 'Lead':
        cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (session['team'],))
        target_artists = cursor.fetchall()
    elif session['role'] == 'Admin':
        cursor.execute("SELECT id, name, username, team, role FROM users WHERE role IN ('Artist', 'Lead') ORDER BY name")
        target_artists = cursor.fetchall()
        
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_profile = cursor.fetchone()

    selected_employee = None
    points_transactions = []
    selected_target = 0
    selected_earned = 0
    selected_pct = 0
    selected_month = request.args.get('month', default=current_month)
    
    import re
    if not selected_month or not re.match(r'^\d{4}-\d{2}$', selected_month):
        selected_month = current_month
        
    selected_employee_id = request.args.get('employee_id', type=int)
    if session['role'] == 'Admin' and selected_employee_id:
        cursor.execute("SELECT id, name, username, team, role FROM users WHERE id = ? AND role IN ('Artist', 'Lead')", (selected_employee_id,))
        selected_employee = cursor.fetchone()
        if selected_employee:
            cursor.execute("SELECT target_points FROM monthly_targets WHERE user_id = ? AND month = ?", (selected_employee['id'], selected_month))
            t_res = cursor.fetchone()
            selected_target = t_res['target_points'] if t_res else 500
            
            cursor.execute("""
                SELECT SUM(points) FROM points 
                WHERE user_id = ? AND strftime('%Y-%m', date) = ?
            """, (selected_employee['id'], selected_month))
            e_res = cursor.fetchone()
            selected_earned = e_res[0] if e_res and e_res[0] is not None else 0
            
            selected_pct = int((selected_earned / selected_target) * 100) if selected_target > 0 else 0
            
            cursor.execute("""
                SELECT p.date, p.points, p.reason, u.name as awarded_by_name
                FROM points p
                LEFT JOIN users u ON p.awarded_by = u.id
                WHERE p.user_id = ? AND strftime('%Y-%m', p.date) = ?
                ORDER BY p.date DESC, p.id DESC
            """, (selected_employee['id'], selected_month))
            points_transactions = cursor.fetchall()

    return render_template(
        'points.html',
        user=user_profile,
        my_target=my_target,
        my_earned=my_earned,
        my_pct=my_pct,
        weekly_points=weekly_points,
        team_scoreboard=team_scoreboard,
        global_scoreboard=global_scoreboard,
        target_artists=target_artists,
        current_month=current_month,
        selected_employee=selected_employee,
        points_transactions=points_transactions,
        selected_target=selected_target,
        selected_earned=selected_earned,
        selected_pct=selected_pct,
        selected_month=selected_month
    )

# LAYER 4 - ATTENDANCE ROUTES
@app.route('/attendance/clock-in', methods=['POST'])
def clock_in():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'Admin':
        flash("Admin accounts do not mark attendance.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    custom_time = request.form.get('custom_time', '').strip()
    custom_date = request.form.get('custom_date', '').strip()
    
    today_str = custom_date if custom_date else datetime.date.today().strftime('%Y-%m-%d')
    
    if custom_time:
        try:
            if len(custom_time.split(':')) == 2:
                custom_time += ':00'
            now = datetime.datetime.strptime(f"{today_str} {custom_time}", "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            flash(f"Invalid custom time format: {e}", "error")
            return redirect(request.referrer or url_for('dashboard'))
    else:
        now = datetime.datetime.now()
        
    clock_in_str = now.strftime('%H:%M:%S')
    
    # Check if already clocked in today
    cursor.execute("SELECT id FROM attendance WHERE user_id = ? AND date = ?", (session['user_id'], today_str))
    if cursor.fetchone():
        flash("You have already checked in today.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    status, late_minutes, early_minutes, total_hours, extra_hours = calculate_attendance_metrics(db, session['user_id'], today_str, clock_in_str)
    
    try:
        cursor.execute("""
            INSERT INTO attendance (user_id, date, clock_in, status, late_minutes)
            VALUES (?, ?, ?, ?, ?)
        """, (session['user_id'], today_str, clock_in_str, status, late_minutes))
        
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Clock In', ?)",
                       (session['user_id'], f"Clocked in today at {clock_in_str} (Status: {status}, Late Minutes: {late_minutes})"))
        db.commit()
        
        flash(f"Checked in successfully at {clock_in_str}. Status: {status}.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error clocking in: {e}", "error")
        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/attendance/clock-out', methods=['POST'])
def clock_out():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'Admin':
        flash("Admin accounts do not mark attendance.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    custom_time = request.form.get('custom_time', '').strip()
    custom_date = request.form.get('custom_date', '').strip()
    
    today_str = custom_date if custom_date else datetime.date.today().strftime('%Y-%m-%d')
    
    if custom_time:
        try:
            if len(custom_time.split(':')) == 2:
                custom_time += ':00'
            now = datetime.datetime.strptime(f"{today_str} {custom_time}", "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            flash(f"Invalid custom time format: {e}", "error")
            return redirect(request.referrer or url_for('dashboard'))
    else:
        now = datetime.datetime.now()
        
    clock_out_str = now.strftime('%H:%M:%S')
    
    # Fetch active clock-in for today
    cursor.execute("""
        SELECT * FROM attendance 
        WHERE user_id = ? AND date = ? AND clock_out IS NULL
    """, (session['user_id'], today_str))
    att = cursor.fetchone()
    
    if not att:
        flash("No active check-in record found for today.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    status, late_minutes, early_minutes, total_hours, extra_hours = calculate_attendance_metrics(
        db, session['user_id'], today_str, att['clock_in'], clock_out_str)
        
    try:
        cursor.execute("""
            UPDATE attendance 
            SET clock_out = ?, status = ?, late_minutes = ?, early_minutes = ?, total_hours = ?, extra_hours = ?
            WHERE id = ?
        """, (clock_out_str, status, late_minutes, early_minutes, total_hours, extra_hours, att['id']))
        
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Clock Out', ?)",
                       (session['user_id'], f"Clocked out today at {clock_out_str} (Duration: {total_hours:.2f} hrs, Extra: {extra_hours:.2f} hrs, Early Mins: {early_minutes})"))
        db.commit()
        
        flash(f"Checked out successfully at {clock_out_str}. Total hours: {total_hours:.2f}.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error clocking out: {e}", "error")
        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/attendance')
def attendance_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    year = request.args.get('year', default=datetime.date.today().year, type=int)
    month = request.args.get('month', default=datetime.date.today().month, type=int)
    
    # Resolve target employee ID for calendar inspection
    target_uid = request.args.get('employee_id', default=session['user_id'], type=int)
    if target_uid != session['user_id'] and session['role'] not in ['Admin', 'HR']:
        if session['role'] == 'Lead':
            cursor.execute("SELECT team FROM users WHERE id = ?", (target_uid,))
            target_u = cursor.fetchone()
            if not target_u or target_u['team'] != session['team']:
                target_uid = session['user_id']
        else:
            target_uid = session['user_id']
    cursor.execute("SELECT * FROM users WHERE id = ?", (target_uid,))
    target_user = cursor.fetchone()
    
    # 1. BUILD INDIVIDUAL MONTHLY CALENDAR GRID
    # calendar.monthrange(year, month) -> (first_weekday, num_days)
    first_weekday, num_days = calendar.monthrange(year, month)
    
    # Get attendance data for selected month
    month_prefix = f"{year}-{month:02d}"
    cursor.execute("""
        SELECT * FROM attendance 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
    """, (target_uid, month_prefix))
    att_list = {row['date']: row for row in cursor.fetchall()}
    
    # Get approved leaves for selected month
    cursor.execute("""
        SELECT * FROM leaves 
        WHERE user_id = ? AND status = 'Approved' 
          AND (strftime('%Y-%m', start_date) = ? OR strftime('%Y-%m', end_date) = ?)
    """, (target_uid, month_prefix, month_prefix))
    leaves_list = cursor.fetchall()
    
    # Get holidays for selected month
    cursor.execute("SELECT * FROM holidays WHERE strftime('%Y-%m', date) = ?", (month_prefix,))
    holidays_list = {row['date']: row['name'] for row in cursor.fetchall()}
    
    calendar_days = []
    
    # Padding cells before first day of month
    # weekday mapping in calendar: Monday is 0, Sunday is 6
    for p in range(first_weekday):
        calendar_days.append({'type': 'padding'})
        
    # Main calendar loop
    today_date = datetime.date.today()
    
    for day in range(1, num_days + 1):
        day_date = datetime.date(year, month, day)
        day_str = day_date.strftime('%Y-%m-%d')
        
        status = 'Future'
        clock_in_time = None
        clock_out_time = None
        late_mins = 0
        extra_hrs = 0.0
        label = ""
        
        # Check database records
        early_mins = 0
        if day_str in att_list:
            status = att_list[day_str]['status']
            clock_in_time = att_list[day_str]['clock_in']
            clock_out_time = att_list[day_str]['clock_out']
            late_mins = att_list[day_str]['late_minutes']
            early_mins = att_list[day_str]['early_minutes'] if 'early_minutes' in att_list[day_str].keys() else 0
            extra_hrs = att_list[day_str]['extra_hours']
        else:
            # Overlapping leave check
            is_leave = False
            for leave in leaves_list:
                s_date = datetime.datetime.strptime(leave['start_date'], '%Y-%m-%d').date()
                e_date = datetime.datetime.strptime(leave['end_date'], '%Y-%m-%d').date()
                if s_date <= day_date <= e_date:
                    is_leave = True
                    break
            
            if is_leave:
                status = 'Leave'
            elif is_weekly_off(day_date):
                status = 'Off'
            elif day_str in holidays_list:
                status = 'Holiday'
                label = holidays_list[day_str]
            else:
                if day_date > today_date:
                    status = 'Future'
                elif day_date == today_date:
                    status = 'Absent' # Not clocked in yet today
                else:
                    status = 'Absent' # Past day un-tracked
                    
        calendar_days.append({
            'type': 'day',
            'day': day,
            'date': day_str,
            'status': status,
            'clock_in': clock_in_time,
            'clock_out': clock_out_time,
            'late_minutes': late_mins,
            'early_minutes': early_mins,
            'extra_hours': extra_hrs,
            'label': label
        })
        
    # Group calendar_days into weeks of 7 cells
    calendar_weeks = [calendar_days[i:i+7] for i in range(0, len(calendar_days), 7)]
    
    # 2. RESOLVE OVERVIEW TABLES BY ROLE
    team_today = []
    team_monthly_stats = []
    global_today = {}
    global_monthly_stats = {}
    
    # Fetch team members (Leads / Admin / HR)
    if session['role'] == 'Lead':
        # Today's Team status
        cursor.execute("""
            SELECT u.id as user_id, u.name, u.username, att.clock_in, att.clock_out, att.status as att_status, att.late_minutes, att.extra_hours
            FROM users u
            LEFT JOIN attendance att ON (u.id = att.user_id AND att.date = ?)
            WHERE u.team = ? AND u.role IN ('Artist', 'Lead')
        """, (today_str, session['team']))
        team_today = cursor.fetchall()
        
        # Monthly team statistics
        cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role IN ('Artist', 'Lead')", (session['team'],))
        team_artists = cursor.fetchall()
        
        for artist in team_artists:
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
                    SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_days,
                    SUM(CASE WHEN status = 'Half Day' THEN 1 ELSE 0 END) as half_days,
                    SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
                    SUM(extra_hours) as extra_hours_total,
                    SUM(late_minutes) as late_mins_total,
                    SUM(early_minutes) as early_mins_total
                FROM attendance
                WHERE user_id = ? AND strftime('%Y-%m', date) = ?
            """, (artist['id'], month_prefix))
            stats = cursor.fetchone()
            
            # Count leaves approved for this artist in the selected month
            cursor.execute("""
                SELECT COUNT(*) FROM leaves 
                WHERE user_id = ? AND status = 'Approved' AND strftime('%Y-%m', start_date) = ?
            """, (artist['id'], month_prefix))
            leaves_cnt = cursor.fetchone()[0]
            
            l_mins = stats['late_mins_total'] if stats['late_mins_total'] else 0
            e_mins = stats['early_mins_total'] if stats['early_mins_total'] else 0
            ex_hours = stats['extra_hours_total'] if stats['extra_hours_total'] else 0.0
            pending_mins = int((l_mins + e_mins) - (ex_hours * 60))
            
            team_monthly_stats.append({
                'id': artist['id'],
                'name': artist['name'],
                'username': artist['username'],
                'present': stats['present_days'] if stats['present_days'] else 0,
                'late': stats['late_days'] if stats['late_days'] else 0,
                'half_day': stats['half_days'] if stats['half_days'] else 0,
                'absent': stats['absent_days'] if stats['absent_days'] else 0,
                'leaves': leaves_cnt,
                'extra_hours': ex_hours,
                'late_minutes': l_mins,
                'early_minutes': e_mins,
                'pending_minutes': pending_mins
            })
            
    elif session['role'] in ['Admin', 'HR']:
        # Fetch today's summary for all employees in the system, grouped by team
        cursor.execute("SELECT id, name, username, team, role FROM users ORDER BY team, role")
        all_users = cursor.fetchall()
        
        for emp in all_users:
            team = emp['team']
            if team not in global_today:
                global_today[team] = []
                global_monthly_stats[team] = []
                
            cursor.execute("""
                SELECT clock_in, clock_out, status, late_minutes, extra_hours 
                FROM attendance WHERE user_id = ? AND date = ?
            """, (emp['id'], today_str))
            emp_att = cursor.fetchone()
            
            # Check leave status
            cursor.execute("""
                SELECT id FROM leaves 
                WHERE user_id = ? AND ? BETWEEN start_date AND end_date AND status = 'Approved'
            """, (emp['id'], today_str))
            on_leave = cursor.fetchone() is not None
            
            resolved_status = 'Absent'
            if emp_att:
                resolved_status = emp_att['status']
            elif on_leave:
                resolved_status = 'Leave'
            elif is_weekly_off(today_date):
                resolved_status = 'Off'
                
            global_today[team].append({
                'id': emp['id'],
                'name': emp['name'],
                'username': emp['username'],
                'role': emp['role'],
                'clock_in': emp_att['clock_in'] if emp_att else None,
                'clock_out': emp_att['clock_out'] if emp_att else None,
                'status': resolved_status,
                'late_minutes': emp_att['late_minutes'] if emp_att else 0,
                'extra_hours': emp_att['extra_hours'] if emp_att else 0.0
            })
            
            # Compute monthly statistics
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
                    SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_days,
                    SUM(CASE WHEN status = 'Half Day' THEN 1 ELSE 0 END) as half_days,
                    SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
                    SUM(extra_hours) as extra_hours_total,
                    SUM(late_minutes) as late_mins_total,
                    SUM(early_minutes) as early_mins_total
                FROM attendance
                WHERE user_id = ? AND strftime('%Y-%m', date) = ?
            """, (emp['id'], month_prefix))
            stats = cursor.fetchone()
            
            cursor.execute("""
                SELECT COUNT(*) FROM leaves 
                WHERE user_id = ? AND status = 'Approved' AND strftime('%Y-%m', start_date) = ?
            """, (emp['id'], month_prefix))
            leaves_cnt = cursor.fetchone()[0]
            
            l_mins = stats['late_mins_total'] if stats['late_mins_total'] else 0
            e_mins = stats['early_mins_total'] if stats['early_mins_total'] else 0
            ex_hours = stats['extra_hours_total'] if stats['extra_hours_total'] else 0.0
            pending_mins = int((l_mins + e_mins) - (ex_hours * 60))
            
            global_monthly_stats[team].append({
                'id': emp['id'],
                'name': emp['name'],
                'username': emp['username'],
                'role': emp['role'],
                'present': stats['present_days'] if stats['present_days'] else 0,
                'late': stats['late_days'] if stats['late_days'] else 0,
                'half_day': stats['half_days'] if stats['half_days'] else 0,
                'absent': stats['absent_days'] if stats['absent_days'] else 0,
                'leaves': leaves_cnt,
                'extra_hours': ex_hours,
                'late_minutes': l_mins,
                'early_minutes': e_mins,
                'pending_minutes': pending_mins
            })

    # Get active clock-in info today for clock-widget on attendance page
    cursor.execute("SELECT * FROM attendance WHERE user_id = ? AND date = ?", (session['user_id'], today_str))
    attendance_today = cursor.fetchone()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_profile = cursor.fetchone()

    return render_template(
        'attendance.html',
        user=user_profile,
        target_user=target_user,
        calendar_weeks=calendar_weeks,
        selected_year=year,
        selected_month=month,
        team_today=team_today,
        team_monthly_stats=team_monthly_stats,
        global_today=global_today,
        global_monthly_stats=global_monthly_stats,
        attendance_today=attendance_today,
        today_str=today_str
    )

@app.route('/attendance/view/<int:employee_id>')
def attendance_view_user(employee_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session['role'] not in ['Admin', 'HR', 'Lead']:
        flash("Unauthorized to view other employee records.", "error")
        return redirect(url_for('attendance_page'))
        
    if session['role'] == 'Lead':
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT team FROM users WHERE id = ?", (employee_id,))
        emp_user = cursor.fetchone()
        if not emp_user or emp_user['team'] != session['team']:
            flash("Unauthorized to view this employee's records.", "error")
            return redirect(url_for('attendance_page'))
            
    return redirect(url_for('attendance_page', employee_id=employee_id))

# LAYER 5: LEAVES & REUSABLE APPROVAL ENGINE

def get_approval_chain(db, user_id, role, reports_to_username):
    cursor = db.cursor()
    # Find Admin's user ID
    cursor.execute("SELECT id FROM users WHERE role = 'Admin' LIMIT 1")
    admin_row = cursor.fetchone()
    admin_id = admin_row['id'] if admin_row else 1
    
    if role == 'Admin':
        return []
        
    chain = []
    
    # If the user is an Artist, they need their Lead first, then the Admin
    if role == 'Artist':
        lead_id = None
        if reports_to_username:
            cursor.execute("SELECT id FROM users WHERE username = ?", (reports_to_username,))
            lead_row = cursor.fetchone()
            if lead_row:
                lead_id = lead_row['id']
        if lead_id:
            chain.append(lead_id)
        chain.append(admin_id)
        
    # If the user is a Lead or HR, they only need Admin approval
    elif role in ['Lead', 'HR']:
        chain.append(admin_id)
        
    else:
        # Default fallback
        chain.append(admin_id)
        
    return chain

@app.route('/attendance/request-edit', methods=['POST'])
def attendance_request_edit():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    
    target_date = request.form.get('date', '').strip()
    clock_in_val = request.form.get('clock_in', '').strip()
    clock_out_val = request.form.get('clock_out', '').strip()
    reason = request.form.get('reason', '').strip()
    
    # Optional target user (if Admin)
    target_user_id = request.form.get('user_id', type=int)
    if not target_user_id or session['role'] != 'Admin':
        target_user_id = session['user_id']
        
    if not target_date or not reason:
        flash("Date and Reason are required.", "error")
        return redirect(request.referrer or url_for('attendance_page'))
        
    # Standardize custom time formats
    if clock_in_val and len(clock_in_val.split(':')) == 2:
        clock_in_val += ':00'
    if clock_out_val and len(clock_out_val.split(':')) == 2:
        clock_out_val += ':00'
        
    # Check if user is Admin
    if session['role'] == 'Admin':
        # Admin directly edits attendance table
        status, late_minutes, early_minutes, total_hours, extra_hours = calculate_attendance_metrics(
            db, target_user_id, target_date, clock_in_val, clock_out_val)
            
        cursor.execute("SELECT id FROM attendance WHERE user_id = ? AND date = ?", (target_user_id, target_date))
        att_row = cursor.fetchone()
        
        try:
            if att_row:
                cursor.execute("""
                    UPDATE attendance 
                    SET clock_in = ?, clock_out = ?, status = ?, late_minutes = ?, early_minutes = ?, total_hours = ?, extra_hours = ?
                    WHERE id = ?
                """, (clock_in_val, clock_out_val, status, late_minutes, early_minutes, total_hours, extra_hours, att_row['id']))
            else:
                cursor.execute("""
                    INSERT INTO attendance (user_id, date, clock_in, clock_out, status, late_minutes, early_minutes, total_hours, extra_hours)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (target_user_id, target_date, clock_in_val, clock_out_val, status, late_minutes, early_minutes, total_hours, extra_hours))
                
            cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Admin Edit Attendance', ?)",
                           (session['user_id'], f"Edited attendance of user ID {target_user_id} on {target_date}: In: {clock_in_val}, Out: {clock_out_val} (Reason: {reason})"))
            db.commit()
            flash("Attendance record updated successfully.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error saving attendance: {e}", "error")
    else:
        # Non-admin submits permission request
        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user_info = cursor.fetchone()
        
        # Approximate hours for request
        try:
            in_t = datetime.datetime.strptime(clock_in_val, '%H:%M:%S')
            out_t = datetime.datetime.strptime(clock_out_val, '%H:%M:%S')
            diff_h = max(0.0, (out_t - in_t).total_seconds() / 3600.0)
        except:
            diff_h = 0.0
            
        try:
            cursor.execute("""
                INSERT INTO permission_requests (user_id, date, hours, reason, status, clock_in, clock_out)
                VALUES (?, ?, ?, ?, 'Pending', ?, ?)
            """, (session['user_id'], target_date, diff_h, reason, 'Pending', clock_in_val, clock_out_val))
            pr_id = cursor.lastrowid
            
            chain = get_approval_chain(db, session['user_id'], user_info['role'], user_info['reports_to'])
            
            if not chain:
                # Auto-approve
                cursor.execute("UPDATE permission_requests SET status = 'Approved', approved_by = ? WHERE id = ?",
                               (session['user_id'], pr_id))
                
                # Write to attendance
                status, late_minutes, early_minutes, total_hours, extra_hours = calculate_attendance_metrics(
                    db, session['user_id'], target_date, clock_in_val, clock_out_val)
                
                cursor.execute("SELECT id FROM attendance WHERE user_id = ? AND date = ?", (session['user_id'], target_date))
                att_row = cursor.fetchone()
                if att_row:
                    cursor.execute("""
                        UPDATE attendance 
                        SET clock_in = ?, clock_out = ?, status = ?, late_minutes = ?, early_minutes = ?, total_hours = ?, extra_hours = ?
                        WHERE id = ?
                    """, (clock_in_val, clock_out_val, status, late_minutes, early_minutes, total_hours, extra_hours, att_row['id']))
                else:
                    cursor.execute("""
                        INSERT INTO attendance (user_id, date, clock_in, clock_out, status, late_minutes, early_minutes, total_hours, extra_hours)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (session['user_id'], target_date, clock_in_val, clock_out_val, status, late_minutes, early_minutes, total_hours, extra_hours))
                
                cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Permission Request', ?)",
                               (session['user_id'], f"Attendance request auto-approved for {target_date}: In: {clock_in_val}, Out: {clock_out_val}."))
                db.commit()
                flash("Attendance adjustment request auto-approved!", "success")
            else:
                import json as _json_local
                chain_json = _json_local.dumps(chain)
                details_str = f"Attendance Adjustment: In: {clock_in_val}, Out: {clock_out_val} on {target_date}. Reason: {reason}"
                cursor.execute("""
                    INSERT INTO approvals (requester_id, type, reference_id, approval_chain, current_index, details, status)
                    VALUES (?, 'Permission', ?, ?, 0, ?, 'Pending')
                """, (session['user_id'], pr_id, chain_json, details_str))
                cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Permission Request', ?)",
                               (session['user_id'], details_str))
                _push_notification(db, chain[0], "Pending Approval Waiting", f"Attendance adjustment request from {session['name']} needs your approval.", "approval", link=url_for('permissions_page'))
                db.commit()
                flash("Attendance adjustment request submitted — pending approval.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error submitting request: {e}", "error")
            
    return redirect(request.referrer or url_for('attendance_page'))

@app.route('/leaves', methods=['GET', 'POST'])
def leaves_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'Admin':
        return redirect(url_for('system_approvals_page'))
        
    db = get_db()
    cursor = db.cursor()
    
    # 1. HANDLE POST (APPLY LEAVE)
    if request.method == 'POST':
        if session['role'] == 'Admin':
            flash("Admin accounts do not submit leave requests.", "error")
            return redirect(url_for('leaves_page'))
        start_date_str = request.form.get('start_date', '').strip()
        end_date_str = request.form.get('end_date', '').strip()
        reason = request.form.get('reason', '').strip()
        
        if not start_date_str or not end_date_str or not reason:
            flash("All fields are required to apply for leave.", "error")
            return redirect(url_for('leaves_page'))
            
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Use YYYY-MM-DD.", "error")
            return redirect(url_for('leaves_page'))
            
        if start_date > end_date:
            flash("Start date cannot be after end date.", "error")
            return redirect(url_for('leaves_page'))
            
        # Calculate requested days
        requested_days = (end_date - start_date).days + 1
        
        # Get user profile for limits check
        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user_info = cursor.fetchone()
        
        # Calculate Approved Used Days in the current year
        current_year = start_date.year
        year_start = f"{current_year}-01-01"
        year_end = f"{current_year}-12-31"
        
        cursor.execute("""
            SELECT start_date, end_date FROM leaves
            WHERE user_id = ? AND status = 'Approved'
              AND NOT (end_date < ? OR start_date > ?)
        """, (session['user_id'], year_start, year_end))
        approved_leaves = cursor.fetchall()
        
        approved_used = 0
        for lv in approved_leaves:
            lv_start = datetime.datetime.strptime(lv['start_date'], '%Y-%m-%d').date()
            lv_end = datetime.datetime.strptime(lv['end_date'], '%Y-%m-%d').date()
            intersect_start = max(lv_start, datetime.date(current_year, 1, 1))
            intersect_end = min(lv_end, datetime.date(current_year, 12, 31))
            approved_used += (intersect_end - intersect_start).days + 1
            
        allowed_leaves = 18.0 + float(user_info['carry_forward'] or 0.0)
        remaining_balance = allowed_leaves - approved_used
        
        if requested_days > remaining_balance:
            flash(f"Insufficient leave balance. Requested: {requested_days} days, Remaining: {remaining_balance:.1f} days.", "error")
            return redirect(url_for('leaves_page'))
            
        # Monthly limit check: max 2 leaves per month (spanned months count)
        spanned_months = {}
        curr_day = start_date
        while curr_day <= end_date:
            month_key = curr_day.strftime('%Y-%m')
            spanned_months[month_key] = spanned_months.get(month_key, 0) + 1
            curr_day += datetime.timedelta(days=1)
            
        # Check limit for each month in spanned_months
        for m_key, days_in_req_month in spanned_months.items():
            month_start_str = f"{m_key}-01"
            y, m = map(int, m_key.split('-'))
            last_day = calendar.monthrange(y, m)[1]
            month_end_str = f"{m_key}-{last_day:02d}"
            
            cursor.execute("""
                SELECT start_date, end_date FROM leaves
                WHERE user_id = ? AND status = 'Approved'
                  AND NOT (end_date < ? OR start_date > ?)
            """, (session['user_id'], month_start_str, month_end_str))
            month_approved_leaves = cursor.fetchall()
            
            month_approved_days = 0
            for lv in month_approved_leaves:
                lv_start = datetime.datetime.strptime(lv['start_date'], '%Y-%m-%d').date()
                lv_end = datetime.datetime.strptime(lv['end_date'], '%Y-%m-%d').date()
                intersect_start = max(lv_start, datetime.date(y, m, 1))
                intersect_end = min(lv_end, datetime.date(y, m, last_day))
                month_approved_days += (intersect_end - intersect_start).days + 1
                
            if month_approved_days + days_in_req_month > 2:
                flash(f"Leave policy violation: Leaves in {y}-{m:02d} exceed the monthly limit of 2 days. (Approved in month: {month_approved_days} days, Requested in month: {days_in_req_month} days)", "error")
                return redirect(url_for('leaves_page'))
                
        # If all checks pass, insert leave request and approval chain
        try:
            cursor.execute("""
                INSERT INTO leaves (user_id, start_date, end_date, leave_type, reason, status)
                VALUES (?, ?, ?, 'General', ?, 'Pending')
            """, (session['user_id'], start_date_str, end_date_str, reason))
            leave_id = cursor.lastrowid
            
            chain = get_approval_chain(db, session['user_id'], user_info['role'], user_info['reports_to'])
            
            if not chain:
                cursor.execute("UPDATE leaves SET status = 'Approved' WHERE id = ?", (leave_id,))
                cursor.execute("""
                    INSERT INTO activity_log (user_id, action, details)
                    VALUES (?, 'Leave Request', ?)
                """, (session['user_id'], f"Leave applied from {start_date_str} to {end_date_str} (Auto-Approved)."))
                db.commit()
                flash("Leave request submitted and auto-approved successfully!", "success")
            else:
                import json
                chain_json = json.dumps(chain)
                details_str = f"Leave Request from {start_date_str} to {end_date_str} ({requested_days} days). Reason: {reason}"
                
                cursor.execute("""
                    INSERT INTO approvals (requester_id, type, reference_id, approval_chain, current_index, details, status)
                    VALUES (?, 'Leave', ?, ?, 0, ?, 'Pending')
                """, (session['user_id'], leave_id, chain_json, details_str))
                
                cursor.execute("""
                    INSERT INTO activity_log (user_id, action, details)
                    VALUES (?, 'Leave Request', ?)
                """, (session['user_id'], f"Leave applied from {start_date_str} to {end_date_str} ({requested_days} days) - Pending approval chain {chain_json}"))
                
                _push_notification(db, chain[0], "Pending Approval Waiting", f"Leave request from {session['name']} needs your approval.", "approval", link=url_for('leaves_page'))
                db.commit()
                flash("Leave request submitted successfully, pending approval chain.", "success")
                
        except Exception as e:
            db.rollback()
            flash(f"Error submitting leave request: {e}", "error")
            
        return redirect(url_for('leaves_page'))
        
    # 2. HANDLE GET
    my_permissions = []
    comp_rows = []
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()
    
    current_year = datetime.date.today().year
    year_start = f"{current_year}-01-01"
    year_end = f"{current_year}-12-31"
    
    cursor.execute("""
        SELECT start_date, end_date FROM leaves
        WHERE user_id = ? AND status = 'Approved'
          AND NOT (end_date < ? OR start_date > ?)
    """, (session['user_id'], year_start, year_end))
    approved_leaves = cursor.fetchall()
    
    approved_used = 0
    for lv in approved_leaves:
        lv_start = datetime.datetime.strptime(lv['start_date'], '%Y-%m-%d').date()
        lv_end = datetime.datetime.strptime(lv['end_date'], '%Y-%m-%d').date()
        intersect_start = max(lv_start, datetime.date(current_year, 1, 1))
        intersect_end = min(lv_end, datetime.date(current_year, 12, 31))
        approved_used += (intersect_end - intersect_start).days + 1
        
    allowed_leaves = 18.0 + float(user_info['carry_forward'] or 0.0)
    remaining_balance = allowed_leaves - approved_used
    
    cursor.execute("""
        SELECT l.*, a.id as approval_id, a.approval_chain, a.current_index, a.status as approval_status
        FROM leaves l
        LEFT JOIN approvals a ON (l.id = a.reference_id AND a.type = 'Leave')
        WHERE l.user_id = ?
        ORDER BY l.start_date DESC
    """, (session['user_id'],))
    my_leaves_raw = cursor.fetchall()
    
    my_leaves = []
    import json
    for row in my_leaves_raw:
        step_info = ""
        total_days = (datetime.datetime.strptime(row['end_date'], '%Y-%m-%d').date() - datetime.datetime.strptime(row['start_date'], '%Y-%m-%d').date()).days + 1
        
        if row['status'] == 'Pending' and row['approval_chain']:
            try:
                chain = json.loads(row['approval_chain'])
                curr_idx = row['current_index']
                if curr_idx < len(chain):
                    cursor.execute("SELECT name, role FROM users WHERE id = ?", (chain[curr_idx],))
                    active_approver = cursor.fetchone()
                    if active_approver:
                        step_info = f"Pending: {active_approver['name']} ({active_approver['role']}) - Step {curr_idx + 1} of {len(chain)}"
            except Exception as e:
                step_info = "Pending in chain"
        elif row['status'] == 'Approved':
            step_info = "Approved"
        elif row['status'] == 'Rejected':
            step_info = "Rejected"
            
        my_leaves.append({
            'id': row['id'],
            'start_date': row['start_date'],
            'end_date': row['end_date'],
            'reason': row['reason'],
            'status': row['status'],
            'total_days': total_days,
            'step_info': step_info
        })
        
    cursor.execute("""
        SELECT a.id as approval_id, a.requester_id, a.type, a.reference_id, a.approval_chain, a.current_index, a.details, a.status as approval_status,
               u.name as requester_name, u.role as requester_role, u.team as requester_team
        FROM approvals a
        JOIN users u ON a.requester_id = u.id
        WHERE a.status = 'Pending'
        ORDER BY a.id ASC
    """)
    all_pending_approvals = cursor.fetchall()
    
    my_pending_approvals = []
    for app_row in all_pending_approvals:
        try:
            chain = json.loads(app_row['approval_chain'])
            curr_idx = app_row['current_index']
            if curr_idx < len(chain) and chain[curr_idx] == session['user_id']:
                my_pending_approvals.append({
                    'id': app_row['approval_id'],
                    'requester_name': app_row['requester_name'],
                    'requester_role': app_row['requester_role'],
                    'requester_team': app_row['requester_team'],
                    'type': app_row['type'],
                    'details': app_row['details'],
                    'step_info': f"Step {curr_idx + 1} of {len(chain)}"
                })
        except Exception as e:
            pass
    if session['role'] in ['Artist', 'Lead', 'HR']:
        import json
        # Fetch Artist's own permissions requests
        cursor.execute("""
            SELECT pr.*, a.id as approval_id, a.approval_chain, a.current_index, a.status as approval_status
            FROM permission_requests pr
            LEFT JOIN approvals a ON (pr.id = a.reference_id AND a.type = 'Permission')
            WHERE pr.user_id = ?
            ORDER BY pr.date DESC, pr.id DESC
        """, (session['user_id'],))
        my_perm_raw = cursor.fetchall()
        for row in my_perm_raw:
            step_info = ""
            if row['status'] == 'Pending' and row['approval_chain']:
                try:
                    chain = json.loads(row['approval_chain'])
                    idx = row['current_index']
                    if idx < len(chain):
                        cursor.execute("SELECT name, role FROM users WHERE id = ?", (chain[idx],))
                        approver = cursor.fetchone()
                        if approver:
                            step_info = f"Awaiting: {approver['name']} ({approver['role']}) — Step {idx+1}/{len(chain)}"
                except Exception:
                    step_info = "Pending in chain"
            elif row['status'] == 'Approved':
                step_info = "Approved"
            elif row['status'] == 'Rejected':
                step_info = "Rejected"

            my_permissions.append({
                'id': row['id'],
                'date': row['date'],
                'hours': row['hours'],
                'reason': row['reason'],
                'status': row['status'],
                'step_info': step_info,
            })
            
        # Fetch Artist's own compensation row
        all_comp = _comp_summary(db)
        comp_rows = [r for r in all_comp if r['uid'] == session['user_id']]

    return render_template(
        'leaves.html',
        user=user_info,
        allowed_leaves=allowed_leaves,
        approved_used=approved_used,
        remaining_balance=remaining_balance,
        my_leaves=my_leaves,
        my_pending_approvals=my_pending_approvals,
        my_permissions=my_permissions,
        comp_rows=comp_rows,
        today_str=datetime.date.today().strftime('%Y-%m-%d')
    )

@app.route('/leaves/approve/<int:approval_id>', methods=['POST'])
def approve_leave(approval_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'HR':
        flash("HR is not authorized to approve leaves.", "error")
        return redirect(request.referrer or url_for('leaves_page'))
        
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM approvals WHERE id = ? AND status = 'Pending'", (approval_id,))
    approval = cursor.fetchone()
    
    if not approval:
        flash("Approval request not found or already actioned.", "error")
        return redirect(request.referrer or url_for('leaves_page'))
        
    import json
    try:
        chain = json.loads(approval['approval_chain'])
        curr_idx = approval['current_index']
    except Exception as e:
        flash("Invalid approval request data.", "error")
        return redirect(request.referrer or url_for('leaves_page'))
        
    if curr_idx >= len(chain) or chain[curr_idx] != session['user_id']:
        flash("Unauthorized to approve this step.", "error")
        return redirect(request.referrer or url_for('leaves_page'))
        
    next_idx = curr_idx + 1
    
    try:
        if next_idx >= len(chain):
            cursor.execute("""
                UPDATE approvals 
                SET status = 'Approved', current_index = ?, actioned_by = ?, actioned_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (next_idx, session['user_id'], approval_id))
            
            if approval['type'] == 'Leave':
                cursor.execute("""
                    UPDATE leaves
                    SET status = 'Approved', approved_by = ?
                    WHERE id = ?
                """, (session['user_id'], approval['reference_id']))
                _push_notification(db, approval['requester_id'], "Leave Approved", f"Your leave request has been approved.", "leave", link=url_for('leaves_page'))
                
            cursor.execute("""
                INSERT INTO activity_log (user_id, action, details)
                VALUES (?, 'Approve Request', ?)
            """, (session['user_id'], f"Approved {approval['type']} ID {approval['reference_id']} (Final step approved)."))
            
            flash("Request approved and finalized successfully!", "success")
        else:
            cursor.execute("""
                UPDATE approvals
                SET current_index = ?
                WHERE id = ?
            """, (next_idx, approval_id))
            
            cursor.execute("""
                INSERT INTO activity_log (user_id, action, details)
                VALUES (?, 'Approve Request', ?)
            """, (session['user_id'], f"Approved {approval['type']} ID {approval['reference_id']} (Advanced to step {next_idx + 1})."))
            
            _push_notification(db, chain[next_idx], "Pending Approval Waiting", f"Leave request needs your approval.", "approval", link=url_for('leaves_page'))
            flash("Request approved and advanced to next step in the chain.", "success")
            
        db.commit()
    except Exception as e:
        db.rollback()
        flash(f"Error actioning approval: {e}", "error")
        
    return redirect(request.referrer or url_for('leaves_page'))

@app.route('/leaves/reject/<int:approval_id>', methods=['POST'])
def reject_leave(approval_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'HR':
        flash("HR is not authorized to reject leaves.", "error")
        return redirect(request.referrer or url_for('leaves_page'))
        
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM approvals WHERE id = ? AND status = 'Pending'", (approval_id,))
    approval = cursor.fetchone()
    
    if not approval:
        flash("Approval request not found or already actioned.", "error")
        return redirect(request.referrer or url_for('leaves_page'))
        
    import json
    try:
        chain = json.loads(approval['approval_chain'])
        curr_idx = approval['current_index']
    except Exception as e:
        flash("Invalid approval request data.", "error")
        return redirect(request.referrer or url_for('leaves_page'))
        
    if curr_idx >= len(chain) or chain[curr_idx] != session['user_id']:
        flash("Unauthorized to reject this step.", "error")
        return redirect(request.referrer or url_for('leaves_page'))
        
    try:
        cursor.execute("""
            UPDATE approvals 
            SET status = 'Rejected', actioned_by = ?, actioned_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (session['user_id'], approval_id))
        
        if approval['type'] == 'Leave':
            cursor.execute("""
                UPDATE leaves
                SET status = 'Rejected'
                WHERE id = ?
            """, (approval['reference_id'],))
            _push_notification(db, approval['requester_id'], "Leave Rejected", f"Your leave request has been rejected.", "leave", link=url_for('leaves_page'))
            
        cursor.execute("""
            INSERT INTO activity_log (user_id, action, details)
            VALUES (?, 'Reject Request', ?)
        """, (session['user_id'], f"Rejected {approval['type']} ID {approval['reference_id']} (Chain terminated)."))
        
        db.commit()
        flash("Request rejected and chain terminated.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error rejecting request: {e}", "error")
        
    return redirect(request.referrer or url_for('leaves_page'))

# ─────────────────────────────────────────────────────────────
# LAYER 6: PERMISSIONS + COMPENSATION
# ─────────────────────────────────────────────────────────────

import json as _json

def _comp_summary(db, selected_month=None):
    """Return compensation summary for all employees (used by /compensation)."""
    cursor = db.cursor()
    cursor.execute("SELECT id, name, username, role, team FROM users ORDER BY team, name")
    all_users = cursor.fetchall()

    rows = []
    for u in all_users:
        uid = u['id']

        if selected_month:
            # 1. Approved permission hours
            cursor.execute("""
                SELECT COALESCE(SUM(hours), 0) FROM permission_requests
                WHERE user_id = ? AND status = 'Approved' AND strftime('%Y-%m', date) = ?
            """, (uid, selected_month))
            perm_hours = cursor.fetchone()[0] or 0.0

            # 2. Late minutes -> hours
            cursor.execute("""
                SELECT COALESCE(SUM(late_minutes), 0) FROM attendance
                WHERE user_id = ? AND late_minutes > 0 AND strftime('%Y-%m', date) = ?
            """, (uid, selected_month))
            late_mins_total = cursor.fetchone()[0] or 0
            late_hours = late_mins_total / 60.0

            # 4. Extra hours banked
            cursor.execute("""
                SELECT COALESCE(SUM(extra_hours), 0) FROM attendance
                WHERE user_id = ? AND extra_hours > 0 AND strftime('%Y-%m', date) = ?
            """, (uid, selected_month))
            total_extra = cursor.fetchone()[0] or 0.0
        else:
            # 1. Approved permission hours (formal excused absences they owe back)
            cursor.execute("""
                SELECT COALESCE(SUM(hours), 0) FROM permission_requests
                WHERE user_id = ? AND status = 'Approved'
            """, (uid,))
            perm_hours = cursor.fetchone()[0] or 0.0

            # 2. Late minutes -> hours (unexcused lateness beyond grace)
            cursor.execute("""
                SELECT COALESCE(SUM(late_minutes), 0) FROM attendance
                WHERE user_id = ? AND late_minutes > 0
            """, (uid,))
            late_mins_total = cursor.fetchone()[0] or 0
            late_hours = late_mins_total / 60.0

            # 4. Extra hours banked (off-day / overtime)
            cursor.execute("""
                SELECT COALESCE(SUM(extra_hours), 0) FROM attendance
                WHERE user_id = ? AND extra_hours > 0
            """, (uid,))
            total_extra = cursor.fetchone()[0] or 0.0

        # 3. Total owed
        total_owed = perm_hours + late_hours

        # 5. Net owed after offset
        net_owed = max(0.0, total_owed - total_extra)

        rows.append({
            'uid': uid,
            'name': u['name'],
            'username': u['username'],
            'role': u['role'],
            'team': u['team'],
            'perm_hours': round(perm_hours, 2),
            'late_hours': round(late_hours, 2),
            'total_owed': round(total_owed, 2),
            'total_extra': round(total_extra, 2),
            'net_owed': round(net_owed, 2),
        })
    return rows


@app.route('/permissions', methods=['GET', 'POST'])
def permissions_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()

    # ── POST: apply for a permission ──
    if request.method == 'POST':
        perm_date  = request.form.get('perm_date', '').strip()
        hours_str  = request.form.get('hours', '').strip()
        reason     = request.form.get('reason', '').strip()

        if not perm_date or not hours_str or not reason:
            flash("All fields are required.", "error")
            return redirect(url_for('permissions_page'))

        try:
            perm_hours = float(hours_str)
            if perm_hours <= 0 or perm_hours > 24:
                raise ValueError
        except ValueError:
            flash("Hours must be a positive number up to 24.", "error")
            return redirect(url_for('permissions_page'))

        try:
            datetime.datetime.strptime(perm_date, '%Y-%m-%d')
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for('permissions_page'))

        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user_info = cursor.fetchone()

        try:
            cursor.execute("""
                INSERT INTO permission_requests (user_id, date, hours, reason, status)
                VALUES (?, ?, ?, ?, 'Pending')
            """, (session['user_id'], perm_date, perm_hours, reason))
            pr_id = cursor.lastrowid

            chain = get_approval_chain(db, session['user_id'], user_info['role'], user_info['reports_to'])

            if not chain:
                # Admin requesting — auto-approve
                cursor.execute("UPDATE permission_requests SET status = 'Approved', approved_by = ? WHERE id = ?",
                               (session['user_id'], pr_id))
                cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Permission Request', ?)",
                               (session['user_id'], f"Permission auto-approved: {perm_hours}h on {perm_date}."))
                db.commit()
                flash("Permission request auto-approved!", "success")
            else:
                chain_json = _json.dumps(chain)
                details_str = f"Permission Request: {perm_hours}h on {perm_date}. Reason: {reason}"
                cursor.execute("""
                    INSERT INTO approvals (requester_id, type, reference_id, approval_chain, current_index, details, status)
                    VALUES (?, 'Permission', ?, ?, 0, ?, 'Pending')
                """, (session['user_id'], pr_id, chain_json, details_str))
                cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Permission Request', ?)",
                               (session['user_id'], details_str))
                _push_notification(db, chain[0], "Pending Approval Waiting", f"Permission request from {session['name']} needs your approval.", "approval", link=url_for('permissions_page'))
                db.commit()
                flash("Permission request submitted — pending approval chain.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error submitting permission request: {e}", "error")

        return redirect(url_for('permissions_page'))

    # ── GET ──
    if session['role'] in ['Artist', 'Lead', 'HR']:
        return redirect(url_for('leaves_page'))
    if session['role'] == 'Admin':
        return redirect(url_for('system_approvals_page'))
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()

    # My permission requests with approval chain step info
    cursor.execute("""
        SELECT pr.*, a.id as approval_id, a.approval_chain, a.current_index, a.status as approval_status
        FROM permission_requests pr
        LEFT JOIN approvals a ON (pr.id = a.reference_id AND a.type = 'Permission')
        WHERE pr.user_id = ?
        ORDER BY pr.date DESC, pr.id DESC
    """, (session['user_id'],))
    my_perm_raw = cursor.fetchall()

    my_permissions = []
    for row in my_perm_raw:
        step_info = ""
        if row['status'] == 'Pending' and row['approval_chain']:
            try:
                chain = _json.loads(row['approval_chain'])
                idx = row['current_index']
                if idx < len(chain):
                    cursor.execute("SELECT name, role FROM users WHERE id = ?", (chain[idx],))
                    approver = cursor.fetchone()
                    if approver:
                        step_info = f"Awaiting: {approver['name']} ({approver['role']}) — Step {idx+1}/{len(chain)}"
            except Exception:
                step_info = "Pending in chain"
        elif row['status'] == 'Approved':
            step_info = "Approved"
        elif row['status'] == 'Rejected':
            step_info = "Rejected"

        my_permissions.append({
            'id': row['id'],
            'date': row['date'],
            'hours': row['hours'],
            'reason': row['reason'],
            'status': row['status'],
            'step_info': step_info,
        })

    # Pending approvals where this user is the current approver
    cursor.execute("""
        SELECT a.id as approval_id, a.requester_id, a.type, a.reference_id,
               a.approval_chain, a.current_index, a.details, a.status as approval_status,
               u.name as requester_name, u.role as requester_role, u.team as requester_team
        FROM approvals a
        JOIN users u ON a.requester_id = u.id
        WHERE a.status = 'Pending' AND a.type = 'Permission'
        ORDER BY a.id ASC
    """)
    all_perm_approvals = cursor.fetchall()

    my_pending_approvals = []
    for app_row in all_perm_approvals:
        try:
            chain = _json.loads(app_row['approval_chain'])
            idx = app_row['current_index']
            if idx < len(chain) and chain[idx] == session['user_id']:
                my_pending_approvals.append({
                    'id': app_row['approval_id'],
                    'requester_name': app_row['requester_name'],
                    'requester_role': app_row['requester_role'],
                    'requester_team': app_row['requester_team'],
                    'type': app_row['type'],
                    'details': app_row['details'],
                    'step_info': f"Step {idx+1} of {len(chain)}",
                })
        except Exception:
            pass

    today_str = datetime.date.today().strftime('%Y-%m-%d')
    return render_template(
        'permissions.html',
        user=user_info,
        my_permissions=my_permissions,
        my_pending_approvals=my_pending_approvals,
        today_str=today_str,
    )


@app.route('/permissions/approve/<int:approval_id>', methods=['POST'])
def approve_permission(approval_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'HR':
        flash("HR is not authorized to approve permissions.", "error")
        return redirect(request.referrer or url_for('permissions_page'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM approvals WHERE id = ? AND status = 'Pending' AND type = 'Permission'", (approval_id,))
    approval = cursor.fetchone()

    if not approval:
        flash("Approval request not found or already actioned.", "error")
        return redirect(request.referrer or url_for('permissions_page'))

    try:
        chain = _json.loads(approval['approval_chain'])
        curr_idx = approval['current_index']
    except Exception:
        flash("Invalid approval data.", "error")
        return redirect(request.referrer or url_for('permissions_page'))

    if curr_idx >= len(chain) or chain[curr_idx] != session['user_id']:
        flash("Unauthorized to approve this step.", "error")
        return redirect(request.referrer or url_for('permissions_page'))

    next_idx = curr_idx + 1
    try:
        if next_idx >= len(chain):
            # Final step — fully approved
            cursor.execute("""
                UPDATE approvals SET status = 'Approved', current_index = ?, actioned_by = ?, actioned_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (next_idx, session['user_id'], approval_id))
            cursor.execute("""
                UPDATE permission_requests SET status = 'Approved', approved_by = ? WHERE id = ?
            """, (session['user_id'], approval['reference_id']))
            
            # Fetch the permission request details to see if this is an attendance adjustment
            cursor.execute("SELECT * FROM permission_requests WHERE id = ?", (approval['reference_id'],))
            pr_req = cursor.fetchone()
            if pr_req and 'clock_in' in pr_req.keys() and 'clock_out' in pr_req.keys() and pr_req['clock_in'] and pr_req['clock_out']:
                clock_in_val = pr_req['clock_in']
                clock_out_val = pr_req['clock_out']
                target_date = pr_req['date']
                target_user_id = pr_req['user_id']
                
                status, late_minutes, early_minutes, total_hours, extra_hours = calculate_attendance_metrics(
                    db, target_user_id, target_date, clock_in_val, clock_out_val)
                
                cursor.execute("SELECT id FROM attendance WHERE user_id = ? AND date = ?", (target_user_id, target_date))
                att_row = cursor.fetchone()
                if att_row:
                    cursor.execute("""
                        UPDATE attendance 
                        SET clock_in = ?, clock_out = ?, status = ?, late_minutes = ?, early_minutes = ?, total_hours = ?, extra_hours = ?
                        WHERE id = ?
                    """, (clock_in_val, clock_out_val, status, late_minutes, early_minutes, total_hours, extra_hours, att_row['id']))
                else:
                    cursor.execute("""
                        INSERT INTO attendance (user_id, date, clock_in, clock_out, status, late_minutes, early_minutes, total_hours, extra_hours)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (target_user_id, target_date, clock_in_val, clock_out_val, status, late_minutes, early_minutes, total_hours, extra_hours))
            
            cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Approve Permission', ?)",
                           (session['user_id'], f"Approved Permission ID {approval['reference_id']} (Final)."))
            _push_notification(db, approval['requester_id'], "Permission Approved", f"Your permission request has been approved.", "approval", link=url_for('permissions_page'))
            flash("Permission approved and finalized!", "success")
        else:
            cursor.execute("UPDATE approvals SET current_index = ? WHERE id = ?", (next_idx, approval_id))
            cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Approve Permission', ?)",
                           (session['user_id'], f"Approved Permission ID {approval['reference_id']} — advanced to step {next_idx+1}."))
            _push_notification(db, chain[next_idx], "Pending Approval Waiting", f"Permission request needs your approval.", "approval", link=url_for('permissions_page'))
            flash("Permission approved — advanced to next step in chain.", "success")
        db.commit()
    except Exception as e:
        db.rollback()
        flash(f"Error approving permission: {e}", "error")

    return redirect(request.referrer or url_for('permissions_page'))


@app.route('/permissions/reject/<int:approval_id>', methods=['POST'])
def reject_permission(approval_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'HR':
        flash("HR is not authorized to reject permissions.", "error")
        return redirect(request.referrer or url_for('permissions_page'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM approvals WHERE id = ? AND status = 'Pending' AND type = 'Permission'", (approval_id,))
    approval = cursor.fetchone()

    if not approval:
        flash("Approval request not found or already actioned.", "error")
        return redirect(request.referrer or url_for('permissions_page'))

    try:
        chain = _json.loads(approval['approval_chain'])
        curr_idx = approval['current_index']
    except Exception:
        flash("Invalid approval data.", "error")
        return redirect(request.referrer or url_for('permissions_page'))

    if curr_idx >= len(chain) or chain[curr_idx] != session['user_id']:
        flash("Unauthorized to reject this step.", "error")
        return redirect(request.referrer or url_for('permissions_page'))

    try:
        cursor.execute("""
            UPDATE approvals SET status = 'Rejected', actioned_by = ?, actioned_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (session['user_id'], approval_id))
        cursor.execute("UPDATE permission_requests SET status = 'Rejected' WHERE id = ?", (approval['reference_id'],))
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Reject Permission', ?)",
                       (session['user_id'], f"Rejected Permission ID {approval['reference_id']} — chain terminated."))
        _push_notification(db, approval['requester_id'], "Permission Rejected", f"Your permission request has been rejected.", "approval", link=url_for('permissions_page'))
        db.commit()
        flash("Permission request rejected.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error rejecting permission: {e}", "error")

    return redirect(request.referrer or url_for('permissions_page'))


@app.route('/compensation')
def compensation_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] in ['Artist', 'Lead', 'HR']:
        return redirect(url_for('leaves_page'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()

    selected_month = request.args.get('month', '')
    import re
    if selected_month and not re.match(r'^\d{4}-\d{2}$', selected_month):
        selected_month = ''

    all_rows = _comp_summary(db, selected_month=selected_month if selected_month else None)

    # Filter rows based on role
    if session['role'] == 'Lead':
        all_rows = [r for r in all_rows if r['team'] == session['team']]
    elif session['role'] == 'Artist':
        all_rows = [r for r in all_rows if r['uid'] == session['user_id']]

    # Gather unique teams for the filter dropdown
    teams = sorted(set(r['team'] for r in all_rows))
    filter_team = request.args.get('team', '')
    if filter_team:
        all_rows = [r for r in all_rows if r['team'] == filter_team]

    today_str = datetime.date.today().strftime('%Y-%m-%d')
    return render_template(
        'compensation.html',
        user=user_info,
        comp_rows=all_rows,
        teams=teams,
        filter_team=filter_team,
        selected_month=selected_month,
        today_str=today_str,
    )


@app.route('/team-approvals')
def team_approvals_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] not in ['Lead', 'Admin']:
        flash("Unauthorized to access Team Approvals.", "error")
        return redirect(url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()

    cursor.execute("""
        SELECT a.id as approval_id, a.requester_id, a.type, a.reference_id, a.approval_chain, a.current_index, a.details, a.status as approval_status,
               u.name as requester_name, u.role as requester_role, u.team as requester_team
        FROM approvals a
        JOIN users u ON a.requester_id = u.id
        WHERE a.status = 'Pending'
        ORDER BY a.id ASC
    """)
    all_pending_approvals = cursor.fetchall()

    my_pending_leaves = []
    my_pending_permissions = []
    
    import json
    for app_row in all_pending_approvals:
        try:
            chain = json.loads(app_row['approval_chain'])
            curr_idx = app_row['current_index']
            if curr_idx < len(chain) and chain[curr_idx] == session['user_id']:
                item = {
                    'id': app_row['approval_id'],
                    'requester_name': app_row['requester_name'],
                    'requester_role': app_row['requester_role'],
                    'requester_team': app_row['requester_team'],
                    'type': app_row['type'],
                    'details': app_row['details'],
                    'step_info': f"Step {curr_idx + 1} of {len(chain)}"
                }
                if app_row['type'] == 'Leave':
                    my_pending_leaves.append(item)
                elif app_row['type'] == 'Permission':
                    my_pending_permissions.append(item)
        except Exception:
            pass

    return render_template(
        'team_approvals.html',
        user=user_info,
        my_pending_leaves=my_pending_leaves,
        my_pending_permissions=my_pending_permissions
    )


@app.route('/system-approvals')
def system_approvals_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] != 'Admin':
        flash("Access restricted to Admin.", "error")
        return redirect(url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()

    # Get user profile
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()

    # Query all pending approvals
    cursor.execute("""
        SELECT a.id as approval_id, a.requester_id, a.type, a.reference_id, a.approval_chain, a.current_index, a.details, a.status as approval_status,
               u.name as requester_name, u.role as requester_role, u.team as requester_team
        FROM approvals a
        JOIN users u ON a.requester_id = u.id
        WHERE a.status = 'Pending'
        ORDER BY a.id ASC
    """)
    all_pending_approvals = cursor.fetchall()

    import json
    my_pending_leaves = []
    my_pending_permissions = []

    for app_row in all_pending_approvals:
        try:
            chain = json.loads(app_row['approval_chain'])
            curr_idx = app_row['current_index']
            if curr_idx < len(chain) and chain[curr_idx] == session['user_id']:
                item = {
                    'id': app_row['approval_id'],
                    'requester_name': app_row['requester_name'],
                    'requester_role': app_row['requester_role'],
                    'requester_team': app_row['requester_team'],
                    'type': app_row['type'],
                    'details': app_row['details'],
                    'step_info': f"Step {curr_idx + 1} of {len(chain)}"
                }
                if app_row['type'] == 'Leave':
                    my_pending_leaves.append(item)
                elif app_row['type'] == 'Permission':
                    my_pending_permissions.append(item)
        except Exception:
            pass

    return render_template(
        'system_approvals.html',
        user=user_info,
        my_pending_leaves=my_pending_leaves,
        my_pending_permissions=my_pending_permissions
    )


@app.route('/attendance/api/calendar/<int:employee_id>')
def attendance_calendar_api(employee_id):
    from flask import jsonify
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if session['role'] not in ['Admin', 'HR', 'Lead']:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (employee_id,))
    target_user = cursor.fetchone()
    if not target_user:
        return jsonify({'error': 'Employee not found'}), 404

    # Lead can only inspect their team
    if session['role'] == 'Lead' and target_user['team'] != session['team']:
        return jsonify({'error': 'Unauthorized'}), 403

    year = request.args.get('year', default=datetime.date.today().year, type=int)
    month = request.args.get('month', default=datetime.date.today().month, type=int)

    month_prefix = f"{year}-{month:02d}"
    first_weekday, num_days = calendar.monthrange(year, month)

    cursor.execute("""
        SELECT * FROM attendance 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
    """, (employee_id, month_prefix))
    att_list = {row['date']: dict(row) for row in cursor.fetchall()}

    cursor.execute("""
        SELECT * FROM leaves 
        WHERE user_id = ? AND status = 'Approved' 
          AND (strftime('%Y-%m', start_date) = ? OR strftime('%Y-%m', end_date) = ?)
    """, (employee_id, month_prefix, month_prefix))
    leaves_list = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM holidays WHERE strftime('%Y-%m', date) = ?", (month_prefix,))
    holidays_list = {row['date']: row['name'] for row in cursor.fetchall()}

    calendar_days = []
    # Padding cells before first day of month
    for p in range(first_weekday):
        calendar_days.append({'type': 'padding'})

    today_date = datetime.date.today()
    for day in range(1, num_days + 1):
        day_date = datetime.date(year, month, day)
        day_str = day_date.strftime('%Y-%m-%d')

        status = 'Future'
        clock_in = None
        clock_out = None
        late_minutes = 0
        extra_hours = 0.0
        label = ""

        if day_str in att_list:
            status = att_list[day_str]['status']
            clock_in = att_list[day_str]['clock_in']
            clock_out = att_list[day_str]['clock_out']
            late_minutes = att_list[day_str]['late_minutes']
            extra_hours = att_list[day_str]['extra_hours']
        else:
            is_leave = False
            for leave in leaves_list:
                s_date = datetime.datetime.strptime(leave['start_date'], '%Y-%m-%d').date()
                e_date = datetime.datetime.strptime(leave['end_date'], '%Y-%m-%d').date()
                if s_date <= day_date <= e_date:
                    is_leave = True
                    break

            if is_leave:
                status = 'Leave'
            elif is_weekly_off(day_date):
                status = 'Off'
            elif day_str in holidays_list:
                status = 'Holiday'
                label = holidays_list[day_str]
            else:
                if day_date > today_date:
                    status = 'Future'
                elif day_date == today_date:
                    status = 'Absent'
                else:
                    status = 'Absent'

        calendar_days.append({
            'type': 'day',
            'day': day,
            'date': day_str,
            'status': status,
            'clock_in': clock_in,
            'clock_out': clock_out,
            'late_minutes': late_minutes,
            'extra_hours': extra_hours,
            'label': label
        })

    # Calculate stats summary for modal / API
    stats = {
        'present': 0, 'late': 0, 'half': 0, 'absent': 0, 'leave': 0,
        'off': 0, 'holiday': 0, 'extra_hours': 0.0, 'late_minutes': 0,
        'early_minutes': 0, 'net_pending': 0
    }
    for cd in calendar_days:
        if cd.get('type') == 'day':
            st = cd.get('status')
            if st == 'Present': stats['present'] += 1
            elif st == 'Late':
                stats['late'] += 1
                stats['late_minutes'] += cd.get('late_minutes') or 0
            elif st == 'Half Day': stats['half'] += 1
            elif st == 'Absent': stats['absent'] += 1
            elif st == 'Leave': stats['leave'] += 1
            elif st == 'Off': stats['off'] += 1
            elif st == 'Holiday': stats['holiday'] += 1
            
            if cd.get('extra_hours'):
                stats['extra_hours'] += float(cd.get('extra_hours'))

    stats['net_pending'] = (stats['late_minutes'] + stats['early_minutes']) - int(stats['extra_hours'] * 60)

    return jsonify({
        'employee_name': target_user['name'],
        'employee_id': employee_id,
        'year': year,
        'month': month,
        'days': calendar_days,
        'stats': stats
    })


@app.route('/upload-project', methods=['GET', 'POST'])
def upload_project_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] != 'HR':
        flash("Unauthorized to access Project Upload.", "error")
        return redirect(url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()

    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part in the request.", "error")
            return redirect(url_for('upload_project_page'))
        file = request.files['file']
        if file.filename == '':
            flash("No selected file.", "error")
            return redirect(url_for('upload_project_page'))

        if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            import openpyxl
            try:
                wb = openpyxl.load_workbook(file, read_only=True)
                sheet = wb.active
                
                rows_processed = 0
                files_created = 0
                
                for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                    if not row or len(row) < 3:
                        continue
                        
                    proj_name = str(row[0] or '').strip()
                    chap_name = str(row[1] or '').strip()
                    file_name = str(row[2] or '').strip()
                    file_desc = str(row[3] or '').strip() if len(row) > 3 and row[3] is not None else ''

                    # Skip header row if it contains header-like words in the first row
                    if row_idx == 1:
                        val_a = proj_name.lower()
                        val_c = file_name.lower()
                        if 'project' in val_a or 'file' in val_c:
                            continue

                    if not proj_name or not chap_name or not file_name:
                        continue

                    # 1. Get or Create Project
                    cursor.execute("SELECT id FROM projects WHERE name = ?", (proj_name,))
                    proj_row = cursor.fetchone()
                    if proj_row:
                        proj_id = proj_row['id']
                    else:
                        cursor.execute("INSERT INTO projects (name, description, status) VALUES (?, 'Imported Project', 'Active')", (proj_name,))
                        proj_id = cursor.lastrowid

                    # 2. Get or Create Chapter
                    cursor.execute("SELECT id FROM chapters WHERE project_id = ? AND name = ?", (proj_id, chap_name))
                    chap_row = cursor.fetchone()
                    if chap_row:
                        chap_id = chap_row['id']
                    else:
                        cursor.execute("INSERT INTO chapters (project_id, name, description, status) VALUES (?, ?, 'Imported Chapter', 'Active')", (proj_id, chap_name))
                        chap_id = cursor.lastrowid

                    # 3. Check if file already exists in this chapter to prevent duplicate imports
                    cursor.execute("SELECT id FROM files WHERE chapter_id = ? AND name = ?", (chap_id, file_name))
                    existing_file = cursor.fetchone()
                    if existing_file:
                        continue

                    # 4. Insert File
                    cursor.execute("""
                        INSERT INTO files (chapter_id, name, description, status)
                        VALUES (?, ?, ?, 'Pending')
                    """, (chap_id, file_name, file_desc))
                    file_id = cursor.lastrowid
                    files_created += 1

                    # 5. Initialize the pipeline stages for this file
                    for stage in PIPELINE_STAGES:
                        status = 'Open' if stage == 'Content' else 'Pending'
                        cursor.execute("""
                            INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points)
                            VALUES (?, ?, ?, NULL, 0)
                        """, (file_id, stage, status))

                    rows_processed += 1

                db.commit()
                flash(f"Successfully processed Excel sheet! Created {files_created} new files across projects.", "success")
                cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Upload Project Excel', ?)",
                               (session['user_id'], f"Uploaded excel file '{file.filename}' creating {files_created} files."))
                db.commit()
                
            except Exception as e:
                db.rollback()
                flash(f"Error reading Excel file: {e}", "error")
                
            return redirect(url_for('upload_project_page'))
        else:
            flash("Invalid file format. Please upload an Excel (.xlsx or .xls) file.", "error")
            return redirect(url_for('upload_project_page'))

    return render_template(
        'upload_project.html',
        user=user_info
    )



# ─────────────────────────────────────────────────────────────────────────────
# LAYER 9: ADMIN REPORTS
# ─────────────────────────────────────────────────────────────────────────────

import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from flask import send_file, Response

_HDR_FILL   = PatternFill("solid", fgColor="1E3A5F")
_HDR_FONT   = Font(color="FFFFFF", bold=True, size=10)
_SUBTTL_FILL= PatternFill("solid", fgColor="D6E4F7")
_SUBTTL_FONT= Font(bold=True, size=10)
_ALT_FILL   = PatternFill("solid", fgColor="F7FAFF")
_THIN       = Side(style='thin', color="B0BEC5")
_BORDER     = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

def _xl_header_row(ws, row, cols):
    for c, val in enumerate(cols, 1):
        cell = ws.cell(row=row, column=c, value=val)
        cell.fill = _HDR_FILL; cell.font = _HDR_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = _BORDER

def _xl_data_row(ws, row, vals, fill=None, bold=False):
    for c, v in enumerate(vals, 1):
        cell = ws.cell(row=row, column=c, value=v)
        cell.border = _BORDER
        cell.alignment = Alignment(vertical='center', wrap_text=True)
        if fill: cell.fill = fill
        if bold: cell.font = Font(bold=True, size=10)

def _xl_autowidth(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except: pass
        ws.column_dimensions[col_letter].width = min(max(max_len + 2, 10), 40)

# ── Report data helpers ──────────────────────────────────────────────────────

def _report_morning(db, date_str):
    """Morning Assignment: per artist/lead per team, what was assigned on date_str."""
    c = db.cursor()
    c.execute("""
        SELECT da.id, da.date, da.status as assign_status, da.points, da.task_description,
               da.submit_time, f.name as file_name,
               u.name as artist_name, u.team, u.role as artist_role,
               fp.step_name as stage
        FROM daily_assignments da
        JOIN users u ON da.user_id = u.id
        LEFT JOIN files f ON da.file_id = f.id
        LEFT JOIN file_pipeline fp ON (fp.file_id = da.file_id AND fp.assigned_to = da.user_id)
        WHERE da.date = ?
        ORDER BY u.team, u.name, da.id
    """, (date_str,))
    rows = c.fetchall()
    # Find artists & leads who had NO tasks
    c.execute("SELECT id, name, team, role FROM users WHERE role IN ('Artist', 'Lead') ORDER BY team, name")
    all_staff = c.fetchall()
    assigned_ids = {r['artist_name'] for r in rows}
    no_task = [a for a in all_staff if a['name'] not in assigned_ids]
    return [dict(r) for r in rows], [dict(a) for a in no_task]

def _report_eod(db, date_str):
    """EOD Validation: Done/Pending per file per team on date_str."""
    c = db.cursor()
    c.execute("""
        SELECT da.id, da.status as assign_status, da.points, da.task_description,
               da.remarks as pending_reason, f.name as file_name,
               u.name as artist_name, u.team,
               fp.step_name as stage
        FROM daily_assignments da
        JOIN users u ON da.user_id = u.id
        LEFT JOIN files f ON da.file_id = f.id
        LEFT JOIN file_pipeline fp ON (fp.file_id = da.file_id AND fp.assigned_to = da.user_id)
        WHERE da.date = ?
        ORDER BY u.team, da.status, u.name
    """, (date_str,))
    return [dict(r) for r in c.fetchall()]

def _report_login(db, date_str):
    """Login Timings: per employee on date_str."""
    c = db.cursor()
    c.execute("""
        SELECT u.name, u.team, u.role,
               a.clock_in, a.clock_out, a.status,
               a.late_minutes, a.total_hours, a.extra_hours
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE a.date = ?
        ORDER BY u.team, u.name
    """, (date_str,))
    day_rows = [dict(r) for r in c.fetchall()]
    # Weekly grid: Mon–Sun of the week containing date_str
    try:
        d = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        d = datetime.date.today()
    monday = d - datetime.timedelta(days=d.weekday())
    week_days = [monday + datetime.timedelta(days=i) for i in range(7)]
    c.execute("SELECT id, name, team FROM users ORDER BY team, name")
    all_users = c.fetchall()
    weekly = {}
    for u in all_users:
        weekly[u['name']] = {'team': u['team'], 'days': {}}
        for wd in week_days:
            c.execute("SELECT status, clock_in, late_minutes FROM attendance WHERE user_id=? AND date=?",
                      (u['id'], wd.strftime('%Y-%m-%d')))
            rec = c.fetchone()
            weekly[u['name']]['days'][wd.strftime('%a %d')] = dict(rec) if rec else None
    return day_rows, weekly, [wd.strftime('%a %d') for wd in week_days]

def _report_monthly_points(db, month_str):
    """Monthly Points: per employee breakdown, earned vs target."""
    c = db.cursor()
    # Get all weeks in month
    try:
        year, mon = map(int, month_str.split('-'))
    except:
        today = datetime.date.today()
        year, mon = today.year, today.month
    _, last_day = calendar.monthrange(year, mon)
    month_start = datetime.date(year, mon, 1)
    month_end   = datetime.date(year, mon, last_day)
    # Split into weeks
    weeks = []
    wstart = month_start
    while wstart <= month_end:
        wend = min(wstart + datetime.timedelta(days=6), month_end)
        weeks.append((wstart, wend))
        wstart = wend + datetime.timedelta(days=1)

    c.execute("SELECT id, name, username, team FROM users ORDER BY team, name")
    all_users = c.fetchall()
    results = []
    for u in all_users:
        # Target
        c.execute("SELECT target_points FROM monthly_targets WHERE user_id=? AND month=?",
                  (u['id'], month_str))
        tgt_row = c.fetchone()
        target = tgt_row['target_points'] if tgt_row else 0
        # Weekly breakdown
        week_pts = []
        total_earned = 0
        for ws_, we_ in weeks:
            c.execute("""
                SELECT COALESCE(SUM(points),0) FROM points
                WHERE user_id=? AND date>=? AND date<=?
            """, (u['id'], ws_.strftime('%Y-%m-%d'), we_.strftime('%Y-%m-%d')))
            wpts = c.fetchone()[0] or 0
            week_pts.append(wpts)
            total_earned += wpts
        pct = round(total_earned / target * 100, 1) if target > 0 else 0
        results.append({
            'name': u['name'], 'username': u['username'], 'team': u['team'],
            'target': target, 'earned': total_earned,
            'pct': pct, 'week_pts': week_pts,
            'salary_impact': 'On Track' if pct >= 80 else ('At Risk' if pct >= 50 else 'Below Target'),
        })
    return results, weeks

# ── Report page ──────────────────────────────────────────────────────────────

@app.route('/reports')
def reports_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] != 'Admin':
        flash("Reports are Admin-only.", "error")
        return redirect(url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user_info = cursor.fetchone()

    today_str   = datetime.date.today().strftime('%Y-%m-%d')
    month_str   = datetime.date.today().strftime('%Y-%m')
    tab         = request.args.get('tab', 'morning')
    rdate       = request.args.get('date', today_str)
    rmonth      = request.args.get('month', month_str)

    morning_rows, no_task_artists = [], []
    eod_rows = []
    login_day, login_weekly, week_labels = [], {}, []
    monthly_rows, monthly_weeks = [], []

    if tab == 'morning':
        morning_rows, no_task_artists = _report_morning(db, rdate)
    elif tab == 'eod':
        eod_rows = _report_eod(db, rdate)
    elif tab == 'login':
        login_day, login_weekly, week_labels = _report_login(db, rdate)
    elif tab == 'monthly':
        monthly_rows, monthly_weeks = _report_monthly_points(db, rmonth)

    return render_template('reports.html',
        user=user_info, tab=tab, rdate=rdate, rmonth=rmonth,
        morning_rows=morning_rows, no_task_artists=no_task_artists,
        eod_rows=eod_rows,
        login_day=login_day, login_weekly=login_weekly, week_labels=week_labels,
        monthly_rows=monthly_rows, monthly_weeks=monthly_weeks,
        today_str=today_str, month_str=month_str,
    )

@app.route('/reports/export/<tab>')
def reports_export(tab):
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    rdate  = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    rmonth = request.args.get('month', datetime.date.today().strftime('%Y-%m'))

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default sheet

    if tab == 'morning':
        rows, no_task = _report_morning(db, rdate)
        ws = wb.create_sheet("Morning Assignment")
        ws.append([f"Morning Assignment Report — {rdate}"])
        ws['A1'].font = Font(bold=True, size=13)
        ws.merge_cells('A1:G1')
        ws.append([])
        _xl_header_row(ws, 3, ['Team','Artist','File','Stage','Points','Assign Status','Submit Time'])
        r = 4
        cur_team = None; team_pts = 0; grand = 0
        for row in rows:
            if cur_team and cur_team != row['team']:
                _xl_data_row(ws, r, [f'{cur_team} Subtotal','','','','', str(team_pts),''], _SUBTTL_FILL, True)
                r += 1; team_pts = 0
            cur_team = row['team']
            team_pts += row['points'] or 0; grand += row['points'] or 0
            _xl_data_row(ws, r, [row['team'], row['artist_name'],
                row['file_name'] or row['task_description'], row['stage'] or '',
                row['points'] or 0, row['assign_status'] or '',
                row['submit_time'] or ''])
            r += 1
        if cur_team:
            _xl_data_row(ws, r, [f'{cur_team} Subtotal','','','','',str(team_pts),''], _SUBTTL_FILL, True)
            r += 1
        _xl_data_row(ws, r, ['GRAND TOTAL','','','','',str(grand),''], _SUBTTL_FILL, True)
        r += 2
        if no_task:
            ws.cell(r, 1, '⚠ Artists & Leads with NO tasks:').font = Font(bold=True, color='CC0000')
            r += 1
            for a in no_task:
                _xl_data_row(ws, r, [a['team'], f"{a['name']} ({a.get('role', 'Artist')})", 'NO TASKS ASSIGNED','','','',''])
                r += 1
        _xl_autowidth(ws)
        fname = f"MorningAssignment_{rdate}.xlsx"

    elif tab == 'eod':
        rows = _report_eod(db, rdate)
        ws = wb.create_sheet("EOD Validation")
        ws.append([f"EOD Validation Report — {rdate}"])
        ws['A1'].font = Font(bold=True, size=13)
        ws.merge_cells('A1:G1')
        ws.append([])
        
        done_rows = [r for r in rows if r['assign_status'] == 'Done']
        pending_rows = [r for r in rows if r['assign_status'] == 'Pending']

        # Done Files Section
        ws.cell(3, 1, "Completed / Done Files").font = Font(bold=True, size=11, color="008000")
        _xl_header_row(ws, 4, ['Team','Artist','File','Stage','Status','Points Credited'])
        r = 5
        done_pts = 0
        for row in done_rows:
            done_pts += (row['points'] or 0)
            _xl_data_row(ws, r, [row['team'], row['artist_name'],
                row['file_name'] or '', row['stage'] or '',
                'Done', row['points'] or 0])
            r += 1
        _xl_data_row(ws, r, ['DONE TOTALS', '', '', '', f'Count: {len(done_rows)}', f'{done_pts} pts'], _SUBTTL_FILL, True)
        r += 3

        # Pending (Carry Forward) Section
        ws.cell(r, 1, "Pending Files (Carry Forward to Tomorrow)").font = Font(bold=True, size=11, color="CC6600")
        r += 1
        _xl_header_row(ws, r, ['Team','Artist','File','Stage','Status','Pending Reason / Remarks'])
        r += 1
        for row in pending_rows:
            _xl_data_row(ws, r, [row['team'], row['artist_name'],
                row['file_name'] or '', row['stage'] or '',
                'Pending (CF)', row['pending_reason'] or 'Carried forward to tomorrow'])
            r += 1
        _xl_data_row(ws, r, ['PENDING CF TOTALS', '', '', '', f'Count: {len(pending_rows)}', ''], _SUBTTL_FILL, True)

        _xl_autowidth(ws)
        fname = f"EODValidation_{rdate}.xlsx"

    elif tab == 'login':
        day_rows, weekly, week_labels = _report_login(db, rdate)
        # Sheet 1: daily
        ws1 = wb.create_sheet("Login Timings")
        ws1.append([f"Login Timings — {rdate}"])
        ws1['A1'].font = Font(bold=True, size=13); ws1.merge_cells('A1:H1'); ws1.append([])
        _xl_header_row(ws1, 3, ['Team','Name','Role','Clock In','Clock Out','Total Hours','Status','Late By (min)'])
        r = 4
        for row in day_rows:
            _xl_data_row(ws1, r, [row['team'], row['name'], row['role'],
                row['clock_in'] or '', row['clock_out'] or '',
                round(row['total_hours'] or 0, 2), row['status'] or '',
                row['late_minutes'] or 0])
            r += 1
        _xl_autowidth(ws1)
        # Sheet 2: weekly grid
        ws2 = wb.create_sheet("Weekly Overview")
        header = ['Employee','Team'] + week_labels
        _xl_header_row(ws2, 1, header)
        r2 = 2
        for emp, info in weekly.items():
            row_vals = [emp, info['team']]
            for lbl in week_labels:
                d = info['days'].get(lbl)
                row_vals.append(d['status'] if d else '–')
            _xl_data_row(ws2, r2, row_vals)
            r2 += 1
        _xl_autowidth(ws2)
        fname = f"LoginTimings_{rdate}.xlsx"

    elif tab == 'monthly':
        rows, weeks = _report_monthly_points(db, rmonth)
        ws = wb.create_sheet("Monthly Points")
        week_hdrs = [f"Wk {i+1}" for i in range(len(weeks))]
        all_cols = ['Team','Employee'] + week_hdrs + ['Total Earned','Target','% Done','Salary Impact']
        ws.append([f"Monthly Points Report — {rmonth}"])
        ws['A1'].font = Font(bold=True, size=13)
        ws.merge_cells(f'A1:{get_column_letter(len(all_cols))}1')
        ws.append([])
        _xl_header_row(ws, 3, all_cols)
        r = 4
        for row in rows:
            vals = [row['team'], row['name']] + row['week_pts'] + \
                   [row['earned'], row['target'], f"{row['pct']}%", row['salary_impact']]
            _xl_data_row(ws, r, vals)
            r += 1
        _xl_autowidth(ws)
        fname = f"MonthlyPoints_{rmonth}.xlsx"
    else:
        return redirect(url_for('reports_page'))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 10: HOLIDAYS
# ─────────────────────────────────────────────────────────────────────────────

INDIA_HOLIDAYS_2026 = [
    ("2026-01-14", "Sankranti"),
    ("2026-01-26", "Republic Day"),
    ("2026-03-17", "Holi"),
    ("2026-03-30", "Ram Navami"),
    ("2026-04-02", "Good Friday"),
    ("2026-04-14", "Ambedkar Jayanti"),
    ("2026-04-24", "Ugadi"),
    ("2026-05-01", "Labour Day"),
    ("2026-06-05", "Eid ul-Adha"),
    ("2026-08-15", "Independence Day"),
    ("2026-08-26", "Janmashtami"),
    ("2026-09-02", "Ganesh Chaturthi"),
    ("2026-10-02", "Gandhi Jayanti / Navratri"),
    ("2026-10-20", "Dussehra"),
    ("2026-11-09", "Diwali"),
    ("2026-11-10", "Diwali"),
    ("2026-11-15", "Guru Nanak Jayanti"),
    ("2026-12-25", "Christmas Day"),
]

def _seed_holidays(db):
    c = db.cursor()
    c.execute("SELECT COUNT(*) FROM holidays")
    cnt = c.fetchone()[0]
    if cnt == 0:
        for date_str, name in INDIA_HOLIDAYS_2026:
            try:
                c.execute("INSERT INTO holidays (date, name) VALUES (?, ?)", (date_str, name))
            except Exception:
                pass
        db.commit()

@app.route('/holidays', methods=['GET', 'POST'])
def holidays_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] != 'HR':
        flash("Access restricted to HR.", "error")
        return redirect(url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()
    _seed_holidays(db)

    if request.method == 'POST':
        if session['role'] == 'Admin':
            flash("Admin accounts cannot modify holidays. Only HR accounts can manage holidays.", "error")
            return redirect(url_for('holidays_page'))
        action = request.form.get('action', 'add')
        if action == 'add':
            h_date = request.form.get('h_date', '').strip()
            h_name = request.form.get('h_name', '').strip()
            if h_date and h_name:
                try:
                    cursor.execute("INSERT INTO holidays (date, name) VALUES (?, ?)", (h_date, h_name))
                    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?,?,?)",
                                   (session['user_id'], 'Holiday Added', f"{h_name} on {h_date}"))
                    db.commit()
                    flash(f"Holiday '{h_name}' added for {h_date}.", "success")
                except Exception as e:
                    db.rollback()
                    flash(f"Error adding holiday: {e}", "error")
            else:
                flash("Date and name are required.", "error")

        elif action == 'delete':
            h_id = request.form.get('h_id', type=int)
            if h_id:
                try:
                    cursor.execute("DELETE FROM holidays WHERE id=?", (h_id,))
                    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?,?,?)",
                                   (session['user_id'], 'Holiday Deleted', f"Holiday ID {h_id} removed"))
                    db.commit()
                    flash("Holiday deleted.", "success")
                except Exception as e:
                    db.rollback()
                    flash(f"Error deleting: {e}", "error")

        elif action == 'edit':
            h_id   = request.form.get('h_id', type=int)
            h_date = request.form.get('h_date', '').strip()
            h_name = request.form.get('h_name', '').strip()
            if h_id and h_date and h_name:
                try:
                    cursor.execute("UPDATE holidays SET date=?, name=? WHERE id=?", (h_date, h_name, h_id))
                    db.commit()
                    flash(f"Holiday updated.", "success")
                except Exception as e:
                    db.rollback()
                    flash(f"Error editing: {e}", "error")
            else:
                flash("All fields required for edit.", "error")

        return redirect(url_for('holidays_page'))

    cursor.execute("SELECT id, name, team FROM users WHERE id=?", (session['user_id'],))
    user_info = cursor.fetchone()
    cursor.execute("SELECT * FROM holidays ORDER BY date")
    all_holidays = cursor.fetchall()
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    return render_template('holidays.html',
        user=user_info, holidays=all_holidays, today_str=today_str)


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 10: NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

def _push_notification(db, user_id, title, body="", ntype="info", link=None):
    """Create a notification for a user. Call and commit outside."""
    try:
        db.cursor().execute(
            "INSERT INTO notifications (user_id, title, body, link, type) VALUES (?,?,?,?,?)",
            (user_id, title, body, link, ntype)
        )
    except Exception as e:
        print(f"Error pushing notification: {e}")

def check_and_push_eod_reminders(db, user_id):
    """Check if the user has pending tasks or validations after 5 PM and push EOD reminder."""
    try:
        now = datetime.datetime.now()
        if now.hour >= 17:  # 5 PM or later
            today_str = now.strftime('%Y-%m-%d')
            cursor = db.cursor()
            
            # Get user info
            cursor.execute("SELECT role, team FROM users WHERE id=?", (user_id,))
            u = cursor.fetchone()
            if not u:
                return
                
            role = u['role']
            team = u['team']
            
            # Check if reminder already sent today
            cursor.execute("""
                SELECT COUNT(*) FROM notifications 
                WHERE user_id=? AND title LIKE '%EOD%Reminder%' AND created_at >= ?
            """, (user_id, today_str + ' 00:00:00'))
            already_notified = cursor.fetchone()[0]
            
            if already_notified == 0:
                if role == 'Artist':
                    # Has daily assignments today that are not Done
                    cursor.execute("""
                        SELECT COUNT(*) FROM daily_assignments
                        WHERE user_id=? AND date=? AND status != 'Done'
                    """, (user_id, today_str))
                    uncompleted = cursor.fetchone()[0]
                    if uncompleted > 0:
                        _push_notification(db, user_id, "EOD Reminder", "You have pending assignments. Please submit EOD updates.", "reminder")
                        db.commit()
                elif role in ['Lead', 'Admin']:
                    # Has unvalidated tasks in their team today
                    if role == 'Lead':
                        cursor.execute("""
                            SELECT COUNT(*) FROM daily_assignments da
                            JOIN users artist ON da.user_id = artist.id
                            WHERE artist.team=? AND da.date=? AND da.status != 'Done'
                        """, (team, today_str))
                    else:
                        cursor.execute("""
                            SELECT COUNT(*) FROM daily_assignments da
                            WHERE da.date=? AND da.status != 'Done'
                        """, (today_str,))
                    unvalidated = cursor.fetchone()[0]
                    if unvalidated > 0:
                        _push_notification(db, user_id, "EOD Validation Reminder", "There are pending daily tasks that require validation.", "reminder", link=url_for('dashboard'))
                        db.commit()
    except Exception as e:
        print(f"Error checking EOD reminders: {e}")

def check_and_push_morning_reminders(db, user_id):
    """Check morning assignments status after 9:30 AM and push reminders/alerts."""
    try:
        now = datetime.datetime.now()
        if now.hour > 9 or (now.hour == 9 and now.minute >= 30):
            today_str = now.strftime('%Y-%m-%d')
            cursor = db.cursor()
            
            cursor.execute("SELECT role, team FROM users WHERE id=?", (user_id,))
            u = cursor.fetchone()
            if not u:
                return
            
            role = u['role']
            team = u['team']
            
            if role == 'Lead':
                cursor.execute("""
                    SELECT COUNT(*) FROM notifications
                    WHERE user_id=? AND title = 'Morning assignment reminder' AND created_at >= ?
                """, (user_id, today_str + ' 00:00:00'))
                if cursor.fetchone()[0] == 0:
                    # Check if there are Open (unassigned) files for their team's stage
                    for stage, stg_team in STAGE_TEAMS.items():
                        if stg_team == team:
                            cursor.execute("""
                                SELECT COUNT(*) FROM file_pipeline fp
                                JOIN files f ON fp.file_id = f.id
                                WHERE fp.step_name = ? AND fp.status = 'Open'
                            """, (stage,))
                            open_cnt = cursor.fetchone()[0]
                            if open_cnt > 0:
                                _push_notification(db, user_id, "Morning assignment reminder", 
                                                   f"You have {open_cnt} unassigned files in {stage} queue. Please allocate them.", 
                                                   "reminder", link=url_for('dashboard'))
                                db.commit()
                                break
                                
            elif role == 'Admin':
                cursor.execute("""
                    SELECT COUNT(*) FROM notifications
                    WHERE user_id=? AND title = 'Lead missed morning assignment' AND created_at >= ?
                """, (user_id, today_str + ' 00:00:00'))
                if cursor.fetchone()[0] == 0:
                    for stage, stg_team in STAGE_TEAMS.items():
                        cursor.execute("""
                            SELECT COUNT(*) FROM file_pipeline fp
                            JOIN files f ON fp.file_id = f.id
                            WHERE fp.step_name = ? AND fp.status = 'Open'
                        """, (stage,))
                        open_cnt = cursor.fetchone()[0]
                        if open_cnt > 0:
                            cursor.execute("SELECT name FROM users WHERE team = ? AND role = 'Lead'", (stg_team,))
                            lead_res = cursor.fetchone()
                            lead_name = lead_res['name'] if lead_res else f"the {stg_team} Lead"
                            _push_notification(db, user_id, "Lead missed morning assignment", 
                                               f"{lead_name} has not allocated {open_cnt} files in {stage} queue.", 
                                               "warning", link=url_for('dashboard'))
                            db.commit()
    except Exception as e:
        print(f"Error check_and_push_morning_reminders: {e}")

def check_and_push_admin_target_alerts(db, admin_id):
    """Check if any artist is far below their target and notify admin."""
    try:
        now = datetime.datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        current_month = now.strftime('%Y-%m')
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM notifications
            WHERE user_id=? AND title = 'Target alert' AND created_at >= ?
        """, (admin_id, today_str + ' 00:00:00'))
        if cursor.fetchone()[0] > 0:
            return
            
        cursor.execute("SELECT id, name, role FROM users WHERE role IN ('Artist', 'Lead')")
        employees = cursor.fetchall()
        
        for emp in employees:
            cursor.execute("SELECT target_points FROM monthly_targets WHERE user_id=? AND month=?", 
                            (emp['id'], current_month))
            tgt_row = cursor.fetchone()
            target = tgt_row['target_points'] if tgt_row else 500
            
            cursor.execute("SELECT SUM(points) FROM points WHERE user_id=? AND strftime('%Y-%m', date)=?", 
                            (emp['id'], current_month))
            earned = cursor.fetchone()[0] or 0
            
            if target > 0 and (earned / target) < 0.3:
                role_label = "Lead" if emp['role'] == 'Lead' else "Artist"
                _push_notification(db, admin_id, "Target alert", 
                                   f"{role_label} {emp['name']} is far below target: earned {earned}/{target} pts.", 
                                   "warning", link=url_for('points_page'))
                db.commit()
                break
    except Exception as e:
        print(f"Error check_and_push_admin_target_alerts: {e}")

@app.context_processor
def inject_notifications():
    """Inject unread notification count and recent list into every template."""
    count = 0
    recent = []
    if 'user_id' in session:
        try:
            db = get_db()
            row = db.cursor().execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",
                (session['user_id'],)
            ).fetchone()
            count = row[0] if row else 0
            
            cursor = db.cursor()
            cursor.execute("""
                SELECT id, title, body, link, type, is_read, created_at
                FROM notifications 
                WHERE user_id=? 
                ORDER BY created_at DESC LIMIT 10
            """, (session['user_id'],))
            recent = cursor.fetchall()
        except Exception:
            count = 0
    return dict(unread_notif_count=count, recent_notifications=recent)

@app.route('/api/notifications/unread_count')
def api_unread_notifications_count():
    if 'user_id' not in session:
        return {'unread_count': 0}
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (session['user_id'],))
        count = cursor.fetchone()[0]
        return {'unread_count': count}
    except Exception:
        return {'unread_count': 0}

@app.route('/notifications')
def notifications_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user_info = cursor.fetchone()
    cursor.execute("""
        SELECT * FROM notifications WHERE user_id=?
        ORDER BY is_read ASC, created_at DESC LIMIT 100
    """, (session['user_id'],))
    notifs = cursor.fetchall()
    # Mark all as read
    cursor.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (session['user_id'],))
    db.commit()
    return render_template('notifications.html', user=user_info, notifs=notifs)

@app.route('/notifications/click/<int:nid>')
def click_notification(nid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM notifications WHERE id=? AND user_id=?", (nid, session['user_id']))
    notif = cursor.fetchone()
    if notif:
        cursor.execute("UPDATE notifications SET is_read=1 WHERE id=?", (nid,))
        db.commit()
        if notif['link']:
            return redirect(notif['link'])
    return redirect(url_for('dashboard'))

@app.route('/notifications/read-all', methods=['POST'])
def read_all_notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (session['user_id'],))
    db.commit()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/notifications/mark-read', methods=['POST'])
def mark_notification_read():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    nid = request.form.get('nid', type=int)
    if nid:
        db = get_db()
        db.cursor().execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?",
                            (nid, session['user_id']))
        db.commit()
    return redirect(request.referrer or url_for('notifications_page'))


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 10: ACTIVITY LOG
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/activity-log')
def activity_log_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] != 'HR':
        flash("Activity log is HR-only.", "error")
        return redirect(url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user_info = cursor.fetchone()

    search  = request.args.get('q', '').strip()
    page    = max(1, request.args.get('page', 1, type=int))
    per_page = 50
    offset  = (page - 1) * per_page

    if search:
        cursor.execute("""
            SELECT al.*, u.name as actor_name, u.username as actor_username
            FROM activity_log al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE al.action LIKE ? OR al.details LIKE ? OR u.name LIKE ? OR u.username LIKE ?
            ORDER BY al.id DESC LIMIT ? OFFSET ?
        """, (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', per_page, offset))
        logs = cursor.fetchall()
        cursor.execute("""
            SELECT COUNT(*) FROM activity_log al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE al.action LIKE ? OR al.details LIKE ? OR u.name LIKE ? OR u.username LIKE ?
        """, (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cursor.execute("""
            SELECT al.*, u.name as actor_name, u.username as actor_username
            FROM activity_log al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.id DESC LIMIT ? OFFSET ?
        """, (per_page, offset))
        logs = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM activity_log")

    total = cursor.fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template('activity_log.html',
        user=user_info, logs=logs, search=search,
        page=page, per_page=per_page, total=total, total_pages=total_pages)



# ─────────────────────────────────────────────────────────────────────────────
# LAYER 11: WORK REPORTS (NEW ADMIN FEATURE)
# ─────────────────────────────────────────────────────────────────────────────

def _get_work_reports_data(db, range_type='this_week', custom_start='', custom_end='', search_query='', employee_id=None):
    today = datetime.date.today()
    if range_type == 'this_week':
        start_date = today - datetime.timedelta(days=today.weekday())
        end_date = today
    elif range_type == 'last_week':
        start_date = today - datetime.timedelta(days=today.weekday() + 7)
        end_date = start_date + datetime.timedelta(days=6)
    elif range_type == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
    elif range_type == 'last_month':
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - datetime.timedelta(days=1)
        start_date = last_month_end.replace(day=1)
        end_date = last_month_end
    elif range_type == '3_months':
        start_date = today - datetime.timedelta(days=90)
        end_date = today
    elif range_type == '6_months':
        start_date = today - datetime.timedelta(days=180)
        end_date = today
    elif range_type == '1_year':
        start_date = today - datetime.timedelta(days=365)
        end_date = today
    elif range_type == 'custom':
        try:
            start_date = datetime.datetime.strptime(custom_start, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(custom_end, '%Y-%m-%d').date()
            if (end_date - start_date).days > 365:
                start_date = end_date - datetime.timedelta(days=365)
        except Exception:
            start_date = today - datetime.timedelta(days=30)
            end_date = today
    else:
        start_date = today - datetime.timedelta(days=today.weekday())
        end_date = today

    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    c = db.cursor()
    query = "SELECT id, name, username, role, team FROM users WHERE role IN ('Artist', 'Lead')"
    params = []
    if employee_id:
        query += " AND id = ?"
        params.append(employee_id)
    if search_query:
        query += " AND (name LIKE ? OR username LIKE ? OR team LIKE ?)"
        params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])
    query += " ORDER BY team, role, name"

    c.execute(query, tuple(params))
    staff_members = c.fetchall()

    staff_reports = []
    total_tasks_completed = 0
    total_points_earned = 0

    current_month = today.strftime('%Y-%m')
    global_scoreboard = {}

    for s in staff_members:
        sid = s['id']
        c.execute("""
            SELECT da.id, da.date, da.status, da.points, da.task_description, da.remarks, da.submit_time,
                   f.name as file_name, fp.step_name as stage,
                   p.name as project_name, ch.name as chapter_name
            FROM daily_assignments da
            LEFT JOIN files f ON da.file_id = f.id
            LEFT JOIN chapters ch ON f.chapter_id = ch.id
            LEFT JOIN projects p ON ch.project_id = p.id
            LEFT JOIN file_pipeline fp ON (fp.file_id = da.file_id AND fp.assigned_to = da.user_id)
            WHERE da.user_id = ? AND da.date >= ? AND da.date <= ?
            ORDER BY da.date DESC, da.id DESC
        """, (sid, start_str, end_str))
        assignments = [dict(r) for r in c.fetchall()]

        done_assignments = [a for a in assignments if a['status'] == 'Done']
        pending_assignments = [a for a in assignments if a['status'] == 'Pending']

        pts_sum = sum(a['points'] or 0 for a in done_assignments)
        
        c.execute("""
            SELECT COUNT(DISTINCT date) as days_worked, COALESCE(SUM(total_hours), 0) as total_hrs
            FROM attendance
            WHERE user_id = ? AND date >= ? AND date <= ? AND status IN ('Present', 'Late', 'Half Day')
        """, (sid, start_str, end_str))
        att_row = c.fetchone()
        days_worked = att_row['days_worked'] if att_row else 0
        total_hrs = round(att_row['total_hrs'], 1) if att_row else 0.0

        c.execute("SELECT target_points FROM monthly_targets WHERE user_id = ? AND month = ?", (sid, current_month))
        target_res = c.fetchone()
        target_pts = target_res['target_points'] if target_res else 500
        prog_pct = round((pts_sum / target_pts) * 100, 1) if target_pts > 0 else 0

        staff_info = {
            'id': sid,
            'name': s['name'],
            'username': s['username'],
            'role': s['role'],
            'team': s['team'],
            'tasks_completed': len(done_assignments),
            'tasks_pending': len(pending_assignments),
            'total_points': pts_sum,
            'target_points': target_pts,
            'progress_pct': prog_pct,
            'days_worked': days_worked,
            'total_hours': total_hrs,
            'assignments': assignments,
            'done_assignments': done_assignments
        }
        staff_reports.append(staff_info)

        tm = s['team']
        if tm not in global_scoreboard:
            global_scoreboard[tm] = []
        global_scoreboard[tm].append(staff_info)

        total_tasks_completed += len(done_assignments)
        total_points_earned += pts_sum

    c.execute("SELECT id, name, username, role, team FROM users WHERE role IN ('Artist', 'Lead') ORDER BY name")
    all_staff_dropdown = [dict(r) for r in c.fetchall()]

    return {
        'range_type': range_type,
        'start_date': start_str,
        'end_date': end_str,
        'custom_start': custom_start,
        'custom_end': custom_end,
        'staff_reports': staff_reports,
        'global_scoreboard': global_scoreboard,
        'all_staff': all_staff_dropdown,
        'total_tasks_completed': total_tasks_completed,
        'total_points_earned': total_points_earned,
        'search_query': search_query,
        'selected_employee_id': employee_id,
        'current_month': current_month
    }


@app.route('/work-reports')
def work_reports_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] != 'Admin':
        flash("Work Reports are Admin-only.", "error")
        return redirect(url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()

    range_type = request.args.get('range_type', 'this_week')
    custom_start = request.args.get('start_date', '')
    custom_end = request.args.get('end_date', '')
    search_query = request.args.get('q', '').strip()
    employee_id = request.args.get('employee_id', type=int)

    data = _get_work_reports_data(db, range_type, custom_start, custom_end, search_query, employee_id)

    selected_staff = None
    if employee_id:
        for s in data['staff_reports']:
            if s['id'] == employee_id:
                selected_staff = s
                break
    elif len(data['staff_reports']) == 1:
        selected_staff = data['staff_reports'][0]

    return render_template(
        'work_reports.html',
        user=user_info,
        data=data,
        selected_staff=selected_staff,
        today_str=datetime.date.today().strftime('%Y-%m-%d')
    )



@app.route('/work-reports/export')
def work_reports_export():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] != 'Admin':
        flash("Unauthorized", "error")
        return redirect(url_for('dashboard'))

    db = get_db()
    range_type = request.args.get('range_type', 'this_week')
    custom_start = request.args.get('start_date', '')
    custom_end = request.args.get('end_date', '')
    search_query = request.args.get('q', '').strip()
    employee_id = request.args.get('employee_id', type=int)

    data = _get_work_reports_data(db, range_type, custom_start, custom_end, search_query, employee_id)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Sheet 1: Staff Work Summary
    ws1 = wb.create_sheet("Staff Work Summary")
    ws1.append([f"Employee Work Report Summary ({data['start_date']} to {data['end_date']})"])
    ws1['A1'].font = Font(bold=True, size=13)
    ws1.merge_cells('A1:H1')
    ws1.append([])
    _xl_header_row(ws1, 3, ['Team', 'Role', 'Employee Name', 'Tasks Completed', 'Tasks Pending', 'Points Earned', 'Days Worked', 'Total Hours'])
    r = 4
    for s in data['staff_reports']:
        _xl_data_row(ws1, r, [
            s['team'], s['role'], f"{s['name']} (@{s['username']})",
            s['tasks_completed'], s['tasks_pending'], s['total_points'],
            s['days_worked'], s['total_hours']
        ])
        r += 1
    _xl_autowidth(ws1)

    # Sheet 2: Detailed Task Log
    ws2 = wb.create_sheet("Detailed Task Log")
    ws2.append([f"Detailed Task Log ({data['start_date']} to {data['end_date']})"])
    ws2['A1'].font = Font(bold=True, size=13)
    ws2.merge_cells('A1:K1')
    ws2.append([])
    _xl_header_row(ws2, 3, ['Date', 'Employee', 'Role', 'Team', 'Project', 'Chapter', 'File / Task Description', 'Stage', 'Points', 'Status', 'Submit Time / Remarks'])
    r2 = 4
    for s in data['staff_reports']:
        for a in s['assignments']:
            _xl_data_row(ws2, r2, [
                a['date'], s['name'], s['role'], s['team'],
                a['project_name'] or '—', a['chapter_name'] or '—',
                a['file_name'] or a['task_description'], a['stage'] or '—',
                a['points'] or 0, a['status'], a['remarks'] or a['submit_time'] or ''
            ])
            r2 += 1
    _xl_autowidth(ws2)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"WorkReport_{data['start_date']}_to_{data['end_date']}.xlsx"
    return send_file(buf, download_name=fname, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/logout')
def logout():
    if 'user_id' in session:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)", 
                       (session['user_id'], 'User Logout', f"User {session['username']} logged out."))
        db.commit()
        
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
