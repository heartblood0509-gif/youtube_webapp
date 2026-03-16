"""Veo 3.1 AI 영상 생성 서비스"""
import os
import time
import json
import logging
import traceback
import requests as http_requests
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

VEO_MODEL = "veo-3.1-generate-preview"
VEO_ASPECT_RATIO = "9:16"
VEO_DURATION = 8
VEO_POLL_INTERVAL = 15
VEO_MAX_WAIT = 420  # 7분
COST_PER_SECOND = 0.40  # standard 720p
MAX_RETRIES = 3
RETRY_BASE_DELAY = 60  # 429 에러 시 기본 대기 60초
CLIP_DELAY = 5  # 클립 사이 대기 (초)


def estimate_cost(sentence_count: int, duration: int = VEO_DURATION) -> dict:
    total_seconds = sentence_count * duration
    total_cost = total_seconds * COST_PER_SECOND
    return {
        "sentence_count": sentence_count,
        "duration_per_clip": duration,
        "total_seconds": total_seconds,
        "estimated_cost_usd": round(total_cost, 2),
        "estimated_time_minutes": round(sentence_count * 2, 1),
    }


def generate_video_prompts(
    gemini_key: str,
    sentences: list[str],
    category: str,
    topic: str,
) -> list[str]:
    """Gemini로 한국어 문장 → 영어 시네마틱 영상 프롬프트 변환"""
    prompt = f"""You are an expert AI video prompt engineer for Google Veo 3.
Convert each Korean narration sentence into a cinematic English video generation prompt.

Category: {category}
Topic: {topic}

Sentences:
{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(sentences))}

Rules:
- Each prompt must describe a specific, visually compelling scene matching the sentence meaning
- Include camera movement (slow pan, aerial shot, tracking shot, dolly zoom)
- Include lighting/mood (golden hour, moody, cinematic, bright, warm)
- Include style keywords (cinematic, 4K, shallow depth of field)
- Keep each prompt 1-2 sentences, under 80 words
- Aspect ratio is 9:16 vertical (phone/shorts format)
- Duration is 8 seconds per clip

SAFETY - CRITICAL RULES (violating these will cause generation to fail):
- NEVER describe human faces, people, body parts, or human figures
- NEVER describe emotions, expressions, or gestures of people
- NEVER use words like "woman", "man", "person", "face", "hand", "close-up on a person"
- Instead, show OBJECTS, PRODUCTS, ENVIRONMENTS, NATURE, TEXTURES, ABSTRACT VISUALS
- For human-related sentences, translate to symbolic/metaphorical visuals:
  e.g. "피부가 좋아졌다" → "A pristine glass bottle of serum on marble, golden light"
  e.g. "스트레스를 받았다" → "Crumpled papers scattered on a dark desk, moody lighting"
  e.g. "여행을 떠났다" → "Aerial drone shot of turquoise ocean coastline, golden hour"
- Do NOT include text, words, subtitles, or UI elements in the scene
- Focus on concrete, filmable visuals - no abstract concepts

Return ONLY a valid JSON array of strings (no markdown, no explanation):
["prompt 1", "prompt 2", ...]"""

    resp = http_requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]

    # JSON 파싱
    json_match = text
    if "```" in text:
        import re
        m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
        if m:
            json_match = m.group(1)
    # 배열 추출
    start = json_match.find("[")
    end = json_match.rfind("]")
    if start >= 0 and end > start:
        json_match = json_match[start:end + 1]

    prompts = json.loads(json_match)
    if not isinstance(prompts, list) or len(prompts) == 0:
        raise ValueError("프롬프트 생성 실패: 빈 결과")

    # 문장 수에 맞춤
    while len(prompts) < len(sentences):
        prompts.append(prompts[-1])
    prompts = prompts[:len(sentences)]

    return prompts


def generate_single_video(
    api_key: str,
    prompt: str,
    output_path: str,
    duration: int = VEO_DURATION,
    progress_callback=None,
) -> dict:
    """Veo 3.1로 단일 영상 생성 (429 자동 재시도 포함)"""
    client = genai.Client(api_key=api_key)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Veo 3.1 생성 요청 (시도 {attempt}/{MAX_RETRIES}): {prompt[:80]}...")

            operation = client.models.generate_videos(
                model=VEO_MODEL,
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio=VEO_ASPECT_RATIO,
                    duration_seconds=duration,
                    number_of_videos=1,
                ),
            )

            logger.info(f"Veo 3.1 operation 시작: {operation.name}")

            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > VEO_MAX_WAIT:
                    raise TimeoutError(f"Veo 3.1 생성 타임아웃 ({int(elapsed)}초)")
                time.sleep(VEO_POLL_INTERVAL)
                operation = client.operations.get(operation)
                logger.info(f"  폴링 중... done={operation.done}, elapsed={int(elapsed)}초")

            # 에러 체크
            if operation.error:
                raise RuntimeError(f"Veo 3.1 API 에러: {operation.error}")

            if not operation.response or not operation.response.generated_videos:
                rai_count = getattr(operation.response, 'rai_media_filtered_count', None)
                rai_reasons = getattr(operation.response, 'rai_media_filtered_reasons', None)
                if rai_count:
                    raise RuntimeError(f"Veo 3.1 안전 필터에 의해 차단됨 (사유: {rai_reasons})")
                raise RuntimeError("Veo 3.1 영상 생성 실패: 빈 응답")

            generated_video = operation.response.generated_videos[0]
            client.files.download(file=generated_video.video)
            generated_video.video.save(output_path)

            elapsed = round(time.time() - start_time, 1)
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"Veo 3.1 영상 생성 완료: {output_path} ({elapsed}초, {file_size:.1f}MB)")
            return {"path": output_path, "elapsed": elapsed}

        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
            if is_rate_limit and attempt < MAX_RETRIES:
                wait = RETRY_BASE_DELAY * attempt
                logger.warning(f"429 할당량 초과 — {wait}초 대기 후 재시도 ({attempt}/{MAX_RETRIES})")
                if progress_callback:
                    progress_callback(
                        step="generating",
                        message=f"할당량 초과 — {wait}초 대기 후 재시도 ({attempt}/{MAX_RETRIES})...",
                    )
                time.sleep(wait)
                continue
            raise


def generate_all_videos(
    gemini_key: str,
    sentences: list[str],
    category: str,
    topic: str,
    output_dir: str,
    progress_callback=None,
) -> list[dict]:
    """모든 문장에 대해 Veo 3.1 영상 순차 생성"""
    os.makedirs(output_dir, exist_ok=True)

    # 1단계: 프롬프트 생성
    if progress_callback:
        progress_callback(step="prompts", message="Gemini가 영상 프롬프트를 생성하고 있습니다...")

    prompts = generate_video_prompts(gemini_key, sentences, category, topic)

    if progress_callback:
        progress_callback(step="prompts_done", prompts=prompts, count=len(prompts))

    # 2단계: 영상 순차 생성
    results = []
    total = len(prompts)
    consecutive_errors = 0

    for i, prompt in enumerate(prompts):
        fname = f"veo_{i + 1:02d}.mp4"
        out_path = os.path.join(output_dir, fname)

        if progress_callback:
            progress_callback(
                step="generating",
                current=i + 1,
                total=total,
                prompt=prompt[:100],
                sentence=sentences[i] if i < len(sentences) else "",
                message=f"[{i + 1}/{total}] AI 영상 생성 중... (1~6분 소요)",
            )

        try:
            result = generate_single_video(
                gemini_key, prompt, out_path,
                progress_callback=progress_callback,
            )
            results.append({**result, "filename": fname, "index": i, "success": True})
            consecutive_errors = 0

            if progress_callback:
                progress_callback(
                    step="generated",
                    current=i + 1,
                    total=total,
                    filename=fname,
                    elapsed=result["elapsed"],
                    message=f"[{i + 1}/{total}] 완료! ({result['elapsed']}초)",
                )

            # 클립 사이 대기 (할당량 보호)
            if i < total - 1:
                time.sleep(CLIP_DELAY)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Veo 3.1 클립 {i + 1} 생성 실패: {error_msg}\n{traceback.format_exc()}")
            results.append({"filename": fname, "index": i, "success": False, "error": error_msg})
            consecutive_errors += 1

            if progress_callback:
                progress_callback(
                    step="clip_error",
                    current=i + 1,
                    total=total,
                    message=f"[{i + 1}/{total}] 실패: {error_msg[:200]}",
                )

            # 연속 3회 실패 시 조기 중단
            if consecutive_errors >= 3:
                logger.error(f"연속 {consecutive_errors}회 실패 — 중단합니다.")
                if progress_callback:
                    progress_callback(
                        step="clip_error",
                        current=i + 1,
                        total=total,
                        message=f"연속 {consecutive_errors}회 실패로 중단. 마지막 에러: {error_msg[:200]}",
                    )
                break

    success_count = sum(1 for r in results if r.get("success"))
    if progress_callback:
        progress_callback(
            step="done",
            count=success_count,
            total=total,
            message=f"완료! {success_count}/{total}개 영상 생성됨",
        )

    return results
