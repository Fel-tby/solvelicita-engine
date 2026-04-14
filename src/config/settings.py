from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env() -> None:
    load_dotenv(ENV_FILE)


def _env_bool(name: str, default: bool = False, env: Mapping[str, str] | None = None) -> bool:
    raw = (env or os.environ).get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "t", "yes", "y", "sim"}


def _env_str(name: str, default: str = "", env: Mapping[str, str] | None = None) -> str:
    return (env or os.environ).get(name, default)


def _resolve_optional_path(raw_path: str) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


@dataclass(frozen=True)
class BigQuerySettings:
    project_id: str
    dataset: str
    enabled: bool
    sa_key_path: str
    resolved_sa_key_path: Path | None

    @property
    def resolved_sa_key_path_str(self) -> str:
        return str(self.resolved_sa_key_path) if self.resolved_sa_key_path else ""

    @property
    def has_credentials_path(self) -> bool:
        return bool(self.sa_key_path)


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    key: str

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.key)


@dataclass(frozen=True)
class AppSettings:
    root_dir: Path
    env_file: Path
    bigquery: BigQuerySettings
    supabase: SupabaseSettings


def get_bigquery_settings(env: Mapping[str, str] | None = None) -> BigQuerySettings:
    sa_key_path = _env_str("GCP_SA_KEY_PATH", env=env)
    return BigQuerySettings(
        project_id=_env_str("GCP_PROJECT_ID", "solvelicita", env=env),
        dataset=_env_str("BQ_DATASET", "raw", env=env),
        enabled=_env_bool("BQ_ENABLED", default=False, env=env),
        sa_key_path=sa_key_path,
        resolved_sa_key_path=_resolve_optional_path(sa_key_path),
    )


def get_supabase_settings(env: Mapping[str, str] | None = None) -> SupabaseSettings:
    return SupabaseSettings(
        url=_env_str("SUPABASE_URL", env=env),
        key=_env_str("SUPABASE_KEY", env=env),
    )


def get_settings(env: Mapping[str, str] | None = None) -> AppSettings:
    return AppSettings(
        root_dir=PROJECT_ROOT,
        env_file=ENV_FILE,
        bigquery=get_bigquery_settings(env=env),
        supabase=get_supabase_settings(env=env),
    )


def build_runtime_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env) if base_env is not None else os.environ.copy()
    bq = get_bigquery_settings(env=env)
    if bq.resolved_sa_key_path_str:
        env["GCP_SA_KEY_PATH"] = bq.resolved_sa_key_path_str
    return env


load_project_env()
