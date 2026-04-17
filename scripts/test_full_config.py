"""
测试完整的 Tushare 代理配置
验证前端和后端的所有修改
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import tushare as ts


def test_config_loaded():
    """测试配置是否正确加载"""
    print("\n1. 测试配置加载")
    print("-" * 50)

    print(f"✓ Token: {config.TUSHARE_TOKEN[:20]}...")
    print(f"✓ 代理 URL: {config.TUSHARE_PROXY_URL}")

    if not config.TUSHARE_TOKEN:
        print("❌ Token 未配置")
        return False

    if not config.TUSHARE_PROXY_URL:
        print("⚠️  代理 URL 未配置（可选）")

    return True


def test_api_with_proxy():
    """测试 API 是否正确使用代理"""
    print("\n2. 测试 API 调用（使用代理）")
    print("-" * 50)

    try:
        # 初始化 API（模拟后端代码）
        pro = ts.pro_api(config.TUSHARE_TOKEN)

        # 设置代理 URL
        if config.TUSHARE_PROXY_URL:
            pro._DataApi__http_url = config.TUSHARE_PROXY_URL
            print(f"✓ 代理已设置: {config.TUSHARE_PROXY_URL}")

        # 测试调用
        df = pro.stock_basic(exchange='', list_status='L', limit=1)

        if not df.empty:
            print(f"✅ API 调用成功！获取到数据")
            print(f"   示例: {df.iloc[0]['ts_code']} - {df.iloc[0]['name']}")
            return True
        else:
            print("❌ 返回数据为空")
            return False

    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return False


def test_api_without_proxy():
    """测试不使用代理的情况"""
    print("\n3. 测试 API 调用（不使用代理）")
    print("-" * 50)

    try:
        # 不设置代理
        pro = ts.pro_api(config.TUSHARE_TOKEN)

        # 测试调用
        df = pro.stock_basic(exchange='', list_status='L', limit=1)

        if not df.empty:
            print(f"✅ API 调用成功！")
            return True
        else:
            print("⚠️  返回数据为空（可能需要代理）")
            return False

    except Exception as e:
        print(f"⚠️  不使用代理时失败（预期行为）: {str(e)[:50]}...")
        return False


def test_config_file():
    """测试配置文件内容"""
    print("\n4. 测试配置文件")
    print("-" * 50)

    try:
        import json
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config.json'
        )

        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        tushare_config = config_data.get('tushare', {})

        print(f"✓ 配置文件读取成功")
        print(f"  - Token: {tushare_config.get('token', '')[:20]}...")
        print(f"  - 代理 URL: {tushare_config.get('proxy_url', '')}")

        if not tushare_config.get('token'):
            print("❌ 配置文件中没有 Token")
            return False

        return True

    except Exception as e:
        print(f"❌ 配置文件读取失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 50)
    print("Tushare 代理配置完整测试")
    print("=" * 50)

    results = []

    # 运行测试
    results.append(("配置加载", test_config_loaded()))
    results.append(("API调用（代理）", test_api_with_proxy()))
    results.append(("API调用（无代理）", test_api_without_proxy()))
    results.append(("配置文件", test_config_file()))

    # 总结
    print("\n" + "=" * 50)
    print("测试结果总结")
    print("=" * 50)

    success_count = 0
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}")
        if success:
            success_count += 1

    print(f"\n通过: {success_count}/{len(results)}")

    if success_count == len(results):
        print("\n🎉 所有测试通过！配置正确")
    else:
        print("\n⚠️  部分测试失败，请检查配置")

    print("\n📋 前端使用说明:")
    print("1. 打开设置页面: http://127.0.0.1:8000/settings")
    print("2. 在 Tushare Token 输入框输入 Token")
    print("3. 在 Tushare 代理 URL 输入框输入: http://124.222.60.121:8020/")
    print("4. 点击'测试连接'按钮验证配置")
    print("5. 点击'保存设置'保存配置")


if __name__ == '__main__':
    main()
