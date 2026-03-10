import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS_DIR = os.path.join(BASE_DIR, "..", "projects")
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
