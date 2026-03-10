import sys
import os

# 모듈 경로 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from core.config import PROJECTS_DIR
from routers import projects, videos, build, agent, pexels

app = FastAPI(title="YouTube Shorts 자동 제작기")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 프로젝트 파일 서빙 (영상 미리보기용)
os.makedirs(PROJECTS_DIR, exist_ok=True)
app.mount("/files", StaticFiles(directory=PROJECTS_DIR), name="files")

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(build.router, prefix="/api/build", tags=["build"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(pexels.router, prefix="/api/pexels", tags=["pexels"])


@app.get("/api/health")
def health():
    return {"status": "ok", "message": "YouTube Shorts 빌더 서버 실행 중"}
