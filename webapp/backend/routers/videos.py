import os
import json
import asyncio
import uuid
import threading
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.config import PROJECTS_DIR, validate_project_id, GEMINI_API_KEY
from services.video_service import (
    analyze_video, download_youtube, auto_generate_clips,
    search_and_download, MAX_QUERIES,
)
from services.video_verifier import verify_videos
from services.smart_clip_service import smart_generate_clips

router = APIRouter()

# AI 검색 SSE를 위한 이벤트 큐
_search_queues: dict[str, asyncio.Queue] = {}


@router.post("/upload")
async def upload_videos(
    project_id: str = Form(...),
    files: list[UploadFile] = File(...),
):
    validate_project_id(project_id)
    project_dir = os.path.join(PROJECTS_DIR, project_id, "input")
    os.makedirs(project_dir, exist_ok=True)
    saved = []
    for f in files:
        path = os.path.join(project_dir, f.filename)
        with open(path, "wb") as out:
            content = await f.read()
            out.write(content)
        saved.append(f.filename)
    return {"uploaded": saved}


class DownloadRequest(BaseModel):
    project_id: str
    urls: list[str]
    filenames: list[str]


@router.post("/download")
def download_videos(req: DownloadRequest):
    validate_project_id(req.project_id)
    input_dir = os.path.join(PROJECTS_DIR, req.project_id, "input")
    os.makedirs(input_dir, exist_ok=True)
    results = []
    for url, fname in zip(req.urls, req.filenames):
        out_path = os.path.join(input_dir, f"{fname}.mp4")
        ok = download_youtube(url, out_path)
        results.append({"filename": f"{fname}.mp4", "success": ok})
    return {"results": results}


@router.get("/analyze/{project_id}")
def analyze_project_videos(project_id: str):
    validate_project_id(project_id)
    input_dir = os.path.join(PROJECTS_DIR, project_id, "input")
    if not os.path.isdir(input_dir):
        return {"videos": []}
    videos = []
    for f in sorted(os.listdir(input_dir)):
        if f.endswith((".mp4", ".mov", ".avi", ".mkv")):
            info = analyze_video(os.path.join(input_dir, f))
            if info:
                videos.append(info)
    return {"videos": videos}


class AutoClipRequest(BaseModel):
    project_id: str
    sentence_count: int


@router.post("/auto-clips")
def generate_auto_clips(req: AutoClipRequest):
    validate_project_id(req.project_id)
    input_dir = os.path.join(PROJECTS_DIR, req.project_id, "input")
    if not os.path.isdir(input_dir):
        return {"clips": []}
    videos = []
    for f in sorted(os.listdir(input_dir)):
        if f.endswith((".mp4", ".mov", ".avi", ".mkv")):
            info = analyze_video(os.path.join(input_dir, f))
            if info:
                videos.append(info)
    clips = auto_generate_clips(videos, req.sentence_count)
    return {"clips": clips}


class SmartClipRequest(BaseModel):
    project_id: str
    gemini_key: str = ""
    sentences: list[str]


@router.post("/smart-clips")
def generate_smart_clips(req: SmartClipRequest):
    """Gemini Vision으로 대본-영상 스마트 매칭"""
    validate_project_id(req.project_id)
    gemini_key = req.gemini_key or GEMINI_API_KEY
    input_dir = os.path.join(PROJECTS_DIR, req.project_id, "input")
    if not os.path.isdir(input_dir):
        return {"clips": [], "error": "입력 영상이 없습니다"}

    # 영상 분석
    videos = []
    for f in sorted(os.listdir(input_dir)):
        if f.endswith((".mp4", ".mov", ".avi", ".mkv")):
            info = analyze_video(os.path.join(input_dir, f))
            if info:
                videos.append(info)

    if not videos:
        return {"clips": [], "error": "분석 가능한 영상이 없습니다"}

    project_dir = os.path.join(PROJECTS_DIR, req.project_id)
    clips = smart_generate_clips(
        gemini_key=gemini_key,
        project_dir=project_dir,
        videos=videos,
        sentences=req.sentences,
    )

    if not clips:
        # 스마트 매칭 실패 시 기본 분배로 폴백
        clips = auto_generate_clips(videos, len(req.sentences))

    return {"clips": clips, "smart": len(clips) > 0}


class AISearchRequest(BaseModel):
    project_id: str
    queries: list[str]
    max_per_query: int = 1
    gemini_key: str = ""
    topic: str = ""
    category: str = ""


@router.post("/ai-search-download")
def ai_search_and_download(req: AISearchRequest):
    """AI가 생성한 검색어로 유튜브 검색 후 다운로드 (동기 방식 - 레거시)"""
    validate_project_id(req.project_id)
    input_dir = os.path.join(PROJECTS_DIR, req.project_id, "input")
    queries = req.queries[:MAX_QUERIES]
    downloaded = search_and_download(queries, input_dir, req.max_per_query)
    return {"downloaded": downloaded, "count": len(downloaded)}


@router.post("/ai-search-stream")
async def ai_search_stream(req: AISearchRequest):
    """AI 검색 + 다운로드를 SSE로 실시간 진행률 전송"""
    validate_project_id(req.project_id)
    gemini_key = req.gemini_key or GEMINI_API_KEY
    job_id = str(uuid.uuid4())[:8]
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _search_queues[job_id] = queue

    queries = req.queries[:MAX_QUERIES]
    input_dir = os.path.join(PROJECTS_DIR, req.project_id, "input")

    def progress_callback(**kwargs):
        """백그라운드 스레드에서 이벤트 루프로 이벤트 전달"""
        asyncio.run_coroutine_threadsafe(queue.put(kwargs), loop)

    def run_search():
        try:
            result = search_and_download(
                queries, input_dir, req.max_per_query,
                progress_callback=progress_callback,
            )

            # AI 영상 적합성 검증
            if gemini_key and result:
                verified = verify_videos(
                    gemini_key=gemini_key,
                    video_dir=input_dir,
                    topic=req.topic,
                    category=req.category,
                    downloaded=result,
                    min_score=4,
                    progress_callback=progress_callback,
                )
                asyncio.run_coroutine_threadsafe(
                    queue.put({
                        "step": "complete",
                        "downloaded": [d for d in verified],
                        "count": len(verified),
                        "original_count": len(result),
                        "rejected": len(result) - len(verified),
                    }),
                    loop,
                )
            else:
                asyncio.run_coroutine_threadsafe(
                    queue.put({"step": "complete", "downloaded": [d for d in result], "count": len(result)}),
                    loop,
                )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                queue.put({"step": "error", "message": str(e)}),
                loop,
            )

    thread = threading.Thread(target=run_search, daemon=True)
    thread.start()

    async def event_generator():
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=120)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("step") in ("complete", "error"):
                    break
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'step': 'error', 'message': '타임아웃 (2분 초과)'})}\n\n"
        finally:
            _search_queues.pop(job_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
