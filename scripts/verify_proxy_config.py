"""
验证所有代理配置是否正确
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def check_config_file():
    """检查配置文件"""
    print("\n1. 检查配置文件")
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

        has_token = bool(tushare_config.get('token'))
        has_proxy = bool(tushare_config.get('proxy_url'))

        print(f"✓ 配置文件存在")
        print(f"  Token: {'✓ 已配置' if has_token else '❌ 未配置'}")
        print(f"  代理 URL: {'✓ 已配置' if has_proxy else '⚠️  未配置'}")

        if has_proxy:
            print(f"  代理地址: {tushare_config['proxy_url']}")

        return has_token

    except Exception as e:
        print(f"❌ 配置文件读取失败: {e}")
        return False


def check_config_module():
    """检查配置模块"""
    print("\n2. 检查配置模块")
    print("-" * 50)

    try:
        print(f"✓ config 模块导入成功")
        print(f"  TUSHARE_TOKEN: {'✓ 已配置' if config.TUSHARE_TOKEN else '❌ 未配置'}")
        print(f"  TUSHARE_PROXY_URL: {'✓ 已配置' if config.TUSHARE_PROXY_URL else '⚠️  未配置'}")

        if config.TUSHARE_PROXY_URL:
            print(f"  代理地址: {config.TUSHARE_PROXY_URL}")

        return bool(config.TUSHARE_TOKEN)

    except Exception as e:
        print(f"❌ 配置模块检查失败: {e}")
        return False


def check_api_test_token():
    """检查 API 测试 Token 代码"""
    print("\n3. 检查 API 测试代码")
    print("-" * 50)

    try:
        # 读取 api/main.py
        api_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'api', 'main.py'
        )

        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否包含 proxy_url 处理
        has_proxy_param = 'proxy_url' in content and 'data.get' in content
        has_proxy_setting = 'pro._DataApi__http_url = proxy_url' in content

        if has_proxy_param and has_proxy_setting:
            print("✓ API 测试代码支持代理")
            return True
        else:
            print("❌ API 测试代码缺少代理支持")
            return False

    except Exception as e:
        print(f"❌ API 代码检查失败: {e}")
        return False


def check_auto_update_script():
    """检查自动更新脚本"""
    print("\n4. 检查自动更新脚本")
    print("-" * 50)

    try:
        script_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scripts', 'auto_update_data.py'
        )

        with open(script_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否使用配置的代理
        uses_config_proxy = 'config.TUSHARE_PROXY_URL' in content
        has_fallback = content.count('http://lianghua.nanyangqiankun.top') <= 2  # 作为后备

        if uses_config_proxy:
            print("✓ 自动更新脚本使用配置代理")
            if has_fallback:
                print("✓ 保留了后备默认代理（向后兼容）")
            return True
        else:
            print("❌ 自动更新脚本未使用配置代理")
            return False

    except Exception as e:
        print(f"❌ 自动更新脚本检查失败: {e}")
        return False


def check_download_script():
    """检查下载脚本"""
    print("\n5. 检查数据下载脚本")
    print("-" * 50)

    try:
        script_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scripts', 'download_etf_data.py'
        )

        with open(script_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否使用配置的代理
        uses_config_proxy = 'config.TUSHARE_PROXY_URL' in content

        if uses_config_proxy:
            print("✓ 数据下载脚本使用配置代理")
            return True
        else:
            print("❌ 数据下载脚本未使用配置代理")
            return False

    except Exception as e:
        print(f"❌ 数据下载脚本检查失败: {e}")
        return False


def check_frontend():
    """检查前端配置"""
    print("\n6. 检查前端配置")
    print("-" * 50)

    try:
        # 检查 HTML
        html_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'templates', 'settings.html'
        )

        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # 检查 JS
        js_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'js', 'settings.js'
        )

        with open(js_file, 'r', encoding='utf-8') as f:
            js_content = f.read()

        has_proxy_input = 'tushareProxyUrl' in html_content
        has_proxy_js = 'proxy_url' in js_content and 'tushareProxyUrl' in js_content

        if has_proxy_input:
            print("✓ HTML 有代理 URL 输入框")
        else:
            print("❌ HTML 缺少代理 URL 输入框")

        if has_proxy_js:
            print("✓ JS 支持代理 URL")
        else:
            print("❌ JS 不支持代理 URL")

        return has_proxy_input and has_proxy_js

    except Exception as e:
        print(f"❌ 前端检查失败: {e}")
        return False


def main():
    """运行所有检查"""
    print("=" * 50)
    print("Tushare 代理配置验证")
    print("=" * 50)

    results = []

    # 运行检查
    results.append(("配置文件", check_config_file()))
    results.append(("配置模块", check_config_module()))
    results.append(("API测试代码", check_api_test_token()))
    results.append(("自动更新脚本", check_auto_update_script()))
    results.append(("数据下载脚本", check_download_script()))
    results.append(("前端配置", check_frontend()))

    # 总结
    print("\n" + "=" * 50)
    print("验证结果总结")
    print("=" * 50)

    success_count = 0
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}")
        if success:
            success_count += 1

    print(f"\n通过: {success_count}/{len(results)}")

    if success_count == len(results):
        print("\n🎉 所有检查通过！代理配置完整")
        print("\n下一步:")
        print("1. 重新启动服务器")
        print("2. 访问 http://127.0.0.1:8000/settings")
        print("3. 测试代理连接")
        print("4. 点击'立即更新数据'验证功能")
    else:
        print("\n⚠️  部分检查失败，请查看详情")


if __name__ == '__main__':
    main()
