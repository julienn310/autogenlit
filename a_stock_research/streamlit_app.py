"""
A股智能体分析系统 - Streamlit 版本
完整迁移自 web/index.html，保留所有指标
streamlit run streamlit_app.py --server.port 8502
"""

import streamlit as st
import sys
import os
import pandas as pd
import threading
import plotly.express as px
from pathlib import Path
import time

print("=== APP STARTING ===", flush=True)
print(f"Python path: {sys.path[:3]}", flush=True)
print(f"CWD: {os.getcwd()}", flush=True)
print(f"src exists: {Path('/mount/src/autogenlit/src').exists() if os.path.exists('/mount/src') else 'not on cloud'}", flush=True)

sys.path.insert(0, str(Path(__file__).parent))

from src.data.astock_collector import AStockDataCollector
from src.data.market_collector import fetch_major_indices
from src.data.news_collector import fetch_news
from src.data.announcement_collector import fetch_announcements, _classify_intent, _fetch_ann_content
from src.analysis.financial_analyzer import FinancialAnalyzer
from src.risk.risk_analyzer import RiskAnalyzer
from src.risk.joint_risk_analyzer import JointRiskAnalyzer
from src.optimization.portfolio_optimizer import PortfolioOptimizer
from src.agents.pdf_risk_agent import PDFRiskAgent
from src.agents.announcement_agent import AnnouncementAgent
from src.cache.shared_cache_stats import get_shared_cache_stats
from src.data.finchina_collector import (
    fetch_capital_flow,
    fetch_margin_trading,
    fetch_block_trades,
    fetch_shareholders_trading,
    fetch_executive_trading,
    fetch_repurchase,
    fetch_company_suppliers,
    fetch_company_customers,
    fetch_company_tendering,
    fetch_company_bidding,
    fetch_company_investment_projects,
    fetch_company_pe_vc,
    fetch_company_guarantee_events,
    fetch_company_equity_pledge,
    fetch_company_receivable_financing,
    fetch_company_suspected_relationships,
)

# UI 动画模块
from src.ui.animations import (
    animated_title, loading_pulse, loading_orb, loading_wave_bars,
    skeleton_table, skeleton_cards, animated_metric, hover_card,
    animated_progress, gradient_banner, section_divider,
    mesh_background, badge, rolling_number,
    floating_particles, glowing_card, sparkle_icon, skeleton_advanced,
)

# 页面配置
st.set_page_config(
    page_title="AutoGen 金融分析系统",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式（极简灰度配色 + 半透明强调色）
st.markdown("""
<style>
    .main-header {
        background: #4a5d6e;
        padding: 18px 25px;
        border-radius: 8px;
        color: #f5f5f5;
        text-align: center;
        margin-bottom: 18px;
    }
    .stApp { background-color: #f4f5f6; }
    .result-card {
        background: white;
        border-radius: 8px;
        padding: 16px;
        margin: 10px 0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        border-left: 3px solid #7d8b9c;
    }
    .section-title {
        font-size: 0.98rem;
        font-weight: 600;
        color: #4a5d6e;
        margin: 16px 0 8px 0;
        padding-bottom: 5px;
        border-bottom: 1px solid #d8dde2;
    }
    .subsection-title {
        font-size: 0.92rem;
        font-weight: 600;
        color: #5a6b7a;
        margin: 10px 0 6px 0;
    }
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        margin: 8px 0;
    }
    .metric-item {
        background: #f7f8fa;
        padding: 9px 12px;
        border-radius: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .metric-item .label { font-size: 0.8rem; color: #9099a3; }
    .metric-item .value { font-size: 0.92rem; font-weight: 600; color: #4a5d6e; }
    .analysis-text {
        background: #f7f8fa;
        padding: 14px;
        border-radius: 6px;
        line-height: 1.7;
        margin: 8px 0;
    }
    .advice-box {
        background: #4a5d6e;
        color: #f5f5f5;
        padding: 16px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .weight-row {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 6px 0;
    }
    .weight-label { min-width: 150px; font-weight: 500; color: #5a6b7a; }
    .weight-bar-container { flex: 1; background: #e8ebee; border-radius: 4px; height: 20px; overflow: hidden; }
    .weight-bar-fill { height: 100%; background: #6a7a8a; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px; color: white; font-weight: 500; font-size: 0.8rem; }
    .weight-value { min-width: 60px; text-align: right; font-weight: 600; color: #4a5d6e; }
    .risk-high { border-left: 3px solid #b89090; background: #f8f4f4; padding: 10px; border-radius: 6px; margin: 6px 0; }
    .risk-medium { border-left: 3px solid #c0a878; background: #f9f6f0; padding: 10px; border-radius: 6px; margin: 6px 0; }
    .risk-low { border-left: 3px solid #90b09a; background: #f4f7f5; padding: 10px; border-radius: 6px; margin: 6px 0; }
    .interpretation { font-size: 0.85rem; color: #9099a3; margin-top: 5px; font-style: italic; }
    div[data-testid="stHorizontalBlock"] > div:first-child .stMetric { background: white; border-radius: 6px; padding: 10px; }
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

def get_cached_analysis(symbol: str):
    """获取分析结果（MongoDB共享缓存）"""
    shared_cache = get_shared_cache_stats()

    # 先检查共享缓存中是否有数据
    cached_data = shared_cache.get_cached_data(symbol)
    # 缓存命中但数据不完整（缺risk_metrics/joint_metrics），当作未命中处理
    if cached_data is not None and cached_data.get('risk_metrics') and cached_data.get('joint_metrics'):
        shared_cache.record_hit(symbol)
        # 命中时只更新 analysis_count，不重复写入完整数据
        shared_cache.set_cached_data(symbol, cached_data)
        return cached_data

    shared_cache.record_miss()

    # 没有缓存，需要重新计算
    collectors = init_collectors()
    data = collectors['data_collector'].collect_stock_data(symbol)
    if not data or not data.get('info'):
        return None
    risk_metrics = collectors['risk_analyzer'].calculate_metrics(data)
    joint_metrics = collectors['joint_risk_analyzer'].analyze(data)

    result = {
        'symbol': symbol,
        'info': data.get('info', {}),
        'risk_metrics': risk_metrics.to_dict() if hasattr(risk_metrics, 'to_dict') else risk_metrics,
        'joint_metrics': joint_metrics.to_dict() if hasattr(joint_metrics, 'to_dict') else joint_metrics,
    }

    # 存入共享缓存
    shared_cache.set_cached_data(symbol, result)
    return result

MINIMAX_API_KEY = "sk-cp-fuHam45Wah1ay6BsZk8ACLYzV3p8_ID5NgTwJE09Kc9kCFdzwiSYzOvD2IfceEcwA-d5l8Dehm7Cks11hQa6i4moTJk-pinWhpBlR2KxsOsJ1V8zZx5S5MY"

def get_api_key():
    return "sk-cp-fuHam45Wah1ay6BsZk8ACLYzV3p8_ID5NgTwJE09Kc9kCFdzwiSYzOvD2IfceEcwA-d5l8Dehm7Cks11hQa6i4moTJk-pinWhpBlR2KxsOsJ1V8zZx5S5MY"

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

def generate_comprehensive_report(info, risk_metrics, joint_metrics, pdf_analysis=None, company_name=""):
    """生成综合年报分析报告（Markdown格式）"""
    from datetime import datetime

    name = info.get('name', company_name or '未知')
    symbol = info.get('symbol', '')
    date = datetime.now().strftime('%Y-%m-%d')

    # 支持 dict 或 dataclass（兼容旧代码）
    def jm(key, default=''):
        v = joint_metrics.get(key, default) if isinstance(joint_metrics, dict) else getattr(joint_metrics, key, default)
        return v if v not in (None, '', '-') else default
    def rm(key, default=''):
        v = risk_metrics.get(key, default) if isinstance(risk_metrics, dict) else getattr(risk_metrics, key, default)
        return v if v not in (None, '', '-') else default

    altman_z = float(jm('altman_z', 0) or 0)
    ohlson_o = float(jm('oholson_o', 0) or 0)
    springate_s = float(jm('springate_s', 0) or 0)
    zmijewski_x = float(jm('zmijewski_x', 0) or 0)
    jones_da = float(jm('jones_da', 0) or 0)
    dd_aq = float(jm('dd_aq', 0) or 0)
    rem_score = float(jm('rem_score', 0) or 0)
    piotroski_f = float(jm('piotroski_f', 0) or 0)
    m_score = float(rm('m_score', 0) or 0)
    dechow_f = float(jm('dechow_f', 0) or 0)
    montier_c = float(jm('montier_c', 0) or 0)
    sloan_accrual = float(jm('sloan_accrual', 0) or 0)
    combined_risk_score = float(jm('combined_risk_score', 0) or 0)
    combined_risk_level = jm('combined_risk_level', '低')
    combined_risk_summary = jm('combined_risk_summary', '-')

    report = f"""# {name} ({symbol}) 综合年报分析报告

**分析日期**: {date}

---

## 一、风险模型分析结果

### 【破产预警】

| 指标 | 数值 | 评级 | 该股解读 |
|------|------|------|----------|
| Altman Z-Score | {altman_z:.2f} | {'安全' if altman_z > 2.99 else '灰色' if altman_z > 1.81 else '高风险'} | {jm('altman_z_interpretation', '-')} |
| Ohlson O-Score | {ohlson_o:.2f} | {'正常' if ohlson_o < 0.5 else '存疑'} | {jm('oholson_o_interpretation', '-')} |
| Springate S-Score | {springate_s:.2f} | {'正常' if springate_s < 0.862 else '预警'} | {jm('springate_s_interpretation', '-')} |
| Zmijewski X-Score | {zmijewski_x:.2f} | {'正常' if zmijewski_x < 0.5 else '存疑'} | {jm('zmijewski_x_interpretation', '-')} |

**原理详述**:
- **Altman Z-Score**: Z = 1.2×(营运资本/总资产) + 1.4×(留存收益/总资产) + 3.3×(息税前利润/总资产) + 0.6×(股票市值/总负债) + 1.0×(销售收入/总资产)。数据来源：资产负债表、利润表。
- **Ohlson O-Score**: 基于8因子logistic回归：SIZE(规模)、TLTA(负债率)、WCTA(流动资产)、CLCA(流动比率)、OENEG(是否亏损)、LNTATA(资产负债率的自然对数)、INTWO(亏损年数年数)、CHIN(盈利变化)。概率>0.5表示高破产风险。
- **Springate S-Score**: S = 1.03×(营运资本/总资产) + 3.07×(息税前利润/总资产) + 1.67×(息税前利润/流动负债) + 1.4×(销售收入/总资产)。S<0.862预示破产风险。
- **Zmijewski X-Score**: X = -4.3 - 4.5×ROA + 5.7×(负债率) - 0.004×(流动比率)，经sigmoid映射为概率值，>0.5表示存疑。

---

### 【盈余管理】

| 指标 | 数值 | 该股解读 |
|------|------|----------|
| Jones DA | {jones_da:.4f} | {jm('jones_interpretation', '-')} |
| DD AQ | {dd_aq:.4f} | {jm('dd_interpretation', '-')} |
| REM Score | {rem_score:.4f} | {jm('rem_interpretation', '-')} |

**原理详述**:
- **Jones DA (可操纵应计利润)**: DA = TA - NDA，其中NDA = α₀ + α₁×(max(ΔREV-ΔREC,0)/A) + α₂×(PPE/A)。参数α₀=-0.001, α₁=0.033, α₂=0.040。数据：利润表(净利润)、现金流量表(经营活动现金流)、资产负债表(应收账款、固定资产)。DA>0表示可能存在向上盈余管理。
- **DD AQ (Dechow-Dichev应计质量)**: AQ = |ΔWC - 0.7×CFO|/A，其中ΔWC为营运资本变化，CFO为经营现金流，A为总资产。应计质量损失越大，说明现金流与应计利润匹配度越差，财报可信度越低。
- **REM Score (真实盈余管理)**: 衡量企业通过构造真实交易操纵利润的程度，包括：降价促销增加收入、减少可支配费用、过度生产降低销售成本。数据：利润表、现金流量表。

---

### 【财务质量】

| 指标 | 数值 | 评级 | 该股解读 |
|------|------|------|----------|
| Piotroski F-Score | {piotroski_f:.0f}/9 | {'优良' if piotroski_f >= 7 else '极差' if piotroski_f <= 3 else '一般'} | {jm('piotroski_f_interpretation', '-')} |

**原理详述**:
Piotroski F-Score从三大维度9个指标评分：
1. **盈利能力**(ROA>0, CFO>0, ΔROA>0)各1分
2. **负债能力**(ΔLEVER↓流动负债率下降, ΔLIQU↑流动比率上升, 无新股票增发)各1分
3. **运营效率**(ΔMARGIN↑毛利率上升, ΔTURN↑资产周转率上升, ΔSGA↓销售管理费用率下降)各1分
数据：利润表、现金流量表、资产负债表。≥7分优良，≤3分极差。

---

### 【舞弊检测】

| 指标 | 数值 | 该股解读 |
|------|------|----------|
| M-Score | {m_score:.2f} | {rm('m_score_interpretation', '-')} |
| Dechow F-Score | {dechow_f:.4f} | {jm('dechow_f_interpretation', '-')} |
| Montier C-Score | {montier_c:.2f} | {jm('montier_c_interpretation', '-')} |
| Sloan 应计异象 | {sloan_accrual:.4f} | {jm('sloan_accrual_interpretation', '-')} |

**原理详述**:
- **M-Score (Beneish 8变量模型)**: M = -4.84 + 0.92×DSRI + 0.53×GMI + 0.40×AQI + 0.89×SGI + 0.12×DEPI - 0.17×SGAI - 0.33×LVGI + 4.70×TATA。DSRI(应收账款指数)= (本期应收账款/本期收入)/(上期应收账款/上期收入); GMI(毛利率指数)= 上期毛利率/本期毛利率; AQI(资产质量指数)= (本期非流动资产/总资产)/(上期非流动资产/总资产); SGI(销售增长指数)= 本期收入/上期收入; DEPI(折旧指数)= 上期折旧率/(上期折旧率+上期净固定资产); SGAI(费用指数)= (本期费用/本期收入)/(上期费用/上期收入); LVGI(杠杆指数)= (本期负债/本期总资产)/(上期负债/上期总资产); TATA= (净利润-经营现金流)/总资产。M > -1.21 表示存在财务操纵嫌疑。
- **Dechow F-Score**: 包含11个变量预测被监管处罚/重大错报概率。关键变量：软资产比率、融资租赁、表外负债、应收账款增长、库存增长、现金流/净利润比率等。概率越高舞弊可能性越大。
- **Montier C-Score**: 6分制红旗系统，检测：AR增长率>收入增长、库存增长、GM下降、折旧率下降、其他流动资产比率、现金流/净利润背离。各1分，>3分风险较高。
- **Sloan应计异象**: Sloan(1996)发现高应计资产占比与未来负收益强相关。应计 = |净利润 - 经营现金流|/总资产。该指标越高，未来收益越差。

---

### 【综合风险评分】

**评分**: {combined_risk_score:.0f}/100 | **等级**: {combined_risk_level}

**综合解读**: {combined_risk_summary}

---

## 二、年报文本分析

"""

    if pdf_analysis:
        report += f"""{pdf_analysis}

"""
    else:
        report += """*（未获取到年报文本数据）*

"""

    report += f"""---

## 三、投资建议

基于以上风险模型分析和年报文本综合评估：

**风险提示**: 综合风险评分 {combined_risk_score:.0f}/100，风险等级 **{combined_risk_level}**。

{'建议关注：该公司财务指标正常，无明显风险信号。' if combined_risk_level == '低' else '建议谨慎：存在一定风险因素，请深入研究后决策。' if combined_risk_level == '中' else '建议回避：多项风险指标异常，建议规避。'}

---

*本报告由A股智能体分析系统自动生成，仅供参考，不构成投资建议。*
"""

    return report

def display_cache_stats():
    """显示缓存统计（从MongoDB共享数据库读取）"""
    shared_cache = get_shared_cache_stats()
    stats = shared_cache.get_stats()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("累计分析", stats['cached_symbols'], "只")
    with col2:
        st.metric("缓存命中", stats['total_hits'])
    with col3:
        st.metric("缓存未命中", stats['total_misses'])


def display_stock_ranking():
    """显示个股热度榜单（带可视化图表）"""
    shared_cache = get_shared_cache_stats()
    stats = shared_cache.get_stats()
    ranking = shared_cache.get_ranking(limit=20)

    # 标题行
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("#### 🔥 站内个股热度")
    with col2:
        total = stats.get('total_analysis', stats['total_hits'] + stats['total_misses'])
        st.metric("总分析次数", total)
    with col3:
        st.metric("上榜股票", len(ranking))

    if ranking:
        df = pd.DataFrame(ranking)
        df.columns = ["股票代码", "股票名称", "分析次数", "最近分析"]
        df.index = range(1, len(df) + 1)
        df.index.name = "排名"

        # ---- Plotly 横向柱状图（按分析次数降序）----
        top10 = df.head(10).sort_values("分析次数", ascending=True)  # 升序排列，Plotly 渲染出来是从上到下递减
        fig = px.bar(
            top10,
            x="分析次数",
            y="股票名称",
            orientation="h",
            text="分析次数",
            color="分析次数",
            color_continuous_scale="Blues",
        )
        fig.update_traces(
            textposition="outside",
            textfont_size=13,
            marker=dict(line=dict(width=0)),
        )
        fig.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title=None,
            yaxis_title=None,
            coloraxis_showscale=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
        )
        fig.update_yaxes(categoryorder="array", categoryarray=top10["股票名称"].tolist())
        st.plotly_chart(fig, use_container_width=True)

        # ---- 榜单表格 ----
        st.dataframe(df, width='stretch', hide_index=False, height=300)
    else:
        st.info("暂无热度数据")


# ---------------------------------------------------------------------------
# 模块顶层缓存函数 — 必须在 page block 之外定义,否则 @st.cache_data 行为不可靠
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def _load_company_rel(company: str, lim: int, kind: str):
    """9 类企业关系查询的统一缓存加载器。
    定义在模块顶层,确保 streamlit cache_data 的源码 hash 永远稳定。"""
    if kind == "supplier":  return fetch_company_suppliers(company, lim)
    if kind == "customer":  return fetch_company_customers(company, lim)
    if kind == "tender":    return fetch_company_tendering(company, lim)
    if kind == "bid":       return fetch_company_bidding(company, lim)
    if kind == "invest":    return fetch_company_investment_projects(company, lim)
    if kind == "pevc":      return fetch_company_pe_vc(company, lim)
    if kind == "guar":      return fetch_company_guarantee_events(company, lim)
    if kind == "pledge":    return fetch_company_equity_pledge(company, lim)
    if kind == "suspected": return fetch_company_suspected_relationships(company, lim)
    raise ValueError(kind)


def _load_company_rel_with_retry(company: str, lim: int, kind: str, retries: int = 2):
    """带超时 + 重试的加载包装(单次失败不影响其他类)。"""
    import time as _time
    last_err = None
    for attempt in range(retries + 1):
        try:
            return _load_company_rel(company, lim, kind)
        except Exception as e:
            last_err = e
            if attempt < retries:
                _time.sleep(0.5 * (attempt + 1))  # 0.5s, 1s
    raise last_err


# 主应用
def main():
    # 全局 mesh 渐变背景
    st.markdown(mesh_background(), unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### AutoGen 金融分析")
        st.divider()
        st.success("API Key 已配置")
        st.divider()
        page = st.radio("导航", [
            "仪表板", "量化策略", "资金流向", "财务分析", "个股交易数据", "企业关系查询", "投资组合", "风险分析", "PDF年报分析", "公告解读", "多智能体协作", "诊断"
        ], index=0)
        st.divider()
        st.caption("系统状态: 正常运行")

    # ==================== 仪表板 ====================
    if page == "仪表板":
        # ── 渐变 banner + 动态光标 + 浮动粒子 ──
        st.markdown(gradient_banner(
            "A股智能体分析系统",
            "二级市场深度交易数据 · 企业关系网络 · AutoGen 多智能体协作",
            icon="📈",
        ), unsafe_allow_html=True)
        st.markdown(floating_particles(), unsafe_allow_html=True)

        # 4 个 metric 数字滚动
        cols = st.columns(4)
        with cols[0]:
            st.markdown(rolling_number(5000, "覆盖股票", 1200) + badge("实时") +
                        "<div style='color:#64748b;font-size:0.78rem;margin-top:4px;'>A 股 / 港股 / 美股</div>",
                        unsafe_allow_html=True)
        with cols[1]:
            st.markdown(rolling_number(4, "数据源", 800) + badge("多源") +
                        "<div style='color:#64748b;font-size:0.78rem;margin-top:4px;'>财汇 · 新浪 · 腾讯 · Akshare</div>",
                        unsafe_allow_html=True)
        with cols[2]:
            st.markdown(rolling_number(35, "分析维度", 1500) + badge("30+") +
                        "<div style='color:#64748b;font-size:0.78rem;margin-top:4px;'>资金 / 关系 / 财务 / 风险</div>",
                        unsafe_allow_html=True)
        with cols[3]:
            st.markdown(rolling_number(4, "智能体", 1000) + badge("AutoGen") +
                        "<div style='color:#64748b;font-size:0.78rem;margin-top:4px;'>分析师 / 风控 / 策略 / 评审</div>",
                        unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)

        # ── 特色功能区(2 行 chip,8 个) ──
        st.markdown("""
        <div style="background:#f5f7fa;border:1px solid #e3e6ea;border-radius:8px;
                    padding:12px 16px;margin:6px 0 14px 0;line-height:1.9;">
            <div style="font-size:0.78rem;color:#666;letter-spacing:0.5px;margin-bottom:4px;">▍ 核心特色</div>
            <span style="display:inline-block;background:#fff;border:1px solid #d8dde3;border-radius:14px;
                         padding:3px 11px;margin:2px 4px 2px 0;font-size:0.82rem;color:#2c3e50;">
                <b style="color:#0d3b66;">二级市场深度数据</b> · 主力/特大/大/中/小单资金流向
            </span>
            <span style="display:inline-block;background:#fff;border:1px solid #d8dde3;border-radius:14px;
                         padding:3px 11px;margin:2px 4px 2px 0;font-size:0.82rem;color:#2c3e50;">
                融资融券 · 大宗交易 · 股东/高管增减持 · 股票回购
            </span>
            <span style="display:inline-block;background:#fff;border:1px solid #d8dde3;border-radius:14px;
                         padding:3px 11px;margin:2px 4px 2px 0;font-size:0.82rem;color:#2c3e50;">
                <b style="color:#2e7d32;">企业关系网络</b> · 供/需 · 招投标 · 投资 · 担保 · 出质
            </span>
            <span style="display:inline-block;background:#fff;border:1px solid #d8dde3;border-radius:14px;
                         padding:3px 11px;margin:2px 4px 2px 0;font-size:0.82rem;color:#2c3e50;">
                一键生成 <b>关系网络图</b>(主公司 + N 家关联方)
            </span>
            <span style="display:inline-block;background:#fff;border:1px solid #d8dde3;border-radius:14px;
                         padding:3px 11px;margin:2px 4px 2px 0;font-size:0.82rem;color:#2c3e50;">
                <b style="color:#6a4a8a;">AutoGen 多智能体</b> 协作完成投研报告
            </span>
            <span style="display:inline-block;background:#fff;border:1px solid #d8dde3;border-radius:14px;
                         padding:3px 11px;margin:2px 4px 2px 0;font-size:0.82rem;color:#2c3e50;">
                <b>PDF 年报</b> 风险识别 · 自动提取关键事项
            </span>
            <span style="display:inline-block;background:#fff;border:1px solid #d8dde3;border-radius:14px;
                         padding:3px 11px;margin:2px 4px 2px 0;font-size:0.82rem;color:#2c3e50;">
                实时公告解读 · 风险/资金/情绪三维度扫描
            </span>
            <span style="display:inline-block;background:#fff;border:1px solid #d8dde3;border-radius:14px;
                         padding:3px 11px;margin:2px 4px 2px 0;font-size:0.82rem;color:#2c3e50;">
                资金/财务/公告 三大数据源打通 · <b>缓存 60 分钟</b>
            </span>
        </div>
        """, unsafe_allow_html=True)

        # ========== 市场成交额集中度（Top5% 警示）============
        @st.cache_data(ttl=3600, show_spinner=False)
        def _load_concentration():
            from src.data.market_collector import fetch_top5_concentration, get_concentration_history
            today = fetch_top5_concentration()
            history = get_concentration_history(120)
            return today, history

        with st.spinner("加载市场结构指标（首次需约50秒）..."):
            try:
                conc_today, conc_history = _load_concentration()
            except Exception:
                conc_today, conc_history = None, []

        # 若当日数据获取失败（API不可用），用历史模拟数据补充
        if not conc_today and conc_history:
            conc_today = conc_history[-1]

        def _render_conc_banner(conc_val):
            """根据集中度数值返回不同颜色风格的HTML banner"""
            if conc_val >= 48:
                color = '#d03b3b'
                label = '极度泡沫化'
                bg = '#fff5f5'
                border = '#d03b3b'
            elif conc_val >= 45:
                color = '#ec835a'
                label = '高热区'
                bg = '#fff8f5'
                border = '#ec835a'
            elif conc_val >= 38:
                color = '#2a78d6'
                label = '正常区间'
                bg = '#f0f5ff'
                border = '#2a78d6'
            else:
                color = '#0ca30c'
                label = '分散偏低'
                bg = '#f0fff0'
                border = '#0ca30c'
            return color, label, bg, border

        if conc_today:
            c = conc_today
            val = c['concentration']
            color, label, bg, border = _render_conc_banner(val)

            # 详细信息（仅当日真实数据有，演示历史数据没有）
            has_detail = all(k in c for k in ('total_stocks', 'top5_stocks', 'top5_amount', 'total_amount'))
            detail_html = (
                f"当日全市场 {c['total_stocks']} 只股票中，前 {c['top5_stocks']} 只（Top 5%）"
                f"贡献成交额 <strong>{c['top5_amount']:.0f}亿</strong> / 总成交额 <strong>{c['total_amount']:.0f}亿</strong>"
                if has_detail else
                f"<strong>演示数据</strong> — 云端部署后显示真实全市场统计"
            )

            st.markdown(f"""
            <div style="background:{bg};border-left:5px solid {border};border-radius:10px;
                        padding:16px 20px;margin:10px 0 14px 0;">
                <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
                    <div>
                        <div style="font-size:0.8rem;color:#888;margin-bottom:4px;">
                            全市场成交额集中度指标 · Top 5% 个股成交额占比
                        </div>
                        <div style="display:flex;align-items:baseline;gap:10px;">
                            <span style="font-size:2.8rem;font-weight:900;color:{color};">{val:.1f}<span style="font-size:1.2rem;">%</span></span>
                            <span style="font-size:0.9rem;color:{color};font-weight:600;">{label}</span>
                        </div>
                        <div style="font-size:0.78rem;color:#888;margin-top:4px;">
                            {detail_html}
                        </div>
                    </div>
                    <div style="text-align:right;min-width:160px;">
                        <div style="font-size:0.75rem;color:#888;">历史均值</div>
                        <div style="font-size:1.2rem;font-weight:700;color:#52514e;">
                            {sum(h['concentration'] for h in conc_history)/max(len(conc_history),1):.1f}%
                        </div>
                        <div style="font-size:0.72rem;color:#888;margin-top:2px;">
                            近 {len(conc_history)} 个交易日
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 历史走势图：集中度（上） + 上证指数（下）共享X轴
            if len(conc_history) >= 2:
                import plotly.graph_objects as go
                from plotly.subplots import make_subplots

                df_hist = pd.DataFrame(conc_history)
                dates = df_hist['date'].tolist()

                # 拉取上证指数近120日数据，与集中度日期对齐
                @st.cache_data(ttl=3600, show_spinner=False)
                def _load_sh_index(d_start):
                    try:
                        from src.data.market_collector import fetch_major_indices_history
                        hist = fetch_major_indices_history('sh000001', d_start)
                        # 标准化为 {date, value}
                        rows = []
                        for d, vals in hist.items():
                            rows.append({'date': d, 'close': float(vals[-1]) if vals else 0})
                        rows.sort(key=lambda x: x['date'])
                        return rows
                    except Exception:
                        return []

                d_start = conc_history[0]['date'] if conc_history else None
                sh_history = _load_sh_index(d_start)

                # 把上证指数对齐到集中度日期（用前值填充缺失日）
                if sh_history:
                    sh_by_date = {r['date']: r['close'] for r in sh_history}
                    sh_aligned = []
                    last_val = None
                    for d in dates:
                        if d in sh_by_date:
                            last_val = sh_by_date[d]
                        sh_aligned.append(last_val if last_val else None)
                    # 简单归一化：当日值 / 区间首日值 × 100
                    base = next((v for v in sh_aligned if v), 100)
                    sh_indexed = [(v / base * 100) if v else None for v in sh_aligned]
                else:
                    sh_indexed = [None] * len(dates)

                # 创建上下双子图，共享X轴
                fig = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    row_heights=[0.55, 0.45],
                    vertical_spacing=0.08,
                )

                # ── 上：集中度 ──
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=df_hist['concentration'],
                    mode='lines+markers',
                    name='集中度',
                    line=dict(color='#667eea', width=2),
                    marker=dict(size=4, color='#667eea'),
                    fill='tozeroy',
                    fillcolor='rgba(102,126,234,0.10)',
                    hovertemplate='%{x}<br>集中度: %{y:.1f}%<extra></extra>',
                ), row=1, col=1)
                fig.add_hrect(y0=45, y1=60, fillcolor='#ec835a', opacity=0.12,
                              line_width=0, row=1, col=1)
                fig.add_hline(y=38, line_dash='dash', line_color='#aaa', line_width=1,
                              annotation_text='38%下限', annotation_font_size=8, annotation_font_color='#888',
                              row=1, col=1)

                # ── 下：上证指数（归一化）──
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=sh_indexed,
                    mode='lines',
                    name='上证指数(归一化)',
                    line=dict(color='#c00', width=1.6),
                    fill='tozeroy',
                    fillcolor='rgba(204,0,0,0.05)',
                    connectgaps=True,
                    hovertemplate='%{x}<br>上证: %{y:.2f}<extra></extra>',
                ), row=2, col=1)

                fig.update_layout(
                    height=360,
                    margin=dict(l=6, r=6, t=20, b=10),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(size=9),
                    showlegend=True,
                    legend=dict(orientation='h', y=1.06, x=0, font=dict(size=9)),
                    hovermode='x unified',
                )
                # 集中度子图Y轴
                fig.update_yaxes(
                    title_text=None, showgrid=True, gridcolor='#f0f0f0',
                    zeroline=False, range=[20, 60], fixedrange=True,
                    row=1, col=1,
                )
                # 指数子图Y轴
                fig.update_yaxes(
                    title_text=None, showgrid=True, gridcolor='#f0f0f0',
                    zeroline=False, fixedrange=True,
                    tickformat='.1f',
                    row=2, col=1,
                )
                # X轴：只在底部显示
                fig.update_xaxes(
                    showgrid=False, zeroline=False, fixedrange=True,
                    tickangle=-30, tickfont=dict(size=8), nticks=8,
                    row=1, col=1,
                )
                fig.update_xaxes(
                    showgrid=False, zeroline=False, fixedrange=True,
                    tickangle=-30, tickfont=dict(size=8), nticks=8,
                    row=2, col=1,
                )
                st.plotly_chart(fig, use_container_width=True)

                # 解读
                latest_val = conc_history[-1]['concentration'] if conc_history else 0
                if latest_val >= 45:
                    st.caption(f"当前集中度 {latest_val:.1f}% 已进入历史高风险区间（阈值45%）。市场见顶/风格切换风险较高，建议关注资金轮动信号。", unsafe_allow_html=False)
                elif latest_val >= 38:
                    st.caption(f"当前集中度 {latest_val:.1f}% 处于正常区间，市场结构健康。", unsafe_allow_html=False)
                else:
                    st.caption(f"当前集中度 {latest_val:.1f}% 偏低，市场资金分散，低量个股活跃。", unsafe_allow_html=False)
        else:
            st.info("集中度指标数据获取失败（当前仅支持云端访问），部署后可显示全市场结构监控")

        st.divider()

        # ========== 三栏并排：全球市场 | 个股热度 | 舆情快讯 ==========
        col_market, col_rank, col_sentiment = st.columns([1, 1, 1])

        # ── 左栏：全球市场 ──
        with col_market:
            st.markdown('<div class="section-title">' + sparkle_icon() + ' 市场行情</div>', unsafe_allow_html=True)
            with st.spinner("加载中..."):
                try:
                    indices = fetch_major_indices()
                except Exception:
                    indices = []

            if indices:
                indices_sorted = sorted(indices, key=lambda x: x['change_pct'], reverse=True)
                A_CODES = {'sh000001', 'sz399001', 'sz399006', 'sh000300', 'sh000016', 'sh000905', 'sh000688'}
                a_stocks = [i for i in indices_sorted if i['code'] in A_CODES][:7]
                g_stocks = [i for i in indices_sorted if i['code'] not in A_CODES][:7]

                def render_idx(d):
                    pct = d['change_pct']
                    color = '#c00' if pct > 0 else ('#1F4E79' if pct < 0 else '#888')
                    sign = '+' if pct >= 0 else ''
                    return f"""<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #eee;">
                        <span style="font-size:0.82rem;min-width:90px;">{d['name']}</span>
                        <span style="color:{color};font-weight:700;font-size:0.82rem;">{sign}{pct:.2f}%</span>
                        <span style="color:#666;font-size:0.78rem;">{d['price']:.2f}</span>
                    </div>"""

                st.markdown("**A股**", unsafe_allow_html=True)
                for d in a_stocks:
                    st.markdown(render_idx(d), unsafe_allow_html=True)
                st.markdown("**全球**", unsafe_allow_html=True)
                for d in g_stocks:
                    st.markdown(render_idx(d), unsafe_allow_html=True)
            else:
                st.caption("暂无数据")

        # ── 中栏：站内个股热度 ──
        with col_rank:
            st.markdown('<div class="section-title">' + sparkle_icon('#f59e0b') + ' 站内个股热度</div>', unsafe_allow_html=True)
            shared_cache = get_shared_cache_stats()
            stats = shared_cache.get_stats()
            ranking = shared_cache.get_ranking(limit=8)

            total = stats.get('total_analysis', stats['total_hits'] + stats['total_misses'])
            st.caption(f"总分析 {total} 次 · {len(ranking)} 只上榜")

            if ranking:
                df = pd.DataFrame(ranking)
                df.columns = ["代码", "名称", "次数", "时间"]
                for i, row in df.head(8).iterrows():
                    pct = row['次数'] / max(total, 1) * 100
                    bar_w = int(pct)
                    st.markdown(f"""
                    <div style="display:flex;align-items:center;gap:6px;margin:3px 0;">
                        <span style="font-size:0.75rem;min-width:55px;color:#555;">{row['名称']}</span>
                        <div style="flex:1;background:#e9ecef;border-radius:3px;height:14px;overflow:hidden;">
                            <div style="width:{bar_w*2}%;height:100%;background:linear-gradient(90deg,#667eea,#764ba2);border-radius:3px;"></div>
                        </div>
                        <span style="font-size:0.72rem;color:#888;min-width:28px;text-align:right;">{row['次数']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("暂无热度数据")

        # ── 右栏：舆情 ──
        with col_sentiment:
            st.markdown('<div class="section-title">' + sparkle_icon('#10b981') + ' 舆情动态</div>', unsafe_allow_html=True)
            with st.spinner("加载舆情..."):
                try:
                    news_data = fetch_news()
                except Exception:
                    news_data = {'flash': [], 'timeline': [], 'xueqiu_hot': []}

            tl = news_data.get('timeline', [])[:10]

            if tl:
                st.markdown("**最新资讯**", unsafe_allow_html=True)
                for n in tl:
                    t = n.get('time', '')[5:] if n.get('time') else ''
                    title = n.get('title', '')
                    short = title[:32] + '...' if len(title) > 32 else title
                    src = n.get('source', '')
                    with st.expander(f"{t} {short}", expanded=False):
                        st.markdown(f"**{title}**")
                        if n.get('url'):
                            st.markdown(f"[查看详情 →]({n['url']})")
                        st.caption(f"来源: {src}")

        st.divider()

        # ========== 快速查询（收窄） ==========
        col_q1, col_q2, col_q3 = st.columns([3, 1, 1])
        with col_q1:
            symbol = st.text_input("输入股票代码查询", placeholder="例如: 000001", label_visibility="collapsed")
        with col_q2:
            analyze_btn = st.button("分析", type="primary", use_container_width=True)
        with col_q3:
            st.page_link("https://www.eastmoney.com", label="财报", icon="📑")

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

    # ==================== 资金流向 ====================
    elif page == "资金流向":
        st.markdown("""
        <div class="main-header" style="padding:15px 25px;margin-bottom:15px;">
            <h2 style="margin:0;">ETF基金资金流向</h2>
            <p style="margin:5px 0 0 0;opacity:0.85;">近30个交易日每日净流入/流出监控</p>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner("正在加载资金流向数据..."):
            try:
                from src.data.market_collector import fetch_etf_data, fetch_etf_daily_flows
                etf_list = fetch_etf_data()
                daily_flows = fetch_etf_daily_flows()
            except Exception as e:
                etf_list = []
                daily_flows = {}
                st.error(f"数据加载失败: {e}")

        import plotly.graph_objects as go

        # ========== 板块资金流向总览 ==========
        with st.spinner("加载板块资金流向..."):
            try:
                from src.data.market_collector import fetch_sector_flow_data
                sector_flows = fetch_sector_flow_data()
            except Exception as ex:
                sector_flows = []
                _fetch_err = str(ex)

        if not sector_flows:
            st.warning("板块资金流向数据获取失败（网络或API问题），请稍后刷新重试")
        else:
            is_demo = any(s.get('demo') for s in sector_flows)
            if is_demo:
                st.info("当前显示演示数据（API暂时不可用），实际数据部署到云端后自动恢复")

            # ── 汇总统计 ────────────────────────────────────────────────
            in_flows = [s for s in sector_flows if s['flow_yi'] > 0]
            out_flows = [s for s in sector_flows if s['flow_yi'] < 0]
            total_in = sum(s['flow_yi'] for s in in_flows)
            total_out = sum(s['flow_yi'] for s in out_flows)
            net = total_in + total_out
            top_flows = sector_flows[:15]

            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.metric("🔵 资金流入板块", f"{len(in_flows)}个",
                          f"{total_in:+.1f}亿", delta_color="normal")
            with col_b:
                st.metric("🔴 资金流出板块", f"{len(out_flows)}个",
                          f"{total_out:+.1f}亿", delta_color="normal")
            with col_c:
                st.metric("📊 全市场主力净流入", f"{net:+.1f}亿",
                          delta_color="normal")
            with col_d:
                st.metric("🏆 最强净流入", top_flows[0]['name'] if top_flows else "—",
                          f"{top_flows[0]['flow_yi']:+.1f}亿", delta_color="normal")

            st.markdown("")  # spacer
            st.markdown("")  # spacer

            # ── 板块主力净流入统计柱状图 ─────────────────────────────────
            # ── 板块主力净流入统计柱状图（高→低排序）─────────────────────────
            sorted_sectors = sorted(sector_flows, key=lambda x: x['flow_yi'], reverse=True)
            # Plotly horizontal bar 默认从下到上 → reverse 让最高在最上
            sorted_sectors = list(reversed(sorted_sectors))

            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=[s['flow_yi'] for s in sorted_sectors],
                y=[s['name'] for s in sorted_sectors],
                orientation='h',
                marker_color=['rgba(140,160,140,0.65)' if s['flow_yi'] >= 0 else 'rgba(170,130,130,0.65)' for s in sorted_sectors],
                text=[f"{s['flow_yi']:+.1f}" for s in sorted_sectors],
                textposition='outside',
                textfont=dict(size=9, color='#6a7785'),
                hovertemplate='%{y}<br>净流入: %{x:+.1f}亿<extra></extra>',
            ))
            fig_bar.update_layout(
                height=max(300, len(sorted_sectors) * 28),
                margin=dict(l=8, r=60, t=8, b=8),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=9, color='#6a7785'),
                showlegend=False,
                xaxis=dict(
                    title=None, showgrid=True, gridcolor='#e8ebee',
                    zeroline=True, zerolinecolor='#c8d0d8', zerolinewidth=1,
                ),
                yaxis=dict(
                    title=None, showgrid=False, tickfont=dict(size=9),
                    categoryorder='array', categoryarray=[s['name'] for s in sorted_sectors],
                ),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        if etf_list:
            rows = []
            for i in range(0, len(etf_list), 3):
                rows.append(etf_list[i:i+3])

            for row_etfs in rows:
                cols = st.columns(3)
                for ci, row_etf in enumerate(row_etfs):
                    with cols[ci]:
                        code = row_etf['code']
                        name = row_etf['name']
                        price = row_etf['price']
                        pct = row_etf['change_pct']
                        sign = '+' if pct >= 0 else ''
                        pct_color = '#c00' if pct > 0 else ('#1F4E79' if pct < 0 else '#888')

                        daily = daily_flows.get(code, [])
                        dates = [d['date'][5:] for d in daily]
                        values = [d['flow'] for d in daily]
                        bar_colors = ['#1F4E79' if v >= 0 else '#dc3545' for v in values]
                        max_abs = max(abs(v) for v in values) if values else 1

                        # 近30日合计
                        total_30d = sum(values)
                        total_str = f"{total_30d:+,.1f}亿"

                        fig = go.Figure()
                        fig.add_trace(go.Bar(
                            x=dates,
                            y=values,
                            marker_color=bar_colors,
                            text=[f"{v:+.0f}" if abs(v) >= 10 else f"{v:+.1f}" for v in values],
                            textposition='outside',
                            textfont_size=7,
                            hovertemplate="%{x}<br>净流入: %{y:+.1f}亿<extra></extra>",
                        ))
                        fig.update_layout(
                            height=160,
                            margin=dict(l=4, r=4, t=4, b=4),
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font=dict(size=9),
                            showlegend=False,
                            xaxis=dict(tickangle=-30, showgrid=False, zeroline=False, tickfont=dict(size=7), type='category'),
                            yaxis=dict(
                                title=None, showgrid=True, gridcolor='#f0f0f0',
                                zeroline=True, zerolinecolor='#ccc',
                                range=[-max_abs * 1.3, max_abs * 1.3],
                                tickfont=dict(size=7),
                            ),
                        )

                        card_html = f'''
                        <div style="background:white;border-radius:10px;padding:12px 12px 8px;margin:4px 0;box-shadow:0 1px 6px rgba(0,0,0,0.08);border-top:3px solid {pct_color};">
                            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                                <div>
                                    <div style="font-weight:700;font-size:0.88rem;color:#1a1a2e;">{name}</div>
                                    <div style="font-size:1.4rem;font-weight:700;color:#1a1a2e;line-height:1.1;">{price:.3f}</div>
                                </div>
                                <div style="text-align:right;">
                                    <div style="font-size:1rem;font-weight:700;color:{pct_color};">{sign}{pct:.2f}%</div>
                                    <div style="font-size:0.68rem;color:#888;">{'资金流入' if pct >= 0 else '资金流出'}</div>
                                </div>
                            </div>
                            <div style="background:#f8f9fa;border-radius:6px;padding:6px 8px;text-align:center;margin-bottom:4px;">
                                <div style="font-size:0.68rem;color:#888;">近30日净流入合计</div>
                                <div style="font-size:1rem;font-weight:700;color:{'#1F4E79' if total_30d >= 0 else '#dc3545'};">{total_str}</div>
                            </div>
                        </div>
                        '''
                        st.markdown(card_html, unsafe_allow_html=True)
                        st.plotly_chart(fig, use_container_width=True)

        st.caption("柱状图蓝色=资金流入，红色=资金流出；数据基于每日成交额与涨跌幅估算")

    # ==================== 财务分析 ====================
    elif page == "财务分析":
        st.markdown("""
        <div class="main-header" style="padding:15px 25px;margin-bottom:15px;">
            <h2 style="margin:0;">财务分析</h2>
            <p style="margin:5px 0 0 0;opacity:0.85;">多维度财报指标与估值分析</p>
        </div>
        """, unsafe_allow_html=True)

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
        st.markdown("""
        <div class="main-header" style="padding:15px 25px;margin-bottom:15px;">
            <h2 style="margin:0;">投资组合优化</h2>
            <p style="margin:5px 0 0 0;opacity:0.85;">均值-方差优化与风险平价模型</p>
        </div>
        """, unsafe_allow_html=True)

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
        st.markdown("""
        <div class="main-header" style="padding:15px 25px;margin-bottom:15px;">
            <h2 style="margin:0;">风险分析</h2>
            <p style="margin:5px 0 0 0;opacity:0.85;">Altman Z-Score / Ohlson O-Score / M-Score 多维风控模型</p>
        </div>
        """, unsafe_allow_html=True)

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

                        # 标题卡片
                        st.markdown(f"""
                        <div style="background:linear-gradient(135deg,#8fa8c0,#7b9cb8);padding:20px;border-radius:12px;color:white;margin-bottom:20px;">
                            <div style="font-size:1.5rem;font-weight:700;">{info.get('name', symbol)} ({symbol})</div>
                            <div style="opacity:0.9;margin-top:5px;">联合风控分析 - 多模型综合风险评估</div>
                        </div>
                        """, unsafe_allow_html=True)

                        # 破产预警指标 - 莫兰迪蓝灰色
                        st.markdown("""
                        <div style="background:#f5f6f8;border-radius:12px;padding:20px;margin:15px 0;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;">
                                <span style="font-size:1.1rem;font-weight:600;color:#5a6b7a;">一、破产预警指标</span>
                                <span class="tooltip-icon" title="基于财务比率预测企业破产风险的模型组合">❓</span>
                            </div>
                            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:18px;">
                                <div style="background:#fff;padding:18px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="font-size:0.95rem;color:#7a8a96;">Altman Z-Score</span>
                                        <span class="tooltip-icon" title=" Altman Z = 1.2×营运资本/总资产 + 1.4×留存收益/总资产 + 3.3×息税前利润/总资产 + 0.6×股票市值/总负债 + 1.0×销售收入/总资产">❓</span>
                                    </div>
                                    <div style="font-size:2.2rem;font-weight:700;color:#3d4f5f;margin:8px 0;">{:.2f}</div>
                                    <div style="font-size:0.88rem;color:#5a7082;line-height:1.5;">{}</div>
                                </div>
                                <div style="background:#fff;padding:18px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="font-size:0.95rem;color:#7a8a96;">Ohlson O-Score</span>
                                        <span class="tooltip-icon" title=" Ohlson O = -1.32 - 0.407×规模 + 6.03×负债/资产 - 1.43×流动资产/负债 + 0.076×流动比率 - 1.72×是否亏损">❓</span>
                                    </div>
                                    <div style="font-size:2.2rem;font-weight:700;color:#3d4f5f;margin:8px 0;">{:.2f}</div>
                                    <div style="font-size:0.88rem;color:#5a7082;line-height:1.5;">{}</div>
                                </div>
                                <div style="background:#fff;padding:18px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="font-size:0.95rem;color:#7a8a96;">Springate S-Score</span>
                                        <span class="tooltip-icon" title=" Springate S = 1.03×营运资本/总资产 + 3.07×息税前利润/总资产 + 1.67×息税前利润/流动负债 + 1.4×销售收入/总资产">❓</span>
                                    </div>
                                    <div style="font-size:2.2rem;font-weight:700;color:#3d4f5f;margin:8px 0;">{:.2f}</div>
                                    <div style="font-size:0.88rem;color:#5a7082;line-height:1.5;">{}</div>
                                </div>
                                <div style="background:#fff;padding:18px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="font-size:0.95rem;color:#7a8a96;">Zmijewski X-Score</span>
                                        <span class="tooltip-icon" title=" Zmijewski X = -4.3 - 4.5×负债/资产 + 5.7×负债/资产² - 0.004×流动比率">❓</span>
                                    </div>
                                    <div style="font-size:2.2rem;font-weight:700;color:#3d4f5f;margin:8px 0;">{:.2f}</div>
                                    <div style="font-size:0.88rem;color:#5a7082;line-height:1.5;">{}</div>
                                </div>
                            </div>
                        </div>
                        """.format(
                            joint_metrics.altman_z, joint_metrics.altman_z_interpretation,
                            joint_metrics.ohlson_o, joint_metrics.oholson_o_interpretation,
                            joint_metrics.springate_s, joint_metrics.springate_s_interpretation,
                            joint_metrics.zmijewski_x, joint_metrics.zmijewski_x_interpretation
                        ), unsafe_allow_html=True)

                        # 盈余管理指标 - 莫兰迪灰绿色
                        st.markdown("""
                        <div style="background:#f5f7f5;border-radius:12px;padding:20px;margin:15px 0;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;">
                                <span style="font-size:1.1rem;font-weight:600;color:#5a6b5a;">二、盈余管理指标</span>
                                <span class="tooltip-icon" title="检测企业是否通过会计手段操纵利润的模型">❓</span>
                            </div>
                            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:18px;">
                                <div style="background:#fff;padding:18px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="font-size:0.95rem;color:#7a8a7a;">Jones DA</span>
                                        <span class="tooltip-icon" title=" Jones模型：可操纵应计利润 = 净利润 - 经营现金流，数值越大盈余管理可能性越高">❓</span>
                                    </div>
                                    <div style="font-size:2rem;font-weight:700;color:#3d4f3d;margin:8px 0;">{:.4f}</div>
                                    <div style="font-size:0.85rem;color:#5a705a;line-height:1.4;">{}</div>
                                </div>
                                <div style="background:#fff;padding:18px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="font-size:0.95rem;color:#7a8a7a;">DD AQ</span>
                                        <span class="tooltip-icon" title=" Dechow-Dichev模型：应计质量 = 经营现金流波动/总资产，应计质量损失越大，财报可信赖度越低">❓</span>
                                    </div>
                                    <div style="font-size:2rem;font-weight:700;color:#3d4f3d;margin:8px 0;">{:.4f}</div>
                                    <div style="font-size:0.85rem;color:#5a705a;line-height:1.4;">{}</div>
                                </div>
                                <div style="background:#fff;padding:18px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="font-size:0.95rem;color:#7a8a7a;">REM Score</span>
                                        <span class="tooltip-icon" title=" 真实盈余管理：企业通过构造真实交易（降价促销、减少研发）来操纵利润">❓</span>
                                    </div>
                                    <div style="font-size:2rem;font-weight:700;color:#3d4f3d;margin:8px 0;">{:.4f}</div>
                                    <div style="font-size:0.85rem;color:#5a705a;line-height:1.4;">{}</div>
                                </div>
                            </div>
                        </div>
                        """.format(joint_metrics.jones_da, joint_metrics.jones_interpretation, joint_metrics.dd_aq, joint_metrics.dd_interpretation, joint_metrics.rem_score, joint_metrics.rem_interpretation), unsafe_allow_html=True)

                        # 财务质量筛查 - 莫兰迪灰蓝色
                        st.markdown(f"""
                        <div style="background:#f4f6f8;border-radius:12px;padding:20px;margin:15px 0;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;">
                                <span style="font-size:1.1rem;font-weight:600;color:#5a6b7a;">三、财务质量筛查</span>
                                <span class="tooltip-icon" title=" Piotroski F-Score：9分制，从盈利能力、负债能力、运营效率三个维度评估财务健康度">❓</span>
                            </div>
                            <div style="background:#fff;padding:25px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);text-align:center;">
                                <div style="font-size:0.95rem;color:#7a8a96;">Piotroski F-Score</div>
                                <div style="font-size:3.5rem;font-weight:700;color:#4a5d6d;margin:10px 0;">{joint_metrics.piotroski_f:.0f}<span style="font-size:1.5rem;color:#8a9aaa;">/9</span></div>
                                <div style="font-size:0.95rem;color:#5a7082;line-height:1.5;">{joint_metrics.piotroski_f_interpretation}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # 财报舞弊概率 - 莫兰迪灰紫色
                        st.markdown("""
                        <div style="background:#f6f5f7;border-radius:12px;padding:20px;margin:15px 0;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;">
                                <span style="font-size:1.1rem;font-weight:600;color:#6b5a7a;">四、财报舞弊/造假概率</span>
                                <span class="tooltip-icon" title="综合多个舞弊检测模型，预测企业财报造假可能性">❓</span>
                            </div>
                            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:18px;">
                                <div style="background:#fff;padding:18px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="font-size:0.95rem;color:#8a7a8a;">Dechow F-Score</span>
                                        <span class="tooltip-icon" title=" Dechow舞弊模型：包含11个变量（软资产、融资租赁等表外负债），直接预测被监管处罚概率">❓</span>
                                    </div>
                                    <div style="font-size:2rem;font-weight:700;color:#4d3d4d;margin:8px 0;">{:.4f}</div>
                                    <div style="font-size:0.85rem;color:#5a4a5a;line-height:1.4;">{}</div>
                                </div>
                                <div style="background:#fff;padding:18px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="font-size:0.95rem;color:#8a7a8a;">Montier C-Score</span>
                                        <span class="tooltip-icon" title=" Montier C-Score：6分制，综合应计项目、应收账款、库存等指标评估舞弊风险">❓</span>
                                    </div>
                                    <div style="font-size:2rem;font-weight:700;color:#4d3d4d;margin:8px 0;">{:.2f}</div>
                                    <div style="font-size:0.85rem;color:#5a4a5a;line-height:1.4;">{}</div>
                                </div>
                                <div style="background:#fff;padding:18px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="font-size:0.95rem;color:#8a7a8a;">Sloan 应计异象</span>
                                        <span class="tooltip-icon" title=" Sloan应计异象：高应计资产占比与未来负收益强相关，应计占比越高越危险">❓</span>
                                    </div>
                                    <div style="font-size:2rem;font-weight:700;color:#4d3d4d;margin:8px 0;">{:.4f}</div>
                                    <div style="font-size:0.85rem;color:#5a4a5a;line-height:1.4;">{}</div>
                                </div>
                            </div>
                        </div>
                        """.format(joint_metrics.dechow_f, joint_metrics.dechow_f_interpretation, joint_metrics.montier_c, joint_metrics.montier_c_interpretation, joint_metrics.sloan_accrual, joint_metrics.sloan_accrual_interpretation), unsafe_allow_html=True)

                        # 综合评分 - 莫兰迪配色
                        if joint_metrics.combined_risk_score > 0:
                            risk_colors = {"极高": "#8b5a5a", "高": "#9b7a6a", "中": "#a89a7a", "低": "#6a8a7a"}
                            bg_colors = {"极高": "#f8f5f5", "高": "#f7f4f2", "中": "#f6f5f2", "低": "#f2f5f4"}
                            border_colors = {"极高": "#8b5a5a", "高": "#9b7a6a", "中": "#a89a7a", "低": "#6a8a7a"}
                            color = risk_colors.get(joint_metrics.combined_risk_level, "#6a7a8a")
                            bg = bg_colors.get(joint_metrics.combined_risk_level, "#f5f6f8")
                            border = border_colors.get(joint_metrics.combined_risk_level, "#7a8a9a")
                            st.markdown(f"""
                            <div style="background:{bg};border-radius:12px;padding:28px;margin:20px 0;box-shadow:0 2px 10px rgba(0,0,0,0.08);border-left:5px solid {border};">
                                <div style="display:flex;justify-content:space-between;align-items:center;">
                                    <div>
                                        <div style="font-size:1rem;color:#6a7a8a;">综合风险等级</div>
                                        <div style="font-size:2.2rem;font-weight:700;color:{color};">{joint_metrics.combined_risk_level}</div>
                                    </div>
                                    <div style="text-align:right;">
                                        <div style="font-size:1rem;color:#6a7a8a;">综合风险评分</div>
                                        <div style="font-size:3.5rem;font-weight:700;color:{color};">{joint_metrics.combined_risk_score:.0f}<span style="font-size:1.5rem;color:#8a9aaa;">/100</span></div>
                                    </div>
                                </div>
                                <div style="margin-top:18px;padding:18px;background:white;border-radius:10px;font-size:1rem;color:#4a5a6a;line-height:1.7;">
                                    {joint_metrics.combined_risk_summary}
                                </div>
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
                        st.markdown('<div class="section-title">Beneish M-Score 财务粉饰检测</div>', unsafe_allow_html=True)
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
        st.markdown("""
        <div class="main-header" style="padding:15px 25px;margin-bottom:15px;">
            <h2 style="margin:0;">PDF年报分析</h2>
            <p style="margin:5px 0 0 0;opacity:0.85;">年报文本风险解读与智能解析</p>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["综合年报分析", "榜单统计"])

        # -------------------- TAB1: 综合年报分析 --------------------
        with tab1:
            st.markdown("""
            <div style="background:#f5f6f8;border-radius:12px;padding:15px;margin-bottom:20px;">
                <div style="font-size:1rem;color:#333;margin-bottom:8px;">🔍 综合年报分析</div>
                <div style="font-size:0.85rem;color:#666;">输入股票代码，自动获取年报、分析风险模型、生成综合报告</div>
            </div>
            """, unsafe_allow_html=True)

            # 显示缓存统计
            display_cache_stats()

            col1, col2 = st.columns([1, 3])
            with col1:
                symbol_input = st.text_input("股票代码", placeholder="000001", key="comprehensive_symbol")
            with col2:
                year_input = st.number_input("年报年份", min_value=2010, max_value=2025, value=2024, key="comprehensive_year")

            uploaded_pdf = st.file_uploader("上传年报PDF（可选，作为补充）", type="pdf", key="comprehensive_pdf")

            if st.button("生成综合报告", type="primary", key="comprehensive_btn"):
                if symbol_input:
                    def load_comprehensive():
                        # 获取缓存分析
                        result = get_cached_analysis(symbol_input)
                        if not result:
                            return None, None, None, "无法获取股票数据"

                        info = result['info']
                        risk_metrics = result['risk_metrics']
                        joint_metrics = result['joint_metrics']

                        pdf_analysis = None
                        annual_data = None

                        from src.pdf.annual_report_downloader import AnnualReportDownloader
                        downloader = AnnualReportDownloader()
                        annual_data, company_name = downloader.download_latest_annual_report(symbol_input, year_input)

                        if annual_data:
                            try:
                                pdf_agent = PDFRiskAgent(get_api_key())
                                pdf_analysis = pdf_agent.analyze_financial_data(
                                    annual_data,
                                    company_name or info.get('name', '')
                                )
                            except Exception as e:
                                pdf_analysis = f"（年报数据分析异常：{e}）"
                        elif uploaded_pdf:
                            # PDF上传作为补充数据源
                            import tempfile
                            from src.pdf.pdf_processor import PDFProcessor
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                                tmp_file.write(uploaded_pdf.getvalue())
                                pdf_path = tmp_file.name
                            try:
                                processor = PDFProcessor()
                                pdf_agent = PDFRiskAgent(get_api_key())
                                text = processor.extract_text(pdf_path, max_pages=100)
                                financial_text = processor.extract_financial_notes(text)
                                if not financial_text:
                                    financial_text = processor.extract_debt_related_content(text)
                                if not financial_text:
                                    financial_text = text[:20000]
                                pdf_analysis = pdf_agent.analyze(financial_text, company_name or info.get('name', ''))
                            finally:
                                import os
                                try: os.unlink(pdf_path)
                                except: pass
                        else:
                            pdf_analysis = "（年报数据获取失败）"

                        return info, risk_metrics, joint_metrics, pdf_analysis

                    try:
                        info, risk_metrics, joint_metrics, pdf_analysis = show_loading_animation(data_loader=load_comprehensive)
                        if info:
                            report = generate_comprehensive_report(info, risk_metrics, joint_metrics, pdf_analysis)
                            st.session_state['last_report'] = report

                            st.markdown("""
                            <div class="result-card">
                                <div style="font-size:1.3rem; font-weight:600; color:#1a1a2e;">综合年报分析报告</div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.markdown(report)

                            if st.button("导出报告", key="export_report"):
                                try:
                                    from reportlab.lib.pagesizes import A4
                                    from reportlab.lib.styles import getSampleStyleSheet
                                    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                                    from reportlab.lib.units import cm
                                    import io

                                    buffer = io.BytesIO()
                                    doc = SimpleDocTemplate(buffer, pagesize=A4)
                                    styles = getSampleStyleSheet()
                                    story = []

                                    for line in report.split('\n'):
                                        if line.startswith('# '):
                                            story.append(Paragraph(f"<b>{line[2:]}</b>", styles['Title']))
                                            story.append(Spacer(1, 0.3*cm))
                                        elif line.startswith('## '):
                                            story.append(Paragraph(f"<b>{line[3:]}</b>", styles['Heading2']))
                                            story.append(Spacer(1, 0.2*cm))
                                        elif line.startswith('### '):
                                            story.append(Paragraph(f"<b>{line[4:]}</b>", styles['Heading3']))
                                            story.append(Spacer(1, 0.15*cm))
                                        elif line.startswith('| '):
                                            story.append(Paragraph(line, styles['Normal']))
                                        elif line.startswith('**') and line.endswith('**'):
                                            story.append(Paragraph(line.replace('**', ''), styles['Normal']))
                                        elif line.strip():
                                            story.append(Paragraph(line, styles['Normal']))
                                            story.append(Spacer(1, 0.1*cm))

                                    doc.build(story)
                                    buffer.seek(0)
                                    st.download_button(
                                        label="下载PDF",
                                        data=buffer.getvalue(),
                                        file_name=f"{symbol_input}_年报分析报告.pdf",
                                        mime="application/pdf"
                                    )
                                except Exception as e:
                                    st.error(f"导出失败: {str(e)}")
                        else:
                            st.error(pdf_analysis or "分析失败")
                    except Exception as e:
                        st.error(f"分析出错: {str(e)}")

        # -------------------- TAB2: 榜单统计 --------------------
        with tab2:
            st.markdown("""
            <div style="background:#f5f6f8;border-radius:12px;padding:15px;margin-bottom:20px;">
                <div style="font-size:1rem;color:#333;margin-bottom:8px;">📊 榜单统计</div>
                <div style="font-size:0.85rem;color:#666;">展示已分析股票排名，分析次数越多排名越高</div>
            </div>
            """, unsafe_allow_html=True)

            display_cache_stats()

            ranking = get_shared_cache_stats().get_ranking(limit=30)

            if ranking:
                # 转换为DataFrame便于可视化
                df_ranking = pd.DataFrame(ranking)
                df_ranking['排名'] = range(1, len(df_ranking) + 1)
                df_ranking['股票名称'] = df_ranking['name'].apply(lambda x: x if x else df_ranking['symbol'])
                df_ranking['分析次数'] = df_ranking['count']

                # ---- 指标卡片 ----
                total_stocks = len(df_ranking)
                total_analysis = int(df_ranking['分析次数'].sum())
                top_stock = df_ranking.iloc[0]['股票名称'] if not df_ranking.empty else '-'
                top_count = int(df_ranking.iloc[0]['分析次数']) if not df_ranking.empty else 0

                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("累计分析股票数", total_stocks)
                with col2: st.metric("累计分析总次数", total_analysis)
                with col3: st.metric("榜首", top_stock)
                with col4: st.metric("榜首次数", top_count)

                st.divider()

                # ---- 柱状图：分析次数排行 ----
                st.markdown("#### 分析次数排行榜（前15名）")
                chart_data = df_ranking.head(15).copy()
                chart_data['label'] = chart_data['股票名称'] + ' (' + chart_data['symbol'] + ')'

                # 使用streamlit原生bar_chart
                bar_df = chart_data.set_index('label')['分析次数']
                st.bar_chart(bar_df, horizontal=True)

                st.divider()

                # ---- 详细榜单表格 ----
                st.markdown("#### 完整榜单")
                display_df = df_ranking[['排名', 'symbol', '股票名称', '分析次数']].copy()
                display_df.columns = ['排名', '代码', '股票名称', '分析次数']
                st.dataframe(display_df, width='stretch', hide_index=True)
            else:
                st.info("暂无分析记录，请先在「综合年报分析」中分析股票")

    # ==================== 公告解读 ====================
    elif page == "公告解读":
        st.markdown("""
        <div class="main-header" style="padding:15px 25px;margin-bottom:15px;">
            <h2 style="margin:0;">公告解读</h2>
            <p style="margin:5px 0 0 0;opacity:0.85;">上市公司公告智能分类与摘要</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:#f5f6f8;border-radius:12px;padding:15px;margin-bottom:20px;">
        输入股票代码，自动抓取近90天公告，AI即时解读公司公告意图、管理层动向。<br>
        <b>数据来源：</b>东方财富 &nbsp;|&nbsp; <b>覆盖：</b>高管变动/业绩/分红/回购/增持/关联交易/监管问询等
        </div>
        """, unsafe_allow_html=True)

        # 初始化 session_state
        if 'ann_anns' not in st.session_state:
            st.session_state['ann_anns'] = None
        if 'ann_symbol' not in st.session_state:
            st.session_state['ann_symbol'] = ""
        if 'ann_analysis' not in st.session_state:
            st.session_state['ann_analysis'] = None  # 综合解读结果
        if 'ann_selected' not in st.session_state:
            st.session_state['ann_selected'] = None  # 当前选中的公告
        if 'ann_selected_result' not in st.session_state:
            st.session_state['ann_selected_result'] = None

        col_sym, col_days = st.columns([2, 1])
        with col_sym:
            ann_symbol = st.text_input("股票代码", value=st.session_state.get('ann_symbol', ''), placeholder="如：000001（平安银行）", key="ann_sym_input")
        with col_days:
            ann_days = st.slider("公告回溯天数", 30, 180, 90, key="ann_days_slider")

        col_fetch, col_clear = st.columns([1, 1])
        with col_fetch:
            fetchClicked = st.button("抓取公告", type="primary", width='stretch')
        with col_clear:
            if st.button("清空", width='stretch'):
                st.session_state['ann_anns'] = None
                st.session_state['ann_symbol'] = ""
                st.session_state['ann_analysis'] = None
                st.session_state['ann_selected'] = None
                st.session_state['ann_selected_result'] = None
                st.rerun()

        anns = st.session_state.get('ann_anns')

        if fetchClicked and ann_symbol:
            ann_symbol = ann_symbol.strip()
            st.session_state['ann_symbol'] = ann_symbol
            placeholder = st.empty()
            with placeholder:
                st.markdown(loading_orb(f"正在抓取 {ann_symbol} 的公告"), unsafe_allow_html=True)
            anns = fetch_announcements(ann_symbol, days=ann_days)
            placeholder.empty()
            st.session_state['ann_anns'] = anns
            st.session_state['ann_analysis'] = None
            st.session_state['ann_selected'] = None
            st.session_state['ann_selected_result'] = None

        if anns:
            from collections import Counter
            cats = Counter(a['category'] for a in anns)
            cat_cols = st.columns(min(len(cats), 6))
            for idx, (cat, cnt) in enumerate(cats.most_common()):
                with cat_cols[idx % 6]:
                    st.metric(cat, f"{cnt}条")

            st.divider()

            # ===== 综合AI解读 =====
            if st.button("AI综合解读全部公告", type="primary"):
                with st.spinner("正在深度分析..."):
                    agent = AnnouncementAgent(get_api_key())
                    st.session_state['ann_analysis'] = agent.analyze(
                        st.session_state['ann_symbol'], days=ann_days
                    )

            if st.session_state.get('ann_analysis'):
                st.markdown("#### 🧠 AI综合解读")
                st.markdown(st.session_state['ann_analysis'])
                st.divider()

            # ===== 公告列表 =====
            st.markdown("#### 📑 公告列表")
            selected = st.session_state.get('ann_selected')

            for i, ann in enumerate(anns[:50]):
                ann_key = f"ann_{i}"
                exp_state = selected == ann_key

                with st.expander(f"**{ann['date']}** [{ann['category']}] {ann['title'][:65]}", expanded=exp_state):
                    st.caption(f"来源：{ann['source']} | 分类：{ann['category']}")
                    st.markdown(f"**{ann['title']}**")

                    # 预计算的意图标签
                    intent = _classify_intent(ann['title'], ann['category'])
                    if intent:
                        st.info(f"AI初步判断：{intent}")

                    if ann.get('url'):
                        st.markdown(f"[🔗 查看原文]({ann['url']})")

                    # 内容：按需获取（避免50条全部请求拖慢速度）
                    ann_content_key = f"ann_content_{i}"
                    cached = st.session_state.get(ann_content_key)
                    if cached:
                        with st.expander("公告内容", expanded=True):
                            st.text(cached)
                    else:
                        col_btn, col_status = st.columns([1, 3])
                        with col_btn:
                            if st.button("获取内容", key=f"fetch_{i}", width='stretch'):
                                with st.spinner("正在获取内容..."):
                                    content = _fetch_ann_content(ann)
                                    st.session_state[ann_content_key] = content
                                st.rerun()
                        with col_status:
                            st.caption("点击「📖 获取内容」查看公告正文")

                    # 深度解读按钮
                    col_ai, col_spacer = st.columns([1, 3])
                    with col_ai:
                        if st.button("深度解读", key=f"ai_{i}"):
                            placeholder = st.empty()
                            with placeholder:
                                st.markdown(loading_wave_bars("AI 智能体深度解读"), unsafe_allow_html=True)
                            agent = AnnouncementAgent(get_api_key())
                            result = agent.analyze_single(ann, company_name="")
                            placeholder.empty()
                            st.session_state['ann_selected_result'] = result
                            st.session_state['ann_selected'] = ann_key

                    # 显示深度解读结果
                    if st.session_state.get('ann_selected') == ann_key and st.session_state.get('ann_selected_result'):
                        st.markdown("---")
                        st.markdown(st.session_state['ann_selected_result'])
        elif st.session_state.get('ann_symbol') and not fetchClicked:
            st.warning("请点击「抓取公告」按钮开始分析")
        else:
            st.info("👆 输入股票代码，点击「抓取公告」开始")

    # ==================== 多智能体协作 ====================
    elif page == "多智能体协作":
        st.markdown("""
        <div class="main-header" style="padding:15px 25px;margin-bottom:15px;">
            <h2 style="margin:0;">多智能体协作</h2>
            <p style="margin:5px 0 0 0;opacity:0.85;">AutoGen 框架下的智能体协作分析系统</p>
        </div>
        """, unsafe_allow_html=True)

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


    # ==================== 个股交易数据 ====================
    elif page == "个股交易数据":
        st.markdown("""
        <div class="main-header" style="padding:15px 25px;margin-bottom:15px;">
            <h2 style="margin:0;">个股交易数据</h2>
            <p style="margin:5px 0 0 0;opacity:0.85;">资金流向 · 融资融券 · 大宗交易 · 股东/高管增减持 · 股票回购</p>
        </div>
        """, unsafe_allow_html=True)

        col_input, col_limit = st.columns([2, 1])
        with col_input:
            stock_code = st.text_input(
                "股票代码",
                value=st.session_state.get("stock_trade_code", "688825"),
                placeholder="例如 688825 / sh688825 / sz000001",
                help="默认 688825（长鑫科技）。6 位数字自动识别交易所。",
                key="stock_trade_code",
            )
        with col_limit:
            limit = st.select_slider(
                "返回条数",
                options=[10, 20, 30, 50, 100],
                value=st.session_state.get("stock_trade_limit", 20),
                key="stock_trade_limit",
            )

        st.caption("数据来源：财汇金融与风险数据 MCP · 缓存 60 分钟 · 切换股票或条数后自动重新拉取")

        tab_labels = ["资金流向", "融资融券", "大宗交易", "股东增减持", "高管增减持", "股票回购"]
        tabs = st.tabs(tab_labels)

        @st.cache_data(ttl=3600, show_spinner=False)
        def _load(code: str, lim: int, kind: str):
            if kind == "flow":   return fetch_capital_flow(code, lim)
            if kind == "margin": return fetch_margin_trading(code, lim)
            if kind == "block":  return fetch_block_trades(code, lim)
            if kind == "share":  return fetch_shareholders_trading(code, lim)
            if kind == "exec":   return fetch_executive_trading(code, lim)
            if kind == "repur":  return fetch_repurchase(code, lim)
            raise ValueError(kind)

        def _format_for_table(df, head_info):
            """表格显示版本:中文列名 + 单位后缀 + 数值格式化
            - 元(金额) -> 万元,列名后缀 (万元)  (除价格/均价外)
            - 元(价格) -> 元,列名后缀 (元)
            - 已是万元/万股/股/% 的列名后缀沿用
            """
            if df is None or df.empty or not head_info:
                return df.copy() if df is not None else None
            show = df.copy()
            # 1) field -> 中文名
            name_map = {h["field"]: h.get("name") or h["field"] for h in head_info}
            show = show.rename(columns=name_map)
            # 2) 单位=元 的列: 数值转换 + 列名后缀用"实际显示的单位"
            to_drop = []
            for h in head_info:
                col = h.get("name") or h["field"]
                unit = h.get("unit")
                if unit != "元" or col not in show.columns:
                    continue
                is_price = any(k in col for k in ("价格", "均价"))
                display_unit = "元" if is_price else "万元"
                target = f"{col}({display_unit})"
                if is_price:
                    show[target] = show[col].apply(
                        lambda v: f"{float(v):.2f}" if v not in (None, "", "-") else "-"
                    )
                else:
                    show[target] = show[col].apply(
                        lambda v: f"{float(v) / 10000:.2f}" if v not in (None, "", "-") else "-"
                    )
                to_drop.append(col)
            show = show.drop(columns=to_drop)
            # 3) 给其他有单位(非%)的列加后缀
            for h in head_info:
                col = h.get("name") or h["field"]
                unit = h.get("unit")
                if col in show.columns and unit and unit not in ("%", None):
                    show = show.rename(columns={col: f"{col}({unit})"})
            return show

        def _viz_flow(df, head_info):
            """资金流向可视化:4 张图环环相扣
            1) 环状图: 当日各级别净流入占比 (越大单越深蓝)
            2) 折线图: 各级别净流入趋势(亿元) - 越大单越深蓝
            3) 堆叠柱状图: 各级别净流入正负堆叠 (直观看出谁在买谁在卖)
            4) 双向柱状图: 当日各级别 流入 vs 流出 对比 (大单在买还是卖)
            """
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # 单子大小排序:超大单 > 大单 > 中单 > 小单 (越大越深)
            levels = [
                ("超大单", "super_large_order_net_inflow",
                 "super_large_order_buy_amt", "super_large_order_sell_amt"),
                ("大单",   "large_order_net_inflow",
                 "large_order_buy_amt", "large_order_sell_amt"),
                ("中单",   "medium_order_net_inflow",
                 "medium_order_buy_amt", "medium_order_sell_amt"),
                ("小单",   "small_order_net_inflow",
                 "small_order_buy_amt", "small_order_sell_amt"),
            ]
            # 越大单颜色越深 (深蓝 -> 浅蓝)
            size_colors = ["#0d3b66", "#1f5f8b", "#3d8bb5", "#7fb3d5"]

            date_col = "trade_date" if "trade_date" in df.columns else df.columns[3]
            df_plot = df.sort_values(date_col).reset_index(drop=True)

            # 元 -> 万元;支持标量 / Series / 数组
            def _to_wan(val):
                if val is None:
                    return 0.0
                s = pd.Series(val) if not isinstance(val, pd.Series) else val.copy()
                s = pd.to_numeric(s, errors="coerce").fillna(0)
                if s.size <= 1:
                    return float(s.iloc[0]) / 10000 if s.size == 1 else 0.0
                return s.div(10000)

            # ===== 图 1 + 2: 环状图 + 折线图 (上一行) =====
            latest = df_plot.iloc[-1]
            pie_labels, pie_values = [], []
            for i, (label, net_f, _, _) in enumerate(levels):
                if net_f in df_plot.columns:
                    v = latest[net_f]
                    try: v_num = abs(float(v))
                    except (TypeError, ValueError): v_num = 0
                    if v_num > 0:
                        pie_labels.append(label)
                        pie_values.append(v_num)

            fig_top = make_subplots(rows=1, cols=2, specs=[[{"type": "domain"}, {"type": "xy"}]],
                                    subplot_titles=("当日各级别净流入占比(万元)", "各级别净流入趋势(万元)"),
                                    column_widths=[0.32, 0.68])
            if pie_values:
                pie_wan = [v / 10000 for v in pie_values]
                pie_color_seq = [size_colors[levels.index((l, f, b, s))]
                                 for l, f, b, s in levels
                                 if f in df_plot.columns and l in pie_labels]
                fig_top.add_trace(go.Pie(
                    labels=pie_labels, values=pie_wan, hole=0.55,
                    marker=dict(colors=pie_color_seq),
                    textinfo="label+percent",
                    hovertemplate="%{label}: %{value:.2f}万元<extra></extra>",
                ), 1, 1)
            for i, (label, net_f, _, _) in enumerate(levels):
                if net_f in df_plot.columns:
                    y = _to_wan(df_plot[net_f]).tolist()
                    fig_top.add_trace(go.Scatter(
                        x=df_plot[date_col], y=y,
                        mode="lines+markers", name=label,
                        line=dict(color=size_colors[i], width=2.2),
                        marker=dict(size=6, color=size_colors[i],
                                    line=dict(color="white", width=1)),
                    ), 1, 2)
            fig_top.update_layout(height=340, showlegend=True,
                                  legend=dict(orientation="h", yanchor="bottom", y=-0.2,
                                              xanchor="center", x=0.5),
                                  margin=dict(l=20, r=20, t=50, b=50))
            fig_top.update_xaxes(title_text="日期", row=1, col=2)
            fig_top.update_yaxes(title_text="净流入(万元)", row=1, col=2)
            st.plotly_chart(fig_top, width="stretch")

            # ===== 图 3: 各级别净流入正负堆叠柱状图 (大单/特大单 在买卖 vs 散户) =====
            st.caption("各级别净流入堆叠(正负分色,单位:万元):直观看出哪天是大单在买卖 vs 散户在买卖")
            fig_stack = go.Figure()
            for i, (label, net_f, _, _) in enumerate(levels):
                if net_f not in df_plot.columns:
                    continue
                y = _to_wan(df_plot[net_f]).tolist()
                fig_stack.add_trace(go.Bar(
                    x=df_plot[date_col], y=y, name=label,
                    marker_color=size_colors[i],
                    hovertemplate="%{x}<br>" + label + " 净流入: %{y:.2f}万元<extra></extra>",
                ))
            fig_stack.update_layout(
                barmode="relative",
                height=320, title="各级别净流入柱状图(万元)",
                xaxis_title="日期", yaxis_title="净流入(万元)",
                legend=dict(orientation="h", yanchor="bottom", y=-0.25,
                            xanchor="center", x=0.5),
                margin=dict(l=20, r=20, t=50, b=50),
            )
            st.plotly_chart(fig_stack, width="stretch")

            # ===== 图 4: 当日各级别 流入 vs 流出 分组柱状图 =====
            st.caption("当日各级别 买入 vs 卖出 金额(万元):大单/特大单主导的方向,就是机构态度")
            if all(b in df_plot.columns and s in df_plot.columns
                   for _, _, b, s in levels):
                today = df_plot.iloc[-1]
                fig_io = go.Figure()
                buy_vals = [_to_wan(today[b]) for _, _, b, _ in levels]
                sell_vals = [_to_wan(today[s]) for _, _, _, s in levels]
                labels = [l for l, _, _, _ in levels]
                fig_io.add_trace(go.Bar(
                    name="买入金额", x=labels, y=buy_vals,
                    marker_color="#1f5f8b",
                    text=[f"{v:.2f}" for v in buy_vals], textposition="outside",
                    hovertemplate="%{x} 买入: %{y:.2f}万元<extra></extra>",
                ))
                fig_io.add_trace(go.Bar(
                    name="卖出金额", x=labels, y=sell_vals,
                    marker_color="#c47a5a",
                    text=[f"{v:.2f}" for v in sell_vals], textposition="outside",
                    hovertemplate="%{x} 卖出: %{y:.2f}万元<extra></extra>",
                ))
                fig_io.update_layout(
                    barmode="group", height=320,
                    title=f"{today[date_col]} 各级别买卖对比(亿元)",
                    yaxis_title="金额(亿元)",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2,
                                xanchor="center", x=0.5),
                    margin=dict(l=20, r=20, t=50, b=40),
                )
                st.plotly_chart(fig_io, width="stretch")

        def _viz_margin(df, head_info):
            """融资融券:融资余额/融券余额/融资融券余额 折线图(万元,源数据已是万元)"""
            import plotly.graph_objects as go
            date_col = "trade_date" if "trade_date" in df.columns else df.columns[2]
            df_plot = df.sort_values(date_col).reset_index(drop=True)
            # 融资融券原数据单位就是"万元",直接用
            fields = [
                ("融资余额", "margin_balance"),
                ("融券余额", "lending_balance"),
                ("融资融券余额", "margin_lending_balance"),
            ]
            fig = go.Figure()
            colors = ["#1f4e79", "#b8232f", "#6a4a8a"]
            for i, (label, f) in enumerate(fields):
                if f in df_plot.columns:
                    y = pd.to_numeric(df_plot[f], errors="coerce").fillna(0).tolist()
                    fig.add_trace(go.Scatter(x=df_plot[date_col], y=y, mode="lines+markers",
                                             name=label, line=dict(color=colors[i], width=2.2),
                                             marker=dict(size=6, color=colors[i],
                                                         line=dict(color="white", width=1)),
                                             hovertemplate="%{x}<br>" + label + ": %{y:.2f}万元<extra></extra>"))
            fig.update_layout(height=380, title="融资融券余额趋势(万元)",
                              xaxis_title="日期", yaxis_title="金额(万元)",
                              margin=dict(l=20, r=20, t=50, b=40))
            st.plotly_chart(fig, width="stretch")

        def _viz_block(df, head_info):
            """大宗交易:成交金额柱状图(万元)"""
            import plotly.graph_objects as go
            date_col = "trade_date" if "trade_date" in df.columns else df.columns[2]
            df_plot = df.sort_values(date_col, ascending=False).reset_index(drop=True)
            fig = go.Figure()
            if "block_trade_amount" in df_plot.columns:
                y = pd.to_numeric(df_plot["block_trade_amount"], errors="coerce").fillna(0).tolist()
                fig.add_trace(go.Bar(
                    x=df_plot[date_col].tolist(),
                    y=y,
                    marker_color="#1f4e79",
                    text=[f"{v:.0f}" for v in y], textposition="outside",
                    hovertemplate="%{x}<br>成交金额: %{y:.2f}万元<extra></extra>",
                ))
            fig.update_layout(height=380, title="大宗交易成交金额(万元)",
                              xaxis_title="交易日期", yaxis_title="成交金额(万元)",
                              margin=dict(l=20, r=20, t=50, b=40))
            st.plotly_chart(fig, width="stretch")

        def _render(df, tab_name, head_info):
            if df is None or df.empty:
                st.info("暂无数据（该股票可能无可披露记录，或数据源返回空集）")
                return
            # 1) 表格(中文列名 + 单位后缀 + 数值格式化)
            show = _format_for_table(df, head_info)
            st.dataframe(show, width="stretch", hide_index=True, height=360)
            # 2) 可视化
            try:
                if tab_name == "资金流向":
                    _viz_flow(df, head_info)
                elif tab_name == "融资融券":
                    _viz_margin(df, head_info)
                elif tab_name == "大宗交易":
                    _viz_block(df, head_info)
            except Exception as e:
                st.caption(f"可视化渲染失败(不影响表格): {e}")

        kinds = ["flow", "margin", "block", "share", "exec", "repur"]
        for tab, kind, name in zip(tabs, kinds, tab_labels):
            with tab:
                try:
                    placeholder = st.empty()
                    with placeholder:
                        st.markdown(loading_orb(f"正在拉取{name}"), unsafe_allow_html=True)
                    df = _load(stock_code.strip(), int(limit), kind)
                    placeholder.empty()
                    head_info = df.attrs.get("head_info") if df is not None else None
                    _render(df, name, head_info)
                except Exception as e:
                    st.warning(f"{name}获取失败:{e}")
                    if st.button(f"重试 {name}", key=f"retry_{kind}"):
                        st.cache_data.clear()
                        st.rerun()


    # ==================== 企业关系查询 ====================
    elif page == "企业关系查询":
        st.markdown("""
        <div class="main-header" style="padding:15px 25px;margin-bottom:15px;">
            <h2 style="margin:0;">企业关系查询</h2>
            <p style="margin:5px 0 0 0;opacity:0.85;">供应链 · 招投标 · 对外投资 · 融资 · 担保 · 股权出质</p>
        </div>
        """, unsafe_allow_html=True)

        col_in, col_lim = st.columns([3, 1])
        with col_in:
            company_name = st.text_input(
                "公司名称",
                value=st.session_state.get("company_rel_name", "北京蓝箭鸿擎科技有限公司"),
                placeholder="如:长鑫科技 / 兆易创新 / 比亚迪",
                help="支持公司全称/简称/股票代码/统一信用代码。默认示例:北京蓝箭鸿擎科技有限公司",
                key="company_rel_name",
            )
        with col_lim:
            limit = st.select_slider(
                "返回条数",
                options=[10, 20, 30, 50],
                value=st.session_state.get("company_rel_limit", 20),
                key="company_rel_limit",
            )

        st.caption("数据来源:财汇金融与风险数据 MCP · 缓存 60 分钟")

        # 6 类关系 + 加载器(都用模块顶层缓存的 _load_company_rel,带 retry)
        tab_labels = ["供应链(供/需)", "招投标", "对外投资", "融资(PE/VC)", "担保关系", "股权出质", "疑似关系"]
        tab_kinds  = ["supplier",    "tender",   "invest",     "pevc",          "guar",       "pledge",     "suspected"]

        def _head_lookup(head_info):
            """field -> {name, unit}"""
            if not head_info:
                return {}
            return {h["field"]: h for h in head_info}

        def _render_table(df, name):
            if df is None or df.empty:
                st.info(f"该公司在「{name}」维度暂无公开数据")
                return
            show = df.copy()
            head = _head_lookup(df.attrs.get("head_info"))
            if head:
                name_map = {f: (h.get("name") or f) for f, h in head.items()}
                show = show.rename(columns=name_map)
                for f, h in head.items():
                    cn = h.get("name") or f
                    unit = h.get("unit")
                    if cn in show.columns and unit and unit not in ("%", None):
                        show = show.rename(columns={cn: f"{cn}({unit})"})
            st.dataframe(show, width="stretch", hide_index=True, height=300)

        # ===== 8 类关系串行拉取(财汇 MCP 对并发限流,实测并行比串行慢)
        # 保留:模块顶层 cache + 2 次 retry + 进度条
        all_kinds_for_summary = tab_kinds + ["customer", "bid"]
        summary_results: dict = {}

        progress = st.progress(0.0, text="准备拉取 8 类关系...")
        status_box = st.empty()
        done_count = 0
        total = len(all_kinds_for_summary)

        for k in all_kinds_for_summary:
            try:
                summary_results[k] = _load_company_rel_with_retry(
                    company_name.strip(), int(limit), k, retries=2,
                )
            except Exception as e:
                summary_results[k] = None
                status_box.warning(f"⚠️ {k} 拉取失败:{type(e).__name__}: {str(e)[:80]}")
            finally:
                done_count += 1
                progress.progress(
                    done_count / total,
                    text=f"已拉取 {done_count}/{total} 类关系",
                )

        progress.empty()
        status_box.empty()

        # 汇总条数
        kind_label = {
            "supplier":  "供应商",   "customer": "客户",
            "tender":    "招标",     "bid":      "投标",
            "invest":    "对外投资", "pevc":     "PE/VC 融资",
            "guar":      "担保关系", "pledge":   "股权出质",
            "suspected": "疑似关系",
        }
        nonzero = [(kind_label[k], len(df)) for k, df in summary_results.items() if df is not None and len(df) > 0]
        if nonzero:
            chips = " · ".join(f"{n} **{c}**" for n, c in nonzero)
            st.success(f"已找到数据:{chips}")
        else:
            st.warning("该公司在财汇数据库中未找到任何关联关系记录。请尝试其他公司(如「比亚迪」「长鑫科技」「兆易创新」)。")

        # 6 个 tab
        tabs = st.tabs(tab_labels)

        # 供应链 tab: 供应商 + 客户
        with tabs[0]:
            _render_table(summary_results.get("supplier"), "供应商 (上游)")
            _render_table(summary_results.get("customer"), "客户 (下游)")

        # 招投标 tab: 招标 + 投标
        with tabs[1]:
            _render_table(summary_results.get("tender"), "招标记录 (招别人)")
            _render_table(summary_results.get("bid"),    "投标记录 (投别人)")

        # 剩余 5 tab
        single_kind_map = {
            "对外投资":   "invest",
            "融资(PE/VC)": "pevc",
            "担保关系":   "guar",
            "股权出质":   "pledge",
            "疑似关系":   "suspected",
        }
        for tab, name in zip(tabs[2:], single_kind_map.keys()):
            with tab:
                if name == "疑似关系":
                    st.caption("基于共同股东/共同高管/共同电话/共同地址/控股链等算法的推断关系")
                _render_table(summary_results.get(single_kind_map[name]), name)

        # ===== 关系网络图 =====
        st.divider()
        st.markdown("### 关系网络图")
        st.caption("汇总上述 9 类关系,以主公司为中心,周围节点为关联方;边颜色对应关系类型")

        try:
            import plotly.graph_objects as go
            import math

            company_clean = company_name.strip()
            edge_colors = {
                "供应商":   "#1f5f8b",
                "客户":     "#0d3b66",
                "招标":     "#7a5c00",
                "投标":     "#b8860b",
                "融资":     "#2e7d32",
                "投资":     "#6a4a8a",
                "担保":     "#b8232f",
                "股权出质": "#c25a1a",
                "疑似关系": "#9aa0a6",  # 灰色,网络图里用虚线
            }

            def _pick_col(df, hints_en, hints_zh):
                """先按英文列名查,再按中文列名查"""
                if df is None or df.empty:
                    return None
                cols = list(df.columns)
                for kw in hints_en:
                    for c in cols:
                        if kw in str(c).lower():
                            return c
                for kw in hints_zh:
                    for c in cols:
                        if kw in str(c):
                            return c
                return None

            def _flatten_investor_info(v):
                """investor_info 形如 [['公司名', '9111...'], ...] → ['公司名', ...]"""
                names = []
                if v is None:
                    return names
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, list) and item:
                            names.append(str(item[0]))
                        elif item:
                            names.append(str(item))
                else:
                    s = str(v).strip()
                    if s and s != company_clean:
                        names.append(s)
                return names

            def _extract_names(df, hints_en, hints_zh, flat_investor=False, max_n=20):
                if df is None or df.empty:
                    return []
                col = _pick_col(df, hints_en, hints_zh)
                if not col:
                    return []
                out = []
                for v in df[col].tolist():
                    if flat_investor:
                        for n in _flatten_investor_info(v):
                            if n and n != company_clean and n not in out:
                                out.append(n)
                                if len(out) >= max_n:
                                    return out
                    else:
                        s = "" if v is None else str(v).strip()
                        if s and s != company_clean and s not in out:
                            out.append(s)
                            if len(out) >= max_n:
                                return out
                return out

            # 财汇对方公司字段均为嵌套 list `[[公司名, 信用代码], ...]`,
            # 所以全部用 flat_investor=True + 正确的英文列名
            sup_names = _extract_names(summary_results.get("supplier"),
                                       ["supplier_name", "supplier"],
                                       ["供应商", "对方", "公司名称", "交易对手"],
                                       flat_investor=True)
            cus_names = _extract_names(summary_results.get("customer"),
                                       ["client_name", "customer", "client"],
                                       ["客户", "对方", "公司名称", "交易对手"],
                                       flat_investor=True)
            ten_names = _extract_names(summary_results.get("tender"),
                                       ["tenderer_info", "tenderer"],
                                       ["招标人", "对方", "公司名称"],
                                       flat_investor=True)
            bid_names = _extract_names(summary_results.get("bid"),
                                       ["tenderer_info", "tenderer"],
                                       ["招标人", "对方", "公司名称"],
                                       flat_investor=True)
            pev_names = _extract_names(summary_results.get("pevc"),
                                       ["investor_info", "investor"],
                                       ["投资方", "投资机构", "公司名称"],
                                       flat_investor=True)
            inv_names = _extract_names(summary_results.get("invest"),
                                       ["project_subject", "investee", "project_name"],
                                       ["被投资", "项目主体", "公司名称", "对方"],
                                       flat_investor=True)
            gua_names = _extract_names(summary_results.get("guar"),
                                       ["guarantor_info", "guaranteed_party_info",
                                        "guarantor", "guaranteed_party"],
                                       ["担保方", "被担保方", "对方", "公司名称"],
                                       flat_investor=True)
            ple_names = _extract_names(summary_results.get("pledge"),
                                       ["pledgee_info", "pledgee"],
                                       ["质权人", "对方", "公司名称"],
                                       flat_investor=True)
            sus_names = _extract_names(summary_results.get("suspected"),
                                       ["suspect_relation_name", "suspect_relation"],
                                       ["疑似关系企业名称", "对方", "公司名称"],
                                       flat_investor=True)

            edges = ([(company_clean, n, "供应商")   for n in sup_names]
                   + [(company_clean, n, "客户")     for n in cus_names]
                   + [(company_clean, n, "招标")     for n in ten_names]
                   + [(company_clean, n, "投标")     for n in bid_names]
                   + [(company_clean, n, "融资")     for n in pev_names]
                   + [(company_clean, n, "投资")     for n in inv_names]
                   + [(company_clean, n, "担保")     for n in gua_names]
                   + [(company_clean, n, "股权出质") for n in ple_names]
                   + [(company_clean, n, "疑似关系") for n in sus_names])

            if not edges:
                st.info("该公司在 9 类关系中均未找到关联公司,无法绘制关系图")
            else:
                all_targets = sorted({t for _, t, _ in edges})
                R = 1.0
                positions = {company_clean: (0, 0)}
                for i, name in enumerate(all_targets):
                    angle = 2 * math.pi * i / max(len(all_targets), 1)
                    positions[name] = (R * math.cos(angle), R * math.sin(angle))

                edge_traces = []
                for rel, color in edge_colors.items():
                    xs, ys = [], []
                    for s, t, r in edges:
                        if r != rel: continue
                        x0, y0 = positions[s]
                        x1, y1 = positions[t]
                        xs += [x0, x1, None]
                        ys += [y0, y1, None]
                    if xs:
                        # 疑似关系用虚线表示(算法推断,非确认关系)
                        line_kwargs = dict(color=color, width=1.6)
                        if rel == "疑似关系":
                            line_kwargs["dash"] = "dash"
                        edge_traces.append(go.Scatter(
                            x=xs, y=ys, mode="lines",
                            line=line_kwargs,
                            name=f"{rel}({sum(1 for e in edges if e[2]==rel)})",
                            hoverinfo="none", opacity=0.8,
                        ))

                node_x = [positions[n][0] for n in [company_clean] + all_targets]
                node_y = [positions[n][1] for n in [company_clean] + all_targets]
                node_text = [company_clean] + all_targets
                node_size = [26] + [12] * len(all_targets)
                node_color = ["#d03b3b"] + ["#7d8b9c"] * len(all_targets)
                node_trace = go.Scatter(
                    x=node_x, y=node_y, mode="markers+text",
                    text=node_text, textposition="top center",
                    marker=dict(size=node_size, color=node_color,
                                line=dict(color="white", width=2)),
                    hoverinfo="text", showlegend=False,
                )

                fig_net = go.Figure(data=edge_traces + [node_trace])
                fig_net.update_layout(
                    title=f"{company_clean} · 关系网络 ({len(edges)} 条关系, {len(all_targets)} 家关联方)",
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                                xanchor="center", x=0.5, font=dict(size=11)),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    height=560,
                    margin=dict(l=20, r=20, t=60, b=60),
                    plot_bgcolor="#fafbfc",
                )
                st.plotly_chart(fig_net, width="stretch")
                legend_html = " | ".join(
                    f"<span style='color:{c}'>■</span> {n}" for n, c in edge_colors.items()
                )
                st.markdown(
                    f"<div style='font-size:0.85rem; color:#666;'>图例:{legend_html} · 红色节点=主公司 · 灰色节点=关联方</div>",
                    unsafe_allow_html=True,
                )
        except Exception as e:
            st.warning(f"关系网络图渲染失败:{e}")



    # ==================== 量化策略页面 ====================
    elif page == "量化策略":
        from src.strategy.page import render_quant_strategy_page
        render_quant_strategy_page(st.session_state)



    # ==================== 诊断页面 ====================
    elif page == "🔧 诊断":
        st.markdown("""
        <div class="main-header" style="padding:15px 25px;margin-bottom:15px;">
            <h2 style="margin:0;">部署诊断</h2>
            <p style="margin:5px 0 0 0;opacity:0.85;">云端 / 本地环境 · API Key · MCP 连通性</p>
        </div>
        """, unsafe_allow_html=True)

        # ── 1. 运行环境信息 ──
        st.subheader("1. 运行环境")
        try:
            import platform, socket
            c1, c2, c3 = st.columns(3)
            with c1:
                st.write(f"**Python**: `{platform.python_version()}`")
                st.write(f"**平台**: `{platform.platform()[:40]}`")
            with c2:
                st.write(f"**Hostname**: `{socket.gethostname()}`")
                try:
                    ip = socket.gethostbyname(socket.gethostname())
                    st.write(f"**本机 IP**: `{ip}`")
                except Exception:
                    st.write("**本机 IP**: 无法解析")
            with c3:
                import streamlit as _stv
                st.write(f"**Streamlit**: `{_stv.__version__}`")
        except Exception as e:
            st.error(f"环境信息获取失败: {e}")

        st.divider()

        # ── 2. API Key 双重来源检查 ──
        st.subheader("2. API Key 读取情况(双重 fallback)")

        st.write("**来源 A: `st.secrets`(云端推荐)**")
        try:
            import streamlit as _sts
            if hasattr(_sts, "secrets") and "CAIHUI_MCP_API_KEY" in _sts.secrets:
                v = str(_sts.secrets["CAIHUI_MCP_API_KEY"])
                st.success(f"✓ 读到 · 长度 {len(v)} · 头 `{v[:8]}` · 尾 `{v[-4:]}`")
                masked = v[:6] + "*" * max(0, len(v) - 10) + v[-4:] if len(v) >= 10 else "(太短)"
                st.code(f"完整值(打码): {masked}", language="text")
            else:
                st.error("✗ st.secrets 里找不到 CAIHUI_MCP_API_KEY")
                st.write("→ 回云端 Settings → Secrets,确认 key 名拼写正确,等号两边有空格,值用双引号")
        except Exception as e:
            st.error(f"读 st.secrets 异常: {type(e).__name__}: {e}")

        st.write("**来源 B: `os.environ`(本机 export)**")
        v_env = os.environ.get("CAIHUI_MCP_API_KEY", "")
        if v_env:
            st.success(f"✓ 读到 · 长度 {len(v_env)} · 头 `{v_env[:8]}` · 尾 `{v_env[-4:]}`")
        else:
            st.info("ℹ️ os.environ 里没有(云端正常,本机需要 export)")

        st.write("**finchina_collector._get_api_key() 实际拿到什么**")
        try:
            from src.data.finchina_collector import _get_api_key as _gak
            v_actual = _gak()
            st.success(f"✓ 拿到 · 长度 {len(v_actual)} · 头 `{v_actual[:8]}` · 尾 `{v_actual[-4:]}`")
        except Exception as e:
            st.error(f"✗ 拿不到: {e}")

        st.divider()

        # ── 3. MCP 直连测试 ──
        st.subheader("3. 财汇 MCP 直连测试")
        st.caption("用当前 _get_api_key() 实际打一次,看 server 怎么回")

        col_btn, col_kind = st.columns([1, 3])
        with col_btn:
            do_test = st.button("🚀 跑一次测试", type="primary", key="diag_run")
        with col_kind:
            test_kind = st.selectbox("测试类型", [
                "list_tools (列工具,最轻量)",
                "supplier (拉一家公司,验证完整链路)",
            ], key="diag_kind")

        if do_test:
            with st.spinner("正在打财汇 MCP..."):
                import requests as _req
                try:
                    from src.data.finchina_collector import _get_api_key as _gak2
                    key = _gak2()
                    if test_kind.startswith("list_tools"):
                        payload = {"jsonrpc": "2.0", "id": 99, "method": "tools/list", "params": {}}
                    else:
                        payload = {
                            "jsonrpc": "2.0", "id": 99, "method": "tools/call",
                            "params": {
                                "name": "execute_tool",
                                "arguments": {
                                    "tool_name": "get_company_suppliers",
                                    "arguments": {"target_company": ["比亚迪"], "limit": 1},
                                },
                            },
                        }
                    masked_key = key[:6] + "*" * max(0, len(key) - 10) + key[-4:] if len(key) >= 10 else "(太短)"
                    st.write("**请求头(打码)**:")
                    st.code(
                        f"x-api-key: {masked_key}\nContent-Type: application/json\nAccept: application/json, text/event-stream",
                        language="http",
                    )

                    resp = _req.post(
                        "https://mcp.finchina.com/finchina-data-mcp-server/mcp",
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/event-stream",
                            "x-api-key": key,
                        },
                        json=payload, timeout=15,
                    )
                    st.write(f"**HTTP 状态码**: `{resp.status_code}`")
                    st.write("**响应体(前 1000 字符)**:")
                    body = resp.text[:1000]
                    try:
                        st.json(resp.json())
                    except Exception:
                        st.code(body, language="text")
                except Exception as e:
                    st.error(f"测试失败: {type(e).__name__}: {e}")

        st.divider()

        # ── 4. 关键 import 检查 ──
        st.subheader("4. 关键模块/依赖")
        mods = ["requests", "pandas", "plotly", "streamlit",
                "src.data.finchina_collector", "src.data.market_collector"]
        for m in mods:
            try:
                __import__(m)
                st.write(f"✓ `{m}`")
            except Exception as e:
                st.write(f"✗ `{m}`: {type(e).__name__}: {str(e)[:80]}")

        st.divider()

        # ── 5. 明文 key 扫描 ──
        st.subheader("5. 代码里明文 key 扫描")
        st.caption("如果之前把 key 写进了 streamlit_app.py / .env 并 push 了 git,这里会扫到")
        import re
        for path in ["streamlit_app.py", "src/data/finchina_collector.py",
                      ".env", ".env.example", "render.yaml"]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                hits = re.findall(r"sk-[a-zA-Z0-9]{20,}", text)
                if hits:
                    masked = [h[:6] + "***" + h[-4:] for h in hits]
                    st.warning(f"⚠️ `{path}` 里有疑似 key: {masked}")
                else:
                    st.write(f"✓ `{path}` 无明文 key")
            except FileNotFoundError:
                st.write(f"ℹ️ `{path}` 不存在")
            except Exception as e:
                st.write(f"? `{path}` 读失败: {e}")


if __name__ == "__main__":
    main()