from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from chapter_parser import ChapterParseError, ChapterParser
from llm import LLMConfigError, LLMResponseError, create_chat_model_from_env
from auth.router import router as auth_router
from projects.router import router as projects_router
from script_yaml import ScriptYamlGenerator
from story_elements import StoryElementExtractor


app = FastAPI(title="ScriptCraft API")
app.include_router(auth_router)
app.include_router(projects_router)


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


class StoryElementsRequest(BaseModel):
    title: str = Field(default="未命名小说", max_length=120, description="小说作品名")
    chapters: list[ChapterResponse] = Field(min_length=3, description="章节解析结果")


class CharacterResponse(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    role: str
    description: str
    motivation: str = ""


class LocationResponse(BaseModel):
    id: str
    name: str
    description: str = ""


class EventResponse(BaseModel):
    id: str
    source_chapter: str
    summary: str
    involved_characters: list[str] = Field(default_factory=list)


class StoryElementsResponse(BaseModel):
    title: str
    characters: list[CharacterResponse]
    locations: list[LocationResponse]
    events: list[EventResponse]


class ScriptYamlRequest(BaseModel):
    title: str = Field(default="未命名小说", max_length=120, description="小说作品名")
    chapters: list[ChapterResponse] = Field(min_length=3, description="章节解析结果")
    characters: list[CharacterResponse] = Field(default_factory=list, description="AI 抽取的角色")
    locations: list[LocationResponse] = Field(default_factory=list, description="AI 抽取的地点")
    events: list[EventResponse] = Field(default_factory=list, description="AI 抽取的事件")


class ScriptYamlResponse(BaseModel):
    yaml: str


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


@app.post("/api/novels/story-elements")
def create_story_elements(request: StoryElementsRequest) -> StoryElementsResponse:
    try:
        model = create_chat_model_from_env()
        result = StoryElementExtractor(model).extract(
            title=request.title,
            chapters=[chapter.model_dump() for chapter in request.chapters],
        )
    except LLMConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return StoryElementsResponse(**result)


@app.post("/api/novels/script-yaml")
def create_script_yaml(request: ScriptYamlRequest) -> ScriptYamlResponse:
    try:
        model = create_chat_model_from_env()
        script_yaml = ScriptYamlGenerator(model).generate(
            title=request.title,
            chapters=[chapter.model_dump() for chapter in request.chapters],
            characters=[character.model_dump() for character in request.characters],
            locations=[location.model_dump() for location in request.locations],
            events=[event.model_dump() for event in request.events],
        )
    except LLMConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ScriptYamlResponse(yaml=script_yaml)


def main() -> None:
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
