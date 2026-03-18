const BACKEND = 'http://localhost:8000';

export async function createProject(name: string, category: string, topic: string) {
  const res = await fetch(`${BACKEND}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, category, topic }),
  });
  return res.json();
}

export async function uploadVideos(projectId: string, files: File[]) {
  const formData = new FormData();
  formData.append('project_id', projectId);
  files.forEach(f => formData.append('files', f));
  const res = await fetch(`${BACKEND}/api/videos/upload`, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

export async function downloadFromYoutube(projectId: string, urls: string[], filenames: string[]) {
  const res = await fetch(`${BACKEND}/api/videos/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, urls, filenames }),
  });
  return res.json();
}

export async function analyzeVideos(projectId: string) {
  const res = await fetch(`${BACKEND}/api/videos/analyze/${projectId}`);
  return res.json();
}

export async function autoGenerateClips(projectId: string, sentenceCount: number) {
  const res = await fetch(`${BACKEND}/api/videos/auto-clips`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, sentence_count: sentenceCount }),
  });
  return res.json();
}

export async function smartGenerateClips(
  projectId: string,
  geminiKey: string,
  sentences: string[],
) {
  const res = await fetch(`${BACKEND}/api/videos/smart-clips`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, gemini_key: geminiKey, sentences }),
  });
  return res.json();
}

export async function aiSearchDownload(projectId: string, queries: string[]) {
  const res = await fetch(`${BACKEND}/api/videos/ai-search-download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, queries, max_per_query: 1 }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.[0]?.msg || `서버 오류: ${res.status}`);
  }
  return res.json();
}

export interface SearchProgressEvent {
  step: 'searching' | 'downloading' | 'verifying' | 'done' | 'complete' | 'error';
  current?: number;
  total?: number;
  query?: string;
  video_title?: string;
  downloaded?: unknown[] | number;
  count?: number;
  original_count?: number;
  rejected?: number;
  message?: string;
}

export async function aiSearchDownloadStream(
  projectId: string,
  queries: string[],
  onProgress: (event: SearchProgressEvent) => void,
  options?: { gemini_key?: string; topic?: string; category?: string },
): Promise<{ downloaded: unknown[]; count: number; rejected?: number }> {
  const res = await fetch(`${BACKEND}/api/videos/ai-search-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectId,
      queries,
      max_per_query: 1,
      gemini_key: options?.gemini_key || '',
      topic: options?.topic || '',
      category: options?.category || '',
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.[0]?.msg || `서버 오류: ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('스트림을 열 수 없습니다');

  const decoder = new TextDecoder();
  let buffer = '';
  let result = { downloaded: [] as unknown[], count: 0, rejected: 0 };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const event: SearchProgressEvent = JSON.parse(line.slice(6));
        onProgress(event);

        if (event.step === 'complete') {
          result = {
            downloaded: (Array.isArray(event.downloaded) ? event.downloaded : []) as unknown[],
            count: event.count || 0,
            rejected: event.rejected || 0,
          };
        }
        if (event.step === 'error') {
          throw new Error(event.message || 'AI 검색 중 오류 발생');
        }
      } catch (e) {
        if (e instanceof Error && e.message !== 'AI 검색 중 오류 발생') continue;
        throw e;
      }
    }
  }

  return result;
}

// ─── Claude Agent SSE ───

export interface AgentProgressEvent {
  step: 'thinking' | 'searching' | 'downloading' | 'verifying' | 'removing' | 'finishing' | 'complete' | 'error';
  message?: string;
  query?: string;
  video_title?: string;
  reason?: string;
  turn?: number;
  count?: number;
  videos?: unknown[];
  turns_used?: number;
}

export async function claudeAgentSearchStream(
  projectId: string,
  claudeKey: string,
  topic: string,
  category: string,
  sentences: string[],
  onProgress: (event: AgentProgressEvent) => void,
): Promise<{ count: number; videos: unknown[] }> {
  const res = await fetch(`${BACKEND}/api/agent/search-videos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectId,
      claude_key: claudeKey,
      topic,
      category,
      sentences,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.[0]?.msg || `서버 오류: ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('스트림을 열 수 없습니다');

  const decoder = new TextDecoder();
  let buffer = '';
  let result = { count: 0, videos: [] as unknown[] };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const event: AgentProgressEvent = JSON.parse(line.slice(6));
        onProgress(event);

        if (event.step === 'complete') {
          result = {
            count: event.count || 0,
            videos: event.videos as unknown[] || [],
          };
        }
        if (event.step === 'error') {
          throw new Error(event.message || 'Claude 에이전트 오류');
        }
      } catch (e) {
        if (e instanceof Error && e.message !== 'Claude 에이전트 오류') continue;
        throw e;
      }
    }
  }

  return result;
}

// ─── Pexels 스톡 영상 SSE ───

export async function pexelsSearchStream(
  projectId: string,
  pexelsKey: string,
  keywords: string[],
  onProgress: (event: SearchProgressEvent) => void,
): Promise<{ downloaded: unknown[]; count: number }> {
  const res = await fetch(`${BACKEND}/api/pexels/search-videos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectId,
      pexels_key: pexelsKey,
      keywords,
      max_per_keyword: 1,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.[0]?.msg || `서버 오류: ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('스트림을 열 수 없습니다');

  const decoder = new TextDecoder();
  let buffer = '';
  let result = { downloaded: [] as unknown[], count: 0 };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const event: SearchProgressEvent = JSON.parse(line.slice(6));
        onProgress(event);

        if (event.step === 'complete') {
          result = {
            downloaded: (Array.isArray(event.downloaded) ? event.downloaded : []) as unknown[],
            count: event.count || 0,
          };
        }
        if (event.step === 'error') {
          throw new Error(event.message || 'Pexels 검색 중 오류 발생');
        }
      } catch (e) {
        if (e instanceof Error && e.message !== 'Pexels 검색 중 오류 발생') continue;
        throw e;
      }
    }
  }

  return result;
}

// ─── Veo 3.1 AI 영상 생성 ───

export interface VeoProgressEvent {
  step: 'prompts' | 'prompts_done' | 'generating' | 'generated' | 'clip_error' | 'done' | 'complete' | 'error';
  current?: number;
  total?: number;
  prompt?: string;
  prompts?: string[];
  sentence?: string;
  filename?: string;
  elapsed?: number;
  count?: number;
  videos?: unknown[];
  message?: string;
}

export async function veoEstimate(sentenceCount: number, duration: number = 8) {
  const res = await fetch(`${BACKEND}/api/veo/estimate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sentence_count: sentenceCount, duration }),
  });
  return res.json();
}

export async function veoGenerateStream(
  projectId: string,
  geminiKey: string,
  sentences: string[],
  category: string,
  topic: string,
  onProgress: (event: VeoProgressEvent) => void,
): Promise<{ videos: unknown[]; count: number }> {
  const res = await fetch(`${BACKEND}/api/veo/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectId,
      gemini_key: geminiKey,
      sentences,
      category,
      topic,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.[0]?.msg || `서버 오류: ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('스트림을 열 수 없습니다');

  const decoder = new TextDecoder();
  let buffer = '';
  let result = { videos: [] as unknown[], count: 0 };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const event: VeoProgressEvent = JSON.parse(line.slice(6));
        onProgress(event);

        if (event.step === 'complete') {
          result = { videos: event.videos || [], count: event.count || 0 };
        }
        if (event.step === 'error') {
          throw new Error(event.message || 'Veo 영상 생성 중 오류');
        }
      } catch (e) {
        if (e instanceof Error && e.message !== 'Veo 영상 생성 중 오류') continue;
        throw e;
      }
    }
  }

  return result;
}

// ─── Nano Banana 2 AI 이미지 생성 ───

export interface ImagenProgressEvent {
  step: 'prompts' | 'prompts_done' | 'generating' | 'generated' | 'clip_error' | 'done' | 'complete' | 'error';
  current?: number;
  total?: number;
  prompt?: string;
  prompts?: string[];
  sentence?: string;
  filename?: string;
  count?: number;
  videos?: unknown[];
  message?: string;
}

export async function imagenEstimate(sentenceCount: number) {
  const res = await fetch(`${BACKEND}/api/imagen/estimate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sentence_count: sentenceCount }),
  });
  return res.json();
}

export async function imagenGenerateStream(
  projectId: string,
  geminiKey: string,
  sentences: string[],
  category: string,
  topic: string,
  onProgress: (event: ImagenProgressEvent) => void,
): Promise<{ videos: unknown[]; count: number }> {
  const res = await fetch(`${BACKEND}/api/imagen/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectId,
      gemini_key: geminiKey,
      sentences,
      category,
      topic,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.[0]?.msg || `서버 오류: ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('스트림을 열 수 없습니다');

  const decoder = new TextDecoder();
  let buffer = '';
  let result = { videos: [] as unknown[], count: 0 };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const event: ImagenProgressEvent = JSON.parse(line.slice(6));
        onProgress(event);

        if (event.step === 'complete') {
          result = { videos: event.videos || [], count: event.count || 0 };
        }
        if (event.step === 'error') {
          throw new Error(event.message || 'AI 이미지 생성 중 오류');
        }
      } catch (e) {
        if (e instanceof Error && e.message !== 'AI 이미지 생성 중 오류') continue;
        throw e;
      }
    }
  }

  return result;
}

// ─── Imagen 이미지 미리보기 & 재생성 ───

export interface ImagenPreview {
  index: number;
  image: string;
  video: string | null;
  image_url: string;
  video_url: string | null;
  prompt: string;
  sentence: string;
}

export async function imagenGetPreviews(projectId: string): Promise<{
  previews: ImagenPreview[];
  prompts: string[];
  sentences: string[];
}> {
  const res = await fetch(`${BACKEND}/api/imagen/preview/${projectId}`);
  return res.json();
}

export async function imagenRegenerateOne(
  projectId: string,
  geminiKey: string,
  index: number,
  prompt: string,
  effect?: string,
): Promise<{ filename: string; image: string; index: number; success: boolean; effect: string }> {
  const res = await fetch(`${BACKEND}/api/imagen/regenerate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectId,
      gemini_key: geminiKey,
      index,
      prompt,
      effect: effect || '',
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `재생성 실패: ${res.status}`);
  }
  return res.json();
}

export interface GalleryVideo {
  project_id: string;
  filename: string;
  url: string;
  width: number;
  height: number;
  duration: number;
  size_mb: number;
  created_at: number;
}

export async function getGallery(): Promise<{ videos: GalleryVideo[] }> {
  const res = await fetch(`${BACKEND}/api/projects/gallery`);
  return res.json();
}

export async function startBuild(data: {
  project_id: string;
  title_text: string;
  narration_sentences: string[];
  tts_engine: string;
  tts_speed: number;
  tts_language: string;
  bgm_volume: number;
  clips: { source: string; start: number; end: number }[];
}) {
  const res = await fetch(`${BACKEND}/api/build/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export function subscribeBuildProgress(
  jobId: string,
  onEvent: (event: import('@/types').BuildProgressEvent) => void,
): EventSource {
  const source = new EventSource(`${BACKEND}/api/build/progress/${jobId}`);
  source.onmessage = (e) => {
    const event = JSON.parse(e.data);
    onEvent(event);
    if (event.type === 'done' || event.type === 'error') {
      source.close();
    }
  };
  return source;
}

export async function getBuildResult(projectId: string) {
  const res = await fetch(`${BACKEND}/api/build/result/${projectId}`);
  return res.json();
}
