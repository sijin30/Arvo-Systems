"""The lead creates and manages agents."""
from sqlalchemy import text

from app.db import init_db
from conftest import PASSWORD, new_ticket

NEW_PW = "Welcome#2026"


def add_agent(client, headers, **overrides):
    body = {"name": "Dev Kumar", "email": "dev@arvo.test", "password": NEW_PW, "role": "agent"}
    body.update(overrides)
    return client.post("/api/admin/agents", json=body, headers=headers)


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_lead_creates_an_agent_who_can_log_in_and_work(client, auth):
    lead = auth("meera")
    r = add_agent(client, lead)
    assert r.status_code == 201
    assert r.json()["email"] == "dev@arvo.test" and r.json()["is_active"] is True
    token = login(client, "DEV@arvo.test", NEW_PW)
    assert token.status_code == 200
    h = {"Authorization": f"Bearer {token.json()['token']}"}
    t = new_ticket(client, h)
    assert client.post(f"/api/tickets/{t['id']}/claim", headers=h).status_code == 200
    assert "Dev Kumar" in [a["name"] for a in client.get("/api/agents", headers=lead).json()]


def test_only_a_lead_can_manage_agents(client, auth):
    agent = auth("asha")
    assert client.get("/api/admin/agents", headers=agent).status_code == 403
    assert add_agent(client, agent).status_code == 403
    assert client.post("/api/admin/agents/1/deactivate", headers=agent).status_code == 403
    assert client.post("/api/admin/agents/1/password", json={"password": NEW_PW}, headers=agent).status_code == 403
    assert client.get("/api/admin/agents").status_code == 401


def test_create_agent_validation(client, auth):
    lead = auth("meera")
    assert add_agent(client, lead, password="short").json()["error"]["code"] == "weak_password"
    assert add_agent(client, lead, email="nope").json()["error"]["code"] == "bad_email"
    assert add_agent(client, lead, role="boss").status_code == 422
    assert add_agent(client, lead).status_code == 201
    dup = add_agent(client, lead, email="DEV@arvo.test")
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "email_in_use"
    assert add_agent(client, lead, name="   ", email="x@arvo.test").status_code == 422


def test_admin_list_shows_status_and_workload(client, auth, agents):
    lead = auth("meera")
    t = new_ticket(client, auth("asha"))
    client.post(f"/api/tickets/{t['id']}/claim", headers=auth("asha"))
    rows = {r["email"]: r for r in client.get("/api/admin/agents", headers=lead).json()}
    assert rows["asha@arvo.test"]["active_tickets"] == 1
    assert rows["ben@arvo.test"]["active_tickets"] == 0
    assert rows["meera@arvo.test"]["role"] == "lead"


def test_deactivated_agent_cannot_log_in_and_existing_session_stops_working(client, auth, agents):
    lead = auth("meera")
    ben = auth("ben")
    assert client.get("/api/tickets", headers=ben).status_code == 200
    off = client.post(f"/api/admin/agents/{agents['ben']}/deactivate", headers=lead)
    assert off.status_code == 200 and off.json()["is_active"] is False
    assert client.get("/api/tickets", headers=ben).status_code == 401
    assert login(client, "ben@arvo.test", PASSWORD).status_code == 401
    assert "Ben" not in [a["name"] for a in client.get("/api/agents", headers=lead).json()]
    on = client.post(f"/api/admin/agents/{agents['ben']}/activate", headers=lead)
    assert on.json()["is_active"] is True
    assert login(client, "ben@arvo.test", PASSWORD).status_code == 200


def test_cannot_deactivate_self_the_last_lead_or_an_agent_with_active_tickets(client, auth, agents):
    lead = auth("meera")
    me = client.post(f"/api/admin/agents/{agents['meera']}/deactivate", headers=lead)
    assert me.status_code == 400 and me.json()["error"]["code"] == "cannot_deactivate_self"

    t = new_ticket(client, auth("asha"))
    client.post(f"/api/tickets/{t['id']}/claim", headers=auth("asha"))
    busy = client.post(f"/api/admin/agents/{agents['asha']}/deactivate", headers=lead)
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "has_active_tickets"
    assert busy.json()["error"]["active_tickets"] == 1
    # reassign, then it works
    client.post(f"/api/tickets/{t['id']}/assign", json={"agent_id": agents["ben"]}, headers=lead)
    assert client.post(f"/api/admin/agents/{agents['asha']}/deactivate", headers=lead).status_code == 200

    # a second lead exists, so the first may be deactivated by the second, but never the last
    second = add_agent(client, lead, email="lead2@arvo.test", name="Second Lead", role="lead").json()
    h2 = {"Authorization": "Bearer " + login(client, "lead2@arvo.test", NEW_PW).json()["token"]}
    assert client.post(f"/api/admin/agents/{agents['meera']}/deactivate", headers=h2).status_code == 200
    last = client.post(f"/api/admin/agents/{second['id']}/deactivate", headers=h2)
    assert last.status_code == 400  # that is the caller's own account
    third = add_agent(client, h2, email="agent3@arvo.test", name="Plain Agent").json()
    h3 = {"Authorization": "Bearer " + login(client, "agent3@arvo.test", NEW_PW).json()["token"]}
    assert client.post(f"/api/admin/agents/{second['id']}/deactivate", headers=h3).status_code == 403
    assert third["role"] == "agent"


def test_reset_password(client, auth, agents):
    lead = auth("meera")
    assert client.post(f"/api/admin/agents/{agents['ben']}/password", json={"password": "short"}, headers=lead).status_code == 400
    ok = client.post(f"/api/admin/agents/{agents['ben']}/password", json={"password": NEW_PW}, headers=lead)
    assert ok.status_code == 204
    assert login(client, "ben@arvo.test", PASSWORD).status_code == 401
    assert login(client, "ben@arvo.test", NEW_PW).status_code == 200
    assert client.post("/api/admin/agents/9999/password", json={"password": NEW_PW}, headers=lead).status_code == 404


def test_agent_changes_own_password(client, auth):
    h = auth("chitra")
    assert client.post("/api/auth/password", json={"current_password": "wrong-one", "new_password": NEW_PW}, headers=h).status_code == 400
    assert client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": NEW_PW}, headers=h).status_code == 204
    assert login(client, "chitra@arvo.test", NEW_PW).status_code == 200
    assert login(client, "chitra@arvo.test", PASSWORD).status_code == 401


def test_admin_actions_are_in_the_permanent_record(client, auth, agents, engine):
    lead = auth("meera")
    add_agent(client, lead)
    client.post(f"/api/admin/agents/{agents['ben']}/deactivate", headers=lead)
    client.post(f"/api/admin/agents/{agents['ben']}/password", json={"password": NEW_PW}, headers=lead)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT action, actor_name, ticket_id, details::text FROM audit_log WHERE action LIKE 'agent.%' ORDER BY seq")
        ).all()
    assert [r[0] for r in rows] == ["agent.created", "agent.deactivated", "agent.password_reset"]
    assert all(r[1] == "Meera" and r[2] is None for r in rows)
    assert all(NEW_PW not in r[3] for r in rows)  # passwords are never written to the record
    assert client.get("/api/audit/verify", headers=lead).json()["intact"] is True


def test_startup_migration_upgrades_an_older_database(client, engine):
    """A database created before customers had accounts gains what it needs."""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE customers DROP COLUMN password_hash"))
        conn.execute(text("ALTER TABLE audit_log DROP CONSTRAINT audit_actor_type_ck"))
        conn.execute(text("ALTER TABLE audit_log ADD CONSTRAINT audit_actor_type_ck CHECK (actor_type IN ('agent', 'system'))"))
    init_db(engine)
    init_db(engine)  # and it is safe to run again
    with engine.begin() as conn:
        conn.execute(text("SELECT password_hash FROM customers LIMIT 1"))
        conn.execute(
            text(
                "INSERT INTO audit_log (actor_type, actor_name, action, details, occurred_at) "
                "VALUES ('customer', 'Someone', 'test', '{}', now())"
            )
        )
