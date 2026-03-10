"""Pexels 무료 스톡 영상 검색 + 다운로드 서비스"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

PEXELS_API_BASE = "https://api.pexels.com/videos/search"
MAX_KEYWORDS = 5
DOWNLOAD_TIMEOUT = 60


def search_pexels_videos(
    api_key: str,
    query: str,
    per_page: int = 5,
    orientation: str = "landscape",
    size: str = "medium",
    min_duration: int = 5,
    max_duration: int = 60,
) -> list[dict]:
    """Pexels API로 영상 검색"""
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": orientation,
        "size": size,
        "per_page": per_page,
        "min_duration": min_duration,
        "max_duration": max_duration,
    }
    resp = requests.get(PEXELS_API_BASE, headers=headers, params=params, timeout=15)
    if resp.status_code == 401:
        raise ValueError("Pexels API 키가 유효하지 않습니다")
    if resp.status_code != 200:
        logger.warning(f"Pexels API error: {resp.status_code}")
        return []

    data = resp.json()
    results = []
    for video in data.get("videos", []):
        video_files = video.get("video_files", [])
        # HD 품질 우선 선택, 없으면 최대 해상도
        chosen = None
        for vf in video_files:
            if vf.get("quality") == "hd" and vf.get("file_type") == "video/mp4":
                if chosen is None or vf.get("width", 0) > chosen.get("width", 0):
                    chosen = vf
        if chosen is None:
            mp4_files = [vf for vf in video_files if vf.get("file_type") == "video/mp4"]
            if mp4_files:
                chosen = max(mp4_files, key=lambda f: f.get("width", 0))
        if chosen is None:
            continue

        results.append({
            "id": video.get("id"),
            "duration": video.get("duration", 0),
            "width": chosen.get("width", 0),
            "height": chosen.get("height", 0),
            "download_url": chosen.get("link", ""),
            "pexels_url": video.get("url", ""),
            "user": video.get("user", {}).get("name", ""),
        })
    return results


def download_pexels_video(url: str, output_path: str) -> bool:
    """Pexels 직접 URL에서 영상 다운로드"""
    try:
        resp = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
        if resp.status_code != 200:
            return False
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 10000
    except Exception as e:
        logger.warning(f"Pexels download failed: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False


def search_and_download_pexels(
    api_key: str,
    keywords: list[str],
    output_dir: str,
    max_per_keyword: int = 1,
    progress_callback=None,
) -> list[dict]:
    """키워드별 Pexels 검색 → 다운로드 전체 흐름"""
    from services.video_service import analyze_video

    keywords = keywords[:MAX_KEYWORDS]
    total = len(keywords)
    os.makedirs(output_dir, exist_ok=True)
    downloaded = []
    seen_ids = set()

    for i, keyword in enumerate(keywords):
        if progress_callback:
            progress_callback(step="searching", current=i + 1, total=total, query=keyword)

        results = search_pexels_videos(api_key, keyword)
        count = 0
        for vid in results:
            if vid["id"] in seen_ids:
                continue
            if vid["width"] < 640:
                continue
            seen_ids.add(vid["id"])

            if progress_callback:
                progress_callback(
                    step="downloading", current=i + 1, total=total,
                    query=keyword, video_title=f"pexels_{vid['id']}",
                )

            fname = f"pexels_{i+1}_{vid['id']}.mp4"
            out_path = os.path.join(output_dir, fname)
            ok = download_pexels_video(vid["download_url"], out_path)
            if ok:
                info = analyze_video(out_path)
                if info and info.get("width", 0) >= 640:
                    downloaded.append({
                        **info,
                        "query": keyword,
                        "source_title": f"Pexels #{vid['id']} by {vid['user']}",
                        "source_url": vid["pexels_url"],
                    })
                    count += 1
                    if count >= max_per_keyword:
                        break
                else:
                    if os.path.exists(out_path):
                        os.remove(out_path)

    if progress_callback:
        progress_callback(step="done", downloaded=len(downloaded))

    return downloaded
