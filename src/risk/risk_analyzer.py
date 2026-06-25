"""风险分析模块"""

import pandas as pd
import numpy as np
from typing import Dict
import logging
from datetime import datetime

from ..data.data_models import RiskMetrics

logger = logging.getLogger(__name__)


class RiskAnalyzer:
    """风险分析器"""

    def __init__(self):
        self.logger = logger

    def calculate_metrics(self, data: Dict) -> RiskMetrics:
        """
        计算风险指标

        Args:
            data: 股票数据字典

        Returns:
            RiskMetrics 对象
        """
        metrics = RiskMetrics()
        try:
            hist_data = data.get('historical_data', pd.DataFrame())

            if not hist_data.empty and 'close' in hist_data.columns:
                prices = hist_data['close']

                # 计算日收益率
                returns = prices.pct_change().dropna()

                if len(returns) > 5:
                    # 波动率（20日滚动标准差，然后年化）
                    rolling_std = returns.rolling(window=20).std()
                    # 取最后一个有效滚动值（如果有足够数据）或整体均值
                    if rolling_std.dropna().shape[0] > 0:
                        metrics.volatility = rolling_std.dropna().iloc[-1] * np.sqrt(252)
                    else:
                        metrics.volatility = returns.std() * np.sqrt(252)

                    # VaR (95%)
                    metrics.var_95 = np.percentile(returns, 5)

                    # CVaR (95%)
                    var_95_val = metrics.var_95
                    metrics.cvar_95 = returns[returns <= var_95_val].mean()

                    # 最大回撤
                    cumulative = (1 + returns).cumprod()
                    rolling_max = cumulative.cummax()
                    drawdown = (cumulative / rolling_max) - 1
                    metrics.max_drawdown = drawdown.min()

                    # 夏普比率（假设无风险利率3%）
                    risk_free_rate = 0.03
                    if metrics.volatility > 0:
                        metrics.sharpe_ratio = (returns.mean() * 252 - risk_free_rate) / metrics.volatility

                    # 计算 Beta（相对上证指数）
                    metrics.beta = self._calculate_beta(returns, data)

                    # 计算 Sortino / Calmar / Treynor / Omega
                    metrics = self._calculate_risk_adjusted_ratios(returns, metrics, risk_free_rate)

            # 计算Beneish M-Score（如果财务数据可用）
            financial_data = data.get('financial_data', {})
            if financial_data:
                metrics = self._calculate_m_score(data, metrics)
            else:
                metrics.m_score_interpretation = "财务数据不可用，无法计算M-Score"

        except Exception as e:
            self.logger.error(f"风险指标计算失败: {e}")

        return metrics

    def _calculate_m_score(self, data: Dict, metrics: RiskMetrics) -> RiskMetrics:
        """
        计算Beneish M-Score财务操纵检测指标

        M-Score = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI + 0.115*TATA
                  - 0.172*SGI + 0.327*LVGI - 0.174*DEPI + 0.174*SGAI

        判断标准:
        - M-Score > -1.21: 可能存在财务操纵
        - M-Score < -1.78: 正常经营
        - -1.78 <= M-Score <= -1.21: 灰色地带
        """
        try:
            financial_data = data.get('financial_data', {})
            info = data.get('info', {})

            # 获取近两年财务数据
            income_stmt = financial_data.get('income_statement')
            balance_sheet = financial_data.get('balance_sheet')
            cashflow = financial_data.get('cashflow')

            if income_stmt is None or income_stmt.empty:
                metrics.m_score_interpretation = "利润表数据不可用"
                return metrics

            if balance_sheet is None or balance_sheet.empty:
                metrics.m_score_interpretation = "资产负债表数据不可用"
                return metrics

            # 按报告日期排序，取最新的两期
            # akShare的利润表数据按REPORT_DATE排序，最近的在前面
            if 'REPORT_DATE' not in income_stmt.columns:
                metrics.m_score_interpretation = "利润表缺少REPORT_DATE列"
                return metrics

            df_income = income_stmt.sort_values('REPORT_DATE', ascending=False).head(2)
            df_balance = balance_sheet.sort_values('REPORT_DATE', ascending=False).head(2)
            df_cashflow = cashflow.sort_values('REPORT_DATE', ascending=False).head(2) if cashflow is not None and not cashflow.empty else pd.DataFrame()

            if len(df_income) < 2:
                metrics.m_score_interpretation = "利润表数据期数不足"
                return metrics

            # 获取两期数据的索引
            idx_t = df_income.index[0]  # 本期
            idx_t_1 = df_income.index[1]  # 上期

            def get_val(df, row_idx, col_name):
                """安全获取DataFrame值"""
                if df is None or df.empty:
                    return 0.0
                if row_idx not in df.index:
                    return 0.0
                if col_name not in df.columns:
                    return 0.0
                val = df.loc[row_idx, col_name]
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return 0.0
                return float(val)

            # 1. DSRI (Days Sales Receivable Index) - 应收账款天数指数
            # DSRI = (AR_t / Revenue_t) / (AR_{t-1} / Revenue_{t-1})
            ar_t = get_val(balance_sheet, idx_t, 'ACCOUNTS_RECE')
            ar_t_1 = get_val(balance_sheet, idx_t_1, 'ACCOUNTS_RECE')
            revenue_t = get_val(income_stmt, idx_t, 'TOTAL_OPERATE_INCOME')
            revenue_t_1 = get_val(income_stmt, idx_t_1, 'TOTAL_OPERATE_INCOME')

            if revenue_t > 0 and revenue_t_1 > 0 and ar_t > 0 and ar_t_1 > 0:
                dsri_t = (ar_t / revenue_t)
                dsri_t_1 = (ar_t_1 / revenue_t_1)
                metrics.dsri = dsri_t / dsri_t_1 if dsri_t_1 > 0 else 1.0
            else:
                metrics.dsri = 1.0

            # 2. GMI (Gross Margin Index) - 毛利率指数
            # GMI = GrossMargin_{t-1} / GrossMargin_t
            if revenue_t > 0 and revenue_t_1 > 0:
                # GROSS_PROFIT not available, use OPERATE_PROFIT as proxy
                profit_t = get_val(income_stmt, idx_t, 'OPERATE_PROFIT')
                profit_t_1 = get_val(income_stmt, idx_t_1, 'OPERATE_PROFIT')
                gm_t = profit_t / revenue_t if revenue_t > 0 else 0
                gm_t_1 = profit_t_1 / revenue_t_1 if revenue_t_1 > 0 else 0
                metrics.gmi = gm_t_1 / gm_t if gm_t > 0 else 1.0
            else:
                metrics.gmi = 1.0

            # 3. AQI (Asset Quality Index) - 资产质量指数
            # AQI = (NCA_t / TA_t) / (NCA_{t-1} / TA_{t-1})
            # NCA = TOTAL_NONCURRENT_ASSETS (非流动资产合计)
            nca_t = get_val(balance_sheet, idx_t, 'TOTAL_NONCURRENT_ASSETS')
            nca_t_1 = get_val(balance_sheet, idx_t_1, 'TOTAL_NONCURRENT_ASSETS')
            ta_t = get_val(balance_sheet, idx_t, 'TOTAL_ASSETS')
            ta_t_1 = get_val(balance_sheet, idx_t_1, 'TOTAL_ASSETS')

            if ta_t > 0 and ta_t_1 > 0:
                aqi_t = nca_t / ta_t
                aqi_t_1 = nca_t_1 / ta_t_1
                metrics.aq_i = aqi_t / aqi_t_1 if aqi_t_1 > 0 else 1.0
            else:
                metrics.aq_i = 1.0

            # 4. TATA (Total Accruals to Assets) - 总应计项目与资产比率
            # TATA = (NetIncome_t - CFO_t) / TA_t
            net_income_t = get_val(income_stmt, idx_t, 'PARENT_NETPROFIT')
            cfo_t = get_val(df_cashflow, idx_t, 'NETCASH_OPERATE') if not df_cashflow.empty else 0

            if ta_t > 0:
                metrics.tata = (net_income_t - cfo_t) / ta_t
            else:
                metrics.tata = 0.0

            # 5. SGI (Sales Growth Index) - 销售增长指数
            # SGI = Revenue_t / Revenue_{t-1}
            if revenue_t > 0 and revenue_t_1 > 0:
                metrics.sgi = revenue_t / revenue_t_1
            else:
                metrics.sgi = 1.0

            # 6. LVGI (Leverage Index) - 杠杆指数
            # LVGI = (TD_t / TA_t) / (TD_{t-1} / TA_{t-1})
            td_t = get_val(balance_sheet, idx_t, 'TOTAL_LIABILITIES')
            td_t_1 = get_val(balance_sheet, idx_t_1, 'TOTAL_LIABILITIES')

            if ta_t > 0 and ta_t_1 > 0 and td_t > 0 and td_t_1 > 0:
                lvgi_t = td_t / ta_t
                lvgi_t_1 = td_t_1 / ta_t_1
                metrics.lvgi = lvgi_t / lvgi_t_1 if lvgi_t_1 > 0 else 1.0
            else:
                metrics.lvgi = 1.0

            # 7. DEPI (Depreciation Index) - 折旧指数
            # DEPI = DepreciationRate_{t-1} / DepreciationRate_t
            # 折旧率 = 固定资产折旧(FA_IR_DEPR) / 固定资产(FIXED_ASSET)
            dep_t = get_val(df_cashflow, idx_t, 'FA_IR_DEPR') if not df_cashflow.empty else 0
            dep_t_1 = get_val(df_cashflow, idx_t_1, 'FA_IR_DEPR') if not df_cashflow.empty else 0
            fa_t = get_val(balance_sheet, idx_t, 'FIXED_ASSET')
            fa_t_1 = get_val(balance_sheet, idx_t_1, 'FIXED_ASSET')

            if fa_t > 0 and fa_t_1 > 0 and dep_t >= 0 and dep_t_1 >= 0:
                dep_rate_t = dep_t / fa_t
                dep_rate_t_1 = dep_t_1 / fa_t_1
                metrics.depi = dep_rate_t_1 / dep_rate_t if dep_rate_t > 0 else 1.0
            else:
                metrics.depi = 1.0

            # 8. SGAI (SGA Index) - 销售管理费用指数
            # SGAI = (SGA_t / Revenue_t) / (SGA_{t-1} / Revenue_{t-1})
            sga_t = get_val(income_stmt, idx_t, 'SALE_EXPENSE') or \
                   get_val(income_stmt, idx_t, 'MANAGE_EXPENSE') or 0
            sga_t_1 = get_val(income_stmt, idx_t_1, 'SALE_EXPENSE') or \
                      get_val(income_stmt, idx_t_1, 'MANAGE_EXPENSE') or 0

            if revenue_t > 0 and revenue_t_1 > 0:
                sgai_t = sga_t / revenue_t if revenue_t > 0 else 0
                sgai_t_1 = sga_t_1 / revenue_t_1 if revenue_t_1 > 0 else 0
                metrics.sgai = sgai_t / sgai_t_1 if sgai_t_1 > 0 else 1.0
            else:
                metrics.sgai = 1.0

            # 计算M-Score (使用用户提供的公式)
            # M-Score = -4.840 + 0.920×DSRI + 0.528×GMI + 0.404×AQ + 0.892×SGI + 0.115×DEPI - 0.172×SGAI - 0.327×LVGI + 4.697×TATA
            metrics.m_score = (-4.840 +
                              0.920 * metrics.dsri +
                              0.528 * metrics.gmi +
                              0.404 * metrics.aq_i +
                              0.892 * metrics.sgi +
                              0.115 * metrics.depi -
                              0.172 * metrics.sgai -
                              0.327 * metrics.lvgi +
                              4.697 * metrics.tata)

            # M-Score解读
            if metrics.m_score > -1.21:
                metrics.m_score_interpretation = "存在财务操纵嫌疑 (M-Score > -1.21)"
            elif metrics.m_score < -1.78:
                metrics.m_score_interpretation = "财务正常 (M-Score < -1.78)"
            else:
                metrics.m_score_interpretation = "灰色地带 (需进一步调查)"

        except Exception as e:
            self.logger.error(f"M-Score计算失败: {e}")
            metrics.m_score_interpretation = f"M-Score计算错误: {str(e)}"

        return metrics

    def _calculate_beta(self, returns: pd.Series, data: Dict) -> float:
        """
        计算 Beta：Cov(ri, rm) / Var(rm)
        使用上证指数 (000001) 或沪深300 (000300) 作为基准

        Args:
            returns: 个股日收益率序列
            data: 股票数据字典

        Returns:
            Beta 值
        """
        try:
            import akshare as ak

            # 获取上证指数历史数据
            index_code = "sh000001"  # 上证指数
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - pd.Timedelta(days=365)).strftime("%Y%m%d")

            try:
                index_df = ak.stock_zh_index_daily(symbol=index_code)
                if index_df is not None and not index_df.empty:
                    index_df = index_df.tail(300)
                    if 'close' in index_df.columns:
                        index_returns = index_df['close'].pct_change().dropna()

                    # 对齐日期（个股收益率的日期索引）
                    common_dates = returns.index.intersection(index_returns.index)
                    if len(common_dates) < 30:
                        return 1.0

                    aligned_returns = returns.loc[common_dates]
                    aligned_index = index_returns.loc[common_dates]

                    cov = np.cov(aligned_returns, aligned_index)[0, 1]
                    var_market = np.var(aligned_index, ddof=1)
                    if var_market < 1e-10:
                        return 1.0
                    beta = cov / var_market
                    return float(beta)
            except Exception:
                pass

            return 1.0  # 数据获取失败返回默认值

        except Exception as e:
            self.logger.warning(f"Beta计算失败: {e}")
            return 1.0

    def _calculate_risk_adjusted_ratios(self, returns: pd.Series,
                                        metrics: RiskMetrics,
                                        risk_free_rate: float = 0.03,
                                        target_return: float = 0.0) -> RiskMetrics:
        """
        计算 Sortino、Calmar、Treynor、Omega 指标

        Args:
            returns: 日收益率序列
            metrics: 已填充部分指标的 RiskMetrics
            risk_free_rate: 无风险利率（年化）
            target_return: 目标收益（年化），默认 0

        Returns:
            填充了新指标的 RiskMetrics
        """
        try:
            n = len(returns)
            if n < 6:
                return metrics

            # 日无风险利率
            daily_rf = risk_free_rate / 252
            daily_target = target_return / 252

            # 1. 下行标准差（仅计算低于目标收益的收益）
            downside_returns = np.minimum(returns - daily_target, 0)
            downside_variance = np.mean(downside_returns ** 2)
            downside_std = np.sqrt(downside_variance) * np.sqrt(252) if downside_variance > 0 else 0.0
            metrics.downside_dev = float(downside_std)
            metrics.target_return = target_return

            # 2. Sortino Ratio = (Rp - Rf) / 下行标准差
            annual_return = returns.mean() * 252
            if downside_std > 0:
                metrics.sortino_ratio = float((annual_return - risk_free_rate) / downside_std)
            else:
                metrics.sortino_ratio = 0.0

            # 3. Calmar Ratio = (Rp - Rf) / |MaxDrawdown|
            max_dd = abs(metrics.max_drawdown) if metrics.max_drawdown != 0 else 1e-10
            if max_dd > 1e-10:
                metrics.calmar_ratio = float((annual_return - risk_free_rate) / max_dd)
            else:
                metrics.calmar_ratio = 0.0

            # 4. Treynor Ratio = (Rp - Rf) / Beta
            beta = metrics.beta if metrics.beta != 0 else 1.0
            if abs(beta) > 1e-10:
                metrics.treynor_ratio = float((annual_return - risk_free_rate) / beta)
            else:
                metrics.treynor_ratio = 0.0

            # 5. Omega Ratio = sum(max(ri - T, 0)) / sum(max(T - ri, 0))
            # T = 日目标收益（默认 0，即盈亏平衡点）
            gains = np.sum(np.maximum(returns - daily_target, 0))
            losses = np.sum(np.maximum(daily_target - returns, 0))
            if losses > 1e-10:
                metrics.omega_ratio = float(gains / losses)
            else:
                metrics.omega_ratio = float('inf') if gains > 0 else 1.0

        except Exception as e:
            self.logger.warning(f"风险调整指标计算失败: {e}")

        return metrics

    def _get_value(self, df: pd.DataFrame, key: str, column) -> float:
        """从DataFrame中获取指定键的值"""
        if df is None or df.empty:
            return 0.0
        for idx, row in df.iterrows():
            if key in str(idx):
                val = row.get(column, 0)
                return float(val) if val else 0.0
        return 0.0

    def generate_analysis_text(self, data: Dict, metrics: RiskMetrics) -> str:
        """
        生成风险分析文本

        Args:
            data: 原始股票数据
            metrics: 计算得到的风险指标

        Returns:
            风险分析报告文本
        """
        info = data.get('info', {})
        name = info.get('name', data.get('symbol', ''))

        analysis = f"""【{name} - 风险分析报告】

一、波动性风险
- 年化波动率: {metrics.volatility:.2%}
- 95% VaR: {metrics.var_95:.2%}
- 95% CVaR: {metrics.cvar_95:.2%}

二、下行风险
- 最大回撤: {metrics.max_drawdown:.2%}
- 最大单日损失: {metrics.var_95 * 100:.2f}%

三、风险调整收益
- 夏普比率: {metrics.sharpe_ratio:.2f}
- Sortino比率: {metrics.sortino_ratio:.2f}
- Calmar比率: {metrics.calmar_ratio:.2f}
- Treynor比率: {metrics.treynor_ratio:.4f}
- Omega比率: {metrics.omega_ratio:.2f}
- 下行标准差: {metrics.downside_dev:.2%}
- Beta系数: {metrics.beta:.2f}

四、风险等级评估
"""

        # 波动率风险等级
        if metrics.volatility < 0.15:
            analysis += "- 波动率风险：低（年化波动率低于15%）\n"
        elif metrics.volatility < 0.30:
            analysis += "- 波动率风险：中等（年化波动率15%-30%）\n"
        else:
            analysis += "- 波动率风险：高（年化波动率高于30%）\n"

        # 最大回撤风险等级
        if metrics.max_drawdown > -0.10:
            analysis += "- 回撤风险：低（最大回撤小于10%）\n"
        elif metrics.max_drawdown > -0.20:
            analysis += "- 回撤风险：中等（最大回撤10%-20%）\n"
        else:
            analysis += "- 回撤风险：高（最大回撤大于20%）\n"

        # 夏普比率评估
        if metrics.sharpe_ratio > 1.5:
            analysis += "- 风险调整收益：优秀（夏普比率>1.5）\n"
        elif metrics.sharpe_ratio > 0.5:
            analysis += "- 风险调整收益：良好（夏普比率0.5-1.5）\n"
        else:
            analysis += "- 风险调整收益：一般（夏普比率<0.5）\n"

        analysis += "\n五、风险提示\n"
        if metrics.volatility > 0.30:
            analysis += "- 该股票波动较大，投资需谨慎\n"
        if metrics.max_drawdown < -0.20:
            analysis += "- 历史最大回撤较大，需注意下行风险\n"
        if metrics.sharpe_ratio < 0.5:
            analysis += "- 风险调整后收益一般，建议谨慎\n"

        # M-Score财务操纵检测
        analysis += "\n六、财务操纵检测 (Beneish M-Score)\n"
        analysis += f"- M-Score综合得分: {metrics.m_score:.2f}\n"
        analysis += f"- 结论: {metrics.m_score_interpretation}\n"
        analysis += "\n各指标详情:\n"
        analysis += f"- DSRI(应收账款天数指数): {metrics.dsri:.2f}\n"
        analysis += f"- GMI(毛利率指数): {metrics.gmi:.2f}\n"
        analysis += f"- AQI(资产质量指数): {metrics.aq_i:.2f}\n"
        analysis += f"- TATA(总应计项目比率): {metrics.tata:.4f}\n"
        analysis += f"- SGI(销售增长指数): {metrics.sgi:.2f}\n"
        analysis += f"- LVGI(杠杆指数): {metrics.lvgi:.2f}\n"
        analysis += f"- DEPI(折旧指数): {metrics.depi:.2f}\n"
        analysis += f"- SGAI(销售管理费用指数): {metrics.sgai:.2f}\n"

        return analysis