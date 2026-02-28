"""
ETF预测系统数据库模块
仅包含ETF相关功能
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
import config
import json

# Database paths
DATABASE_PATH = config.DATABASE_PATH


def _init_batch_cache_table():
    """初始化批量数据缓存表"""
    conn = get_etf_connection()
    if not conn:
        return

    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_type TEXT NOT NULL,
            data_date TEXT NOT NULL,
            cache_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(cache_type, data_date)
        )
    ''')
    conn.commit()
    conn.close()


def get_batch_cache(cache_type: str, data_date: str) -> Optional[Dict]:
    """获取批量数据缓存

    Args:
        cache_type: 缓存类型 ('signals' 或 'backtest')
        data_date: 数据日期 (YYYYMMDD格式)

    Returns:
        缓存数据字典，如果不存在或过期返回None
    """
    conn = get_etf_connection()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute('''
        SELECT cache_data, created_at
        FROM batch_cache
        WHERE cache_type = ? AND data_date = ?
        ORDER BY created_at DESC
        LIMIT 1
    ''', (cache_type, data_date))

    result = cursor.fetchone()
    conn.close()

    if result:
        try:
            return json.loads(result['cache_data'])
        except:
            return None
    return None


def set_batch_cache(cache_type: str, data_date: str, data: Dict):
    """设置批量数据缓存

    Args:
        cache_type: 缓存类型 ('signals' 或 'backtest')
        data_date: 数据日期 (YYYYMMDD格式)
        data: 要缓存的数据字典
    """
    # 确保缓存表存在
    _init_batch_cache_table()

    conn = get_etf_connection()
    if not conn:
        return

    cursor = conn.cursor()
    cache_json = json.dumps(data, ensure_ascii=False)

    # 使用REPLACE INTO，如果存在则更新，不存在则插入
    cursor.execute('''
        REPLACE INTO batch_cache (cache_type, data_date, cache_data)
        VALUES (?, ?, ?)
    ''', (cache_type, data_date, cache_json))

    conn.commit()
    conn.close()


def clear_batch_cache(cache_type: Optional[str] = None):
    """清除批量数据缓存

    Args:
        cache_type: 缓存类型，如果为None则清除所有缓存
    """
    conn = get_etf_connection()
    if not conn:
        return

    cursor = conn.cursor()

    if cache_type:
        cursor.execute('DELETE FROM batch_cache WHERE cache_type = ?', (cache_type,))
    else:
        cursor.execute('DELETE FROM batch_cache')

    conn.commit()
    conn.close()


def get_latest_data_date() -> Optional[str]:
    """获取数据库中最新的交易日期

    Returns:
        最新交易日期字符串 (YYYYMMDD格式)，如果没有数据返回None
    """
    conn = get_etf_connection()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute('SELECT MAX(trade_date) as max_date FROM etf_daily')
    result = cursor.fetchone()
    conn.close()

    return result['max_date'] if result and result['max_date'] else None


def get_etf_connection():
    """Get connection to ETF database."""
    if not Path(DATABASE_PATH).exists():
        return None
    # 添加超时设置，防止数据库锁定导致段错误
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_etf_list(search: Optional[str] = None) -> List[Dict]:
    """Get list of all ETFs with optional search filter.

    Args:
        search: Optional search term to filter by name or code

    Returns:
        List of ETFs with code, name, exchange, and record count
    """
    conn = get_etf_connection()
    if not conn:
        return []

    cursor = conn.cursor()

    if search:
        # Search by code or name
        cursor.execute('''
            SELECT b.ts_code, b.extname, b.exchange, COUNT(d.ts_code) as count
            FROM etf_basic b
            LEFT JOIN etf_daily d ON b.ts_code = d.ts_code
            WHERE b.ts_code LIKE ? OR b.extname LIKE ? OR b.index_name LIKE ?
            GROUP BY b.ts_code
            ORDER BY b.ts_code
        ''', (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        # Get all ETFs
        cursor.execute('''
            SELECT b.ts_code, b.extname, b.exchange, COUNT(d.ts_code) as count
            FROM etf_basic b
            LEFT JOIN etf_daily d ON b.ts_code = d.ts_code
            GROUP BY b.ts_code
            ORDER BY b.ts_code
        ''')

    results = cursor.fetchall()
    conn.close()

    return [
        {
            'code': r['ts_code'],
            'name': r['extname'] or r['ts_code'],
            'exchange': r['exchange'],
            'count': r['count'] or 0
        }
        for r in results
    ]


def get_etf_kline_data(ts_code: str, start_date: Optional[str] = None,
                       end_date: Optional[str] = None, limit: int = 500) -> List[Dict]:
    """Get OHLC + volume data for an ETF.

    Args:
        ts_code: ETF code (e.g., '510330.SH')
        start_date: Start date in YYYYMMDD format (optional)
        end_date: End date in YYYYMMDD format (optional)
        limit: Maximum number of records to return

    Returns:
        List of daily data records
    """
    conn = get_etf_connection()
    if not conn:
        return []

    cursor = conn.cursor()

    query = '''
        SELECT trade_date as date, open, high, low, close, vol, amount
        FROM etf_daily
        WHERE ts_code = ?
    '''
    params = [ts_code]

    if start_date:
        query += ' AND trade_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND trade_date <= ?'
        params.append(end_date)

    query += ' ORDER BY trade_date DESC LIMIT ?'
    params.append(limit)

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    # Reverse to get ascending order
    data = [dict(r) for r in results]
    data.reverse()
    return data


def get_etf_info(ts_code: str) -> Optional[Dict]:
    """Get ETF basic information.

    Args:
        ts_code: ETF code

    Returns:
        ETF info dict or None if not found
    """
    conn = get_etf_connection()
    if not conn:
        return None

    cursor = conn.cursor()

    cursor.execute('''
        SELECT ts_code, extname, cname, index_code, index_name,
               setup_date, list_date, exchange, mgr_name, custod_name, etf_type
        FROM etf_basic
        WHERE ts_code = ?
    ''', (ts_code,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return dict(result)
    return None


def get_etf_data_range(ts_code: str) -> Optional[Dict]:
    """Get ETF data date range.

    Args:
        ts_code: ETF code

    Returns:
        Dict with min_date and max_date, or None if no data
    """
    conn = get_etf_connection()
    if not conn:
        return None

    cursor = conn.cursor()

    cursor.execute('''
        SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date
        FROM etf_daily
        WHERE ts_code = ?
    ''', (ts_code,))

    result = cursor.fetchone()
    conn.close()

    if result and result['min_date']:
        return {
            'min_date': result['min_date'],
            'max_date': result['max_date']
        }
    return None


def get_etf_daily_data(ts_code: str, start_date: str = None, end_date: str = None) -> Optional[List[Dict]]:
    """
    Get ETF daily OHLCV data for backtesting.

    Args:
        ts_code: ETF code (e.g., '510330.SH')
        start_date: Start date in YYYYMMDD format (optional)
        end_date: End date in YYYYMMDD format (optional)

    Returns:
        List of daily data records or None if database not available
    """
    conn = get_etf_connection()
    if not conn:
        return None

    cursor = conn.cursor()

    query = '''
        SELECT trade_date, open, high, low, close, vol
        FROM etf_daily
        WHERE ts_code = ?
    '''
    params = [ts_code]

    if start_date:
        query += ' AND trade_date >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND trade_date <= ?'
        params.append(end_date)

    query += ' ORDER BY trade_date ASC'

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return [dict(r) for r in results]


def get_data_statistics() -> Dict:
    """Get comprehensive data statistics for ETF database.

    Returns:
        Dictionary containing statistics for etf_basic, etf_daily
    """
    stats = {}

    # ETF database statistics
    try:
        conn = get_etf_connection()
        if conn:
            cursor = conn.cursor()

            # etf_basic
            cursor.execute('SELECT COUNT(*) as count FROM etf_basic')
            stats['etf_basic'] = cursor.fetchone()['count']

            # etf_daily
            cursor.execute('SELECT COUNT(*) as count FROM etf_daily')
            stats['etf_daily'] = cursor.fetchone()['count']
            if stats['etf_daily'] > 0:
                cursor.execute('SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date FROM etf_daily')
                etf_range = cursor.fetchone()
                stats['etf_daily_range'] = f"{etf_range['min_date']} 至 {etf_range['max_date']}"
            else:
                stats['etf_daily_range'] = "无数据"

            # etf with data
            cursor.execute('SELECT COUNT(DISTINCT ts_code) as count FROM etf_daily')
            stats['etf_with_daily_data'] = cursor.fetchone()['count']

            conn.close()
    except Exception as e:
        stats['etf_db_error'] = str(e)

    # Database file size
    import os
    stats['db_file'] = {}
    if os.path.exists(DATABASE_PATH):
        size_mb = os.path.getsize(DATABASE_PATH) / (1024 * 1024)
        stats['db_file']['etf.db'] = f"{size_mb:.2f} MB"
    else:
        stats['db_file']['etf.db'] = "不存在"

    return stats


def get_data_quality_report() -> Dict:
    """Generate comprehensive data quality report.

    Returns:
        Dictionary containing:
        - etf_missing_daily: ETFs without daily data (up to 20)
        - data_gaps: Number of ETFs with sparse data (<100 records)
        - stale_etfs: Number of ETFs not updated in 7 days
        - data_freshness: Last update time for each table
        - quality_score: Overall quality score (0-100)
    """
    report = {}
    etf_conn = get_etf_connection()

    try:
        if etf_conn:
            cursor = etf_conn.cursor()

            # 1. ETFs without daily data
            cursor.execute('''
                SELECT b.ts_code, b.extname
                FROM etf_basic b
                LEFT JOIN etf_daily d ON b.ts_code = d.ts_code
                WHERE d.ts_code IS NULL
                LIMIT 20
            ''')
            report['etf_missing_daily'] = [dict(r) for r in cursor.fetchall()]

            # 2. ETFs with sparse data (<100 records)
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM (
                    SELECT ts_code
                    FROM etf_daily
                    GROUP BY ts_code
                    HAVING COUNT(*) < 100
                )
            ''')
            report['data_gaps'] = cursor.fetchone()['count']

            # 3. ETFs not updated in 7 days
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM (
                    SELECT ts_code, MAX(trade_date) as last_date
                    FROM etf_daily
                    GROUP BY ts_code
                    HAVING last_date < date('now', '-7 days')
                )
            ''')
            report['stale_etfs'] = cursor.fetchone()['count']

            # 4. Data freshness - last update times
            report['data_freshness'] = {
                'etf_basic': get_table_last_update(DATABASE_PATH, 'etf_basic'),
                'etf_daily': get_table_last_update(DATABASE_PATH, 'etf_daily'),
            }
            etf_conn.close()

        # 5. Calculate quality score (0-100)
        score = 100
        if report.get('etf_missing_daily'):
            score -= min(len(report['etf_missing_daily']) * 2, 20)
        if report.get('data_gaps', 0) > 0:
            score -= min(report['data_gaps'] * 0.5, 15)
        if report.get('stale_etfs', 0) > 0:
            score -= min(report['stale_etfs'] * 0.3, 10)

        report['quality_score'] = max(0, round(score, 1))

    except Exception as e:
        report['error'] = str(e)

    return report


def get_table_last_update(db_path: str, table_name: str) -> Optional[str]:
    """Get the last update time for a table based on its data.

    Args:
        db_path: Path to the database file
        table_name: Name of the table to check

    Returns:
        Last update date string or None if unavailable
    """
    try:
        if not Path(db_path).exists():
            return None

        conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Try to find a date column and get the latest date
        if table_name == 'etf_daily':
            cursor.execute(f'SELECT MAX(trade_date) as last_date FROM {table_name}')
        elif table_name == 'etf_basic':
            cursor.execute(f'SELECT MAX(list_date) as last_date FROM {table_name}')
        else:
            cursor.execute(f'SELECT MAX(rowid) as last_date FROM {table_name}')

        result = cursor.fetchone()
        conn.close()

        return result['last_date'] if result and result['last_date'] else None

    except Exception:
        return None


def get_system_status() -> Dict:
    """Get system status information.

    Returns:
        Dictionary containing:
        - db_files: Database file sizes
        - uptime: System uptime in seconds
        - memory_usage: Current memory usage info
    """
    import os
    try:
        import psutil
    except ImportError:
        psutil = None

    from datetime import datetime

    status = {}

    try:
        # Database file sizes
        status['db_files'] = {}
        if os.path.exists(DATABASE_PATH):
            size_bytes = os.path.getsize(DATABASE_PATH)
            size_mb = size_bytes / (1024 * 1024)
            status['db_files']['etf.db'] = {
                'size_mb': round(size_mb, 2),
                'size_bytes': size_bytes
            }
        else:
            status['db_files']['etf.db'] = {'size_mb': 0, 'size_bytes': 0}

        # Process uptime and memory (if psutil available)
        if psutil:
            process = psutil.Process()
            create_time = process.create_time()
            uptime_seconds = datetime.now().timestamp() - create_time
            status['uptime_seconds'] = round(uptime_seconds, 2)

            # Memory usage
            memory_info = process.memory_info()
            status['memory'] = {
                'rss_mb': round(memory_info.rss / (1024 * 1024), 2),
                'vms_mb': round(memory_info.vms / (1024 * 1024), 2)
            }

            # System memory
            sys_memory = psutil.virtual_memory()
            status['system_memory'] = {
                'total_gb': round(sys_memory.total / (1024**3), 2),
                'available_gb': round(sys_memory.available / (1024**3), 2),
                'percent_used': sys_memory.percent
            }

    except Exception as e:
        status['error'] = str(e)

    return status
