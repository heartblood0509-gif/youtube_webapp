import subprocess
import json
import os
import logging

logger = logging.getLogger(__name__)

MAX_QUERIES = 5
SEARCH_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 90


def ffprobe_info(filepath: str) -> dict:
    """ffprobe로 영상 메타데이터 조회"""
    r = subprocess.run(
        f'ffprobe -v quiet -print_format json -show_format -show_streams "{filepath}"',
        shell=True, capture_output=True, text=True,
    )
    if r.returncode != 0:
        return {}
    return json.loads(r.stdout)


def analyze_video(filepath: str) -> dict:
    """영상 파일 분석 → 해상도, 길이, 크기"""
    info = ffprobe_info(filepath)
    if not info:
        return {}
    video_stream = next(
        (s for s in info.get("streams", []) if s.get("codec_type") == "video"), {}
    )
    fmt = info.get("format", {})
    return {
        "filename": os.path.basename(filepath),
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "duration": float(fmt.get("duration", 0)),
        "size_mb": round(os.path.getsize(filepath) / 1024 / 1024, 1),
    }


def download_youtube(url: str, output_path: str) -> bool:
    """yt-dlp로 유튜브 영상 다운로드 (타임아웃 적용)"""
    cmd = (
        f'yt-dlp -f "bestvideo[height>=720][height<=1080][ext=mp4]+bestaudio[ext=m4a]'
        f'/best[height>=720][height<=1080][ext=mp4]/best" '
        f'--merge-output-format mp4 '
        f'--no-playlist '
        f'-o "{output_path}" "{url}"'
    )
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=DOWNLOAD_TIMEOUT)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        logger.warning(f"다운로드 타임아웃 ({DOWNLOAD_TIMEOUT}s): {url}")
        # 타임아웃 시 부분 다운로드 파일 정리
        for ext in [".mp4", ".part", ".mp4.part"]:
            partial = output_path.replace(".mp4", ext)
            if os.path.exists(partial):
                os.remove(partial)
        return False


def search_youtube(query: str, max_results: int = 3) -> list[dict]:
    """yt-dlp로 유튜브 검색 → 영상 정보 목록 반환"""
    cmd = (
        f'yt-dlp "ytsearch{max_results}:{query}" '
        f'--dump-json --no-download --flat-playlist '
        f'--no-warnings 2>/dev/null'
    )
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=SEARCH_TIMEOUT)
    except subprocess.TimeoutExpired:
        logger.warning(f"검색 타임아웃 ({SEARCH_TIMEOUT}s): {query}")
        return []
    results = []
    for line in r.stdout.strip().split('\n'):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            results.append({
                "id": data.get("id", ""),
                "title": data.get("title", ""),
                "url": data.get("url") or f"https://www.youtube.com/watch?v={data.get('id', '')}",
                "duration": data.get("duration") or 0,
                "channel": data.get("channel") or data.get("uploader") or "",
            })
        except json.JSONDecodeError:
            continue
    return results


def search_and_download(
    queries: list[str],
    output_dir: str,
    max_per_query: int = 1,
    progress_callback=None,
) -> list[dict]:
    """여러 검색 쿼리로 유튜브 검색 후 다운로드 (최대 5개 쿼리)"""
    # 검색어 개수 강제 제한
    queries = queries[:MAX_QUERIES]
    total = len(queries)

    os.makedirs(output_dir, exist_ok=True)
    downloaded = []
    seen_ids = set()

    for i, query in enumerate(queries):
        if progress_callback:
            progress_callback(
                step="searching",
                current=i + 1,
                total=total,
                query=query,
            )

        results = search_youtube(query, max_results=3)
        count = 0
        for vid in results:
            if vid["id"] in seen_ids:
                continue
            if vid["duration"] and vid["duration"] < 10:
                continue
            # 너무 긴 영상 스킵 (5분 초과)
            if vid["duration"] and vid["duration"] > 300:
                continue
            seen_ids.add(vid["id"])

            if progress_callback:
                progress_callback(
                    step="downloading",
                    current=i + 1,
                    total=total,
                    query=query,
                    video_title=vid["title"],
                )

            fname = f"ai_clip_{i+1}_{vid['id']}"
            out_path = os.path.join(output_dir, f"{fname}.mp4")
            ok = download_youtube(vid["url"], out_path)
            if ok and os.path.exists(out_path):
                info = analyze_video(out_path)
                if info and info.get("width", 0) >= 640:
                    downloaded.append({
                        **info,
                        "query": query,
                        "source_title": vid["title"],
                        "source_url": vid["url"],
                    })
                    count += 1
                    if count >= max_per_query:
                        break
                else:
                    if os.path.exists(out_path):
                        os.remove(out_path)

    if progress_callback:
        progress_callback(step="done", downloaded=len(downloaded))

    return downloaded


def auto_generate_clips(videos: list[dict], sentence_count: int) -> list[dict]:
    """영상들을 문장 수에 맞게 자동 분배하여 클립 설정 생성"""
    clips = []
    if not videos:
        return clips

    per_clip_base = 5.0
    for i in range(sentence_count):
        v = videos[i % len(videos)]
        dur = v.get("duration", 30)
        # 영상 내에서 균등 분배
        segment_len = max(dur - 10, 10) / max(
            sentence_count // len(videos), 1
        )
        start = min(5.0 + (i // len(videos)) * segment_len, dur - 5)
        end = min(start + per_clip_base + 5, dur - 0.5)
        clips.append({
            "source": f"input/{v['filename']}",
            "start": round(start, 1),
            "end": round(end, 1),
        })
    return clips
