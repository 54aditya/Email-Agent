import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import confirm, importance
from storage import db


def test_interview_mail_scores_high():
    email = {
        "subject": "Interview schedule for AI Engineer",
        "snippet": "",
        "from": "hr@corp.com",
        "labels": ["INBOX"],
    }
    score, reasons = importance.score_email(email)
    assert score >= 8 and reasons


def test_promotions_are_filtered_out():
    email = {
        "subject": "Big sale",
        "snippet": "50% off",
        "from": "no-reply@shop.com",
        "labels": ["CATEGORY_PROMOTIONS"],
    }
    assert importance.rank_emails([email]) == []


def test_ranking_order():
    low = {"subject": "meeting", "snippet": "", "from": "a@b.com", "labels": []}
    high = {
        "subject": "Job offer and interview",
        "snippet": "",
        "from": "c@d.com",
        "labels": ["IMPORTANT"],
    }
    ranked = importance.rank_emails([low, high])
    assert ranked[0]["subject"] == "Job offer and interview"


def test_sensitive_tools():
    assert confirm.needs_confirmation("send_email")
    assert confirm.needs_confirmation("trash_email")
    assert not confirm.needs_confirmation("read_email")
    assert not confirm.needs_confirmation("create_draft")


def test_preview_contains_key_fields():
    text = confirm.format_preview(
        "send_email",
        {
            "to": "hr@x.com",
            "subject": "Hi",
            "body": "Hello there",
            "attachments": ["cv.pdf"],
        },
    )
    for part in ("hr@x.com", "Hi", "Hello there", "cv.pdf"):
        assert part in text


def test_cli_confirm_declines_by_default(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    approved, message = confirm.cli_confirm("send_email", {"to": "a@b.com"})
    assert approved is False and "DECLINED" in message


def test_cli_confirm_accepts_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    approved, _ = confirm.cli_confirm("send_email", {"to": "a@b.com"})
    assert approved is True


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return db


def test_sent_log_and_followups(temp_db):
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    old_id = temp_db.log_sent("a@b.com", "Old mail", "m1", "t1", sent_at=old)
    temp_db.log_sent("c@d.com", "New mail", "m2", "t2")

    pending = temp_db.pending_follow_ups(days=5)
    assert [row["subject"] for row in pending] == ["Old mail"]

    temp_db.mark_replied(old_id)
    assert temp_db.pending_follow_ups(days=5) == []
    assert len(temp_db.recent_sent()) == 2


def test_templates(temp_db):
    temp_db.save_template("job", "Subject A", "Body A")
    temp_db.save_template("job", "Subject B", "Body B")
    assert temp_db.get_template("job")["subject"] == "Subject B"
    assert temp_db.list_templates() == ["job"]
    assert temp_db.get_template("missing") is None
