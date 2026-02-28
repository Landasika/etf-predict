# 快速开始指南

本指南帮助你在 5 分钟内启动 ETF 策略回测系统。

## 前置要求

- Python 3.8 或更高版本
- 2GB+ 可用磁盘空间
- 已有 ETF 数据库文件（etf.db）

## 步骤 1：安装依赖

```bash
cd etf-predict
pip install -r requirements.txt
```

如果安装失败，尝试：

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 步骤 2：准备数据库

### 选项 A：使用现有数据库（推荐）

```bash
# 将数据库文件复制到 data 目录
cp /path/to/your/etf.db data/

# 检查数据库
python init_db.py
```

### 选项 B：下载示例数据

如果你没有数据库，可以使用系统内置的下载功能：

```bash
# 编辑 config.py，设置你的 Tushare Token
# 然后运行
python scripts/download_etf_data.py
```

## 步骤 3：启动服务

```bash
python run.py
```

看到以下输出说明启动成功：

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

## 步骤 4：访问系统

打开浏览器访问：http://127.0.0.1:8001

你应该能看到策略汇总页面，显示 21 个 ETF 的实时信号。

## 常见启动问题

### 问题 1：端口被占用

```bash
# 错误信息
[Errno 98] error while attempting to bind on address ('0.0.0.0', 8001)

# 解决方法：修改 config.py 中的 API_PORT
API_PORT = 8002  # 改为其他端口
```

### 问题 2：模块未找到

```bash
# 错误信息
ModuleNotFoundError: No module named 'xxx'

# 解决方法：重新安装依赖
pip install -r requirements.txt
```

### 问题 3：数据库不存在

```bash
# 错误信息
FileNotFoundError: data/etf.db does not exist

# 解决方法：检查数据库文件路径
ls -la data/etf.db
```

## 下一步

### 添加你的第一个 ETF

1. 点击页面上的"添加 ETF"按钮
2. 输入 ETF 代码，例如：`510330.SH`（沪深300ETF）
3. 选择策略类型（推荐选择"MACD优化做T策略"）
4. 点击"确认添加"

### 查看策略信号

添加后，页面会自动刷新，显示该 ETF 的：
- 当前信号（买入/持有/卖出）
- 下个交易日操作建议
- 近一年收益率
- MACD 指标数值

### 自定义备注

点击表格中的"备注"列，可以添加个人笔记，例如：
- 长期持有
- 观望中
- 适合定投

备注会自动保存。

## 快速命令参考

```bash
# 启动服务
python run.py

# 检查数据质量
python scripts/check_data.py

# 查看数据库统计
python -c "from core.database import get_data_statistics; import json; print(json.dumps(get_data_statistics(), indent=2))"

# 优化单个 ETF 权重
cd optimization
python optimize_etf_advanced.py --etf_code 510330.SH
```

## 进阶使用

### 切换策略

在添加 ETF 时，可以选择三种策略：

1. **MACD 激进策略**：适合波动大的 ETF，频繁交易
2. **MACD 优化做T策略**：适合震荡市场，降低交易频率
3. **多因子量化策略**：需要先运行权重优化，适合长期投资

### 权重优化

```bash
cd optimization

# 优化单个 ETF
python optimize_etf_advanced.py --etf_code 510330.SH

# 批量优化自选列表
python batch_optimize_watchlist.py
```

### 导出自选列表

```bash
# 查看当前自选列表
cat data/watchlist_etfs.json
```

## 获取帮助

- 查看 [README.md](README.md) 了解完整功能
- 查看 [DEPLOYMENT.md](DEPLOYMENT.md) 了解部署细节
- 访问 http://127.0.0.1:8001/docs 查看 API 文档

## 下一步建议

1. ✅ 添加 5-10 个你感兴趣的 ETF
2. ✅ 尝试不同的策略类型
3. ✅ 运行权重优化
4. ✅ 观察一段时间，记录信号表现
5. ✅ 根据实际情况调整策略参数

祝你投资顺利！ 📈

---

**需要帮助？** 请提交 Issue 或查看文档目录。
