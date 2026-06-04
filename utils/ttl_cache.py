"""TTL 缓存工具"""

import time
from typing import Any, Optional


class TTLCache:
    """简单的 TTL 缓存"""

    def __init__(self, ttl: int = 300):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，过期返回 None"""
        if key in self._cache:
            ts, val = self._cache[key]
            if time.monotonic() - ts < self._ttl:
                return val
            del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        """设置缓存值"""
        self._cache[key] = (time.monotonic(), value)

    def invalidate(self, key: str):
        """删除指定缓存"""
        self._cache.pop(key, None)

    def clear(self):
        """清空所有缓存"""
        self._cache.clear()

    def cleanup(self):
        """清理过期缓存"""
        now = time.monotonic()
        expired = [k for k, (ts, _) in self._cache.items() if now - ts >= self._ttl]
        for k in expired:
            del self._cache[k]

    @property
    def size(self) -> int:
        return len(self._cache)
