# ETF预测系统 - 认证功能快速启动指南

## 🚀 快速开始（3分钟）

### 步骤 1: 配置环境变量（可选）

如需使用自定义秘钥，创建 `.env` 文件：

```bash
# 生成安全密钥（推荐）
python -c "import secrets; print('SESSION_SECRET_KEY=' + secrets.token_urlsafe(32))" > .env

# 添加你的访问秘钥
echo "AUTH_KEY=my-secret-key" >> .env
```

### 步骤 2: 启动系统

```bash
python run.py
```

系统将在 http://127.0.0.1:8000 启动

### 步骤 3: 登录系统

1. 浏览器访问 http://127.0.0.1:8000
2. 自动跳转到登录页面
3. 输入秘钥：
   - **开发环境默认**: `admin123`
   - **生产环境**: 你在 .env 中设置的秘钥
4. 点击"登录系统"

✅ 完成！现在可以正常使用所有功能。

---

## 🔑 默认秘钥

### 开发环境
```
SESSION_SECRET_KEY: change-this-in-production-please-use-env-var
AUTH_KEY: admin123
```

⚠️ **警告**: 生产环境请务必修改这些默认值！

---

## 📋 功能检查清单

登录后，你应该能够：

- ✅ 访问所有4个主页面（策略汇总、详细策略、收益情况、系统设置）
- ✅ 使用所有API接口（自动携带认证信息）
- ✅ 看到页面右上角的"🚪 登出"按钮
- ✅ 点击登出后返回登录页面

---

## 🛡️ 安全特性

1. **会话管理**: 浏览器关闭时自动登出
2. **防暴力破解**: 5次失败后锁定15分钟
3. **API保护**: 所有API需要认证
4. **安全日志**: 所有登录活动记录在 `logs/auth.log`

---

## 🧪 快速测试

### 测试登录功能
```bash
# 使用curl测试
curl -c cookies.txt -X POST \
  -d "auth_key=admin123" \
  http://127.0.0.1:8000/login

# 使用session访问API
curl -b cookies.txt http://127.0.0.1:8000/api/watchlist
```

### 查看登录日志
```bash
tail -f logs/auth.log
```

---

## 📚 详细文档

- **用户指南**: `docs/AUTHENTICATION.md`
- **安全测试**: `docs/SECURITY_TESTING.md`
- **实施总结**: `docs/IMPLEMENTATION_SUMMARY.md`

---

## ⚙️ 配置示例

### 开发环境 (.env.development)
```bash
SESSION_SECRET_KEY=dev-key-only
AUTH_KEY=dev123
```

### 生产环境 (.env.production)
```bash
# 使用生成的随机密钥
SESSION_SECRET_KEY=abc123xyz456...（64字符随机字符串）
AUTH_KEY=YourStr0ng!Pass@word
```

---

## 🔧 故障排除

### 问题 1: 无法登录
**解决方案**:
1. 检查秘钥是否正确
2. 查看 `logs/auth.log` 了解详细错误
3. 确认服务器正在运行

### 问题 2: 频繁被锁定
**解决方案**:
1. 等待15分钟自动解锁
2. 或重启服务器清除锁定记录

### 问题 3: API返回401错误
**解决方案**:
1. 确保已登录
2. 检查浏览器Cookie
3. 尝试重新登录

---

## 📞 获取帮助

如遇到问题：

1. 查看日志: `tail -f logs/*.log`
2. 检查配置: `cat .env`
3. 参考文档: `docs/AUTHENTICATION.md`

---

## ✨ 下一步

- 📖 阅读完整用户指南
- 🧪 运行安全测试
- 🔒 配置生产环境
- 📊 监控登录日志

**祝使用愉快！** 🎉
