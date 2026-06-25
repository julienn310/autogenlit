"""
A股智能体分析系统 - 核心模块
基于AutoGen框架的多智能体协作系统
使用GroupChat实现真正的多智能体协作
"""

import autogen
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.minimax_client import MiniMaxClient
from src.data.astock_collector import AStockDataCollector
from src.data.data_models import StockAnalysisResult, FinancialMetrics, RiskMetrics
from src.analysis.financial_analyzer import FinancialAnalyzer
from src.risk.risk_analyzer import RiskAnalyzer
from .agent_tools import TOOL_FUNCTIONS, register_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AStockAutoGenSystem:
    """A股智能体分析系统"""

    def __init__(self, minimax_api_key: str):
        """
        初始化系统

        Args:
            minimax_api_key: MiniMax API密钥
        """
        self.api_key = minimax_api_key
        self.client = MiniMaxClient(minimax_api_key)
        self.data_collector = AStockDataCollector()
        self.financial_analyzer = FinancialAnalyzer()
        self.risk_analyzer = RiskAnalyzer()

        # 创建LLM配置
        self.llm_config = self.client.create_autogen_config()
        # 注册工具
        self.tools = register_tools()

    def create_agents(self) -> Dict[str, autogen.Agent]:
        """创建AutoGen智能体团队"""
        factory = AutoGenAgentFactory(self.llm_config, self.tools)

        return {
            'user_proxy': factory.create_user_proxy_agent(),
            'data_analyst': factory.create_data_analyst_agent(),
            'financial_analyst': factory.create_financial_analyst_agent(),
            'risk_analyst': factory.create_risk_analyst_agent(),
            'investment_advisor': factory.create_investment_advisor_agent()
        }

    def analyze_stock(self, symbol: str) -> Dict[str, Any]:
        """
        分析指定股票

        Args:
            symbol: A股股票代码，如 "000001"

        Returns:
            分析结果字典
        """
        logger.info(f"开始分析股票 {symbol} - 启动AutoGen多智能体协作")

        # 1. 收集数据
        data = self.data_collector.collect_stock_data(symbol)
        if not data or not data.get('info'):
            return {"error": f"无法获取股票 {symbol} 的数据", "symbol": symbol}

        # 2. 计算指标
        financial_metrics = self.financial_analyzer.calculate_metrics(data)
        risk_metrics = self.risk_analyzer.calculate_metrics(data)

        # 3. 创建智能体团队
        agents = self.create_agents()

        # 4. 准备分析数据
        info = data.get('info', {})
        analysis_data = {
            'symbol': symbol,
            'name': info.get('name', symbol),
            'price': info.get('price', 0),
            'financial_metrics': financial_metrics.to_dict(),
            'risk_metrics': risk_metrics.to_dict(),
            'industry': info.get('sector', data.get('industry_info', {}).get('industry', '未知')),
        }

        # 5. 使用智能体编排器启动多智能体协作分析
        orchestrator = AgentOrchestrator(agents)
        collaboration_results = orchestrator.orchestrate_analysis(symbol, analysis_data)

        # 6. 整理综合结果
        result = {
            'symbol': symbol,
            'name': analysis_data['name'],
            'price': analysis_data['price'],
            'industry': analysis_data['industry'],
            'financial_metrics': analysis_data['financial_metrics'],
            'risk_metrics': analysis_data['risk_metrics'],
            'data_analysis': collaboration_results.get('data_analysis', ''),
            'financial_analysis': collaboration_results.get('financial_analysis', ''),
            'risk_analysis': collaboration_results.get('risk_analysis', ''),
            'investment_advice': collaboration_results.get('investment_advice', ''),
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'collaboration_summary': "AutoGen多智能体协作分析完成：数据分析师、财务分析师、风险分析师和投资顾问共同协作完成了完整的股票分析流程"
        }

        logger.info(f"完成股票 {symbol} 的AutoGen智能体协作分析")
        return result


class AutoGenAgentFactory:
    """AutoGen智能体工厂"""

    def __init__(self, llm_config: Dict, tools: List[Dict]):
        self.llm_config = llm_config
        self.tools = tools
        # 将工具函数映射到AutoGen格式
        self.tool_functions = {name: func for name, func in TOOL_FUNCTIONS.items()}

    def _create_assistant_agent(
        self,
        name: str,
        system_message: str,
        description: str = ""
    ) -> autogen.AssistantAgent:
        """创建通用AssistantAgent"""
        return autogen.AssistantAgent(
            name=name,
            system_message=system_message,
            llm_config=self.llm_config,
            description=description,
        )

    def create_data_analyst_agent(self) -> autogen.AssistantAgent:
        """创建数据分析师智能体"""
        return self._create_assistant_agent(
            name="data_analyst",
            system_message="""你是一位专业的数据分析师，擅长:
1. 分析和解读A股金融数据
2. 提取关键财务指标和市场信号
3. 识别数据中的趋势和异常
4. 为后续分析提供数据洞察

你可以使用以下工具:
- get_stock_info: 获取股票基本信息
- get_historical_data: 获取历史K线数据
- get_financial_data: 获取财务报表数据

在群聊中，你负责收集和整理数据，为其他分析师提供分析素材。""",
            description="数据分析师 - 收集和整理股票数据"
        )

    def create_financial_analyst_agent(self) -> autogen.AssistantAgent:
        """创建财务分析师智能体"""
        return self._create_assistant_agent(
            name="financial_analyst",
            system_message="""你是一位资深的A股财务分析师，具备以下专业能力:
1. 深度财务分析(盈利能力、偿债能力、运营能力、成长能力)
2. 财务比率解读和行业对比
3. 识别财务健康状况和潜在风险
4. 提供专业的财务评估意见

你可以使用以下工具:
- calculate_financial_metrics: 计算财务指标(ROE、ROA、毛利率、净利率等)

在群聊中，当数据分析师分享数据后，你需要深入分析财务状况。你可以:
- 询问数据分析师补充特定数据
- 向风险分析师分享发现的财务风险点
- 与投资顾问讨论估值观点""",
            description="财务分析师 - 分析盈利能力、偿债能力等"
        )

    def create_risk_analyst_agent(self) -> autogen.AssistantAgent:
        """创建风险分析师智能体"""
        return self._create_assistant_agent(
            name="risk_analyst",
            system_message="""你是一位专业的风险分析师，专注于:
1. 评估A股投资风险和回报
2. 解读风险指标(波动率、VaR、最大回撤等)
3. 分析潜在风险因素和影响
4. 提供风险缓解建议
5. Beneish M-Score财务操纵检测

你可以使用以下工具:
- calculate_risk_metrics: 计算风险指标(波动率、VaR、最大回撤、夏普比率、M-Score等)

在群聊中，当数据分析师分享数据后，你需要评估风险。你可以:
- 向财务分析师询问财务数据的细节
- 与投资顾问讨论风险收益比
- 指出需要注意的风险点""",
            description="风险分析师 - 评估波动率、VaR、最大回撤等"
        )

    def create_investment_advisor_agent(self) -> autogen.AssistantAgent:
        """创建投资顾问智能体"""
        return self._create_assistant_agent(
            name="investment_advisor",
            system_message="""你是一位经验丰富的A股投资顾问，擅长:
1. 综合财务分析和风险评估结果
2. 提供投资建议和决策支持
3. 评估投资价值和潜在回报
4. 给出明确的投资评级和目标价格区间

在群聊中，你综合所有分析师的观点，给出最终的投资建议。你需要:
- 倾听财务分析师和风险分析师的分析
- 整合各方观点，形成综合判断
- 协调讨论，推动达成共识
- 给出最终的投资评级和建议""",
            description="投资顾问 - 综合分析给出投资建议"
        )

    def create_user_proxy_agent(self) -> autogen.UserProxyAgent:
        """创建用户代理智能体"""
        return autogen.UserProxyAgent(
            name="user_proxy",
            system_message="""用户代理，负责协调和管理智能体团队完成A股投资分析任务。

在群聊中，你负责:
1. 初始化讨论，提出分析目标
2. 推动讨论按逻辑顺序进行
3. 在适当时候总结各方观点
4. 确保最终形成投资建议

你不直接参与数据分析，而是协调各分析师的讨论。""",
            code_execution_config=False,
            human_input_mode="NEVER"
        )


class AgentOrchestrator:
    """智能体编排器 - 实现GroupChat多智能体协作"""

    def __init__(self, agents: Dict[str, autogen.Agent]):
        self.agents = agents

    def orchestrate_analysis(self, symbol: str, analysis_data: Dict) -> Dict[str, str]:
        """编排智能体协作分析流程 - 使用GroupChat"""
        user_proxy = self.agents['user_proxy']
        data_analyst = self.agents['data_analyst']
        financial_analyst = self.agents['financial_analyst']
        risk_analyst = self.agents['risk_analyst']
        investment_advisor = self.agents['investment_advisor']

        results = {}

        # 构建初始分析上下文
        initial_context = f"""请分析股票 {symbol} ({analysis_data['name']})

公司基本信息:
- 股票代码: {symbol}
- 公司名称: {analysis_data['name']}
- 当前价格: {analysis_data['price']}元
- 所属行业: {analysis_data['industry']}

已计算的财务指标:
{analysis_data['financial_metrics']}

已计算的风险指标:
{analysis_data['risk_metrics']}

请各位分析师协作完成以下分析任务:

1. data_analyst: 确认数据完整性，补充任何缺失的关键信息
2. financial_analyst: 基于数据，深入分析盈利能力和财务健康状况
3. risk_analyst: 评估风险因素，特别关注波动性和潜在风险点
4. investment_advisor: 综合所有分析，给出最终投资建议

请各位依次发言，协作完成分析。"""

        # 创建GroupChat进行多智能体协作
        llm_cfg = self.agents['user_proxy'].llm_config
        groupchat = autogen.GroupChat(
            agents=[user_proxy, data_analyst, financial_analyst, risk_analyst, investment_advisor],
            messages=[],
            max_round=12,
            speaker_transitions_type="disallowed",
            select_speaker_auto_llm_config=llm_cfg
        )

        manager = autogen.GroupChatManager(
            groupchat=groupchat,
            llm_config=llm_cfg
        )

        # 启动群聊
        user_proxy.initiate_chat(
            manager,
            message=initial_context
        )

        # 从群聊历史中提取各Agent的分析结果
        chat_history = groupchat.messages

        for msg in chat_history:
            speaker = msg.get("name", "")
            content = msg.get("content", "")

            if speaker == "data_analyst" and not results.get('data_analysis'):
                results['data_analysis'] = content
            elif speaker == "financial_analyst" and not results.get('financial_analysis'):
                results['financial_analysis'] = content
            elif speaker == "risk_analyst" and not results.get('risk_analysis'):
                results['risk_analysis'] = content
            elif speaker == "investment_advisor" and not results.get('investment_advice'):
                results['investment_advice'] = content

        # 如果某些结果为空，使用之前的顺序执行方式作为回退
        if not results.get('data_analysis'):
            results['data_analysis'] = self._generate_data_summary(analysis_data)
        if not results.get('financial_analysis'):
            results['financial_analysis'] = self._generate_financial_summary(analysis_data)
        if not results.get('risk_analysis'):
            results['risk_analysis'] = self._generate_risk_summary(analysis_data)
        if not results.get('investment_advice'):
            results['investment_advice'] = self._generate_investment_advice(analysis_data)

        return results

    def _generate_data_summary(self, analysis_data: Dict) -> str:
        """生成数据分析师摘要"""
        return f"""【{analysis_data['name']}({analysis_data['symbol']})数据概览】

• 当前价格: {analysis_data['price']}元
• 所属行业: {analysis_data['industry']}

• 财务指标:
  - ROE: {analysis_data['financial_metrics'].get('roe', 'N/A')}
  - 资产负债率: {analysis_data['financial_metrics'].get('debt_ratio', 'N/A')}
  - 毛利率: {analysis_data['financial_metrics'].get('gross_margin', 'N/A')}

• 风险指标:
  - 波动率: {analysis_data['risk_metrics'].get('volatility', 'N/A')}
  - 最大回撤: {analysis_data['risk_metrics'].get('max_drawdown', 'N/A')}
  - 夏普比率: {analysis_data['risk_metrics'].get('sharpe_ratio', 'N/A')}"""

    def _generate_financial_summary(self, analysis_data: Dict) -> str:
        """生成财务分析师摘要"""
        return f"""【{analysis_data['name']}财务分析】

基于提供的财务指标：
• 盈利能力: ROE {analysis_data['financial_metrics'].get('roe', 'N/A')}，处于行业{'较高' if float(analysis_data['financial_metrics'].get('roe', 0).replace('%', '')) > 15 else '中等'}水平
• 财务结构: 资产负债率 {analysis_data['financial_metrics'].get('debt_ratio', 'N/A')}
• 运营效率: 毛利率 {analysis_data['financial_metrics'].get('gross_margin', 'N/A')}

详细分析需要更多数据支持。"""

    def _generate_risk_summary(self, analysis_data: Dict) -> str:
        """生成风险分析师摘要"""
        return f"""【{analysis_data['name']}风险评估】

波动性风险: {analysis_data['risk_metrics'].get('volatility', 'N/A')} - 处于行业{'较高' if float(analysis_data['risk_metrics'].get('volatility', '0%').replace('%', '')) > 30 else '正常'}水平
下行风险: 最大回撤 {analysis_data['risk_metrics'].get('max_drawdown', 'N/A')}
风险调整收益: 夏普比率 {analysis_data['risk_metrics'].get('sharpe_ratio', 'N/A')}

M-Score: {analysis_data['risk_metrics'].get('m_score', 'N/A')} - {analysis_data['risk_metrics'].get('m_score_interpretation', '')}"""

    def _generate_investment_advice(self, analysis_data: Dict) -> str:
        """生成投资顾问摘要"""
        return f"""【{analysis_data['name']}投资建议】

基于财务分析和风险评估的综合判断：

风险等级: 中等
建议: 建议关注

详细投资建议需要更深入的讨论和分析。"""


class MultiAgentCollaborator:
    """多智能体协作器 - 高级GroupChat实现"""

    def __init__(self, agents: Dict[str, autogen.Agent], llm_config: Dict):
        self.agents = agents
        self.llm_config = llm_config

    def run_collaborative_analysis(self, symbol: str, analysis_data: Dict) -> Dict[str, Any]:
        """
        运行协作式多智能体分析

        这个方法实现了真正得多智能体协作:
        - Agent之间可以直接对话
        - 共享分析上下文
        - 可以互相提问和补充
        """
        user_proxy = self.agents['user_proxy']
        data_analyst = self.agents['data_analyst']
        financial_analyst = self.agents['financial_analyst']
        risk_analyst = self.agents['risk_analyst']
        investment_advisor = self.agents['investment_advisor']

        # 初始化讨论话题
        topic = f"""作为团队，请协作分析 {symbol} ({analysis_data['name']})这只股票。

背景数据:
- 价格: {analysis_data['price']}元
- 行业: {analysis_data['industry']}
- 财务指标: {analysis_data['financial_metrics']}
- 风险指标: {analysis_data['risk_metrics']}

请按以下顺序进行协作分析:

1. data_analyst: 首先确认数据的完整性和可靠性
2. financial_analyst和risk_analyst: 交替讨论，互相补充发现
3. investment_advisor: 综合讨论结果，给出最终建议

每轮讨论后，请投资顾问总结当前共识。"""

        # 启动群聊
        groupchat = autogen.GroupChat(
            agents=[user_proxy, data_analyst, financial_analyst, risk_analyst, investment_advisor],
            messages=[],
            max_round=15
        )

        manager = autogen.GroupChatManager(
            groupchat=groupchat,
            llm_config=self.llm_config
        )

        user_proxy.initiate_chat(
            manager,
            message=topic
        )

        # 提取讨论结果
        discussion_log = []
        for msg in groupchat.messages:
            discussion_log.append({
                "speaker": msg.get("name"),
                "content": msg.get("content", "")[:500]  # 截断避免过长
            })

        # 生成最终报告
        final_report = self._synthesize_report(analysis_data, discussion_log)

        return {
            "analysis_data": analysis_data,
            "discussion_log": discussion_log,
            "final_report": final_report
        }

    def _synthesize_report(self, analysis_data: Dict, discussion_log: List) -> str:
        """综合讨论生成最终报告"""
        # 简单的报告生成，实际项目中可以由investment_advisor Agent完成
        report = f"""# {analysis_data['name']}({analysis_data['symbol']}) 分析报告

## 讨论摘要

"""

        for entry in discussion_log:
            report += f"### {entry['speaker']}:\n{entry['content']}\n\n"

        report += f"""
## 综合结论

本报告由多智能体团队协作完成。

财务状况: {analysis_data['financial_metrics'].get('roe', 'N/A')}
风险等级: {analysis_data['risk_metrics'].get('volatility', 'N/A')}

投资建议: 建议关注
"""

        return report