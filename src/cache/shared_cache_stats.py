"""
共享缓存统计模块 - SQLite 实现
为所有用户提供统一的缓存命中/未命中统计，以及跨用户数据共享
支持文件不可写时降级到内存模式（适配 Streamlit Cloud 等受限环境）
"""

import sqlite3
import threading
import json
import os
from pathlib import Path
from typing import Optional

_db_lock = threading.Lock()
_db_path = Path(__file__).parent / "cache_stats.db"
_use_memory = False  # 文件不可写时降级为内存模式
_memory_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（线程安全）"""
    global _memory_conn
    if _use_memory:
        if _memory_conn is None:
            _memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            _init_schema(_memory_conn)
        return _memory_conn
    return sqlite3.connect(str(_db_path), check_same_thread=False)


def _init_schema(conn: sqlite3.Connection):
    """在指定连接上初始化表结构"""
    conn.execute("PRAGMA journal_mode=WAL")
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
    try:
        conn.execute("ALTER TABLE symbol_cache ADD COLUMN analysis_count INTEGER DEFAULT 1")
    except Exception:
        pass
    conn.commit()


def _init_db():
    """初始化数据库表（文件不可写时降级到内存模式）"""
    global _use_memory
    try:
        # 尝试创建文件并写入，如果路径不可写则抛出异常
        _db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_db_path), check_same_thread=False)
        _init_schema(conn)
        conn.close()
    except Exception:
        # 文件不可写，降级到内存模式
        _use_memory = True


# 模块级初始化（try/except 防止 Streamlit Cloud 文件系统只读导致崩溃）
try:
    _init_db()
except Exception:
    _use_memory = True


class SharedCacheStats:
    """轻量级共享缓存统计（SQLite，异常安全）"""

    def __init__(self):
        pass

    def record_hit(self, symbol: str) -> None:
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
                    'cached_symbols': cached_count,
                }
            finally:
                conn.close()

    def is_cached(self, symbol: str) -> bool:
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
    global _shared_stats
    if _shared_stats is None:
        _shared_stats = SharedCacheStats()
    return _shared_stats
