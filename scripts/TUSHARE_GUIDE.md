# Tushare 代理配置指南

## ✅ 配置完成

你的系统已成功配置 Tushare 代理服务器。

### 配置信息

- **Token**: etuDqwpsoXrvbGawRaPpOAweXoqZYcUztvxwIJEwWzQmLfVxovXGRSUFTlwpyKcD
- **代理服务器**: http://124.222.60.121:8020/
- **配置文件**: `config.json`

## 📝 使用方法

### 1. 测试连接

```bash
python scripts/test_tushare_proxy.py
```

### 2. 下载 ETF 数据

```bash
# 下载所有 ETF 列表和日线数据
python scripts/download_etf_data_tushare.py
```

### 3. 在代码中使用

```python
import sys
sys.path.append('..')
import config
import tushare as ts

# 初始化 API
pro = ts.pro_api(config.TUSHARE_TOKEN)

# 设置代理（关键步骤！）
if config.TUSHARE_PROXY_URL:
    pro._DataApi__http_url = config.TUSHARE_PROXY_URL

# 使用 API
df = pro.index_basic(limit=5)
print(df)
```

## 🔧 配置文件说明

`config.json` 中的 Tushare 配置：

```json
{
  "tushare": {
    "token": "你的Token",
    "proxy_url": "http://124.222.60.121:8020/"
  }
}
```

## ⚠️ 重要提示

1. **必须设置代理 URL**：如果不设置 `pro._DataApi__http_url`，将无法使用代理服务器
2. **Token 安全**：不要将 Token 提交到公开仓库
3. **代理可用性**：如果代理不可用，请联系代理服务提供商

## 📚 更多资源

- [Tushare 官方文档](https://tushare.pro/document/2)
- [代理服务文档](https://www.yuque.com/a493465197/fl1fxx/ixwtsutxwaf0chdc)

## 🐛 常见问题

### Q: 提示 Token 不对
A: 检查是否设置了代理 URL：
```python
pro._DataApi__http_url = "http://124.222.60.121:8020/"
```

### Q: 网络超时
A: 检查代理服务器是否可用，尝试：
```bash
curl http://124.222.60.121:8020/
```

### Q: 如何更新 Token
A: 编辑 `config.json` 文件，修改 `tushare.token` 字段

## 📊 数据下载示例

下载特定 ETF 的数据：

```python
from scripts.download_etf_data_tushare import download_etf_daily

# 下载沪深300 ETF 数据
download_etf_daily('510330.SH', start_date='20200101')
```
