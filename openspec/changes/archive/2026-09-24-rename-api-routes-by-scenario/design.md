## Context

见 `proposal.md` 的 Why。当前路由都在 `backend/src/backend/api/routes/`，由 FastAPI `APIRouter` 直接声明完整路径，没有路径前缀或版本层。前端只通过 `frontend/src/api.ts` 调用这些路径。`backend/README.md` 有一张与代码一致的接口表。业务规格不绑定 URL。

现有重名（路径字符串相同、方法不同）：

- `POST` 与 `GET` `/api/conversations`
- `GET` 与 `PUT` `/api/preferences`

另外，`GET /api/conversations/{conversation_id}` 与 `POST /api/conversations/{conversation_id}/messages` 的路径本身没有写出「详情」和「发送」。处理函数 `api_send`、`api_trace`、`api_usage`、`api_me`、`api_get_prefs`、`api_put_prefs` 用方法或缩写命名，和场景对不上。

## Goals / Non-Goals

**Goals:**

- 用一张固定路径表替换全部公开 `/api` 路由，保证路径字符串全局唯一。
- 处理函数名与场景一致，且在路由模块内互不重复。
- 同一变更里改完前端客户端、后端测试和 README，避免新旧路径并存。

**Non-Goals:**

- 不改请求体、响应体、状态码、cookie、SSE 事件、鉴权和业务规则。
- 不为旧路径保留转发或别名。
- 不引入路由前缀常量层或 OpenAPI 定制之外的新框架。

## Decisions

### 1. 路径末段写场景，而不是只靠 HTTP 方法区分

重名的资源路径在末段加上场景词：`create`、`list`、`detail`、`send`、`current`、`save`、`summary`。登录相关收进 `/api/auth/`，因为 `login`、`logout`、`me` 原先散在 `/api` 根上，和对话、偏好混在一起。

已经唯一且场景清楚的路径保持不动：`GET /api/health`、`GET /api/admin/traces/{trace_id}`。用量从 `/api/admin/usage` 改为 `/api/admin/usage/summary`，与「汇总 token」这个场景一致，也避免以后再挂一个同路径的明细接口。

备选：继续用同一路径加不同方法（REST）。这正是当前看不出场景的原因，不采用。备选：只改 Python 函数名、路径不动。调用方和 README 仍然看到重名路径，不采用。

### 2. 处理函数去掉 `api_` 前缀，改成场景名

`api_` 前缀没有区分场景。函数名与路径场景对齐，并保证互不相同：

| 方法 | 路径 | 函数 |
| --- | --- | --- |
| POST | `/api/conversations/create` | `create_conversation` |
| GET | `/api/conversations/list` | `list_conversations` |
| GET | `/api/conversations/{conversation_id}/detail` | `get_conversation_detail` |
| POST | `/api/conversations/{conversation_id}/messages/send` | `send_conversation_message` |
| GET | `/api/preferences/current` | `get_current_preferences` |
| PUT | `/api/preferences/save` | `save_current_preferences` |
| POST | `/api/auth/login` | `login_user` |
| POST | `/api/auth/logout` | `logout_user` |
| GET | `/api/auth/me` | `get_current_user` |
| GET | `/api/health` | `check_health` |
| GET | `/api/admin/traces/{trace_id}` | `get_admin_trace` |
| GET | `/api/admin/usage/summary` | `get_admin_usage_summary` |

函数体搬到新装饰器下，不改内部逻辑。`login_user` 仍调用 `backend.services.auth.login`，不要把路由函数和同名服务函数缠在一起：路由模块里给服务函数使用现有导入名；若与路由函数重名，则导入时起别名（例如 `login as login_account`）。`logout` 同样处理。

备选：保留 `api_` 前缀只改后缀。前缀仍然让所有接口看起来是同一类名字，不采用。

### 3. 前端只改 `api.ts` 里的路径字符串

`Chat.vue`、`Preferences.vue`、`Login.vue`、`Admin.vue`、`router.ts` 使用 `api.conversations`、`api.createConversation` 等方法名。这些客户端方法名已经按场景分开，保持不动，只替换它们内部的 URL。`sendMessage` 改为请求 `.../messages/send`。

### 4. 用路由表断言防止再出现重名

在 `backend/tests/test_core.py` 增加一项检查：收集应用已注册路由中以 `/api` 开头的路径，断言路径字符串唯一，且与规格中的 12 条一致。现有用例里的旧 URL 全部换成新 URL，并增加对退役路径返回 404 的断言（至少覆盖 `POST /api/conversations`、`GET /api/preferences`、`GET /api/me`、`GET /api/admin/usage`）。

## Risks / Trade-offs

- [仓库外的调用方仍请求旧路径] → 本仓库内的调用方只有前端 `api.ts`、`test_core.py` 和 `backend/README.md`。三者与后端同时修改。不保留别名，旧路径 404。
- [`/api/auth/login` 与服务层 `login` 重名导致调用错误函数] → 路由函数用 `login_user`，服务函数导入时加别名。
- [FastAPI 把 `list`、`create` 当成 `{conversation_id}`] → `create`、`list` 路由声明在带路径参数的路由之前；测试请求这两条字面路径，确认不会进详情处理函数。

## Migration Plan

1. 后端改路由装饰器和函数名。
2. 前端 `api.ts`、测试和 README 改为新路径。
3. 跑后端测试，确认新路径可用、旧路径 404、路径表无重复。
4. 回滚：还原同一次改动。没有数据迁移。

## Open Questions

无。路径表已在规格中固定。
