"""
Lightweight backtest engine for VIBE TRADING LIT.
Simple bar-by-bar execution with optional stop-loss / take-profit.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .lite_metrics import (
    BacktestMetrics,
    EquitySnapshot,
    Position,
    TradeRecord,
    calc_metrics,
)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    codes: list[str]
    start: str        # YYYY-MM-DD
    end: str          # YYYY-MM-DD
    interval: str = "1D"
    initial_cash: float = 100_000.0
    stop_loss_pct: float = 0.0    # 0.05 = 5%
    take_profit_pct: float = 0.0  # 0.15 = 15%
    signal_engine_code: str = ""  # Python source code
    signal_engine_path: Optional[Path] = None  # Alternative: load from file


@dataclass
class BacktestResult:
    """Result of a backtest run."""
    config: BacktestConfig
    status: str  # "success" | "failed"
    error: str = ""
    metrics: Optional[BacktestMetrics] = None
    equity_curve: list[EquitySnapshot] = field(default_factory=list)
    trades: list[TradeRecord] = field(default_factory=list)
    ohlcv: dict[str, pd.DataFrame] = field(default_factory=dict)


def run_backtest(
    config: BacktestConfig,
    data: dict[str, pd.DataFrame],
) -> BacktestResult:
    """
    Run a backtest with the given config and OHLCV data.

    Args:
        config: BacktestConfig with codes, dates, cash, and signal code
        data: dict of symbol -> DataFrame with columns: open, high, low, close, volume

    Returns:
        BacktestResult with metrics, equity curve, and trades
    """
    # ── Validate data ───────────────────────────────────────────────────────
    if not data:
        return BacktestResult(
            config=config,
            status="failed",
            error="No market data provided",
        )

    # Ensure all symbols have required columns
    required_cols = {"open", "high", "low", "close", "volume"}
    for symbol, df in data.items():
        missing = required_cols - set(df.columns)
        if missing:
            return BacktestResult(
                config=config,
                status="failed",
                error=f"Symbol {symbol} missing columns: {missing}",
            )

    # ── Load signal engine ──────────────────────────────────────────────────
    generate_signals: Optional[callable] = None
    if config.signal_engine_code:
        try:
            generate_signals = _load_signal_function(config.signal_engine_code)
        except Exception as e:
            return BacktestResult(
                config=config,
                status="failed",
                error=f"Failed to load signal engine: {e}",
            )
    else:
        return BacktestResult(
            config=config,
            status="failed",
            error="No signal engine code provided",
        )

    # ── Generate signals ────────────────────────────────────────────────────
    try:
        signals = generate_signals(data)
    except Exception as e:
        tb = traceback.format_exc()
        return BacktestResult(
            config=config,
            status="failed",
            error=f"Signal generation error:\n{tb}",
        )

    # Normalize signals to dict[symbol, Series]
    if not isinstance(signals, dict):
        # If single symbol passed, wrap in dict
        symbol = list(data.keys())[0]
        signals = {symbol: signals}

    # ── Align all data ───────────────────────────────────────────────────────
    # Find common dates across all symbols
    all_dates: set[pd.Timestamp] = set()
    for df in data.values():
        all_dates.update(df.index)

    aligned_dates = sorted(all_dates)
    start_date = pd.Timestamp(config.start)
    end_date = pd.Timestamp(config.end)
    aligned_dates = [d for d in aligned_dates if start_date <= d <= end_date]

    if not aligned_dates:
        return BacktestResult(
            config=config,
            status="failed",
            error=f"No trading dates in range {config.start} to {config.end}",
        )

    # ── Main backtest loop ──────────────────────────────────────────────────
    cash = config.initial_cash
    position: Optional[Position] = None
    equity_curve: list[EquitySnapshot] = []
    trades: list[TradeRecord] = []

    # Track entry price for stop/take-profit
    entry_price: float = 0.0
    stop_price: float = 0.0
    tp_price: float = 0.0

    peak_equity = cash
    n_shares = 0

    for date in aligned_dates:
        date_str = date.strftime("%Y-%m-%d")

        # Current prices per symbol
        current_prices = {}
        for symbol, df in data.items():
            if date in df.index:
                current_prices[symbol] = df.loc[date, "close"]

        if not current_prices:
            equity_curve.append(EquitySnapshot(date=date_str, equity=cash, cash=cash))
            continue

        # Primary symbol for single-symbol backtest
        primary_symbol = config.codes[0] if config.codes else list(data.keys())[0]
        current_price = current_prices.get(primary_symbol, 0.0)

        # Get today's signal for primary symbol
        today_signal = 0
        if primary_symbol in signals:
            sig_series = signals[primary_symbol]
            if date in sig_series.index:
                today_signal = int(sig_series.loc[date])

        # ── Position management ──────────────────────────────────────────
        if position is not None:
            # Check stop-loss / take-profit first
            exit_reason = ""
            should_exit = False

            if position.direction == 1:  # Long
                # Stop-loss
                if config.stop_loss_pct > 0 and current_price <= stop_price:
                    should_exit = True
                    exit_reason = "stop_loss"
                # Take-profit
                if config.take_profit_pct > 0 and current_price >= tp_price:
                    should_exit = True
                    exit_reason = "take_profit"
                # Signal exit
                if today_signal == -1:
                    should_exit = True
                    exit_reason = "signal"

                if should_exit:
                    pnl = (current_price - position.entry_price) * position.shares
                    pnl_pct = (current_price - position.entry_price) / position.entry_price
                    trades.append(TradeRecord(
                        entry_date=position.entry_date,
                        entry_price=position.entry_price,
                        exit_date=date_str,
                        exit_price=current_price,
                        direction=1,
                        shares=position.shares,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        exit_reason=exit_reason,
                    ))
                    cash += pnl
                    position = None
                    n_shares = 0

            elif position.direction == -1:  # Short
                if config.stop_loss_pct > 0 and current_price >= stop_price:
                    should_exit = True
                    exit_reason = "stop_loss"
                if config.take_profit_pct > 0 and current_price <= tp_price:
                    should_exit = True
                    exit_reason = "take_profit"
                if today_signal == 1:
                    should_exit = True
                    exit_reason = "signal"

                if should_exit:
                    pnl = (position.entry_price - current_price) * position.shares
                    pnl_pct = (position.entry_price - current_price) / position.entry_price
                    trades.append(TradeRecord(
                        entry_date=position.entry_date,
                        entry_price=position.entry_price,
                        exit_date=date_str,
                        exit_price=current_price,
                        direction=-1,
                        shares=position.shares,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        exit_reason=exit_reason,
                    ))
                    cash += pnl
                    position = None
                    n_shares = 0

        # ── Open new position ──────────────────────────────────────────────
        if position is None and today_signal != 0:
            direction = today_signal  # 1=long, -1=short
            # Allocate 95% of cash to position (both long and short need buying power)
            available = cash
            shares = int(available * 0.95 / current_price) if available > 0 else 0

            if shares > 0:
                if direction == 1:
                    cost = shares * current_price
                    cash -= cost
                else:
                    # Short: receive proceeds from selling borrowed shares
                    proceeds = shares * current_price
                    cash += proceeds
                position = Position(
                    shares=shares,
                    entry_price=current_price,
                    entry_date=date_str,
                    direction=direction,
                )

                # Set stop-loss and take-profit prices
                if direction == 1:
                    stop_price = current_price * (1 - config.stop_loss_pct)
                    tp_price = current_price * (1 + config.take_profit_pct)
                else:
                    stop_price = current_price * (1 + config.stop_loss_pct)
                    tp_price = current_price * (1 - config.take_profit_pct)

        # ── Calculate equity ───────────────────────────────────────────────
        if position is not None:
            if position.direction == 1:
                unrealized = (current_price - position.entry_price) * position.shares
            else:
                unrealized = (position.entry_price - current_price) * position.shares
            total_equity = cash + unrealized
        else:
            total_equity = cash

        if total_equity > peak_equity:
            peak_equity = total_equity
        dd = (peak_equity - total_equity) / peak_equity if peak_equity > 0 else 0.0

        equity_curve.append(EquitySnapshot(
            date=date_str,
            equity=total_equity,
            cash=cash,
            drawdown=dd,
        ))

    # ── Close any open position at end ─────────────────────────────────────
    if position is not None:
        last_date = aligned_dates[-1].strftime("%Y-%m-%d")
        last_prices = {}
        for symbol, df in data.items():
            if aligned_dates[-1] in df.index:
                last_prices[symbol] = df.loc[aligned_dates[-1], "close"]

        last_price = last_prices.get(primary_symbol, position.entry_price)
        if position.direction == 1:
            pnl = (last_price - position.entry_price) * position.shares
            pnl_pct = (last_price - position.entry_price) / position.entry_price
        else:
            pnl = (position.entry_price - last_price) * position.shares
            pnl_pct = (position.entry_price - last_price) / position.entry_price

        trades.append(TradeRecord(
            entry_date=position.entry_date,
            entry_price=position.entry_price,
            exit_date=last_date,
            exit_price=last_price,
            direction=position.direction,
            shares=position.shares,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason="end",
        ))
        cash += pnl

    # ── Calculate metrics ────────────────────────────────────────────────────
    metrics = calc_metrics(
        equity_curve=equity_curve,
        trades=trades,
        initial_cash=config.initial_cash,
    )

    return BacktestResult(
        config=config,
        status="success",
        metrics=metrics,
        equity_curve=equity_curve,
        trades=trades,
        ohlcv=data,
    )


def _load_signal_function(code: str) -> callable:
    """
    Safely load the generate_signals function from a code string.
    Creates a new module, compiles, and imports it.
    """
    module_name = f"signal_engine_{id(code)}"

    # Create a fake file for importlib
    spec = importlib.util.spec_from_loader(
        module_name,
        loader=None,
        origin="<string>",
    )
    if spec is None:
        raise ValueError("Could not create module spec")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        exec(compile(code, "<signal_engine>", "exec"), module.__dict__)
    except Exception as e:
        raise ValueError(f"Compilation error: {e}") from e

    if not hasattr(module, "generate_signals"):
        raise ValueError("signal_engine.py must define a generate_signals(data) function")

    return module.generate_signals


def save_result(result: BacktestResult, run_dir: Path) -> None:
    """Save backtest result artifacts to disk."""
    run_dir.mkdir(parents=True, exist_ok=True)

    # Equity curve
    if result.equity_curve:
        eq_df = pd.DataFrame([
            {"date": e.date, "equity": e.equity, "cash": e.cash, "drawdown": e.drawdown}
            for e in result.equity_curve
        ])
        eq_df.to_csv(run_dir / "artifacts" / "equity.csv", index=False)

    # Trades
    if result.trades:
        trades_df = pd.DataFrame([
            {
                "entry_date": t.entry_date,
                "entry_price": t.entry_price,
                "exit_date": t.exit_date,
                "exit_price": t.exit_price,
                "direction": t.direction,
                "shares": t.shares,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "exit_reason": t.exit_reason,
            }
            for t in result.trades
        ])
        trades_df.to_csv(run_dir / "artifacts" / "trades.csv", index=False)

    # Metrics
    if result.metrics:
        m = result.metrics
        metrics_dict = {
            "total_return": f"{m.total_return:.4f}",
            "annual_return": f"{m.annual_return:.4f}",
            "final_value": f"{m.final_value:.2f}",
            "max_drawdown": f"{m.max_drawdown:.4f}",
            "sharpe": f"{m.sharpe:.4f}",
            "sortino": f"{m.sortino:.4f}",
            "calmar": f"{m.calmar:.4f}",
            "win_rate": f"{m.win_rate:.4f}",
            "trade_count": m.trade_count,
            "profit_loss_ratio": f"{m.profit_loss_ratio:.4f}",
            "profit_factor": f"{m.profit_factor:.4f}",
            "max_consecutive_loss": m.max_consecutive_loss,
            "avg_holding_days": f"{m.avg_holding_days:.2f}",
        }
        with open(run_dir / "artifacts" / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics_dict, f, indent=2)

    # Config
    config_dict = {
        "codes": result.config.codes,
        "start": result.config.start,
        "end": result.config.end,
        "interval": result.config.interval,
        "initial_cash": result.config.initial_cash,
        "stop_loss_pct": result.config.stop_loss_pct,
        "take_profit_pct": result.config.take_profit_pct,
    }
    with open(run_dir / "code" / "config.json", "w", encoding="utf-8") as f:
        json.dump(config_dict, f, indent=2)
