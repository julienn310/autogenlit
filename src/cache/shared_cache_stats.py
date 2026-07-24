"""
共享缓存统计模块 - MongoDB 实现（Streamlit Cloud 兼容）
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


def _get_mongo_uri() -> str:
    """获取 MongoDB 连接字符串，优先从 st.secrets 读"""
    try:
        return st.secrets["MONGODB_URI"]
    except Exception:
        # 本地开发回退到空，模块仍可导入
        return ""


def _get_collection():
    """懒加载 MongoDB collection（连接池由 pymongo 自动管理）"""
    uri = _get_mongo_uri()
    if not uri:
        return None
    client = MongoClient(uri, appName="a_stock_research")
    db = client.get_database("stock_cache")
    return db["cache_stats"]


class SharedCacheStats:
    """共享缓存统计（MongoDB 版，跨实例/跨用户持久化）"""

    def __init__(self):
        self._col = None

    @property
    def col(self):
        if self._col is None:
            self._col = _get_collection()
        return self._col

    def record_hit(self, symbol: str) -> None:
        if self.col is None:
            return
        with _lock:
            self.col.update_one(
                {"_id": "total_hits"},
                {"$inc": {"value": 1}},
                upsert=True,
            )
            self.col.update_one(
                {"_id": f"symbol:{symbol}"},
                {"$inc": {"analysis_count": 1}, "$set": {"symbol": symbol}},
                upsert=True,
            )

    def record_miss(self) -> None:
        if self.col is None:
            return
        with _lock:
            self.col.update_one(
                {"_id": "total_misses"},
                {"$inc": {"value": 1}},
                upsert=True,
            )

    def get_stats(self) -> dict:
        if self.col is None:
            return {"total_hits": 0, "total_misses": 0, "cached_symbols": 0}
        with _lock:
            hits = self.col.find_one({"_id": "total_hits"})
            misses = self.col.find_one({"_id": "total_misses"})
            cached_count = self.col.count_documents(
                {"_id": {"$regex": "^symbol:"}}
            )
            return {
                "total_hits": hits["value"] if hits else 0,
                "total_misses": misses["value"] if misses else 0,
                "cached_symbols": cached_count,
            }

    def is_cached(self, symbol: str) -> bool:
        if self.col is None:
            return False
        with _lock:
            return self.col.find_one({"_id": f"symbol:{symbol}"}) is not None

    def get_cached_data(self, symbol: str) -> Optional[dict]:
        if self.col is None:
            return None
        with _lock:
            doc = self.col.find_one({"_id": f"symbol:{symbol}"})
            return doc.get("data") if doc else None

    def set_cached_data(self, symbol: str, data: dict) -> None:
        if self.col is None:
            return
        with _lock:
            self.col.update_one(
                {"_id": f"symbol:{symbol}"},
                {
                    "$set": {
                        "symbol": symbol,
                        "data": data,
                        "cached_at": time.time(),
                    },
                    "$setOnInsert": {
                        "analysis_count": 1,
                    },
                },
                upsert=True,
            )

    def get_ranking(self, limit: int = 20) -> list:
        if self.col is None:
            return []
        with _lock:
            cursor = (
                self.col.find({"_id": {"$regex": "^symbol:"}})
                .sort("analysis_count", -1)
                .limit(limit)
            )
            result = []
            for doc in cursor:
                result.append({
                    "symbol": doc.get("symbol", ""),
                    "name": (
                        doc.get("data", {})
                        .get("info", {})
                        .get("name", "")
                        if isinstance(doc.get("data"), dict)
                        else ""
                    ),
                    "count": doc.get("analysis_count", 0),
                    "cached_at": doc.get("cached_at", 0),
                })
            return result


# 全局单例
_shared_stats: Optional[SharedCacheStats] = None


def get_shared_cache_stats() -> SharedCacheStats:
    """获取共享缓存统计单例"""
    global _shared_stats
    if _shared_stats is None:
        _shared_stats = SharedCacheStats()
    return _shared_stats
