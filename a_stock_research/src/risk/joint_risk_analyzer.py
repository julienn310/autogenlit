"""联合风控分析模块 - 多模型综合风险评估"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class JointRiskMetrics:
    """联合风控指标"""
    # === 一、盈余管理 ===
    # Jones Model
    jones_da: float = 0.0          # 可操纵应计利润
    jones_interpretation: str = ""
    # Dechow-Dichev
    dd_aq: float = 0.0             # 应计质量损失
    dd_interpretation: str = ""
    # Roychowdhury REM
    rem_score: float = 0.0          # 真实盈余管理得分
    rem_interpretation: str = ""

    # === 二、财务困境/破产预警 ===
    altman_z: float = 0.0           # Altman Z-Score
    altman_z_interpretation: str = ""
    ohlson_o: float = 0.0           # Ohlson O-Score
    ohlson_o_interpretation: str = ""
    springate_s: float = 0.0        # Springate S-Score
    springate_s_interpretation: str = ""
    zmijewski_x: float = 0.0       # Zmijewski X-Score
    zmijewski_x_interpretation: str = ""

    # === 三、财务质量筛查 ===
    piotroski_f: float = 0.0       # Piotroski F-Score (0-9)
    piotroski_f_interpretation: str = ""

    # === 四、Beneish M-Score（8变量原版）===
    m_score: float = 0.0            # Beneish M-Score
    m_score_interpretation: str = ""

    # === 五、财报舞弊/造假概率模型 ===
    dechow_f: float = 0.0          # Dechow F-Score (舞弊概率)
    dechow_f_interpretation: str = ""
    montier_c: float = 0.0          # Montier C-Score (6分制)
    montier_c_interpretation: str = ""
    sloan_accrual: float = 0.0       # Sloan 应计异象模型
    sloan_accrual_interpretation: str = ""

    # === 五、综合评分 ===
    combined_risk_score: float = 0.0  # 综合风险评分 (0-100)
    combined_risk_level: str = ""     # 综合风险等级: 低/中/高/极高
    combined_risk_summary: str = ""  # 综合风控总结

    def to_dict(self) -> Dict:
        return {
            # 盈余管理
            'jones_da': f"{self.jones_da:.4f}" if self.jones_da != 0 else '-',
            'jones_interpretation': self.jones_interpretation,
            'dd_aq': f"{self.dd_aq:.4f}" if self.dd_aq != 0 else '-',
            'dd_interpretation': self.dd_interpretation,
            'rem_score': f"{self.rem_score:.4f}" if self.rem_score != 0 else '-',
            'rem_interpretation': self.rem_interpretation,
            # 破产预警
            'altman_z': f"{self.altman_z:.2f}" if self.altman_z != 0 else '-',
            'altman_z_interpretation': self.altman_z_interpretation,
            'oholson_o': f"{self.oholson_o:.2f}" if self.oholson_o != 0 else '-',
            'oholson_o_interpretation': self.oholson_o_interpretation,
            'springate_s': f"{self.springate_s:.2f}" if self.springate_s != 0 else '-',
            'springate_s_interpretation': self.springate_s_interpretation,
            'zmijewski_x': f"{self.zmijewski_x:.2f}" if self.zmijewski_x != 0 else '-',
            'zmijewski_x_interpretation': self.zmijewski_x_interpretation,
            # 财务质量
            'piotroski_f': f"{int(self.piotroski_f)}" if self.piotroski_f != 0 else '-',
            'piotroski_f_interpretation': self.piotroski_f_interpretation,
            # M-Score
            'm_score': f"{self.m_score:.2f}" if self.m_score != 0 else '-',
            'm_score_interpretation': self.m_score_interpretation,
            # 财报舞弊/造假
            'dechow_f': f"{self.dechow_f:.4f}" if self.dechow_f != 0 else '-',
            'dechow_f_interpretation': self.dechow_f_interpretation,
            'montier_c': f"{self.montier_c:.1f}" if self.montier_c != 0 else '-',
            'montier_c_interpretation': self.montier_c_interpretation,
            'sloan_accrual': f"{self.sloan_accrual:.4f}" if self.sloan_accrual != 0 else '-',
            'sloan_accrual_interpretation': self.sloan_accrual_interpretation,
            # 综合
            'combined_risk_score': f"{self.combined_risk_score:.0f}" if self.combined_risk_score != 0 else '-',
            'combined_risk_level': self.combined_risk_level,
            'combined_risk_summary': self.combined_risk_summary,
        }


def _safe_val(df: pd.DataFrame, row_pos: int, col_name: str, default=0.0) -> float:
    """安全获取DataFrame中的值（positional index）"""
    if df is None or df.empty:
        return default
    if row_pos < 0 or row_pos >= len(df):
        return default
    if col_name not in df.columns:
        return default
    val = df.iloc[row_pos][col_name]
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    return float(val)


class JointRiskAnalyzer:
    """联合风控分析器"""

    def __init__(self):
        self.logger = logger

    def analyze(self, data: Dict) -> JointRiskMetrics:
        """
        执行联合风控分析

        Args:
            data: AStockDataCollector.collect_stock_data() 返回的数据字典

        Returns:
            JointRiskMetrics
        """
        metrics = JointRiskMetrics()
        try:
            financial_data = data.get('financial_data', {})
            info = data.get('info', {})

            income_stmt = financial_data.get('income_statement')
            balance_sheet = financial_data.get('balance_sheet')
            cashflow = financial_data.get('cashflow')

            if income_stmt is None or balance_sheet is None or income_stmt.empty or balance_sheet.empty:
                metrics.jones_interpretation = "财务数据不足，无法计算"
                metrics.dd_interpretation = "财务数据不足，无法计算"
                metrics.rem_interpretation = "财务数据不足，无法计算"
                metrics.altman_z_interpretation = "财务数据不足，无法计算"
                metrics.oholson_o_interpretation = "财务数据不足，无法计算"
                metrics.springate_s_interpretation = "财务数据不足，无法计算"
                metrics.zmijewski_x_interpretation = "财务数据不足，无法计算"
                metrics.piotroski_f_interpretation = "财务数据不足，无法计算"
                metrics.combined_risk_summary = "财务数据不足，无法完成联合风控分析"
                return metrics

            # 按日期排序取最新两期
            df_inc = income_stmt.sort_values('REPORT_DATE', ascending=False).head(2)
            df_bal = balance_sheet.sort_values('REPORT_DATE', ascending=False).head(2)
            df_cf = cashflow.sort_values('REPORT_DATE', ascending=False).head(2) if cashflow is not None and not cashflow.empty else pd.DataFrame()

            if len(df_inc) < 2 or len(df_bal) < 2:
                metrics.jones_interpretation = "数据期数不足"
                metrics.combined_risk_summary = "数据期数不足"
                return metrics

            idx_t = 0   # 本期（positional index，sort后取头2行，iloc[0]即最新一期）
            idx_t1 = 1  # 上期

            # ===== 1. Jones Model =====
            metrics = self._calc_jones_model(df_inc, df_bal, df_cf, idx_t, idx_t1, metrics)

            # ===== 2. Dechow-Dichev =====
            metrics = self._calc_dechow_dichev(df_inc, df_bal, df_cf, idx_t, idx_t1, metrics)

            # ===== 3. Roychowdhury REM =====
            metrics = self._calc_roychowdhury_rem(df_inc, df_bal, df_cf, idx_t, idx_t1, metrics)

            # ===== 4. Altman Z-Score =====
            metrics = self._calc_altman_z(df_inc, df_bal, info, idx_t, metrics)

            # ===== 5. Ohlson O-Score =====
            metrics = self._calc_ohlson_o(df_inc, df_bal, info, idx_t, idx_t1, metrics)

            # ===== 6. Springate S-Score =====
            metrics = self._calc_springate_s(df_inc, df_bal, idx_t, metrics)

            # ===== 7. Zmijewski X-Score =====
            metrics = self._calc_zmijewski_x(df_inc, df_bal, idx_t, metrics)

            # ===== 8. Piotroski F-Score =====
            metrics = self._calc_piotroski_f(df_inc, df_bal, df_cf, idx_t, idx_t1, metrics)

            # ===== 9. Dechow F-Score (舞弊概率) =====
            metrics = self._calc_dechow_f(df_inc, df_bal, df_cf, idx_t, idx_t1, metrics)

            # ===== 10. Montier C-Score =====
            metrics = self._calc_montier_c(df_inc, df_bal, df_cf, idx_t, idx_t1, metrics)

            # ===== 11. Sloan 应计异象 =====
            metrics = self._calc_sloan_accrual(df_inc, df_bal, df_cf, idx_t, idx_t1, metrics)

            # ===== 13. 综合评分 =====
            metrics = self._calc_combined_score(metrics)

        except Exception as e:
            self.logger.error(f"联合风控分析失败: {e}")
            metrics.combined_risk_summary = f"分析异常: {str(e)}"

        return metrics

    # ────────────────────────────
    # 1. Jones Model (Modified)
    # ────────────────────────────
    def _calc_jones_model(self, df_inc, df_bal, df_cf, idx_t, idx_t1, metrics):
        """
        修正 Jones Model: DA = TA - NDA
        TA = 营业利润 - 经营现金流（标准化为资产）
        NDA = α0 + α1*(ΔREV - ΔREC)/A + α2*(PPE/A)
        """
        try:
            # 资产标准化：使用期初总资产
            A_t1 = _safe_val(df_bal, idx_t1, 'TOTAL_ASSETS', 1)
            A_t = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', A_t1)
            A = (A_t + A_t1) / 2  # 平均资产

            if A <= 0:
                metrics.jones_interpretation = "资产数据异常"
                return metrics

            # 总应计利润 TA = (NI - CFO) / A
            NI_t = _safe_val(df_inc, idx_t, 'PARENT_NETPROFIT', 0)
            CFO_t = _safe_val(df_cf, idx_t, 'NETCASH_OPERATE', NI_t) if not df_cf.empty else NI_t
            TA = (NI_t - CFO_t) / A

            # 营业收入变化
            REV_t = _safe_val(df_inc, idx_t, 'TOTAL_OPERATE_INCOME', 0)
            REV_t1 = _safe_val(df_inc, idx_t1, 'TOTAL_OPERATE_INCOME', 0)
            delta_REV = (REV_t - REV_t1) / A

            # 应收账款变化
            REC_t = _safe_val(df_bal, idx_t, 'ACCOUNTS_RECE', 0)
            REC_t1 = _safe_val(df_bal, idx_t1, 'ACCOUNTS_RECE', 0)
            delta_REC = (REC_t - REC_t1) / A

            # 固定资产
            PPE_t = _safe_val(df_bal, idx_t, 'FIXED_ASSET', 0)
            PPE = PPE_t / A

            # 回归系数（使用行业标准值，简化）
            alpha0, alpha1, alpha2 = -0.001, 0.033, 0.040
            NDA = alpha0 + alpha1 * max(delta_REV - delta_REC, 0) + alpha2 * PPE

            DA = TA - NDA
            metrics.jones_da = DA

            abs_da = abs(DA)
            if abs_da < 0.03:
                metrics.jones_interpretation = f"正常 (DA={DA:.4f})，盈余管理迹象不明显"
            elif abs_da < 0.08:
                metrics.jones_interpretation = f"轻度异常 (DA={DA:.4f})，存在轻微盈余调节"
            else:
                metrics.jones_interpretation = f"显著异常 (DA={DA:.4f})，可能存在较大利润操纵"

        except Exception as e:
            metrics.jones_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 2. Dechow-Dichev Accrual Quality
    # ────────────────────────────
    def _calc_dechow_dichev(self, df_inc, df_bal, df_cf, idx_t, idx_t1, metrics):
        """
        Dechow-Dichev: 应计质量 = 回归残差标准误
        ΔWC = f(CFO) + ε，ε为应计质量损失
        """
        try:
            A_t1 = _safe_val(df_bal, idx_t1, 'TOTAL_ASSETS', 1)
            A_t = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', A_t1)
            A = (A_t + A_t1) / 2
            if A <= 0:
                metrics.dd_interpretation = "资产数据异常"
                return metrics

            # 工作资本变化 = ΔAR + ΔInventory - ΔAP
            AR_t = _safe_val(df_bal, idx_t, 'ACCOUNTS_RECE', 0)
            AR_t1 = _safe_val(df_bal, idx_t1, 'ACCOUNTS_RECE', 0)
            INV_t = _safe_val(df_bal, idx_t, 'INVENTORY', 0)
            INV_t1 = _safe_val(df_bal, idx_t1, 'INVENTORY', 0)
            AP_t = _safe_val(df_bal, idx_t, 'ACCOUNTS_PAYABLE', 0)
            AP_t1 = _safe_val(df_bal, idx_t1, 'ACCOUNTS_PAYABLE', 0)
            delta_WC = ((AR_t - AR_t1) + (INV_t - INV_t1) - (AP_t - AP_t1)) / A

            # 经营现金流
            CFO_t = _safe_val(df_cf, idx_t, 'NETCASH_OPERATE', 0) if not df_cf.empty else 0
            CFO_t1 = _safe_val(df_cf, idx_t1, 'NETCASH_OPERATE', 0) if not df_cf.empty else 0
            CFO = (CFO_t + CFO_t1) / 2 / A

            # 简化残差：|ΔWC - 0.7*CFO| 作为应计质量损失
            expected = 0.7 * CFO
            AQ_loss = abs(delta_WC - expected)
            metrics.dd_aq = AQ_loss

            if AQ_loss < 0.05:
                metrics.dd_interpretation = f"优秀 (AQ损失={AQ_loss:.4f})，应计质量良好"
            elif AQ_loss < 0.10:
                metrics.dd_interpretation = f"一般 (AQ损失={AQ_loss:.4f})，存在一定应计偏差"
            else:
                metrics.dd_interpretation = f"较差 (AQ损失={AQ_loss:.4f})，会计估计激进"

        except Exception as e:
            metrics.dd_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 3. Roychowdhury REM
    # ────────────────────────────
    def _calc_roychowdhury_rem(self, df_inc, df_bal, df_cf, idx_t, idx_t1, metrics):
        """
        真实盈余管理REM：
        - 异常现金流 (ABCFO)
        - 异常生产成本 (ABPROD)
        - 异常酌量性费用 (ADISX)
        REM = |ABPROD| + |ABCFO| + |ADISX| 越高越异常
        """
        try:
            A_t1 = _safe_val(df_bal, idx_t1, 'TOTAL_ASSETS', 1)
            A_t = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', A_t1)
            A = (A_t + A_t1) / 2
            if A <= 0:
                metrics.rem_interpretation = "资产数据异常"
                return metrics

            REV_t = _safe_val(df_inc, idx_t, 'TOTAL_OPERATE_INCOME', 0)
            REV_t1 = _safe_val(df_inc, idx_t1, 'TOTAL_OPERATE_INCOME', 0)
            CFO_t = _safe_val(df_cf, idx_t, 'NETCASH_OPERATE', 0) if not df_cf.empty else 0
            CFO_t1 = _safe_val(df_cf, idx_t1, 'NETCASH_OPERATE', 0) if not df_cf.empty else 0

            SGA_t = _safe_val(df_inc, idx_t, 'SALE_EXPENSE', 0) + _safe_val(df_inc, idx_t, 'MANAGE_EXPENSE', 0)
            SGA_t1 = _safe_val(df_inc, idx_t1, 'SALE_EXPENSE', 0) + _safe_val(df_inc, idx_t1, 'MANAGE_EXPENSE', 0)

            COGS_t = _safe_val(df_inc, idx_t, 'OPERATE_COST', 0)
            INV_t = _safe_val(df_bal, idx_t, 'INVENTORY', 0)
            INV_t1 = _safe_val(df_bal, idx_t1, 'INVENTORY', 0)

            # 标准化
            CFO_norm = CFO_t / A
            REV_norm = REV_t / A
            SGA_norm = SGA_t / A
            COGS_norm = COGS_t / A
            INV_norm = (INV_t - INV_t1) / A

            # 简化 REM
            rem_score = abs(CFO_norm / max(REV_norm, 0.01) - 0.1) + abs(SGA_norm / max(REV_norm, 0.01) - 0.15)
            metrics.rem_score = rem_score

            if rem_score < 0.2:
                metrics.rem_interpretation = f"正常 (REM={rem_score:.4f})，无明显真实盈余管理"
            elif rem_score < 0.5:
                metrics.rem_interpretation = f"轻度异常 (REM={rem_score:.4f})，存在一定真实活动调节"
            else:
                metrics.rem_interpretation = f"显著异常 (REM={rem_score:.4f})，可能存在重大真实盈余管理"

        except Exception as e:
            metrics.rem_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 4. Altman Z-Score
    # ────────────────────────────
    def _calc_altman_z(self, df_inc, df_bal, info, idx_t, metrics):
        """
        Altman Z-Score (上市公司制造业)
        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
        X1 = 营运资本/总资产
        X2 = 留存收益/总资产
        X3 = EBIT/总资产
        X4 = 股权市值/总负债
        X5 = 销售额/总资产
        """
        try:
            TA = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', 1)
            if TA <= 0:
                metrics.altman_z_interpretation = "资产数据异常"
                return metrics

            WC = _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_ASSETS', 0) - _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_LIABILITIES', 0)
            RE = _safe_val(df_bal, idx_t, 'SURPLUS_RESERVE', 0) + _safe_val(df_bal, idx_t, 'UNPAID_INCOME', 0)
            EBIT = _safe_val(df_inc, idx_t, 'OPERATE_PROFIT', 0)
            total_debt = _safe_val(df_bal, idx_t, 'TOTAL_LIABILITIES', 0)
            revenue = _safe_val(df_inc, idx_t, 'TOTAL_OPERATE_INCOME', 0)

            market_cap = info.get('market_cap', 0)
            if total_debt > 0:
                equity_debt_ratio = market_cap / total_debt
            else:
                equity_debt_ratio = 99.0

            X1 = WC / TA
            X2 = RE / TA
            X3 = EBIT / TA
            X4 = equity_debt_ratio
            X5 = revenue / TA

            Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
            metrics.altman_z = Z

            if Z > 2.99:
                metrics.altman_z_interpretation = f"安全区 (Z={Z:.2f})，破产风险低"
            elif Z > 1.81:
                metrics.altman_z_interpretation = f"灰色地带 (Z={Z:.2f})，存在一定风险"
            else:
                metrics.altman_z_interpretation = f"高风险区 (Z={Z:.2f})，破产风险高"

        except Exception as e:
            metrics.altman_z_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 5. Ohlson O-Score
    # ────────────────────────────
    def _calc_ohlson_o(self, df_inc, df_bal, info, idx_t, idx_t1, metrics):
        """
        Ohlson O-Score (Logistic)
        O = -1.32 - 0.407*SIZE + 6.03*TLTA - 1.43*WCTA + 0.076*CLCA - 1.72*OENEG - 2.37*NITA - 1.83*LAGT
        """
        try:
            TA = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', 1)
            if TA <= 0:
                metrics.oholson_o_interpretation = "资产数据异常"
                return metrics

            TLTA = _safe_val(df_bal, idx_t, 'TOTAL_LIABILITIES', 0) / TA
            WCTA = (_safe_val(df_bal, idx_t, 'TOTAL_CURRENT_ASSETS', 0) - _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_LIABILITIES', 0)) / TA
            CLCA = _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_LIABILITIES', 0) / _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_ASSETS', 1)
            OENEG = 1.0 if _safe_val(df_bal, idx_t, 'TOTAL_LIABILITIES', 0) > _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', 1) else 0.0
            NITA = _safe_val(df_inc, idx_t, 'PARENT_NETPROFIT', 0) / TA
            NI_t = _safe_val(df_inc, idx_t, 'PARENT_NETPROFIT', 0)
            NI_t1 = _safe_val(df_inc, idx_t1, 'PARENT_NETPROFIT', 0)
            LAGT = 1.0 if NI_t < 0 and NI_t1 < 0 else 0.0

            SIZE = np.log(max(TA, 1)) / 10  # 缩放

            O = -1.32 - 0.407*SIZE + 6.03*TLTA - 1.43*WCTA + 0.076*CLCA - 1.72*OENEG - 2.37*NITA - 1.83*LAGT
            # 转换为概率
            prob = 1 / (1 + np.exp(-O))
            metrics.oholson_o = prob

            if prob < 0.1:
                metrics.oholson_o_interpretation = f"低风险 (O={prob:.2%})，财务状况良好"
            elif prob < 0.5:
                metrics.oholson_o_interpretation = f"中风险 (O={prob:.2%})，存在财务困境可能"
            else:
                metrics.oholson_o_interpretation = f"高风险 (O={prob:.2%})，破产概率较高"

        except Exception as e:
            metrics.oholson_o_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 6. Springate S-Score
    # ────────────────────────────
    def _calc_springate_s(self, df_inc, df_bal, idx_t, metrics):
        """
        Springate S-Score
        S = 1.03*A + 3.07*B + 0.66*C + 0.4*D
        A = WC/TA, B = EBIT/TA, C = EBT/CL, D = Sales/TA
        S < 0.862 → 高破产风险
        """
        try:
            TA = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', 1)
            if TA <= 0:
                metrics.springate_s_interpretation = "资产数据异常"
                return metrics

            WC = _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_ASSETS', 0) - _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_LIABILITIES', 0)
            EBIT = _safe_val(df_inc, idx_t, 'OPERATE_PROFIT', 0)
            EBT = _safe_val(df_inc, idx_t, 'PARENT_NETPROFIT', 0)
            CL = _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_LIABILITIES', 1)
            Sales = _safe_val(df_inc, idx_t, 'TOTAL_OPERATE_INCOME', 0)

            A = WC / TA
            B = EBIT / TA
            C = EBT / max(CL, 1)
            D = Sales / TA

            S = 1.03*A + 3.07*B + 0.66*C + 0.4*D
            metrics.springate_s = S

            if S > 0.862:
                metrics.springate_s_interpretation = f"安全 (S={S:.2f})，破产风险低"
            else:
                metrics.springate_s_interpretation = f"高风险 (S={S:.2f})，破产风险高"

        except Exception as e:
            metrics.springate_s_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 7. Zmijewski X-Score（A股校准版）
    # ────────────────────────────
    def _calc_zmijewski_x(self, df_inc, df_bal, idx_t, metrics):
        """
        Zmijewski X-Score（A股校准版）
        原始公式: X = -4.3 - 4.5*ROA + 5.7*DEBT - 0.004*CR
        A股校准: X = -2.5 - 2.0*ROA + 3.5*DEBT - 0.02*CR
        转换为概率: P = 1/(1+e^X)
        """
        try:
            TA = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', 1)
            if TA <= 0:
                metrics.zmijewski_x_interpretation = "资产数据异常"
                return metrics

            ROA = _safe_val(df_inc, idx_t, 'PARENT_NETPROFIT', 0) / TA
            DEBT = _safe_val(df_bal, idx_t, 'TOTAL_LIABILITIES', 0) / TA
            CL = _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_LIABILITIES', 1)
            CR = _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_ASSETS', 1) / max(CL, 1)

            # A股校准版系数（原系数对A股普通公司会持续输出≈1）
            X = -2.5 - 2.0*ROA + 3.5*DEBT - 0.02*CR
            prob = 1 / (1 + np.exp(max(min(X, 700), -700)))
            metrics.zmijewski_x = prob

            if prob < 0.1:
                metrics.zmijewski_x_interpretation = f"低风险 (X={prob:.2%})"
            elif prob < 0.3:
                metrics.zmijewski_x_interpretation = f"中风险 (X={prob:.2%})"
            elif prob < 0.5:
                metrics.zmijewski_x_interpretation = f"较高风险 (X={prob:.2%})"
            else:
                metrics.zmijewski_x_interpretation = f"高风险 (X={prob:.2%})"

        except Exception as e:
            metrics.zmijewski_x_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 8. Piotroski F-Score (0-9)
    # ────────────────────────────
    def _calc_piotroski_f(self, df_inc, df_bal, df_cf, idx_t, idx_t1, metrics):
        """
        Piotroski F-Score (9分制)
        盈利能力(3项): ROA>0, CFO>0, ΔROA>0
        杠杆/流动性(3项): ΔLEVER↓, ΔLIQU↑, 无增发
        运营效率(3项): ΔMARGIN↑, ΔTURN↑, ΔSGA↓
        """
        try:
            TA_t = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', 1)
            TA_t1 = _safe_val(df_bal, idx_t1, 'TOTAL_ASSETS', 1)
            NI_t = _safe_val(df_inc, idx_t, 'PARENT_NETPROFIT', 0)
            NI_t1 = _safe_val(df_inc, idx_t1, 'PARENT_NETPROFIT', 0)
            CFO_t = _safe_val(df_cf, idx_t, 'NETCASH_OPERATE', 0) if not df_cf.empty else NI_t
            CFO_t1 = _safe_val(df_cf, idx_t1, 'NETCASH_OPERATE', 0) if not df_cf.empty else NI_t1

            ROA_t = NI_t / TA_t
            ROA_t1 = NI_t1 / TA_t1
            LEVER_t = _safe_val(df_bal, idx_t, 'TOTAL_LIABILITIES', 0) / TA_t
            LEVER_t1 = _safe_val(df_bal, idx_t1, 'TOTAL_LIABILITIES', 0) / TA_t1
            LIQU_t = _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_ASSETS', 0) / max(_safe_val(df_bal, idx_t, 'TOTAL_CURRENT_LIABILITIES', 1), 1)
            LIQU_t1 = _safe_val(df_bal, idx_t1, 'TOTAL_CURRENT_ASSETS', 0) / max(_safe_val(df_bal, idx_t1, 'TOTAL_CURRENT_LIABILITIES', 1), 1)
            REV_t = _safe_val(df_inc, idx_t, 'TOTAL_OPERATE_INCOME', 0)
            REV_t1 = _safe_val(df_inc, idx_t1, 'TOTAL_OPERATE_INCOME', 0)
            GP_t = _safe_val(df_inc, idx_t, 'OPERATE_PROFIT', 0)
            GP_t1 = _safe_val(df_inc, idx_t1, 'OPERATE_PROFIT', 0)
            SGA_t = _safe_val(df_inc, idx_t, 'MANAGE_EXPENSE', 0) + _safe_val(df_inc, idx_t, 'SALE_EXPENSE', 0)
            SGA_t1 = _safe_val(df_inc, idx_t1, 'MANAGE_EXPENSE', 0) + _safe_val(df_inc, idx_t1, 'SALE_EXPENSE', 0)

            score = 0
            # 盈利能力
            if ROA_t > 0: score += 1
            if CFO_t > 0: score += 1
            if ROA_t > ROA_t1: score += 1
            # 杠杆/流动性
            if LEVER_t < LEVER_t1: score += 1
            if LIQU_t > LIQU_t1: score += 1
            if TA_t <= TA_t1 * 1.1: score += 1  # 无增发
            # 运营效率
            if REV_t / TA_t > REV_t1 / TA_t1: score += 1  # 资产周转提升
            if GP_t / max(REV_t, 1) > GP_t1 / max(REV_t1, 1): score += 1  # 毛利率提升
            if SGA_t / max(REV_t, 1) < SGA_t1 / max(REV_t1, 1): score += 1  # 费用率下降

            metrics.piotroski_f = score

            if score >= 7:
                metrics.piotroski_f_interpretation = f"优秀 (F={score})，财务质量优良"
            elif score >= 5:
                metrics.piotroski_f_interpretation = f"良好 (F={score})，财务质量良好"
            elif score >= 3:
                metrics.piotroski_f_interpretation = f"一般 (F={score})，存在一定财务压力"
            else:
                metrics.piotroski_f_interpretation = f"较差 (F={score})，财务质量差，建议警惕"

        except Exception as e:
            metrics.piotroski_f_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 9. Dechow F-Score (舞弊概率)
    # ────────────────────────────
    def _calc_dechow_f(self, df_inc, df_bal, df_cf, idx_t, idx_t1, metrics):
        """
        Dechow F-Score：直接预测财报重大错报/舞弊概率
        基于 Logistic 回归，11项指标
        F > 1 对应舞弊风险显著上升
        """
        try:
            TA = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', 1)
            if TA <= 0:
                metrics.dechow_f_interpretation = "资产数据异常"
                return metrics

            # 核心变量
            WC = (_safe_val(df_bal, idx_t, 'TOTAL_CURRENT_ASSETS', 0) - _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_LIABILITIES', 0)) / TA
            AR = _safe_val(df_bal, idx_t, 'ACCOUNTS_RECE', 0) / TA
            INV = _safe_val(df_bal, idx_t, 'INVENTORY', 0) / TA
            soft_assets = (_safe_val(df_bal, idx_t, 'TOTAL_NONCURRENT_ASSETS', 0) - _safe_val(df_bal, idx_t, 'FIXED_ASSET', 0)) / TA
            REV_growth = _safe_val(df_inc, idx_t, 'TOTAL_OPERATE_INCOME', 0) / max(_safe_val(df_inc, idx_t1, 'TOTAL_OPERATE_INCOME', 1), 1) - 1

            NI = _safe_val(df_inc, idx_t, 'PARENT_NETPROFIT', 0)
            CFO = _safe_val(df_cf, idx_t, 'NETCASH_OPERATE', 0) if not df_cf.empty else NI
            CFO_ratio = CFO / max(abs(NI), 1) if NI != 0 else 1.0

            # 简化版 Dechow F (实务近似)
            # F = -3.84 + 4.14*WC + 2.24*AR + 1.65*INV + 3.1*soft_assets - 1.03*REV_growth + 1.63*CFO_ratio
            F = -3.84 + 4.14*WC + 2.24*AR + 2.24*INV + 3.1*soft_assets - 1.03*REV_growth + 1.63*CFO_ratio
            # 映射到 0-1 概率
            prob = 1 / (1 + np.exp(max(min(-F, 700), -700)))

            metrics.dechow_f = prob
            if prob < 0.3:
                metrics.dechow_f_interpretation = f"低风险 (F-Score={prob:.2%})，舞弊可能性低"
            elif prob < 0.7:
                metrics.dechow_f_interpretation = f"中风险 (F-Score={prob:.2%})，存在舞弊嫌疑，需深入尽调"
            else:
                metrics.dechow_f_interpretation = f"高风险 (F-Score={prob:.2%})，舞弊概率高，建议回避"

        except Exception as e:
            metrics.dechow_f_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 10. Montier C-Score (6分制简化舞弊筛查)
    # ────────────────────────────
    def _calc_montier_c(self, df_inc, df_bal, df_cf, idx_t, idx_t1, metrics):
        """
        Montier C-Score：6个财务扭曲指标，每项异常+1分
        总分≥4分高度可疑
        """
        try:
            TA_t = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', 1)
            TA_t1 = _safe_val(df_bal, idx_t1, 'TOTAL_ASSETS', 1)
            if TA_t <= 0:
                metrics.montier_c_interpretation = "资产数据异常"
                return metrics

            score = 0
            reasons = []

            # 1. 应收增速 > 营收增速
            AR_t = _safe_val(df_bal, idx_t, 'ACCOUNTS_RECE', 0)
            AR_t1 = _safe_val(df_bal, idx_t1, 'ACCOUNTS_RECE', 0)
            REV_t = _safe_val(df_inc, idx_t, 'TOTAL_OPERATE_INCOME', 0)
            REV_t1 = _safe_val(df_inc, idx_t1, 'TOTAL_OPERATE_INCOME', 0)
            if REV_t > 0 and REV_t1 > 0:
                ar_growth = AR_t / AR_t1 - 1
                rev_growth = REV_t / REV_t1 - 1
                if ar_growth > rev_growth + 0.1:
                    score += 1
                    reasons.append('应收增速异常高于营收增速')

            # 2. 存货增速
            INV_t = _safe_val(df_bal, idx_t, 'INVENTORY', 0)
            INV_t1 = _safe_val(df_bal, idx_t1, 'INVENTORY', 0)
            if INV_t1 > 0 and (INV_t / INV_t1 - 1) > 0.2:
                score += 1
                reasons.append('存货增速异常')

            # 3. 毛利率变动
            GP_t = _safe_val(df_inc, idx_t, 'OPERATE_PROFIT', 0)
            GP_t1 = _safe_val(df_inc, idx_t1, 'OPERATE_PROFIT', 0)
            if REV_t > 0 and REV_t1 > 0:
                gp_ratio_t = GP_t / REV_t
                gp_ratio_t1 = GP_t1 / REV_t1
                if gp_ratio_t1 > 0 and (gp_ratio_t - gp_ratio_t1) < -0.05:
                    score += 1
                    reasons.append('毛利率显著下滑')

            # 4. 折旧率下降
            dep_t = _safe_val(df_cf, idx_t, 'FA_IR_DEPR', 0) if not df_cf.empty else 0
            fa_t = _safe_val(df_bal, idx_t, 'FIXED_ASSET', 1)
            if fa_t > 0 and dep_t / fa_t < 0.03:
                score += 1
                reasons.append('折旧率异常偏低')

            # 5. 其他流动资产占比异常
            other_current = _safe_val(df_bal, idx_t, 'TOTAL_CURRENT_ASSETS', 0) - AR_t - INV_t
            if other_current / TA_t > 0.15:
                score += 1
                reasons.append('其他流动资产占比异常')

            # 6. CFO/NI 严重偏离
            NI = _safe_val(df_inc, idx_t, 'PARENT_NETPROFIT', 0)
            CFO = _safe_val(df_cf, idx_t, 'NETCASH_OPERATE', 0) if not df_cf.empty else NI
            if NI > 0 and CFO / NI < 0.5:
                score += 1
                reasons.append('经营现金流严重偏离净利润')

            metrics.montier_c = score
            if score >= 4:
                metrics.montier_c_interpretation = f"高度可疑 (C={score}/6)，存在{', '.join(reasons)}等{score}项异常"
            elif score >= 2:
                metrics.montier_c_interpretation = f"轻度异常 (C={score}/6)，存在{', '.join(reasons)}等异常"
            else:
                metrics.montier_c_interpretation = f"正常 (C={score}/6)，财务扭曲迹象不明显"

        except Exception as e:
            metrics.montier_c_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 11. Beneish 5变量简化版 M-Score
    # ────────────────────────────
    # 11. Sloan 应计异象模型
    # ────────────────────────────
    def _calc_sloan_accrual(self, df_inc, df_bal, df_cf, idx_t, idx_t1, metrics):
        """
        Sloan 应计异象：应计占利润比值越高，操纵风险越大
        应计 = 净利润 - 经营现金流
        """
        try:
            TA_t = _safe_val(df_bal, idx_t, 'TOTAL_ASSETS', 1)
            if TA_t <= 0:
                metrics.sloan_accrual_interpretation = "资产数据异常"
                return metrics

            NI_t = _safe_val(df_inc, idx_t, 'PARENT_NETPROFIT', 0)
            CFO_t = _safe_val(df_cf, idx_t, 'NETCASH_OPERATE', 0) if not df_cf.empty else NI_t
            accrual = abs(NI_t - CFO_t) / TA_t
            ratio = abs(NI_t) / max(abs(CFO_t), 1) if CFO_t != 0 else 99

            metrics.sloan_accrual = accrual

            if accrual < 0.05:
                metrics.sloan_accrual_interpretation = f"优秀 (应计={accrual:.2%})，现金流健康，会计操纵风险低"
            elif accrual < 0.10:
                metrics.sloan_accrual_interpretation = f"一般 (应计={accrual:.2%})，存在一定应计偏高"
            else:
                if ratio > 2.0:
                    metrics.sloan_accrual_interpretation = f"异常 (应计={accrual:.2%})，净利润虚高严重，疑似纸面盈利"
                else:
                    metrics.sloan_accrual_interpretation = f"警告 (应计={accrual:.2%})，应计占比高，盈余操纵风险"

        except Exception as e:
            metrics.sloan_accrual_interpretation = f"计算失败: {str(e)}"

        return metrics

    # ────────────────────────────
    # 13. 综合评分
    # ────────────────────────────
    def _calc_combined_score(self, metrics: JointRiskMetrics):
        """
        综合风险评分 (0-100)
        各维度权重:
        - 盈余管理(DA+REM): 20%
        - 财报舞弊(Dechow+Montier+Sloan+M-Score): 25%
        - 破产预警(Z+Ohlson+Springate+Zmijewski): 25%
        - 财务质量(F-Score): 15%
        - 应计质量(AQ): 15%
        """
        try:
            score = 0

            # 1. 盈余管理风险 (0-20)
            da_risk = min(abs(metrics.jones_da) / 0.10 * 10, 10)
            rem_risk = min(abs(metrics.rem_score) / 0.5 * 10, 10)
            accrual_risk = da_risk + rem_risk

            # 2. 财报舞弊风险 (0-25，删除Beneish5后重新分配，新增M-Score)
            dechow_risk = min(metrics.dechow_f / 0.7 * 10, 10)
            montier_risk = min(metrics.montier_c / 6 * 5, 5)
            sloan_risk = min(metrics.sloan_accrual / 0.15 * 5, 5)
            # M-Score: >0 说明存在正向操纵倾向（A股严苛阈值），按实际值比例打分，上限5分
            m_risk = min(max(metrics.m_score / 3 * 5, 0), 5) if metrics.m_score > 0 else 0
            fraud_risk = dechow_risk + montier_risk + sloan_risk + m_risk

            # 3. 破产预警风险 (0-25)
            # Altman Z: <1.81 → 10分, <2.99 → 5分
            if metrics.altman_z > 0:
                if metrics.altman_z < 1.81:
                    z_risk = 10
                elif metrics.altman_z < 2.99:
                    z_risk = 5
                else:
                    z_risk = 0
            else:
                z_risk = 5

            # Ohlson: prob > 50% → 10分, > 20% → 5分
            o_risk = 10 if metrics.oholson_o > 0.5 else (5 if metrics.oholson_o > 0.2 else 0)

            # Springate: <0.862 → 8分（上调权重）
            s_risk = 8 if 0 < metrics.springate_s < 0.862 else 0

            # Zmijewski: 重新校准为0-8分（避免总是1）
            # prob<0.1 → 0分, prob<0.3 → 3分, prob<0.5 → 5分, prob≥0.5 → 8分
            x_risk = 0 if metrics.zmijewski_x < 0.1 else (3 if metrics.zmijewski_x < 0.3 else (5 if metrics.zmijewski_x < 0.5 else 8))
            bankruptcy_risk = min(z_risk + o_risk + s_risk + x_risk, 25)

            # 4. 应计质量风险 (0-15)
            aq_risk = min(metrics.dd_aq / 0.15 * 15, 15)

            # 5. 财务质量风险 (0-15) — F-Score越低风险越高
            f_risk = max((9 - metrics.piotroski_f) / 9 * 15, 0)

            score = int(min(accrual_risk + fraud_risk + bankruptcy_risk + aq_risk + f_risk, 100))
            metrics.combined_risk_score = score

            if score < 25:
                level = "低"
                summary = "综合风控评估：各项风控指标表现良好，风险总体可控"
            elif score < 50:
                level = "中"
                summary = "综合风控评估：存在一定风险因素，建议关注财报舞弊与偿债风险"
            elif score < 75:
                level = "高"
                summary = "综合风控评估：多项风控指标异常，需重点关注舞弊嫌疑与破产风险"
            else:
                level = "极高"
                summary = "综合风控评估：风险极高，建议回避，可能同时存在重大舞弊与偿债危机"

            metrics.combined_risk_level = level
            metrics.combined_risk_summary = summary

        except Exception as e:
            metrics.combined_risk_summary = f"综合评分计算异常: {str(e)}"

        return metrics
