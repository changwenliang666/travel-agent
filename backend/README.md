# 旅行助手后端

FastAPI 服务。负责登录、多日行程对话、高德和网页搜索、模型熔断、记忆、trace 和 token 统计。

页面在 `frontend/`。日常开发时，MySQL 和 Redis 留在 Compose 里，前后端在本机启动，改代码会自动重载。

## 一起启动

在仓库根目录：

```bash
cp .env.example .env
```

编辑 `.env`，填入 `QWEN_API_KEY`、`DEEPSEEK_API_KEY`、`AMAP_KEY`、`TAVILY_API_KEY`。不要把真实密钥提交到仓库。`DATABASE_URL` 使用 `127.0.0.1` 和 `MYSQL_PUBLISH_PORT`（示例是 3307）。

```bash
docker compose up -d
```

这只启动 MySQL（`127.0.0.1:3307`）和 Redis（`127.0.0.1:6379`）。

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

- 页面：Vite 打印的地址，一般是 http://localhost:5173 。保存 Vue 文件会热更新。
- 接口：http://127.0.0.1:8000 。保存 Python 文件后 uvicorn 会自动重载。
- 健康检查：http://127.0.0.1:8000/api/health
- 首次启动会用 `.env` 里的 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 创建管理员。示例账号是 `admin` / `admin123456`，用前请改掉。

配置从仓库根目录的 `.env` 读取，与在哪个目录执行 uvicorn 无关。

测试：

```bash
uv run pytest
```

## 对话怎么走

每条用户消息进一张三路图：

1. 抽出目的地、天数和日期。
2. 缺目的地，或天数不是 1 到 14：只追问，不查外部资料。
3. 信息够：查天气、网页搜索、地点，再写成按天行程。
4. 已有行程只是提问：最多再查一次。

主模型是 `qwen3.7-plus`。超时或 5xx 会切到 DeepSeek。熔断有关闭、打开、半开三种状态，半开时只有一个请求试探主模型。

## 接口

登录后浏览器带着 Cookie。未登录访问对话接口会返回 401。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| POST | `/api/auth/login` | 登录，body：`username`、`password` |
| POST | `/api/auth/logout` | 退出 |
| GET | `/api/auth/me` | 当前用户 |
| GET | `/api/preferences/current` | 查看当前偏好 |
| PUT | `/api/preferences/save` | 保存偏好 |
| POST | `/api/conversations/create` | 新建对话 |
| GET | `/api/conversations/list` | 对话列表 |
| GET | `/api/conversations/{id}/detail` | 消息和当前行程 |
| POST | `/api/conversations/{id}/messages/send` | 发送消息，SSE 返回进度、正文、行程和 `trace_id` |
| GET | `/api/health` | 健康检查 |
| GET | `/api/admin/traces/{trace_id}` | 查看一轮调用的步骤，仅管理员 |
| GET | `/api/admin/usage/summary` | token 汇总，仅管理员。可用 `user_id`、`start`、`end` |

普通用户调用管理员接口返回 403。
