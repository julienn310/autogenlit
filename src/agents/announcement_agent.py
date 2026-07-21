"""公告解读智能体 - 分析公司公告意图"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.minimax_client import MiniMaxClient
from src.data.announcement_collector import (
    fetch_announcements,
    build_announcement_context,
    fetch_content_for_ann,
)

SYSTEM_PROMPT = """你是一位资深的A股上市公司公告解读专家，擅长从公告中推断公司真实意图和潜在影响。

## 你的任务
输入一只股票近期的公告列表，你要做的是：
1. 判断每类公告对公司的真实含义
2. 识别潜在的积极/消极信号
3. 推断管理层的真实意图
4. 给出投资参考建议

## 公告类型参考
- **高管变动**：更换管理层可能带来战略调整
- **业绩公告**：营收/净利润变化反映经营状况
- **分红配送**：现金分红说明现金流充裕；高送转可能是在做市值管理
- **回购/增持**：股东或公司回购股票通常意味着认为股价被低估
- **减持**：股东减持需警惕，但也要看具体原因
- **关联交易**：需重点关注是否涉及利益输送
- **监管/问询**：问询函说明监管层关注，处罚则是重大利空
- **股权变动**：控制权变更属于重大事件
- **重大合同**：大额订单/中标是经营利好

## 分析框架
对每类公告从以下角度分析：
1. **表面信息**：公告说了什么
2. **潜在意图**：公司为什么要发这个公告
3. **对谁有利**：对大股东/管理层/中小股东/债主的影响
4. **风险提示**：需要警惕的地方
5. **投资参考**：短线/中线/长线影响

## 输出格式
请用以下格式输出：

【公告概览】
近N个月共N条公告，分类分布：XXX

【重要公告解读】
对每条重要公告按以下格式解读：

📌 [公告标题]（[日期] [类别]）
   → 表面信息：[一句话说明]
   → 潜在意图：[管理层可能的想法]
   → 影响对象：[对谁影响最大]
   → 风险/机会：[需警惕的点 或 积极信号]
   → 投资参考：[短线/中线/长线建议]

【综合研判】
从公告整体判断：
- 公司近期战略重心：XXX
- 管理层信心：XXX（增持/减持/回购情况）
- 主要风险点：XXX
- 综合评级：积极 / 中性 / 谨慎 / 警示

直接输出分析内容，不要使用Markdown格式。"""


class AnnouncementAgent:
    """公告解读智能体"""

    def __init__(self, api_key: str):
        self.client = MiniMaxClient(api_key)
        self.system_prompt = SYSTEM_PROMPT

    def analyze(self, symbol: str, company_name: str = "", days: int = 90) -> str:
        """
        解读股票公告意图

        Args:
            symbol: 股票代码，如 "000001"
            company_name: 公司名称（可选）
            days: 回溯天数，默认90天

        Returns:
            公告解读报告
        """
        try:
            # 1. 获取公告
            announcements = fetch_announcements(symbol, days=days)
            if not announcements:
                return f"近{days}天无公告记录，请检查股票代码是否正确。"

            # 2. 构建上下文
            ann_context = build_announcement_context(announcements, include_content=False)

            # 3. 构建prompt
            stock_info = f"{company_name or symbol}（{symbol}）"
            user_prompt = f"""请分析以下{stock_info}的近期公告：

{ann_context}

请仔细阅读以上公告列表，从专业角度解读公司近期动向和管理层意图。

重点关注：
1. 各类公告的潜在含义
2. 高管变动的战略信号
3. 回购/增持体现的股东态度
4. 关联交易是否合理
5. 监管问询的严重程度
6. 业绩变化的背后原因

请给出综合研判。"""

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = self.client.chat_completion(
                messages=messages,
                model="MiniMax-M2.7",
                temperature=0.2,
                max_tokens=6000
            )

            choices = response.get("choices")
            if not choices or not choices[0]:
                return "公告解读失败: API返回异常"

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return "公告解读失败: 收到的内容为空"

            return content

        except Exception as e:
            return f"公告解读异常：{e}"

    def analyze_single(self, announcement: dict, company_name: str = "") -> str:
        """
        深度解读单条公告

        Args:
            announcement: 公告字典，包含 title, date, category, url, source
            company_name: 公司名称

        Returns:
            单条公告的深度解读
        """
        try:
            # 尝试获取公告正文
            content = fetch_content_for_ann(announcement)
            content_section = f"\n\n公告正文摘录：\n{content[:500]}" if content else "\n\n（公告正文无法获取，仅基于标题分析）"

            user_prompt = f"""请深度解读以下{company_name or '某公司'}的公告：

标题：{announcement.get('title', '')}
日期：{announcement.get('date', '')}
类别：{announcement.get('category', '')}
来源：{announcement.get('source', '')}{content_section}

请分析：
1. 这条公告的核心内容是什么？
2. 公司发布这条公告的真实意图可能是什么？
3. 对不同利益方（股东/债权人/管理层/中小投资者）的影响？
4. 需要重点关注的风险或机会点？
5. 短线和中线的投资参考？

直接输出分析内容，不要使用Markdown格式。"""

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = self.client.chat_completion(
                messages=messages,
                model="MiniMax-M2.7",
                temperature=0.2,
                max_tokens=3000
            )

            choices = response.get("choices")
            if not choices or not choices[0]:
                return "单条公告解读失败: API返回异常"

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return "单条公告解读失败: 收到的内容为空"

            return content

        except Exception as e:
            return f"单条公告解读异常：{e}"
