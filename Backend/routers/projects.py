from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

# Note the absolute imports using 'Backend'
from Backend import models
from Backend.database import get_db

# 1. Create the Router
# The prefix="/projects" means every route here automatically starts with /projects
router = APIRouter(prefix="/projects", tags=["Projects"])


# 2. Define Schemas (Moved from main.py)
class ProjectCreate(BaseModel):
    name: str
    path: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    is_active: Optional[bool] = None


class IDECreate(BaseModel):
    name: str
    path: str


# 3. Define the Routes (Notice we use @router instead of @app now)

@router.post("/")
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    db_project = models.Project(name=project.name, path=project.path)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/")
def get_projects(db: Session = Depends(get_db)):
    return db.query(models.Project).all()


@router.put("/{project_id}")
def update_project(project_id: int, project_data: ProjectUpdate, db: Session = Depends(get_db)):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project_data.name is not None:
        db_project.name = project_data.name
    if project_data.path is not None:
        db_project.path = project_data.path
    if project_data.is_active is not None:
        db_project.is_active = project_data.is_active

    db.commit()
    db.refresh(db_project)
    return db_project


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(db_project)
    db.commit()
    return {"message": f"Project {project_id} deleted successfully"}


# --- IDE ROUTES ---
# We can keep IDE routes in the Projects router since they are closely related,
# but we'll give them their own prefix and tags here for clarity.

ide_router = APIRouter(prefix="/ides", tags=["IDE Paths"])


@ide_router.post("/")
def add_ide(ide: IDECreate, db: Session = Depends(get_db)):
    db_ide = models.IDEPath(name=ide.name, path=ide.path)
    db.add(db_ide)
    db.commit()
    db.refresh(db_ide)
    return db_ide


@ide_router.get("/")
def get_ides(db: Session = Depends(get_db)):
    return db.query(models.IDEPath).all()