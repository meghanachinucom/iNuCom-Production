import os
import datetime
import calendar
import re
import io
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, jsonify, make_response, send_file
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from db import open_encrypted_connection, get_db_password
from pipeline_excel import (
    generate_team_excel_template,
    parse_and_validate_upload,
    commit_team_upload,
    get_team_open_queue,
)

load_dotenv()

DATABASE = os.environ.get('DATABASE_PATH', 'production.db')
SCHEMA_FILE = 'schema.sql'

# Fail-fast security configuration
get_db_password()
_secret_key = os.environ.get('FLASK_SECRET_KEY', '').strip()
if not _secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is required.")

app = Flask(__name__)
app.secret_key = _secret_key
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('HTTPS_ENABLED', '0') == '1'
app.config['WTF_CSRF_TIME_LIMIT'] = None

csrf = CSRFProtect(app)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash("You do not have permission to access that resource.", "error")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


@app.template_filter('strftime')
def _strftime_filter(value, fmt='%d-%m-%Y'):
    if not value:
        return ''
    try:
        val_str = str(value).strip().split(' ')[0].split('T')[0]
        return datetime.datetime.strptime(val_str, '%Y-%m-%d').strftime(fmt)
    except Exception:
        return value


@app.template_filter('ddmmyyyy')
@app.template_filter('date_ddmmyyyy')
def _ddmmyyyy_filter(value):
    if not value:
        return ''
    try:
        val_str = str(value).strip()
        return re.sub(r'\b(20\d\d)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b', lambda m: f"{m.group(3)}-{m.group(2)}-{m.group(1)}", val_str)
    except Exception:
        return str(value)


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


# Ordered Pipeline Stages (Sequential Handoff Order)
ORDERED_PIPELINE_STAGES = [
    ("Content", "Content", 1),
    ("Modeling", "Modeling", 2),
    ("Texturing", "Texturing", 3),
    ("Rig", "Rig", 4),
    ("Animation", "Animation", 5),
    ("FBX Export", "Animation", 6),
    ("VFX", "VFX", 7),
    ("Lighting", "Lighting", 8),
    ("Rendering", "Rendering", 9),
    ("3D Comp", "3D Comp & Motion Graphics", 10),
    ("Motion Graphics", "3D Comp & Motion Graphics", 11),
    ("VR", "VR", 12),
]

PRODUCTION_TEAMS = [
    "Content",
    "Modeling",
    "Texturing",
    "Rig",
    "Animation",
    "VFX",
    "Lighting",
    "Rendering",
    "3D Comp & Motion Graphics",
    "VR",
]

ASSET_STAGES = ['Reference', 'Explanation', 'Modeling', 'Texturing', 'Rig']

SCENE_STAGES_FULL = [
    'Voice Over', 'Narration', 'Storyboards', 'Explanation', 'Scene-wise Assets',
    'Animation', 'FBX export', 'VFX', 'Lighting', 'Rendering', '3D Comp & Motion Graphics', 'VR'
]

SCENE_STAGES_COMPAI = [
    'Voice Over', 'Narration', 'Storyboards', 'Explanation', 'Scene-wise Assets',
    '3D Comp & Motion Graphics'
]

PIPELINE_STAGES = [
    'Content', 'Modeling', 'Texturing', 'Rig', 'Animation', 'FBX Export',
    'VFX', 'Lighting', 'Rendering', '3D Comp', 'Motion Graphics', 'VR'
]

STAGE_TEAMS = {stage: team for stage, team, _ in ORDERED_PIPELINE_STAGES}

STAGE_SUFFIX_MAP = {
    'Content': 'cnt', 'Modeling': 'mdl', 'Texturing': 'tex', 'Rig': 'rig',
    'Animation': 'anim', 'FBX Export': 'fbx', 'VFX': 'vfx', 'Lighting': 'lgt',
    'Rendering': 'rnd', '3D Comp': 'comp', 'Motion Graphics': 'mgx', 'VR': 'vr'
}

def get_clean_base_name(name):
    if not name:
        return ""
    return name.strip()

def compute_file_display_name(base_name, take_count, stage_name=None):
    return get_clean_base_name(base_name)

def get_file_pipeline_sequence(db, file_id):
    return PIPELINE_STAGES

SEEDED_USERS = [
    {"name": "Vasu", "username": "vasu", "role": "Admin", "team": "Management", "reports_to": None},
    {"name": "Meghana. Ch", "username": "meghana", "role": "Admin", "team": "Management", "reports_to": None},
    {"name": "Pooja. L", "username": "pooja", "role": "Lead", "team": "Content", "reports_to": "vasu"},
    {"name": "Prabhas", "username": "prabhas", "role": "Artist", "team": "Content", "reports_to": "pooja"},
    {"name": "Amit Pounikar", "username": "amit", "role": "Lead", "team": "Modeling", "reports_to": "vasu"},
    {"name": "Raveendra. K", "username": "raveendra", "role": "Artist", "team": "Modeling", "reports_to": "amit"},
    {"name": "Nagireddy. E", "username": "nagireddy", "role": "Artist", "team": "Modeling", "reports_to": "amit"},
    {"name": "Rajendra Prasad. K", "username": "rajendra", "role": "Artist", "team": "Modeling", "reports_to": "amit"},
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
    {"name": "Pavan Kalyan. I", "username": "pavan", "role": "Lead", "team": "Lighting", "reports_to": "vasu"},
    {"name": "Abhilash. A", "username": "abhilash", "role": "Artist", "team": "Lighting", "reports_to": "pavan"},
    {"name": "Spandana. K", "username": "spandana", "role": "Lead", "team": "3D Comp & Motion Graphics", "reports_to": "vasu"},
    {"name": "L. Shiva Kumar", "username": "shiva", "role": "Artist", "team": "3D Comp & Motion Graphics", "reports_to": "spandana"},
    {"name": "Laxman. G", "username": "laxman", "role": "Artist", "team": "3D Comp & Motion Graphics", "reports_to": "spandana"},
    {"name": "Prashanth. M", "username": "prashanth", "role": "Artist", "team": "3D Comp & Motion Graphics", "reports_to": "spandana"},
    {"name": "Santosh Kedari", "username": "santosh", "role": "Lead", "team": "VR", "reports_to": "vasu"},
    {"name": "Agnijeet", "username": "agnijeet", "role": "Artist", "team": "VR", "reports_to": "santosh"}
]


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = open_encrypted_connection(DATABASE)
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        if exception:
            try:
                db.rollback()
            except Exception:
                pass
        db.close()


def recalculate_file_metadata(db, file_id):
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

    # For Chapters 13, 14, 15: direct 3D Comp & Motion Graphics flow (bypass upstream stages)
    cursor.execute("""
        SELECT c.name 
        FROM files f 
        JOIN chapters c ON f.chapter_id = c.id 
        WHERE f.id = ?
    """, (file_id,))
    ch_res = cursor.fetchone()
    if ch_res and ch_res['name'] in ['Chapter 13', 'Chapter 14', 'Chapter 15']:
        upstream = ['Voice Over', 'Narration', 'Storyboards', 'Explanation', 'Scene-wise Assets', 'Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering']
        for up_stg in upstream:
            if up_stg in steps_map and steps_map[up_stg]['status'] != 'Done':
                cursor.execute("""
                    UPDATE file_pipeline
                    SET status = 'Done', start_date = COALESCE(start_date, ?), end_date = COALESCE(end_date, ?)
                    WHERE file_id = ? AND step_name = ?
                """, (today_str, today_str, file_id, up_stg))
                steps_map[up_stg]['status'] = 'Done'

    # Auto-mark Content stages as 'Done' if any downstream team has started or completed work
    content_stages_set = {'Reference', 'Explanation', 'Voice Over', 'Narration', 'Storyboards', 'Scene-wise Assets'}
    has_downstream_work = any(
        s['status'] in ['In Progress', 'WIP', 'Open', 'Review', 'Done', 'Approved']
        for s in ordered_steps if s['step_name'] not in content_stages_set
    )
    if has_downstream_work:
        for c_stg in content_stages_set:
            if c_stg in steps_map and steps_map[c_stg]['status'] not in ['Done', 'Approved']:
                cursor.execute("""
                    UPDATE file_pipeline 
                    SET status = 'Done', start_date = COALESCE(start_date, ?), end_date = COALESCE(end_date, ?) 
                    WHERE file_id = ? AND step_name = ?
                """, (today_str, today_str, file_id, c_stg))
                steps_map[c_stg]['status'] = 'Done'

    # Check 2D Comp AI status for this file
    cursor.execute("SELECT is_comp_ai FROM files WHERE id = ?", (file_id,))
    f_ai_row = cursor.fetchone()
    file_is_comp_ai = (f_ai_row and f_ai_row['is_comp_ai'] == 1)

    # Sequential team handover unlocking: Step i opens ONLY when preceding Step i-1 is 'Done' or 'Approved'
    comp_ai_bypassed_stages = {'Modeling', 'Texturing', 'Rig', 'Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering'}
    for idx, step in enumerate(ordered_steps):
        if idx == 0:
            if step['status'] in ['Yts', None, '']:
                cursor.execute("UPDATE file_pipeline SET status = 'Open' WHERE file_id = ? AND step_name = ?", (file_id, step['step_name']))
                step['status'] = 'Open'
        else:
            if file_is_comp_ai and step['step_name'] in comp_ai_bypassed_stages:
                continue
            prev_step = ordered_steps[idx - 1]
            prev_is_bypassed = (file_is_comp_ai and prev_step['step_name'] in comp_ai_bypassed_stages)
            prev_done = (prev_step['status'] in ['Done', 'Approved', 'Not Applicable', 'Skipped']) or prev_is_bypassed
            if prev_done and step['status'] in ['Yts', None, '']:
                cursor.execute("UPDATE file_pipeline SET status = 'Open' WHERE file_id = ? AND step_name = ?", (file_id, step['step_name']))
                step['status'] = 'Open'

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
    all_done = all(s['status'] in ['Done', 'Approved', 'Not Applicable', 'Skipped'] for s in ordered_steps) if ordered_steps else False
    any_hold = any(s['status'] in ['Hold', 'ON HOLD', 'On Hold', 'hold'] for s in ordered_steps)
    any_rtk = any(s['status'] in ['RTK', 'Rework', 'Re-take'] for s in ordered_steps)
    any_review = any(s['status'] in ['Review', 'Lead Review', 'Content Review', 'Final Review'] for s in ordered_steps)
    any_wip = any(s['status'] in ['Wip', 'In Progress', 'WIP', 'Open'] for s in ordered_steps)
    
    if any_hold:
        calc_status = 'Hold'
    elif all_done and file_row['final_review_status'] == 'Approved':
        calc_status = 'Done'
    elif all_done or any_review:
        calc_status = 'Review'
    elif any_rtk:
        calc_status = 'RTK'
    elif any_wip:
        calc_status = 'Wip'
    else:
        calc_status = 'Yts'

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


def is_lead_absent_today(db, team_name):
    return None


def record_rtk_event(db, file_id, stage_name, rework_reason, target_team=None, assigned_to_user_id=None):
    cursor = db.cursor()
    cursor.execute("""
        SELECT f.id, f.name, f.take_count, f.chapter_id
        FROM files f
        WHERE f.id = ?
    """, (file_id,))
    file_row = cursor.fetchone()
    if not file_row:
        return
        
    base_name = get_clean_base_name(file_row['name'])
    current_take = file_row['take_count'] or 0
    new_take = current_take + 1
    
    old_file_name = compute_file_display_name(base_name, current_take, stage_name)
    new_file_name = compute_file_display_name(base_name, new_take, stage_name)
    
    if not target_team:
        target_team = STAGE_TEAMS.get(stage_name, 'Unknown')
        
    artist_name = None
    artist_username = None
    if assigned_to_user_id:
        cursor.execute("SELECT id, name, username FROM users WHERE id = ?", (assigned_to_user_id,))
        u_row = cursor.fetchone()
        if u_row:
            artist_name = u_row['name']
            artist_username = u_row['username']
    else:
        cursor.execute("SELECT assigned_to FROM file_pipeline WHERE file_id = ? AND step_name = ?", (file_id, stage_name))
        fp_row = cursor.fetchone()
        if fp_row and fp_row['assigned_to']:
            assigned_to_user_id = fp_row['assigned_to']
            cursor.execute("SELECT id, name, username FROM users WHERE id = ?", (assigned_to_user_id,))
            u_row = cursor.fetchone()
            if u_row:
                artist_name = u_row['name']
                artist_username = u_row['username']
                
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user_id = session.get('user_id')
    user_name = session.get('name') or 'System'
    creator_team = session.get('team') or ''
    creator_role = session.get('role') or ''
    if creator_team and creator_role:
        creator_label = f"{user_name} ({creator_team} {creator_role})"
    elif creator_team:
        creator_label = f"{user_name} ({creator_team})"
    else:
        creator_label = user_name
    
    # 1. Update files table (reset review approval statuses to Pending)
    cursor.execute("""
        UPDATE files
        SET take_count = ?, rework_reason = ?, rework_target_team = ?, status = 'RTK',
            internal_lead_status = 'Pending', internal_content_status = 'Pending', final_review_status = 'Pending'
        WHERE id = ?
    """, (new_take, rework_reason, target_team, file_id))
    
    # 2. Update target stage (reset assigned_to, end_date, submitted_at, set status = 'RTK')
    cursor.execute("""
        UPDATE file_pipeline
        SET status = 'RTK', take_count = ?, rework_reason = ?, rework_target_team = ?,
            assigned_to = NULL, end_date = NULL, submitted_at = NULL
        WHERE file_id = ? AND step_name = ?
    """, (new_take, rework_reason, target_team, file_id, stage_name))

    # 3. Reset all downstream pipeline stages (steps occurring after stage_name) to 'Yts'
    pipeline_seq = get_file_pipeline_sequence(db, file_id)
    if stage_name in pipeline_seq:
        target_idx = pipeline_seq.index(stage_name)
        downstream_stages = pipeline_seq[target_idx + 1:]
        for ds_stg in downstream_stages:
            cursor.execute("""
                UPDATE file_pipeline
                SET status = 'Yts', take_count = ?, rework_reason = NULL, rework_target_team = NULL,
                    assigned_to = NULL, start_date = NULL, end_date = NULL, submitted_at = NULL
                WHERE file_id = ? AND step_name = ?
            """, (new_take, file_id, ds_stg))
    
    # 4. Insert RTK History Record
    cursor.execute("""
        INSERT INTO rtk_history (
            file_id, take_number, stage_name, target_team, assigned_to,
            assigned_to_name, assigned_to_username, old_file_name, new_file_name,
            reason, created_at, created_by, created_by_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        file_id, new_take, stage_name, target_team, assigned_to_user_id,
        artist_name, artist_username, old_file_name, new_file_name,
        rework_reason or "Rework Requested", now_str, user_id, creator_label
    ))
    db.commit()

    # 5. Recalculate file metadata so active stage, status, and handover rules refresh immediately
    recalculate_file_metadata(db, file_id)


def init_db():
    db_exists = os.path.exists(DATABASE)
    conn = open_encrypted_connection(DATABASE)
    try:
        cursor = conn.cursor()
        has_users = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if not db_exists or not has_users:
            with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
                conn.executescript(f.read())

        # Ensure new tables exist on existing encrypted DBs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stage_name TEXT NOT NULL UNIQUE,
                team_id INTEGER,
                team_name TEXT NOT NULL,
                stage_order INTEGER NOT NULL,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_upload_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                uploaded_by INTEGER NOT NULL,
                upload_date TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                files_updated INTEGER DEFAULT 0,
                files_added INTEGER DEFAULT 0,
                files_handed_off INTEGER DEFAULT 0,
                files_rework INTEGER DEFAULT 0,
                filename TEXT,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Seed users if empty
        user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            default_pwd_hash = generate_password_hash("inucom@123")
            for user in SEEDED_USERS:
                cursor.execute(
                    """
                    INSERT INTO users (name, username, password_hash, role, team, reports_to, must_change_password)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                    """,
                    (user['name'], user['username'], default_pwd_hash, user['role'], user['team'], user['reports_to']),
                )
            current_month = datetime.date.today().strftime('%Y-%m')
            artist_ids = [r[0] for r in cursor.execute("SELECT id FROM users WHERE role IN ('Artist', 'Lead')").fetchall()]
            for aid in artist_ids:
                cursor.execute("INSERT INTO monthly_targets (user_id, month, target_points) VALUES (?, ?, ?)", (aid, current_month, 500))
            cursor.execute("INSERT INTO activity_log (action, details) VALUES ('System Init', 'Encrypted database initialized.')")

        # Seed teams and link leads
        for t_name in PRODUCTION_TEAMS + ["Management"]:
            lead_row = cursor.execute(
                "SELECT id FROM users WHERE team = ? AND role = 'Lead' LIMIT 1", (t_name,)
            ).fetchone()
            lead_id = lead_row['id'] if lead_row else None
            existing_team = cursor.execute("SELECT id FROM teams WHERE name = ?", (t_name,)).fetchone()
            if existing_team:
                if lead_id:
                    cursor.execute("UPDATE teams SET lead_id = COALESCE(lead_id, ?) WHERE id = ?", (lead_id, existing_team['id']))
            else:
                cursor.execute("INSERT INTO teams (name, lead_id, department) VALUES (?, ?, 'Production')", (t_name, lead_id))

        # Seed ordered pipeline stages
        for stage_name, team_name, order in ORDERED_PIPELINE_STAGES:
            t_row = cursor.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()
            tid = t_row['id'] if t_row else None
            cursor.execute(
                """
                INSERT OR IGNORE INTO pipeline_stages (stage_name, team_id, team_name, stage_order)
                VALUES (?, ?, ?, ?)
                """,
                (stage_name, tid, team_name, order),
            )

        # Seed default RBAC permissions
        default_perms = [
            ("Admin", "manage_users", 1),
            ("Admin", "view_all_teams", 1),
            ("Admin", "view_compliance", 1),
            ("Admin", "upload_excel", 1),
            ("Lead", "manage_users", 0),
            ("Lead", "view_all_teams", 0),
            ("Lead", "view_compliance", 0),
            ("Lead", "upload_excel", 1),
            ("Artist", "manage_users", 0),
            ("Artist", "view_all_teams", 0),
            ("Artist", "view_compliance", 0),
            ("Artist", "upload_excel", 0),
        ]
        for role, perm, allowed in default_perms:
            cursor.execute(
                "INSERT OR IGNORE INTO permissions (role, permission_name, allowed) VALUES (?, ?, ?)",
                (role, perm, allowed),
            )

        # Ensure default project exists
        if cursor.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO projects (name, description, status, project_type) VALUES ('Promo Videos', 'Promo Videos Production Project', 'Active', 'Promo Videos')"
            )
            pid = cursor.lastrowid
            cursor.execute(
                "INSERT INTO chapters (project_id, name, description, status) VALUES (?, 'Promo Videos Main Chapter', 'Main Promo Videos Chapter', 'Active')",
                (pid,),
            )

        conn.commit()
    finally:
        conn.close()


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
        if session.get('role') == 'Admin':
            return redirect(url_for('reports_page'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if 'user_id' in session:
            if session.get('role') == 'Admin':
                return redirect(url_for('reports_page'))
            return redirect(url_for('dashboard'))
        return render_template('login.html')

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
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['name'] = user['name']
        session['role'] = user['role']
        session['team'] = user['team']
        session['logged_in'] = True

        cursor.execute(
            "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
            (user['id'], 'User Login', f"User {user['username']} logged in successfully."),
        )
        db.commit()

        if user['must_change_password'] == 1:
            return redirect(url_for('change_password'))
        elif user['role'] == 'Admin':
            return redirect(url_for('reports_page'))
        return redirect(url_for('dashboard'))

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

    sub_tab = request.args.get('sub_tab', '')
    if session['role'] == 'Admin' and sub_tab not in ['assets', 'scenes']:
        return redirect(url_for('reports_page'))
        
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
    
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    attendance_today = None
    
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
    sub_tab = request.args.get('sub_tab')
    if not sub_tab:
        if session.get('role') in ['Lead', 'Artist', 'Admin']:
            sub_tab = 'dashboard'
        else:
            sub_tab = 'assets'

    if sub_tab not in ['dashboard', 'assets', 'scenes']:
        sub_tab = 'dashboard' if session.get('role') in ['Lead', 'Artist', 'Admin'] else 'assets'

    sheet_view = request.args.get('sheet_view', 'standard')
    if sheet_view not in ['standard', 'team_overview']:
        sheet_view = 'standard'
        
    if sub_tab == 'scenes':
        stages_list = SCENE_STAGES_FULL
    else:
        stages_list = ASSET_STAGES

    active_projects_list = []
    project_chapters_map = {}
    chapter_files_map = {}
    matrix = {}
    
    view_tab = request.args.get('view', 'overview')
    if project_id:
        active_projects_list = [p for p in projects if p['id'] == project_id]
        if not active_projects_list and projects:
            active_projects_list = [projects[0]]
    else:
        active_projects_list = projects

    for proj in active_projects_list:
        pid = proj['id']
        if chapter_id:
            cursor.execute("SELECT * FROM chapters WHERE id = ? AND status = 'Active'", (chapter_id,))
        else:
            cursor.execute("SELECT * FROM chapters WHERE project_id = ? AND status = 'Active'", (pid,))
        chaps = cursor.fetchall()
        project_chapters_map[pid] = chaps
        for chap in chaps:
            cid = chap['id']
            if sub_tab == 'scenes':
                cursor.execute("SELECT * FROM files WHERE chapter_id = ? AND (file_type = 'Scene' OR (file_type != 'Asset' AND (LOWER(name) LIKE '%_sc_%' OR LOWER(name) LIKE '%scene%') AND LOWER(name) NOT LIKE '%obd_scanner%')) ORDER BY id", (cid,))
            else:
                cursor.execute("SELECT * FROM files WHERE chapter_id = ? AND (file_type = 'Asset' OR (file_type != 'Scene' AND (LOWER(name) NOT LIKE '%_sc_%' AND LOWER(name) NOT LIKE '%scene%') OR LOWER(name) LIKE '%obd_scanner%')) ORDER BY id", (cid,))
            chapter_files_map[cid] = cursor.fetchall()
                
        cursor.execute("""
            SELECT fp.file_id, fp.step_name, fp.status, fp.points, fp.take_count, u.name as artist_name, u.username as artist_username, u.reports_to as artist_lead
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
                'take_count': row['take_count'] if 'take_count' in row.keys() and row['take_count'] is not None else 0,
                'artist_name': row['artist_name'],
                'artist_username': row['artist_username'],
                'artist_lead': row['artist_lead']
            }
        for cid, flist in list(chapter_files_map.items()):
            updated_flist = []
            for f_item in flist:
                f_dict = dict(f_item)
                f_dict['display_name'] = f_dict['name']
                updated_flist.append(f_dict)
            chapter_files_map[cid] = updated_flist

        files = []
        for cid, flist in chapter_files_map.items():
            files.extend(flist)

    asset_stages = ASSET_STAGES
    scene_stages = SCENE_STAGES_FULL
    active_stages = asset_stages if sub_tab == 'assets' else scene_stages

    pipeline_summary = {
        'sub_tab': sub_tab,
        'total_items': 0,
        'subtab_active_files': 0,
        'total_assets_count': 0,
        'total_scenes_count': 0,
        'total_yts': 0,
        'total_wip': 0,
        'total_review': 0,
        'total_rework': 0,
        'total_rtk': 0,
        'total_done': 0,
        'total_hold': 0,
        'total_open': 0,
        'total_pending': 0,
        'stage_stats': {stg: {'yts': 0, 'wip': 0, 'review': 0, 'rework': 0, 'rtk': 0, 'done': 0, 'hold': 0, 'open': 0, 'pending': 0} for stg in active_stages}
    }

    if view_tab == 'pipeline' or session['role'] in ['Admin', 'Lead', 'Artist']:
        active_chaps_files = []
        if chapter_id:
            active_chaps_files = chapter_files_map.get(int(chapter_id), chapter_files_map.get(str(chapter_id), []))
            if not active_chaps_files:
                for c_id, fl in chapter_files_map.items():
                    if str(c_id) == str(chapter_id):
                        active_chaps_files = fl
                        break
        else:
            for fl in chapter_files_map.values():
                active_chaps_files.extend(fl)

        total_file_count = len(active_chaps_files)
        pipeline_summary['total_items'] = total_file_count
        pipeline_summary['subtab_active_files'] = total_file_count

        if chapter_id:
            cursor.execute("""
                SELECT COUNT(DISTINCT f.id)
                FROM files f
                JOIN file_pipeline fp ON fp.file_id = f.id
                WHERE f.chapter_id = ? AND fp.step_name IN ('Reference', 'Explanation', 'Modeling', 'Texturing', 'Rig')
            """, (chapter_id,))
            pipeline_summary['total_assets_count'] = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT COUNT(DISTINCT f.id)
                FROM files f
                JOIN file_pipeline fp ON fp.file_id = f.id
                WHERE f.chapter_id = ? AND fp.step_name IN ('Voice Over', 'Narration', 'Storyboards', 'Explanation', 'Scene-wise Assets', 'Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering', '3D Comp & Motion Graphics')
            """, (chapter_id,))
            pipeline_summary['total_scenes_count'] = cursor.fetchone()[0] or 0
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT f.id)
                FROM files f
                JOIN chapters c ON f.chapter_id = c.id
                JOIN projects p ON c.project_id = p.id
                JOIN file_pipeline fp ON fp.file_id = f.id
                WHERE c.status = 'Active' AND p.status = 'Active'
                  AND fp.step_name IN ('Reference', 'Explanation', 'Modeling', 'Texturing', 'Rig')
            """)
            pipeline_summary['total_assets_count'] = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT COUNT(DISTINCT f.id)
                FROM files f
                JOIN chapters c ON f.chapter_id = c.id
                JOIN projects p ON c.project_id = p.id
                JOIN file_pipeline fp ON fp.file_id = f.id
                WHERE c.status = 'Active' AND p.status = 'Active'
                  AND fp.step_name IN ('Voice Over', 'Narration', 'Storyboards', 'Explanation', 'Scene-wise Assets', 'Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering', '3D Comp & Motion Graphics')
            """)
            pipeline_summary['total_scenes_count'] = cursor.fetchone()[0] or 0

        for file_obj in active_chaps_files:
            file_id_val = file_obj['id']
            file_matrix = matrix.get(file_id_val, {})
            is_comp_ai_file = file_obj.get('is_comp_ai', 0)
            file_statuses = []
            file_takes = []
            for stg in active_stages:
                # If file is Comp AI, skip counting stats for intermediate 3D stages
                if is_comp_ai_file == 1 and stg in ['Modeling', 'Texturing', 'Rig', 'Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering']:
                    continue
                cell_info = file_matrix.get(stg)
                if cell_info:
                    st = cell_info['status']
                    tk = cell_info['take_count']
                    file_statuses.append(st)
                    file_takes.append(tk)

                    if st in ['Hold', 'ON HOLD', 'On Hold', 'hold']:
                        pipeline_summary['stage_stats'][stg]['hold'] += 1
                    elif st in ['Pending', 'YTS', 'Yts', 'YTS / Open', 'Open']:
                        pipeline_summary['stage_stats'][stg]['yts'] += 1
                        if st == 'Open':
                            pipeline_summary['stage_stats'][stg]['open'] += 1
                    elif st in ['In Progress', 'WIP', 'Wip']:
                        pipeline_summary['stage_stats'][stg]['wip'] += 1
                        if st == 'Open':
                            pipeline_summary['stage_stats'][stg]['open'] += 1
                    elif st in ['Review', 'Final Review', 'Lead Review', 'Content Review']:
                        pipeline_summary['stage_stats'][stg]['review'] += 1
                    elif st in ['Rework', 'RTK', 'Re-take', 'Reject', 'Rejected']:
                        pipeline_summary['stage_stats'][stg]['rework'] += 1
                        pipeline_summary['stage_stats'][stg]['rtk'] += 1
                    elif st in ['Done', 'Approved']:
                        pipeline_summary['stage_stats'][stg]['done'] += 1

            if file_statuses and all(st in ['Done', 'Approved'] for st in file_statuses):
                pipeline_summary['total_done'] += 1
            elif any(st in ['Hold', 'ON HOLD', 'On Hold', 'hold'] for st in file_statuses):
                pipeline_summary['total_hold'] += 1
            elif any(st in ['Rework', 'RTK', 'Re-take', 'Reject', 'Rejected'] or (tk >= 1 and st not in ['Done', 'Approved']) for st, tk in zip(file_statuses, file_takes)):
                pipeline_summary['total_rework'] += 1
                pipeline_summary['total_rtk'] += 1
            elif any(st in ['Review', 'Final Review', 'Lead Review', 'Content Review'] for st in file_statuses):
                pipeline_summary['total_review'] += 1
            elif any(st in ['In Progress', 'WIP', 'Wip'] for st in file_statuses):
                pipeline_summary['total_wip'] += 1
            else:
                pipeline_summary['total_yts'] += 1
                pipeline_summary['total_pending'] += 1
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
            
    artists = []
    lead_queue = []
    queue_stage = None
    # Total reworks count across active files
    cursor.execute("SELECT COUNT(*) FROM file_pipeline WHERE take_count >= 1 OR status = 'Rework' OR rework_reason IS NOT NULL")
    tot_reworks_row = cursor.fetchone()
    total_reworks_count = tot_reworks_row[0] if tot_reworks_row else 0
    
    if session['role'] in ['Lead', 'Admin']:
        queue_stage = request.args.get('queue_stage')
        if not queue_stage:
            if session['role'] == 'Lead':
                for stage, team in STAGE_TEAMS.items():
                    if team == session['team']:
                        queue_stage = stage
                        break
            if not queue_stage:
                queue_stage = 'Reference' if sub_tab == 'assets' else 'Voice Over'

        if queue_stage:
            if queue_stage == 'Content':
                order_clause = "f.id ASC"
            else:
                order_clause = "f.content_released_at ASC, f.id ASC"

            # Determine extra queue filters (Asset vs Scene files, and Comp AI exclusion for middle stages)
            extra_queue_where = ""
            if queue_stage in ['Reference', 'Explanation', 'Modeling', 'Texturing', 'Rig']:
                extra_queue_where += " AND (f.file_type = 'Asset' OR (f.file_type != 'Scene' AND LOWER(f.name) NOT LIKE '%_sc_%' AND LOWER(f.name) NOT LIKE '%scene%'))"
            elif queue_stage in ['Voice Over', 'Narration', 'Storyboards', 'Scene-wise Assets', 'Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering', '3D Comp & Motion Graphics']:
                extra_queue_where += " AND (f.file_type = 'Scene' OR (f.file_type != 'Asset' AND (LOWER(f.name) LIKE '%_sc_%' OR LOWER(f.name) LIKE '%scene%')))"

            if queue_stage in ['Modeling', 'Texturing', 'Rig', 'Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering']:
                extra_queue_where += " AND (f.is_comp_ai IS NULL OR f.is_comp_ai = 0)"

            lead_queue = []
            if sub_tab in ['assets', 'scenes'] and chapter_id:
                cursor.execute(f"""
                    SELECT f.id as file_id, f.name as file_name, f.description as file_desc, f.is_comp_ai,
                           fp.id as pipeline_id, fp.status as step_status, fp.assigned_to as step_assigned_to,
                           fp.points, fp.take_count, fp.rework_reason, fp.rework_target_team, f.content_released_at, p.name as project_name, c.name as chapter_name
                    FROM file_pipeline fp
                    JOIN files f ON fp.file_id = f.id
                    JOIN chapters c ON f.chapter_id = c.id
                    JOIN projects p ON c.project_id = p.id
                    WHERE f.chapter_id = ? AND fp.step_name = ?
                      AND (fp.assigned_to IS NULL OR fp.status IN ('Open', 'Yts'))
                      AND f.id NOT IN (SELECT file_id FROM daily_assignments WHERE status = 'Pending' AND file_id IS NOT NULL)
                      {extra_queue_where}
                    ORDER BY {order_clause}
                """, (chapter_id, queue_stage))
                lead_queue = cursor.fetchall()
            else:
                cursor.execute(f"""
                    SELECT f.id as file_id, f.name as file_name, f.description as file_desc, f.is_comp_ai,
                           fp.id as pipeline_id, fp.status as step_status, fp.assigned_to as step_assigned_to,
                           fp.points, fp.take_count, fp.rework_reason, fp.rework_target_team, f.content_released_at, p.name as project_name, c.name as chapter_name
                    FROM file_pipeline fp
                    JOIN files f ON fp.file_id = f.id
                    JOIN chapters c ON f.chapter_id = c.id
                    JOIN projects p ON c.project_id = p.id
                    WHERE c.status = 'Active' AND p.status = 'Active' AND fp.step_name = ?
                      AND (fp.assigned_to IS NULL OR fp.status IN ('Open', 'Yts'))
                      AND f.id NOT IN (SELECT file_id FROM daily_assignments WHERE status = 'Pending' AND file_id IS NOT NULL)
                      {extra_queue_where}
                    ORDER BY {order_clause}
                """, (queue_stage,))
                lead_queue = cursor.fetchall()
            
            if session['role'] == 'Lead':
                cursor.execute("SELECT id, name, username, role FROM users WHERE team = ? AND role IN ('Artist', 'Lead') ORDER BY role DESC, name ASC", (session['team'],))
                artists = cursor.fetchall()
            else:
                target_team = STAGE_TEAMS.get(queue_stage, 'Content')
                cursor.execute("SELECT id, name, username, role FROM users WHERE team = ? AND role IN ('Artist', 'Lead') ORDER BY role DESC, name ASC", (target_team,))
                artists = cursor.fetchall()

    validation_list = []
    if session['role'] in ['Lead', 'Admin']:
        target_team = session['team'] if session['role'] == 'Lead' else STAGE_TEAMS.get(queue_stage)
        if target_team:
            cursor.execute("""
                SELECT da.id as assignment_id, da.date as assigned_date, da.points, da.status as assignment_status, da.task_description, da.remarks, da.submit_time, da.submitted_at,
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
    artist_upcoming_tasks = []
    if session['role'] == 'Artist':
        cursor.execute("""
            SELECT da.id as assignment_id, da.date as assigned_date, da.task_description, da.points, da.status as assignment_status,
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

        cursor.execute("""
            SELECT da.id as assignment_id, da.date as assigned_date, da.task_description, da.points, da.status as assignment_status,
                   f.id as file_id, f.name as file_name, f.description as file_desc,
                   p.name as project_name, c.name as chapter_name
            FROM daily_assignments da
            JOIN files f ON da.file_id = f.id
            JOIN chapters c ON f.chapter_id = c.id
            JOIN projects p ON c.project_id = p.id
            WHERE da.user_id = ? AND da.date > ? AND da.status = 'Pending'
            ORDER BY da.date ASC, p.name, c.name, f.name
        """, (session['user_id'], today_str))
        artist_upcoming_tasks = cursor.fetchall()

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
        
    pending_approvals_count = 0
    attendance_ratio = "N/A"
    if session['role'] == 'Artist':
        chart_stages = [stage for stage, team in STAGE_TEAMS.items() if team == session['team']]
        if not chart_stages:
            chart_stages = ['Animation']
    else:
        chart_stages = [
            'Content', 'Modeling', 'Texturing', 'Rig', 'Animation', 
            'FBX export', 'VFX', 'Lightning', 'Rendering', '3D Comp & Motion Graphics'
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
        performance_data.append({'name': session.get('name', session.get('username', 'Artist')), 'target': tgt, 'earned': earned})
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
    artist_att_stats = None
    hr_attendance_stats = None
    hr_leave_summary = None

    # Team Incoming / Open Queue & Completed / Handed Off Tab + Today's Upload Log
    user_team = session.get('team', '')
    team_open_queue = get_team_open_queue(db, user_team) if user_team else []
    team_completed_queue = []
    today_upload_log = None
    if user_team:
        cursor.execute("""
            SELECT fp.file_id, fp.step_name, fp.status, fp.complexity, fp.points, fp.time_worked,
                   fp.end_date, fp.submitted_at, fp.remarks,
                   f.name AS file_name, p.name AS project_name, c.name AS chapter_name, u.name AS artist_name
            FROM file_pipeline fp
            JOIN files f ON fp.file_id = f.id
            JOIN chapters c ON f.chapter_id = c.id
            JOIN projects p ON c.project_id = p.id
            LEFT JOIN users u ON fp.assigned_to = u.id
            WHERE fp.team_name = ? AND fp.status = 'Done'
            ORDER BY fp.submitted_at DESC, fp.id DESC
            LIMIT 100
        """, (user_team,))
        team_completed_queue = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT l.*, u.name AS uploader_name
            FROM daily_upload_logs l
            JOIN teams t ON l.team_id = t.id
            JOIN users u ON l.uploaded_by = u.id
            WHERE t.name = ? AND l.upload_date = ?
            ORDER BY l.id DESC LIMIT 1
        """, (user_team, today_str))
        today_upload_log = cursor.fetchone()

    recent_logs = []
    if session['role'] == 'Admin':
        cursor.execute("""
            SELECT l.action, l.timestamp, l.details, u.name as user_name 
            FROM activity_log l 
            LEFT JOIN users u ON l.user_id = u.id 
            ORDER BY l.id DESC LIMIT 15
        """)
        recent_logs = cursor.fetchall()
        
    lead_absent_info = is_lead_absent_today(db, session.get('team')) if session.get('team') else None
    pending_self_logs = []
    if session.get('role') in ['Admin', 'Lead']:
        if session['role'] == 'Admin':
            cursor.execute("SELECT * FROM self_logged_work WHERE approval_status = 'Pending' ORDER BY id DESC")
        else:
            cursor.execute("SELECT * FROM self_logged_work WHERE team = ? AND approval_status = 'Pending' ORDER BY id DESC", (session['team'],))
        pending_self_logs = [dict(r) for r in cursor.fetchall()]
        
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
        sheet_view=sheet_view,
        lead_queue=lead_queue,
        queue_stage=queue_stage,
        total_reworks_count=total_reworks_count,
        artists=artists,
        artist_tasks=artist_tasks,
        artist_upcoming_tasks=artist_upcoming_tasks,
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
        pipeline_summary=pipeline_summary,
        lead_absent_info=lead_absent_info,
        pending_self_logs=pending_self_logs,
        team_open_queue=team_open_queue,
        team_completed_queue=team_completed_queue,
        today_upload_log=today_upload_log,
        production_teams=PRODUCTION_TEAMS
    )

@app.route('/project/add', methods=['POST'])
def add_project():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session['role'] not in ['Admin', 'Lead']:
        flash("Unauthorized to create projects.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    project_type = request.form.get('project_type', 'Standard').strip()
    
    if not name:
        flash("Project name is required.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO projects (name, description, status, project_type)
            VALUES (?, ?, 'Active', ?)
        """, (name, description, project_type))
        proj_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO chapters (project_id, name, description, status)
            VALUES (?, ?, 'Default Chapter', 'Active')
        """, (proj_id, f"{name} Chapter"))
        
        db.commit()
        flash(f"Project '{name}' ({project_type}) created successfully.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error creating project: {e}", "error")
        
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/file/add', methods=['POST'])
def add_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    
    chapter_id = request.form.get('chapter_id', type=int)
    project_id = request.form.get('project_id', type=int)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    project_category = request.form.get('project_category', '').strip()
    points = request.form.get('points', type=int, default=0)
    
    if project_id and not chapter_id:
        cursor.execute("SELECT id FROM chapters WHERE project_id = ? LIMIT 1", (project_id,))
        ch_row = cursor.fetchone()
        if ch_row:
            chapter_id = ch_row['id']
            
    proj_info = None
    if chapter_id:
        cursor.execute("""
            SELECT p.id as project_id, p.name as project_name, p.project_type
            FROM chapters c
            JOIN projects p ON c.project_id = p.id
            WHERE c.id = ?
        """, (chapter_id,))
        proj_info = cursor.fetchone()

    is_promo_project = False
    if proj_info and (proj_info['project_type'] == 'Promo Videos' or proj_info['project_name'] == 'Promo Videos'):
        is_promo_project = True
    elif project_category and project_category.lower() == 'promo videos':
        is_promo_project = True

    if is_promo_project:
        # Restriction 1: Only Lead or Admin (NO Artists)
        if session['role'] not in ['Admin', 'Lead']:
            flash("Only Team Leads and Admins can add files to Promo Videos projects.", "error")
            return redirect(request.referrer or url_for('dashboard'))
            
        # Restriction 2: All 5 Mandatory Fields Required
        raw_stages = request.form.getlist('custom_stages')
        clean_stages = []
        for item in raw_stages:
            if ',' in item:
                clean_stages.extend([s.strip() for s in item.split(',') if s.strip()])
            elif item.strip():
                clean_stages.append(item.strip())
        
        if not name or not project_category or not description or points <= 0 or not clean_stages:
            flash("All 5 mandatory fields are required to create a Promo Video file: File Name, Project Category, Description, Complexity Points (> 0), and Dynamic Stage Sequence.", "error")
            return redirect(request.referrer or url_for('dashboard'))
            
        # Restriction 3: '3D Comp & Motion Graphics' MUST ALWAYS be the final stage
        final_stage = '3D Comp & Motion Graphics'
        clean_stages = [s for s in clean_stages if s != final_stage]
        clean_stages.append(final_stage)
        
        try:
            cursor.execute("""
                INSERT INTO files (chapter_id, name, description, project_category, status)
                VALUES (?, ?, ?, ?, 'Pending')
            """, (chapter_id, name, description, project_category))
            file_id = cursor.lastrowid
            
            for idx, stage in enumerate(clean_stages):
                status = 'Open' if idx == 0 else 'Pending'
                cursor.execute("""
                    INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points)
                    VALUES (?, ?, ?, NULL, ?)
                """, (file_id, stage, status, points))
                
            cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Create Promo Video File', ?)",
                           (session['user_id'], f"Created Promo Video file '{name}' in Category '{project_category}' with {len(clean_stages)} custom stages ending at {final_stage}"))
            db.commit()
            recalculate_file_metadata(db, file_id)
            flash(f"Promo Video file '{name}' created successfully with {len(clean_stages)} custom stages ending at 3D Comp & Motion Graphics.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error creating Promo Video file: {e}", "error")
            
        return redirect(request.referrer or url_for('dashboard'))

    # Standard project file creation: Only Content Team Lead can add files
    if not (session['role'] == 'Lead' and session['team'] == 'Content'):
        flash("Only Content Team Lead can add files to the asset and scene pipeline.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    if not chapter_id or not name:
        flash("File name and chapter are required.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    sub_tab = request.form.get('sub_tab', 'assets')
    
    try:
        cursor.execute("""
            INSERT INTO files (chapter_id, name, description, status)
            VALUES (?, ?, ?, 'Pending')
        """, (chapter_id, name, description))
        file_id = cursor.lastrowid
        
        for stage in PIPELINE_STAGES:
            if sub_tab == 'scenes':
                status = 'Open' if stage == 'Voice Over' else 'Pending'
            else:
                status = 'Open' if stage == 'Reference' else 'Pending'
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

@app.route('/files/<int:file_id>/rename', methods=['POST'])
@app.route('/files/rename', methods=['POST'])
@app.route('/files/edit-name/<int:file_id>', methods=['POST'])
def rename_file(file_id=None):
    if 'user_id' not in session:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Unauthorized'}), 401
        return redirect(url_for('login'))

    # STRICT PERMISSION: ONLY Content team members (Lead and members whose team == 'Content') can rename a file/scene once set.
    user_team = session.get('team')
    if user_team != 'Content':
        err_msg = "Forbidden: ONLY the Content team (its Lead and members) can rename a file/scene once it's been set."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': err_msg}), 403
        flash(err_msg, "error")
        return redirect(request.referrer or url_for('dashboard'))

    if not file_id:
        file_id = request.form.get('file_id', type=int)
        if not file_id and request.is_json:
            file_id = request.json.get('file_id')

    new_name = (request.form.get('new_name') or request.form.get('name') or '').strip()
    if request.is_json and not new_name:
        new_name = (request.json.get('new_name') or request.json.get('name') or '').strip()

    if not file_id or not new_name:
        err_msg = "File ID and new file name are required."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': err_msg}), 400
        flash(err_msg, "error")
        return redirect(request.referrer or url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    file_row = cursor.fetchone()
    if not file_row:
        err_msg = "File not found."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': err_msg}), 404
        flash(err_msg, "error")
        return redirect(request.referrer or url_for('dashboard'))

    old_name = file_row['name']

    try:
        cursor.execute("UPDATE files SET name = ? WHERE id = ?", (new_name, file_id))
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Rename File', ?)",
                       (session['user_id'], f"Renamed file ID {file_id} from '{old_name}' to '{new_name}'."))
        db.commit()

        recalculate_file_metadata(db, file_id)

        msg = f"File successfully renamed from '{old_name}' to '{new_name}'."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': msg, 'new_name': new_name, 'file_id': file_id})
        flash(msg, "success")
        return redirect(request.referrer or url_for('dashboard'))
    except Exception as e:
        db.rollback()
        err_msg = f"Error renaming file: {e}"
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': err_msg}), 500
        flash(err_msg, "error")
        return redirect(request.referrer or url_for('dashboard'))


@app.route('/files/<int:file_id>/assign-comp-ai', methods=['POST'])
def assign_comp_ai(file_id):
    if 'user_id' not in session:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Unauthorized'}), 401
        return redirect(url_for('login'))

    # ONLY Content team members can assign 2D Comp AI
    user_team = session.get('team')
    if user_team != 'Content':
        err_msg = "Forbidden: Only Content team can assign 2D Comp AI."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': err_msg}), 403
        flash(err_msg, "error")
        return redirect(request.referrer or url_for('dashboard'))

    comp_ai_artist_id = request.form.get('comp_ai_artist_id', type=int)
    if not comp_ai_artist_id and request.is_json:
        comp_ai_artist_id = request.json.get('comp_ai_artist_id')

    if not comp_ai_artist_id:
        err_msg = "Please select an artist from 3D Comp & Motion Graphics team."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': err_msg}), 400
        flash(err_msg, "error")
        return redirect(request.referrer or url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()

    # Check file existence
    cursor.execute("SELECT id, name, file_type FROM files WHERE id = ?", (file_id,))
    file_row = cursor.fetchone()
    if not file_row:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'File not found'}), 404
        flash("File not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))

    # Mark file as is_comp_ai = 1 and comp_ai_artist_id = comp_ai_artist_id
    current_name = file_row['name'] or ''
    if 'compo' not in current_name.lower() and 'comp ai' not in current_name.lower():
        new_name = f"{current_name}_compo_AI"
        cursor.execute("UPDATE files SET is_comp_ai = 1, comp_ai_artist_id = ?, name = ? WHERE id = ?", (comp_ai_artist_id, new_name, file_id))
    else:
        cursor.execute("UPDATE files SET is_comp_ai = 1, comp_ai_artist_id = ? WHERE id = ?", (comp_ai_artist_id, file_id))

    # In file_pipeline:
    # 1. Mark intermediate 3D stages ('Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering') as status = 'Done' (bypassed)
    bypassed_stages = ['Animation', 'FBX export', 'VFX', 'Lightning', 'Rendering']
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    for b_stage in bypassed_stages:
        cursor.execute("""
            UPDATE file_pipeline
            SET status = 'Done', remarks = 'Bypassed for 2D Comp AI', end_date = ?
            WHERE file_id = ? AND step_name = ? AND status != 'Done'
        """, (today_str, file_id, b_stage))

    # 2. Mark 3D Comp & Motion Graphics stage as Open and assigned to comp_ai_artist_id
    cursor.execute("""
        UPDATE file_pipeline
        SET status = 'Open', assigned_to = ?, start_date = ?
        WHERE file_id = ? AND step_name = '3D Comp & Motion Graphics'
    """, (comp_ai_artist_id, today_str, file_id))

    # 3. Update active file assignment to comp_ai_artist_id
    cursor.execute("UPDATE files SET assigned_to = ? WHERE id = ?", (comp_ai_artist_id, file_id))

    db.commit()
    recalculate_file_metadata(db, file_id)

    msg = "File successfully marked as 2D Comp AI and assigned to 3D Comp & Motion Graphics artist!"
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': msg})

    flash(msg, "success")
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/files/<int:file_id>/details', methods=['GET'])
def get_file_details(file_id):
    if 'user_id' not in session:
        return {'error': 'Unauthorized'}, 401

    db = get_db()
    
    # Recalculate dynamic metadata on get details request
    recalculate_file_metadata(db, file_id)
    
    cursor = db.cursor()
    # Query file details
    cursor.execute("""
        SELECT f.id, f.name, f.file_type, f.description, f.chapter_id, f.assigned_to, f.start_date, f.end_date, f.remarks, f.final_approval_date,
               f.internal_lead_status, f.internal_content_status, f.final_review_status, f.status,
               f.rework_reason, f.rework_target_team, f.hold_reason, f.is_comp_ai, f.comp_ai_artist_id,
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
    
    # Fetch project assets and scene-wise asset references
    cursor.execute("""
        SELECT DISTINCT f.id, f.name
        FROM files f
        JOIN chapters c ON f.chapter_id = c.id
        JOIN file_pipeline fp ON fp.file_id = f.id
        WHERE c.project_id = (SELECT c2.project_id FROM files f2 JOIN chapters c2 ON f2.chapter_id = c2.id WHERE f2.id = ?)
          AND fp.step_name IN ('Modeling', 'Reference')
    """, (file_id,))
    project_assets = [dict(r) for r in cursor.fetchall()]
    file_data['project_assets'] = project_assets
    
    cursor.execute("SELECT remarks FROM file_pipeline WHERE file_id = ? AND step_name = 'Scene-wise Assets'", (file_id,))
    swa_row = cursor.fetchone()
    file_data['used_assets'] = swa_row['remarks'] if swa_row and swa_row['remarks'] else ''
    
    # Fetch all pipeline steps for this file
    cursor.execute("""
        SELECT fp.step_name, fp.status, fp.assigned_to, fp.points, fp.start_date, fp.end_date, fp.remarks, fp.submitted_at, fp.rework_reason, fp.rework_target_team, fp.hold_reason,
               u.name as artist_name, u.username as artist_username, u.team as artist_team
        FROM file_pipeline fp
        LEFT JOIN users u ON fp.assigned_to = u.id
        WHERE fp.file_id = ?
    """, (file_id,))
    pipeline_steps = [dict(r) for r in cursor.fetchall()]
    
    # Filter & sort steps by exact file pipeline sequence (Asset stages for Assets, Scene stages for Scenes)
    seq_stages = get_file_pipeline_sequence(db, file_id)
    steps_map = {s['step_name']: s for s in pipeline_steps}
    sorted_steps = []
    for stage in seq_stages:
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

    file_data['active_stage'] = active_stage
    file_data['pending_team'] = pending_team

    raw_name = file_data['name']
    clean_base = get_clean_base_name(raw_name)
    
    # Take count & retake versioning details (Take 0 = Original File, Take 1 = 1st Rework)
    cursor.execute("SELECT COUNT(*) FROM rtk_history WHERE file_id = ?", (file_id,))
    current_take = cursor.fetchone()[0] or 0
    file_data['take_count'] = current_take

    dynamic_name = compute_file_display_name(clean_base, current_take)
    file_data['dynamic_name'] = dynamic_name

    # Format 12-hour submission time if final_approval_date or end_date exists
    sub_time_12 = ""
    if file_data['final_approval_date']:
        try:
            parts = file_data['final_approval_date'].split(' ')
            if len(parts) > 1:
                t_str = _time12_filter(parts[1])
                sub_time_12 = f"{parts[0]} {t_str}"
            else:
                sub_time_12 = parts[0]
        except Exception:
            sub_time_12 = file_data['final_approval_date']
    file_data['submission_time_12'] = sub_time_12

    # Build side-by-side original vs retake versions
    file_data['original_version'] = {
        'name': raw_name,
        'start_date': file_data['start_date'] or 'N/A',
        'end_date': file_data['end_date'] or 'N/A',
        'status': 'Original File'
    }
    
    file_data['retake_version'] = {
        'name': raw_name if current_take == 0 else f"{raw_name}_take{current_take}",
        'take_label': 'Original File' if current_take == 0 else f"Take {current_take} (Rework)",
        'is_rework': (current_take >= 1 or bool(file_data.get('rework_reason'))),
        'start_date': target_step['start_date'] if target_step and target_step['start_date'] else (file_data['start_date'] or 'N/A'),
        'end_date': target_step['end_date'] if target_step and target_step['end_date'] else (file_data['end_date'] or 'N/A'),
        'status': file_data['status'],
        'submission_time_12': sub_time_12
    }

    # Fetch Comp AI artist details if assigned
    comp_ai_artist_name = ""
    comp_ai_artist_username = ""
    if file_data.get('comp_ai_artist_id'):
        cursor.execute("SELECT name, username FROM users WHERE id = ?", (file_data['comp_ai_artist_id'],))
        ca_row = cursor.fetchone()
        if ca_row:
            comp_ai_artist_name = ca_row['name']
            comp_ai_artist_username = ca_row['username']
    file_data['comp_ai_artist_name'] = comp_ai_artist_name
    file_data['comp_ai_artist_username'] = comp_ai_artist_username

    # Calculate initial start date from first team stage
    first_start_date = file_data.get('start_date') or ""
    if sorted_steps:
        for stp in sorted_steps:
            if stp.get('start_date'):
                first_start_date = stp['start_date']
                break
    file_data['first_team_start_date'] = first_start_date or 'N/A'

    # Fetch RTK history records
    cursor.execute("""
        SELECT id, file_id, take_number, stage_name, target_team, assigned_to,
               assigned_to_name, assigned_to_username, old_file_name, new_file_name,
               reason, created_at, created_by, created_by_name
        FROM rtk_history
        WHERE file_id = ?
        ORDER BY take_number ASC, id ASC
    """, (file_id,))
    rtk_history_rows = [dict(r) for r in cursor.fetchall()]

    latest_rework_info = None
    if rtk_history_rows:
        last_rtk = rtk_history_rows[-1]
        latest_rework_info = {
            'take_number': last_rtk['take_number'],
            'origin_lead': last_rtk['created_by_name'] or 'Team Lead',
            'target_team': last_rtk['target_team'] or 'N/A',
            'reason': last_rtk['reason'] or 'Rework Requested',
            'created_at': last_rtk['created_at']
        }
    file_data['latest_rework_info'] = latest_rework_info

    # Fetch all artists for dropdown selection
    cursor.execute("SELECT id, name, username, team FROM users WHERE role = 'Artist' ORDER BY name")
    artists_list = [dict(r) for r in cursor.fetchall()]

    # Fetch 3D Comp & Motion Graphics artists for 2D Comp AI assignment
    cursor.execute("SELECT id, name, username, team FROM users WHERE team = '3D Comp & Motion Graphics' ORDER BY name")
    comp_artists = [dict(r) for r in cursor.fetchall()]
    
    # Return everything including metadata about the current user and the pipeline steps
    return {
        'file': file_data,
        'pipeline_steps': sorted_steps,
        'rtk_history': rtk_history_rows,
        'artists': artists_list,
        'comp_artists': comp_artists,
        'current_user': {
            'username': session['username'],
            'role': session['role'],
            'team': session['team']
        }
    }


@app.route('/files/<int:file_id>/save-scene-assets', methods=['POST'])
def save_scene_assets(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    
    asset_names = request.form.getlist('asset_names')
    asset_str = request.form.get('asset_str', '').strip()
    if not asset_str and asset_names:
        asset_str = ", ".join(asset_names)
        
    cursor.execute("""
        UPDATE file_pipeline
        SET remarks = ?
        WHERE file_id = ? AND step_name = 'Scene-wise Assets'
    """, (asset_str, file_id))
    db.commit()
    
    flash(f"Referenced assets for scene updated to: {asset_str}", "success")
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/files/<int:file_id>/stage-status', methods=['POST'])
def update_stage_status(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    
    step_name = request.form.get('step_name', '').strip()
    new_status = request.form.get('status', '').strip()
    hold_reason = request.form.get('hold_reason', '').strip()
    
    cursor.execute("""
        SELECT fp.id, fp.assigned_to, fp.points, f.name as file_name 
        FROM file_pipeline fp
        JOIN files f ON fp.file_id = f.id
        WHERE fp.file_id = ? AND fp.step_name = ?
    """, (file_id, step_name))
    pipeline_step = cursor.fetchone()
    
    if not pipeline_step:
        flash("Pipeline step not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    target_team = STAGE_TEAMS.get(step_name)
    is_lead = (session['role'] == 'Lead' and session['team'] == target_team)
    is_admin = (session['role'] == 'Admin')
    
    if not (is_lead or is_admin):
        flash("Unauthorized: Only Leads and Admins can update stage status directly.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    if new_status in ['Hold', 'hold', 'ON HOLD']:
        if not hold_reason:
            flash("Hold reason is required when placing a stage on Hold.", "error")
            return redirect(request.referrer or url_for('dashboard'))
        final_status = 'Hold'
    elif new_status in ['Yts', 'YTS', 'Pending']:
        final_status = 'Yts'
    elif new_status in ['Wip', 'WIP', 'In Progress', 'Open']:
        final_status = 'Wip'
    elif new_status in ['Review', 'Lead Review']:
        final_status = 'Review'
    elif new_status in ['RTK', 'Rework', 'Re-take']:
        final_status = 'RTK'
    elif new_status in ['Done', 'Approved']:
        final_status = 'Done'
    else:
        final_status = new_status

    today_str = datetime.date.today().strftime('%Y-%m-%d')
    now_full_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if final_status == 'Hold':
        cursor.execute("""
            UPDATE file_pipeline 
            SET status = 'Hold', hold_reason = ?, remarks = COALESCE(remarks, ?)
            WHERE file_id = ? AND step_name = ?
        """, (hold_reason, f"On Hold: {hold_reason}", file_id, step_name))
        cursor.execute("UPDATE files SET hold_reason = ? WHERE id = ?", (hold_reason, file_id))
    elif final_status == 'RTK':
        record_rtk_event(db, file_id, step_name, hold_reason or "Rework Requested")
    elif final_status == 'Done':
        cursor.execute("""
            UPDATE file_pipeline 
            SET status = 'Done', start_date = COALESCE(start_date, ?), end_date = COALESCE(end_date, ?), submitted_at = ?
            WHERE file_id = ? AND step_name = ?
        """, (today_str, today_str, now_full_str, file_id, step_name))
    elif final_status == 'Wip':
        cursor.execute("""
            UPDATE file_pipeline 
            SET status = 'Wip', start_date = COALESCE(start_date, ?)
            WHERE file_id = ? AND step_name = ?
        """, (today_str, file_id, step_name))
    else:
        cursor.execute("""
            UPDATE file_pipeline 
            SET status = ?
            WHERE file_id = ? AND step_name = ?
        """, (final_status, file_id, step_name))

    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Stage Status Update', ?)",
                   (session['user_id'], f"Updated stage '{step_name}' status for file ID {file_id} to '{final_status}'" + (f" (Reason: {hold_reason})" if final_status == 'Hold' else "")))
    db.commit()

    recalculate_file_metadata(db, file_id)
    flash(f"Status for '{pipeline_step['file_name']}' [{step_name}] updated to '{final_status}'.", "success")
    return redirect(request.referrer or url_for('dashboard'))


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
        rework_team = request.form.get('rework_team', '').strip()
        rework_reason = request.form.get('rework_reason', '').strip()

        def apply_review_rework(target_team_name, reason_text):
            target_stg = None
            for stg, tm in STAGE_TEAMS.items():
                if tm.lower() == target_team_name.lower():
                    target_stg = stg
                    break
            if not target_stg:
                target_stg = 'Modeling'

            record_rtk_event(db, file_id, target_stg, reason_text, target_team_name)

            cursor.execute("""
                UPDATE files 
                SET internal_lead_status = 'Pending', 
                    internal_content_status = 'Pending', 
                    final_review_status = 'Pending',
                    rework_reason = ?, 
                    rework_target_team = ?
                WHERE id = ?
            """, (reason_text, target_team_name, file_id))

            cursor.execute("SELECT id FROM users WHERE team = ? AND role = 'Lead'", (target_team_name,))
            target_leads = cursor.fetchall()
            for tl in target_leads:
                _push_notification(db, tl['id'], "Rework Assigned to Your Team", 
                                   f"File '{file_row['name']}' sent for Rework to {target_team_name} team by {session['name']}. Reason: {reason_text}", 
                                   "approval", link=url_for('dashboard'))

        # 1. Respective team lead review
        if lead_review_action:
            if session['role'] == 'Admin' or (session['role'] == 'Lead' and artist_lead == session['username']):
                if lead_review_action == 'Approve':
                    cursor.execute("UPDATE files SET internal_lead_status = 'Approved' WHERE id = ?", (file_id,))
                elif lead_review_action == 'Reject':
                    cursor.execute("UPDATE files SET internal_lead_status = 'Rejected' WHERE id = ?", (file_id,))
                    if rework_team:
                        apply_review_rework(rework_team, rework_reason or "Lead requested rework")
                db.commit()
                cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Review Action', ?)",
                               (session['user_id'], f"Team Lead set Lead Review for file ID {file_id} to '{lead_review_action}'"))
                db.commit()
                
        # 2. Content lead review
        if content_review_action:
            if session['role'] == 'Admin' or (session['role'] == 'Lead' and session['username'] == 'pooja'):
                if content_review_action == 'Approve':
                    cursor.execute("UPDATE files SET internal_content_status = 'Approved' WHERE id = ?", (file_id,))
                elif content_review_action == 'Reject':
                    cursor.execute("UPDATE files SET internal_content_status = 'Rejected' WHERE id = ?", (file_id,))
                    if rework_team:
                        apply_review_rework(rework_team, rework_reason or "Content Lead requested rework")
                db.commit()
                cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Review Action', ?)",
                               (session['user_id'], f"Content Lead set Content Review for file ID {file_id} to '{content_review_action}'"))
                db.commit()
                
        # 3. Final review
        if final_review_action:
            if session['role'] == 'Admin':
                if final_review_action == 'Approve':
                    today_str = datetime.date.today().strftime('%Y-%m-%d')
                    cursor.execute("""
                        UPDATE files 
                        SET final_review_status = 'Approved', status = 'Done', final_approval_date = COALESCE(final_approval_date, ?) 
                        WHERE id = ?
                    """, (today_str, file_id))
                elif final_review_action == 'Reject':
                    cursor.execute("UPDATE files SET final_review_status = 'Rejected' WHERE id = ?", (file_id,))
                    if rework_team:
                        apply_review_rework(rework_team, rework_reason or "Admin requested rework")
                db.commit()
                cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Review Action', ?)",
                               (session['user_id'], f"Admin set Final Review for file ID {file_id} to '{final_review_action}'"))
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
    deadline_days = request.form.get('deadline_days', type=int, default=0)
    end_date = request.form.get('end_date', '').strip()
    
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
    
    cursor.execute("SELECT points, take_count, rework_reason FROM file_pipeline WHERE file_id = ? AND step_name = ?", (file_id, step_name))
    existing_step = cursor.fetchone()
    existing_points = existing_step['points'] if existing_step and existing_step['points'] else 0
    take_count = existing_step['take_count'] if existing_step and existing_step['take_count'] is not None else 0
    rework_reason = existing_step['rework_reason'] if existing_step else None
    
    is_rework = (take_count >= 1) or bool(rework_reason)
    
    if artist_id:
        if is_rework and existing_points > 0:
            points = existing_points  # Points locked on Retake / Rework
        elif points <= 0:
            flash("A file stage cannot be assigned to an artist or lead until complexity points are specified (> 0).", "error")
            return redirect(request.referrer or url_for('dashboard'))
            
        if deadline_days > 0:
            end_date = (datetime.date.today() + datetime.timedelta(days=deadline_days)).strftime('%Y-%m-%d')
        elif not end_date:
            deadline_days = 1
            end_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            
        cursor.execute("SELECT name, team, role FROM users WHERE id = ?", (artist_id,))
        artist = cursor.fetchone()
        if not artist or artist['role'] not in ['Artist', 'Lead'] or artist['team'] != target_team:
            flash("Selected user is not an Artist or Lead of this team.", "error")
            return redirect(request.referrer or url_for('dashboard'))
        artist_name = artist['name']
        new_status = 'In Progress'
    else:
        artist_name = "Unassigned"
        new_status = 'Open'
        points = existing_points
        
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
                    SET points = ?, status = 'Pending', task_description = ?, deadline_days = ?
                    WHERE id = ?
                """, (points, f"{step_name}: {f_info['name']}", deadline_days, exist_da['id']))
            else:
                cursor.execute("""
                    INSERT INTO daily_assignments (user_id, date, file_id, task_description, points, status, deadline_days)
                    VALUES (?, ?, ?, ?, ?, 'Pending', ?)
                """, (artist_id, today_str, file_id, f"{step_name}: {f_info['name']}", points, deadline_days))
                
        if artist_id:
            _push_notification(db, artist_id, "New task assigned", f"You have been assigned: '{f_info['name']}' ({step_name}) with {points} points. Deadline: {deadline_days} day(s).", "task", link=url_for('dashboard'))
            
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Assign File', ?)",
                       (session['user_id'], f"Assigned '{f_info['name']}' [{step_name}] to {artist_name} (Points: {points}, Deadline: {deadline_days} days)"))
        db.commit()
        
        # Recalculate file metadata
        recalculate_file_metadata(db, file_id)
        
        flash(f"File updated: {f_info['name']} assigned to {artist_name} with {points} complexity points (Deadline: {deadline_days} days).", "success")

    except Exception as e:
        db.rollback()
        flash(f"Error assigning file: {e}", "error")
        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/lead/pre-assign-work', methods=['POST'])
def pre_assign_work():
    if 'user_id' not in session or session.get('role') != 'Lead':
        flash("Unauthorized: Only Leads can pre-assign work.", "error")
        return redirect(url_for('login'))

    from_date = request.form.get('from_date', '').strip()
    to_date = request.form.get('to_date', '').strip()
    file_id = request.form.get('file_id', type=int)
    artist_id = request.form.get('artist_id', type=int)
    points = request.form.get('points', type=int, default=0)
    task_description = request.form.get('task_description', '').strip()

    if not from_date or not to_date or not file_id or not artist_id:
        flash("Please select From Date, To Date, File, and Artist.", "error")
        return redirect(request.referrer or url_for('dashboard'))

    try:
        d_start = datetime.datetime.strptime(from_date, '%Y-%m-%d').date()
        d_end = datetime.datetime.strptime(to_date, '%Y-%m-%d').date()
    except Exception:
        flash("Invalid date format. Please select valid dates.", "error")
        return redirect(request.referrer or url_for('dashboard'))

    if d_start > d_end:
        flash("From Date cannot be after To Date.", "error")
        return redirect(request.referrer or url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT f.id, f.name, f.chapter_id, c.name as chapter_name FROM files f JOIN chapters c ON f.chapter_id = c.id WHERE f.id = ?", (file_id,))
    f_info = cursor.fetchone()
    if not f_info:
        flash("Selected file not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))

    cursor.execute("SELECT name FROM users WHERE id = ?", (artist_id,))
    art_row = cursor.fetchone()
    artist_name = art_row['name'] if art_row else 'Artist'

    lead_stage = None
    for stage, team in STAGE_TEAMS.items():
        if team == session.get('team'):
            lead_stage = stage
            break

    full_task_desc = task_description if task_description else f"Pre-Assigned [{lead_stage or 'Task'}]: {f_info['name']}"

    curr_date = d_start
    assigned_count = 0
    while curr_date <= d_end:
        ds_str = curr_date.strftime('%Y-%m-%d')
        assigned_count += 1

        cursor.execute("""
            SELECT id FROM daily_assignments
            WHERE file_id = ? AND status = 'Pending'
        """, (file_id,))
        exist = cursor.fetchone()

        if exist:
            cursor.execute("""
                UPDATE daily_assignments
                SET user_id = ?, date = ?, points = ?, status = 'Pending', task_description = ?
                WHERE id = ?
            """, (artist_id, ds_str, points, full_task_desc, exist['id']))
        else:
            cursor.execute("""
                INSERT INTO daily_assignments (user_id, date, file_id, task_description, points, status)
                VALUES (?, ?, ?, ?, ?, 'Pending')
            """, (artist_id, ds_str, file_id, full_task_desc, points))

        curr_date += datetime.timedelta(days=1)

    if lead_stage:
        cursor.execute("""
            UPDATE file_pipeline
            SET assigned_to = ?, points = ?, status = 'Open'
            WHERE file_id = ? AND step_name = ?
        """, (artist_id, points, file_id, lead_stage))

    _push_notification(db, artist_id, "Pre-Assigned Work Alert",
                       f"Work pre-assigned for dates {from_date} to {to_date}: '{f_info['name']}' ({points} pts).",
                       "task", link=url_for('dashboard'))

    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Pre-Assign Work', ?)",
                   (session['user_id'], f"Pre-assigned '{f_info['name']}' to {artist_name} for dates {from_date} to {to_date} (Points: {points})"))
    db.commit()

    recalculate_file_metadata(db, file_id)

    flash(f"Work pre-assigned successfully to {artist_name} for dates {from_date} to {to_date} ({assigned_count} days).", "success")
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
    
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    now_full_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    is_assigned = (pipeline_step['assigned_to'] == session['user_id'])
    if not is_assigned:
        cursor.execute("SELECT id FROM daily_assignments WHERE file_id = ? AND user_id = ? AND date = ?", (file_id, session['user_id'], today_str))
        if cursor.fetchone():
            is_assigned = True

    is_lead = (session['role'] == 'Lead' and session['team'] == target_team)
    is_admin = (session['role'] == 'Admin')
    
    if not (is_assigned or is_lead or is_admin):
        flash("Unauthorized to update status for this stage.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    hold_reason = request.form.get('hold_reason', '').strip()
    status_clean = status.strip()
    if status_clean in ['Hold', 'hold', 'ON HOLD']:
        status_clean = 'Hold'
        if not hold_reason:
            flash("Hold reason is required when placing a stage on Hold.", "error")
            return redirect(request.referrer or url_for('dashboard'))

    if status_clean == 'Hold':
        cursor.execute("""
            UPDATE file_pipeline 
            SET status = 'Hold', hold_reason = ?, remarks = COALESCE(remarks, ?)
            WHERE file_id = ? AND step_name = ?
        """, (hold_reason, f"On Hold: {hold_reason}", file_id, step_name))
        cursor.execute("UPDATE files SET hold_reason = ? WHERE id = ?", (hold_reason, file_id))
    elif status_clean in ['In Progress', 'Wip', 'WIP']:
        cursor.execute("""
            UPDATE file_pipeline 
            SET status = 'Wip', start_date = COALESCE(start_date, ?) 
            WHERE file_id = ? AND step_name = ?
        """, (today_str, file_id, step_name))
    elif status_clean in ['Done', 'Approved']:
        cursor.execute("""
            UPDATE file_pipeline 
            SET status = ?, start_date = COALESCE(start_date, ?), end_date = COALESCE(end_date, ?), submitted_at = ?
            WHERE file_id = ? AND step_name = ?
        """, (status_clean, today_str, today_str, now_full_str, file_id, step_name))
    else:
        cursor.execute("""
            UPDATE file_pipeline 
            SET status = ? 
            WHERE file_id = ? AND step_name = ?
        """, (status_clean, file_id, step_name))
    
    submit_time_val = None
    if status == 'Done':
        submit_time_val = datetime.datetime.now().strftime('%H:%M:%S')

    target_user_for_da = pipeline_step['assigned_to'] or session['user_id']
    if target_user_for_da:
        cursor.execute("""
            UPDATE daily_assignments 
            SET status = 'Pending', submit_time = ?, submitted_at = ?
            WHERE file_id = ? AND user_id = ? AND date = ?
        """, (submit_time_val, now_full_str, file_id, target_user_for_da, today_str))
    
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
        
        target_user_id = pipeline_step['assigned_to'] or session['user_id']
        if target_user_id:
            cursor.execute("""
                INSERT INTO points (user_id, date, points, reason, awarded_by)
                VALUES (?, ?, ?, ?, ?)
            """, (target_user_id, today_str, pipeline_step['points'] or 0, 
                  f"Completed stage: {pipeline_step['file_name']} [{step_name}]", session['user_id']))
              
        if step_name in ['Reference', 'Explanation', 'Voice Over', 'Narration', 'Storyboards', 'Scene-wise Assets']:
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE files SET content_released_at = ? WHERE id = ?", (now_str, file_id))
            
        vfx_choice = request.form.get('vfx_choice', 'send').strip().lower()
        seq = get_file_pipeline_sequence(db, file_id)
        if step_name in seq:
            idx = seq.index(step_name)
            if idx < len(seq) - 1:
                next_stage = seq[idx + 1]
                
                # Check for Skip VFX choice when completing FBX export or Animation
                if step_name in ['FBX export', 'Animation'] and (vfx_choice == 'skip' or request.form.get('skip_vfx') == '1'):
                    cursor.execute("""
                        UPDATE file_pipeline 
                        SET status = 'Not Applicable', remarks = 'Skipped VFX'
                        WHERE file_id = ? AND step_name = 'VFX'
                    """, (file_id,))
                    next_stage = 'Lightning'
                
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
    
    if not assignment_id or validation_status not in ['Done', 'Pending', 'Rework']:
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
            
            if step_name in ['Reference', 'Explanation', 'Voice Over', 'Narration', 'Storyboards', 'Scene-wise Assets']:
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("UPDATE files SET content_released_at = ? WHERE id = ?", (now_str, da['file_id']))
                
            vfx_choice = request.form.get('vfx_choice', 'send').strip().lower()
            seq = get_file_pipeline_sequence(db, da['file_id'])
            if step_name in seq:
                idx = seq.index(step_name)
                if idx < len(seq) - 1:
                    next_stage = seq[idx + 1]
                    
                    if step_name in ['FBX export', 'Animation'] and (vfx_choice == 'skip' or request.form.get('skip_vfx') == '1'):
                        cursor.execute("""
                            UPDATE file_pipeline 
                            SET status = 'Not Applicable', remarks = 'Skipped VFX'
                            WHERE file_id = ? AND step_name = 'VFX'
                        """, (da['file_id'],))
                        next_stage = 'Lightning'
                    
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

    elif validation_status == 'Rework':
        rework_team = request.form.get('rework_team', '').strip()
        if not rework_team:
            rework_team = da['team']
            
        if not remarks:
            flash("A mandatory rework reason/feedback is required before sending a task for Rework.", "error")
            return redirect(request.referrer or url_for('dashboard'))
            
        target_stage = None
        for stg, tm in STAGE_TEAMS.items():
            if tm.lower() == rework_team.lower():
                target_stage = stg
                break
        if not target_stage:
            target_stage = 'Modeling'
            
        record_rtk_event(db, da['file_id'], target_stage, remarks, rework_team)
        
        cursor.execute("UPDATE daily_assignments SET status = 'Rework', remarks = ? WHERE id = ?", 
                       (remarks, assignment_id))
                       
        cursor.execute("SELECT id FROM users WHERE team = ? AND role = 'Lead'", (rework_team,))
        target_leads = cursor.fetchall()
        for tl in target_leads:
            _push_notification(db, tl['id'], "Rework Assigned to Your Team", 
                               f"File '{da['file_name']}' sent for Rework to {rework_team} team by {session['name']}. Reason: {remarks}", 
                               "approval", link=url_for('dashboard'))
                               
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'EOD Validation Rework', ?)",
                       (session['user_id'], f"Sent task for Rework to {rework_team} team on '{da['file_name']}'. Reason: {remarks}"))
        db.commit()
        flash(f"Task sent for Rework to {rework_team} team. Stage is OPEN for target lead to assign. Take counter incremented, points unchanged!", "warning")

    return redirect(request.referrer or url_for('dashboard'))

@app.route('/file/rework', methods=['POST'])
def file_rework():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session['role'] not in ['Admin', 'Lead']:
        flash("Unauthorized to issue rework for files.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    file_id = request.form.get('file_id', type=int)
    rework_team = request.form.get('rework_team', '').strip()
    rework_reason = request.form.get('rework_reason', '').strip()
    
    if not file_id or not rework_team:
        flash("File ID and Rework Target Team are required.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    if not rework_reason:
        flash("A mandatory rework reason/feedback is required before submitting a rework request.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    target_stage = None
    for stg, tm in STAGE_TEAMS.items():
        if tm.lower() == rework_team.lower():
            target_stage = stg
            break
            
    if not target_stage:
        target_stage = 'Modeling'
        
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT name FROM files WHERE id = ?", (file_id,))
    f_info = cursor.fetchone()
    if not f_info:
        flash("File not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    file_name = f_info['name']
    
    record_rtk_event(db, file_id, target_stage, rework_reason, rework_team)
    
    # Notify Target Team Lead
    cursor.execute("SELECT id FROM users WHERE team = ? AND role = 'Lead'", (rework_team,))
    target_leads = cursor.fetchall()
    for tl in target_leads:
        _push_notification(db, tl['id'], "Rework Assigned to Your Team", 
                           f"File '{file_name}' sent for Rework to {rework_team} team by {session['name']}. Reason: {rework_reason}", 
                           "approval", link=url_for('dashboard'))
                           
    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'File Rework Issued', ?)",
                   (session['user_id'], f"Issued Rework on '{file_name}' to {rework_team} team. Reason: {rework_reason}"))
                   
    db.commit()
    recalculate_file_metadata(db, file_id)
    
    flash(f"File '{file_name}' successfully sent for Rework to {rework_team} team. Stage is now OPEN for target lead to assign. Points remain locked!", "warning")
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/self-log-work', methods=['POST'])
def submit_self_logged_work():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    lead_info = is_lead_absent_today(db, session.get('team'))
    if not lead_info:
        flash("Self-logging is only available when your Team Lead is Absent for today.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    file_id = request.form.get('file_id', type=int)
    step_name = request.form.get('step_name', '').strip()
    status_val = request.form.get('status', '').strip()
    remarks_val = request.form.get('remarks', '').strip()
    
    if not file_id or not step_name or not status_val:
        flash("File, stage, and status are required for self-logging.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    cursor = db.cursor()
    cursor.execute("SELECT name FROM files WHERE id = ?", (file_id,))
    file_row = cursor.fetchone()
    if not file_row:
        flash("File not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    cursor.execute("SELECT points FROM file_pipeline WHERE file_id = ? AND step_name = ?", (file_id, step_name))
    fp_row = cursor.fetchone()
    stage_points = fp_row['points'] if fp_row and fp_row['points'] else 0
    
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    cursor.execute("""
        INSERT INTO self_logged_work (
            artist_id, artist_name, lead_id, team, file_id, file_name,
            step_name, status, remarks, points, log_date, approval_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
    """, (
        session['user_id'], session['name'], lead_info['id'], session['team'],
        file_id, file_row['name'], step_name, status_val, remarks_val, stage_points, today_str
    ))
    db.commit()
    
    flash(f"Work for '{file_row['name']}' ({step_name}) self-logged successfully for today! Points ({stage_points} pts) will be credited upon Lead approval.", "success")
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/self-log-work/<int:log_id>/approve', methods=['POST'])
def approve_self_logged_work(log_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM self_logged_work WHERE id = ?", (log_id,))
    log_row = cursor.fetchone()
    if not log_row:
        flash("Self-logged entry not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    if session['role'] != 'Admin' and (session['role'] != 'Lead' or session['team'] != log_row['team']):
        flash("Unauthorized to approve this self-logged work.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    cursor.execute("""
        UPDATE self_logged_work
        SET approval_status = 'Approved', approved_at = ?
        WHERE id = ?
    """, (now_str, log_id))
    
    file_id = log_row['file_id']
    step_name = log_row['step_name']
    artist_id = log_row['artist_id']
    status_val = log_row['status']
    remarks_val = log_row['remarks']
    points_val = log_row['points']
    
    cursor.execute("""
        UPDATE file_pipeline
        SET status = ?, assigned_to = COALESCE(assigned_to, ?), remarks = COALESCE(remarks, ?),
            submitted_at = CASE WHEN ? IN ('Done', 'Approved') THEN ? ELSE submitted_at END
        WHERE file_id = ? AND step_name = ?
    """, (status_val, artist_id, remarks_val, status_val, now_str, file_id, step_name))
    
    cursor.execute("""
        SELECT id FROM daily_assignments
        WHERE user_id = ? AND file_id = ? AND date = ?
    """, (artist_id, file_id, today_str))
    da_row = cursor.fetchone()
    if da_row:
        cursor.execute("""
            UPDATE daily_assignments
            SET status = ?, points = ?, submitted_at = ?
            WHERE id = ?
        """, (status_val, points_val, now_str, da_row['id']))
    else:
        cursor.execute("""
            INSERT INTO daily_assignments (
                user_id, file_id, task_description, status, points, date, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (artist_id, file_id, step_name, status_val, points_val, today_str, now_str))
        
    recalculate_file_metadata(db, file_id)
    db.commit()
    
    flash(f"Self-logged work for '{log_row['file_name']}' approved! {points_val} points credited to {log_row['artist_name']}.", "success")
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/self-log-work/<int:log_id>/reject', methods=['POST'])
def reject_self_logged_work(log_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM self_logged_work WHERE id = ?", (log_id,))
    log_row = cursor.fetchone()
    if not log_row:
        flash("Self-logged entry not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    if session['role'] != 'Admin' and (session['role'] != 'Lead' or session['team'] != log_row['team']):
        flash("Unauthorized to reject this self-logged work.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        UPDATE self_logged_work
        SET approval_status = 'Rejected', approved_at = ?
        WHERE id = ?
    """, (now_str, log_id))
    db.commit()
    
    flash(f"Self-logged work entry for '{log_row['file_name']}' rejected.", "info")
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
        
    sub_tab = request.args.get('sub_tab', 'assets')
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
        sub_tab=sub_tab,
        current_month=current_month,
        selected_employee=selected_employee,
        points_transactions=points_transactions,
        selected_target=selected_target,
        selected_earned=selected_earned,
        selected_pct=selected_pct,
        selected_month=selected_month
    )


# ─────────────────────────────────────────────────────────────────────────────
# USER / TEAM / ROLE MANAGEMENT (Admin Only)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/permissions', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')
def permissions_page():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'update_user':
            uid = request.form.get('user_id', type=int)
            new_role = request.form.get('role', '').strip()
            new_team = request.form.get('team', '').strip()
            if uid and new_role in ('Admin', 'Lead', 'Artist') and new_team:
                cursor.execute("UPDATE users SET role = ?, team = ? WHERE id = ?", (new_role, new_team, uid))
                if new_role == 'Lead':
                    cursor.execute("UPDATE teams SET lead_id = ? WHERE name = ?", (uid, new_team))
                cursor.execute(
                    "INSERT INTO activity_log (user_id, action, details) VALUES (?, 'User Updated', ?)",
                    (session['user_id'], f"Updated user ID {uid} to role={new_role}, team={new_team}"),
                )
                db.commit()
                flash("User role and team updated.", "success")
        elif action == 'create_user':
            name = request.form.get('name', '').strip()
            username = request.form.get('username', '').strip().lower()
            role = request.form.get('role', 'Artist').strip()
            team = request.form.get('team', 'Content').strip()
            temp_pw = request.form.get('password', 'inucom@123')
            if name and username and role in ('Admin', 'Lead', 'Artist') and team:
                try:
                    cursor.execute(
                        """
                        INSERT INTO users (name, username, password_hash, role, team, must_change_password)
                        VALUES (?, ?, ?, ?, ?, 1)
                        """,
                        (name, username, generate_password_hash(temp_pw), role, team),
                    )
                    db.commit()
                    flash(f"User @{username} created.", "success")
                except Exception as exc:
                    db.rollback()
                    flash(f"Could not create user: {exc}", "error")
        elif action == 'reset_password':
            uid = request.form.get('user_id', type=int)
            if uid:
                cursor.execute(
                    "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE id = ?",
                    (generate_password_hash("inucom@123"), uid),
                )
                db.commit()
                flash("Password reset to default (inucom@123); user must change on next login.", "success")
        elif action == 'toggle_permission':
            pid = request.form.get('perm_id', type=int)
            allowed = 1 if request.form.get('allowed') == '1' else 0
            if pid:
                cursor.execute("UPDATE permissions SET allowed = ? WHERE id = ?", (allowed, pid))
                db.commit()
                flash("Permission updated.", "success")
        return redirect(url_for('permissions_page'))

    users_list = cursor.execute("SELECT id, name, username, role, team, must_change_password FROM users ORDER BY team, role, name").fetchall()
    teams_list = cursor.execute("SELECT t.*, u.name AS lead_name FROM teams t LEFT JOIN users u ON t.lead_id = u.id ORDER BY t.name").fetchall()
    perms_list = cursor.execute("SELECT * FROM permissions ORDER BY role, permission_name").fetchall()
    stages_list = cursor.execute("SELECT * FROM pipeline_stages ORDER BY stage_order ASC").fetchall()
    user_info = cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    return render_template(
        'permissions.html',
        user=user_info,
        users_list=users_list,
        teams_list=teams_list,
        perms_list=perms_list,
        stages_list=stages_list,
        production_teams=PRODUCTION_TEAMS + ['Management'],
    )


# ─────────────────────────────────────────────────────────────────────────────
# PER-TEAM EXCEL TEMPLATE DOWNLOAD & DRY-RUN / ATOMIC UPLOAD
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_target_team(requested_team: str | None) -> str:
    if session.get('role') == 'Admin':
        if requested_team and requested_team in PRODUCTION_TEAMS:
            return requested_team
        return PRODUCTION_TEAMS[0]
    return session.get('team', '')


@app.route('/team/template/download', methods=['GET'])
@login_required
@roles_required('Lead', 'Admin')
def download_team_template():
    req_team = request.args.get('team', '').strip()
    if session.get('role') == 'Lead' and req_team and req_team != session.get('team'):
        flash("Team Leads can only download templates for their own assigned team.", "error")
        return redirect(url_for('dashboard'))

    target_team = _resolve_target_team(req_team)
    db = get_db()
    xlsx_bytes = generate_team_excel_template(db, target_team)
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    safe_team = re.sub(r'[^A-Za-z0-9_-]+', '_', target_team)
    fname = f"{safe_team}_Daily_Template_{today_str}.xlsx"
    return send_file(
        io.BytesIO(xlsx_bytes),
        download_name=fname,
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@app.route('/team/upload', methods=['GET', 'POST'])
@login_required
@roles_required('Lead', 'Admin')
def team_upload():
    db = get_db()
    user_info = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    req_team = request.values.get('team', '').strip()

    if session.get('role') == 'Lead' and req_team and req_team != session.get('team'):
        flash("Team Leads can only upload files for their own assigned team.", "error")
        return redirect(url_for('dashboard'))

    target_team = _resolve_target_team(req_team)

    if request.method == 'POST':
        action = request.form.get('action', 'preview')

        if action == 'confirm':
            pending = session.get('pending_upload')
            if not pending or pending.get('team') != target_team:
                flash("No pending validated upload found for this team. Please upload and preview again.", "error")
                return redirect(url_for('team_upload', team=target_team))
            try:
                stats = commit_team_upload(
                    db,
                    target_team,
                    session['user_id'],
                    pending['rows'],
                    filename=pending.get('filename', 'upload.xlsx'),
                )
                session.pop('pending_upload', None)
                flash(
                    f"Upload committed for {target_team}: {stats['files_updated']} updated, "
                    f"{stats['files_added']} added, {stats['files_handed_off']} handed off, "
                    f"{stats['files_rework']} sent for rework.",
                    "success",
                )
                return redirect(url_for('dashboard'))
            except Exception as exc:
                flash(f"Atomic commit failed (rolled back): {exc}", "error")
                return redirect(url_for('team_upload', team=target_team))

        # Step A: Validate & Preview
        uploaded_file = request.files.get('excel_file')
        if not uploaded_file or not uploaded_file.filename:
            flash("Please select an .xlsx file to upload.", "error")
            return redirect(url_for('team_upload', team=target_team))

        file_bytes = uploaded_file.read()
        preview = parse_and_validate_upload(db, target_team, file_bytes)
        if preview['ok']:
            session['pending_upload'] = {
                'team': target_team,
                'filename': uploaded_file.filename,
                'rows': preview['rows'],
            }
        else:
            session.pop('pending_upload', None)

        return render_template(
            'team_upload.html',
            user=user_info,
            target_team=target_team,
            production_teams=PRODUCTION_TEAMS,
            preview=preview,
            filename=uploaded_file.filename,
            open_queue=get_team_open_queue(db, target_team),
        )

    return render_template(
        'team_upload.html',
        user=user_info,
        target_team=target_team,
        production_teams=PRODUCTION_TEAMS,
        preview=None,
        filename=None,
        open_queue=get_team_open_queue(db, target_team),
    )


@app.route('/upload-project', methods=['GET', 'POST'])
def upload_project_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['role'] != 'Admin':
        flash("Unauthorized to access Project Upload.", "error")
        return redirect(url_for('dashboard'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()

    if request.method == 'POST':
        pipeline_type = request.form.get('pipeline_type', 'assets')
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

                is_scene_pipeline = (pipeline_type == 'scenes')
                file_type_val = 'Scene' if is_scene_pipeline else 'Asset'
                target_stages = SCENE_STAGES_FULL if is_scene_pipeline else ASSET_STAGES
                first_stage = target_stages[0] if target_stages else 'Reference'
                
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

                    # 4. Insert File with specific file_type
                    cursor.execute("""
                        INSERT INTO files (chapter_id, name, description, file_type, status)
                        VALUES (?, ?, ?, ?, 'Pending')
                    """, (chap_id, file_name, file_desc, file_type_val))
                    file_id = cursor.lastrowid
                    files_created += 1

                    # 5. Initialize the pipeline stages for this file
                    for stage in target_stages:
                        status = 'Open' if stage == first_stage else 'Pending'
                        cursor.execute("""
                            INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points)
                            VALUES (?, ?, ?, NULL, 0)
                        """, (file_id, stage, status))

                    rows_processed += 1

                db.commit()
                pipe_label = "Scene" if is_scene_pipeline else "Asset"
                flash(f"Successfully processed {pipe_label} Project Excel! Created {files_created} new {file_type_val.lower()} files across projects.", "success")
                cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Upload Project Excel', ?)",
                               (session['user_id'], f"Uploaded {pipe_label} excel file '{file.filename}' creating {files_created} files."))
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

def _report_morning(db, date_str, end_date=None):
    """Morning Assignment Report: Team-wise grouping with Team Lead info."""
    c = db.cursor()
    c.execute("SELECT team, name FROM users WHERE role = 'Lead'")
    leads_by_team = {r['team']: r['name'] for r in c.fetchall()}
    
    c.execute("SELECT DISTINCT team FROM users WHERE role IN ('Artist', 'Lead') ORDER BY team")
    teams = [r[0] for r in c.fetchall()]
    
    if end_date and end_date != date_str:
        c.execute("""
            SELECT da.id, da.date, da.status as assign_status, da.points, da.task_description,
                   da.submit_time, f.name as file_name,
                   u.id as artist_id, u.name as artist_name, u.team, u.role as artist_role,
                   fp.step_name as stage
            FROM daily_assignments da
            JOIN users u ON da.user_id = u.id
            LEFT JOIN files f ON da.file_id = f.id
            LEFT JOIN file_pipeline fp ON (fp.file_id = da.file_id AND fp.assigned_to = da.user_id)
            WHERE da.date >= ? AND da.date <= ?
            ORDER BY u.team, da.date DESC, u.name, da.id
        """, (date_str, end_date))
    else:
        c.execute("""
            SELECT da.id, da.date, da.status as assign_status, da.points, da.task_description,
                   da.submit_time, f.name as file_name,
                   u.id as artist_id, u.name as artist_name, u.team, u.role as artist_role,
                   fp.step_name as stage
            FROM daily_assignments da
            JOIN users u ON da.user_id = u.id
            LEFT JOIN files f ON da.file_id = f.id
            LEFT JOIN file_pipeline fp ON (fp.file_id = da.file_id AND fp.assigned_to = da.user_id)
            WHERE da.date = ?
            ORDER BY u.team, u.name, da.id
        """, (date_str,))
    assignments_raw = [dict(r) for r in c.fetchall()]
    
    c.execute("SELECT id, name, team, role FROM users WHERE role IN ('Artist', 'Lead') ORDER BY team, name")
    all_staff = [dict(r) for r in c.fetchall()]
    
    team_data = {}
    for tm in teams:
        lead_name = leads_by_team.get(tm, 'No Lead Assigned')
        tm_staff = [s for s in all_staff if s['team'] == tm]
        tm_assignments = [a for a in assignments_raw if a['team'] == tm]
        assigned_artist_ids = {a['artist_id'] for a in tm_assignments}
        unassigned_staff = [s for s in tm_staff if s['id'] not in assigned_artist_ids]
        
        if len(tm_assignments) == 0:
            status_label = "Missed Morning Assignment"
            status_color = "red"
        elif len(unassigned_staff) > 0:
            status_label = f"Partially Assigned ({len(unassigned_staff)} unassigned)"
            status_color = "warning"
        else:
            status_label = "Fully Assigned"
            status_color = "green"
            
        team_data[tm] = {
            'team': tm,
            'lead_name': lead_name,
            'status_label': status_label,
            'status_color': status_color,
            'assignments': tm_assignments,
            'unassigned_staff': unassigned_staff,
            'total_staff': len(tm_staff)
        }
        
    return team_data, assignments_raw

def _report_eod(db, date_str, end_date=None):
    """EOD Validation: Team-wise grouping with Team Lead info and validation status."""
    c = db.cursor()
    c.execute("SELECT team, name FROM users WHERE role = 'Lead'")
    leads_by_team = {r['team']: r['name'] for r in c.fetchall()}
    
    c.execute("SELECT DISTINCT team FROM users WHERE role IN ('Artist', 'Lead') ORDER BY team")
    teams = [r[0] for r in c.fetchall()]
    
    if end_date and end_date != date_str:
        c.execute("""
            SELECT da.id, da.date, da.status as assign_status, da.points, da.task_description,
                   da.remarks as pending_reason, f.name as file_name,
                   u.name as artist_name, u.team, u.role as artist_role,
                   fp.step_name as stage
            FROM daily_assignments da
            JOIN users u ON da.user_id = u.id
            LEFT JOIN files f ON da.file_id = f.id
            LEFT JOIN file_pipeline fp ON (fp.file_id = da.file_id AND fp.assigned_to = da.user_id)
            WHERE da.date >= ? AND da.date <= ?
            ORDER BY u.team, da.date DESC, da.status, u.name
        """, (date_str, end_date))
    else:
        c.execute("""
            SELECT da.id, da.date, da.status as assign_status, da.points, da.task_description,
                   da.remarks as pending_reason, f.name as file_name,
                   u.name as artist_name, u.team, u.role as artist_role,
                   fp.step_name as stage
            FROM daily_assignments da
            JOIN users u ON da.user_id = u.id
            LEFT JOIN files f ON da.file_id = f.id
            LEFT JOIN file_pipeline fp ON (fp.file_id = da.file_id AND fp.assigned_to = da.user_id)
            WHERE da.date = ?
            ORDER BY u.team, da.status, u.name
        """, (date_str,))
    assignments_raw = [dict(r) for r in c.fetchall()]
    
    team_data = {}
    for tm in teams:
        lead_name = leads_by_team.get(tm, 'No Lead Assigned')
        tm_assignments = [a for a in assignments_raw if a['team'] == tm]
        done_cnt = sum(1 for a in tm_assignments if a['assign_status'] == 'Done')
        pending_cnt = sum(1 for a in tm_assignments if a['assign_status'] != 'Done')
        
        if len(tm_assignments) == 0:
            status_label = "No Tasks Submitted"
            status_color = "muted"
        elif pending_cnt > 0:
            status_label = f"Pending Validation ({pending_cnt} pending)"
            status_color = "warning"
        else:
            status_label = "All Tasks Validated & Done"
            status_color = "green"
            
        team_data[tm] = {
            'team': tm,
            'lead_name': lead_name,
            'status_label': status_label,
            'status_color': status_color,
            'assignments': tm_assignments,
            'done_count': done_cnt,
            'pending_count': pending_cnt
        }
        
    return team_data

def _report_monthly_points(db, month_str):
    """Monthly Points: per employee breakdown, earned vs target."""
    c = db.cursor()
    try:
        year, mon = map(int, month_str.split('-'))
    except:
        today = datetime.date.today()
        year, mon = today.year, today.month
    _, last_day = calendar.monthrange(year, mon)
    month_start = datetime.date(year, mon, 1)
    month_end   = datetime.date(year, mon, last_day)
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
        c.execute("SELECT target_points FROM monthly_targets WHERE user_id=? AND month=?",
                  (u['id'], month_str))
        tgt_row = c.fetchone()
        target = tgt_row['target_points'] if tgt_row else 0
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

    today_dt    = datetime.date.today()
    today_str   = today_dt.strftime('%Y-%m-%d')

    tab         = request.args.get('tab', 'compliance')
    if tab not in ['morning', 'eod', 'compliance']:
        tab = 'compliance'

    range_type  = request.args.get('range_type', 'today')
    rdate       = request.args.get('date', today_str)

    if range_type == 'this_week':
        monday_dt  = today_dt - datetime.timedelta(days=today_dt.weekday())
        start_date = monday_dt.strftime('%Y-%m-%d')
        end_date   = today_str
    elif range_type == 'this_month':
        start_date = today_dt.replace(day=1).strftime('%Y-%m-%d')
        end_date   = today_str
    elif range_type == 'custom':
        start_date = request.args.get('start_date', rdate)
        end_date   = request.args.get('end_date', rdate)
    else:
        range_type = 'today'
        start_date = rdate
        end_date   = rdate

    morning_rows, no_task_artists = [], []
    eod_rows = []

    if tab == 'morning':
        morning_rows, no_task_artists = _report_morning(db, start_date, end_date)
    elif tab == 'eod':
        eod_rows = _report_eod(db, start_date, end_date)

    # Admin Daily Upload Compliance (always computed for Admin Reports)
    compliance_rows = []
    for t_name in PRODUCTION_TEAMS:
        t_row = cursor.execute(
            "SELECT t.id, u.name AS lead_name FROM teams t LEFT JOIN users u ON t.lead_id = u.id WHERE t.name = ?",
            (t_name,),
        ).fetchone()
        tid = t_row['id'] if t_row else None
        lead_name = t_row['lead_name'] if t_row and t_row['lead_name'] else 'Unassigned'
        log_row = None
        if tid:
            log_row = cursor.execute(
                """
                SELECT l.*, u.name AS uploader_name
                FROM daily_upload_logs l
                JOIN users u ON l.uploaded_by = u.id
                WHERE l.team_id = ? AND l.upload_date = ?
                ORDER BY l.id DESC LIMIT 1
                """,
                (tid, today_str),
            ).fetchone()
        compliance_rows.append({
            'team_name': t_name,
            'lead_name': lead_name,
            'uploaded': bool(log_row),
            'uploaded_at': log_row['uploaded_at'] if log_row else None,
            'uploader_name': log_row['uploader_name'] if log_row else None,
            'files_updated': log_row['files_updated'] if log_row else 0,
            'files_added': log_row['files_added'] if log_row else 0,
            'files_handed_off': log_row['files_handed_off'] if log_row else 0,
            'files_rework': log_row['files_rework'] if log_row else 0,
        })

    return render_template('reports.html',
        user=user_info, tab=tab, range_type=range_type,
        rdate=rdate, start_date=start_date, end_date=end_date,
        morning_rows=morning_rows, no_task_artists=no_task_artists,
        eod_rows=eod_rows,
        compliance_rows=compliance_rows,
        today_str=today_str,
    )

@app.route('/reports/export/<tab>')
def reports_export(tab):
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))

    db = get_db()
    today_dt    = datetime.date.today()
    today_str   = today_dt.strftime('%Y-%m-%d')

    range_type  = request.args.get('range_type', 'today')
    rdate       = request.args.get('date', today_str)

    if range_type == 'this_week':
        monday_dt  = today_dt - datetime.timedelta(days=today_dt.weekday())
        start_date = monday_dt.strftime('%Y-%m-%d')
        end_date   = today_str
    elif range_type == 'this_month':
        start_date = today_dt.replace(day=1).strftime('%Y-%m-%d')
        end_date   = today_str
    elif range_type == 'custom':
        start_date = request.args.get('start_date', rdate)
        end_date   = request.args.get('end_date', rdate)
    else:
        range_type = 'today'
        start_date = rdate
        end_date   = rdate

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    if tab == 'morning':
        team_data, assignments_raw = _report_morning(db, start_date, end_date)
        ws = wb.create_sheet("Morning Assignment")
        ws.append([f"Morning Assignment Report — Range: {start_date} to {end_date}"])
        ws['A1'].font = Font(bold=True, size=13)
        ws.merge_cells('A1:I1')
        ws.append([])
        _xl_header_row(ws, 3, ['Date', 'Team', 'Artist Name', 'Role', 'File / Task Description', 'Pipeline Stage', 'Points', 'Assign Status', 'Submit Time'])
        r = 4
        cur_team = None; team_pts = 0; grand = 0
        for row in assignments_raw:
            if cur_team and cur_team != row['team']:
                _xl_data_row(ws, r, ['Subtotal', cur_team, '', '', '', '', str(team_pts), '', ''], _SUBTTL_FILL, True)
                r += 1; team_pts = 0
            cur_team = row['team']
            team_pts += (row['points'] or 0); grand += (row['points'] or 0)
            _xl_data_row(ws, r, [
                row.get('date', start_date),
                row['team'],
                row['artist_name'],
                row.get('artist_role', 'Artist'),
                row['file_name'] or row['task_description'] or '',
                row['stage'] or '',
                row['points'] or 0,
                row['assign_status'] or '',
                row.get('submit_time', '') or ''
            ])
            r += 1
        if cur_team:
            _xl_data_row(ws, r, ['Subtotal', cur_team, '', '', '', '', str(team_pts), '', ''], _SUBTTL_FILL, True)
            r += 1
        _xl_data_row(ws, r, ['GRAND TOTAL', '', '', '', '', '', str(grand), '', ''], _SUBTTL_FILL, True)
        r += 2

        unassigned_list = []
        for tm, tinfo in team_data.items():
            for ustaff in tinfo.get('unassigned_staff', []):
                unassigned_list.append(ustaff)

        if unassigned_list:
            ws.cell(r, 1, '⚠ Staff with NO tasks assigned:').font = Font(bold=True, color='CC0000')
            r += 1
            for a in unassigned_list:
                _xl_data_row(ws, r, [start_date, a['team'], f"{a['name']} ({a.get('role', 'Artist')})", 'NO TASKS ASSIGNED', '', '', '', '', ''])
                r += 1
        _xl_autowidth(ws)
        fname = f"MorningAssignment_{start_date}_to_{end_date}.xlsx"

    elif tab == 'eod':
        team_data = _report_eod(db, start_date, end_date)
        ws = wb.create_sheet("EOD Validation")
        ws.append([f"EOD Validation Report — Range: {start_date} to {end_date}"])
        ws['A1'].font = Font(bold=True, size=13)
        ws.merge_cells('A1:G1')
        ws.append([])

        all_assignments = []
        for tname, tinfo in team_data.items():
            all_assignments.extend(tinfo.get('assignments', []))

        done_rows = [r for r in all_assignments if r['assign_status'] == 'Done']
        pending_rows = [r for r in all_assignments if r['assign_status'] != 'Done']

        ws.cell(3, 1, "Completed / Done Work (Points Credited)").font = Font(bold=True, size=11, color="008000")
        _xl_header_row(ws, 4, ['Date', 'Team', 'Artist Name', 'File / Task Description', 'Pipeline Stage', 'Status', 'Points Credited'])
        r = 5
        done_pts = 0
        for row in done_rows:
            done_pts += (row['points'] or 0)
            _xl_data_row(ws, r, [
                row.get('date', start_date),
                row['team'],
                row['artist_name'],
                row['file_name'] or row['task_description'] or '',
                row['stage'] or '',
                'Done',
                row['points'] or 0
            ])
            r += 1
        _xl_data_row(ws, r, ['DONE TOTALS', '', '', '', '', f'Count: {len(done_rows)}', f'{done_pts} pts'], _SUBTTL_FILL, True)
        r += 3

        ws.cell(r, 1, "Carry Forwarded Work (Pending / Retake)").font = Font(bold=True, size=11, color="CC6600")
        r += 1
        _xl_header_row(ws, r, ['Date', 'Team', 'Artist Name', 'File / Task Description', 'Pipeline Stage', 'Status', 'Pending Reason / Remarks'])
        r += 1
        for row in pending_rows:
            _xl_data_row(ws, r, [
                row.get('date', start_date),
                row['team'],
                row['artist_name'],
                row['file_name'] or row['task_description'] or '',
                row['stage'] or '',
                row['assign_status'] or 'Pending',
                row['pending_reason'] or 'Carried forward to tomorrow'
            ])
            r += 1
        _xl_data_row(ws, r, ['CARRY FORWARD TOTALS', '', '', '', '', f'Count: {len(pending_rows)}', ''], _SUBTTL_FILL, True)

        _xl_autowidth(ws)
        fname = f"EODValidation_{start_date}_to_{end_date}.xlsx"
    else:
        return redirect(url_for('reports_page'))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

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
                                               "warning", link=url_for('reports_page', tab='morning'))
                            db.commit()
    except Exception as e:
        print(f"Error check_and_push_morning_reminders: {e}")

def check_and_push_admin_target_alerts(db, admin_id):
    """Target alert notifications have been removed as per user requirements."""
    pass

@app.context_processor
def inject_notifications():
    """Inject notification counts into templates."""
    unread = 0
    if 'user_id' in session:
        try:
            db = get_db()
            unread = db.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                (session['user_id'],),
            ).fetchone()[0]
        except Exception:
            unread = 0
    return dict(
        pending_approvals_count=0,
        unread_notif_count=unread,
        unread_approvals_count=0,
        unread_work_count=unread,
        recent_notifications=[],
    )


@app.route('/api/notifications/unread_count')
def api_unread_notifications_count():
    if 'user_id' not in session:
        return {'unread_count': 0, 'unread_approvals': 0, 'unread_work': 0}
    db = get_db()
    cnt = db.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (session['user_id'],),
    ).fetchone()[0]
    return {'unread_count': cnt, 'unread_approvals': 0, 'unread_work': cnt}


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
    raw_notifs = [dict(r) for r in cursor.fetchall()]
    
    approvals_list = []
    work_list = []
    for n in raw_notifs:
        ntype = (n.get('type') or '').lower()
        title = (n.get('title') or '').lower()
        if ntype in ['approval', 'leave', 'permission'] or any(k in title for k in ['approval', 'leave', 'permission', 'validation']):
            n['category'] = 'Approvals'
            approvals_list.append(n)
        else:
            n['category'] = 'Work'
            work_list.append(n)
            
    return render_template('notifications.html', user=user_info, notifs=raw_notifs, approvals_notifs=approvals_list, work_notifs=work_list)

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
        
        ntype = (notif['type'] or '').lower()
        title = (notif['title'] or '').lower()
        link = notif['link']

        if 'morning' in title or 'assignment' in title:
            return redirect(url_for('reports_page', tab='morning'))

        target_link = link or url_for('dashboard')
        return redirect(target_link)
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
    if session['role'] != 'Admin':
        flash("Activity log is Admin-only.", "error")
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

def _get_work_reports_data(db, range_type='this_week', custom_start='', custom_end='', search_query='', employee_id=None, selected_month='', selected_year='', sub_tab='assets', global_month=''):
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
    elif range_type == 'select_month' and selected_month:
        try:
            start_date = datetime.datetime.strptime(selected_month, '%Y-%m').date()
            _, last_day = calendar.monthrange(start_date.year, start_date.month)
            end_date = datetime.date(start_date.year, start_date.month, last_day)
        except Exception:
            start_date = today.replace(day=1)
            end_date = today
    elif range_type == 'select_year' and selected_year:
        try:
            yr = int(selected_year)
            start_date = datetime.date(yr, 1, 1)
            end_date = datetime.date(yr, 12, 31)
        except Exception:
            start_date = datetime.date(today.year, 1, 1)
            end_date = datetime.date(today.year, 12, 31)
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
    start_display = start_date.strftime('%d-%m-%Y')
    end_display = end_date.strftime('%d-%m-%Y')

    # Global month calculation (independent of top selection duration)
    current_month = today.strftime('%Y-%m')
    if not global_month:
        global_month = current_month
    try:
        g_start_date = datetime.datetime.strptime(global_month, '%Y-%m').date()
        _, g_last_day = calendar.monthrange(g_start_date.year, g_start_date.month)
        g_end_date = datetime.date(g_start_date.year, g_start_date.month, g_last_day)
    except Exception:
        global_month = current_month
        g_start_date = today.replace(day=1)
        _, g_last_day = calendar.monthrange(g_start_date.year, g_start_date.month)
        g_end_date = datetime.date(g_start_date.year, g_start_date.month, g_last_day)

    g_start_str = g_start_date.strftime('%Y-%m-%d')
    g_end_str = g_end_date.strftime('%Y-%m-%d')

    c = db.cursor()
    query = "SELECT id, name, username, role, team FROM users WHERE role IN ('Artist', 'Lead') ORDER BY team, role, name"
    c.execute(query)
    staff_members = c.fetchall()

    staff_reports = []
    global_scoreboard = {}
    global_staff_reports = []
    total_tasks_completed = 0
    total_points_earned = 0

    for s in staff_members:
        sid = s['id']
        # 1) Selection duration calculations (for top chips & selected employee details)
        c.execute("""
            SELECT da.id, da.date, da.status, da.points, da.task_description, da.remarks, da.submit_time,
                   f.name as file_name, f.take_count as file_take_count, f.rework_reason as file_rework_reason, f.hold_reason as file_hold_reason,
                   fp.step_name as stage, fp.take_count, fp.rework_reason, fp.hold_reason,
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
            SELECT COUNT(DISTINCT date) as days_worked, COALESCE(SUM(time_worked), 0) as total_hrs
            FROM daily_assignments
            WHERE user_id = ? AND date >= ? AND date <= ?
        """, (sid, start_str, end_str))
        att_row = c.fetchone()
        days_worked = att_row['days_worked'] if att_row else 0
        total_hrs = round(att_row['total_hrs'], 1) if att_row else 0.0

        c.execute("SELECT target_points FROM monthly_targets WHERE user_id = ? AND month = ?", (sid, global_month))
        target_res = c.fetchone()
        target_pts = target_res['target_points'] if target_res else 500
        prog_pct = round((pts_sum / target_pts) * 100, 1) if target_pts > 0 else 0

        c.execute("""
            SELECT COUNT(*) FROM daily_assignments da
            JOIN file_pipeline fp ON (fp.file_id = da.file_id AND fp.assigned_to = da.user_id)
            WHERE da.user_id = ? AND da.date >= ? AND da.date <= ? AND (fp.take_count >= 1 OR fp.rework_reason IS NOT NULL)
        """, (sid, start_str, end_str))
        rework_count_res = c.fetchone()
        rework_count = rework_count_res[0] if rework_count_res else 0

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
            'rework_count': rework_count,
            'days_worked': days_worked,
            'total_hours': total_hrs,
            'assignments': assignments,
            'done_assignments': done_assignments
        }
        staff_reports.append(staff_info)

        total_tasks_completed += len(done_assignments)
        total_points_earned += pts_sum

        # 2) Independent Global Monthly calculation (for Global Scoreboard & Global Staff Summary)
        c.execute("""
            SELECT da.status, da.points
            FROM daily_assignments da
            WHERE da.user_id = ? AND da.date >= ? AND da.date <= ?
        """, (sid, g_start_str, g_end_str))
        g_assigns = c.fetchall()
        g_done = [a for a in g_assigns if a['status'] == 'Done']
        g_pending = [a for a in g_assigns if a['status'] == 'Pending']
        g_pts_sum = sum(a['points'] or 0 for a in g_done)

        c.execute("SELECT target_points FROM monthly_targets WHERE user_id = ? AND month = ?", (sid, global_month))
        target_res = c.fetchone()
        g_target_pts = target_res['target_points'] if target_res else 500
        g_prog_pct = round((g_pts_sum / g_target_pts) * 100, 1) if g_target_pts > 0 else 0

        c.execute("""
            SELECT COUNT(DISTINCT date) as days_worked, COALESCE(SUM(time_worked), 0) as total_hrs
            FROM daily_assignments
            WHERE user_id = ? AND date >= ? AND date <= ?
        """, (sid, g_start_str, g_end_str))
        g_att_row = c.fetchone()
        g_days_worked = g_att_row['days_worked'] if g_att_row else 0
        g_total_hrs = round(g_att_row['total_hrs'], 1) if g_att_row else 0.0

        g_staff_info = {
            'id': sid,
            'name': s['name'],
            'username': s['username'],
            'role': s['role'],
            'team': s['team'],
            'tasks_completed': len(g_done),
            'tasks_pending': len(g_pending),
            'total_points': g_pts_sum,
            'target_points': g_target_pts,
            'progress_pct': g_prog_pct,
            'days_worked': g_days_worked,
            'total_hours': g_total_hrs
        }
        global_staff_reports.append(g_staff_info)

        tm = s['team']
        if tm not in global_scoreboard:
            global_scoreboard[tm] = []
        global_scoreboard[tm].append(g_staff_info)

    c.execute("SELECT id, name, username, role, team FROM users WHERE role IN ('Artist', 'Lead') ORDER BY name")
    all_staff_dropdown = [dict(r) for r in c.fetchall()]

    available_years = [str(y) for y in range(today.year, today.year - 3, -1)]

    return {
        'range_type': range_type,
        'start_date': start_str,
        'end_date': end_str,
        'start_date_display': start_display,
        'end_date_display': end_display,
        'custom_start': custom_start,
        'custom_end': custom_end,
        'selected_month': selected_month or current_month,
        'selected_year': selected_year or str(today.year),
        'global_month': global_month,
        'available_years': available_years,
        'staff_reports': staff_reports,
        'global_scoreboard': global_scoreboard,
        'global_staff_reports': global_staff_reports,
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

    sub_tab = request.args.get('sub_tab', 'assets')
    if sub_tab not in ['assets', 'scenes']:
        sub_tab = 'assets'

    range_type = request.args.get('range_type', 'this_week')
    custom_start = request.args.get('start_date', '')
    custom_end = request.args.get('end_date', '')
    search_query = request.args.get('q', '').strip()
    employee_id = request.args.get('employee_id', type=int)
    selected_month = request.args.get('selected_month', '')
    selected_year = request.args.get('selected_year', '')
    global_month = request.args.get('global_month', '')

    data = _get_work_reports_data(db, range_type, custom_start, custom_end, search_query, employee_id, selected_month, selected_year, sub_tab, global_month)

    selected_staff = None
    if employee_id:
        for s in data['staff_reports']:
            if s['id'] == employee_id:
                selected_staff = s
                break

    return render_template(
        'work_reports.html',
        user=user_info,
        data=data,
        selected_staff=selected_staff,
        sub_tab=sub_tab,
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
    selected_month = request.args.get('selected_month', '')
    selected_year = request.args.get('selected_year', '')
    global_month = request.args.get('global_month', '')
    data = _get_work_reports_data(db, range_type, custom_start, custom_end, search_query, employee_id, selected_month, selected_year, 'assets', global_month)

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
    _xl_header_row(ws2, 3, ['Date', 'Employee', 'Role', 'Team', 'Project', 'Chapter', 'File / Task Description', 'Stage', 'Points', 'Status', 'Comments / Remarks', 'Retakes / Rework / Hold Info'])
    r2 = 4
    for s in data['staff_reports']:
        for a in s['assignments']:
            retake_info_parts = []
            t_cnt = a.get('take_count') or a.get('file_take_count') or 0
            if t_cnt > 0:
                retake_info_parts.append(f"Takes: {t_cnt}")
            rw_rsn = a.get('rework_reason') or a.get('file_rework_reason')
            if rw_rsn:
                retake_info_parts.append(f"Rework: {rw_rsn}")
            h_rsn = a.get('hold_reason') or a.get('file_hold_reason')
            if h_rsn:
                retake_info_parts.append(f"Hold: {h_rsn}")
            retake_str = " | ".join(retake_info_parts) if retake_info_parts else "—"

            _xl_data_row(ws2, r2, [
                a['date'], s['name'], s['role'], s['team'],
                a['project_name'] or '—', a['chapter_name'] or '—',
                a['file_name'] or a['task_description'], a['stage'] or '—',
                a['points'] or 0, a['status'], a.get('remarks') or a.get('submit_time') or '—', retake_str
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
