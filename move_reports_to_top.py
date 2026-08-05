import glob, re

for path in sorted(glob.glob('templates/*.html')):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove any existing Reports menu item block
    cleaned = re.sub(r'\s*<li class="menu-item \{% if request\.endpoint == \'reports_page\' %\}active\{% endif %\}">\s*<a href="\{\{ url_for\(\'reports_page\'\) \}\}"><span>Reports</span></a>\s*</li>', '', content)
    cleaned = re.sub(r'\s*\{% if session\[\'role\'\] in \[\'Admin\', \'HR\'\] %\}\s*<li class="menu-item \{% if request\.endpoint == \'reports_page\' %\}active\{% endif %\}">\s*<a href="\{\{ url_for\(\'reports_page\'\) \}\}"><span>Reports</span></a>\s*</li>\s*\{% endif %\}', '', cleaned)
    cleaned = re.sub(r'\s*\{% if session\[\'role\'\] == \'Admin\' %\}\s*<li class="menu-item \{% if request\.endpoint == \'reports_page\' %\}active\{% endif %\}">\s*<a href="\{\{ url_for\(\'reports_page\'\) \}\}"><span>Reports</span></a>\s*</li>\s*\{% endif %\}', '', cleaned)

    reports_block = """
                {% if session['role'] in ['Admin', 'HR'] %}
                <li class="menu-item {% if request.endpoint == 'reports_page' %}active{% endif %}">
                    <a href="{{ url_for('reports_page') }}"><span>Reports</span></a>
                </li>
                {% endif %}"""

    nav_header = '<li class="menu-section-title">Navigation</li>'
    if nav_header in cleaned:
        new_content = cleaned.replace(nav_header, nav_header + reports_block, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Placed Reports at very top of sidebar in {path}")

print("Done updating sidebar nav order in all 17 templates!")
