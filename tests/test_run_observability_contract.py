from datetime import UTC, datetime

from src.utils import run_observability


def test_build_run_id_includes_timestamp_scope_and_suffix():
    run_id = run_observability.build_run_id(
        uf="SE",
        mode="incremental",
        now=datetime(2026, 4, 15, 12, 30, 45, tzinfo=UTC),
    )

    assert run_id.startswith("20260415T123045Z_se_incremental_")
    assert len(run_id.split("_")[-1]) == 6


def test_isoformat_utc_normalizes_timezone():
    value = datetime(2026, 4, 15, 12, 30, 45, tzinfo=UTC)
    assert run_observability.isoformat_utc(value) == "2026-04-15T12:30:45Z"
