#!/bin/bash
# 飞书推送问题排查脚本
# 在远程服务器 192.168.8.30 上运行此脚本

echo "=========================================="
echo "飞书推送问题排查"
echo "=========================================="
echo ""

echo "1. 检查代码版本"
echo "----------------------------------------"
cd /root/etf-predict 2>/dev/null || cd /root/etf-predict
git log -1 --oneline
echo ""

echo "2. 检查飞书配置"
echo "----------------------------------------"
python3 << 'PYEOF'
import json
try:
    with open('conf.json', 'r') as f:
        config = json.load(f)
        feishu = config.get('feishu', {})
        print(f"✓ conf.json 存在")
        print(f"  飞书启用: {feishu.get('enabled', False)}")
        bots = feishu.get('bots', [])
        print(f"  机器人数量: {len(bots)}")
        for bot in bots:
            print(f"  - {bot.get('name', bot.get('id', '未知'))}")
            print(f"    启用: {bot.get('enabled', False)}")
            app_id = bot.get('app_id', '')
            print(f"    App ID: {app_id[:15]}..." if app_id else "    App ID: 未配置")
            chat_id = bot.get('chat_id', '')
            print(f"    Chat ID: {chat_id[:15]}..." if chat_id else "    Chat ID: 未配置")
except Exception as e:
    print(f"❌ 读取conf.json失败: {e}")
PYEOF
echo ""

echo "3. 测试飞书连接"
echo "----------------------------------------"
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/root/etf-predict')

try:
    from feishu_bot import FeishuBot

    # 读取配置
    import json
    with open('conf.json', 'r') as f:
        config = json.load(f)

    feishu_config = config.get('feishu', {})
    bots = feishu_config.get('bots', [])

    if not feishu_config.get('enabled', False):
        print("❌ 飞书通知未启用")
        sys.exit(1)

    if not bots:
        print("❌ 未配置飞书机器人")
        sys.exit(1)

    bot_config = bots[0]

    if not all([bot_config.get('app_id'), bot_config.get('app_secret'), bot_config.get('chat_id')]):
        print("❌ 飞书机器人配置不完整")
        print(f"   App ID: {'已配置' if bot_config.get('app_id') else '未配置'}")
        print(f"   App Secret: {'已配置' if bot_config.get('app_secret') else '未配置'}")
        print(f"   Chat ID: {'已配置' if bot_config.get('chat_id') else '未配置'}")
        sys.exit(1)

    print("✓ 飞书配置完整")

    # 测试连接
    bot = FeishuBot(
        app_id=bot_config['app_id'],
        app_secret=bot_config['app_secret'],
        chat_id=bot_config['chat_id'],
        name=bot_config.get('name', 'test')
    )

    print("📤 发送测试消息...")
    result = bot.send_text_message("这是一条测试消息")

    if result.get('code') == 0:
        print("✅ 飞书消息发送成功！")
        msg_id = result.get('data', {}).get('message_id', '')
        print(f"   消息ID: {msg_id}")
    else:
        print(f"❌ 飞书消息发送失败")
        print(f"   错误码: {result.get('code')}")
        print(f"   错误信息: {result.get('msg')}")

except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

PYEOF
echo ""

echo "4. 检查调度器状态"
echo "----------------------------------------"
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/root/etf-predict')

try:
    from core.data_update_scheduler import get_scheduler
    scheduler = get_scheduler()
    status = scheduler.get_status()

    print(f"调度器运行中: {status['is_running']}")
    print(f"调度器启用: {status['enabled']}")

    feishu_notif = status.get('feishu_notification', {})
    print(f"飞书消息定时发送: {feishu_notif.get('enabled', False)}")

    if feishu_notif.get('enabled'):
        times = feishu_notif.get('times', [])
        print(f"发送时间: {', '.join(times)}")

    print()
    print("✓ 调度器状态检查完成")

except Exception as e:
    print(f"❌ 检查调度器失败: {e}")

PYEOF
echo ""

echo "5. 诊断持仓数据"
echo "----------------------------------------"
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/root/etf-predict')

try:
    from scripts.diagnose_holdings import main as diagnose_holdings
    diagnose_holdings()
except Exception as e:
    print(f"❌ 持仓诊断失败: {e}")
    import traceback
    traceback.print_exc()

PYEOF
echo ""

echo "6. 查看服务器日志"
echo "----------------------------------------"
echo "最近的错误日志:"
tail -20 logs/server.log 2>/dev/null | grep -i "error\|feishu\|failed" || echo "没有日志文件"
echo ""

echo "=========================================="
echo "排查完成"
echo "=========================================="
