from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.auth import require_user
from app.db.session import get_db
from app.models.project import Project
from app.models.user import AppUser
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


def _owned_project_or_404(project_id: str, db: Session, user: AppUser) -> Project:
    """按归属取项目：NULL 归属视为旧数据共享，其余必须匹配当前用户。"""
    project = db.get(Project, project_id)
    if project is None or (
        project.owner_user_id is not None and project.owner_user_id != user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user: AppUser = Depends(require_user)):
    return (
        db.query(Project)
        .filter(or_(
            Project.owner_user_id == user.id,
            Project.owner_user_id.is_(None),
        ))
        .order_by(Project.created_at.desc())
        .all()
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    project = Project(**payload.model_dump(), owner_user_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    return _owned_project_or_404(project_id, db, user)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    project = _owned_project_or_404(project_id, db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    project = _owned_project_or_404(project_id, db, user)
    db.delete(project)
    db.commit()
