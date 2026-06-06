from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_session
from chapter_parser import ChapterParseError
from llm import LLMResponseError
from models.user import User
from . import pipeline_service, service
from .schemas import (
    ProjectCreateRequest,
    ProjectAITaskJobResponse,
    ProjectChaptersRequest,
    ProjectChaptersResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectScriptVersionRequest,
    ProjectScriptVersionResponse,
    ProjectUpdateRequest,
    ProjectWorkspaceResponse,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
def list_projects(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectListResponse:
    return ProjectListResponse(projects=service.list_projects(session, current_user.id))


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    project = service.create_project(session, request, current_user.id)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    try:
        project = service.get_project(session, project_id, current_user.id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}/workspace", response_model=ProjectWorkspaceResponse)
def get_project_workspace(
    project_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectWorkspaceResponse:
    try:
        return pipeline_service.get_project_workspace(session, project_id, current_user.id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    request: ProjectUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    try:
        project = service.update_project(session, project_id, request, current_user.id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/chapters", response_model=ProjectChaptersResponse)
def parse_project_chapters(
    project_id: int,
    request: ProjectChaptersRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectChaptersResponse:
    try:
        return pipeline_service.parse_and_save_chapters(session, project_id, current_user.id, request.source_text)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ChapterParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/chapter-analyses/jobs", response_model=ProjectAITaskJobResponse)
def start_project_chapter_analysis_job(
    project_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectAITaskJobResponse:
    try:
        job = pipeline_service.prepare_chapter_analysis_job(session, project_id, current_user.id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except pipeline_service.ProjectPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if job.should_start:
        background_tasks.add_task(
            pipeline_service.run_chapter_analysis_job,
            job.response.ai_run.id,
            project_id,
            current_user.id,
        )

    return job.response


@router.post("/{project_id}/story-elements/jobs", response_model=ProjectAITaskJobResponse)
def start_project_story_elements_job(
    project_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectAITaskJobResponse:
    try:
        job = pipeline_service.prepare_story_elements_job(session, project_id, current_user.id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except pipeline_service.ProjectPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if job.should_start:
        background_tasks.add_task(
            pipeline_service.run_story_elements_job,
            job.response.ai_run.id,
            project_id,
            current_user.id,
        )

    return job.response


@router.post("/{project_id}/script-yaml/jobs", response_model=ProjectAITaskJobResponse)
def start_project_script_yaml_job(
    project_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectAITaskJobResponse:
    try:
        job = pipeline_service.prepare_script_yaml_job(session, project_id, current_user.id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except pipeline_service.ProjectPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if job.should_start:
        background_tasks.add_task(
            pipeline_service.run_script_yaml_job,
            job.response.ai_run.id,
            project_id,
            current_user.id,
        )

    return job.response


@router.post("/{project_id}/script-versions", response_model=ProjectScriptVersionResponse)
def save_project_script_version(
    project_id: int,
    request: ProjectScriptVersionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectScriptVersionResponse:
    try:
        return pipeline_service.save_script_version(session, project_id, current_user.id, request)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    try:
        service.delete_project(session, project_id, current_user.id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
