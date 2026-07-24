"""A股智能体分析系统"""

__version__ = "0.1.0"

import sys
import os

print(f"[DEBUG src/__init__.py] __file__={__file__}", flush=True)
print(f"[DEBUG src/__init__.py] os.listdir src/={os.listdir(os.path.dirname(__file__) or '.')}", flush=True)
