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
    """获取个股近N天公告列表（新浪 + 东财双来源，去重后按日期排序）"""
    import datetime
    from datetime import timedelta
    import requests

    end_date = datetime.datetime.now()
    start_date = end_date - timedelta(days=days)

    all_results = {}  # key: (title[:40], date) -> dict, 用于去重

    # ── 新浪公告（可抓正文）─────────────────────────────
    try:
        session = requests.Session()
        session.trust_env = False
        sina_base = 'https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid'
        page = 1
        while page <= 5:
            url = f'{sina_base}/{symbol}/page/{page}.phtml'
            r = session.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            text = r.content.decode('gbk', errors='replace')

            datelist_match = re.search(r'class="datelist">(.*?)</ul>', text, re.DOTALL)
            if not datelist_match:
                break
            datelist = datelist_match.group(1)
            entries = re.findall(
                r'(\d{4}-\d{2}-\d{2})&nbsp;<a[^>]+/corp/view/vCB_AllBulletinDetail\.php\?stockid=\d+&id=(\d+)[^>]*>([^<]+)</a>',
                datelist
            )
            if not entries:
                break

            page_has_new = False
            for date_str, sina_id, title in entries:
                title = title.strip()
                if not title:
                    continue
                notice_date = date_str
                d = datetime.datetime.strptime(notice_date, '%Y-%m-%d')
                if d < start_date:
                    continue
                page_has_new = True
                key = (title[:40].replace('：', ':'), notice_date)
                if key not in all_results:
                    all_results[key] = {
                        'category': _classify(title),
                        'title': title,
                        'date': notice_date,
                        'url': f'https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid={symbol}&id={sina_id}',
                        'source': '新浪',
                        'art_id': sina_id,
                    }
            if not page_has_new:
                break
            page += 1
    except Exception as e:
        logger.warning(f"新浪公告失败: {e}")

    # ── 东财公告（补充，没有内容但补全公告覆盖面）─────────
    try:
        session2 = requests.Session()
        session2.trust_env = False
        url = 'https://np-anotice-stock.eastmoney.com/api/security/ann'
        page_index = 1
        all_items = []
        while True:
            params = {
                'sr': -1, 'page_size': 50, 'page_index': page_index,
                'ann_type': 'A', 'client_source': 'web',
                'f_node': 0, 's_node': 0, 'stock_list': symbol
            }
            r = session2.get(url, params=params, timeout=10)
            j = r.json()
            data = j.get('data', {})
            items = data.get('list', []) if isinstance(data, dict) else []
            all_items.extend(items)
            total = data.get('total_hits', 0) if isinstance(data, dict) else 0
            if not items or len(all_items) >= total or page_index >= 5:
                break
            page_index += 1

        for item in all_items:
            title = (item.get('title', '') or item.get('title_ch', '')).strip()
            notice_date = str(item.get('notice_date', ''))[:10]
            art_code = item.get('art_code', '')
            if not title or not notice_date:
                continue
            d = datetime.datetime.strptime(notice_date, '%Y-%m-%d')
            if d < start_date:
                continue
            key = (title[:40].replace('：', ':'), notice_date)
            if key not in all_results:
                all_results[key] = {
                    'category': _classify(title),
                    'title': title,
                    'date': notice_date,
                    'url': f'https://data.eastmoney.com/notices/detail/{symbol}/{art_code}.html',
                    'source': '东财',
                    'art_id': art_code,
                }
    except Exception as e:
        logger.warning(f"东财公告失败: {e}")

    # 按日期排序
    results = sorted(all_results.values(), key=lambda x: x.get('date', ''), reverse=True)
    return results


def _extract_em_content(art_id: str) -> Optional[str]:
    """东财公告正文已被JS渲染锁死，无法服务端获取，直接返回None"""
    return None


def fetch_content_for_ann(ann: Dict) -> Optional[str]:
    """获取单条公告的正文内容"""
    # 新浪详情页（可抓正文）
    url = ann.get('url', '')
    if 'sina.com.cn' in url:
        return _fetch_ann_content(ann)
    # 东财（正文被JS渲染锁死，尝试备选）
    if ann.get('source') == '东财' and ann.get('art_id'):
        content = _extract_em_content(ann['art_id'])
        if content and len(content) > 50:
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
                    content_note = f"\n  内容摘要: {content[:2000]}..."
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
    从新浪财经详情页抓取公告正文。
    公告列表的 url 字段直接是新浪详情页URL。
    """
    url = ann.get('url', '')
    if not url or 'sina.com.cn' not in url:
        return None

    try:
        import requests
        session = requests.Session()
        session.trust_env = False
        r = session.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        text = r.content.decode('gbk', errors='replace')

        # 提取 <div id="content"> 正文
        m = re.search(r'<div[^>]+id=["\']content["\'][^>]*>(.*?)</div>', text, re.DOTALL)
        if not m:
            return None

        content = re.sub(r'<[^>]+>', '', m.group(1))
        content = re.sub(r'\s+', ' ', content).strip()
        # 过滤残留词
        for w in ['查看信息地雷', '新浪财经', '手机版', '收藏', '分享', '附件', '相关', '推荐']:
            content = content.replace(w, '')
        content = re.sub(r'\s+', ' ', content).strip()

        if len(content) < 20:
            return None

        return content[:5000]  # 最多5000字

    except Exception:
        return None

