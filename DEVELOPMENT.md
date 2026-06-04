# Hindsight AstrBot 插件开发日志

**开发日期**：2026-06-01 ~ 2026-06-04
**开发者**：aimercat + Hermes Agent
**仓库**：https://github.com/aimercat1994/astrbot-plugin-hindsight

---

## 1. 项目背景

### 1.1 需求起源
- 用户已有 Hindsight 长期记忆系统部署在 FNOS NAS (192.168.1.10:8888)
- 希望将 AstrBot 的对话历史导入 Hindsight，让机器人拥有跨会话记忆能力
- 最初设计文档保存在 `/home/aimercat/hindsight-astrbot-plugin-design.md`

### 1.2 核心目标
- 自动记忆存储：对话时自动存储用户消息
- 智能回忆注入：对话时自动注入相关历史记忆
- 历史对话导入：一键导入 AstrBot 历史对话
- Dashboard 配置：可视化配置界面

---

## 2. 技术架构

```
AstrBot 插件 (事件监听 + 命令处理)
        ↓
Hindsight API Client (httpx 异步调用 + 连接池)
        ↓
Hindsight API (:8888) → PostgreSQL (pgvector)
```

### 2.1 文件结构
```
astrbot_plugin_hindsight/
├── main.py                  # 插件主入口
├── metadata.yaml            # 元数据
├── _conf_schema.json        # 配置 Schema
├── requirements.txt         # 依赖：httpx
├── README.md                # 说明文档
├── DEVELOPMENT.md           # 开发日志
└── utils/
    ├── __init__.py
    └── hindsight_client.py  # API 客户端
```

### 2.2 核心组件
- **HindsightClient**: 封装 Hindsight REST API 调用（连接池复用）
- **HindsightPlugin**: AstrBot 插件主类，处理事件和命令
- **BANK_CONFIG**: 预定义的 bank 配置模板

---

## 3. 开发过程

### 3.1 第一阶段：基础框架搭建（v1.0.0）

**时间**：2026-06-01 10:00-10:30

**任务**：
- 创建插件目录结构
- 实现 HindsightClient API 客户端
- 实现基本的插件框架

**关键代码**：
```python
# utils/hindsight_client.py
class HindsightClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    async def retain(self, content: str, bank_id: str = "astrbot", ...):
        # 存储记忆
        ...

    async def recall(self, query: str, bank_id: str = "astrbot", ...):
        # 检索记忆
        ...
```

**遇到的问题**：
- 最初使用了错误的 API 路径 `/api/v1/banks/{bank_id}/...`
- 实际路径是 `/v1/default/banks/{bank_id}/...`

**解决方案**：
- 通过 `curl http://192.168.1.10:8888/openapi.json` 获取正确的 API 文档

---

### 3.2 第二阶段：命令组实现（v1.0.0）

**时间**：2026-06-01 10:30-11:00

**任务**：
- 实现 `/hindsight` 命令组
- 实现 recall、list、delete、stats、health 命令

**遇到的问题**：
- 使用 `@filter.command("hindsight")` 导致 `AttributeError: 'function' object has no attribute 'command'`
- 应该使用 `@filter.command_group("hindsight")`

**解决方案**：
```python
# 错误写法
@filter.command("hindsight")
async def hindsight_group(self):
    pass

# 正确写法
@filter.command_group("hindsight")
def hindsight_group(self):
    pass
```

**关键教训**：
- AstrBot 的命令组必须用 `@filter.command_group()` 装饰
- 命令组方法不能是 `async`

---

### 3.3 第三阶段：自动记忆功能（v1.0.0）

**时间**：2026-06-01 11:00-11:30

**任务**：
- 实现 `on_llm_request` 钩子：自动注入相关记忆
- 实现 `on_llm_response` 钩子：自动存储用户消息

**最初设计**：
- 使用 LLM 分析对话提取值得记忆的信息（EXTRACTION_PROMPT）
- 需要配置 `extraction_provider_id`

**用户质疑**：
> "hindsight不是已经配置了LLM吗，为什么插件里还要设置LLM"

**优化方案**：
- 删除 EXTRACTION_PROMPT 和 extraction_provider_id
- 直接把用户消息传给 Hindsight retain，让它自己处理实体提取
- 简化代码，减少依赖

---

### 3.4 第四阶段：Bank 初始化（v1.0.0）

**时间**：2026-06-01 11:30-12:00

**任务**：
- 自动创建 Hindsight bank
- 自动创建 Mental Models（用户画像、待办事项）

**遇到的问题**：
- Health check 端点错误：使用 `/healthcheck` 返回 404
- 正确端点是 `/health`

---

### 3.5 第五阶段：历史对话导入（v1.0.0）

**时间**：2026-06-01 12:00-13:00

**任务**：
- 实现 `/hindsight import` 命令
- 实现启动时自动导入功能

**遇到的问题**：

**问题 1：405 Method Not Allowed**
- 使用 POST `/v1/default/banks/{bank_id}/memories/retain` 返回 405
- 正确路径是 POST `/v1/default/banks/{bank_id}/memories`

**问题 2：422 Unprocessable Entity**
- `metadata` 字段的值必须全是字符串类型
- `user_id` 可能是数字类型

**解决方案**：
```python
# 保留metadata值为字符串
safe_metadata = {}
if metadata:
    for k, v in metadata.items():
        safe_metadata[k] = str(v) if v is not None else ""
```

**问题 3：多模态消息处理**
- 有些对话的 `content` 是 list 类型（包含文本和引用等）
- 需要提取文本部分

**导入结果**：
- 成功导入 171 条消息

---

### 3.6 第六阶段：Dashboard 配置（v1.0.0）

**时间**：2026-06-01 13:00-13:30

**任务**：
- 添加 `import_history_on_load` 配置项
- 添加 `import_history_limit` 配置项

---

### 3.7 第七阶段：幂等导入修复（v1.0.0）

**时间**：2026-06-01 14:00

**问题**：每次 AstrBot 重启都会重复导入所有历史对话

**解决方案**：
- 本地 JSON 文件跟踪已导入的对话 ID (`imported_cids`)
- 启动时跳过已导入对话
- 添加 `force` 参数允许强制重新导入
- 添加 `reset_import` 命令清除状态

---

### 3.8 第八阶段：v1.1.0 命令增强 + 连接池优化

**时间**：2026-06-04

**新增命令**：

#### `/hindsight retain` - 手动存储记忆
```python
@hindsight_group.command("retain", alias={"存储记忆", "记住"})
async def retain_memory(self, event: AstrMessageEvent, *, content: str):
    await self.hindsight.retain(
        content=content,
        bank_id=self.bank_id,
        tags=["manual"],
        metadata=self._get_event_metadata(event),
    )
    yield event.plain_result(f"✅ 已记住：{content[:50]}")
```

#### `/hindsight ask` - 综合记忆问答
```python
@hindsight_group.command("ask", alias={"问记忆", "记忆问答"})
async def ask_memory(self, event: AstrMessageEvent, *, question: str):
    # 并行获取 recall 结果和 mental models
    recall_task = self.hindsight.recall(query=question, ...)
    models_task = self.hindsight.list_mental_models(...)
    results, models = await asyncio.gather(recall_task, models_task)
    # 合并输出
```

#### `/hindsight reflect` - 查看 Mental Models
```python
@hindsight_group.command("reflect", alias={"画像", "用户画像", "心智模型"})
async def reflect_memory(self, event: AstrMessageEvent, name: str = ""):
    models = await self.hindsight.list_mental_models(bank_id=self.bank_id)
    if name:
        models = [m for m in models if name.lower() in m.get("name", "").lower()]
    # 格式化输出
```

#### `/hindsight refresh` - 手动刷新 Mental Models
```python
@hindsight_group.command("refresh", alias={"刷新画像"})
async def refresh_model(self, event: AstrMessageEvent, name: str = ""):
    models = await self.hindsight.list_mental_models(bank_id=self.bank_id)
    for model in models:
        await self.hindsight.refresh_mental_model(model["id"], bank_id=self.bank_id)
```

---

### 3.9 第九阶段：完整对话存储

**时间**：2026-06-04

**改进**：同时存储用户消息和 bot 回复

**实现**：
```python
# on_llm_request 中缓存用户消息
self._user_msg_cache[session_id] = event.message_str

# on_llm_response 中配对存储
user_msg = self._user_msg_cache.pop(session_id, event.message_str)
bot_reply = result.get_plain_text() if self.config.get("retain_bot_replies", True) else ""

if user_msg and bot_reply:
    content = f"用户: {user_msg}\n助手: {bot_reply}"
elif user_msg:
    content = f"用户: {user_msg}"
```

**新增配置**：
- `retain_bot_replies`: 控制是否存储助手回复（默认开启）

---

### 3.10 第十阶段：连接池优化

**时间**：2026-06-04

**问题**：每次 API 请求都创建新的 `httpx.AsyncClient`，TCP 连接开销大

**解决方案**：
```python
class HindsightClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
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
        if self._client and not self._client.is_closed:
            await self._client.aclose()
```

**terminate 中关闭**：
```python
async def terminate(self):
    await self.hindsight.close()
```

---

### 3.11 第十一阶段：导入并发控制

**时间**：2026-06-04

**问题**：批量导入时无限制并发，可能触发 Hindsight 限流或 OOM

**解决方案**：
```python
sem = asyncio.Semaphore(self.config.get("import_concurrency", 5))

async def _import_msg(content: str, conv, msg_idx: int):
    async with sem:
        await self.hindsight.retain(...)

# 批量并发执行
tasks = [_import_msg(content, conv, msg_idx) for ...]
await asyncio.gather(*tasks)
```

**新增配置**：
- `import_concurrency`: 导入并发数（默认 5）

---

### 3.12 第十二阶段：Dashboard 设置增强

**时间**：2026-06-04

**改进**：
- `min_relevance` 添加 slider 滑块（0-1, step 0.05）
- 重要配置项添加 `obvious_hint` 高亮
- 新增 `retain_bot_replies` 开关
- 优化所有配置项的 hint 描述

---

### 3.13 第十三阶段：性能优化（v1.2.0）

**时间**：2026-06-04

**问题**：
- on_response 中 retain 阻塞响应发送
- 每次 on_request 都从 API 拉取 Mental Model
- 相同查询短时间内重复调用 recall API
- user_msg_cache 无限增长可能导致内存泄漏

**解决方案**：

#### 1. TTL 缓存（utils/ttl_cache.py）
```python
class TTLCache:
    def __init__(self, ttl: int = 300):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            ts, val = self._cache[key]
            if time.monotonic() - ts < self._ttl:
                return val
            del self._cache[key]
        return None
```

#### 2. Fire-and-forget retain
```python
@filter.on_llm_response()
async def on_response(self, event, result):
    # 不再 await retain，改用 create_task
    asyncio.create_task(self._retain_async(content, event))
```

#### 3. 批量 retain 队列
```python
class HindsightClient:
    def __init__(self, ...):
        self._retain_queue: List[Dict] = []
        self._batch_size = 10
        self._batch_interval = 2.0  # 秒

    async def retain(self, content, ..., batch=False):
        if batch:
            self._retain_queue.append(item)
            if len(self._retain_queue) >= self._batch_size:
                await self._flush_retain_queue()
```

#### 4. Mental Model 上下文注入
```python
async def _get_mental_models_context(self) -> str:
    cached = self._mm_cache.get(cache_key)
    if cached:
        return cached
    models = await self.hindsight.list_mental_models(...)
    context = format_models(models)
    self._mm_cache.set(cache_key, context)
    return context
```

#### 5. 后台清理
```python
async def _periodic_cleanup(self):
    while True:
        await asyncio.sleep(300)  # 每 5 分钟
        self._mm_cache.cleanup()
        self._recall_cache.cleanup()
        if len(self._user_msg_cache) > 1000:
            # 保留最后 500 条
```

**新增配置**：
- `inject_mental_models`: 是否注入用户画像到上下文（默认开启）
- `cache_ttl`: Mental Model 缓存时长（默认 300s）
- `recall_cache_ttl`: Recall 结果缓存时长（默认 60s）

---

### 3.14 第十四阶段：Mental Model 去重修复

**时间**：2026-06-04

**问题**：每次 AstrBot 重启都会创建新的 Mental Models，导致出现 12 个重复模型（6 对）

**原因**：`create_mental_model` API 不检查名称唯一性，总是创建新模型

**解决方案**：创建前先 list 检查是否已存在同名模型
```python
existing_models = await self.hindsight.list_mental_models(bank_id=self.bank_id)
existing_names = {m.get("name") for m in existing_models}

for model in BANK_CONFIG.get("mental_models", []):
    if model["name"] in existing_names:
        continue  # 已存在，跳过
    await self.hindsight.create_mental_model(...)
```

**清理**：删除了 10 个重复的 Mental Models，保留原始 2 个

---

### 3.15 第十五阶段：群聊优化（v1.3.0）

**时间**：2026-06-04

**背景**：AstrBot 通过 NapCat 接入个人 QQ，定位为个人助手+赛博群友，需要针对群聊场景优化

**问题**：
- 每条群消息都触发 recall → API 风暴
- 每条群消息都存储 → 记忆库被刷屏
- 存储不含发言人名字 → 回忆时不知道谁说的
- 无频率限制 → 活跃群 recall 太频繁
- 无私聊/群聊差异化 → 行为相同

**解决方案**：

#### 1. 群聊存储模式（`group_store_mode`）
```python
def _should_store_group_msg(self, event, content):
    mode = self.config.get("group_store_mode", "smart")
    if mode == "all": return not self._is_group_noise(content)
    if mode == "bot_only": return True  # bot 已回复
    if mode == "smart":
        if self._is_group_noise(content): return False
        if len(content) > 30: return True
        if "？" in content or "?" in content: return True
        return True
```

#### 2. 群聊回忆模式（`group_recall_mode`）
```python
def _should_recall_group(self, event):
    mode = self.config.get("group_recall_mode", "smart")
    if mode == "always": return True
    if mode == "bot_only": return self._is_bot_mentioned(event)
    if mode == "smart":
        if self._is_bot_mentioned(event): return True
        if len(event.message_str) > 20: return True
        if "？" in event.message_str: return True
        return False
```

#### 3. 群聊频率限制
```python
def _check_group_rate_limit(self, group_id):
    now = time.monotonic()
    last_ts = self._group_recall_ts.get(group_id, 0)
    if now - last_ts < self._group_recall_interval:
        return False  # 限流
    self._group_recall_ts[group_id] = now
    return True
```

#### 4. 噪声过滤
```python
GROUP_NOISE_PATTERNS = [
    "[图片]", "[表情]", "[语音]", "[视频]", "[文件]",
    "[动画表情]", "[QQ表情]", "[贴纸]",
    "撤回了一条消息", "加入了群聊", "退出了群聊",
]

def _is_group_noise(self, content):
    if len(content.strip()) < 6: return True  # 短消息
    for pattern in GROUP_NOISE_PATTERNS:
        if pattern in content: return True
    return False
```

#### 5. 群聊发言人标注（昵称 + QQ号）
```python
def _format_group_content(self, event, content):
    user_name = event.get_sender_name()  # 昵称（可更改）
    user_id = event.get_sender_id()      # QQ号（不变）
    if not event.get_group_id():
        return content
    # 格式: [昵称(123456)] 消息内容
    if user_name and user_id:
        return f"[{user_name}({user_id})] {content}"
    elif user_name:
        return f"[{user_name}] {content}"
    elif user_id:
        return f"[{user_id}] {content}"
    return content
```

#### 6. 差异化配置
- 群聊默认更低的相关度阈值（0.5 vs 0.7）
- 群聊默认不注入 Mental Model（减少上下文长度）
- stats 命令展示群聊存储/跳过统计

**新增配置**：
- `group_store_mode`: 群聊存储模式（all/bot_only/smart）
- `group_recall_mode`: 群聊回忆模式（always/bot_only/smart）
- `group_recall_interval`: 群聊回忆最小间隔（默认 5s）
- `group_min_relevance`: 群聊相关度阈值（默认 0.5）
- `group_inject_mm`: 群聊注入用户画像（默认关闭）

---

## 4. 关键设计决策

### 4.1 为什么删除 EXTRACTION_PROMPT？
- Hindsight 本身已经有实体提取功能
- 减少 LLM 调用，降低成本
- 简化代码，减少依赖

### 4.2 为什么只导入用户消息？
- 避免重复存储机器人回复
- 用户消息包含更丰富的个人信息和偏好
- 机器人回复可以由 LLM 根据上下文重新生成

### 4.3 为什么使用连接池？
- 避免每次请求都创建/销毁 TCP 连接
- 减少延迟，提高吞吐量
- httpx.AsyncClient 支持 keep-alive

### 4.4 为什么缓存用户消息配对 bot 回复？
- `on_llm_request` 有用户消息，`on_llm_response` 有 bot 回复
- 同一轮对话的两个事件需要关联
- 用 session_id 作为缓存 key

### 4.5 为什么用 fire-and-forget 存储记忆？
- retain 是异步操作（Hindsight async=True），不需要等结果
- on_response 是关键路径，阻塞会延迟用户看到回复
- create_task 后台执行，失败只记日志不影响用户体验

### 4.6 为什么缓存 Mental Model？
- Mental Model 内容变化慢（每次 consolidation 才更新）
- on_request 是每个消息的必经路径，频繁调用 API 增加延迟
- TTL 300s 缓存平衡了实时性和性能

### 4.7 为什么创建前检查 Mental Model 是否存在？
- Hindsight API 的 create_mental_model 不检查名称唯一性
- 每次重启都会创建重复模型（观察到 12 个重复模型）
- 先 list 检查 existing_names 集合，跳过已存在的

### 4.8 为什么群聊默认 smart 模式而不是 always？
- 群消息量大，每条都 recall 会导致 API 风暴
- 群聊中大部分消息是闲聊/表情包，recall 价值低
- smart 模式只在 bot 被触发或消息有价值时才 recall

### 4.9 为什么群聊存储时添加发言人名字？
- 群聊是多人对话，记忆需要区分谁说的
- 存储为 `[用户名] 消息内容` 格式，recall 时能匹配到具体发言人
- 便于 Mental Model 提取不同用户的偏好

### 4.10 为什么群聊默认不注入 Mental Model？
- Mental Model 内容较长，会占用大量 LLM 上下文
- 群聊回复通常较短，不需要深度个性化
- 用户可通过 `group_inject_mm=true` 开启

---

## 5. API 路径参考

### 5.1 正确的 API 路径
```
POST   /v1/default/banks/{bank_id}/memories          # 保留记忆
POST   /v1/default/banks/{bank_id}/memories/recall    # 检索记忆
GET    /v1/default/banks/{bank_id}/memories/list      # 列出记忆
DELETE /v1/default/banks/{bank_id}/memories/{id}      # 删除记忆
GET    /v1/default/banks/{bank_id}/stats              # 统计信息
GET    /health                                         # 健康检查
PUT    /v1/default/banks/{bank_id}                     # 创建 bank
PATCH  /v1/default/banks/{bank_id}/config             # 更新配置
POST   /v1/default/banks/{bank_id}/mental-models      # 创建 mental model
GET    /v1/default/banks/{bank_id}/mental-models      # 列出 mental models
GET    /v1/default/banks/{bank_id}/mental-models/{id} # 获取 mental model
POST   /v1/default/banks/{bank_id}/mental-models/{id}/refresh  # 刷新
```

### 5.2 请求格式
```json
// 保留记忆
{
  "items": [
    {
      "content": "消息内容",
      "tags": ["tag1", "tag2"],
      "metadata": {"key": "value"}  // 值必须是字符串
    }
  ],
  "async": true
}
```

---

## 6. 踩坑记录

### 6.1 AstrBot 插件开发

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `'function' object has no attribute 'command'` | 使用了 `@filter.command()` 而不是 `@filter.command_group()` | 改用 `@filter.command_group()` |
| `on_astrbot_loaded` 热重载不触发 | 只在冷启动触发 | 关键逻辑放 `__init__` |
| Dashboard HTTP API 返回 401 | 需要认证 | 使用内部 Python API |
| `upload_document` 的 `file_content` 必须是 `bytes` | 类型不匹配 | 用 `content.encode("utf-8")` |
| 数据目录用 `get_astrbot_data_path()` | 路径错误 | 不要用 `os.path.dirname(__file__)` |

### 6.2 Hindsight API

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 405 Method Not Allowed | 路径错误 | `/v1/default/banks/{bank_id}/memories` 而不是 `/memories/retain` |
| 422 Unprocessable Entity | metadata 值不是字符串 | `str(v) if v is not None else ""` |
| 404 Not Found | Health check 端点错误 | 使用 `/health` 而不是 `/healthcheck` |
| `hnsw index only supports up to 2000 dimensions` | Embedding 维度超限 | 使用 1536 维 |

### 6.3 Python 类型处理

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `content` 是 list 类型 | 多模态消息 | 提取 `type="text"` 的部分 |
| `metadata` 值类型错误 | 数字类型 | 转换为字符串 |
| `user_id` 可能为 None | 空值处理 | `conv.user_id or ""` |

---

## 7. 测试用例

### 7.1 基本功能测试
```bash
# 检查服务状态
/hindsight health

# 手动存储记忆
/hindsight retain 测试记忆内容

# 搜索记忆
/hindsight recall 测试

# 查看记忆列表
/hindsight list 10

# 查看统计
/hindsight stats
```

### 7.2 Mental Model 测试
```bash
# 查看所有 Mental Models
/hindsight reflect

# 查看指定模型
/hindsight reflect 用户画像

# 刷新 Mental Models
/hindsight refresh
```

### 7.3 综合问答测试
```bash
# 综合问答
/hindsight ask 用户的技术偏好是什么
```

### 7.4 历史导入测试
```bash
# 手动导入
/hindsight import 100

# 强制重新导入
/hindsight import 100 true

# 重置导入状态
/hindsight reset_import
```

### 7.5 API 测试
```bash
# 健康检查
curl http://192.168.1.10:8888/health

# 保留记忆
curl -X POST http://192.168.1.10:8888/v1/default/banks/astrbot/memories \
  -H "Content-Type: application/json" \
  -d '{"items": [{"content": "测试消息", "tags": ["test"]}], "async": true}'

# 检索记忆
curl -X POST http://192.168.1.10:8888/v1/default/banks/astrbot/memories/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "测试", "max_results": 5}'

# 列出 Mental Models
curl http://192.168.1.10:8888/v1/default/banks/astrbot/mental-models

# 刷新 Mental Model
curl -X POST http://192.168.1.10:8888/v1/default/banks/astrbot/mental-models/{id}/refresh
```

---

## 8. 后续优化方向

### 8.1 功能增强
- [ ] 支持按时间范围导入
- [ ] 支持按用户/群组过滤导入
- [ ] 支持导出记忆到文件
- [ ] 支持批量删除记忆
- [ ] `/hindsight search` 按标签筛选记忆

### 8.2 性能优化
- [ ] 添加导入进度条
- [ ] 支持断点续传
- [ ] 优化大量记忆时的 recall 性能

### 8.3 用户体验
- [ ] 添加导入预览功能
- [ ] 支持取消导入任务
- [ ] 优化错误提示信息

---

## 9. 版本历史

### v1.4.0 (2026-06-04)
**功能增强 - 按时间/用户/群组导入 + 导出 + 批量删除 + 标签搜索**

新增：
- `import` 命令支持时间范围过滤（start_time/end_time）
- `import` 命令支持用户过滤（user_id）
- `import` 命令支持群组过滤（group_id）
- `_parse_time_param()` - 时间参数解析（支持 YYYY-MM-DD、相对时间、unix timestamp）
- `/hindsight export` - 导出记忆到文件（json/csv/txt 格式）
- `/hindsight delete_batch` - 批量删除记忆（支持按标签删除）
- `/hindsight search` - 按标签搜索记忆
- HindsightClient.recall() 支持 tags 和 tags_match 参数

改进：
- import 命令现在显示过滤条件摘要
- export 支持多种格式（json/csv/txt）
- delete_batch 支持按标签或按时间删除
- search 命令使用 recall API 的 tags 参数进行标签搜索

### v1.3.0 (2026-06-04)
**群聊优化**

新增：
- `group_store_mode` - 群聊存储模式（all/bot_only/smart）
- `group_recall_mode` - 群聊回忆模式（always/bot_only/smart）
- `group_recall_interval` - 群聊回忆最小间隔（默认 5s）
- `group_min_relevance` - 群聊相关度阈值（默认 0.5）
- `group_inject_mm` - 群聊注入用户画像（默认关闭）
- 群聊噪声过滤（短消息、表情包、系统消息）
- 群聊发言人标注（存储时添加 [用户名] 前缀）
- 群聊频率限制（per-group 限流）
- stats 命令展示群聊存储/跳过统计

改进：
- 私聊/群聊差异化行为
- 群聊默认不注入 Mental Model（减少上下文长度）
- 群聊使用更低的相关度阈值（更宽泛地回忆）

### v1.2.0 (2026-06-04)
**性能优化 + Mental Model 上下文注入**

新增：
- `utils/ttl_cache.py` - TTL 缓存工具类
- `inject_mental_models` 配置项 - 控制是否注入用户画像到上下文
- `cache_ttl` 配置项 - Mental Model 缓存时长（默认 300s）
- `recall_cache_ttl` 配置项 - Recall 结果缓存时长（默认 60s）
- `batch` 参数 - retain 支持批量队列模式
- 后台清理任务（每 5 分钟清理过期缓存）
- stats 命令展示缓存命中率、队列大小等性能指标

改进：
- on_response retain 改为 fire-and-forget（不阻塞响应发送）
- 批量 retain 队列（满 10 条或 2s 自动 flush）
- Mental Model 上下文自动注入到 LLM（带 TTL 缓存）
- Recall 结果缓存（避免短时间重复查询）
- user_msg_cache 超过 1000 条自动裁剪
- terminate 时刷新未发送的队列

修复：
- 防止重复创建 Mental Models（创建前检查是否已存在同名模型）

### v1.1.0 (2026-06-04)
**命令增强 + 连接池优化 + 完整对话存储**

新增：
- `/hindsight retain` - 手动存储记忆
- `/hindsight ask` - 综合记忆问答（recall + mental model）
- `/hindsight reflect` - 查看 Mental Models
- `/hindsight refresh` - 手动刷新 Mental Models
- `retain_bot_replies` 配置项 - 控制是否存储助手回复
- `import_concurrency` 配置项 - 导入并发控制

改进：
- 同时存储用户消息和 bot 回复（完整对话上下文）
- HindsightClient 连接池复用（httpx.AsyncClient）
- 导入并发控制（asyncio.Semaphore）
- stats 命令展示 Mental Models 状态
- Dashboard 设置增强（slider、obvious_hint）
- terminate() 时正确关闭连接池

### v1.0.0 (2026-06-01)
**初始发布**

功能：
- 自动记忆存储（on_llm_response）
- 自动记忆回忆（on_llm_request）
- `/hindsight recall` - 搜索记忆
- `/hindsight list` - 查看记忆列表
- `/hindsight delete` - 删除记忆
- `/hindsight stats` - 记忆统计
- `/hindsight health` - 服务状态检查
- `/hindsight init` - 初始化记忆库
- `/hindsight import` - 导入历史对话
- `/hindsight reset_import` - 重置导入状态
- 自动创建 bank 和 Mental Models
- 幂等导入（防止重启重复导入）
- Dashboard 可视化配置

---

## 10. 参考资源

### 10.1 官方文档
- [AstrBot 插件开发文档](https://docs.astrbot.app/)
- [Hindsight GitHub](https://github.com/vectorize-io/hindsight)
- [AstrBot 插件模板](https://github.com/Soulter/helloworld)

### 10.2 项目文件
- 设计文档：`/home/aimercat/hindsight-astrbot-plugin-design.md`
- 插件目录：`~/data/plugins/astrbot_plugin_hindsight/`
- GitHub 仓库：https://github.com/aimercat1994/astrbot-plugin-hindsight

---

## 11. 附录

### 11.1 完整配置项
```json
{
  "hindsight_api_url": "http://192.168.1.10:8888",
  "hindsight_api_key": "",
  "bank_id": "astrbot",
  "auto_retain": true,
  "retain_bot_replies": true,
  "auto_recall": true,
  "max_recall_results": 5,
  "min_relevance": 0.7,
  "inject_mental_models": true,
  "cache_ttl": 300,
  "recall_cache_ttl": 60,
  "group_store_mode": "smart",
  "group_recall_mode": "smart",
  "group_recall_interval": 5.0,
  "group_min_relevance": 0.5,
  "group_inject_mm": false,
  "import_history_on_load": false,
  "import_history_limit": 100,
  "import_concurrency": 5,
  "exclude_groups": [],
  "exclude_users": []
}
```

### 11.2 命令列表
```bash
/hindsight health              # 检查服务状态
/hindsight recall <关键词>      # 搜索记忆
/hindsight retain <内容>        # 手动存储记忆
/hindsight ask <问题>           # 综合记忆问答
/hindsight reflect [名称]       # 查看 Mental Models
/hindsight refresh [名称]       # 刷新 Mental Models
/hindsight list [数量]          # 查看记忆列表
/hindsight delete <ID>         # 删除记忆
/hindsight stats               # 记忆统计
/hindsight init                # 初始化记忆库
/hindsight import [数量] [force] # 导入历史对话
/hindsight reset_import        # 重置导入状态
```
