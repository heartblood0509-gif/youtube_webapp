"""Nano Banana 2 AI 이미지 생성 + Ken Burns 효과 서비스"""
import os
import time
import json
import subprocess
import logging
import traceback
import requests as http_requests
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

IMAGEN_MODEL = "gemini-2.5-flash-image"
IMAGEN_ASPECT_RATIO = "9:16"
IMAGEN_SIZE = "1K"
DEFAULT_CLIP_DURATION = 5  # 기본 클립 길이 (초) — 빌드 시 TTS 길이에 맞춰 재조정됨
FPS = 30
OUTPUT_W = 1080
OUTPUT_H = 1920
MAX_RETRIES = 5
DELAY_BETWEEN_REQUESTS = 10  # 요청 간 대기 (초) — RPM 제한 회피

# Ken Burns 효과 종류
EFFECTS = ["zoom_in", "zoom_out", "pan_left_to_right", "pan_right_to_left"]


def estimate_time(sentence_count: int) -> dict:
    """예상 소요시간 (이미지 생성은 무료)"""
    return {
        "sentence_count": sentence_count,
        "estimated_time_seconds": sentence_count * 15,  # 이미지당 ~10초 + Ken Burns ~5초
        "estimated_cost_usd": 0,
        "note": "Nano Banana 2 이미지 생성은 무료입니다.",
    }


def generate_image_prompts(
    gemini_key: str,
    sentences: list[str],
    category: str,
    topic: str,
) -> list[str]:
    """Gemini로 한국어 문장 → 영어 이미지 프롬프트 변환"""
    prompt = f"""You are an expert AI image prompt engineer for Google's Nano Banana 2 image generation model.
Convert each Korean narration sentence into a high-quality English image generation prompt.

Category: {category}
Topic: {topic}

Sentences:
{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(sentences))}

Rules:
- Each prompt must describe a specific, visually stunning scene matching the sentence meaning
- Include composition details (close-up, wide shot, overhead, low angle)
- Include lighting/mood (golden hour, studio lighting, moody, bright, warm, cinematic)
- Include style keywords (photorealistic, 4K, high detail, professional photography)
- Keep each prompt 1-2 sentences, under 60 words
- The image will be 9:16 vertical format (phone/shorts)

SAFETY - CRITICAL RULES:
- NEVER describe human faces, people, body parts, or human figures
- NEVER describe emotions, expressions, or gestures of people
- NEVER use words like "woman", "man", "person", "face", "hand"
- Instead, show OBJECTS, PRODUCTS, ENVIRONMENTS, NATURE, TEXTURES
- For human-related sentences, translate to symbolic/metaphorical visuals:
  e.g. "피부가 좋아졌다" → "A pristine glass bottle of serum on white marble, soft golden light, photorealistic"
  e.g. "여행을 떠났다" → "Aerial view of turquoise ocean meeting white sand beach, golden hour, stunning"
- Do NOT include text, words, or UI elements in the scene

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
    start = json_match.find("[")
    end = json_match.rfind("]")
    if start >= 0 and end > start:
        json_match = json_match[start:end + 1]

    prompts = json.loads(json_match)
    if not isinstance(prompts, list) or len(prompts) == 0:
        raise ValueError("이미지 프롬프트 생성 실패: 빈 결과")

    # 문장 수에 맞춤
    while len(prompts) < len(sentences):
        prompts.append(prompts[-1])
    prompts = prompts[:len(sentences)]

    return prompts


def generate_single_image(
    gemini_key: str,
    prompt: str,
    output_path: str,
    aspect_ratio: str = IMAGEN_ASPECT_RATIO,
    image_size: str = IMAGEN_SIZE,
) -> dict:
    """Nano Banana 2로 단일 이미지 생성"""
    client = genai.Client(api_key=gemini_key)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Nano Banana 2 이미지 생성 (시도 {attempt}/{MAX_RETRIES}): {prompt[:80]}...")

            response = client.models.generate_content(
                model=IMAGEN_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                        image_size=image_size,
                    ),
                ),
            )

            # 이미지 추출 및 저장
            for part in response.parts:
                if part.inline_data is not None:
                    image = part.as_image()
                    image.save(output_path)
                    file_size = os.path.getsize(output_path) / 1024  # KB
                    logger.info(f"이미지 저장 완료: {output_path} ({file_size:.1f}KB)")
                    return {"path": output_path, "size_kb": round(file_size, 1)}

            raise RuntimeError("이미지 생성 응답에 이미지가 없습니다")

        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
            if is_rate_limit and attempt < MAX_RETRIES:
                wait = 60 * attempt  # 60초, 120초, 180초, 240초 점진 대기
                logger.warning(f"429 할당량 초과 — {wait}초 대기 후 재시도 ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            raise


def apply_ken_burns(
    image_path: str,
    output_video_path: str,
    duration: float = DEFAULT_CLIP_DURATION,
    effect_type: str = "zoom_in",
) -> dict:
    """FFmpeg zoompan으로 정적 이미지 → 동적 영상 클립 변환

    입력 이미지를 3배 업스케일 후 zoompan 적용 → 떨림 없는 부드러운 효과.
    원본 이미지(~1024px)가 출력(1080px)보다 작으면 zoompan이 범위를 벗어나
    떨림/지터가 발생하므로, 충분한 해상도를 확보한 뒤 처리한다.
    """
    total_frames = int(duration * FPS)

    # 3배 업스케일 해상도 (zoompan이 고해상도에서 작업 → 떨림 방지)
    UP_W = OUTPUT_W * 3  # 3240
    UP_H = OUTPUT_H * 3  # 5760

    if effect_type == "zoom_in":
        zp = (
            f"zoompan=z='1.0+0.5*on/{total_frames}'"
            f":x='(iw-{OUTPUT_W}/zoom)/2':y='(ih-{OUTPUT_H}/zoom)/2'"
            f":d={total_frames}:s={OUTPUT_W}x{OUTPUT_H}:fps={FPS}"
        )
    elif effect_type == "zoom_out":
        zp = (
            f"zoompan=z='1.5-0.5*on/{total_frames}'"
            f":x='(iw-{OUTPUT_W}/zoom)/2':y='(ih-{OUTPUT_H}/zoom)/2'"
            f":d={total_frames}:s={OUTPUT_W}x{OUTPUT_H}:fps={FPS}"
        )
    elif effect_type == "pan_left_to_right":
        zp = (
            f"zoompan=z='1.5'"
            f":x='(iw-{OUTPUT_W}/zoom)*on/{total_frames}':y='(ih-{OUTPUT_H}/zoom)/2'"
            f":d={total_frames}:s={OUTPUT_W}x{OUTPUT_H}:fps={FPS}"
        )
    elif effect_type == "pan_right_to_left":
        zp = (
            f"zoompan=z='1.5'"
            f":x='(iw-{OUTPUT_W}/zoom)*(1-on/{total_frames})':y='(ih-{OUTPUT_H}/zoom)/2'"
            f":d={total_frames}:s={OUTPUT_W}x{OUTPUT_H}:fps={FPS}"
        )
    else:
        raise ValueError(f"알 수 없는 효과: {effect_type}")

    vf = f"scale={UP_W}:{UP_H}:flags=lanczos,{zp}"

    cmd = [
        "ffmpeg", "-hide_banner", "-y", "-loop", "1",
        "-i", image_path,
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-an",
        output_video_path,
    ]

    logger.info(f"Ken Burns 효과 적용 중: {effect_type} → {output_video_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err = result.stderr.strip()
        last_lines = "\n".join(err.split("\n")[-5:])
        raise RuntimeError(f"Ken Burns 변환 실패: {last_lines[-500:]}")

    file_size = os.path.getsize(output_video_path) / (1024 * 1024)
    logger.info(f"Ken Burns 완료: {output_video_path} ({file_size:.1f}MB)")
    return {"path": output_video_path, "size_mb": round(file_size, 1), "effect": effect_type}


def regenerate_single(
    gemini_key: str,
    index: int,
    prompt: str,
    output_dir: str,
    effect_type: str | None = None,
) -> dict:
    """단일 이미지 재생성 + Ken Burns 효과 적용"""
    img_fname = f"imagen_{index + 1:02d}.png"
    vid_fname = f"imagen_{index + 1:02d}.mp4"
    img_path = os.path.join(output_dir, img_fname)
    vid_path = os.path.join(output_dir, vid_fname)
    effect = effect_type or EFFECTS[index % len(EFFECTS)]

    # 이미지 재생성
    generate_single_image(gemini_key, prompt, img_path)

    # Ken Burns 효과 재적용
    apply_ken_burns(img_path, vid_path, duration=DEFAULT_CLIP_DURATION, effect_type=effect)

    return {
        "filename": vid_fname,
        "image": img_fname,
        "index": index,
        "success": True,
        "effect": effect,
    }


def get_image_previews(input_dir: str) -> list[dict]:
    """생성된 이미지 미리보기 목록 반환"""
    previews = []
    if not os.path.isdir(input_dir):
        return previews

    for fname in sorted(os.listdir(input_dir)):
        if fname.startswith("imagen_") and fname.endswith(".png"):
            idx_str = fname.replace("imagen_", "").replace(".png", "")
            try:
                idx = int(idx_str) - 1  # 0-based index
            except ValueError:
                continue
            vid_fname = fname.replace(".png", ".mp4")
            vid_exists = os.path.exists(os.path.join(input_dir, vid_fname))
            previews.append({
                "index": idx,
                "image": fname,
                "video": vid_fname if vid_exists else None,
                "image_url": f"input/{fname}",
                "video_url": f"input/{vid_fname}" if vid_exists else None,
            })

    return previews


def generate_all_images(
    gemini_key: str,
    sentences: list[str],
    category: str,
    topic: str,
    output_dir: str,
    progress_callback=None,
) -> list[dict]:
    """모든 문장에 대해 이미지 순차 생성 + Ken Burns 효과 적용

    429 에러 방지를 위해 요청 간 DELAY_BETWEEN_REQUESTS초 대기.
    429 발생 시 최대 MAX_RETRIES회 재시도 (대기시간 점진 증가).
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1단계: 프롬프트 생성
    if progress_callback:
        progress_callback(step="prompts", message="Gemini가 이미지 프롬프트를 생성하고 있습니다...")

    prompts = generate_image_prompts(gemini_key, sentences, category, topic)

    if progress_callback:
        progress_callback(step="prompts_done", prompts=prompts, count=len(prompts))

    # 프롬프트를 파일에 저장 (재생성 시 사용)
    prompts_path = os.path.join(output_dir, "imagen_prompts.json")
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump({"prompts": prompts, "sentences": sentences}, f, ensure_ascii=False, indent=2)

    # 2단계: 이미지 순차 생성 + Ken Burns
    total = len(prompts)
    results = []

    for i, prompt in enumerate(prompts):
        img_fname = f"imagen_{i + 1:02d}.png"
        vid_fname = f"imagen_{i + 1:02d}.mp4"
        img_path = os.path.join(output_dir, img_fname)
        vid_path = os.path.join(output_dir, vid_fname)
        effect = EFFECTS[i % len(EFFECTS)]
        sentence = sentences[i] if i < len(sentences) else ""

        # 첫 번째 이미지 이후 딜레이
        if i > 0:
            logger.info(f"RPM 제한 회피: {DELAY_BETWEEN_REQUESTS}초 대기...")
            if progress_callback:
                progress_callback(
                    step="generating",
                    current=i + 1,
                    total=total,
                    message=f"[{i + 1}/{total}] {DELAY_BETWEEN_REQUESTS}초 대기 후 생성 시작...",
                )
            time.sleep(DELAY_BETWEEN_REQUESTS)

        try:
            if progress_callback:
                progress_callback(
                    step="generating",
                    current=i + 1,
                    total=total,
                    prompt=prompt[:100],
                    sentence=sentence,
                    message=f"[{i + 1}/{total}] 이미지 생성 중...",
                )

            # 이미지 생성
            generate_single_image(gemini_key, prompt, img_path)

            # Ken Burns 효과 적용
            if progress_callback:
                progress_callback(
                    step="generating",
                    current=i + 1,
                    total=total,
                    message=f"[{i + 1}/{total}] Ken Burns 효과 적용 중 ({effect})...",
                )

            apply_ken_burns(img_path, vid_path, duration=DEFAULT_CLIP_DURATION, effect_type=effect)

            if progress_callback:
                progress_callback(
                    step="generated",
                    current=i + 1,
                    total=total,
                    filename=vid_fname,
                    message=f"[{i + 1}/{total}] 완료! ({effect})",
                )

            results.append({
                "filename": vid_fname,
                "image": img_fname,
                "index": i,
                "success": True,
                "effect": effect,
            })

        except Exception as e:
            error_msg = str(e)
            logger.error(f"이미지 클립 {i + 1} 생성 실패: {error_msg}\n{traceback.format_exc()}")

            if progress_callback:
                progress_callback(
                    step="clip_error",
                    current=i + 1,
                    total=total,
                    message=f"[{i + 1}/{total}] 실패: {error_msg[:200]}",
                )

            results.append({"filename": vid_fname, "index": i, "success": False, "error": error_msg})

    success_count = sum(1 for r in results if r.get("success"))
    if progress_callback:
        progress_callback(
            step="done",
            count=success_count,
            total=total,
            message=f"완료! {success_count}/{total}개 이미지 클립 생성됨",
        )

    return results
