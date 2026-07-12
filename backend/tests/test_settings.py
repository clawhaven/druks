from druks.settings import Settings, ensure_data_dirs, load_settings


def test_ensure_data_dirs_provisions_skills_dir(tmp_path, monkeypatch):
    # The settings UI installs skill collections into skills_dir; if startup
    # doesn't create it, the first install's write raises OSError → opaque 500.
    # This is the DRUKS_SKILLS_DIR-outside-data_dir case that bit us.
    monkeypatch.setenv("DRUKS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DRUKS_SKILLS_DIR", str(tmp_path / "shared" / "skills"))
    settings = load_settings()
    ensure_data_dirs(settings)
    assert settings.skills_dir.is_dir()


def test_settings_no_longer_carries_agent_knob_fields(monkeypatch, tmp_path):

    monkeypatch.setenv("DRUKS_DATA_DIR", str(tmp_path))
    settings = load_settings()

    for forbidden in (
        "codex_model",
        "codex_fast_mode",
        "codex_reasoning_effort",
        "codex_plan_reasoning_effort",
        "codex_evaluate_reasoning_effort",
        "claude_model",
        "claude_fast_mode",
        "claude_reasoning_effort",
        "claude_plan_review_effort",
        "claude_implement_effort",
    ):
        assert forbidden not in Settings.model_fields, (
            f"{forbidden!r} should have moved to user_settings"
        )
        assert not hasattr(settings, forbidden), f"Settings instance still exposes {forbidden!r}"
