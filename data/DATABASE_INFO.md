# ETF数据库说明

## 数据库文件

**文件位置**: `data/etf.db`
**文件大小**: 197MB
**复制时间**: 2026-02-16

## 数据库内容

### ETF基本信息
- **ETF数量**: 1,435个
- **覆盖范围**: 沪深两市所有ETF

### 日线数据
- **数据条数**: 1,080,731条
- **数据范围**: 2020-01-02 ~ 2026-02-13
- **包含字段**:
  - 交易日期 (trade_date)
  - 开盘价 (open)
  - 最高价 (high)
  - 最低价 (low)
  - 收盘价 (close)
  - 成交量 (vol)
  - 成交额 (amount)

## 支持的ETF

系统已配置52个主流ETF，包括：

### 宽基指数
- 510330.SH - 沪深300ETF
- 159672.SZ - 创业板ETF
- 510050.SH - 上证50ETF

### 行业ETF
- 512760.SH - 芯片ETF
- 512170.SH - 医疗ETF
- 512880.SH - 证券ETF
- 512800.SH - 银行ETF
- 515980.SH - 人工智能ETF
- 515700.SH - 新能车ETF
- 515790.SH - 光伏ETF

### 商品类
- 518880.SH - 黄金ETF
- 159985.SZ - 豆粕ETF
- 510170.SH - 大宗商品ETF

### 跨境ETF
- 513520.SH - 日经ETF
- 513660.SH - 恒生ETF
- 159941.SZ - 纳指ETF

完整列表见：[data/watchlist_etfs.json](watchlist_etfs.json)

## 数据质量

### 数据完整性
- ✅ 所有52个配置的ETF都有完整数据
- ✅ 数据时间跨度超过6年
- ✅ 包含完整的OHLCV数据
- ✅ 无明显数据缺失

### 数据更新
- 最新数据日期: 2026-02-13
- 建议定期更新以保持数据时效性

## 数据库维护

### 更新数据

方法1: 使用Tushare更新（需要Token）
```bash
python scripts/download_etf_data.py
```

方法2: 从原系统复制
```bash
cp /home/landasika/etf/data/etf.db data/etf.db
```

### 检查数据质量
```bash
python scripts/check_data.py
```

### 检查特定ETF
```bash
python scripts/check_data.py 510330.SH
```

## 数据库结构

### etf_basic 表
```sql
CREATE TABLE etf_basic (
    ts_code TEXT PRIMARY KEY,      -- ETF代码
    name TEXT,                     -- ETF名称
    extname TEXT,                  -- ETF扩展名称
    market TEXT,                   -- 市场
    exchange TEXT,                 -- 交易所
    list_date TEXT,                -- 上市日期
    fund_type TEXT                 -- 基金类型
);
```

### etf_daily 表
```sql
CREATE TABLE etf_daily (
    ts_code TEXT,                  -- ETF代码
    trade_date TEXT,               -- 交易日期
    open REAL,                     -- 开盘价
    high REAL,                     -- 最高价
    low REAL,                      -- 最低价
    close REAL,                    -- 收盘价
    vol REAL,                      -- 成交量
    amount REAL,                   -- 成交额
    PRIMARY KEY (ts_code, trade_date)
);
```

## 性能优化

数据库已创建以下索引以提升查询性能：

```sql
-- 按日期索引
CREATE INDEX idx_etf_daily_date ON etf_daily(trade_date);

-- 按代码索引
CREATE INDEX idx_etf_daily_code ON etf_daily(ts_code);

-- 复合索引
CREATE INDEX idx_etf_daily_code_date ON etf_daily(ts_code, trade_date);
```

## 数据备份

### 自动备份脚本
```bash
#!/bin/bash
# backup_db.sh

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

cp data/etf.db $BACKUP_DIR/etf_$TIMESTAMP.db

# 保留最近30天的备份
find $BACKUP_DIR -name "etf_*.db" -mtime +30 -delete

echo "备份完成: etf_$TIMESTAMP.db"
```

### 恢复数据库
```bash
cp backups/etf_20260216_120000.db data/etf.db
```

## 注意事项

1. **文件大小**: 数据库文件197MB，Git上传时会被忽略
2. **定期更新**: 建议每周更新一次数据
3. **数据备份**: 定期备份数据库文件
4. **权限管理**: 确保数据库文件有正确的读写权限

## 数据来源

- **原始数据**: Tushare Pro API
- **数据周期**: 日线数据
- **数据质量**: 官方数据源，可靠准确

## 相关文档

- [下载脚本](../scripts/download_etf_data.py)
- [检查脚本](../scripts/check_data.py)
- [初始化脚本](../init_db.py)

---

**最后更新**: 2026-02-16
**数据状态**: ✅ 完整
**可以使用**: ✅ 是
