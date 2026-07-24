"""
共享缓存统计模块 - MongoDB 实现（Streamlit Cloud 兼容）
能连 MongoDB 就用，连不上自动降级到内存
"""

import time
import threading
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
_memory_cache = {}  # symbol -> {"data": ..., "cached_at": ..., "analysis_count": ...}
_use_memory = False


def _get_mongo_collection():
    """尝试连接 MongoDB，失败则返回 None"""
    try:
        uri = st.secrets.get("MONGODB_URI", "")
        if not uri:
            return None
        client = MongoClient(
            uri,
            appName="a_stock_research",
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            tlsAllowInvalidCertificates=True,
        )
        # 尝试 ping 验证连通性
        client.admin.command("ping")
        return client.get_database("stock_cache")["cache_stats"]
    except Exception:
        return None


def _init_mongo():
    global _use_memory
    if MONGODB_AVAILABLE:
        col = _get_mongo_collection()
        if col is not None:
            return col
    _use_memory = True
    return None


# 启动时初始化
_col = _init_mongo()


class SharedCacheStats:
    """共享缓存统计（MongoDB 主用，内存降级）"""

    @property
    def col(self):
        return _col

    def record_hit(self, symbol: str) -> None:
        if _use_memory or self.col is None:
            with _lock:
                _memory_stats["total_hits"] = _memory_stats.get("total_hits", 0) + 1
                if symbol in _memory_cache:
                    _memory_cache[symbol]["analysis_count"] += 1
            return
        try:
            with _lock:
                self.col.update_one({"_id": "total_hits"}, {"$inc": {"value": 1}}, upsert=True)
                self.col.update_one(
                    {"_id": f"symbol:{symbol}"},
                    {"$inc": {"analysis_count": 1}, "$set": {"symbol": symbol}},
                    upsert=True,
                )
        except Exception:
            self.record_hit(symbol)  # 重试内存

    def record_miss(self) -> None:
        if _use_memory or self.col is None:
            with _lock:
                _memory_stats["total_misses"] = _memory_stats.get("total_misses", 0) + 1
            return
        try:
            with _lock:
                self.col.update_one({"_id": "total_misses"}, {"$inc": {"value": 1}}, upsert=True)
        except Exception:
            self.record_miss()

    def get_stats(self) -> dict:
        if _use_memory or self.col is None:
            with _lock:
                return {
                    "total_hits": _memory_stats.get("total_hits", 0),
                    "total_misses": _memory_stats.get("total_misses", 0),
                    "cached_symbols": len(_memory_cache),
                }
        try:
            with _lock:
                hits = self.col.find_one({"_id": "total_hits"})
                misses = self.col.find_one({"_id": "total_misses"})
                cached_count = self.col.count_documents({"_id": {"$regex": "^symbol:"}})
                return {
                    "total_hits": hits["value"] if hits else 0,
                    "total_misses": misses["value"] if misses else 0,
                    "cached_symbols": cached_count,
                }
        except Exception:
            return self.get_stats()  # 降级

    def is_cached(self, symbol: str) -> bool:
        if _use_memory or self.col is None:
            return symbol in _memory_cache
        try:
            with _lock:
                return self.col.find_one({"_id": f"symbol:{symbol}"}) is not None
        except Exception:
            return self.is_cached(symbol)

    def get_cached_data(self, symbol: str) -> Optional[dict]:
        if _use_memory or self.col is None:
            entry = _memory_cache.get(symbol)
            return entry["data"] if entry else None
        try:
            with _lock:
                doc = self.col.find_one({"_id": f"symbol:{symbol}"})
                return doc.get("data") if doc else None
        except Exception:
            return self.get_cached_data(symbol)

    def set_cached_data(self, symbol: str, data: dict) -> None:
        if _use_memory or self.col is None:
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
            with _lock:
                self.col.update_one(
                    {"_id": f"symbol:{symbol}"},
                    {
                        "$set": {"symbol": symbol, "data": data, "cached_at": time.time()},
                        "$setOnInsert": {"analysis_count": 1},
                    },
                    upsert=True,
                )
        except Exception:
            self.set_cached_data(symbol, data)

    def get_ranking(self, limit: int = 20) -> list:
        if _use_memory or self.col is None:
            with _lock:
                sorted_symbols = sorted(
                    _memory_cache.items(),
                    key=lambda x: (x[1]["analysis_count"], x[1]["cached_at"]),
                    reverse=True,
                )
                return [
                    {
                        "symbol": sym,
                        "name": _memory_cache[sym].get("data", {}).get("info", {}).get("name", "") if isinstance(_memory_cache[sym].get("data"), dict) else "",
                        "count": _memory_cache[sym]["analysis_count"],
                        "cached_at": _memory_cache[sym]["cached_at"],
                    }
                    for sym, _ in sorted_symbols[:limit]
                ]
        try:
            with _lock:
                cursor = (
                    self.col.find({"_id": {"$regex": "^symbol:"}})
                    .sort("analysis_count", -1)
                    .limit(limit)
                )
                return [
                    {
                        "symbol": doc.get("symbol", ""),
                        "name": doc.get("data", {}).get("info", {}).get("name", "") if isinstance(doc.get("data"), dict) else "",
                        "count": doc.get("analysis_count", 0),
                        "cached_at": doc.get("cached_at", 0),
                    }
                    for doc in cursor
                ]
        except Exception:
            return self.get_ranking(limit)


_shared_stats: Optional[SharedCacheStats] = None


def get_shared_cache_stats() -> SharedCacheStats:
    global _shared_stats
    if _shared_stats is None:
        _shared_stats = SharedCacheStats()
    return _shared_stats
