from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from auth.router import router as auth_router
from projects import pipeline_service
from projects.router import router as projects_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline_service.mark_interrupted_ai_runs_on_startup()
    yield


app = FastAPI(title="ScriptCraft API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(projects_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "scriptcraft-backend"}


def main() -> None:
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
