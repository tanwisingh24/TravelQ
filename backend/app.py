"""
TravelQ — Travel Budget Planner (v2 — with Authentication)
Flask REST API + SQLite3 + JWT Auth
"""

import uuid
import json
import hashlib
import hmac
import base64
import os
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, g

import db_compat

app = Flask(__name__, static_folder='../frontend', static_url_path='')

# ──────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'travelq-secret-key-change-in-prod-2025')
TOKEN_EXPIRY_HOURS = 24

# ──────────────────────────────────────────
# SIMPLE JWT (no external libs needed)
# ──────────────────────────────────────────
def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + '=' * (pad % 4))

def create_token(user_id: str, username: str) -> str:
    header = b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64url_encode(json.dumps({
        "sub": user_id,
        "username": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRY_HOURS * 3600
    }).encode())
    msg = f"{header}.{payload}"
    sig = b64url_encode(hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest())
    return f"{msg}.{sig}"

def verify_token(token: str):
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header, payload, sig = parts
        msg = f"{header}.{payload}"
        expected = b64url_encode(hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(b64url_decode(payload))
        if data.get('exp', 0) < time.time():
            return None
        return data
    except Exception:
        return None

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return base64.b64encode(salt + dk).decode()

def check_password(password: str, stored: str) -> bool:
    try:
        raw = base64.b64decode(stored.encode())
        salt, dk = raw[:16], raw[16:]
        new_dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return hmac.compare_digest(dk, new_dk)
    except Exception:
        return False

# ──────────────────────────────────────────
# DATABASE
# ──────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = db_compat.connect()
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()

def init_db():
    db = db_compat.connect()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            username    TEXT UNIQUE NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            full_name   TEXT,
            avatar      TEXT DEFAULT 'https://api.dicebear.com/7.x/initials/svg',
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trips (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            name        TEXT NOT NULL,
            destination TEXT,
            start_date  TEXT,
            end_date    TEXT,
            budget      REAL DEFAULT 0,
            currency    TEXT DEFAULT 'INR',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          TEXT PRIMARY KEY,
            trip_id     TEXT NOT NULL,
            name        TEXT NOT NULL,
            amount      REAL NOT NULL,
            category    TEXT DEFAULT 'Other',
            date        TEXT,
            method      TEXT DEFAULT 'Cash',
            note        TEXT,
            FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS packing_items (
            id          TEXT PRIMARY KEY,
            trip_id     TEXT NOT NULL,
            category    TEXT DEFAULT 'General',
            item        TEXT NOT NULL,
            checked     INTEGER DEFAULT 0,
            FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id          TEXT PRIMARY KEY,
            trip_id     TEXT NOT NULL,
            threshold   INTEGER NOT NULL,
            triggered_at TEXT NOT NULL,
            FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sprints (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            name        TEXT NOT NULL,
            goal        TEXT,
            start_date  TEXT NOT NULL,
            end_date    TEXT NOT NULL,
            status      TEXT DEFAULT 'active',
            velocity    INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS user_stories (
            id          TEXT PRIMARY KEY,
            sprint_id   TEXT NOT NULL,
            title       TEXT NOT NULL,
            description TEXT,
            priority    TEXT DEFAULT 'medium',
            status      TEXT DEFAULT 'todo',
            story_points INTEGER DEFAULT 1,
            assigned_to TEXT,
            created_at  TEXT NOT NULL,
            FOREIGN KEY(sprint_id) REFERENCES sprints(id) ON DELETE CASCADE
        );
    """)
    db.commit()

    # Seed demo user if not exists
    row = db.execute("SELECT id FROM users WHERE username='demo'").fetchone()
    if not row:
        uid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        db.execute(
            "INSERT INTO users(id,username,email,password,full_name,created_at) VALUES(?,?,?,?,?,?)",
            (uid, 'demo', 'demo@travelq.app', hash_password('demo123'), 'Demo User', now)
        )
        # Seed a sample trip
        tid = str(uuid.uuid4())
        db.execute(
            "INSERT INTO trips(id,user_id,name,destination,start_date,end_date,budget,currency,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (tid, uid, 'Goa Trip 2025', 'Goa, India', '2025-12-20', '2025-12-27', 35000, 'INR', now, now)
        )
        # Sample expenses
        for name, amt, cat in [
            ('Flight tickets', 8000, '✈️ Transport'),
            ('Hotel 5 nights', 12000, '🏨 Accommodation'),
            ('Beach restaurants', 3500, '🍽️ Food'),
            ('Water sports', 2000, '🎯 Activities'),
        ]:
            db.execute(
                "INSERT INTO expenses(id,trip_id,name,amount,category,date,method) VALUES(?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), tid, name, amt, cat, '2025-12-20', 'UPI')
            )
        # Sample sprint
        sid = str(uuid.uuid4())
        db.execute(
            "INSERT INTO sprints(id,user_id,name,goal,start_date,end_date,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (sid, uid, 'Sprint 1 — Core Features', 'Build MVP with trip & expense management', '2025-01-06', '2025-01-20', 'completed', now)
        )
        for title, pts, status in [
            ('Trip setup form', 3, 'done'),
            ('Expense CRUD', 5, 'done'),
            ('Dashboard analytics', 8, 'done'),
            ('Currency converter', 3, 'done'),
            ('Packing list', 2, 'done'),
        ]:
            db.execute(
                "INSERT INTO user_stories(id,sprint_id,title,priority,status,story_points,created_at) VALUES(?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), sid, title, 'high', status, pts, now)
            )
        db.commit()
    db.close()

# ──────────────────────────────────────────
# AUTH DECORATOR
# ──────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        token = auth.replace('Bearer ', '').strip()
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Unauthorized — invalid or expired token'}), 401
        g.user_id = payload['sub']
        g.username = payload['username']
        return f(*args, **kwargs)
    return wrapper

def now():
    return datetime.utcnow().isoformat()

# ──────────────────────────────────────────
# STATIC
# ──────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

# ──────────────────────────────────────────
# AUTH ROUTES
# ──────────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
def register():
    d = request.json or {}
    username = (d.get('username') or '').strip().lower()
    email = (d.get('email') or '').strip().lower()
    password = d.get('password', '')
    full_name = d.get('full_name', '').strip()

    if not username or not email or not password:
        return jsonify({'error': 'username, email and password are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    db = get_db()
    if db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
        return jsonify({'error': 'Username already taken'}), 409
    if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
        return jsonify({'error': 'Email already registered'}), 409

    uid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users(id,username,email,password,full_name,created_at) VALUES(?,?,?,?,?,?)",
        (uid, username, email, hash_password(password), full_name, now())
    )
    db.commit()
    token = create_token(uid, username)
    return jsonify({
        'token': token,
        'user': {'id': uid, 'username': username, 'email': email, 'full_name': full_name}
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    d = request.json or {}
    username = (d.get('username') or '').strip().lower()
    password = d.get('password', '')

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username=? OR email=?", (username, username)).fetchone()
    if not row or not check_password(password, row['password']):
        return jsonify({'error': 'Invalid username or password'}), 401

    token = create_token(row['id'], row['username'])
    return jsonify({
        'token': token,
        'user': {
            'id': row['id'],
            'username': row['username'],
            'email': row['email'],
            'full_name': row['full_name']
        }
    })

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def me():
    db = get_db()
    row = db.execute("SELECT id,username,email,full_name,created_at FROM users WHERE id=?", (g.user_id,)).fetchone()
    if not row:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(dict(row))

@app.route('/api/auth/update', methods=['PUT'])
@require_auth
def update_profile():
    d = request.json or {}
    db = get_db()
    full_name = d.get('full_name', '').strip()
    db.execute("UPDATE users SET full_name=? WHERE id=?", (full_name, g.user_id))
    db.commit()
    return jsonify({'message': 'Profile updated'})

@app.route('/api/auth/change-password', methods=['PUT'])
@require_auth
def change_password():
    d = request.json or {}
    old_pw = d.get('old_password', '')
    new_pw = d.get('new_password', '')
    if len(new_pw) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    db = get_db()
    row = db.execute("SELECT password FROM users WHERE id=?", (g.user_id,)).fetchone()
    if not check_password(old_pw, row['password']):
        return jsonify({'error': 'Old password is incorrect'}), 401
    db.execute("UPDATE users SET password=? WHERE id=?", (hash_password(new_pw), g.user_id))
    db.commit()
    return jsonify({'message': 'Password changed successfully'})

# ──────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '2.0.0', 'auth': 'JWT'})

# ──────────────────────────────────────────
# TRIPS
# ──────────────────────────────────────────
@app.route('/api/trips', methods=['GET'])
@require_auth
def get_trips():
    db = get_db()
    rows = db.execute(
        "SELECT t.*, COALESCE(SUM(e.amount),0) AS total_spent FROM trips t LEFT JOIN expenses e ON e.trip_id=t.id WHERE t.user_id=? GROUP BY t.id ORDER BY t.created_at DESC",
        (g.user_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/trips', methods=['POST'])
@require_auth
def create_trip():
    d = request.json or {}
    tid = str(uuid.uuid4())
    n = now()
    db = get_db()
    db.execute(
        "INSERT INTO trips(id,user_id,name,destination,start_date,end_date,budget,currency,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (tid, g.user_id, d.get('name','Untitled Trip'), d.get('destination',''), d.get('start_date',''), d.get('end_date',''), float(d.get('budget',0)), d.get('currency','INR'), n, n)
    )
    db.commit()
    row = db.execute("SELECT * FROM trips WHERE id=?", (tid,)).fetchone()
    return jsonify(dict(row)), 201

@app.route('/api/trips/<tid>', methods=['GET'])
@require_auth
def get_trip(tid):
    db = get_db()
    row = db.execute("SELECT * FROM trips WHERE id=? AND user_id=?", (tid, g.user_id)).fetchone()
    if not row:
        return jsonify({'error': 'Trip not found'}), 404
    return jsonify(dict(row))

@app.route('/api/trips/<tid>', methods=['PUT'])
@require_auth
def update_trip(tid):
    d = request.json or {}
    db = get_db()
    row = db.execute("SELECT id FROM trips WHERE id=? AND user_id=?", (tid, g.user_id)).fetchone()
    if not row:
        return jsonify({'error': 'Trip not found'}), 404
    db.execute(
        "UPDATE trips SET name=?,destination=?,start_date=?,end_date=?,budget=?,currency=?,updated_at=? WHERE id=?",
        (d.get('name'), d.get('destination'), d.get('start_date'), d.get('end_date'), float(d.get('budget',0)), d.get('currency','INR'), now(), tid)
    )
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM trips WHERE id=?", (tid,)).fetchone()))

@app.route('/api/trips/<tid>', methods=['DELETE'])
@require_auth
def delete_trip(tid):
    db = get_db()
    db.execute("DELETE FROM trips WHERE id=? AND user_id=?", (tid, g.user_id))
    db.commit()
    return jsonify({'deleted': tid})

@app.route('/api/trips/<tid>/summary', methods=['GET'])
@require_auth
def trip_summary(tid):
    db = get_db()
    trip = db.execute("SELECT * FROM trips WHERE id=? AND user_id=?", (tid, g.user_id)).fetchone()
    if not trip:
        return jsonify({'error': 'Trip not found'}), 404
    expenses = db.execute("SELECT * FROM expenses WHERE trip_id=?", (tid,)).fetchall()
    total_spent = sum(e['amount'] for e in expenses)
    cats = {}
    for e in expenses:
        cats[e['category']] = cats.get(e['category'], 0) + e['amount']
    return jsonify({
        'trip': dict(trip),
        'total_spent': total_spent,
        'remaining': trip['budget'] - total_spent,
        'percentage': round(total_spent / trip['budget'] * 100, 1) if trip['budget'] else 0,
        'category_breakdown': cats,
        'expense_count': len(expenses)
    })

# ──────────────────────────────────────────
# EXPENSES
# ──────────────────────────────────────────
@app.route('/api/trips/<tid>/expenses', methods=['GET'])
@require_auth
def get_expenses(tid):
    db = get_db()
    cat_filter = request.args.get('category')
    q = "SELECT * FROM expenses WHERE trip_id=?"
    params = [tid]
    if cat_filter:
        q += " AND category=?"
        params.append(cat_filter)
    rows = db.execute(q + " ORDER BY date DESC", params).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/trips/<tid>/expenses', methods=['POST'])
@require_auth
def add_expense(tid):
    d = request.json or {}
    eid = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO expenses(id,trip_id,name,amount,category,date,method,note) VALUES(?,?,?,?,?,?,?,?)",
        (eid, tid, d.get('name','Expense'), float(d.get('amount',0)), d.get('category','Other'), d.get('date', now()[:10]), d.get('method','Cash'), d.get('note',''))
    )
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM expenses WHERE id=?", (eid,)).fetchone())), 201

@app.route('/api/trips/<tid>/expenses/<eid>', methods=['PUT'])
@require_auth
def update_expense(tid, eid):
    d = request.json or {}
    db = get_db()
    db.execute(
        "UPDATE expenses SET name=?,amount=?,category=?,date=?,method=?,note=? WHERE id=? AND trip_id=?",
        (d.get('name'), float(d.get('amount',0)), d.get('category'), d.get('date'), d.get('method'), d.get('note'), eid, tid)
    )
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM expenses WHERE id=?", (eid,)).fetchone()))

@app.route('/api/trips/<tid>/expenses/<eid>', methods=['DELETE'])
@require_auth
def delete_expense(tid, eid):
    db = get_db()
    db.execute("DELETE FROM expenses WHERE id=? AND trip_id=?", (eid, tid))
    db.commit()
    return jsonify({'deleted': eid})

# ──────────────────────────────────────────
# PACKING LIST
# ──────────────────────────────────────────
@app.route('/api/trips/<tid>/packing', methods=['GET'])
@require_auth
def get_packing(tid):
    db = get_db()
    rows = db.execute("SELECT * FROM packing_items WHERE trip_id=? ORDER BY category,item", (tid,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/trips/<tid>/packing', methods=['POST'])
@require_auth
def add_packing(tid):
    d = request.json or {}
    pid = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO packing_items(id,trip_id,category,item,checked) VALUES(?,?,?,?,0)",
        (pid, tid, d.get('category','General'), d.get('item','Item'))
    )
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM packing_items WHERE id=?", (pid,)).fetchone())), 201

@app.route('/api/trips/<tid>/packing/<pid>', methods=['PUT'])
@require_auth
def toggle_packing(tid, pid):
    db = get_db()
    row = db.execute("SELECT checked FROM packing_items WHERE id=? AND trip_id=?", (pid, tid)).fetchone()
    if not row:
        return jsonify({'error': 'Item not found'}), 404
    db.execute("UPDATE packing_items SET checked=? WHERE id=?", (1 - row['checked'], pid))
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM packing_items WHERE id=?", (pid,)).fetchone()))

@app.route('/api/trips/<tid>/packing/<pid>', methods=['DELETE'])
@require_auth
def delete_packing(tid, pid):
    db = get_db()
    db.execute("DELETE FROM packing_items WHERE id=? AND trip_id=?", (pid, tid))
    db.commit()
    return jsonify({'deleted': pid})

# ──────────────────────────────────────────
# AGILE — SPRINTS
# ──────────────────────────────────────────
@app.route('/api/sprints', methods=['GET'])
@require_auth
def get_sprints():
    db = get_db()
    rows = db.execute("SELECT * FROM sprints WHERE user_id=? ORDER BY start_date DESC", (g.user_id,)).fetchall()
    result = []
    for r in rows:
        s = dict(r)
        stories = db.execute("SELECT * FROM user_stories WHERE sprint_id=? ORDER BY priority DESC", (r['id'],)).fetchall()
        s['stories'] = [dict(st) for st in stories]
        s['total_points'] = sum(st['story_points'] for st in stories)
        s['completed_points'] = sum(st['story_points'] for st in stories if st['status'] == 'done')
        result.append(s)
    return jsonify(result)

@app.route('/api/sprints', methods=['POST'])
@require_auth
def create_sprint():
    d = request.json or {}
    sid = str(uuid.uuid4())
    n = now()
    db = get_db()
    db.execute(
        "INSERT INTO sprints(id,user_id,name,goal,start_date,end_date,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (sid, g.user_id, d.get('name','Sprint'), d.get('goal',''), d.get('start_date', n[:10]), d.get('end_date', n[:10]), 'active', n)
    )
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM sprints WHERE id=?", (sid,)).fetchone())), 201

@app.route('/api/sprints/<sid>', methods=['PUT'])
@require_auth
def update_sprint(sid):
    d = request.json or {}
    db = get_db()
    db.execute(
        "UPDATE sprints SET name=?,goal=?,start_date=?,end_date=?,status=? WHERE id=? AND user_id=?",
        (d.get('name'), d.get('goal'), d.get('start_date'), d.get('end_date'), d.get('status'), sid, g.user_id)
    )
    db.commit()
    return jsonify({'updated': sid})

@app.route('/api/sprints/<sid>', methods=['DELETE'])
@require_auth
def delete_sprint(sid):
    db = get_db()
    db.execute("DELETE FROM sprints WHERE id=? AND user_id=?", (sid, g.user_id))
    db.commit()
    return jsonify({'deleted': sid})

# ──────────────────────────────────────────
# AGILE — USER STORIES
# ──────────────────────────────────────────
@app.route('/api/sprints/<sid>/stories', methods=['POST'])
@require_auth
def add_story(sid):
    d = request.json or {}
    stid = str(uuid.uuid4())
    n = now()
    db = get_db()
    db.execute(
        "INSERT INTO user_stories(id,sprint_id,title,description,priority,status,story_points,assigned_to,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (stid, sid, d.get('title','Story'), d.get('description',''), d.get('priority','medium'), d.get('status','todo'), int(d.get('story_points',1)), d.get('assigned_to',''), n)
    )
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM user_stories WHERE id=?", (stid,)).fetchone())), 201

@app.route('/api/stories/<stid>', methods=['PUT'])
@require_auth
def update_story(stid):
    d = request.json or {}
    db = get_db()
    db.execute(
        "UPDATE user_stories SET title=?,description=?,priority=?,status=?,story_points=?,assigned_to=? WHERE id=?",
        (d.get('title'), d.get('description'), d.get('priority'), d.get('status'), int(d.get('story_points',1)), d.get('assigned_to'), stid)
    )
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM user_stories WHERE id=?", (stid,)).fetchone()))

@app.route('/api/stories/<stid>', methods=['DELETE'])
@require_auth
def delete_story(stid):
    db = get_db()
    db.execute("DELETE FROM user_stories WHERE id=?", (stid,))
    db.commit()
    return jsonify({'deleted': stid})

# ──────────────────────────────────────────
# CURRENCY
# ──────────────────────────────────────────
RATES = {
    'INR': 1, 'USD': 0.012, 'EUR': 0.011, 'GBP': 0.0095,
    'JPY': 1.78, 'AED': 0.044, 'SGD': 0.016, 'AUD': 0.018,
    'CAD': 0.016, 'CHF': 0.011, 'CNY': 0.087
}

@app.route('/api/currency/rates')
def currency_rates():
    return jsonify({'base': 'INR', 'rates': RATES})

@app.route('/api/currency/convert')
def currency_convert():
    try:
        amount = float(request.args.get('amount', 0))
        from_c = request.args.get('from', 'INR').upper()
        to_c = request.args.get('to', 'USD').upper()
        inr = amount / RATES.get(from_c, 1)
        converted = inr * RATES.get(to_c, 1)
        return jsonify({'amount': amount, 'from': from_c, 'to': to_c, 'result': round(converted, 4)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ──────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────
# Initialize the database (create tables + seed demo user) at import time.
# This must NOT live inside the `if __name__ == '__main__'` guard below,
# because production runs this module via gunicorn ("gunicorn --chdir
# backend app:app"), which imports app.py as a module rather than running
# it as a script — so that guard never executes under gunicorn, and the
# database (and demo user) never got created, breaking login in production.
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    print("\n  ✈️  TravelQ v2 — with Authentication & Agile Board")
    print("  ─────────────────────────────────────────────────")
    print("  🌐  http://localhost:5000")
    print("  📋  API Health: http://localhost:5000/api/health")
    print("  🔑  Demo login: demo / demo123")
    print("  Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
