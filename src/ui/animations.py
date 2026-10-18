"""
UI 动画模块 — SVG + CSS,提升 Streamlit 页面颜值
====================================================
- 标题动态光标
- 加载动画(脉冲圆环)
- 数字滚动
- 骨架屏
- 卡片悬浮
- 背景渐变
"""
import streamlit as st


# ============================================================================
# 1. 标题动态光标
# ============================================================================

def animated_title(text: str, color: str = "#0d3b66", cursor_color: str = "#0d3b66") -> str:
    """标题 + 闪烁光标 ▎
    返回 HTML,直接 st.markdown(..., unsafe_allow_html=True)"""
    return f"""
<div style="display:inline-flex; align-items:baseline; gap:6px;
            font-size:1.8rem; font-weight:700; color:{color};">
  <span>{text}</span>
  <span class="blink-cursor" style="color:{cursor_color};
        animation: blink 1.1s steps(2, start) infinite;">▎</span>
</div>
<style>
  @keyframes blink {{
    to {{ visibility: hidden; }}
  }}
  .blink-cursor {{ font-weight: 400; }}
</style>
"""


# ============================================================================
# 2. 加载动画(脉冲圆环 / 跳动点 / 骨架)
# ============================================================================

def loading_pulse(label: str = "正在加载") -> str:
    """3 个圆环脉冲,适合短操作(<2s)，带扩撒光晕效果"""
    return f"""
<div style="display:flex; align-items:center; gap:14px; padding:18px 0;
            font-size:0.95rem; color:#666;">
  <svg width="60" height="24" viewBox="0 0 60 24">
    <!-- 左圆环 - 带扩散效果 -->
    <circle cx="12" cy="12" r="6" fill="none" stroke="#0d3b66" stroke-width="2" opacity="0.3">
      <animate attributeName="r" values="6;14;6" dur="1.4s" begin="0s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.3;0;0.3" dur="1.4s" begin="0s" repeatCount="indefinite"/>
    </circle>
    <circle cx="12" cy="12" r="4" fill="#0d3b66">
      <animate attributeName="opacity" values="1;0.3;1" dur="1.2s" begin="0s" repeatCount="indefinite"/>
      <animate attributeName="r" values="3;5;3" dur="1.2s" begin="0s" repeatCount="indefinite"/>
    </circle>
    <!-- 中圆环 - 带扩散效果 -->
    <circle cx="30" cy="12" r="6" fill="none" stroke="#667eea" stroke-width="2" opacity="0.3">
      <animate attributeName="r" values="6;14;6" dur="1.4s" begin="0.2s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.3;0;0.3" dur="1.4s" begin="0.2s" repeatCount="indefinite"/>
    </circle>
    <circle cx="30" cy="12" r="4" fill="#667eea">
      <animate attributeName="opacity" values="1;0.3;1" dur="1.2s" begin="0.4s" repeatCount="indefinite"/>
      <animate attributeName="r" values="3;5;3" dur="1.2s" begin="0.4s" repeatCount="indefinite"/>
    </circle>
    <!-- 右圆环 - 带扩散效果 -->
    <circle cx="48" cy="12" r="6" fill="none" stroke="#764ba2" stroke-width="2" opacity="0.3">
      <animate attributeName="r" values="6;14;6" dur="1.4s" begin="0.4s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.3;0;0.3" dur="1.4s" begin="0.4s" repeatCount="indefinite"/>
    </circle>
    <circle cx="48" cy="12" r="4" fill="#764ba2">
      <animate attributeName="opacity" values="1;0.3;1" dur="1.2s" begin="0.8s" repeatCount="indefinite"/>
      <animate attributeName="r" values="3;5;3" dur="1.2s" begin="0.8s" repeatCount="indefinite"/>
    </circle>
  </svg>
  <span>{label}<span class="dot-anim">…</span></span>
</div>
<style>
  .dot-anim {{
    display:inline-block;
    animation: dot-fade 1.4s steps(4, end) infinite;
    width: 1.2em;
    text-align: left;
  }}
  @keyframes dot-fade {{
    0%   {{ content: '';   }}
    25%  {{ content: '.';   }}
    50%  {{ content: '..';  }}
    75%  {{ content: '...'; }}
    100% {{ content: '';   }}
  }}
</style>
"""


def loading_orb(label: str = "AI 正在思考") -> str:
    """单个旋转光球 + 文字,适合中等操作(2-10s)，带多重光晕和粒子效果"""
    return f"""
<div style="display:flex; align-items:center; gap:16px; padding:24px;
            background:linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
            border-radius:10px; border:1px solid #e3e6ea;">
  <svg width="50" height="50" viewBox="0 0 50 50">
    <defs>
      <linearGradient id="orb-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%"  stop-color="#667eea"/>
        <stop offset="50%" stop-color="#764ba2"/>
        <stop offset="100%" stop-color="#0d3b66"/>
      </linearGradient>
      <filter id="orb-glow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="2" result="blur"/>
        <feMerge>
          <feMergeNode in="blur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    <!-- 外层扩散光环 -->
    <circle cx="25" cy="25" r="20" fill="none" stroke="#667eea" stroke-width="1" opacity="0.2">
      <animate attributeName="r" values="18;24;18" dur="2s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.2;0;0.2" dur="2s" repeatCount="indefinite"/>
    </circle>
    <!-- 旋转环1 -->
    <circle cx="25" cy="25" r="16" fill="none" stroke="url(#orb-grad)"
            stroke-width="2.5" stroke-linecap="round"
            stroke-dasharray="70 30" transform-origin="25 25" filter="url(#orb-glow)">
      <animateTransform attributeName="transform" type="rotate"
                        from="0 25 25" to="360 25 25" dur="1.5s"
                        repeatCount="indefinite"/>
    </circle>
    <!-- 旋转环2 (反向) -->
    <circle cx="25" cy="25" r="12" fill="none" stroke="#764ba2"
            stroke-width="2" stroke-linecap="round"
            stroke-dasharray="40 20" transform-origin="25 25" opacity="0.7">
      <animateTransform attributeName="transform" type="rotate"
                        from="360 25 25" to="0 25 25" dur="2s"
                        repeatCount="indefinite"/>
    </circle>
    <!-- 中心光球 -->
    <circle cx="25" cy="25" r="5" fill="url(#orb-grad)" filter="url(#orb-glow)">
      <animate attributeName="r" values="4;7;4" dur="1.3s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="1;0.6;1" dur="1.3s" repeatCount="indefinite"/>
    </circle>
    <!-- 粒子点 -->
    <circle cx="25" cy="5" r="1.5" fill="#667eea" opacity="0.8">
      <animate attributeName="opacity" values="0.8;0;0.8" dur="1.5s" begin="0s" repeatCount="indefinite"/>
    </circle>
    <circle cx="45" cy="25" r="1.5" fill="#764ba2" opacity="0.8">
      <animate attributeName="opacity" values="0.8;0;0.8" dur="1.5s" begin="0.5s" repeatCount="indefinite"/>
    </circle>
    <circle cx="25" cy="45" r="1.5" fill="#0d3b66" opacity="0.8">
      <animate attributeName="opacity" values="0.8;0;0.8" dur="1.5s" begin="1s" repeatCount="indefinite"/>
    </circle>
  </svg>
  <div>
    <div style="font-size:0.95rem; color:#2c3e50; font-weight:600;">{label}</div>
    <div style="font-size:0.8rem; color:#94a3b8; margin-top:2px;">
      预计几秒,请稍候…
    </div>
  </div>
</div>
"""


def loading_wave_bars(label: str = "正在处理") -> str:
    """5 个柱形波动,适合长操作(>5s)，带渐变和光泽效果"""
    return f"""
<div style="display:flex; align-items:center; gap:16px; padding:20px;
            background:linear-gradient(135deg, #f8f9fc 0%, #eef1f5 100%); border-radius:8px;">
  <svg width="60" height="40" viewBox="0 0 60 40">
    <defs>
      <linearGradient id="bar-grad-1" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#667eea"/>
        <stop offset="100%" stop-color="#764ba2"/>
      </linearGradient>
      <linearGradient id="bar-grad-2" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#0d3b66"/>
        <stop offset="100%" stop-color="#1f5f8b"/>
      </linearGradient>
      <filter id="bar-glow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation="1.5" result="blur"/>
        <feMerge>
          <feMergeNode in="blur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    <!-- 底部反射 -->
    <rect x="2"  y="32" width="6" height="3" fill="#667eea" rx="1" opacity="0.3">
      <animate attributeName="opacity" values="0.3;0.1;0.3" dur="0.9s" begin="0s" repeatCount="indefinite"/>
    </rect>
    <rect x="12" y="32" width="6" height="3" fill="#764ba2" rx="1" opacity="0.3">
      <animate attributeName="opacity" values="0.3;0.1;0.3" dur="0.9s" begin="0.15s" repeatCount="indefinite"/>
    </rect>
    <rect x="22" y="32" width="6" height="3" fill="#0d3b66" rx="1" opacity="0.3">
      <animate attributeName="opacity" values="0.3;0.1;0.3" dur="0.9s" begin="0.3s" repeatCount="indefinite"/>
    </rect>
    <rect x="32" y="32" width="6" height="3" fill="#1f5f8b" rx="1" opacity="0.3">
      <animate attributeName="opacity" values="0.3;0.1;0.3" dur="0.9s" begin="0.45s" repeatCount="indefinite"/>
    </rect>
    <rect x="42" y="32" width="6" height="3" fill="#5a8fb0" rx="1" opacity="0.3">
      <animate attributeName="opacity" values="0.3;0.1;0.3" dur="0.9s" begin="0.6s" repeatCount="indefinite"/>
    </rect>
    <!-- 主柱体 -->
    <rect x="2"  y="14" width="6" height="4" fill="url(#bar-grad-1)" rx="1" filter="url(#bar-glow)">
      <animate attributeName="height" values="4;20;4" dur="0.9s" begin="0s" repeatCount="indefinite"/>
      <animate attributeName="y"      values="14;6;14" dur="0.9s" begin="0s" repeatCount="indefinite"/>
    </rect>
    <rect x="12" y="14" width="6" height="4" fill="url(#bar-grad-2)" rx="1" filter="url(#bar-glow)">
      <animate attributeName="height" values="4;24;4" dur="0.9s" begin="0.15s" repeatCount="indefinite"/>
      <animate attributeName="y"      values="14;4;14" dur="0.9s" begin="0.15s" repeatCount="indefinite"/>
    </rect>
    <rect x="22" y="14" width="6" height="4" fill="url(#bar-grad-1)" rx="1" filter="url(#bar-glow)">
      <animate attributeName="height" values="4;18;4" dur="0.9s" begin="0.3s" repeatCount="indefinite"/>
      <animate attributeName="y"      values="14;8;14" dur="0.9s" begin="0.3s" repeatCount="indefinite"/>
    </rect>
    <rect x="32" y="14" width="6" height="4" fill="url(#bar-grad-2)" rx="1" filter="url(#bar-glow)">
      <animate attributeName="height" values="4;22;4" dur="0.9s" begin="0.45s" repeatCount="indefinite"/>
      <animate attributeName="y"      values="14;5;14" dur="0.9s" begin="0.45s" repeatCount="indefinite"/>
    </rect>
    <rect x="42" y="14" width="6" height="4" fill="#5a8fb0" rx="1" filter="url(#bar-glow)">
      <animate attributeName="height" values="4;14;4" dur="0.9s" begin="0.6s" repeatCount="indefinite"/>
      <animate attributeName="y"      values="14;10;14" dur="0.9s" begin="0.6s" repeatCount="indefinite"/>
    </rect>
  </svg>
  <span style="color:#475569; font-size:0.95rem; font-weight:500;">{label}…</span>
</div>
"""


# ============================================================================
# 3. 骨架屏
# ============================================================================

def skeleton_table(rows: int = 5, cols: int = 5) -> str:
    """表格骨架(灰色块)"""
    cells = "".join(
        f'<td><div class="skeleton-cell" style="animation-delay:{i*0.1:.1f}s"></div></td>'
        for i in range(cols)
    )
    rows_html = "".join(
        f"<tr>{cells.replace(f'animation-delay:{i*0.1:.1f}s', f'animation-delay:{(r*0.1+i*0.05):.2f}s')}</tr>"
        for r in range(rows)
    )
    return f"""
<table class="skeleton-table">
  <tbody>{rows_html}</tbody>
</table>
<style>
  .skeleton-table {{ width:100%; border-collapse:separate; border-spacing:6px; }}
  .skeleton-cell {{
    height: 16px;
    border-radius: 4px;
    background: linear-gradient(90deg, #e5e7eb 0%, #f3f4f6 50%, #e5e7eb 100%);
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
  }}
  @keyframes shimmer {{
    0%   {{ background-position: 200% 0; }}
    100% {{ background-position: -200% 0; }}
  }}
</style>
"""


def skeleton_cards(count: int = 3) -> str:
    """N 个卡片骨架(顶部 metric 用)"""
    cards = "".join(
        f'<div class="skeleton-card" style="animation-delay:{i*0.15:.1f}s"></div>'
        for i in range(count)
    )
    return f"""
<div style="display:grid; grid-template-columns:repeat({count}, 1fr); gap:14px;">{cards}</div>
<style>
  .skeleton-card {{
    height: 90px;
    border-radius: 8px;
    background: linear-gradient(90deg, #e5e7eb 0%, #f3f4f6 50%, #e5e7eb 100%);
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
  }}
  @keyframes shimmer {{
    0%   {{ background-position: 200% 0; }}
    100% {{ background-position: -200% 0; }}
  }}
</style>
"""


# ============================================================================
# 4. 数字滚动 / Metric 动画
# ============================================================================

def animated_metric(label: str, value: str, delta: str = "", icon: str = "") -> str:
    """数字带图标 + 边框渐变(可配合 st.metric 使用,这里提供自定义版本)"""
    return f"""
<div class="metric-card" style="padding:14px 18px; border-radius:10px;
            background:linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            border:1px solid #e3e6ea; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            transition: all 0.25s ease;">
  <div style="font-size:0.78rem; color:#94a3b8; margin-bottom:6px;
              display:flex; align-items:center; gap:6px;">
    {f'<span>{icon}</span>' if icon else ''}
    <span>{label}</span>
  </div>
  <div style="font-size:1.8rem; font-weight:700; color:#0d3b66;
              line-height:1.1; font-variant-numeric: tabular-nums;">
    {value}
  </div>
  {f'<div style="font-size:0.78rem; color:#64748b; margin-top:4px;">{delta}</div>' if delta else ''}
</div>
"""


# ============================================================================
# 5. 卡片悬浮效果
# ============================================================================

def hover_card(content_html: str, hover_color: str = "#0d3b66") -> str:
    """通用悬浮卡片:鼠标移上去轻微浮起 + 阴影加深 + 边框变蓝"""
    return f"""
<style>
  .hover-card {{
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid #e3e6ea;
    border-radius: 10px;
    padding: 14px 18px;
    background: #ffffff;
    cursor: pointer;
  }}
  .hover-card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(13, 59, 102, 0.15);
    border-color: {hover_color};
  }}
</style>
<div class="hover-card">
  {content_html}
</div>
"""


# ============================================================================
# 6. 进度条动画(更炫的版本)
# ============================================================================

def animated_progress(value: int, total: int = 100, text: str = "") -> str:
    """带渐变和光流动效的进度条"""
    pct = min(100, max(0, int(value / total * 100)))
    return f"""
<div>
  <div style="background:#e5e7eb; height:10px; border-radius:5px; overflow:hidden;
              position:relative;">
    <div style="background:linear-gradient(90deg, #0d3b66 0%, #1f5f8b 50%, #5a8fb0 100%);
                height:100%; width:{pct}%; border-radius:5px;
                box-shadow:0 0 8px rgba(13,59,102,0.4);
                transition: width 0.6s ease;"></div>
  </div>
  <div style="display:flex; justify-content:space-between;
              font-size:0.78rem; color:#64748b; margin-top:4px;">
    <span>{text}</span>
    <span><b style="color:#0d3b66;">{pct}%</b></span>
  </div>
</div>
"""


# ============================================================================
# 7. 渐变标题 / 装饰横幅
# ============================================================================

def gradient_banner(title: str, subtitle: str = "", icon: str = "💎") -> str:
    """大标题横幅:渐变背景 + 图标 + 副标题 + 流光动画"""
    return f"""
<div style="background:linear-gradient(135deg, #0d3b66 0%, #1f5f8b 50%, #2c5f8b 100%);
            padding:30px 36px; border-radius:12px; margin-bottom:18px;
            color:white; position:relative; overflow:hidden;
            box-shadow: 0 4px 20px rgba(13, 59, 102, 0.25);">
  <!-- 流光动画层 -->
  <div style="position:absolute; top:0; left:-100%; width:60%; height:100%;
              background:linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
              animation: shine-sweep 4s ease-in-out infinite;"></div>
  <!-- 背景装饰圆 -->
  <div style="position:absolute; top:-40px; right:-40px; opacity:0.15; font-size:140px;
              animation: float-icon 6s ease-in-out infinite;">{icon}</div>
  <!-- 装饰粒子 -->
  <svg style="position:absolute; top:10px; left:20px; width:100px; height:60px; opacity:0.3;" viewBox="0 0 100 60">
    <circle cx="10" cy="30" r="3" fill="white">
      <animate attributeName="opacity" values="0.3;0.8;0.3" dur="3s" repeatCount="indefinite"/>
    </circle>
    <circle cx="50" cy="15" r="2" fill="white">
      <animate attributeName="opacity" values="0.5;1;0.5" dur="2.5s" repeatCount="indefinite"/>
    </circle>
    <circle cx="80" cy="40" r="2.5" fill="white">
      <animate attributeName="opacity" values="0.4;0.9;0.4" dur="3.5s" repeatCount="indefinite"/>
    </circle>
  </svg>
  <div style="position:relative; z-index:1;">
    <div style="font-size:2rem; font-weight:700; margin-bottom:6px;
                text-shadow: 0 2px 8px rgba(0,0,0,0.15);">
      {icon} {title}
    </div>
    {f'<div style="font-size:0.95rem; opacity:0.9;">{subtitle}</div>' if subtitle else ''}
  </div>
</div>
<style>
  @keyframes shine-sweep {{
    0% {{ left: -100%; }}
    50% {{ left: 150%; }}
    100% {{ left: -100%; }}
  }}
  @keyframes float-icon {{
    0%, 100% {{ transform: translateY(0) rotate(0deg); }}
    50% {{ transform: translateY(-10px) rotate(5deg); }}
  }}
</style>
"""


def section_divider(text: str = "") -> str:
    """带渐变线的 section 分隔"""
    return f"""
<div style="display:flex; align-items:center; gap:14px; margin:24px 0 14px 0;">
  <div style="height:2px; flex:1;
              background:linear-gradient(90deg, transparent 0%, #cbd5e1 50%, transparent 100%);"></div>
  <div style="font-size:0.78rem; color:#94a3b8; letter-spacing:1px;
              text-transform:uppercase; font-weight:500;">{text}</div>
  <div style="height:2px; flex:1;
              background:linear-gradient(90deg, transparent 0%, #cbd5e1 50%, transparent 100%);"></div>
</div>
"""


# ============================================================================
# 8. 装饰性背景
# ============================================================================

def mesh_background() -> str:
    """整页 mesh gradient 背景(SVG 数据 URL,几乎零成本)"""
    return """
<style>
  .stApp {
    background:
      radial-gradient(at 0% 0%,  rgba(13, 59, 102, 0.04) 0px, transparent 50%),
      radial-gradient(at 100% 0%, rgba(31, 95, 139, 0.04) 0px, transparent 50%),
      radial-gradient(at 100% 100%, rgba(90, 143, 176, 0.04) 0px, transparent 50%),
      radial-gradient(at 0% 100%, rgba(168, 197, 216, 0.04) 0px, transparent 50%),
      #fafbfc !important;
  }
</style>
"""


# ============================================================================
# 9. Badge / Tag
# ============================================================================

def badge(text: str, color: str = "#0d3b66", bg: str = "#e8eef5") -> str:
    """小徽章"""
    return f"""
<span style="display:inline-block; padding:2px 10px; border-radius:12px;
             font-size:0.72rem; color:{color}; background:{bg};
             font-weight:500; margin-right:4px;">{text}</span>
"""


# ============================================================================
# 10. 数字滚动(JS 实现,加载完成后从 0 滚到目标)
# ============================================================================

def rolling_number(target: int, label: str = "", duration_ms: int = 1200) -> str:
    """数字滚动动画(初始显示目标值，CSS动画效果)"""
    return f"""
<div style="display:flex; flex-direction:column; align-items:flex-start;
            padding:8px 0;">
  <div style="font-size:2.2rem; font-weight:700; color:#0d3b66;
              line-height:1; font-variant-numeric: tabular-nums;
              position:relative;">
    <span class="roll-num" data-target="{target}">{target}</span>
    <svg class="roll-glow" width="8" height="8" viewBox="0 0 8 8" style="position:absolute;top:50%;transform:translateY(-50%);margin-left:2px;">
      <circle cx="4" cy="4" r="3" fill="#667eea" opacity="0.8">
        <animate attributeName="r" values="2;4;2" dur="1.5s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.8;0.3;0.8" dur="1.5s" repeatCount="indefinite"/>
      </circle>
    </svg>
  </div>
  <div style="font-size:0.78rem; color:#94a3b8; margin-top:6px;
              text-transform:uppercase; letter-spacing:0.5px;">{label}</div>
</div>
<style>
  .roll-num {{
    background: linear-gradient(90deg, #0d3b66 0%, #1f5f8b 50%, #667eea 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: num-glow 2s ease-in-out infinite alternate;
  }}
  @keyframes num-glow {{
    0% {{ filter: drop-shadow(0 0 2px rgba(13,59,102,0.3)); }}
    100% {{ filter: drop-shadow(0 0 8px rgba(102,126,234,0.5)); }}
  }}
</style>
"""


# ============================================================================
# 11. 浮动粒子背景
# ============================================================================

def floating_particles() -> str:
    """页面浮动粒子装饰"""
    return """
<svg width="100%" height="120" viewBox="0 0 800 120" preserveAspectRatio="none"
     style="position:absolute;top:0;left:0;width:100%;height:120px;pointer-events:none;opacity:0.6;">
  <defs>
    <radialGradient id="particle-grad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#667eea" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#667eea" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <circle cx="50" cy="30" r="4" fill="url(#particle-grad)">
    <animate attributeName="cy" values="30;70;30" dur="6s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.6;1;0.6" dur="6s" repeatCount="indefinite"/>
  </circle>
  <circle cx="150" cy="80" r="3" fill="url(#particle-grad)">
    <animate attributeName="cy" values="80;20;80" dur="8s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.5;0.9;0.5" dur="8s" repeatCount="indefinite"/>
  </circle>
  <circle cx="280" cy="50" r="5" fill="url(#particle-grad)">
    <animate attributeName="cy" values="50;90;50" dur="7s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.7;0.4;0.7" dur="7s" repeatCount="indefinite"/>
  </circle>
  <circle cx="400" cy="35" r="3" fill="url(#particle-grad)">
    <animate attributeName="cy" values="35;75;35" dur="5s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.4;0.8;0.4" dur="5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="520" cy="85" r="4" fill="url(#particle-grad)">
    <animate attributeName="cy" values="85;25;85" dur="9s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.6;1;0.6" dur="9s" repeatCount="indefinite"/>
  </circle>
  <circle cx="650" cy="45" r="3" fill="url(#particle-grad)">
    <animate attributeName="cy" values="45;85;45" dur="6.5s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.5;0.9;0.5" dur="6.5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="750" cy="65" r="4" fill="url(#particle-grad)">
    <animate attributeName="cy" values="65;15;65" dur="7.5s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.7;0.4;0.7" dur="7.5s" repeatCount="indefinite"/>
  </circle>
</svg>
"""


# ============================================================================
# 12. 发光边框卡片
# ============================================================================

def glowing_card(content: str, glow_color: str = "#667eea") -> str:
    """带发光边框的卡片"""
    return f"""
<div style="position:relative; border-radius:12px; padding:1px;
            background: linear-gradient(135deg, {glow_color}, #764ba2, {glow_color});
            background-size: 200% 200%;
            animation: glow-border 3s ease infinite;">
  <div style="background:white; border-radius:11px; padding:16px;">
    {content}
  </div>
</div>
<style>
  @keyframes glow-border {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
  }}
</style>
"""


# ============================================================================
# 13. 火花图标动画
# ============================================================================

def sparkle_icon(color: str = "#667eea") -> str:
    """带火花效果的图标"""
    return f"""
<svg width="24" height="24" viewBox="0 0 24 24" style="display:inline-block;">
  <path d="M12 2L14 10L22 12L14 14L12 22L10 14L2 12L10 10Z" fill="{color}" opacity="0.9">
    <animate attributeName="opacity" values="0.9;0.4;0.9" dur="1.5s" repeatCount="indefinite"/>
    <animateTransform attributeName="transform" type="scale" values="1;1.2;1" dur="1.5s" repeatCount="indefinite" additive="sum"/>
  </path>
  <circle cx="6" cy="6" r="1" fill="{color}" opacity="0.6">
    <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" repeatCount="indefinite"/>
  </circle>
  <circle cx="18" cy="6" r="1" fill="{color}" opacity="0.6">
    <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" begin="0.5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="18" cy="18" r="1" fill="{color}" opacity="0.6">
    <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" begin="1s" repeatCount="indefinite"/>
  </circle>
  <circle cx="6" cy="18" r="1" fill="{color}" opacity="0.6">
    <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" begin="1.5s" repeatCount="indefinite"/>
  </circle>
</svg>
"""


# ============================================================================
# 14. 数据加载骨架（更炫的版本）
# ============================================================================

def skeleton_advanced(rows: int = 5, height_px: int = 20) -> str:
    """高级骨架屏动画"""
    cells = "".join(
        f'<div class="skel-cell" style="height:{height_px}px;animation-delay:{i*0.08:.2f}s"></div>'
        for i in range(4)
    )
    rows_html = "".join(
        f'<div class="skel-row">{cells.replace(f"animation-delay:{i*0.08:.2f}s", f"animation-delay:{(r*0.1+i*0.08):.2f}s")}</div>'
        for r in range(rows)
    )
    return f"""
<div class="skeleton-wrap">{rows_html}</div>
<style>
  .skeleton-wrap {{ display:flex; flex-direction:column; gap:10px; }}
  .skel-row {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }}
  .skel-cell {{
    border-radius:6px;
    background: linear-gradient(90deg, #e5e7eb 0%, #f3f4f6 50%, #e5e7eb 100%);
    background-size: 200% 100%;
    animation: shimmer 1.5s ease-in-out infinite;
    position:relative;
    overflow:hidden;
  }}
  .skel-cell::after {{
    content:'';
    position:absolute;
    top:0; left:-100%;
    width:100%; height:100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent);
    animation: shine 1.5s ease-in-out infinite;
  }}
  @keyframes shimmer {{
    0% {{ background-position: 200% 0; }}
    100% {{ background-position: -200% 0; }}
  }}
  @keyframes shine {{
    0% {{ left: -100%; }}
    100% {{ left: 100%; }}
  }}
</style>
"""

