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


def _get_mongo_collection():
    """懒加载 MongoDB collection，失败返回 None"""
    if not MONGODB_AVAILABLE:
        return None
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
        )
        client.admin.command("ping")
        return client.get_database("stock_cache")["cache_stats"]
    except Exception:
        return None


class SharedCacheStats:
    """共享缓存统计（MongoDB 主用，内存降级，懒加载）"""

    def __init__(self):
        self._col = None  # 懒加载，首次使用时才连接

    @property
    def col(self):
        if self._col is None:
            self._col = _get_mongo_collection()
        return self._col

    @property
    def use_memory(self):
        """检查是否应该使用内存模式（MongoDB 不可用时）"""
        return self._col is None and MONGODB_AVAILABLE

    def record_hit(self, symbol: str) -> None:
        if self.col is None:
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
            pass

    def record_miss(self) -> None:
        if self.col is None:
            with _lock:
                _memory_stats["total_misses"] = _memory_stats.get("total_misses", 0) + 1
            return
        try:
            with _lock:
                self.col.update_one({"_id": "total_misses"}, {"$inc": {"value": 1}}, upsert=True)
        except Exception:
            pass

    def get_stats(self) -> dict:
        if self.col is None:
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
            return {"total_hits": 0, "total_misses": 0, "cached_symbols": 0}

    def is_cached(self, symbol: str) -> bool:
        if self.col is None:
            return symbol in _memory_cache
        try:
            with _lock:
                return self.col.find_one({"_id": f"symbol:{symbol}"}) is not None
        except Exception:
            return False

    def get_cached_data(self, symbol: str) -> Optional[dict]:
        if self.col is None:
            entry = _memory_cache.get(symbol)
            return entry["data"] if entry else None
        try:
            with _lock:
                doc = self.col.find_one({"_id": f"symbol:{symbol}"})
                return doc.get("data") if doc else None
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
            with _lock:
                self.col.update_one(
                    {"_id": f"symbol:{symbol}"},
                    {
                        "$set": {"symbol": symbol, "data": data, "cached_at": time.time()},
                        "$setOnInsert": {"analysis_count": 1},
                    },
                    upsert=True,
                )
                # 如果是更新已有记录，额外 increment analysis_count
                if self.is_cached(symbol):
                    self.col.update_one(
                        {"_id": f"symbol:{symbol}"},
                        {"$inc": {"analysis_count": 1}},
                    )
        except Exception:
            pass

    def get_ranking(self, limit: int = 20) -> list:
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
            return []


_shared_stats: Optional[SharedCacheStats] = None


def get_shared_cache_stats() -> SharedCacheStats:
    global _shared_stats
    if _shared_stats is None:
        _shared_stats = SharedCacheStats()
    return _shared_stats
