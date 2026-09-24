# api-routes Specification

## Purpose

规定公开 HTTP 接口按实际场景单独命名，任意两个操作不得共用同一条路径，并固定替换后的路径表。

## Requirements

### Requirement: Each operation has one unique path

系统 MUST 为每个公开 HTTP 操作注册恰好一条路径。路径字符串相同即视为重名，无论 HTTP 方法是否不同。系统 MUST NOT 让两个操作共用同一路径字符串。公开接口 MUST 恰好是下表，不得另增未列出的 `/api` 路径：

- `POST /api/conversations/create`：创建一条空对话
- `GET /api/conversations/list`：列出当前用户的对话
- `GET /api/conversations/{conversation_id}/detail`：读取一条对话的消息和行程
- `POST /api/conversations/{conversation_id}/messages/send`：发送一条消息并以 SSE 返回进度、正文、行程和 `trace_id`
- `GET /api/preferences/current`：读取当前用户的长期偏好
- `PUT /api/preferences/save`：保存当前用户的长期偏好
- `POST /api/auth/login`：登录并写入会话 cookie
- `POST /api/auth/logout`：登出并清除会话 cookie
- `GET /api/auth/me`：读取当前登录用户
- `GET /api/health`：健康检查
- `GET /api/admin/traces/{trace_id}`：管理员读取一条 trace
- `GET /api/admin/usage/summary`：管理员汇总 token 用量，查询参数仍为 `user_id`、`start`、`end`

#### Scenario: Create and list no longer share a path

- **WHEN** 已登录用户分别请求创建对话和列出对话
- **THEN** 创建使用 `POST /api/conversations/create`，列出使用 `GET /api/conversations/list`，两条路径字符串不同

#### Scenario: Read and save preferences no longer share a path

- **WHEN** 已登录用户分别请求读取偏好和保存偏好
- **THEN** 读取使用 `GET /api/preferences/current`，保存使用 `PUT /api/preferences/save`，两条路径字符串不同

#### Scenario: The route table has no duplicate path strings

- **WHEN** 列出全部已注册的 `/api` 路径
- **THEN** 每个路径字符串只出现一次，且集合与本要求中的路径表一致

### Requirement: Retired paths do not perform the old operation

下列旧路径 MUST NOT 再执行原来的操作，并且 MUST 作为不存在的路由拒绝（HTTP 404）：

- `POST /api/conversations` 与 `GET /api/conversations`
- `GET /api/conversations/{conversation_id}`（路径止于对话 id，没有 `/detail`）
- `POST /api/conversations/{conversation_id}/messages`（路径止于 `messages`，没有 `/send`）
- `GET /api/preferences` 与 `PUT /api/preferences`
- `POST /api/login`、`POST /api/logout`、`GET /api/me`
- `GET /api/admin/usage`（路径止于 `usage`，没有 `/summary`）

`GET /api/health` 与 `GET /api/admin/traces/{trace_id}` 保持原路径，不在退役之列。

#### Scenario: Shared conversation path no longer creates or lists

- **WHEN** 已登录客户端请求 `POST /api/conversations` 或 `GET /api/conversations`
- **THEN** 系统返回 404，不创建对话，也不返回对话列表

#### Scenario: Shared preferences path no longer reads or saves

- **WHEN** 已登录客户端请求 `GET /api/preferences` 或 `PUT /api/preferences`
- **THEN** 系统返回 404，不返回偏好，也不写入偏好

#### Scenario: Previous auth and usage paths are gone

- **WHEN** 客户端请求 `POST /api/login`、`GET /api/me` 或 `GET /api/admin/usage`
- **THEN** 系统返回 404

### Requirement: Renamed routes keep the previous payloads and access rules

新路径 MUST 沿用对应旧操作的请求体、响应体、状态码、cookie、SSE 事件和访问规则。未登录访问需要登录的接口时 MUST 仍被拒绝。用户 MUST NOT 通过新的详情路径读取他人对话。非管理员 MUST NOT 通过新的用量路径读取用量汇总。

#### Scenario: Creating a conversation still returns id and title

- **WHEN** 已登录用户请求 `POST /api/conversations/create`
- **THEN** 系统返回新建对话的 `id` 和 `title`，且该对话没有历史消息和行程

#### Scenario: Sending a message still streams the turn

- **WHEN** 已登录用户向自己的对话请求 `POST /api/conversations/{conversation_id}/messages/send`，请求体含 `text`
- **THEN** 系统以 SSE 返回该轮的进度、正文、行程和 `trace_id`

#### Scenario: Another user's detail stays forbidden

- **WHEN** 已登录用户请求 `GET /api/conversations/{conversation_id}/detail`，且该对话不属于该用户
- **THEN** 系统拒绝该请求

#### Scenario: Anonymous and non-admin access stay rejected

- **WHEN** 未登录客户端请求 `GET /api/conversations/list`，或非管理员请求 `GET /api/admin/usage/summary`
- **THEN** 系统拒绝这些请求
