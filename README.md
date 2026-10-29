<p align="center">
  <img src="frontend/public/brand/spex-logo-navy.png" alt="SPEX" height="72" />
</p>

<h1 align="center">SPEX School Manager</h1>

<p align="center">
  School management for Ugandan nursery, primary and secondary schools:<br />
  registers, marks, report cards, promotion, timetables, staff and school spending.<br />
  <b>Secure. Intelligent. Powered.</b>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12+-0B1F3A?logo=python&logoColor=white" />
  <img alt="Django" src="https://img.shields.io/badge/Django-6.1-0B1F3A?logo=django&logoColor=white" />
  <img alt="React" src="https://img.shields.io/badge/React-19-1E88E5?logo=react&logoColor=white" />
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-strict-1E88E5?logo=typescript&logoColor=white" />
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-17-7C4DFF?logo=postgresql&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/license-proprietary-F5A623" />
</p>

---

SPEX School Manager is a multi-school platform built by **SPEX Labs**, the software division of
Security, Power & Engineering Experts Limited (Seeta–Mukono, Uganda). One installation serves many
schools: the SPEX team registers and sets up each school from an owner console, and every school
signs in with its own School ID and sees only its own records.

It is built around the Ugandan curriculum and calendar (PLE, the O-Level competence-based
curriculum, UCE, UACE; three terms; Uganda public holidays) and works on a phone in a classroom
without internet. School fees are deliberately out of scope: schools keep using SchoolPay.

## Contents

- [Features](#features)
- [Roles and access](#roles-and-access)
- [Architecture](#architecture)
- [Getting started](#getting-started)
- [Testing and quality](#testing-and-quality)
- [Deployment](#deployment)
- [Security and privacy](#security-and-privacy)
- [Project structure](#project-structure)
- [License](#license)

## Features

### For the SPEX team (owner console)
- Register schools with their full profile, School ID (e.g. `NewHope-003`), plan and modules.
- Set each school up centrally: levels, years and terms on the standard Ugandan dates, classes,
  streams, subjects, grading scales and report card design. Schools see their setup read-only.
- Create each school's first accounts, follow up website requests, see adoption across schools.

### Learners and admissions
- Enrol one learner with a form, or a whole class from an Excel template (names, parents and
  guardians, residence, allergies and illnesses). Admission numbers are generated.
- Admissions pipeline (application → interview → offer → admit), enquiries and visitors' register.

### Teaching and learning
- **Daily register** on school days only (weekends, public holidays and holidays skipped), with a
  monthly class register and chronic-absence alerts. Works offline and syncs later.
- **Curriculum**: who teaches what, filled from teachers' subject specialisations; schemes of work;
  CBC competencies. Schools propose extra subjects; the head teacher, director or DOS approves them.
- **Timetables** generated from teaching allocations, published to teachers, printable per class,
  teacher or room. **Exam timetables** generated automatically, with mixed seating plans per room.
- **Marks**: class or subject teachers enter, the DOS approves and locks. Continuous assessment and
  end-of-term exams are weighted consistently.

### Results and reporting
- Grading engines for nursery ratings, PLE aggregates and divisions, CBC achievement levels and
  UACE points, with editable cut-offs.
- **Report cards** in four designs in the school's colours and crest: subject teachers' comments
  and initials, a performance chart, serial number and QR code anyone can verify.
- **Performance history** term by term for the school, each class and stream, each subject and
  each learner.
- **Promotion** lists reviewed by the class teacher, recommended by the DOS, approved by the
  director, and applied when the new year opens.

### Staff and school operations
- Staff records and sign-ins, class teachers and deputies per class or stream, leave, duty rosters,
  staff attendance and a weekly planner for every teacher.
- **Finance (expenditure)**: expenses with approval limits, categories and sub-categories, budgets,
  petty cash, suppliers and bills. **Requisitions** climb the ranks above the requester, finance
  issues the money, and the requester accounts for it with receipts.
- Discipline and welfare, notices and calendar, library, sickbay and stores (optional add-ons).

## Roles and access

Access is enforced by the API, not only hidden in screens. A person can hold several roles, each
limited to a class, stream or department.

| Level | Role | In short |
| ---: | --- | --- |
| – | Platform team | Owner console: schools, setup, plans, users. No access to school records. |
| 100 | Director / proprietor | Acts in every module; final approvals; all accounts |
| 90 | School administrator | Accounts and roles, audit log |
| 80 | Head teacher | All academic and operational work; approvals within limits |
| 70 | Director of Studies | Curriculum, timetables, exams, mark approval, enrolment |
| 60 | Bursar | Expenses, budgets, issuing requisition money |
| 50 | Head of department | Department marks review, subject proposals |
| 40 | Class teacher | Their class: register, marks, comments, enrolment, promotion review |
| 30 | Subject teacher, nurse, librarian, storekeeper | Their own area |
| 10 | General staff | Dashboard, notices, timetable, requisitions, own leave |

Nobody can raise their own access, approve their own request or appoint themselves.

## Architecture

| Layer | Technology |
| --- | --- |
| API | Python 3.12+, Django 6.1, Django REST Framework, drf-spectacular (OpenAPI) |
| Database | PostgreSQL with row-level security per school (SQLite for local development) |
| Web app | React 19, TypeScript, Vite, Mantine, TanStack Query, React Router |
| Offline | Installable PWA: service worker and an IndexedDB queue synced through `/api/sync/` |
| Documents | ReportLab PDFs (report cards, timetables, seating plans), openpyxl Excel |
| Admin | Django admin with the Unfold theme at `/admin/` |

Every record carries its school; the API filters by the signed-in school and PostgreSQL
row-level security is a second barrier. Every create, edit and delete is audited.

## Getting started

Requirements: Python 3.12+ and Node.js 24 LTS.

```bash
# API
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.lock.txt   # macOS/Linux: .venv/bin/pip
cd backend
../.venv/Scripts/python manage.py migrate
../.venv/Scripts/python manage.py seed_demo        # optional: a demo primary school
../.venv/Scripts/python manage.py runserver 127.0.0.1:8000

# Web app (second terminal)
cd frontend
npm ci            # install scripts are disabled in .npmrc
npm run dev       # http://localhost:5173
```

`seed_demo` prints the sign-ins it creates. Passwords are never stored in the code: set
`SPEX_SUPERUSER_PASSWORD` and `SPEX_DEMO_PASSWORD` before running it, or random ones are generated
and printed once. Further sample data for development:

```bash
python manage.py seed_class_sample --school <School ID> --class P1 --stream East --count 50
python manage.py seed_history --school <School ID> --year 2025
```

| Address | What |
| --- | --- |
| `/home` | Public website and **Request access** form |
| `/login` | School sign-in (School ID + username) |
| `/platform/login` | Owner console for the SPEX team |
| `/api/docs/` | API documentation (OpenAPI) |

## Testing and quality

```bash
cd backend  && ../.venv/Scripts/ruff check . && ../.venv/Scripts/python -m pytest --cov
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

The backend suite covers the access rules, school isolation, grading, report cards, promotion,
requisitions, exam planning and the owner console. Continuous integration runs both suites on
every push and pull request.

## Deployment

1. Copy `.env.example` to `.env` and set `DEBUG=false`, `SECRET_KEY`, `ALLOWED_HOSTS`,
   `CSRF_TRUSTED_ORIGINS`, `PUBLIC_BASE_URL`, PostgreSQL (`DB_*`) and email settings.
2. Run migrations as the database owner and the app as a separate role, so row-level security
   applies.
3. Build the web app (`npm run build`), serve `frontend/dist`, and proxy `/api`, `/admin` and
   `/media` to Django (see `deploy/nginx.conf`). Serve everything over HTTPS.
4. Back up the database and media every night to another location, and test a restore each term.

## Security and privacy

- The system holds children's personal and health records. Operators must register with Uganda's
  Personal Data Protection Office under the Data Protection and Privacy Act, 2019, record guardian
  consent at admission and set retention rules for leavers.
- Health records are visible only to the nurse and head teacher, and every view is logged.
- The SPEX team can open a school's records only when the school grants time-limited support access.
- Report security issues privately to **info@spex.co.ug**; do not open a public issue.

## Project structure

```
backend/
  apps/            Django apps: accounts, schoolsetup, learners, staff, curriculum, timetable,
                   attendance, assessment, promotion, finance, communication, subscriptions, …
  config/          settings and URLs
  tests/           pytest suite
frontend/
  src/pages/       screens by area (academics, attendance, finance, learners, admin, public)
  src/components/  shared building blocks (forms, tables, SPEX brand)
  public/brand/    SPEX logo artwork
deploy/            nginx configuration
```

## License

Copyright © 2026 Security, Power & Engineering Experts Limited (SPEX). All rights reserved.
See [LICENSE](LICENSE). This is proprietary software; no use, copying or distribution is permitted
without written permission from SPEX.
