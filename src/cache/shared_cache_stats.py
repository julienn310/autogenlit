"""
共享缓存统计模块 - MongoDB 实现（Streamlit Cloud 兼容）
所有 MongoDB 操作均在线程池中执行，避免阻塞 Streamlit 主线程
"""

import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

try:
    from pymongo import MongoClient
    import streamlit as st
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False


_lock = threading.Lock()

# 内存降级存储
_memory_stats = {"total_hits": 0, "total_misses": 0}
_memory_cache = {}

# 基础热度股票（共56次，随机分配）
random.seed(42)
_BASE_CODES = ["688712", "603259", "002938", "600319", "300738", "301479", "301155", "688525"]
_BASE_NAMES = ["北芯生命", "药明康德", "鹏鼎控股", "亚星化学", "奥飞数据", "弘景光电", "海力风电", "佰维存储"]
_BASE_COUNTS = [random.randint(3, 12) for _ in range(8)]
diff = 56 - sum(_BASE_COUNTS)
_BASE_COUNTS[0] += diff
BASE_HOT_STOCKS = {code: {"name": name, "count": count}
                   for code, name, count in zip(_BASE_CODES, _BASE_NAMES, _BASE_COUNTS)}

# 全局单例 MongoClient + 线程池（进程级共享）
_mongo_client: Optional[MongoClient] = None
_mongo_col = None
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mongo_")


def _get_mongo_collection():
    """懒加载 MongoDB collection"""
    global _mongo_client, _mongo_col
    if not MONGODB_AVAILABLE:
        return None
    if _mongo_col is not None:
        return _mongo_col
    try:
        uri = st.secrets.get("MONGODB_URI", "")
        if not uri:
            return None
        if _mongo_client is None:
            _mongo_client = MongoClient(
                uri,
                appName="a_stock_research",
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                maxPoolSize=20,
                minPoolSize=1,
                maxIdleTimeMS=30000,
            )
        _mongo_col = _mongo_client.get_database("stock_cache")["cache_stats"]
        return _mongo_col
    except Exception:
        return None


def _call_mongo(fn, *args, timeout=5.0, **kwargs):
    """在线程池中执行 MongoDB 操作，超时则返回 None"""
    try:
        future = _executor.submit(fn, *args, **kwargs)
        return future.result(timeout=timeout)
    except (FuturesTimeoutError, TimeoutError):
        return None
    except Exception:
        return None


def _init_base_hotness(col):
    """初始化基础热度数据"""
    try:
        from pymongo import ReplaceOne
        ops = [
            ReplaceOne(
                {"_id": f"symbol:{code}"},
                {
                    "_id": f"symbol:{code}",
                    "symbol": code,
                    "name": info["name"],
                    "data": {"info": {"name": info["name"]}},
                    "cached_at": time.time(),
                    "analysis_count": info["count"],
                },
                upsert=True,
            )
            for code, info in BASE_HOT_STOCKS.items()
        ]
        col.bulk_write(ops, ordered=True)
        return True
    except Exception:
        return False


class SharedCacheStats:
    """共享缓存统计（MongoDB 主用，内存降级，线程池执行）"""

    def __init__(self):
        self._col = None
        self._base_initialized = False

    @property
    def col(self):
        if self._col is None:
            self._col = _get_mongo_collection()
        return self._col

    def _ensure_base_initialized(self):
        if self._base_initialized or self.col is None:
            return
        ok = _call_mongo(_init_base_hotness, self.col, timeout=10.0)
        if ok:
            self._base_initialized = True

    def record_hit(self, symbol: str) -> None:
        if self.col is None:
            with _lock:
                _memory_stats["total_hits"] = _memory_stats.get("total_hits", 0) + 1
                if symbol in _memory_cache:
                    _memory_cache[symbol]["analysis_count"] += 1
            return
        try:
            def _do_hit():
                self.col.update_one(
                    {"_id": "total_hits"}, {"$inc": {"value": 1}}, upsert=True
                )
                self.col.update_one(
                    {"_id": f"symbol:{symbol}"},
                    {"$inc": {"analysis_count": 1}, "$set": {"symbol": symbol}},
                    upsert=True,
                )
            _call_mongo(_do_hit, timeout=3.0)
        except Exception:
            pass

    def record_miss(self) -> None:
        if self.col is None:
            with _lock:
                _memory_stats["total_misses"] = _memory_stats.get("total_misses", 0) + 1
            return
        try:
            def _do_miss():
                self.col.update_one(
                    {"_id": "total_misses"}, {"$inc": {"value": 1}}, upsert=True
                )
            _call_mongo(_do_miss, timeout=3.0)
        except Exception:
            pass

    def get_stats(self) -> dict:
        self._ensure_base_initialized()
        if self.col is None:
            with _lock:
                total_analysis = sum(v["analysis_count"] for v in _memory_cache.values())
                return {
                    "total_hits": _memory_stats.get("total_hits", 0),
                    "total_misses": _memory_stats.get("total_misses", 0),
                    "total_analysis": total_analysis,
                    "cached_symbols": len(_memory_cache),
                }

        def _do_stats():
            hits = self.col.find_one({"_id": "total_hits"}, max_time_ms=3000)
            misses = self.col.find_one({"_id": "total_misses"}, max_time_ms=3000)
            cached_count = self.col.count_documents(
                {"_id": {"$regex": "^symbol:"}}, max_time_ms=3000
            )
            pipeline = [
                {"$match": {"_id": {"$regex": "^symbol:"}}},
                {"$group": {"_id": None, "total": {"$sum": "$analysis_count"}}},
            ]
            agg = list(self.col.aggregate(pipeline, maxTimeMS=3000))
            total_analysis = agg[0]["total"] if agg else 0
            return {
                "total_hits": hits["value"] if hits else 0,
                "total_misses": misses["value"] if misses else 0,
                "total_analysis": total_analysis,
                "cached_symbols": cached_count,
            }

        result = _call_mongo(_do_stats, timeout=6.0)
        if result is not None:
            return result
        return {"total_hits": 0, "total_misses": 0, "total_analysis": 0, "cached_symbols": 0}

    def is_cached(self, symbol: str) -> bool:
        if self.col is None:
            return symbol in _memory_cache
        try:
            def _do_check():
                return self.col.find_one(
                    {"_id": f"symbol:{symbol}"}, max_time_ms=3000
                ) is not None
            return _call_mongo(_do_check, timeout=4.0) or False
        except Exception:
            return False

    def get_cached_data(self, symbol: str) -> Optional[dict]:
        if self.col is None:
            entry = _memory_cache.get(symbol)
            return entry["data"] if entry else None
        try:
            def _do_get():
                doc = self.col.find_one(
                    {"_id": f"symbol:{symbol}"}, max_time_ms=3000
                )
                return doc.get("data") if doc else None
            return _call_mongo(_do_get, timeout=4.0)
        except Exception:
            return None

    def set_cached_data(self, symbol: str, data: dict) -> None:
        if self.col is None:
            with _lock:
                if symbol in _memory_cache:
                    _memory_cache[symbol] = {
                        "data": data,
                        "cached_at": time.time(),
                        "analysis_count": _memory_cache[symbol]["analysis_count"] + 1,
                    }
                else:
                    _memory_cache[symbol] = {
                        "data": data,
                        "cached_at": time.time(),
                        "analysis_count": 1,
                    }
            return
        try:
            def _do_set():
                self.col.update_one(
                    {"_id": f"symbol:{symbol}"},
                    {
                        "$set": {"symbol": symbol, "data": data, "cached_at": time.time()},
                        "$setOnInsert": {"analysis_count": 1},
                    },
                    upsert=True,
                    max_time_ms=5000,
                )
                if self.is_cached(symbol):
                    self.col.update_one(
                        {"_id": f"symbol:{symbol}"},
                        {"$inc": {"analysis_count": 1}},
                        max_time_ms=3000,
                    )
            _call_mongo(_do_set, timeout=6.0)
        except Exception:
            pass

    def get_ranking(self, limit: int = 20) -> list:
        self._ensure_base_initialized()
        if self.col is None:
            with _lock:
                sorted_symbols = sorted(
                    _memory_cache.items(),
                    key=lambda x: (x[1]["analysis_count"], x[1]["cached_at"]),
                    reverse=True,
                )
                return [
                    {
                        "symbol": sym,
                        "name": _memory_cache[sym].get("data", {}).get("info", {}).get("name", "")
                        if isinstance(_memory_cache[sym].get("data"), dict) else "",
                        "count": _memory_cache[sym]["analysis_count"],
                        "cached_at": _memory_cache[sym]["cached_at"],
                    }
                    for sym, _ in sorted_symbols[:limit]
                ]

        def _do_ranking():
            cursor = (
                self.col.find({"_id": {"$regex": "^symbol:"}}, max_time_ms=5000)
                .sort("analysis_count", -1)
                .limit(limit)
            )
            return [
                {
                    "symbol": doc.get("symbol", ""),
                    "name": doc.get("name") or (
                        doc.get("data", {}).get("info", {}).get("name", "")
                        if isinstance(doc.get("data"), dict) else ""
                    ),
                    "count": doc.get("analysis_count", 0),
                    "cached_at": doc.get("cached_at", 0),
                }
                for doc in cursor
            ]

        result = _call_mongo(_do_ranking, timeout=6.0)
        return result if result is not None else []


_shared_stats: Optional[SharedCacheStats] = None


def get_shared_cache_stats() -> SharedCacheStats:
    global _shared_stats
    if _shared_stats is None:
        _shared_stats = SharedCacheStats()
    return _shared_stats
