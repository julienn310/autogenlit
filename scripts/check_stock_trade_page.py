"""
用 Streamlit AppTest 做 headless 渲染验证:
把导航切到「个股交易数据」,检查 6 个 tab 是否成功拿到数据。

用法: python scripts/check_stock_trade_page.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest

at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=180)
at.run()
print("[1] 首屏渲染完成")

# 切到「个股交易数据」
radio = None
for r in at.radio:
    if "导航" in (r.label or ""):
        radio = r
        break
if radio is None:
    print("[FAIL] 找不到导航 radio")
    sys.exit(1)

radio.set_value("个股交易数据").run()
print("[2] 已切到「个股交易数据」")

# 异常检查
if at.exception:
    for e in at.exception:
        print("[EXC]", str(e)[:400])
    sys.exit(1)

# 收集告警 / 错误
alerts = []
for a in at.warning:
    alerts.append(("warning", a.value))
for a in at.error:
    alerts.append(("error", a.value))
for a in at.info:
    alerts.append(("info", a.value))

print(f"\n[3] 页面元素: dataframe={len(at.dataframe)}  markdown={len(at.markdown)}")
print("[4] 告警/提示:")
if not alerts:
    print("    (无)")
for kind, txt in alerts:
    t = (txt or "").replace("\n", " ")
    print(f"    [{kind}] {t[:160]}")

# 数据表内容摘要
print("\n[5] 数据表:")
if not at.dataframe:
    print("    (没有 dataframe — 说明 6 个 tab 都没拿到数据)")
for i, el in enumerate(at.dataframe):
    try:
        df = el.value
        print(f"    table#{i}: shape={df.shape}")
        print(f"       cols: {list(df.columns)[:8]}")
        if len(df):
            print(f"       head: {df.head(2).to_dict('records')[:1]}")
    except Exception as e:
        print(f"    table#{i}: <读取失败 {type(e).__name__}: {e}>")

# 判定
fails = [t for k, t in alerts if k in ("warning", "error") and ("获取失败" in (t or "") or "未设置" in (t or ""))]
if fails:
    print(f"\n[FAIL] {len(fails)} 个数据源失败:")
    for f in fails:
        print("   -", f[:200])
    sys.exit(1)
print("\n[OK] 「个股交易数据」页面全部数据源正常")
