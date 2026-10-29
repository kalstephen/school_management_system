# SPEX School Manager

A school management system for Ugandan schools (nursery, primary/PLE, O-Level CBC, A-Level UACE):
academics, staff, campus operations and **expenditure**. It deliberately does **not** handle school
fees, has no parent portal and no boarding module (see the
[revised concept](https://claude.ai/artifact/AnQjsKdrs9YCvPNwyuDRnc)).

| Part | Technology |
| --- | --- |
| API | Python 3.12+, Django 6.1, Django REST Framework, drf-spectacular (OpenAPI) |
| Database | PostgreSQL (production, with row-level security) · SQLite (development) |
| Web app | React 19, TypeScript, Vite 8, Mantine 9, TanStack Query, React Router 8 |
| Offline teacher app | Installable PWA: hand-written service worker + IndexedDB queue → `/api/sync/` |
| Content manager | Django admin with the Unfold theme at `/admin/` |
| PDFs | ReportLab (report cards with serial + QR, circulars) |
| Tests | pytest, pytest-django, factory_boy, coverage · Vitest, Testing Library |
| Code quality | Ruff (lint + format) · ESLint, TypeScript strict |

## Website, sign-in and requests

- `/home` is the public SPEX School Manager website (features, how it works, about us). Visitors
  who are not signed in land there; `/login` is the school sign-in, `/platform/login` the owner
  console.
- `/join` is "Request access": a school asks to register, book a demo or get information. The
  request is saved (`AccessRequest`), emailed to platform-team accounts that have an email, and
  listed in the owner console under **Requests** for follow-up. The form is limited to
  `ACCESS_REQUEST_RATE` (default 5/hour) per address and drops bot submissions.
- Branding follows the SPEX brand book v1.0: the master logo artwork in `frontend/public/brand/`
  (taken from the brand kit, never retyped), SPEX Navy with Electric Blue as the main colour,
  Montserrat headings and Inter text, and the four-colour stripe.

## Access levels (top to bottom)

| Level | Who | Can |
| --- | --- | --- |
| Super admin | Platform owner (Django superuser) | Everything in the content manager; manages the platform team |
| Platform team | Your staff | Schools, plans, add-ons, each school's first director/administrator; school records only with the school's time-limited support grant |
| 100 Director / proprietor | School owner | Everything in the school, top expense approvals, all accounts (can appoint another director) |
| 90 School administrator | Runs the system | Settings, user accounts and roles, audit log |
| 80 Head teacher | | All academic and operational work, approvals within limits |
| 70 DOS · 60 Bursar · 50 HOD · 40 Class teacher · 30 Subject teacher, nurse, librarian, storekeeper | | Their own area only (see Users & roles → Access levels) |
| 10 General staff | Any staff account | Dashboard, notices, timetable, own leave requests |

Rules (enforced by the API, not just the screens): you can only assign roles, edit or disable
people **below** your level; nobody changes their own access; temporary permissions can only be
granted by someone who holds them. Demo accounts cover every level, e.g. `support` (general staff)
up to `director`, and the super admin `admin`.

## Schools, School IDs and modules

The platform team registers each school with its full profile (registration numbers, location
from region down to village, head teacher, director) and ticks the modules it has. Every school
gets a **School ID** such as `NewHope-003`; staff type it on the sign-in screen with their username.
School setup and Learners are always on; every other module can be ticked per school, and each user
can be narrowed to a subset of their school's modules (none ticked = all of them).

## Run it locally

Requirements: Python 3.12+ and Node.js 24 LTS. (This repository can also use a portable Node in
`.tools/node`, which is git-ignored.)

```bash
# 1. API
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt      # or requirements.lock.txt for exact versions
cd backend
../.venv/Scripts/python manage.py migrate
../.venv/Scripts/python manage.py seed_demo                 # demo primary school with data
../.venv/Scripts/python manage.py runserver 127.0.0.1:8000

# 2. Web app (second terminal)
cd frontend
npm ci                                                       # install scripts are disabled in .npmrc
npm run dev                                                  # http://localhost:5173
```

Demo sign-ins (password `Demo@School2026`, development only): `head`, `dos`, `bursar`, `director`,
`nurse`, `librarian`, `store`, `schooladmin`, `support`, `ct.p5` (class teacher P5),
`t.maths`, `t.english`. Super admin (app and `/admin/` content manager): `admin` / `Kampala2020`.

Sample class in a real school (here 50 learners in New Hope's P1 East, with parents, health notes,
a class teacher, planner, published timetable, exams, marks and attendance; safe to run twice):

```bash
../.venv/Scripts/python manage.py seed_class_sample --school NewHope-002 --class P1 --stream East --count 50
../.venv/Scripts/python manage.py seed_history --school DemoPrimary-001 --year 2025   # a past year of sample results
```

It prints the sign-ins it creates (development only): class teacher `p1east` / `Teacher@2026` and
Director of Studies `nhdos` / `Studies@2026`, both with School ID `NewHope-002`.

API docs: http://localhost:8000/api/docs/

## Checks

```bash
cd backend  && ../.venv/Scripts/ruff check . && ../.venv/Scripts/python -m pytest --cov
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

## Modules

Core (every school): school setup, admissions & front desk, learners, staff & HR, academics &
curriculum, timetable, attendance, exams/assessment/report cards, promotion, discipline & welfare,
communication, finance (expenditure). Add-ons switched on per school by the platform: library,
sickbay, stores/inventory/assets.

Highlights:

- **School isolation**: every record carries `school_id`; the API filters by the active school and
  PostgreSQL row-level security is a second barrier (`apps/core/migrations/0002_row_level_security.py`).
- **Scoped, combinable roles**: e.g. class teacher of P5 + Maths teacher of P6 + head of Sciences
  (`apps/accounts/roles.py`), with time-limited permission grants.
- **Audit trail**: every create, edit and delete with before/after values; health-record views go to
  an access log.
- **Grading engines** per section (`apps/assessment/grading.py`): PLE aggregates and divisions,
  generic marks, CBC with activities of integration, UACE points, nursery ratings. Grade bands are
  editable; the defaults are common practice and must be checked against current UNEB/NCDC guidance.
- **Mark approval workflow**: teacher → head of department → DOS (locked); reopening needs a reason
  and reissues affected report cards under a new serial.
- **Report cards**: bulk PDFs per class, serial number and QR code verified at `/verify/<token>`.
  Four designs (classic, modern banner, prestige letterhead, compact) with a framed page,
  watermark, colour-coded grades and a subject bar chart. Design, colour, logo and footer are set
  in the owner console; the school previews them under School setup → Report card.
- **School setup in the owner console**: owner console → school → Open school setup. Levels and
  Ugandan defaults, years and terms (one click on the standard Ugandan dates), profile and logo,
  classes, streams and subjects. Schools see all of it read-only (requests carry `X-Setup-School`;
  only views marked `platform_setup` accept them, never learner, marks or finance records).
  Schools choose their own class teachers and may adjust grade cut-offs.
- **Grading set-up**: start from a standard Ugandan scale (PLE D1–F9, O-Level CBC, UCE, UACE) and
  adjust the cut-offs; gaps and overlaps are rejected. Exams are weighted (e.g. BOT 20 + MOT 30
  continuous assessment, EOT 50 final) and Exams → How marks add up flags classes not at 100%.
- **Enrolment**: by the director, head teacher, DOS or a class teacher (own class only). One
  learner at a time, or a whole class from the Excel template (names, residence, parents and
  guardians, allergies and illnesses); both take the academic year, class and optional stream and
  generate admission numbers.
- **Class teachers**: each class, and each stream, has one class teacher and one deputy (same
  access). Set on the staff form ("Class teacher of", "Deputy class teacher of"), the staff list's
  quick action or the classes list, by the DOS, head teacher, director or school administrator,
  never by the teacher for themselves. Appointing someone to a taken post replaces the holder; a
  teacher leads one class at a time.
- **Subjects**: teachers' subject specialisations (any level) fill "who teaches what" in one step
  (Curriculum → Fill from specialisations), which the timetable generator uses. The director,
  DOS, head teacher or a head of department propose extra subjects; the head teacher, director or
  DOS approves them (not their own proposal), and only approved subjects reach mark sheets,
  report cards and timetables.
- **Report card comments**: each subject carries its teacher's comment (Mark sheets → Subject
  comments; preset comments by mark from the comment bank fill any left empty) and the teacher's
  initials (the allocated teacher, else the class teacher).
- **Exam timetables**: Exams → Exam timetable → Generate automatically places every paper on
  school days between the exam's dates, in the chosen sessions; a paper is sat by all its
  classes at once, no class sits more than N papers a day, invigilators never teach the subject
  to that class and are never double-booked. Seating plan seats each session's learners across
  chosen rooms with classes and streams interleaved, printable per room.
- **Form notes**: every add/edit form starts with a one-line note on what it is for.
- **Timetables**: every lesson shows subject, teacher and class; the PDF is titled by class,
  teacher or room, with the class teacher and deputy.
- **Classes and staff**: the class teacher (chosen by the school) gets class-teacher access
  automatically; a new staff member can get a sign-in in the same step.
- **Daily register**: school days only: no weekends, Uganda public holidays (fixed dates, Easter,
  Eid) or days between terms; school closures are calendar events of kind "holiday". A monthly
  register shows every learner and day, and flags school days without a register. Attendance
  reports filter by class and stream.
- **Timetables**: the DOS builds or generates the week and the exam timetable, then publishes them;
  teachers see them only after publishing, with "My lessons" and PDF downloads.
- **Planner**: every teacher has a weekly to-do list (My planner); heads can view a teacher's.
- **Performance history** (Academics): the whole school, each class and stream, each subject and
  each learner term by term, with changes from the term before and past report cards. Past terms
  with approved marks but no computed results are computed on first view.
- **Curriculum**: who teaches what (decides who enters which marks), schemes of work and lesson
  plans, CBC competencies; the subject list itself is set in the owner console.
- **Every module has someone who can act in it**: the director can work in every module the owner
  console switches on (staff, finance, library, stores, timetable, exams…), so a module never sits
  idle waiting for a bursar or librarian account. Marks approval stays with the DOS/head teacher
  and health records with the nurse/head teacher. A test guards this.
- **Promotion**: each class's list splits learners into passed and below the pass mark (class rule,
  or the term average with a pass mark chosen when preparing it). Class teacher reviews and
  comments → DOS changes decisions (promote, probation, repeat, demote) and recommends → director
  approves; either can send it back. Applied when the new year opens, undoable until then.
- **Requisitions**: any staff member asks; the request climbs the ranks above them (head of
  department when a department is named, DOS, head teacher, director above the head teacher's
  limit), skipping roles nobody holds or at/below the requester's rank. Finance (bursar or
  director) issues the money at the end, recorded as an expense; the requester accounts for it
  (spent, change, receipts) and finance confirms, correcting the expense to what was spent.
  Everyone has My requests and Waiting for me, and is notified when it is their turn.
- **Expense categories**: Finance → Categories (bursar or director) keeps categories and their
  sub-categories; an expense offers only its category's sub-categories.
- **Audit log**: school administrators only.
- **Finance**: expenses with approval limits (bursar → head teacher → director), petty cash, termly
  budgets with 80%/100% alerts, suppliers, bills and part payments, non-fee income, reports and
  Excel export. Holiday spending counts towards the term just ended.
- **Offline**: roll call and mark entry work without internet; changes sync with idempotency and
  conflict detection (`apps/sync/services.py`).

## Production notes

- Set `DEBUG=false`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PUBLIC_BASE_URL`, and
  `DB_ENGINE=postgres` with `DB_*` variables (see `.env.example`).
- Run migrations as the database owner and the app as a separate role so row-level security applies.
- Serve `frontend/dist` and proxy `/api`, `/admin`, `/media` to Django (see `deploy/nginx.conf`).
- Take nightly off-site backups of the database and `MEDIA_ROOT`, and test a restore each term.
- Report-card PDFs and emails are generated in the request; for very large schools move them to a
  task queue (Celery + Redis) — the services are already separate functions.
- Uganda's Data Protection and Privacy Act 2019: register with the PDPO, record guardian consent at
  admission, and set retention rules for leavers.
