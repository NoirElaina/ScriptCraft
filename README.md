# ScriptCraft

ScriptCraft 是一个小说改编工作台。它先把长篇正文按章节整理出来，再逐步抽取角色、地点和剧情事件，最后生成可以继续编辑的 YAML 剧本。

## 现在能做什么

- 粘贴 3 章以上小说正文，识别章节标题和正文内容
- 在工作台里查看章节列表和单章内容
- 提供剧本 YAML Schema 文档，方便后续生成、校验和导出

## 技术栈

- 前端：Vue 3 + Vite + TypeScript + shadcn-vue + Tailwind CSS v4
- 后端：Python + uv + FastAPI

## 目录结构

```text
ScriptCraft/
  backend/    后端项目
  docs/       项目文档
  frontend/   前端项目
```

## 本地运行

后端：

```powershell
cd backend
uv sync
uv run python main.py
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`。前端开发服务会把 `/api` 转发到 `http://127.0.0.1:8000`。

## 接口

```text
GET /api/health
POST /api/novels/chapters
```

## 文档

- [剧本 YAML Schema](docs/yaml-schema.md)
