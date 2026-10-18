"""
数据适配器 — 把 AStockDataCollector.historical_data 转成 run_backtest 所需的格式

关键差异:
- AStockDataCollector 返回的 DataFrame 中,date 是普通列
- run_backtest 期望 DatetimeIndex + 必要列 {open, high, low, close, volume}
"""
from __future__ import annotations
import pandas as pd
from typing import Optional, Dict


REQUIRED_COLS = ('open', 'high', 'low', 'close', 'volume')

# 防御性重命名映射 (历史数据可能含中文列名)
RENAME_MAP = {
    '日期': 'date', '开盘': 'open', '收盘': 'close',
    '最高': 'high', '最低': 'low', '成交量': 'volume',
    '成交额': 'amount',
}


def prepare_ohlcv(
    historical_data: pd.DataFrame,
    start: str,
    end: str,
    min_rows: int = 30,
) -> Optional[pd.DataFrame]:
    """
    把 AStockDataCollector 输出的扁平 DataFrame 转换为索引形式的 OHLCV。
    返回 None 表示数据不足。

    Parameters
    ----------
    historical_data : pd.DataFrame
        来自 AStockDataCollector.collect_stock_data()['historical_data']
    start, end : str
        'YYYY-MM-DD' 格式的起止日期
    min_rows : int
        至少需要的行数 (默认 30 天,MVP 阶段降低门槛)

    Returns
    -------
    pd.DataFrame or None
        索引为 DatetimeIndex,包含必需列
    """
    if historical_data is None or historical_data.empty:
        return None

    df = historical_data.copy()

    # 1) 防御性重命名
    for src, dst in RENAME_MAP.items():
        if src in df.columns and dst not in df.columns:
            df = df.rename(columns={src: dst})

    # 2) 校验必需列
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"historical_data 缺少列: {missing}")

    # 3) date → DatetimeIndex
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df = df.set_index('date').sort_index()

    # 4) 强制数值化
    for col in REQUIRED_COLS:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=list(REQUIRED_COLS))

    # 5) 日期切片
    start_dt = pd.Timestamp(start)
    end_dt = pd.Timestamp(end)
    df = df.loc[(df.index >= start_dt) & (df.index <= end_dt)]

    # 6) 去重
    df = df[~df.index.duplicated(keep='last')]

    if len(df) < min_rows:
        return None

    return df


def build_engine_input(
    historical_data: pd.DataFrame,
    symbol: str,
    start: str,
    end: str,
) -> Optional[Dict[str, pd.DataFrame]]:
    """
    把 AStockDataCollector 输出转为 run_backtest 所需格式:
        {symbol: DataFrame(DatetimeIndex + OHLCV)}
    """
    df = prepare_ohlcv(historical_data, start, end)
    if df is None:
        return None
    return {symbol: df}
