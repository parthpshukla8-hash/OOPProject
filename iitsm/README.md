# I-ITSM – Intelligent IT Service Management & Incident Resolution System

**Stack:** React 18 (Vite) · Django 5 · Django REST Framework · SQLite · Token auth

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

# Tests (26 cases) and optional continuous SLA monitor
python manage.py test itsm -v 2
python manage.py check_sla --loop --interval 60
```

Demo logins: `admin/admin123` · technicians `t101…t104 / tech1234` · employees `e101…e103 / pass1234`

## Architecture

```
React SPA (role-based UI)  --REST/JSON + Token-->  DRF views (thin)
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
