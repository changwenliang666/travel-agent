## Why

对话页在查询时把进度写在气泡外面，助手气泡是空的；回复要等模型整段返回后才一次画出来。输入只能点发送，顶栏会跟着页面一起滚走。后端除 `tools/` 外所有模块堆在同一目录，本机也连不上 Compose 里的 MySQL，无法用 Navicat 看数据。

## What Changes

- 发送消息后，当前轮的进度说明（如「正在搜索」）显示在该轮助手气泡内，直到可见正文开始出现。
- 助手回复按已生成的可见文本逐步出现在气泡里，而不是等整段结束后一次渲染。行程卡片仍在正文就绪后出现。模型用来生成行程的结构化 JSON 不直接铺进气泡。
- 输入框按 Enter 发送，Shift+Enter 换行。空白内容不发送。
- 顶栏固定在视口顶部。对话页里只有消息列表滚动，输入区留在底部。
- 后端按职责拆到 `api`、`services`、`config` 等包。HTTP 行为、鉴权和现有业务规则保持不变。
- 为 Compose 中的 MySQL 发布本机端口，使 Navicat 能从本机连上并查看库表。

## Capabilities

### New Capabilities

- `chat-ui`: 进度在助手气泡内、回复增量渲染、Enter / Shift+Enter、顶栏固定且消息列表独立滚动
- `local-mysql`: 本机可通过映射端口用 Navicat 连接 Compose 中的 MySQL 并查看数据

### Modified Capabilities

- 无。`trip-planning` 仍要求客户端先收到进度说明再收到回复正文；本次只规定这些事件在界面上怎么呈现。熔断、工具、记忆和管理员接口的要求不变。

## Impact

- 前端：`frontend/src/views/Chat.vue`、`frontend/src/style.css`，以及共用 `.topbar` 的偏好页和管理页。`frontend/src/api.ts` 的 SSE 读取方式保持，用来消费真正逐段到达的事件。
- 后端：`backend/src/backend/llm.py` 目前用普通 `httpx` POST 读完整包后再拆流，需要改成边收边转发。`backend/src/backend/` 下除 `tools/` 外的模块按包拆分，并更新 `backend/Dockerfile` 的 uvicorn 入口和 `backend/tests/test_core.py` 的导入。
- 运行：`docker-compose.yml` 为 `mysql` 增加仅绑定本机的端口映射。连接账号仍来自 `.env`，不把新的密钥写进仓库。
