"""
公告扫描模块 - 获取个股近三月公告，分析管理层行为
数据来源：巨潮资讯（CNINFO）+ 东方财富
"""

import logging
import re
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# 公告分类标签
CATEGORY_KEYWORDS = {
    '高管变动': ['董事', '监事', '高管', '辞职', '聘任', '任命', '罢免', '变更', '换届'],
    '业绩公告': ['季报', '半年报', '年报', '业绩', '净利润', '营业收入', '财务报告'],
    '分红配送': ['分红', '派息', '送股', '转增', '利润分配', '股息'],
    '融资公告': ['定增', '配股', '公开募股', '发行', '上市', 'IPO'],
    '回购/增持': ['回购', '增持', '减持', '高管增持', '股东增持'],
    '股权变动': ['股权', '股份变动', '稀释', '控制权', '转让', '收购'],
    '关联交易': ['关联', '担保', '借款', '授信', '资产出售', '资产收购'],
    '监管/问询': ['问询函', '监管函', '警示函', '处罚', '立案调查', '纪律处分'],
    '股东大会': ['股东大会', '临时股东大会', '特别决议', '表决'],
    '重大合同': ['合同', '中标', '框架协议', '战略合作', '备忘录'],
    '人事招聘': ['招聘', '员工', '股权激励', '期权激励', '限制性股票'],
}


def _classify(title: str) -> str:
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in title:
                return cat
    return '其他公告'


def fetch_announcements(symbol: str, days: int = 90) -> List[Dict]:
    """获取个股近N天公告列表（使用东财 np-anotice API）"""
    import datetime
    from datetime import timedelta
    import requests

    end_date = datetime.datetime.now()
    start_date = end_date - timedelta(days=days)

    results = []

    # 东财公告（np-anotice API，直接调通）
    try:
        session = requests.Session()
        session.trust_env = False
        url = 'https://np-anotice-stock.eastmoney.com/api/security/ann'
        page_size = 50
        page_index = 1
        all_items = []

        while True:
            params = {
                'sr': -1,
                'page_size': page_size,
                'page_index': page_index,
                'ann_type': 'A',
                'client_source': 'web',
                'f_node': 0,
                's_node': 0,
                'stock_list': symbol
            }
            r = session.get(url, params=params, timeout=10)
            j = r.json()
            data = j.get('data', {})
            if isinstance(data, dict):
                items = data.get('list', [])
                total = data.get('total_hits', 0)
            else:
                items = []
                total = 0
            all_items.extend(items)
            if not items or len(all_items) >= total or page_index >= 3:
                break
            page_index += 1

        for item in all_items:
            title = item.get('title', '') or item.get('title_ch', '')
            notice_date = item.get('notice_date', '') or item.get('sort_date', '')
            art_code = item.get('art_code', '')
            if not title:
                continue
            results.append({
                'category': _classify(title),
                'title': title,
                'date': notice_date[:10] if len(str(notice_date)) > 10 else str(notice_date),
                'url': f'https://data.eastmoney.com/notices/detail/{symbol}/{art_code}.html',
                'source': '东财',
                'art_id': art_code,
            })
    except Exception as e:
        logger.warning(f"东财公告失败: {e}")

    # 去重 + 排序
    seen = set()
    unique = []
    for r in results:
        key = (r['title'][:30], r['date'][:10])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda x: x.get('date', ''), reverse=True)
    return unique


def _extract_em_content(art_id: str) -> Optional[str]:
    """尝试从东财HTML页面提取公告正文（尽力而为）"""
    try:
        import requests
        from html import unescape
        session = requests.Session()
        session.trust_env = False
        url = f'https://noticecdn.eastmoney.com/content/web?artCode={art_id}'
        r = session.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://data.eastmoney.com/'
        })
        text = r.content.decode('utf-8', errors='replace')
        text = unescape(text)
        # 去掉导航/sidebar/footer
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        # 找主内容区（通常包含 class="detail" 或 id="detail"）
        # 提取 article 或 main 区域
        main = re.search(r'<article[^>]*>(.*?)</article>', text, re.DOTALL)
        if main:
            content = main.group(1)
        else:
            # 找正文区域
            content = text
        # 去标签
        content = re.sub(r'<[^>]+>', ' ', content)
        content = re.sub(r'\s+', ' ', content).strip()
        # 去掉导航文字残留
        nav_words = ['登录', '注册', '东方财富', '财经', '手机版', '客户端', '收藏', '分享', '评论', '点赞', '相关', '推荐', '更多']
        for w in nav_words:
            content = content.replace(w, '')
        # 只保留长段落（正文）
        sentences = [s.strip() for s in re.split(r'[。！？\n]', content) if len(s.strip()) > 30]
        if not sentences:
            return None
        return '。'.join(sentences[:20])  # 最多20段
    except Exception:
        return None


def fetch_content_for_ann(ann: Dict) -> str:
    """获取单条公告的正文内容（尽力而为）"""
    if ann.get('source') == '东财' and ann.get('art_id'):
        content = _extract_em_content(ann['art_id'])
        if content and len(content) > 100:
            return content
    return None


def build_announcement_context(anns: List[Dict], include_content: bool = True) -> str:
    """将公告格式化为LLM上下文"""
    if not anns:
        return "近三月无公告记录"

    from collections import Counter
    cats = Counter(a['category'] for a in anns)
    cat_summary = ', '.join(f"{k}({v}条)" for k, v in cats.most_common())

    lines = [f"共{len(anns)}条公告，分类分布：{cat_summary}", ""]

    # 重要公告优先展示
    important_cats = {'监管/问询', '高管变动', '股权变动', '回购/增持'}
    important = [a for a in anns if a['category'] in important_cats]
    if important:
        lines.append("【重要公告】")
        for a in important[:8]:
            content_note = ""
            if include_content:
                content = fetch_content_for_ann(a)
                if content:
                    content_note = f"\n  内容摘要: {content[:200]}..."
            lines.append(f"  {a['date']} [{a['category']}] {a['title']}{content_note}")
        lines.append("")

    # 全量分类
    for cat in ['监管/问询', '高管变动', '业绩公告', '股权变动', '分红配送',
                 '融资公告', '回购/增持', '关联交易', '重大合同', '股东大会', '人事招聘', '其他公告']:
        items = [a for a in anns if a['category'] == cat]
        if items:
            lines.append(f"【{cat}】({len(items)}条)")
            for item in items[:5]:
                lines.append(f"  {item['date']} {item['title'][:70]}")
            if len(items) > 5:
                lines.append(f"  ... 还有{len(items)-5}条")
            lines.append("")

    return '\n'.join(lines)


# ─── AI意图预判 & 内容获取 ────────────────────────────────

def _classify_intent(title: str, category: str) -> str:
    """
    基于标题关键词+分类，对公告意图做初步预判（不调AI，快速返回）
    """
    # 增持/回购 → 股东认为低估
    if any(k in title for k in ['增持', '回购', '拟增持', '计划增持']):
        return "股东/公司认为股价被低估，看好未来发展"
    if any(k in title for k in ['减持', '拟减持', '计划减持']):
        return "股东减持，可能因资金需求或估值偏高"

    # 分红 → 现金流充裕
    if '分红' in title or '派息' in title or '权益分派' in title:
        return "公司盈利良好，现金流充裕，注重股东回报"
    if '送股' in title or '转增' in title:
        return "高送转可能含有市值管理意图，关注后续业绩匹配"

    # 高管变动
    if category == '高管变动' or any(k in title for k in ['董事', '监事', '高管', '行长', '副行长', '总经理', '财务总监', '副总裁', '聘任', '辞职', '任命', '任职资格', '换届']):
        # 先匹配具体关键词（更精确的放前面）
        if any(k in title for k in ['任职资格', '核准', '任职']):
            return "人事任命程序完成，新任高管正式上任"
        if any(k in title for k in ['董事', '董事长', '独立董事', '变更']):
            return "董事会层面变动，可能涉及战略方向调整"
        if any(k in title for k in ['监事', '监事会']):
            return "监事会变动，监督层调整"
        if any(k in title for k in ['行长', '副行长', '总经理', '财务总监', '副总裁', '首席', 'CFO', 'CEO']):
            return "核心管理层执行层变动，关注新任背景及分管业务"
        if any(k in title for k in ['辞职', '离职', '罢免']):
            return "⚠️ 高管离职，需关注原因及对公司影响"
        if any(k in title for k in ['聘任', '任命', '换届']):
            return "管理层换届，关注新团队背景和战略走向"
        return "高管人事变动，关注对经营的影响"

    # 监管问询
    if category == '监管/问询':
        if '处罚' in title or '立案' in title or '纪律处分' in title:
            return "⚠️ 重大监管处罚，属于重大利空信号"
        if '警示函' in title or '监管措施' in title:
            return "⚠️ 监管警示，违反相关法规"
        return "⚠️ 监管层关注，需警惕合规风险"

    # 关联交易
    if category == '关联交易':
        if '担保' in title:
            return "⚠️ 对外担保增加，关注财务风险"
        if '资产' in title and ('收购' in title or '出售' in title):
            return "资产重组行为，关注定价是否合理"
        return "⚠️ 关联交易需关注是否涉及利益输送"

    # 股权变动
    if '股权' in title or '股份' in title:
        if '控制权' in title:
            return "⚠️⚠️ 控制权变更，属于重大事件"
        if '第一大股东' in title or '实际控制人' in title:
            return "股权结构变化，实际控制人或发生变更"
        return "股权结构变化，可能涉及股东权益变动"

    # 重大合同
    if category == '重大合同':
        if '中标' in title:
            return "业务中标积极信号，关注金额占比"
        if '战略合作' in title or '框架协议' in title:
            return "战略合作意向，具体落地待观察"
        return "业务推进积极信号，关注合同金额及执行能力"

    # 融资
    if any(k in title for k in ['定增', '配股', '公开募股', '发行']):
        return "融资扩张需求，关注资金用途和摊薄效应"

    # 业绩
    if category == '业绩公告':
        if any(k in title for k in ['预减', '首亏', '续亏', '下降', '减少', '下滑']):
            return "⚠️ 业绩下滑警示，需关注原因"
        if any(k in title for k in ['预增', '扭亏', '大增', '增长', '上升']):
            return "业绩增长积极信号"
        if any(k in title for k in ['季报', '半年报', '年报']):
            return "正常业绩披露，结合历史数据判断趋势"

    return ""


def _fetch_ann_content(ann: Dict) -> Optional[str]:
    """
    尝试获取公告正文摘要。
    由于东财公告正文通过JS动态渲染，服务端无法直接获取，
    因此改用规则从标题中提取关键信息作为"摘要"。
    """
    title = ann.get('title', '')
    category = ann.get('category', '')
    date = ann.get('date', '')

    if not title:
        return None

    # 从标题中提取公司名和核心内容
    parts = title.split(':', 1)
    company = parts[0] if len(parts) > 1 else ''
    content_part = parts[1] if len(parts) > 1 else title

    # 根据不同公告类型生成摘要
    summary_parts = []

    if '分红' in content_part or '权益分派' in content_part:
        # 提取分红相关信息
        summary_parts.append("年度权益分派实施公告")
    elif '副行长' in content_part or '行长' in content_part or '总经理' in content_part:
        summary_parts.append("高管人事任命公告")
    elif '董事' in content_part and ('决议' in content_part or '通过' in content_part):
        summary_parts.append("董事会决议公告")
    elif '股东大会' in content_part or '股东会' in content_part:
        summary_parts.append("股东大会决议公告")
    elif '问询函' in content_part or '监管函' in content_part:
        summary_parts.append("⚠️ 监管问询公告")
    elif '回购' in content_part:
        summary_parts.append("股份回购进展公告")
    elif '增持' in content_part:
        summary_parts.append("股东增持公告")
    elif '减持' in content_part:
        summary_parts.append("⚠️ 股东减持公告")
    elif '季报' in content_part or '半年报' in content_part or '年报' in content_part:
        summary_parts.append("定期财务报告")
    elif '法律意见书' in content_part:
        summary_parts.append("年度股东大会法律意见书")
    elif '决议公告' in content_part:
        summary_parts.append("公司决议公告")
    else:
        summary_parts.append(f"公告类型：{category}")

    if company:
        summary_parts.insert(0, company)

    return ' | '.join(summary_parts)

