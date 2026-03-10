"""Pexels 스톡 영상 검색 SSE 엔드포인트"""
import os
import json
import asyncio
import threading
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.config import PROJECTS_DIR
from services.pexels_service import search_and_download_pexels

router = APIRouter()


class PexelsSearchRequest(BaseModel):
    project_id: str
    pexels_key: str
    keywords: list[str]
    max_per_keyword: int = 1


@router.post("/search-videos")
async def pexels_search_videos(req: PexelsSearchRequest):
    """Pexels 스톡 영상 검색 + 다운로드 (SSE 스트림)"""
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    input_dir = os.path.join(PROJECTS_DIR, req.project_id, "input")
    os.makedirs(input_dir, exist_ok=True)

    def progress_callback(**kwargs):
        asyncio.run_coroutine_threadsafe(queue.put(kwargs), loop)

    def run_in_thread():
        try:
            result = search_and_download_pexels(
                api_key=req.pexels_key,
                keywords=req.keywords,
                output_dir=input_dir,
                max_per_keyword=req.max_per_keyword,
                progress_callback=progress_callback,
            )
            asyncio.run_coroutine_threadsafe(
                queue.put({
                    "step": "complete",
                    "downloaded": [d for d in result],
                    "count": len(result),
                }),
                loop,
            )
        except ValueError as e:
            asyncio.run_coroutine_threadsafe(
                queue.put({"step": "error", "message": str(e)}),
                loop,
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                queue.put({"step": "error", "message": str(e)}),
                loop,
            )

    thread = threading.Thread(target=run_in_thread, daemon=True)
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

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
