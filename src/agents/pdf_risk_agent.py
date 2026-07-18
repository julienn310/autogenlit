"""PDF年报风险分析Agent - 财务风险管理专家"""

from typing import Dict, List, Optional, Any
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.minimax_client import MiniMaxClient

logger = logging.getLogger(__name__)


# 系统提示词 - 财务风险管理专家（增强版）
SYSTEM_PROMPT = """你是一位资深的财务风险管理专家，20年从业经验，专注于A股上市公司债务风险分析。

## 你的任务
分析上市公司年报财务数据，输出专业的财务风险评估报告。

## 分析维度（按重要性排序）

### 1. 债务结构（核心）
- 短期借款、长期借款、应付债券、租赁负债金额及占比
- 有息负债vs无息负债结构
- 债务期限结构（1年内到期/1年以上）

### 2. 偿债能力
- 货币资金对短期债务的覆盖倍数
- 流动比率、速动比率行业对比
- 现金流对债务的保障程度

### 3. 杠杆水平
- 资产负债率行业排名（同行业央企/国企/民企对比）
- 权益乘数分析

### 4. 管理层讨论与分析（MD&A）
- 营业收入增长驱动因素（量/价/新业务）
- 毛利率变化原因（原材料成本/产品结构/定价能力）
- 费用率管控效果（销售费用率/管理费用率/研发费用率）
- 现金流质量（经营现金流/净利润比率，近年趋势）
- 管理层对下一年经营计划的表述（是否保守/激进）

### 5. 产业链上下游分析
- 上游原材料供应商集中度（第一大供应商占比）
- 下游客户集中度（第一大客户占比，前5名客户占比）
- 上下游议价能力对比（应收账款周转天数/应付账款周转天数）
- 产业链地位：是龙头还是夹心层？
- 供应商/客户过度集中的风险提示

### 6. 风险预警
- 对外担保是否存在风险（担保总额/净资产比例）
- 或有负债是否过大
- 关联交易是否有利益输送嫌疑
- 应收账款/存货是否异常
- 应收账款账龄结构（是否逾期）
- 存货周转趋势（是否积压）

## 行业对标参考
分析时参考以下标准：
- 银行、建筑、地产：资产负债率>70%为高风险
- 制造业：资产负债率>60%为高风险
- 科技、消费：资产负债率>50%为高风险
- 流动比率：>1.5为健康，<1为预警
- 速动比率：>1为健康，<0.8为预警
- 供应商集中度：CR1>30%为高风险
- 客户集中度：CR1>25%为高风险

## 输出要求（重要）
1. 直接输出分析内容，**不要使用Markdown格式**
2. 每项数据判断要给出行业参考值
3. 语言简洁专业，不说废话
4. 最后给出风险评级：低/中/高/极高

## 输出结构
一、核心债务数据（二三十字概括）
二、偿债能力评估（列出关键指标及行业对比）
三、管理层讨论与分析（重点关注增长质量、费用管控、现金流）
四、产业链上下游分析（供应商/客户集中度、议价能力）
五、风险点列表（每个风险点附上数据来源）
六、综合风险评级及理由"""




class PDFRiskAgent:
    """PDF年报风险分析Agent"""

    def __init__(self, api_key: str):
        self.client = MiniMaxClient(api_key)
        self.system_prompt = SYSTEM_PROMPT

    def analyze(self, pdf_text: str, company_name: str = "") -> str:
        """
        分析PDF年报文本 - 不分段，直接发送完整文本

        Args:
            pdf_text: 提取的PDF文本内容
            company_name: 公司名称（可选）

        Returns:
            风险分析报告
        """
        try:
            # 直接发送完整文本（MiniMax支持较长上下文）
            user_prompt = self._build_prompt(pdf_text, company_name)

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            logger.info(f"发送文本长度: {len(pdf_text)}")

            response = self.client.chat_completion(
                messages=messages,
                model="MiniMax-M2.7",
                temperature=0.1,
                max_tokens=8000
            )

            choices = response.get("choices")
            if not choices or not choices[0]:
                logger.warning(f"API返回无choices: {response}")
                return "分析失败: API返回异常"

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                logger.warning(f"API返回空content: {response}")
                return "分析失败: 收到的内容为空"

            logger.info(f"分析完成，结果长度: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"PDF风险分析失败: {e}")
            raise

    def analyze_financial_data(self, annual_data: dict, company_name: str = "") -> str:
        """
        分析akshare获取的年报财务数据（含附注信息）

        Args:
            annual_data: 包含indicator/profit/balance/cashflow/notes DataFrame的字典
            company_name: 公司名称

        Returns:
            风险分析报告
        """
        try:
            indicator = annual_data.get('indicator')
            profit = annual_data.get('profit')
            balance = annual_data.get('balance')
            cashflow = annual_data.get('cashflow')
            notes = annual_data.get('notes', {}) or {}

            # 取最新一期（第一行）
            def get_latest(df, year_col='REPORT_DATE'):
                if df is None or df.empty:
                    return {}
                # 尝试按日期排序取最新
                if year_col in df.columns:
                    df = df.sort_values(year_col, ascending=False)
                row = df.iloc[0] if not df.empty else {}
                return row.to_dict()

            ind = get_latest(indicator)
            prof = get_latest(profit)
            bal = get_latest(balance)
            cash = get_latest(cashflow)

            # 提取关键指标
            def fmt(val, is_pct=False):
                if val is None or (isinstance(val, float) and (val != val)):  # NaN
                    return "N/A"
                if is_pct:
                    try:
                        return f"{float(val):.2f}%"
                    except:
                        return "N/A"
                try:
                    v = float(val)
                    if abs(v) >= 1e8:
                        return f"{v/1e8:.2f}亿"
                    elif abs(v) >= 1e4:
                        return f"{v/1e4:.2f}万"
                    else:
                        return f"{v:.2f}"
                except:
                    return str(val)

            # 格式化财务数据为文本
            financial_text = self._format_financial_data_text(ind, prof, bal, cash, fmt)

            # 格式化附注信息（供应商/客户/关联交易）
            notes_text = self._format_notes_text(notes)

            user_prompt = f"""公司：{company_name or annual_data.get('name', '未知')}
以下是从东方财富获取的年报财务数据，请基于这些真实数据进行分析：

{financial_text}

{notes_text}

请仔细分析以上数据，输出专业的财务风险评估报告，包括：
1. 核心债务数据及偿债能力
2. 管理层讨论与分析（增长质量、费用管控、现金流）
3. 产业链上下游分析（供应商/客户集中度、议价能力）
4. 风险预警信号
5. 综合风险评级

直接输出分析内容，**不要使用Markdown格式**。"""

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]

            logger.info(f"发送年报数据，指标数: {len(ind)}, 附注: {'有' if notes_text != '（附注信息不可用）' else '无'}")

            response = self.client.chat_completion(
                messages=messages,
                model="MiniMax-M2.7",
                temperature=0.1,
                max_tokens=8000
            )

            choices = response.get("choices")
            if not choices or not choices[0]:
                return "年报数据分析失败: API返回异常"

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return "年报数据分析失败: 收到的内容为空"

            logger.info(f"年报数据分析完成，结果长度: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"年报数据分析失败: {e}")
            return f"年报数据分析异常：{e}"

    def _format_financial_data_text(self, ind: dict, prof: dict, bal: dict, cash: dict, fmt) -> str:
        """将财务数据字典格式化为易读的文本"""
        lines = []

        # 关键指标（来自财务指标表）
        lines.append("=== 财务指标 ===")
        key_metrics = {
            'ROEJQ': '净资产收益率(ROE)',
            'ROEKCJQ': '扣非ROE',
            'EPSJB': '每股收益(EPS)',
            'BPS': '每股净资产',
            'MGZBGJ': '每股资本公积',
            'XSMLL': '销售毛利率',
            'XSJLL': '销售净利率',
            'DEBT_RATIO': '资产负债率',
            'CURRENT_RATIO': '流动比率',
            'QUICK_RATIO': '速动比率',
            'OPRC_RATIO': '营业利润率',
            'GROSS_PROFIT_RATIO': '毛利率',
        }
        for key, label in key_metrics.items():
            val = ind.get(key, prof.get(key, bal.get(key)))
            lines.append(f"{label}: {fmt(val, is_pct=True)}")

        # 利润表关键数据
        lines.append("\n=== 利润表 ===")
        profit_keys = {
            'OPERATE_INCOME': '营业收入',
            'OPERATE_PROFIT': '营业利润',
            'TOTAL_PROFIT': '利润总额',
            'NETPROFIT': '净利润',
            'PARENT_NETPROFIT': '归母净利润',
        }
        for key, label in profit_keys.items():
            val = prof.get(key)
            if val is not None:
                lines.append(f"{label}: {fmt(val)}")

        # 资产负债表关键数据
        lines.append("\n=== 资产负债表 ===")
        balance_keys = {
            'TOTAL_ASSETS': '总资产',
            'TOTAL_LIABILITIES': '总负债',
            'TOTAL_EQUITY': '股东权益',
            'FIXED_ASSET': '固定资产',
            'INTANGIBLE_ASSET': '无形资产',
            'CURRENT_ASSETS': '流动资产',
            'CURRENT_LIAB': '流动负债',
            'LONG_TERM_BORROW': '长期借款',
            'SHORT_TERM_BORROW': '短期借款',
            'BOND_PAYABLE': '应付债券',
        }
        for key, label in balance_keys.items():
            val = bal.get(key)
            if val is not None:
                lines.append(f"{label}: {fmt(val)}")

        # 现金流量表关键数据
        lines.append("\n=== 现金流量表 ===")
        cashflow_keys = {
            'NETCASH_OPERATE': '经营活动现金流净额',
            'NETCASH_INVEST': '投资活动现金流净额',
            'NETCASH_FINANCE': '筹资活动现金流净额',
            'END_CCE': '期末现金及等价物',
        }
        for key, label in cashflow_keys.items():
            val = cash.get(key)
            if val is not None:
                lines.append(f"{label}: {fmt(val)}")

        return "\n".join(lines)

    def _format_notes_text(self, notes: dict) -> str:
        """将附注信息（供应商/客户/关联交易）格式化为易读的文本"""
        if not notes:
            return "（附注信息不可用）"

        lines = []

        # 主要供应商信息
        supplier_df = notes.get('supplier_info')
        if supplier_df is not None and not supplier_df.empty:
            lines.append("\n=== 主要供应商信息 ===")
            try:
                # 东方财富接口常见列名
                cols = supplier_df.columns.tolist()
                # 尝试找到供应商名称和采购占比列
                name_col = None
                ratio_col = None
                for col in cols:
                    col_lower = col.lower()
                    if 'name' in col_lower or 'supplier' in col_lower:
                        name_col = col
                    if 'ratio' in col_lower or 'percent' in col_lower or 'proportion' in col_lower or '占比' in col:
                        ratio_col = col

                if name_col and ratio_col:
                    for i, row in supplier_df.iterrows():
                        lines.append(f"供应商{i+1}: {row[name_col]} - 采购占比: {row[ratio_col]}")
                elif not supplier_df.empty:
                    # 通用：直接打印前5行
                    lines.append(supplier_df.head(5).to_string())
            except Exception as e:
                lines.append(f"（供应商数据解析异常：{e}）")
        else:
            lines.append("\n=== 主要供应商信息 ===（数据不可用）")

        # 主要客户信息
        customer_df = notes.get('customer_info')
        if customer_df is not None and not customer_df.empty:
            lines.append("\n=== 主要客户信息 ===")
            try:
                cols = customer_df.columns.tolist()
                name_col = None
                ratio_col = None
                for col in cols:
                    col_lower = col.lower()
                    if 'name' in col_lower or 'customer' in col_lower or '客户' in col:
                        name_col = col
                    if 'ratio' in col_lower or 'percent' in col_lower or 'proportion' in col_lower or '占比' in col:
                        ratio_col = col

                if name_col and ratio_col:
                    for i, row in customer_df.iterrows():
                        lines.append(f"客户{i+1}: {row[name_col]} - 销售占比: {row[ratio_col]}")
                elif not customer_df.empty:
                    lines.append(customer_df.head(5).to_string())
            except Exception as e:
                lines.append(f"（客户数据解析异常：{e}）")
        else:
            lines.append("\n=== 主要客户信息 ===（数据不可用）")

        # 关联交易摘要
        related_df = notes.get('related_party')
        if related_df is not None and not related_df.empty:
            lines.append("\n=== 关联交易摘要 ===")
            try:
                # 打印关联交易类型和金额汇总
                if 'TRANSACTION_TYPE' in related_df.columns or 'type' in related_df.columns.str.lower():
                    type_col = [c for c in related_df.columns if 'type' in c.lower() or '类型' in c][0]
                    amount_col = [c for c in related_df.columns if 'amount' in c.lower() or '金额' in c or 'ratio' in c.lower()]
                    amount_col = amount_col[0] if amount_col else None

                    summary = related_df.groupby(type_col).size()
                    lines.append(f"关联交易类型分布: {summary.to_dict()}")
                    if amount_col:
                        lines.append(f"关联交易金额（万元）:\n{related_df.groupby(type_col)[amount_col].sum()}")
                else:
                    lines.append(related_df.head(5).to_string())
            except Exception as e:
                lines.append(f"（关联交易数据解析异常：{e}）")

        return "\n".join(lines) if lines else "（附注信息不可用）"

    def _build_prompt(self, pdf_text: str, company_name: str = "") -> str:
        """
        构建分析提示词

        Args:
            pdf_text: PDF文本
            company_name: 公司名称

        Returns:
            提示词
        """
        company_prefix = f"公司：{company_name}\n" if company_name else ""
        return f"""{company_prefix}以下是年报文本，请仔细分析：

{pdf_text}

（注意：如果文本中未包含财务报表数据（如资产负债表、利润表），请明确指出数据不可用，不要编造数据。）"""