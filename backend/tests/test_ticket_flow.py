"""End-to-end behaviour of tickets: ownership, replies, clock pausing, closing, reopening."""
from datetime import date, timedelta

from app import worktime as wt
from app.jobs import run_housekeeping
from conftest import ist, new_ticket


def claim(client, h, tid):
    return client.post(f"/api/tickets/{tid}/claim", headers=h)


def reply(client, h, tid, body="Hello", kind="public_reply", **extra):
    return client.post(
        f"/api/tickets/{tid}/messages", json={"kind": kind, "body": body, **extra}, headers=h
    )


# ---------------------------------------------------------------- auth
def test_login_and_wrong_password(client):
    bad = client.post("/api/auth/login", json={"email": "asha@arvo.test", "password": "nope"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "bad_credentials"
    assert client.get("/api/tickets").status_code == 401
    assert client.get("/api/tickets", headers={"Authorization": "Bearer junk"}).status_code == 401


# ----------------------------------------------------------- ownership
def test_claim_assigns_and_second_agent_is_refused(client, auth):
    t = new_ticket(client, auth("asha"))
    first = claim(client, auth("asha"), t["id"])
    assert first.status_code == 200
    assert first.json()["status"] == "open"
    assert first.json()["assignee"]["name"] == "Asha"

    second = claim(client, auth("ben"), t["id"])
    assert second.status_code == 409
    err = second.json()["error"]
    assert err["code"] == "already_claimed"
    assert err["assignee"]["name"] == "Asha"
    # nothing about the ticket changed
    assert client.get(f"/api/tickets/{t['id']}", headers=auth("ben")).json()["assignee"]["name"] == "Asha"


def test_two_agents_clicking_at_the_same_instant_only_one_wins(factory, agents, engine):
    """INC-0291 at the database level: real concurrent transactions."""
    import threading

    from app import clock, service
    from app.errors import DomainError
    from app.models import Agent

    with factory() as s:
        asha = s.get(Agent, agents["asha"])
        ticket = service.create_ticket(
            s, asha, subject="x", description="y", priority="low",
            customer_name="C", customer_email="c@c.test", related_ticket_id=None, now=clock.now(),
        )
        s.commit()
        tid = ticket.id

    contenders = ["asha", "ben", "chitra", "meera"]
    barrier = threading.Barrier(len(contenders))
    outcomes: list[str] = []

    def attempt(handle):
        with factory() as s:
            agent = s.get(Agent, agents[handle])
            barrier.wait()
            try:
                service.claim_ticket(s, agent, tid, clock.now())
                s.commit()
                outcomes.append(f"won:{handle}")
            except DomainError as e:
                s.rollback()
                outcomes.append(f"lost:{e.code}")

    threads = [threading.Thread(target=attempt, args=(h,)) for h in contenders]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert len([o for o in outcomes if o.startswith("won")]) == 1, outcomes
    assert outcomes.count("lost:already_claimed") == 3, outcomes


def test_only_the_assignee_may_reply_or_resolve_but_anyone_may_add_a_note(client, auth):
    t = new_ticket(client, auth("asha"))
    claim(client, auth("asha"), t["id"])
    assert reply(client, auth("ben"), t["id"]).status_code == 403
    assert reply(client, auth("ben"), t["id"]).json()["error"]["code"] == "not_assignee"
    assert client.post(f"/api/tickets/{t['id']}/resolve", json={}, headers=auth("ben")).status_code == 403
    assert reply(client, auth("ben"), t["id"], "psst", kind="internal_note").status_code == 201


def test_cannot_reply_before_claiming(client, auth):
    t = new_ticket(client, auth("asha"))
    r = reply(client, auth("asha"), t["id"])
    assert r.status_code == 403


def test_release_and_lead_assignment(client, auth, agents):
    t = new_ticket(client, auth("asha"))
    claim(client, auth("asha"), t["id"])
    assert client.post(f"/api/tickets/{t['id']}/release", headers=auth("ben")).status_code == 403
    released = client.post(f"/api/tickets/{t['id']}/release", headers=auth("asha")).json()
    assert released["status"] == "new" and released["assignee"] is None

    body = {"agent_id": agents["chitra"]}
    assert client.post(f"/api/tickets/{t['id']}/assign", json=body, headers=auth("ben")).status_code == 403
    assigned = client.post(f"/api/tickets/{t['id']}/assign", json=body, headers=auth("meera")).json()
    assert assigned["assignee"]["name"] == "Chitra" and assigned["status"] == "open"


# ------------------------------------------------------------- replies
def test_first_public_reply_sets_first_response_but_internal_note_does_not(client, auth, fake_clock):
    t = new_ticket(client, auth("asha"))
    claim(client, auth("asha"), t["id"])
    fake_clock.advance(minutes=10)
    r = reply(client, auth("asha"), t["id"], "thinking...", kind="internal_note")
    assert r.json()["first_response_at"] is None
    fake_clock.advance(minutes=20)
    r = reply(client, auth("asha"), t["id"], "Hi Cora")
    assert r.json()["first_response_at"].startswith("2026-11-23T05:00:00")  # 10:30 IST in UTC
    assert r.json()["sla"]["response"]["state"] == "met"


def test_blank_message_rejected(client, auth):
    t = new_ticket(client, auth("asha"))
    claim(client, auth("asha"), t["id"])
    assert reply(client, auth("asha"), t["id"], "   ").status_code == 422


def test_set_waiting_requires_a_public_reply(client, auth):
    t = new_ticket(client, auth("asha"))
    claim(client, auth("asha"), t["id"])
    r = reply(client, auth("asha"), t["id"], "note", kind="internal_note", set_waiting=True)
    assert r.status_code == 400


# ------------------------------------------------------------ the clock
def test_friday_6pm_ticket_is_not_late_on_sunday_morning(client, auth, fake_clock):
    fake_clock.set(ist(2026, 11, 20, 18, 0))  # Friday 6 PM
    t = new_ticket(client, auth("asha"), priority="urgent")
    fake_clock.set(ist(2026, 11, 22, 9, 0))  # Sunday morning
    got = client.get(f"/api/tickets/{t['id']}", headers=auth("asha")).json()
    assert got["late"] is False
    assert got["sla"]["response"]["due_at"].startswith("2026-11-23T05:30:00")  # Mon 11:00 IST
    # ... and it does become late once Monday's working time has run out
    fake_clock.set(ist(2026, 11, 23, 11, 1))
    assert client.get(f"/api/tickets/{t['id']}", headers=auth("asha")).json()["late"] is True


def test_waiting_for_customer_stops_the_clock_and_reply_resumes_it(client, auth, fake_clock):
    h = auth("asha")
    t = new_ticket(client, h, priority="medium")  # Mon 10:00
    claim(client, h, t["id"])
    fake_clock.advance(minutes=30)  # 10:30
    waiting = reply(client, h, t["id"], "Which browser?", set_waiting=True).json()
    assert waiting["status"] == "waiting_customer"
    assert waiting["sla"]["waiting_on_customer"] is True
    assert waiting["sla"]["resolution"]["state"] == "paused"

    fake_clock.set(ist(2026, 12, 4, 12, 0))  # nearly two weeks of silence
    still = client.get(f"/api/tickets/{t['id']}", headers=h).json()
    assert still["late"] is False
    assert still["sla"]["resolution"]["remaining_seconds"] == int(timedelta(hours=26, minutes=30).total_seconds())

    fake_clock.set(ist(2026, 12, 7, 10, 0))
    back = reply(client, h, t["id"], "Chrome, report 'Q3'.", kind="customer_message").json()
    assert back["status"] == "open"
    assert back["sla"]["waiting_on_customer"] is False
    # 26h30m left, resumed Monday 10:00 -> 8h30 + 9h + 9h => Wednesday 18:30
    assert back["sla"]["resolution"]["due_at"].startswith("2026-12-09T13:00:00")  # 18:30 IST


def test_priority_change_recomputes_from_creation(client, auth, fake_clock):
    h = auth("asha")
    t = new_ticket(client, h, priority="medium")  # Mon 10:00, reply due 14:30
    fake_clock.set(ist(2026, 11, 23, 13, 0))  # 3h in: fine for medium (4.5h)...
    assert client.get(f"/api/tickets/{t['id']}", headers=h).json()["late"] is False
    changed = client.post(f"/api/tickets/{t['id']}/priority", json={"priority": "urgent"}, headers=h).json()
    # ... but the urgent promise (2h) is measured from creation, so it is already missed
    assert changed["priority"] == "urgent"
    assert changed["late"] is True
    assert changed["sla"]["response"]["breached"] is True
    again = client.post(f"/api/tickets/{t['id']}/priority", json={"priority": "urgent"}, headers=h)
    assert again.status_code == 400


def test_holidays_do_not_count(client, auth, fake_clock):
    lead = auth("meera")
    assert client.post("/api/holidays", json={"day": "2026-11-24", "name": "Local festival"}, headers=lead).status_code == 201
    assert client.post("/api/holidays", json={"day": "2026-11-25", "name": "x"}, headers=auth("asha")).status_code == 403
    fake_clock.set(ist(2026, 11, 23, 18, 0))
    t = new_ticket(client, auth("asha"), priority="medium")
    fake_clock.set(ist(2026, 11, 24, 15, 0))  # Tuesday afternoon, a holiday
    got = client.get(f"/api/tickets/{t['id']}", headers=auth("asha")).json()
    assert got["late"] is False
    assert got["sla"]["response"]["due_at"].startswith("2026-11-25T")  # pushed to Wednesday
    assert client.delete("/api/holidays/2026-11-24", headers=lead).status_code == 204


# ------------------------------------------------- resolve / reopen / close
def test_cannot_resolve_without_replying(client, auth):
    h = auth("asha")
    t = new_ticket(client, h)
    claim(client, h, t["id"])
    r = client.post(f"/api/tickets/{t['id']}/resolve", json={}, headers=h)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "reply_required"
    ok = client.post(f"/api/tickets/{t['id']}/resolve", json={"message": "Fixed it."}, headers=h)
    assert ok.status_code == 200
    assert ok.json()["status"] == "resolved"
    assert ok.json()["first_response_at"] is not None


def test_reopen_within_a_working_week(client, auth, fake_clock):
    h = auth("asha")
    t = new_ticket(client, h)
    claim(client, h, t["id"])
    client.post(f"/api/tickets/{t['id']}/resolve", json={"message": "Done"}, headers=h)
    fake_clock.set(ist(2026, 11, 27, 9, 30))  # 4 working days later: still inside the window
    r = client.post(f"/api/tickets/{t['id']}/reopen", json={"message": "Still broken!"}, headers=auth("ben"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "open" and body["reopen_count"] == 1
    assert body["assignee"]["name"] == "Asha"
    assert body["messages"][-1]["body"] == "Still broken!"


def test_reopen_after_the_window_is_refused_and_ticket_closes(client, auth, factory, fake_clock):
    h = auth("asha")
    t = new_ticket(client, h)
    claim(client, h, t["id"])
    client.post(f"/api/tickets/{t['id']}/resolve", json={"message": "Done"}, headers=h)  # Mon 10:00
    limit = wt.add_working_time(ist(2026, 11, 23, 10, 0), timedelta(hours=45), set())
    fake_clock.set(limit)
    assert client.get(f"/api/tickets/{t['id']}", headers=h).json()["actions"]["can_reopen"] is True
    fake_clock.set(limit + timedelta(minutes=1))
    r = client.post(f"/api/tickets/{t['id']}/reopen", json={}, headers=h)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "reopen_window_expired"

    result = run_housekeeping(factory)
    assert result.auto_closed_resolved == 1
    got = client.get(f"/api/tickets/{t['id']}", headers=h).json()
    assert got["status"] == "closed" and got["closed_reason"] == "reopen_window_expired"
    # a closed ticket is final: the follow-up is a new ticket
    r = client.post(f"/api/tickets/{t['id']}/reopen", json={}, headers=h)
    assert r.json()["error"]["code"] == "closed_create_new"
    followup = new_ticket(client, h, related_ticket_id=t["id"])
    assert followup["related_reference"] == t["reference"]


def test_customer_silence_for_a_working_week_closes_the_ticket(client, auth, factory, fake_clock):
    h = auth("asha")
    t = new_ticket(client, h)
    claim(client, h, t["id"])
    reply(client, h, t["id"], "Any update?", set_waiting=True)  # Mon 10:00
    due = wt.add_working_time(ist(2026, 11, 23, 10, 0), timedelta(hours=45), set())
    fake_clock.set(due - timedelta(minutes=1))
    assert run_housekeeping(factory).auto_closed_waiting == 0
    fake_clock.set(due)
    assert run_housekeeping(factory).auto_closed_waiting == 1
    got = client.get(f"/api/tickets/{t['id']}", headers=h).json()
    assert got["status"] == "closed" and got["closed_reason"] == "customer_inactive"
    assert got["late"] is False
    # running it again changes nothing
    assert run_housekeeping(factory).auto_closed_waiting == 0
    actions = [e["action"] for e in client.get(f"/api/tickets/{t['id']}/audit", headers=h).json()]
    assert actions.count("ticket.auto_closed") == 1


def test_weekend_silence_does_not_count_towards_closing(client, auth, factory, fake_clock):
    h = auth("asha")
    fake_clock.set(ist(2026, 11, 20, 17, 0))  # Friday 5 PM
    t = new_ticket(client, h)
    claim(client, h, t["id"])
    reply(client, h, t["id"], "Question?", set_waiting=True)
    fake_clock.set(ist(2026, 11, 27, 9, 0))  # a full wall-clock week later, only 4d 9h30 of work
    assert run_housekeeping(factory).auto_closed_waiting == 0


# ------------------------------------------------------- breach logging
def test_sla_breach_is_logged_once_with_the_moment_it_happened(client, auth, factory, fake_clock):
    h = auth("asha")
    t = new_ticket(client, h, priority="urgent")  # Mon 10:00, reply due 12:00
    fake_clock.set(ist(2026, 11, 23, 15, 0))
    assert run_housekeeping(factory).breaches_logged == 1
    assert run_housekeeping(factory).breaches_logged == 0
    entries = client.get(f"/api/tickets/{t['id']}/audit", headers=h).json()
    breach = [e for e in entries if e["action"] == "sla.response_breached"]
    assert len(breach) == 1
    assert breach[0]["occurred_at"].startswith("2026-11-23T06:30:00")  # 12:00 IST
    assert breach[0]["actor_type"] == "system"
    # we noticed three hours after it happened, and the entry says so
    assert breach[0]["details"]["detected_at"].startswith("2026-11-23T09:30:00")  # 15:00 IST


# ------------------------------------------------------------- listing
def test_dashboard_views(client, auth, fake_clock):
    a, b = auth("asha"), auth("ben")
    late = new_ticket(client, a, priority="urgent", subject="late one")
    mine = new_ticket(client, a, priority="low", subject="mine")
    claim(client, a, mine["id"])
    waiting = new_ticket(client, a, priority="low", subject="waiting")
    claim(client, a, waiting["id"])
    reply(client, a, waiting["id"], "q?", set_waiting=True)
    fake_clock.set(ist(2026, 11, 23, 16, 0))

    counts = client.get("/api/tickets/counts", headers=a).json()
    assert counts == {"active": 3, "unassigned": 1, "late": 1, "waiting_on_customer": 1}

    mine_view = client.get("/api/tickets?scope=mine", headers=a).json()
    assert {i["subject"] for i in mine_view["items"]} == {"mine", "waiting"}
    assert client.get("/api/tickets?scope=mine", headers=b).json()["total"] == 0

    late_view = client.get("/api/tickets?view=late", headers=a).json()
    assert [i["subject"] for i in late_view["items"]] == ["late one"]
    waiting_view = client.get("/api/tickets?view=waiting", headers=a).json()
    assert [i["subject"] for i in waiting_view["items"]] == ["waiting"]
    assert client.get("/api/tickets?q=LATE", headers=a).json()["total"] == 1
    assert late["id"] == late_view["items"][0]["id"]
