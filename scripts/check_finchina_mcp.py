"""
财汇 MCP 连通性诊断脚本
========================
用法:
    python scripts/check_finchina_mcp.py            # 用 .env 里的 key
    python scripts/check_finchina_mcp.py 688825     # 指定股票代码

依次检测:
  1. API key 是否配置(来源: .env / 环境变量 / st.secrets)
  2. MCP tools/list 是否通
  3. 6 个子工具是否都能返回数据
不会打印 key 本身。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MCP_URL = "https://mcp.finchina.com/finchina-data-mcp-server/mcp"
TIMEOUT = 30


def load_key() -> tuple[str, str]:
    """返回 (key, 来源说明)"""
    # 1) .env
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("CAIHUI_MCP_API_KEY="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v, ".env"
    # 2) 环境变量
    v = os.environ.get("CAIHUI_MCP_API_KEY", "").strip()
    if v:
        return v, "os.environ"
    # 3) Streamlit secrets
    try:
        import streamlit as st
        if "CAIHUI_MCP_API_KEY" in st.secrets:
            v = str(st.secrets["CAIHUI_MCP_API_KEY"]).strip()
            if v:
                return v, "st.secrets"
    except Exception:
        pass
    return "", "未配置"


def call(key: str, tool: str, args: dict, req_id: int = 1) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "x-api-key": key,
    }
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {"name": "execute_tool",
                   "arguments": {"tool_name": tool, "arguments": args}},
    }
    resp = requests.post(MCP_URL, headers=headers, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    text = resp.text.strip()
    if text.startswith("data:"):
        for line in reversed(text.splitlines()):
            if line.startswith("data:"):
                text = line[5:].strip()
                break
    return json.loads(text)


def main() -> int:
    code = sys.argv[1] if len(sys.argv) > 1 else "688825"

    key, source = load_key()
    print("=" * 66)
    print(f"API key: {'已配置' if key else '未配置'}  (来源: {source}, 长度 {len(key)})")
    if not key:
        print("  -> 无法继续。请在 .env 里配置 CAIHUI_MCP_API_KEY 变量(值为 sk 开头的密钥)")
        print("     云端请在 Streamlit Cloud -> Settings -> Secrets 配置同名变量。")
        print("=" * 66)
        return 1

    # 1) tools/list
    print("\n[1] 握手 tools/list ...")
    try:
        r = requests.post(
            MCP_URL,
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "x-api-key": key},
            json={"jsonrpc": "2.0", "id": 0, "method": "tools/list", "params": {}},
            timeout=TIMEOUT,
        )
        print(f"    HTTP {r.status_code}")
        if r.status_code == 401:
            print("    -> 401: key 无效 / 已过期 / 未授权")
            return 1
        r.raise_for_status()
    except Exception as e:
        print(f"    EXC {type(e).__name__}: {e}")
        return 1

    # 2) 6 个子工具
    subs = [
        ("资金流向",   "get_stock_capital_flow",           True),
        ("融资融券",   "get_stock_margin_trading_details", True),
        ("大宗交易",   "get_stock_block_trades",           True),
        ("股东增减持", "get_shareholders_trading_details", False),
        ("高管增减持", "get_executive_trading_details",    True),
        ("股票回购",   "get_stock_repurchase_details",     True),
    ]
    print(f"\n[2] 子工具逐个测试 (股票 {code}) ...")
    ok = 0
    for i, (label, tool, use_limit) in enumerate(subs):
        args = {"target_stock": [code]}
        if use_limit:
            args["limit"] = 5
        try:
            obj = call(key, tool, args, req_id=i + 1)
            if "error" in obj:
                print(f"    [FAIL] {label:8s} {tool}")
                print(f"           JSON-RPC error: {obj['error']}")
                continue
            content = obj.get("result", {}).get("content", [])
            if not content:
                print(f"    [FAIL] {label:8s} 空 content: {obj.get('result')}")
                continue
            inner = json.loads(content[0].get("text", "{}"))
            stt = inner.get("status", {})
            sc = stt.get("code")
            if sc not in (0, 1):
                print(f"    [FAIL] {label:8s} 业务错误 code={sc} {stt.get('message')}")
                continue
            recs = (inner.get("data") or {}).get("records") or {}
            head = recs.get("headInfo") or []
            rows = recs.get("data") or []
            print(f"    [ OK ] {label:8s} {len(head)} 字段 / {len(rows)} 行")
            ok += 1
        except Exception as e:
            print(f"    [FAIL] {label:8s} {type(e).__name__}: {e}")

    print("\n" + "=" * 66)
    print(f"结果: {ok}/{len(subs)} 个子工具可用")
    print("=" * 66)
    return 0 if ok == len(subs) else 1


if __name__ == "__main__":
    sys.exit(main())
