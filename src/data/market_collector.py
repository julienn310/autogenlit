"""
市场行情数据采集 - 从腾讯/东财获取主要指数数据
"""

import requests
import logging
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
    # 全球指数
    'hkHSI': '恒生指数',
    'usIXIC': '纳斯达克综合',
    'usDJI': '道琼斯工业',
    'usINX': '标普500',
    'jpNKY': '日经225',
    'krKOSPI': '韩国综合',
    'sgSTI': '新加坡海峡时报',
    'ukFTSE': '英国富时100',
    'deDAX': '德国DAX',
    'frCAC': '法国CAC40',
    'auAS51': '澳大利亚标普200',
    'inNIFTY': '印度NIFTY50',
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

    return results


def fetch_sector_data() -> Dict[str, List[Dict]]:
    """
    尝试获取行业板块数据
    由于网络限制，优先使用可用接口

    Returns:
        {'gainers': [...], 'losers': [...]}
    """
    # 网络受限，尝试akshare
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            cols = df.columns.tolist()
            # 找涨跌幅列
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
