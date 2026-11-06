"""
用 caihui_mcp_metadata 查二级子工具元数据,搜索龙虎榜相关能力。
用法: python scripts/explore_mcp_subtools.py [关键词]
"""
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.check_finchina_mcp import load_key  # noqa: E402

MCP_URL = "https://mcp.finchina.com/finchina-data-mcp-server/mcp"


def rpc(key, method, params, req_id=1):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "x-api-key": key,
    }
    resp = requests.post(MCP_URL, headers=headers,
                         json={"jsonrpc": "2.0", "id": req_id, "method": method, "params": params},
                         timeout=40)
    resp.raise_for_status()
    text = resp.text.strip()
    if text.startswith("data:"):
        for line in reversed(text.splitlines()):
            if line.startswith("data:"):
                text = line[5:].strip()
                break
    return json.loads(text)


def main():
    key, src = load_key()
    if not key:
        print("no key")
        return 1

    # 先看 metadata 工具自己的 schema
    obj = rpc(key, "tools/list", {}, 1)
    for t in obj.get("result", {}).get("tools", []):
        if t.get("name") == "caihui_mcp_metadata":
            print("=== caihui_mcp_metadata schema ===")
            print(json.dumps(t.get("inputSchema", {}), ensure_ascii=False, indent=2)[:1500])

    kw = sys.argv[1] if len(sys.argv) > 1 else "龙虎榜"
    print(f"\n=== metadata query={kw} ===")
    for cat in ("params_metadata", "tool_info", "all"):
        try:
            r = rpc(key, "tools/call", {
                "name": "caihui_mcp_metadata",
                "arguments": {"query": kw, "category": cat},
            }, 2)
            content = r.get("result", {}).get("content", [])
            txt = content[0].get("text", "") if content else json.dumps(r, ensure_ascii=False)
            print(f"\n--- category={cat} ---")
            print(txt[:2000])
            if txt.strip():
                break
        except Exception as e:
            print(f"category={cat} EXC {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
