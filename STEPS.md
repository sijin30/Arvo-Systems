# Frontdesk – Beginner-Friendly Breakdown and Step Plan

This guide explains the task from scratch, so you can learn as we build.
**Rule we follow: nothing gets coded until you confirm the decision it depends on.**

---

## 1. What is this task?

A company (Arvo Systems) hires you to build **Frontdesk**, a small support
ticket system, and **put it online**. The PDF gives **no requirements list**.
It gives a story (meeting notes + 3 incident reports) and you must dig the
rules out yourself. Finding them is part of the test.

- Time budget: about **8 hours**
- Send back: **live URL, repo link, README, short note** on what you did not finish and why

## 2. Words you need to know

| Term | Meaning |
|------|---------|
| Ticket | One customer problem |
| Agent | Support person who handles tickets |
| Priority | How serious: urgent / medium / low |
| SLA | The promise to the customer: reply within X, fix within Y |
| First response | The first reply an agent sends to the customer |
| Resolution | Ticket marked done |
| Working hours | Mon–Fri, 9:30–18:30 (9 hours/day), minus holidays |
| Breach / late | The deadline passed before the promise was met |
| Internal note | Message only the team sees |
| Public reply | Message the customer sees |
| Audit log | Permanent history of every action |

## 3. The use case

Today: spreadsheet + WhatsApp, 9 agents, ~40 tickets/day, ~20% late, no history.
Wanted: one system where agents work tickets, deadlines are computed
correctly, and managers can answer "which tickets were late and why?"

## 4. Rules hidden in the story

### 4.1 Deadlines (from Meera's words)

| Priority | First reply within | Fix within |
|----------|--------------------|------------|
| Urgent (customer cannot work) | 2 working hours | same working day |
| Medium | half a day (4 working hours, our interpretation) | ~3 working days |
| Low (questions, small requests) | 1 working day | ~5 working days |

"Half a day" = 4 hours and "about a week" = 5 working days are **interpretations**; we confirm them below.

### 4.2 The working-time clock

- Only counts 9:30–18:30, Mon–Fri, not holidays.
- Ticket arriving Friday 6 PM must not be late on Sunday. The clock effectively
  continues Monday morning.
- Needs a **holiday list** stored in the database.

### 4.3 Pausing the clock

When an agent asks the customer a question, status becomes
**Waiting on Customer** and the SLA timer **pauses**. When the customer replies,
it **resumes** with the remaining time (not a fresh start).

### 4.4 Auto-close

Customer silent for ~1 working week (5 working days) while waiting -> ticket auto-closes.

### 4.5 Reopen

Customer unhappy after "resolved" -> can reopen, but only within ~1 week.
After that they must create a **new** ticket.

### 4.6 Agent screen

One screen showing the agent's tickets, with clear marks for **late** and
**waiting on customer**. Opening a ticket lets them send a **public reply** or an **internal note**.

### 4.7 The unanswered question

"What happens to the timer if priority changes to urgent mid-way?"
Nobody answered. We must **decide and document** it (see section 9).

### 4.8 Lessons from the 3 incidents

| Incident | Problem | What we must build |
|----------|---------|--------------------|
| INC-0291 | Two agents took the same ticket | **Atomic claim**: only one wins, the other gets a clear error |
| INC-0304 | Private note reached the customer | **Notes never leak** in any screen, API, list or export. Enforce on the server, not just by hiding in the UI |
| INC-0318 | Nobody could prove when a reply was sent | **Append-only audit log** with timestamp, actor, action; database blocks edit/delete |

## 5. Features

1. Ticket creation (priority, customer, subject, description)
2. Ticket statuses and allowed transitions (state machine)
3. Claim/assign ticket (race-safe)
4. Public replies and internal notes
5. SLA engine (working-hours calculator, pause/resume, breach detection)
6. Auto-close job (scheduled)
7. Reopen within allowed window
8. Agent dashboard (my tickets, late, waiting)
9. Audit log
10. Customer-safe views/exports that never include internal notes
11. Holiday management
12. Login for agents

## 6. Components

- **Database (PostgreSQL):** tickets, messages (with visibility field), audit_log, agents, holidays, sla_policies
- **Backend API:** ticket endpoints, SLA calculator, scheduler, audit writer
- **Frontend:** agent dashboard, ticket detail page
- **Background job:** auto-close and breach checks
- **Hosting:** online deployment

## 7. Suggested ticket lifecycle

```
New -> Open (claimed) -> Waiting on Customer <-> Open
                      -> Resolved -> Reopened (within 1 week) -> Open
                      -> Closed (auto, or after reopen window)
```

## 8. Step-by-step plan (about 8 hours)

| Step | Work | Approx. time |
|------|------|--------------|
| 1 | Confirm decisions (section 9) | 0.5h |
| 2 | Pick stack, create project skeleton | 0.5h |
| 3 | Database schema and migrations | 1h |
| 4 | Working-hours / SLA calculator + tests | 1.5h |
| 5 | Ticket API: create, claim (atomic), reply, note, status | 1.5h |
| 6 | Audit log with database-level protection | 0.5h |
| 7 | Auto-close, reopen rules | 0.5h |
| 8 | Agent screen | 1h |
| 9 | Deploy online | 0.5h |
| 10 | README and "what I did not finish" note | 0.5h |

## 9. Decisions I need from you BEFORE coding

1. **Backend language:** Node.js or Python? (Frameworks too, e.g. Express/NestJS or FastAPI/Django)
2. **Frontend:** React, Vue, plain HTML, or something else?
3. **Database:** PostgreSQL (recommended) or MySQL?
4. **Hosting:** Render, Railway, Fly.io, or other?
5. **Medium reply "half a day":** 4 working hours OK?
6. **Low "about a week" / "about three days":** 5 and 3 working days OK?
7. **Priority change mid-ticket:** options
   - (a) Recompute deadlines from ticket creation using the new priority (strictest, simple)
   - (b) Recompute from the moment of change
   - (c) Keep the tighter of old and new deadline
   Which one? (my suggestion: a, and log the change)
8. **Reopen window:** 5 working days or 7 calendar days?
9. **Holidays:** which list? (we can seed Kerala/India examples, editable)
10. **Who are the customers?** Do customers log in, or are tickets entered by agents on their behalf? (Affects whether we need a customer-facing view.)
11. **Agent login:** simple seeded accounts, fine?
12. **Timezone:** Asia/Kolkata assumed.

## 10. Git rules for this project

- Remote: `https://github.com/sijin30/Arvo-Systems.git` (this folder only)
- Commits only, no co-author or "authored by Claude" lines
- Commit descriptions: 2–3 words
