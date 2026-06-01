"""Hindsight API 异步客户端"""

import httpx
from typing import Optional, List, Dict, Any
from astrbot.api import logger


class HindsightClient:
    """Hindsight API 异步客户端"""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    async def retain(
        self,
        content: str,
        bank_id: str = "astrbot",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """存储记忆"""
        # 确保 metadata 的值都是字符串
        safe_metadata = {}
        if metadata:
            for k, v in metadata.items():
                safe_metadata[k] = str(v) if v is not None else ""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/default/banks/{bank_id}/memories",
                headers=self.headers,
                json={
                    "items": [
                        {
                            "content": content,
                            "tags": tags or [],
                            "metadata": safe_metadata,
                        }
                    ],
                    "async": True,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def recall(
        self,
        query: str,
        bank_id: str = "astrbot",
        max_results: int = 5,
        min_relevance: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """检索相关记忆"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/default/banks/{bank_id}/memories/recall",
                headers=self.headers,
                json={
                    "query": query,
                    "max_results": max_results,
                    "min_relevance": min_relevance,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])

    async def list_recent(
        self, bank_id: str = "astrbot", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/default/banks/{bank_id}/memories/list",
                headers=self.headers,
                params={"limit": limit},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json().get("items", [])

    async def delete(self, memory_id: str, bank_id: str = "astrbot") -> bool:
        """删除记忆"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/v1/default/banks/{bank_id}/memories/{memory_id}",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return True

    async def get_stats(self, bank_id: str = "astrbot") -> Dict[str, Any]:
        """获取统计信息"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/default/banks/{bank_id}/stats",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> bool:
        """检查服务状态"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health", timeout=5.0
                )
                return response.status_code == 200
        except Exception:
            return False

    async def create_bank(
        self, bank_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """创建记忆库"""
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/v1/default/banks/{bank_id}",
                headers=self.headers,
                json={"metadata": metadata or {}},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def update_bank_config(
        self, bank_id: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新记忆库配置"""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/v1/default/banks/{bank_id}/config",
                headers=self.headers,
                json=config,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_bank_config(self, bank_id: str) -> Dict[str, Any]:
        """获取记忆库配置"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/default/banks/{bank_id}/config",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def create_mental_model(
        self,
        bank_id: str,
        name: str,
        source_query: str,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """创建 mental model"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/default/banks/{bank_id}/mental-models",
                headers=self.headers,
                json={
                    "name": name,
                    "source_query": source_query,
                    "max_tokens": max_tokens,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()
