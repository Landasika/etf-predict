"""
配置助手 - 帮助配置Tushare Token

运行此脚本来设置Tushare Token
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_tushare_token():
    """设置Tushare Token"""

    print("=" * 60)
    print("Tushare Token 配置助手")
    print("=" * 60)
    print()

    print("📖 什么是Tushare Token?")
    print("   Tushare是一个免费的财经数据接口，提供ETF、股票等数据")
    print("   Token是访问API的密钥")
    print()

    print("📝 如何获取Token?")
    print("   1. 访问: https://tushare.pro/register")
    print("   2. 注册账号（免费）")
    print("   3. 登录后访问: https://tushare.pro/user/token")
    print("   4. 复制你的Token")
    print()

    # 检查是否已配置
    import config
    if config.TUSHARE_TOKEN:
        print(f"✅ 当前已配置Token: {config.TUSHARE_TOKEN[:10]}...")
        print()
        choice = input("是否要重新配置? (y/N): ").strip().lower()
        if choice != 'y':
            print("保持现有配置")
            return

    print()
    print("请输入你的Tushare Token:")
    print("(按Enter取消)")

    token = input("> ").strip()

    if not token:
        print("❌ 已取消")
        return

    # 验证Token格式（通常是一串字符串）
    if len(token) < 10:
        print("⚠️  Token格式可能不正确，请检查")
        confirm = input("是否继续? (y/N): ").strip().lower()
        if confirm != 'y':
            return

    # 更新config.py
    config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.py')

    try:
        # 读取现有配置
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 替换TUSHARE_TOKEN
        import re
        pattern = r"TUSHARE_TOKEN\s*=\s*['\"].*['\"]"
        replacement = f"TUSHARE_TOKEN = '{token}'"

        if re.search(pattern, content):
            new_content = re.sub(pattern, replacement, content)
        else:
            # 如果没有找到，在文件末尾添加
            new_content = content + f"\n\n# Tushare配置\nTUSHARE_TOKEN = '{token}'\n"

        # 写回文件
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print()
        print("✅ Token已保存到 config.py")
        print(f"   Token: {token[:10]}...")
        print()
        print("🔄 请重启系统以使配置生效:")
        print("   python run.py")

    except Exception as e:
        print(f"❌ 保存失败: {e}")
        print()
        print("你可以手动编辑 config.py 文件:")
        print(f"   文件路径: {config_file}")
        print(f"   添加内容: TUSHARE_TOKEN = '{token}'")


if __name__ == '__main__':
    setup_tushare_token()
