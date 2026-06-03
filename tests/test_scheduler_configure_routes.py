import hashlib

import pytest
from fastapi.testclient import TestClient

import config
from api.main import app
from core import scheduler_settings_service


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        config,
        "AUTH_KEY_HASH",
        hashlib.sha256("test-auth-key".encode()).hexdigest(),
    )
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"auth_key": "test-auth-key"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


@pytest.mark.parametrize(
    ("path", "payload", "service_name"),
    [
        (
            "/api/data-update/scheduler/configure",
            {"enabled": True, "update_time": "bad-time"},
            "configure_data_update_schedule",
        ),
        (
            "/api/feishu/notification/configure",
            {"enabled": True, "times": ["bad-time"]},
            "configure_feishu_notification_schedule",
        ),
        (
            "/api/macd/optimization/schedule/configure",
            {"enabled": True, "time": "bad-time"},
            "configure_macd_optimization_schedule",
        ),
    ],
)
def test_configure_routes_map_value_error_to_http_400(
    monkeypatch, client, path, payload, service_name
):
    monkeypatch.setattr(
        scheduler_settings_service,
        service_name,
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("invalid schedule")),
    )

    response = client.post(path, json=payload)

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid schedule"}


@pytest.mark.parametrize(
    ("path", "payload", "service_name"),
    [
        (
            "/api/data-update/scheduler/configure",
            {"enabled": True, "update_time": "16:20"},
            "configure_data_update_schedule",
        ),
        (
            "/api/feishu/notification/configure",
            {"enabled": True, "times": ["09:35"]},
            "configure_feishu_notification_schedule",
        ),
        (
            "/api/macd/optimization/schedule/configure",
            {"enabled": True, "time": "22:15"},
            "configure_macd_optimization_schedule",
        ),
    ],
)
def test_configure_routes_map_runtime_error_to_http_500(
    monkeypatch, client, path, payload, service_name
):
    monkeypatch.setattr(
        scheduler_settings_service,
        service_name,
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("save failed")),
    )

    response = client.post(path, json=payload)

    assert response.status_code == 500
    assert response.json() == {"detail": "save failed"}


def test_macd_configure_route_passes_none_when_notify_feishu_missing(
    monkeypatch, client
):
    calls = []

    def configure(enabled, opt_time, notify_feishu):
        calls.append((enabled, opt_time, notify_feishu))
        return {"success": True, "message": "ok", "data": {}}

    monkeypatch.setattr(
        scheduler_settings_service,
        "configure_macd_optimization_schedule",
        configure,
    )

    response = client.post(
        "/api/macd/optimization/schedule/configure",
        json={"enabled": True, "time": "22:15"},
    )

    assert response.status_code == 200
    assert calls == [(True, "22:15", None)]
