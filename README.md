# global-memory

跨项目全局记忆 MCP server，为 ZCode 设计，兼容任何 MCP 客户端（Claude Desktop、Codex、Cursor 等）。解决编码 Agent 原生记忆按项目隔离、机器级事实（电脑配置、软件环境、全局路径）跨项目反复重查的问题。零第三方依赖（仅需 `mcp` 包），单文件部署。

## 定位与分工

| 层 | 位置 | 用途 |
|---|---|---|
| 全局指令 | `C:\Users\PC\.zcode\AGENTS.md` | 行为约束，每次会话自动注入 |
| **全局记忆（本项目）** | `C:\Users\PC\.zcode\memories\global\` | 机器级/用户级跨项目事实，MCP 工具读写检索 |
| 项目记忆（ZCode 原生） | `C:\Users\PC\.zcode\cli\memories\projects\<hash>\` | 单项目工作事实，auto-memory 机制管理 |
| 第二大脑 | `D:\cherry-workplace\knowledge-hub\vault` | 可检索长文档知识库 |

## 工具集（5 个）

- `memory_write(name, description, content, type)` — 写/更新一条记忆，自动维护 `MEMORY.md` 索引
- `memory_read(name)` — 按名读取
- `memory_search(query, type?, limit?)` — 关键词检索（中文 bigram + 英文分词打分，零模型依赖）
- `memory_list(type?)` — 列出索引（可按类型过滤）
- `memory_delete(name)` — 删除（含索引行）

记忆类型：`env`（机器/环境事实）、`user`（用户偏好）、`feedback`（工作方式指导）、`project`（跨项目进行中事项）、`reference`（外部资源指针）。`env` 为本项目在 ZCode 原生四类型基础上的扩展。

## 文件格式

与 ZCode auto-memory 完全一致，可手工编辑（手改后无需重建索引，工具按需扫描目录）：

```markdown
---
name: hardware-overview
description: 台式机硬件配置一览
metadata:
  type: env
---

正文短句，直接给结论。
```

## 配置与运行

- 解释器：Python 3.10+，仅依赖 `mcp` 包（`pip install mcp`）
- 存储目录：默认 `~/.zcode/memories/global/`（Windows 为 `C:\Users\<用户>\.zcode\memories\global\`），可用环境变量 `GLOBAL_MEMORY_DIR` 覆盖
- 传输：stdio，单文件启动 `python server.py`

### 通用 MCP 客户端接入

以 Claude Desktop 为例（其他客户端同理，改 `mcpServers` 配置即可）：

```json
{
  "mcpServers": {
    "global-memory": {
      "command": "python",
      "args": ["-X", "utf8", "/path/to/global-memory/server.py"],
      "env": { "GLOBAL_MEMORY_DIR": "/path/to/memory/dir" }
    }
  }
}
```

`-X utf8` 保证中文在 Windows 管道下无乱码（建议保留）。

### ZCode 接入（本机示例）

已注册于 ZCode `config.json` 的 `mcp.servers["global-memory"]`：

```json
{
  "enabled": true,
  "command": "D:\\anaconda3\\python.exe",
  "args": ["-X", "utf8", "D:\\cherry-workplace\\mcp_servers\\global-memory\\server.py"]
}
```

## 升级路径

当前检索为纯打分（无向量）。记忆量超千条或召回不佳时，可接入嵌入模型升级为混合检索，工具接口不变。

## License

[MIT](LICENSE)
