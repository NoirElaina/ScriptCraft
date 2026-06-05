from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from chapter_parser import ChapterParseError, ChapterParser


app = FastAPI(title="ScriptCraft API")


class ChapterParseRequest(BaseModel):
    text: str = Field(min_length=1, description="包含 3 个章节以上的小说文本")


class ChapterResponse(BaseModel):
    id: str
    index: int
    heading: str
    title: str
    content: str


class ChapterParseResponse(BaseModel):
    chapter_count: int
    chapters: list[ChapterResponse]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "scriptcraft-backend"}


@app.post("/api/chapters/parse")
def parse_chapters(request: ChapterParseRequest) -> ChapterParseResponse:
    try:
        chapters = ChapterParser().parse(request.text)
    except ChapterParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChapterParseResponse(
        chapter_count=len(chapters),
        chapters=[ChapterResponse(**chapter.__dict__) for chapter in chapters],
    )


def main() -> None:
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
