"""
回填「全市场成交额集中度」历史(近 N 个交易日) → data/concentration_history_seed.json

方法
----
分子 = 该日成交额最高的 Top-K 只之和,K = 全市场只数 × 5%
       K 用「全市场实时快照」的只数算(约 5200 → 260 只),
       不是池子只数的 5%(那会少算一个数量级,把集中度严重低估)
       每只成交额 = volume(股) × (open+high+low+close)/4
                    [新浪日线接口,对比 akshare 精确 amount 平均误差 0.24%]
分母 = 沪深两市当日股票成交总额
       沪市 stock_sse_deal_daily(date)(单位亿元) + 深市 stock_szse_summary(date)(单位元)

池子(pool)= 按回填日成交额排序的前 N 只,用于取样个股日线。
池子只数必须显著大于 K,才能保证「池内 Top-K」≈「全市场 Top-K」。

用法: python scripts/backfill_concentration.py [天数] [池子大小]
"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import requests  # noqa: E402

_local = threading.local()
POOL_CACHE = ROOT / '.cache' / 'backfill_pool.json'


def _session():
    if not hasattr(_local, 's'):
        s = requests.Session()
        s.trust_env = False
        s.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://finance.sina.com.cn/',
        })
        _local.s = s
    return _local.s


def fetch_universe():
    """东财全市场实时快照(分页) → [{code, name, amount}]"""
    from src.data.market_collector import _EM_FS, _is_a_share

    s = requests.Session()
    s.trust_env = False
    headers = {'Referer': 'https://data.eastmoney.com/', 'User-Agent': 'Mozilla/5.0'}
    base = 'https://push2.eastmoney.com/api/qt/clist/get?'
    query = f'po=1&np=1&fltt=2&invt=2&fid=f6&fs={_EM_FS}&fields=f12,f14,f6'

    out, total = [], None
    for page in range(1, 80):
        r = s.get(f'{base}pn={page}&pz=100&{query}', headers=headers, timeout=15)
        r.encoding = 'utf-8'
        data = (r.json().get('data') or {})
        if total is None:
            total = int(data.get('total') or 0)
        diff = data.get('diff') or []
        if not diff:
            break
        for it in diff:
            code = str(it.get('f12', ''))
            if not _is_a_share(code):
                continue
            try:
                amt = float(it.get('f6', 0) or 0)
            except (TypeError, ValueError):
                continue
            if amt > 0:
                out.append({'code': code, 'name': str(it.get('f14', '')), 'amount': amt})
        if total and len(out) >= total:
            break
        print(f'  ...已拉 {len(out)}/{total}', end='\r', flush=True)
    print()
    out.sort(key=lambda x: x['amount'], reverse=True)
    return out


def fetch_kline_amounts(code, datalen=70):
    """新浪日线 → {date_str: 成交额(元)}"""
    sym = ('sh' if code[0] in '6' else 'sz') + code
    try:
        r = _session().get(
            'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
            'CN_MarketData.getKLineData?symbol=%s&scale=240&ma=no&datalen=%d' % (sym, datalen),
            timeout=12)
        if r.status_code != 200:
            return {}
        rows = r.json()
    except Exception:
        return {}
    res = {}
    for row in rows or []:
        try:
            d = row['day'][:10]
            o, h, l, c, v = (float(row[k]) for k in ('open', 'high', 'low', 'close', 'volume'))
            if v <= 0:
                continue
            res[d] = v * ((o + h + l + c) / 4.0)
        except Exception:
            continue
    return res


def fetch_market_total(date_str):
    """沪深两市当日股票成交总额(元)"""
    import akshare as ak
    d = date_str.replace('-', '')
    a = b = 0.0
    try:
        sse = ak.stock_sse_deal_daily(date=d)
        row = sse[sse['单日情况'] == '成交金额']
        a = float(row['股票'].iloc[0]) * 1e8      # SSE 单位:亿元
    except Exception as e:
        print('    SSE 缺失 %s: %s' % (date_str, e))
    try:
        szse = ak.stock_szse_summary(date=d)
        b = float(szse[szse['证券类别'] == '股票']['成交金额'].iloc[0])   # SZSE 单位:元
    except Exception as e:
        print('    SZSE 缺失 %s: %s' % (date_str, e))
    return a + b


def trading_days(n):
    """最近 n 个交易日(以上证指数日线为准)"""
    import akshare as ak
    idx = ak.stock_zh_index_daily(symbol='sh000001')
    days = sorted({str(d)[:10] for d in idx['date'].tolist()})
    return days[-n:]


def build_pool(pool_size):
    """取头部池 + 池子日线(带磁盘缓存,重算时无需重新请求)"""
    if POOL_CACHE.exists():
        with open(POOL_CACHE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        if cache.get('pool_size') == pool_size:
            print('  复用缓存池子 (%s)' % cache.get('built_at'))
            return cache['market_size'], cache['hist']

    print('  拉全市场实时快照...')
    universe = fetch_universe()
    market_size = len(universe)
    pool = universe[:pool_size]
    print('  全市场 %d 只;池子 %d 只,占全市场成交额 %.1f%%' % (
        market_size, len(pool),
        sum(p['amount'] for p in pool) / sum(p['amount'] for p in universe) * 100))

    print('  拉池子逐股日线(并发 12)...')
    t0 = time.time()
    hist, done = {}, [0]

    def job(p):
        res = fetch_kline_amounts(p['code'])
        done[0] += 1
        if done[0] % 200 == 0:
            print('    ...%d/%d  %.0fs' % (done[0], len(pool), time.time() - t0), flush=True)
        return p['code'], res

    with ThreadPoolExecutor(max_workers=12) as ex:
        for code, res in ex.map(job, pool):
            if res:
                hist[code] = res
    print('  %d/%d 只取到日线,耗时 %.0fs' % (len(hist), len(pool), time.time() - t0))

    # 失败重试一轮(新浪偶发限流)
    missing = [p for p in pool if p['code'] not in hist]
    if missing:
        print('  重试 %d 只失败个股...' % len(missing))
        def job2(p):
            return p['code'], fetch_kline_amounts(p['code'])
        with ThreadPoolExecutor(max_workers=8) as ex:
            for code, res in ex.map(job2, missing):
                if res:
                    hist[code] = res
        print('  重试后共 %d/%d 只' % (len(hist), len(pool)))

    POOL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(POOL_CACHE, 'w', encoding='utf-8') as f:
        json.dump({
            'built_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'pool_size': pool_size,
            'market_size': market_size,
            'hist': hist,
        }, f, ensure_ascii=False)
    return market_size, hist


def main():
    n_days = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    pool_size = int(sys.argv[2]) if len(sys.argv) > 2 else 600

    print('=' * 68)
    print('集中度历史回填  天数=%d  池子=%d 只' % (n_days, pool_size))
    print('=' * 68)

    print('\n[1/4] 准备头部池...')
    market_size, hist = build_pool(pool_size)
    n_top = max(1, int(market_size * 0.05))
    print('  全市场 %d 只 → Top 5%% = %d 只(池子 %d 只,覆盖倍数 %.1fx)' % (
        market_size, n_top, len(hist), len(hist) / n_top))

    print('\n[2/4] 取最近 %d 个交易日...' % n_days)
    days = trading_days(n_days)
    print('  %s ... %s (%d 天)' % (days[0], days[-1], len(days)))

    print('\n[3/4] 逐日计算集中度...')
    out = []
    for d in days:
        day_amts = []
        for series in hist.values():
            a = series.get(d)
            if a and a > 0:
                day_amts.append(a)
        if len(day_amts) < n_top:
            print('  %s 池内样本不足(%d < %d),跳过' % (d, len(day_amts), n_top))
            continue
        total = fetch_market_total(d)
        if total <= 0:
            print('  %s 交易所成交额缺失,跳过' % d)
            continue
        day_amts.sort(reverse=True)
        top_sum = sum(day_amts[:n_top])
        out.append({
            'date': d,
            'concentration': (top_sum / total) * 100,
            'total_stocks': market_size,
            'top5_stocks': n_top,
            'top5_amount': top_sum / 1e8,
            'total_amount': total / 1e8,
            'source': 'backfill',
        })
        print('  %s  集中度=%6.2f%%  分子=%7.0f亿  分母=%7.0f亿  池内=%d 只' % (
            d, out[-1]['concentration'], top_sum / 1e8, total / 1e8, len(day_amts)))

    print('\n[4/4] 写入种子文件...')
    out_path = ROOT / 'data' / 'concentration_history_seed.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pool_size': pool_size,
        'market_size': market_size,
        'method': '新浪日线推算成交额(误差<1%) + 交易所每日成交总额',
        'history': out,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print('  已写入 %s (%d 条)' % (out_path, len(out)))
    if out:
        vals = [x['concentration'] for x in out]
        print('  区间集中度 %.2f%% ~ %.2f%%  均值 %.2f%%' % (
            min(vals), max(vals), sum(vals) / len(vals)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
