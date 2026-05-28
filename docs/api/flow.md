# 流程

> LLM API 集成层的完整流程。从客户端创建、流式请求、消息格式转换到错误处理和重试。

---

## 概览

API 模块负责所有与 LLM 后端 API 的通信。核心职责：创建 SDK 客户端 → 构建请求参数 → 流式发送 → 解析响应事件 → 错误处理和重试。同时提供协议转换代理支持 OpenAI 兼容后端。v1 实现完整的 Anthropic API 调用 + OpenAI 代理支持。

---

## 阶段1：SDK 客户端创建

### 多后端支持

`getAnthropicClient()` 支持 5 个后端：

| 后端 | 条件 | SDK 包 | v1 |
|---|---|---|---|
| **直接 API** | 默认 | `anthropic` | 实现 |
| **AWS Bedrock** | `CLAUDE_CODE_USE_BEDROCK` | `@anthropic-ai/bedrock-sdk` | 实现 |
| **Azure Foundry** | `CLAUDE_CODE_USE_FOUNDRY` | `@anthropic-ai/foundry-sdk` | 不实现 |
| **Vertex AI** | `CLAUDE_CODE_USE_VERTEX` | `@anthropic-ai/vertex-sdk` | 不实现 |
| **OpenAI 代理** | 服务器 proxy 模式 | OpenAI 协议转换 | 实现 |

### 客户端配置

```
client = Anthropic({
  apiKey:               来自环境变量或 keychain 帮助器
  baseURL:              可选（用于自定义端点）
  timeout:              600 秒（默认）
  maxRetries:           0（自带重试逻辑）

  defaultHeaders:
    x-app:              'cli'
    User-Agent:         包含版本号
    X-Claude-Code-Session-Id:  会话 UUID
    x-client-request-id:      请求 UUID

  fetch:                注入 x-client-request-id 的自定义 fetch 包装器
})
```

### API 密钥解析

1. `ANTHROPIC_API_KEY` 环境变量
2. `CLAUDE_CODE_API_KEY_HELPER_TTL_MS` — 键帮助器路径，定期刷新
3. API key 帮助器子进程（macOS keychain）
4. OAuth 访问令牌（Claude.ai 订阅者）

---

## 阶段2：流式查询（主路径）

### 入口函数

```
queryModel(messages, systemPrompt, thinkingConfig, tools, signal, options)
    → AsyncGenerator[StreamEvent | AssistantMessage | SystemAPIErrorMessage]
```

这是单一核心函数，同时处理流式和非流式请求（错误时回退）。

### 请求构建流程

1. **关闭开关检查** — 非订阅者的 GrowthBook 功能开关
2. **模型解析** — Bedrock 推理配置文件映射
3. **工具 Schema 构建** — Advisor 工具、工具搜索、延迟加载
4. **消息规范化** — `normalizeMessagesForAPI()`
   - 剥离 Advisor 块（无 beta 标头时）
   - 修复孤立的 tool_use/tool_result 对
   - 剥离多余媒体项（>100 限制）
   - 注入延迟加载的工具名
5. **系统提示词构建** — 属性标头 + CLI 前缀 + Advisor 指令 → `buildSystemPromptBlocks()`
6. **缓存断点** — `addCacheBreakpoints()` 放置 `cache_control` 标记
7. **Beta 标头锁定** — AFK 模式、快速模式、缓存编辑、思考清除
8. **参数构建** — `paramsFromContext()`
   - 1M 上下文 beta（Sonnet 实验时）
   - 思考配置（`adaptive` / `enabled` + `budget_tokens`）
   - 快速模式速度（`'fast'` 或默认）
   - 温度（仅禁用思考时）
   - 最终：model、messages、system、tools、max_tokens、betas

### 流式响应处理

```
anthropic.beta.messages.create({ stream: true }).withResponse()
    → 原始 HTTP 响应 + 流
    → 解析 SSE 事件流
```

**流事件循环：**

| 事件 | 操作 |
|---|---|
| `message_start` | 捕获 partialMessage、TTFT、初始使用情况 |
| `content_block_start` | 初始化块（tool_use / text / thinking） |
| `content_block_delta` | |
| `text_delta` | 追加到文本内容 |
| `input_json_delta` | 追加到 tool_use 输入 JSON 字符串 |
| `thinking_delta` | 追加到思考内容 |
| `signature_delta` | 设置思考签名 |
| `content_block_stop` | 创建一个 AssistantMessage，yield 每个内容块一个 |
| `message_delta` | 更新使用情况、stop_reason、成本 |
| `message_stop` | 无操作 |

**每个块：** yield `{ type: 'stream_event', event: part }` 供消费者使用

### 看门狗

- **流空闲看门狗**：90 秒无数据 → 中止流（可配置）
- **停顿检测**：记录 >30 秒的事件间隙

### 非流式回退

当流式错误发生时（非用户中止）：
1. 检查 `CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK`
2. 调用 `executeNonStreamingRequest()` 并重试
3. 对连续 529 预算进行计数
4. 成功时：规范化内容 → 创建 AssistantMessage → yield

---

## 阶段3：重试逻辑

### `withRetry()` 参数

```
withRetry(getClient, operation, options):
  maxRetries:        10（默认，DEFAULT_MAX_RETRIES）
  BASE_DELAY_MS:     500ms（指数退避，25% 抖动）
  MAX_529_RETRIES:   3（触发 Opus→Sonnet 回退）
  signal:            AbortSignal
```

### 可重试错误

- **408**（超时）、**409**（锁超时）
- **429**（速率限制）— ClaudeAI 订阅者除外（非企业）
- **529**（过载）— 仅前台查询源
- **5xx**（服务器错误）
- **401/403** — 刷新认证令牌
- **APIConnectionError**（包括 ECONNRESET、EPIPE）
- **Max tokens context overflow**（400 带可解析消息）

### 特别行为

- **快速模式冷却**：429/529 处理 — 短延迟（<20s）在快速模式激活下重试；长延迟触发冷却到标准速度
- **持久重试**（`CLAUDE_CODE_UNATTENDED_RETRY`）：对于无监督会话，无限重试 429/529，带分块保持活跃 yield
- **模型回退**：连续 3 次 Opus 529 → `FallbackTriggeredError`
- **客户端重建**：认证错误或陈旧连接 → 创建新的 Anthropic 客户端

---

## 阶段4：Haiku/轻量级查询

### `queryHaiku()`（无工具无思考）

专用路径用于轻量级分类/标题生成：

1. 使用非流式路径
2. 禁用思考
3. 无工具
4. 无缓存断点
5. 仅返回 AssistantMessage

### `queryWithModel()`

功能完整的特定模型查询路径。与 `queryModel` 形状相同，但通过给定的模型名称传递。

---

## 阶段5：错误处理和用户消息

### 错误分类

`classifyAPIError()` 将错误映射到标准化的分析字符串。

### 用户可见错误

`getAssistantMessageFromError()` 将原始错误映射为可操作消息：

| 错误 | 消息 |
|---|---|
| 超时（APIConnectionTimeoutError） | "请求超时" |
| 图片过大 | "图片过大" |
| 提示过长（413） | "提示过长"（含 Token 计数） |
| 速率限制（429） | 解析 `anthropic-ratelimit-*` 响应标头 |
| 认证失败（401/403） | "/login" 指导 |
| 模型未找到（404） | 回退建议 |
| 连接错误（SSL、DNS 等） | 通过 `formatAPIError()` 格式化 |
| 工具使用不匹配（400） | `/rewind` 恢复指令 |

### 拒绝处理

`stop_reason: 'refusal'` 由 `getErrorMessageIfRefusal()` 处理，提供使用策略指导。

### 连接错误详情

`extractConnectionErrorDetails()` 遍历错误因果链，获取根 SSL/TLS 错误代码。支持约 20 种 SSL 错误代码。

---

## 阶段6：使用情况跟踪

### 增量使用情况更新

```
EMPTY_USAGE = {
  input_tokens: 0,
  cache_creation_input_tokens: 0,
  cache_read_input_tokens: 0,
  output_tokens: 0,
  server_tool_use: { web_search_requests: 0, web_fetch_requests: 0 },
  service_tier: 'standard',
  cache_creation: { ephemeral_1h: 0, ephemeral_5m: 0 },
}
```

`updateUsage()` 从流事件累积使用情况。每次事件包含截至该点的完整使用情况。防止零覆盖输入 Token 字段。

`accumulateUsage()` 跨多个助理轮次进行汇总。

### 成本计算

```
每轮成本 = calculateUSDCost(resolvedModel, usage)
会话总额 = addToTotalSessionCost(每轮成本)
```

---

## 阶段7：代理协议转换

### 入口点

`handleProxyRequest()` — 对 `/proxy/v1/messages` 的 HTTP POST 处理：

1. 从 `ProviderService` 读取提供商配置
2. 确定格式：`openai_chat` 或 `openai_responses`
3. 解析传入的 Anthropic Messages API 请求体

### 流式代理路径

```
Anthropic 请求
  → anthropicToOpenaiChat.transform()
  → fetch 到 OpenAI 上游
  → openaiChatStreamToAnthropic.transform()
  → Anthropic 流式事件
```

### 非流式代理路径

```
Anthropic 请求
  → anthropicToOpenaiChat.transform()
  → fetch 到 OpenAI 上游
  → openaiChatToAnthropic.transform()
  → Anthropic JSON 响应
```

### Responses API 特殊情况

当上游在非流式模式下要求 `stream: true` 时：
1. 透明重试为流式
2. 通过 `openaiResponsesStreamToResponse` 聚合回普通 JSON

### 转换模块

| 模块 | 方向 |
|---|---|
| `anthropicToOpenaiChat` | Anthropic Messages → OpenAI 聊天完成 |
| `openaiChatToAnthropic` | OpenAI 聊天完成 → Anthropic 响应 |
| `anthropicToOpenaiResponses` | Anthropic Messages → OpenAI 响应 |
| `openaiResponsesToAnthropic` | OpenAI 响应 → Anthropic 响应 |
| `openaiChatStreamToAnthropic` | OpenAI SSE 流 → Anthropic SSE 流 |
| `openaiResponsesStreamToAnthropic` | OpenAI Responses SSE → Anthropic SSE |

### 消息格式类型

```
AnthropicRequest:
  model: str
  max_tokens: int
  system: str | list[TextBlock]
  messages: list[Message]
  tools: list[Tool]
  ...（其余参数）

OpenAIChatRequest:
  model: str
  messages: list[OpenAIMessage]
  tools: list[OpenAIFunction]      # Functions 工具格式
  stream: bool
  ...（其余参数）

OpenAIResponsesRequest:
  model: str
  input: str | list[InputItem]
  tools: list[OpenAITool]          # Responses API 工具格式
  stream: bool
  ...（其余参数）
```

---

## v1 实际实现 (Phase 1)

general-agent v1 Phase 1 API 集成：

1. **双接口分发** — `GENERAL_AGENT_PROVIDER` 控制 OpenAI 或 Anthropic
2. **OpenAI 格式** — 调任意提供商 `/v1/chat/completions`，流式/非流式
3. **Anthropic 格式** — 调任意提供商 `/anthropic` 端点，Anthropic SDK
4. **流式查询** — async generator，text_delta + tool_use 累积
5. **非流式回退** — 流式失败自动 fallback
6. **重试** — 指数退避 + 断路器（5xxx/429）
7. **错误处理** — 分类 + 重试进度消息
8. **消息格式转换** — OpenAI ↔ internal ↔ Anthropic 双向转换
9. **使用统计** — Token 数 + 耗时 + DeepSeek 计费

与文档计划差异：
- 不做 Anthropic 官方 API（仅 `/anthropic` 端点）
- 不做 OpenAI 代理层（直接 SDK 调用，无反向代理）
- 不做 Bedrock/Vertex/Foundry 后端

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0
>
> 参考源：cc-haha src/services/api/claude.ts, client.ts, withRetry.ts, errors.ts; src/server/proxy/handler.ts, transform/
