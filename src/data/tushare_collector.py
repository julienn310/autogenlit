"""Tushare Pro API数据获取模块（可选）"""

import tushare as ts
import pandas as pd
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class TushareDataCollector:
    """Tushare Pro数据收集器（需要token）"""

    def __init__(self, token: str = None):
        self.token = token
        self.pro = None
        if token:
            ts.set_token(token)
            self.pro = ts.pro_api()

    def is_available(self) -> bool:
        """检查是否可用（是否有token）"""
        return self.pro is not None

    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票基本信息
        注意：Tushare的股票信息需要通过其他接口组合获取
        """
        if not self.pro:
            return {}

        try:
            # 获取股票基本信息
            df = self.pro.stock_basic(
                ts_code=f"{self._symbol_to_tscode(symbol)}",
                fields='ts_code,symbol,name,area,industry,market,list_date'
            )
            if df.empty:
                return {}

            row = df.iloc[0]
            return {
                'symbol': symbol,
                'name': row.get('name', ''),
                'area': row.get('area', ''),
                'industry': row.get('industry', ''),
                'market': row.get('market', ''),
                'list_date': row.get('list_date', ''),
            }
        except Exception as e:
            logger.error(f"获取股票 {symbol} 信息失败: {e}")
            return {}

    def _symbol_to_tscode(self, symbol: str) -> str:
        """将A股代码转换为tushare格式（如 000001 -> 000001.SZ）"""
        symbol = symbol.zfill(6)
        if symbol.startswith(('600', '601', '603', '605', '688')):
            return f"{symbol}.SH"
        else:
            return f"{symbol}.SZ"

    def get_daily_price(self, symbol: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """
        获取日线行情

        Args:
            symbol: 股票代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
        """
        if not self.pro:
            return pd.DataFrame()

        try:
            ts_code = self._symbol_to_tscode(symbol)
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

            if df is not None and not df.empty:
                # 转换列名
                df = df.rename(columns={
                    'trade_date': 'date',
                    'vol': 'volume'
                })
                df = df.sort_values('date')
            return df
        except Exception as e:
            logger.error(f"获取 {symbol} 日线数据失败: {e}")
            return pd.DataFrame()

    def get_financial_data(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """
        获取财务数据
        需要Tushare Pro积分
        """
        if not self.pro:
            return {}

        result = {}
        ts_code = self._symbol_to_tscode(symbol)

        try:
            # 利润表
            df = self.pro.income(ts_code=ts_code)
            if df is not None and not df.empty:
                result['income_statement'] = df
        except Exception as e:
            logger.error(f"获取 {symbol} 利润表失败: {e}")

        try:
            # 资产负债表
            df = self.pro.balancesheet(ts_code=ts_code)
            if df is not None and not df.empty:
                result['balance_sheet'] = df
        except Exception as e:
            logger.error(f"获取 {symbol} 资产负债表失败: {e}")

        try:
            # 现金流量表
            df = self.pro.cashflow(ts_code=ts_code)
            if df is not None and not df.empty:
                result['cashflow'] = df
        except Exception as e:
            logger.error(f"获取 {symbol} 现金流量表失败: {e}")

        try:
            # 财务指标
            df = self.pro.fina_indicator(ts_code=ts_code)
            if df is not None and not df.empty:
                result['financial_indicators'] = df
        except Exception as e:
            logger.error(f"获取 {symbol} 财务指标失败: {e}")

        return result

    def get_realtime_quote(self, symbol: str = None) -> pd.DataFrame:
        """
        获取实时行情
        需要实时行情接口权限
        """
        if not self.pro:
            return pd.DataFrame()

        try:
            if symbol:
                ts_code = self._symbol_to_tscode(symbol)
                df = self.pro.realtime_quote(ts_code=ts_code)
            else:
                df = self.pro.realtime_quote()
            return df
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return pd.DataFrame()


def create_tushare_collector(token: str = None) -> TushareDataCollector:
    """工厂函数：创建Tushare收集器"""
    return TushareDataCollector(token)