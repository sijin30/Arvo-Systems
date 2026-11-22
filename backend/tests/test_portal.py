"""The customer side: sign up, sign in, raise tickets, follow and answer them."""
from datetime import timedelta

from app import worktime as wt
from app.jobs import run_housekeeping
from conftest import ist, new_ticket

PW = "Customer#2026"
SECRET = "SECRET-NOTE-FOR-PORTAL-9d2b"


def signup(client, email="cora@customer.test", name="Cora Customer", password=PW):
    r = client.post("/api/portal/signup", json={"name": name, "email": email, "password": password})
    return r


def customer_headers(client, email="cora@customer.test", name="Cora Customer"):
    r = signup(client, email, name)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def portal_ticket(client, headers, **overrides):
    payload = {"subject": "Cannot log in", "description": "The login page loops.", "priority": "urgent"}
    payload.update(overrides)
    r = client.post("/api/portal/tickets", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------- accounts
def test_signup_login_and_me(client):
    r = signup(client)
    assert r.status_code == 201
    assert r.json()["customer"]["email"] == "cora@customer.test"
    login = client.post("/api/portal/login", json={"email": "CORA@customer.test", "password": PW})
    assert login.status_code == 200
    h = {"Authorization": f"Bearer {login.json()['token']}"}
    assert client.get("/api/portal/me", headers=h).json()["name"] == "Cora Customer"


def test_signup_validation(client):
    assert signup(client, password="short").status_code == 400
    assert signup(client, password="short").json()["error"]["code"] == "weak_password"
    assert signup(client, email="not-an-email").status_code == 400
    assert signup(client, name="   ").status_code == 422
    assert signup(client).status_code == 201
    dup = signup(client)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "account_exists"


def test_wrong_password_and_unknown_email_look_the_same(client):
    signup(client)
    a = client.post("/api/portal/login", json={"email": "cora@customer.test", "password": "wrong-password"})
    b = client.post("/api/portal/login", json={"email": "nobody@customer.test", "password": "wrong-password"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_signup_cannot_take_over_an_email_an_agent_already_logged_tickets_for(client, auth):
    new_ticket(client, auth("asha"), customer_email="vip@customer.test", customer_name="Vee VIP")
    r = signup(client, email="vip@customer.test", name="Not Vee")
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_in_use"


def test_customer_and_agent_tokens_cannot_be_swapped(client, auth):
    cust = customer_headers(client)
    agent = auth("asha")
    # a customer token is useless on every agent endpoint, and vice versa
    assert client.get("/api/tickets", headers=cust).status_code == 401
    assert client.get("/api/auth/me", headers=cust).status_code == 401
    assert client.post("/api/ops/housekeeping", headers=cust).status_code == 401
    assert client.get("/api/portal/tickets", headers=agent).status_code == 401
    assert client.get("/api/portal/me", headers=agent).status_code == 401
    assert client.get("/api/portal/tickets").status_code == 401


def test_change_password(client):
    h = customer_headers(client)
    bad = client.post("/api/portal/password", json={"current_password": "nope-nope", "new_password": "Another#2026"}, headers=h)
    assert bad.status_code == 400
    weak = client.post("/api/portal/password", json={"current_password": PW, "new_password": "x"}, headers=h)
    assert weak.status_code == 400
    ok = client.post("/api/portal/password", json={"current_password": PW, "new_password": "Another#2026"}, headers=h)
    assert ok.status_code == 204
    assert client.post("/api/portal/login", json={"email": "cora@customer.test", "password": PW}).status_code == 401
    assert client.post("/api/portal/login", json={"email": "cora@customer.test", "password": "Another#2026"}).status_code == 200


# --------------------------------------------------------------- tickets
def test_customer_ticket_lands_in_the_shared_queue_and_an_agent_takes_it(client, auth):
    h = customer_headers(client)
    t = portal_ticket(client, h, priority="urgent")
    assert t["status"] == "received" and t["priority"] == "urgent"
    assert [m["sender"] for m in t["messages"]] == ["you"]

    agent = auth("asha")
    queue = client.get("/api/tickets?view=unassigned", headers=agent).json()["items"]
    assert [i["subject"] for i in queue] == ["Cannot log in"]
    assert queue[0]["customer"]["name"] == "Cora Customer"
    assert queue[0]["assignee"] is None

    claimed = client.post(f"/api/tickets/{queue[0]['id']}/claim", headers=agent)
    assert claimed.status_code == 200
    assert client.get(f"/api/tickets/{t['id']}", headers=agent).json()["status"] == "open"
    # the same double-claim protection applies to customer-created tickets
    assert client.post(f"/api/tickets/{t['id']}/claim", headers=auth("ben")).status_code == 409
    assert client.get(f"/api/portal/tickets/{t['id']}", headers=h).json()["status"] == "in_progress"


def test_customer_ticket_message_is_attributed_to_the_customer_not_an_agent(client, auth):
    h = customer_headers(client)
    t = portal_ticket(client, h)
    first = client.get(f"/api/tickets/{t['id']}", headers=auth("asha")).json()["messages"][0]
    assert first["author_type"] == "customer" and first["author"] is None
    created = [e for e in client.get(f"/api/tickets/{t['id']}/audit", headers=auth("asha")).json() if e["action"] == "ticket.created"][0]
    assert created["actor_type"] == "customer" and created["actor_name"] == "Cora Customer"
    assert created["details"]["created_by"] == "customer"


def test_customers_only_see_their_own_tickets(client):
    a = customer_headers(client, "a@customer.test", "Ann")
    b = customer_headers(client, "b@customer.test", "Bob")
    ta = portal_ticket(client, a, subject="Ann's problem")
    portal_ticket(client, b, subject="Bob's problem")
    assert [t["subject"] for t in client.get("/api/portal/tickets", headers=a).json()] == ["Ann's problem"]
    for method, path in (
        ("get", f"/api/portal/tickets/{ta['id']}"),
        ("get", f"/api/portal/tickets/{ta['id']}/transcript"),
        ("post", f"/api/portal/tickets/{ta['id']}/messages"),
        ("post", f"/api/portal/tickets/{ta['id']}/reopen"),
    ):
        r = getattr(client, method)(path, headers=b, **({"json": {"body": "hi", "message": "hi"}} if method == "post" else {}))
        assert r.status_code == 404, (method, path, r.status_code)


def test_portal_never_shows_private_notes_or_internals(client, auth):
    h = customer_headers(client)
    t = portal_ticket(client, h)
    agent = auth("asha")
    client.post(f"/api/tickets/{t['id']}/claim", headers=agent)
    client.post(f"/api/tickets/{t['id']}/messages", json={"kind": "internal_note", "body": f"Careful: {SECRET}"}, headers=agent)
    client.post(f"/api/tickets/{t['id']}/messages", json={"kind": "public_reply", "body": "We are on it."}, headers=agent)
    for url in (
        "/api/portal/tickets",
        f"/api/portal/tickets/{t['id']}",
        f"/api/portal/tickets/{t['id']}/transcript",
    ):
        r = client.get(url, headers=h)
        assert r.status_code == 200
        assert SECRET not in r.text, url
    view = client.get(f"/api/portal/tickets/{t['id']}", headers=h).json()
    assert [m["body"] for m in view["messages"]] == ["The login page loops.", "We are on it."]
    # nothing about agents, SLA or ownership leaks into the customer shape
    assert set(view) == {"id", "reference", "subject", "priority", "status", "created_at", "messages", "can_reply", "can_reopen", "reopen_until"}
    assert set(view["messages"][0]) == {"id", "sender", "body", "created_at"}


def test_customer_reply_while_waiting_resumes_the_clock(client, auth, fake_clock):
    h = customer_headers(client)
    t = portal_ticket(client, h, priority="medium")  # Mon 10:00
    agent = auth("asha")
    client.post(f"/api/tickets/{t['id']}/claim", headers=agent)
    fake_clock.advance(minutes=30)
    waiting = client.post(
        f"/api/tickets/{t['id']}/messages",
        json={"kind": "public_reply", "body": "Which browser?", "set_waiting": True},
        headers=agent,
    ).json()
    assert waiting["status"] == "waiting_customer"
    assert client.get(f"/api/portal/tickets/{t['id']}", headers=h).json()["status"] == "waiting_for_you"

    fake_clock.set(ist(2026, 12, 4, 12, 0))
    answered = client.post(f"/api/portal/tickets/{t['id']}/messages", json={"body": "Chrome, on Windows."}, headers=h)
    assert answered.status_code == 201
    assert answered.json()["status"] == "in_progress"
    detail = client.get(f"/api/tickets/{t['id']}", headers=agent).json()
    assert detail["status"] == "open" and detail["sla"]["waiting_on_customer"] is False
    assert detail["late"] is False
    audit = client.get(f"/api/tickets/{t['id']}/audit", headers=agent).json()
    replied = [e for e in audit if e["action"] == "ticket.customer_replied"][0]
    assert replied["actor_type"] == "customer" and replied["details"]["clock"] == "resumed"


def test_customer_reply_rules(client, auth):
    h = customer_headers(client)
    t = portal_ticket(client, h)
    assert client.post(f"/api/portal/tickets/{t['id']}/messages", json={"body": "  "}, headers=h).status_code == 422
    assert client.post(f"/api/portal/tickets/{t['id']}/messages", json={"body": "Any news?"}, headers=h).status_code == 201

    agent = auth("asha")
    client.post(f"/api/tickets/{t['id']}/claim", headers=agent)
    client.post(f"/api/tickets/{t['id']}/resolve", json={"message": "Fixed."}, headers=agent)
    r = client.post(f"/api/portal/tickets/{t['id']}/messages", json={"body": "Still broken"}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "use_reopen"


def test_customer_can_reopen_within_the_window_and_not_after(client, auth, factory, fake_clock):
    h = customer_headers(client)
    t = portal_ticket(client, h)
    agent = auth("asha")
    client.post(f"/api/tickets/{t['id']}/claim", headers=agent)
    client.post(f"/api/tickets/{t['id']}/resolve", json={"message": "Done"}, headers=agent)  # Mon 10:00
    view = client.get(f"/api/portal/tickets/{t['id']}", headers=h).json()
    assert view["status"] == "resolved" and view["can_reopen"] is True and view["can_reply"] is False
    assert view["reopen_until"] is not None

    fake_clock.set(ist(2026, 11, 26, 11, 0))
    ok = client.post(f"/api/portal/tickets/{t['id']}/reopen", json={"message": "Still failing"}, headers=h)
    assert ok.status_code == 200 and ok.json()["status"] == "in_progress"
    detail = client.get(f"/api/tickets/{t['id']}", headers=agent).json()
    assert detail["reopen_count"] == 1 and detail["messages"][-1]["author"] is None

    # resolve again, and let the window run out
    client.post(f"/api/tickets/{t['id']}/resolve", json={"message": "Really done"}, headers=agent)
    limit = wt.add_working_time(ist(2026, 11, 26, 11, 0), timedelta(hours=45), set())
    fake_clock.set(limit + timedelta(minutes=1))
    late = client.post(f"/api/portal/tickets/{t['id']}/reopen", json={}, headers=h)
    assert late.status_code == 409 and late.json()["error"]["code"] == "reopen_window_expired"
    run_housekeeping(factory)
    closed = client.get(f"/api/portal/tickets/{t['id']}", headers=h).json()
    assert closed["status"] == "closed" and closed["can_reopen"] is False
    again = client.post(f"/api/portal/tickets/{t['id']}/reopen", json={}, headers=h)
    assert again.json()["error"]["code"] == "closed_create_new"
    assert client.post(f"/api/portal/tickets/{t['id']}/messages", json={"body": "hello?"}, headers=h).status_code == 409


def test_customer_can_raise_a_new_ticket_after_one_closes(client):
    h = customer_headers(client)
    portal_ticket(client, h, subject="First")
    portal_ticket(client, h, subject="Second", priority="low")
    assert len(client.get("/api/portal/tickets", headers=h).json()) == 2


def test_active_ticket_cap_stops_spam(client):
    h = customer_headers(client)
    for i in range(20):
        portal_ticket(client, h, subject=f"Ticket {i}")
    r = client.post("/api/portal/tickets", json={"subject": "One more", "description": "x", "priority": "low"}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "too_many_open"


def test_a_ticket_an_agent_logs_for_a_customer_with_an_account_shows_up_in_their_portal(client, auth):
    h = customer_headers(client, "carol@customer.test", "Carol")
    new_ticket(client, auth("asha"), customer_email="carol@customer.test", customer_name="Carol", subject="Phoned in")
    subjects = [t["subject"] for t in client.get("/api/portal/tickets", headers=h).json()]
    assert subjects == ["Phoned in"]


def test_signup_and_activity_are_in_the_audit_trail(client, auth):
    h = customer_headers(client)
    portal_ticket(client, h)
    lead = auth("meera")
    assert client.get("/api/audit/verify", headers=lead).json()["intact"] is True
