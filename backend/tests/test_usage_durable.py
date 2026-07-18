import asyncio
import os
from types import SimpleNamespace

import psycopg
import pytest
from druks.database import configure_session, get_session
from druks.durable import Run, RunState
from druks.durable.engine import configure_engine, init_dbos, launch, shutdown
from druks.usage.models import UsageScrape
from sqlalchemy import create_engine

PG_BASE = os.environ.get("DRUKS_TEST_PG", "postgresql://druks:druks@localhost:5432")
DB = "druks_usage_durable_test"
URL = f"{PG_BASE.replace('postgresql://', 'postgresql+psycopg://')}/{DB}"


def _pg_up() -> bool:
    try:
        psycopg.connect(f"{PG_BASE}/postgres", connect_timeout=2).close()
        return True
    except psycopg.Error:
        return False


pytestmark = [
    pytest.mark.skipif(not _pg_up(), reason="test Postgres not reachable"),
    pytest.mark.asyncio(loop_scope="module"),
]


class _FakeHarness:
    # Duck-typed, not a Harness subclass: subclassing would enroll it in the
    # global registry (get_harnesses() == Harness.__subclasses__()). poll_usage
    # calls the real UsageScrape.save() — the exact write the step must commit.
    name = "faketest"

    @staticmethod
    async def poll_usage(connection) -> dict[str, object]:
        UsageScrape(
            harness="faketest",
            account_id=connection.account_id,
            parse_ok=True,
            five_hour_percent_left=73,
            week_percent_left=41,
        ).save()
        return {"harness": "faketest", "status": "recorded", "parse_ok": True, "error": None}


@pytest.fixture(scope="module", autouse=True)
def rt():
    from druks.database import init_db

    db_url_snap = os.environ.get("DRUKS_DATABASE_URL")

    admin = psycopg.connect(f"{PG_BASE}/postgres", autocommit=True)
    admin.execute(f"DROP DATABASE IF EXISTS {DB}")
    admin.execute(f"CREATE DATABASE {DB}")
    admin.close()

    engine = create_engine(URL)
    init_db(engine)
    configure_engine(engine)
    configure_session(engine)

    from druks.usage import workflows as usage_workflows

    # The step reads get_harnesses at call time; the fake writes a scrape without
    # real HTTP, so a scheduled tick during the test window is harmless too. The
    # poll walks connected rows, so the fake harness needs a real connection.
    usage_workflows.get_harnesses = lambda: (_FakeHarness,)
    from druks.accounts.models import Account
    from druks.harnesses.models import HarnessConnection

    seed = get_session(engine)
    try:
        account = Account(email="op@example.com")
        seed.add(account)
        seed.flush()
        seed.add(
            HarnessConnection(
                harness="faketest",
                account_id=account.id,
                provider_email=account.email,
                payload={"token": "t"},
            )
        )
        seed.commit()
    finally:
        seed.close()

    os.environ["DRUKS_DATABASE_URL"] = URL
    init_dbos()
    launch()
    try:
        yield SimpleNamespace(engine=engine, flow=usage_workflows.PollUsage)
    finally:
        shutdown()
        engine.dispose()
        if db_url_snap is None:
            os.environ.pop("DRUKS_DATABASE_URL", None)
        else:
            os.environ["DRUKS_DATABASE_URL"] = db_url_snap


async def _wait(engine, wfid, predicate, timeout=20.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        session = get_session(engine)
        try:
            row = session.get(Run, wfid)
            if row is not None and predicate(row):
                return row
        finally:
            session.close()
        await asyncio.sleep(0.1)
    raise AssertionError("timed out")


async def test_poll_persists_a_scrape_through_the_engine(rt):
    # Asserts the write actually landed, not just that the run finished.
    wfid = await rt.flow.start(subject=None)
    await _wait(rt.engine, wfid, lambda r: r.state == RunState.FINISHED)

    session = get_session(rt.engine)
    try:
        rows = (
            session.query(UsageScrape)
            .filter(UsageScrape.harness == "faketest")
            .order_by(UsageScrape.scraped_at.desc())
            .all()
        )
    finally:
        session.close()
    assert rows, "poll run finished but no scrape was committed"
    assert rows[0].parse_ok is True
    assert rows[0].five_hour_percent_left == 73
    assert rows[0].week_percent_left == 41
