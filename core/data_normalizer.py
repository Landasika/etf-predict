"""
数据单位归一化工具

统一不同Tushare接口返回的数据单位：
- fund_daily（历史接口）：vol单位是"手"，amount单位是"千元"
- rt_etf_k（实时接口）：vol单位是"股"，amount单位是"元"

存储到数据库前统一转换为：vol"手"，amount"千元"
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def normalize_data_units(df: pd.DataFrame, data_source: str = 'auto') -> pd.DataFrame:
    """
    归一化数据单位（统一转换为：vol"手"，amount"千元"）

    Args:
        df: 原始数据DataFrame
        data_source: 数据来源标识
            - 'fund_daily': 历史接口（vol已经是"手"，amount已经是"千元"）
            - 'rt_etf_k': 实时接口（vol需要除以100，amount需要除以1000）
            - 'auto': 自动检测（按行判断，根据数值大小判断）

    Returns:
        归一化后的DataFrame
    """
    if df.empty:
        return df

    df_copy = df.copy()

    if data_source == 'fund_daily':
        # 历史接口：无需转换
        logger.debug("历史数据，无需转换")
        pass

    elif data_source == 'rt_etf_k':
        # 实时接口：全部转换
        if 'vol' in df_copy.columns:
            df_copy['vol'] = df_copy['vol'] / 100
            logger.debug(f"单位转换: vol 股 -> 手 ({len(df_copy)}行)")

        if 'amount' in df_copy.columns:
            df_copy['amount'] = df_copy['amount'] / 1000
            logger.debug(f"单位转换: amount 元 -> 千元 ({len(df_copy)}行)")

    elif data_source == 'auto':
        # 自动检测：按行判断
        if 'vol' in df_copy.columns:
            # 创建转换标记：vol > 1亿 的行需要转换
            need_convert = df_copy['vol'] > 100_000_000
            convert_count = need_convert.sum()

            if convert_count > 0:
                logger.info(f"自动检测: {convert_count}/{len(df_copy)} 行需要转换（vol疑似'股'单位）")
                # 只转换需要转换的行
                df_copy.loc[need_convert, 'vol'] = df_copy.loc[need_convert, 'vol'] / 100

        if 'amount' in df_copy.columns:
            # 类似处理amount
            need_convert = df_copy['amount'] > 100_000_000
            convert_count = need_convert.sum()

            if convert_count > 0:
                logger.info(f"自动检测: {convert_count}/{len(df_copy)} 行需要转换（amount疑似'元'单位）")
                df_copy.loc[need_convert, 'amount'] = df_copy.loc[need_convert, 'amount'] / 1000

    return df_copy


def _detect_data_source(df: pd.DataFrame) -> str:
    """
    自动检测数据来源（通过数值大小判断）

    判断逻辑：
    - 如果vol超过1亿，很可能是实时接口的"股"单位
    - 如果amount超过1亿，很可能是实时接口的"元"单位

    Returns:
        'fund_daily' 或 'rt_etf_k'
    """
    # 检测vol
    if 'vol' in df.columns:
        max_vol = df['vol'].max()
        if max_vol > 100_000_000:  # 超过1亿，很可能是"股"单位
            logger.info(f"检测到实时接口数据（vol最大值: {max_vol/10000:.2f}万手，疑似'股'单位）")
            return 'rt_etf_k'

    # 检测amount
    if 'amount' in df.columns:
        max_amount = df['amount'].max()
        if max_amount > 100_000_000:  # 超过1亿，很可能是"元"单位
            logger.info(f"检测到实时接口数据（amount最大值: {max_amount/10000:.2f}万元，疑似'元'单位）")
            return 'rt_etf_k'

    # 默认认为是历史数据
    logger.debug("默认为历史数据（fund_daily）")
    return 'fund_daily'


def normalize_row_data(row_dict: dict, data_source: str = 'auto') -> dict:
    """
    归一化单行数据（用于实时数据等单条记录）

    Args:
        row_dict: 数据字典
        data_source: 数据来源（'fund_daily' 或 'rt_etf_k' 或 'auto'）

    Returns:
        归一化后的数据字典
    """
    result = row_dict.copy()

    # 自动检测
    if data_source == 'auto':
        # 简单判断：如果vol超过1亿，认为是实时数据
        if result.get('vol', 0) > 100_000_000:
            data_source = 'rt_etf_k'
        else:
            data_source = 'fund_daily'

    # 转换
    if data_source == 'rt_etf_k':
        if 'vol' in result and result['vol']:
            result['vol'] = result['vol'] / 100

        if 'amount' in result and result['amount']:
            result['amount'] = result['amount'] / 1000

    return result


# 便捷函数：直接归一化并保存到数据库
def save_normalized_data(df: pd.DataFrame, table_name: str, conn, data_source: str = 'auto'):
    """
    归一化数据并保存到数据库

    Args:
        df: 原始DataFrame
        table_name: 表名
        conn: 数据库连接
        data_source: 数据来源（自动检测或指定）
    """
    # 归一化
    df_normalized = normalize_data_units(df, data_source)

    # 保存
    df_normalized.to_sql(table_name, conn, if_exists='append', index=False)

    logger.info(f"✅ 已归一化并保存 {len(df_normalized)} 条数据到 {table_name}")


if __name__ == '__main__':
    # 测试代码
    import sqlite3
    from core.database import get_etf_connection

    print("=" * 70)
    print("数据单位归一化工具测试")
    print("=" * 70)

    # 测试自动检测
    test_data = {
        'trade_date': ['20260226', '20260225'],
        'ts_code': ['159755.SZ', '159755.SZ'],
        'vol': [373853100.0, 2812054.0],  # 第一条是"股"，第二条是"手"
        'amount': [411924975.0, 313201.295],
        'close': [1.095, 1.123]
    }

    df = pd.DataFrame(test_data)

    print("\n原始数据:")
    print(df)

    print("\n归一化后:")
    df_normalized = normalize_data_units(df, data_source='auto')
    print(df_normalized)

    print("\n验证:")
    print(f"第一条vol: {df_normalized['vol'].iloc[0]:.0f} 手 ({df_normalized['vol'].iloc[0]/10000:.2f}万手)")
    print(f"第二条vol: {df_normalized['vol'].iloc[1]:.0f} 手 ({df_normalized['vol'].iloc[1]/10000:.2f}万手)")
