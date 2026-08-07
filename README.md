# 🚀 iNuCom Production Tracker

An **Enterprise Production, Team Workflow, HR, Attendance, and Performance Management System** built with Python Flask and SQLite. Designed specifically for 3D/VFX/Animation studios and digital media production companies to streamline project execution, stage pipelines, attendance tracking, leave requests, employee targets, compensation, and approval chains.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [✨ Key Features](#-key-features)
- [🛠️ Tech Stack](#️-tech-stack)
- [🏗️ Database Schema & Architecture](#️-database-schema--architecture)
- [📂 Directory Structure](#-directory-structure)
- [⚡ Quick Start & Installation](#-quick-start--installation)
- [👥 Seeded Default Users & Roles](#-seeded-default-users--roles)
- [🎨 Production Pipeline Stages](#-production-pipeline-stages)
- [📊 Reporting & Excel Export](#-reporting--excel-export)
- [🧪 Verification & Migration Scripts](#-verification--migration-scripts)

---

## 📖 Overview

**iNuCom Production Tracker** serves as a single source of truth for managing digital media assets, multi-stage production pipelines, daily staff assignments, employee timekeeping, leave approvals, monthly performance points, and payroll metrics.

With role-based dashboards tailored for Administrators, HR Personnel, Team Leads, and Artists/Executives, the platform provides seamless operational clarity across projects and team workflows.

---

## ✨ Key Features

### 🏢 Multi-Level Role-Based Access Control (RBAC)
- Multi-tiered hierarchy supporting roles across **L1 through L10** levels, Admin, HR, Team Lead, and Artist/Executive.
- Granular permission matrix (`permissions.html`) allowing dynamic control over route and feature access per role.

### 🎬 Production & 3D Pipeline Tracking
- Hierarchical structure: **Projects ➔ Chapters ➔ Files ➔ Pipeline Steps**.
- Complete tracking across **12 standardized 3D/VFX pipeline stages** (Content, Modeling, Texturing, Rig, Animation, FBX Export, VFX, Lighting, Rendering, 3D Comp, Motion Graphics, VR).
- Status workflow tracking (Pending, In Progress, Completed, Approved, On Hold) with internal lead and content status reviews.
- **Bulk Excel Upload** (`upload_project.html`) to quickly import complete projects, chapters, and tasks via `.xlsx` spreadsheets.

### 📋 Daily Assignments & EOD Submissions
- Daily task assignment to employees with custom point values.
- **End of Day (EOD)** validation portal where Team Leads review and approve daily task submissions and progress remarks.

### ⏱️ Attendance & Timekeeping System
- Daily **Clock In / Clock Out** interface with optional device binding.
- Configurable shift timing (Default: 09:00 AM - 07:00 PM).
- Automatic calculation of **Late Minutes, Early Departure, Total Worked Hours, and Extra/OT Hours**.
- Admin/HR attendance status overrides and historical log tracking.

### 🌴 Leaves & Short Permission Requests
- Multi-type Leave Portal (Casual, Sick, Paid, Unpaid) with date range selection and reasoning.
- **Short Permission Requests** for hourly time-offs.
- Multi-stage hierarchical approval chains routing requests dynamically through Team Leads, HR, and Admin (`approvals` system).

### 🎯 Points & Performance Gamification
- Dynamic point allocation for tasks and assignments.
- Monthly target setting (e.g., standard 500 points target) with visual progress tracking.
- Individual and team performance dashboards & leaderboards.

### 💰 Payroll & Compensation Tracker
- Salary structure monitoring including Basic Salary, Carry-Forward amounts, and performance bonuses based on monthly points earned.

### 🔔 Notifications & Activity Audit Trail
- Real-time in-app notification center for pending approvals, task assignments, and status updates.
- Full audit logging (`activity_log.html`) capturing user actions, logins, logouts, administrative overrides, and system changes.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.8+, Flask v3.0.3, Werkzeug
- **Database**: SQLite3 (`production.db`)
- **Data Import/Export**: OpenPyXL (`.xlsx` spreadsheet handling)
- **Frontend**: HTML5, Jinja2 Templating, Vanilla CSS3 (Glassmorphism, Dark/Light themed responsive layouts), JavaScript (ES6)

---

## 🏗️ Database Schema & Architecture

The system utilizes an SQLite relational database configured via `schema.sql`. Core tables include:

| Table Name | Purpose / Description |
|---|---|
| `users` | Employee profiles, credentials, role (L1-L10, Admin, HR, etc.), team, shift hours, basic salary. |
| `projects` | High-level project metadata and active statuses. |
| `chapters` | Project subdivisions linked to parent projects. |
| `files` | Individual asset/task entries belonging to chapters with lead & content review statuses. |
| `file_pipeline` | Stage-by-stage pipeline steps assigned to specific team members with point allocations. |
| `teams` | Team definitions, departments, and assigned Team Lead user IDs. |
| `daily_assignments` | Daily user tasks, points, status, remarks, and submission timestamps. |
| `eod_validations` | End-Of-Day work summaries submitted by users and validated by leads. |
| `attendance` | Daily clock-in/out records, device IDs, late/early minutes, and worked/extra hours. |
| `leaves` | Leave applications, leave types, date ranges, and approval statuses. |
| `permission_requests` | Short hourly leave requests with reason and approval tracking. |
| `permissions` | Role-based feature permission flags. |
| `points` | Points transactions awarded to employees. |
| `monthly_targets` | Monthly target points set for staff members. |
| `holidays` | Public and company holiday calendar schedule. |
| `approvals` | Multi-step approval chain state machine for leaves, permissions, and system requests. |
| `notifications` | User notifications with read/unread status and links. |
| `activity_log` | System audit trail logging all major user activities. |

---

## 📂 Directory Structure

```
iNuCom Production/
├── app.py                      # Main Flask application (routes, DB setup, logic)
├── schema.sql                  # Database schema DDL script
├── requirements.txt            # Python dependencies
├── production.db               # SQLite database file
├── migrate_admin_sidebars.py   # Migration script for sidebar configurations
├── migrate_l6.py               # Migration script for L6 role setup
├── migrate_l9l10.py            # Migration script for L9 & L10 role setup
├── move_reports_to_top.py      # Migration script for UI navigation adjustments
├── check_passwords.py          # Password verification utility
├── verify_*.py                 # Suite of feature test & verification scripts
├── static/                     # Static files (CSS, JS, assets)
└── templates/                  # Jinja2 HTML templates
    ├── activity_log.html       # System audit log dashboard
    ├── attendance.html         # Main HR/Lead attendance management
    ├── attendance_user.html    # User clock-in/out portal
    ├── change_password.html    # Password change screen
    ├── compensation.html      # Payroll & salary compensation dashboard
    ├── dashboard.html         # Main role-based user dashboard
    ├── holidays.html          # Company holiday calendar management
    ├── leaves.html             # Leave application and history modal
    ├── login.html              # System login page
    ├── notifications.html      # User notifications center
    ├── permissions.html        # Role permission settings matrix
    ├── points.html             # Points and monthly targets tracker
    ├── reports.html            # Overall system & executive reports
    ├── system_approvals.html   # System-wide approval request center
    ├── team_approvals.html     # Team Lead approval dashboard
    ├── upload_project.html     # Bulk Excel project upload tool
    └── work_reports.html       # Staff daily work summaries & export
```

---

## ⚡ Quick Start & Installation

### 1. Prerequisites
- Python 3.8 or higher installed on your system.
- Git (optional, for cloning).

### 2. Setup Virtual Environment
```bash
# Navigate to project directory
cd "iNuCom Production"

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Database Initialization
The application automatically creates and initializes `production.db` using `schema.sql` on its first run if the database file does not exist.

### 5. Launch Application
```bash
python app.py
```
The server will start at `http://localhost:5000` (or `http://<your-ip>:5000` across your local network).

---

## 👥 Seeded Default Users & Roles

The system comes pre-configured with default accounts across teams:

| Username | Name | Default Role | Team |
|---|---|---|---|
| `vasu` | Vasu | Admin | Management |
| `meghana` | Meghana. Ch | HR | HR |
| `pooja` | Pooja. L | Lead | Content |
| `prabhas` | Prabhas | Artist | Content |
| `sana` | Sana | Artist | Content |
| `amit` | Amit Pounikar | Lead | Modeling |
| `raveendra` | Raveendra. K | Artist | Modeling |
| `nagireddy` | Nagireddy. E | Artist | Modeling |
| `rajendra` | Rajendra Prasad. K | Lead | Char MDL |
| `mahesh` | Mahesh Goud. C | Lead | Texturing |
| `rattaiah` | Rattaiah. Y | Artist | Texturing |
| `sai` | Sai Ravi Varma. G | Lead | Rig |
| `gowri` | Gowri Sandeep. M | Artist | Rig |
| `anilboda` | Anil Boda | Lead | Animation |
| `ganesh` | Ganesh Bykani | Artist | Animation |
| `bhavani` | K. Bhavani | Artist | Animation |

---

## 🎨 Production Pipeline Stages

Files assigned in the tracker move sequentially through 12 pipeline stages:

1. **Content**
2. **Modeling**
3. **Texturing**
4. **Rig**
5. **Animation**
6. **FBX export**
7. **VFX**
8. **Lightning**
9. **Rendering**
10. **3D Comp**
11. **Motion graphics**
12. **VR**

---

## 📊 Reporting & Excel Export

- **Work Summary Export**: Filter task logs by date range, month/year, employee, or team, and export a formatted dual-sheet `.xlsx` report containing:
  - **Sheet 1**: Staff Work Summary (Tasks completed, pending, total points, days worked, total hours).
  - **Sheet 2**: Detailed Task Log (Date, employee, project, chapter, task description, stage, points, status).
- **Bulk Upload**: Import large scale project hierarchies directly from Excel template files via `/upload_project`.

---

## 🧪 Verification & Migration Scripts

The workspace contains dedicated utility and verification scripts:

- `verify_admin_live.py`: Tests Admin portal permissions & functionality.
- `verify_hr_live.py`: Tests HR attendance, leaves, and salary features.
- `verify_leaves_live.py`: Validates leave creation and multi-level approval workflows.
- `verify_attendance.py`: Verifies time calculation, clock-in/out logic, and 12-hour formatting.
- `verify_permissions_live.py`: Tests dynamic permission evaluation across roles.
- `verify_pipeline.py`: Tests project file pipeline creation and progress updates.
- `migrate_admin_sidebars.py` / `migrate_l6.py` / `migrate_l9l10.py`: Database schema and configuration migration scripts.

---

## 📄 License & Maintenance

Developed for **iNuCom Production Tracker**. All rights reserved.
