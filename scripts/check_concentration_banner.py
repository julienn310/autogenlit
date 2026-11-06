"""
用 Streamlit AppTest 做 headless 渲染验证:
检查仪表盘的「全市场成交额集中度」banner 与历史走势图是否正常显示。

用法: python scripts/check_concentration_banner.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest

at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=240)
at.run()
print("[1] 首屏渲染完成")

if at.exception:
    for e in at.exception:
        print("[EXC]", str(e)[:600])
    sys.exit(1)

# banner 是 markdown 里的 HTML,直接从所有 markdown 元素里找关键字
KEYS = ['全市场成交额集中度指标', 'Top 5%', '历史均值', '口径']
found = {}
for m in at.markdown:
    v = m.value or ''
    for k in KEYS:
        if k in v:
            found.setdefault(k, v)

for k in KEYS:
    print(f"[2] 关键字 '{k}': {'✔ 命中' if k in found else '✘ 未命中'}")

try:
    n_charts = len(at.get("plotly_chart"))
except Exception:
    n_charts = -1
print(f"[3] plotly 图表数: {n_charts}")

# 把命中的 markdown 摘出来看关键数字
for k, v in found.items():
    import re
    nums = re.findall(r'(\d+\.\d)%', v)
    print(f"    [{k}] 百分比数字: {nums[:6]}")

alerts = [('warning', a.value) for a in at.warning] + [('error', e.value) for e in at.error]
if alerts:
    print("[4] 告警/错误:")
    for kind, txt in alerts:
        print(f"    [{kind}] {(txt or '').replace(chr(10),' ')[:200]}")
else:
    print("[4] 无告警/错误")

ok = '全市场成交额集中度指标' in found and n_charts >= 1
print("\n[OK] 集中度 banner 与走势图正常" if ok else "\n[FAIL] 集中度指标未正常显示")
sys.exit(0 if ok else 1)
