import pytest
from druks.workflows import ReviewReply, RunRecord
from pydantic import BaseModel


class Finding(BaseModel):
    status: str
    title: str = ""


class Grade(BaseModel):
    decision: str


def _record() -> RunRecord:
    record = RunRecord()
    record._append(Finding(status="success", title="a"))
    record._append(Grade(decision="approve"))
    record._append(Finding(status="failed", title="b"))
    record._append(Finding(status="success", title="c"))
    return record


def test_selection_is_by_contract_type_in_call_order():
    record = _record()
    assert [finding.title for finding in record.list(Finding)] == ["a", "b", "c"]
    assert [grade.decision for grade in record.list(Grade)] == ["approve"]


def test_latest_is_the_newest_match_or_none():
    record = _record()
    latest = record.latest(Finding)
    assert latest and latest.title == "c"
    assert RunRecord().latest(Finding) is None


def test_filters_are_flat_anded_equality():
    record = _record()
    assert [f.title for f in record.list(Finding, status="success")] == ["a", "c"]
    assert [f.title for f in record.list(Finding, status="success", title="a")] == ["a"]
    assert record.latest(Finding, status="missing") is None
    assert RunRecord().list(Finding, status="success") == []


def test_a_filter_typo_raises_when_entries_scan():
    with pytest.raises(AttributeError):
        _record().list(Finding, verdict="success")


def test_review_reply_validates_the_resume_wire_shape():
    # The resume endpoint's payload — {action, answers, note} — validates
    # unchanged; answers and note default for partial senders.
    reply = ReviewReply.model_validate(
        {"action": "request_changes", "answers": {"q1": "redis"}, "note": "why q1"}
    )
    assert reply.action == "request_changes"
    assert (reply.answers, reply.note) == ({"q1": "redis"}, "why q1")
    assert ReviewReply.model_validate({"action": "approve"}).answers == {}
    # The recv topic stays the wire's "review", not the class-name derivation.
    assert ReviewReply.topic == "review"
