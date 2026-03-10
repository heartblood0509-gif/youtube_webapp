"""Gemini Vision 기반 스마트 클립 매칭 - 대본 문장과 영상 장면을 AI로 매칭"""
import subprocess
import os
import base64
import json
import logging
import requests

logger = logging.getLogger(__name__)


def extract_frames(video_path: str, output_dir: str, count: int = 3) -> list[str]:
    """영상에서 여러 프레임 추출 (균등 간격)"""
    # 영상 길이 조회
    r = subprocess.run(
        f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{video_path}"',
        shell=True, capture_output=True, text=True,
    )
    duration = float(r.stdout.strip()) if r.stdout.strip() else 10.0

    frames = []
    for i in range(count):
        # 영상의 20%, 50%, 80% 지점에서 프레임 추출
        ratio = 0.2 + (0.6 * i / max(count - 1, 1))
        ts = round(duration * ratio, 1)
        ts = min(ts, duration - 0.5)

        basename = os.path.splitext(os.path.basename(video_path))[0]
        frame_path = os.path.join(output_dir, f"{basename}_frame_{i}.jpg")

        result = subprocess.run(
            f'ffmpeg -y -ss {ts} -i "{video_path}" -vframes 1 -q:v 5 "{frame_path}"',
            shell=True, capture_output=True, text=True,
        )
        if result.returncode == 0 and os.path.exists(frame_path):
            frames.append({"path": frame_path, "timestamp": ts})

    return frames


def match_clips_with_gemini(
    gemini_key: str,
    videos: list[dict],
    sentences: list[str],
    frames_per_video: dict[str, list[dict]],
) -> list[dict]:
    """Gemini Vision으로 각 문장에 최적의 영상+구간 매칭"""
    # Gemini에 보낼 이미지 파트 구성
    parts = []

    # 텍스트 프롬프트
    video_desc = []
    for i, v in enumerate(videos):
        dur = v.get("duration", 30)
        frames = frames_per_video.get(v["filename"], [])
        ts_list = [f"{f['timestamp']}s" for f in frames]
        video_desc.append(f"  Video {i}: \"{v['filename']}\" (duration: {dur:.1f}s, frames at: {', '.join(ts_list)})")

    sentence_desc = []
    for i, s in enumerate(sentences):
        sentence_desc.append(f"  Sentence {i}: \"{s}\"")

    prompt = f"""You are a professional video editor. Match each narration sentence to the best video clip.

Available videos:
{chr(10).join(video_desc)}

Narration sentences:
{chr(10).join(sentence_desc)}

Below are sample frames from each video. Use them to understand what each video contains visually.

Rules:
- Each sentence MUST be assigned exactly one video clip
- Choose the video whose visual content BEST matches the sentence meaning
- Set start/end times within the video's duration
- Each clip should be 4-8 seconds long
- Avoid using the exact same time range twice for the same video
- Spread clips across different parts of the videos

Return ONLY JSON array:
[{{"sentence_idx": 0, "video_idx": 0, "start": 2.0, "end": 7.0, "reason": "brief reason"}}, ...]"""

    parts.append({"text": prompt})

    # 각 비디오의 프레임 이미지 추가
    for i, v in enumerate(videos):
        frames = frames_per_video.get(v["filename"], [])
        for j, frame in enumerate(frames):
            if not os.path.exists(frame["path"]):
                continue
            with open(frame["path"], "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            parts.append({"text": f"[Video {i}, frame at {frame['timestamp']}s]"})
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_data}})

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
            json={
                "contents": [{"parts": parts}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2000},
            },
            timeout=30,
        )

        if resp.status_code != 200:
            logger.warning(f"Gemini API 오류: {resp.status_code} - {resp.text[:200]}")
            return []

        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        # JSON 배열 추출
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            logger.warning(f"JSON 배열 파싱 실패: {text[:200]}")
            return []

        matches = json.loads(text[start:end])
        return matches

    except Exception as e:
        logger.error(f"Gemini 스마트 클립 매칭 실패: {e}")
        return []


def smart_generate_clips(
    gemini_key: str,
    project_dir: str,
    videos: list[dict],
    sentences: list[str],
) -> list[dict]:
    """AI 스마트 클립 생성 메인 함수"""
    input_dir = os.path.join(project_dir, "input")
    temp_dir = os.path.join(project_dir, "temp_frames")
    os.makedirs(temp_dir, exist_ok=True)

    # 1) 각 영상에서 프레임 추출
    frames_per_video = {}
    for v in videos:
        video_path = os.path.join(input_dir, v["filename"])
        if not os.path.exists(video_path):
            continue
        frames = extract_frames(video_path, temp_dir, count=3)
        frames_per_video[v["filename"]] = frames

    if not frames_per_video:
        logger.error("프레임을 추출할 수 있는 영상이 없습니다")
        return []

    # 2) Gemini로 매칭
    matches = match_clips_with_gemini(gemini_key, videos, sentences, frames_per_video)

    # 3) 프레임 파일 정리
    for frames in frames_per_video.values():
        for f in frames:
            if os.path.exists(f["path"]):
                os.remove(f["path"])

    if not matches:
        logger.warning("Gemini 매칭 결과가 비어있음 - 기본 분배 사용")
        return []

    # 4) 클립 설정 생성
    clips = []
    for m in matches:
        s_idx = m.get("sentence_idx", 0)
        v_idx = m.get("video_idx", 0)
        start = m.get("start", 0)
        end = m.get("end", 5)

        if v_idx >= len(videos):
            v_idx = v_idx % len(videos)

        v = videos[v_idx]
        dur = v.get("duration", 30)

        # 범위 보정
        start = max(0, min(start, dur - 2))
        end = max(start + 2, min(end, dur))

        clips.append({
            "source": f"input/{v['filename']}",
            "start": round(start, 1),
            "end": round(end, 1),
        })

    return clips
