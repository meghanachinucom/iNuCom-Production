import os
import re

sidebar_replacement = """        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="sidebar-brand">
                <h2><span class="blue">iNuCom</span> <span class="red">Tracker</span></h2>
            </div>
            
            <div class="sidebar-user">
                <div class="user-name">{{ session['name'] }}</div>
                <div class="user-designation">
                    {% if session['role'] == 'Admin' %}
                        Admin
                    {% elif session['role'] == 'HR' %}
                        HR
                    {% elif session['role'] == 'Lead' %}
                        Lead
                    {% else %}
                        Artist
                    {% endif %}
                </div>
                <div class="user-team">{{ session['team'] }} Team</div>
            </div>
            
            <ul class="sidebar-menu">
                <li class="menu-section-title">Navigation</li>
                <li class="menu-item {% if request.endpoint == 'dashboard' and request.args.get('view') != 'pipeline' %}active{% endif %}">
                    <a href="{{ url_for('dashboard') }}"><span>Dashboard Overview</span></a>
                </li>
                <li class="menu-item {% if request.endpoint == 'dashboard' and request.args.get('view') == 'pipeline' %}active{% endif %}">
                    <a href="{{ url_for('dashboard', view='pipeline') }}"><span>Production Sheet</span></a>
                </li>
                <li class="menu-item {% if request.endpoint == 'points_page' %}active{% endif %}">
                    <a href="{{ url_for('points_page') }}"><span>Points &amp; Targets</span></a>
                </li>
                <li class="menu-item {% if request.endpoint == 'attendance_page' %}active{% endif %}">
                    <a href="{{ url_for('attendance_page') }}"><span>Attendance Tracker</span></a>
                </li>
                {% if session['role'] in ['Artist', 'Lead', 'HR'] %}
                <li class="menu-item {% if request.endpoint == 'leaves_page' %}active{% endif %}">
                    <a href="{{ url_for('leaves_page') }}"><span>Leaves and Permissions</span></a>
                </li>
                {% if session['role'] == 'Lead' %}
                <li class="menu-item {% if request.endpoint == 'team_approvals_page' %}active{% endif %}">
                    <a href="{{ url_for('team_approvals_page') }}"><span>Team Approvals</span></a>
                </li>
                {% endif %}
                {% endif %}
                
                {% if session['role'] == 'Admin' %}
                <li class="menu-item {% if request.endpoint == 'system_approvals_page' %}active{% endif %}">
                    <a href="{{ url_for('system_approvals_page') }}"><span>System Approvals</span></a>
                </li>
                {% endif %}
                
                {% if session['role'] == 'Admin' %}
                <li class="menu-item {% if request.endpoint == 'compensation_page' %}active{% endif %}">
                    <a href="{{ url_for('compensation_page') }}"><span>Compensation View</span></a>
                </li>
                {% endif %}
                <li class="menu-item {% if request.endpoint == 'notifications_page' %}active{% endif %}">
                    <a href="{{ url_for('notifications_page') }}">
                        <span>Notifications{% if unread_notif_count > 0 %} <span style="background:var(--color-red);color:#fff;border-radius:10px;padding:1px 7px;font-size:10px;margin-left:4px;">{{ unread_notif_count }}</span>{% endif %}</span>
                    </a>
                </li>
                {% if session['role'] == 'Admin' %}
                <li class="menu-section-title">Admin</li>
                <li class="menu-item {% if request.endpoint == 'reports_page' %}active{% endif %}">
                    <a href="{{ url_for('reports_page') }}"><span>Reports</span></a>
                </li>
                {% elif session['role'] == 'HR' %}
                <li class="menu-section-title">HR Management</li>
                <li class="menu-item {% if request.endpoint == 'holidays_page' %}active{% endif %}">
                    <a href="{{ url_for('holidays_page') }}"><span>Holidays</span></a>
                </li>
                <li class="menu-item {% if request.endpoint == 'upload_project_page' %}active{% endif %}">
                    <a href="{{ url_for('upload_project_page') }}"><span>Upload Project</span></a>
                </li>
                <li class="menu-item {% if request.endpoint == 'activity_log_page' %}active{% endif %}">
                    <a href="{{ url_for('activity_log_page') }}"><span>Activity Log</span></a>
                </li>
                {% endif %}
            </ul>
            
            <div class="sidebar-footer">
                <a href="{{ url_for('logout') }}" class="btn-logout">
                    <span>Sign Out</span>
                </a>
            </div>
        </aside>"""

# Match from <!-- Sidebar --> (optional) to </aside>
# We can search for the <aside class="sidebar">... </aside> tag directly and optionally match <!-- Sidebar --> if it is there
pattern = re.compile(r'(<!--\s*Sidebar\s*-->\s*)?<aside class="sidebar">.*?</aside>', re.DOTALL)

templates_dir = 'templates'
migrated_count = 0

for filename in os.listdir(templates_dir):
    if filename.endswith('.html'):
        filepath = os.path.join(templates_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if '<aside class="sidebar">' in content:
            new_content, count = pattern.subn(sidebar_replacement, content)
            if count > 0:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Migrated sidebar in {filename}")
                migrated_count += 1
            else:
                print(f"Skipped {filename} (could not match pattern)")

print(f"Done! Migrated {migrated_count} files.")
