from pathlib import Path

from src.config import settings


def test_bigquery_settings_resolve_relative_sa_path_from_project_root(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "demo-project")
    monkeypatch.setenv("BQ_DATASET", "raw")
    monkeypatch.setenv("BQ_ENABLED", "true")
    monkeypatch.setenv("GCP_SA_KEY_PATH", "./gcp-credentials.json")

    cfg = settings.get_bigquery_settings()

    assert cfg.project_id == "demo-project"
    assert cfg.dataset == "raw"
    assert cfg.enabled is True
    assert cfg.sa_key_path == "./gcp-credentials.json"
    assert cfg.resolved_sa_key_path == (settings.PROJECT_ROOT / "gcp-credentials.json").resolve()
    assert cfg.resolved_sa_key_path_str.endswith("gcp-credentials.json")


def test_build_runtime_env_keeps_existing_values_and_injects_resolved_sa_path():
    env = settings.build_runtime_env(
        {
            "EXTRA_VAR": "ok",
            "GCP_SA_KEY_PATH": "./gcp-credentials.json",
        }
    )

    assert env["EXTRA_VAR"] == "ok"
    assert Path(env["GCP_SA_KEY_PATH"]).is_absolute()
    assert env["GCP_SA_KEY_PATH"].endswith("gcp-credentials.json")


def test_supabase_settings_read_current_environment(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    cfg = settings.get_supabase_settings()

    assert cfg.url == "https://demo.supabase.co"
    assert cfg.key == "secret"
    assert cfg.is_configured is True
