from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.chapter import Chapter
from models.project import Project
from models.script_version import ScriptVersion
from .schemas import ProjectCreateRequest, ProjectListItemResponse, ProjectUpdateRequest


class ProjectNotFoundError(RuntimeError):
    pass


def list_projects(session: Session) -> list[ProjectListItemResponse]:
    chapter_count = func.count(func.distinct(Chapter.id))
    script_version_count = func.count(func.distinct(ScriptVersion.id))

    rows = session.execute(
        select(Project, chapter_count, script_version_count)
        .outerjoin(Chapter, Chapter.project_id == Project.id)
        .outerjoin(ScriptVersion, ScriptVersion.project_id == Project.id)
        .group_by(Project.id)
        .order_by(Project.updated_at.desc(), Project.id.desc())
    ).all()

    return [
        ProjectListItemResponse.model_validate(project).model_copy(
            update={
                "chapter_count": chapters,
                "script_version_count": script_versions,
            }
        )
        for project, chapters, script_versions in rows
    ]


def create_project(session: Session, request: ProjectCreateRequest) -> Project:
    project = Project(
        title=request.title.strip(),
        description=request.description.strip(),
        source_text=request.source_text,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def get_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"项目不存在：{project_id}")
    return project


def update_project(session: Session, project_id: int, request: ProjectUpdateRequest) -> Project:
    project = get_project(session, project_id)
    update_values = request.model_dump(exclude_unset=True)

    for field, value in update_values.items():
        if isinstance(value, str) and field in {"title", "description", "status"}:
            value = value.strip()
        setattr(project, field, value)

    session.commit()
    session.refresh(project)
    return project


def delete_project(session: Session, project_id: int) -> None:
    project = get_project(session, project_id)
    session.delete(project)
    session.commit()
