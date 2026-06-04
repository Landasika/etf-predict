from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docker_compose_persists_feishu_config_file():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "./conf.json:/app/conf.json" in compose


def test_docker_compose_exposes_macd_optimization_feishu_switch():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "MACD_OPTIMIZATION_NOTIFY_FEISHU=${MACD_OPTIMIZATION_NOTIFY_FEISHU:-false}" in compose
