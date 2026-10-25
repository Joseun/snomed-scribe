from app import models
from app.main import app
from app.routers.notes import get_extraction_client


def _override_extraction(client, raw_candidates):
    def _get():
        return client(raw_candidates)

    app.dependency_overrides[get_extraction_client] = _get


def test_preview_returns_candidates_without_persisting(client, db_session, fake_extraction_client):
    _override_extraction(
        fake_extraction_client,
        [{"term": "Cough", "snomed_code": "49727002", "confidence": 0.75, "source_span": "cough"}],
    )

    resp = client.post("/notes/preview", json={"raw_text": "Patient has a persistent cough."})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["snomed_code"] == "49727002"
    assert body[0]["term"] == "Cough"

    assert db_session.query(models.ConsultationNote).count() == 0
    assert db_session.query(models.SuggestedCode).count() == 0


def test_preview_drops_negated_candidate(client, fake_extraction_client):
    _override_extraction(
        fake_extraction_client,
        [{"term": "Chest pain", "snomed_code": "29857009", "confidence": 0.8, "source_span": "chest pain"}],
    )

    resp = client.post("/notes/preview", json={"raw_text": "Patient denies chest pain."})
    assert resp.status_code == 200
    assert resp.json() == []


def test_preview_shows_out_of_subset_candidate_with_no_code(client, fake_extraction_client):
    _override_extraction(
        fake_extraction_client,
        [{"term": "Chest xray", "snomed_code": "99999999", "confidence": 0.7, "source_span": "chest xray"}],
    )

    resp = client.post("/notes/preview", json={"raw_text": "Sent for chest xray."})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["snomed_code"] is None
    assert body[0]["term"] == "Chest xray"


def test_preview_shows_null_code_candidate_as_no_code(client, fake_extraction_client):
    _override_extraction(
        fake_extraction_client,
        [{"term": "Losing weight", "snomed_code": None, "confidence": 0.6, "source_span": "losing weight"}],
    )

    resp = client.post("/notes/preview", json={"raw_text": "He is losing weight."})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["snomed_code"] is None
