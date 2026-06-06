from fastapi import FastAPI
import uvicorn

from auth.router import router as auth_router
from projects.router import router as projects_router


app = FastAPI(title="ScriptCraft API")
app.include_router(auth_router)
app.include_router(projects_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "scriptcraft-backend"}


def main() -> None:
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
