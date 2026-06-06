from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    source_text: str = Field(default="")


class ProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, min_length=1, max_length=40)
    source_text: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int | None
    title: str
    description: str
    status: str
    source_text: str
    created_at: datetime
    updated_at: datetime


class ProjectListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int | None
    title: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    chapter_count: int = 0
    script_version_count: int = 0


class ProjectListResponse(BaseModel):
    projects: list[ProjectListItemResponse]


class ChapterItemResponse(BaseModel):
    id: str
    index: int
    heading: str
    title: str
    content: str


class ProjectChaptersRequest(BaseModel):
    source_text: str = Field(min_length=1)


class ProjectChaptersResponse(BaseModel):
    project_id: int
    title: str
    chapter_count: int
    chapters: list[ChapterItemResponse]


class ChapterAnalysisItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    chapter_id: int
    chapter_key: str
    chapter_index: int
    summary: str
    analysis: dict
    created_at: datetime
    updated_at: datetime


class ProjectChapterAnalysesResponse(BaseModel):
    project_id: int
    title: str
    ai_run_id: int
    chapter_analyses: list[ChapterAnalysisItemResponse]


class CharacterItemResponse(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    role: str
    description: str
    motivation: str = ""


class LocationItemResponse(BaseModel):
    id: str
    name: str
    description: str = ""


class EventItemResponse(BaseModel):
    id: str
    source_chapter: str
    summary: str
    involved_characters: list[str] = Field(default_factory=list)


class StoryElementsSnapshotResponse(BaseModel):
    id: int
    project_id: int
    characters: list[CharacterItemResponse]
    locations: list[LocationItemResponse]
    events: list[EventItemResponse]
    created_at: datetime


class ProjectStoryElementsResponse(BaseModel):
    project_id: int
    title: str
    ai_run_id: int
    story_elements: StoryElementsSnapshotResponse


class ScriptVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    version_name: str
    schema_version: str
    yaml_content: str
    created_at: datetime
    updated_at: datetime


class ProjectScriptYamlResponse(BaseModel):
    project_id: int
    title: str
    ai_run_id: int
    script_version: ScriptVersionResponse


class ProjectScriptVersionRequest(BaseModel):
    version_name: str = Field(default="手动编辑版", min_length=1, max_length=120)
    yaml_content: str = Field(min_length=1)


class ProjectScriptVersionResponse(BaseModel):
    project_id: int
    title: str
    script_version: ScriptVersionResponse


class AIRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    task_type: str
    provider: str
    model: str
    status: str
    error_message: str
    duration_ms: int | None
    created_at: datetime


class ProjectChapterAnalysisJobResponse(BaseModel):
    project_id: int
    title: str
    ai_run: AIRunResponse


class ProjectWorkspaceResponse(BaseModel):
    project: ProjectResponse
    chapters: list[ChapterItemResponse]
    chapter_analyses: list[ChapterAnalysisItemResponse]
    story_elements: StoryElementsSnapshotResponse | None
    script_version: ScriptVersionResponse | None
    ai_runs: list[AIRunResponse]
