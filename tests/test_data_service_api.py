from fastapi.testclient import TestClient

import config
from api.main import app


def test_data_service_health_returns_service_status_with_api_key(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-api-key")

    with TestClient(app) as client:
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


def test_data_service_health_rejects_missing_api_key():
    with TestClient(app) as client:
        response = client.get("/api/data-service/health")

    assert response.status_code == 401
    assert response.json() == {
        "error": "未认证",
        "message": "无效的 API Key",
        "code": "UNAUTHORIZED",
    }
