from druks.user_settings.models import HarnessSettings, SettingsOverride


def test_agent_model_falls_back_to_default(db_session):
    resolved = SettingsOverride.agent_model("planner", "claude-opus-4-7")
    assert resolved.value == "claude-opus-4-7"
    assert resolved.source == "default"


def test_agent_effort_override_then_declared_then_harness(db_session):
    # No override, no declared value → the agent's harness effort default.
    assert SettingsOverride.agent_effort("planner", None, "claude") == ("high", "harness")
    # The operator retunes per harness, independently.
    HarnessSettings.require("claude").update(effort="low")
    assert SettingsOverride.agent_effort("planner", None, "claude") == ("low", "harness")
    assert SettingsOverride.agent_effort("planner", None, "codex") == ("high", "harness")
    # A declared value wins over the harness default.
    assert SettingsOverride.agent_effort("planner", "medium", "claude") == ("medium", "declared")
    # A per-agent override wins over everything.
    SettingsOverride.set_agent_effort("planner", "high")
    assert SettingsOverride.agent_effort("planner", "medium", "claude") == ("high", "agent")


def test_extension_setting_override_then_default(db_session):
    # No override → the declared default passed by the caller.
    assert SettingsOverride.extension_setting("build", "auto_merge", True) is True
    # An override wins — including turning it off.
    SettingsOverride.set_extension_setting("build", "auto_merge", False)
    assert SettingsOverride.extension_setting("build", "auto_merge", True) is False
    # Clearing reverts to the caller's default.
    SettingsOverride.set_extension_setting("build", "auto_merge", None)
    assert SettingsOverride.extension_setting("build", "auto_merge", True) is True


def test_agent_timeout_override_then_declared_then_harness(db_session):
    # No override, no declared value → the agent's harness timeout default.
    assert SettingsOverride.agent_timeout("planner", None, "claude") == (1800, "harness")
    # The operator retunes per harness, independently.
    HarnessSettings.require("claude").update(timeout=1200)
    assert SettingsOverride.agent_timeout("planner", None, "claude") == (1200, "harness")
    assert SettingsOverride.agent_timeout("planner", None, "codex") == (1800, "harness")
    # A declared value wins over the harness default.
    assert SettingsOverride.agent_timeout("planner", 2700, "claude") == (2700, "declared")
    # A per-agent override wins over everything.
    SettingsOverride.set_agent_timeout("planner", 600)
    assert SettingsOverride.agent_timeout("planner", 2700, "claude") == (600, "agent")


def test_harness_token_default_resolves_to_the_harness_model(db_session):
    # codex/claude tokens resolve to their harness's model.
    assert SettingsOverride.agent_model("planner", "codex").value == "gpt-5.5"
    assert SettingsOverride.agent_model("reviewer", "claude").value == "claude-opus-4-7"

    HarnessSettings.require("claude").update(model="claude-sonnet-4-6")
    assert SettingsOverride.agent_model("reviewer", "claude").value == "claude-sonnet-4-6"


def test_agent_override_wins_over_the_default(db_session):
    SettingsOverride.set_agent_model("planner", "claude-haiku-4-5")
    resolved = SettingsOverride.agent_model("planner", "codex")
    assert resolved.value == "claude-haiku-4-5"
    assert resolved.source == "agent"


def test_clearing_an_override_reverts_to_inherit(db_session):
    SettingsOverride.set_agent_model("planner", "claude-haiku-4-5")
    SettingsOverride.set_agent_model("planner", None)  # None clears
    assert SettingsOverride.agent_model("planner", "codex").source == "default"


def test_workflow_setting_resolves_override_then_default(db_session):
    assert SettingsOverride.workflow_setting("build_workflow", "max_revs", 5) == 5
    SettingsOverride.set_workflow_setting("build_workflow", "max_revs", 8)
    assert SettingsOverride.workflow_setting("build_workflow", "max_revs", 5) == 8
    SettingsOverride.set_workflow_setting("build_workflow", "max_revs", None)
    assert SettingsOverride.workflow_setting("build_workflow", "max_revs", 5) == 5


def test_workflow_setting_namespaced_by_kind(db_session):
    SettingsOverride.set_workflow_setting("build_workflow", "shared", "a")
    SettingsOverride.set_workflow_setting("other_workflow", "shared", "b")
    assert SettingsOverride.workflow_setting("build_workflow", "shared", None) == "a"
    assert SettingsOverride.workflow_setting("other_workflow", "shared", None) == "b"
