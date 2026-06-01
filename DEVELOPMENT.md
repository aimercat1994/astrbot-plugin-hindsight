# Hindsight AstrBot 插件开发日志

**开发日期**：2026-06-01  
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
Hindsight API Client (httpx 异步调用)
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
└── utils/
    ├── __init__.py
    └── hindsight_client.py  # API 客户端
```

### 2.2 核心组件
- **HindsightClient**: 封装 Hindsight REST API 调用
- **HindsightPlugin**: AstrBot 插件主类，处理事件和命令
- **BANK_CONFIG**: 预定义的 bank 配置模板

---

## 3. 开发过程

### 3.1 第一阶段：基础框架搭建

**时间**：10:00-10:30

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

### 3.2 第二阶段：命令组实现

**时间**：10:30-11:00

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

### 3.3 第三阶段：自动记忆功能

**时间**：11:00-11:30

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

**最终实现**：
```python
@filter.on_llm_response()
async def on_response(self, event: AstrMessageEvent):
    """在 LLM 响应后存储对话记忆"""
    if not self.config.get("auto_retain", True):
        return
    
    content = f"用户: {event.message_str}"
    await self.hindsight.retain(
        content=content,
        bank_id=self.bank_id,
        tags=["conversation"],
        metadata={...}
    )
```

---

### 3.4 第四阶段：Bank 初始化

**时间**：11:30-12:00

**任务**：
- 自动创建 Hindsight bank
- 自动创建 Mental Models（用户画像、待办事项）

**遇到的问题**：
- Health check 端点错误：使用 `/healthcheck` 返回 404
- 正确端点是 `/health`

**解决方案**：
```python
async def health_check(self) -> bool:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
    except Exception:
        return False
```

**Bank 配置模板**：
```python
BANK_CONFIG = {
    "mental_models": [
        {
            "id": "user-profile",
            "name": "用户画像",
            "source_query": "我们对这个用户了解什么？",
            "max_tokens": 2048,
        },
        {
            "id": "active-tasks",
            "name": "待办事项与承诺",
            "source_query": "用户当前在追踪什么任务？",
            "max_tokens": 1024,
        },
    ],
}
```

---

### 3.5 第五阶段：历史对话导入

**时间**：12:00-13:00

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

**解决方案**：
```python
if isinstance(content, list):
    text_parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text_parts.append(item.get("text", ""))
        elif isinstance(item, str):
            text_parts.append(item)
    content = " ".join(text_parts)
```

**导入结果**：
- 成功导入 171 条消息
- 只有 1 个对话的部分消息返回 422（可能是并发或临时性问题）

---

### 3.6 第六阶段：Dashboard 配置

**时间**：13:00-13:30

**任务**：
- 添加 `import_history_on_load` 配置项
- 添加 `import_history_limit` 配置项

**配置 Schema**：
```json
{
  "import_history_on_load": {
    "description": "启动时自动导入历史",
    "type": "bool",
    "default": false,
    "hint": "插件加载时自动导入 AstrBot 历史对话"
  },
  "import_history_limit": {
    "description": "历史导入数量",
    "type": "int",
    "default": 100,
    "hint": "自动导入时的最大对话数量"
  }
}
```

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

### 4.3 为什么使用 `async=True`？
- 异步处理可以提高性能
- 避免阻塞 AstrBot 主线程
- Hindsight 后台处理实体提取和 embedding 生成

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

# 存储记忆
/hindsight recall 测试

# 查看记忆列表
/hindsight list 10

# 查看统计
/hindsight stats
```

### 7.2 历史导入测试
```bash
# 手动导入
/hindsight import 100

# 自动导入（在 Dashboard 中开启）
# 重启 AstrBot 观察日志
```

### 7.3 API 测试
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
```

---

## 8. 后续优化方向

### 8.1 功能增强
- [ ] 支持导入机器人回复（可选配置）
- [ ] 支持按时间范围导入
- [ ] 支持按用户/群组过滤导入
- [ ] 支持导出记忆到文件
- [ ] 支持批量删除记忆

### 8.2 性能优化
- [ ] 批量导入时使用批量 API（如果 Hindsight 支持）
- [ ] 添加导入进度条
- [ ] 支持断点续传
- [ ] 优化并发请求控制

### 8.3 用户体验
- [ ] 添加导入预览功能
- [ ] 支持取消导入任务
- [ ] 添加导入历史记录
- [ ] 优化错误提示信息

### 8.4 监控和日志
- [ ] 添加导入统计面板
- [ ] 记录导入失败的具体原因
- [ ] 支持导出导入日志

---

## 9. 参考资源

### 9.1 官方文档
- [AstrBot 插件开发文档](https://docs.astrbot.app/)
- [Hindsight GitHub](https://github.com/vectorize-io/hindsight)
- [AstrBot 插件模板](https://github.com/Soulter/helloworld)

### 9.2 相关技能
- `astrbot-plugin-dev`: AstrBot 插件开发全流程
- `hindsight`: Hindsight 部署和集成

### 9.3 项目文件
- 设计文档：`/home/aimercat/hindsight-astrbot-plugin-design.md`
- 插件目录：`~/data/plugins/astrbot_plugin_hindsight/`
- GitHub 仓库：https://github.com/aimercat1994/astrbot-plugin-hindsight

---

## 10. 开发时间线

| 时间 | 任务 | 状态 |
|------|------|------|
| 10:00 | 创建项目结构 | ✅ |
| 10:15 | 实现 HindsightClient | ✅ |
| 10:30 | 实现命令组 | ✅ |
| 10:45 | 实现自动记忆 | ✅ |
| 11:00 | 实现 Bank 初始化 | ✅ |
| 11:30 | 实现历史导入 | ✅ |
| 12:00 | 修复 API 路径 | ✅ |
| 12:30 | 修复 metadata 类型 | ✅ |
| 13:00 | 添加 Dashboard 配置 | ✅ |
| 13:30 | 编写 README | ✅ |
| 14:00 | 推送到 GitHub | ✅ |

**总开发时间**：约 4 小时

---

## 11. 附录

### 11.1 完整配置项
```json
{
  "hindsight_api_url": "http://192.168.1.10:8888",
  "hindsight_api_key": "",
  "bank_id": "astrbot",
  "auto_retain": true,
  "auto_recall": true,
  "max_recall_results": 5,
  "min_relevance": 0.7,
  "import_history_on_load": false,
  "import_history_limit": 100,
  "exclude_groups": [],
  "exclude_users": []
}
```

### 11.2 命令列表
```bash
/hindsight health              # 检查服务状态
/hindsight recall <关键词>      # 搜索记忆
/hindsight list [数量]          # 查看记忆列表
/hindsight delete <ID>         # 删除记忆
/hindsight stats               # 查看统计
/hindsight init                # 初始化 bank
/hindsight import [数量]        # 导入历史对话
```

### 11.3 日志关键字
```
Hindsight 插件已加载
已创建 bank 'astrbot'
已创建 mental model: 用户画像
已创建 mental model: 待办事项与承诺
Bank 'astrbot' 初始化完成
自动导入历史完成，共导入 XXX 条消息
```

---

**文档版本**：v1.0  
**最后更新**：2026-06-01  
**维护者**：aimercat
