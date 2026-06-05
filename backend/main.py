from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from chapter_parser import ChapterParseError, ChapterParser


app = FastAPI(title="ScriptCraft API")


class NovelChapterRequest(BaseModel):
    title: str = Field(default="未命名小说", max_length=120, description="小说作品名")
    text: str = Field(min_length=1, description="包含 3 个章节以上的小说文本")


class ChapterResponse(BaseModel):
    id: str
    index: int
    heading: str
    title: str
    content: str


class NovelChaptersResponse(BaseModel):
    title: str
    chapter_count: int
    chapters: list[ChapterResponse]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "scriptcraft-backend"}


@app.post("/api/novels/chapters")
def create_novel_chapters(request: NovelChapterRequest) -> NovelChaptersResponse:
    try:
        chapters = ChapterParser().parse(request.text)
    except ChapterParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    title = request.title.strip() or "未命名小说"

    return NovelChaptersResponse(
        title=title,
        chapter_count=len(chapters),
        chapters=[ChapterResponse(**chapter.__dict__) for chapter in chapters],
    )


def main() -> None:
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
