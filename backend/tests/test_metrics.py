from datetime import datetime, timezone

import httpx
import pytest

from app import metrics, models


def _seed_rejected_suggestions(db_session, count: int, note_id: str = "note-1"):
    db_session.add(models.ConsultationNote(id=note_id, patient_ref="p1", clinician_id="gp1", raw_text="note"))
    for i in range(count):
        db_session.add(
            models.SuggestedCode(
                id=f"s{i}",
                note_id=note_id,
                snomed_code="49727002",
                term="Cough",
                confidence=0.5,
                status="rejected",
                resolved_code=None,
                decided_at=datetime.now(timezone.utc),
                decided_by="gp1",
            )
        )
    db_session.commit()


def test_alert_fires_webhook_called_with_expected_payload(db_session, monkeypatch):
    calls = []
    monkeypatch.setattr(metrics, "ALERT_WEBHOOK_URL", "https://example.test/hook")
    monkeypatch.setattr(metrics.httpx, "post", lambda url, json, timeout: calls.append((url, json)))

    _seed_rejected_suggestions(db_session, 5)
    fired = metrics.check_and_fire_alert(db_session)

    assert fired is True
    assert len(calls) == 1
    url, payload = calls[0]
    assert url == "https://example.test/hook"
    assert payload["alert"] == "coding-quality-degraded"
    assert payload["rejected"] == 5


def test_webhook_down_does_not_fail_alert_check(db_session, monkeypatch):
    monkeypatch.setattr(metrics, "ALERT_WEBHOOK_URL", "https://example.test/hook")

    def _raise(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(metrics.httpx, "post", _raise)

    _seed_rejected_suggestions(db_session, 5)
    fired = metrics.check_and_fire_alert(db_session)

    assert fired is True


def test_no_webhook_configured_skips_delivery(db_session, monkeypatch):
    monkeypatch.setattr(metrics, "ALERT_WEBHOOK_URL", None)
    calls = []
    monkeypatch.setattr(metrics.httpx, "post", lambda *a, **k: calls.append((a, k)))

    _seed_rejected_suggestions(db_session, 5)
    fired = metrics.check_and_fire_alert(db_session)

    assert fired is True
    assert calls == []
