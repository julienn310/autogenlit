"""数据模型定义"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd


@dataclass
class FinancialMetrics:
    """财务指标"""
    roe: float = 0.0  # 净资产收益率
    roa: float = 0.0  # 总资产收益率
    debt_ratio: float = 0.0  # 资产负债率
    gross_margin: float = 0.0  # 毛利率
    net_margin: float = 0.0  # 净利率
    current_ratio: float = 0.0  # 流动比率
    quick_ratio: float = 0.0  # 速动比率
    inventory_turnover: float = 0.0  # 存货周转率
    total_asset_turnover: float = 0.0  # 总资产周转率
    earnings_per_share: float = 0.0  # 每股收益
    book_value_per_share: float = 0.0  # 每股净资产
    ocf_per_share: float = 0.0  # 每股经营现金流

    def to_dict(self) -> Dict:
        return {
            'roe': f"{self.roe:.2f}%",
            'roa': f"{self.roa:.2f}%",
            'debt_ratio': f"{self.debt_ratio:.2f}%",
            'gross_margin': f"{self.gross_margin:.2f}%",
            'net_margin': f"{self.net_margin:.2f}%",
            'current_ratio': f"{self.current_ratio:.2f}",
            'quick_ratio': f"{self.quick_ratio:.2f}",
            'inventory_turnover': f"{self.inventory_turnover:.2f}",
            'total_asset_turnover': f"{self.total_asset_turnover:.2f}",
            'eps': f"{self.earnings_per_share:.4f}",
            'bvps': f"{self.book_value_per_share:.4f}",
            'ocfps': f"{self.ocf_per_share:.4f}",
        }


@dataclass
class RiskMetrics:
    """风险指标"""
    volatility: float = 0.0  # 波动率（年化）
    var_95: float = 0.0  # 95% VaR
    cvar_95: float = 0.0  # 95% CVaR
    max_drawdown: float = 0.0  # 最大回撤
    sharpe_ratio: float = 0.0  # 夏普比率
    beta: float = 0.0  # Beta系数
    # 新增：风险调整收益指标
    sortino_ratio: float = 0.0  # Sortino 比率
    calmar_ratio: float = 0.0  # Calmar 比率
    treynor_ratio: float = 0.0  # Treynor 比率
    omega_ratio: float = 0.0  # Omega 比率
    downside_dev: float = 0.0  # 下行标准差（年化）
    target_return: float = 0.0  # Sortino/Omega 计算用的目标收益
    # Beneish M-Score 相关指标
    m_score: float = 0.0  # M-Score综合得分
    dsri: float = 0.0  # 应收账款天数指数
    gmi: float = 0.0  # 毛利率指数
    aq_i: float = 0.0  # 资产质量指数
    tata: float = 0.0  # 总应计项目与资产比率
    sgi: float = 0.0  # 销售增长指数
    lvgi: float = 0.0  # 杠杆指数
    depi: float = 0.0  # 折旧指数
    sgai: float = 0.0  # 销售管理费用指数
    m_score_interpretation: str = ""  # M-Score解读

    def to_dict(self) -> Dict:
        return {
            'volatility': f"{self.volatility:.2%}",
            'var_95': f"{self.var_95:.2%}",
            'cvar_95': f"{self.cvar_95:.2%}",
            'max_drawdown': f"{self.max_drawdown:.2%}",
            'sharpe_ratio': f"{self.sharpe_ratio:.2f}",
            'beta': f"{self.beta:.2f}",
            'sortino_ratio': f"{self.sortino_ratio:.2f}",
            'calmar_ratio': f"{self.calmar_ratio:.2f}",
            'treynor_ratio': f"{self.treynor_ratio:.2f}",
            'omega_ratio': f"{self.omega_ratio:.2f}",
            'downside_dev': f"{self.downside_dev:.2%}",
            'm_score': f"{self.m_score:.2f}",
            'm_score_interpretation': self.m_score_interpretation,
            # M-Score sub-indicators
            'dsri': f"{self.dsri:.2f}",
            'gmi': f"{self.gmi:.2f}",
            'aq_i': f"{self.aq_i:.2f}",
            'tata': f"{self.tata:.4f}",
            'sgi': f"{self.sgi:.2f}",
            'lvgi': f"{self.lvgi:.2f}",
            'depi': f"{self.depi:.2f}",
            'sgai': f"{self.sgai:.2f}",
        }


@dataclass
class ValuationMetrics:
    """估值指标"""
    pe_ratio: float = 0.0  # 市盈率
    pb_ratio: float = 0.0  # 市净率
    ps_ratio: float = 0.0  # 市销率
    pcf_ratio: float = 0.0  # 市现率
    market_cap: float = 0.0  # 总市值
    float_market_cap: float = 0.0  # 流通市值

    def to_dict(self) -> Dict:
        return {
            'pe': f"{self.pe_ratio:.2f}",
            'pb': f"{self.pb_ratio:.2f}",
            'ps': f"{self.ps_ratio:.2f}",
            'pcf': f"{self.pcf_ratio:.2f}",
            'market_cap': f"{self.market_cap/1e8:.2f}亿",
            'float_market_cap': f"{self.float_market_cap/1e8:.2f}亿",
        }


@dataclass
class StockAnalysisResult:
    """股票分析结果"""
    symbol: str
    name: str
    industry: str
    analysis_date: str
    financial_metrics: FinancialMetrics = field(default_factory=FinancialMetrics)
    risk_metrics: RiskMetrics = field(default_factory=RiskMetrics)
    valuation_metrics: ValuationMetrics = field(default_factory=ValuationMetrics)
    data_analysis: str = ""
    financial_analysis: str = ""
    risk_analysis: str = ""
    investment_advice: str = ""

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'name': self.name,
            'industry': self.industry,
            'analysis_date': self.analysis_date,
            'financial_metrics': self.financial_metrics.to_dict(),
            'risk_metrics': self.risk_metrics.to_dict(),
            'valuation_metrics': self.valuation_metrics.to_dict(),
            'data_analysis': self.data_analysis,
            'financial_analysis': self.financial_analysis,
            'risk_analysis': self.risk_analysis,
            'investment_advice': self.investment_advice,
        }


@dataclass
class PortfolioMetrics:
    """组合风险指标"""
    expected_return: float = 0.0  # 年化预期收益
    volatility: float = 0.0  # 年化波动率
    sharpe_ratio: float = 0.0  # 夏普比率
    var_95: float = 0.0  # 95% VaR（日频）
    cvar_95: float = 0.0  # 95% CVaR
    max_drawdown: float = 0.0  # 最大回撤
    cumulative_return: float = 0.0  # 回测期间累计收益
    # 新增：风险调整收益指标
    sortino_ratio: float = 0.0  # Sortino 比率
    calmar_ratio: float = 0.0  # Calmar 比率
    treynor_ratio: float = 0.0  # Treynor 比率
    omega_ratio: float = 0.0  # Omega 比率
    downside_dev: float = 0.0  # 下行标准差（年化）
    weights: Dict[str, float] = field(default_factory=dict)  # 各资产权重

    def to_dict(self) -> Dict:
        return {
            'expected_return': f"{self.expected_return:.2%}",
            'volatility': f"{self.volatility:.2%}",
            'sharpe_ratio': f"{self.sharpe_ratio:.2f}",
            'var_95': f"{self.var_95:.2%}",
            'cvar_95': f"{self.cvar_95:.2%}",
            'max_drawdown': f"{self.max_drawdown:.2%}",
            'cumulative_return': f"{self.cumulative_return:.2%}",
            'sortino_ratio': f"{self.sortino_ratio:.2f}",
            'calmar_ratio': f"{self.calmar_ratio:.2f}",
            'treynor_ratio': f"{self.treynor_ratio:.2f}",
            'omega_ratio': f"{self.omega_ratio:.2f}",
            'downside_dev': f"{self.downside_dev:.2%}",
            'weights': {k: f"{v:.2%}" for k, v in self.weights.items()},
        }

    def to_raw_dict(self) -> Dict:
        """返回格式化后的数值，用于API传输"""
        return {
            'expected_return': f"{self.expected_return:.2%}",
            'volatility': f"{self.volatility:.2%}",
            'sharpe_ratio': f"{self.sharpe_ratio:.2f}",
            'var_95': f"{self.var_95:.2%}",
            'cvar_95': f"{self.cvar_95:.2%}",
            'max_drawdown': f"{self.max_drawdown:.2%}",
            'cumulative_return': f"{self.cumulative_return:.2%}",
            'sortino_ratio': f"{self.sortino_ratio:.2f}",
            'calmar_ratio': f"{self.calmar_ratio:.2f}",
            'treynor_ratio': f"{self.treynor_ratio:.2f}",
            'omega_ratio': f"{self.omega_ratio:.2f}",
            'downside_dev': f"{self.downside_dev:.2%}",
            'weights': {k: f"{v:.2%}" for k, v in self.weights.items()},
        }


@dataclass
class OptimizationResult:
    """组合优化结果"""
    weights: Dict[str, float] = field(default_factory=dict)  # 最优权重
    portfolio_metrics: Optional[PortfolioMetrics] = None
    frontier_points: List['PortfolioMetrics'] = field(default_factory=list)  # 有效前沿曲线
    error_message: str = ""

    def to_dict(self) -> Dict:
        return {
            'weights': {k: f"{v:.2%}" for k, v in self.weights.items()},
            'portfolio_metrics': self.portfolio_metrics.to_raw_dict() if self.portfolio_metrics else {},
            'frontier_points': [p.to_raw_dict() for p in self.frontier_points] if self.frontier_points else [],
            'error_message': self.error_message,
        }