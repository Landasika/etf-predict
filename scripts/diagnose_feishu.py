#!/usr/bin/env python3
"""
飞书配置诊断脚本
用于检查飞书机器人配置是否正确
"""
import json
import sys
from pathlib import Path

def check_feishu_config():
    """检查飞书配置"""
    print("=" * 60)
    print("飞书配置诊断")
    print("=" * 60)
    print()

    # 读取配置文件
    conf_path = Path(__file__).parent.parent / "conf.json"

    if not conf_path.exists():
        print("❌ conf.json 文件不存在！")
        print(f"   期望路径: {conf_path}")
        return False

    try:
        with open(conf_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ 读取 conf.json 失败: {e}")
        return False

    # 检查飞书配置
    if "feishu" not in config:
        print("❌ conf.json 中未找到 feishu 配置！")
        return False

    feishu_config = config["feishu"]
    print(f"✓ 找到飞书配置")
    print(f"  - 启用状态: {feishu_config.get('enabled', False)}")
    print()

    # 检查机器人列表
    bots = feishu_config.get("bots", [])
    if not bots:
        print("❌ 未配置任何飞书机器人！")
        return False

    print(f"✓ 找到 {len(bots)} 个机器人配置")
    print()

    # 检查每个机器人的配置
    all_valid = True
    for i, bot in enumerate(bots, 1):
        print(f"机器人 {i}: {bot.get('name', bot.get('id', '未知'))}")
        print("-" * 40)

        bot_id = bot.get('id', '')
        app_id = bot.get('app_id', '')
        app_secret = bot.get('app_secret', '')
        chat_id = bot.get('chat_id', '')
        enabled = bot.get('enabled', False)

        # 检查必需字段
        if not app_id:
            print("  ❌ app_id 未配置")
            all_valid = False
        else:
            if app_id.startswith('cli_'):
                print(f"  ✓ app_id: {app_id[:15]}... (格式正确)")
            else:
                print(f"  ⚠️  app_id: {app_id} (格式可能不正确，应以 'cli_' 开头)")
                all_valid = False

        if not app_secret:
            print("  ❌ app_secret 未配置")
            all_valid = False
        else:
            print(f"  ✓ app_secret: {app_secret[:10]}... (已配置)")

        if not chat_id:
            print("  ❌ chat_id 未配置")
            all_valid = False
        else:
            if chat_id.startswith('oc_'):
                print(f"  ✓ chat_id: {chat_id[:15]}... (格式正确)")
            else:
                print(f"  ⚠️  chat_id: {chat_id} (格式可能不正确，应以 'oc_' 开头)")
                all_valid = False

        print(f"  {'✓' if enabled else '❌'} 启用状态: {enabled}")
        print()

    # 尝试导入 feishu_bot 模块
    print("检查 feishu_bot 模块...")
    print("-" * 40)
    try:
        # 添加项目根目录到路径
        import sys
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from feishu_bot import FeishuBot
        print("  ✓ feishu_bot 模块已安装")
    except ImportError as e:
        print(f"  ❌ feishu_bot 模块导入失败: {e}")
        print("     请检查是否在项目根目录运行此脚本")
        all_valid = False
    print()

    # 尝试测试连接
    if all_valid and feishu_config.get('enabled'):
        print("尝试测试连接...")
        print("-" * 40)

        try:
            from core.feishu_notifier import get_feishu_notifier
            import asyncio

            async def test_connection():
                notifier = get_feishu_notifier()
                bot_id = feishu_config.get('default_bot', bots[0]['id'])
                result = await notifier.send_message("这是一条测试消息", bot_id)
                return result

            result = asyncio.run(test_connection())

            if result:
                print("  ✓ 测试消息发送成功！")
            else:
                print("  ❌ 测试消息发送失败")
                print("     请检查:")
                print("     1. app_id 和 app_secret 是否正确")
                print("     2. 机器人是否在飞书群组中")
                print("     3. 网络连接是否正常")
                all_valid = False
        except Exception as e:
            print(f"  ❌ 测试连接失败: {e}")
            import traceback
            traceback.print_exc()
            all_valid = False

    print()
    print("=" * 60)
    if all_valid:
        print("✅ 飞书配置检查通过！")
    else:
        print("❌ 飞书配置存在问题，请根据上述提示修复")
    print("=" * 60)

    return all_valid


if __name__ == "__main__":
    success = check_feishu_config()
    sys.exit(0 if success else 1)
