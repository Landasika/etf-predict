"""
飞书推送使用示例
展示如何在代码中调用飞书推送功能
"""
import asyncio
from core.feishu_notifier import get_feishu_notifier


async def example_signal_notification():
    """示例1: 发送策略信号通知"""
    notifier = get_feishu_notifier()

    # 检查是否启用
    if not notifier.is_enabled():
        print("飞书通知未启用")
        return

    # 发送信号提醒
    await notifier.send_signal_alert(
        etf_code="510330.SH",
        etf_name="沪深300ETF",
        signal="BUY",
        strategy="MACD激进策略"
    )

    print("✓ 信号提醒已发送")


async def example_data_update_notification():
    """示例2: 发送数据更新通知"""
    notifier = get_feishu_notifier()

    # 数据更新成功
    await notifier.send_data_update(
        success=True,
        count=52
    )

    # 数据更新失败
    await notifier.send_data_update(
        success=False,
        error="连接超时"
    )

    print("✓ 数据更新通知已发送")


async def example_error_alert():
    """示例3: 发送错误告警"""
    notifier = get_feishu_notifier()

    await notifier.send_error_alert(
        error_type="数据更新失败",
        error_message="API连接超时，请检查网络"
    )

    print("✓ 错误告警已发送")


async def example_custom_message():
    """示例4: 发送自定义消息"""
    notifier = get_feishu_notifier()

    # 发送自定义消息
    await notifier.send_message(
        message="📊 今日收益总结\n\n"
                 "总收益: +5.2%\n"
                 "盈利ETF: 45个\n"
                 "亏损ETF: 7个\n\n"
                 "时间: 2026-03-10 15:00:00"
    )

    print("✓ 自定义消息已发送")


async def example_multiple_bots():
    """示例5: 发送到指定机器人"""
    notifier = get_feishu_notifier()

    # 发送到默认机器人
    await notifier.send_message("这条消息发送到默认机器人")

    # 发送到指定机器人
    await notifier.send_message(
        message="这条消息发送到指定机器人",
        bot_id="bot_2"  # 指定机器人ID
    )

    print("✓ 多机器人消息已发送")


async def example_check_config():
    """示例6: 检查配置"""
    notifier = get_feishu_notifier()

    print("飞书配置状态:")
    print(f"  启用状态: {notifier.is_enabled()}")
    print(f"  默认机器人: {notifier.config.get('default_bot')}")
    print(f"  机器人数量: {len(notifier.config.get('bots', []))}")

    # 检查通知类型
    notifications = notifier.config.get('notifications', {})
    print(f"  通知类型:")
    print(f"    - 策略信号: {notifications.get('signal_alerts')}")
    print(f"    - 数据更新: {notifications.get('data_updates')}")
    print(f"    - 回测完成: {notifications.get('backtest_complete')}")
    print(f"    - 错误告警: {notifications.get('error_alerts')}")


# 在策略信号生成时集成
async def on_signal_generated(etf_code: str, etf_name: str, signal: str, strategy: str):
    """
    在策略信号生成时调用

    这个函数应该在策略信号生成的代码中调用
    """
    notifier = get_feishu_notifier()

    # 只在特定信号时推送（如BUY/SELL，不包括HOLD）
    if signal in ['BUY', 'SELL']:
        await notifier.send_signal_alert(
            etf_code=etf_code,
            etf_name=etf_name,
            signal=signal,
            strategy=strategy
        )


# 在数据更新完成时集成
async def on_data_updated(success: bool, count: int = 0, error: str = ""):
    """
    在数据更新完成时调用

    这个函数应该在数据更新的代码中调用
    """
    notifier = get_feishu_notifier()
    await notifier.send_data_update(success, count, error)


# 在回测完成时集成
async def on_backtest_completed(etf_code: str, total_return: float):
    """
    在回测完成时调用

    这个函数应该在回测完成的代码中调用
    """
    notifier = get_feishu_notifier()

    if notifier.is_enabled() and notifier.config.get('notifications', {}).get('backtest_complete'):
        await notifier.send_message(
            f"📈 回测完成通知\n\n"
            f"ETF代码: {etf_code}\n"
            f"总收益率: {total_return:.2f}%\n\n"
            f"时间: {notifier._get_current_time()}"
        )


# 在错误发生时集成
async def on_error(error_type: str, error_message: str):
    """
    在错误发生时调用

    这个函数应该在错误处理代码中调用
    """
    notifier = get_feishu_notifier()
    await notifier.send_error_alert(error_type, error_message)


# 运行所有示例
async def main():
    """运行所有示例"""
    print("=" * 50)
    print("飞书推送使用示例")
    print("=" * 50)

    # 示例1: 检查配置
    await example_check_config()

    # 示例2: 发送信号通知
    # await example_signal_notification()

    # 示例3: 发送数据更新通知
    # await example_data_update_notification()

    # 示例4: 发送错误告警
    # await example_error_alert()

    # 示例5: 发送自定义消息
    # await example_custom_message()

    # 示例6: 多机器人
    # await example_multiple_bots()

    print("\n提示: 取消上面的注释来运行各个示例")


if __name__ == "__main__":
    asyncio.run(main())
