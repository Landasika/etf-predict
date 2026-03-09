# 错误排查：刷新缓存失败

## 错误信息

```
刷新缓存失败: Unexpected token 'I', "Internal S"... is not valid JSON
```

## 原因分析

这个错误通常是由以下原因之一导致的：

### 1. 未登录或Session过期

**症状**:
- 访问页面时没有登录
- 浏览器关闭后重新打开，session已过期
- 长时间未操作，session失效

**解决方案**:
1. 访问 http://127.0.0.1:8000
2. 自动跳转到登录页面
3. 输入秘钥: `admin123`（开发环境默认）
4. 登录成功后再尝试刷新缓存

### 2. 服务器内部错误

**症状**:
- 已登录但仍然出现错误
- 查看浏览器控制台显示500错误
- 服务器日志显示异常

**解决方案**:
1. 查看服务器日志: `tail -f logs/*.log`
2. 检查数据库是否正常: `python -c "from core.database import engine; print(engine)"`
3. 重启服务器: `python run.py`

### 3. API认证问题

**症状**:
- 前端代码无法正确处理401响应
- Cookie未正确保存

**解决方案**:
1. 清除浏览器Cookie
2. 重新登录
3. 确保浏览器允许Cookie

## 快速修复步骤

### 步骤 1: 确认登录状态

```bash
# 1. 打开浏览器访问 http://127.0.0.1:8000
# 2. 如果跳转到登录页面，输入秘钥: admin123
# 3. 登录成功后，页面右上角应该显示 "🚪 登出" 按钮
```

### 步骤 2: 清除浏览器缓存

```bash
# Chrome/Edge:
# 1. 按 F12 打开开发者工具
# 2. 右键点击刷新按钮 → "清空缓存并硬性重新加载"
# 3. 或手动清除 Cookie: F12 → Application → Cookies → 删除所有

# Firefox:
# 1. 按 F12 打开开发者工具
# 2. 网络设置 → 禁用缓存
# 3. 或手动清除 Cookie
```

### 步骤 3: 重启服务器

```bash
# 按 Ctrl+C 停止服务器
# 重新启动
python run.py
```

## 验证修复

### 测试登录功能

1. 访问 http://127.0.0.1:8000
2. 应该自动跳转到 `/login`
3. 输入秘钥 `admin123`
4. 点击"登录系统"
5. 成功后应该跳转回主页

### 测试刷新缓存功能

1. 登录后，点击"🔄 刷新页面"按钮
2. 应该显示"刷新成功"的提示
3. 不应该再出现JSON解析错误

## 已修复的问题

### 前端代码增强

所有JavaScript文件已更新，添加了 `fetchAPI` 辅助函数：

- ✅ `static/js/home.js` - v75
- ✅ `static/js/macd_watchlist.js`
- ✅ `static/js/earnings.js` - v10
- ✅ `static/js/settings.js`

**新功能**:
- 自动检测401未认证响应
- 友好的错误提示
- 自动跳转到登录页面
- 更好的错误处理

## 常见问题

### Q1: 为什么会突然需要登录？

**A**: 认证系统使用浏览器session，关闭浏览器后会自动失效，这是正常的安全设计。

### Q2: 可以永久保持登录状态吗？

**A**: 可以修改 `api/main.py` 中的 `max_age` 参数：

```python
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET_KEY,
    max_age=3600,  # 设置为1小时（单位：秒）
    same_site="lax",
)
```

### Q3: 如何修改默认秘钥？

**A**: 编辑 `.env` 文件（或创建）：

```bash
SESSION_SECRET_KEY=your-random-secret-key
AUTH_KEY=your-new-access-key
```

然后重启服务器。

### Q4: 如何查看详细的错误日志？

**A**:
```bash
# 查看认证日志
tail -f logs/auth.log

# 查看应用日志（如果有的话）
tail -f logs/app.log

# 或查看服务器输出
python run.py
```

## 技术细节

### 错误原因详解

当用户未登录时，API认证中间件会返回401状态码：

```json
{
  "error": "未认证",
  "message": "请先登录系统",
  "code": "UNAUTHORIZED"
}
```

旧版前端代码直接调用 `response.json()` 而不检查状态码，导致：
1. 服务器返回401和JSON（正确）
2. 前端尝试解析JSON（成功）
3. 但某些情况下服务器返回HTML错误页面（500错误）
4. 前端尝试解析HTML为JSON，导致 `"Unexpected token 'I'"` 错误

新版代码使用 `fetchAPI` 辅助函数，正确处理所有HTTP状态码。

### 修改对比

**旧代码**:
```javascript
const response = await fetch('/api/watchlist/refresh-cache', {
    method: 'POST'
});
const result = await response.json(); // ❌ 未检查状态码
```

**新代码**:
```javascript
const result = await fetchAPI('/api/watchlist/refresh-cache', {
    method: 'POST'
}); // ✅ fetchAPI自动处理所有错误
```

## 获取帮助

如果问题仍然存在：

1. **检查日志**: `tail -f logs/*.log`
2. **查看浏览器控制台**: F12 → Console
3. **查看网络请求**: F12 → Network
4. **参考文档**:
   - `docs/AUTHENTICATION.md`
   - `docs/SECURITY_TESTING.md`

## 更新日期

2026-03-09
