"""
检查「个股交易数据」各数据源的最新日期(T+0 可见性验证)。

对每只测试股票,逐个调用 MCP 子工具,取最新一条记录里的日期字段,
并跟"今天"比较,判断当天收盘后能否看到当天数据。

用法: python scripts/check_data_freshness.py [股票代码...]
"""
import datetime
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=False)

from src.data import finchina_collector as fc  # noqa: E402

TODAY = datetime.date.today()

# (tab 名, 取数函数, 日期字段候选)
SOURCES = [
    ("资金流向", fc.fetch_capital_flow, ["trade_date", "date"]),
    ("融资融券", fc.fetch_margin_trading, ["trade_date", "date"]),
    ("大宗交易", fc.fetch_block_trades, ["trade_date", "date"]),
    ("龙虎榜", fc.fetch_dragon_tiger_board, ["declare_date", "trade_date", "date"]),
    ("股东增减持", fc.fetch_shareholders_trading, ["publish_date", "trade_date", "date"]),
    ("高管增减持", fc.fetch_executive_trading, ["publish_date", "trade_date", "date"]),
    ("股票回购", fc.fetch_repurchase, ["announce_date", "publish_date", "trade_date", "date"]),
]


def pick_date_field(df):
    for c in df.columns:
        if any(k in c.lower() for k in ("date", "day")):
            return c
    return None


def latest_date(df):
    if df is None or df.empty:
        return None, None
    col = pick_date_field(df)
    if not col:
        return None, None
    try:
        s = df[col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        s = s[s.str.len() >= 8]
        if s.empty:
            return col, None
        return col, s.max()
    except Exception:
        return col, None


def main():
    codes = sys.argv[1:] or ["000001", "600519", "300750"]
    print("今天 = %s (%s)" % (TODAY, TODAY.strftime("%A")))
    print("=" * 78)

    for code in codes:
        print("\n### %s" % code)
        for name, fn, _ in SOURCES:
            try:
                df = fn(code, 30)
            except Exception as e:
                print("  %-10s ERROR  %s: %s" % (name, type(e).__name__, str(e)[:80]))
                continue
            if df is None or df.empty:
                print("  %-10s (空)" % name)
                continue
            col, latest = latest_date(df)
            if not latest:
                print("  %-10s 无日期字段 | cols=%s" % (name, list(df.columns)[:6]))
                continue
            try:
                d = datetime.date.fromisoformat(latest[:10])
                lag = (TODAY - d).days
                tag = "当天!" if lag == 0 else ("T+%d" % lag if lag < 0 else "T-%d" % lag)
            except Exception:
                tag = "?"
            print("  %-10s 最新=%s (%s)  lag=%s" % (name, latest, col, tag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
