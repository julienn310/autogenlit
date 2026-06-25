"""导出模块 - 生成多种格式的分析报告"""

import io
import json
import os
from typing import List, Dict, Any
from datetime import datetime

import pandas as pd
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 注册中文字体（Windows）
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont('SimHei', FONT_PATH))
    CHINESE_FONT = 'SimHei'
else:
    CHINESE_FONT = 'Helvetica'


def export_to_json(results: List[Dict], filename: str = None) -> bytes:
    """导出为 JSON 格式"""
    data = {
        "export_time": datetime.now().isoformat(),
        "total_stocks": len(results),
        "results": results
    }
    content = json.dumps(data, ensure_ascii=False, indent=2)
    return content.encode('utf-8')


def export_to_csv(results: List[Dict], filename: str = None) -> bytes:
    """导出为 CSV 格式（Excel友好）"""
    if not results:
        return b""

    # 展平嵌套字段
    rows = []
    for r in results:
        row = {
            "股票代码": r.get("symbol", ""),
            "股票名称": r.get("name", ""),
            "现价": r.get("price", ""),
            "市盈率(PE)": r.get("pe", ""),
            "市净率(PB)": r.get("pb", ""),
            "市销率(PS)": r.get("ps", ""),
            "总市值": r.get("market_cap", ""),
            "流通市值": r.get("float_market_cap", ""),
        }

        # 展平财务指标
        fm = r.get("financial_metrics", {})
        if isinstance(fm, dict):
            for k, v in fm.items():
                row[f"财务_{k}"] = v

        # 展平风险指标
        rm = r.get("risk_metrics", {})
        if isinstance(rm, dict):
            for k, v in rm.items():
                row[f"风险_{k}"] = v

        rows.append(row)

    df = pd.DataFrame(rows)
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    return output.getvalue().encode('utf-8-sig')


def export_to_html(results: List[Dict], filename: str = None) -> bytes:
    """导出为 HTML 格式（带样式）"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_parts = [f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>A股分析报告</title>
<style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
               background: #f5f7fa; padding: 20px; color: #333; }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               color: white; padding: 30px; border-radius: 12px; margin-bottom: 24px; }}
    .header h1 {{ font-size: 24px; margin-bottom: 6px; }}
    .header p {{ opacity: 0.85; font-size: 13px; }}
    .stock-card {{ background: white; border-radius: 10px; padding: 24px; margin-bottom: 20px;
                   box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
    .stock-header {{ display: flex; justify-content: space-between; align-items: center;
                     border-bottom: 1px solid #eee; padding-bottom: 14px; margin-bottom: 16px; }}
    .stock-name {{ font-size: 18px; font-weight: bold; color: #1a1a2e; }}
    .stock-code {{ color: #888; font-size: 13px; }}
    .stock-price {{ font-size: 22px; color: #667eea; font-weight: bold; }}
    .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }}
    .metric-item {{ background: #f8f9fc; border-radius: 8px; padding: 12px 14px; }}
    .metric-label {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
    .metric-value {{ font-size: 16px; font-weight: 600; color: #333; }}
    .metric-value.positive {{ color: #27ae60; }}
    .metric-value.negative {{ color: #e74c3c; }}
    .section-title {{ font-size: 14px; font-weight: 600; color: #667eea; margin: 16px 0 10px; }}
    .analysis-text {{ background: #fafbff; border-left: 3px solid #667eea; padding: 12px 16px;
                      border-radius: 0 8px 8px 0; font-size: 13px; line-height: 1.7; color: #444; }}
    .footer {{ text-align: center; color: #aaa; font-size: 12px; margin-top: 30px; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>📊 A股智能体分析报告</h1>
        <p>生成时间：{timestamp} &nbsp;|&nbsp; 共 {len(results)} 只股票</p>
    </div>
"""]

    for r in results:
        symbol = r.get("symbol", "")
        name = r.get("name", symbol)
        price = r.get("price", "-")
        pe = r.get("pe", "-")
        pb = r.get("pb", "-")
        ps = r.get("ps", "-")
        market_cap = r.get("market_cap", "-")
        float_market_cap = r.get("float_market_cap", "-")

        fm = r.get("financial_metrics", {})
        rm = r.get("risk_metrics", {})
        fin_analysis = r.get("financial_analysis", "暂无")
        risk_analysis = r.get("risk_analysis", "暂无")

        # 过滤掉带%的展示值
        def clean(v):
            if isinstance(v, str) and "%" in v:
                return v
            return v

        html_parts.append(f"""
    <div class="stock-card">
        <div class="stock-header">
            <div>
                <div class="stock-name">{name}</div>
                <div class="stock-code">{symbol}</div>
            </div>
            <div class="stock-price">¥{price}</div>
        </div>

        <div class="metrics-grid">
            <div class="metric-item">
                <div class="metric-label">市盈率 (PE)</div>
                <div class="metric-value">{pe}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">市净率 (PB)</div>
                <div class="metric-value">{pb}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">市销率 (PS)</div>
                <div class="metric-value">{ps}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">总市值</div>
                <div class="metric-value">{market_cap}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">流通市值</div>
                <div class="metric-value">{float_market_cap}</div>
            </div>
        </div>

        <div class="section-title">财务分析</div>
        <div class="analysis-text">{fin_analysis}</div>

        <div class="section-title">风险分析</div>
        <div class="analysis-text">{risk_analysis}</div>
    </div>
""")

    html_parts.append(f"""
    <div class="footer">
        <p>由 A股智能体分析系统 生成 &nbsp;|&nbsp; {timestamp}</p>
    </div>
</div>
</body>
</html>""")

    return "".join(html_parts).encode('utf-8')


def export_to_pdf(results: List[Dict], filename: str = None) -> bytes:
    """导出为 PDF 格式（中文友好）"""
    output = io.BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=portrait(A4),
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'],
                                  fontSize=18, spaceAfter=6, textColor=colors.HexColor('#667eea'),
                                  alignment=TA_CENTER, fontName=CHINESE_FONT)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
                                     fontSize=10, textColor=colors.grey, alignment=TA_CENTER,
                                     fontName=CHINESE_FONT)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'],
                                    fontSize=13, textColor=colors.HexColor('#667eea'),
                                    spaceAfter=6, spaceBefore=14, fontName=CHINESE_FONT)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                fontSize=9, leading=14, textColor=colors.HexColor('#444444'),
                                fontName=CHINESE_FONT)
    small_style = ParagraphStyle('Small', parent=styles['Normal'],
                                fontSize=8, textColor=colors.grey, fontName=CHINESE_FONT)

    story = []

    # 标题
    story.append(Paragraph("A股智能体分析报告", title_style))
    story.append(Paragraph(
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; 共 {len(results)} 只股票",
        subtitle_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#667eea'), spaceAfter=10))

    F = CHINESE_FONT
    FB = CHINESE_FONT  # SimHei 没有独立粗体，混用即可

    for i, r in enumerate(results):
        symbol = r.get("symbol", "")
        name = r.get("name", symbol)
        price = r.get("price", "-")
        pe = r.get("pe", "-")
        pb = r.get("pb", "-")
        ps = r.get("ps", "-")
        market_cap = r.get("market_cap", "-")

        story.append(Paragraph(f"{name}（{symbol}）", heading_style))

        # 估值指标
        val_data = [
            ["现价", f"¥{price}", "市盈率(PE)", str(pe), "市净率(PB)", str(pb), "总市值", market_cap]
        ]
        val_table = Table(val_data, colWidths=[2*cm, 2.8*cm, 2.2*cm, 1.8*cm, 2.2*cm, 1.8*cm, 2*cm, 2.8*cm])
        val_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), F),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.grey),
            ('TEXTCOLOR', (4, 0), (4, -1), colors.grey),
            ('TEXTCOLOR', (6, 0), (6, -1), colors.grey),
            ('FONTNAME', (1, 0), (1, -1), FB),
            ('FONTNAME', (3, 0), (3, -1), FB),
            ('FONTNAME', (5, 0), (5, -1), FB),
            ('FONTNAME', (7, 0), (7, -1), FB),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fc')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(val_table)
        story.append(Spacer(1, 0.2*cm))

        # 财务指标
        fm = r.get("financial_metrics", {})
        if isinstance(fm, dict) and fm:
            story.append(Paragraph("财务指标", ParagraphStyle('SubHead', parent=heading_style, fontSize=10, fontName=CHINESE_FONT)))
            fm_rows = []
            row = []
            for j, (k, v) in enumerate(fm.items()):
                row.append(k)
                row.append(str(v))
                if len(row) == 4:
                    fm_rows.append(row)
                    row = []
            if row:
                while len(row) < 4:
                    row.append("")
                fm_rows.append(row)

            if fm_rows:
                fm_table = Table(fm_rows, colWidths=[3*cm, 3*cm, 3*cm, 3*cm])
                fm_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, -1), F),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
                    ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f0f0f0')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(fm_table)
                story.append(Spacer(1, 0.2*cm))

        # 风险指标
        rm = r.get("risk_metrics", {})
        if isinstance(rm, dict) and rm:
            story.append(Paragraph("风险指标", ParagraphStyle('SubHead', parent=heading_style, fontSize=10, fontName=CHINESE_FONT)))
            rm_rows = []
            row = []
            for j, (k, v) in enumerate(rm.items()):
                row.append(k)
                row.append(str(v))
                if len(row) == 4:
                    rm_rows.append(row)
                    row = []
            if row:
                while len(row) < 4:
                    row.append("")
                rm_rows.append(row)

            if rm_rows:
                rm_table = Table(rm_rows, colWidths=[3*cm, 3*cm, 3*cm, 3*cm])
                rm_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, -1), F),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
                    ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f0f0f0')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(rm_table)
                story.append(Spacer(1, 0.2*cm))

        # 分析文本
        fin = r.get("financial_analysis", "")
        risk = r.get("risk_analysis", "")
        if fin:
            story.append(Paragraph("财务分析", ParagraphStyle('SubHead', parent=heading_style, fontSize=10)))
            story.append(Paragraph(fin.replace('\n', '<br/>'), body_style))
            story.append(Spacer(1, 0.15*cm))
        if risk:
            story.append(Paragraph("风险分析", ParagraphStyle('SubHead', parent=heading_style, fontSize=10)))
            story.append(Paragraph(risk.replace('\n', '<br/>'), body_style))

        if i < len(results) - 1:
            story.append(Spacer(1, 0.4*cm))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#eee'), spaceAfter=10))

    # 页脚
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=6))
    story.append(Paragraph(
        f"由A股智能体分析系统生成 &nbsp;|&nbsp; {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        small_style))

    doc.build(story)
    return output.getvalue()


def export_to_excel(results: List[Dict], filename: str = None) -> bytes:
    """导出为 Excel 格式（多Sheet）"""
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet1: 汇总
        rows = []
        for r in results:
            row = {
                "股票代码": r.get("symbol", ""),
                "股票名称": r.get("name", ""),
                "现价": r.get("price", ""),
                "市盈率(PE)": r.get("pe", ""),
                "市净率(PB)": r.get("pb", ""),
                "市销率(PS)": r.get("ps", ""),
                "总市值": r.get("market_cap", ""),
                "流通市值": r.get("float_market_cap", ""),
            }
            rows.append(row)
        df_summary = pd.DataFrame(rows)
        df_summary.to_excel(writer, sheet_name="概览", index=False)

        # Sheet2: 财务指标
        fm_rows = []
        for r in results:
            row = {"股票代码": r.get("symbol", ""), "股票名称": r.get("name", "")}
            fm = r.get("financial_metrics", {})
            if isinstance(fm, dict):
                row.update(fm)
            fm_rows.append(row)
        if fm_rows:
            df_fm = pd.DataFrame(fm_rows)
            df_fm.to_excel(writer, sheet_name="财务指标", index=False)

        # Sheet3: 风险指标
        rm_rows = []
        for r in results:
            row = {"股票代码": r.get("symbol", ""), "股票名称": r.get("name", "")}
            rm = r.get("risk_metrics", {})
            if isinstance(rm, dict):
                row.update(rm)
            rm_rows.append(row)
        if rm_rows:
            df_rm = pd.DataFrame(rm_rows)
            df_rm.to_excel(writer, sheet_name="风险指标", index=False)

        # Sheet4: 分析文本
        text_rows = []
        for r in results:
            text_rows.append({
                "股票代码": r.get("symbol", ""),
                "股票名称": r.get("name", ""),
                "财务分析": r.get("financial_analysis", ""),
                "风险分析": r.get("risk_analysis", ""),
            })
        df_text = pd.DataFrame(text_rows)
        df_text.to_excel(writer, sheet_name="分析文本", index=False)
        # 设置列宽
        worksheet = writer.sheets["分析文本"]
        worksheet.column_dimensions['A'].width = 12
        worksheet.column_dimensions['B'].width = 12
        worksheet.column_dimensions['C'].width = 60
        worksheet.column_dimensions['D'].width = 60

    return output.getvalue()


SUPPORTED_FORMATS = {
    "json": ("application/json", "json", export_to_json),
    "csv": ("text/csv", "csv", export_to_csv),
    "html": ("text/html", "html", export_to_html),
    "pdf": ("application/pdf", "pdf", export_to_pdf),
    "excel": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx", export_to_excel),
}


def generate_export(results: List[Dict], export_format: str) -> tuple:
    """
    生成导出文件

    Returns:
        (file_bytes, mime_type, extension)
    """
    fmt = export_format.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"不支持的格式: {fmt}，支持: {list(SUPPORTED_FORMATS.keys())}")

    mime, ext, func = SUPPORTED_FORMATS[fmt]
    content = func(results)
    return content, mime, ext
