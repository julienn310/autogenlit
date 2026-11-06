"""
对照实验:确认 trade_date 过滤器有效(用已知有数据的日期),
再逐日回溯,找出各数据源「最新可用交易日」。
"""
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=False)

from src.data.finchina_collector import _call_mcp  # noqa: E402


def rows_for(subtool, code, date_field, dstr, limit=5):
    args = {"target_stock": [code], "limit": limit, date_field: dstr}
    raw = _call_mcp("execute_tool", {"tool_name": subtool, "arguments": args}, request_id=92)
    content = (raw.get("result") or {}).get("content") or [{}]
    payload = json.loads(content[0].get("text", "{}"))
    status = payload.get("status") or {}
    recs = ((payload.get("data") or {}).get("records") or {})
    rows = recs.get("data") or []
    head = recs.get("headInfo") or []
    cols = [h.get("field") for h in head]
    dates = []
    for i, c in enumerate(cols):
        if c and ("date" in c.lower() or "day" in c.lower()):
            vals = []
            for r in rows:
                vals.append(r.get(c) if isinstance(r, dict) else (r[i] if i < len(r) else None))
            dates.append("%s=%s" % (c, vals))
    return status.get("code"), len(rows), "; ".join(dates)


def main():
    today = datetime.date.today()
    print("today = %s\n" % today)

    # 1) 对照:已知有数据的日期
    print("=== 对照测试 (过滤日期是否生效) ===")
    for subtool, field, code, d in [
        ("get_stock_capital_flow", "trade_date", "000001", "2026-11-05"),
        ("get_stock_capital_flow", "trade_date", "000001", "2026-11-04"),
        ("get_stock_capital_flow", "trade_date", "000001", "2026-11-03"),
        ("get_stock_margin_trading_details", "trade_date", "000001", "2026-11-05"),
    ]:
        code_, n, dates = rows_for(subtool, code, field, d)
        print("  %-34s %s -> code=%s rows=%d %s" % (subtool, d, code_, n, dates))

    # 2) 逐日回溯:找每个源最新可用日期
    print("\n=== 逐日回溯(最近 12 天) ===")
    days = [(today - datetime.timedelta(days=i)).isoformat() for i in range(0, 12)]
    for subtool, field, code, label in [
        ("get_stock_capital_flow", "trade_date", "000001", "资金流向"),
        ("get_stock_margin_trading_details", "trade_date", "000001", "融资融券"),
        ("search_stock_block_trades", "trade_date", "000001", "大宗交易"),
        ("search_stock_dragon_tiger_board", "declare_date", "000001", "龙虎榜"),
    ]:
        hits = []
        for d in days:
            try:
                _, n, _ = rows_for(subtool, code, field, d, limit=1)
            except Exception as e:
                hits.append((d, "EXC:%s" % type(e).__name__))
                continue
            if n > 0:
                hits.append((d, "%d行" % n))
        print("  %-8s %s" % (label, "  ".join("%s:%s" % h for h in hits)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
