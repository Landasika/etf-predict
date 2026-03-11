#!/usr/bin/env python3
"""
启用飞书消息定时发送
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_update_scheduler import get_scheduler

def main():
    print("=" * 60)
    print("飞书消息定时发送 - 状态检查")
    print("=" * 60)
    print()

    scheduler = get_scheduler()
    status = scheduler.get_status()

    print("📊 当前状态：")
    print(f"  调度器运行中: {status['is_running']}")
    print(f"  调度器已启用: {status['enabled']}")
    print(f"  数据更新时间: {status['update_time']}")

    feishu_notif = status.get('feishu_notification', {})
    print()
    print("📱 飞书消息定时发送：")
    print(f"  已启用: {feishu_notif.get('enabled', False)}")
    print(f"  发送时间: {', '.join(feishu_notif.get('times', []))}")

    notif_status = feishu_notif.get('status', {})
    print(f"  正在发送: {notif_status.get('is_sending', False)}")
    print(f"  最后发送: {notif_status.get('last_send', '从未发送')}")
    print(f"  最后结果: {notif_status.get('last_result', '无')}")

    print()
    print("=" * 60)

    if not feishu_notif.get('enabled', False):
        print("⚠️  飞书消息定时发送未启用！")
        print()
        response = input("是否要启用？(y/n): ").strip().lower()

        if response == 'y':
            # 设置默认发送时间
            times = ["09:40", "10:40", "11:40", "13:40", "14:40"]
            scheduler.set_feishu_notification_times(times)
            scheduler.set_feishu_notification_enabled(True)

            print()
            print("✅ 飞书消息定时发送已启用！")
            print(f"   发送时间: {', '.join(times)}")
            print()
            print("注意：如果调度器未运行，请先在设置页面启用自动更新")
        else:
            print("❌ 未启用")
    else:
        print("✅ 飞书消息定时发送已启用")

    print("=" * 60)

if __name__ == "__main__":
    main()
