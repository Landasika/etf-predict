import json
import sqlite3

import pytest

import core.position_manager as position_manager


@pytest.fixture
def isolated_position_db(tmp_path, monkeypatch):
    db_path = tmp_path / "etf.db"
    monkeypatch.setattr(position_manager, "DB_PATH", db_path)
    position_manager.init_tables()
    return db_path


def fetch_snapshots(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM position_snapshots ORDER BY trade_date, etf_code"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def test_snapshot_positions_for_date_writes_full_watchlist_with_zero_for_missing(
    isolated_position_db,
):
    position_manager.upsert_position(
        "159870.SZ",
        current_positions=5,
        avg_cost=0.83,
        total_shares=1200,
        cash_used=996,
        position_date="20260603",
    )

    result = position_manager.snapshot_positions_for_date(
        "20260603",
        [{"code": "159870.SZ"}, {"code": "512980.SH"}],
    )

    assert result == {"date": "20260603", "snapshots": 2}
    snapshots = fetch_snapshots(isolated_position_db)
    assert [(row["etf_code"], row["positions"]) for row in snapshots] == [
        ("159870.SZ", 5),
        ("512980.SH", 0),
    ]
    assert snapshots[0]["avg_cost"] == 0.83
    assert snapshots[0]["total_shares"] == 1200
    assert snapshots[0]["cash_used"] == 996
    assert snapshots[0]["source"] == "auto_close"


def test_snapshot_positions_for_date_updates_existing_snapshot_for_same_day(
    isolated_position_db,
):
    watchlist = [{"code": "159870.SZ"}]
    position_manager.upsert_position("159870.SZ", current_positions=2)
    position_manager.snapshot_positions_for_date("20260603", watchlist)

    position_manager.upsert_position("159870.SZ", current_positions=5)
    position_manager.snapshot_positions_for_date("20260603", watchlist)

    snapshots = fetch_snapshots(isolated_position_db)
    assert len(snapshots) == 1
    assert snapshots[0]["trade_date"] == "20260603"
    assert snapshots[0]["etf_code"] == "159870.SZ"
    assert snapshots[0]["positions"] == 5


def test_run_auto_sync_all_writes_snapshot_after_signal_sync(
    tmp_path,
    monkeypatch,
    isolated_position_db,
):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "watchlist_etfs.json").write_text(
        json.dumps(
            {
                "etfs": [
                    {"code": "159870.SZ", "strategy": "macd_aggressive"},
                    {"code": "512980.SH", "strategy": "macd_aggressive"},
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_signal(code, start_date, strategy):
        target = 5 if code == "159870.SZ" else 0
        return {
            "success": True,
            "data": {
                "positions_used": target,
                "latest_date": "20260603",
                "latest_data": {"close": 1.23},
            },
        }

    monkeypatch.setattr(
        "core.watchlist.calculate_realtime_signal",
        fake_signal,
    )

    result = position_manager.run_auto_sync_all()

    assert result["snapshot"] == {"date": "20260603", "snapshots": 2}
    snapshots = fetch_snapshots(isolated_position_db)
    assert [(row["etf_code"], row["positions"]) for row in snapshots] == [
        ("159870.SZ", 5),
        ("512980.SH", 0),
    ]
