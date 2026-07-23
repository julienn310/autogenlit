"""
年报下载模块 - 基于akshare财务数据 + 东方财富附注
不再依赖PDF下载，直接获取年报财务数据及附注信息
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class AnnualReportDownloader:
    """A股年报数据下载器（基于akshare）"""

    def __init__(self):
        self._ak = None

    def _get_ak(self):
        """懒加载akshare"""
        if self._ak is None:
            import akshare as ak
            self._ak = ak
        return self._ak

    def download_latest_annual_report(self, symbol: str, year: int = None, timeout: int = 15) -> Tuple[Optional[dict], Optional[str]]:
        """
        获取年报数据（不下载PDF，直接通过akshare获取财务数据）
        带超时保护，适配 Streamlit Cloud 等受限环境

        Args:
            symbol: 股票代码，如 "000001"
            year: 指定年份，不指定则获取最新
            timeout: 单次API调用超时秒数，默认15秒

        Returns:
            (年报数据字典, 公司名称) 或 (None, None)
        """
        import threading
        from datetime import datetime

        class TimeoutError(Exception):
            pass

        def run_with_timeout(result_holder, fn, *args, **kwargs):
            """在子线程中运行耗时操作，结果存入 result_holder[0]"""
            try:
                result_holder[0] = fn(*args, **kwargs)
            except Exception as e:
                result_holder[0] = e

        if year is None:
            year = datetime.now().year - 1

        ak = self._get_ak()

        # 格式化股票代码：深交所用 000001.SZ，沪交所用 600519.SH
        if symbol.startswith(('6', '5', '9')):
            sec_code = f"{symbol}.SH"
        else:
            sec_code = f"{symbol}.SZ"

        def fetch_with_timeout(fn, *args, **kwargs):
            """跨平台超时包装：Windows/Mac/Linux 均可用"""
            result_holder = [None]
            t = threading.Thread(target=run_with_timeout, args=(result_holder, fn, *args), kwargs=kwargs)
            t.start()
            t.join(timeout=timeout)
            if t.is_alive():
                # 超时，result_holder[0] 仍是 None 或正在进行的异常
                raise TimeoutError(f"调用 {fn.__name__} 超时（{timeout}s）")
            if isinstance(result_holder[0], Exception):
                raise result_holder[0]
            return result_holder[0]

        try:
            # 获取财务指标（可能较慢，加超时）
            indicator_df = fetch_with_timeout(ak.stock_financial_analysis_indicator_em, symbol=sec_code)

            # 获取利润表
            profit_df = fetch_with_timeout(ak.stock_profit_sheet_by_report_em, symbol=sec_code)

            # 获取资产负债表
            balance_df = fetch_with_timeout(ak.stock_balance_sheet_by_report_em, symbol=sec_code)

            # 获取现金流量表
            cashflow_df = fetch_with_timeout(ak.stock_cash_flow_sheet_by_report_em, symbol=sec_code)

            # 获取公司名称
            name = None
            if indicator_df is not None and not indicator_df.empty:
                if 'SECURITY_NAME_ABBR' in indicator_df.columns:
                    name = indicator_df['SECURITY_NAME_ABBR'].iloc[0]

            # 获取附注信息（供应商/客户/上下游相关）- 非关键，失败也继续
            try:
                notes_df = self._get_financial_notes(ak, sec_code, symbol)
            except Exception as e:
                logger.warning(f"附注信息获取失败（不影响主分析）: {e}")
                notes_df = {}

            result = {
                'symbol': symbol,
                'year': year,
                'name': name,
                'indicator': indicator_df,
                'profit': profit_df,
                'balance': balance_df,
                'cashflow': cashflow_df,
                'notes': notes_df,
            }

            logger.info(f"年报数据获取成功: {symbol} {year}年")
            return result, name

        except TimeoutError:
            logger.warning(f"年报数据获取超时: {symbol} {year}年")
            return None, None
        except Exception as e:
            logger.warning(f"年报数据获取失败: {symbol} {year}年 - {e}")
            return None, None

    def _get_financial_notes(self, ak, sec_code: str, symbol: str) -> Optional[dict]:
        """
        获取财务报表附注中的关键信息：
        - 主要供应商采购占比
        - 主要客户销售占比
        - 前5名供应商/客户明细
        - 关联交易摘要
        """
        notes = {
            'supplier_info': None,   # 供应商信息
            'customer_info': None,   # 客户信息
            'related_party': None,    # 关联交易摘要
            'guarantees': None,      # 对外担保
            'contingent': None,      # 或有负债
        }

        try:
            # 尝试获取东方财富的关联交易明细
            related_df = self._get_related_party_transactions(ak, sec_code)
            if related_df is not None and not related_df.empty:
                notes['related_party'] = related_df
        except Exception as e:
            logger.debug(f"关联交易数据获取失败: {e}")

        try:
            # 尝试通过巨潮获取供应商客户信息
            supplier_customer = self._get_supplier_customer(ak, symbol)
            if supplier_customer:
                notes['supplier_info'] = supplier_customer.get('suppliers')
                notes['customer_info'] = supplier_customer.get('customers')
        except Exception as e:
            logger.debug(f"供应商客户数据获取失败: {e}")

        return notes

    def _get_related_party_transactions(self, ak, sec_code: str):
        """获取关联交易明细"""
        try:
            # 东方财富关联交易
            df = ak.stock_related_party_transaction_em(symbol=sec_code)
            return df
        except Exception:
            pass
        return None

    def _get_supplier_customer(self, ak, symbol: str) -> Optional[dict]:
        """
        通过东方财富获取供应商和客户信息
        返回格式: {'suppliers': {...}, 'customers': {...}}
        """
        result = {}
        try:
            # 格式化为东方财富接口需要的代码格式
            if symbol.startswith(('6', '5', '9')):
                em_code = f"SH{symbol}"
            else:
                em_code = f"SZ{symbol}"

            # 获取主要客户销售占比
            try:
                customer_df = ak.stock_main_customer_em(symbol=em_code)
                if customer_df is not None and not customer_df.empty:
                    result['customers'] = customer_df
            except Exception:
                pass

            # 获取主要供应商采购占比
            try:
                supplier_df = ak.stock_main_supplier_em(symbol=em_code)
                if supplier_df is not None and not supplier_df.empty:
                    result['suppliers'] = supplier_df
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"供应商客户信息获取异常: {e}")

        return result if result else None

    def get_company_name(self, symbol: str) -> Optional[str]:
        """获取公司名称"""
        try:
            ak = self._get_ak()
            if symbol.startswith(('6', '5', '9')):
                sec_code = f"SH{symbol}"
            else:
                sec_code = f"SZ{symbol}"

            df = ak.stock_financial_analysis_indicator_em(symbol=sec_code)
            if not df.empty:
                return df['SECURITY_NAME_ABBR'].iloc[0]
        except:
            pass
        return None
