import sqlite3
from werkzeug.security import check_password_hash

conn = sqlite3.connect('production.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT username, password_hash FROM users WHERE username IN ('prabhas','pooja','vasu','sana')")
rows = c.fetchall()
pwds = ['inucom@123', 'prabhas123', 'pooja123', 'vasu123', 'sana123', 'test@123', '123456']
for r in rows:
    matches = {p: check_password_hash(r['password_hash'], p) for p in pwds}
    working = [p for p, ok in matches.items() if ok]
    print(f"{r['username']}: working passwords = {working}")
conn.close()
