"""
探索财汇 MCP 的工具清单,找出与「龙虎榜」相关的子工具。
用法: python scripts/explore_mcp_tools.py [关键词...]
"""
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.check_finchina_mcp import load_key  # noqa: E402

MCP_URL = "https://mcp.finchina.com/finchina-data-mcp-server/mcp"


def rpc(key: str, method: str, params: dict, req_id: int = 1) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "x-api-key": key,
    }
    resp = requests.post(
        MCP_URL, headers=headers,
        json={"jsonrpc": "2.0", "id": req_id, "method": method, "params": params},
        timeout=40,
    )
    resp.raise_for_status()
    text = resp.text.strip()
    if text.startswith("data:"):
        for line in reversed(text.splitlines()):
            if line.startswith("data:"):
                text = line[5:].strip()
                break
    return json.loads(text)


def main() -> int:
    key, source = load_key()
    if not key:
        print("no key (source=%s)" % source)
        return 1

    obj = rpc(key, "tools/list", {}, 1)
    tools = obj.get("result", {}).get("tools", [])
    print("=== 顶层工具 %d 个 ===" % len(tools))
    for t in tools:
        name = t.get("name", "")
        desc = (t.get("description") or "").replace("\n", " ")[:90]
        print("  %-38s %s" % (name, desc))

    kws = sys.argv[1:] or ["龙虎", "榜", "lhb", "dragon", "abnormal", "limit_up"]
    print("\n=== 按关键词过滤 ===")
    hit = False
    for t in tools:
        blob = (t.get("name", "") + " " + (t.get("description") or "") + " " +
                json.dumps(t.get("inputSchema", {}), ensure_ascii=False)).lower()
        for k in kws:
            if k.lower() in blob:
                print("\n[MATCH %s] %s" % (k, t.get("name")))
                print("  desc: %s" % (t.get("description") or "")[:300])
                print("  schema: %s" % json.dumps(t.get("inputSchema", {}), ensure_ascii=False)[:400])
                hit = True
                break
    if not hit:
        print("  (顶层工具无匹配 —— 需用 caihui_mcp_metadata 查二级工具)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
