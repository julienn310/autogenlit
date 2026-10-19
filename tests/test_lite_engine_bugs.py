"""
回归测试:修复 lite_engine 净值 < -100% + 逐笔 P&L 与曲线不一致 两个 bug
- Bug A:持仓权益用 cash + unrealized_pnl → 改成 cash + market_value
- Bug B:平仓用 cash += pnl(成本被扣两次) → 改成 cash ± shares*price
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategy.lite_engine import BacktestConfig, run_backtest


def make_df(prices):
    """把价格列表构造成 OHLCV DataFrame,索引是连续交易日"""
    dates = pd.bdate_range("2026-01-01", periods=len(prices))
    df = pd.DataFrame({
        "open":  prices, "high":  prices, "low":  prices,
        "close": prices, "volume": [1_000_000] * len(prices),
    }, index=dates)
    df.index.name = "date"
    return df


def _signal_buy_then_flat(data):
    """第 2 天买入,一直持有到结束"""
    df = list(data.values())[0]
    s = pd.Series(0, index=df.index, dtype=int)
    s.iloc[1] = 1   # 第二天开多
    # 不退出,期末强平
    sym = list(data.keys())[0]
    return {sym: s}


def _signal_short_then_flat(data):
    """第 2 天做空,期末强平"""
    df = list(data.values())[0]
    s = pd.Series(0, index=df.index, dtype=int)
    s.iloc[1] = -1
    sym = list(data.keys())[0]
    return {sym: s}


def test_long_equity_lower_bound():
    """Bug A 验证:Long 仓位,股价从 10 跌到 1,净值不能 < -95%"""
    prices = [10.0, 10.0, 1.0, 1.0, 1.0]   # 第 2 天买入,股价随后腰斩 → 跌 90%
    df = make_df(prices)
    config = BacktestConfig(
        codes=["TEST"], start="2026-01-01", end="2026-01-07",
        initial_cash=100_000.0, stop_loss_pct=0.0, take_profit_pct=0.0,
    )
    # 把 generate_signals 注入 config
    src = (
        "def generate_signals(data):\n"
        "    df = list(data.values())[0]\n"
        "    s = [0]*len(df); s[1] = 1\n"
        "    return {list(data.keys())[0]: __import__('pandas').Series(s, index=df.index, dtype=int)}\n"
    )
    config.signal_engine_code = src
    result = run_backtest(config, {"TEST": df})

    assert result.status == "success", result.error
    eqs = result.equity_curve
    # 最低点不应跌破 0.05 * initial_cash = 5000
    min_eq = min(e.equity for e in eqs)
    assert min_eq >= 0.04 * config.initial_cash, (
        f"净值跌穿下限: min_equity={min_eq:.2f}, 应 ≥ 5000"
    )
    # 末值应 = 期末强平所得 = (1 - 10) * shares + 残余现金
    # shares = int(95000 / 10) = 9500,残余 cash = 100000 - 95000 = 5000
    # 末值 = 5000 + 9500 * 1 = 14500
    assert abs(eqs[-1].equity - 14500) < 1, f"末值 {eqs[-1].equity}, 应=14500"


def test_long_pnl_matches_curve():
    """Bug B 验证:Long,逐笔 pnl 之和 + 残余现金 = 最终权益"""
    prices = [10.0, 10.0, 12.0, 12.0]  # 第二天买入,涨 20%,期末强平
    df = make_df(prices)
    src = (
        "def generate_signals(data):\n"
        "    df = list(data.values())[0]\n"
        "    s = [0]*len(df); s[1] = 1\n"
        "    return {list(data.keys())[0]: __import__('pandas').Series(s, index=df.index, dtype=int)}\n"
    )
    config = BacktestConfig(
        codes=["TEST"], start="2026-01-01", end="2026-01-05",
        initial_cash=100_000.0,
    )
    config.signal_engine_code = src
    result = run_backtest(config, {"TEST": df})

    total_pnl = sum(t.pnl for t in result.trades)
    final_eq = result.equity_curve[-1].equity
    # shares = 9500, 一笔交易 pnl = (12-10)*9500 = 19000
    # final_eq = 5000 + 9500*12 = 5000 + 114000 = 119000
    # total_pnl = 19000
    # 验: 初始 - 投入 + 卖出 + 浮动 = 100000 - 95000 + 114000 = 119000 ✓
    assert abs(final_eq - 119_000) < 1, f"final_eq {final_eq}, 应=119000"
    assert abs(total_pnl - 19_000) < 1, f"total_pnl {total_pnl}, 应=19000"
    # 关键:逐笔 pnl 之和 = 终值 - 初值 - 残余现金
    # 修正后:final_eq - initial_cash = 119000 - 100000 = 19000 == total_pnl ✓
    assert abs((final_eq - config.initial_cash) - total_pnl) < 1, (
        f"逐笔 pnl ({total_pnl}) 与权益变动 ({final_eq - config.initial_cash:.0f}) 不一致"
    )


def test_short_equity_lower_bound():
    """Bug A 验证:Short 仓位,股价翻倍,净值不能 < -95%"""
    prices = [10.0, 10.0, 20.0, 20.0, 20.0]  # 第二天做空,股价翻倍
    df = make_df(prices)
    src = (
        "def generate_signals(data):\n"
        "    df = list(data.values())[0]\n"
        "    s = [0]*len(df); s[1] = -1\n"
        "    return {list(data.keys())[0]: __import__('pandas').Series(s, index=df.index, dtype=int)}\n"
    )
    config = BacktestConfig(
        codes=["TEST"], start="2026-01-01", end="2026-01-07",
        initial_cash=100_000.0,
    )
    config.signal_engine_code = src
    result = run_backtest(config, {"TEST": df})

    eqs = result.equity_curve
    min_eq = min(e.equity for e in eqs)
    assert min_eq >= 0.04 * config.initial_cash, (
        f"Short 净值跌穿下限: min_equity={min_eq:.2f}, 应 ≥ 5000"
    )
    # shares=9500,做空收到 95000,cash=195000
    # 股价 20,买回花 190000,期末 cash = 5000
    assert abs(eqs[-1].equity - 5_000) < 1, f"Short 末值 {eqs[-1].equity}, 应=5000"


def test_short_pnl_matches_curve():
    """Bug B 验证:Short 获利,逐笔 pnl 与权益变动一致"""
    prices = [10.0, 10.0, 8.0, 8.0]  # 做空,股价跌 20%
    df = make_df(prices)
    src = (
        "def generate_signals(data):\n"
        "    df = list(data.values())[0]\n"
        "    s = [0]*len(df); s[1] = -1\n"
        "    return {list(data.keys())[0]: __import__('pandas').Series(s, index=df.index, dtype=int)}\n"
    )
    config = BacktestConfig(
        codes=["TEST"], start="2026-01-01", end="2026-01-05",
        initial_cash=100_000.0,
    )
    config.signal_engine_code = src
    result = run_backtest(config, {"TEST": df})

    total_pnl = sum(t.pnl for t in result.trades)
    final_eq = result.equity_curve[-1].equity
    # shares=9500,做空 10 收到 95000,cash=195000
    # 买回 8*9500=76000,期末 cash=195000-76000=119000
    assert abs(final_eq - 119_000) < 1
    # pnl = (10-8)*9500 = 19000
    assert abs(total_pnl - 19_000) < 1
    assert abs((final_eq - config.initial_cash) - total_pnl) < 1


def test_no_position_equity_unchanged():
    """无持仓时,权益应该 = 现金 = initial_cash,不会被 bug 误算"""
    prices = [10.0, 10.5, 11.0, 10.8, 10.2]  # 永远不开仓
    df = make_df(prices)
    src = (
        "def generate_signals(data):\n"
        "    return {list(data.keys())[0]: __import__('pandas').Series(0, index=data[list(data.keys())[0]].index, dtype=int)}\n"
    )
    config = BacktestConfig(
        codes=["TEST"], start="2026-01-01", end="2026-01-07",
        initial_cash=100_000.0,
    )
    config.signal_engine_code = src
    result = run_backtest(config, {"TEST": df})
    assert abs(result.equity_curve[-1].equity - 100_000) < 0.01
    assert result.trades == []


if __name__ == "__main__":
    tests = [
        test_long_equity_lower_bound,
        test_long_pnl_matches_curve,
        test_short_equity_lower_bound,
        test_short_pnl_matches_curve,
        test_no_position_equity_unchanged,
    ]
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            sys.exit(1)
    print(f"\nAll {len(tests)} tests passed!")
