# 🔍 快速测试指南 - Session和鉴权修复验证

## 准备工作

### 1. 重启服务器
```bash
# 按 Ctrl+C 停止当前服务器
# 然后重新启动
cd /home/landasika/etf-predict
python run.py
```

看到以下输出表示启动成功：
```
INFO:     Started server process [XXXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 2. 清除浏览器缓存
**重要**: 必须清除缓存才能加载新的JavaScript代码（v76）

- **Windows/Linux**: 按 `Ctrl + Shift + R`
- **Mac**: 按 `Cmd + Shift + R`
- 或手动清除: F12 → Application → Clear storage → Clear site data

---

## 测试步骤

### ✅ 测试1: 未认证访问主页

**步骤**:
1. 关闭所有浏览器窗口（清除session）
2. 重新打开浏览器
3. 访问 http://127.0.0.1:8000

**预期结果**:
- ✅ 自动跳转到 `/login`
- ✅ 显示登录页面
- ✅ URL显示 `http://127.0.0.1:8000/login`

**如果失败**:
- 检查服务器是否运行
- 清除浏览器Cookie
- 查看浏览器控制台(F12)的错误

---

### ✅ 测试2: 登录功能

**步骤**:
1. 在登录页面输入秘钥: `admin123`
2. 点击"登录系统"按钮

**预期结果**:
- ✅ 登录成功
- ✅ 自动跳转回主页 `/`
- ✅ 页面右上角显示 "🚪 登出" 按钮
- ✅ 页面正常加载数据

**如果失败**:
- 检查秘钥是否正确
- 查看服务器日志
- 尝试强制刷新浏览器

---

### ✅ 测试3: 页面访问

**步骤**:
登录后，依次访问以下页面：
1. http://127.0.0.1:8000/
2. http://127.0.0.1:8000/macd-watchlist
3. http://127.0.0.1:8000/profit
4. http://127.0.0.1:8000/settings

**预期结果**:
- ✅ 所有页面都能正常访问
- ✅ 不需要重复登录
- ✅ 每个页面右上角都有 "🚪 登出" 按钮
- ✅ 浏览器控制台无错误

**如果失败**:
- 检查session是否过期
- 查看浏览器控制台的网络请求
- 验证中间件是否正确配置

---

### ✅ 测试4: API调用

**步骤**:
1. 按 F12 打开开发者工具
2. 切换到 "Console" 标签
3. 刷新主页
4. 观察控制台输出

**预期结果**:
```
✅ home.js v76 已加载 - 修复session和鉴权问题
✅ DOMContentLoaded 事件触发
✅ 策略数据来自缓存/重新计算完成
```

**不应该出现的错误**:
- ❌ `AssertionError: SessionMiddleware must be installed...`
- ❌ `500 Internal Server Error`
- ❌ `Unexpected token 'I', "Internal S"... is not valid JSON`
- ❌ `加载信号数据失败`

**如果出现错误**:
- 检查是否强制刷新了浏览器
- 确认服务器已重启
- 查看Network标签的请求状态

---

### ✅ 测试5: 登出功能

**步骤**:
1. 点击页面右上角的 "🚪 登出" 按钮

**预期结果**:
- ✅ 清除session
- ✅ 跳转到登录页面
- ✅ 无法直接访问受保护的页面
- ✅ 浏览器控制台显示登出消息

---

### ✅ 测试6: Session过期后访问

**步骤**:
1. 登录系统
2. 点击 "🚪 登出"
3. 直接在浏览器输入 http://127.0.0.1:8000/

**预期结果**:
- ✅ 自动跳转到登录页面
- ✅ 提示需要登录
- ✅ 不显示页面内容

---

## 命令行测试

### 使用curl测试

```bash
# 测试1: 未认证访问API（应该返回401）
curl -i http://127.0.0.1:8000/api/watchlist/batch-signals

# 预期输出:
# HTTP/1.1 401 Unauthorized
# {"error":"未认证","message":"请先登录系统","code":"UNAUTHORIZED"}

# 测试2: 未认证访问主页（应该302重定向）
curl -I http://127.0.0.1:8000/

# 预期输出:
# HTTP/1.1 302 Found
# location: /login

# 测试3: 访问登录页面（应该正常）
curl -I http://127.0.0.1:8000/login

# 预期输出:
# HTTP/1.1 200 OK
```

---

## 浏览器开发者工具检查

### Console标签
应该看到：
```
✅ home.js v76 已加载 - 修复session和鉴权问题
✅ DOMContentLoaded 事件触发
```

**不应该有**：
- ❌ 红色错误消息
- ❌ 500错误
- ❌ AssertionError

### Network标签
检查API请求的状态码：
- `/api/watchlist/batch-signals`: 200 OK
- `/api/data/latest-date`: 200 OK
- 所有其他API: 200 OK

**不应该有**：
- ❌ 500 Internal Server Error
- ❌ 401 Unauthorized (登录后)

### Application标签
检查Cookie：
1. 切换到 "Application" 标签
2. 左侧选择 "Cookies"
3. 查看 `http://127.0.0.1:8000` 的Cookie
4. 应该看到 `session` Cookie

---

## 常见问题排查

### 问题1: 浏览器显示旧版本JavaScript

**症状**: 控制台显示 `home.js v75` 或更早版本

**解决**:
```bash
# 强制刷新浏览器
Ctrl + Shift + R (Windows/Linux)
Cmd + Shift + R (Mac)

# 或手动清除缓存
F12 → Application → Clear storage → Clear site data
```

### 问题2: 仍然看到500错误

**症状**: Network标签显示500 Internal Server Error

**解决**:
```bash
# 1. 确认服务器已重启
ps aux | grep python

# 2. 查看服务器日志
tail -f logs/server.log

# 3. 检查中间件配置
python -c "from api.main import app; print('✓ OK')"
```

### 问题3: 登录后立即退出

**症状**: 登录成功后马上跳转回登录页

**解决**:
```bash
# 1. 检查浏览器Cookie设置
# 确保允许Cookie

# 2. 清除所有Cookie
F12 → Application → Cookies → 右键 → Clear

# 3. 重新登录
```

### 问题4: API返回401但已登录

**症状**: 已登录但API调用仍然返回401

**解决**:
```bash
# 1. 检查session是否正确设置
F12 → Application → Cookies → 查看session值

# 2. 尝试重新登录
点击 "🚪 登出" → 重新登录

# 3. 检查中间件顺序
python -c "
from api.main import app
print('中间件数量:', len(app.user_middleware))
"
```

---

## 性能验证

### 响应时间检查

打开浏览器开发者工具 → Network标签，刷新页面：

**良好的性能**:
- 主页加载: < 1秒
- API请求: < 500ms
- 总体响应: < 2秒

**如果性能差**:
- 检查服务器CPU使用率
- 查看网络延迟
- 优化数据库查询

---

## 完整测试清单

使用此清单确保所有功能正常：

- [ ] 服务器正常启动
- [ ] 未认证访问主页 → 跳转到登录页
- [ ] 输入正确秘钥 → 登录成功
- [ ] 登录后能访问所有页面
- [ ] 所有页面右上角显示登出按钮
- [ ] API调用正常工作（200状态码）
- [ ] 浏览器控制台无错误
- [ ] 点击登出 → 跳转到登录页
- [ ] 登出后无法直接访问受保护页面
- [ ] JavaScript版本号为v76
- [ ] Session Cookie正确设置
- [ ] 服务器日志无错误

---

## 测试成功标准

✅ **所有测试通过**
✅ **无浏览器控制台错误**
✅ **无服务器错误日志**
✅ **用户体验流畅**

---

## 如果测试失败

1. **重启服务器**
   ```bash
   # Ctrl+C 停止
   python run.py
   ```

2. **强制刷新浏览器**
   ```
   Ctrl + Shift + R
   ```

3. **清除所有数据**
   ```
   F12 → Application → Clear storage → Clear site data
   ```

4. **查看文档**
   - `docs/SESSION_AUTH_FIX.md` - 完整修复报告
   - `docs/AUTHENTICATION.md` - 认证使用指南
   - `docs/TROUBLESHOOTING_QUICK.md` - 故障排除

---

**最后更新**: 2026-03-10
**版本**: v76
**状态**: ✅ 测试通过
