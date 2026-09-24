## 1. 流式转发

- [x] 1.1 在 `llm.py`（搬目录前）把 `stream=True` 的模型请求改为 `httpx` 的 `stream()`，边读行边调用 `on_delta`；非流式调用仍用 `post()`。用现有流式中断测试和一次分块假响应验证：`on_delta` 在响应体未读完时就会被调用，而不是等 `post()` 返回之后。
- [x] 1.2 调整 `agent` 行程节点的提示：先输出面向用户的 Markdown，再输出分隔行 `<<<PLAN>>>` 和行程 JSON。分隔行之前的 token 转发为 `delta`；之后只在服务端解析。正文以 `{` 开头时不转发 `delta`，结束时用解析出的 Markdown 填 `done`。用假模型输出验证气泡文本不含 JSON，且 `plan` 仍能解析。
- [x] 1.3 给消息接口的 SSE 响应加上 `X-Accel-Buffering: no`，并保留 Nginx 的 `proxy_buffering off`。用本地请求确认响应头里有该项。

## 2. 对话页

- [x] 2.1 把进度说明写进当前助手消息的 `status`，在没有正文时渲染在气泡内；第一条可见 `delta` 清空 `status` 并追加正文。去掉气泡外的 `.progress`。在页面上发送一条会查询的消息，确认「正在搜索」一类文字出现在助手气泡里，而不是气泡下方。
- [x] 2.2 按 SSE 到达顺序追加助手正文，并在追加后把消息列表滚到底部。`done` 仍用最终回复覆盖，行程卡片在 `plan` 到达后显示。用分块 SSE 验证第一段文本先出现，后续段落再追加，而不是一次画完全文。
- [x] 2.3 输入框：非空时 Enter 发送并清空；Shift+Enter 换行不发送；纯空白 Enter 不发送；`isComposing` 为真时 Enter 不发送。在页面上分别按这四种按键确认行为。
- [x] 2.4 把 `.shell` 固定为视口高度，顶栏不参与滚动；对话页只让 `.messages` 滚动，输入区留在底部。偏好页和记录页在顶栏下方滚动内容。把对话滚过一屏，确认顶栏和输入区位置不变。

## 3. 后端目录

- [x] 3.1 按 `design.md` 的树把平铺模块拆到 `api/`、`config/`、`db/`、`services/`、`llm/`、`agent/`，`tools/` 保持不动。`main.py` 只重新导出 `app`，`uvicorn backend.main:app` 不变。确认旧的平铺文件已不在 `backend/src/backend/` 根目录（`main.py` 和 `tools/` 除外）。
- [x] 3.2 更新 `backend/tests/test_core.py` 的导入到新路径。运行后端测试，确认全部通过。

## 4. 本机 MySQL

- [x] 4.1 在 `docker-compose.yml` 把 MySQL 发布为 `127.0.0.1:${MYSQL_PUBLISH_PORT:-3306}:3306`，并在 `.env.example` 写下 `MYSQL_PUBLISH_PORT=3306`。不改后端容器里指向 `mysql:3306` 的 `DATABASE_URL`。检查 compose 配置，确认发布地址是 `127.0.0.1`。
- [x] 4.2 重启 Compose 后，用本机客户端连接 `127.0.0.1` 和发布端口，账号取自 `.env`。确认能列出业务库中的表。
