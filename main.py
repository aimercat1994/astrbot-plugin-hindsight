"""Hindsight 长期记忆插件

自动记忆存储、智能回忆、手动管理、Mental Model 查询
"""

import json
import time
import asyncio
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star
from astrbot.api import AstrBotConfig, logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .utils.hindsight_client import HindsightClient

# AstrBot 场景的 bank 配置模板
BANK_CONFIG = {
    "version": "1",
    "bank": {
        "retain_mission": "提取用户的偏好、习惯、重要人物、承诺、重复请求和个人上下文。追踪用户关心的事情和反复提到的内容。",
        "enable_observations": True,
        "observations_mission": "追踪用户的稳定偏好、日常习惯、重要人物关系，以及他们的优先级如何随时间变化。",
    },
    "mental_models": [
        {
            "id": "user-profile",
            "name": "用户画像",
            "source_query": "我们对这个用户了解什么？他们的偏好、习惯、重要人物是什么？他们喜欢怎样被帮助？",
            "max_tokens": 2048,
            "trigger": {"refresh_after_consolidation": True},
        },
        {
            "id": "active-tasks",
            "name": "待办事项与承诺",
            "source_query": "用户当前在追踪什么任务、承诺或待办？有什么截止日期或承诺？",
            "max_tokens": 1024,
            "trigger": {"refresh_after_consolidation": True},
        },
    ],
}


class HindsightPlugin(Star):
    """Hindsight 长期记忆插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 初始化 Hindsight 客户端
        self.hindsight = HindsightClient(
            base_url=config.get("hindsight_api_url", "http://192.168.1.10:8888"),
            api_key=config.get("hindsight_api_key") or None,
        )
        self.bank_id = config.get("bank_id", "astrbot")

        logger.info("Hindsight 插件已加载")

        # 导入状态文件
        self._import_state_file = Path(get_astrbot_data_path()) / "plugins" / "hindsight_import_state.json"
        self._import_state = self._load_import_state()

        # 缓存用户消息（用于配对 bot 回复）
        self._user_msg_cache: dict[str, str] = {}  # session_id -> user_message

    def _load_import_state(self) -> dict:
        """加载导入状态"""
        try:
            if self._import_state_file.exists():
                with open(self._import_state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载导入状态失败: {e}")
        return {"last_import_time": 0, "imported_cids": []}

    def _save_import_state(self):
        """保存导入状态"""
        try:
            self._import_state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._import_state_file, "w", encoding="utf-8") as f:
                json.dump(self._import_state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存导入状态失败: {e}")

    async def _init_bank(self):
        """初始化 bank 配置（插件加载时自动执行）"""
        try:
            # 先检查服务是否可用
            if not await self.hindsight.health_check():
                logger.warning("Hindsight 服务不可用，跳过 bank 初始化")
                return

            # 直接尝试创建 bank（如果已存在会返回成功或错误，都可以忽略）
            try:
                await self.hindsight.create_bank(
                    self.bank_id,
                    metadata={"description": f"AstrBot 记忆库 - {self.bank_id}"},
                )
                logger.info(f"已创建 bank '{self.bank_id}'")
            except Exception:
                pass  # bank 可能已存在

            # 创建 mental models
            for model in BANK_CONFIG.get("mental_models", []):
                try:
                    await self.hindsight.create_mental_model(
                        self.bank_id,
                        name=model["name"],
                        source_query=model["source_query"],
                        max_tokens=model.get("max_tokens", 2048),
                    )
                    logger.info(f"已创建 mental model: {model['name']}")
                except Exception:
                    pass  # 可能已存在

            logger.info(f"Bank '{self.bank_id}' 初始化完成")

        except Exception as e:
            logger.warning(f"初始化 bank 失败: {e}")

    @filter.on_astrbot_loaded()
    async def on_loaded(self):
        """AstrBot 加载完成后初始化 bank"""
        await self._init_bank()

        # 如果启用了自动导入历史，执行导入
        if self.config.get("import_history_on_load", False):
            await self._auto_import_history()

    async def _auto_import_history(self):
        """自动导入历史对话（只导入新对话）"""
        try:
            limit = self.config.get("import_history_limit", 100)
            conv_mgr = self.context.conversation_manager
            if not conv_mgr:
                logger.warning("无法获取对话管理器，跳过自动导入")
                return

            conversations = await conv_mgr.get_conversations()
            if not conversations:
                logger.info("没有历史对话需要导入")
                return

            # 已导入的对话 ID 集合
            imported_cids = set(self._import_state.get("imported_cids", []))
            last_import_time = self._import_state.get("last_import_time", 0)

            imported = 0
            skipped = 0
            for conv in conversations[:limit]:
                try:
                    # 跳过已导入的对话
                    if conv.cid in imported_cids:
                        skipped += 1
                        continue

                    history = json.loads(conv.history or "[]")
                    for msg in history:
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if not content or len(content) < 5:
                            continue
                        if role == "user":
                            await self.hindsight.retain(
                                content=content,
                                bank_id=self.bank_id,
                                tags=["history", "auto_import"],
                                metadata={
                                    "source": "astrbot_history",
                                    "conversation_id": conv.cid,
                                    "platform_id": conv.platform_id,
                                    "user_id": conv.user_id,
                                },
                            )
                            imported += 1

                    # 标记为已导入
                    imported_cids.add(conv.cid)

                except Exception as e:
                    logger.warning(f"导入对话 {conv.cid} 失败: {e}")

            # 保存导入状态
            self._import_state["imported_cids"] = list(imported_cids)
            self._import_state["last_import_time"] = int(time.time())
            self._save_import_state()

            if imported > 0:
                logger.info(f"自动导入历史完成，新导入 {imported} 条消息，跳过 {skipped} 个已导入对话")
            else:
                logger.info(f"没有新对话需要导入，跳过 {skipped} 个已导入对话")

        except Exception as e:
            logger.error(f"自动导入历史失败: {e}")

    def _is_excluded(self, event: AstrMessageEvent) -> bool:
        """检查是否在排除列表"""
        user_id = event.get_sender_id()
        group_id = event.get_group_id()

        exclude_users = self.config.get("exclude_users", [])
        exclude_groups = self.config.get("exclude_groups", [])

        if user_id in exclude_users:
            return True
        if group_id and group_id in exclude_groups:
            return True
        return False

    def _get_event_metadata(self, event: AstrMessageEvent) -> dict:
        """从事件中提取标准元数据"""
        return {
            "source": "astrbot",
            "user_id": event.get_sender_id() or "",
            "user_name": event.get_sender_name() or "",
            "platform": event.get_platform_name() or "",
            "group_id": event.get_group_id() or "",
        }

    # ==================== 事件钩子 ====================

    @filter.on_llm_request()
    async def on_request(self, event: AstrMessageEvent):
        """在 LLM 请求前：缓存用户消息 + 注入相关记忆"""
        if self._is_excluded(event):
            return

        user_msg = event.message_str
        session_id = event.session_id

        # 缓存用户消息，用于后续配对 bot 回复
        if user_msg:
            self._user_msg_cache[session_id] = user_msg

        # 自动回忆注入
        if not self.config.get("auto_recall", True):
            return

        try:
            max_results = self.config.get("max_recall_results", 5)
            memories = await self.hindsight.recall(
                query=user_msg,
                bank_id=self.bank_id,
                max_results=max_results,
                min_relevance=self.config.get("min_relevance", 0.7),
            )

            if memories and hasattr(event, "llm_request") and event.llm_request:
                # 格式化记忆为上下文
                lines = []
                for mem in memories[:max_results]:
                    content = mem.get("content", "")
                    relevance = mem.get("relevance", 0)
                    lines.append(f"- {content} (相关度: {relevance:.0%})")
                context = "\n".join(lines)

                event.llm_request.context.append(
                    {
                        "role": "system",
                        "content": f"以下是与用户相关的历史记忆，可作为参考：\n{context}",
                    }
                )
                logger.debug(f"注入 {len(memories)} 条记忆到上下文")

        except Exception as e:
            logger.error(f"记忆回忆失败: {e}")

    @filter.on_llm_response()
    async def on_response(self, event: AstrMessageEvent, result: MessageEventResult):
        """在 LLM 响应后：存储用户消息 + bot 回复"""
        if not self.config.get("auto_retain", True):
            return
        if self._is_excluded(event):
            return

        try:
            session_id = event.session_id
            user_msg = self._user_msg_cache.pop(session_id, event.message_str)

            # 尝试获取 bot 回复（取决于配置）
            bot_reply = ""
            if self.config.get("retain_bot_replies", True):
                try:
                    if result and hasattr(result, "get_plain_text"):
                        bot_reply = result.get_plain_text()
                except Exception:
                    pass

            # 构建完整对话内容
            if user_msg and bot_reply:
                content = f"用户: {user_msg}\n助手: {bot_reply}"
            elif user_msg:
                content = f"用户: {user_msg}"
            else:
                return

            await self.hindsight.retain(
                content=content,
                bank_id=self.bank_id,
                tags=["conversation"],
                metadata=self._get_event_metadata(event),
            )
            logger.debug(f"已存储对话记忆: {content[:80]}...")

        except Exception as e:
            logger.error(f"记忆存储失败: {e}")

    # ==================== 用户命令 ====================

    @filter.command_group("hindsight")
    def hindsight_group(self):
        """记忆管理命令组"""
        pass

    @hindsight_group.command("recall", alias={"搜索记忆", "回忆"})
    async def recall_memory(self, event: AstrMessageEvent, *, query: str):
        """搜索相关记忆

        Args:
            query(string): 搜索关键词
        """
        try:
            results = await self.hindsight.recall(
                query=query, bank_id=self.bank_id, max_results=10
            )

            if not results:
                yield event.plain_result("🔍 未找到相关记忆")
                return

            output = "🧠 相关记忆：\n\n"
            for i, mem in enumerate(results, 1):
                content = mem.get("content", "")
                relevance = mem.get("relevance", 0)
                tags = mem.get("tags", [])

                output += f"{i}. {content}\n"
                output += f"   相关度: {relevance:.0%}"
                if tags:
                    output += f" | 标签: {', '.join(tags)}"
                output += "\n\n"

            yield event.plain_result(output.strip())

        except Exception as e:
            logger.error(f"记忆搜索失败: {e}")
            yield event.plain_result(f"❌ 搜索失败: {e}")

    @hindsight_group.command("retain", alias={"存储记忆", "记住"})
    async def retain_memory(self, event: AstrMessageEvent, *, content: str):
        """手动存储一条记忆

        Args:
            content(string): 要记住的内容
        """
        try:
            await self.hindsight.retain(
                content=content,
                bank_id=self.bank_id,
                tags=["manual"],
                metadata=self._get_event_metadata(event),
            )
            preview = content[:50] + "..." if len(content) > 50 else content
            yield event.plain_result(f"✅ 已记住：{preview}")

        except Exception as e:
            logger.error(f"手动存储失败: {e}")
            yield event.plain_result(f"❌ 存储失败: {e}")

    @hindsight_group.command("reflect", alias={"画像", "用户画像", "心智模型"})
    async def reflect_memory(self, event: AstrMessageEvent, name: str = ""):
        """查看 Mental Model（用户画像/待办事项等）

        Args:
            name(string): 模型名称，留空显示所有
        """
        try:
            models = await self.hindsight.list_mental_models(bank_id=self.bank_id)

            if not models:
                yield event.plain_result("📭 暂无 Mental Model，请先运行 /hindsight init 初始化")
                return

            # 如果指定了名称，筛选匹配的模型
            if name:
                matched = [m for m in models if name.lower() in m.get("name", "").lower()]
                if not matched:
                    names = ", ".join(m.get("name", "?") for m in models)
                    yield event.plain_result(f"❌ 未找到名为 '{name}' 的模型\n可用模型: {names}")
                    return
                models = matched

            output = "🧠 Mental Models：\n"
            for model in models:
                model_name = model.get("name", "未命名")
                content = model.get("content") or "(尚未生成，请等待记忆积累后自动刷新)"
                source_query = model.get("source_query", "")

                output += f"\n{'='*30}\n"
                output += f"📌 {model_name}\n"
                if source_query:
                    output += f"   查询: {source_query}\n"
                output += f"\n{content}\n"

            yield event.plain_result(output.strip())

        except Exception as e:
            logger.error(f"查询 Mental Model 失败: {e}")
            yield event.plain_result(f"❌ 查询失败: {e}")

    @hindsight_group.command("ask", alias={"问记忆", "记忆问答"})
    async def ask_memory(self, event: AstrMessageEvent, *, question: str):
        """综合记忆问答（recall + mental model）

        Args:
            question(string): 你的问题
        """
        try:
            # 并行获取 recall 结果和 mental models
            recall_task = self.hindsight.recall(
                query=question,
                bank_id=self.bank_id,
                max_results=5,
                min_relevance=0.5,
            )
            models_task = self.hindsight.list_mental_models(bank_id=self.bank_id)

            results, models = await asyncio.gather(recall_task, models_task)

            output = f"❓ 问题: {question}\n"

            # 相关记忆
            if results:
                output += f"\n📚 相关记忆 ({len(results)} 条)：\n"
                for i, mem in enumerate(results, 1):
                    content = mem.get("content", "")
                    relevance = mem.get("relevance", 0)
                    if len(content) > 150:
                        content = content[:150] + "..."
                    output += f"  {i}. {content} (相关度: {relevance:.0%})\n"
            else:
                output += "\n📚 未找到相关记忆\n"

            # Mental Models 摘要
            if models:
                output += f"\n🧠 记忆画像：\n"
                for model in models:
                    model_name = model.get("name", "")
                    content = model.get("content") or "(无)"
                    # 只取前 300 字符作为摘要
                    if len(content) > 300:
                        content = content[:300] + "..."
                    output += f"\n  【{model_name}】\n  {content}\n"

            yield event.plain_result(output.strip())

        except Exception as e:
            logger.error(f"记忆问答失败: {e}")
            yield event.plain_result(f"❌ 问答失败: {e}")

    @hindsight_group.command("list", alias={"记忆列表", "最近记忆"})
    async def list_memory(self, event: AstrMessageEvent, limit: int = 10):
        """查看最近的记忆

        Args:
            limit(number): 显示数量，默认 10
        """
        try:
            results = await self.hindsight.list_recent(
                bank_id=self.bank_id, limit=min(limit, 50)
            )

            if not results:
                yield event.plain_result("📭 暂无记忆")
                return

            output = f"📋 最近 {len(results)} 条记忆：\n\n"
            for i, mem in enumerate(results, 1):
                content = mem.get("content", "")
                created_at = mem.get("created_at", "")
                tags = mem.get("tags", [])

                if len(content) > 100:
                    content = content[:100] + "..."

                output += f"{i}. {content}\n"
                if created_at:
                    output += f"   时间: {created_at}"
                if tags:
                    output += f" | 标签: {', '.join(tags)}"
                output += "\n\n"

            yield event.plain_result(output.strip())

        except Exception as e:
            logger.error(f"获取记忆列表失败: {e}")
            yield event.plain_result(f"❌ 获取失败: {e}")

    @hindsight_group.command("delete", alias={"删除记忆"})
    async def delete_memory(self, event: AstrMessageEvent, memory_id: str):
        """删除指定记忆

        Args:
            memory_id(string): 记忆 ID
        """
        try:
            await self.hindsight.delete(memory_id=memory_id, bank_id=self.bank_id)
            yield event.plain_result(f"✅ 已删除记忆: {memory_id}")
        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
            yield event.plain_result(f"❌ 删除失败: {e}")

    @hindsight_group.command("stats", alias={"记忆统计"})
    async def memory_stats(self, event: AstrMessageEvent):
        """查看记忆统计信息"""
        try:
            stats = await self.hindsight.get_stats(bank_id=self.bank_id)

            total_nodes = stats.get("total_nodes", 0)
            total_links = stats.get("total_links", 0)
            total_docs = stats.get("total_documents", 0)

            nodes_by_type = stats.get("nodes_by_fact_type", {})
            links_by_type = stats.get("links_by_link_type", {})

            output = "📊 记忆统计：\n\n"
            output += f"📄 文档数: {total_docs}\n"
            output += f"🧠 知识节点: {total_nodes}\n"
            output += f"🔗 关系链接: {total_links}\n"

            if nodes_by_type:
                output += "\n节点类型分布:\n"
                for ntype, count in nodes_by_type.items():
                    output += f"  • {ntype}: {count}\n"

            if links_by_type:
                output += "\n链接类型分布:\n"
                for ltype, count in links_by_type.items():
                    output += f"  • {ltype}: {count}\n"

            # Mental Models 状态
            try:
                models = await self.hindsight.list_mental_models(bank_id=self.bank_id)
                if models:
                    output += f"\n🧠 Mental Models ({len(models)}):\n"
                    for m in models:
                        name = m.get("name", "?")
                        has_content = "✅" if m.get("content") else "⏳"
                        output += f"  {has_content} {name}\n"
            except Exception:
                pass

            yield event.plain_result(output.strip())

        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            yield event.plain_result(f"❌ 获取失败: {e}")

    @hindsight_group.command("refresh", alias={"刷新画像"})
    async def refresh_model(self, event: AstrMessageEvent, name: str = ""):
        """手动刷新 Mental Model

        Args:
            name(string): 模型名称，留空刷新所有
        """
        try:
            models = await self.hindsight.list_mental_models(bank_id=self.bank_id)

            if not models:
                yield event.plain_result("📭 暂无 Mental Model")
                return

            if name:
                models = [m for m in models if name.lower() in m.get("name", "").lower()]
                if not models:
                    yield event.plain_result(f"❌ 未找到名为 '{name}' 的模型")
                    return

            refreshed = []
            for model in models:
                model_id = model.get("id", "")
                model_name = model.get("name", "?")
                try:
                    await self.hindsight.refresh_mental_model(model_id, bank_id=self.bank_id)
                    refreshed.append(model_name)
                except Exception as e:
                    logger.warning(f"刷新 {model_name} 失败: {e}")

            if refreshed:
                yield event.plain_result(f"✅ 已触发刷新: {', '.join(refreshed)}\n⏳ 生成需要一些时间，请稍后查看")
            else:
                yield event.plain_result("❌ 刷新失败")

        except Exception as e:
            logger.error(f"刷新 Mental Model 失败: {e}")
            yield event.plain_result(f"❌ 刷新失败: {e}")

    @hindsight_group.command("health", alias={"记忆状态"})
    async def health_check(self, event: AstrMessageEvent):
        """检查 Hindsight 服务状态"""
        is_healthy = await self.hindsight.health_check()

        if is_healthy:
            yield event.plain_result("✅ Hindsight 服务正常")
        else:
            yield event.plain_result("❌ Hindsight 服务不可用")

    @hindsight_group.command("init", alias={"初始化记忆库"})
    async def init_bank(self, event: AstrMessageEvent):
        """初始化或重置记忆库配置"""
        try:
            await self.hindsight.create_bank(
                self.bank_id,
                metadata={"description": f"AstrBot 记忆库 - {self.bank_id}"},
            )
            # 创建 mental models
            for model in BANK_CONFIG.get("mental_models", []):
                try:
                    await self.hindsight.create_mental_model(
                        self.bank_id,
                        name=model["name"],
                        source_query=model["source_query"],
                        max_tokens=model.get("max_tokens", 2048),
                    )
                except Exception:
                    pass
            yield event.plain_result(f"✅ 已初始化记忆库 '{self.bank_id}'")
        except Exception as e:
            logger.error(f"初始化记忆库失败: {e}")
            yield event.plain_result(f"❌ 初始化失败: {e}")

    @hindsight_group.command("reset_import", alias={"重置导入状态"})
    async def reset_import_state(self, event: AstrMessageEvent):
        """重置导入状态（下次启动将重新导入所有对话）"""
        try:
            self._import_state = {"last_import_time": 0, "imported_cids": []}
            self._save_import_state()
            yield event.plain_result("✅ 已重置导入状态，下次启动将重新导入所有对话")
        except Exception as e:
            logger.error(f"重置导入状态失败: {e}")
            yield event.plain_result(f"❌ 重置失败: {e}")

    @hindsight_group.command("import", alias={"导入历史"})
    async def import_history(self, event: AstrMessageEvent, limit: int = 100, force: bool = False):
        """导入 AstrBot 历史对话到 Hindsight

        Args:
            limit(number): 导入的对话数量，默认 100
            force(bool): 强制重新导入所有对话（忽略已导入记录），默认 false
        """
        try:
            yield event.plain_result("📥 开始导入历史对话...")

            # 获取对话管理器
            conv_mgr = self.context.conversation_manager
            if not conv_mgr:
                yield event.plain_result("❌ 无法获取对话管理器")
                return

            # 获取所有对话
            conversations = await conv_mgr.get_conversations()
            if not conversations:
                yield event.plain_result("📭 没有找到历史对话")
                return

            # 已导入的对话 ID 集合
            imported_cids = set(self._import_state.get("imported_cids", [])) if not force else set()

            imported = 0
            skipped = 0
            errors = 0

            # 并发控制
            sem = asyncio.Semaphore(self.config.get("import_concurrency", 5))

            async def _import_msg(content: str, conv, msg_idx: int):
                nonlocal imported
                async with sem:
                    try:
                        await self.hindsight.retain(
                            content=content,
                            bank_id=self.bank_id,
                            tags=["history", "auto_import"],
                            metadata={
                                "source": "astrbot_history",
                                "conversation_id": conv.cid or "",
                                "platform_id": conv.platform_id or "",
                                "user_id": conv.user_id or "",
                            },
                        )
                        imported += 1
                    except Exception as retain_err:
                        logger.warning(f"导入消息失败 (conv={conv.cid}, msg={msg_idx}): {retain_err}")

            for conv in conversations[:limit]:
                try:
                    # 跳过已导入的对话（除非强制模式）
                    if conv.cid in imported_cids:
                        skipped += 1
                        continue

                    history = json.loads(conv.history or "[]")

                    tasks = []
                    for msg_idx, msg in enumerate(history):
                        role = msg.get("role", "")
                        content = msg.get("content", "")

                        # 处理 list 类型的 content（多模态消息）
                        if isinstance(content, list):
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text_parts.append(item.get("text", ""))
                                elif isinstance(item, str):
                                    text_parts.append(item)
                            content = " ".join(text_parts)

                        if not content or not isinstance(content, str) or len(content) < 5:
                            continue

                        # 导入用户消息
                        if role == "user":
                            tasks.append(_import_msg(content, conv, msg_idx))

                    # 批量并发执行
                    if tasks:
                        await asyncio.gather(*tasks)

                    # 标记为已导入
                    imported_cids.add(conv.cid)

                except Exception as e:
                    errors += 1
                    try:
                        if hasattr(e, 'response') and e.response is not None:
                            error_body = e.response.text
                            logger.warning(f"导入对话 {conv.cid} 失败 (422): {error_body[:500]}")
                        else:
                            logger.warning(f"导入对话 {conv.cid} 失败: {e}")
                    except Exception:
                        logger.warning(f"导入对话 {conv.cid} 失败: {e}")

            # 保存导入状态
            self._import_state["imported_cids"] = list(imported_cids)
            self._import_state["last_import_time"] = int(time.time())
            self._save_import_state()

            result = f"✅ 导入完成！新导入 {imported} 条消息"
            if skipped > 0:
                result += f"，跳过 {skipped} 个已导入对话"
            if errors > 0:
                result += f"，{errors} 个对话导入失败"
            if force:
                result += "（强制模式）"
            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"导入历史对话失败: {e}")
            yield event.plain_result(f"❌ 导入失败: {e}")

    # ==================== 生命周期 ====================

    async def terminate(self):
        """插件卸载时清理"""
        await self.hindsight.close()
        logger.info("Hindsight 插件已卸载")
