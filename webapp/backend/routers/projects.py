import os
import shutil
import time
from fastapi import APIRouter
from pydantic import BaseModel
from core.config import PROJECTS_DIR

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    category: str
    topic: str


@router.post("")
def create_project(req: ProjectCreate):
    pid = f"{req.name}_{int(time.time())}"
    project_dir = os.path.join(PROJECTS_DIR, pid)
    for sub in ["input", "bgm", "output", "temp_frames"]:
        os.makedirs(os.path.join(project_dir, sub), exist_ok=True)
    return {"id": pid, "path": project_dir, "status": "created"}


@router.get("")
def list_projects():
    if not os.path.isdir(PROJECTS_DIR):
        return {"projects": []}
    projects = []
    for d in sorted(os.listdir(PROJECTS_DIR), reverse=True):
        p = os.path.join(PROJECTS_DIR, d)
        if os.path.isdir(p):
            has_output = bool(os.listdir(os.path.join(p, "output"))) if os.path.isdir(os.path.join(p, "output")) else False
            projects.append({"id": d, "has_output": has_output})
    return {"projects": projects}


@router.delete("/{project_id}")
def delete_project(project_id: str):
    p = os.path.join(PROJECTS_DIR, project_id)
    if os.path.isdir(p):
        shutil.rmtree(p)
        return {"status": "deleted"}
    return {"status": "not_found"}
