"""
市场行情数据采集 - 从腾讯/东财获取主要指数数据
"""

import requests
import logging
import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 腾讯行情接口可用的指数列表
INDICES_TENCENT = {
    # A股主要指数
    'sh000001': '上证指数',
    'sz399001': '深证成指',
    'sz399006': '创业板指',
    'sh000300': '沪深300',
    'sh000016': '上证50',
    'sh000905': '中证500',
    'sh000688': '科创50',
    # 全球指数（腾讯API不稳定，日韩英德法澳印时常失败，以实际能获取的为准）
    'hkHSI': '恒生指数',
    'hkHSCEI': '恒生科技',
    'usIXIC': '纳斯达克综合',
    'usDJI': '道琼斯工业',
    'usINX': '标普500',
}

# 腾讯行情字段索引
# v_pv_none_match="1" 或 v_s_xxx="1~名称~代码~当前价~涨跌~涨跌幅~成交量~成交额~~..."
TQ_FIELDS = ['name', 'code', 'price', 'change', 'change_pct', 'volume', 'amount', 'unused', 'label']


def _parse_tencent_response(text: str, code: str) -> Optional[Dict]:
    """解析腾讯行情返回的单条数据

    腾讯行情字段索引（以sh000001为例）：
      [3]  当前价格
      [4]  昨日收盘/开盘？
      [5]  今日开盘
      [31] 涨跌额
      [32] 涨跌幅（%，如 -3.05 表示 -3.05%）
    """
    try:
        prefix = f'v_{code}="'
        idx = text.find(prefix)
        if idx < 0:
            return None

        start = idx + len(prefix)
        end = text.find('"', start)
        if end < 0:
            return None

        raw = text[start:end]
        parts = raw.split('~')
        if len(parts) < 33:
            return None

        name = parts[1]
        try:
            price = float(parts[3]) if parts[3] not in ('', '-') else 0.0
        except (ValueError, TypeError):
            price = 0.0
        try:
            change = float(parts[31]) if parts[31] not in ('', '-') else 0.0
        except (ValueError, TypeError):
            change = 0.0
        try:
            change_pct = float(parts[32]) if parts[32] not in ('', '-') else 0.0
        except (ValueError, TypeError):
            change_pct = 0.0

        return {
            'name': name,
            'code': code,
            'price': price,
            'change': change,
            'change_pct': change_pct,
            'source': 'tencent',
        }
    except Exception as e:
        logger.debug(f"解析腾讯行情失败 {code}: {e}")
        return None


def fetch_major_indices_history(code: str, start_date: str) -> Dict[str, List[float]]:
    """
    获取主要指数历史K线（OHLC），通过新浪接口
    code: 'sh000001' 等
    start_date: 'YYYY-MM-DD'
    返回: {date: [open, close, high, low, volume]}
    """
    try:
        # 新浪指数代码：上交所加 sh，深交所加 sz
        symbol = 'sh' + code[2:] if code.startswith('sh') else 'sz' + code[2:]
        url = (
            f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
            f'CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen=180'
        )
        session = requests.Session()
        r = session.get(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn'
        }, timeout=10)
        r.encoding = 'utf-8'
        data = r.json()
        if not isinstance(data, list):
            return {}
        result = {}
        for row in data:
            d = row.get('day', '')
            try:
                o = float(row.get('open', 0))
                c = float(row.get('close', 0))
                h = float(row.get('high', 0))
                l = float(row.get('low', 0))
                v = float(row.get('volume', 0))
                result[d] = [o, c, h, l, v]
            except Exception:
                continue
        # 过滤掉早于 start_date 的数据
        if start_date:
            result = {d: v for d, v in result.items() if d >= start_date}
        return result
    except Exception as e:
        logger.debug(f"指数历史获取失败 {code}: {e}")
        return {}


def fetch_major_indices() -> List[Dict]:
    """
    获取主要市场指数行情

    Returns:
        [{name, code, price, change, change_pct, source}, ...]
    """
    session = requests.Session()
    session.trust_env = False

    results = []
    codes = list(INDICES_TENCENT.keys())

    # 分批请求（腾讯接口每次最多约20个）
    batch_size = 15
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        query = ','.join(batch)
        url = f'https://qt.gtimg.cn/q={query}'

        try:
            r = session.get(url, timeout=10)
            r.encoding = 'gbk'

            for code in batch:
                data = _parse_tencent_response(r.text, code)
                if data:
                    results.append(data)
        except Exception as e:
            logger.warning(f"批次获取失败 {batch[0]}: {e}")
            continue

    # 补充新浪全球指数（日经、英国富时；美股用腾讯已有数据，不再重复添加）
    try:
        sina_results = fetch_sina_global_indices()
        # 只保留日经和英国富时（Sina有，美股用腾讯的避免重复）
        sina_keep = {'int_nikkei', 'int_ftse'}
        results.extend([s for s in sina_results if s['code'] in sina_keep])
    except Exception:
        pass

    return results


# 新浪全球指数（补充腾讯覆盖不到的日经、英国富时）
SINA_GLOBAL_CODES = {
    'int_nikkei': '日经225',
    'int_ftse': '英国富时100',
    'int_nasdaq': '纳斯达克综合',
    'int_dji': '道琼斯工业',
    'int_sp500': '标普500',
}


def fetch_sina_global_indices() -> List[Dict]:
    """
    通过新浪财经接口获取全球指数（腾讯覆盖不到的补充）
    格式: int_nikkei, int_ftse, int_nasdaq, int_dji, int_sp500
    返回: [{name, code, price, change, change_pct}, ...]
    """
    session = requests.Session()
    session.trust_env = False
    headers = {'Referer': 'https://finance.sina.com.cn'}

    codes_str = ','.join(SINA_GLOBAL_CODES.keys())
    url = f'https://hq.sinajs.cn/list={codes_str}'

    try:
        r = session.get(url, headers=headers, timeout=10)
        r.encoding = 'gbk'
        results = []

        for line in r.text.strip().split('\n'):
            try:
                raw = line.split('=')
                if len(raw) < 2:
                    continue
                key = raw[0].replace('var hq_str_', '').strip()
                if key not in SINA_GLOBAL_CODES:
                    continue
                val = raw[1].strip('";\n')
                if not val:
                    continue
                fields = val.split(',')
                if len(fields) < 4 or not fields[1]:
                    continue

                name = fields[0]
                try:
                    price = float(fields[1])
                except (ValueError, TypeError):
                    price = 0.0
                try:
                    change_pct = float(fields[3])
                except (ValueError, TypeError):
                    change_pct = 0.0

                results.append({
                    'name': name,
                    'code': key,
                    'price': price,
                    'change': 0.0,
                    'change_pct': change_pct,
                    'source': 'sina',
                })
            except Exception:
                continue

        return results
    except Exception:
        return []


# 主要ETF列表（宽基 + 热门行业）
ETF_CODES = {
    'sh510300': '沪深300ETF',
    'sh510500': '中证500ETF',
    'sz159915': '创业板ETF',
    'sh510050': '上证50ETF',
    'sh512880': '证券ETF',
    'sh512760': '芯片ETF',
    'sh512690': '酒ETF',
    'sh515000': '科技ETF',
    'sh512010': '医药ETF',
    'sh512660': '军工ETF',
    'sh510880': '红利ETF华泰柏瑞',
    'sz159998': '农业ETF平安',
}


def fetch_etf_data() -> List[Dict]:
    """
    获取主要ETF实时行情（价格、涨跌幅、估算资金流向）
    资金流向估算：基于价格涨跌方向 + 成交量变化
    """
    session = requests.Session()
    session.trust_env = False

    results = []
    codes = list(ETF_CODES.keys())

    # 腾讯行情字段索引（ETF格式）
    # v_sh510300="1~名称~代码~当前价~昨日收盘~今日开盘~成交量~成交额~~..."
    # ETF字段：parts[3]=当前价, parts[4]=昨日收盘, parts[31]=涨跌额, parts[32]=涨跌幅%
    TQ_FIELDS_ETF = ['unused', 'name', 'code', 'price', 'prev_close', 'open',
                     'volume', 'amount', 'unused2', 'bid', 'ask',
                     'change', 'change_pct']

    batch_size = 10
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        query = ','.join(batch)
        url = f'https://qt.gtimg.cn/q={query}'

        try:
            r = session.get(url, timeout=10)
            r.encoding = 'gbk'

            for code in batch:
                try:
                    prefix = f'v_{code}="'
                    idx = r.text.find(prefix)
                    if idx < 0:
                        continue
                    start = idx + len(prefix)
                    end = r.text.find('"', start)
                    raw = r.text[start:end]
                    parts = raw.split('~')
                    if len(parts) < 33:
                        continue

                    name = parts[1]
                    try:
                        price = float(parts[3]) if parts[3] not in ('', '-') else 0.0
                    except (ValueError, TypeError):
                        price = 0.0
                    try:
                        prev_close = float(parts[4]) if parts[4] not in ('', '-') else 0.0
                    except (ValueError, TypeError):
                        prev_close = 0.0
                    try:
                        change_pct = float(parts[32]) if parts[32] not in ('', '-') else 0.0
                    except (ValueError, TypeError):
                        change_pct = 0.0
                    try:
                        amount = float(parts[37]) if len(parts) > 37 and parts[37] not in ('', '-') else 0.0
                    except (ValueError, TypeError):
                        amount = 0.0
                    try:
                        # [44]=估算市值(亿元), [78]=估算净值(IOPV), [72]=总市值(元)
                        market_cap_yi = float(parts[44]) if len(parts) > 44 and parts[44] not in ('', '-') else 0.0
                        iopv = float(parts[78]) if len(parts) > 78 and parts[78] not in ('', '-') else 0.0
                        total_market_cap = float(parts[72]) if len(parts) > 72 and parts[72] not in ('', '-') else 0.0
                    except (ValueError, TypeError):
                        market_cap_yi = 0.0
                        iopv = 0.0
                        total_market_cap = 0.0

                    results.append({
                        'name': name,
                        'code': code,
                        'price': price,
                        'prev_close': prev_close,
                        'change_pct': change_pct,
                        'amount': amount,       # 成交额（万元）
                        'market_cap_yi': market_cap_yi,   # 估算市值（亿元）
                        'iopv': iopv,           # 估算净值 IOPV（元）
                        'total_market_cap': total_market_cap,  # 总市值（元）
                        'source': 'tencent',
                    })
                except Exception:
                    continue
        except Exception:
            continue

    return results


def fetch_etf_monthly_flows() -> Dict[str, Dict[str, float]]:
    """
    获取主要ETF近一年每月净流入/流出数据
    资金流向估算：日净流入 ≈ (收盘价-开盘价)×成交量，再按月汇总
    返回: {etf_code: {month_str: flow_billion_yuan}}
    """
    import pandas as pd
    import datetime
    session = requests.Session()
    session.trust_env = False

    # ETF 列表：(腾讯代码, 中文名)
    etf_list = [
        ('sh510300', '沪深300ETF'),
        ('sh510500', '中证500ETF'),
        ('sz159915', '创业板ETF'),
        ('sh510050', '上证50ETF'),
        ('sh512880', '证券ETF'),
        ('sh512760', '芯片ETF'),
        ('sh512690', '酒ETF'),
        ('sh515000', '科技ETF'),
        ('sh512010', '医药ETF'),
        ('sh512660', '军工ETF'),
        ('sh510880', '红利ETF华泰柏瑞'),
        ('sz159998', '农业ETF平安'),
    ]

    results = {}  # {etf_code: {month: flow_billion}}

    # 腾讯K线接口，每次最多320条日K（约1.3年）
    url_tpl = 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get?_var=kline_dayqfq&param={code},day,,,320,qfq'
    for code, name in etf_list:
        try:
            r = session.get(url_tpl.format(code=code), timeout=15)
            text = r.text
            if text.startswith('kline_dayqfq='):
                text = text[len('kline_dayqfq='):]
            data = json.loads(text)
            qfqday = data.get('data', {}).get(code, {}).get('qfqday', [])
            if not qfqday:
                qfqday = data.get('data', {}).get(code, {}).get('day', [])

            records = []
            for item in qfqday:
                if len(item) < 9:
                    continue
                try:
                    date = item[0]            # YYYY-MM-DD
                    open_p = float(item[1])  # 前复权开盘价（元）
                    close_p = float(item[2])  # 前复权收盘价（元）
                    # amt=成交额(万元), vol=成交量(万股)
                    # 均价(元) ≈ amt/vol × 100
                    amt = float(item[8])   # 成交额，万元
                    vol = float(item[5])   # 成交量，万股
                    # 日净流入(亿元) = 成交额(万元) × 涨跌幅 / 100 / 10000
                    # 涨跌幅 = (收盘-开盘)/收盘
                    if close_p > 0 and amt > 0:
                        pct_chg = (close_p - open_p) / close_p  # 比例
                        flow_yi = amt * pct_chg / 100   # 万元 -> 亿元
                        month = date[:7]  # YYYY-MM
                        records.append({'month': month, 'flow': flow_yi})
                except Exception:
                    continue

            if records:
                df = pd.DataFrame(records)
                monthly = df.groupby('month')['flow'].sum().to_dict()
                results[code] = monthly

        except Exception:
            continue

    return results


def fetch_etf_daily_flows() -> Dict[str, List[Dict]]:
    """
    获取主要ETF近30个交易日每日净流入/流出数据
    返回: {etf_code: [{date: str, flow: float}, ...]}
    """
    session = requests.Session()
    session.trust_env = False

    etf_list = [
        ('sh510300', '沪深300ETF'),
        ('sh510500', '中证500ETF'),
        ('sz159915', '创业板ETF'),
        ('sh510050', '上证50ETF'),
        ('sh512880', '证券ETF'),
        ('sh512760', '芯片ETF'),
        ('sh512690', '酒ETF'),
        ('sh515000', '科技ETF'),
        ('sh512010', '医药ETF'),
        ('sh512660', '军工ETF'),
        ('sh510880', '红利ETF华泰柏瑞'),
        ('sz159998', '农业ETF平安'),
    ]

    results = {}  # {etf_code: [{date, flow}, ...]}

    url_tpl = 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get?_var=kline_dayqfq&param={code},day,,,60,qfq'
    for code, name in etf_list:
        try:
            r = session.get(url_tpl.format(code=code), timeout=15)
            text = r.text
            if text.startswith('kline_dayqfq='):
                text = text[len('kline_dayqfq='):]
            data = json.loads(text)
            qfqday = data.get('data', {}).get(code, {}).get('qfqday', [])
            if not qfqday:
                qfqday = data.get('data', {}).get(code, {}).get('day', [])

            records = []
            for item in qfqday:  # qfqday 本身是从旧到新排列好的
                if len(item) < 9:
                    continue
                try:
                    date = item[0]          # YYYY-MM-DD
                    open_p = float(item[1])
                    close_p = float(item[2])
                    amt = float(item[8])    # 成交额（万元）
                    if close_p > 0 and amt > 0:
                        pct_chg = (close_p - open_p) / close_p
                        flow_yi = amt * pct_chg / 100  # 万元 -> 亿元
                        records.append({'date': date, 'flow': flow_yi})
                except Exception:
                    continue

            if records:
                results[code] = records[-30:]  # 取最近30条
        except Exception:
            continue

    return results


def fetch_sector_data() -> Dict[str, List[Dict]]:
    """
    获取东财行业板块数据（名称、涨跌幅、主力净流入）
    """
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            cols = df.columns.tolist()
            pct_col = None
            name_col = None
            for c in cols:
                c_lower = c.lower()
                if 'pct' in c_lower or 'change' in c_lower or '涨跌幅' in c:
                    pct_col = c
                if 'name' in c_lower or '板块' in c or '行业' in c:
                    name_col = c
            if not pct_col:
                pct_col = [c for c in cols if c not in ['代码', '代码']][0]

            df = df.sort_values(pct_col, ascending=False)
            gainers = df.head(10)
            losers = df.tail(10).iloc[::-1]

            return {
                'gainers': gainers.to_dict('records'),
                'losers': losers.to_dict('records'),
            }
    except Exception as e:
        logger.debug(f"行业板块获取失败: {e}")

    return {'gainers': [], 'losers': []}


def fetch_sector_flow_data() -> List[Dict]:
    """
    从东财API获取各行业板块实时资金流向
    f62=主力净流入（元）, f3=涨跌幅（%）
    返回: [{name, code, price, change_pct, flow_yi}, ...] 按净流入降序
    """
    import re

    # ── 方案1：东财API ──────────────────────────────────────
    def _try_eastmoney():
        session = requests.Session()
        session.trust_env = False
        url = (
            'https://push2.eastmoney.com/api/qt/clist/get?'
            'pn=1&pz=30&po=1&np=1&fltt=2&invt=2&fid=f62&'
            'fs=m%3A90+t%3A2&'
            'fields=f12,f14,f2,f3,f62'
        )
        headers = {
            'Referer': 'https://data.eastmoney.com/',
            'User-Agent': 'Mozilla/5.0'
        }
        r = session.get(url, headers=headers, timeout=8)
        r.encoding = r.apparent_encoding
        text = r.text
        m = re.match(r'jQuery\((.*)\)', text, re.DOTALL)
        if m:
            text = m.group(1)
        data = json.loads(text)
        diff = data.get('data', {}).get('diff', [])
        results = []
        for item in diff:
            try:
                name = str(item.get('f14', ''))
                code = str(item.get('f12', ''))
                if not name or not code:
                    continue
                results.append({
                    'name': name,
                    'code': code,
                    'price': float(item.get('f2', 0)),
                    'change_pct': float(item.get('f3', 0)),
                    'flow_yi': float(item.get('f62', 0)) / 1e8,
                })
            except Exception:
                continue
        results.sort(key=lambda x: x['flow_yi'], reverse=True)
        return results

    # ── 方案2：新浪API（板块资金流） ────────────────────────
    def _try_sina():
        session = requests.Session()
        session.trust_env = False
        headers = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}
        # 新浪板块行情接口（BK_开头）
        codes = 'BK0428,BK0430,BK0440,BK0441,BK0442,BK0443,BK0444,BK0445,BK0446,BK0447,BK0448,BK0449,BK0450,BK0451,BK0452,BK0453,BK0454,BK0455,BK0456,BK0457,BK0458,BK0459,BK0460,BK0461,BK0462,BK0463,BK0464,BK0465,BK0466,BK0467,BK0468,BK0469,BK0470'
        url = f'https://hq.sinajs.cn/list={codes}'
        r = session.get(url, headers=headers, timeout=8)
        r.encoding = 'gbk'
        results = []
        for line in r.text.strip().split('\n'):
            try:
                parts = line.split('=')
                if len(parts) < 2:
                    continue
                code = parts[0].replace('var hq_str_', '').strip()
                val = parts[1].strip('";\n')
                fields = val.split(',')
                if len(fields) < 10:
                    continue
                name = fields[0]
                price = float(fields[1]) if fields[1] else 0
                pct = float(fields[3]) if fields[3] else 0
                amount = float(fields[9]) if len(fields) > 9 and fields[9] else 0  # 成交额（万元）
                flow_yi = amount * pct / 100  # 估算净流入
                results.append({
                    'name': name,
                    'code': code,
                    'price': price,
                    'change_pct': pct,
                    'flow_yi': flow_yi,
                })
            except Exception:
                continue
        results.sort(key=lambda x: x['flow_yi'], reverse=True)
        return results

    # 按优先级尝试
    for src_name, src_fn in [
        ('eastmoney', _try_eastmoney),
        ('sina', _try_sina),
    ]:
        try:
            result = src_fn()
            if result:
                logger.debug(f"板块资金流向获取成功: {src_name}, {len(result)}条")
                return result
        except Exception as e:
            logger.debug(f"板块资金流向{src_name}失败: {e}")
            continue

    # 所有 API 失败,返回空列表 (UI 会显示警告,不再用 random 假装有数据)
    logger.debug("板块资金流向所有源失败,返回 [] (UI 将显示警告)")
    return []


# ─────────────────────────────────────────────────────────────────────────────
# 全市场成交额集中度指标（Top5% 成交额占比）
# 指标：每天成交额前5%的股票 / 全市场总成交额 × 100%
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
from datetime import datetime, timedelta
import time as _time

_concentration_cache: Dict[str, float] = {}
_concentration_history: List[Dict] = []


def fetch_top5_concentration() -> Dict:
    """
    获取当日全市场成交额集中度（前5%个股成交额占比）
    返回: {'date': str, 'concentration': float, 'total_stocks': int,
           'top5_stocks': int, 'top5_amount': float, 'total_amount': float}
    """
    import os
    os.environ['NO_PROXY'] = '*'

    # ── 方案1：东财全市场实时行情（成交额字段：f6）───────────
    def _try_eastmoney_spot():
        session = requests.Session()
        session.trust_env = False
        headers = {
            'Referer': 'https://data.eastmoney.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        # 沪深北三市全市场，f6=成交额（元）
        url = (
            'https://push2.eastmoney.com/api/qt/clist/get?'
            'pn=1&pz=5000&po=1&np=1&fltt=2&invt=2&fid=f6&'
            'fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23&'
            'fields=f12,f14,f6,f8,f3'
        )
        r = session.get(url, headers=headers, timeout=15)
        r.encoding = 'utf-8'
        data = r.json()
        stocks = data.get('data', {}).get('diff', [])
        if not stocks:
            return None

        total_amount = 0.0
        valid = []
        for s in stocks:
            try:
                amt = float(s.get('f6', 0) or 0)
                if amt <= 0:
                    continue
                valid.append({'code': str(s.get('f12', '')), 'name': str(s.get('f14', '')), 'amount': amt})
                total_amount += amt
            except Exception:
                continue

        if not valid or total_amount <= 0:
            return None

        # 按成交额降序，取前5%
        valid.sort(key=lambda x: x['amount'], reverse=True)
        n_top = max(1, int(len(valid) * 0.05))
        top5_amount = sum(x['amount'] for x in valid[:n_top])
        concentration = (top5_amount / total_amount) * 100

        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'concentration': concentration,
            'total_stocks': len(valid),
            'top5_stocks': n_top,
            'top5_amount': top5_amount / 1e8,   # 转为亿元
            'total_amount': total_amount / 1e8,  # 转为亿元
            'source': 'eastmoney',
        }

    # ── 方案2：akshare全市场股票列表+新浪批量实时行情─────────
    def _try_akshare_sina():
        try:
            import akshare as ak
            stock_list = ak.stock_info_a_code_name()
            codes_raw = stock_list['code'].tolist()
        except Exception:
            return None

        # akshare返回纯数字代码，补上前缀：沪市600/601/603/605/688开头 → sh，深市000/001/002/003/300开头 → sz
        codes = []
        for c in codes_raw:
            c = str(c).zfill(6)
            if c.startswith(('600', '601', '603', '605', '688')):
                codes.append('sh' + c)
            elif c.startswith(('000', '001', '002', '003', '300')):
                codes.append('sz' + c)

        if not codes:
            return None

        session = requests.Session()
        headers = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}
        total_amount = 0.0
        valid = []

        # 新浪每批50个code（留余量），全量获取不设上限
        batch_size = 50
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i+batch_size]
            codes_param = ','.join(batch)
            url = f'https://hq.sinajs.cn/list={codes_param}'
            try:
                r = session.get(url, headers=headers, timeout=20)
                r.encoding = 'gbk'
                for line in r.text.strip().split('\n'):
                    if '="";' in line or '=""' in line.split('=')[-1]:
                        continue
                    parts = line.split('"')
                    if len(parts) < 2:
                        continue
                    fields = parts[1].split(',')
                    if len(fields) < 10:
                        continue
                    try:
                        # 新浪字段：8=成交额（元）
                        code_raw = line.split('var hq_str_')[1].split('=')[0].strip()
                        amount = float(fields[8]) if fields[8] else 0.0
                        if amount > 0:
                            valid.append({'code': code_raw, 'amount': amount})
                            total_amount += amount
                    except Exception:
                        continue
            except Exception as ex:
                logger.debug(f"Sina batch {i//batch_size} failed: {ex}")
                continue
            _time.sleep(0.08)  # 加快批量请求

        if not valid or total_amount <= 0:
            return None

        valid.sort(key=lambda x: x['amount'], reverse=True)
        n_top = max(1, int(len(valid) * 0.05))
        top5_amount = sum(x['amount'] for x in valid[:n_top])
        concentration = (top5_amount / total_amount) * 100

        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'concentration': concentration,
            'total_stocks': len(valid),
            'top5_stocks': n_top,
            'top5_amount': top5_amount / 1e8,   # 元→亿元
            'total_amount': total_amount / 1e8,  # 元→亿元
            'source': 'sina_batch',
        }

    # ── 方案3：腾讯 qt.gtimg.cn 批量（fallback #3）───────────────
    def _try_tencent_batch():
        """用 akshare 拿全市场代码，再分批调腾讯 qt.gtimg.cn 拿成交额"""
        try:
            import akshare as ak
            stock_list = ak.stock_info_a_code_name()
            codes_raw = [str(c).zfill(6) for c in stock_list['code'].tolist()]
        except Exception:
            return None

        # 补前缀：沪市 600/601/603/605/688 → sh，深市 → sz
        codes = []
        for c in codes_raw:
            if c.startswith(('600', '601', '603', '605', '688')):
                codes.append('sh' + c)
            elif c.startswith(('000', '001', '002', '003', '300')):
                codes.append('sz' + c)
        if not codes:
            return None

        session = requests.Session()
        headers = {
            'Referer': 'https://stockapp.finance.qq.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        total_amount = 0.0
        valid = []
        batch_size = 50
        # 最多拉 80 批 ≈ 4000 只，覆盖全市场 99% 成交额；超过不再拉（避免超时）
        max_batches = 80
        for i in range(0, min(len(codes), batch_size * max_batches), batch_size):
            batch = codes[i:i+batch_size]
            try:
                r = session.get(
                    f'https://qt.gtimg.cn/q={",".join(batch)}',
                    headers=headers, timeout=8,
                )
                r.encoding = 'utf-8'
                for line in r.text.strip().split('\n'):
                    if '="";' in line or '=""' in line.split('=')[-1]:
                        continue
                    parts = line.split('"')
                    if len(parts) < 2:
                        continue
                    fields = parts[1].split('~')
                    if len(fields) < 38:
                        continue
                    try:
                        # 腾讯字段：[6]=当前价，[37]=成交额（元），[38]=成交额（元，与37冗余）
                        amount = float(fields[37]) if fields[37] else 0.0
                        if amount > 0:
                            valid.append({'amount': amount})
                            total_amount += amount
                    except Exception:
                        continue
            except Exception as ex:
                logger.debug(f"Tencent batch {i//batch_size} failed: {ex}")
                continue
            _time.sleep(0.05)

        if not valid or total_amount <= 0:
            return None

        valid.sort(key=lambda x: x['amount'], reverse=True)
        n_top = max(1, int(len(valid) * 0.05))
        top5_amount = sum(x['amount'] for x in valid[:n_top])
        concentration = (top5_amount / total_amount) * 100

        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'concentration': concentration,
            'total_stocks': len(valid),
            'top5_stocks': n_top,
            'top5_amount': top5_amount / 1e8,
            'total_amount': total_amount / 1e8,
            'source': 'tencent_batch',
        }

    # ── 优先级链:东财(快) → 新浪(稳) → 腾讯(兜底) ──
    # 各自独立 try,失败记录日志继续下一个;任一成功立即返回
    candidates = [
        ('eastmoney', _try_eastmoney_spot),
        ('akshare_sina', _try_akshare_sina),
        ('tencent_batch', _try_tencent_batch),
    ]
    for src_name, src_fn in candidates:
        try:
            result = src_fn()
            if result and result.get('concentration', 0) > 0:
                # 给没有 source 字段的补一个,方便 UI 区分
                result.setdefault('source', src_name)
                logger.debug(f"Top5%集中度获取成功: {src_name} → {result['concentration']:.2f}%")
                return result
        except Exception as e:
            logger.debug(f"Top5%集中度{src_name}失败: {e}")
            continue

    logger.debug("Top5%集中度所有源失败,返回 None (UI 将降级展示)")
    return None


# ── 持久化历史缓存 (跨 session 累积) ──
# 优先尝试 /mount/src/autogenlit/.cache (Streamlit Cloud writable 路径),
# 否则用项目根 .cache,再否则用临时目录
def _history_cache_path() -> Optional[str]:
    """获取持久化缓存文件路径(根据运行环境选择可写位置)"""
    import platform
    is_linux = platform.system() == 'Linux'
    candidates = []
    # Streamlit Cloud 路径:只在 Linux 上尝试(Windows 上会假成功但不真写)
    if is_linux:
        candidates.append('/mount/src/autogenlit/.cache/concentration_history.json')
    # 本机项目根 (跨平台)
    candidates.append(str(Path(__file__).parent.parent.parent / '.cache' / 'concentration_history.json'))

    for c in candidates:
        try:
            d = os.path.dirname(c)
            os.makedirs(d, exist_ok=True)
            test = os.path.join(d, '.write_test')
            with open(test, 'w') as f:
                f.write('1')
            os.remove(test)
            return c
        except Exception:
            continue
    return None


def _load_history_from_disk() -> List[Dict]:
    """从磁盘读取历史缓存"""
    path = _history_cache_path()
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_history_to_disk(history: List[Dict]):
    """持久化历史缓存到磁盘"""
    path = _history_cache_path()
    if not path:
        return
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.debug(f"持久化集中度历史失败: {e}")


# 模块加载时即从磁盘恢复(如果有的话)
if not _concentration_history:
    _concentration_history = _load_history_from_disk()


def get_concentration_history(n_days: int = 90) -> List[Dict]:
    """
    返回近N个交易日的集中度历史数据。
    从磁盘 JSON 缓存恢复(跨 session 累积);无缓存则返回 []。
    """
    # 优先用内存,空的话从磁盘读
    hist = _concentration_history if _concentration_history else _load_history_from_disk()
    if hist and not _concentration_history:
        # 同步到内存
        _concentration_history.extend(hist)
    return hist[-n_days:] if hist else []


def update_concentration_cache():
    """每日更新一次集中度数据,持久化到磁盘供后续 session 使用"""
    global _concentration_cache, _concentration_history
    today = datetime.now().strftime('%Y-%m-%d')
    # 同一天不重复拉
    if _concentration_cache.get('date') == today and _concentration_cache.get('latest'):
        return _concentration_cache['latest']
    result = fetch_top5_concentration()
    if result:
        _concentration_cache['date'] = today
        _concentration_cache['latest'] = result
        # 去重:如果今天已有,替换
        _concentration_history = [
            h for h in _concentration_history if h.get('date') != today
        ]
        _concentration_history.append(result)
        if len(_concentration_history) > 365:
            _concentration_history = _concentration_history[-365:]
        # 持久化
        _save_history_to_disk(_concentration_history)
        return result
    return None
