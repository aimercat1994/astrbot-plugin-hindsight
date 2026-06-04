"""Hindsight API 异步客户端"""

import httpx
from typing import Optional, List, Dict, Any
from astrbot.api import logger


class HindsightClient:
    """Hindsight API 异步客户端（连接池复用）"""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.headers: Dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建复用的 AsyncClient"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30,
                ),
            )
        return self._client

    async def close(self):
        """关闭连接池"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ==================== 记忆操作 ====================

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

        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/default/banks/{bank_id}/memories",
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
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/default/banks/{bank_id}/memories/recall",
            json={
                "query": query,
                "max_results": max_results,
                "min_relevance": min_relevance,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    async def list_recent(
        self, bank_id: str = "astrbot", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        client = self._get_client()
        response = await client.get(
            f"{self.base_url}/v1/default/banks/{bank_id}/memories/list",
            params={"limit": limit},
        )
        response.raise_for_status()
        return response.json().get("items", [])

    async def delete(self, memory_id: str, bank_id: str = "astrbot") -> bool:
        """删除记忆"""
        client = self._get_client()
        response = await client.delete(
            f"{self.base_url}/v1/default/banks/{bank_id}/memories/{memory_id}",
        )
        response.raise_for_status()
        return True

    async def get_stats(self, bank_id: str = "astrbot") -> Dict[str, Any]:
        """获取统计信息"""
        client = self._get_client()
        response = await client.get(
            f"{self.base_url}/v1/default/banks/{bank_id}/stats",
        )
        response.raise_for_status()
        return response.json()

    # ==================== Bank 操作 ====================

    async def health_check(self) -> bool:
        """检查服务状态"""
        try:
            client = self._get_client()
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
        client = self._get_client()
        response = await client.put(
            f"{self.base_url}/v1/default/banks/{bank_id}",
            json={"metadata": metadata or {}},
        )
        response.raise_for_status()
        return response.json()

    async def update_bank_config(
        self, bank_id: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新记忆库配置"""
        client = self._get_client()
        response = await client.patch(
            f"{self.base_url}/v1/default/banks/{bank_id}/config",
            json=config,
        )
        response.raise_for_status()
        return response.json()

    async def get_bank_config(self, bank_id: str) -> Dict[str, Any]:
        """获取记忆库配置"""
        client = self._get_client()
        response = await client.get(
            f"{self.base_url}/v1/default/banks/{bank_id}/config",
        )
        response.raise_for_status()
        return response.json()

    # ==================== Mental Model 操作 ====================

    async def list_mental_models(
        self, bank_id: str = "astrbot"
    ) -> List[Dict[str, Any]]:
        """列出所有 mental models"""
        client = self._get_client()
        response = await client.get(
            f"{self.base_url}/v1/default/banks/{bank_id}/mental-models",
        )
        response.raise_for_status()
        return response.json().get("items", [])

    async def get_mental_model(
        self, model_id: str, bank_id: str = "astrbot"
    ) -> Dict[str, Any]:
        """获取单个 mental model 详情"""
        client = self._get_client()
        response = await client.get(
            f"{self.base_url}/v1/default/banks/{bank_id}/mental-models/{model_id}",
        )
        response.raise_for_status()
        return response.json()

    async def refresh_mental_model(
        self, model_id: str, bank_id: str = "astrbot"
    ) -> Dict[str, Any]:
        """刷新 mental model（异步操作）"""
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/default/banks/{bank_id}/mental-models/{model_id}/refresh",
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
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/default/banks/{bank_id}/mental-models",
            json={
                "name": name,
                "source_query": source_query,
                "max_tokens": max_tokens,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()
