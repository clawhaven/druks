from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import configure_app_for_test, make_settings
from druks.database import db_session
from druks.settings import Settings
from druks.usage.models import UsageScrape
from druks.usage.workflows import PollUsage
from fastapi.testclient import TestClient


@pytest.fixture
def extension_settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def client(extension_settings: Settings):
    with TestClient(configure_app_for_test(settings=extension_settings)) as c:
        yield c


def _seed(snapshots: list[UsageScrape]) -> None:
    # save() flushes onto the ambient per-test connection session (bound by the
    # _txn fixture), so the rows are visible to the request and roll back with the
    # test — no separate engine, no commit.
    for snap in snapshots:
        snap.save()


def _harness(body: dict, name: str) -> dict:
    return next(entry for entry in body["harnesses"] if entry["name"] == name)


def test_usage_today_counts_calls_whose_model_isnt_a_current_harness(client, db_session) -> None:
    # Model ids churn on deploys (opus-4-7 → 4-8), so a call finished earlier today
    # can carry an id no harness claims any more. Money spent must not vanish from
    # the display — the sys-strip's total_run_spend_between counts every call, and
    # the two surfaces must quote the same number. Unclaimed and unresolved models
    # land in the "unattributed" bucket the panel's grand total sums.
    from conftest import seed_agent_run

    for model in ("claude-opus-4-5", None):
        call = seed_agent_run(model=model)
        call.finished_at = datetime.now(UTC)
        call.cost_usd = 2.5
    db_session.flush()

    body = client.get("/api/usage/today").json()
    bucket = _harness(body, "unattributed")
    assert bucket["runs"] == 2
    assert bucket["spendUsd"] == 5.0


def test_get_usage_empty_returns_available_false(client) -> None:
    response = client.get("/api/usage")
    assert response.status_code == 200
    body = response.json()
    # One entry per registered harness, none available pre-first-poll.
    assert {entry["name"] for entry in body["harnesses"]} == {"claude", "codex"}
    assert all(entry["available"] is False for entry in body["harnesses"])
    assert body["pollingEnabled"] is True
    assert body["pollingIntervalSeconds"] == 300


def test_get_usage_serializes_latest_per_harness(client, extension_settings) -> None:
    # Plant a snapshot for claude only — codex should still report
    # ``available=false`` rather than missing-key/404.
    _seed(
        [
            UsageScrape(
                harness="claude",
                parse_ok=True,
                plan_tier="Max",
                five_hour_percent_left=54,
                five_hour_resets_at=datetime(2026, 5, 23, 18, 40, tzinfo=UTC),
                week_percent_left=38,
                scraped_at=datetime.now(UTC) - timedelta(seconds=45),
            ),
        ],
    )

    response = client.get("/api/usage")
    assert response.status_code == 200
    body = response.json()

    claude = _harness(body, "claude")
    assert claude["available"] is True
    assert claude["planTier"] == "Max"
    assert claude["fiveHour"]["percentLeft"] == 54
    assert claude["week"]["percentLeft"] == 38
    assert claude["ageSeconds"] is not None
    assert 30 <= claude["ageSeconds"] <= 90  # close to the planted 45s
    assert claude["stale"] is False

    assert _harness(body, "codex")["available"] is False


def test_get_usage_flags_stale_after_24h(client, extension_settings) -> None:
    _seed(
        [
            UsageScrape(
                harness="claude",
                parse_ok=True,
                five_hour_percent_left=10,
                scraped_at=datetime.now(UTC) - timedelta(hours=30),
            ),
        ],
    )

    body = client.get("/api/usage").json()
    assert _harness(body, "claude")["stale"] is True


def test_get_usage_exposes_unlimited_flag(client, extension_settings) -> None:
    # Codex business plan: scraper synthesizes permanently-full buckets
    # and marks the row unmetered so the UI can render "unmetered"
    # instead of a quota bar that never moves.
    _seed(
        [
            UsageScrape(
                harness="codex",
                parse_ok=True,
                plan_tier="business",
                five_hour_percent_left=100,
                week_percent_left=100,
                unlimited=True,
            ),
        ],
    )

    body = client.get("/api/usage").json()
    assert _harness(body, "codex")["unlimited"] is True
    assert _harness(body, "codex")["fiveHour"]["percentLeft"] == 100
    assert _harness(body, "claude")["unlimited"] is False


def test_usage_history_serializes_series_oldest_first(client, extension_settings) -> None:
    now = datetime.now(UTC)
    snaps = [
        UsageScrape(
            harness="claude",
            parse_ok=True,
            five_hour_percent_left=pct,
            week_percent_left=90 - i,
            scraped_at=now - timedelta(minutes=10 * i),
        )
        for i, pct in enumerate([20, 40, 60])
    ]
    # Outside the 6h five-hour range but inside the weekly range.
    snaps.append(
        UsageScrape(
            harness="claude",
            parse_ok=True,
            five_hour_percent_left=95,
            week_percent_left=99,
            scraped_at=now - timedelta(hours=12),
        ),
    )
    # Failed scrape — no percentages, must not appear in either series.
    snaps.append(
        UsageScrape(harness="claude", parse_ok=False, scraped_at=now - timedelta(minutes=5))
    )
    _seed(snaps)

    body = client.get("/api/usage/history").json()

    assert [p["pct"] for p in _harness(body, "claude")["fiveHour"]] == [60, 40, 20]
    assert [p["pct"] for p in _harness(body, "claude")["week"]] == [99, 88, 89, 90]
    assert _harness(body, "codex")["fiveHour"] == []
    assert _harness(body, "codex")["week"] == []


def test_usage_today_aggregates_spend_and_tokens_by_provider(client, extension_settings) -> None:
    from zoneinfo import ZoneInfo

    from conftest import seed_agent_run

    codex_run = seed_agent_run(model="gpt-5.5")
    codex_run.cost_usd = 1.25
    codex_run.cost_metadata = {
        "provider": "openai",
        "input_tokens": 1000,
        "output_tokens": 200,
        "reasoning_output_tokens": 50,
    }
    codex_run.finished_at = datetime.now(UTC)

    claude_run = seed_agent_run(model="claude-opus-4-7")
    claude_run.cost_usd = 2.5
    claude_run.cost_metadata = {
        "provider": "anthropic",
        "input_tokens": 100,
        "cache_read_input_tokens": 50,
        "cache_creation_input_tokens": 25,
        "output_tokens": 75,
    }
    claude_run.finished_at = datetime.now(UTC)

    # Finished yesterday — outside today's boundary, must not count.
    old_run = seed_agent_run(model="gpt-5.5")
    old_run.cost_usd = 99.0
    old_run.finished_at = datetime.now(UTC) - timedelta(days=2)

    # Still running — no cost yet, counted nowhere.
    seed_agent_run(model="gpt-5.5")
    db_session().flush()

    body = client.get("/api/usage/today").json()

    codex = _harness(body, "codex")
    assert codex["spendUsd"] == 1.25
    assert codex["tokens"] == 1250  # 1000 input + (200 + 50) output
    assert codex["runs"] == 1
    claude = _harness(body, "claude")
    assert claude["spendUsd"] == 2.5
    assert claude["tokens"] == 250  # (100 + 50 + 25) input + 75 output
    assert claude["runs"] == 1

    hour = datetime.now(ZoneInfo(body["timezone"])).hour
    assert codex["hours"][hour] == 1.25
    assert claude["hours"][hour] == 2.5
    assert sum(codex["hours"]) == 1.25
    assert sum(claude["hours"]) == 2.5


def test_polling_toggle_reflected(client, extension_settings) -> None:
    # The pause knob is the workflow's schedule_enabled override — the same
    # switch the settings modal's usage pane writes.
    PollUsage.override_setting("schedule_enabled", False)
    db_session().flush()

    body = client.get("/api/usage").json()
    assert body["pollingEnabled"] is False


def test_polling_interval_derived_from_schedule_override(client, extension_settings) -> None:
    PollUsage.override_setting("schedule", "*/10 * * * *")
    db_session().flush()

    body = client.get("/api/usage").json()
    assert body["pollingIntervalSeconds"] == 600
