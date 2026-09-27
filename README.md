# ✈️ TravelQ v2 — Travel Budget Planner
### Full-Stack Web App | BTech Web Technology Major Project | with Authentication + Agile Board

---

## 🌐 Live Demo

**👉 [https://travel-q-travel-budget-plannar-1.onrender.com/](https://travel-q-travel-budget-plannar-1.onrender.com/)**

Demo login: `demo` / `demo123`

> ⏳ Hosted on Render's free tier — the app sleeps after 15 minutes of inactivity. The first request after idle time can take 30–50 seconds to wake up; it's fast after that.

---

## 📋 What's New in v2

| Feature | Details |
|---------|---------|
| **🔑 JWT Authentication** | Register / Login / Logout with secure token-based auth (no external libs) |
| **🔐 Password Hashing** | PBKDF2-SHA256 with salt (Python built-in only) |
| **👤 User Profiles** | Each user has their own trips, expenses, and sprints |
| **🚀 Agile Board** | Full Kanban board with Sprints & User Stories |
| **📊 Sprint Velocity** | Track completed story points per sprint |
| **🗂️ User Isolation** | All data is scoped per user — no data leakage |

---

## 🗂️ Project Structure

```
travelq/
├── backend/
│   ├── app.py          ← Flask REST API (Auth + Trips + Agile)
│   └── travelq.db      ← SQLite database (auto-created on first run)
├── frontend/
│   └── index.html      ← Single-page application (no framework)
├── start.sh            ← One-click startup script (Linux/Mac)
└── README.md
```

---

## ⚙️ Setup & Running

### Prerequisites
- Python 3.8+
- pip

### Step 1 — Install Flask
```bash
pip3 install flask
```

### Step 2 — Start the Server
```bash
# Option A: start script (Linux/Mac)
chmod +x start.sh
./start.sh

# Option B: run directly
cd backend
python3 app.py
```

### Step 3 — Open the App
```
http://localhost:5000
```

**Demo account:** `demo` / `demo123` (auto-seeded on first run)

---

## 🔑 Authentication Flow

```
POST /api/auth/register  →  { token, user }
POST /api/auth/login     →  { token, user }
GET  /api/auth/me        →  user profile        (requires Bearer token)
PUT  /api/auth/update    →  update profile      (requires Bearer token)
PUT  /api/auth/change-password                  (requires Bearer token)
```

All protected endpoints require:
```
Authorization: Bearer <JWT_TOKEN>
```

The JWT is **manually implemented** using Python's built-in `hmac` + `hashlib` (no PyJWT needed).

---

## 🚀 Agile API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sprints` | List all sprints with stories |
| POST | `/api/sprints` | Create a new sprint |
| PUT | `/api/sprints/:id` | Update sprint (name, status) |
| DELETE | `/api/sprints/:id` | Delete sprint + all stories |
| POST | `/api/sprints/:sid/stories` | Add user story to sprint |
| PUT | `/api/stories/:id` | Update story (status, points) |
| DELETE | `/api/stories/:id` | Delete story |

---

## 🔌 Full API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register` | No | Register user |
| POST | `/api/auth/login` | No | Login |
| GET | `/api/auth/me` | Yes | Get profile |
| GET | `/api/trips` | Yes | List my trips |
| POST | `/api/trips` | Yes | Create trip |
| GET | `/api/trips/:id/summary` | Yes | Budget summary |
| GET | `/api/trips/:id/expenses` | Yes | List expenses |
| POST | `/api/trips/:id/expenses` | Yes | Add expense |
| DELETE | `/api/trips/:id/expenses/:eid` | Yes | Delete expense |
| GET | `/api/trips/:id/packing` | Yes | Packing list |
| POST | `/api/trips/:id/packing` | Yes | Add packing item |
| PUT | `/api/trips/:id/packing/:pid` | Yes | Toggle checked |
| GET | `/api/sprints` | Yes | List sprints |
| POST | `/api/sprints` | Yes | Create sprint |
| POST | `/api/sprints/:sid/stories` | Yes | Add user story |
| PUT | `/api/stories/:id` | Yes | Update story |
| GET | `/api/currency/rates` | No | Exchange rates |
| GET | `/api/currency/convert` | No | Convert amount |

---

## 🗄️ Database Schema (v2 — additional tables)

### `users` table
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary key |
| username | TEXT UNIQUE | Login identifier |
| email | TEXT UNIQUE | |
| password | TEXT | PBKDF2-SHA256 hashed |
| full_name | TEXT | Display name |
| created_at | TEXT | ISO timestamp |

### `sprints` table
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary key |
| user_id | TEXT | Foreign key → users |
| name | TEXT | Sprint name |
| goal | TEXT | Sprint goal |
| start_date | TEXT | YYYY-MM-DD |
| end_date | TEXT | YYYY-MM-DD |
| status | TEXT | active / completed |
| velocity | INTEGER | Completed points |

### `user_stories` table
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary key |
| sprint_id | TEXT | Foreign key → sprints |
| title | TEXT | Story title |
| description | TEXT | Acceptance criteria |
| priority | TEXT | high / medium / low |
| status | TEXT | todo / inprogress / done |
| story_points | INTEGER | Fibonacci: 1,2,3,5,8,13 |
| assigned_to | TEXT | Team member name |

---

## 🎯 All Features

| Page | Features |
|------|---------|
| **Auth** | Register, Login, Auto-login (token in localStorage), Change password, Profile edit |
| **Dashboard** | Budget stats, spending bars, category breakdown, recent expenses |
| **Trips** | CRUD trips, expense management, CSV export, packing list |
| **Analytics** | Category breakdown charts, payment method analysis, key stats |
| **Agile Board** | Kanban (To Do / In Progress / Done), Sprint velocity, User story CRUD |
| **Currency** | 11-currency converter, rate reference table |
| **Profile** | Name update, password change |

---

## 🏗️ Architecture

```
Browser (SPA — index.html)
       │
       │  HTTP/JSON + JWT Bearer Token
       ▼
Flask Server (app.py) — port 5000
  ├── Auth middleware (verify_token decorator)
  ├── REST routes (trips, expenses, packing, agile, currency)
       │
       │  sqlite3 (built-in Python module)
       ▼
SQLite Database (travelq.db)
```

---

## 🔒 Security Implementation

- **JWT** — hand-rolled with HMAC-SHA256 (Python `hmac` + `hashlib`)
- **Password hashing** — PBKDF2-SHA256 with 16-byte random salt, 100,000 iterations
- **Token expiry** — 24 hours
- **User isolation** — all trip/sprint queries filter by `user_id = g.user_id`
- **Foreign key cascades** — SQLite `ON DELETE CASCADE` for referential integrity

---

## 🌍 Deploy Your Own Copy (Free)

This repo is deployed on **[Render](https://render.com)** — free tier, no credit card needed.

1. Push this folder to a GitHub repo.
2. On [render.com](https://render.com): **New +** → **Web Service** → connect your repo.
3. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --chdir backend app:app`
4. Add an environment variable: **Key** `SECRET_KEY`, **Value** → click **Generate**.
5. Click **Deploy**. Your live URL will look like `https://<your-app-name>.onrender.com`.

Other hosts that work the same way: **Railway**, **Fly.io**, **PythonAnywhere**.

> ⚠️ Note: GitHub itself (GitHub Pages) only serves static files — it can't run this Flask backend. GitHub is where your *code* lives; Render is where it *runs*.

### Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit — TravelQ v2"
git branch -M main
git remote add origin https://github.com/<your-username>/travelq.git
git push -u origin main
```

---

## 📚 References

1. Flask Docs — https://flask.palletsprojects.com
2. SQLite Docs — https://www.sqlite.org/docs.html
3. MDN Web Docs — https://developer.mozilla.org
4. HMAC-based JWT — RFC 7519
5. PBKDF2 — NIST SP 800-132
6. Agile/Scrum — Scrum Guide 2020 — https://scrumguides.org
