# 旅行助手前端

Vue 3 + TypeScript + Vite + Element Plus。用来登录、新建对话、看 Markdown 行程卡片、改偏好。管理员还能看 trace 和 token 用量。

接口在 `backend/`。`npm run dev` 启动 Vite，保存文件会热更新，并把 `/api` 代理到 `http://127.0.0.1:8000`。

## 一起启动

在仓库根目录配置 `.env` 后，按 `backend/README.md` 启动 MySQL、Redis 和带 `--reload` 的接口。然后：

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 Vite 打印的地址，一般是 http://localhost:5173 。

管理员来自 `.env` 的 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`。示例是 `admin` / `admin123456`。

生产构建：

```bash
npm run build
```

## 页面

- `/login`：登录。
- `/`：对话。左侧是对话列表和「新对话」，中间是消息。回复用 Markdown，多日行程另外显示按天卡片。
- `/preferences`：常住城市、节奏、预算、饮食、是否早起。保存后会带到之后的行程里。
- `/admin`：按 `trace_id` 看调用步骤，按时间和用户看 token 汇总。只有管理员看得到入口，直接打开也会被送回对话页。

目的地或天数没说清时，助手只追问，不会出行程。说清之后会先显示「正在查天气」「正在搜索」这类进度，再给出行程。
