"""Nano Banana 2 AI 이미지 생성 SSE 엔드포인트"""
import os
import json
import asyncio
import threading
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.config import PROJECTS_DIR, validate_project_id, GEMINI_API_KEY
from services.imagen_service import (
    generate_all_images, estimate_time,
    get_image_previews, regenerate_single,
)

router = APIRouter()


class ImagenEstimateRequest(BaseModel):
    sentence_count: int


class ImagenGenerateRequest(BaseModel):
    project_id: str
    gemini_key: str
    sentences: list[str]
    category: str
    topic: str


class ImagenRegenerateRequest(BaseModel):
    project_id: str
    gemini_key: str
    index: int
    prompt: str
    effect: str = ""


@router.post("/estimate")
async def imagen_estimate(req: ImagenEstimateRequest):
    """소요시간 견적"""
    return estimate_time(req.sentence_count)


@router.get("/preview/{project_id}")
async def imagen_preview(project_id: str):
    """생성된 이미지 미리보기 목록"""
    validate_project_id(project_id)
    input_dir = os.path.join(PROJECTS_DIR, project_id, "input")
    previews = get_image_previews(input_dir)

    # 저장된 프롬프트 로드
    prompts_path = os.path.join(input_dir, "imagen_prompts.json")
    prompts = []
    sentences = []
    if os.path.exists(prompts_path):
        with open(prompts_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            prompts = data.get("prompts", [])
            sentences = data.get("sentences", [])

    # 프롬프트와 문장 정보 추가
    for p in previews:
        idx = p["index"]
        p["prompt"] = prompts[idx] if idx < len(prompts) else ""
        p["sentence"] = sentences[idx] if idx < len(sentences) else ""

    return {"previews": previews, "prompts": prompts, "sentences": sentences}


@router.post("/regenerate")
async def imagen_regenerate(req: ImagenRegenerateRequest):
    """단일 이미지 재생성"""
    validate_project_id(req.project_id)
    gemini_key = req.gemini_key or GEMINI_API_KEY
    input_dir = os.path.join(PROJECTS_DIR, req.project_id, "input")

    result = await asyncio.to_thread(
        regenerate_single,
        gemini_key=gemini_key,
        index=req.index,
        prompt=req.prompt,
        output_dir=input_dir,
        effect_type=req.effect or None,
    )

    return result


@router.post("/generate")
async def imagen_generate(req: ImagenGenerateRequest):
    """Nano Banana 2 이미지 생성 + Ken Burns (SSE 스트림)"""
    validate_project_id(req.project_id)
    gemini_key = req.gemini_key or GEMINI_API_KEY
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    input_dir = os.path.join(PROJECTS_DIR, req.project_id, "input")
    os.makedirs(input_dir, exist_ok=True)

    def progress_callback(**kwargs):
        asyncio.run_coroutine_threadsafe(queue.put(kwargs), loop)

    def run_in_thread():
        try:
            result = generate_all_images(
                gemini_key=gemini_key,
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
                event = await asyncio.wait_for(queue.get(), timeout=600)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("step") in ("complete", "error"):
                    break
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'step': 'error', 'message': '타임아웃 (10분 초과)'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
