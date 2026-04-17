"""
测试 Tushare 代理的不同配置方法
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import tushare as ts

def test_method_1():
    """方法1: 标准方式"""
    print("\n方法1: 标准方式")
    print("-" * 40)
    try:
        pro = ts.pro_api(config.TUSHARE_TOKEN)
        pro._DataApi__http_url = config.TUSHARE_PROXY_URL
        df = pro.index_basic(limit=1)
        print(f"✅ 成功！获取到 {len(df)} 条数据")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


def test_method_2():
    """方法2: 使用 request 参数"""
    print("\n方法2: 使用 token 参数")
    print("-" * 40)
    try:
        pro = ts.pro_api()
        pro._DataApi__http_url = config.TUSHARE_PROXY_URL
        pro._DataApi__token = config.TUSHARE_TOKEN
        df = pro.index_basic(limit=1)
        print(f"✅ 成功！获取到 {len(df)} 条数据")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


def test_method_3():
    """方法3: 使用环境变量"""
    print("\n方法3: 使用环境变量")
    print("-" * 40)
    try:
        import os
        os.environ['TUSHARE_TOKEN'] = config.TUSHARE_TOKEN
        pro = ts.pro_api(config.TUSHARE_TOKEN)
        pro._DataApi__http_url = config.TUSHARE_PROXY_URL
        df = pro.index_basic(limit=1)
        print(f"✅ 成功！获取到 {len(df)} 条数据")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


def test_method_4():
    """方法4: 代理 URL 带 token 参数"""
    print("\n方法4: 代理 URL 带 token 参数")
    print("-" * 40)
    try:
        proxy_url_with_token = f"{config.TUSHARE_PROXY_URL}?token={config.TUSHARE_TOKEN}"
        pro = ts.pro_api(config.TUSHARE_TOKEN)
        pro._DataApi__http_url = proxy_url_with_token
        df = pro.index_basic(limit=1)
        print(f"✅ 成功！获取到 {len(df)} 条数据")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


def test_method_5():
    """方法5: 仅设置代理 URL，不设置 token"""
    print("\n方法5: 仅设置代理 URL")
    print("-" * 40)
    try:
        pro = ts.pro_api(config.TUSHARE_TOKEN)
        # 尝试使用不同的属性名
        pro.http_url = config.TUSHARE_PROXY_URL
        df = pro.index_basic(limit=1)
        print(f"✅ 成功！获取到 {len(df)} 条数据")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


def test_stock_api():
    """测试股票 API（可能需要的接口不同）"""
    print("\n测试: 股票基本信息 API")
    print("-" * 40)
    try:
        pro = ts.pro_api(config.TUSHARE_TOKEN)
        pro._DataApi__http_url = config.TUSHARE_PROXY_URL
        df = pro.stock_basic(exchange='', list_status='L', limit=1)
        print(f"✅ 成功！获取到 {len(df)} 条数据")
        print(f"示例: {df.iloc[0]['ts_code']} - {df.iloc[0]['name']}")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


if __name__ == '__main__':
    print("=" * 50)
    print("Tushare 代理配置方法测试")
    print("=" * 50)
    print(f"\n配置信息:")
    print(f"  Token: {config.TUSHARE_TOKEN[:20]}...")
    print(f"  代理: {config.TUSHARE_PROXY_URL}")

    # 测试各种方法
    results = []

    results.append(("方法1: 标准方式", test_method_1()))
    results.append(("方法2: token参数", test_method_2()))
    results.append(("方法3: 环境变量", test_method_3()))
    results.append(("方法4: URL带token", test_method_4()))
    results.append(("方法5: 仅代理URL", test_method_5()))
    results.append(("股票API测试", test_stock_api()))

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

    print(f"\n成功: {success_count}/{len(results)}")

    if success_count == 0:
        print("\n⚠️ 所有方法都失败了，可能的原因：")
        print("  1. Token 不正确或已过期")
        print("  2. 代理服务器不可用")
        print("  3. 需要联系代理服务提供商获取正确的配置方法")
