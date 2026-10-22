from datetime import datetime, timezone

from app import models, oncall
from app.extraction_config import get_or_create_extraction_config


def _note(db_session, note_id="note-1"):
    db_session.add(models.ConsultationNote(id=note_id, patient_ref="p1", clinician_id="gp1", raw_text="note"))
    db_session.commit()


def _rejected(db_session, note_id, suggestion_id, snomed_code):
    db_session.add(
        models.SuggestedCode(
            id=suggestion_id,
            note_id=note_id,
            snomed_code=snomed_code,
            term="term",
            confidence=0.5,
            status="rejected",
            resolved_code=None,
            decided_at=datetime.now(timezone.utc),
            decided_by="gp1",
        )
    )


def test_category_skew_raises_incident_without_touching_model(db_session):
    _note(db_session)
    for i in range(5):
        _rejected(db_session, "note-1", f"s{i}", "49727002")  # same code every time
    db_session.commit()

    config_before = get_or_create_extraction_config(db_session)
    active_before = config_before.active_model

    result = oncall.diagnose_and_act(db_session)

    assert result["cause"] == "category_skew"
    assert result["action"] == "raise_incident"

    events = db_session.query(models.AuditEvent).filter(models.AuditEvent.event_type == "on_call_action").all()
    assert len(events) == 1
    assert events[0].payload["action"] == "raise_incident"

    config_after = get_or_create_extraction_config(db_session)
    assert config_after.active_model == active_before  # untouched


def test_diffuse_rejections_trigger_rollback(db_session):
    _note(db_session)
    codes = ["111", "222", "333", "444", "555"]  # no single code dominates
    for i, code in enumerate(codes):
        _rejected(db_session, "note-1", f"s{i}", code)
    db_session.commit()

    config = get_or_create_extraction_config(db_session)
    config.active_model = "claude-sonnet-5-4"  # simulate a bad deploy, not yet rolled back
    db_session.commit()

    result = oncall.diagnose_and_act(db_session)

    assert result["cause"] == "model_regression"
    assert result["action"] == "rollback"
    assert result["to_model"] == config.known_good_model

    db_session.refresh(config)
    assert config.active_model == config.known_good_model

    events = db_session.query(models.AuditEvent).filter(models.AuditEvent.event_type == "on_call_action").all()
    assert len(events) == 1
    assert events[0].payload["action"] == "rollback"


def test_diffuse_rejections_on_known_good_raises_incident(db_session):
    _note(db_session)
    codes = ["111", "222", "333", "444", "555"]
    for i, code in enumerate(codes):
        _rejected(db_session, "note-1", f"s{i}", code)
    db_session.commit()

    config = get_or_create_extraction_config(db_session)
    assert config.active_model == config.known_good_model  # already on known-good

    result = oncall.diagnose_and_act(db_session)

    assert result["cause"] == "model_regression_on_known_good"
    assert result["action"] == "raise_incident"


def test_agent_never_touches_suggestion_status(db_session):
    _note(db_session)
    for i in range(5):
        _rejected(db_session, "note-1", f"s{i}", "49727002")
    db_session.commit()

    oncall.diagnose_and_act(db_session)

    statuses = {s.status for s in db_session.query(models.SuggestedCode).all()}
    assert statuses == {"rejected"}  # agent never writes accepted/edited itself


def test_no_rejections_is_insufficient_data(db_session):
    _note(db_session)
    result = oncall.diagnose_and_act(db_session)
    assert result == {"cause": "insufficient_data", "action": "none"}
