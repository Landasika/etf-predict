from fastapi.testclient import TestClient

import config
from api import data_service
from api.main import app


def test_data_service_health_returns_service_status_with_api_key(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-api-key")

    client = TestClient(app)
    response = client.get(
        "/api/data-service/health",
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "data-service",
        },
    }


def test_data_service_health_rejects_missing_api_key(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-api-key")

    client = TestClient(app)
    response = client.get("/api/data-service/health")

    assert response.status_code == 401
    assert response.json() == {
        "error": "未认证",
        "message": "无效的 API Key",
        "code": "UNAUTHORIZED",
    }


def test_data_service_health_rejects_wrong_api_key(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-api-key")

    client = TestClient(app)
    response = client.get(
        "/api/data-service/health",
        headers={"X-API-Key": "wrong-api-key"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": "未认证",
        "message": "无效的 API Key",
        "code": "UNAUTHORIZED",
    }


def test_data_service_health_rejects_empty_server_api_key(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "")

    client = TestClient(app)
    response = client.get("/api/data-service/health")

    assert response.status_code == 401
    assert response.json() == {
        "error": "未认证",
        "message": "无效的 API Key",
        "code": "UNAUTHORIZED",
    }


def test_data_service_daily_requires_symbol(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-api-key")

    client = TestClient(app)
    response = client.get(
        "/api/data-service/daily",
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "symbol is required"}


def test_data_service_daily_rejects_out_of_range_days(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-api-key")

    client = TestClient(app)
    response = client.get(
        "/api/data-service/daily",
        params={"symbol": "562360.SH", "days": 0},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "days must be between 1 and 1000"}


def test_data_service_daily_returns_bars_with_volume_mapping(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-api-key")
    monkeypatch.setattr(
        data_service,
        "get_latest_daily_bars",
        lambda symbol, days: [
            {
                "trade_date": "20240517",
                "open": 1.11,
                "high": 1.22,
                "low": 1.01,
                "close": 1.15,
                "vol": 123456,
            },
            {
                "trade_date": "20240516",
                "open": 1.05,
                "high": 1.16,
                "low": 1.0,
                "close": 1.1,
                "vol": 654321,
            },
        ],
        raising=False,
    )

    client = TestClient(app)
    response = client.get(
        "/api/data-service/daily",
        params={"symbol": "562360.SH", "days": 2},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "symbol": "562360.SH",
            "count": 2,
            "bars": [
                {
                    "trade_date": "20240517",
                    "open": 1.11,
                    "high": 1.22,
                    "low": 1.01,
                    "close": 1.15,
                    "volume": 123456,
                },
                {
                    "trade_date": "20240516",
                    "open": 1.05,
                    "high": 1.16,
                    "low": 1.0,
                    "close": 1.1,
                    "volume": 654321,
                },
            ],
        },
    }


def test_data_service_daily_returns_empty_bars_when_no_data(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-api-key")
    monkeypatch.setattr(
        data_service,
        "get_latest_daily_bars",
        lambda symbol, days: [],
        raising=False,
    )

    client = TestClient(app)
    response = client.get(
        "/api/data-service/daily",
        params={"symbol": "562360.SH"},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "symbol": "562360.SH",
            "count": 0,
            "bars": [],
        },
    }


def test_data_service_daily_returns_500_when_database_unavailable(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-api-key")
    monkeypatch.setattr(
        data_service,
        "get_latest_daily_bars",
        lambda symbol, days: None,
        raising=False,
    )

    client = TestClient(app)
    response = client.get(
        "/api/data-service/daily",
        params={"symbol": "562360.SH"},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "database unavailable"}
