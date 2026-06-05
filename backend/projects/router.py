from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from database import get_session
from chapter_parser import ChapterParseError
from llm import LLMConfigError, LLMResponseError
from . import pipeline_service, service
from .schemas import (
    ProjectCreateRequest,
    ProjectChaptersRequest,
    ProjectChaptersResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectScriptYamlResponse,
    ProjectStoryElementsResponse,
    ProjectUpdateRequest,
    ProjectWorkspaceResponse,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
def list_projects(session: Session = Depends(get_session)) -> ProjectListResponse:
    return ProjectListResponse(projects=service.list_projects(session))


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreateRequest,
    session: Session = Depends(get_session),
) -> ProjectResponse:
    project = service.create_project(session, request)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, session: Session = Depends(get_session)) -> ProjectResponse:
    try:
        project = service.get_project(session, project_id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}/workspace", response_model=ProjectWorkspaceResponse)
def get_project_workspace(project_id: int, session: Session = Depends(get_session)) -> ProjectWorkspaceResponse:
    try:
        return pipeline_service.get_project_workspace(session, project_id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    request: ProjectUpdateRequest,
    session: Session = Depends(get_session),
) -> ProjectResponse:
    try:
        project = service.update_project(session, project_id, request)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/chapters", response_model=ProjectChaptersResponse)
def parse_project_chapters(
    project_id: int,
    request: ProjectChaptersRequest,
    session: Session = Depends(get_session),
) -> ProjectChaptersResponse:
    try:
        return pipeline_service.parse_and_save_chapters(session, project_id, request.source_text)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ChapterParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/story-elements", response_model=ProjectStoryElementsResponse)
def extract_project_story_elements(
    project_id: int,
    session: Session = Depends(get_session),
) -> ProjectStoryElementsResponse:
    try:
        return pipeline_service.extract_and_save_story_elements(session, project_id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except pipeline_service.ProjectPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{project_id}/script-yaml", response_model=ProjectScriptYamlResponse)
def generate_project_script_yaml(
    project_id: int,
    session: Session = Depends(get_session),
) -> ProjectScriptYamlResponse:
    try:
        return pipeline_service.generate_and_save_script_yaml(session, project_id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except pipeline_service.ProjectPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, session: Session = Depends(get_session)) -> Response:
    try:
        service.delete_project(session, project_id)
    except service.ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
