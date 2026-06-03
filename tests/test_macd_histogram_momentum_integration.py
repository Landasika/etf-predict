import pandas as pd

from optimization.optimize_histogram_params import HistogramParamOptimizer
from strategies.macd_histogram_momentum import MACDHistogramMomentumSignalGenerator


def _sample_market_data(days=90, start="2025-01-01"):
    dates = pd.date_range(start, periods=days, freq="D")
    closes = []
    price = 10.0
    for i in range(days):
        if i < 30:
            price *= 0.992
        elif i < 55:
            price *= 1.006
        else:
            price *= 1.003
        closes.append(round(price, 4))

    return pd.DataFrame({
        "trade_date": dates.strftime("%Y%m%d"),
        "date": dates.strftime("%Y%m%d"),
        "open": closes,
        "high": [p * 1.01 for p in closes],
        "low": [p * 0.99 for p in closes],
        "close": closes,
        "vol": [1000000 + i * 1000 for i in range(days)],
    })


def test_watchlist_accepts_macd_histogram_strategy():
    import core.watchlist as watchlist

    assert "macd_histogram_momentum" in watchlist.STRATEGY_TYPES


def test_run_backtest_uses_optimized_histogram_params(monkeypatch):
    import core.watchlist as watchlist

    sample_data = _sample_market_data().to_dict("records")
    optimized_params = {
        "macd_fast": 7,
        "macd_slow": 19,
        "macd_signal": 4,
        "deadzone": 0.012,
        "confirm_days": 2,
        "smooth": 2,
        "max_change": 3,
        "min_position_change": 2,
    }
    seen = {}

    original_init = MACDHistogramMomentumSignalGenerator.__init__

    def spy_init(self, params=None):
        seen["params"] = dict(params or {})
        original_init(self, params)

    monkeypatch.setattr(watchlist, "load_watchlist", lambda: {
        "etfs": [{
            "code": "510300.SH",
            "strategy": "macd_histogram_momentum",
            "initial_capital": 2000,
            "total_positions": 10,
            "optimized_histogram_params": optimized_params,
        }]
    })
    monkeypatch.setattr(watchlist, "get_etf_daily_data", lambda *args, **kwargs: sample_data)
    monkeypatch.setattr(MACDHistogramMomentumSignalGenerator, "__init__", spy_init)

    result = watchlist.run_backtest("510300.SH", start_date="20250101")

    assert result["success"] is True
    assert result["strategy"] == "macd_histogram_momentum"
    assert seen["params"] == optimized_params
    assert "hist_state" in result["data"]["latest_data"]


def test_calculate_realtime_signal_uses_histogram_strategy(monkeypatch):
    import core.watchlist as watchlist

    sample_data = _sample_market_data().to_dict("records")
    optimized_params = {
        "macd_fast": 8,
        "macd_slow": 21,
        "macd_signal": 5,
        "deadzone": 0.01,
        "confirm_days": 1,
        "smooth": 1,
        "max_change": 4,
    }

    monkeypatch.setattr(watchlist, "load_watchlist", lambda: {
        "etfs": [{
            "code": "510300.SH",
            "strategy": "macd_histogram_momentum",
            "initial_capital": 2000,
            "total_positions": 10,
            "optimized_histogram_params": optimized_params,
        }]
    })
    monkeypatch.setattr(watchlist, "get_etf_daily_data", lambda *args, **kwargs: sample_data)

    result = watchlist.calculate_realtime_signal("510300.SH", start_date="20250101")

    assert result["success"] is True
    assert result["strategy"] == "macd_histogram_momentum"
    assert result["data"]["latest_data"]["target_position"] == result["data"]["positions_used"]
    assert result["data"]["latest_data"]["hist_state"]


def test_optimizer_reuses_histogram_signal_generator(monkeypatch):
    df = _sample_market_data()
    params = {
        "macd_fast": 8,
        "macd_slow": 21,
        "macd_signal": 5,
        "deadzone": 0.01,
        "confirm_days": 2,
        "smooth": 2,
        "max_change": 3,
        "min_position_change": 2,
    }
    called = {}

    original_generate = MACDHistogramMomentumSignalGenerator.generate_signals

    def spy_generate(self, input_df):
        called["params"] = dict(self.params)
        return original_generate(self, input_df)

    monkeypatch.setattr(MACDHistogramMomentumSignalGenerator, "generate_signals", spy_generate)
    optimizer = HistogramParamOptimizer("510300.SH")

    optimized_df = optimizer._generate_signals(df, params)
    direct_df = MACDHistogramMomentumSignalGenerator(params).generate_signals(df)

    assert called["params"]["macd_fast"] == params["macd_fast"]
    assert optimized_df["target_position"].tolist() == direct_df["target_position"].tolist()
    assert optimized_df["hist_state"].tolist() == direct_df["hist_state"].tolist()


def test_walk_forward_validation_reports_train_and_validation_windows(monkeypatch):
    sample_data = _sample_market_data(days=180, start="2020-01-01").to_dict("records")

    def fake_get_data(etf_code, start_date=None, end_date=None):
        rows = []
        for row in sample_data:
            date = row["trade_date"]
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue
            rows.append(row)
        return rows

    monkeypatch.setattr("optimization.optimize_histogram_params.get_etf_daily_data", fake_get_data)

    optimizer = HistogramParamOptimizer("510300.SH")
    result = optimizer.walk_forward_validate(
        params=MACDHistogramMomentumSignalGenerator.default_params(),
        windows=[
            ("train_2020_2023", "20200101", "20200229"),
            ("validation_2024", "20200301", "20200430"),
            ("validation_2025_2026", "20200501", "20200630"),
        ],
    )

    assert [item["name"] for item in result["windows"]] == [
        "train_2020_2023",
        "validation_2024",
        "validation_2025_2026",
    ]
    assert all("total_return_pct" in item["metrics"] for item in result["windows"])
