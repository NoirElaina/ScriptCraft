from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from chapter_analysis import ChapterAnalyzer
from chapter_parser import ChapterParseError, ChapterParser, parse_chapter_heading_index
from database.session import get_session_factory
from llm import LLMConfigError, LLMResponseError, create_chat_model_from_env
from models.ai_run import AIRun
from models.chapter import Chapter
from models.chapter_analysis import ChapterAnalysis
from models.project import Project
from models.script_version import ScriptVersion
from models.story_element import StoryElement
from script_yaml import ScriptYamlGenerator, ScriptYamlToolRepairer, normalize_script_yaml_content
from story_elements import StoryElementExtractor
from .schemas import (
    AIRunResponse,
    ChapterAnalysisItemResponse,
    ProjectAITaskJobResponse,
    ChapterItemResponse,
    ProjectChaptersResponse,
    ProjectResponse,
    ProjectScriptYamlRepairRequest,
    ProjectScriptYamlRepairResponse,
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

    chapters = _sync_project_chapters(session, project, parsed_chapters)
    project.source_text = ""
    project.status = _chapter_parse_status(session, project.id, chapters)
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
    pending_chapters = _chapters_requiring_analysis(session, project.id, chapters)
    if not pending_chapters:
        project.status = "chapter_analyses_ready"
        ai_run = _create_ai_run(
            session,
            project.id,
            "chapter_analysis",
            _chapter_analysis_input_payload(project, chapters, pending_chapters),
        )
        _finish_ai_run(
            session,
            ai_run,
            "succeeded",
            perf_counter(),
            output_payload={
                "analyzed_count": 0,
                "skipped_count": len(chapters),
                "progress": {
                    "phase": "finished",
                    "chapter_total": len(chapters),
                    "completed_chapters": len(chapters),
                    "message": "全部章节已完成分析",
                },
            },
        )
        session.commit()
        session.refresh(ai_run)
        return PreparedAITaskJob(
            response=ProjectAITaskJobResponse(
                project_id=project.id,
                title=project.title,
                ai_run=AIRunResponse.model_validate(ai_run),
            ),
            should_start=False,
        )

    project.status = "chapter_analysis_running"
    ai_run = _create_ai_run(
        session,
        project.id,
        "chapter_analysis",
        _chapter_analysis_input_payload(project, chapters, pending_chapters),
    )

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
        analyzed_count = 0
        skipped_count = 0

        try:
            project = get_project(session, project_id, owner_id)
            chapters = _require_chapters(session, project)
            analyses_by_chapter_id = _chapter_analysis_by_chapter_id(session, project.id)
            pending_chapters = [chapter for chapter in chapters if chapter.id not in analyses_by_chapter_id]
            if not pending_chapters:
                project.status = "chapter_analyses_ready"
                _finish_ai_run(
                    session,
                    ai_run,
                    "succeeded",
                    started_at,
                    output_payload={
                        "chapter_analyses": [analysis.analysis for analysis in analyses_by_chapter_id.values()],
                        "analyzed_count": 0,
                        "skipped_count": len(chapters),
                    },
                )
                session.commit()
                return

            model = model_factory()
            analyzer = ChapterAnalyzer(model)
            on_stream = _make_ai_run_stream_callback(session, ai_run)

            for chapter in chapters:
                existing_analysis = analyses_by_chapter_id.get(chapter.id)
                if existing_analysis is not None:
                    output_payloads.append(existing_analysis.analysis)
                    skipped_count += 1
                    continue

                _update_ai_run_progress(
                    session,
                    ai_run,
                    _chapter_analysis_progress(
                        chapter,
                        len(output_payloads) + 1,
                        len(chapters),
                        len(output_payloads),
                    ),
                )
                analysis_payload = analyzer.analyze(
                    project.title,
                    _chapter_payload(chapter),
                    memory=_chapter_analysis_memory(output_payloads),
                    on_stream=on_stream,
                )

                output_payloads.append(analysis_payload)
                _save_chapter_analysis(session, project.id, chapter, analysis_payload)
                analyzed_count += 1
                _update_ai_run_progress(
                    session,
                    ai_run,
                    _chapter_analysis_progress(
                        chapter,
                        len(output_payloads),
                        len(chapters),
                        len(output_payloads),
                        completed=True,
                    ),
                )
                session.commit()

            project.status = "chapter_analyses_ready"
            _finish_ai_run(
                session,
                ai_run,
                "succeeded",
                started_at,
                output_payload={
                    "chapter_analyses": output_payloads,
                    "analyzed_count": analyzed_count,
                    "skipped_count": skipped_count,
                },
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
            on_stream = _make_ai_run_stream_callback(session, ai_run)
            result = StoryElementExtractor(model).extract(
                project.title,
                chapters,
                on_progress=lambda progress: _update_ai_run_progress(session, ai_run, progress),
                on_stream=on_stream,
            )

            story_element = StoryElement(
                project_id=project.id,
                characters=result["characters"],
                locations=result["locations"],
                events=result["events"],
                scenes=result["scenes"],
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
            on_stream = _make_ai_run_stream_callback(session, ai_run)
            yaml_content = ScriptYamlGenerator(model).generate(
                title=project.title,
                chapters=chapters,
                characters=story_element.characters,
                locations=story_element.locations,
                events=story_element.events,
                scene_cards=story_element.scenes,
                on_progress=lambda progress: _update_ai_run_progress(session, ai_run, progress),
                on_stream=on_stream,
            )

            script_version = ScriptVersion(
                project_id=project.id,
                version_name=f"AI 初稿 {_next_script_version_index(session, project.id)}",
                schema_version="2.0",
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
        schema_version="2.0",
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


def repair_script_yaml(
    session: Session,
    project_id: int,
    owner_id: int,
    request: ProjectScriptYamlRepairRequest,
    model_factory: ModelFactory = create_chat_model_from_env,
) -> ProjectScriptYamlRepairResponse:
    project = _get_project_for_ai_task(session, project_id, owner_id)
    running_ai_run = _latest_running_project_ai_run(session, project.id)
    if running_ai_run is not None:
        raise ProjectPipelineError(f"当前项目已有 AI 任务运行中：{_task_type_label(running_ai_run.task_type)}")

    ai_run = _create_ai_run(
        session,
        project.id,
        "script_yaml_repair",
        {
            "title": project.title,
            "validation_error": request.validation_error,
            "yaml_length": len(request.yaml_content),
        },
    )
    started_at = perf_counter()

    try:
        on_stream = _make_ai_run_stream_callback(session, ai_run)
        result = ScriptYamlToolRepairer(model_factory()).repair(
            yaml_content=request.yaml_content,
            validation_error=request.validation_error,
            on_stream=on_stream,
        )
        script_version = ScriptVersion(
            project_id=project.id,
            version_name=_script_repair_version_name(session, project.id),
            schema_version="2.0",
            yaml_content=result.yaml_content,
        )
        project.status = "script_ready"
        session.add(script_version)
        session.flush()
        _finish_ai_run(
            session,
            ai_run,
            "succeeded",
            started_at,
            output_payload={
                "operations": result.operations,
                "yaml_length": len(result.yaml_content),
                "script_version_id": script_version.id,
            },
        )
        session.commit()
        session.refresh(ai_run)
        session.refresh(script_version)
        return ProjectScriptYamlRepairResponse(
            project_id=project.id,
            title=project.title,
            yaml_content=result.yaml_content,
            operations=result.operations,
            script_version=ScriptVersionResponse.model_validate(script_version),
            ai_run=AIRunResponse.model_validate(ai_run),
        )
    except (LLMConfigError, LLMResponseError) as exc:
        _finish_ai_run(session, ai_run, "failed", started_at, error_message=str(exc))
        session.commit()
        raise ProjectPipelineError(str(exc)) from exc


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


def mark_interrupted_ai_runs_on_startup() -> int:
    session_factory = get_session_factory()
    with session_factory() as session:
        running_ai_runs = list(
            session.scalars(
                select(AIRun)
                .where(AIRun.status == "running")
                .order_by(AIRun.created_at.asc(), AIRun.id.asc())
            )
        )
        if not running_ai_runs:
            return 0

        now = datetime.now(timezone.utc)
        for ai_run in running_ai_runs:
            ai_run.status = "failed"
            ai_run.error_message = "后端服务重启，进程内后台任务已中断，请重新发起。"
            ai_run.duration_ms = int((now - _as_utc(ai_run.created_at)).total_seconds() * 1000)
            session.add(ai_run)

            project = session.get(Project, ai_run.project_id) if ai_run.project_id is not None else None
            if project is not None:
                project.status = _task_failed_project_status(ai_run.task_type)
                session.add(project)

        session.commit()
        return len(running_ai_runs)


def _list_chapters(session: Session, project_id: int) -> list[Chapter]:
    return list(
        session.scalars(
            select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_index.asc())
        )
    )


def _sync_project_chapters(session: Session, project: Project, parsed_chapters) -> list[Chapter]:
    existing_chapters = _normalize_existing_chapter_indexes(session, _list_chapters(session, project.id))
    existing_by_index = {chapter.chapter_index: chapter for chapter in existing_chapters}

    for parsed_chapter in parsed_chapters:
        existing_chapter = existing_by_index.get(parsed_chapter.index)
        if existing_chapter is None:
            session.add(
                Chapter(
                    project_id=project.id,
                    chapter_index=parsed_chapter.index,
                    chapter_key=parsed_chapter.id,
                    heading=parsed_chapter.heading,
                    title=parsed_chapter.title,
                    content=parsed_chapter.content,
                )
            )
            continue

        if _chapter_content_changed(existing_chapter, parsed_chapter):
            session.execute(delete(ChapterAnalysis).where(ChapterAnalysis.chapter_id == existing_chapter.id))

        existing_chapter.chapter_key = parsed_chapter.id
        existing_chapter.heading = parsed_chapter.heading
        existing_chapter.title = parsed_chapter.title
        existing_chapter.content = parsed_chapter.content
        session.add(existing_chapter)

    session.flush()
    return _list_chapters(session, project.id)


def _normalize_existing_chapter_indexes(session: Session, chapters: list[Chapter]) -> list[Chapter]:
    existing_by_index = {chapter.chapter_index: chapter for chapter in chapters}
    changed = False

    for chapter in chapters:
        parsed_index = parse_chapter_heading_index(chapter.heading)
        if parsed_index <= 0 or parsed_index == chapter.chapter_index:
            continue

        existing = existing_by_index.get(parsed_index)
        if existing is not None and existing.id != chapter.id:
            raise ProjectPipelineError(f"章节编号冲突：{chapter.heading} 与 {existing.heading}")

        existing_by_index.pop(chapter.chapter_index, None)
        chapter.chapter_index = parsed_index
        chapter.chapter_key = f"chapter_{parsed_index:03d}"
        session.add(chapter)
        existing_by_index[parsed_index] = chapter
        changed = True

    if changed:
        session.flush()
        return _list_chapters(session, chapters[0].project_id)

    return chapters


def _chapter_content_changed(chapter: Chapter, parsed_chapter) -> bool:
    return (
        chapter.chapter_key != parsed_chapter.id
        or chapter.heading != parsed_chapter.heading
        or chapter.title != parsed_chapter.title
        or chapter.content != parsed_chapter.content
    )


def _chapter_parse_status(session: Session, project_id: int, chapters: list[Chapter]) -> str:
    if not chapters:
        return "chapters_ready"

    analyses = _chapter_analysis_by_chapter_id(session, project_id)
    return "chapter_analyses_ready" if len(analyses) >= len(chapters) else "chapters_ready"


def _get_project_for_ai_task(session: Session, project_id: int, owner_id: int) -> Project:
    project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None or (project.owner_id is not None and project.owner_id != owner_id):
        raise ProjectNotFoundError(f"项目不存在：{project_id}")

    assign_owner_if_needed(project, owner_id)
    return project


def _require_chapters(session: Session, project: Project) -> list[Chapter]:
    chapters = _list_chapters(session, project.id)
    if not chapters:
        raise ProjectPipelineError("项目需要先保存章节")
    return chapters


def _chapter_analysis_input_payload(
    project: Project,
    chapters: list[Chapter],
    pending_chapters: list[Chapter] | None = None,
) -> dict[str, Any]:
    pending_ids = {chapter.chapter_key for chapter in pending_chapters} if pending_chapters is not None else {
        chapter.chapter_key for chapter in chapters
    }
    return {
        "title": project.title,
        "generation_mode": "incremental",
        "chapter_count": len(chapters),
        "pending_chapter_count": len(pending_ids),
        "pending_chapter_ids": sorted(pending_ids),
        "chapters": [
            {
                "id": chapter.chapter_key,
                "index": chapter.chapter_index,
                "heading": chapter.heading,
                "title": chapter.title,
                "needs_analysis": chapter.chapter_key in pending_ids,
            }
            for chapter in chapters
        ],
    }


def _chapters_requiring_analysis(session: Session, project_id: int, chapters: list[Chapter]) -> list[Chapter]:
    analyses_by_chapter_id = _chapter_analysis_by_chapter_id(session, project_id)
    return [chapter for chapter in chapters if chapter.id not in analyses_by_chapter_id]


def _chapter_analysis_by_chapter_id(session: Session, project_id: int) -> dict[int, ChapterAnalysis]:
    analyses = _list_chapter_analyses(session, project_id)
    return {analysis.chapter_id: analysis for analysis in analyses}


def _chapter_analysis_progress(
    chapter: Chapter,
    chapter_index: int,
    chapter_total: int,
    completed_chapters: int,
    *,
    completed: bool = False,
) -> dict[str, Any]:
    return {
        "phase": "chapter_completed" if completed else "chapter_analysis",
        "chapter_index": chapter_index,
        "chapter_total": chapter_total,
        "completed_chapters": completed_chapters,
        "current_chapter_id": chapter.chapter_key,
        "current_chapter_title": chapter.title,
        "message": (
            f"第 {chapter_index}/{chapter_total} 章分析完成"
            if completed
            else f"正在分析《{chapter.title}》：{chapter_index}/{chapter_total}"
        ),
    }


def _chapter_analysis_memory(previous_analyses: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "story_so_far": " ".join(str(item.get("summary", "")).strip() for item in previous_analyses if item.get("summary")),
        "known_characters": _unique_texts(
            character.get("name")
            for analysis in previous_analyses
            for character in analysis.get("characters", [])
            if isinstance(character, dict)
        ),
        "known_locations": _unique_texts(
            location.get("name")
            for analysis in previous_analyses
            for location in analysis.get("locations", [])
            if isinstance(location, dict)
        ),
        "continuity_notes": _unique_texts(
            note
            for analysis in previous_analyses
            for note in analysis.get("continuity_notes", [])
        ),
    }


def _story_elements_input_payload(project: Project, chapters: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "title": project.title,
        "generation_mode": "chapter_streaming",
        "chapter_count": len(chapters),
    }


def _script_yaml_input_payload(
    project: Project,
    chapters: list[dict[str, Any]],
    story_element: StoryElement,
) -> dict[str, Any]:
    return {
        "title": project.title,
        "generation_mode": "chapter_streaming",
        "chapter_count": len(chapters),
        "character_count": len(story_element.characters),
        "location_count": len(story_element.locations),
        "event_count": len(story_element.events),
        "scene_count": len(story_element.scenes),
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
        "script_yaml_repair": "剧本 YAML 修复",
    }
    return labels.get(task_type, task_type)


def _unique_texts(values) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            texts.append(text)
    return texts


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
    if not chapters:
        raise ProjectPipelineError("项目需要先保存章节")
    if len(analyses) < len(chapters):
        raise ProjectPipelineError("项目需要先完成 AI 章节分析")
    chapters_by_id = {chapter.id: chapter for chapter in chapters}
    contexts: list[dict[str, Any]] = []
    for analysis in analyses:
        chapter = chapters_by_id.get(analysis.chapter_id)
        if chapter is None:
            raise ProjectPipelineError("章节分析与章节记录不一致，请重新保存章节并分析")
        contexts.append(_chapter_analysis_context(analysis, chapter))
    return contexts


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


def _script_repair_version_name(session: Session, project_id: int) -> str:
    latest_version = _latest_script_version(session, project_id)
    if latest_version is None:
        return f"AI 修复版 {_next_script_version_index(session, project_id)}"
    return f"{latest_version.version_name} 修复版"


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


def _chapter_analysis_context(analysis: ChapterAnalysis, chapter: Chapter) -> dict[str, Any]:
    return {
        "id": analysis.chapter_key,
        "index": analysis.chapter_index,
        "heading": chapter.heading,
        "title": chapter.title,
        "content": chapter.content,
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
        scenes=story_element.scenes,
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
    if output_payload is not None:
        payload = _ai_run_output_payload(ai_run)
        payload.update(output_payload)
        ai_run.output_payload = payload
    ai_run.error_message = error_message
    session.add(ai_run)


def _update_ai_run_progress(session: Session, ai_run: AIRun, progress: dict[str, Any]) -> None:
    if ai_run.status != "running":
        return

    payload = _ai_run_output_payload(ai_run)
    payload["progress"] = dict(progress)
    ai_run.output_payload = payload
    session.add(ai_run)
    session.commit()


def _make_ai_run_stream_callback(session: Session, ai_run: AIRun) -> Callable[[dict[str, Any]], None]:
    def callback(event: dict[str, Any]) -> None:
        _append_ai_run_stream_event(session, ai_run, event)

    return callback


def _append_ai_run_stream_event(session: Session, ai_run: AIRun, event: dict[str, Any]) -> None:
    if ai_run.status != "running":
        return

    payload = _ai_run_output_payload(ai_run)
    stream = payload.get("stream")
    if not isinstance(stream, list):
        stream = []

    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": len(stream) + 1,
        "created_at": now,
        "type": str(event.get("type") or "message"),
        "node": str(event.get("node") or ""),
        "title": str(event.get("title") or ""),
        "content": str(event.get("content") or ""),
    }

    if (
        event.get("append")
        and stream
        and stream[-1].get("type") == entry["type"]
        and stream[-1].get("node") == entry["node"]
        and stream[-1].get("title") == entry["title"]
    ):
        stream[-1]["content"] = str(stream[-1].get("content") or "") + entry["content"]
        stream[-1]["created_at"] = now
    else:
        stream.append(entry)

    payload["stream"] = stream[-100:]
    ai_run.output_payload = payload
    session.add(ai_run)
    session.commit()


def _ai_run_output_payload(ai_run: AIRun) -> dict[str, Any]:
    if isinstance(ai_run.output_payload, dict):
        return dict(ai_run.output_payload)
    return {}


def _task_failed_project_status(task_type: str) -> str:
    statuses = {
        "chapter_analysis": "chapter_analysis_failed",
        "story_elements": "story_elements_failed",
        "script_yaml": "script_yaml_failed",
        "script_yaml_repair": "script_yaml_failed",
    }
    return statuses.get(task_type, "ai_task_failed")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
