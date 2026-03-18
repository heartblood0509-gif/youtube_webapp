import os
import json
import shutil
import subprocess
import time
from fastapi import APIRouter
from pydantic import BaseModel
from core.config import PROJECTS_DIR, validate_project_id

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


@router.get("/gallery")
def gallery():
    """완성된 영상 목록 (미리보기용)"""
    if not os.path.isdir(PROJECTS_DIR):
        return {"videos": []}
    results = []
    for d in sorted(os.listdir(PROJECTS_DIR), reverse=True):
        output_dir = os.path.join(PROJECTS_DIR, d, "output")
        if not os.path.isdir(output_dir):
            continue
        for f in os.listdir(output_dir):
            if not f.endswith(".mp4"):
                continue
            path = os.path.join(output_dir, f)
            # ffprobe로 영상 정보 추출
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", path],
                capture_output=True, text=True,
            )
            width, height, duration = 0, 0, 0.0
            try:
                info = json.loads(probe.stdout)
                vs = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
                width = int(vs.get("width", 0))
                height = int(vs.get("height", 0))
                duration = round(float(info.get("format", {}).get("duration", 0)), 1)
            except Exception:
                pass
            results.append({
                "project_id": d,
                "filename": f,
                "url": f"/files/{d}/output/{f}",
                "width": width,
                "height": height,
                "duration": duration,
                "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1),
                "created_at": int(os.path.getmtime(path)),
            })
    return {"videos": results}


@router.delete("/{project_id}")
def delete_project(project_id: str):
    validate_project_id(project_id)
    p = os.path.join(PROJECTS_DIR, project_id)
    if os.path.isdir(p):
        shutil.rmtree(p)
        return {"status": "deleted"}
    return {"status": "not_found"}
