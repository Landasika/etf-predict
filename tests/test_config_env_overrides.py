def test_config_env_overrides_macd_optimization_notify_feishu(monkeypatch):
    import config

    data = {
        "macd_optimization_schedule": {
            "enabled": False,
            "time": "23:00",
            "notify_feishu": False,
        }
    }

    monkeypatch.setenv("MACD_OPTIMIZATION_NOTIFY_FEISHU", "true")

    result = config._apply_env_overrides(data)

    assert result["macd_optimization_schedule"]["notify_feishu"] is True
