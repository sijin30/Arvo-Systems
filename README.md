# Frontdesk

**A support-ticket system for Arvo Systems.** Customers report problems, agents fix them,
and every deadline, reply and change is calculated and recorded automatically.

Built for the iNav Technologies *Full Stack Developer* hiring test.

| | |
|---|---|
| **Live app** | _add the live URL here_ |
| **Repository** | https://github.com/sijin30/Arvo-Systems |
| **Stack** | React 19 + Tailwind CSS 4 (frontend), Python 3.12 + FastAPI (backend), PostgreSQL (database), hosted on Render |

> **First visit tip:** the free hosting plan sleeps when idle, so the very first page load
> can take about a minute. After that it is fast.

---

## Contents

1. [The problem we solved](#1-the-problem-we-solved)
2. [Try it in two minutes](#2-try-it-in-two-minutes)
3. [Who uses it](#3-who-uses-it)
4. [Use cases, one by one](#4-use-cases-one-by-one)
5. [The rules behind the clock](#5-the-rules-behind-the-clock)
6. [The three incidents and how they are prevented](#6-the-three-incidents-and-how-they-are-prevented)
7. [Decisions the brief left open](#7-decisions-the-brief-left-open)
8. [How it is built](#8-how-it-is-built)
9. [Running it locally](#9-running-it-locally)
10. [Tests](#10-tests)
11. [Deploying](#11-deploying)
12. [API reference](#12-api-reference)
13. [What is not finished](#13-what-is-not-finished)

---

## 1. The problem we solved

Arvo Systems has nine support agents who handle about forty customer problems a day. They
used a shared spreadsheet and a WhatsApp group. That broke down:

- About **one ticket in five was late**, and nobody could say which or why. The spreadsheet
  showed only how a ticket looks *now* and kept no history.
- Deadlines were counted in clock hours, so a ticket arriving **Friday 6 PM looked late on
  Sunday morning** even though nobody works weekends.
- **Waiting for the customer** counted against the team.
- **INC-0291:** two agents took the same ticket and sent the customer different answers.
- **INC-0304:** a private team note was sent to a customer by mistake.
- **INC-0318:** a customer said a reply took until next morning; Arvo said forty minutes.
  Nobody could prove it.

Frontdesk replaces the spreadsheet. A **customer** reports a problem; it waits in a shared
queue until one **agent** takes it; deadlines are measured in **working hours**; and every
action goes into a **permanent record** that nobody can edit.

---

## 2. Try it in two minutes

Open the live app and use one of these accounts. The password is the same for all:
**`Frontdesk@123`**

| Sign in as | Tab on the login page | Email |
|---|---|---|
| Support lead (can do everything) | *Support staff* | `meera@arvosystems.example` |
| Support agent | *Support staff* | `arjun@arvosystems.example` |
| Demo customer | *I'm a customer* | `priya@brightfin.example` |
| A brand-new customer | *I'm a customer* → **Create an account** | your own email and password |

The other agents are `anjali`, `rahul`, `sneha`, `vishnu`, `neha`, `kiran` and `fathima`, all
at `@arvosystems.example`.

**Suggested path:**

1. Create a customer account and **report a problem** (pick *I cannot work at all*).
2. Log out. Sign in as `arjun@arvosystems.example`, open **Everyone → Unassigned**, open your
   ticket and click **Take this ticket**.
3. Write a **Private team note**, then a **Reply to customer** with *waiting for the
   customer's answer* ticked. The ticket turns blue and its clock shows **Paused**.
4. Sign back in as the customer. You see the question and **not** the private note. Answer it.
5. Sign in as `meera@arvosystems.example`. Open **Team** to add an agent, and **Admin** to
   click **Verify now** on the history.

The app also starts with five demo tickets: a late urgent one, one waiting on a customer
(with a private note on it), one past its fix deadline, a fresh urgent one, and a recently
resolved one that can still be reopened.

---

## 3. Who uses it

| Who | How they get an account | What they can do |
|---|---|---|
| **Customer** | Signs up on the login page, no approval needed | Report problems, follow them, answer questions, reopen a solved ticket. Sees **only their own** tickets and **never** private notes |
| **Agent** | The lead creates the account | Takes tickets from the shared queue, replies, writes private notes, resolves |
| **Lead** | The lead creates the account (the first lead, Meera, comes pre-created) | Everything an agent does, plus assign tickets, **create / switch off agents and reset passwords**, manage holidays, verify the history |
| **System** | It is the app itself | Closes silent tickets and records missed deadlines |

There is one login page with two tabs. Staff and customer sessions are kept strictly
separate: a customer's login can never be used on a staff screen or action.

### Ticket statuses

| Status | Meaning | SLA clock |
|---|---|---|
| **New** | Reported, nobody owns it yet | Running |
| **Open** | An agent owns it and is working | Running |
| **Waiting on customer** | We asked a question and wait for the answer | **Paused** |
| **Resolved** | We say it is fixed; the customer can reopen it | Stopped |
| **Closed** | Finished for good | Stopped |

---

## 4. Use cases, one by one

### 4.1 A customer reports a problem
**Who:** customer. **Where:** *Report a problem*.

The customer enters a subject, a description, and chooses how much it affects them:
*I cannot work at all* (urgent), *something is broken but I can work around it* (medium) or
*a question or small request* (low). The ticket appears in the shared **Unassigned** queue
and the clocks start. The customer is told when we aim to reply.

### 4.2 A customer follows and answers their ticket
**Who:** customer. **Where:** *My requests*.

The customer sees only their own tickets with a plain status ("We are working on it", "We
are waiting for your reply"). Opening one shows the conversation, which contains **public
replies only**, and a box to write back. When we asked a question, the page says so, and the
customer's answer **restarts our clock**.

### 4.3 A customer reopens a solved ticket
**Who:** customer (or an agent on their behalf). **Where:** ticket page → *It is not fixed: reopen*.

Allowed for **one working week** after the ticket was resolved. The ticket goes back to
*Open* with the same agent and its clock carries on. After that week the ticket is closed and
the customer reports a **new** request instead.

### 4.4 An agent works the queue
**Who:** agent. **Where:** *Tickets* (the dashboard).

One screen shows four tiles (**Active**, **Unassigned**, **Already late**, **Waiting on
customer**) and a table. Late tickets are tinted red with a red **Late 3d** chip; tickets
waiting on the customer show a blue **Paused** chip. Tabs filter the list, *Mine / Everyone*
switches scope, there is a search box, and the page refreshes every 30 seconds. The
CSV export contains no message text.

### 4.5 An agent takes a ticket (no double-claiming)
**Who:** agent. **Where:** ticket page → *Take this ticket*.

If two agents click at the same moment, **exactly one wins**; the other sees "Asha already
took this ticket." Only the owner can then reply or resolve, so conflicting answers cannot be
sent. An agent can *Release* a ticket back to the queue; a lead can *Assign* it to someone.

### 4.6 An agent replies, or writes a private note
**Who:** agent. **Where:** the three tabs on the ticket page.

| Tab | Colour | Who sees it | Counts as the reply to the customer? |
|---|---|---|---|
| **Reply to customer** | Blue ("The customer WILL see this") | The customer | Yes. The first one stops the reply clock |
| **Private team note** | Amber with a lock ("Only your team can see this") | Staff only | No |
| **Log customer's message** | Grey | Staff | No (use it for what a customer says by phone) |

Any agent can add a note; only the owner can reply. A ticket needs at least one reply to the
customer before it can be resolved.

### 4.7 An agent asks the customer a question (pause the clock)
**Who:** agent. **Where:** *Reply to customer* with **I am waiting for the customer's answer** ticked.

The status becomes *Waiting on customer* and the SLA clock **pauses**. The page shows when
the ticket will close by itself if the customer stays silent. The clock restarts, with the
time that was left, when the customer answers.

### 4.8 An agent resolves a ticket
**Who:** agent (the owner). **Where:** *Resolve…* with an optional closing message.

Status becomes *Resolved*, and the customer can reopen it for a working week.

### 4.9 A ticket closes by itself
**Who:** the system.

- **Customer silent** for one working week while we wait → closed (`customer_inactive`).
- **Resolved** for more than one working week → closed (`reopen_window_expired`).

A background job runs every minute, and the history records every automatic close.

### 4.10 An agent changes the priority
**Who:** the owner, or a lead. **Where:** *Priority* drop-down (it asks for confirmation).

Deadlines are recalculated **from the time the ticket was created** under the new priority,
keeping time already used and paused time. Raising an old ticket to urgent can make it late
immediately. The change is recorded.

### 4.11 An agent logs a call or email
**Who:** agent. **Where:** *New ticket* and *Log customer's message*.

For customers who phone or email instead of using the site, an agent can create a ticket on
their behalf and type in what they say.

### 4.12 The lead manages the team
**Who:** lead. **Where:** *Team*.

Add an agent (name, email, role, a generated starting password), **switch an agent off or
on**, and **reset a password**. Safeguards: you cannot switch off yourself, the last active
lead, or an agent who still owns active tickets (reassign those first). Every action is
recorded, and passwords are never written to the record.

### 4.13 The lead manages holidays
**Who:** lead. **Where:** *Admin*.

Add or remove holidays. They do not count towards any deadline. Only fixed-date national
holidays are pre-loaded; add festival dates (Onam, Vishu, Eid, Diwali…) as they are announced.

### 4.14 The lead checks that history has not been tampered with
**Who:** lead. **Where:** *Admin → Verify now*.

Confirms every entry of the permanent record still matches its checksum. If anything was
altered, it says which entry.

### 4.15 Anyone can see the history of a ticket
**Who:** agents. **Where:** *History* panel on every ticket.

Every action with **what**, **who** and **when**: created, taken, replied, note added, waiting,
customer replied, resolved, reopened, priority changed, closed, deadline missed.

### 4.16 A read-only link for the customer
**Who:** anyone with the link. **Where:** *Copy customer view link* on a ticket.

A page that shows the ticket exactly as the customer sees it, without logging in. It is
read from a database view that **contains no private notes**.

---

## 5. The rules behind the clock

Only **working time** counts: **Monday to Friday, 9:30 am to 6:30 pm India time**, minus
holidays. That is 9 working hours a day. Deadlines are measured from the moment the ticket
was created.

| Priority | First reply within | Fix within |
|---|---|---|
| **Urgent** | 2 working hours | 1 working day (9 working hours) |
| **Medium** | half a working day (4h 30m) | 3 working days |
| **Low** | 1 working day | 5 working days |

- **Friday 6 PM:** a ticket arriving then has only 30 working minutes left on Friday. The
  rest starts Monday at 9:30, so an urgent reply is due **Monday 11:00** and the ticket is
  **not** late on Sunday morning.
- **Waiting on customer** pauses the clock; it resumes with the time that was left.
- **Resolved** time is not counted; a reopened ticket continues from where it stopped.
- A deadline that was already missed **stays missed**. Pausing afterwards cannot undo it.
- A missed deadline is written to the history once, stamped with the moment it was missed.
- Auto-close after silence, and the reopen window, are each **5 working days**.

All of this lives in two pure modules, `backend/app/worktime.py` (calendar arithmetic) and
`backend/app/sla.py` (deadlines and pausing), and is covered by unit tests, including the
Friday 6 PM example.

---

## 6. The three incidents and how they are prevented

### INC-0291: two agents took the same ticket
"Take this ticket" is **one database statement** that means "give it to me *only if nobody
has it*" (`service.claim_ticket`). Two simultaneous clicks cannot both succeed. Every other
change locks the ticket row first, and only the owner can reply or resolve. A test fires four
simultaneous claims from four database connections and expects exactly one winner. This also
protects tickets created by customers.

### INC-0304: a private note reached a customer
Several layers, so one mistake cannot expose a note:

1. Everything a customer can see is read from a database view (`customer_messages`) that
   **physically contains no private notes**.
2. The customer data shapes have **no field** that could carry a note, author or visibility flag.
3. Each customer sees **only their own tickets**; someone else's ticket answers "not found".
4. Exports contain **no message text**, and search ignores message text.
5. The history stores that a note *was added*, never what it said.

Tests plant a secret note and search every list, export, count, transcript, customer page and
link for it.

### INC-0318: "Did we reply in 40 minutes or the next morning?"
Every action writes a history entry: **what**, **who** and **when**, using both the app's
clock and the database's own clock. Then:

- The database **refuses to edit or delete** history (messages, history entries), and refuses
  to delete tickets or change when they were created or first answered. Even raw SQL is blocked.
- Each history entry holds a **SHA-256 fingerprint of the previous one**, assigned by the
  database. *Admin → Verify now* shows exactly where anything was altered, even by someone
  who switched the protection off.

*Limit:* it records when a reply was **saved in Frontdesk**. The app sends no email, so it
cannot say when anything reached an inbox.

---

## 7. Decisions the brief left open

The brief gives a story, not a requirements list. These were judgement calls. Each is
isolated in one place so it is easy to change.

| Question | Decision |
|---|---|
| Priority changed mid-way (nobody knew in the meeting) | Recompute deadlines **from creation time** under the new priority; keep used and paused time. Logged |
| "Half a day" | Half of the 9-hour working day: 4h 30m |
| "Same working day" (urgent fix) | One full working day (9 working hours). Reading it as "before 6:30 PM that day" would make a Friday 6 PM ticket late by Sunday, which the brief forbids |
| "About three days" / "about a week" | 3 and 5 working days |
| What counts as the first reply | The first **public** reply; a private note does not stop the reply clock |
| Pausing the clock | Only by a public reply with *waiting* ticked, so the question is on record. Only a customer message resumes it |
| Resolved time | The clock is stopped while resolved; reopening continues from where it stopped |
| Closed tickets | Final. The customer gets a new, linked ticket |
| How a customer's ticket reaches an agent | A shared queue; agents take tickets. Customers do not pick an agent |
| Customer accounts | Open sign-up, **no email verification** (the app sends no email). Sign-up is refused for an email support has already logged tickets for, so nobody can claim another person's history |
| Priority on a customer ticket | The customer chooses from plain-language options; an agent can change it |
| Time zone | India Standard Time everywhere; stored in UTC |

Policy numbers are in `backend/app/sla.py`.

---

## 8. How it is built

```
React + Tailwind  --HTTPS-->  FastAPI  --SQLAlchemy-->  PostgreSQL
 customer + staff screens     routes -> service -> sla / worktime      tickets, messages, sla_pauses,
                              background housekeeping thread           audit_log, holidays, agents, customers
```

| Part | Where | What it does |
|---|---|---|
| Working calendar | `backend/app/worktime.py` | Pure functions: working time between two moments, add working time |
| SLA engine | `backend/app/sla.py` | Deadlines, pausing, breach detection |
| Rules | `backend/app/service.py` | Every ticket state change, one row lock per ticket |
| Accounts | `backend/app/accounts.py` | Customer sign-up, passwords, agent management |
| Database and integrity | `backend/app/models.py`, `db.py` | Tables, append-only triggers, hash chain, customer view, upgrade of older databases |
| API | `routes.py`, `portal.py`, `views.py`, `schemas.py` | Staff API, customer API, and the two response families (staff shapes may carry notes; customer shapes cannot) |
| Background job | `backend/app/jobs.py` | Auto-close and missed-deadline logging, every minute |
| Frontend | `frontend/src/` | Customer pages, staff pages, Team and Admin |

In production the backend also serves the built frontend, so there is **one service** to host.

---

## 9. Running it locally

You need Python 3.12+ and Node 22+. PostgreSQL is optional for development because a
throw-away one is bundled.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt

# 2. A database. Use your own (DATABASE_URL=postgresql://user:password@localhost:5432/frontdesk)
#    or start the bundled one in a second terminal; it prints a DATABASE_URL:
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
automatically on first start, and a database created by an earlier version is upgraded in
place. To run it as one process: `npm run build` in `frontend/`, then start the API with
`STATIC_DIR` pointing at `frontend/dist`.

### Settings

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | _required_ | PostgreSQL URL (`postgres://` and `postgresql://` are both accepted) |
| `SECRET_KEY` | dev value | Signs login tokens. **Required** when `APP_ENV=production` |
| `APP_ENV` | `development` | `production` enforces `SECRET_KEY` |
| `STATIC_DIR` | _unset_ | Folder with the built frontend to serve |
| `SEED_DEMO` | `true` | Create agents, holidays, demo tickets and the demo customer on first start |
| `DEMO_PASSWORD` | `Frontdesk@123` | Password for the seeded accounts |
| `RUN_SCHEDULER` | `true` | Run housekeeping every minute inside the app |
| `TOKEN_HOURS` | `12` | Login lifetime |

---

## 10. Tests

```bash
cd backend
pytest
```

**110 tests**, run against a real PostgreSQL (a bundled one starts automatically; set
`TEST_DATABASE_URL` to use your own, or `PGTEST_DIR` to keep its files outside a synced folder).

| Area | What is proved |
|---|---|
| Working time and SLA | Friday 6 PM, weekends, holidays, pausing, resuming, priority change, auto-close and reopen limits |
| Ticket lifecycle | Claim, release, assign, reply, note, resolve, reopen, close, dashboard views |
| Concurrency | Four simultaneous claims produce exactly one winner; concurrent history writes keep one unbroken chain |
| Privacy | A secret note never appears in any customer response, list, export, transcript or count |
| Integrity | Raw SQL cannot rewrite history; tampering is detected; inconsistent rows are rejected |
| Customer portal | Sign-up rules, isolation between customers, replies resume the clock, reopen window |
| Agent management | Lead-only access, switch-off rules, password reset, an older database upgrades safely |

---

## 11. Deploying

A `Dockerfile` (builds the frontend and serves everything from one container) and a
`render.yaml` blueprint (web service + PostgreSQL) are included.

1. Push the repository to GitHub.
2. In Render choose **New → Blueprint** and select the repository. It creates the database,
   passes `DATABASE_URL` to the app and generates `SECRET_KEY`.
3. Open the URL Render gives you.

When a newer version starts against an existing database, the app upgrades the tables
itself and keeps the data. On the free plan the service sleeps when idle, and the free
database expires after about 30 days.

---

## 12. API reference

All endpoints are under `/api`. Errors look like `{"error": {"code", "message"}}`. Staff
endpoints need `Authorization: Bearer <staff token>`; portal endpoints need a customer token.

**Staff**

| Method and path | Purpose |
|---|---|
| `POST /auth/login`, `GET /auth/me`, `POST /auth/password`, `GET /agents` | Sign in, profile, change own password, agent list |
| `GET /tickets?scope=mine\|all&view=active\|unassigned\|late\|waiting\|resolved\|closed\|history&q=&priority=` | List tickets with SLA state |
| `GET /tickets/counts`, `GET /tickets/export.csv` | Dashboard counters; CSV without message text |
| `POST /tickets` | Log a ticket for a customer |
| `GET /tickets/{id}` | Thread (including private notes), SLA and allowed actions |
| `POST /tickets/{id}/claim`, `/release`, `/assign` | Ownership (assign is lead-only) |
| `POST /tickets/{id}/messages` | `public_reply`, `internal_note` or `customer_message`; `set_waiting` pauses the clock |
| `POST /tickets/{id}/resolve`, `/reopen`, `/priority` | Lifecycle |
| `GET /tickets/{id}/audit`, `GET /tickets/{id}/transcript` | History; customer-safe transcript |
| `GET/POST/DELETE /holidays` | Holiday calendar (changes are lead-only) |
| `GET/POST /admin/agents`, `POST /admin/agents/{id}/deactivate`, `/activate`, `/password` | Lead-only agent management |
| `GET /audit/verify`, `POST /ops/housekeeping` | Lead-only: verify history, run the sweep now |

**Customer**

| Method and path | Purpose |
|---|---|
| `POST /portal/signup`, `/portal/login`, `GET /portal/me`, `POST /portal/password` | Account |
| `GET/POST /portal/tickets`, `GET /portal/tickets/{id}` | The customer's own tickets |
| `POST /portal/tickets/{id}/messages`, `/reopen` | Reply (restarts the clock if we were waiting); reopen |
| `GET /public/tickets/{token}` | Read-only shared link; no login, no private notes |

`GET /health` is a health check.

---

## 13. What is not finished

- **No email.** The app sends none, so there is no email verification at sign-up, no "forgot
  password" link and no notification when someone replies. A forgotten agent password is reset
  by the lead; a forgotten customer password cannot be reset yet.
- **Sessions:** a password change or reset does not end a session that is already open (it
  expires within 12 hours).
- **Customers cannot choose a preferred agent**, and sign-up has no rate limit beyond the
  failed-login throttle (which is in memory, one server).
- **The dashboard** shows the first 100 matching tickets with no paging.
- **Holidays:** only fixed-date national holidays are pre-loaded.
- **Frontend tests:** the React screens have no automated tests; they were checked with a
  scripted real-browser run (Microsoft Edge) covering sign-up, queue, claim, note, reply,
  customer answer, and creating an agent.
- **"Sent" means saved**, not delivered to an inbox.

See [`NOTE.md`](./NOTE.md) for the short note on what was left out and why.
