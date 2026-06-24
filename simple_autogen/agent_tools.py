"""
AutoGen Agent工具集
定义各Agent可使用的工具函数
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.astock_collector import AStockDataCollector
from src.analysis.financial_analyzer import FinancialAnalyzer
from src.risk.risk_analyzer import RiskAnalyzer

# 全局实例
_data_collector = None
_financial_analyzer = None
_risk_analyzer = None


def get_data_collector():
    global _data_collector
    if _data_collector is None:
        _data_collector = AStockDataCollector()
    return _data_collector


def get_financial_analyzer():
    global _financial_analyzer
    if _financial_analyzer is None:
        _financial_analyzer = FinancialAnalyzer()
    return _financial_analyzer


def get_risk_analyzer():
    global _risk_analyzer
    if _risk_analyzer is None:
        _risk_analyzer = RiskAnalyzer()
    return _risk_analyzer


def register_tools():
    """注册AutoGen工具（返回工具列表供Agent使用）"""
    return [
        {
            "name": "get_stock_info",
            "description": "获取股票的基本信息，包括名称、价格、市值、PE、PB等",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码，如 '000001' 或 '600519'"
                    }
                },
                "required": ["symbol"]
            }
        },
        {
            "name": "get_historical_data",
            "description": "获取股票的历史K线数据，用于分析价格趋势和波动率",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "period": {
                        "type": "string",
                        "description": "时间周期：1m, 3m, 6m, 1y, 5y",
                        "default": "1y"
                    }
                },
                "required": ["symbol"]
            }
        },
        {
            "name": "get_financial_data",
            "description": "获取股票的财务报表数据，包括利润表、资产负债表、现金流量表",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    }
                },
                "required": ["symbol"]
            }
        },
        {
            "name": "calculate_financial_metrics",
            "description": "计算财务指标，包括ROE、ROA、毛利率、净利率、资产负债率、流动比率等",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    }
                },
                "required": ["symbol"]
            }
        },
        {
            "name": "calculate_risk_metrics",
            "description": "计算风险指标，包括波动率、VaR、CVaR、最大回撤、夏普比率、Beta，以及Beneish M-Score财务操纵检测",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    }
                },
                "required": ["symbol"]
            }
        },
        {
            "name": "get_market_context",
            "description": "获取市场情绪和宏观数据，帮助判断当前市场环境",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    }
                },
                "required": ["symbol"]
            }
        }
    ]


# 工具实现函数
def tool_get_stock_info(symbol: str) -> dict:
    """获取股票基本信息"""
    collector = get_data_collector()
    info = collector.get_stock_info(symbol)
    if info:
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "name": info.get("name", ""),
                "price": info.get("price", 0),
                "change_pct": info.get("change_pct", 0),
                "market_cap": info.get("market_cap", 0),
                "float_market_cap": info.get("float_market_cap", 0),
                "pe_ttm": info.get("pe_ttm", 0),
                "pb": info.get("pb", 0),
                "ps_ttm": info.get("ps_ttm", 0),
            }
        }
    return {"success": False, "error": f"无法获取股票 {symbol} 的信息"}


def tool_get_historical_data(symbol: str, period: str = "1y") -> dict:
    """获取历史K线数据"""
    collector = get_data_collector()
    end_date = "20250526"
    if period == "1y":
        start_date = "20250526"
    elif period == "6m":
        start_date = "20241126"
    elif period == "3m":
        start_date = "20250226"
    elif period == "1m":
        start_date = "20250426"
    elif period == "5y":
        start_date = "20210526"
    else:
        start_date = "20250526"

    df = collector.get_historical_data(symbol, "daily", start_date, end_date)
    if df is not None and not df.empty:
        # 计算基本统计
        close_prices = df['close'].tolist()
        volumes = df['volume'].tolist() if 'volume' in df.columns else []
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "period": period,
                "data_points": len(close_prices),
                "latest_price": close_prices[-1] if close_prices else 0,
                "price_range": {
                    "max": max(close_prices) if close_prices else 0,
                    "min": min(close_prices) if close_prices else 0
                },
                "recent_volumes": volumes[-10:] if volumes else []
            }
        }
    return {"success": False, "error": f"无法获取股票 {symbol} 的历史数据"}


def tool_get_financial_data(symbol: str) -> dict:
    """获取财务报表数据"""
    collector = get_data_collector()
    financial_data = collector.get_financial_data(symbol)
    if financial_data:
        result = {}
        for key, df in financial_data.items():
            if df is not None and not df.empty:
                result[key] = {
                    "rows": len(df),
                    "columns": list(df.columns),
                    "latest": df.iloc[0].to_dict() if len(df) > 0 else {}
                }
        return {"success": True, "data": result}
    return {"success": False, "error": f"无法获取股票 {symbol} 的财务数据"}


def tool_calculate_financial_metrics(symbol: str) -> dict:
    """计算财务指标"""
    collector = get_data_collector()
    financial_analyzer = get_financial_analyzer()

    data = collector.collect_stock_data(symbol)
    if data and data.get('info'):
        metrics = financial_analyzer.calculate_metrics(data)
        return {
            "success": True,
            "data": metrics.to_dict()
        }
    return {"success": False, "error": f"无法计算股票 {symbol} 的财务指标"}


def tool_calculate_risk_metrics(symbol: str) -> dict:
    """计算风险指标"""
    collector = get_data_collector()
    risk_analyzer = get_risk_analyzer()

    data = collector.collect_stock_data(symbol)
    if data and data.get('info'):
        metrics = risk_analyzer.calculate_metrics(data)
        return {
            "success": True,
            "data": metrics.to_dict()
        }
    return {"success": False, "error": f"无法计算股票 {symbol} 的风险指标"}


def tool_get_market_context(symbol: str) -> dict:
    """获取市场情绪"""
    collector = get_data_collector()
    info = collector.get_stock_info(symbol)
    if info:
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "name": info.get("name", ""),
                "industry": info.get("sector", "未知"),
                "market_sentiment": "neutral",  # 简化处理
                "price": info.get("price", 0),
                "change_pct": info.get("change_pct", 0)
            }
        }
    return {"success": False, "error": f"无法获取股票 {symbol} 的市场信息"}


# 工具函数映射表
TOOL_FUNCTIONS = {
    "get_stock_info": tool_get_stock_info,
    "get_historical_data": tool_get_historical_data,
    "get_financial_data": tool_get_financial_data,
    "calculate_financial_metrics": tool_calculate_financial_metrics,
    "calculate_risk_metrics": tool_calculate_risk_metrics,
    "get_market_context": tool_get_market_context,
}