# 数据结构

> LLM API 集成层的核心数据结构。请求/响应格式、流式事件、错误类型。

---

## API 请求参数

```
AnthropicRequest:
  model: str                           # 模型标识符
  max_tokens: int                      # 最大输出 Token
  system: str | list[TextBlock]        # 系统提示词
  messages: list[Message]             # 对话消息
  tools: list[Tool]                    # 工具定义
  tool_choice: str                     # (可选) 'auto' | 'any' | 'tool'
  stop_sequences: list[str]           # (可选) 停止序列
  temperature: float                   # (可选) 温度（仅禁用思考时）
  thinking:
    type: 'enabled' | 'adaptive' | 'disabled'
    budget_tokens: int                # (可选) 思考预算 Token
  betas: list[str]                     # (可选) beta 功能标头
  metadata: dict                       # (可选) 用户标识
```

## API 响应

```
AnthropicResponse:
  id: str                              # 响应 ID
  type: 'message'
  role: 'assistant'
  model: str                           # 使用的模型
  content: list[ContentBlock]         # 文本/工具使用块
  stop_reason: str                     # 'end_turn' | 'max_tokens' | 'tool_use'
  stop_sequence: str                   # (可选) 匹配的停止序列
  usage:
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
    server_tool_use:                   # 服务器端工具使用
      web_search_requests: int
      web_fetch_requests: int
    service_tier: 'standard' | 'premium'
    cache_creation:
      ephemeral_1h_input_tokens: int
      ephemeral_5m_input_tokens: int
```

---

## 流式事件类型

```
StreamEvent:
  type: 'stream_event'
  event:
    type: 'message_start' |
          'content_block_start' |
          'content_block_delta' |
          'content_block_stop' |
          'message_delta' |
          'message_stop'
    # ... 事件特定字段由 Anthropic SDK 定义

TextDelta:
  type: 'text_delta'
  text: str                            # 累计文本块
  text_content_block_index: int        # 内容块索引

InputJsonDelta:
  type: 'input_json_delta'
  partial_json: str                    # 完整 JSON 字符串
  tool_use_content_block_index: int

ThinkingDelta:
  type: 'thinking_delta'
  thinking: str                        # 思考文本

SignatureDelta:
  type: 'signature_delta'
  signature: str
```

---

## 内部选项类型

```
APIOptions:
  # 模型
  model: str                           # 主模型
  fallbackModel: str                   # (可选) 回退模型

  # 工具
  extraToolSchemas: list               # (可选) 额外工具 Schema
  mcpTools: list                       # MCP 工具
  hasPendingMcpServers: bool           # 是否有待连接的 MCP 服务器

  # 查询元数据
  querySource: str                     # 'repl_main_thread' | 'agent:custom' | 'compact' 等
  agentId: str                         # (可选) Agent ID
  queryTracking: dict                  # (可选) 查询链深度

  # 思考/努力
  enablePromptCaching: bool            # 启用提示缓存
  skipCacheWrite: bool                 # 跳过缓存写入

  # 其他
  maxOutputTokensOverride: int         # (可选) 覆盖最大输出 Token
  temperatureOverride: float           # (可选) 覆盖温度
  effortValue: str                     # (可选) 努力值
  outputFormat: dict                   # (可选) JSON 输出格式
  fastMode: bool                       # (可选) 快速模式
  toolChoice: 'auto' | 'any'           # (可选) 工具选择

  # 交互
  isNonInteractiveSession: bool        # 非交互模式
  hasAppendSystemPrompt: bool          # 是否有追加提示
```

---

## 使用情况

```
Usage:
  input_tokens: int                    # 输入 Token
  output_tokens: int                   # 输出 Token
  cache_creation_input_tokens: int     # 缓存创建输入 Token
  cache_read_input_tokens: int         # 缓存读取输入 Token
  server_tool_use:
    web_search_requests: int
    web_fetch_requests: int
  service_tier: str                    # 'standard' | 'premium'
  cache_creation:
    ephemeral_1h_input_tokens: int
    ephemeral_5m_input_tokens: int
  inference_geo: str                   # 推理地理位置
  speed: str                           # 'standard' | 'fast'
  iterations: list                     # 迭代详情
```

---

## 错误类型

```
APIErrorCategory:
  'timeout' |                          # 请求超时
  'rate_limited' |                     # 速率限制
  'overloaded' |                       # 服务器过载
  'auth_failure' |                     # 认证失败
  'model_not_found' |                  # 模型未找到
  'prompt_too_long' |                  # 提示过长
  'max_context_exceeded' |            # 超出上下文限制
  'image_too_large' |                  # 图片过大
  'connection_error' |                 # 网络连接错误
  'ssl_error' |                        # SSL 错误
  'unknown'                            # 未知错误

APIErrorInfo:
  category: APIErrorCategory
  status: int                          # HTTP 状态码
  message: str                         # 用户可见消息
  retryAfter: int                      # (可选) Retry-After 值
  limitInfo:                           # (可选) 速率限制详情
    requestsLimit: int
    requestsRemaining: int
    tokensLimit: int
    tokensRemaining: int
  rawError: any                        # 原始错误对象
```

---

## 重试状态

```
RetryState:
  attempt: int                         # 当前尝试次数
  maxRetries: int                      # 最大重试次数（默认 10）
  consecutive529s: int                 # 连续 529 响应计数
  fallbackTriggered: bool              # 是否触发模型回退
  baseDelayMs: int                     # 基础延迟（500ms）
  currentDelayMs: int                  # 当前延迟（指数增长 + 25% 抖动）
```

---

## 代理消息类型

```
# Anthropic 格式
AnthropicMessage:
  role: 'user' | 'assistant' | 'system'
  content: str | list[ContentBlock]

# OpenAI 聊天完成格式
OpenAIChatMessage:
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: str | list[OpenAIContentPart]
  tool_call_id: str                   # (可选) 工具结果时
  tool_calls: list[OpenAIToolCall]    # (可选) 助手工具调用时

OpenAIFunction:
  type: 'function'
  function:
    name: str
    description: str
    parameters: dict                    # JSON Schema

OpenAIResponsesInputItem:
  type: 'message' | 'function_call' | 'function_call_output'
  # ... 类型特定字段

# 响应
OpenAIChatResponse:
  id: str
  choices:
    - index: int
      message: OpenAIChatMessage
      finish_reason: str              # 'stop' | 'tool_calls' | 'length'
  usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

OpenAIResponsesResponse:
  id: str
  output: list[OutputItem]            # message | function_call
  usage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
```

---

## API 客户端配置

```
APIClientConfig:
  apiKey: str                          # API 密钥
  baseURL: str                         # API 端点 URL
  timeout: int                         # 超时（毫秒）
  headers: dict[str, str]             # 自定义标头
  maxRetries: int                      # 客户端级重试
  provider: str                        # 'anthropic' | 'bedrock' | 'openai_proxy'
```

---

## v1 简化

general-agent v1 仅需：

```
AnthropicRequest（核心字段）
AnthropicResponse（核心字段）
StreamEvent（text_delta + input_json_delta）
Usage
APIErrorCategory + APIErrorInfo
RetryState
代理：OpenAIChatMessage + OpenAIFunction + 双向转换
```

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/services/api/claude.ts, client.ts, src/server/proxy/transform/types.ts
