import os
import re
import pathlib

from dotenv import load_dotenv

# backend/.env 파일에서 환경변수 로드 (API 키 등)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS_DIR = os.path.join(BASE_DIR, "..", "projects")

# API Keys (백엔드 환경변수에서 로드 — 프론트엔드에 노출하지 않음)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")


def validate_project_id(project_id: str) -> str:
    """project_id 검증 — Path Traversal 방지

    영문, 숫자, 한글, 언더스코어, 하이픈만 허용.
    ../ 등 경로 탈출 패턴을 차단한다.
    """
    if not project_id or not re.match(r'^[\w\-]+$', project_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"유효하지 않은 프로젝트 ID: {project_id}")
    resolved = pathlib.Path(PROJECTS_DIR, project_id).resolve()
    if not resolved.is_relative_to(pathlib.Path(PROJECTS_DIR).resolve()):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="프로젝트 경로 접근이 거부되었습니다")
    return project_id
SHARED_BGM_DIR = os.path.join(BASE_DIR, "..", "shared", "bgm")

# 빌드 상수 (SKILL.md 기준)
CANVAS_W = 1080
CANVAS_H = 1920
SQUARE_SIZE = 1080
SQUARE_Y = 420
TITLE_COLOR = "#00CED1"
TITLE_FONTSIZE = 73
SUBTITLE_FONTSIZE = 48
SUBTITLE_Y = 1370
TITLE_Y_SINGLE = 317
TITLE_Y_UPPER = 232
TITLE_Y_LOWER = 317
TITLE_LINE_GAP = 85
MAX_SUBTITLE_DISPLAY = 12
CLIP_BUFFER = 0.15
BGM_VOLUME_DEFAULT = 0.12

# Typecast TTS
TYPECAST_API_KEY = os.environ.get("TYPECAST_API_KEY", "")
TYPECAST_VOICE_ID = "tc_62e8f21e979b3860fe2f6a24"
TYPECAST_MODEL = "ssfm-v30"

# 폰트 우선순위
FONT_PRIORITY = [
    os.path.expanduser("~/Library/Fonts/GmarketSansTTFBold.ttf"),
    os.path.expanduser("~/Library/Fonts/NanumSquareEB.ttf"),
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]


def find_best_font() -> str:
    for path in FONT_PRIORITY:
        if os.path.exists(path):
            return path
    raise RuntimeError("사용 가능한 한글 폰트를 찾을 수 없습니다")


def find_bgm(project_dir: str) -> str | None:
    bgm_dir = os.path.join(project_dir, "bgm")
    if os.path.isdir(bgm_dir):
        for f in os.listdir(bgm_dir):
            if f.endswith((".mp3", ".wav", ".m4a")):
                return os.path.join(bgm_dir, f)
    # 공유 BGM 폴더 탐색
    if os.path.isdir(SHARED_BGM_DIR):
        for f in os.listdir(SHARED_BGM_DIR):
            if f.endswith((".mp3", ".wav", ".m4a")):
                return os.path.join(SHARED_BGM_DIR, f)
    # 다른 프로젝트에서 탐색
    ai_project = os.path.expanduser("~/AI project")
    if os.path.isdir(ai_project):
        for d in os.listdir(ai_project):
            bgm_path = os.path.join(ai_project, d, "bgm")
            if os.path.isdir(bgm_path):
                for f in os.listdir(bgm_path):
                    if f.endswith((".mp3", ".wav", ".m4a")):
                        return os.path.join(bgm_path, f)
    return None
