#!/usr/bin/env python3
"""
批量优化自选ETF权重

从watchlist读取所有ETF，为每个ETF单独优化权重，
并自动更新watchlist配置文件。
"""

import sys
sys.path.append('/home/landasika/etf')

import json
import time
from pathlib import Path
from optimize_etf_advanced import AdvancedETFOptimizer


def load_watchlist():
    """加载自选列表"""
    watchlist_file = Path("data/watchlist_etfs.json")

    if not watchlist_file.exists():
        print(f"❌ 找不到自选列表文件: {watchlist_file}")
        return []

    with open(watchlist_file, 'r') as f:
        watchlist = json.load(f)

    return watchlist.get('etfs', [])


def update_watchlist_weights(etf_code: str, weights_file: Path):
    """更新watchlist中的权重配置"""
    watchlist_file = Path("data/watchlist_etfs.json")

    if not watchlist_file.exists():
        return False

    # 读取权重
    if not weights_file.exists():
        print(f"   ⚠️  权重文件不存在: {weights_file}")
        return False

    with open(weights_file, 'r') as f:
        weights = json.load(f)

    # 读取watchlist
    with open(watchlist_file, 'r') as f:
        watchlist = json.load(f)

    # 更新对应ETF的权重文件路径
    for etf in watchlist.get('etfs', []):
        if etf['code'] == etf_code:
            etf['weights_file'] = str(weights_file)
            etf['strategy'] = 'multifactor'  # 使用多因子策略
            etf['last_optimized'] = time.strftime('%Y-%m-%d %H:%M:%S')
            break

    # 保存
    with open(watchlist_file, 'w') as f:
        json.dump(watchlist, f, indent=2, ensure_ascii=False)

    print(f"   ✅ 已更新 {etf_code} 的权重配置")
    return True


def batch_optimize():
    """批量优化所有自选ETF"""
    print("\n" + "="*70)
    print("批量优化自选ETF权重")
    print("="*70)

    # 加载自选列表
    watchlist = load_watchlist()

    if not watchlist:
        print("❌ 自选列表为空，请先添加ETF到自选")
        return

    print(f"\n找到 {len(watchlist)} 个自选ETF:")
    for i, etf in enumerate(watchlist, 1):
        print(f"   {i}. {etf['code']} - {etf.get('name', 'N/A')}")

    # 询问是否继续
    response = input(f"\n是否开始优化? (y/n): ").strip().lower()
    if response != 'y':
        print("已取消")
        return

    # 批量优化
    print("\n开始批量优化...\n")
    results = {}

    for i, etf in enumerate(watchlist, 1):
        etf_code = etf['code']
        etf_name = etf.get('name', 'N/A')

        print(f"\n{'='*70}")
        print(f"[{i}/{len(watchlist)}] 优化 {etf_code} ({etf_name})")
        print(f"{'='*70}")

        try:
            # 创建优化器
            optimizer = AdvancedETFOptimizer(
                etf_code=etf_code,
                start_date='20230101',
                end_date=None,
                cv_folds=3,
                test_size=0.2
            )

            # 运行优化
            result = optimizer.run_optimization()

            if result:
                results[etf_code] = result

                # 更新watchlist配置
                weights_file = optimizer.output_dir / "best_weights.json"
                update_watchlist_weights(etf_code, weights_file)

            else:
                print(f"   ⚠️  {etf_code} 优化失败")

        except Exception as e:
            print(f"   ❌ {etf_code} 优化出错: {e}")
            import traceback
            traceback.print_exc()
            continue

        # 避免过热
        if i < len(watchlist):
            print(f"\n等待5秒后继续...")
            time.sleep(5)

    # 打印总结
    print("\n" + "="*70)
    print("批量优化完成")
    print("="*70)

    print(f"\n成功优化: {len(results)}/{len(watchlist)} 个ETF")

    if results:
        print("\n各ETF优化结果:")
        print(f"{'ETF代码':15s} {'收益率':>10s} {'夏普比率':>10s} {'胜率':>10s}")
        print("-"*70)

        for etf_code, result in results.items():
            metrics = result['backtest']['metrics']
            print(f"{etf_code:15s} "
                  f"{metrics['total_return_pct']:>+8.2f}% "
                  f"{metrics['sharpe_ratio']:>10.2f} "
                  f"{metrics['win_rate']*100:>9.1f}%")

        print(f"\n✅ 所有权重已保存到: optimized_weights/<ETF代码>/")
        print(f"✅ watchlist配置已自动更新")
        print(f"\n💡 提示：刷新前端页面即可看到优化后的效果")


def quick_optimize_single():
    """快速优化单个ETF"""
    print("\n" + "="*70)
    print("快速优化单个ETF")
    print("="*70)

    # 加载自选列表
    watchlist = load_watchlist()

    if not watchlist:
        print("❌ 自选列表为空")
        return

    print("\n可用的ETF:")
    for i, etf in enumerate(watchlist, 1):
        print(f"   {i}. {etf['code']} - {etf.get('name', 'N/A')}")

    # 选择ETF
    try:
        choice = input(f"\n请选择ETF编号 (1-{len(watchlist)}): ").strip()
        idx = int(choice) - 1

        if idx < 0 or idx >= len(watchlist):
            print("❌ 无效的选择")
            return

        etf = watchlist[idx]
        etf_code = etf['code']

    except ValueError:
        print("❌ 无效的输入")
        return

    # 询问优化参数
    print(f"\n优化参数设置:")
    print(f"   种群大小 (默认30，越大越慢但越准):")
    pop_input = input(f"   >> ").strip()
    population_size = int(pop_input) if pop_input else 30

    print(f"\n   迭代次数 (默认50，越大越慢但越准):")
    gen_input = input(f"   >> ").strip()
    generations = int(gen_input) if gen_input else 50

    print(f"\n开始优化 {etf_code}...")
    print(f"   种群大小: {population_size}")
    print(f"   迭代次数: {generations}")
    print(f"   预计耗时: {(population_size * generations / 1000):.1f}分钟\n")

    # 创建优化器
    optimizer = AdvancedETFOptimizer(
        etf_code=etf_code,
        start_date='20230101',
        end_date=None,
        cv_folds=3,
        test_size=0.2
    )

    # 运行优化
    result = optimizer.run_optimization()

    if result:
        # 更新watchlist
        weights_file = optimizer.output_dir / "best_weights.json"
        update_watchlist_weights(etf_code, weights_file)

        print(f"\n✅ {etf_code} 优化完成！")
        print(f"   权重文件: {weights_file}")
    else:
        print(f"\n❌ {etf_code} 优化失败")


def main():
    """主函数"""
    print("\n" + "="*70)
    print("ETF权重批量优化工具")
    print("="*70)

    print("\n请选择模式:")
    print("   1. 批量优化所有自选ETF (耗时较长)")
    print("   2. 快速优化单个ETF")

    choice = input("\n请输入选择 (1/2): ").strip()

    if choice == '1':
        batch_optimize()
    elif choice == '2':
        quick_optimize_single()
    else:
        print("❌ 无效的选择")


if __name__ == '__main__':
    main()
