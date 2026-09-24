## Why

个人旅行助手需要能把一次对话收成可修改的多日行程，并在目的地或天数不足时先追问。当前仓库只有 OpenSpec 脚手架，没有前后端实现。

## What Changes

- 在仓库根目录新增 `frontend/`（Vue 3 + TypeScript + Vite + Element Plus）和 `backend/`（Python + FastAPI + uv），并用 Docker Compose 一键启动前端、后端、MySQL、Redis。
- 第一版主路径是多日行程：信息不够时只追问；信息够时按天气、网页搜索、地点生成按天行程；已有行程可整份修改，或针对行程提问。
- 用一张三节点的 LangGraph 表达分支（澄清 / 生成行程 / 回答问题）。节点是普通函数。模型调用、熔断、trace、数据库不交给框架。
- 主模型为 `qwen3.7-plus`，超时或 5xx 时经三态熔断器切到 DeepSeek。半开状态只允许一个试探请求打主模型。
- 记录每轮 `trace_id` 和 token 用量。只有管理员能查看 trace 和用量。
- 短期记忆、长期偏好和上下文压缩。用户可查看并修改自己的偏好。
- 工具为高德（天气、地理编码、POI、路径）和 Tavily 网页搜索（最多 5 条摘要）。工具失败不阻断行程生成。
- 密钥只从本地环境变量读取，不写入仓库。

## Capabilities

### New Capabilities

- `trip-planning`: 新建对话、澄清追问、生成和修改多日行程、针对行程提问、Markdown 回复和行程卡片
- `travel-tools`: 高德天气、地理编码、POI、路径，以及 Tavily 搜索；外部工具失败时的降级
- `model-gateway`: 主备模型、超时与三态熔断、半开单试探
- `memory`: 短期对话记忆、长期偏好、上下文压缩
- `admin-observability`: 用户与角色、trace 全链路、token 统计，以及仅管理员可查看

### Modified Capabilities

- 无。仓库里还没有现有能力说明。

## Impact

- 新代码位于 `frontend/` 与 `backend/`，根目录增加 `docker-compose.yml` 和 `.env.example`。
- 新增依赖：LangGraph（仅作三路分支）、MySQL、Redis、高德 Web 服务、Tavily、通义与 DeepSeek 的 OpenAI 兼容接口。
- 不引入 LangChain Agent，也不使用框架的检查点作为对话存储。
- 对外接口为对话流式或一次性回复、偏好读写，以及管理员的 trace 和用量查询。普通用户调用管理接口会被拒绝。
