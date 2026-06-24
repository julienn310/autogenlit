"""PDF年报风险分析Agent - 财务风险管理专家"""

from typing import Dict, List, Optional, Any
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.minimax_client import MiniMaxClient

logger = logging.getLogger(__name__)


# 系统提示词 - 财务风险管理专家（精简版）
SYSTEM_PROMPT = """你是一位资深的财务风险管理专家，20年从业经验，专注于A股上市公司债务风险分析。

## 你的任务
分析上市公司年报文本，输出专业的财务风险评估报告。

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

### 4. 风险预警
- 对外担保是否存在风险
- 或有负债是否过大
- 关联交易是否有利益输送嫌疑
- 应收账款/存货是否异常

## 行业对标参考
分析时参考以下标准：
- 银行、建筑、地产：资产负债率>70%为高风险
- 制造业：资产负债率>60%为高风险
- 科技、消费：资产负债率>50%为高风险
- 流动比率：>1.5为健康，<1为预警
- 速动比率：>1为健康，<0.8为预警

## 输出要求（重要）
1. 直接输出分析内容，**不要使用Markdown格式**
2. 每项数据判断要给出行业参考值
3. 关键数据要标注【第X页】来源
4. 语言简洁专业，不说废话
5. 最后给出风险评级：低/中/高/极高

## 输出结构
一、核心债务数据（二三十字概括）
二、偿债能力评估（列出关键指标及行业对比）
三、风险点列表（每个风险点附上原文标注）
四、综合风险评级及理由"""




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