"""
测试前端是否能正确加载配置
"""
import json

# 读取配置
with open('config.json', 'r') as f:
    config = json.load(f)

tushare_config = config.get('tushare', {})

print("=" * 50)
print("配置文件检查")
print("=" * 50)
print(f"\nToken: {tushare_config.get('token', '')[:20]}...")
print(f"代理 URL: {tushare_config.get('proxy_url', '')}")

print("\n" + "=" * 50)
print("前端输入框应该显示的值")
print("=" * 50)
print(f"\nToken 输入框: {tushare_config.get('token', '')[:8]}...")
print(f"代理 URL 输入框: {tushare_config.get('proxy_url', '')}")

print("\n" + "=" * 50)
print("请检查浏览器中的设置页面")
print("=" * 50)
print("""
步骤：
1. 访问 http://127.0.0.1:8000/settings
2. 按 Ctrl+Shift+R 强制刷新
3. 检查以下输入框：
   - Tushare Token: 应显示 etuDqwpso...
   - Tushare 代理 URL: 应显示 http://124.222.60.121:8020/

4. 如果代理 URL 输入框是空的：
   手动输入: http://124.222.60.121:8020/

5. 点击"测试连接"按钮

6. 查看服务器日志，应该显示：
   使用的 Tushare API URL: http://124.222.60.121:8020/

7. 如果测试成功，点击"保存设置"
""")
