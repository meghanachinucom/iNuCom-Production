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

# Pipeline Constants
PIPELINE_STAGES = [
    'Content',
    'Modeling',
    'Texturing',
    'Rig',
    'Animation',
    'VFX',
    'Lighting/Rendering',
    'Motion Graphics/3D Comp',
    'VR'
]

STAGE_TEAMS = {
    'Content': 'Content',
    'Modeling': 'Modeling',
    'Texturing': 'Texturing',
    'Rig': 'Rig',
    'Animation': 'Animation',
    'VFX': 'VFX',
    'Lighting/Rendering': 'Lighting',
    'Motion Graphics/3D Comp': 'Motion Graphics',
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
    {"name": "Pavan Kalyan. I", "username": "pavan", "role": "Lead", "team": "Lighting", "reports_to": "vasu"},
    {"name": "Abhilash. A", "username": "abhilash", "role": "Artist", "team": "Lighting", "reports_to": "pavan"},
    {"name": "Spandana. K", "username": "spandana", "role": "Lead", "team": "Motion Graphics", "reports_to": "vasu"},
    {"name": "L. Shiva Kumar", "username": "shiva", "role": "Artist", "team": "Motion Graphics", "reports_to": "spandana"},
    {"name": "Laxman. G", "username": "laxman", "role": "Artist", "team": "Motion Graphics", "reports_to": "spandana"},
    {"name": "Prashanth. M", "username": "prashanth", "role": "Artist", "team": "Motion Graphics", "reports_to": "spandana"},
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
    {"chapter_name": "ch_13", "name": "FW_13_08_SunLight", "description": "Sunlight dynamic lighting setup", "active_stage": "Lighting/Rendering", "status": "In Progress", "assigned": "abhilash", "content_released_offset": 21600}
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

    if not db_exists or schema_needs_update:
        if db_exists:
            try:
                os.remove(DATABASE)
            except Exception as e:
                print(f"Error removing old database: {e}")
                
        print("Initializing database from schema...")
        conn = sqlite3.connect(DATABASE)
        with open(SCHEMA_FILE, 'r') as f:
            conn.executescript(f.read())
        
        cursor = conn.cursor()
        
        # Seed users
        print("Seeding initial 28 user accounts...")
        default_pwd_hash = generate_password_hash("inucom@123")
        for user in SEEDED_USERS:
            cursor.execute("""
                INSERT INTO users (name, username, password_hash, role, team, reports_to, must_change_password)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (user['name'], user['username'], default_pwd_hash, user['role'], user['team'], user['reports_to']))
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
            
            for stage in PIPELINE_STAGES:
                if stage == f_demo['active_stage']:
                    stage_status = f_demo['status']
                    stage_assigned = artist_id
                    stage_points = points_val
                elif PIPELINE_STAGES.index(stage) < PIPELINE_STAGES.index(f_demo['active_stage']):
                    stage_status = 'Done'
                    stage_assigned = None
                    stage_points = points_val
                else:
                    stage_status = 'Pending'
                    stage_assigned = None
                    stage_points = 0
                    
                cursor.execute("""
                    INSERT INTO file_pipeline (file_id, step_name, status, assigned_to, points)
                    VALUES (?, ?, ?, ?, ?)
                """, (file_id, stage, stage_status, stage_assigned, stage_points))
                
                if stage == f_demo['active_stage'] and stage_assigned and stage_status != 'Done':
                    cursor.execute("""
                        INSERT INTO daily_assignments (user_id, date, file_id, task_description, points, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (stage_assigned, today_str, file_id, f"{stage}: {f_demo['name']}", stage_points, stage_status))
        
        # Seed targets
        current_month = datetime.date.today().strftime('%Y-%m')
        cursor.execute("SELECT id FROM users WHERE role = 'Artist'")
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
        
    files = []
    if chapter_id:
        cursor.execute("SELECT * FROM files WHERE chapter_id = ? ORDER BY id", (chapter_id,))
        files = cursor.fetchall()
        
    matrix = {}
    if chapter_id:
        cursor.execute("""
            SELECT fp.file_id, fp.step_name, fp.status, fp.points, u.name as artist_name, u.username as artist_username 
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
                'artist_username': row['artist_username']
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
            
        if queue_stage and chapter_id:
            if queue_stage == 'Content':
                order_clause = "f.id ASC"
            else:
                order_clause = "f.content_released_at ASC, f.id ASC"
                
            cursor.execute(f"""
                SELECT f.id as file_id, f.name as file_name, f.description as file_desc, 
                       fp.id as pipeline_id, fp.status as step_status, fp.assigned_to as step_assigned_to,
                       fp.points, f.content_released_at
                FROM file_pipeline fp
                JOIN files f ON fp.file_id = f.id
                WHERE f.chapter_id = ? AND fp.step_name = ? AND fp.status IN ('Open', 'In Progress')
                ORDER BY {order_clause}
            """, (chapter_id, queue_stage))
            lead_queue = cursor.fetchall()
            
            if session['role'] == 'Lead':
                cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (session['team'],))
                artists = cursor.fetchall()
            else:
                target_team = STAGE_TEAMS[queue_stage]
                cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (target_team,))
                artists = cursor.fetchall()

    validation_list = []
    if session['role'] in ['Lead', 'Admin'] and chapter_id:
        target_team = session['team'] if session['role'] == 'Lead' else STAGE_TEAMS.get(queue_stage)
        cursor.execute("""
            SELECT da.id as assignment_id, da.points, da.status as assignment_status, da.task_description, da.remarks,
                   u.name as artist_name, u.username as artist_username, f.name as file_name, f.id as file_id
            FROM daily_assignments da
            JOIN users u ON da.user_id = u.id
            JOIN files f ON da.file_id = f.id
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
        selected_project_id=project_id,
        selected_chapter_id=chapter_id,
        selected_chapter_name=selected_chapter_name,
        files=files,
        matrix=matrix,
        stages=PIPELINE_STAGES,
        lead_queue=lead_queue,
        queue_stage=queue_stage,
        artists=artists,
        artist_tasks=artist_tasks,
        validation_list=validation_list,
        late_assignment_flag=late_assignment_flag,
        late_validation_flag=late_validation_flag,
        today_str=today_str,
        attendance_today=attendance_today
    )

@app.route('/file/add', methods=['POST'])
def add_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session['role'] != 'Admin' and not (session['role'] == 'Lead' and session['team'] == 'Content'):
        flash("Unauthorized to add files.", "error")
        return redirect(url_for('dashboard'))
        
    chapter_id = request.form.get('chapter_id', type=int)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    
    if not chapter_id or not name:
        flash("File name and chapter are required.", "error")
        return redirect(url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO files (chapter_id, name, description, status)
            VALUES (?, ?, ?, 'Pending')
        """, (chapter_id, name, description))
        file_id = cursor.lastrowid
        
        for stage in PIPELINE_STAGES:
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
        
    return redirect(url_for('dashboard', chapter_id=chapter_id))

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
        return redirect(url_for('dashboard'))
        
    target_team = STAGE_TEAMS.get(step_name)
    if not target_team:
        flash("Invalid pipeline stage.", "error")
        return redirect(url_for('dashboard'))
        
    if session['role'] != 'Admin' and not (session['role'] == 'Lead' and session['team'] == target_team):
        flash("Unauthorized to assign files for this stage.", "error")
        return redirect(url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    if artist_id:
        cursor.execute("SELECT name, team, role FROM users WHERE id = ?", (artist_id,))
        artist = cursor.fetchone()
        if not artist or artist['role'] != 'Artist' or artist['team'] != target_team:
            flash("Selected user is not an Artist of this team.", "error")
            return redirect(url_for('dashboard'))
        artist_name = artist['name']
        new_status = 'In Progress'
    else:
        artist_name = "Unassigned"
        new_status = 'Open'
        points = 0
        
    try:
        cursor.execute("""
            UPDATE file_pipeline 
            SET assigned_to = ?, status = ?, points = ?
            WHERE file_id = ? AND step_name = ?
        """, (artist_id, new_status, points, file_id, step_name))
        
        cursor.execute("SELECT name, chapter_id FROM files WHERE id = ?", (file_id,))
        f_info = cursor.fetchone()
        
        if artist_id:
            today_str = datetime.date.today().strftime('%Y-%m-%d')
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
                
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Assign File', ?)",
                       (session['user_id'], f"Assigned '{f_info['name']}' [{step_name}] to {artist_name} (Points: {points})"))
        db.commit()
        flash(f"File updated: {f_info['name']} assigned to {artist_name} with {points} complexity points.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error assigning file: {e}", "error")
        
    return redirect(url_for('dashboard', chapter_id=f_info['chapter_id'] if artist_id else None))

@app.route('/file/status', methods=['POST'])
def update_status():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    file_id = request.form.get('file_id', type=int)
    step_name = request.form.get('step_name', '')
    status = request.form.get('status', '')
    
    if not file_id or not step_name or status not in ['In Progress', 'Done']:
        flash("Invalid status update parameters.", "error")
        return redirect(url_for('dashboard'))
        
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
        return redirect(url_for('dashboard'))
        
    target_team = STAGE_TEAMS.get(step_name)
    
    is_assigned = (pipeline_step['assigned_to'] == session['user_id'])
    is_lead = (session['role'] == 'Lead' and session['team'] == target_team)
    is_admin = (session['role'] == 'Admin')
    
    if not (is_assigned or is_lead or is_admin):
        flash("Unauthorized to update status for this stage.", "error")
        return redirect(url_for('dashboard'))
        
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    cursor.execute("""
        UPDATE file_pipeline 
        SET status = ? 
        WHERE file_id = ? AND step_name = ?
    """, (status, file_id, step_name))
    
    cursor.execute("""
        UPDATE daily_assignments 
        SET status = 'Pending' 
        WHERE file_id = ? AND user_id = ? AND date = ?
    """, (file_id, pipeline_step['assigned_to'], today_str))
    
    log_details = f"Artist updated status of '{pipeline_step['file_name']}' [{step_name}] to '{status}'"
    
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
            
    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                   (session['user_id'], 'Pipeline Update', log_details))
    db.commit()
    
    flash(f"Status updated for '{pipeline_step['file_name']}' [{step_name}] to '{status}'.", "success")
    return redirect(url_for('dashboard', chapter_id=pipeline_step['chapter_id']))

@app.route('/assignment/validate', methods=['POST'])
def validate_assignment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    assignment_id = request.form.get('assignment_id', type=int)
    validation_status = request.form.get('validation_status', '')
    remarks = request.form.get('remarks', '').strip()
    
    if not assignment_id or validation_status not in ['Done', 'Pending']:
        flash("Invalid validation parameters.", "error")
        return redirect(url_for('dashboard'))
        
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
        return redirect(url_for('dashboard'))
        
    if session['role'] != 'Admin' and not (session['role'] == 'Lead' and session['team'] == da['team']):
        flash("Unauthorized to validate assignments for this team.", "error")
        return redirect(url_for('dashboard'))
        
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
                UPDATE file_pipeline SET status = 'Done' 
                WHERE file_id = ? AND step_name = ?
            """, (da['file_id'], step_name))
            
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
            else:
                cursor.execute("UPDATE files SET status = 'Completed' WHERE id = ?", (da['file_id'],))
                
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'EOD Validation Done', ?)",
                       (session['user_id'], f"Validated EOD Task Done for {da['artist_name']} on '{da['file_name']}'"))
        db.commit()
        flash(f"Task for {da['artist_name']} validated as completed. Points credited!", "success")
        
    elif validation_status == 'Pending':
        if not remarks:
            flash("A typed reason is required to mark a task as Pending.", "error")
            return redirect(url_for('dashboard'))
            
        cursor.execute("UPDATE daily_assignments SET status = 'Pending', remarks = ? WHERE id = ?", (remarks, assignment_id))
        
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        cursor.execute("""
            INSERT INTO daily_assignments (user_id, date, file_id, task_description, points, status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
        """, (da['user_id'], tomorrow_str, da['file_id'], da['task_description'], da['points']))
        
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'EOD Validation Pending', ?)",
                       (session['user_id'], f"Carried forward task for {da['artist_name']} on '{da['file_name']}' to tomorrow. Reason: {remarks}"))
        db.commit()
        flash(f"Task for {da['artist_name']} marked pending and carried forward to tomorrow.", "info")
        
    return redirect(url_for('dashboard'))

@app.route('/target/set', methods=['POST'])
def set_monthly_target():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    artist_id = request.form.get('artist_id', type=int)
    target_points = request.form.get('target_points', type=int)
    month = request.form.get('month', '')
    
    if not artist_id or not target_points or not month:
        flash("Invalid target values.", "error")
        return redirect(url_for('points_page'))
        
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT team, name FROM users WHERE id = ?", (artist_id,))
    artist = cursor.fetchone()
    
    if not artist:
        flash("Artist not found.", "error")
        return redirect(url_for('points_page'))
        
    if session['role'] != 'Admin' and not (session['role'] == 'Lead' and session['team'] == artist['team']):
        flash("Unauthorized to set target for this artist.", "error")
        return redirect(url_for('points_page'))
        
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
    return redirect(url_for('points_page'))

@app.route('/points')
def points_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
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
        cursor.execute("SELECT id, name, username, team FROM users WHERE role = 'Artist' ORDER BY team")
        artists = cursor.fetchall()
        for artist in artists:
            team = artist['team']
            if team not in global_scoreboard:
                global_scoreboard[team] = []
            target, earned, pct = get_user_progress(artist['id'])
            global_scoreboard[team].append({
                'id': artist['id'],
                'name': artist['name'],
                'username': artist['username'],
                'target': target,
                'earned': earned,
                'pct': pct
            })
            
    target_artists = []
    if session['role'] == 'Lead':
        cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (session['team'],))
        target_artists = cursor.fetchall()
    elif session['role'] == 'Admin':
        cursor.execute("SELECT id, name, username, team FROM users WHERE role = 'Artist' ORDER BY name")
        target_artists = cursor.fetchall()
        
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_profile = cursor.fetchone()

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
        current_month=current_month
    )

# LAYER 4 - ATTENDANCE ROUTES
@app.route('/attendance/clock-in', methods=['POST'])
def clock_in():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
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
        
    # Policy Check: Grace 09:30, Late 09:31 - 11:00, Half Day after 11:00
    minutes_from_midnight = now.hour * 60 + now.minute
    
    if minutes_from_midnight <= 570:  # 09:30 AM
        status = 'Present'
        late_minutes = 0
    elif minutes_from_midnight <= 660:  # 11:00 AM
        status = 'Late'
        late_minutes = max(0, minutes_from_midnight - 585)  # counts from 09:45 AM (585 mins)
    else:
        status = 'Half Day'
        late_minutes = 0
        
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
        
    # Calculate elapsed hours
    in_dt = datetime.datetime.strptime(f"{today_str} {att['clock_in']}", "%Y-%m-%d %H:%M:%S")
    out_dt = now
    duration = out_dt - in_dt
    total_hours = max(0.0, duration.total_seconds() / 3600.0)
    
    # Retrieve user's shift length
    cursor.execute("SELECT shift_start, shift_end FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()
    
    try:
        start_h, start_m = map(int, user_info['shift_start'].split(':'))
        end_h, end_m = map(int, user_info['shift_end'].split(':'))
        shift_length = (end_h * 60 + end_m - (start_h * 60 + start_m)) / 60.0
        if shift_length < 0:
            shift_length += 24.0
    except:
        shift_length = 10.0 # Default fallback
        
    # Check off-day or holiday status
    try:
        today_date = datetime.datetime.strptime(today_str, '%Y-%m-%d').date()
    except:
        today_date = datetime.date.today()
    off_day = is_weekly_off(today_date)
    
    cursor.execute("SELECT COUNT(*) FROM holidays WHERE date = ?", (today_str,))
    is_holiday_flag = cursor.fetchone()[0] > 0
    
    if off_day or is_holiday_flag:
        # All hours count as extra compensation on off-days/holidays
        extra_hours = total_hours
    else:
        # Standard day: hours beyond shift length count as extra
        extra_hours = max(0.0, total_hours - shift_length)
        
    try:
        cursor.execute("""
            UPDATE attendance 
            SET clock_out = ?, total_hours = ?, extra_hours = ?
            WHERE id = ?
        """, (clock_out_str, total_hours, extra_hours, att['id']))
        
        cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Clock Out', ?)",
                       (session['user_id'], f"Clocked out today at {clock_out_str} (Duration: {total_hours:.2f} hrs, Extra: {extra_hours:.2f} hrs)"))
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
    
    # Permission check for other employee calendar
    if target_uid != session['user_id'] and session['role'] not in ['Admin', 'HR']:
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
        if day_str in att_list:
            status = att_list[day_str]['status']
            clock_in_time = att_list[day_str]['clock_in']
            clock_out_time = att_list[day_str]['clock_out']
            late_mins = att_list[day_str]['late_minutes']
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
            WHERE u.team = ? AND u.role = 'Artist'
        """, (today_str, session['team']))
        team_today = cursor.fetchall()
        
        # Monthly team statistics
        cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (session['team'],))
        team_artists = cursor.fetchall()
        
        for artist in team_artists:
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
                    SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_days,
                    SUM(CASE WHEN status = 'Half Day' THEN 1 ELSE 0 END) as half_days,
                    SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
                    SUM(extra_hours) as extra_hours_total,
                    SUM(late_minutes) as late_mins_total
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
            
            team_monthly_stats.append({
                'id': artist['id'],
                'name': artist['name'],
                'username': artist['username'],
                'present': stats['present_days'] if stats['present_days'] else 0,
                'late': stats['late_days'] if stats['late_days'] else 0,
                'half_day': stats['half_days'] if stats['half_days'] else 0,
                'absent': stats['absent_days'] if stats['absent_days'] else 0,
                'leaves': leaves_cnt,
                'extra_hours': stats['extra_hours_total'] if stats['extra_hours_total'] else 0.0,
                'late_minutes': stats['late_mins_total'] if stats['late_mins_total'] else 0
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
                    SUM(late_minutes) as late_mins_total
                FROM attendance
                WHERE user_id = ? AND strftime('%Y-%m', date) = ?
            """, (emp['id'], month_prefix))
            stats = cursor.fetchone()
            
            cursor.execute("""
                SELECT COUNT(*) FROM leaves 
                WHERE user_id = ? AND status = 'Approved' AND strftime('%Y-%m', start_date) = ?
            """, (emp['id'], month_prefix))
            leaves_cnt = cursor.fetchone()[0]
            
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
                'extra_hours': stats['extra_hours_total'] if stats['extra_hours_total'] else 0.0,
                'late_minutes': stats['late_mins_total'] if stats['late_mins_total'] else 0
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
        
    if session['role'] not in ['Admin', 'HR']:
        flash("Unauthorized to view other employee records.", "error")
        return redirect(url_for('attendance_page'))
        
    return redirect(url_for('attendance_page', employee_id=employee_id))

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
