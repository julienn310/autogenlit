# A股智能体分析系统

基于 AI 多智能体协作的 A 股基本面分析平台，覆盖行情、舆情、财务、风险、公告等维度。

## 功能模块

| 模块 | 说明 |
|---|---|
| **仪表板** | 全球指数实时行情、新闻舆情汇总、KOL观点 |
| **财务分析** | 成长/盈利/偿债能力指标，量化评分 |
| **风险分析** | 破产预警、流动性风险、信用评级 |
| **PDF年报分析** | 年度财务数据AI风险评估 |
| **公告解读** | 近90天公告抓取 + AI意图预判 + 深度解读 |
| **多智能体协作** | AutoGen框架多Agent协作分析 |

## 快速部署（Docker）

```bash
# 构建镜像
docker build -t astock-research .

# 运行（默认端口8501）
docker run -p 8501:8501 astock-research
```

## 手动部署

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `MINIMAX_API_KEY` | MiniMax API Key（用于AI分析）| 需配置 |

## 数据来源

- 行情：腾讯 qt.gtimg.cn（实时）
- 财务：akshare（东方财富/新浪/WSJ RSS）
- 公告：东方财富 np-anotice API
- 新闻：东方财富快讯、新浪财经、WSJ RSS

## 项目结构

```
├── streamlit_app.py          # 主应用
├── src/
│   ├── agents/              # AI智能体
│   │   ├── announcement_agent.py  # 公告解读Agent
│   │   └── pdf_risk_agent.py     # 年报风险Agent
│   ├── cache/               # 共享缓存（SQLite）
│   ├── data/                # 数据采集
│   │   ├── announcement_collector.py  # 公告采集
│   │   ├── market_collector.py       # 行情采集
│   │   └── news_collector.py         # 新闻采集
│   └── risk/                # 风险模型
└── requirements.txt
```

## 部署平台推荐

- **Render.com**：直接连接 GitHub 仓库，Dockerfile 自动检测
- **Railway**：支持 Dockerfile 部署
- **Streamlit Cloud**：需 `packages.txt` + `streamlit_app.py`
