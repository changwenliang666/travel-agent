## 1. 后端路由

- [x] 1.1 按 `design.md` 的路径表改 `conversations.py`：创建、列出、详情、发送消息四条路径，函数改为 `create_conversation`、`list_conversations`、`get_conversation_detail`、`send_conversation_message`。`create` 与 `list` 声明在带 `{conversation_id}` 的路由之前。函数体保持原逻辑。确认文件中不再出现旧路径 `/api/conversations`、`/api/conversations/{conversation_id}`、`/messages`（不含 `/send`）以及 `api_create_conversation`、`api_list_conversations`、`api_get_conversation`、`api_send`。
- [x] 1.2 改 `preferences.py`：`GET /api/preferences/current` 对应 `get_current_preferences`，`PUT /api/preferences/save` 对应 `save_current_preferences`。确认不再注册 `/api/preferences` 这一条不带场景末段的路径。
- [x] 1.3 改 `auth.py`：`POST /api/auth/login`（`login_user`）、`POST /api/auth/logout`（`logout_user`）、`GET /api/auth/me`（`get_current_user`）。服务层 `login`、`logout` 导入时加别名，避免和路由函数重名。确认不再注册 `/api/login`、`/api/logout`、`/api/me`。
- [x] 1.4 改 `admin.py` 与 `health.py`：用量改为 `GET /api/admin/usage/summary`（`get_admin_usage_summary`），trace 路径保持 `GET /api/admin/traces/{trace_id}` 但函数改为 `get_admin_trace`，健康检查路径保持 `GET /api/health` 但函数改为 `check_health`。确认不再注册 `/api/admin/usage` 这一条不带 `/summary` 的路径。

## 2. 调用方与文档

- [x] 2.1 只改 `frontend/src/api.ts` 中的 URL：列表、创建、详情、发送、偏好读取与保存、登录、登出、当前用户、用量汇总。客户端方法名（`conversations`、`createConversation`、`sendMessage` 等）保持不变。确认 `frontend/src` 下不再请求退役路径。
- [x] 2.2 更新 `backend/README.md` 的接口表，使每一行的方法与路径与规格中的 12 条一致。健康检查地址仍为 `/api/health`。确认文档里不再出现退役路径。

## 3. 测试

- [x] 3.1 把 `backend/tests/test_core.py` 里现有请求改为新路径：创建、发送消息、读取他人对话、登录、登出、当前用户、未登录拒绝、非管理员用量。断言仍检查原有状态码和响应字段。
- [x] 3.2 在同一测试文件增加路由表检查：已注册且以 `/api` 开头的路径字符串互不重复，且与规格中的 12 条一致。再断言退役路径返回 404，至少包括 `POST /api/conversations`、`GET /api/preferences`、`GET /api/me`、`GET /api/admin/usage`。在 `backend/` 下运行 `uv run pytest`，确认全部通过。
