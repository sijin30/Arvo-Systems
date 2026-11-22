"""INC-0304: internal notes must never reach a customer - not on a screen, in an API
response, in an export or in a list."""
import json

from sqlalchemy import text

from conftest import new_ticket

SECRET = "SECRET-HANDLING-ADVICE-7f3a"


def _ticket_with_secret(client, auth):
    a = auth("asha")
    t = new_ticket(client, a, subject="Angry customer", description="Where is my refund?")
    client.post(f"/api/tickets/{t['id']}/claim", headers=a)
    r = client.post(
        f"/api/tickets/{t['id']}/messages",
        json={"kind": "internal_note", "body": f"Careful, {SECRET}"},
        headers=a,
    )
    assert r.status_code == 201
    r = client.post(
        f"/api/tickets/{t['id']}/messages",
        json={"kind": "public_reply", "body": "We are on it."},
        headers=a,
    )
    assert r.status_code == 201
    return t, a


def test_agent_screen_marks_notes_internal(client, auth):
    t, a = _ticket_with_secret(client, auth)
    detail = client.get(f"/api/tickets/{t['id']}", headers=a).json()
    notes = [m for m in detail["messages"] if m["kind"] == "internal_note"]
    assert len(notes) == 1 and notes[0]["visibility"] == "internal"
    assert SECRET in notes[0]["body"]


def test_customer_view_never_contains_the_note(client, auth):
    t, a = _ticket_with_secret(client, auth)
    r = client.get(f"/api/public/tickets/{t['public_token']}")  # no login at all
    assert r.status_code == 200
    assert SECRET not in r.text
    view = r.json()
    assert [m["body"] for m in view["messages"]] == ["Where is my refund?", "We are on it."]
    assert [m["sender"] for m in view["messages"]] == ["you", "support"]
    # the customer shape has no field that could carry visibility or author identity
    assert set(view["messages"][0]) == {"id", "sender", "body", "created_at"}
    assert r.headers["cache-control"] == "no-store"


def test_exports_never_contain_the_note(client, auth):
    t, a = _ticket_with_secret(client, auth)
    for url in (
        f"/api/tickets/{t['id']}/transcript",
        f"/api/public/tickets/{t['public_token']}/transcript",
        "/api/tickets/export.csv",
        "/api/tickets/export.csv?view=history",
    ):
        r = client.get(url, headers=a)
        assert r.status_code == 200, url
        assert SECRET not in r.text, url
    assert "We are on it." in client.get(f"/api/tickets/{t['id']}/transcript", headers=a).text


def test_lists_counts_and_audit_never_contain_the_note(client, auth):
    t, a = _ticket_with_secret(client, auth)
    for url in (
        "/api/tickets",
        "/api/tickets?scope=mine",
        "/api/tickets?view=history",
        "/api/tickets?q=Careful",
        "/api/tickets/counts",
        f"/api/tickets/{t['id']}/audit",
    ):
        r = client.get(url, headers=a)
        assert r.status_code == 200, url
        assert SECRET not in r.text, url
    # searching for text that only exists inside a note finds nothing
    assert client.get("/api/tickets?q=Careful", headers=a).json()["total"] == 0


def test_database_view_for_customers_has_no_internal_rows(client, auth, engine):
    _ticket_with_secret(client, auth)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT body FROM customer_messages")).scalars().all()
    assert SECRET not in json.dumps(rows)
    assert len(rows) == 2


def test_customer_endpoint_rejects_unknown_token(client):
    assert client.get("/api/public/tickets/not-a-real-token").status_code == 404


def test_csv_export_neutralises_formula_cells(client, auth):
    a = auth("asha")
    new_ticket(client, a, subject='=HYPERLINK("http://evil")')
    csv_text = client.get("/api/tickets/export.csv", headers=a).text
    assert "'=HYPERLINK" in csv_text
