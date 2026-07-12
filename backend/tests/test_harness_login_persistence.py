import os

import psycopg
import pytest
from druks.database import configure_session, db_session, get_session
from druks.harnesses.claude import ClaudeHarness
from druks.harnesses.models import HarnessLogin
from sqlalchemy import create_engine

# The credential store's whole job is to persist a mutated credential-file dict
# through a real commit. The rollback-based suite can't verify that — its identity
# map hands back the mutated in-memory object no matter what reached the DB — so
# this module runs against its own database with real commits and fresh sessions,
# the way rotation actually persists in production.

PG_BASE = os.environ.get("DRUKS_TEST_PG", "postgresql://druks:druks@localhost:5432")
DB = "druks_harness_login_test"
URL = f"{PG_BASE.replace('postgresql://', 'postgresql+psycopg://')}/{DB}"


def _pg_up() -> bool:
    try:
        psycopg.connect(f"{PG_BASE}/postgres", connect_timeout=2).close()
        return True
    except psycopg.Error:
        return False


pytestmark = pytest.mark.skipif(not _pg_up(), reason="test Postgres not reachable")


@pytest.fixture
def engine():
    from druks.database import init_db

    admin = psycopg.connect(f"{PG_BASE}/postgres", autocommit=True)
    admin.execute(f"DROP DATABASE IF EXISTS {DB}")
    admin.execute(f"CREATE DATABASE {DB}")
    admin.close()

    created = create_engine(URL)
    init_db(created)
    configure_session(created)
    try:
        yield created
    finally:
        created.dispose()


def _committed(engine, work):
    session = get_session(engine)
    db_session.registry.set(session)
    try:
        result = work()
        session.commit()
        return result
    finally:
        db_session.remove()
        session.close()


def test_store_persists_mutated_payload_across_sessions(engine):
    # Load the row, edit the payload in place, store it, then read it back from a
    # fresh session — the round-trip refresh actually makes. Commit + new session
    # proves the edit reached the DB, not just the in-memory object.
    _committed(
        engine,
        lambda: ClaudeHarness.store_credentials(
            {"claudeAiOauth": {"accessToken": "old", "refreshToken": "R0"}}
        ),
    )

    def mutate_in_place():
        data = ClaudeHarness.get_credentials()
        data["claudeAiOauth"]["accessToken"] = "new"
        ClaudeHarness.store_credentials(data)

    _committed(engine, mutate_in_place)

    block = _committed(engine, lambda: HarnessLogin.get("claude").payload["claudeAiOauth"])
    assert block["accessToken"] == "new"
