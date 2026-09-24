# 旅行助手

一个前后端在同一仓库里的多日行程助手。用户登录后用对话收集目的地和天数，助手查询天气、网页和地点，再给出按天行程。管理员可以查看单轮调用步骤和 token 用量。

- `backend/`：FastAPI 服务。登录、对话、高德与网页搜索、模型熔断、记忆、trace 和 token 统计。
- `frontend/`：Vue 3 + TypeScript + Vite + Element Plus。登录、对话、Markdown 行程卡片、偏好设置，以及管理员页。

更细的接口和页面说明见 [backend/README.md](backend/README.md) 和 [frontend/README.md](frontend/README.md)。

## 启动

在仓库根目录：

```bash
cp .env.example .env
```

编辑 `.env`，填入 `QWEN_API_KEY`、`DEEPSEEK_API_KEY`、`AMAP_KEY`、`TAVILY_API_KEY`。不要把真实密钥提交到仓库。`DATABASE_URL` 使用 `127.0.0.1` 和 `MYSQL_PUBLISH_PORT`（示例是 3307）。

```bash
docker compose up -d
```

这只启动 MySQL（`127.0.0.1:3307`）和 Redis（`127.0.0.1:6379`）。前后端在本机启动，改代码会自动重载。

另开两个终端：

```bash
cd backend
uv sync
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

- 页面：Vite 打印的地址，一般是 http://localhost:5173 。`/api` 会代理到后端。
- 接口：http://127.0.0.1:8000 。健康检查：http://127.0.0.1:8000/api/health
- 首次启动会用 `.env` 里的 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 创建管理员。示例账号是 `admin` / `admin123456`，用前请改掉。

配置从仓库根目录的 `.env` 读取，与在哪个目录执行 uvicorn 无关。

后端测试：

```bash
cd backend
uv run pytest
```

前端生产构建：

```bash
cd frontend
npm run build
```

## 怎么用

- `/login`：登录。未登录访问对话接口会返回 401。
- `/`：对话。左侧是对话列表，中间是消息。回复用 Markdown，多日行程另外显示按天卡片。
- `/preferences`：常住城市、节奏、预算、饮食、是否早起。保存后会带到之后的行程里。
- `/admin`：按 `trace_id` 看调用步骤，按时间和用户看 token 汇总。只有管理员看得到入口。

每条用户消息会先抽出目的地、天数和日期。缺目的地，或天数不是 1 到 14 时，只追问，不查外部资料。信息够了才查天气、网页和地点，再写成按天行程。

主模型是 `qwen3.7-plus`。超时或 5xx 会切到 DeepSeek。
