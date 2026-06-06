# ScriptCraft Backend

Python uv + FastAPI 后端项目。

## 运行

```powershell
uv sync
uv run python main.py
```

## 接口

- `GET /api/health`：健康检查。
- `/api/auth/*`：注册、登录和当前用户信息。
- `/api/projects/*`：项目、章节、AI 后台任务、剧本版本管理。
