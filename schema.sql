-- Schema DDL for iNuCom Production Tracker (SQLCipher-encrypted SQLite)

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    team TEXT NOT NULL,
    reports_to TEXT,
    must_change_password INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    lead_id INTEGER,
    department TEXT,
    FOREIGN KEY (lead_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS pipeline_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_name TEXT NOT NULL UNIQUE,
    team_id INTEGER,
    team_name TEXT NOT NULL,
    stage_order INTEGER NOT NULL,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    project_type TEXT DEFAULT 'Standard',
    status TEXT DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    file_type TEXT DEFAULT 'Asset',
    complexity TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'Yet to Start',
    assigned_to INTEGER,
    is_comp_ai INTEGER DEFAULT 0,
    comp_ai_artist_id INTEGER,
    content_released_at TEXT,
    start_date TEXT,
    end_date TEXT,
    remarks TEXT,
    final_approval_date TEXT,
    internal_lead_status TEXT DEFAULT 'Pending',
    internal_content_status TEXT DEFAULT 'Pending',
    final_review_status TEXT DEFAULT 'Pending',
    take_count INTEGER DEFAULT 0,
    rework_reason TEXT,
    hold_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS file_pipeline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    stage_order INTEGER DEFAULT 0,
    team_name TEXT,
    status TEXT DEFAULT 'Locked',
    assigned_to INTEGER,
    complexity TEXT DEFAULT 'Medium',
    points INTEGER DEFAULT 0,
    time_worked REAL DEFAULT 0.0,
    take_count INTEGER DEFAULT 0,
    start_date TEXT,
    end_date TEXT,
    submitted_at TEXT,
    rework_reason TEXT,
    rework_target_team TEXT,
    hold_reason TEXT,
    remarks TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(file_id, step_name)
);

CREATE TABLE IF NOT EXISTS daily_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    file_id INTEGER,
    stage_name TEXT,
    team_name TEXT,
    complexity TEXT DEFAULT 'Medium',
    task_description TEXT NOT NULL,
    points INTEGER DEFAULT 0,
    time_worked REAL DEFAULT 0.0,
    status TEXT DEFAULT 'Yet to Start',
    remarks TEXT,
    submit_time TEXT,
    submitted_at TEXT,
    upload_log_id INTEGER,
    deadline_days INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL,
    FOREIGN KEY (upload_log_id) REFERENCES daily_upload_logs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS eod_validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    submission_details TEXT,
    status TEXT DEFAULT 'Pending',
    validated_by INTEGER,
    validation_date TEXT,
    remarks TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (validated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    permission_name TEXT NOT NULL,
    allowed INTEGER DEFAULT 0,
    UNIQUE(role, permission_name)
);

CREATE TABLE IF NOT EXISTS points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    file_id INTEGER,
    stage_name TEXT,
    points INTEGER NOT NULL,
    reason TEXT,
    awarded_by INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL,
    FOREIGN KEY (awarded_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS monthly_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    month TEXT NOT NULL,
    target_points INTEGER DEFAULT 500,
    target_details TEXT,
    status TEXT DEFAULT 'Pending',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

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
);

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
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS self_logged_work (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    team TEXT NOT NULL,
    file_id INTEGER,
    step_name TEXT,
    status TEXT,
    remarks TEXT,
    approval_status TEXT DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
