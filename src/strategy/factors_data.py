"""
因子库聚合器 — 把 5 个因子模块合并成扁平 list,支持搜索与分类过滤
"""
from __future__ import annotations
from typing import List, Dict, Optional

from .factors import alpha_101, gtja_191, qlib_158, academic, financial_quality


CATEGORIES = {
    'alpha_101':       ('Alpha 101',     alpha_101.FACTORS),
    'gtja_191':        ('国泰 191',      gtja_191.FACTORS),
    'qlib_158':        ('Qlib 158',      qlib_158.FACTORS),
    'academic':        ('学术因子',      academic.FACTORS),
    'financial_quality': ('财务质量面',   financial_quality.FACTORS),
}


def get_all_factors() -> List[Dict]:
    """返回所有 74 个因子,每条带 _cat/_cat_label 字段"""
    out = []
    for cat_key, (label, factors) in CATEGORIES.items():
        for f in factors:
            item = dict(f)
            item['_cat'] = cat_key
            item['_cat_label'] = label
            out.append(item)
    return out


def search_factors(query: str = "", categories: Optional[List[str]] = None) -> List[Dict]:
    """
    按关键词搜索因子
    - query: 匹配 name / formula / 原理 / 如何使用 / 注意事项
    - categories: 限制分类列表,None 或空列表表示全部
    """
    cats = categories or list(CATEGORIES.keys())
    q = (query or '').strip().lower()
    results = []
    for f in get_all_factors():
        if f['_cat'] not in cats:
            continue
        if not q:
            results.append(f)
            continue
        haystack = ' '.join([
            str(f.get('name', '')),
            str(f.get('formula', '')),
            str(f.get('原理', '')),
            str(f.get('如何使用', '')),
            str(f.get('注意事项', '')),
        ]).lower()
        if q in haystack:
            results.append(f)
    return results
