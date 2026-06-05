# ScriptCraft Backend

Python uv + FastAPI 后端项目。

## 运行

```powershell
uv sync
uv run python main.py
```

## 接口

- `GET /api/health`：健康检查。
- `POST /api/chapters/parse`：解析小说章节，要求至少 3 个章节。
