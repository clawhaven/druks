from druks.durable.enums import RunState
from druks.durable.exceptions import GateTimeout
from druks.durable.models import Run
from druks.durable.reads import _status


def _run(
    id: str,
    kind: str,
    state: RunState,
    input_request: dict | None = None,
    failure: str | None = None,
    failure_code: str | None = None,
) -> Run:
    return Run(
        id=id,
        kind=kind,
        state=state.value,
        input_request=input_request,
        failure=failure,
        failure_code=failure_code,
    )


def _status_of(runs, active_calls=None):
    active_run = next((run for run in runs if run.is_active), None)
    return _status(runs, active_run, active_calls or [])


def test_subject_state_prefers_the_newer_active_run_over_a_stale_parked_one():
    # runs arrives newest-first, mirroring Run.list_for_subject.
    runs = [
        _run("new", "build.build_workflow", RunState.RUNNING),
        _run("old", "build.build_workflow", RunState.PENDING_INPUT),
    ]
    assert _status_of(runs).state == RunState.RUNNING


def test_subject_state_prefers_a_newer_parked_run_over_an_older_running_one():
    # Recency decides, not a hardcoded state preference.
    runs = [
        _run("new", "build.build_workflow", RunState.PENDING_INPUT),
        _run("old", "build.build_workflow", RunState.RUNNING),
    ]
    assert _status_of(runs).state == RunState.PENDING_INPUT


def test_subject_state_uses_the_latest_outcome_once_every_run_is_terminal():
    runs = [
        _run("new", "build.build_workflow", RunState.FINISHED),
        _run("old", "build.build_workflow", RunState.FAILED),
    ]
    assert _status_of(runs).state == RunState.FINISHED


def test_subject_label_surfaces_the_newest_active_runs_gate_ask():
    runs = [
        _run("new", "build.build_workflow", RunState.PENDING_INPUT, {"label": "Approve plan"}),
        _run("old", "build.build_workflow", RunState.PENDING_INPUT, {"label": "Answer questions"}),
    ]
    assert _status_of(runs).label == "Approve plan"


def test_subject_label_falls_back_to_the_running_runs_kind():
    runs = [
        _run("new", "build.build_workflow", RunState.RUNNING),
        _run("old", "build.build_workflow", RunState.PENDING_INPUT, {"label": "Approve plan"}),
    ]
    assert _status_of(runs).label == "Build workflow"


def test_subject_label_says_timed_out_when_the_run_failed_on_an_unanswered_gate():
    # The gate timeout's stamped failure_code is the marker — the board tells
    # the operator to re-trigger instead of showing a bare "failed".
    runs = [
        _run("new", "build.scope", RunState.FAILED, failure_code=GateTimeout.code),
    ]
    assert _status_of(runs).label == "Scope timed out — re-trigger to retry"


def test_status_stays_empty_but_carries_failure_when_the_run_crashed():
    # A genuine crash keeps the empty label; the failure rides the status instead.
    runs = [
        _run("new", "build.scope", RunState.FAILED, failure="boom"),
    ]
    status = _status_of(runs)
    assert status.label == ""
    assert status.failure == "boom"
