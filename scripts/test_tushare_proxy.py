"""
测试 Tushare 代理配置
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

def test_tushare_connection():
    """测试 Tushare 连接"""
    print("=" * 50)
    print("Tushare 代理配置测试")
    print("=" * 50)

    # 检查配置
    print("\n1. 检查配置...")
    if not config.TUSHARE_TOKEN:
        print("❌ 错误：请先在 config.json 中设置 tushare.token")
        return False

    print(f"✓ Token: {config.TUSHARE_TOKEN[:20]}...")
    if config.TUSHARE_PROXY_URL:
        print(f"✓ 代理URL: {config.TUSHARE_PROXY_URL}")
    else:
        print("⚠️  未配置代理URL，使用官方API")

    # 导入 tushare
    print("\n2. 导入 Tushare 库...")
    try:
        import tushare as ts
        print("✓ Tushare 库已安装")
    except ImportError:
        print("❌ 未安装 Tushare 库")
        print("   请运行: pip install tushare")
        return False

    # 初始化 API
    print("\n3. 初始化 API 客户端...")
    try:
        pro = ts.pro_api(config.TUSHARE_TOKEN)
        print("✓ API 客户端初始化成功")
    except Exception as e:
        print(f"❌ API 客户端初始化失败: {e}")
        return False

    # 设置代理
    if config.TUSHARE_PROXY_URL:
        print(f"\n4. 设置代理服务器...")
        try:
            pro._DataApi__http_url = config.TUSHARE_PROXY_URL
            print(f"✓ 代理已设置: {config.TUSHARE_PROXY_URL}")
        except Exception as e:
            print(f"❌ 设置代理失败: {e}")
            return False

    # 测试 API 调用
    print("\n5. 测试 API 调用（获取指数基础信息）...")
    try:
        df = pro.index_basic(limit=5)
        if df is not None and len(df) > 0:
            print(f"✓ API 调用成功！获取到 {len(df)} 条数据")
            print("\n前5条数据：")
            print(df[['ts_code', 'name', 'market']].to_string(index=False))
            return True
        else:
            print("❌ API 返回空数据")
            return False
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        print("\n可能的原因：")
        print("  1. Token 不正确或已过期")
        print("  2. 代理服务器不可用")
        print("  3. 网络连接问题")
        return False


if __name__ == '__main__':
    success = test_tushare_connection()

    print("\n" + "=" * 50)
    if success:
        print("✅ 所有测试通过！配置正确")
    else:
        print("❌ 测试失败，请检查配置")
    print("=" * 50)
