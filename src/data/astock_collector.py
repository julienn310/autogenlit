"""A股数据获取模块 - 使用新浪财经API（无代理版本）"""

import requests
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime
import logging
import re
import os

# 禁用代理
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

logger = logging.getLogger(__name__)


class AStockDataCollector:
    """A股数据收集器，使用新浪财经API获取实时数据（无需代理）"""

    def __init__(self):
        self.logger = logger
        self.session = requests.Session()
        self.session.trust_env = False  # 禁用环境变量代理
        self.session.headers.update({
            'Referer': 'https://finance.sina.com.cn',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _get_sina_code(self, symbol: str) -> str:
        """获取新浪股票代码"""
        symbol = symbol.zfill(6)
        if symbol.startswith(('600', '601', '603', '605', '688')):
            return f"sh{symbol}"
        else:
            return f"sz{symbol}"

    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票实时行情信息"""
        try:
            sina_code = self._get_sina_code(symbol)
            url = f"https://hq.sinajs.cn/list={sina_code}"

            resp = self.session.get(url, timeout=10)
            for enc in ['gbk', 'gb2312', 'gb18030']:
                try:
                    resp.encoding = enc
                    resp.text.encode(enc)
                    break
                except:
                    continue

            pattern = r'="([^"]+)"'
            match = re.search(pattern, resp.text)

            if not match:
                return {}

            data = match.group(1).split(',')
            if len(data) < 32:
                return {}

            # 计算涨跌
            close_yesterday = float(data[2] or 0)
            price = float(data[3] or 0)
            change = price - close_yesterday
            change_pct = (change / close_yesterday * 100) if close_yesterday > 0 else 0

            info = {
                'symbol': symbol,
                'name': data[0],
                'open': float(data[1] or 0),
                'close_yesterday': close_yesterday,
                'price': price,
                'high': float(data[4] or 0),
                'low': float(data[5] or 0),
                'volume': float(data[8] or 0),
                'amount': float(data[9] or 0),
                'buy1': float(data[10] or 0),
                'sell1': float(data[20] or 0),
                'change': change,
                'change_pct': change_pct,
                'date': data[30],
                'time': data[31],
            }

            # 从腾讯获取扩展数据（PE、PB、市值等）
            tencent_info = self._get_tencent_extended_info(symbol)
            if tencent_info:
                info.update(tencent_info)

            return info
        except Exception as e:
            self.logger.error(f"获取股票 {symbol} 信息失败: {e}")
            return {}

    def _get_tencent_extended_info(self, symbol: str) -> Dict[str, Any]:
        """从腾讯获取扩展数据（PE、PB、市值等）"""
        try:
            sina_code = self._get_sina_code(symbol)
            url = f"https://qt.gtimg.cn/q={sina_code}"
            resp = self.session.get(url, timeout=10)
            resp.encoding = 'utf-8'
            text = resp.text

            if '="' not in text:
                return {}

            data_part = text.split('="')[1].split('"')[0]
            fields = data_part.split('~')

            if len(fields) < 50:
                return {}

            # 市值（亿元）
            market_cap_str = fields[44] if len(fields) > 44 else '0'
            market_cap = float(market_cap_str) * 1e8 if market_cap_str else 0

            return {
                'pe_ttm': float(fields[39]) if len(fields) > 39 and fields[39] else 0,
                'pb': float(fields[46]) if len(fields) > 46 and fields[46] else 0,
                'ps_ttm': float(fields[47]) if len(fields) > 47 and fields[47] else 0,
                'market_cap': market_cap,  # 总市值（元）
                'float_market_cap': float(fields[45]) * 1e8 if len(fields) > 45 and fields[45] else 0,  # 流通市值
                'high_52w': float(fields[55]) if len(fields) > 55 and fields[55] else 0,  # 52周高点
                'low_52w': float(fields[56]) if len(fields) > 56 and fields[56] else 0,  # 52周低点
            }
        except Exception:
            return {}

    def get_historical_data(self, symbol: str, period: str = "daily",
                           start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """
        获取历史K线数据 - 使用akshare API
        """
        try:
            # 转换日期格式
            if start_date and len(start_date) == 8:
                start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            if end_date and len(end_date) == 8:
                end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

            # 使用akshare获取K线数据
            df = self.get_historical_data_akshare(symbol, period, start_date, end_date)

            if df is None or df.empty:
                # 后备：使用腾讯财经API
                return self._get_historical_data_tencent(symbol, start_date, end_date)

            return df
        except Exception as e:
            self.logger.error(f"获取 {symbol} 历史数据失败: {e}")
            return pd.DataFrame()

    def _get_historical_data_tencent(self, symbol: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """使用腾讯财经API获取历史K线数据（后备方案）"""
        try:
            sina_code = self._get_sina_code(symbol)
            # 转换日期格式
            if start_date and len(start_date) == 8:
                start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            if end_date and len(end_date) == 8:
                end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

            # 腾讯财经历史K线接口（前复权）
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                '_var': 'kline_dayqfq',
                'param': f'{sina_code},day,{start_date},{end_date},250,qfq'
            }

            resp = self.session.get(url, params=params, timeout=10)
            resp.encoding = 'utf-8'

            # 解析JSONP
            import json
            text = resp.text
            json_str = text[text.index('=') + 1:]
            data = json.loads(json_str)

            stock_data = data['data'][sina_code]
            klines = stock_data.get('qfqday') or stock_data.get('day')

            if not klines:
                return pd.DataFrame()

            normalized_klines = []
            for kline in klines:
                normalized_klines.append(kline[:6])
            df = pd.DataFrame(normalized_klines, columns=['date', 'open', 'close', 'high', 'low', 'volume'])

            for col in ['open', 'close', 'high', 'low', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df
        except Exception as e:
            self.logger.error(f"腾讯财经获取 {symbol} 历史数据失败: {e}")
            return pd.DataFrame()

    def get_historical_data_akshare(self, symbol: str, period: str = "daily",
                                   start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """使用akshare获取历史K线数据"""
        try:
            import akshare as ak

            # 转换日期格式
            if start_date and len(start_date) == 8:
                start_date_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            else:
                start_date_fmt = start_date

            if end_date and len(end_date) == 8:
                end_date_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
            else:
                end_date_fmt = end_date

            # 确定交易所前缀
            symbol_str = symbol.zfill(6)
            if symbol_str.startswith(('600', '601', '603', '605', '688')):
                market = 'sh'
            else:
                market = 'sz'

            # 使用akshare的新接口 stock_zh_a_daily
            df = ak.stock_zh_a_daily(
                symbol=f"{market}{symbol_str}",
                start_date=start_date_fmt,
                end_date=end_date_fmt,
                adjust="qfq"
            )

            if df is not None and not df.empty:
                # 重命名列以匹配我们的格式
                if '日期' in df.columns:
                    df = df.rename(columns={'日期': 'date'})
                if '开盘' in df.columns:
                    df = df.rename(columns={'开盘': 'open'})
                if '收盘' in df.columns:
                    df = df.rename(columns={'收盘': 'close'})
                if '最高' in df.columns:
                    df = df.rename(columns={'最高': 'high'})
                if '最低' in df.columns:
                    df = df.rename(columns={'最低': 'low'})
                if '成交量' in df.columns:
                    df = df.rename(columns={'成交量': 'volume'})
                if '成交额' in df.columns:
                    df = df.rename(columns={'成交额': 'amount'})

                # 确保按日期排序
                if 'date' in df.columns:
                    df = df.sort_values('date')

            return df if df is not None else pd.DataFrame()
        except Exception as e:
            self.logger.error(f"akshare获取 {symbol} 历史数据失败: {e}")
            return pd.DataFrame()

    def get_financial_data_akshare(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """使用akshare获取财务报表数据"""
        try:
            import akshare as ak

            symbol_str = symbol.zfill(6)
            # akshare需要sz/sh前缀
            if symbol_str.startswith(('600', '601', '603', '605', '688')):
                market_prefix = 'sh'
            else:
                market_prefix = 'sz'

            result = {}

            # 利润表
            try:
                income_df = ak.stock_profit_sheet_by_report_em(symbol=f'{market_prefix}{symbol_str}')
                if income_df is not None and not income_df.empty:
                    result['income_statement'] = income_df
            except Exception as e:
                self.logger.error(f"获取利润表失败: {e}")

            # 资产负债表
            try:
                balance_df = ak.stock_balance_sheet_by_report_em(symbol=f'{market_prefix}{symbol_str}')
                if balance_df is not None and not balance_df.empty:
                    result['balance_sheet'] = balance_df
            except Exception as e:
                self.logger.error(f"获取资产负债表失败: {e}")

            # 现金流量表
            try:
                cashflow_df = ak.stock_cash_flow_sheet_by_report_em(symbol=f'{market_prefix}{symbol_str}')
                if cashflow_df is not None and not cashflow_df.empty:
                    result['cashflow'] = cashflow_df
            except Exception as e:
                self.logger.error(f"获取现金流量表失败: {e}")

            return result
        except Exception as e:
            self.logger.error(f"akshare获取财务数据失败: {e}")
            return {}

    def _get_historical_data_sina(self, symbol: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """使用新浪财经API获取历史K线数据（后备方案）"""
        try:
            sina_code = self._get_sina_code(symbol)
            # 新浪财经历史数据接口
            url = f"https://finance.sina.com.cn/realstock/company/{sina_code}/hisdata/klc_kl.js"
            resp = self.session.get(url, timeout=10)
            resp.encoding = 'gbk'

            if not resp.text or len(resp.text) < 100:
                return pd.DataFrame()

            # 解析加密的JS数据
            import base64
            import struct

            text = resp.text
            # 提取base64编码的数据部分
            match = re.search(r'"([^"]+)"$', text)
            if not match:
                return pd.DataFrame()

            encoded_data = match.group(1)
            # 解码base64
            try:
                decoded = base64.b64decode(encoded_data)
                # 解析自定义格式的二进制数据
                rows = []
                idx = 0
                data_len = len(decoded)
                while idx < data_len - 24:
                    # 解析日期字符串 (8 bytes)
                    date_bytes = decoded[idx:idx+8]
                    date_str = date_bytes.decode('utf-8').strip('\x00')
                    idx += 8

                    # 解析5个浮点数 (5 * 8 = 40 bytes)
                    values = struct.unpack('>5d', decoded[idx:idx+40])
                    idx += 40

                    rows.append({
                        'date': date_str,
                        'open': values[0],
                        'close': values[1],
                        'high': values[2],
                        'low': values[3],
                        'volume': values[4]
                    })

                df = pd.DataFrame(rows)
                # 按日期排序
                if not df.empty and 'date' in df.columns:
                    df = df.sort_values('date')
                return df
            except Exception:
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"新浪财经获取 {symbol} 历史数据失败: {e}")
            return pd.DataFrame()

    def get_financial_data(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """
        获取财务数据 - 使用akshare获取财务报表数据
        """
        return self.get_financial_data_akshare(symbol)

    def get_realtime_quote(self, symbols: list) -> pd.DataFrame:
        """批量获取实时行情"""
        try:
            codes = ','.join([self._get_sina_code(s) for s in symbols])
            url = f"https://hq.sinajs.cn/list={codes}"

            resp = self.session.get(url, timeout=10)
            resp.encoding = 'gbk'

            rows = []
            for line in resp.text.strip().split('\n'):
                match = re.search(r'hq_str_(\w+)="([^"]+)"', line)
                if match:
                    code = match.group(1)
                    data = match.group(2).split(',')
                    if len(data) >= 32:
                        rows.append({
                            'code': code,
                            'name': data[0],
                            'price': float(data[3] or 0),
                            'change': float(data[3] or 0) - float(data[2] or 0),
                            'volume': float(data[8] or 0),
                            'amount': float(data[9] or 0),
                        })

            return pd.DataFrame(rows)
        except Exception as e:
            self.logger.error(f"批量获取行情失败: {e}")
            return pd.DataFrame()

    def get_stock_industry(self, symbol: str) -> Dict[str, str]:
        """获取股票所属行业信息"""
        try:
            # 尝试从新浪获取行业信息
            sina_code = self._get_sina_code(symbol)
            url = f"https://hq.sinajs.cn/list={sina_code}"
            resp = self.session.get(url, timeout=10)
            resp.encoding = 'gbk'

            pattern = r'="([^"]+)"'
            match = re.search(pattern, resp.text)
            if match:
                data = match.group(1).split(',')
                if len(data) > 32:
                    return {
                        'name': data[0],
                        'sector': data[33] if len(data) > 33 else '',
                    }
        except:
            pass
        return {}

    def collect_stock_data(self, symbol: str, period: str = "1y") -> Dict[str, Any]:
        """
        收集股票完整数据

        Returns:
            包含实时行情、历史K线（如果有）、行业信息的字典
        """
        self.logger.info(f"开始收集 {symbol} 的数据...")

        # 收集实时数据
        info = self.get_stock_info(symbol)

        # 收集历史数据
        end_date = datetime.now().strftime("%Y%m%d")
        if period == "1y":
            start_date = "20250524"
        elif period == "6mo":
            start_date = "20241124"
        else:
            start_date = "20250524"

        historical_data = self.get_historical_data(symbol, "daily", start_date, end_date)

        # 收集行业信息
        industry_info = self.get_stock_industry(symbol)

        # 收集财务数据
        financial_data = self.get_financial_data(symbol)

        data = {
            'symbol': symbol,
            'info': info,
            'historical_data': historical_data,
            'financial_data': financial_data,
            'industry_info': industry_info,
            'collection_time': datetime.now().isoformat()
        }

        self.logger.info(f"成功收集 {symbol} 的数据")
        return data


def get_stock_name(symbol: str) -> str:
    """根据股票代码获取股票名称"""
    try:
        collector = AStockDataCollector()
        info = collector.get_stock_info(symbol)
        return info.get('name', symbol)
    except:
        return symbol