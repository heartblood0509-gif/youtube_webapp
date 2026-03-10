"""
AI 영상 적합성 검증 - Gemini Vision API로 다운로드된 영상이 주제에 맞는지 확인
"""
import subprocess
import os
import base64
import json
import logging
import requests

logger = logging.getLogger(__name__)


def extract_frame(video_path: str, output_path: str, timestamp: float = 2.0) -> bool:
    """영상에서 대표 프레임 추출"""
    r = subprocess.run(
        f'ffmpeg -y -ss {timestamp} -i "{video_path}" -vframes 1 -q:v 3 "{output_path}"',
        shell=True, capture_output=True, text=True,
    )
    if r.returncode != 0:
        # 시작 부분에서 추출 시도
        r = subprocess.run(
            f'ffmpeg -y -ss 0.5 -i "{video_path}" -vframes 1 -q:v 3 "{output_path}"',
            shell=True, capture_output=True, text=True,
        )
    return r.returncode == 0 and os.path.exists(output_path)


def verify_with_gemini(
    gemini_key: str,
    image_path: str,
    topic: str,
    category: str,
    query: str,
) -> dict:
    """Gemini Vision API로 영상 프레임이 주제에 적합한지 확인"""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    prompt = f"""You are a video content relevance checker.

Analyze this image (a frame from a YouTube video) and determine if it's suitable as B-roll footage for the following content:

Topic: {topic}
Category: {category}
Search query used: {query}

Score the relevance from 1-10:
- 1-3: Completely irrelevant (wrong subject, text-heavy, faces/talking heads, low quality)
- 4-5: Marginally relevant (loosely related but not ideal)
- 6-7: Relevant (matches the topic, usable)
- 8-10: Highly relevant (perfect B-roll for this topic)

Reject criteria (score 1-3):
- Contains prominent faces or talking heads (not suitable for B-roll)
- Is a screenshot, thumbnail, or text overlay
- Is completely unrelated to the topic
- Is very low quality or blurry

Respond ONLY with JSON:
{{"score": <number>, "reason": "<brief reason in Korean>"}}"""

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
            json={
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": image_data}},
                    ]
                }],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200},
            },
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(f"Gemini API 오류: {resp.status_code}")
            return {"score": 5, "reason": "검증 API 오류 - 기본 통과"}

        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        json_match = text[text.find("{"):text.rfind("}") + 1]
        result = json.loads(json_match)
        return {"score": result.get("score", 5), "reason": result.get("reason", "")}

    except Exception as e:
        logger.warning(f"Gemini 검증 실패: {e}")
        return {"score": 5, "reason": "검증 실패 - 기본 통과"}


def verify_videos(
    gemini_key: str,
    video_dir: str,
    topic: str,
    category: str,
    downloaded: list[dict],
    min_score: int = 4,
    progress_callback=None,
) -> list[dict]:
    """다운로드된 영상들의 적합성을 AI로 검증하고 부적합한 영상 제거"""
    if not gemini_key:
        logger.info("Gemini API 키 없음 - 검증 건너뜀")
        return downloaded

    verified = []
    total = len(downloaded)

    for i, video in enumerate(downloaded):
        if progress_callback:
            progress_callback(
                step="verifying",
                current=i + 1,
                total=total,
                video_title=video.get("source_title", video.get("filename", "")),
            )

        video_path = os.path.join(video_dir, video["filename"])
        if not os.path.exists(video_path):
            continue

        # 프레임 추출
        frame_path = video_path.replace(".mp4", "_verify.jpg")
        if not extract_frame(video_path, frame_path):
            logger.warning(f"프레임 추출 실패: {video['filename']}")
            verified.append({**video, "ai_score": 5, "ai_reason": "프레임 추출 실패 - 기본 통과"})
            continue

        # Gemini 검증
        result = verify_with_gemini(
            gemini_key, frame_path, topic, category,
            video.get("query", ""),
        )
        score = result["score"]
        reason = result["reason"]

        # 프레임 파일 정리
        if os.path.exists(frame_path):
            os.remove(frame_path)

        if score >= min_score:
            verified.append({**video, "ai_score": score, "ai_reason": reason})
            logger.info(f"✓ 적합 ({score}/10): {video.get('source_title', '')} - {reason}")
        else:
            # 부적합 영상 제거
            if os.path.exists(video_path):
                os.remove(video_path)
            logger.info(f"✕ 부적합 ({score}/10): {video.get('source_title', '')} - {reason}")

    return verified
