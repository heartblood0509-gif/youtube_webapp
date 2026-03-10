"""
Claude Agent - Claude Code처럼 AI가 도구를 사용하여 자율적으로 영상을 검색/평가/선택
Tool Use (Function Calling) 기반 에이전트 루프
"""
import os
import json
import base64
import subprocess
import logging
import anthropic

logger = logging.getLogger(__name__)

# ─── 도구 정의 (Claude가 호출 가능한 함수들) ───

TOOLS = [
    {
        "name": "search_youtube",
        "description": "유튜브에서 영상을 검색합니다. 검색어와 최대 결과 수를 지정하세요. 영문 검색어가 결과가 더 풍부합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색어 (영어 권장)"},
                "max_results": {"type": "integer", "description": "최대 검색 결과 수 (1-5)", "default": 3},
            },
            "required": ["query"],
        },
    },
    {
        "name": "download_video",
        "description": "유튜브 영상을 다운로드합니다. 720p-1080p MP4 포맷으로 다운로드됩니다. 다운로드 후 영상 정보(해상도, 길이 등)를 반환합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "video_id": {"type": "string", "description": "유튜브 영상 ID"},
                "video_title": {"type": "string", "description": "영상 제목 (파일명용)"},
            },
            "required": ["video_id"],
        },
    },
    {
        "name": "check_video_frame",
        "description": "다운로드된 영상에서 프레임을 추출하여 이미지로 확인합니다. 영상의 실제 내용을 눈으로 보고 적합한지 판단할 때 사용하세요.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "확인할 영상 파일명 (예: clip_1_abc123.mp4)"},
                "timestamp": {"type": "number", "description": "프레임 추출 시점 (초)", "default": 2.0},
            },
            "required": ["filename"],
        },
    },
    {
        "name": "list_downloaded",
        "description": "현재까지 다운로드된 영상 목록과 상세 정보를 확인합니다.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "remove_video",
        "description": "부적합한 영상을 제거합니다. 주제와 맞지 않거나 품질이 낮은 영상을 삭제할 때 사용하세요.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "제거할 영상 파일명"},
                "reason": {"type": "string", "description": "제거 사유"},
            },
            "required": ["filename", "reason"],
        },
    },
    {
        "name": "finish",
        "description": "영상 검색 및 선택을 완료합니다. 충분한 영상이 확보되었을 때 호출하세요.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "최종 요약 (한국어)"},
            },
            "required": ["summary"],
        },
    },
]


# ─── 도구 실행 함수들 ───

def _run_cmd(cmd: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)


def tool_search_youtube(query: str, max_results: int = 3) -> str:
    """yt-dlp로 유튜브 검색"""
    max_results = min(max_results, 5)
    cmd = (
        f'yt-dlp "ytsearch{max_results}:{query}" '
        f'--dump-json --no-download --flat-playlist --no-warnings 2>/dev/null'
    )
    try:
        r = _run_cmd(cmd, timeout=20)
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "검색 타임아웃"})

    results = []
    for line in r.stdout.strip().split('\n'):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            results.append({
                "id": data.get("id", ""),
                "title": data.get("title", ""),
                "duration": data.get("duration") or 0,
                "channel": data.get("channel") or data.get("uploader") or "",
                "view_count": data.get("view_count") or 0,
            })
        except json.JSONDecodeError:
            continue
    return json.dumps({"results": results, "count": len(results)}, ensure_ascii=False)


def tool_download_video(video_id: str, video_title: str, output_dir: str, clip_index: int) -> str:
    """유튜브 영상 다운로드"""
    safe_title = "".join(c for c in video_title[:20] if c.isalnum() or c in " _-").strip().replace(" ", "_")
    fname = f"clip_{clip_index}_{video_id}.mp4"
    out_path = os.path.join(output_dir, fname)

    if os.path.exists(out_path):
        return json.dumps({"success": True, "filename": fname, "message": "이미 다운로드됨"})

    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = (
        f'yt-dlp -f "bestvideo[height>=720][height<=1080][ext=mp4]+bestaudio[ext=m4a]'
        f'/best[height>=720][height<=1080][ext=mp4]/best" '
        f'--merge-output-format mp4 --no-playlist '
        f'-o "{out_path}" "{url}"'
    )
    try:
        r = _run_cmd(cmd, timeout=90)
        if r.returncode != 0:
            return json.dumps({"success": False, "error": "다운로드 실패", "detail": r.stderr[:200]})
    except subprocess.TimeoutExpired:
        # 부분 파일 정리
        for ext in [".mp4", ".part", ".mp4.part"]:
            p = out_path.replace(".mp4", ext)
            if os.path.exists(p):
                os.remove(p)
        return json.dumps({"success": False, "error": "다운로드 타임아웃 (90초)"})

    if not os.path.exists(out_path):
        return json.dumps({"success": False, "error": "파일이 생성되지 않음"})

    # 메타데이터
    probe = _run_cmd(f'ffprobe -v quiet -print_format json -show_format -show_streams "{out_path}"')
    try:
        info = json.loads(probe.stdout)
        vs = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        return json.dumps({
            "success": True,
            "filename": fname,
            "width": int(vs.get("width", 0)),
            "height": int(vs.get("height", 0)),
            "duration": round(float(info["format"]["duration"]), 1),
            "size_mb": round(os.path.getsize(out_path) / 1024 / 1024, 1),
        })
    except Exception:
        return json.dumps({"success": True, "filename": fname, "message": "다운로드 완료 (메타데이터 파싱 실패)"})


def tool_check_video_frame(filename: str, output_dir: str, timestamp: float = 2.0) -> tuple[str, str | None]:
    """영상 프레임 추출 → base64 이미지 반환"""
    video_path = os.path.join(output_dir, filename)
    if not os.path.exists(video_path):
        return json.dumps({"error": f"파일 없음: {filename}"}), None

    frame_path = video_path.replace(".mp4", "_frame.jpg")
    r = _run_cmd(f'ffmpeg -y -ss {timestamp} -i "{video_path}" -vframes 1 -q:v 3 "{frame_path}"')
    if r.returncode != 0 or not os.path.exists(frame_path):
        # 시작 부분에서 재시도
        _run_cmd(f'ffmpeg -y -ss 0.5 -i "{video_path}" -vframes 1 -q:v 3 "{frame_path}"')

    if not os.path.exists(frame_path):
        return json.dumps({"error": "프레임 추출 실패"}), None

    with open(frame_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    os.remove(frame_path)
    return json.dumps({"filename": filename, "frame_extracted": True}), image_b64


def tool_list_downloaded(output_dir: str) -> str:
    """다운로드된 영상 목록"""
    if not os.path.isdir(output_dir):
        return json.dumps({"videos": [], "count": 0})

    videos = []
    for f in sorted(os.listdir(output_dir)):
        if not f.endswith((".mp4", ".mov", ".avi", ".mkv")):
            continue
        path = os.path.join(output_dir, f)
        probe = _run_cmd(f'ffprobe -v quiet -print_format json -show_format -show_streams "{path}"')
        try:
            info = json.loads(probe.stdout)
            vs = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
            videos.append({
                "filename": f,
                "width": int(vs.get("width", 0)),
                "height": int(vs.get("height", 0)),
                "duration": round(float(info["format"]["duration"]), 1),
                "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1),
            })
        except Exception:
            videos.append({"filename": f, "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1)})

    return json.dumps({"videos": videos, "count": len(videos)}, ensure_ascii=False)


def tool_remove_video(filename: str, reason: str, output_dir: str) -> str:
    """부적합 영상 제거"""
    path = os.path.join(output_dir, filename)
    if os.path.exists(path):
        os.remove(path)
        return json.dumps({"removed": True, "filename": filename, "reason": reason})
    return json.dumps({"removed": False, "error": f"파일 없음: {filename}"})


# ─── 에이전트 실행 ───

def execute_tool(tool_name: str, tool_input: dict, output_dir: str, state: dict) -> tuple[list, dict]:
    """도구 실행 → 결과 반환 (텍스트 + 선택적 이미지)"""
    content_blocks = []

    if tool_name == "search_youtube":
        result = tool_search_youtube(tool_input["query"], tool_input.get("max_results", 3))
        content_blocks.append({"type": "text", "text": result})

    elif tool_name == "download_video":
        state["clip_index"] = state.get("clip_index", 0) + 1
        result = tool_download_video(
            tool_input["video_id"],
            tool_input.get("video_title", ""),
            output_dir,
            state["clip_index"],
        )
        content_blocks.append({"type": "text", "text": result})

    elif tool_name == "check_video_frame":
        result_text, image_b64 = tool_check_video_frame(
            tool_input["filename"], output_dir, tool_input.get("timestamp", 2.0)
        )
        if image_b64:
            content_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64},
            })
        content_blocks.append({"type": "text", "text": result_text})

    elif tool_name == "list_downloaded":
        result = tool_list_downloaded(output_dir)
        content_blocks.append({"type": "text", "text": result})

    elif tool_name == "remove_video":
        result = tool_remove_video(tool_input["filename"], tool_input["reason"], output_dir)
        content_blocks.append({"type": "text", "text": result})

    elif tool_name == "finish":
        content_blocks.append({"type": "text", "text": json.dumps({"finished": True, "summary": tool_input["summary"]})})

    return content_blocks, state


def run_agent(
    api_key: str,
    topic: str,
    category: str,
    sentences: list[str],
    output_dir: str,
    progress_callback=None,
    max_turns: int = 25,
) -> dict:
    """Claude 에이전트 루프 실행 - Claude Code처럼 자율적으로 영상 검색/평가/선택"""

    os.makedirs(output_dir, exist_ok=True)
    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = f"""당신은 유튜브 쇼츠 영상 제작을 위한 B-roll 영상 소스 전문가입니다.

## 작업
아래 나레이션 대본에 어울리는 유튜브 B-roll 영상을 검색하고, 다운로드하고, 직접 확인하여 적합한 영상만 선택하세요.

## 정보
- 카테고리: {category}
- 주제: {topic}
- 나레이션 대본:
{chr(10).join(f"  {i+1}. {s}" for i, s in enumerate(sentences))}

## 필요한 영상 수
대본 문장 수({len(sentences)}개)에 맞게 최소 {min(len(sentences), 5)}개 ~ 최대 {len(sentences)}개의 적합한 영상을 확보하세요.

## 작업 순서
1. 대본 내용을 분석하여 적절한 검색어를 생각하세요 (영어 검색어가 결과가 풍부합니다)
2. search_youtube로 검색하세요
3. 결과 중 적합해 보이는 영상을 download_video로 다운로드하세요
4. check_video_frame으로 실제 영상 내용을 눈으로 확인하세요
5. 부적합한 영상은 remove_video로 제거하세요
6. 충분한 영상이 모이면 finish를 호출하세요

## 영상 선택 기준
- B-roll로 적합한 풍경, 장면, 활동 영상 선호
- 얼굴이 크게 나오는 토킹헤드 영상은 피하세요
- 워터마크가 큰 영상은 피하세요
- 720p 이상 고화질 선호
- 10초 미만이거나 5분 이상인 영상은 피하세요
- 주제와 직접적으로 관련된 영상을 우선하세요

## 주의사항
- 검색어는 다양하게 시도하세요 (한 검색어가 안 되면 다른 표현 시도)
- 각 영상을 다운로드 후 반드시 check_video_frame으로 확인하세요
- 효율적으로 작업하세요 - 불필요한 반복을 피하세요
- 한국어로 진행 상황을 설명하세요"""

    messages = [{"role": "user", "content": "위 대본에 맞는 B-roll 영상을 찾아주세요. 검색부터 시작해주세요."}]
    state = {"clip_index": 0}
    finished = False

    for turn in range(max_turns):
        if finished:
            break

        try:
            response = client.messages.create(
                model="claude-sonnet-4-5-20250514",
                max_tokens=4096,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.APIError as e:
            logger.error(f"Claude API 오류: {e}")
            if progress_callback:
                progress_callback(step="error", message=f"Claude API 오류: {str(e)}")
            return {"error": str(e)}

        # 응답 처리
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # 텍스트 블록에서 사고 과정 추출
        for block in assistant_content:
            if block.type == "text" and block.text.strip():
                if progress_callback:
                    progress_callback(step="thinking", message=block.text, turn=turn + 1)

        # stop_reason 확인
        if response.stop_reason == "end_turn":
            finished = True
            break

        if response.stop_reason != "tool_use":
            finished = True
            break

        # 도구 호출 처리
        tool_results = []
        for block in assistant_content:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input

            if progress_callback:
                if tool_name == "search_youtube":
                    progress_callback(step="searching", query=tool_input.get("query", ""), turn=turn + 1)
                elif tool_name == "download_video":
                    progress_callback(step="downloading", video_title=tool_input.get("video_title", ""), turn=turn + 1)
                elif tool_name == "check_video_frame":
                    progress_callback(step="verifying", video_title=tool_input.get("filename", ""), turn=turn + 1)
                elif tool_name == "remove_video":
                    progress_callback(step="removing", video_title=tool_input.get("filename", ""), reason=tool_input.get("reason", ""), turn=turn + 1)
                elif tool_name == "finish":
                    progress_callback(step="finishing", message=tool_input.get("summary", ""), turn=turn + 1)
                    finished = True

            # 도구 실행
            result_content, state = execute_tool(tool_name, tool_input, output_dir, state)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_content,
            })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    # 최종 결과
    final_videos = json.loads(tool_list_downloaded(output_dir))
    if progress_callback:
        progress_callback(step="complete", downloaded=final_videos["count"])

    return {
        "videos": final_videos["videos"],
        "count": final_videos["count"],
        "turns_used": turn + 1 if 'turn' in dir() else 0,
    }
