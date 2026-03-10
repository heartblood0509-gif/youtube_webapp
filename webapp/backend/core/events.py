import asyncio
import json


class EventManager:
    """SSE 이벤트 매니저 - 빌드 진행률을 실시간 전송"""

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def create_job(self, job_id: str):
        self._queues[job_id] = asyncio.Queue()

    def get_queue(self, job_id: str) -> asyncio.Queue | None:
        return self._queues.get(job_id)

    async def emit(self, job_id: str, event: dict):
        q = self._queues.get(job_id)
        if q:
            await q.put(event)

    def cleanup(self, job_id: str):
        self._queues.pop(job_id, None)


event_manager = EventManager()
