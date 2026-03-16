import os
import subprocess
import asyncio
import logging
import time
import requests
from core.config import TYPECAST_API_KEY, TYPECAST_VOICE_ID, TYPECAST_MODEL

logger = logging.getLogger(__name__)


def _run_sync(cmd):
    """동기 subprocess 실행 (스레드 풀에서 호출)"""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


async def generate_edge_tts(sentences: list[str], output_dir: str, language: str = "ko") -> list[dict]:
    """Edge TTS로 문장별 WAV 생성, 듀레이션 반환"""
    try:
        import edge_tts
    except ImportError:
        await asyncio.to_thread(
            subprocess.run, "pip3 install edge-tts", shell=True, capture_output=True
        )
        import edge_tts

    voices = {
        "ko": "ko-KR-InJoonNeural",
        "ko_f": "ko-KR-SunHiNeural",
        "en": "en-US-GuyNeural",
    }
    voice = voices.get(language, voices["ko"])
    results = []

    for i, sent in enumerate(sentences):
        out_path = os.path.join(output_dir, f"sent_{i:02d}.wav")
        mp3_path = os.path.join(output_dir, f"sent_{i:02d}.mp3")

        logger.info(f"[TTS {i+1}/{len(sentences)}] 생성 중: {sent[:30]}...")

        try:
            communicate = edge_tts.Communicate(sent, voice, rate="+10%")
            await communicate.save(mp3_path)
        except Exception as e:
            logger.error(f"[TTS {i+1}] edge_tts 실패: {e}")
            raise RuntimeError(f"TTS mp3 생성 실패 (문장 {i+1}): {e}")

        if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
            raise RuntimeError(f"TTS mp3 파일이 생성되지 않았습니다: sent_{i:02d}.mp3")

        # mp3 → wav 변환 (비동기)
        conv = await asyncio.to_thread(
            _run_sync,
            f'ffmpeg -hide_banner -y -i "{mp3_path}" "{out_path}"',
        )
        if conv.returncode != 0:
            logger.error(f"[TTS {i+1}] mp3→wav 변환 실패: {conv.stderr[-200:]}")
            raise RuntimeError(f"TTS wav 변환 실패 (문장 {i+1}): {conv.stderr[-200:]}")

        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise RuntimeError(f"TTS wav 파일이 생성되지 않았습니다: sent_{i:02d}.wav")

        # 듀레이션 측정 (비동기)
        r = await asyncio.to_thread(
            _run_sync,
            f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{out_path}"',
        )
        dur = float(r.stdout.strip()) if r.stdout.strip() else 2.0
        logger.info(f"[TTS {i+1}] 완료: {dur}s")
        results.append({"text": sent, "duration": round(dur, 2), "path": out_path})

    return results


async def generate_typecast_tts(sentences: list[str], output_dir: str, speed: float = 1.1) -> list[dict]:
    """Typecast TTS로 문장별 WAV 생성 (비동기)"""
    headers = {"X-API-KEY": TYPECAST_API_KEY, "Content-Type": "application/json"}
    base_url = "https://api.typecast.ai"
    results = []

    for i, sent in enumerate(sentences):
        payload = {
            "text": sent,
            "voice_id": TYPECAST_VOICE_ID,
            "model": TYPECAST_MODEL,
            "lang": "ko-kr",
            "emotion_tone_preset": "normal",
            "speed_x": speed,
        }
        resp = await asyncio.to_thread(
            requests.post, f"{base_url}/v1/text-to-speech", headers=headers, json=payload
        )
        out_path = os.path.join(output_dir, f"sent_{i:02d}.wav")

        content_type = resp.headers.get("Content-Type", "")
        if "audio" in content_type or "octet-stream" in content_type:
            with open(out_path, "wb") as f:
                f.write(resp.content)
        else:
            result = resp.json()
            speak_url = result.get("result", {}).get("speak_v2_url")
            if speak_url:
                for _ in range(30):
                    await asyncio.sleep(2)
                    poll = await asyncio.to_thread(
                        requests.get, speak_url, headers=headers
                    )
                    if poll.status_code == 200:
                        data = poll.json()
                        if data.get("result", {}).get("status") == "done":
                            audio_url = data["result"].get("audio_download_url") or data["result"].get("audio_url")
                            audio_resp = await asyncio.to_thread(requests.get, audio_url)
                            with open(out_path, "wb") as f:
                                f.write(audio_resp.content)
                            break

        # 듀레이션 측정 (비동기)
        r = await asyncio.to_thread(
            _run_sync,
            f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{out_path}"',
        )
        dur = float(r.stdout.strip()) if r.stdout.strip() else 2.0
        results.append({"text": sent, "duration": round(dur, 2), "path": out_path})
        await asyncio.sleep(0.3)

    return results
