# I-ITSM: Intelligent IT Service Management & Incident Resolution System

**Stack:** React 18 + TypeScript (Vite) + Fluent UI v9 · Django 5 + Django REST Framework · SQLite · token auth
>[!IMPORTANT]
> We have added the video in the GitHub repo since the video was large for the GForm and not getting uploaded in the GDrive folder too

## Run it

```bash
# Local demo only. Do not enable DEBUG or seed demo accounts in a deployment.
export DJANGO_DEBUG=true

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations itsm                   # custom user model: create migrations first
python manage.py migrate
ITSM_ALLOW_DEMO_SEED=1 python manage.py seed           # disposable demo users, services, SLA policies and incidents
python manage.py runserver                             # http://127.0.0.1:8000

# Frontend (second terminal)
cd frontend
npm install
npm start                                              # http://localhost:5173, proxies /api to Django

# Tests
cd backend && python manage.py test itsm -v 2          # 52 tests
cd frontend && npm test                                # API key translation
python manage.py check_sla --loop --interval 60        # optional: continuous SLA monitor
```

Demo logins: `admin/admin123` · IT manager `manager/manager123` · technicians `t101…t104 / tech1234` · employees `e101…e104 / pass1234`.
Employee self-registration is not available; administrators provision employee accounts. Employee accounts identify incident reporters so access to reports, updates, and notifications can be scoped correctly.
To re-seed, delete `db.sqlite3` and the `itsm/migrations/` folder, then repeat the migrate and seed steps.

API endpoints require authentication. Login issues a token that rotates on each successful login and expires after 24 hours; login is limited to 5 attempts per minute per IP. For multi-worker deployments, configure a shared Django cache so throttling is consistent across workers.

For deployments, leave `DJANGO_DEBUG` unset or set it to `false`, provide a unique `DJANGO_SECRET_KEY`, and set `DJANGO_ALLOWED_HOSTS` to a comma-separated list of the deployment's hostnames. The demo seed command refuses to run when `DEBUG` is disabled.

### 1. Cosine similarity everywhere text is compared (`backend/itsm/similarity.py`)
TF-IDF vectors (unigrams + bigrams, light stemming, an incident-language synonym map so "unavailable", "down" and "outage" count as one idea) compared with cosine similarity. Pure Python, no ML dependency.

| Where it is used | Module | How |
|---|---|---|
| Duplicate detection (>= 0.5 likely duplicate, >= 0.28 related) | `intelligence.find_similar_incidents` | New text vs open incidents, +0.1 when the service matches |
| Category and service auto-detect | `intelligence.suggest_category / suggest_service` | Text vs the centroid of each label's keywords and past incidents (`CentroidClassifier`) |
| Live "already reported" help while typing | `services.analyze_report` | Same index, shown beside the report form with an "I'm affected too" action |
| Suggested resolutions | `intelligence.suggest_resolutions` | Text vs resolved incidents, de-duplicated by resolution |
| Incident correlation | `intelligence.correlate_open_incidents` | Pairwise cosine over open incidents, union-find clusters |
| Smart technician recommendation | `assignment.SmartAssignmentStrategy` | 40 skill + 30 free capacity + 20 experience + 10 cosine similarity to the technician's resolved history |
| Free-text search | `services.search_incidents` | Results ranked by cosine score; `INC0012` style codes match exactly |
| Command palette (Ctrl K) | `CommandPalette.tsx` | Calls the same ranked search |

Every match carries its `matched_terms`, so the UI can say why ("matches on payment, down").

### 2. A UI built around the person's situation, not a dashboard kit
- **Role-aware by construction:** the server returns `available_actions` for each incident and user (State pattern + permissions); the UI renders only those. A technician sees *Acknowledge*, then *Start investigating*, then *Mark resolved*; the reporter sees *It works now / Not fixed*; an admin sees *Assign* with ranked suggestions.
- **Report page:** one plain-language form. As you type, the right column fills with: similar open reports (join instead of duplicating), fixes that worked before, and how the incident will be treated. "Who is affected" and "how soon" replace raw impact/urgency numbers.
- **Linear-style workspace:** list and detail side by side, `J`/`K` to move, `/` to search, filters kept in the URL, Ctrl K command palette.
- **Tufte-style data:** SLA is one thin bar with a tick at the 80% warning point; sparklines for volume; capacity bars for workload; no tile grids.
- **Situation page for administrators:** one sentence on what needs a human, then an ordered list (unassigned, escalated, likely to breach, correlated reports).
- **Service map:** layered dependency graph; select a service to dim everything unrelated and see what it affects.
- Fluent UI v9 theme (custom brand ramp, light and dark), CSS Modules with BEM names, Fluent tokens for colour.

Design references: Linear (list/detail, keyboard, command palette), Edward Tufte (sparklines, data-ink), Dieter Rams (less, but better), incident.io (activity timeline as a narrative).

## Architecture

```
React SPA (Fluent UI v9, role-aware)  --REST/JSON + Token-->  DRF views (thin)
                                                  |
                       services.py (use cases: create, update, perform_action, assign, join, search)
                          |         |          |            |             |
                  factories.py  lifecycle.py  assignment.py  priority.py  sla.py
                          \         |          |            /             |
                           intelligence.py <- similarity.py (TF-IDF + cosine)      insights.py (dependency graph)
                                   |
                           models.py (ORM) <-> SQLite
                           events.py (EventBus) -> observers.py -> AuditEvent + channels.py (Notification)
```

## OOP concepts and patterns

| Pattern / concept | Where |
|---|---|
| **State** | `lifecycle.py`: one class per status with allowed next states, entry guards and side effects. `NEW -> CLOSED` raises `InvalidStateTransition`. |
| **Strategy** | `assignment.py` (Skill, Load, Round-robin, Smart), `priority.py` (Weighted, Rule-based), `channels.py` (In-app, Email, SMS). Administrators switch strategies at runtime. |
| **Observer** | `events.py` + `observers.py`: services publish `DomainEvent`s; `AuditObserver` and `NotificationObserver` react. |
| **Factory** | `UserFactory`, `IncidentFactory` (`factories.py`), `ChannelFactory` (`channels.py`). |
| Abstraction / interfaces | ABCs `IncidentState`, `AssignmentStrategy`, `PriorityStrategy`, `NotificationChannel`, `EventObserver` |
| Encapsulation | `SparseVector` is immutable; `User.active_incident_count`, `Incident.code` are computed properties |
| Composition | `RuleBasedPriorityStrategy` wraps `WeightedScoringPriorityStrategy`; `TfidfModel` is owned by `SimilarityIndex` |
| Inheritance (true is-a only) | `ItsmError` hierarchy, `User(AbstractUser)`, `IncidentDetailSerializer(IncidentSerializer)` |
| Exceptions | `exceptions.py` (13 domain errors) mapped to HTTP codes in `api_errors.py`; database failure becomes 503 |

**Priority:** `score = impact (1-4) x urgency (1-4) x criticality (1-5)`, x1.25 for 20+ users, x1.5 for 100+. Bands: >= 48 P1, >= 24 P2, >= 8 P3, else P4. Criticality is dependency-aware: a service is at least as critical as the most critical service that relies on it.

**SLA:** per-priority defaults with per-service overrides; response and resolution deadlines; warning at 80%; violations recorded once; escalation Technician -> Team lead -> System administrator -> IT manager for unacknowledged P1/P2.

**Innovation:** service dependency graph, automated root-cause hint, dependency-aware priority, predictive SLA breach score (history, technician queue, logistic curve), cosine-based correlation and join-an-existing-incident flow.

## Requirement coverage
Users (employee, technician, administrator, IT manager flag) · incident create/view/update/assign/acknowledge/investigate/request-info/resolve/verify/reopen/close/feedback · 8 search criteria (text/ID, status, priority, category, service, technician, SLA status, date range) · reports (overview, by service/priority/status/category, workload, fix time, satisfaction, correlations, predicted breaches) · audit trail on every event · in-app, simulated email and SMS (outbox in Administration) · token auth, hashed passwords, role checks on every endpoint, queryset scoping, input validation, soft-delete of users.

## Naming
Follows `NamingConvention.pdf`: `incident`, `technician`, `service` used everywhere; PascalCase components with `.module.css` BEM classes; kebab-case non-component modules; snake_case Python; plural kebab-case API routes (`/api/sla-policies/`). The API is snake_case and the front end camelCase; the translation lives in one place, `frontend/src/api/api-client.ts`. The single Django app is named `itsm` (the product domain) rather than split by capability, to keep migrations simple; internal modules are split by responsibility.

## Honest limits
- Similarity indexes are rebuilt per request (fine for thousands of incidents). For scale, cache the index and invalidate on incident save, or move to pgvector/Elasticsearch.
- The SLA clock does not pause while waiting for the reporter.
- SMS and email are simulated.
- Created in an environment without Django or npm access: the backend was compile-checked and the similarity engine unit-tested, but the Django test suite and the front-end build have **not been run yet**. Run `python manage.py test itsm` and `npm run build` first and send me any failures.
