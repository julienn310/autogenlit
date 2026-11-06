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
import ast
import json
import logging
from typing import Dict, List, Optional, Tuple
import requests
import pandas as pd

logger = logging.getLogger(__name__)

MCP_URL = "https://mcp.finchina.com/finchina-data-mcp-server/mcp"
TIMEOUT = 30  # seconds


class FinchinaMCPError(Exception):
    """MCP 调用或业务异常"""


class FinchinaToolNotFound(FinchinaMCPError):
    """子工具在服务端不存在(被改名或下线)"""


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    """按优先级读取 key:st.secrets (云端) > os.environ (本机)"""
    # 1) 优先:Streamlit Secrets(云端推荐)
    try:
        import streamlit as _st
        if hasattr(_st, "secrets") and "CAIHUI_MCP_API_KEY" in _st.secrets:
            v = str(_st.secrets["CAIHUI_MCP_API_KEY"]).strip()
            if v:
                return v
    except Exception:
        pass
    # 2) Fallback:环境变量(本机 export)
    key = os.environ.get("CAIHUI_MCP_API_KEY", "").strip()
    if not key:
        raise FinchinaMCPError(
            "CAIHUI_MCP_API_KEY 未设置。请在 Streamlit Cloud 的 Settings → Secrets 配置,"
            "或在本机 export CAIHUI_MCP_API_KEY=... 后重启 Streamlit。"
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
        err = status.get("error") or {}
        detail = str(err.get("message") or "")
        # 服务端「子工具不在工具清单」= 工具被改名/下线,交由上层换名重试
        if "未找到子工具" in detail or "工具不存在" in detail:
            raise FinchinaToolNotFound(detail or str(status))
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

# 这些子工具不支持 limit 参数(传了会 PROTOCOL_ERROR)
_NO_LIMIT_TOOLS = {"get_shareholders_trading_details"}

# 财汇历史上把一批 get_stock_xxx / get_shareholders_xxx / get_executive_xxx
# 改名为 search_stock_xxx / search_shareholders_xxx / search_executive_xxx。
# 保留旧名作为首选 + 新名兜底,服务端任一存在即可工作。
_RENAME_PREFIXES = (
    ("get_stock_", "search_stock_"),
    ("get_shareholders_", "search_shareholders_"),
    ("get_executive_", "search_executive_"),
)


def _tool_candidates(subtool: str) -> list:
    """返回该子工具的候选名(按优先级)"""
    cands = [subtool]
    for old, new in _RENAME_PREFIXES:
        if subtool.startswith(old):
            cands.append(new + subtool[len(old):])
            break
    return cands


def _fetch(subtool: str, stock_code: str, limit: int, request_id: int) -> pd.DataFrame:
    code = _normalize_code(stock_code)
    if not code:
        raise FinchinaMCPError("股票代码不能为空")

    last_err: Optional[Exception] = None
    for cand in _tool_candidates(subtool):
        # 不同子工具的参数约束不一样:
        #   - 旧版 get_shareholders_trading_details 不支持 limit (会 PROTOCOL_ERROR)
        #   - 其他子工具都支持 target_stock + limit
        args = {"target_stock": [code]}
        if cand not in _NO_LIMIT_TOOLS:
            args["limit"] = int(limit)
        try:
            raw = _call_mcp(
                "execute_tool",
                {"tool_name": cand, "arguments": args},
                request_id=request_id,
            )
            return _parse_records(raw)
        except FinchinaToolNotFound as e:
            # 该名字在服务端不存在 → 换下一个候选名
            last_err = e
            continue
    raise last_err or FinchinaMCPError(f"子工具不可用: {subtool}")


def fetch_capital_flow(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """主力/超大单/大单/中单/小单 资金流向"""
    return _fetch("get_stock_capital_flow", stock_code, limit, request_id=2)


def fetch_margin_trading(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """融资融券明细"""
    return _fetch("get_stock_margin_trading_details", stock_code, limit, request_id=3)


def fetch_block_trades(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """大宗交易明细"""
    return _fetch("search_stock_block_trades", stock_code, limit, request_id=4)


def fetch_shareholders_trading(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """重要股东二级市场增减持"""
    return _fetch("search_shareholders_trading_details", stock_code, limit, request_id=5)


def fetch_executive_trading(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """董监高增减持明细"""
    return _fetch("search_executive_trading_details", stock_code, limit, request_id=6)


def fetch_repurchase(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """股票回购明细"""
    return _fetch("get_stock_repurchase_details", stock_code, limit, request_id=7)


def fetch_dragon_tiger_board(stock_code: str, limit: int = 20) -> pd.DataFrame:
    """龙虎榜上榜记录(含买入/卖出前五营业部明细)

    对应 MCP 子工具 search_stock_dragon_tiger_board
    """
    return _fetch("search_stock_dragon_tiger_board", stock_code, limit, request_id=8)


# ---------------------------------------------------------------------------
# 龙虎榜营业部字段解析
# ---------------------------------------------------------------------------

def _parse_seat_list(raw) -> List[Tuple[str, str, float]]:
    """解析龙虎榜营业部字段

    MCP 返回的是字符串形态的嵌套列表,例如:
        "[['1', '中信证券股份有限公司上海分公司', 26637.46], ['2', '...', 21600.0]]"

    Returns
    -------
    list[tuple[str, str, float]]: (排名, 营业部名称, 金额[万元])
    """
    if raw is None:
        return []
    s = str(raw).strip()
    if not s or s in ("[]", "nan", "None"):
        return []

    data = None
    for loader in (ast.literal_eval, json.loads):
        try:
            data = loader(s)
            break
        except Exception:
            continue
    if not isinstance(data, list):
        return []

    out: List[Tuple[str, str, float]] = []
    for item in data:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            try:
                out.append((str(item[0]).strip(), str(item[1]).strip(), float(item[2])))
            except (TypeError, ValueError):
                continue
    return out


def _format_seats(seats: List[Tuple[str, str, float]], top_n: int = 5) -> str:
    """把营业部列表格式化成多行文本"""
    if not seats:
        return ""
    return "\n".join(
        f"{rank}. {name} ({amt:,.0f}万)" for rank, name, amt in seats[:top_n]
    )


def parse_dragon_tiger_seats(df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """给龙虎榜 df 追加两列可读文本:
        buy_seat_text  — 买入前五营业部
        sell_seat_text — 卖出前五营业部
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    buy_txt, sell_txt = [], []
    for _, row in out.iterrows():
        buy_txt.append(_format_seats(_parse_seat_list(row.get("buy_seat")), top_n))
        sell_txt.append(_format_seats(_parse_seat_list(row.get("sell_seat")), top_n))
    out["buy_seat_text"] = buy_txt
    out["sell_seat_text"] = sell_txt
    return out


def aggregate_seat_flow(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """按营业部聚合龙虎榜买卖金额,返回净买入排行

    Returns
    -------
    pd.DataFrame: columns = [seat, buy, sell, net]  金额单位: 万元
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["seat", "buy", "sell", "net"])

    agg: Dict[str, Dict[str, float]] = {}
    for _, row in df.iterrows():
        for field, side in (("buy_seat", "buy"), ("sell_seat", "sell")):
            for _rank, name, amt in _parse_seat_list(row.get(field)):
                slot = agg.setdefault(name, {"buy": 0.0, "sell": 0.0})
                slot[side] += amt

    rows = []
    for name, slot in agg.items():
        rows.append({
            "seat": name,
            "buy": slot["buy"],
            "sell": slot["sell"],
            "net": slot["buy"] - slot["sell"],
        })
    out = pd.DataFrame(rows, columns=["seat", "buy", "sell", "net"])
    if out.empty:
        return out
    out = out.sort_values("net", ascending=False).reset_index(drop=True)
    return out.head(top_n)


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


def fetch_company_suspected_relationships(company_name: str, limit: int = 30) -> pd.DataFrame:
    """企业疑似关系 — 算法推断(共同股东/共同高管/共同电话/共同地址/控股链等)"""
    return _fetch_company("get_company_suspected_relationships", company_name, limit, request_id=19)
