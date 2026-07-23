"""
共享缓存统计模块 - SQLite 实现
为所有用户提供统一的缓存命中/未命中统计，以及跨用户数据共享
"""

import sqlite3
import threading
import json
import os
from pathlib import Path
from typing import Optional

_db_lock = threading.Lock()
_db_path = Path(__file__).parent / "cache_stats.db"


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（线程安全）"""
    conn = sqlite3.connect(str(_db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db():
    """初始化数据库表"""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_cache (
                symbol TEXT PRIMARY KEY,
                data TEXT,
                cached_at REAL,
                analysis_count INTEGER DEFAULT 1
            )
        """)
        # 确保 analysis_count 列存在（兼容已有数据库）
        try:
            conn.execute("ALTER TABLE symbol_cache ADD COLUMN analysis_count INTEGER DEFAULT 1")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


_init_db()


class SharedCacheStats:
    """
    轻量级共享缓存统计（SQLite）
    所有用户共享同一数据库文件
    """

    def __init__(self):
        pass

    def record_hit(self, symbol: str) -> None:
        """记录缓存命中"""
        with _db_lock:
            conn = _get_conn()
            try:
                conn.execute("""
                    INSERT INTO cache_stats (key, value) VALUES ('total_hits', 1)
                    ON CONFLICT(key) DO UPDATE SET value = value + 1
                    WHERE key = 'total_hits'
                """)
                conn.commit()
            finally:
                conn.close()

    def record_miss(self) -> None:
        """记录缓存未命中"""
        with _db_lock:
            conn = _get_conn()
            try:
                conn.execute("""
                    INSERT INTO cache_stats (key, value) VALUES ('total_misses', 1)
                    ON CONFLICT(key) DO UPDATE SET value = value + 1
                    WHERE key = 'total_misses'
                """)
                conn.commit()
            finally:
                conn.close()

    def get_stats(self) -> dict:
        """获取缓存统计"""
        with _db_lock:
            conn = _get_conn()
            try:
                cursor = conn.execute("SELECT key, value FROM cache_stats")
                rows = cursor.fetchall()
                stats = {row[0]: row[1] for row in rows}

                cursor2 = conn.execute("SELECT COUNT(*) FROM symbol_cache")
                cached_count = cursor2.fetchone()[0]

                return {
                    'total_hits': stats.get('total_hits', 0),
                    'total_misses': stats.get('total_misses', 0),
                    'cached_symbols': cached_count
                }
            finally:
                conn.close()

    def is_cached(self, symbol: str) -> bool:
        """检查符号是否已缓存（跨用户）"""
        with _db_lock:
            conn = _get_conn()
            try:
                cursor = conn.execute(
                    "SELECT 1 FROM symbol_cache WHERE symbol = ?", (symbol,)
                )
                return cursor.fetchone() is not None
            finally:
                conn.close()

    def get_cached_data(self, symbol: str) -> Optional[dict]:
        """获取缓存的数据"""
        with _db_lock:
            conn = _get_conn()
            try:
                cursor = conn.execute(
                    "SELECT data FROM symbol_cache WHERE symbol = ?", (symbol,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
                return None
            finally:
                conn.close()

    def set_cached_data(self, symbol: str, data: dict) -> None:
        """存储缓存数据"""
        with _db_lock:
            conn = _get_conn()
            try:
                json_data = json.dumps(data, default=str)
                conn.execute("""
                    INSERT INTO symbol_cache (symbol, data, cached_at, analysis_count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(symbol) DO UPDATE SET
                        data = ?,
                        cached_at = ?,
                        analysis_count = analysis_count + 1
                """, (symbol, json_data, self._now(), json_data, self._now()))
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _now() -> float:
        import time
        return time.time()

    def get_ranking(self, limit: int = 20) -> list:
        """获取分析次数排行榜

        Returns:
            list of dict: [{'symbol': '000001', 'name': '平安银行', 'count': 5, 'cached_at': timestamp}, ...]
        """
        with _db_lock:
            conn = _get_conn()
            try:
                cursor = conn.execute("""
                    SELECT symbol, data, cached_at, analysis_count
                    FROM symbol_cache
                    ORDER BY analysis_count DESC, cached_at DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()

                result = []
                for row in rows:
                    symbol = row[0]
                    data_str = row[1]
                    cached_at = row[2]
                    count = row[3]
                    try:
                        data = json.loads(data_str) if data_str else {}
                        name = data.get('info', {}).get('name', '') if isinstance(data, dict) else ''
                    except Exception:
                        name = ''
                    result.append({
                        'symbol': symbol,
                        'name': name,
                        'count': count,
                        'cached_at': cached_at,
                    })
                return result
            finally:
                conn.close()


# 全局单例
_shared_stats: Optional[SharedCacheStats] = None


def get_shared_cache_stats() -> SharedCacheStats:
    """获取共享缓存统计单例"""
    global _shared_stats
    if _shared_stats is None:
        _shared_stats = SharedCacheStats()
    return _shared_stats
