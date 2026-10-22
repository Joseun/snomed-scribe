from app.main import app
from app.routers.notes import get_extraction_client


def _override_extraction(client, raw_candidates):
    def _get():
        return client(raw_candidates)

    app.dependency_overrides[get_extraction_client] = _get


def test_create_note_returns_suggestions(client, fake_extraction_client):
    _override_extraction(
        fake_extraction_client,
        [{"term": "Cough", "snomed_code": "49727002", "confidence": 0.75, "source_span": "cough"}],
    )
    resp = client.post(
        "/notes",
        json={"patient_ref": "p1", "clinician_id": "gp1", "raw_text": "Patient has a persistent cough."},
    )
    assert resp.status_code == 200
    note_id = resp.json()["id"]

    suggestions = client.get(f"/notes/{note_id}/suggestions").json()
    assert len(suggestions) == 1
    assert suggestions[0]["status"] == "pending"
    assert suggestions[0]["resolved_code"] is None


def test_accept_persists_resolved_code(client, fake_extraction_client):
    _override_extraction(
        fake_extraction_client,
        [{"term": "Cough", "snomed_code": "49727002", "confidence": 0.75, "source_span": "cough"}],
    )
    note = client.post(
        "/notes", json={"patient_ref": "p1", "clinician_id": "gp1", "raw_text": "Persistent cough."}
    ).json()
    suggestion_id = client.get(f"/notes/{note['id']}/suggestions").json()[0]["id"]

    resp = client.patch(f"/suggestions/{suggestion_id}", json={"action": "accept", "decided_by": "gp1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["resolved_code"] == "49727002"


def test_reject_never_sets_resolved_code(client, fake_extraction_client):
    _override_extraction(
        fake_extraction_client,
        [{"term": "Cough", "snomed_code": "49727002", "confidence": 0.75, "source_span": "cough"}],
    )
    note = client.post(
        "/notes", json={"patient_ref": "p1", "clinician_id": "gp1", "raw_text": "Persistent cough."}
    ).json()
    suggestion_id = client.get(f"/notes/{note['id']}/suggestions").json()[0]["id"]

    resp = client.patch(f"/suggestions/{suggestion_id}", json={"action": "reject", "decided_by": "gp1"})
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["resolved_code"] is None
