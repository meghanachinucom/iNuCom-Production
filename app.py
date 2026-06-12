import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'production.db'
SCHEMA_FILE = 'schema.sql'

app = Flask(__name__)
app.secret_key = 'inucom_production_tracker_secret_key_LAN_offline_2026'

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
    conn = sqlite3.connect(DATABASE)
    
    if not db_exists:
        print("Initializing database from schema...")
        with open(SCHEMA_FILE, 'r') as f:
            conn.executescript(f.read())
        
        cursor = conn.cursor()
        # Seed users if empty
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            print("Seeding initial 28 user accounts...")
            default_pwd_hash = generate_password_hash("inucom@123")
            for user in SEEDED_USERS:
                cursor.execute("""
                    INSERT INTO users (name, username, password_hash, role, team, reports_to, must_change_password)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (user['name'], user['username'], default_pwd_hash, user['role'], user['team'], user['reports_to']))
            conn.commit()
            print("Seeding activity log...")
            cursor.execute("INSERT INTO activity_log (action, details) VALUES ('System Init', 'Database schema created and seeded with 28 user accounts.')")
            conn.commit()
    conn.close()

# Enforce auth and forced password change
@app.before_request
def enforce_auth_and_password_change():
    # Static files and auth endpoints are always allowed
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
            
            # Log the login activity
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
        
    # Get statistics from DB for the dashboard view to make it look active
    db = get_db()
    cursor = db.cursor()
    
    # Get user profile
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user_profile = cursor.fetchone()
    
    # Fetch some system activity logs for admins
    recent_logs = []
    if session['role'] == 'Admin':
        cursor.execute("""
            SELECT l.action, l.timestamp, l.details, u.name as user_name 
            FROM activity_log l 
            LEFT JOIN users u ON l.user_id = u.id 
            ORDER BY l.id DESC LIMIT 10
        """)
        recent_logs = cursor.fetchall()
        
    return render_template('dashboard.html', user=user_profile, logs=recent_logs)

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
