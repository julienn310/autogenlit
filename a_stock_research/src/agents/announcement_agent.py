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

SYSTEM_PROMPT = """你是一位资深的A股上市公司公告解读专家，风格犀利、一针见血，擅长从公告字里行间推断公司真实意图。

## 输出格式要求

**每条公告必须先概括主要内容，再做解读，两者缺一不可。**

### 格式模板：

📌 [公告标题]（[日期]）
【内容概括】用2-3句话概括这份公告说了什么（50字以内），让读者不看原文也能了解公告核心信息。
【一针见血】
   → 潜台词：[管理层实际想表达/隐瞒什么]
   → 谁受益：[大股东/管理层/中小股东/债权人]
   → 危险信号 或 利好信号（二选一，理由要说清楚）
   → 核心结论：[一句话说明这件事对公司的本质影响]

### 综合研判（在分析完全部公告后输出）

【管理层信心】
增持/回购次数与减持次数的比例，说明什么？
高管团队是否稳定？大股东是否有实质性支持动作？

【近期最大风险点】
按严重程度列出，最多3条，每条要有数据支撑。

【综合评级】
积极 / 中性 / 谨慎 / 警示
理由：不超过30字

## 重点公告类型的解读要点

### 高管变动
- 新任何职、分管什么业务 → 战略方向可能转向
- 独立董事批量辞职 → 可能有分歧，内部有问题
- CFO/财务总监换人 → 财报可能有猫腻，或在准备融资

### 回购/增持
- 回购价格上限 vs 当前股价 → 底气足不足一看便知
- 大股东增持 vs 员工持股计划 → 谁在真金白银看好

### 关联交易
- 向大股东收购资产 → 是否溢价、是否输送利益
- 对联营公司担保/借款 → 风险是否可控

### 监管问询
- 问询"会计处理变更" → 可能在调节利润
- 问询"业绩波动" → 年报可能有水分
- 多次问询同一问题 → 可能是惯犯，风险极高

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
            ann_context = build_announcement_context(announcements, include_content=True)

            # 3. 构建prompt
            stock_info = f"{company_name or symbol}（{symbol}）"
            user_prompt = f"""请对以下{stock_info}的近期公告进行犀利的一针见血的解读：

{ann_context}

要求：
1. 不要简单复述公告内容，要说出公告背后的潜台词
2. 重点识别：谁在这次公告中获益、谁受损
3. 关联分析：把同一时间段不同公告串起来看，往往能发现真相
4. 最关键的问题：如果你是大股东，你为什么要发这个公告？

重点关注高管变动、回购增持、关联交易、监管问询、股权变动这五类公告。

给出一针见血的分析结论。"""

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
                # 返回详细错误信息
                base_resp = response.get("base_resp", {})
                status_msg = base_resp.get("status_msg", "") or str(response)
                return f"公告解读失败: {status_msg[:200]}"

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
            content_section = f"\n\n公告正文摘录：\n{content[:5000]}" if content else "\n\n（公告正文无法获取，仅基于标题分析）"

            user_prompt = f"""请对以下{company_name or '某公司'}的公告进行一针见血的深度解读：

标题：{announcement.get('title', '')}
日期：{announcement.get('date', '')}
类别：{announcement.get('category', '')}
来源：{announcement.get('source', '')}{content_section}

请按以下格式输出，**先概括内容，再做解读**：

【内容概括】用2-3句话概括公告说了什么，让读者不看原文也能了解核心信息。

【一针见血】
→ 潜台词：管理层实际想表达/隐瞒什么
→ 谁受益：谁从这次公告中获益/受损
→ 危险信号 或 利好信号（二选一，附理由）
→ 核心结论：这件事对公司的本质影响

直接输出，不要使用Markdown格式。"""

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
                base_resp = response.get("base_resp", {})
                status_msg = base_resp.get("status_msg", "") or str(response)
                return f"单条公告解读失败: {status_msg[:200]}"

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return "单条公告解读失败: 收到的内容为空"

            return content

        except Exception as e:
            return f"单条公告解读异常：{e}"
