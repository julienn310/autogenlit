"""
金融新闻与舆情采集模块

数据源策略（按可用性排序）：
1. akshare stable: stock_js_weibo_report(微博情绪) / stock_hot_tweet_xq(雪球热帖)
2. eastmoney: 多分类快讯（A股/港股/美股/基金/期货，要闻）
3. 新浪财经: 国内财经/外汇/期货/基金
4. WSJ RSS: 国际市场

KOL来源：通过东财快讯关键词匹配 + akshare微博情绪中的名称
"""

import logging
import re
import json
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# KOL 列表
KOLS = [
    '李大霄', '任泽平', '付鹏', '刘煜辉', '高善文',
    '李迅雷', '姜超', '徐彪', '洪灏', '陈李',
]


# ─── 工具函数 ────────────────────────────────────────────

def _bracket_json(text: str) -> dict:
    """从 text 中提取配对花括号的 JSON 对象（避免正则遇到 }{ 截断）"""
    start = text.index('{')
    count = 0
    for i, c in enumerate(text):
        if c == '{':
            count += 1
        elif c == '}':
            count -= 1
            if count == 0:
                return json.loads(text[:i+1])
    return {}


def _fetch_em_category(url: str) -> List[Dict]:
    """获取东财单个分类快讯"""
    try:
        import requests
        r = requests.get(url, timeout=10)
        raw = r.content
        idx = raw.find(b'ajaxResult=')
        if idx < 0:
            return []
        json_bytes = raw[idx + len(b'ajaxResult='):]
        # 找配对花括号
        start = json_bytes.index(b'{')
        count = 0
        for i, c in enumerate(json_bytes):
            if c == 123:  # '{'
                count += 1
            elif c == 125:  # '}'
                count -= 1
                if count == 0:
                    json_bytes = json_bytes[:i+1]
                    break
        text = json_bytes.decode('utf-8', errors='replace')
        data = json.loads(text)
        lives = data.get('LivesList', [])
        results = []
        for item in lives:
            title = item.get('title', '')
            if not title:
                continue
            results.append({
                'title': title,
                'url': item.get('url_w', ''),
                'time': item.get('showtime', '')[:16],
                'kol': None,
                'source': '东财',
            })
        return results
    except Exception as e:
        logger.debug(f"东财分类获取失败: {e}")
        return []


def _fetch_sina_news() -> List[Dict]:
    """获取新浪财经滚动新闻"""
    results = []
    lids = {
        '2517': '国内财经',
        '2513': '外汇',
        '2518': '期货',
        '2515': '基金',
    }
    try:
        import requests
        session = requests.Session()
        session.trust_env = False
        for lid, category in lids.items():
            try:
                r = session.get(
                    f'https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid={lid}&k=&num=8&page=1&r=0.5',
                    timeout=8,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                j = r.json()
                for it in j.get('result', {}).get('data', []):
                    title = it.get('title', '')
                    if not title:
                        continue
                    results.append({
                        'title': title,
                        'url': it.get('url', ''),
                        'time': it.get('intime', '')[:16] if it.get('intime') else '',
                        'kol': None,
                        'source': f'新浪·{category}',
                    })
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"新浪新闻获取失败: {e}")
    return results


def _fetch_wsj_news() -> List[Dict]:
    """获取华尔街日报 RSS（国际市场）"""
    results = []
    try:
        import requests
        import xml.etree.ElementTree as ET
        session = requests.Session()
        session.trust_env = False
        r = session.get(
            'https://feeds.a.dj.com/rss/RSSMarketsMain.xml',
            timeout=10,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        root = ET.fromstring(r.content)
        for item in root.findall('.//item')[:10]:
            title_el = item.find('title')
            link_el = item.find('link')
            title = title_el.text if title_el is not None else ''
            if not title:
                continue
            results.append({
                'title': title,
                'url': link_el.text if link_el is not None else '',
                'time': '',
                'kol': None,
                'source': 'WSJ',
            })
    except Exception as e:
        logger.debug(f"WSJ RSS获取失败: {e}")
    return results


def _fetch_caixin_news() -> List[Dict]:
    """获取财新市场资讯"""
    try:
        import akshare as ak
        df = ak.stock_news_main_cx()
        if df is None or df.empty:
            return []
        return [
            {
                'title': row.get('summary', '')[:200],
                'url': row.get('url', ''),
                'time': '',
                'kol': None,
                'source': f"财新·{row.get('tag', '')}",
            }
            for _, row in df.head(10).iterrows()
        ]
    except Exception as e:
        logger.debug(f"财新要闻获取失败: {e}")
        return []


def _fetch_akshare_weibo_sentiment() -> List[Dict]:
    """获取akshare微博情绪数据"""
    try:
        import akshare as ak
        df = ak.stock_js_weibo_report()
        if df is None or df.empty:
            return []
        return [
            {
                'title': f"{row.get('name', '')} 舆情指数: {row.get('rate', 0):+.2f}",
                'url': '',
                'time': '',
                'kol': None,
                'source': '微博情绪',
            }
            for _, row in df.iterrows()
        ]
    except Exception as e:
        logger.debug(f"微博情绪获取失败: {e}")
        return []


def _fetch_akshare_xueqiu_hot() -> List[Dict]:
    """获取akshare雪球热帖（按讨论数排序）"""
    try:
        import akshare as ak
        df = ak.stock_hot_tweet_xq()
        if df is None or df.empty:
            return []
        # 取讨论数最高的前20只股票
        cols = df.columns.tolist()
        # 猜测列顺序: [股票代码, 股票名称, 讨论数, 最新价]
        code_col = cols[0] if len(cols) > 0 else None
        name_col = cols[1] if len(cols) > 1 else None
        discuss_col = cols[2] if len(cols) > 2 else None
        price_col = cols[3] if len(cols) > 3 else None

        results = []
        for _, row in df.head(20).iterrows():
            name = str(row[name_col]) if name_col else ''
            code = str(row[code_col]) if code_col else ''
            discuss = row[discuss_col] if discuss_col else 0
            price = row[price_col] if price_col else 0
            try:
                price_f = float(price)
                price_str = f"{price_f:.2f}"
            except (ValueError, TypeError):
                price_str = str(price)
            try:
                discuss_i = int(discuss)
            except (ValueError, TypeError):
                discuss_i = 0

            results.append({
                'title': f"{name}({code}) 讨论 {discuss_i} | 最新价 {price_str}",
                'url': f'https://xueqiu.com/S/{code}',
                'time': '',
                'kol': None,
                'source': '雪球热帖',
            })
        return results
    except Exception as e:
        logger.debug(f"雪球热帖获取失败: {e}")
        return []


def _enrich_kol(news_list: List[Dict]) -> List[Dict]:
    """在新闻列表中标记KOL关键词匹配"""
    for item in news_list:
        title = item.get('title', '')
        for kol in KOLS:
            if kol in title:
                item['kol'] = kol
                break
    return news_list


# ─── 主函数 ──────────────────────────────────────────────

def fetch_news() -> Dict[str, List[Dict]]:
    """
    获取所有新闻与舆情数据（按时间排序）

    Returns:
        {
            'timeline': [...],  # 所有新闻按时间排序
            'kol': [...],      # KOL提及（从timeline中过滤）
            'weibo_sentiment': [...],  # 微博情绪
            'xueqiu_hot': [...],       # 雪球热帖
            'flash': [...],     # 快讯（东财A股）
        }
    """
    timeline = []
    em_categories = {
        '101': '东财·要闻',
        '102': '东财·A股',
        '103': '东财·港股',
        '104': '东财·美股',
        '106': '东财·基金',
        '107': '东财·期货',
    }

    # 1. 东财快讯（多分类）
    for cat_id, cat_label in em_categories.items():
        url = f'https://newsapi.eastmoney.com/kuaixun/v1/getlist_{cat_id}_ajaxResult_20_1_.html'
        items = _fetch_em_category(url)
        for it in items:
            it['source'] = cat_label
        timeline.extend(items)

    # 2. 新浪财经
    sina_items = _fetch_sina_news()
    timeline.extend(sina_items)

    # 3. KOL标记
    timeline = _enrich_kol(timeline)

    # 4. WSJ 国际
    wsj_items = _fetch_wsj_news()
    caixin_items = _fetch_caixin_news()

    # 5. 微博情绪（akshare）
    weibo_sentiment = _fetch_akshare_weibo_sentiment()

    # 6. 雪球热帖（akshare）
    xueqiu_hot = _fetch_akshare_xueqiu_hot()

    # 7. KOL专区的新闻（从timeline中提出来）
    kol_news = [n for n in timeline if n.get('kol')]

    # 8. 按时间排序（最新在前，空时间的放最后）
    def sort_key(n):
        t = n.get('time', '')
        return t if t else '0000'
    timeline.sort(key=sort_key, reverse=True)

    # 9. 快讯：取东财A股前10条
    flash = [n for n in timeline if n.get('source', '').startswith('东财')][:10]

    return {
        'timeline': timeline[:100],     # 最新100条
        'kol': kol_news,               # KOL提及
        'weibo_sentiment': weibo_sentiment,
        'xueqiu_hot': xueqiu_hot,
        'flash': flash,
    }
