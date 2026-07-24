"""
共享缓存统计模块 - 内存实现（Streamlit Cloud 兼容）
所有用户共享同一内存副本（进程内），单实例部署最稳定
"""

import threading
import time
from typing import Optional

_lock = threading.Lock()

# 进程内共享数据（单实例 Streamlit Cloud 最稳定）
_cache_stats: dict = {
    "total_hits": 0,
    "total_misses": 0,
}
_symbol_cache: dict = {}  # symbol -> {"data": ..., "cached_at": ..., "analysis_count": ...}


class SharedCacheStats:
    """轻量级共享缓存统计（内存版，Streamlit Cloud 兼容）"""

    def record_hit(self, symbol: str) -> None:
        with _lock:
            _cache_stats["total_hits"] += 1
            if symbol in _symbol_cache:
                _symbol_cache[symbol]["analysis_count"] += 1

    def record_miss(self) -> None:
        with _lock:
            _cache_stats["total_misses"] += 1

    def get_stats(self) -> dict:
        with _lock:
            return {
                "total_hits": _cache_stats.get("total_hits", 0),
                "total_misses": _cache_stats.get("total_misses", 0),
                "cached_symbols": len(_symbol_cache),
            }

    def is_cached(self, symbol: str) -> bool:
        with _lock:
            return symbol in _symbol_cache

    def get_cached_data(self, symbol: str) -> Optional[dict]:
        with _lock:
            entry = _symbol_cache.get(symbol)
            return entry["data"] if entry else None

    def set_cached_data(self, symbol: str, data: dict) -> None:
        with _lock:
            if symbol in _symbol_cache:
                _symbol_cache[symbol]["data"] = data
                _symbol_cache[symbol]["cached_at"] = time.time()
                _symbol_cache[symbol]["analysis_count"] += 1
            else:
                _symbol_cache[symbol] = {
                    "data": data,
                    "cached_at": time.time(),
                    "analysis_count": 1,
                }

    def get_ranking(self, limit: int = 20) -> list:
        with _lock:
            sorted_symbols = sorted(
                _symbol_cache.items(),
                key=lambda x: (x[1]["analysis_count"], x[1]["cached_at"]),
                reverse=True,
            )
            result = []
            for symbol, entry in sorted_symbols[:limit]:
                data = entry.get("data", {})
                name = ""
                if isinstance(data, dict):
                    info = data.get("info", {})
                    if isinstance(info, dict):
                        name = info.get("name", "")
                result.append({
                    "symbol": symbol,
                    "name": name,
                    "count": entry["analysis_count"],
                    "cached_at": entry["cached_at"],
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
