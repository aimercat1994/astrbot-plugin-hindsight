# AstrBot Hindsight 记忆助手

[Hindsight](https://github.com/vectorize-io/hindsight) 长期记忆系统集成插件，让 AstrBot 机器人拥有跨会话记忆能力。支持私聊和群聊场景，群聊智能过滤噪声、频率限制、差异化行为。

## ✨ 功能特性

- **自动记忆存储** - 对话时自动存储用户消息和助手回复到 Hindsight
- **智能回忆注入** - 对话时自动注入相关历史记忆 + 用户画像作为上下文
- **手动记忆管理** - 手动存储、搜索、删除记忆
- **Mental Models** - 用户画像、待办事项等心智模型查询与刷新
- **综合记忆问答** - 结合记忆检索和心智模型的智能问答
- **群聊优化** - 智能噪声过滤、频率限制、差异化存储/回忆策略
- **历史对话导入** - 一键导入 AstrBot 历史对话到 Hindsight（支持并发控制）
- **Dashboard 配置** - 可视化配置界面，无需手动编辑文件
- **性能优化** - 连接池复用、TTL 缓存、fire-and-forget、批量 retain

## 📦 安装

### 方式一：插件市场安装

在 AstrBot Dashboard → 插件市场搜索「Hindsight」安装

### 方式二：手动安装

```bash
cd ~/data/plugins/
git clone https://github.com/aimercat1994/astrbot-plugin-hindsight.git
```

重启 AstrBot 生效。

## ⚙️ 配置

进入 AstrBot Dashboard → 插件管理 → Hindsight 记忆助手 → 设置

### 连接配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `hindsight_api_url` | Hindsight API 地址 | `http://192.168.1.10:8888` |
| `hindsight_api_key` | API Key（留空不需要认证） | 空 |
| `bank_id` | 记忆库 ID，隔离不同机器人记忆 | `astrbot` |

### 记忆管理

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `auto_retain` | 自动记忆存储 | ✅ 开启 |
| `retain_bot_replies` | 存储助手回复（关闭则仅存用户消息） | ✅ 开启 |
| `auto_recall` | 自动记忆回忆 | ✅ 开启 |
| `max_recall_results` | 每次注入的最大记忆条数 | 5 |
| `min_relevance` | 最小相关度阈值（私聊，0-1，滑块调节） | 0.7 |
| `inject_mental_models` | 私聊时注入用户画像到上下文 | ✅ 开启 |

### 群聊优化

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `group_store_mode` | 群聊存储模式 | `smart` |
| `group_recall_mode` | 群聊回忆模式 | `smart` |
| `group_recall_interval` | 群聊回忆最小间隔（秒） | 5.0 |
| `group_min_relevance` | 群聊相关度阈值（0-1，滑块） | 0.5 |
| `group_inject_mm` | 群聊注入用户画像 | ❌ 关闭 |

**存储模式说明：**
- `all` - 存储所有群消息（过滤噪声后）
- `bot_only` - 仅存储 bot 参与的对话
- `smart` - 智能模式：过滤噪声 + 长消息 + 问句 + bot 参与

**回忆模式说明：**
- `always` - 每条群消息都触发 recall（消耗较大）
- `bot_only` - 仅 bot 被 @ 或回复时触发
- `smart` - 被 @ 或消息较长或含问号时触发

### 性能调优

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `cache_ttl` | Mental Model 缓存时长（秒） | 300 |
| `recall_cache_ttl` | Recall 结果缓存时长（秒） | 60 |

### 历史导入

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `import_history_on_load` | 启动时自动导入历史对话 | ❌ 关闭 |
| `import_history_limit` | 历史导入数量上限 | 100 |
| `import_concurrency` | 导入并发请求数 | 5 |

### 过滤规则

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `exclude_groups` | 排除的群组 ID | 空 |
| `exclude_users` | 排除的用户 ID | 空 |

## 🎮 使用

### 命令列表

```bash
/hindsight health              # 检查 Hindsight 服务状态
/hindsight recall <关键词>      # 搜索相关记忆
/hindsight retain <内容>        # 手动存储一条记忆
/hindsight ask <问题>           # 综合记忆问答（recall + 心智模型）
/hindsight reflect [名称]       # 查看 Mental Models（用户画像/待办等）
/hindsight refresh [名称]       # 手动刷新 Mental Model
/hindsight list [数量]          # 查看最近记忆
/hindsight delete <ID>         # 删除指定记忆
/hindsight stats               # 查看记忆统计（含群聊性能指标）
/hindsight init                # 初始化/重置记忆库配置
/hindsight import [数量] [force] [start_time] [end_time] [user_id] [group_id]  # 导入历史对话
/hindsight export [数量] [格式]  # 导出记忆到文件（json/csv/txt）
/hindsight delete_batch [标签] [数量]  # 批量删除记忆
/hindsight search <标签> [数量]  # 按标签搜索记忆
/hindsight reset_import        # 重置导入状态
```

### 示例

```bash
# 检查服务是否正常
/hindsight health

# 手动存储一条记忆
/hindsight retain 用户喜欢用 Python 写脚本

# 搜索关于"Python"的记忆
/hindsight recall Python

# 综合问答：结合记忆和用户画像回答
/hindsight ask 用户的技术偏好是什么

# 查看用户画像
/hindsight reflect 用户画像

# 刷新所有 Mental Models
/hindsight refresh

# 导入最近 200 条历史对话
/hindsight import 200

# 强制重新导入（忽略已导入记录）
/hindsight import 100 true

# 按时间范围导入（最近7天）
/hindsight import 100 false 7d

# 按时间范围导入（指定日期范围）
/hindsight import 100 false 2024-01-01 2024-01-31

# 只导入特定用户的对话
/hindsight import 100 false "" "" 123456789

# 只导入特定群组的对话
/hindsight import 100 false "" "" "" 976177610

# 导出记忆到 JSON 文件
/hindsight export 100 json

# 导出记忆到 CSV 文件
/hindsight export 50 csv

# 导出记忆到 TXT 文件
/hindsight export 200 txt

# 批量删除最近 10 条记忆
/hindsight delete_batch "" 10

# 按标签批量删除
/hindsight delete_batch conversation 20

# 按标签搜索记忆
/hindsight search conversation 10

# 查看记忆统计（含群聊性能指标）
/hindsight stats
```

## 🏗️ 前置要求

- AstrBot >= 4.16
- Hindsight API 服务（[部署文档](https://github.com/vectorize-io/hindsight)）

## 📝 工作原理

```
用户消息 → AstrBot 插件
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
 私聊模式            群聊模式
    ↓                   ↓
 总是 recall        smart 过滤 + 频率限制
 总是 store         智能存储（过滤噪声）
 注入 MM            默认不注入 MM
    ↓                   ↓
         ┌────┴────┐
         ↓         ↓
    自动回忆    自动存储
   (on_request) (on_response)
         ↓         ↓
   注入上下文   存储到 Hindsight（fire-and-forget）
         ↓
      LLM 生成回复
```

- **私聊**：全量 recall + MM 注入 + 全量存储
- **群聊**：smart 过滤 + 频率限制 + 差异化存储
- **群聊噪声过滤**：自动跳过短消息、表情包、系统消息
- **群聊发言人**：存储时自动添加 `[用户名]` 前缀
- **性能优化**：连接池复用、TTL 缓存、fire-and-forget、批量 retain

## 🔧 常见问题

### Q: 如何检查 Hindsight 服务是否正常？

```bash
/hindsight health
```

### Q: 群聊消息太多，记忆库被刷屏了？

将 `group_store_mode` 设为 `smart` 或 `bot_only`，自动过滤噪声。

### Q: 群聊 recall 太频繁，API 压力大？

1. 将 `group_recall_mode` 设为 `smart` 或 `bot_only`
2. 增大 `group_recall_interval`（如 10 秒）

### Q: 群聊中想注入用户画像？

将 `group_inject_mm` 开启（会增加上下文长度）。

### Q: 导入历史对话失败怎么办？

检查 Hindsight 服务状态和网络连接，然后重试：

```bash
/hindsight health
/hindsight import 100
```

### Q: 如何重置记忆库配置？

```bash
/hindsight init
```

### Q: 只想存储用户消息，不存储助手回复？

在设置中关闭 `retain_bot_replies` 开关。

## 📄 开源协议

MIT License

## 🔗 相关链接

- [AstrBot](https://github.com/Soulter/AstrBot)
- [Hindsight](https://github.com/vectorize-io/hindsight)
- [插件开发文档](https://github.com/aimercat1994/astrbot-plugin-hindsight/blob/main/DEVELOPMENT.md)
