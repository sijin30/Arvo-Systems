"""INC-0318: the record of what happened, when and by whom cannot be changed."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from conftest import new_ticket


def _busy_ticket(client, auth):
    a = auth("asha")
    t = new_ticket(client, a)
    client.post(f"/api/tickets/{t['id']}/claim", headers=a)
    client.post(f"/api/tickets/{t['id']}/messages", json={"kind": "public_reply", "body": "Hello"}, headers=a)
    return t, a


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_log SET actor_name = 'someone else'",
        "DELETE FROM audit_log",
        "TRUNCATE audit_log",
        "UPDATE messages SET body = 'rewritten'",
        "DELETE FROM messages",
        "TRUNCATE messages",
        "UPDATE messages SET created_at = created_at - interval '1 day'",
        "DELETE FROM tickets",
        "TRUNCATE tickets CASCADE",
        "UPDATE tickets SET created_at = created_at + interval '1 day'",
        "UPDATE tickets SET first_response_at = first_response_at + interval '1 day'",
    ],
)
def test_history_cannot_be_rewritten_even_with_raw_sql(client, auth, engine, statement):
    _busy_ticket(client, auth)
    with pytest.raises(DBAPIError) as err:
        with engine.begin() as conn:
            conn.execute(text(statement))
    assert any(w in str(err.value) for w in ("append-only", "cannot be"))


def test_a_pause_can_be_closed_once_and_not_rewritten(client, auth, engine):
    a = auth("asha")
    t = new_ticket(client, a)
    client.post(f"/api/tickets/{t['id']}/claim", headers=a)
    client.post(
        f"/api/tickets/{t['id']}/messages",
        json={"kind": "public_reply", "body": "Question?", "set_waiting": True},
        headers=a,
    )
    client.post(f"/api/tickets/{t['id']}/messages", json={"kind": "customer_message", "body": "Answer"}, headers=a)
    with pytest.raises(DBAPIError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE sla_pauses SET started_at = started_at + interval '2 days'"))
    with pytest.raises(DBAPIError):  # already closed, cannot be re-opened or changed
        with engine.begin() as conn:
            conn.execute(text("UPDATE sla_pauses SET ended_at = NULL"))
    with pytest.raises(DBAPIError):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM sla_pauses"))


def test_audit_log_records_who_what_and_when(client, auth):
    t, a = _busy_ticket(client, auth)
    entries = client.get(f"/api/tickets/{t['id']}/audit", headers=a).json()
    assert [e["action"] for e in entries] == [
        "ticket.created",
        "ticket.claimed",
        "message.public_reply",
    ]
    assert all(e["actor_name"] == "Asha" for e in entries)
    assert [e["seq"] for e in entries] == sorted(e["seq"] for e in entries)
    assert entries[2]["details"]["first_response"] is True
    for e in entries:
        assert e["recorded_at"] and e["occurred_at"]


def test_audit_chain_verifies_and_detects_tampering(client, auth, engine):
    _busy_ticket(client, auth)
    a = auth("asha")
    lead = auth("meera")
    ok = client.get("/api/audit/verify", headers=lead).json()
    assert ok["intact"] is True and ok["entries_checked"] >= 3
    assert client.get("/api/audit/verify", headers=a).status_code == 403

    # Someone with full database rights switches the guard off and edits history...
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_append_only"))
        conn.execute(text("UPDATE audit_log SET actor_name = 'Mallory' WHERE seq = 2"))
        conn.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_append_only"))
    # ... and the hash chain shows exactly where the record no longer matches.
    bad = client.get("/api/audit/verify", headers=lead).json()
    assert bad["intact"] is False and bad["first_broken_seq"] == 2


def test_concurrent_audit_writes_keep_a_single_unbroken_chain(factory, agents, engine):
    import threading

    from app import audit, clock
    from app.models import Agent

    def writer(n):
        with factory() as s:
            agent = s.get(Agent, agents["asha"])
            for i in range(5):
                audit.record(s, audit.agent_actor(agent), "test.event", clock.now(), details={"n": n, "i": i})
                s.commit()

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT audit_verify()")).scalar() is None
        assert conn.execute(text("SELECT count(*) FROM audit_log")).scalar() == 30
        assert conn.execute(text("SELECT max(seq) FROM audit_log")).scalar() == 30


def test_database_rejects_inconsistent_rows(client, auth, engine):
    t, _ = _busy_ticket(client, auth)
    with pytest.raises(DBAPIError):  # an internal note cannot be marked public
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO messages (ticket_id, kind, visibility, author_type, body, created_at) "
                    f"VALUES ({t['id']}, 'internal_note', 'public', 'agent', 'x', now())"
                )
            )
    with pytest.raises(DBAPIError):  # a working ticket must have an owner
        with engine.begin() as conn:
            conn.execute(text(f"UPDATE tickets SET assignee_id = NULL WHERE id = {t['id']}"))
