# Arvo Systems – Frontdesk

A support ticketing system for Arvo Systems' support team, built as the
**iNav Technologies Full Stack Developer hiring test** (dated 21-11-2026).

> **Status:** Planning / analysis complete. No application code yet.
> Implementation starts only after the open decisions are confirmed.`n`n## The problem

Arvo has 9 support agents handling ~40 tickets a day using a shared
spreadsheet and a WhatsApp group. About 1 in 5 tickets was late last quarter,
and nobody could say which or why, because the spreadsheet keeps no history.
Frontdesk replaces it.

## What Frontdesk must do

| Area | Requirement |
|------|-------------|
| SLA by priority | Urgent: reply 2h, resolve same working day. Medium: reply half a day, resolve ~3 days. Low: reply 1 day, resolve ~1 week |
| Working-time clock | Counts only Mon–Fri, 09:30–18:30, excluding holidays |
| Pause on customer | Clock stops while waiting for the customer's reply |
| Auto-close | Ticket closes after ~1 working week of customer silence |
| Reopen | Customer can reopen a resolved ticket for ~1 week; after that, a new ticket |
| Agent screen | One screen of my tickets, showing late ones and waiting-on-customer ones |
| Replies and notes | Public reply to customer, or internal note for team only |
| No double-claiming | Two agents cannot take the same ticket (INC-0291) |
| Private notes stay private | Never in a screen, API response, export or list for customers (INC-0304) |
| Tamper-proof history | Append-only record of what happened, when, by whom (INC-0318) |

## Planned tech stack (not final – pending confirmation)

- Backend: Node.js or Python
- Database: PostgreSQL
- Frontend: any framework, simple agent screen
- Hosting: free tier (Render / Railway / Fly.io etc.), kept live for one week

## Deliverables

1. Live URL
2. Repository link
3. This README (with local run instructions – added once code exists)
4. Short note: what was not finished, and why

## Repository contents

| File | Purpose |
|------|---------|
| `Hiring Test - Full Stack Developer.pdf` | The original brief |
| `README.md` | This file |

## Running locally

_To be added once the application is implemented._
