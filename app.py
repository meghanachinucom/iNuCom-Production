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
    {"chapter_name": "ch_13", "name": "FW_13_08_SunLight", "description": "Daytime lighting and ambient occlusion rendering", "active_stage": "Lighting/Rendering", "status": "In Progress", "assigned": "abhilash", "content_released_offset": 21600}
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
            cursor.execute("SELECT content_released_at FROM files LIMIT 1")
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
            # We set must_change_password=0 by default now for convenience of testing,
            # but let's keep the option. To match user request, let's set it to 0 as updated.
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
        
        # Seed demo files
        print("Seeding demo pipeline files...")
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
            
            for stage in PIPELINE_STAGES:
                if stage == f_demo['active_stage']:
                    stage_status = f_demo['status']
                    stage_assigned = artist_id
                elif PIPELINE_STAGES.index(stage) < PIPELINE_STAGES.index(f_demo['active_stage']):
                    stage_status = 'Done'
                    stage_assigned = None
                else:
                    stage_status = 'Pending'
                    stage_assigned = None
                    
                cursor.execute("""
                    INSERT INTO file_pipeline (file_id, step_name, status, assigned_to)
                    VALUES (?, ?, ?, ?)
                """, (file_id, stage, stage_status, stage_assigned))
        
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
    
    if not chapter_id and chapters:
        chapter_id = chapters[0]['id']
        
    # Get all files in selected chapter
    files = []
    if chapter_id:
        cursor.execute("SELECT * FROM files WHERE chapter_id = ? ORDER BY id", (chapter_id,))
        files = cursor.fetchall()
        
    # Build status matrix for the active chapter
    # matrix[file_id][stage_name] = {status, artist_name, artist_username}
    matrix = {}
    if chapter_id:
        cursor.execute("""
            SELECT fp.file_id, fp.step_name, fp.status, u.name as artist_name, u.username as artist_username 
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
                'artist_name': row['artist_name'],
                'artist_username': row['artist_username']
            }
            
    # Resolve user active stage queue (Leads and Admins)
    lead_queue = []
    queue_stage = None
    artists = []
    
    if session['role'] in ['Lead', 'Admin']:
        if session['role'] == 'Lead':
            # Map lead team to pipeline stage
            for stage, team in STAGE_TEAMS.items():
                if team == session['team']:
                    queue_stage = stage
                    break
        else:
            # Admins can choose which queue stage to view, default to first stage
            queue_stage = request.args.get('queue_stage', 'Content')
            
        if queue_stage and chapter_id:
            # Query open/in-progress files for this stage in this chapter
            # Sort by content_released_at. If stage is Content, order by file_id
            if queue_stage == 'Content':
                order_clause = "f.id ASC"
            else:
                order_clause = "f.content_released_at ASC, f.id ASC"
                
            cursor.execute(f"""
                SELECT f.id as file_id, f.name as file_name, f.description as file_desc, 
                       fp.id as pipeline_id, fp.status as step_status, fp.assigned_to as step_assigned_to,
                       f.content_released_at
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
                # Admin can assign anyone on the target team for the selected stage
                target_team = STAGE_TEAMS[queue_stage]
                cursor.execute("SELECT id, name, username FROM users WHERE team = ? AND role = 'Artist'", (target_team,))
                artists = cursor.fetchall()

    # Artist personal tasks board
    artist_tasks = []
    if session['role'] == 'Artist':
        cursor.execute("""
            SELECT f.id as file_id, f.name as file_name, f.description as file_desc, 
                   fp.id as pipeline_id, fp.step_name, fp.status as step_status,
                   p.name as project_name, c.name as chapter_name
            FROM file_pipeline fp
            JOIN files f ON fp.file_id = f.id
            JOIN chapters c ON f.chapter_id = c.id
            JOIN projects p ON c.project_id = p.id
            WHERE fp.assigned_to = ? AND fp.status IN ('Open', 'In Progress')
            ORDER BY p.name, c.name, f.name
        """, (session['user_id'],))
        artist_tasks = cursor.fetchall()

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
        files=files,
        matrix=matrix,
        stages=PIPELINE_STAGES,
        lead_queue=lead_queue,
        queue_stage=queue_stage,
        artists=artists,
        artist_tasks=artist_tasks
    )

@app.route('/file/add', methods=['POST'])
def add_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    # Content Lead and Admins only
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
        
        # Initialize pipeline stages
        for stage in PIPELINE_STAGES:
            # First stage (Content) is Open, others are Pending
            status = 'Open' if stage == 'Content' else 'Pending'
            cursor.execute("""
                INSERT INTO file_pipeline (file_id, step_name, status, assigned_to)
                VALUES (?, ?, ?, NULL)
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
        
    # Permission check: Admin or Lead of target team
    if session['role'] != 'Admin' and not (session['role'] == 'Lead' and session['team'] == target_team):
        flash("Unauthorized to assign files for this stage.", "error")
        return redirect(url_for('dashboard'))
        
    db = get_db()
    cursor = db.cursor()
    
    # Verify the artist belongs to target team (if artist assigned)
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
        
    cursor.execute("""
        UPDATE file_pipeline 
        SET assigned_to = ?, status = ?
        WHERE file_id = ? AND step_name = ?
    """, (artist_id, new_status, file_id, step_name))
    
    cursor.execute("SELECT name, chapter_id FROM files WHERE id = ?", (file_id,))
    f_info = cursor.fetchone()
    
    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Assign File', ?)",
                   (session['user_id'], f"Assigned '{f_info['name']}' [{step_name}] to {artist_name}"))
    db.commit()
    
    flash(f"File updated: {f_info['name']} assigned to {artist_name}.", "success")
    return redirect(url_for('dashboard', chapter_id=f_info['chapter_id']))

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
    
    # Retrieve pipeline details
    cursor.execute("""
        SELECT fp.id, fp.status, fp.assigned_to, f.name as file_name, f.chapter_id 
        FROM file_pipeline fp
        JOIN files f ON fp.file_id = f.id
        WHERE fp.file_id = ? AND fp.step_name = ?
    """, (file_id, step_name))
    pipeline_step = cursor.fetchone()
    
    if not pipeline_step:
        flash("Pipeline step not found.", "error")
        return redirect(url_for('dashboard'))
        
    target_team = STAGE_TEAMS.get(step_name)
    
    # Permission check: Assigned artist, their lead, or Admin
    is_assigned = (pipeline_step['assigned_to'] == session['user_id'])
    is_lead = (session['role'] == 'Lead' and session['team'] == target_team)
    is_admin = (session['role'] == 'Admin')
    
    if not (is_assigned or is_lead or is_admin):
        flash("Unauthorized to update status for this stage.", "error")
        return redirect(url_for('dashboard'))
        
    cursor.execute("""
        UPDATE file_pipeline 
        SET status = ? 
        WHERE file_id = ? AND step_name = ?
    """, (status, file_id, step_name))
    
    log_details = f"Updated status of '{pipeline_step['file_name']}' [{step_name}] to '{status}'"
    
    if status == 'Done':
        # If Content stage marked done, record content_released_at
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
            log_details += f". Released to next stage: {next_stage}."
        else:
            # Final pipeline stage completed
            cursor.execute("UPDATE files SET status = 'Completed' WHERE id = ?", (file_id,))
            log_details += ". Project file fully completed."
            
    cursor.execute("INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                   (session['user_id'], 'Pipeline Update', log_details))
    db.commit()
    
    flash(f"Status updated for '{pipeline_step['file_name']}' [{step_name}] to '{status}'.", "success")
    return redirect(url_for('dashboard', chapter_id=pipeline_step['chapter_id']))

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
