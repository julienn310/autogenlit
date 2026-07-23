"""
A股智能体分析系统 - Streamlit 版本
完整迁移自 web/index.html，保留所有指标
"""

import streamlit as st
import sys
import os
import pandas as pd
import threading
from pathlib import Path
import time

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

def get_cached_analysis(symbol: str):
    """获取分析结果"""
    collectors = init_collectors()
    data = collectors['data_collector'].collect_stock_data(symbol)
    if not data or not data.get('info'):
        return None
    risk_metrics = collectors['risk_analyzer'].calculate_metrics(data)
    joint_metrics = collectors['joint_risk_analyzer'].analyze(data)

    return {
        'symbol': symbol,
        'info': data.get('info', {}),
        'risk_metrics': risk_metrics.to_dict() if hasattr(risk_metrics, 'to_dict') else risk_metrics,
        'joint_metrics': joint_metrics.to_dict() if hasattr(joint_metrics, 'to_dict') else joint_metrics,
    }

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


# 主应用
def main():
    with st.sidebar:
        st.markdown("### AutoGen 金融分析")
        st.divider()
        st.success("API Key 已配置")
        st.divider()
        page = st.radio("导航", [
            "仪表板", "财务分析", "投资组合", "风险分析", "PDF年报分析", "公告解读", "多智能体协作"
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

        # ========== 全球市场行情 ==========
        st.markdown('<div class="section-title">🌏 全球市场行情</div>', unsafe_allow_html=True)

        with st.spinner("🌐 正在加载全球指数，请稍候..."):
            try:
                indices = fetch_major_indices()
            except Exception:
                indices = []

        if indices:
            # 按涨跌幅排序
            indices_sorted = sorted(indices, key=lambda x: x['change_pct'], reverse=True)

            # A股 / 全球分区
            A_STOCK_CODES = {'sh000001', 'sz399001', 'sz399006', 'sh000300', 'sh000016', 'sh000905', 'sh000688'}
            a_stocks = [i for i in indices_sorted if i['code'] in A_STOCK_CODES]
            global_stocks = [i for i in indices_sorted if i['code'] not in A_STOCK_CODES]

            def render_index_row(d):
                pct = d['change_pct']
                color = '#c00' if pct > 0 else ('#1F4E79' if pct < 0 else '#888')
                sign = '+' if pct >= 0 else ''
                return f"""
                <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #eee;">
                    <span style="font-weight:600;min-width:100px;">{d['name']}</span>
                    <span style="color:{color};font-weight:700;">{sign}{pct:.2f}%</span>
                    <span style="color:#666;font-size:0.9em;">{d['price']:.2f}</span>
                </div>"""

            col_a, col_g = st.columns(2)
            with col_a:
                st.markdown("**📈 A股主要指数**", unsafe_allow_html=True)
                for d in a_stocks[:7]:
                    st.markdown(render_index_row(d), unsafe_allow_html=True)
            with col_g:
                st.markdown("**🌍 全球指数**", unsafe_allow_html=True)
                for d in global_stocks[:7]:
                    st.markdown(render_index_row(d), unsafe_allow_html=True)
        else:
            st.info("行情数据暂时不可用（网络环境限制）")

        st.divider()

        # ========== 金融舆情简报 ==========
        st.markdown('<div class="section-title">📰 舆情与市场动态</div>', unsafe_allow_html=True)

        with st.spinner("📡 正在抓取新闻与舆情，请稍候..."):
            try:
                news_data = fetch_news()
            except Exception:
                news_data = {'timeline': [], 'kol': [], 'weibo_sentiment': [], 'xueqiu_hot': [], 'flash': []}

        timeline = news_data.get('timeline', [])
        kol_list = news_data.get('kol', [])
        weibo_sentiment = news_data.get('weibo_sentiment', [])
        xueqiu_hot = news_data.get('xueqiu_hot', [])
        flash = news_data.get('flash', [])

        # ── 第一行：微博情绪 + 雪球热帖 ──
        col_ws, col_xq = st.columns(2)

        with col_ws:
            st.markdown("**📊 微博情绪指数**（舆情冷暖）", unsafe_allow_html=True)
            if weibo_sentiment:
                for n in weibo_sentiment[:10]:
                    title = n.get('title', '')
                    # 提取指数值判断颜色
                    import re
                    m = re.search(r'([+-]?[\d.]+)', title.split(':')[-1] if ':' in title else '')
                    if m:
                        try:
                            val = float(m.group(1))
                            color = '#c00' if val > 0 else ('#1F4E79' if val < 0 else '#888')
                        except:
                            color = '#666'
                    else:
                        color = '#666'
                    st.markdown(f"<span style='color:{color}'>● {title[:30]}</span>", unsafe_allow_html=True)
            else:
                st.caption("暂无数据")

        with col_xq:
            st.markdown("**🔥 雪球热议榜**（讨论热度）", unsafe_allow_html=True)
            if xueqiu_hot:
                for n in xueqiu_hot[:10]:
                    title = n.get('title', '')
                    url = n.get('url', '')
                    if url:
                        st.markdown(f"[{title[:35]}]({url})")
                    else:
                        st.markdown(f"{title[:35]}")
            else:
                st.caption("暂无数据")

        st.divider()

        # ── 第二行：快讯 + 最新资讯 ──
        col_flash, col_news = st.columns([1, 2])

        with col_flash:
            st.markdown("**⚡ A股快讯**", unsafe_allow_html=True)
            if flash:
                for n in flash[:8]:
                    t = n.get('time', '')
                    time_str = t[5:] if t else ''
                    short = n.get('title', '')[:28] + '...' if len(n.get('title', '')) > 28 else n.get('title', '')
                    st.markdown(f"**{time_str}** {short}")
            else:
                st.caption("暂无数据")

        with col_news:
            st.markdown("**📰 最新资讯**（点击展开）", unsafe_allow_html=True)
            if timeline:
                for n in timeline[:12]:
                    title = n.get('title', '')
                    short = title[:40] + '...' if len(title) > 40 else title
                    t = n.get('time', '')
                    time_str = t[5:] if t else ''
                    src = n.get('source', '')
                    with st.expander(f"{time_str} {short}", expanded=False):
                        st.markdown(f"**{title}**")
                        if n.get('url'):
                            st.markdown(f"[查看详情 →]({n['url']})")
                        st.caption(f"来源: {src}")
            else:
                st.caption("暂无数据")

        # ── KOL 动态 ──
        if kol_list:
            st.divider()
            st.markdown("**💬 KOL 最新言论**", unsafe_allow_html=True)
            for n in kol_list[:6]:
                with st.expander(
                    f"👤 {n.get('kol', '')} · {n.get('time', '')[5:] if n.get('time') else ''} — {n.get('title', '')[:40]}...",
                    expanded=False
                ):
                    st.markdown(f"**{n.get('title', '')}**")
                    if n.get('url'):
                        st.markdown(f"[来源链接 →]({n['url']})")

        st.divider()

        st.markdown('<div class="section-title">快速股票查询</div>', unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])
        with col1:
            symbol = st.text_input("输入股票代码", placeholder="例如: 000001", label_visibility="collapsed")
        with col2:
            st.write("")
            analyze_btn = st.button("查询", type="primary", width='stretch')

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
        st.markdown("### 综合年报分析")

        tab1, tab2 = st.tabs(["🔍 综合年报分析", "📊 榜单统计"])

        # -------------------- TAB1: 综合年报分析 --------------------
        with tab1:
            st.markdown("""
            <div style="background:#f5f6f8;border-radius:12px;padding:15px;margin-bottom:20px;">
                <div style="font-size:1rem;color:#333;margin-bottom:8px;">🔍 综合年报分析</div>
                <div style="font-size:0.85rem;color:#666;">输入股票代码，自动获取年报、分析风险模型、生成综合报告</div>
            </div>
            """, unsafe_allow_html=True)

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

                            if st.button("📥 导出报告", key="export_report"):
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

            st.info("榜单统计功能即将上线，请先在「综合年报分析」中分析股票")

    # ==================== 公告解读 ====================
    elif page == "公告解读":
        st.markdown("### 📋 公司公告解读")

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
            fetchClicked = st.button("🔍 抓取公告", type="primary", width='stretch')
        with col_clear:
            if st.button("🗑 清空", width='stretch'):
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
            with st.spinner("正在抓取公告..."):
                anns = fetch_announcements(ann_symbol, days=ann_days)
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
            if st.button("🧠 AI综合解读全部公告", type="primary"):
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
                        st.info(f"💡 AI初步判断：{intent}")

                    if ann.get('url'):
                        st.markdown(f"[🔗 查看原文]({ann['url']})")

                    # 内容：按需获取（避免50条全部请求拖慢速度）
                    ann_content_key = f"ann_content_{i}"
                    cached = st.session_state.get(ann_content_key)
                    if cached:
                        with st.expander("📄 公告内容", expanded=True):
                            st.text(cached)
                    else:
                        col_btn, col_status = st.columns([1, 3])
                        with col_btn:
                            if st.button("📖 获取内容", key=f"fetch_{i}", width='stretch'):
                                with st.spinner("正在获取内容..."):
                                    content = _fetch_ann_content(ann)
                                    st.session_state[ann_content_key] = content
                                st.rerun()
                        with col_status:
                            st.caption("点击「📖 获取内容」查看公告正文")

                    # 深度解读按钮
                    col_ai, col_spacer = st.columns([1, 3])
                    with col_ai:
                        if st.button("🤖 深度解读", key=f"ai_{i}"):
                            with st.spinner("正在解读..."):
                                agent = AnnouncementAgent(get_api_key())
                                result = agent.analyze_single(ann, company_name="")
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