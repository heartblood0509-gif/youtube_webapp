"""
YouTube Shorts 9:16 빌드 파이프라인 (웹앱용)
build_shorts.py 기반, SSE progress callback 추가
모든 subprocess 호출은 asyncio.to_thread로 비동기 처리하여 이벤트 루프 차단 방지
"""
import subprocess
import os
import re
import json
import asyncio
import logging
from core.config import (
    CANVAS_W, CANVAS_H, SQUARE_SIZE, SQUARE_Y,
    TITLE_COLOR, TITLE_FONTSIZE, SUBTITLE_FONTSIZE, SUBTITLE_Y,
    TITLE_Y_SINGLE, TITLE_Y_UPPER, TITLE_Y_LOWER, TITLE_LINE_GAP,
    MAX_SUBTITLE_DISPLAY, CLIP_BUFFER,
    find_best_font, find_bgm,
)

logger = logging.getLogger(__name__)


def _run_sync(cmd):
    """동기 subprocess 실행 (스레드 풀에서 호출)"""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


async def run(cmd, desc=""):
    """비동기 subprocess 실행 - 이벤트 루프 차단 방지"""
    result = await asyncio.to_thread(_run_sync, cmd)
    if result.returncode != 0:
        raise RuntimeError(f"{desc} 실패: {result.stderr[:500]}")
    return result


async def get_duration(filepath):
    r = await asyncio.to_thread(
        _run_sync,
        f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{filepath}"',
    )
    return float(r.stdout.strip()) if r.stdout.strip() else 0


def split_title(text, max_chars=8):
    if len(text) <= max_chars:
        return [text]
    words = text.split(" ")
    line1, line2 = "", ""
    for word in words:
        if not line1 or len(line1 + " " + word) <= max_chars:
            line1 = (line1 + " " + word).strip()
        else:
            line2 = (line2 + " " + word).strip()
    if not line2:
        mid = len(text) // 2
        line1, line2 = text[:mid], text[mid:]
    return [line1, line2]


def display_len(text):
    return len(re.sub(r'[?,!.~…]', '', text))


def natural_split(text):
    if display_len(text) <= MAX_SUBTITLE_DISPLAY:
        return [text]
    comma_idx = text.find(',')
    if comma_idx > 0:
        p1 = text[:comma_idx + 1].strip()
        p2 = text[comma_idx + 1:].strip()
        if p2:
            return natural_split(p1) + natural_split(p2)
    words = text.split(' ')
    best, best_score = None, float('inf')
    for i in range(1, len(words)):
        p1, p2 = ' '.join(words[:i]), ' '.join(words[i:])
        l1, l2 = display_len(p1), display_len(p2)
        if l1 <= MAX_SUBTITLE_DISPLAY and l2 <= MAX_SUBTITLE_DISPLAY:
            if abs(l1 - l2) < best_score:
                best_score = abs(l1 - l2)
                best = (p1, p2)
    if best:
        return [best[0], best[1]]
    chunks, current = [], ""
    for word in words:
        test = (current + " " + word).strip() if current else word
        if display_len(test) <= MAX_SUBTITLE_DISPLAY:
            current = test
        else:
            if current:
                chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks


def ff_escape(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


async def run_build(
    project_dir: str,
    title_text: str,
    sentences: list[str],
    clips_config: list[dict],
    tts_results: list[dict],
    bgm_volume: float,
    emit,
):
    """전체 빌드 파이프라인 실행 (비동기 - 이벤트 루프 차단 없음)"""
    temp = os.path.join(project_dir, "temp_frames")
    os.makedirs(temp, exist_ok=True)
    font = find_best_font()
    bgm_path = find_bgm(project_dir)

    tts_durations = [t["duration"] for t in tts_results]

    # 클립 듀레이션 계산
    clip_durations = []
    clip_starts = []
    t = 0.0
    for i, dur in enumerate(tts_durations):
        if i >= len(clips_config):
            break
        clip_dur = round(dur + CLIP_BUFFER, 2)
        clip_durations.append(clip_dur)
        clip_starts.append(round(t, 2))
        t += clip_dur
    total_dur = round(t, 2)

    n = len(clip_durations)

    if n == 0:
        raise RuntimeError("클립이 없습니다. TTS 결과와 클립 설정을 확인하세요.")

    # === STEP 1: 클립 추출 ===
    await emit({"type": "progress", "step": "클립 추출", "step_number": 1, "total_steps": 5, "progress_percent": 10, "message": f"{n}개 클립 추출 중..."})

    crop_vf = "crop='min(iw,ih):min(iw,ih):(iw-min(iw,ih))/2:(ih-min(iw,ih))/2',scale=1080:1080,setsar=1,pad=1080:1920:0:420:black"
    for i in range(n):
        cfg = clips_config[i]
        src = os.path.join(project_dir, cfg["source"])

        # 소스 파일 존재 확인
        if not os.path.exists(src):
            raise RuntimeError(f"소스 영상 파일이 없습니다: {cfg['source']}")

        dur = clip_durations[i]
        out = os.path.join(temp, f"clip_{i:02d}.mp4")

        await emit({"type": "progress", "step": "클립 추출", "step_number": 1, "total_steps": 5, "progress_percent": 10 + int(15 * i / n), "message": f"클립 {i+1}/{n} 추출 중..."})

        await run(
            f'ffmpeg -y -ss {cfg["start"]} -i "{src}" -t {dur} '
            f'-vf "{crop_vf}" -an -c:v libx264 -preset fast -crf 18 "{out}"',
            f"클립 {i+1}",
        )

    # === STEP 2: 클립 연결 ===
    await emit({"type": "progress", "step": "클립 연결", "step_number": 2, "total_steps": 5, "progress_percent": 30, "message": "클립 연결 중..."})

    inputs = " ".join(f'-i "{temp}/clip_{i:02d}.mp4"' for i in range(n))
    streams = "".join(f"[{i}:v]" for i in range(n))
    fc = f'{streams}concat=n={n}:v=1:a=0[outv]'
    await run(
        f'ffmpeg -y {inputs} -filter_complex "{fc}" -map "[outv]" '
        f'-c:v libx264 -preset fast -crf 18 -r 30 -pix_fmt yuv420p "{temp}/concat_raw.mp4"',
        "클립 연결",
    )

    # === STEP 3: 나레이션 정렬 + 오디오 믹싱 ===
    await emit({"type": "progress", "step": "오디오 믹싱", "step_number": 3, "total_steps": 5, "progress_percent": 50, "message": "나레이션 정렬 + BGM 믹싱 중..."})

    narr_inputs = " ".join(f'-i "{temp}/sent_{i:02d}.wav"' for i in range(n))
    delays = []
    for i in range(n):
        ms = int(clip_starts[i] * 1000)
        delays.append(f"[{i}]adelay={ms}|{ms}[s{i}]")
    mix_in = "".join(f"[s{i}]" for i in range(n))
    fc_narr = ";".join(delays) + f";{mix_in}amix=inputs={n}:duration=longest:normalize=0"
    await run(
        f'ffmpeg -y {narr_inputs} -filter_complex "{fc_narr}" -t {total_dur} "{temp}/narration_aligned.wav"',
        "나레이션 정렬",
    )

    # BGM 믹싱
    if bgm_path and os.path.exists(bgm_path):
        await emit({"type": "progress", "step": "오디오 믹싱", "step_number": 3, "total_steps": 5, "progress_percent": 60, "message": "BGM 믹싱 중..."})
        fc_audio = (
            f"[1]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume=1.0[narr];"
            f"[2]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={bgm_volume}[bgm];"
            f"[narr][bgm]amix=inputs=2:duration=first:normalize=0[aout]"
        )
        await run(
            f'ffmpeg -y -i "{temp}/concat_raw.mp4" -i "{temp}/narration_aligned.wav" -i "{bgm_path}" '
            f'-filter_complex "{fc_audio}" -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 128k '
            f'-t {total_dur} "{temp}/mixed_audio.mp4"',
            "BGM 믹싱",
        )
    else:
        await run(
            f'ffmpeg -y -i "{temp}/concat_raw.mp4" -i "{temp}/narration_aligned.wav" '
            f'-map 0:v -map 1:a -c:v copy -c:a aac -b:a 128k '
            f'-shortest "{temp}/mixed_audio.mp4"',
            "오디오 합성",
        )

    # === STEP 4: 타이틀 + 자막 오버레이 ===
    await emit({"type": "progress", "step": "자막 오버레이", "step_number": 4, "total_steps": 5, "progress_percent": 70, "message": "타이틀 + 자막 오버레이 적용 중..."})

    filters = []

    # 타이틀
    title_lines = split_title(title_text, max_chars=8)
    for j, line in enumerate(title_lines):
        escaped = ff_escape(line)
        if len(title_lines) == 1:
            ty = TITLE_Y_SINGLE
        else:
            ty = TITLE_Y_UPPER if j == 0 else TITLE_Y_LOWER
        filters.append(
            f"drawtext=fontfile='{font}':text='{escaped}':"
            f"fontcolor={TITLE_COLOR}:fontsize={TITLE_FONTSIZE}:borderw=3:bordercolor=black:"
            f"x=(w-text_w)/2:y={ty}:"
            f"alpha='if(lt(t\\,0.3)\\,t/0.3\\,1)':"
            f"enable='between(t,0,{total_dur + 1})'"
        )

    # 자막
    for i, sent in enumerate(sentences):
        if i >= n:
            break
        parts = natural_split(sent)
        sent_dur = tts_durations[i]
        part_dur = sent_dur / len(parts)
        for j, part in enumerate(parts):
            t_start = round(clip_starts[i] + j * part_dur, 3)
            t_end = round(clip_starts[i] + (j + 1) * part_dur, 3)
            escaped = ff_escape(part)
            filters.append(
                f"drawtext=fontfile='{font}':text='{escaped}':"
                f"fontcolor=white:fontsize={SUBTITLE_FONTSIZE}:borderw=3:bordercolor=black:"
                f"x=(w-text_w)/2:y={SUBTITLE_Y}:"
                f"enable='between(t,{t_start},{t_end})'"
            )

    vf = ",".join(filters)
    output_name = os.path.basename(project_dir) + ".mp4"
    output_path = os.path.join(project_dir, "output", output_name)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    await emit({"type": "progress", "step": "자막 오버레이", "step_number": 4, "total_steps": 5, "progress_percent": 80, "message": "렌더링 중... (가장 오래 걸리는 단계)"})

    await run(
        f'ffmpeg -y -i "{temp}/mixed_audio.mp4" -vf "{vf}" '
        f'-c:v libx264 -preset fast -crf 18 -c:a copy "{output_path}"',
        "오버레이 렌더링",
    )

    # === STEP 5: 검증 ===
    await emit({"type": "progress", "step": "검증", "step_number": 5, "total_steps": 5, "progress_percent": 95, "message": "결과 검증 중..."})

    probe_result = await asyncio.to_thread(
        _run_sync,
        f'ffprobe -v quiet -print_format json -show_format -show_streams "{output_path}"',
    )
    info = json.loads(probe_result.stdout)
    video_stream = next((s for s in info["streams"] if s.get("codec_type") == "video"), {})
    result = {
        "filename": output_name,
        "path": output_path,
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "duration": round(float(info["format"]["duration"]), 1),
        "size_mb": round(os.path.getsize(output_path) / 1024 / 1024, 1),
    }

    await emit({"type": "done", "step": "완료", "step_number": 5, "total_steps": 5, "progress_percent": 100, "message": "영상 제작 완료!", "result": result})

    return result
