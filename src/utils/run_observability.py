from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_run_id(*, uf: str, mode: str, now: datetime | None = None) -> str:
    instant = (now or utc_now()).astimezone(UTC)
    prefix = instant.strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{uf.lower()}_{mode.lower()}_{uuid4().hex[:6]}"
