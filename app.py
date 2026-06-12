import os
import sqlite3
import datetime
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
            cursor.execute("SELECT points FROM file_pipeline LIMIT 1")
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
            
            # Find artist ID if assigned
            artist_id = None
            if f_demo['assigned']:
                cursor.execute("SELECT id FROM users WHERE username = ?", (f_demo['assigned'],))
                res = cursor.fetchone()
                if res:
                    artist_id = res[0]
            
            # Default complexity points based on active stage
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
                
                # If currently assigned/in progress, seed a daily assignment for today
                if stage == f_demo['active_stage'] and stage_assigned and stage_status != 'Done':
                    cursor.execute("""
                        INSERT INTO daily_assignments (user_id, date, file_id, task_description, points, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (stage_assigned, today_str, file_id, f"{stage}: {f_demo['name']}", stage_points, stage_status))
        
        # Seed targets for current month for all artists (default 500)
        current_month = datetime.date.today().strftime('%Y-%m')
        cursor.execute("SELECT id FROM users WHERE role = 'Artist'")
        artist_ids = [row[0] for row in cursor.fetchall()]
        for aid in artist_ids:
            cursor.execute("INSERT INTO monthly_targets (user_id, month, target_points) VALUES (?, ?, ?)", (aid, current_month, 500))
            
        # Seed some demo points (points earned earlier this week)
        yesterday_str = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        # Award 60 points to raveendra yesterday
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
        
    # Get all files in selected chapter
    files = []
    if chapter_id:
        cursor.execute("SELECT * FROM files WHERE chapter_id = ? ORDER BY id", (chapter_id,))
        files = cursor.fetchall()
        
    # Build status matrix for the active chapter
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
            
    # Resolve user active stage queue (Leads and Admins)
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
            
            # Fetch artists for assignment selection
            if session['role'] == 'Lead':
                cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (session['team'],))
                artists = cursor.fetchall()
            else:
                target_team = STAGE_TEAMS[queue_stage]
                cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (target_team,))
                artists = cursor.fetchall()

    # EOD Validation Panel List (Leads / Admins)
    validation_list = []
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    if session['role'] in ['Lead', 'Admin'] and chapter_id:
        # Fetch today's assignments for EOD validation for this team/stage
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

    # Artist personal tasks board
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
    
    # 1. Morning Assignment (10:00 AM)
    if now.hour >= 10:
        # Check if there are active files open at any pipeline stage that are not assigned to anyone
        cursor.execute("""
            SELECT COUNT(*) 
            FROM file_pipeline fp
            JOIN files f ON fp.file_id = f.id
            WHERE fp.status = 'Open' AND f.chapter_id = ?
        """, (chapter_id,))
        open_count = cursor.fetchone()[0]
        if open_count > 0:
            late_assignment_flag = True
            
    # 2. EOD Validation (6:30 PM)
    # Check if past 6:30 PM and there are unvalidated daily assignments for today for this team
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

    # Fetch audit logs for admins
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
        today_str=today_str
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
        # Update pipeline step status, assignee, and complexity points
        cursor.execute("""
            UPDATE file_pipeline 
            SET assigned_to = ?, status = ?, points = ?
            WHERE file_id = ? AND step_name = ?
        """, (artist_id, new_status, points, file_id, step_name))
        
        cursor.execute("SELECT name, chapter_id FROM files WHERE id = ?", (file_id,))
        f_info = cursor.fetchone()
        
        # If assigning an artist, create a daily assignment for today
        if artist_id:
            today_str = datetime.date.today().strftime('%Y-%m-%d')
            # Check if active daily assignment for today already exists
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
    # Keep standard status updates (Artist setting In Progress or Done).
    # Done triggers direct EOD Validation style done, or artist sets done.
    # To support direct EOD done credits points, we also update file_pipeline.
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
        
    # Artist can update daily assignment to Done or In Progress
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    cursor.execute("""
        UPDATE file_pipeline 
        SET status = ? 
        WHERE file_id = ? AND step_name = ?
    """, (status, file_id, step_name))
    
    # Update today's daily assignment status as well
    cursor.execute("""
        UPDATE daily_assignments 
        SET status = 'Pending' if ? == 'In Progress' else 'Pending' 
        WHERE file_id = ? AND user_id = ? AND date = ?
    """, ('Pending' if status == 'In Progress' else 'Pending', file_id, pipeline_step['assigned_to'], today_str))
    
    log_details = f"Artist updated status of '{pipeline_step['file_name']}' [{step_name}] to '{status}'"
    
    # If artist marks Done, it goes to Lead EOD queue for final approval (it stays Pending in daily_assignments
    # until validated Done by Lead, which awards points).
    # However, if Admin or Lead changes it, they can validate it directly.
    if status == 'Done' and (is_lead or is_admin):
        # Direct validation via Lead/Admin
        cursor.execute("""
            UPDATE daily_assignments 
            SET status = 'Done' 
            WHERE file_id = ? AND date = ?
        """, (file_id, today_str))
        
        # Credit points
        cursor.execute("""
            INSERT INTO points (user_id, date, points, reason, awarded_by)
            VALUES (?, ?, ?, ?, ?)
        """, (pipeline_step['assigned_to'], today_str, pipeline_step['points'], 
              f"Completed stage: {pipeline_step['file_name']} [{step_name}]", session['user_id']))
              
        if step_name == 'Content':
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE files SET content_released_at = ? WHERE id = ?", (now_str, file_id))
            
        # Move to next stage
        idx = PIPELINE_STAGES.index(step_name)
        if idx < len(PIPELINE_STAGES) - 1:
            next_stage = PIPELINE_STAGES[idx + 1]
            cursor.execute("""
                UPDATE file_pipeline 
                SET status = 'Open' 
                WHERE file_id = ? AND step_name = ? AND status = 'Pending'
            """, (file_id, next_stage))
            
    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Status Update', ?)",
                   (session['user_id'], 'Pipeline Update', log_details))
    db.commit()
    
    flash(f"Status updated for '{pipeline_step['file_name']}' [{step_name}] to '{status}'.", "success")
    return redirect(url_for('dashboard', chapter_id=pipeline_step['chapter_id']))

@app.route('/assignment/validate', methods=['POST'])
def validate_assignment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    assignment_id = request.form.get('assignment_id', type=int)
    validation_status = request.form.get('validation_status', '') # 'Done' or 'Pending'
    remarks = request.form.get('remarks', '').strip()
    
    if not assignment_id or validation_status not in ['Done', 'Pending']:
        flash("Invalid validation parameters.", "error")
        return redirect(url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    # Retrieve assignment details
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
        
    # Permission check: Admin or Lead of that team
    if session['role'] != 'Admin' and not (session['role'] == 'Lead' and session['team'] == da['team']):
        flash("Unauthorized to validate assignments for this team.", "error")
        return redirect(url_for('dashboard'))
        
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    if validation_status == 'Done':
        # Mark daily assignment as Done
        cursor.execute("UPDATE daily_assignments SET status = 'Done', remarks = ? WHERE id = ?", ("Validated Done", assignment_id))
        
        # Get active step name for this file/artist
        cursor.execute("""
            SELECT step_name, points FROM file_pipeline 
            WHERE file_id = ? AND assigned_to = ? AND status IN ('Open', 'In Progress')
        """, (da['file_id'], da['user_id']))
        step_row = cursor.fetchone()
        
        if step_row:
            step_name = step_row['step_name']
            points_val = step_row['points']
            
            # Set pipeline step status to Done
            cursor.execute("""
                UPDATE file_pipeline SET status = 'Done' 
                WHERE file_id = ? AND step_name = ?
            """, (da['file_id'], step_name))
            
            # Credit points to the artist
            cursor.execute("""
                INSERT INTO points (user_id, date, points, reason, awarded_by)
                VALUES (?, ?, ?, ?, ?)
            """, (da['user_id'], today_str, points_val, f"EOD Completed: {da['file_name']} [{step_name}]", session['user_id']))
            
            # Record content release
            if step_name == 'Content':
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("UPDATE files SET content_released_at = ? WHERE id = ?", (now_str, da['file_id']))
                
            # Transition to the next stage
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
            
        # Update current daily assignment with remarks/reason
        cursor.execute("UPDATE daily_assignments SET status = 'Pending', remarks = ? WHERE id = ?", (remarks, assignment_id))
        
        # Calculate tomorrow's date
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        # Roll forward: Create a new daily assignment for tomorrow
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
    
    # Check artist's team
    cursor.execute("SELECT team, name FROM users WHERE id = ?", (artist_id,))
    artist = cursor.fetchone()
    
    if not artist:
        flash("Artist not found.", "error")
        return redirect(url_for('points_page'))
        
    # Permission check: Admin or Lead of artist's team
    if session['role'] != 'Admin' and not (session['role'] == 'Lead' and session['team'] == artist['team']):
        flash("Unauthorized to set target for this artist.", "error")
        return redirect(url_for('points_page'))
        
    # Check if target already exists
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
    
    # 1. Fetch current month metrics
    current_month = datetime.date.today().strftime('%Y-%m')
    
    # Helper to calculate points and progress for a user
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
    
    # 2. Build 7-day Weekly Breakdown (Monday - Sunday)
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday()) # Monday
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
        
    # 3. Resolve Admin / Lead views
    team_scoreboard = []
    global_scoreboard = {}
    
    if session['role'] == 'Lead':
        # Fetch scoreboard for all artists on the Lead's team
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
        # Fetch scoreboard for all artists, grouped by team
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
            
    # Fetch all artists that this user has authority to set target for (Leads/Admins)
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

# Initialize database on startup
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
