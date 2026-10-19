"""
数据适配器 — 把 AStockDataCollector.historical_data 转成 run_backtest 所需的格式

关键差异:
- AStockDataCollector 返回的 DataFrame 中,date 是普通列
- run_backtest 期望 DatetimeIndex + 必要列 {open, high, low, close, volume}
"""
from __future__ import annotations
import logging
import pandas as pd
from typing import Optional, Dict

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# 基准指数(用于在权益曲线上叠加对比线)
# ---------------------------------------------------------------------------

# 默认的上证指数代码 — akshare 直接用 sh000001 即可
DEFAULT_BENCHMARK = 'sh000001'


def fetch_benchmark_ohlcv(
    symbol: str = DEFAULT_BENCHMARK,
    start: str = "",
    end: str = "",
) -> Optional[pd.DataFrame]:
    """
    拉基准指数的 OHLCV;失败返回 None,不抛异常。
    指数用 akshare 的 stock_zh_index_daily (collector 的 stock_zh_a_daily 不支持指数代码)。
    """
    try:
        import akshare as ak
        # 该接口只接受 sh000001 / sz399001 这类代码,且不带日期参数(返回全历史)
        raw = ak.stock_zh_index_daily(symbol=symbol)
        if raw is None or raw.empty:
            logger.warning(f"基准指数 {symbol} 数据为空")
            return None
        # 列名是 date/open/high/low/close/volume (英文,无重命名必要)
        for col in ('open', 'high', 'low', 'close', 'volume'):
            if col not in raw.columns:
                logger.warning(f"基准指数 {symbol} 缺列 {col}")
                return None
        raw['date'] = pd.to_datetime(raw['date'], errors='coerce')
        raw = raw.dropna(subset=['date']).set_index('date').sort_index()
        for col in ('open', 'high', 'low', 'close', 'volume'):
            raw[col] = pd.to_numeric(raw[col], errors='coerce')
        raw = raw.dropna(subset=['open', 'high', 'low', 'close'])
        # 日期切片
        if start:
            raw = raw.loc[raw.index >= pd.Timestamp(start)]
        if end:
            raw = raw.loc[raw.index <= pd.Timestamp(end)]
        if len(raw) < 5:
            logger.warning(f"基准指数 {symbol} 区间内有效行 < 5")
            return None
        return raw
    except Exception as e:
        logger.warning(f"拉基准指数 {symbol} 失败: {e}")
        return None


def build_benchmark_curve(
    benchmark_df: pd.DataFrame,
    initial_cash: float,
    equity_dates: list,
) -> pd.DataFrame:
    """
    把指数 OHLCV 归一化为"投入 initial_cash 全买指数"的资金曲线,
    对齐到主策略的 equity_dates(用前向填充填补非交易日)。

    Returns
    -------
    pd.DataFrame: columns = [date, benchmark_equity]
    """
    if benchmark_df is None or benchmark_df.empty:
        return pd.DataFrame(columns=['date', 'benchmark_equity'])

    # 起点 = equity 第一个交易日或之前最近一个指数交易日
    if not equity_dates:
        return pd.DataFrame(columns=['date', 'benchmark_equity'])

    start_ts = pd.Timestamp(equity_dates[0])
    end_ts = pd.Timestamp(equity_dates[-1])

    # 用首日 close 当锚点,等比归一化
    base = float(benchmark_df['close'].loc[benchmark_df.index <= start_ts].iloc[-1]) \
        if (benchmark_df.index <= start_ts).any() else float(benchmark_df['close'].iloc[0])

    if base <= 0:
        return pd.DataFrame(columns=['date', 'benchmark_equity'])

    # 切片到回测区间
    slice_df = benchmark_df.loc[(benchmark_df.index >= start_ts) & (benchmark_df.index <= end_ts)]
    if slice_df.empty:
        return pd.DataFrame(columns=['date', 'benchmark_equity'])

    out = pd.DataFrame({
        'date': slice_df.index.strftime('%Y-%m-%d'),
        'benchmark_equity': slice_df['close'].astype(float).values / base * initial_cash,
    })
    return out
