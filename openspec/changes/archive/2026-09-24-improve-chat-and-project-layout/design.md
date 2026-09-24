## Context

见 `proposal.md` 的 Why。现状约束：

- 进度事件已经通过 SSE 的 `progress` 发出，但 `Chat.vue` 把它写在 `.progress`，助手气泡在正文到达前是空的。截图里的「正在搜索」就在气泡外面。
- `nodes.py` 对面向用户的模型调用传了 `stream=True` 和 `on_delta`。`llm.py` 的 `_once` 使用 `httpx.Client.post()`，会先读完整个响应，再在 `_read_stream` 里拆行。因此 `delta` 在模型结束后一次性入队，前端一次渲染完整段。
- 生成行程时，模型输出的是含 `markdown` 和 `plan` 的 JSON。`done` 事件用解析后的 Markdown 覆盖气泡。若把原始 token 直接画进气泡，用户会看到 JSON。
- 前端经 Nginx（`proxy_buffering off`）或 Vite 代理访问 `/api`。输入框是普通 `textarea`，没有键盘处理。`.shell` 随内容增高，顶栏在文档流里，整页一起滚。
- `backend/src/backend/` 除 `tools/` 外是平铺模块。`Dockerfile` 使用 `uvicorn backend.main:app`。测试从这些平铺模块导入。
- `docker-compose.yml` 的 `mysql` 没有 `ports`。`.env.example` 里本机 `DATABASE_URL` 已经指向 `127.0.0.1:3306`。Compose 内的后端仍用服务名 `mysql:3306`。

## Goals / Non-Goals

**Goals:**

- 进度出现在当前助手气泡内；面向用户的文本按到达顺序追加。
- 模型 HTTP 响应边收边转发为 SSE `delta`。
- Enter 发送，Shift+Enter 换行；中文输入法选词时的 Enter 不发送。
- 顶栏固定；对话页只滚动消息列表。
- 后端按包拆分，现有 HTTP 行为不变。
- MySQL 只发布到本机回环地址。

**Non-Goals:**

- 不改行程、工具、熔断、记忆、管理员接口的业务规则。
- 不改 SSE 事件名（`progress`、`delta`、`plan`、`done`、`error`）。
- 不引入新的数据库或迁移；不给 MySQL 增加数据卷。
- 不为每个旧模块保留兼容导入。

## Decisions

### 1. 进度挂在当前助手消息上

发送时照旧插入一条空的助手消息，并给它一个 `status` 字段。`progress` 更新这条消息的 `status`。第一条可见 `delta` 到达时清空 `status` 并追加正文。模板在没有正文时渲染 `status`，有正文时渲染 Markdown。去掉消息列表外的 `.progress`。

备选：在气泡下方单独画状态行。不采用，因为空气泡仍然在。

### 2. 用 httpx 流式读取，再原样转发 delta

`stream=True` 时改用 `client.stream("POST", ...)`，在响应体到达过程中调用 `on_delta`。非流式调用保持 `post()`。响应头增加 `X-Accel-Buffering: no`。Nginx 现有的 `proxy_buffering off` 保留。

备选：在后端攒完整段落后再按字符切片推给前端。不采用，用户仍要等模型结束。

流式读取的 `read` 超时继续用 `model_first_token_timeout`（30 秒）。这是 token 间隔上限，不是整段生成时限。

### 3. 行程回复只向前端推 Markdown

`answer_node` 的输出已经是 Markdown，`on_delta` 直接转发。

`build_node` 改为要求模型先写面向用户的 Markdown，然后写分隔行 `<<<PLAN>>>`，再写行程 JSON。分隔行之前的 token 经 `on_delta` 转发；分隔行之后只在服务端解析为 `plan`。若正文以 `{` 开头，说明模型仍输出了整段 JSON：这一轮不转发 `delta`，解析完成后只通过 `done` 写入 Markdown，避免气泡里出现 JSON。

备选：边收边解析 JSON 字符串里的 `markdown` 字段。转义处理容易出错，不采用。

### 4. 键盘与滚动

`textarea` 监听 `keydown`。`Enter` 且未按 Shift、且 `isComposing` 为假时阻止默认换行并调用现有 `send()`。`Shift+Enter` 保持浏览器换行。

`.shell` 改为 `height: 100vh` 的纵向 flex，`overflow: hidden`。顶栏 `flex: none`。对话区占满剩余高度，`.messages` 单独 `overflow: auto`。偏好页和记录页的内容区同样在顶栏下方滚动。消息追加后把消息列表滚到底部。

### 5. 后端包划分

```
backend/src/backend/
  main.py              # 只重新导出 api.app:app，uvicorn 入口不变
  api/app.py           # FastAPI、中间件、startup、挂载路由
  api/schemas.py
  api/routes/          # auth、conversations、preferences、admin、health
  config/settings.py   # 现 config.py
  db/models.py
  db/session.py        # engine、SessionLocal、get_db、init_db
  services/auth.py
  services/turn.py
  services/memory.py
  services/trace.py
  llm/gateway.py       # 现 llm.py
  llm/breaker.py
  agent/graph.py
  agent/nodes.py
  tools/               # 保持不动
```

路由只做 HTTP 和 SSE；一轮对话仍由 `services/turn.py` 调用图。测试改为从新路径导入。除 `main.py` 外，不为旧的平铺模块留转发文件。

备选：把图、模型和熔断器都放进 `services/`。根目录会少几个包，但 `services/` 会重新变成杂项目录，不采用。

### 6. MySQL 只绑定 127.0.0.1

```yaml
ports:
  - "127.0.0.1:${MYSQL_PUBLISH_PORT:-3306}:3306"
```

`.env.example` 增加 `MYSQL_PUBLISH_PORT=3306`。不改 Compose 里后端的 `DATABASE_URL`。Navicat 使用 `127.0.0.1`、发布端口，以及 `.env` 中的库名、用户和密码。

## Risks / Trade-offs

- [模型不遵守 `<<<PLAN>>>`，或把 JSON 写在分隔行之前] → 以 `{` 开头时抑制 `delta`，结束时用解析结果覆盖气泡。
- [中文输入法把 Enter 当成选词] → 忽略 `isComposing` 的 Enter。
- [搬目录漏改导入，容器起不来] → 保留 `backend.main:app`；搬完跑现有测试。
- [本机 3306 已被占用] → 设置 `MYSQL_PUBLISH_PORT`，不必改应用容器的连接串。
- [流式 `read` 超时沿用 30 秒] → 两个 token 间隔超过 30 秒会中断这一轮。这与现在的首 token 超时同一量级，本次不另加整段时限。

## Migration Plan

1. 先改流式转发和对话页，再搬后端目录，最后加端口映射。三块可以独立回滚。
2. 目录搬迁不改表结构。重启 Compose 后再测对话。
3. 端口映射不迁移数据。若 3306 冲突，只改 `MYSQL_PUBLISH_PORT` 并重启 `mysql`。
4. 回滚：恢复平铺模块与 `docker-compose.yml` 的端口段；前端恢复气泡外进度。无数据回填。

## Open Questions

无。发布端口默认 3306、包边界和行程分隔行都已在上面定下。
