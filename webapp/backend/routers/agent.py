"""Claude Agent SSE 엔드포인트 - Claude Code처럼 AI가 자율적으로 영상 검색/평가/선택"""
import os
import json
import asyncio
import threading
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.config import PROJECTS_DIR, validate_project_id
from services.claude_agent import run_agent

router = APIRouter()


class AgentSearchRequest(BaseModel):
    project_id: str
    claude_key: str
    topic: str
    category: str
    sentences: list[str]


@router.post("/search-videos")
async def agent_search_videos(req: AgentSearchRequest):
    """Claude 에이전트가 자율적으로 영상 검색/다운로드/평가 (SSE 스트림)"""
    validate_project_id(req.project_id)
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    input_dir = os.path.join(PROJECTS_DIR, req.project_id, "input")
    os.makedirs(input_dir, exist_ok=True)

    def progress_callback(**kwargs):
        """백그라운드 스레드에서 이벤트 루프로 이벤트 전달"""
        asyncio.run_coroutine_threadsafe(queue.put(kwargs), loop)

    def run_in_thread():
        try:
            result = run_agent(
                api_key=req.claude_key,
                topic=req.topic,
                category=req.category,
                sentences=req.sentences,
                output_dir=input_dir,
                progress_callback=progress_callback,
            )
            asyncio.run_coroutine_threadsafe(
                queue.put({
                    "step": "complete",
                    "count": result.get("count", 0),
                    "videos": result.get("videos", []),
                    "turns_used": result.get("turns_used", 0),
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
                event = await asyncio.wait_for(queue.get(), timeout=300)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("step") in ("complete", "error"):
                    break
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'step': 'error', 'message': '타임아웃 (5분 초과)'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
