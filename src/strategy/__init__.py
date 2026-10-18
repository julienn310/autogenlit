"""
量化策略模块 — 移植自 VIBE-TRADING-LIT
- lite_engine: 单股回测引擎
- lite_metrics: 回测指标计算
- strategy_templates: 策略模板库
- factors: 52 个投研因子知识库
- data_adapter: A股数据桥接
"""
from .lite_metrics import (
    TradeRecord, Position, EquitySnapshot, BacktestMetrics, calc_metrics,
)
from .lite_engine import BacktestConfig, BacktestResult, run_backtest
from .strategy_templates import (
    TEMPLATES, StrategyTemplate, TemplateParam, ParamType,
    get_template, list_templates, list_template_names,
)

__all__ = [
    'BacktestConfig', 'BacktestResult', 'run_backtest',
    'TradeRecord', 'Position', 'EquitySnapshot', 'BacktestMetrics', 'calc_metrics',
    'TEMPLATES', 'StrategyTemplate', 'TemplateParam', 'ParamType',
    'get_template', 'list_templates', 'list_template_names',
]
