# 快速修复指南

## 问题：调度器状态接口500错误 + TUSHARE_TOKEN未配置

### ✅ 已修复

1. **安装了缺失的依赖库**:
   ```bash
   pip install schedule
   ```

2. **添加了Token状态检查API**

3. **添加了配置助手脚本**

### 📋 配置Tushare Token（必需）

#### 方法1: 使用配置助手（推荐）

```bash
cd /home/landasika/etf-predict
python scripts/setup_token.py
```

按提示操作：
1. 访问 https://tushare.pro/register 注册
2. 登录后访问 https://tushare.pro/user/token
3. 复制Token
4. 粘贴到配置脚本
5. 重启系统

#### 方法2: 手动配置

1. 编辑 `config.py`:
   ```bash
   vim config.py
   ```

2. 添加Token:
   ```python
   TUSHARE_TOKEN = '你的Token'
   ```

3. 保存并重启系统

### 🔄 重启系统

```bash
# 停止当前运行的系统（Ctrl+C）
# 然后重新启动
python run.py
```

### ✅ 验证配置

访问: http://127.0.0.1:8000

1. 点击"📥 立即更新数据"按钮
2. 如果Token已配置，会提示开始更新
3. 如果Token未配置，会显示配置指南

### 📊 功能说明

配置Token后，系统可以：
- ✅ 自动下载最新的ETF日线数据
- ✅ 每个交易日收盘后自动更新
- ✅ 通过前端界面手动触发更新
- ✅ 显示更新进度

### 📝 注意事项

1. **免费账号积分**: Tushare免费账号有积分限制
   - fund_daily接口需要至少5000积分
   - 免费账号可以通过签到、完成任务获取积分

2. **数据更新时间**: 建议15:05（收盘后5分钟）
   - Tushare数据通常在收盘后30分钟内更新
   - 可以设置稍晚的时间确保数据已发布

3. **系统运行**: 系统需要在更新时间运行
   - 如果系统关闭，定时任务不会执行
   - 可以随时点击"立即更新"手动更新

### 🆘 常见问题

**Q: Token从哪里获取？**
A: https://tushare.pro/user/token

**Q: 免费账号够用吗？**
A: 够用。免费账号通过签到可以积累积分，足够获取ETF数据。

**Q: 更新失败怎么办？**
A: 检查：
1. Token是否正确配置
2. 网络连接是否正常
3. Tushare服务是否可用
4. 查看日志：`tail -f logs/auto_update.log`

**Q: 如何查看更新进度？**
A:
- 前端：会显示进度条
- 日志：`tail -f logs/auto_update.log`

### 📚 相关文档

- Tushare文档: https://tushare.pro/document/2
- ETF数据接口: https://tushare.pro/document/2?doc_id=127
- 调度器使用指南: `SCHEDULER_GUIDE.md`
