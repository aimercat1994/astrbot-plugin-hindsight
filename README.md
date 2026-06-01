# AstrBot Hindsight 记忆助手

[Hindsight](https://github.com/vectorize-io/hindsight) 长期记忆系统集成插件，让 AstrBot 机器人拥有跨会话记忆能力。

## ✨ 功能特性

- **自动记忆存储** - 对话时自动存储用户消息到 Hindsight
- **智能回忆注入** - 对话时自动注入相关历史记忆作为上下文
- **历史对话导入** - 一键导入 AstrBot 历史对话到 Hindsight
- **Dashboard 配置** - 可视化配置界面，无需手动编辑文件
- **Mental Models** - 自动创建用户画像、待办事项等心智模型

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

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `hindsight_api_url` | Hindsight API 地址 | `http://192.168.1.10:8888` |
| `bank_id` | 记忆库 ID | `astrbot` |
| `auto_retain` | 自动记忆存储 | ✅ 开启 |
| `auto_recall` | 自动记忆回忆 | ✅ 开启 |
| `max_recall_results` | 最大回忆数量 | 5 |
| `min_relevance` | 最小相关度阈值 | 0.7 |
| `import_history_on_load` | 启动时自动导入历史 | ❌ 关闭 |
| `import_history_limit` | 历史导入数量 | 100 |
| `exclude_groups` | 掘除的群组 ID | 空 |
| `exclude_users` | 排除的用户 ID | 空 |

## 🎮 使用

### 命令列表

```bash
/hindsight health              # 检查 Hindsight 服务状态
/hindsight recall <关键词>      # 搜索相关记忆
/hindsight list [数量]          # 查看最近记忆
/hindsight delete <ID>         # 删除指定记忆
/hindsight stats               # 查看记忆统计
/hindsight init                # 初始化/重置记忆库配置
/hindsight import [数量]        # 导入 AstrBot 历史对话
```

### 示例

```bash
# 检查服务是否正常
/hindsight health

# 搜索关于"Python"的记忆
/hindsight recall Python

# 导入最近 200 条历史对话
/hindsight import 200

# 查看记忆统计
/hindsight stats
```

## 🏗️ 前置要求

- AstrBot >= 4.16
- Hindsight API 服务（[部署文档](https://github.com/vectorize-io/hindsight)）

## 📝 工作原理

```
用户消息 → AstrBot 插件
              ↓
         ┌────┴────┐
         ↓         ↓
    自动回忆    自动存储
   (on_request) (on_response)
         ↓         ↓
   注入上下文   存储到 Hindsight
         ↓
      LLM 生成回复
```

- **自动回忆**：在 LLM 请求前，从 Hindsight 检索相关记忆注入上下文
- **自动存储**：在 LLM 响应后，将用户消息存储到 Hindsight
- **历史导入**：遍历 AstrBot 对话历史，批量导入到 Hindsight

## 🔧 常见问题

### Q: 如何检查 Hindsight 服务是否正常？

```bash
/hindsight health
```

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

### Q: 如何排除特定群组不记录记忆？

在插件设置中添加群组 ID 到 `exclude_groups` 列表。

## 📄 开源协议

MIT License

## 🔗 相关链接

- [AstrBot](https://github.com/Soulter/AstrBot)
- [Hindsight](https://github.com/vectorize-io/hindsight)
- [插件设计文档](https://github.com/aimercat1994/astrbot-plugin-hindsight/blob/main/design.md)
