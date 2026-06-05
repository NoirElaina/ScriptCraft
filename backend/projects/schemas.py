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
