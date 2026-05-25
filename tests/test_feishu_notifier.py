import json

from core.feishu_notifier import FeishuNotifier


def test_feishu_notifier_falls_back_to_env_when_conf_has_default_empty_bot(
    monkeypatch,
    tmp_path,
):
    conf_path = tmp_path / "conf.json"
    conf_path.write_text(
        json.dumps(
            {
                "feishu": {
                    "enabled": False,
                    "default_bot": "bot_1",
                    "bots": [
                        {
                            "id": "bot_1",
                            "name": "默认机器人",
                            "app_id": "",
                            "app_secret": "",
                            "chat_id": "",
                            "enabled": True,
                        }
                    ],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("core.feishu_notifier.CONF_FILE", conf_path)
    monkeypatch.setenv("BOT_1_NAME", "default")
    monkeypatch.setenv("BOT_1_APP_ID", "cli_env_app")
    monkeypatch.setenv("BOT_1_APP_SECRET", "env_secret")
    monkeypatch.setenv("BOT_1_CHAT_ID", "oc_env_chat")

    notifier = FeishuNotifier()

    assert notifier.is_enabled() is True
    assert notifier.get_bot() == {
        "id": "bot_1",
        "name": "default",
        "app_id": "cli_env_app",
        "app_secret": "env_secret",
        "chat_id": "oc_env_chat",
        "enabled": True,
    }
