## Why

多个 HTTP 接口共用同一条路径，只靠方法区分，从路径看不出是在创建、列出、读取还是保存。对话的创建和列表都叫 `/api/conversations`，偏好的读取和保存都叫 `/api/preferences`。发送消息的处理函数叫 `api_send`，也看不出场景。需要按实际场景给每个接口单独命名，并检查全部接口，禁止路径重名。

## What Changes

- **BREAKING**：每个操作使用一条只属于自己的路径。路径字符串相同即视为重名，即使 HTTP 方法不同也不允许。旧路径删除，不保留别名。
- 请求体、响应体、状态码、鉴权、流式事件和业务规则保持不变。只改路径和处理函数名。
- 对话：创建、列出、读取详情、发送消息分成四条路径。
- 偏好：读取当前偏好和保存偏好分成两条路径。
- 登录、登出、当前用户归到 `/api/auth/` 下，名称对应登录、登出、读取当前用户。
- 管理员 trace 与用量、健康检查的路径已经唯一；用量路径补上「汇总」场景，处理函数一律改成场景名，不再使用含糊的 `api_send`、`api_trace`、`api_usage`、`api_me`。
- 前端 `api` 客户端和后端测试改调新路径。

## Capabilities

### New Capabilities

- `api-routes`: 公开 HTTP 接口按场景唯一命名；任意两条操作不得共用同一路径字符串

### Modified Capabilities

- 无。`trip-planning`、`memory`、`admin-observability` 仍只约束登录、对话归属、偏好和 trace 行为，不绑定具体 URL。

## Impact

- 后端路由：`backend/src/backend/api/routes/conversations.py`、`preferences.py`、`auth.py`、`admin.py`、`health.py`。
- 前端：`frontend/src/api.ts`（`Chat.vue`、`Preferences.vue`、`Login.vue`、`Admin.vue`、`router.ts` 经该客户端访问，调用点名称可保持）。
- 测试：`backend/tests/test_core.py` 中写死的旧路径。
- 文档：`backend/README.md` 的接口表和健康检查地址。
- 无新依赖。现有规格里的业务要求不改。
