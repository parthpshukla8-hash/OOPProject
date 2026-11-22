# I-ITSM – Intelligent IT Service Management & Incident Resolution System

**Stack:** React 18 (Vite) + **Fluent UI v9** (`@fluentui/react-components`, `@fluentui/react-icons`) · Django 5 · Django REST Framework · SQLite · Token auth

## Run it

```bash
# 1) Backend
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations itsm                       # custom user model => generate migrations first
python manage.py migrate
python manage.py seed                                      # demo users, services, SLA policies, history
python manage.py runserver                                 # http://127.0.0.1:8000

# 2) Frontend (new terminal)
cd frontend
npm install
npm run dev                                                # http://localhost:5173  (proxies /api to Django)

# Tests (30 cases) and optional continuous SLA monitor
python manage.py test itsm -v 2
python manage.py check_sla --loop --interval 60
```

Demo logins: `admin/admin123` · technicians `t101…t104 / tech1234` · employees `e101…e103 / pass1234`

## Architecture

```
React SPA + Fluent UI v9 (role-based UI, light/dark theme)  --REST/JSON + Token-->  DRF views (thin)
                                                      |
                              services.py (use-cases: create, update, perform, assign)
                                  |            |             |              |
                           factories.py   lifecycle.py   assignment.py   priority.py   sla.py   intelligence.py
                                  \            |             |              /
                                   models.py (Django ORM)  <->  SQLite
                                   events.py (EventBus) -> observers.py -> AuditLog + channels.py (Notifications)
```

## OOP concepts and design patterns (where to find them)

| Pattern / concept | Where | What it does |
|---|---|---|
| **State** | `lifecycle.py` | One class per lifecycle state; each declares legal next states, entry guards (e.g. no ASSIGNED without technician, no RESOLVED without resolution) and side-effects (timestamps, SLA breach flags). `NEW -> CLOSED` raises `InvalidStateTransition`. |
| **Strategy** | `assignment.py`, `priority.py`, `channels.py` | 4 assignment strategies (Skill, Load, Round-Robin, Smart), 2 priority strategies (Weighted, Rule-based), 3 notification channels. Admin switches strategy at runtime from the UI – no code change. |
| **Observer** | `events.py`, `observers.py` | Domain code only *publishes* events. `AuditObserver` writes the audit trail; `NotificationObserver` fans out to channels. New reactions = new observer. |
| **Factory** | `factories.py`, `channels.py` | `IncidentFactory` (validation, service lookup, auto-category, priority, SLA deadlines, duplicate guard), `UserFactory` (role validation, password rules), `ChannelFactory`. |
| Abstraction / Interfaces | ABCs: `IncidentState`, `AssignmentStrategy`, `PriorityStrategy`, `NotificationChannel` | |
| Inheritance | `ITSMError` hierarchy, `User(AbstractUser)`, `IncidentDetailSerializer(IncidentSerializer)` | only true is-a relations |
| Composition / Association | `Incident` has `reporter`, `assignee`, `service`, `category`, comments, audit; `User.skills` many-to-many | |
| Exceptions | `exceptions.py` | 9 custom exceptions mapped to HTTP codes; DB failure -> 503 |

**Priority:** `score = Impact(1-4) × Urgency(1-4) × Business criticality(1-5)`, ×1.25 for ≥20 users, ×1.5 for ≥100 users. Bands: ≥48 P1, ≥24 P2, ≥8 P3, else P4. The rule-based variant additionally forces P1 for impact ≥3 on a criticality-5 service.

**Smart technician score (100 pts):** skill match 40 + free capacity 30 + experience 20 + prior work on the same service 10.

## MVP / requirement coverage

- **Users:** Employee (self-register), Technician, Administrator; role-based UIs and server-side authorization.
- **Incidents:** create / view / update / assign / acknowledge / investigate / request-info / resolve / verify / reopen / close; feedback.
- **SLA:** per-priority and per-service overrides, deadlines, response+resolution tracking, 80 % warnings, violation recording, risk indicator.
- **Notifications:** In-app, Email (simulated, console + outbox), SMS (simulated, P1/escalations).
- **Audit:** every event, with timestamp, user, action, previous/new state, description.
- **Search:** ID/text, status, priority, category, service, technician, SLA status, date range.
- **Reports:** overview, by service/priority/status/category, technician workload, average resolution time, feedback, correlations.
- **Intelligent features (6):** duplicate detection · category suggestion · smart technician recommendation · SLA risk detection + warnings · automatic escalation (Technician → Team Lead → System Admin → IT Manager) · suggested resolutions · incident correlation.
- **Security:** token auth, hashed passwords, role checks on every endpoint, queryset scoping (employees see only their incidents, technicians only assigned ones), input validation, soft-delete of users.

## Demo workflows (for the video)

1. **Report → prioritise → assign → notify:** log in as `e101`, report "Payment application unavailable" (impact 4, urgency 4, 150 users) – watch category auto-detect, P1, SLA, auto-assignment; open Notifications as `t101`.
2. **Investigate → resolve → verify:** as `t101` acknowledge → start → see *suggested resolutions* from history → resolve; as `e101` confirm and rate; `t101` closes. Show audit trail as `admin`.
3. **Duplicates / correlation / escalation:** report 3 similar payment incidents as different employees → duplicate flags + dashboard correlation hint. Leave a P1 unacknowledged and click through the dashboard (the SLA monitor runs on load) or `python manage.py check_sla` → breach + escalation levels.

## Notes / assumptions

- Closing is done by the assigned technician or admin; verification by the reporter (or admin).
- The SLA monitor runs when an admin opens the dashboard (and every 60 s) or via `check_sla --loop`; swap in Celery/cron for production.
- SQLite is ideal for a course project (zero-config, file-based). For scale, only `DATABASES` in `settings.py` changes (PostgreSQL), because all access goes through the ORM.

## Frontend (Fluent UI v9)

- `App.jsx` wraps everything in `FluentProvider` (`webLightTheme` / `webDarkTheme`, toggle in the sidebar, remembered in localStorage) and builds the sidebar from a vertical `TabList` with Fluent icons.
- `ui.jsx` holds the shared Fluent building blocks (Section card, Stat, DTable, IncidentTable, badges, MessageBar helpers, Field-wrapped `Txt` / `Sel` / `Area`), so each page stays short and the look is consistent.
- Components used: Card, Table, Badge, Field, Input, Textarea, Select, Dropdown (multi-select skills), Switch, Checkbox, TabList, MessageBar, ProgressBar, Avatar, Spinner, Button.
- Styling uses Griffel `makeStyles` + design `tokens` (no hand-written colours), so dark mode works everywhere.

## Innovation features (beyond the MVP)

All logic lives in `backend/itsm/insights.py`; UI in `ServiceMap.jsx`, the dashboard and the incident page.

1. **Service dependency graph** – admins define "Payment depends on Database / SSO / Network" (Administration -> Dependencies; cycles are rejected). The *Service map* page draws the graph live, coloured by open incidents (green / amber / red for an open P1). Click a service to see what it depends on and its blast radius.
2. **Automated root-cause analysis** – when an incident is reported, the system walks the dependency graph upstream. If an upstream service already has open incidents, the deepest one is flagged as the *probable root cause*: an audit entry + notification is raised and the technician sees it in the incident's *Insights* panel.
3. **Dependency-aware priority** – a service's business criticality is raised to that of the most critical service that relies on it (a "low" database that feeds the payment system is treated as critical). Works with both priority strategies.
4. **Predictive SLA breach scoring** – for every open incident: `expected time` (historical mean for the same category+priority, falling back to 50 % of the SLA) -> remaining work -> inflated by the technician's queue (+15 % per active incident) -> logistic probability of breaching the resolution target. Shown per incident and as a "Predicted SLA breaches" table on the admin dashboard.

> **After pulling this update** the schema changed (new `ServiceDependency` table): delete `db.sqlite3` and the old `itsm/migrations/`, then re-run `makemigrations itsm`, `migrate`, `seed` (the seed now also creates the dependency graph).

Further ideas if time permits: LLM chatbot/voice reporting via the Anthropic API (the category-suggestion hook is the natural integration point), WebSocket push with Django Channels, and learning the priority weights from historical resolution data.
