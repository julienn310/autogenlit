"""
A股智能体分析系统 - Streamlit 版本
完整迁移自 web/index.html，保留所有指标
"""

import streamlit as st
import sys
import pandas as pd
import threading
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.data.astock_collector import AStockDataCollector
from src.analysis.financial_analyzer import FinancialAnalyzer
from src.risk.risk_analyzer import RiskAnalyzer
from src.risk.joint_risk_analyzer import JointRiskAnalyzer
from src.optimization.portfolio_optimizer import PortfolioOptimizer
from src.pdf.pdf_processor import PDFProcessor
from src.agents.pdf_risk_agent import PDFRiskAgent

# 页面配置
st.set_page_config(
    page_title="AutoGen 金融分析系统",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 25px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
    }
    .stApp { background-color: #f8f9fa; }
    .result-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        border-left: 4px solid #667eea;
    }
    .section-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #1a1a2e;
        margin: 20px 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #667eea;
    }
    .subsection-title {
        font-size: 1rem;
        font-weight: 600;
        color: #0f3460;
        margin: 15px 0 10px 0;
    }
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 15px;
        margin: 12px 0;
    }
    .metric-item {
        background: #f8f9fa;
        padding: 12px 15px;
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .metric-item .label { font-size: 0.85rem; color: #6c757d; }
    .metric-item .value { font-size: 1rem; font-weight: 600; color: #0f3460; }
    .analysis-text {
        background: #f8f9fa;
        padding: 18px;
        border-radius: 8px;
        line-height: 1.9;
        margin: 12px 0;
    }
    .advice-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin: 15px 0;
    }
    .weight-row {
        display: flex;
        align-items: center;
        gap: 15px;
        margin: 10px 0;
    }
    .weight-label { min-width: 180px; font-weight: 500; }
    .weight-bar-container { flex: 1; background: #e9ecef; border-radius: 5px; height: 25px; overflow: hidden; }
    .weight-bar-fill { height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); display: flex; align-items: center; justify-content: flex-end; padding-right: 10px; color: white; font-weight: 500; font-size: 0.85rem; }
    .weight-value { min-width: 70px; text-align: right; font-weight: 600; color: #0f3460; }
    .risk-high { border-left: 4px solid #dc3545; background: #fff5f5; padding: 15px; border-radius: 8px; margin: 10px 0; }
    .risk-medium { border-left: 4px solid #ffc107; background: #fffbf0; padding: 15px; border-radius: 8px; margin: 10px 0; }
    .risk-low { border-left: 4px solid #28a745; background: #f0fff0; padding: 15px; border-radius: 8px; margin: 10px 0; }
    .interpretation { font-size: 0.9rem; color: #6c757d; margin-top: 8px; font-style: italic; }
    div[data-testid="stHorizontalBlock"] > div:first-child .stMetric { background: white; border-radius: 10px; padding: 15px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_collectors():
    return {
        'data_collector': AStockDataCollector(),
        'financial_analyzer': FinancialAnalyzer(),
        'risk_analyzer': RiskAnalyzer(),
        'joint_risk_analyzer': JointRiskAnalyzer(),
        'portfolio_optimizer': PortfolioOptimizer(),
    }

MINIMAX_API_KEY = "sk-cp-fuHam45Wah1ay6BsZk8ACLYzV3p8_ID5NgTwJE09Kc9kCFdzwiSYzOvD2IfceEcwA-d5l8Dehm7Cks11hQa6i4moTJk-pinWhpBlR2KxsOsJ1V8zZx5S5MY"

def get_api_key():
    return MINIMAX_API_KEY

# 中文标签映射
FINANCIAL_METRICS_LABELS = {
    'roe': 'ROE (净资产收益率)',
    'roa': 'ROA (资产收益率)',
    'debt_ratio': '资产负债率',
    'gross_margin': '毛利率',
    'net_margin': '净利率',
    'current_ratio': '流动比率',
    'quick_ratio': '速动比率',
    'inventory_turnover': '存货周转率',
    'total_asset_turnover': '资产周转率',
    'earnings_per_share': '每股收益 (EPS)',
    'book_value_per_share': '每股净资产 (BVPS)',
    'ocf_per_share': '每股经营现金流 (OCFPS)',
}

RISK_METRICS_LABELS = {
    'volatility': '波动率',
    'var_95': 'VaR (95%置信度)',
    'cvar_95': 'CVaR (条件VaR)',
    'max_drawdown': '最大回撤',
    'sharpe_ratio': '夏普比率',
    'beta': '贝塔系数',
    'sortino_ratio': '索提诺比率',
    'calmar_ratio': '卡尔马比率',
    'treynor_ratio': '特雷诺比率',
    'omega_ratio': '欧米伽比率',
    'downside_dev': '下行偏差',
    'm_score': 'M-Score',
    'dsri': 'DSRI (应收账款指数)',
    'gmi': 'GMI (毛利率指数)',
    'aq_i': 'AQ_I (应收入指数)',
    'tata': 'TATA (总应计项目比率)',
    'sgi': 'SGI (营收增长指数)',
    'lvgi': 'LVGI (杠杆指数)',
    'depi': 'DEPI (折旧指数)',
    'sgai': 'SGAI (管理费用指数)',
    'm_score_interpretation': 'M-Score解读',
}

def apply_labels(metrics_dict, label_map):
    """将英文键名转换为中文标签"""
    return {label_map.get(k, k): v for k, v in metrics_dict.items()}

def display_metrics_grid(metrics_dict, cols=4, tooltips=None):
    """显示指标网格（可选tooltip字典）"""
    items = list(metrics_dict.items())
    tooltips = tooltips or {}
    for i in range(0, len(items), cols):
        row_cols = st.columns(cols)
        for j in range(cols):
            if i + j < len(items):
                k, v = items[i + j]
                title = tooltips.get(k, '')
                title_attr = f' title="{title}"' if title else ''
                with row_cols[j]:
                    st.markdown(f"""
                    <div class="metric-item"{title_attr}>
                        <span class="label">{k}</span>
                        <span class="value">{v}</span>
                    </div>
                    """, unsafe_allow_html=True)

def display_interpretation(text, label="解读"):
    """显示指标解读"""
    if text:
        st.markdown(f"<div class='interpretation'><strong>{label}:</strong> {text}</div>", unsafe_allow_html=True)

def show_loading_animation(data_loader=None, data_args=None):
    """光圈 + spinner 双动画 + 专业语句循环"""
    phases = [
        "正在检索数据源",
        "正在连接数据接口",
        "正在清洗与校验",
        "正在解析返回数据",
        "正在构建模型参数",
        "正在初始化模型",
        "正在交叉验证推演",
        "正在计算特征值",
        "正在整合多维指标",
        "正在生成风险因子",
        "正在生成风险洞察",
        "正在整理分析结果",
        "正在深度校验",
        "正在多重比对",
        "正在优化权重配置",
        "正在生成风险矩阵",
        "正在传回计算结果",
        "正在整合结果",
        "正在完成最终报告",
    ]

    if data_loader is None:
        return

    result = [None]
    error = [None]

    def load():
        try:
            result[0] = data_loader(*data_args) if data_args else data_loader()
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=load)
    t.start()

    status_ph = st.empty()
    spinner_ph = st.empty()

    spinner_html = """
    <style>
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 20px;
    }
    .spinner-ring {
        width: 50px;
        height: 50px;
        border: 4px solid #e8e8e8;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }
    .spinner-inner {
        width: 36px;
        height: 36px;
        border: 3px solid #e8e8e8;
        border-bottom: 3px solid #764ba2;
        border-radius: 50%;
        animation: spin 0.6s linear infinite reverse;
        margin-top: -46px;
    }
    </style>
    <div class="loading-container">
        <div class="spinner-ring"></div>
        <div class="spinner-inner"></div>
    </div>
    """

    idx = 0
    while t.is_alive():
        phase = phases[idx % len(phases)]
        dots = "." * ((idx % 3) + 1)
        spinner_ph.markdown(spinner_html, unsafe_allow_html=True)
        status_ph.markdown(
            f"<p style='text-align:center; color:#667eea; font-weight:600; font-size:15px; margin-top:5px;'>{phase}{dots}</p>",
            unsafe_allow_html=True
        )
        time.sleep(1.0)
        idx += 1

    t.join()
    spinner_ph.empty()
    status_ph.empty()

    if error[0]:
        raise error[0]
    return result[0]

def mscore_warning_expander():
    """返回M-Score警告的展开式提示（兼容Streamlit）"""
    with st.expander("⚠️ 模型注意事项", expanded=False):
        st.markdown("""
        <div style="font-size:13px; color:#856404; background:#fff3cd; padding:12px; border-radius:8px; border:1px solid #ffeaa7;">
        <strong>⚠️ 警告：</strong>该模型基于<strong>美股数据</strong>训练，A股判定标准可能过严，<strong>false positive 率较高</strong>，请结合实际业务情况综合判断，<strong>切勿仅凭此指标下结论</strong>。
        </div>
        """, unsafe_allow_html=True)

# 主应用
def main():
    with st.sidebar:
        st.markdown("### AutoGen 金融分析")
        st.divider()
        st.success("API Key 已配置")
        st.divider()
        page = st.radio("导航", [
            "仪表板", "财务分析", "投资组合", "风险分析", "PDF年报分析", "多智能体协作"
        ], index=0)
        st.divider()
        st.caption("系统状态: 正常运行")

    # ==================== 仪表板 ====================
    if page == "仪表板":
        st.markdown("""
        <div class="main-header">
            <h1>A股智能体分析系统</h1>
            <p>基于 AutoGen 多智能体协作的金融分析平台</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("支持股票", "5000+", "实时数据")
        with col2: st.metric("分析维度", "20+", "财务/风险/市场")
        with col3: st.metric("智能体数量", "4", "协作分析")
        with col4: st.metric("PDF分析", "支持", "年报风险识别")

        st.markdown('<div class="section-title">快速股票查询</div>', unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])
        with col1:
            symbol = st.text_input("输入股票代码", placeholder="例如: 000001", label_visibility="collapsed")
        with col2:
            st.write("")
            analyze_btn = st.button("查询", type="primary", use_container_width=True)

        if analyze_btn and symbol:
            collectors = init_collectors()
            data = show_loading_animation(
                data_loader=collectors['data_collector'].collect_stock_data,
                data_args=(symbol,)
            )

            if data and data.get('info'):
                info = data['info']
                risk_metrics = collectors['risk_analyzer'].calculate_metrics(data)

                st.markdown(f"""
                <div class="result-card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <div style="font-size:1.5rem; font-weight:700; color:#1a1a2e;">{info.get('name', symbol)} ({symbol})</div>
                            <div style="color:#6c757d; margin-top:5px;">所属行业: {info.get('industry', '未知')}</div>
                        </div>
                        <div style="font-size:2rem; color:#667eea; font-weight:bold;">{info.get('price', '-')} 元</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # 估值指标
                st.markdown('<div class="section-title">估值指标</div>', unsafe_allow_html=True)
                valuation_metrics = {
                    '市盈率(TTM)': info.get('pe_ttm', '-'),
                    '市净率': info.get('pb', '-'),
                    '市销率(TTM)': info.get('ps_ttm', '-'),
                    '总市值': f"{info.get('market_cap', 0)/1e8:.2f}亿" if info.get('market_cap') else '-',
                    '流通市值': f"{info.get('float_market_cap', 0)/1e8:.2f}亿" if info.get('float_market_cap') else '-',
                    '总股本': f"{info.get('total_share', 0)/1e8:.2f}亿" if info.get('total_share') else '-',
                }
                display_metrics_grid(valuation_metrics)

                # 风险指标
                st.markdown('<div class="section-title">风险指标</div>', unsafe_allow_html=True)
                risk_dict = apply_labels(risk_metrics.to_dict(), RISK_METRICS_LABELS)
                display_metrics_grid(risk_dict)
                display_interpretation(risk_metrics.m_score_interpretation, "M-Score解读")
            else:
                st.error("获取数据失败，请检查股票代码是否正确")

    # ==================== 财务分析 ====================
    elif page == "财务分析":
        st.markdown("### 财务分析")

        symbols_input = st.text_area("股票代码（每行一个）", placeholder="000001\n000002\n600000", height=100)

        if st.button("开始分析", type="primary") and symbols_input:
            symbols = [s.strip() for s in symbols_input.strip().split('\n') if s.strip()]
            collectors = init_collectors()

            for symbol in symbols:
                data = show_loading_animation(
                    data_loader=collectors['data_collector'].collect_stock_data,
                    data_args=(symbol,)
                )

                if data and data.get('info'):
                    info = data['info']
                    financial_metrics = collectors['financial_analyzer'].calculate_metrics(data)
                    risk_metrics = collectors['risk_analyzer'].calculate_metrics(data)

                    st.markdown(f"""
                    <div class="result-card">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div>
                                <div style="font-size:1.4rem; font-weight:700; color:#1a1a2e;">{info.get('name', symbol)} ({symbol})</div>
                                <div style="color:#6c757d;">当前价格: {info.get('price', '-')} 元</div>
                            </div>
                            <div style="font-size:1.8rem; color:#667eea; font-weight:bold;">{info.get('price', '-')} 元</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # 估值指标
                    st.markdown('<div class="section-title">估值指标</div>', unsafe_allow_html=True)
                    valuation_metrics = {
                        '市盈率(TTM)': info.get('pe_ttm', '-'),
                        '市净率': info.get('pb', '-'),
                        '市销率(TTM)': info.get('ps_ttm', '-'),
                        '总市值': f"{info.get('market_cap', 0)/1e8:.2f}亿" if info.get('market_cap') else '-',
                        '流通市值': f"{info.get('float_market_cap', 0)/1e8:.2f}亿" if info.get('float_market_cap') else '-',
                        '总股本': f"{info.get('total_share', 0)/1e8:.2f}亿" if info.get('total_share') else '-',
                    }
                    display_metrics_grid(valuation_metrics)

                    # 财务指标
                    st.markdown('<div class="section-title">财务指标</div>', unsafe_allow_html=True)
                    fin_dict = apply_labels(financial_metrics.to_dict(), FINANCIAL_METRICS_LABELS)
                    display_metrics_grid(fin_dict)

                    # 风险指标
                    st.markdown('<div class="section-title">风险指标</div>', unsafe_allow_html=True)
                    risk_dict = apply_labels(risk_metrics.to_dict(), RISK_METRICS_LABELS)
                    display_metrics_grid(risk_dict)
                    display_interpretation(risk_metrics.m_score_interpretation, "M-Score解读")

                    st.divider()

    # ==================== 投资组合 ====================
    elif page == "投资组合":
        st.markdown("### 投资组合优化")

        symbols_input = st.text_area("股票池（每行一个）", placeholder="000001\n000002\n600000\n000858", height=120)

        col1, col2 = st.columns(2)
        with col1:
            objective = st.selectbox("优化目标", ["最大夏普比率", "最小方差", "风险平价", "有效前沿"])
        with col2:
            period = st.selectbox("数据周期", ["1月", "3月", "6月", "1年"])

        risk_free_rate = st.slider("无风险利率 (%)", 0.0, 10.0, 3.0) / 100

        if st.button("优化组合", type="primary") and symbols_input:
            symbols = [s.strip() for s in symbols_input.strip().split('\n') if s.strip()]
            if len(symbols) < 2:
                st.error("至少需要2只股票进行组合优化")
            else:
                collectors = init_collectors()
                objective_map = {"最大夏普比率": "max_sharpe", "最小方差": "min_variance", "风险平价": "risk_parity", "有效前沿": "efficient_frontier"}
                period_map = {"1月": "1mo", "3月": "3mo", "6月": "6mo", "1年": "1y"}

                def load_portfolio():
                    return collectors['portfolio_optimizer'].optimize(
                        symbols=symbols,
                        period=period_map[period],
                        objective=objective_map[objective],
                        risk_free_rate=risk_free_rate
                    )

                result = show_loading_animation(data_loader=load_portfolio)

                if result.error_message:
                    st.error(result.error_message)
                else:
                    st.markdown("""
                    <div class="result-card">
                        <div style="font-size:1.3rem; font-weight:600; color:#1a1a2e;">组合优化结果</div>
                    </div>
                    """, unsafe_allow_html=True)

                    # 核心指标
                    col1, col2, col3 = st.columns(3)
                    with col1: st.metric("预期年化收益", f"{result.portfolio_metrics.expected_return:.2%}")
                    with col2: st.metric("年化波动率", f"{result.portfolio_metrics.volatility:.2%}")
                    with col3: st.metric("夏普比率", f"{result.portfolio_metrics.sharpe_ratio:.2f}")

                    # 完整风险指标
                    st.markdown('<div class="section-title">完整风险指标</div>', unsafe_allow_html=True)
                    metrics = result.portfolio_metrics
                    metrics_dict = {
                        'Sortino比率': f"{metrics.sortino_ratio:.2f}",
                        'Calmar比率': f"{metrics.calmar_ratio:.2f}",
                        'Treynor比率': f"{metrics.treynor_ratio:.2f}",
                        'Omega比率': f"{metrics.omega_ratio:.2f}",
                        '下行标准差': f"{metrics.downside_dev:.2%}",
                        '95% VaR': f"{metrics.var_95:.2%}",
                        '95% CVaR': f"{metrics.cvar_95:.2%}",
                        '最大回撤': f"{metrics.max_drawdown:.2%}",
                        '累计收益': f"{metrics.cumulative_return:.2%}",
                    }
                    display_metrics_grid(metrics_dict)

                    # 权重分配
                    st.markdown('<div class="section-title">最优权重分配</div>', unsafe_allow_html=True)
                    for symbol, weight in result.weights.items():
                        data = collectors['data_collector'].get_stock_info(symbol)
                        name = data.get('name', symbol) if data else symbol
                        st.markdown(f"""
                        <div class="weight-row">
                            <div class="weight-label">{name} ({symbol})</div>
                            <div class="weight-bar-container">
                                <div class="weight-bar-fill" style="width:{weight*100}%">{weight*100:.1f}%</div>
                            </div>
                            <div class="weight-value">{weight:.2%}</div>
                        </div>
                        """, unsafe_allow_html=True)

    # ==================== 风险分析 ====================
    elif page == "风险分析":
        st.markdown("### 风险分析")

        symbols_input = st.text_area("股票代码（每行一个）", placeholder="000001\n000002\n600000", height=100)
        analysis_mode = st.radio("分析模式", ["综合风险分析", "联合风控分析"])

        if st.button("开始分析", type="primary") and symbols_input:
            symbols = [s.strip() for s in symbols_input.strip().split('\n') if s.strip()]
            collectors = init_collectors()

            for symbol in symbols:
                data = show_loading_animation(
                    data_loader=collectors['data_collector'].collect_stock_data,
                    data_args=(symbol,)
                )

                if data and data.get('info'):
                    info = data['info']

                    if analysis_mode == "联合风控分析":
                        joint_metrics = collectors['joint_risk_analyzer'].analyze(data)
                        risk_metrics = collectors['risk_analyzer'].calculate_metrics(data)
                        joint_metrics.m_score = risk_metrics.m_score
                        joint_metrics.m_score_interpretation = risk_metrics.m_score_interpretation

                        st.markdown(f"""
                        <div class="result-card">
                            <div style="font-size:1.4rem; font-weight:700; color:#1a1a2e;">{info.get('name', symbol)} ({symbol})</div>
                            <div style="color:#6c757d; margin-top:5px;">联合风控分析 - 多模型综合风险评估</div>
                        </div>
                        """, unsafe_allow_html=True)

                        # 破产预警指标
                        st.markdown('<div class="section-title">破产预警指标</div>', unsafe_allow_html=True)
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"""
                            <div class="metric-item">
                                <span class="label">Altman Z-Score</span>
                                <span class="value">{joint_metrics.altman_z:.2f}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            display_interpretation(joint_metrics.altman_z_interpretation, "Altman Z解读")
                        with col2:
                            st.markdown(f"""
                            <div class="metric-item">
                                <span class="label">Ohlson O-Score</span>
                                <span class="value">{joint_metrics.ohlson_o:.2f}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            display_interpretation(joint_metrics.oholson_o_interpretation, "Ohlson O解读")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"""
                            <div class="metric-item">
                                <span class="label">Springate S-Score</span>
                                <span class="value">{joint_metrics.springate_s:.2f}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            display_interpretation(joint_metrics.springate_s_interpretation, "Springate S解读")
                        with col2:
                            st.markdown(f"""
                            <div class="metric-item">
                                <span class="label">Zmijewski X-Score</span>
                                <span class="value">{joint_metrics.zmijewski_x:.2f}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            display_interpretation(joint_metrics.zmijewski_x_interpretation, "Zmijewski X解读")

                        # 盈余管理指标
                        st.markdown('<div class="section-title">盈余管理指标</div>', unsafe_allow_html=True)
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"""
                            <div class="metric-item">
                                <span class="label">Jones DA (可操纵应计利润)</span>
                                <span class="value">{joint_metrics.jones_da:.4f}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            display_interpretation(joint_metrics.jones_interpretation, "Jones解读")
                        with col2:
                            st.markdown(f"""
                            <div class="metric-item">
                                <span class="label">DD AQ (应计质量损失)</span>
                                <span class="value">{joint_metrics.dd_aq:.4f}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            display_interpretation(joint_metrics.dd_interpretation, "Dechow-Dichev解读")
                        with col3:
                            st.markdown(f"""
                            <div class="metric-item">
                                <span class="label">REM Score (真实盈余管理)</span>
                                <span class="value">{joint_metrics.rem_score:.4f}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            display_interpretation(joint_metrics.rem_interpretation, "REM解读")

                        # 财务质量筛查
                        st.markdown('<div class="section-title">财务质量筛查 - Piotroski F-Score</div>', unsafe_allow_html=True)
                        st.markdown(f"""
                        <div class="metric-item">
                            <span class="label">Piotroski F-Score (0-9)</span>
                            <span class="value">{joint_metrics.piotroski_f:.0f}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        display_interpretation(joint_metrics.piotroski_f_interpretation, "Piotroski F解读")

                        # Beneish M-Score
                        st.markdown('<div class="section-title">Beneish M-Score (8变量原版)</div>', unsafe_allow_html=True)
                        st.markdown(f"""
                        <div class="metric-item" style="padding:15px; background:linear-gradient(135deg,#667eea22,#764ba222);border-radius:10px;">
                            <span class="label" style="font-size:16px;font-weight:600;">M-Score 综合得分</span>
                            <span class="value" style="font-size:28px;color:#667eea;font-weight:bold;">{joint_metrics.m_score:.2f}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        display_interpretation(joint_metrics.m_score_interpretation, "M-Score解读")

                        # 财报舞弊概率
                        st.markdown('<div class="section-title">财报舞弊/造假概率模型</div>', unsafe_allow_html=True)
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"""
                            <div class="metric-item">
                                <span class="label">Dechow F-Score (舞弊概率)</span>
                                <span class="value">{joint_metrics.dechow_f:.4f}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            display_interpretation(joint_metrics.dechow_f_interpretation, "Dechow F解读")
                        with col2:
                            st.markdown(f"""
                            <div class="metric-item">
                                <span class="label">Montier C-Score (6分制)</span>
                                <span class="value">{joint_metrics.montier_c:.2f}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            display_interpretation(joint_metrics.montier_c_interpretation, "Montier C解读")
                        with col3:
                            st.markdown(f"""
                            <div class="metric-item">
                                <span class="label">Sloan 应计异象</span>
                                <span class="value">{joint_metrics.sloan_accrual:.4f}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            display_interpretation(joint_metrics.sloan_accrual_interpretation, "Sloan解读")

                        # 综合评分
                        if joint_metrics.combined_risk_score > 0:
                            st.markdown('<div class="section-title">综合风险评分</div>', unsafe_allow_html=True)
                            risk_level_class = "risk-high" if joint_metrics.combined_risk_level in ["高", "极高"] else "risk-medium" if joint_metrics.combined_risk_level == "中" else "risk-low"
                            st.markdown(f"""
                            <div class="{risk_level_class}">
                                <div style="display:flex; justify-content:space-between; align-items:center;">
                                    <span style="font-size:1.2rem; font-weight:600;">综合风险等级: {joint_metrics.combined_risk_level}</span>
                                    <span style="font-size:1.5rem; font-weight:bold;">{joint_metrics.combined_risk_score:.0f}/100</span>
                                </div>
                                <div class="interpretation" style="margin-top:10px;">{joint_metrics.combined_risk_summary}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    else:
                        risk_metrics = collectors['risk_analyzer'].calculate_metrics(data)

                        st.markdown(f"""
                        <div class="result-card">
                            <div style="font-size:1.4rem; font-weight:700; color:#1a1a2e;">{info.get('name', symbol)} ({symbol})</div>
                            <div style="color:#6c757d; margin-top:5px;">综合风险分析</div>
                        </div>
                        """, unsafe_allow_html=True)

                        # 风险指标
                        st.markdown('<div class="section-title">市场风险指标</div>', unsafe_allow_html=True)
                        col1, col2, col3, col4 = st.columns(4)
                        with col1: st.metric("波动率", f"{risk_metrics.volatility:.2%}")
                        with col2: st.metric("VaR(95%)", f"{risk_metrics.var_95:.2%}")
                        with col3: st.metric("CVaR(95%)", f"{risk_metrics.cvar_95:.2%}")
                        with col4: st.metric("最大回撤", f"{risk_metrics.max_drawdown:.2%}")

                        st.markdown('<div class="section-title">风险调整收益指标</div>', unsafe_allow_html=True)
                        col1, col2, col3, col4 = st.columns(4)
                        with col1: st.metric("夏普比率", f"{risk_metrics.sharpe_ratio:.2f}")
                        with col2: st.metric("Sortino比率", f"{risk_metrics.sortino_ratio:.2f}")
                        with col3: st.metric("Calmar比率", f"{risk_metrics.calmar_ratio:.2f}")
                        with col4: st.metric("Beta", f"{risk_metrics.beta:.2f}")

                        col1, col2, col3 = st.columns(3)
                        with col1: st.metric("Treynor比率", f"{risk_metrics.treynor_ratio:.2f}")
                        with col2: st.metric("Omega比率", f"{risk_metrics.omega_ratio:.2f}")
                        with col3: st.metric("下行标准差", f"{risk_metrics.downside_dev:.2%}")

                        # Beneish M-Score
                        st.markdown('<div class="section-title">Beneish M-Score (8变量原版)</div>', unsafe_allow_html=True)
                        st.markdown(f"""
                        <div class="metric-item" style="padding:15px; background:linear-gradient(135deg,#667eea22,#764ba222);border-radius:10px;">
                            <span class="label" style="font-size:16px;font-weight:600;">M-Score 综合得分</span>
                            <span class="value" style="font-size:28px;color:#667eea;font-weight:bold;">{risk_metrics.m_score:.2f}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        display_interpretation(risk_metrics.m_score_interpretation, "M-Score解读")

                        # M-Score 8变量详情表格（带解释）
                        st.markdown('<div class="subsection-title">M-Score 8变量详情</div>', unsafe_allow_html=True)
                        mscore_data = [
                            ("DSRI", f"{risk_metrics.dsri:.2f}", "应收账款天数指数", "DSRI > 1.5 表明应收账款增速显著快于收入增速，可能存在虚构销售"),
                            ("GMI", f"{risk_metrics.gmi:.2f}", "毛利率指数", "GMI > 1.2 表明毛利率下降，盈利能力恶化"),
                            ("AQI", f"{risk_metrics.aq_i:.2f}", "资产质量指数", "AQI > 1.1 表明非流动资产占比上升，资产质量下降"),
                            ("TATA", f"{risk_metrics.tata:.4f}", "总应计项目比率", "TATA > 0.1（净利润中超过10%没有现金支撑），应计利润=净利润中还没变成现金的部分"),
                            ("SGI", f"{risk_metrics.sgi:.2f}", "销售增长指数", "SGI > 1 表明销售增长快，当SGI与DSRI同时偏高时，可能涉及财务操纵"),
                            ("LVGI", f"{risk_metrics.lvgi:.2f}", "杠杆指数", "LVGI > 1.5 表明负债率边际变化，杠杆上升"),
                            ("DEPI", f"{risk_metrics.depi:.2f}", "折旧指数", "DEPI < 0.8 表明折旧率下降，可能虚增资产"),
                            ("SGAI", f"{risk_metrics.sgai:.2f}", "销售管理费用指数", "SGAI异常低+AQI异常高=联合预警（费用资本化嫌疑）"),
                        ]
                        for name, val, cn_name, meaning in mscore_data:
                            st.markdown(f"""
                            <div style="display:flex; padding:12px 0; border-bottom:1px solid #eee;align-items:center;">
                                <div style="width:90px;"><strong style="font-size:16px;color:#1a1a2e;">{name}</strong><br><small style="color:#666;font-size:12px;">{cn_name}</small></div>
                                <div style="width:90px; text-align:center; color:#667eea; font-weight:bold; font-size:18px;">{val}</div>
                                <div style="flex:1; color:#444; font-size:14px; line-height:1.4;">{meaning}</div>
                            </div>
                            """, unsafe_allow_html=True)

                        # 判断标准
                        st.markdown("""
                        <div style="background:#f8f9fa; padding:15px; border-radius:8px; margin-top:15px;">
                            <h6 style="margin-bottom:10px;">📊 判断标准</h6>
                            <span style="color:#28a745;font-size:14px;">● M-Score < -1.78 财务正常</span>&nbsp;&nbsp;&nbsp;
                            <span style="color:#ffc107;font-size:14px;">● -1.78 ~ -1.21 灰色地带</span>&nbsp;&nbsp;&nbsp;
                            <span style="color:#dc3545;font-size:14px;">● M-Score > -1.21 操纵嫌疑</span>
                            <p style="margin-top:12px; margin-bottom:0; font-size:13px; color:#555;">
                                <strong>公式:</strong> M-Score = -4.840 + 0.920×DSRI + 0.528×GMI + 0.404×AQI + 0.892×SGI + 0.115×DEPI - 0.172×SGAI - 0.327×LVGI + 4.697×TATA
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                        mscore_warning_expander()

                    st.divider()

    # ==================== PDF年报分析 ====================
    elif page == "PDF年报分析":
        st.markdown("### PDF年报风险分析")

        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_file = st.file_uploader("上传PDF年报", type="pdf")
        with col2:
            company_name = st.text_input("公司名称（可选）", placeholder="贵州茅台")

        if uploaded_file and st.button("开始分析", type="primary"):
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            def load_pdf():
                processor = PDFProcessor()
                pdf_agent = PDFRiskAgent(get_api_key())
                text = processor.extract_text(tmp_path, max_pages=100)
                financial_text = processor.extract_financial_notes(text)
                if not financial_text:
                    financial_text = processor.extract_debt_related_content(text)
                if not financial_text:
                    financial_text = text[:20000]
                return pdf_agent.analyze(financial_text, company_name)

            try:
                result = show_loading_animation(data_loader=load_pdf)

                st.markdown("""
                <div class="result-card">
                    <div style="font-size:1.3rem; font-weight:600; color:#1a1a2e;">年报风险分析结果</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown(f"""
                <div class="analysis-text" style="white-space:pre-wrap;">{result}</div>
                """, unsafe_allow_html=True)
            finally:
                import os
                try: os.unlink(tmp_path)
                except: pass

    # ==================== 多智能体协作 ====================
    elif page == "多智能体协作":
        st.markdown("### AutoGen 多智能体协作分析")

        st.info("""
        本系统使用 AutoGen 框架构建多智能体协作分析系统:
        - 数据收集Agent: 获取股票数据
        - 财务分析Agent: 分析财务指标
        - 风险分析Agent: 评估市场风险
        - 投资顾问Agent: 给出投资建议
        """)

        symbol = st.text_input("股票代码", placeholder="例如: 000001")

        if st.button("启动分析", type="primary") and symbol:
            from simple_autogen.astock_autogen_system import AStockAutoGenSystem
            def load_autogen():
                system = AStockAutoGenSystem(get_api_key())
                return system.analyze_stock(symbol)
            result = show_loading_animation(data_loader=load_autogen)

            if 'error' in result:
                st.error(result['error'])
            else:
                st.markdown(f"""
                <div class="result-card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <div style="font-size:1.5rem; font-weight:700; color:#1a1a2e;">{result.get('name', '-')} ({result.get('symbol', '-')})</div>
                            <div style="color:#6c757d;">所属行业: {result.get('industry', '未知')}</div>
                        </div>
                        <div style="font-size:2rem; color:#667eea; font-weight:bold;">{result.get('price', '-')} 元</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col1, col2 = st.columns(2)
                with col1: st.metric("分析日期", result.get('analysis_date', '-'))
                with col2: st.metric("当前价格", f"{result.get('price', '-')}元")

                # 财务指标
                if result.get('financial_metrics'):
                    st.markdown('<div class="section-title">财务指标</div>', unsafe_allow_html=True)
                    fin_dict = apply_labels(result.get('financial_metrics', {}), FINANCIAL_METRICS_LABELS)
                    display_metrics_grid(fin_dict)

                # 风险指标
                if result.get('risk_metrics'):
                    st.markdown('<div class="section-title">风险指标</div>', unsafe_allow_html=True)
                    risk_dict = apply_labels(result.get('risk_metrics', {}), RISK_METRICS_LABELS)
                    display_metrics_grid(risk_dict)

                # 数据分析
                if result.get('data_analysis'):
                    st.markdown('<div class="section-title">数据分析</div>', unsafe_allow_html=True)
                    st.markdown(f"<div class='analysis-text'>{result.get('data_analysis', '')}</div>", unsafe_allow_html=True)

                # 财务分析
                if result.get('financial_analysis'):
                    st.markdown('<div class="section-title">财务分析</div>', unsafe_allow_html=True)
                    st.markdown(f"<div class='analysis-text'>{result.get('financial_analysis', '')}</div>", unsafe_allow_html=True)

                # 风险分析
                if result.get('risk_analysis'):
                    st.markdown('<div class="section-title">风险分析</div>', unsafe_allow_html=True)
                    st.markdown(f"<div class='analysis-text'>{result.get('risk_analysis', '')}</div>", unsafe_allow_html=True)

                # 投资建议
                st.markdown('<div class="section-title">投资建议</div>', unsafe_allow_html=True)
                st.markdown(f"""
                <div class="advice-box">
                    <div style="font-size:1.1rem; font-weight:600; margin-bottom:10px;">投资建议</div>
                    <div>{result.get('investment_advice', '暂无建议')}</div>
                </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()