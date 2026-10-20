from fastapi.testclient import TestClient

from nuru.app import create_app
from nuru.red_flags import FIXED_MESSAGES
from nuru.sms import DryRunSender


def make_client(router, settings, token=""):
    settings.webhook_token = token
    sender = DryRunSender()
    app = create_app(router=router, sender=sender, settings=settings)
    return TestClient(app), sender


def at_form(text, phone="+255712345678", **extra):
    form = {
        "from": phone,
        "to": "15xxx",
        "text": text,
        "date": "2026-10-20 10:00:00",
        "id": "ATXid_test",
        "linkId": "SampleLinkId123",
    }
    form.update(extra)
    return form


def test_health(router, settings):
    client, _ = make_client(router, settings)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "none"
    assert body["content_entries"] >= 15
    assert body["sample_facility_data"] is True
    assert "key" not in str(body).lower()


def test_incoming_sms_answer(router, settings):
    client, sender = make_client(router, settings)
    resp = client.post("/sms/incoming", data=at_form("kondomu inazuia ukimwi"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert len(sender.outbox) == 1
    to, text = sender.outbox[0]
    assert to == "+255712345678"
    assert "Kondomu" in text
    assert len(text) <= 306


def test_incoming_sms_red_flag(router, settings):
    client, sender = make_client(router, settings)
    client.post("/sms/incoming", data=at_form("nina mimba natoka damu"))
    assert sender.outbox[0][1] == FIXED_MESSAGES["URGENT_MATERNAL"].sw


def test_incoming_sms_facility(router, settings):
    client, sender = make_client(router, settings)
    client.post("/sms/incoming", data=at_form("KITUO Makole"))
    assert "Makole" in sender.outbox[0][1]


def test_incoming_sms_missing_from_is_rejected(router, settings):
    client, _ = make_client(router, settings)
    resp = client.post("/sms/incoming", data={"text": "habari"})
    assert resp.status_code == 422


def test_incoming_sms_empty_text_gets_menu(router, settings):
    client, sender = make_client(router, settings)
    client.post("/sms/incoming", data=at_form(""))
    assert "NURU" in sender.outbox[0][1]


def test_webhook_token(router, settings):
    client, sender = make_client(router, settings, token="s3cret")
    assert client.post("/sms/incoming", data=at_form("habari")).status_code == 403
    assert client.post("/sms/incoming?token=s3cret", data=at_form("habari")).status_code == 200
    assert len(sender.outbox) == 1


def test_rapidpro_webhook(router, settings):
    client, _ = make_client(router, settings)
    payload = {
        "contact": {"uuid": "c-123", "name": ""},
        "input": {"text": "maziwa ya kwanza ni machafu", "urn": "tel:+255712345678"},
    }
    resp = client.post("/rapidpro/webhook", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "answer"
    assert body["reply"].startswith("Si kweli")
    assert body["segments"] <= 2


def test_rapidpro_webhook_red_flag(router, settings):
    client, _ = make_client(router, settings)
    resp = client.post("/rapidpro/webhook", json={"urn": "tel:+255700", "text": "mtoto hanyonyi"})
    assert resp.json()["category"] == "red_flag"
    assert resp.json()["rule_id"] == "child_cannot_feed"
