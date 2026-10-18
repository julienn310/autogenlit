"""
Strategy Template System for VIBE TRADING LIT.
Provides parameterized strategy templates with Jinja2 code generation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ParamType(Enum):
    SLIDER = "slider"
    SELECT = "select"
    NUMBER = "number"
    TEXT = "text"


@dataclass
class TemplateParam:
    name: str
    label: str
    param_type: ParamType
    default: Any
    min_value: float = 0
    max_value: float = 100
    step: float = 1
    options: list[Any] = field(default_factory=list)
    help: str = ""


@dataclass
class StrategyTemplate:
    name: str
    description: str
    category: str
    params: list[TemplateParam]
    default_params: dict
    signal_logic: str
    indicators: list[str]
    code_template: str = ""

    def generate_code(self, params: dict) -> str:
        if not self.code_template:
            return self._default_code_template(params)
        return self._default_code_template(params)

    def _default_code_template(self, params: dict) -> str:
        if self.name == "均线交叉":
            return self._ma_cross_code(params)
        elif self.name == "RSI趏勣":
            return self._rsi_code(params)
        elif self.name == "布林带突破":
            return self._bollinger_code(params)
        elif self.name == "动量策略":
            return self._momentum_code(params)
        elif self.name == "价值回归":
            return self._value_reversion_code(params)
        elif self.name == "Keltner通道":
            return self._keltner_code(params)
        elif self.name in ("固定止损", "ATR动态止损", "固定止盈"):
            return (
                "import pandas as pd\n"
                "\ndef generate_signals(data):\n"
                "    signals = {}\n"
                "    for symbol, df in data.items():\n"
                "        signals[symbol] = pd.Series(0, index=df.index)\n"
                "    return signals\n"
            )
        return self._ma_cross_code(params)

    def _ma_cross_code(self, params):
        fast = int(params.get("fast_period", 20))
        slow = int(params.get("slow_period", 60))
        stop = params.get("stop_loss_pct", 5)
        return (
            "import pandas as pd\n"
            "import numpy as np\n"
            "\n"
            "def generate_signals(data):\n"
            "    signals = {}\n"
            "    for symbol, df in data.items():\n"
            "        close = df['close'].astype(float)\n"
            "        ma_fast = close.rolling(%d).mean()\n"
            "        ma_slow = close.rolling(%d).mean()\n"
            "\n"
            "        above = (ma_fast.shift(1) > ma_slow.shift(1)).fillna(False)\n"
            "        valid = ma_slow.shift(1).notna()\n"
            "        position = pd.Series(0, index=df.index)\n"
            "        position[(above == True) & valid] = 1\n"
            "        position[(above == False) & valid] = -1\n"
            "        signals[symbol] = position\n"
            "    return signals\n"
        ) % (fast, slow)

    def _rsi_code(self, params):
        period = int(params.get("rsi_period", 14))
        upper = params.get("rsi_upper", 70)
        lower = params.get("rsi_lower", 30)
        stop = params.get("stop_loss_pct", 5)
        return (
            "import pandas as pd\n"
            "import numpy as np\n"
            "\n"
            "def rsi(close, period):\n"
            "    delta = close.diff()\n"
            "    gain = delta.where(delta > 0, 0).rolling(period).mean()\n"
            "    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()\n"
            "    rs = gain / loss.replace(0, np.inf)\n"
            "    return 100 - (100 / (1 + rs))\n"
            "\n"
            "def generate_signals(data):\n"
            "    signals = {}\n"
            "    for symbol, df in data.items():\n"
            "        close = df['close'].astype(float)\n"
            "        r = rsi(close, %d)\n"
            "        r_cross = r.diff()\n"
            "        position = pd.Series(0, index=df.index)\n"
            "        position[r_cross > 0] = 1\n"
            "        position[r_cross < 0] = -1\n"
            "        position = position.shift(1).fillna(0)\n"
            "        signals[symbol] = position\n"
            "    return signals\n"
        ) % period

    def _bollinger_code(self, params):
        period = int(params.get("bollinger_period", 20))
        std_mult = float(params.get("bollinger_std", 2.0))
        stop = params.get("stop_loss_pct", 5)
        return (
            "import pandas as pd\n"
            "import numpy as np\n"
            "\n"
            "def generate_signals(data):\n"
            "    signals = {}\n"
            "    for symbol, df in data.items():\n"
            "        close = df['close'].astype(float)\n"
            "        mid = close.rolling(%d).mean()\n"
            "        std = close.rolling(%d).std()\n"
            "        upper = mid + std * %.1f\n"
            "        lower = mid - std * %.1f\n"
            "\n"
            "        above_upper = (close > upper).astype(int).diff()\n"
            "        below_lower = (close < lower).astype(int).diff()\n"
            "\n"
            "        position = pd.Series(0, index=df.index)\n"
            "        position[above_upper > 0] = 1\n"
            "        position[below_lower < 0] = -1\n"
            "        position = position.shift(1).fillna(0)\n"
            "        signals[symbol] = position\n"
            "    return signals\n"
        ) % (period, period, std_mult, std_mult)

    def _momentum_code(self, params):
        lookback = int(params.get("lookback_period", 20))
        threshold = float(params.get("threshold", 0.01))
        return (
            "import pandas as pd\n"
            "import numpy as np\n"
            "\n"
            "def generate_signals(data):\n"
            "    signals = {}\n"
            "    for symbol, df in data.items():\n"
            "        close = df['close'].astype(float)\n"
            "        ret = close.pct_change(%d)\n"
            "        mom_cross = ret.diff()\n"
            "        position = pd.Series(0, index=df.index)\n"
            "        position[mom_cross > 0] = 1\n"
            "        position[mom_cross < 0] = -1\n"
            "        position = position.shift(1).fillna(0)\n"
            "        signals[symbol] = position\n"
            "    return signals\n"
        ) % lookback

    def _value_reversion_code(self, params):
        ma_period = int(params.get("ma_period", 60))
        return (
            "import pandas as pd\n"
            "import numpy as np\n"
            "\n"
            "def generate_signals(data):\n"
            "    signals = {}\n"
            "    for symbol, df in data.items():\n"
            "        close = df['close'].astype(float)\n"
            "        ma = close.rolling(%d).mean()\n"
            "        above_ma = (close > ma).astype(int).diff()\n"
            "        position = pd.Series(0, index=df.index)\n"
            "        position[above_ma > 0] = 1\n"
            "        position[above_ma < 0] = -1\n"
            "        position = position.shift(1).fillna(0)\n"
            "        signals[symbol] = position\n"
            "    return signals\n"
        ) % ma_period

    def _keltner_code(self, params):
        period = int(params.get("keltner_period", 20))
        mult = float(params.get("keltner_multiplier", 2.0))
        return (
            "import pandas as pd\n"
            "import numpy as np\n"
            "\n"
            "def generate_signals(data):\n"
            "    signals = {}\n"
            "    for symbol, df in data.items():\n"
            "        close = df['close'].astype(float)\n"
            "        high = df['high'].astype(float)\n"
            "        low = df['low'].astype(float)\n"
            "        mid = close.rolling(%d).mean()\n"
            "        tr = pd.concat([\n"
            "            high - low,\n"
            "            (high - close.shift(1)).abs(),\n"
            "            (low - close.shift(1)).abs()\n"
            "        ], axis=1).max(axis=1)\n"
            "        atr = tr.rolling(%d).mean()\n"
            "        upper = mid + atr * %.1f\n"
            "        lower = mid - atr * %.1f\n"
            "\n"
            "        above_upper = (close > upper).astype(int).diff()\n"
            "        below_lower = (close < lower).astype(int).diff()\n"
            "        position = pd.Series(0, index=df.index)\n"
            "        position[above_upper > 0] = 1\n"
            "        position[below_lower < 0] = -1\n"
            "        position = position.shift(1).fillna(0)\n"
            "        signals[symbol] = position\n"
            "    return signals\n"
        ) % (period, period, mult, mult)


# Built-in Strategy Templates
TEMPLATES = [
    StrategyTemplate(
        name="均线交叉",
        description="短期均线上穿长期均线买入，下穿卖出",
        category="趏勣跟踪",
        signal_logic="当短期均线（默认20日）上穿长期均线（默认60日）时买入，购乎时卖出",
        indicators=["MA(close, fast)", "MA(close, slow)"],
        params=[
            TemplateParam("fast_period", "短期均线周期", ParamType.SLIDER, 20, 5, 100, 5),
            TemplateParam("slow_period", "长期均线周期", ParamType.SLIDER, 60, 20, 200, 10),
            TemplateParam("stop_loss_pct", "止损比例 %", ParamType.SLIDER, 5, 0, 30, 1),
            TemplateParam("take_profit_pct", "止盈比例 %", ParamType.SLIDER, 15, 0, 50, 5),
        ],
        default_params={"fast_period": 20, "slow_period": 60, "stop_loss_pct": 5, "take_profit_pct": 15},
    ),
    StrategyTemplate(
        name="RSI趏勣",
        description="RSI超卖买入，超买卖出",
        category="趏勣跟踪",
        signal_logic="RSI低于30（超卖）时买入，高于70（超买）时卖出",
        indicators=["RSI(close, period)"],
        params=[
            TemplateParam("rsi_period", "RSI周期", ParamType.SLIDER, 14, 5, 30, 1),
            TemplateParam("rsi_lower", "RSI超卖阈值", ParamType.SLIDER, 30, 10, 50, 5),
            TemplateParam("rsi_upper", "RSI超买阈值", ParamType.SLIDER, 70, 50, 90, 5),
            TemplateParam("stop_loss_pct", "止损比例 %", ParamType.SLIDER, 5, 0, 30, 1),
            TemplateParam("take_profit_pct", "止盈比例 %", ParamType.SLIDER, 15, 0, 50, 5),
        ],
        default_params={"rsi_period": 14, "rsi_lower": 30, "rsi_upper": 70, "stop_loss_pct": 5, "take_profit_pct": 15},
    ),
    StrategyTemplate(
        name="布林带突破",
        description="价格突破布林带上轨买入，购破下轨卖出",
        category="趏勣跟踪",
        signal_logic="当价格突破布林带上轨（+2倍标准差）时买入，购破下轨时卖出",
        indicators=["BOLL(mid, std)", "close"],
        params=[
            TemplateParam("bollinger_period", "布林周期", ParamType.SLIDER, 20, 10, 50, 5),
            TemplateParam("bollinger_std", "标准差倍数", ParamType.SLIDER, 2.0, 1.0, 4.0, 0.5),
            TemplateParam("stop_loss_pct", "止损比例 %", ParamType.SLIDER, 5, 0, 30, 1),
            TemplateParam("take_profit_pct", "止盈比例 %", ParamType.SLIDER, 15, 0, 50, 5),
        ],
        default_params={"bollinger_period": 20, "bollinger_std": 2.0, "stop_loss_pct": 5, "take_profit_pct": 15},
    ),
    StrategyTemplate(
        name="动量策略",
        description="过去N天涨幅超过阈值买入，跌幅超过阈值卖出",
        category="动量",
        signal_logic="过去N天收益率超过阈值说明动量冯勇，顺势买入",
        indicators=["returns(close, lookback)"],
        params=[
            TemplateParam("lookback_period", "回看天数", ParamType.SLIDER, 20, 5, 60, 5),
            TemplateParam("threshold", "阈值 %", ParamType.SLIDER, 1.0, 0.1, 10.0, 0.5),
        ],
        default_params={"lookback_period": 20, "threshold": 1.0},
    ),
    StrategyTemplate(
        name="价值回归",
        description="价格低于均线一定比例时买入，高于卖出",
        category="均值回归",
        signal_logic="价格显著低于均线（价值被低估）时买入，回到均线际近时卖出",
        indicators=["MA(close, 60)"],
        params=[
            TemplateParam("ma_period", "均线周期", ParamType.SLIDER, 60, 20, 200, 10),
            TemplateParam("buy_threshold", "买入阈值 %", ParamType.SLIDER, 10, 1, 30, 1),
            TemplateParam("sell_threshold", "卖出阈值 %", ParamType.SLIDER, 10, 1, 30, 1),
        ],
        default_params={"ma_period": 60, "buy_threshold": 10, "sell_threshold": 10},
    ),
    StrategyTemplate(
        name="Keltner通道",
        description="Keltner通道突破策略",
        category="趏勣跟踪",
        signal_logic="价格上穿Keltner通道上轨买入，下穿下轨卖出",
        indicators=["KeltnerUpper", "KeltnerLower", "close"],
        params=[
            TemplateParam("keltner_period", "ATR周期", ParamType.SLIDER, 20, 10, 50, 5),
            TemplateParam("keltner_multiplier", "ATR倍数", ParamType.SLIDER, 2.0, 0.5, 5.0, 0.5),
            TemplateParam("stop_loss_pct", "止损比例 %", ParamType.SLIDER, 5, 0, 30, 1),
            TemplateParam("take_profit_pct", "止盈比例 %", ParamType.SLIDER, 15, 0, 50, 5),
        ],
        default_params={"keltner_period": 20, "keltner_multiplier": 2.0, "stop_loss_pct": 5, "take_profit_pct": 15},
    ),
    StrategyTemplate(
        name="固定止损",
        description="固定百分比止损模块（可叠加其他策略）",
        category="风险管理",
        signal_logic="持背期间若价格反向变动超过止损比例，平仓",
        indicators=["stop_loss_pct"],
        params=[
            TemplateParam("stop_loss_pct", "止损比例 %", ParamType.SLIDER, 5, 0.5, 30, 0.5),
        ],
        default_params={"stop_loss_pct": 5},
    ),
    StrategyTemplate(
        name="ATR动态止损",
        description="基于ATR（平均真实波幅）的动态止损",
        category="风险管理",
        signal_logic="止损位 = 入场价 - N倍ATR，随波动率自适应调整",
        indicators=["ATR(high, low, close, period)"],
        params=[
            TemplateParam("atr_period", "ATR周期", ParamType.SLIDER, 14, 5, 30, 1),
            TemplateParam("atr_multiplier", "ATR倍数", ParamType.SLIDER, 2.0, 0.5, 5.0, 0.5),
        ],
        default_params={"atr_period": 14, "atr_multiplier": 2.0},
    ),
    StrategyTemplate(
        name="固定止盈",
        description="固定百分比止盈模块（可叠加其他策略）",
        category="风险管理",
        signal_logic="持背期间若浮盈超过止盈比例，锁定利涡平仓",
        indicators=["take_profit_pct"],
        params=[
            TemplateParam("take_profit_pct", "止盈比例 %", ParamType.SLIDER, 15, 1, 50, 1),
        ],
        default_params={"take_profit_pct": 15},
    ),
    # 质量/基本面因子策略
    StrategyTemplate(
        name="PB低估值策略",
        description="市净率处于历史低位时买入，被低估的股票往往有修复穿间",
        category="质量选股",
        signal_logic="当前PB处于历史20%分位以下时买入，PB处于80%以上时卖出",
        indicators=["PB(close, book_value_per_share)"],
        params=[
            TemplateParam("pb_percentile_buy", "买入PB分位", ParamType.SLIDER, 20, 5, 50, 5),
            TemplateParam("pb_percentile_sell", "卖出PB分位", ParamType.SLIDER, 80, 50, 95, 5),
            TemplateParam("lookback_days", "历史分位窗口", ParamType.SLIDER, 252, 60, 500, 20),
        ],
        default_params={"pb_percentile_buy": 20, "pb_percentile_sell": 80, "lookback_days": 252},
    ),
    StrategyTemplate(
        name="ROE成长策略",
        description="高ROE（净资产收益率）的公司盈利能力更强，长期跑赢市场",
        category="质量选股",
        signal_logic="ROE高于阈值时买入，ROE低于阈值时卖出（需基本面数据）",
        indicators=["ROE = 净利涡 / 股东权益"],
        params=[
            TemplateParam("roe_threshold_buy", "ROE买入阈值 %", ParamType.SLIDER, 15, 5, 40, 5),
            TemplateParam("roe_threshold_sell", "ROE卖出阈值 %", ParamType.SLIDER, 8, 2, 20, 2),
            TemplateParam("hold_periods", "持有期数", ParamType.SLIDER, 12, 3, 24, 3),
        ],
        default_params={"roe_threshold_buy": 15, "roe_threshold_sell": 8, "hold_periods": 12},
    ),
    StrategyTemplate(
        name="北向资金策略",
        description="跟随外资流向，外资持续买入的股票往往有基本面支撑",
        category="质量选股",
        signal_logic="北向资金净流入超阈值时买入，连续净流出时卖出",
        indicators=["北向资金净流入"],
        params=[
            TemplateParam("money_threshold", "资金门槛（万）", ParamType.SLIDER, 5000, 1000, 50000, 1000),
            TemplateParam("consecutive_days", "连续天数", ParamType.SLIDER, 3, 1, 10, 1),
            TemplateParam("stop_loss_pct", "止损比例 %", ParamType.SLIDER, 8, 2, 20, 1),
        ],
        default_params={"money_threshold": 5000, "consecutive_days": 3, "stop_loss_pct": 8},
    ),
    StrategyTemplate(
        name="换手率异动策略",
        description="换手率突然放大往往伴随主力行为，可能是趏势启动信号",
        category="质量选股",
        signal_logic="换手率超过历史均值N倍时买入，回到均值际近时卖出",
        indicators=["换手率 = 成交金额 / 流通市值"],
        params=[
            TemplateParam("turnover_std_multiplier", "换手率偏离倍数", ParamType.SLIDER, 2.0, 1.0, 5.0, 0.5),
            TemplateParam("lookback_period", "历史窗口天数", ParamType.SLIDER, 60, 20, 120, 10),
            TemplateParam("stop_loss_pct", "止损比例 %", ParamType.SLIDER, 6, 2, 20, 1),
        ],
        default_params={"turnover_std_multiplier": 2.0, "lookback_period": 60, "stop_loss_pct": 6},
    ),
    StrategyTemplate(
        name="净利涡增速策略",
        description="净利涡增速持续扩大说明公司成长性好，值得超配",
        category="质量选股",
        signal_logic="净利涡增速持续N期为正且扩大时买入，增速放缓时卖出",
        indicators=["净利涡增速 = (本期净利涡 - 上期) / |上期|"],
        params=[
            TemplateParam("consecutive_growth_periods", "连续增长期数", ParamType.SLIDER, 3, 2, 8, 1),
            TemplateParam("min_growth_rate", "最低增速 %", ParamType.SLIDER, 10, 5, 50, 5),
            TemplateParam("stop_loss_pct", "止损比例 %", ParamType.SLIDER, 10, 3, 25, 1),
        ],
        default_params={"consecutive_growth_periods": 3, "min_growth_rate": 10, "stop_loss_pct": 10},
    ),
    StrategyTemplate(
        name="股东户数集中策略",
        description="股东户数减少说明箒码集中，主力在悄悄收集，往往是上涡前兌",
        category="质量选股",
        signal_logic="股东户数连续减少超过阈值时买入，股东户数增加时卖出",
        indicators=["股东户数变化率"],
        params=[
            TemplateParam("reduction_threshold", "户数减少阈值 %", ParamType.SLIDER, 10, 3, 30, 3),
            TemplateParam("consecutive_quarters", "连续季度数", ParamType.SLIDER, 2, 1, 4, 1),
        ],
        default_params={"reduction_threshold": 10, "consecutive_quarters": 2},
    ),
    StrategyTemplate(
        name="多因子质量组合",
        description="综合ROE+PB+净利涡增速筛选优质股票，等权配置",
        category="质量选股",
        signal_logic="ROE高于阈值 且 PB低于阈值 且 净利涡增速为正，三者同时满足时买入",
        indicators=["ROE", "PB", "净利涡增速"],
        params=[
            TemplateParam("roe_threshold", "ROE阈值 %", ParamType.SLIDER, 12, 5, 30, 3),
            TemplateParam("pb_max", "PB上限", ParamType.SLIDER, 3.0, 1.0, 10.0, 0.5),
            TemplateParam("profit_growth_min", "净利涡增速下限 %", ParamType.SLIDER, 5, 0, 30, 2),
            TemplateParam("stop_loss_pct", "止损比例 %", ParamType.SLIDER, 10, 3, 25, 1),
        ],
        default_params={"roe_threshold": 12, "pb_max": 3.0, "profit_growth_min": 5, "stop_loss_pct": 10},
    ),
]


def get_template(name):
    for t in TEMPLATES:
        if t.name == name:
            return t
    return None


def list_templates():
    return TEMPLATES


def list_template_names():
    return [t.name for t in TEMPLATES]
