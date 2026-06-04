from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docker_compose_persists_feishu_config_file():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "./conf.json:/app/conf.json" in compose
