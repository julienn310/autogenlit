"""
财汇MCP (finchina-data-mcp-server) 个股交易数据采集
====================================================
- 6 sub-tools under query_stock_trading_and_capital_flow
- API key: env var CAIHUI_MCP_API_KEY
- 股票代码: 6 位数字 (如 688825) 或带 sh/sz 前缀,自动剥离
- 不传 trade_date (中文乱码);仅传 target_stock + limit
- 端点: https://mcp.finchina.com/finchina-data-mcp-server/mcp (Streamable HTTP, JSON-RPC 2.0)
"""
import os
import json
import logging
from typing import Dict
import requests
import pandas as pd

logger = logging.getLogger(__name__)

MCP_URL = "https://mcp.finchina.com/finchina-data-mcp-server/mcp"
TIMEOUT = 30  # seconds


class FinchinaMCPError(Exception):
    """MCP 调用或业务异常"""


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    key = os.environ.get("CAIHUI_MCP_API_KEY", "").strip()
    if not key:
        raise FinchinaMCPError(
            "环境变量 CAIHUI_MCP_API_KEY 未设置。请 export 该变量后重启 Streamlit。"
        )
    return key


def _normalize_code(stock_code: str) -> str:
    """剥离 sh/sz 前缀与空白"""
    s = (stock_code or "").strip()
    if not s:
        return s
    low = s.lower()
    if low.startswith(("sh", "sz")) and len(s) > 2 and s[2:].isdigit():
        s = s[2:]
    return s


def _call_mcp(tool_name: str, arguments: Dict, request_id: int = 1) -> Dict:
    """JSON-RPC 2.0 调用;自动处理 SSE / JSON 两种响应格式"""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "x-api-key": _get_api_key(),
    }
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    resp = requests.post(MCP_URL, headers=headers, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    text = resp.text.strip()
    if text.startswith("data:"):  # SSE 帧
        for line in reversed(text.splitlines()):
            if line.startswith("data:"):
                text = line[5:].strip()
                break
    return json.loads(text)


def _parse_records(mcp_response: Dict) -> pd.DataFrame:
    """将 MCP 返回的 result.content[0].text 解析为 DataFrame"""
    result = mcp_response.get("result") or {}
    content = result.get("content") or []
    if not content:
        raise FinchinaMCPError("MCP 返回空 content")
    text_str = content[0].get("text", "")
    if not text_str:
        raise FinchinaMCPError("MCP 返回 content[0].text 为空")
    payload = json.loads(text_str)
    status = payload.get("status") or {}
    if status.get("code") not in (0, 1):  # 1 = 兼容处理后的成功
        raise FinchinaMCPError(f"MCP 业务错误: {status.get('message') or status}")
    data_obj = payload.get("data") or {}
    records = data_obj.get("records") or {}
    head = records.get("headInfo") or []
    rows = records.get("data") or []
    cols = [h.get("field", f"col{i}") for i, h in enumerate(head)]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows, columns=cols)
    df.attrs["head_info"] = [
        {"field": h.get("field"), "name": h.get("name"), "unit": h.get("unit")}
        for h in head
    ]
    return df


def _yi(val) -> str:
    """元 → 亿元显示 (用于金额列美化)"""
    try:
        return f"{float(val) / 1e8:.2f}亿"
    except (TypeError, ValueError):
        return str(val) if val is not None else "-"


# ---------------------------------------------------------------------------
# 公开 API - 6 个子工具
# ---------------------------------------------------------------------------

def _fetch(subtool: str, stock_code: str, limit: int, request_id: int) -> pd.DataFrame:
    code = _normalize_code(stock_code)
    if not code:
        raise FinchinaMCPError("股票代码不能为空")
    # 不同子工具的参数约束不一样:
    #   - get_shareholders_trading_details 不支持 limit (会 PROTOCOL_ERROR)
    #   - 其他子工具都支持 target_stock + limit
    args = {"target_stock": [code]}
    if subtool != "get_shareholders_trading_details":
        args["limit"] = int(limit)
    raw = _call_mcp(
        "execute_tool",
        {"tool_name": subtool, "arguments": args},
        request_id=request_id,
    )
    return _parse_records(raw)


def fetch_capital_flow(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """主力/超大单/大单/中单/小单 资金流向"""
    return _fetch("get_stock_capital_flow", stock_code, limit, request_id=2)


def fetch_margin_trading(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """融资融券明细"""
    return _fetch("get_stock_margin_trading_details", stock_code, limit, request_id=3)


def fetch_block_trades(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """大宗交易明细"""
    return _fetch("get_stock_block_trades", stock_code, limit, request_id=4)


def fetch_shareholders_trading(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """重要股东二级市场增减持"""
    return _fetch("get_shareholders_trading_details", stock_code, limit, request_id=5)


def fetch_executive_trading(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """董监高增减持明细"""
    return _fetch("get_executive_trading_details", stock_code, limit, request_id=6)


def fetch_repurchase(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """股票回购明细"""
    return _fetch("get_stock_repurchase_details", stock_code, limit, request_id=7)


# ---------------------------------------------------------------------------
# 公开 API - 企业关系查询 (单家公司向外扩展)
# ---------------------------------------------------------------------------

def _fetch_company(subtool: str, company_name: str, limit: int, request_id: int) -> pd.DataFrame:
    """单家公司关系查询的统一入口;company_name 必须是 list (MCP schema array<string>)"""
    if not company_name or not company_name.strip():
        raise FinchinaMCPError("公司名称不能为空")
    raw = _call_mcp(
        "execute_tool",
        {
            "tool_name": subtool,
            "arguments": {
                "target_company": [company_name.strip()],
                "limit": int(limit),
            },
        },
        request_id=request_id,
    )
    return _parse_records(raw)


def fetch_company_suppliers(company_name: str, limit: int = 30) -> pd.DataFrame:
    """公司供应商"""
    return _fetch_company("get_company_suppliers", company_name, limit, request_id=10)


def fetch_company_customers(company_name: str, limit: int = 30) -> pd.DataFrame:
    """公司客户"""
    return _fetch_company("get_company_customers", company_name, limit, request_id=11)


def fetch_company_tendering(company_name: str, limit: int = 30) -> pd.DataFrame:
    """公司招标记录"""
    return _fetch_company("get_company_tendering_details", company_name, limit, request_id=12)


def fetch_company_bidding(company_name: str, limit: int = 30) -> pd.DataFrame:
    """公司投标记录"""
    return _fetch_company("get_company_bidding_details", company_name, limit, request_id=13)


def fetch_company_investment_projects(company_name: str, limit: int = 30) -> pd.DataFrame:
    """公司对外投资项目"""
    return _fetch_company("get_company_investment_projects", company_name, limit, request_id=14)


def fetch_company_pe_vc(company_name: str, limit: int = 30) -> pd.DataFrame:
    """公司 PE/VC 融资"""
    return _fetch_company("get_company_pe_vc_details", company_name, limit, request_id=15)


def fetch_company_guarantee_events(company_name: str, limit: int = 30) -> pd.DataFrame:
    """公司担保事件(它担保了谁 / 谁担保了它)"""
    return _fetch_company("get_company_guarantee_events", company_name, limit, request_id=16)


def fetch_company_equity_pledge(company_name: str, limit: int = 30) -> pd.DataFrame:
    """公司股权出质"""
    return _fetch_company("get_company_equity_pledge_details", company_name, limit, request_id=17)


def fetch_company_receivable_financing(company_name: str, limit: int = 30) -> pd.DataFrame:
    """公司应收账款融资"""
    return _fetch_company("get_company_receivable_financing_details", company_name, limit, request_id=18)
