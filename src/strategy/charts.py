"""
回测图表 — 净值曲线 + 回撤
配色延续 a_stock_research: #0d3b66 (主), #c14545 (回撤)
"""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_equity_with_drawdown(eq_df: pd.DataFrame) -> go.Figure:
    """
    两行子图: 70% 净值面积 + 30% 回撤面积

    Parameters
    ----------
    eq_df : pd.DataFrame
        必含列: date (str/date), equity (float), drawdown (float 0..1)
    """
    if eq_df.empty:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.7, 0.3],
        subplot_titles=("净值曲线", "回撤 (%)"),
        vertical_spacing=0.08,
    )

    # 上: 净值曲线
    fig.add_trace(
        go.Scatter(
            x=eq_df['date'],
            y=eq_df['equity'],
            fill='tozeroy',
            name='净值',
            line=dict(color='#0d3b66', width=2),
            fillcolor='rgba(13, 59, 102, 0.08)',
            hovertemplate='%{x}<br>净值 ¥%{y:,.0f}<extra></extra>',
        ),
        row=1, col=1,
    )

    # 初始资金参考线
    if 'equity' in eq_df.columns and len(eq_df) > 0:
        initial = float(eq_df['equity'].iloc[0]) if not eq_df.empty else 100000
        fig.add_hline(
            y=initial, line_dash='dash', line_color='#94a3b8', line_width=1,
            annotation_text=f'初始 ¥{initial:,.0f}',
            annotation_font_size=10, annotation_font_color='#64748b',
            row=1, col=1,
        )

    # 下: 回撤
    fig.add_trace(
        go.Scatter(
            x=eq_df['date'],
            y=eq_df['drawdown'] * 100,
            fill='tozeroy',
            name='回撤%',
            line=dict(color='#c14545', width=1.2),
            fillcolor='rgba(193, 69, 69, 0.10)',
            hovertemplate='%{x}<br>回撤 %{y:.2f}%<extra></extra>',
        ),
        row=2, col=1,
    )

    fig.update_layout(
        template='plotly_white',
        height=460,
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode='x unified',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#475569', size=11),
    )
    fig.update_xaxes(gridcolor='#E4E7ED', showgrid=False)
    fig.update_yaxes(gridcolor='#E4E7ED', tickformat=',.0f', row=1, col=1)
    fig.update_yaxes(ticksuffix='%', row=2, col=1)
    return fig


def plot_signal_chart(df: pd.DataFrame, signals: pd.Series, title: str = "") -> go.Figure:
    """
    收盘价 + 买卖信号散点图
    signals: 1=买入, -1=卖出, 0=持仓不变
    """
    if df.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df['close'],
        mode='lines', name='收盘价',
        line=dict(color='#0d3b66', width=1.5),
        hovertemplate='%{x}<br>¥%{y:.2f}<extra></extra>',
    ))

    # 买入点 (signal==1)
    buy_mask = signals == 1
    if buy_mask.any():
        fig.add_trace(go.Scatter(
            x=df.index[buy_mask],
            y=df['close'][buy_mask],
            mode='markers', name='买入',
            marker=dict(symbol='triangle-up', size=10, color='#16a34a'),
            hovertemplate='%{x}<br>买入 ¥%{y:.2f}<extra></extra>',
        ))

    # 卖出点 (signal==-1)
    sell_mask = signals == -1
    if sell_mask.any():
        fig.add_trace(go.Scatter(
            x=df.index[sell_mask],
            y=df['close'][sell_mask],
            mode='markers', name='卖出',
            marker=dict(symbol='triangle-down', size=10, color='#dc2626'),
            hovertemplate='%{x}<br>卖出 ¥%{y:.2f}<extra></extra>',
        ))

    fig.update_layout(
        template='plotly_white',
        title=title,
        height=300,
        showlegend=True,
        legend=dict(orientation='h', y=1.08, x=0, font=dict(size=10)),
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode='x unified',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#475569', size=11),
    )
    fig.update_xaxes(gridcolor='#E4E7ED')
    fig.update_yaxes(gridcolor='#E4E7ED')
    return fig
