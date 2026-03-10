import os
import json
import uuid
import asyncio
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.config import PROJECTS_DIR, BGM_VOLUME_DEFAULT
from core.events import event_manager
from services.build_pipeline import run_build
from services.tts_service import generate_edge_tts, generate_typecast_tts

router = APIRouter()


class BuildRequest(BaseModel):
    project_id: str
    title_text: str
    narration_sentences: list[str]
    tts_engine: str = "edge"
    tts_speed: float = 1.0
    tts_language: str = "ko"
    bgm_volume: float = BGM_VOLUME_DEFAULT
    clips: list[dict]


async def _build_task(job_id: str, req: BuildRequest):
    """백그라운드 빌드 태스크"""
    project_dir = os.path.join(PROJECTS_DIR, req.project_id)
    temp_dir = os.path.join(project_dir, "temp_frames")
    os.makedirs(temp_dir, exist_ok=True)

    async def emit(event):
        await event_manager.emit(job_id, event)

    try:
        # 즉시 초기 이벤트 발송
        await emit({
            "type": "progress", "step": "준비",
            "step_number": 0, "total_steps": 5,
            "progress_percent": 1,
            "message": "빌드 준비 중...",
        })

        # 클립 소스 파일 존재 확인
        for clip in req.clips:
            src = os.path.join(project_dir, clip["source"])
            if not os.path.exists(src):
                # 존재하는 파일 목록 로깅
                input_dir = os.path.join(project_dir, "input")
                files = os.listdir(input_dir) if os.path.isdir(input_dir) else []
                raise FileNotFoundError(
                    f"소스 영상이 없습니다: {clip['source']} "
                    f"(input/ 내 파일: {files})"
                )

        # TTS 생성
        await emit({
            "type": "progress", "step": "TTS 생성",
            "step_number": 1, "total_steps": 5,
            "progress_percent": 5,
            "message": f"{req.tts_engine.upper()} TTS 생성 중... ({len(req.narration_sentences)}개 문장)",
        })

        if req.tts_engine == "typecast":
            tts_results = await generate_typecast_tts(
                req.narration_sentences, temp_dir, speed=req.tts_speed
            )
        else:
            tts_results = await generate_edge_tts(
                req.narration_sentences, temp_dir, language=req.tts_language
            )

        if not tts_results:
            raise RuntimeError("TTS 생성 결과가 비어 있습니다.")

        await emit({
            "type": "progress", "step": "TTS 완료",
            "step_number": 1, "total_steps": 5,
            "progress_percent": 8,
            "message": f"TTS 완료! {len(tts_results)}개 음성 파일 생성됨",
        })

        # 빌드 실행
        result = await run_build(
            project_dir=project_dir,
            title_text=req.title_text,
            sentences=req.narration_sentences,
            clips_config=req.clips,
            tts_results=tts_results,
            bgm_volume=req.bgm_volume,
            emit=emit,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        await emit({
            "type": "error",
            "step": "오류",
            "step_number": -1, "total_steps": 5,
            "progress_percent": 0,
            "message": f"빌드 실패: {str(e)}",
        })


@router.post("/start")
async def start_build(req: BuildRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    event_manager.create_job(job_id)
    background_tasks.add_task(_build_task, job_id, req)
    return {"job_id": job_id}


@router.get("/progress/{job_id}")
async def build_progress(job_id: str):
    async def event_generator():
        queue = event_manager.get_queue(job_id)
        if not queue:
            yield f"data: {json.dumps({'type': 'error', 'message': '작업을 찾을 수 없습니다'})}\n\n"
            return
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("done", "error"):
                    event_manager.cleanup(job_id)
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/result/{project_id}")
def get_build_result(project_id: str):
    output_dir = os.path.join(PROJECTS_DIR, project_id, "output")
    if not os.path.isdir(output_dir):
        return {"error": "출력 폴더가 없습니다"}
    for f in os.listdir(output_dir):
        if f.endswith(".mp4"):
            path = os.path.join(output_dir, f)
            return {
                "filename": f,
                "url": f"/files/{project_id}/output/{f}",
                "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1),
            }
    return {"error": "완성 영상이 없습니다"}
