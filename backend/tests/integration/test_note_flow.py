"""Full note -> suggestion -> clinician decision flow against real Postgres.

Proves the thing SQLite-backed unit tests can't: that a note really flows
end to end to a persisted, clinician-approved code in the system of record.
"""
from app import models
from app.main import app
from app.routers.notes import get_extraction_client

from .conftest import requires_postgres


def _override_extraction(fake_extraction_client, raw_candidates):
    app.dependency_overrides[get_extraction_client] = lambda: fake_extraction_client(raw_candidates)


@requires_postgres
def test_accept_persists_resolved_code_in_postgres(pg_client, pg_session, fake_extraction_client):
    _override_extraction(
        fake_extraction_client,
        [{"term": "Cough", "snomed_code": "49727002", "confidence": 0.75, "source_span": "cough"}],
    )
    try:
        note = pg_client.post(
            "/notes", json={"patient_ref": "p1", "clinician_id": "gp1", "raw_text": "Persistent cough."}
        ).json()
        suggestion_id = pg_client.get(f"/notes/{note['id']}/suggestions").json()[0]["id"]

        resp = pg_client.patch(f"/suggestions/{suggestion_id}", json={"action": "accept", "decided_by": "gp1"})
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_extraction_client, None)

    pg_session.expire_all()  # force a real reload from Postgres, not the ORM identity map
    persisted = db_lookup(pg_session, suggestion_id)
    assert persisted.status == "accepted"
    assert persisted.resolved_code == "49727002"


@requires_postgres
def test_reject_never_persists_resolved_code_in_postgres(pg_client, pg_session, fake_extraction_client):
    _override_extraction(
        fake_extraction_client,
        [{"term": "Cough", "snomed_code": "49727002", "confidence": 0.75, "source_span": "cough"}],
    )
    try:
        note = pg_client.post(
            "/notes", json={"patient_ref": "p1", "clinician_id": "gp1", "raw_text": "Persistent cough."}
        ).json()
        suggestion_id = pg_client.get(f"/notes/{note['id']}/suggestions").json()[0]["id"]

        resp = pg_client.patch(f"/suggestions/{suggestion_id}", json={"action": "reject", "decided_by": "gp1"})
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_extraction_client, None)

    pg_session.expire_all()
    persisted = db_lookup(pg_session, suggestion_id)
    assert persisted.status == "rejected"
    assert persisted.resolved_code is None


@requires_postgres
def test_pending_suggestion_has_no_resolved_code_until_decided(pg_client, pg_session, fake_extraction_client):
    _override_extraction(
        fake_extraction_client,
        [{"term": "Cough", "snomed_code": "49727002", "confidence": 0.75, "source_span": "cough"}],
    )
    try:
        note = pg_client.post(
            "/notes", json={"patient_ref": "p1", "clinician_id": "gp1", "raw_text": "Persistent cough."}
        ).json()
        suggestion_id = pg_client.get(f"/notes/{note['id']}/suggestions").json()[0]["id"]
    finally:
        app.dependency_overrides.pop(get_extraction_client, None)

    pg_session.expire_all()
    persisted = db_lookup(pg_session, suggestion_id)
    assert persisted.status == "pending"
    assert persisted.resolved_code is None


def db_lookup(session, suggestion_id):
    return session.query(models.SuggestedCode).filter(models.SuggestedCode.id == suggestion_id).first()
