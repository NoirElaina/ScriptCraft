from collections.abc import Callable
from time import perf_counter
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from chapter_parser import ChapterParseError, ChapterParser
from llm import LLMConfigError, LLMResponseError, create_chat_model_from_env
from models.ai_run import AIRun
from models.chapter import Chapter
from models.project import Project
from models.script_version import ScriptVersion
from models.story_element import StoryElement
from script_yaml import ScriptYamlGenerator
from story_elements import StoryElementExtractor
from .schemas import (
    AIRunResponse,
    ChapterItemResponse,
    ProjectChaptersResponse,
    ProjectResponse,
    ProjectScriptYamlResponse,
    ProjectStoryElementsResponse,
    ProjectWorkspaceResponse,
    ScriptVersionResponse,
    StoryElementsSnapshotResponse,
)
from .service import ProjectNotFoundError, assign_owner_if_needed, get_project


ModelFactory = Callable[[], BaseChatModel]


class ProjectPipelineError(RuntimeError):
    pass


def parse_and_save_chapters(
    session: Session,
    project_id: int,
    owner_id: int,
    source_text: str,
) -> ProjectChaptersResponse:
    project = get_project(session, project_id, owner_id)
    assign_owner_if_needed(project, owner_id)

    try:
        parsed_chapters = ChapterParser().parse(source_text)
    except ChapterParseError:
        raise

    session.execute(delete(Chapter).where(Chapter.project_id == project.id))
    project.source_text = source_text
    project.status = "chapters_ready"

    chapters = [
        Chapter(
            project_id=project.id,
            chapter_index=chapter.index,
            chapter_key=chapter.id,
            heading=chapter.heading,
            title=chapter.title,
            content=chapter.content,
        )
        for chapter in parsed_chapters
    ]
    session.add_all(chapters)
    session.commit()
    session.refresh(project)

    return ProjectChaptersResponse(
        project_id=project.id,
        title=project.title,
        chapter_count=len(chapters),
        chapters=[_chapter_response(chapter) for chapter in _list_chapters(session, project.id)],
    )


def extract_and_save_story_elements(
    session: Session,
    project_id: int,
    owner_id: int,
    model_factory: ModelFactory = create_chat_model_from_env,
) -> ProjectStoryElementsResponse:
    project = get_project(session, project_id, owner_id)
    assign_owner_if_needed(project, owner_id)
    chapters = _require_chapters(session, project)
    input_payload = {"title": project.title, "chapters": [_chapter_payload(chapter) for chapter in chapters]}
    ai_run = _create_ai_run(session, project.id, "story_elements", input_payload)
    started_at = perf_counter()

    try:
        model = model_factory()
        result = StoryElementExtractor(model).extract(project.title, input_payload["chapters"])
    except (LLMConfigError, LLMResponseError) as exc:
        _finish_ai_run(session, ai_run, "failed", started_at, error_message=str(exc))
        session.commit()
        raise

    story_element = StoryElement(
        project_id=project.id,
        characters=result["characters"],
        locations=result["locations"],
        events=result["events"],
    )
    project.status = "story_elements_ready"
    session.add(story_element)
    session.flush()
    _finish_ai_run(session, ai_run, "succeeded", started_at, output_payload=result)
    session.commit()
    session.refresh(story_element)

    return ProjectStoryElementsResponse(
        project_id=project.id,
        title=project.title,
        ai_run_id=ai_run.id,
        story_elements=_story_elements_response(story_element),
    )


def generate_and_save_script_yaml(
    session: Session,
    project_id: int,
    owner_id: int,
    model_factory: ModelFactory = create_chat_model_from_env,
) -> ProjectScriptYamlResponse:
    project = get_project(session, project_id, owner_id)
    assign_owner_if_needed(project, owner_id)
    chapters = _require_chapters(session, project)
    story_element = _require_latest_story_elements(session, project)
    characters = story_element.characters
    locations = story_element.locations
    events = story_element.events
    input_payload = {
        "title": project.title,
        "chapters": [_chapter_payload(chapter) for chapter in chapters],
        "characters": characters,
        "locations": locations,
        "events": events,
    }
    ai_run = _create_ai_run(session, project.id, "script_yaml", input_payload)
    started_at = perf_counter()

    try:
        model = model_factory()
        yaml_content = ScriptYamlGenerator(model).generate(
            title=project.title,
            chapters=input_payload["chapters"],
            characters=characters,
            locations=locations,
            events=events,
        )
    except (LLMConfigError, LLMResponseError) as exc:
        _finish_ai_run(session, ai_run, "failed", started_at, error_message=str(exc))
        session.commit()
        raise

    script_version = ScriptVersion(
        project_id=project.id,
        version_name=f"AI 初稿 {_next_script_version_index(session, project.id)}",
        schema_version="1.0",
        yaml_content=yaml_content,
    )
    project.status = "script_ready"
    session.add(script_version)
    session.flush()
    _finish_ai_run(session, ai_run, "succeeded", started_at, output_payload={"yaml": yaml_content})
    session.commit()
    session.refresh(script_version)

    return ProjectScriptYamlResponse(
        project_id=project.id,
        title=project.title,
        ai_run_id=ai_run.id,
        script_version=ScriptVersionResponse.model_validate(script_version),
    )


def get_project_workspace(session: Session, project_id: int, owner_id: int) -> ProjectWorkspaceResponse:
    project = get_project(session, project_id, owner_id)
    chapters = [_chapter_response(chapter) for chapter in _list_chapters(session, project.id)]
    story_element = _latest_story_elements(session, project.id)
    script_version = _latest_script_version(session, project.id)
    ai_runs = session.scalars(
        select(AIRun).where(AIRun.project_id == project.id).order_by(AIRun.created_at.desc(), AIRun.id.desc()).limit(20)
    ).all()

    return ProjectWorkspaceResponse(
        project=ProjectResponse.model_validate(project),
        chapters=chapters,
        story_elements=_story_elements_response(story_element) if story_element else None,
        script_version=ScriptVersionResponse.model_validate(script_version) if script_version else None,
        ai_runs=[AIRunResponse.model_validate(ai_run) for ai_run in ai_runs],
    )


def _list_chapters(session: Session, project_id: int) -> list[Chapter]:
    return list(
        session.scalars(
            select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_index.asc())
        )
    )


def _require_chapters(session: Session, project: Project) -> list[Chapter]:
    chapters = _list_chapters(session, project.id)
    if len(chapters) < 3:
        raise ProjectPipelineError("项目至少需要先保存 3 个章节")
    return chapters


def _latest_story_elements(session: Session, project_id: int) -> StoryElement | None:
    return session.scalar(
        select(StoryElement)
        .where(StoryElement.project_id == project_id)
        .order_by(StoryElement.created_at.desc(), StoryElement.id.desc())
    )


def _require_latest_story_elements(session: Session, project: Project) -> StoryElement:
    story_element = _latest_story_elements(session, project.id)
    if story_element is None:
        raise ProjectPipelineError("项目需要先完成 AI 故事元素抽取")
    return story_element


def _latest_script_version(session: Session, project_id: int) -> ScriptVersion | None:
    return session.scalar(
        select(ScriptVersion)
        .where(ScriptVersion.project_id == project_id)
        .order_by(ScriptVersion.created_at.desc(), ScriptVersion.id.desc())
    )


def _next_script_version_index(session: Session, project_id: int) -> int:
    version_count = session.scalar(select(func.count()).select_from(ScriptVersion).where(ScriptVersion.project_id == project_id))
    return int(version_count or 0) + 1


def _chapter_payload(chapter: Chapter) -> dict[str, Any]:
    return {
        "id": chapter.chapter_key,
        "index": chapter.chapter_index,
        "heading": chapter.heading,
        "title": chapter.title,
        "content": chapter.content,
    }


def _chapter_response(chapter: Chapter) -> ChapterItemResponse:
    return ChapterItemResponse(**_chapter_payload(chapter))


def _story_elements_response(story_element: StoryElement) -> StoryElementsSnapshotResponse:
    return StoryElementsSnapshotResponse(
        id=story_element.id,
        project_id=story_element.project_id,
        characters=story_element.characters,
        locations=story_element.locations,
        events=story_element.events,
        created_at=story_element.created_at,
    )


def _create_ai_run(session: Session, project_id: int, task_type: str, input_payload: dict[str, Any]) -> AIRun:
    ai_run = AIRun(
        project_id=project_id,
        task_type=task_type,
        status="running",
        input_payload=input_payload,
    )
    session.add(ai_run)
    session.commit()
    session.refresh(ai_run)
    return ai_run


def _finish_ai_run(
    session: Session,
    ai_run: AIRun,
    status: str,
    started_at: float,
    output_payload: dict[str, Any] | None = None,
    error_message: str = "",
) -> None:
    ai_run.status = status
    ai_run.duration_ms = int((perf_counter() - started_at) * 1000)
    ai_run.output_payload = output_payload
    ai_run.error_message = error_message
    session.add(ai_run)
