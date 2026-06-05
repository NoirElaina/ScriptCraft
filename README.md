# ScriptCraft

ScriptCraft 是一个 AI 小说转剧本工具，对应 XEngineer 第三批次议题三。项目目标是将 3 个章节以上的小说文本转换为结构化剧本 YAML，并提供可编辑、可校验的剧本初稿。

## 技术栈

- 前端：Vue 3、Vite、TypeScript、Pinia、Vue Router、shadcn-vue、Tailwind CSS v4
- 后端：Python、uv、FastAPI

## 目录结构

```text
ScriptCraft/
  frontend/   前端项目
  backend/    后端项目
```

## 本地运行

前端：

```powershell
cd frontend
npm install
npm run dev
```

后端：

```powershell
cd backend
uv sync
uv run python main.py
```

章节解析接口：

```text
POST /api/chapters/parse
```

## 当前进度

- 已初始化 Vue 前端项目
- 已初始化 Python uv 后端项目
- 已新增小说章节解析接口
