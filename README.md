# Frontdesk

A support-ticket system for **Arvo Systems**, built for the iNav Technologies
*Full Stack Developer* hiring test. It replaces a shared spreadsheet and a WhatsApp
group with one place where nine agents work about forty tickets a day, and where
every deadline, reply and change is on the record.

| | |
|---|---|
| Frontend | React 19, Tailwind CSS 4, Vite |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 |
| Database | PostgreSQL 12+ |
| Live URL | _add after deploying (see [Deploying](#deploying))_ |

## What the brief asked for, and where it lives

The brief contains no requirement list, only a meeting transcript and three incident
reports. These are the rules found in them and how each is implemented.

| Rule found in the brief | How Frontdesk handles it | Code |
|---|---|---|
| Promise depends on priority: urgent reply 2h / fix same working day, medium reply half a day / fix about 3 days, low reply 1 day / fix about a week | `POLICIES` table, one entry per priority | `backend/app/sla.py` |
| Time is **working time**: 9:30-18:30, Mon-Fri, no holidays. A ticket arriving Friday 6 PM must not be late on Sunday | Pure working-time calculator; holidays come from a table the lead can edit | `backend/app/worktime.py` |
| Time spent waiting for the customer does not count against us | The SLA clock is stopped while a ticket is *Waiting on customer*, and resumes with the time that was left | `sla.py`, `service.py` |
| ~1 working week of customer silence closes the ticket | Background job closes it after 5 working days | `backend/app/jobs.py` |
| Customer can reopen a resolved ticket for ~1 week, after that it is a new ticket | Reopen allowed for 5 working days; afterwards the API refuses and the screen offers *Create follow-up ticket* (linked to the old one) | `service.reopen_ticket` |
| Agents see their tickets on one screen, with late and waiting ones obvious | Dashboard with counters, tabs, coloured SLA chips | `frontend/src/pages/Dashboard.jsx` |
| Agent can reply to the customer or write a team-only note | Ticket page with three clearly coloured composer tabs | `frontend/src/pages/Ticket.jsx` |
| Unanswered: what happens to the timer when priority changes? | Decided and written down, see [Decisions](#decisions-the-brief-left-open) | `sla.py`, `service.change_priority` |
| **INC-0291** two agents took the same ticket | Claiming is one atomic database statement; exactly one agent wins, the other gets a clear 409. Only the owner can reply or resolve | `service.claim_ticket` |
| **INC-0304** a private note reached a customer | Notes are filtered at the database: customer-facing code can only read the `customer_messages` view, which contains no internal rows. Customer-shaped responses have no field that could carry a note. Exports contain no message text at all | `db.py`, `views.py`, `schemas.py` |
| **INC-0318** nobody could prove who did what, and when | Append-only, hash-chained audit log. Triggers refuse UPDATE/DELETE/TRUNCATE on history tables, even for raw SQL | `db.py`, `audit.py` |

## Quick tour

1. Sign in (demo accounts below). The dashboard shows *My tickets*, with counters for
   active, unassigned, **already late** and **waiting on customer** tickets.
2. Open a ticket, **Take this ticket**, and use the composer:
   - blue **Reply to customer**: "The customer WILL see this message."
   - amber **Private team note**: "Only your team can see this."
   - grey **Log customer's message**: record what the customer said by phone or email.
3. Tick *I am waiting for the customer's answer* when you ask a question. The clock
   pauses and the ticket shows when it will close by itself.
4. **Resolve** sends a closing message; **Reopen** works for a working week.
5. The *History* panel lists every action with who and when. Leads get an **Admin**
   page for holidays, an integrity check of the history, and a manual housekeeping run.
6. *Copy customer view link* gives a page exactly as the customer would see it.

### Demo accounts

All nine agents exist; the password is the same for all (change it with `DEMO_PASSWORD`).

| Email | Role |
|---|---|
| `meera@arvosystems.example` | Support lead (can assign, manage holidays, verify history) |
| `arjun@`, `anjali@`, `rahul@`, `sneha@`, `vishnu@`, `neha@`, `kiran@`, `fathima@` followed by `arvosystems.example` | Agent |

Password: `Frontdesk@123`

On first start the app also creates five demo tickets that show a late urgent ticket, a
ticket waiting on a customer (with a private note on it), a ticket past its fix
deadline, a fresh urgent ticket and a recently resolved ticket that can still be reopened.
Set `SEED_DEMO=false` to start empty.

## How the clock works

All durations are **working time** (one working day = 9 hours). Deadlines are measured
from the moment the ticket was created.

| Priority | First reply within | Fix within |
|---|---|---|
| Urgent | 2 working hours | 1 working day (9 hours) |
| Medium | half a working day (4h 30m) | 3 working days |
| Low | 1 working day | 5 working days |

- The clock **stops** while the ticket is *Waiting on customer* and while it is *Resolved*,
  and carries on with the remaining time afterwards.
- A ticket that arrives at 6 PM on Friday has 30 working minutes left on Friday; the
  rest of its time starts on Monday at 9:30.
- A deadline that was already missed stays missed: pausing afterwards cannot undo it.
- A missed deadline is written to the history once, stamped with the moment it was
  missed (not the moment someone noticed).

## Decisions the brief left open

These are judgement calls. Each is isolated in one place so it is easy to change.

| Question | Decision |
|---|---|
| Priority changed mid-way | Deadlines are recomputed **from creation time** using the new priority's policy; time already used and paused time are kept. Raising a ticket to urgent can therefore make it late immediately. The change and the new standing are logged |
| "Half a day" | Half of the 9-hour working day: 4h 30m |
| "Same working day" (urgent fix) | One full working day (9 working hours) from arrival. Reading it as "before 6:30 PM on the arrival date" would make a Friday 6 PM ticket late by Sunday, which the brief forbids |
| "About three days" / "about a week" | 3 and 5 working days. Auto-close and the reopen window are also 5 working days |
| Resolved time | The clock is stopped while resolved. A reopened ticket continues with the time it had left |
| What counts as the first reply | The first **public** reply. A private note does not stop the reply clock |
| Pausing the clock | Only by sending a public reply with *waiting* ticked, so the question is on record. Only a customer message (logged by the agent) resumes it. Agents cannot pause or resume by themselves |
| Closed tickets | Final. Auto-closed tickets, and tickets resolved more than a working week ago, are not reopened; the customer gets a new, linked ticket |
| Who are customers | The brief describes a screen for agents, so agents log tickets and customer messages. Customers get a read-only link, not a login |
| Holidays | Seeded with fixed-date national holidays only. Festival dates that move every year (Onam, Vishu, Eid, Diwali...) are added by the lead on the Admin page |
| Time zone | Asia/Kolkata (IST) everywhere; stored in UTC |

## Architecture

```
React (Vite, Tailwind)  --HTTPS-->  FastAPI  --SQLAlchemy-->  PostgreSQL
 agent screens + customer view      routes -> service -> sla/worktime      tickets, messages, sla_pauses,
                                    background housekeeping thread         audit_log, holidays, agents ...
```

- `worktime.py`, `sla.py`: pure functions with no database or clock; the heart of the app.
- `service.py`: every state change. One place for the rules, one row lock per ticket.
- `db.py`: schema creation plus the integrity triggers (append-only tables, hash chain).
- `routes.py`, `views.py`, `schemas.py`: thin HTTP layer and the two response families
  (agent shapes may carry notes; customer shapes cannot).
- In production the backend also serves the built frontend, so there is one service to host.

### Why the guarantees hold

- **One owner per ticket.** `UPDATE ... WHERE assignee_id IS NULL AND status = 'new'` is a
  single statement, so concurrent clicks cannot both succeed. Every other change takes a
  `SELECT ... FOR UPDATE` row lock first. A test fires four simultaneous claims from four
  database connections and expects exactly one winner.
- **Notes cannot leak.** Three layers: the customer API reads only from the
  `customer_messages` view; the customer response models contain no note-capable field;
  audit entries store message ids, never message text. Tests search every list, export,
  count, transcript, audit and customer response for a secret string.
- **History cannot be rewritten.** Triggers reject UPDATE, DELETE and TRUNCATE on
  `messages` and `audit_log`; `tickets` cannot be deleted and `created_at` and
  `first_response_at` cannot change; a pause row can be closed once. Each audit row also
  stores a SHA-256 hash of the previous row, assigned by the database, so
  `GET /api/audit/verify` shows if anyone with full database rights bypassed the triggers.

## Running locally

You need Python 3.12+ and Node 22+. PostgreSQL is optional for development: a
throw-away one is bundled.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt

# 2. A database. Either use your own...
#      DATABASE_URL=postgresql://user:password@localhost:5432/frontdesk
#    ...or start the bundled one in a second terminal (it prints a DATABASE_URL):
python run_dev_db.py

# 3. Start the API (set DATABASE_URL first)
#    PowerShell: $env:DATABASE_URL="postgresql://postgres:@127.0.0.1:PORT/postgres"
#    bash:       export DATABASE_URL=postgresql://postgres:@127.0.0.1:PORT/postgres
uvicorn app.main:create_app --factory --reload --port 8000
```

```bash
# 4. Frontend, in another terminal
cd frontend
npm install
npm run dev                        # http://localhost:5173 (proxies /api to :8000)
```

Tables, integrity triggers, the nine agents, holidays and demo tickets are created
automatically on first start.

To run it like production (one process): `npm run build` in `frontend/`, then start the
API with `STATIC_DIR` pointing at `frontend/dist`, and open http://localhost:8000.

### Settings

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | _required_ | PostgreSQL URL (`postgres://` and `postgresql://` both accepted) |
| `SECRET_KEY` | dev value | Signs login tokens. **Required** when `APP_ENV=production` |
| `APP_ENV` | `development` | `production` enforces `SECRET_KEY` |
| `STATIC_DIR` | _unset_ | Folder with the built frontend to serve |
| `SEED_DEMO` | `true` | Create agents, holidays and demo tickets on an empty database |
| `DEMO_PASSWORD` | `Frontdesk@123` | Password given to the seeded agents |
| `RUN_SCHEDULER` | `true` | Run housekeeping every minute inside the app |
| `TOKEN_HOURS` | `12` | Login lifetime |

### Tests

```bash
cd backend
pytest
```

83 tests: the working-time and SLA maths (including the Friday 6 PM example, holidays,
pausing and priority changes), the full ticket lifecycle over HTTP, real concurrent
claims, privacy (no note ever reaches a customer-facing response) and integrity (raw SQL
cannot rewrite history; tampering is detected). The tests start a bundled PostgreSQL
automatically; set `TEST_DATABASE_URL` to use your own.

## API overview

All endpoints are under `/api` and, except login and the customer view, need
`Authorization: Bearer <token>`. Errors look like `{"error": {"code", "message"}}`.

| Method and path | Purpose |
|---|---|
| `POST /auth/login`, `GET /auth/me`, `GET /agents` | Sign in, current agent, agent list |
| `GET /tickets?scope=mine\|all&view=active\|unassigned\|late\|waiting\|resolved\|closed\|history&q=&priority=` | List tickets with SLA state |
| `GET /tickets/counts`, `GET /tickets/export.csv` | Dashboard counters; customer-safe CSV (no message text) |
| `POST /tickets` | Create a ticket for a customer |
| `GET /tickets/{id}` | Ticket with its full thread (including private notes, agents only) and allowed actions |
| `POST /tickets/{id}/claim`, `/release`, `/assign` | Ownership (assign is lead-only) |
| `POST /tickets/{id}/messages` | `public_reply`, `internal_note` or `customer_message`; `set_waiting` pauses the clock |
| `POST /tickets/{id}/resolve`, `/reopen`, `/priority` | Lifecycle |
| `GET /tickets/{id}/audit`, `GET /tickets/{id}/transcript` | History; customer-safe transcript |
| `GET /public/tickets/{token}` (+ `/transcript`) | What a customer may see. No login, no private notes |
| `GET/POST/DELETE /holidays` | Holiday calendar (changes are lead-only) |
| `GET /audit/verify`, `POST /ops/housekeeping` | Lead-only: verify history, run the sweep now |
| `GET /health` | Health check |

## Deploying

A `Dockerfile` (builds the frontend, serves everything from one container) and a
`render.yaml` blueprint (web service + free PostgreSQL) are included. They have not been
run yet; see `NOTE.md`.

1. Push the repository to GitHub.
2. In Render: **New, Blueprint**, select the repository. It creates the database, injects
   `DATABASE_URL`, and generates `SECRET_KEY`.
3. When the build finishes, put the live URL in the table at the top of this file.

Notes for the free tier: the service sleeps when idle, so the first request after a pause
takes about a minute to wake. Housekeeping is based on timestamps, so after waking it
catches up on anything that came due while it slept.

## Repository layout

```
backend/app/        worktime, sla, models, db (triggers), service, routes, views, jobs, seed
backend/tests/      unit, API, concurrency, privacy and integrity tests
backend/run_dev_db.py   throw-away local PostgreSQL for development
frontend/src/       React app: pages/, components, API client
Dockerfile, render.yaml
NOTE.md             what was not finished, and why
```

See [`NOTE.md`](./NOTE.md) for what is not finished.
