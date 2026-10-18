"""
 量化策略页面 — MVP 版本
- Tab 1: 策略模板 (3 个可执行: 均线交叉 / RSI / 布林带)
- Tab 2: 因子库 (52 个投研因子)
- Tab 3: 我的回测 (session 内历史)
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import uuid
from typing import Dict, List

from src.data.astock_collector import AStockDataCollector
from src.strategy.data_adapter import build_engine_input
from src.strategy.lite_engine import BacktestConfig, run_backtest
from src.strategy.strategy_templates import (
    TEMPLATES, get_template, list_template_names,
)
from src.strategy.factors_data import get_all_factors, search_factors, CATEGORIES
from src.strategy.charts import plot_equity_with_drawdown, plot_signal_chart
from src.ui.animations import gradient_banner, section_divider, rolling_number, badge

# MVP 阶段暴露 6 个真正可执行的策略 (3 个趋势 + 1 个动量 + 1 个均值回归 + 1 个通道)
EXECUTABLE_STRATEGIES = [
    "均线交叉",      # 趋势跟踪: 短期均线上穿长期均线买入
    "RSI趏勣",      # 趋势跟踪: RSI 超卖买入,超买卖出
    "布林带突破",    # 趋势跟踪: 价格突破布林带上轨买入
    "动量策略",      # 动量: N 日涨幅超过阈值买入
    "价值回归",      # 均值回归: 价格低于均线一定比例买入
    "Keltner通道",   # 通道: 价格上穿 Keltner 上轨买入
]
EXIT_REASON_CN = {"signal": "信号", "stop_loss": "止损", "take_profit": "止盈", "end": "期末"}

# ---------------------------------------------------------------------------
# 顶层缓存数据拉取 (避免在函数内定义造成的 cache 警告)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def _fetch_historical(symbol: str, start: str, end: str) -> pd.DataFrame:
    """拉取历史 OHLCV"""
    collector = AStockDataCollector()
    return collector.get_historical_data(
        symbol, "daily",
        start_date=start,
        end_date=end,
    )

def _ensure_state(session):
    if "quant_runs" not in session:
        session.quant_runs = []

# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def render_quant_strategy_page(session):
    _ensure_state(session)

    # ── Header ──
    st.markdown(gradient_banner(
        "量化策略实验室",
        "3 套可执行策略 · 52 个投研因子 · 单股历史回测 · 实时权益曲线",
    ), unsafe_allow_html=True)

    # ── 3 个数字 roll-up ──
    cols = st.columns(3)
    with cols[0]:
        st.markdown(rolling_number(13, "策略模板", 1000) + badge("MVP=3") +
                    "<div style='color:#64748b;font-size:0.78rem;margin-top:4px;'>均线 / RSI / 布林带</div>",
                    unsafe_allow_html=True)
    with cols[1]:
        st.markdown(rolling_number(52, "投研因子", 1500) + badge("4 类") +
                    "<div style='color:#64748b;font-size:0.78rem;margin-top:4px;'>Alpha101 / 国泰191 / Qlib158 / 学术</div>",
                    unsafe_allow_html=True)
    with cols[2]:
        st.markdown(rolling_number(len(session.quant_runs), "本会话回测", 600) + badge("实时") +
                    "<div style='color:#64748b;font-size:0.78rem;margin-top:4px;'>仅本会话内存</div>",
                    unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    # ── Tabs ──
    tab_t, tab_f, tab_h = st.tabs([" 策略模板", " 因子库", " 我的回测"])

    with tab_t:
        _render_strategy_tab(session)

    with tab_f:
        _render_factors_tab()

    with tab_h:
        _render_history_tab(session)

# ---------------------------------------------------------------------------
# Tab 1: 策略模板
# ---------------------------------------------------------------------------

def _render_strategy_tab(session):
    st.markdown(section_divider("选策略 + 调参数 + 跑回测"), unsafe_allow_html=True)

    col_input, col_strategy, col_params = st.columns([1, 1, 2])

    with col_input:
        st.markdown("##### 数据输入")
        symbol = st.text_input(
            "股票代码",
            value=session.get("quant_symbol", "000001"),
            key="quant_symbol_input",
            help="A 股代码, 如 000001 / 600000 / 300750",
        )
        today = datetime.now().date()
        col_a, col_b = st.columns(2)
        with col_a:
            start = st.date_input(
                "起始日期",
                value=today - timedelta(days=365),
                min_value=today - timedelta(days=1825),  # 最多 5 年
                max_value=today,
                key="quant_start_input",
            )
        with col_b:
            end = st.date_input(
                "结束日期",
                value=today,
                max_value=today,
                key="quant_end_input",
            )

        st.caption(" 数据源: 财汇 / akshare / 新浪 / 腾讯")
        st.caption("️ A 股不支持做空,做空信号将转为平仓")

    with col_strategy:
        st.markdown("##### 选择策略")
        selected = st.selectbox(
            "可执行策略",
            options=EXECUTABLE_STRATEGIES,
            key="quant_strategy_select",
            help="MVP 阶段提供 3 个可执行策略。后续会扩展到全部 13 个。",
        )
        tpl = get_template(selected)
        if tpl:
            st.info(f"**{selected}**\n\n{tpl.description}")

        st.markdown("##### ️ 风控参数")
        risk_cash = st.number_input(
            "初始资金 (元)",
            min_value=10000,
            max_value=10_000_000,
            value=100_000,
            step=10_000,
            key="quant_cash",
        )
        risk_sl = st.slider(
            "止损 %",
            0.0, 30.0, 5.0, 0.5,
            key="quant_sl",
            help="亏损达到该比例时强制平仓",
        )
        risk_tp = st.slider(
            "止盈 %",
            0.0, 100.0, 15.0, 1.0,
            key="quant_tp",
            help="浮盈达到该比例时锁定利润",
        )

    with col_params:
        st.markdown(f"##### ️ {selected} — 策略参数")
        tpl = get_template(selected)
        params = {}
        if tpl:
            for p in tpl.params:
                if p.name in ('stop_loss_pct', 'take_profit_pct'):
                    continue  # 用全局风控代替
                if p.param_type.value == 'slider':
                    params[p.name] = st.slider(
                        p.label,
                        float(p.min_value),
                        float(p.max_value),
                        float(p.default),
                        float(p.step),
                        key=f"q_p_{p.name}",
                        help=p.help,
                    )
                elif p.param_type.value == 'number':
                    params[p.name] = st.number_input(
                        p.label,
                        value=int(p.default),
                        key=f"q_p_{p.name}",
                    )
        # 加入全局风控
        params['stop_loss_pct'] = risk_sl
        params['take_profit_pct'] = risk_tp

        with st.expander(" 查看信号生成代码", expanded=False):
            code = tpl.generate_code(params) if tpl else ""
            st.code(code, language='python')

    # ── 运行按钮 ──
    st.markdown("<br/>", unsafe_allow_html=True)
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
    with col_btn1:
        run_btn = st.button(" 运行回测", type="primary", use_container_width=True, key="quant_run")
    with col_btn2:
        clear_btn = st.button("️ 清空历史", use_container_width=True, key="quant_clear")
    if clear_btn:
        session.quant_runs = []
        st.rerun()

    if run_btn:
        _execute_backtest(
            session, symbol.strip(), selected, params,
            start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
            initial_cash=float(risk_cash),
            stop_loss_pct=risk_sl / 100.0,
            take_profit_pct=risk_tp / 100.0,
        )

    # ── 显示最近一次结果 ──
    if session.quant_runs:
        st.markdown(section_divider("最近一次回测结果"), unsafe_allow_html=True)
        _render_single_result(session.quant_runs[-1], position="latest")

# ---------------------------------------------------------------------------
# 回测执行
# ---------------------------------------------------------------------------

def _execute_backtest(
    session, symbol: str, strategy_name: str, params: Dict,
    start: str, end: str,
    initial_cash: float, stop_loss_pct: float, take_profit_pct: float,
):
    if not symbol:
        st.error("请输入股票代码")
        return

    # 1) 拉数据
    with st.spinner(f"拉取 {symbol} 的历史数据..."):
        try:
            hist = _fetch_historical(symbol, start, end)
        except Exception as e:
            st.error(f"拉取数据失败: {e}")
            return

    if hist is None or hist.empty:
        st.error(f"未取到 {symbol} 的历史数据,请检查代码或延长日期范围")
        return

    # 2) 适配
    data = build_engine_input(hist, symbol, start, end)
    if data is None:
        st.warning(
            f"数据不足 (需要 ≥30 个交易日)。当前可用: {len(hist)} 行。\n\n"
            f"建议: 延长起始日期,或换一个有更多历史的股票。"
        )
        return

    # 3) 生成信号代码
    tpl = get_template(strategy_name)
    if tpl is None:
        st.error(f"未找到策略: {strategy_name}")
        return
    code = tpl.generate_code(params)

    # 4) 跑回测
    with st.spinner("运行回测中..."):
        cfg = BacktestConfig(
            codes=[symbol],
            start=start,
            end=end,
            interval='1D',
            initial_cash=initial_cash,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            signal_engine_code=code,
        )
        result = run_backtest(cfg, data)

    if result.status != 'success':
        st.error(f"回测失败: {result.error}")
        return

    # 5) 落盘到 session
    run_record = {
        'meta': {
            'symbol': symbol,
            'strategy': strategy_name,
            'params': dict(params),
            'start': start,
            'end': end,
            'initial_cash': initial_cash,
            'sl': stop_loss_pct,
            'tp': take_profit_pct,
            'run_at': datetime.now(),
        },
        'result': result,
    }
    # 注入唯一 run_id 供前端组件 key 使用
    run_record['run_id'] = uuid.uuid4().hex
    session.quant_runs.append(run_record)
    m = result.metrics
    st.success(
        f" 回测完成 · {symbol} · {strategy_name}  |  "
        f"总收益 {m.total_return:+.2%} · 年化 {m.annual_return:+.2%} · "
        f"夏普 {m.sharpe:.2f} · 最大回撤 {m.max_drawdown:.2%} · "
        f"胜率 {m.win_rate:.1%} · 交易 {m.trade_count} 笔"
    )

# ---------------------------------------------------------------------------
# 单次回测结果展示
# ---------------------------------------------------------------------------

def _render_single_result(run_record: Dict, position: str = ""):
    result = run_record['result']
    meta = run_record['meta']
    m = result.metrics

    # 标题
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d3b66,#1f5f8b);color:white;
                padding:14px 18px;border-radius:10px;margin-bottom:12px;
                box-shadow:0 4px 12px rgba(13,59,102,0.18);">
        <div style="font-size:1.15rem;font-weight:700;">
            {meta['symbol']} · {meta['strategy']}
        </div>
        <div style="font-size:0.78rem;opacity:0.85;margin-top:4px;">
            回测区间: {meta['start']} → {meta['end']}  |  初始资金: ¥{meta['initial_cash']:,.0f}
             |  止损/止盈: {meta['sl']:.1%} / {meta['tp']:.1%}
             |  跑测于 {meta['run_at'].strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 6 个核心指标
    cols = st.columns(6)
    metrics = [
        ("总收益",       m.total_return,       "{:+.2%}"),
        ("年化收益",     m.annual_return,      "{:+.2%}"),
        ("最大回撤",     m.max_drawdown,       "{:.2%}"),
        ("夏普比率",     m.sharpe,             "{:.2f}"),
        ("胜率",         m.win_rate,           "{:.1%}"),
        ("交易次数",     m.trade_count,        "{}"),
    ]
    for col, (label, value, fmt) in zip(cols, metrics):
        with col:
            if isinstance(value, (int, float)):
                color = '#16a34a' if (label in ('总收益', '年化收益', '夏普比率', '胜率') and value > 0) else (
                    '#dc2626' if label in ('总收益', '年化收益') and value < 0 else '#475569')
            else:
                color = '#475569'
            st.markdown(f"""
            <div style="background:white;border:1px solid #e3e6ea;border-radius:8px;
                        padding:10px 12px;text-align:center;">
                <div style="font-size:0.72rem;color:#94a3b8;letter-spacing:0.3px;">{label}</div>
                <div style="font-size:1.45rem;font-weight:700;color:{color};
                            font-variant-numeric:tabular-nums;margin-top:4px;">
                    {fmt.format(value)}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 净值曲线 + 回撤
    if result.equity_curve:
        eq_df = pd.DataFrame([
            {'date': e.date, 'equity': e.equity, 'drawdown': e.drawdown}
            for e in result.equity_curve
        ])
        st.plotly_chart(
            plot_equity_with_drawdown(eq_df),
            use_container_width=True,
            key=f"equity_{run_record.get('run_id', id(run_record))}_{position}",
        )

    # 交易明细
    if result.trades:
        st.markdown("##### 交易明细")
        trades_df = pd.DataFrame([{
            '买入日期': t.entry_date,
            '买入价':   round(t.entry_price, 2),
            '卖出日期': t.exit_date,
            '卖出价':   round(t.exit_price, 2),
            '方向':     '多' if t.direction == 1 else '空',
            '股数':     int(t.shares),
            '盈亏(元)': round(t.pnl, 2),
            '盈亏%':    f"{t.pnl_pct:+.2%}",
            '退出原因': EXIT_REASON_CN.get(t.exit_reason, t.exit_reason),
        } for t in result.trades])
        st.dataframe(
            trades_df, use_container_width=True, hide_index=True, height=300,
            key=f"trades_{run_record.get('run_id', id(run_record))}_{position}",
        )
    else:
        st.info("本次回测无交易 (信号未触发或全部被风控过滤)")

# ---------------------------------------------------------------------------
# Tab 2: 因子库
# ---------------------------------------------------------------------------

def _render_factors_tab():
    st.markdown(section_divider("52 个投研因子 · 分类浏览 · 关键词搜索"), unsafe_allow_html=True)

    col_search, col_cat = st.columns([2, 3])
    with col_search:
        query = st.text_input(" 搜索", "", key="factor_query", placeholder="如 RSI / 资金流 / Beta")
    with col_cat:
        cat_filter = st.multiselect(
            "分类筛选",
            options=list(CATEGORIES.keys()),
            format_func=lambda k: f"{CATEGORIES[k][0]} ({len(CATEGORIES[k][1])} 个)",
            default=list(CATEGORIES.keys()),
            key="factor_cat",
        )

    results = search_factors(query, cat_filter)
    st.caption(f"共 **{len(results)}** 个因子 (总计 52)")

    if not results:
        st.info("未找到匹配的因子,试试其他关键词")
        return

    # 按分类分组展示
    for cat_key in cat_filter:
        cat_results = [r for r in results if r['_cat'] == cat_key]
        if not cat_results:
            continue
        cat_label = CATEGORIES[cat_key][0]
        with st.expander(f" {cat_label}  ·  {len(cat_results)} 个", expanded=(query != "")):
            for r in cat_results:
                with st.container():
                    st.markdown(f"""
                    <div style="background:white;border:1px solid #e3e6ea;border-left:3px solid #667eea;
                                border-radius:8px;padding:12px 14px;margin:6px 0;">
                        <div style="font-size:1rem;font-weight:600;color:#0d3b66;">{r['name']}</div>
                        <div style="margin:6px 0;">
                            <code style="background:#f5f7fa;padding:3px 6px;border-radius:4px;
                                         font-size:0.85rem;color:#1f5f8b;">{r.get('formula','')}</code>
                        </div>
                        <div style="font-size:0.85rem;color:#475569;line-height:1.6;margin:4px 0;">
                            <strong style="color:#0d3b66;">原理:</strong> {r.get('原理','')}
                        </div>
                        <div style="font-size:0.85rem;color:#475569;line-height:1.6;margin:4px 0;">
                            <strong style="color:#0d3b66;">如何使用:</strong> {r.get('如何使用','')}
                        </div>
                        <div style="font-size:0.82rem;color:#94a3b8;line-height:1.6;margin-top:4px;
                                    padding-top:6px;border-top:1px dashed #e3e6ea;">
                            ️ {r.get('注意事项','')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tab 3: 我的回测
# ---------------------------------------------------------------------------

def _render_history_tab(session):
    runs = session.quant_runs
    st.markdown(
        section_divider(f"本会话历史回测 (共 {len(runs)} 条 · 浏览器刷新后清空)"),
        unsafe_allow_html=True,
    )

    if not runs:
        st.info("还没有回测结果。\n\n 切换到「 策略模板」,选一只股票和策略,点「 运行回测」试试。")
        return

    # 倒序展示
    for idx, run in enumerate(reversed(runs)):
        run_idx = len(runs) - idx
        m = run['result'].metrics
        meta = run['meta']
        label = (f"#{run_idx}  ·  {meta['symbol']} · {meta['strategy']} · "
                 f"总收益 {m.total_return:+.2%} · 夏普 {m.sharpe:.2f} · "
                 f"{meta['run_at'].strftime('%Y-%m-%d %H:%M')}")
        with st.expander(label, expanded=(idx == 0)):
            _render_single_result(run, position=f"hist_{idx}")
