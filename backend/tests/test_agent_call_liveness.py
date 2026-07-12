from conftest import finish_agent_run, seed_agent_run
from druks.durable.dbos_state import workflow_status
from druks.durable.enums import AgentCallStatus
from druks.durable.schemas import AgentCallResponse
from sqlalchemy import update


def test_from_call_derives_running_while_run_active(db_session):
    call = seed_agent_run()  # unfinished RUNNING row on an active run
    assert AgentCallResponse.from_call(call).status == "running"


def test_from_call_derives_abandoned_when_run_terminal(db_session):
    call = seed_agent_run()  # unfinished, but its run has died
    db_session.execute(
        update(workflow_status)
        .where(workflow_status.c.workflow_uuid == call.run_id)
        .values(status="ERROR")
    )
    db_session.expire_all()
    assert AgentCallResponse.from_call(call).status == "abandoned"


def test_from_call_keeps_a_finished_calls_outcome(db_session):
    call = finish_agent_run(seed_agent_run(), status=AgentCallStatus.SUCCEEDED)
    # A finished call keeps its outcome regardless of its run's state.
    assert AgentCallResponse.from_call(call).status == "succeeded"
