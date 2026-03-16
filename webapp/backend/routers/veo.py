"""Veo 3.1 AI 영상 생성 SSE 엔드포인트"""
import os
import json
import asyncio
import threading
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.config import PROJECTS_DIR
from services.veo_service import generate_all_videos, estimate_cost

router = APIRouter()


class VeoEstimateRequest(BaseModel):
    sentence_count: int
    duration: int = 8


class VeoGenerateRequest(BaseModel):
    project_id: str
    gemini_key: str
    sentences: list[str]
    category: str
    topic: str
    duration: int = 8


@router.post("/estimate")
async def veo_estimate(req: VeoEstimateRequest):
    """비용/시간 견적"""
    return estimate_cost(req.sentence_count, req.duration)


@router.post("/generate")
async def veo_generate(req: VeoGenerateRequest):
    """Veo 3.1 영상 생성 (SSE 스트림)"""
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    input_dir = os.path.join(PROJECTS_DIR, req.project_id, "input")
    os.makedirs(input_dir, exist_ok=True)

    def progress_callback(**kwargs):
        asyncio.run_coroutine_threadsafe(queue.put(kwargs), loop)

    def run_in_thread():
        try:
            result = generate_all_videos(
                gemini_key=req.gemini_key,
                sentences=req.sentences,
                category=req.category,
                topic=req.topic,
                output_dir=input_dir,
                progress_callback=progress_callback,
            )
            asyncio.run_coroutine_threadsafe(
                queue.put({
                    "step": "complete",
                    "videos": [r for r in result if r.get("success")],
                    "count": sum(1 for r in result if r.get("success")),
                    "total": len(result),
                }),
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
                event = await asyncio.wait_for(queue.get(), timeout=3600)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("step") in ("complete", "error"):
                    break
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'step': 'error', 'message': '타임아웃 (60분 초과)'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
