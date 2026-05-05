# PDPTW Logistics Web Application

Full-stack web app wrapping the ALNS PDPTW solver.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + SQLAlchemy + PostgreSQL |
| Auth | JWT (python-jose) + bcrypt |
| Frontend | React 18 + TypeScript + Vite |
| Map | react-leaflet + OpenStreetMap |
| Styles | Tailwind CSS |

## Roles

| Role | Access |
|------|--------|
| **Quản lý** (Manager) | Full access: users, fleet, jobs, solutions, orders |
| **Điều phối viên** (Dispatcher) | Fleet, jobs, solutions, orders |
| **Khách hàng** (Customer) | Own orders only |

## Quick Start

### 1. Database (PostgreSQL)
```bash
createdb pdptw_db
createuser pdptw_user -P   # password: pdptw_pass
psql -c "GRANT ALL ON DATABASE pdptw_db TO pdptw_user;"
```

### 2. Backend
```bash
cd backend
cp .env.example .env        # edit DATABASE_URL if needed
pip install -r requirements.txt
python run.py               # → http://localhost:8000
python app/db/seed.py       # seed demo users (first run only)
```

API docs: http://localhost:8000/docs

### 3. Frontend
```bash
cd frontend
npm install
npm run dev                 # → http://localhost:5173
```

## Demo Accounts

| Email | Password | Role |
|-------|----------|------|
| manager@pdptw.vn | manager123 | Quản lý |
| dispatcher@pdptw.vn | dispatcher123 | Điều phối viên |
| customer@pdptw.vn | customer123 | Khách hàng |

## Folder Structure

```
backend/
├── app/
│   ├── main.py              FastAPI app + CORS + router registration
│   ├── core/
│   │   ├── config.py        Settings (DATABASE_URL, SECRET_KEY, …)
│   │   ├── security.py      JWT encode/decode, bcrypt
│   │   └── deps.py          FastAPI Depends (auth guards)
│   ├── db/
│   │   ├── models.py        SQLAlchemy ORM models
│   │   ├── session.py       DB engine + get_db dependency
│   │   └── seed.py          Seed demo users
│   ├── models/
│   │   └── schemas.py       Pydantic request/response schemas
│   ├── routers/
│   │   ├── auth.py          POST /auth/login
│   │   ├── users.py         CRUD /users/
│   │   ├── fleet.py         CRUD /fleet/
│   │   ├── instances.py     GET  /instances/
│   │   ├── jobs.py          CRUD /jobs/ + background solver task
│   │   ├── solutions.py     GET  /solutions/
│   │   └── orders.py        CRUD /orders/
│   └── services/
│       └── solver_service.py  Wraps ALNS solver, persists solution to DB
└── requirements.txt

frontend/
├── src/
│   ├── api/client.ts        Axios instance + typed API helpers + TypeScript types
│   ├── contexts/
│   │   └── AuthContext.tsx  JWT storage, role helpers
│   ├── components/
│   │   ├── Layout.tsx       Sidebar + nav (role-aware)
│   │   ├── StatusBadge.tsx  Colour-coded status pills
│   │   ├── MapView.tsx      react-leaflet route visualisation
│   │   ├── JobStatusPoller.tsx  useJobPoller hook (2s interval)
│   │   └── ConfirmModal.tsx Reusable confirm dialog
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── InstancesPage.tsx
│   │   ├── JobsPage.tsx
│   │   ├── NewJobPage.tsx
│   │   ├── JobDetailPage.tsx   (auto-polls until done, shows solution)
│   │   ├── SolutionsPage.tsx
│   │   ├── SolutionDetailPage.tsx  (map + route table)
│   │   ├── FleetPage.tsx
│   │   ├── UsersPage.tsx
│   │   ├── OrdersPage.tsx
│   │   ├── OrderFormModal.tsx
│   │   ├── OrderDetailModal.tsx
│   │   └── ProfilePage.tsx
│   └── App.tsx              React Router v6 routes + guards
└── package.json
```

## API Endpoints Summary

```
POST /auth/login

GET/POST  /users/
GET       /users/me
PATCH/DELETE /users/{id}

GET/POST  /fleet/
PATCH/DELETE /fleet/{id}

GET       /instances/
GET       /instances/{name}

POST      /jobs/          ← triggers background solver
GET       /jobs/
GET/DELETE /jobs/{id}

GET       /solutions/
GET       /solutions/{id}
GET       /solutions/by-job/{job_id}

GET/POST  /orders/
GET/PATCH/DELETE /orders/{id}
```
