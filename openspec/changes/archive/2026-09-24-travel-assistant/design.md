## Context

仓库目前只有 OpenSpec 脚手架，没有前后端代码。见 `proposal.md` 的 Why。

约束：个人使用，但要有用户和角色；代码用普通函数和直白的分支，避免多层抽象；密钥只来自环境变量。

## Goals / Non-Goals

**Goals:**

- 用一张能直接读懂的三路图完成澄清、生成行程、回答问题。
- 模型超时熔断、trace、token、记忆都落在普通函数上，和这张图分开。
- 根目录 `docker compose up` 能启动前端、后端、MySQL、Redis。

**Non-Goals:**

- 酒店、机票、火车的查询和预订。
- LangChain Agent、LCEL 管道、框架自带的对话检查点。
- Tavily 抓取整页正文。
- 把熔断器做成通用库。

## Decisions

### 1. 三路分支用薄 LangGraph，节点是普通函数

每条用户消息跑一次图。状态是一个字典：`messages`、`slots`、`action`、`plan`、`reply`。

```text
extract
   |
   +-- clarify   信息不够，返回追问，结束
   +-- build     天气 -> 搜索 -> POI -> 模型写成行程
   +-- answer    至多一次工具，再回答
```

`extract` 做一次模型调用，要求返回普通 JSON：`action`、`destination`、`days`、`date_start`、`question`、`revise_note`。解析失败时把 `action` 定为 `clarify`，并请用户换种说法。

`clarify` 不再调用模型或外部工具，直接采用 `question`。

另一种做法是在 `handle_message` 里写 `if`。分支本身更短，但图的形状要靠读代码才能看到。这里保留图，是为了三路分支一眼能看清；图的 API 只用 `StateGraph`、节点和条件边。

### 2. 对话状态存在 MySQL，不使用框架检查点

槽位、消息、行程 JSON 写在当前对话上。用户下一条消息会重新跑图，并读出已有槽位和行程。

另一种做法是用 LangGraph 的检查点把图暂停在追问节点。那会和 MySQL 里的对话各存一份，排错时要对两套状态。

### 3. 生成与修改行程的步骤固定

`build` 按顺序调用普通函数，没有隐藏的工具循环：

1. 高德天气
2. Tavily 搜索（最多 5 条标题、链接、短摘要）
3. 高德 POI
4. 一次模型调用，写出 Markdown 和行程 JSON

已有行程且目的地、出发日期都没变时，跳过前三步，把上一份行程和 `revise_note` 交给模型整份重写。

`answer` 最多调用一次工具（搜索、POI 或路径）。不需要外部信息时零次调用。

天数必须是 1 到 14 的整数。超过 14 天走 `clarify`，请用户缩短。日期可以缺省。

### 4. 模型网关和三态熔断独立于图

通义和 DeepSeek 都走 OpenAI 兼容的对话接口。`call_model` 先问熔断器该用哪个模型，再发请求。默认主模型名是 `qwen3.7-plus`，备用模型名来自环境变量。

熔断状态放在 Redis 的一个哈希里：`state`、`fail_count`、`window_started_at`、`opened_at`。

```text
失败达到阈值                         冷却结束
closed -------------------------> open -----------------> half_open
   ^                               |                         |
   | 试探成功                      |                         | 仅 1 个试探打主模型
   +-------------------------------+---- 试探失败 ----------+
```

默认：60 秒内 5 次失败则打开，打开后冷却 30 秒。这些数放在环境变量里。

计入失败：建连超时、首个 token 前超时、连接错误、5xx。内容审核类 4xx 不计入。

还没有任何 token 输出时，同一次调用可以改走备用模型，并记在同一条 trace 里。已经向外输出过 token 时，不再中途换模型，这一轮以明确错误结束。

半开时用 Redis 锁占用试探名额。拿到锁的请求打主模型，其余请求走备用模型。

另一种做法是用框架的 fallback 列表。那种切换没有半开，也不能保证同时只有一个试探请求。

### 5. 记忆

- 短期：当前对话最近若干轮。热数据在 Redis，全文在 MySQL。交给模型的上下文是：长期偏好 + 滚动摘要 + 最近 6 轮原文 + 当前消息。
- 长期：每个用户一份 JSON 偏好（常住城市、节奏、预算、饮食、是否早起）。用户可以在偏好页查看和修改。回复发送之后再异步抽取，不挡住首字。
- 压缩：估算 token 超过 6000 时，把最近 6 轮之前的内容收成滚动摘要。工具观察算进这个预算。压缩本身的模型调用计入 token。

### 6. Trace 和权限

每个用户轮次一个 `trace_id`，放进响应头。span 覆盖：读记忆、压缩、每次模型调用（模型名、耗时、熔断状态、token）、每次工具调用（名称、耗时、成败）。

Token 以供应商返回的 usage 为准。抽取偏好和压缩如果另开模型调用，也记一笔。

登录使用放在 MySQL 里的不透明会话令牌，浏览器以 HttpOnly Cookie 携带。用户表有 `user` 和 `admin` 两种角色。管理接口在服务端检查角色。首次启动且用户表为空时，用环境变量里的管理员用户名和密码创建一名管理员。

### 7. 行程 JSON 与界面

模型同时返回 Markdown 说明和下面这种结构。前端用 Markdown 显示说明和来源，用卡片显示行程。

```json
{
  "destination": "杭州",
  "days_count": 2,
  "date_start": "2026-10-01",
  "days": [
    {
      "day": 1,
      "title": "西湖",
      "weather": "小雨 18°C",
      "items": [{ "time": "上午", "name": "断桥", "note": "沿白堤走" }]
    }
  ],
  "sources": [{ "title": "来源标题", "url": "https://example.com" }]
}
```

界面是对话产品：左侧对话列表和「新对话」，中间消息流，顶部是偏好入口。管理员才看得到 trace 和用量入口。Element Plus 只做组件底子，换一套偏 C 端的颜色和字号。

同一条 SSE 先推工具进度（正在查天气、正在搜索、正在找地点、正在写行程），再推回复文本，最后给出行程 JSON 和 `trace_id`。

### 8. 目录和写法

```text
frontend/src/views/Login.vue
frontend/src/views/Chat.vue
frontend/src/views/Preferences.vue
frontend/src/views/Admin.vue
frontend/src/components/Message.vue
frontend/src/components/ItineraryCard.vue
frontend/src/api.ts
backend/app/main.py
backend/app/config.py
backend/app/db.py
backend/app/auth.py
backend/app/graph.py
backend/app/nodes.py
backend/app/llm.py
backend/app/breaker.py
backend/app/memory.py
backend/app/trace.py
backend/app/tools/amap.py
backend/app/tools/search.py
docker-compose.yml
.env.example
```

Python 使用函数、`if`、`for` 和字段直白的 class。FastAPI 请求体用 Pydantic。类型标注写到能看懂参数和返回值。错误用 `try/except` 写入 trace，再返回明确原因。Vue 使用 `<script setup>`，请求集中在 `api.ts`。

### 9. 部署

Compose 服务：`frontend`（构建后由 nginx 提供）、`backend`、`mysql`、`redis`。后端用 uv 安装依赖。`.env.example` 只列变量名：`QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`AMAP_KEY`、`TAVILY_API_KEY`、数据库和 Redis 连接、`ADMIN_USERNAME`、`ADMIN_PASSWORD`。真实值留在本地 `.env`，并列入 `.gitignore`。

高德和 Tavily 的单次超时默认 8 秒。模型建连超时默认 10 秒，首 token 超时默认 30 秒。

## Risks / Trade-offs

- [主模型名 `qwen3.7-plus` 与供应商目录不一致] → 模型名放在环境变量中，实现时对照供应商文档确认默认真名。
- [对话里出现过的密钥已被泄露] → 实现前轮换通义、DeepSeek、高德、Tavily 的密钥；仓库中不出现真实值。
- [Tavily 开发密钥额度有限，搜索结果撑爆上下文] → 最多 5 条短摘要，并计入压缩预算。
- [LangGraph 版本变动] → 锁版本，调用面只保留建图和条件边。
- [整份重写行程比按天增量修改多花 token] → 接受这份开销，避免「哪一天受影响」的依赖分析。
- [半开试探和普通请求并发] → Redis 锁保证只有一个试探打到主模型。

## Migration Plan

这是新项目。配置 `.env` 后执行 `docker compose up --build`。回退时 `docker compose down`。需要清空数据时再删掉 MySQL 和 Redis 的数据卷。

## Open Questions

无。天数上限、熔断默认阈值、会话存在 MySQL，都已在上面定死，实现时只按这些默认值做，不需要再改规格。
