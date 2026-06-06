from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from chapter_analysis import ChapterAnalyzer
from chapter_parser import ChapterParseError, ChapterParser
from database.session import get_session_factory
from llm import LLMConfigError, LLMResponseError, create_chat_model_from_env
from models.ai_run import AIRun
from models.chapter import Chapter
from models.chapter_analysis import ChapterAnalysis
from models.project import Project
from models.script_version import ScriptVersion
from models.story_element import StoryElement
from script_yaml import ScriptYamlGenerator, normalize_script_yaml_content
from story_elements import StoryElementExtractor
from .schemas import (
    AIRunResponse,
    ChapterAnalysisItemResponse,
    ProjectAITaskJobResponse,
    ChapterItemResponse,
    ProjectChaptersResponse,
    ProjectResponse,
    ProjectScriptVersionRequest,
    ProjectScriptVersionResponse,
    ProjectWorkspaceResponse,
    ScriptVersionResponse,
    StoryElementsSnapshotResponse,
)
from .service import ProjectNotFoundError, assign_owner_if_needed, get_project


ModelFactory = Callable[[], BaseChatModel]


class ProjectPipelineError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedAITaskJob:
    response: ProjectAITaskJobResponse
    should_start: bool


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

    session.execute(delete(ChapterAnalysis).where(ChapterAnalysis.project_id == project.id))
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


def prepare_chapter_analysis_job(
    session: Session,
    project_id: int,
    owner_id: int,
) -> PreparedAITaskJob:
    project = _get_project_for_ai_task(session, project_id, owner_id)
    running_ai_run = _running_ai_run_for_task_or_raise(session, project, "chapter_analysis")
    if running_ai_run:
        return PreparedAITaskJob(
            response=ProjectAITaskJobResponse(
                project_id=project.id,
                title=project.title,
                ai_run=AIRunResponse.model_validate(running_ai_run),
            ),
            should_start=False,
        )

    chapters = _require_chapters(session, project)
    session.execute(delete(ChapterAnalysis).where(ChapterAnalysis.project_id == project.id))
    project.status = "chapter_analysis_running"
    ai_run = _create_ai_run(session, project.id, "chapter_analysis", _chapter_analysis_input_payload(project, chapters))

    return PreparedAITaskJob(
        response=ProjectAITaskJobResponse(
            project_id=project.id,
            title=project.title,
            ai_run=AIRunResponse.model_validate(ai_run),
        ),
        should_start=True,
    )


def run_chapter_analysis_job(
    ai_run_id: int,
    project_id: int,
    owner_id: int,
    model_factory: ModelFactory = create_chat_model_from_env,
) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        ai_run = session.get(AIRun, ai_run_id)
        if ai_run is None or ai_run.status != "running":
            return

        started_at = perf_counter()
        output_payloads: list[dict[str, Any]] = []

        try:
            project = get_project(session, project_id, owner_id)
            chapters = _require_chapters(session, project)
            model = model_factory()
            analyzer = ChapterAnalyzer(model)

            for chapter in chapters:
                analysis_payload = analyzer.analyze(project.title, _chapter_payload(chapter))
                output_payloads.append(analysis_payload)
                _save_chapter_analysis(session, project.id, chapter, analysis_payload)
                session.commit()

            project.status = "chapter_analyses_ready"
            _finish_ai_run(
                session,
                ai_run,
                "succeeded",
                started_at,
                output_payload={"chapter_analyses": output_payloads},
            )
            session.commit()
        except (ProjectNotFoundError, ProjectPipelineError, LLMConfigError, LLMResponseError) as exc:
            _mark_chapter_analysis_job_failed(session, ai_run, started_at, str(exc))
        except Exception as exc:
            _mark_chapter_analysis_job_failed(session, ai_run, started_at, f"章节分析任务异常：{exc}")
            raise


def prepare_story_elements_job(
    session: Session,
    project_id: int,
    owner_id: int,
) -> PreparedAITaskJob:
    project = _get_project_for_ai_task(session, project_id, owner_id)
    running_ai_run = _running_ai_run_for_task_or_raise(session, project, "story_elements")
    if running_ai_run:
        return PreparedAITaskJob(
            response=ProjectAITaskJobResponse(
                project_id=project.id,
                title=project.title,
                ai_run=AIRunResponse.model_validate(running_ai_run),
            ),
            should_start=False,
        )

    chapters = _require_chapter_analysis_contexts(session, project)
    project.status = "story_elements_running"
    ai_run = _create_ai_run(
        session,
        project.id,
        "story_elements",
        _story_elements_input_payload(project, chapters),
    )

    return PreparedAITaskJob(
        response=ProjectAITaskJobResponse(
            project_id=project.id,
            title=project.title,
            ai_run=AIRunResponse.model_validate(ai_run),
        ),
        should_start=True,
    )


def run_story_elements_job(
    ai_run_id: int,
    project_id: int,
    owner_id: int,
    model_factory: ModelFactory = create_chat_model_from_env,
) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        ai_run = session.get(AIRun, ai_run_id)
        if ai_run is None or ai_run.status != "running":
            return

        started_at = perf_counter()

        try:
            project = get_project(session, project_id, owner_id)
            chapters = _require_chapter_analysis_contexts(session, project)
            model = model_factory()
            result = StoryElementExtractor(model).extract(project.title, chapters)

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
        except (ProjectNotFoundError, ProjectPipelineError, LLMConfigError, LLMResponseError) as exc:
            _mark_ai_task_job_failed(session, ai_run, "story_elements_failed", started_at, str(exc))
        except Exception as exc:
            _mark_ai_task_job_failed(session, ai_run, "story_elements_failed", started_at, f"故事元素抽取任务异常：{exc}")
            raise


def prepare_script_yaml_job(
    session: Session,
    project_id: int,
    owner_id: int,
) -> PreparedAITaskJob:
    project = _get_project_for_ai_task(session, project_id, owner_id)
    running_ai_run = _running_ai_run_for_task_or_raise(session, project, "script_yaml")
    if running_ai_run:
        return PreparedAITaskJob(
            response=ProjectAITaskJobResponse(
                project_id=project.id,
                title=project.title,
                ai_run=AIRunResponse.model_validate(running_ai_run),
            ),
            should_start=False,
        )

    chapters = _require_chapter_analysis_contexts(session, project)
    story_element = _require_latest_story_elements(session, project)
    project.status = "script_yaml_running"
    ai_run = _create_ai_run(
        session,
        project.id,
        "script_yaml",
        _script_yaml_input_payload(project, chapters, story_element),
    )

    return PreparedAITaskJob(
        response=ProjectAITaskJobResponse(
            project_id=project.id,
            title=project.title,
            ai_run=AIRunResponse.model_validate(ai_run),
        ),
        should_start=True,
    )


def run_script_yaml_job(
    ai_run_id: int,
    project_id: int,
    owner_id: int,
    model_factory: ModelFactory = create_chat_model_from_env,
) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        ai_run = session.get(AIRun, ai_run_id)
        if ai_run is None or ai_run.status != "running":
            return

        started_at = perf_counter()

        try:
            project = get_project(session, project_id, owner_id)
            chapters = _require_chapter_analysis_contexts(session, project)
            story_element = _require_latest_story_elements(session, project)
            model = model_factory()
            yaml_content = ScriptYamlGenerator(model).generate(
                title=project.title,
                chapters=chapters,
                characters=story_element.characters,
                locations=story_element.locations,
                events=story_element.events,
            )

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
        except (ProjectNotFoundError, ProjectPipelineError, LLMConfigError, LLMResponseError) as exc:
            _mark_ai_task_job_failed(session, ai_run, "script_yaml_failed", started_at, str(exc))
        except Exception as exc:
            _mark_ai_task_job_failed(session, ai_run, "script_yaml_failed", started_at, f"剧本 YAML 生成任务异常：{exc}")
            raise


def save_script_version(
    session: Session,
    project_id: int,
    owner_id: int,
    request: ProjectScriptVersionRequest,
) -> ProjectScriptVersionResponse:
    project = get_project(session, project_id, owner_id)
    assign_owner_if_needed(project, owner_id)

    try:
        yaml_content = normalize_script_yaml_content(request.yaml_content)
    except LLMResponseError:
        raise

    script_version = ScriptVersion(
        project_id=project.id,
        version_name=request.version_name.strip() or f"手动编辑版 {_next_script_version_index(session, project.id)}",
        schema_version="1.0",
        yaml_content=yaml_content,
    )
    project.status = "script_ready"
    session.add(script_version)
    session.commit()
    session.refresh(script_version)

    return ProjectScriptVersionResponse(
        project_id=project.id,
        title=project.title,
        script_version=ScriptVersionResponse.model_validate(script_version),
    )


def get_project_workspace(session: Session, project_id: int, owner_id: int) -> ProjectWorkspaceResponse:
    project = get_project(session, project_id, owner_id)
    chapters = [_chapter_response(chapter) for chapter in _list_chapters(session, project.id)]
    chapter_analyses = [_chapter_analysis_response(analysis) for analysis in _list_chapter_analyses(session, project.id)]
    story_element = _latest_story_elements(session, project.id)
    script_version = _latest_script_version(session, project.id)
    ai_runs = session.scalars(
        select(AIRun).where(AIRun.project_id == project.id).order_by(AIRun.created_at.desc(), AIRun.id.desc()).limit(20)
    ).all()

    return ProjectWorkspaceResponse(
        project=ProjectResponse.model_validate(project),
        chapters=chapters,
        chapter_analyses=chapter_analyses,
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


def _get_project_for_ai_task(session: Session, project_id: int, owner_id: int) -> Project:
    project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None or (project.owner_id is not None and project.owner_id != owner_id):
        raise ProjectNotFoundError(f"项目不存在：{project_id}")

    assign_owner_if_needed(project, owner_id)
    return project


def _require_chapters(session: Session, project: Project) -> list[Chapter]:
    chapters = _list_chapters(session, project.id)
    if len(chapters) < 3:
        raise ProjectPipelineError("项目至少需要先保存 3 个章节")
    return chapters


def _chapter_analysis_input_payload(project: Project, chapters: list[Chapter]) -> dict[str, Any]:
    return {
        "title": project.title,
        "chapters": [
            {
                "id": chapter.chapter_key,
                "index": chapter.chapter_index,
                "heading": chapter.heading,
                "title": chapter.title,
            }
            for chapter in chapters
        ],
    }


def _story_elements_input_payload(project: Project, chapters: list[dict[str, Any]]) -> dict[str, Any]:
    return {"title": project.title, "chapters": chapters}


def _script_yaml_input_payload(
    project: Project,
    chapters: list[dict[str, Any]],
    story_element: StoryElement,
) -> dict[str, Any]:
    return {
        "title": project.title,
        "chapters": chapters,
        "characters": story_element.characters,
        "locations": story_element.locations,
        "events": story_element.events,
    }


def _running_ai_run_for_task_or_raise(session: Session, project: Project, task_type: str) -> AIRun | None:
    ai_run = _latest_running_project_ai_run(session, project.id)
    if ai_run is None:
        return None
    if ai_run.task_type == task_type:
        return ai_run

    raise ProjectPipelineError(f"当前项目已有 AI 任务运行中：{_task_type_label(ai_run.task_type)}")


def _latest_running_project_ai_run(session: Session, project_id: int) -> AIRun | None:
    return session.scalar(
        select(AIRun)
        .where(
            AIRun.project_id == project_id,
            AIRun.status == "running",
        )
        .order_by(AIRun.created_at.desc(), AIRun.id.desc())
    )


def _task_type_label(task_type: str) -> str:
    labels = {
        "chapter_analysis": "章节分析",
        "story_elements": "故事元素抽取",
        "script_yaml": "剧本 YAML 生成",
    }
    return labels.get(task_type, task_type)


def _list_chapter_analyses(session: Session, project_id: int) -> list[ChapterAnalysis]:
    return list(
        session.scalars(
            select(ChapterAnalysis)
            .where(ChapterAnalysis.project_id == project_id)
            .order_by(ChapterAnalysis.chapter_index.asc(), ChapterAnalysis.id.asc())
        )
    )


def _require_chapter_analysis_contexts(session: Session, project: Project) -> list[dict[str, Any]]:
    chapters = _list_chapters(session, project.id)
    analyses = _list_chapter_analyses(session, project.id)
    if len(chapters) < 3:
        raise ProjectPipelineError("项目至少需要先保存 3 个章节")
    if len(analyses) < len(chapters):
        raise ProjectPipelineError("项目需要先完成 AI 章节分析")
    return [_chapter_analysis_context(analysis) for analysis in analyses]


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


def _build_chapter_analysis(project_id: int, chapter: Chapter, analysis: dict[str, Any]) -> ChapterAnalysis:
    return ChapterAnalysis(
        project_id=project_id,
        chapter_id=chapter.id,
        chapter_key=chapter.chapter_key,
        chapter_index=chapter.chapter_index,
        summary=analysis["summary"],
        analysis=analysis,
    )


def _save_chapter_analysis(
    session: Session,
    project_id: int,
    chapter: Chapter,
    analysis: dict[str, Any],
) -> ChapterAnalysis:
    chapter_analysis = session.scalar(
        select(ChapterAnalysis).where(
            ChapterAnalysis.project_id == project_id,
            ChapterAnalysis.chapter_id == chapter.id,
        )
    )
    if chapter_analysis is None:
        chapter_analysis = _build_chapter_analysis(project_id, chapter, analysis)
        session.add(chapter_analysis)
        return chapter_analysis

    chapter_analysis.chapter_key = chapter.chapter_key
    chapter_analysis.chapter_index = chapter.chapter_index
    chapter_analysis.summary = analysis["summary"]
    chapter_analysis.analysis = analysis
    session.add(chapter_analysis)
    return chapter_analysis


def _chapter_analysis_response(analysis: ChapterAnalysis) -> ChapterAnalysisItemResponse:
    return ChapterAnalysisItemResponse.model_validate(analysis)


def _chapter_analysis_context(analysis: ChapterAnalysis) -> dict[str, Any]:
    return {
        "id": analysis.chapter_key,
        "index": analysis.chapter_index,
        "heading": analysis.analysis.get("heading", ""),
        "title": analysis.analysis.get("title", ""),
        "summary": analysis.summary,
        "analysis": analysis.analysis,
    }


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


def _mark_chapter_analysis_job_failed(
    session: Session,
    ai_run: AIRun,
    started_at: float,
    error_message: str,
) -> None:
    _mark_ai_task_job_failed(session, ai_run, "chapter_analysis_failed", started_at, error_message)


def _mark_ai_task_job_failed(
    session: Session,
    ai_run: AIRun,
    project_status: str,
    started_at: float,
    error_message: str,
) -> None:
    project = session.get(Project, ai_run.project_id) if ai_run.project_id is not None else None
    if project is not None:
        project.status = project_status

    _finish_ai_run(session, ai_run, "failed", started_at, error_message=error_message)
    session.commit()
