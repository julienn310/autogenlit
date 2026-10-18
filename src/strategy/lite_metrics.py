"""
Lightweight metrics calculation for VIBE TRADING LIT.
Implements Tier 1+2 metrics from the original backtest engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import math


@dataclass
class TradeRecord:
    """A single trade."""
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    direction: int       # 1 = long, -1 = short
    shares: float
    pnl: float
    pnl_pct: float       # as a fraction, e.g. 0.05 = 5%
    exit_reason: str      # "signal", "stop_loss", "take_profit", "end"


@dataclass
class Position:
    """Current portfolio position."""
    shares: float
    entry_price: float
    entry_date: str
    direction: int        # 1 = long, -1 = short
    unrealized_pnl: float = 0.0


@dataclass
class EquitySnapshot:
    """Equity curve entry."""
    date: str
    equity: float
    cash: float
    drawdown: float = 0.0


@dataclass
class BacktestMetrics:
    """Results of a backtest run."""
    total_return: float = 0.0        # total return as fraction, e.g. 0.25 = 25%
    annual_return: float = 0.0       # annualized return
    final_value: float = 0.0
    max_drawdown: float = 0.0       # max drawdown as fraction
    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    win_rate: float = 0.0            # fraction
    trade_count: int = 0
    profit_loss_ratio: float = 0.0  # avg win / avg loss
    profit_factor: float = 0.0       # gross profit / gross loss
    max_consecutive_loss: int = 0
    avg_holding_days: float = 0.0
    by_symbol: dict = field(default_factory=dict)


def calc_metrics(
    equity_curve: list[EquitySnapshot],
    trades: list[TradeRecord],
    initial_cash: float = 100_000.0,
    annual_days: int = 252,
) -> BacktestMetrics:
    """
    Calculate Tier 1+2 backtest metrics.

    Args:
        equity_curve: List of daily equity snapshots
        trades: List of completed trades
        initial_cash: Starting capital
        annual_days: Trading days per year (default 252)

    Returns:
        BacktestMetrics dataclass
    """
    if not equity_curve:
        return BacktestMetrics()

    # ── Tier 1: Core metrics ────────────────────────────────────────────────
    final_equity = equity_curve[-1].equity
    total_return = (final_equity - initial_cash) / initial_cash
    final_value = final_equity

    # Annual return
    n_days = len(equity_curve)
    years = n_days / annual_days
    if years > 0 and initial_cash > 0 and final_equity > 0:
        annual_return = (final_equity / initial_cash) ** (1 / years) - 1
    else:
        annual_return = 0.0

    # Max drawdown
    peak = initial_cash
    max_dd = 0.0
    for snap in equity_curve:
        if snap.equity > peak:
            peak = snap.equity
        dd = (peak - snap.equity) / peak
        if dd > max_dd:
            max_dd = dd
    max_drawdown = max_dd

    # ── Tier 2: Risk-adjusted ──────────────────────────────────────────────
    # Daily returns
    daily_rets = []
    prev_equity = initial_cash
    for snap in equity_curve:
        ret = (snap.equity - prev_equity) / prev_equity if prev_equity > 0 else 0.0
        daily_rets.append(ret)
        prev_equity = snap.equity

    # Sharpe ratio (annualized)
    if daily_rets and len(daily_rets) > 1:
        mean_ret = sum(daily_rets) / len(daily_rets)
        std_ret = _std(daily_rets)
        sharpe = (mean_ret / std_ret) * math.sqrt(annual_days) if std_ret > 0 else 0.0

        # Sortino: downside deviation
        neg_rets = [r for r in daily_rets if r < 0]
        downside_std = _std(neg_rets) if len(neg_rets) > 1 else 0.0
        sortino = (mean_ret / downside_std) * math.sqrt(annual_days) if downside_std > 0 else 0.0
    else:
        sharpe = sortino = 0.0

    # Calmar: annual return / max drawdown
    calmar = abs(annual_return / max_drawdown) if max_drawdown > 0.001 else 0.0

    # ── Trade statistics ────────────────────────────────────────────────────
    trade_count = len(trades)
    if trades:
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]

        win_rate = len(wins) / trade_count if trade_count > 0 else 0.0

        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(t.pnl for t in losses) / len(losses)) if losses else 0.0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        # Max consecutive losses
        max_cons = 0
        cur_cons = 0
        for t in trades:
            if t.pnl < 0:
                cur_cons += 1
                max_cons = max(max_cons, cur_cons)
            else:
                cur_cons = 0
        max_consecutive_loss = max_cons

        # Avg holding days
        all_days = []
        for t in trades:
            try:
                from datetime import datetime
                d1 = datetime.strptime(t.entry_date, "%Y-%m-%d")
                d2 = datetime.strptime(t.exit_date, "%Y-%m-%d")
                all_days.append((d2 - d1).days)
            except Exception:
                pass
        avg_holding_days = sum(all_days) / len(all_days) if all_days else 0.0
    else:
        win_rate = profit_loss_ratio = profit_factor = 0.0
        max_consecutive_loss = avg_holding_days = 0

    # Per-symbol breakdown
    by_symbol: dict[str, dict] = {}
    if trades:
        for t in trades:
            # extract symbol from entry_date string (placeholder)
            key = t.entry_date  # simplified; real impl would track symbol per trade
            if key not in by_symbol:
                by_symbol[key] = {"count": 0, "wins": 0, "pnl": 0.0}
            by_symbol[key]["count"] += 1
            if t.pnl > 0:
                by_symbol[key]["wins"] += 1
            by_symbol[key]["pnl"] += t.pnl

    return BacktestMetrics(
        total_return=total_return,
        annual_return=annual_return,
        final_value=final_equity,
        max_drawdown=max_drawdown,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        win_rate=win_rate,
        trade_count=trade_count,
        profit_loss_ratio=profit_loss_ratio,
        profit_factor=profit_factor,
        max_consecutive_loss=max_consecutive_loss,
        avg_holding_days=avg_holding_days,
        by_symbol=by_symbol,
    )


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)
