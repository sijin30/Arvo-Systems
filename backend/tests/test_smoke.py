from conftest import new_ticket


def test_boot_and_create_ticket(client, auth):
    a = auth("asha")
    t = new_ticket(client, a)
    assert t["reference"].startswith("FD-")
    assert t["status"] == "new"
    assert t["messages"][0]["kind"] == "customer_message"
    r = client.get("/api/health")
    assert r.json() == {"status": "ok"}
