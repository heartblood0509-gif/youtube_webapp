'use client';

import { useRef, useState } from 'react';
import type { VideoInfo } from '@/types';
import {
  uploadVideos, downloadFromYoutube, analyzeVideos, createProject,
  aiSearchDownloadStream, pexelsSearchStream,
} from '@/lib/api';
import type { SearchProgressEvent } from '@/lib/api';
import { callGemini } from '@/lib/gemini';
import { buildSearchQueryPrompt, buildPexelsKeywordPrompt } from '@/lib/prompts';

const MAX_QUERIES = 5;

interface Props {
  geminiKey: string;
  pexelsKey: string;
  projectId: string | null;
  category: string;
  topic: string;
  script: string[];
  videoSource: 'upload' | 'youtube' | 'ai' | 'pexels';
  videos: VideoInfo[];
  youtubeUrls: { url: string; name: string }[];
  onChangeSource: (src: 'upload' | 'youtube' | 'ai' | 'pexels') => void;
  onSetProjectId: (id: string) => void;
  onSetVideos: (v: VideoInfo[]) => void;
  onSetYoutubeUrls: (urls: { url: string; name: string }[]) => void;
  onNext: () => void;
  onPrev: () => void;
}

export default function Step2_VideoSource({
  geminiKey,
  pexelsKey,
  projectId,
  category,
  topic,
  script,
  videoSource,
  videos,
  youtubeUrls,
  onChangeSource,
  onSetProjectId,
  onSetVideos,
  onSetYoutubeUrls,
  onNext,
  onPrev,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [aiQueries, setAiQueries] = useState<string[]>([]);
  const [aiStatus, setAiStatus] = useState('');
  const [searchProgress, setSearchProgress] = useState<{ current: number; total: number; step: string; detail: string } | null>(null);
  async function ensureProject(): Promise<string> {
    if (projectId) return projectId;
    const name = `shorts_${Date.now()}`;
    const res = await createProject(name, category, topic);
    onSetProjectId(res.id);
    return res.id;
  }

  async function handleUpload(files: FileList) {
    setLoading(true);
    setError('');
    try {
      const pid = await ensureProject();
      const res = await uploadVideos(pid, Array.from(files));
      if (res.error) throw new Error(res.error);
      const analysis = await analyzeVideos(pid);
      onSetVideos(analysis.videos || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '업로드 실패');
    } finally {
      setLoading(false);
    }
  }

  async function handleYoutubeDownload() {
    const validUrls = youtubeUrls.filter((u) => u.url.trim());
    if (validUrls.length === 0) return;
    setLoading(true);
    setError('');
    try {
      const pid = await ensureProject();
      const res = await downloadFromYoutube(
        pid,
        validUrls.map((u) => u.url),
        validUrls.map((u) => u.name || `video_${Date.now()}`),
      );
      if (res.error) throw new Error(res.error);
      const analysis = await analyzeVideos(pid);
      onSetVideos(analysis.videos || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '다운로드 실패');
    } finally {
      setLoading(false);
    }
  }

  // ─── Pexels 스톡 영상 검색 ───
  async function handlePexelsSearch() {
    if (!pexelsKey) {
      setError('Pexels API 키를 먼저 입력하세요.');
      return;
    }
    if (!geminiKey) {
      setError('Gemini API 키를 먼저 입력하세요. (키워드 생성에 필요)');
      return;
    }
    if (script.length === 0) {
      setError('대본이 없습니다. 이전 단계에서 대본을 먼저 작성하세요.');
      return;
    }
    setLoading(true);
    setError('');
    setAiQueries([]);
    setSearchProgress(null);
    setAiStatus('Gemini가 스톡 영상 키워드를 생성하고 있습니다...');

    try {
      // 1) Gemini로 키워드 생성
      const prompt = buildPexelsKeywordPrompt(category, topic, script);
      const raw = await callGemini(geminiKey, prompt);
      const jsonMatch = raw.match(/\{[\s\S]*\}/);
      if (!jsonMatch) throw new Error('키워드 생성 실패');
      const parsed = JSON.parse(jsonMatch[0]);
      let keywords: string[] = parsed.keywords || [];
      if (keywords.length === 0) throw new Error('생성된 키워드가 없습니다');
      if (keywords.length > 5) keywords = keywords.slice(0, 5);
      setAiQueries(keywords);

      // 2) Pexels 검색 + 다운로드
      setAiStatus(`${keywords.length}개 키워드로 Pexels에서 스톡 영상을 찾고 있습니다...`);
      const pid = await ensureProject();

      const res = await pexelsSearchStream(pid, pexelsKey, keywords, (event: SearchProgressEvent) => {
        if (event.step === 'searching') {
          setSearchProgress({
            current: event.current || 0,
            total: event.total || keywords.length,
            step: '검색',
            detail: event.query || '',
          });
          setAiStatus(`[${event.current}/${event.total}] "${event.query}" Pexels 검색 중...`);
        } else if (event.step === 'downloading') {
          setSearchProgress({
            current: event.current || 0,
            total: event.total || keywords.length,
            step: '다운로드',
            detail: event.video_title || '',
          });
          setAiStatus(`[${event.current}/${event.total}] 스톡 영상 다운로드 중...`);
        } else if (event.step === 'done') {
          setAiStatus(`${event.downloaded || 0}개 스톡 영상 다운로드 완료!`);
        }
      });

      setAiStatus(`${res.count}개 스톡 영상 준비 완료! 분석 중...`);

      // 3) 분석
      const analysis = await analyzeVideos(pid);
      onSetVideos(analysis.videos || []);
      setAiStatus(`완료! ${analysis.videos?.length || 0}개 스톡 영상 준비됨`);
      setSearchProgress(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Pexels 검색 실패');
      setAiStatus('');
      setSearchProgress(null);
    } finally {
      setLoading(false);
    }
  }

  // ─── Gemini AI 검색 (레거시) ───
  async function handleAISearch() {
    if (!geminiKey) {
      setError('Gemini API 키를 먼저 입력하세요.');
      return;
    }
    setLoading(true);
    setError('');
    setSearchProgress(null);
    setAiStatus('AI가 검색어를 생성하고 있습니다...');
    try {
      const prompt = buildSearchQueryPrompt(category, topic, script);
      const raw = await callGemini(geminiKey, prompt);
      const jsonMatch = raw.match(/\{[\s\S]*\}/);
      if (!jsonMatch) throw new Error('검색어 생성 실패');
      const parsed = JSON.parse(jsonMatch[0]);
      let queries: string[] = parsed.queries || [];
      if (queries.length === 0) throw new Error('생성된 검색어가 없습니다');

      if (queries.length > MAX_QUERIES) {
        queries = queries.slice(0, MAX_QUERIES);
      }
      setAiQueries(queries);

      setAiStatus(`${queries.length}개 검색어로 유튜브에서 영상을 찾고 있습니다...`);
      const pid = await ensureProject();

      const res = await aiSearchDownloadStream(pid, queries, (event: SearchProgressEvent) => {
        if (event.step === 'searching') {
          setSearchProgress({
            current: event.current || 0,
            total: event.total || queries.length,
            step: '검색',
            detail: event.query || '',
          });
          setAiStatus(`[${event.current}/${event.total}] "${event.query}" 검색 중...`);
        } else if (event.step === 'downloading') {
          setSearchProgress({
            current: event.current || 0,
            total: event.total || queries.length,
            step: '다운로드',
            detail: event.video_title || '',
          });
          setAiStatus(`[${event.current}/${event.total}] 영상 다운로드 중: ${event.video_title || ''}`);
        } else if (event.step === 'verifying') {
          setSearchProgress({
            current: event.current || 0,
            total: event.total || 0,
            step: 'AI 검증',
            detail: event.video_title || '',
          });
          setAiStatus(`[${event.current}/${event.total}] AI 영상 적합성 검증 중: ${event.video_title || ''}`);
        } else if (event.step === 'done') {
          setAiStatus(`${event.downloaded || 0}개 영상 다운로드 완료!`);
        }
      }, { gemini_key: geminiKey, topic, category });

      const rejectedMsg = res.rejected ? ` (부적합 ${res.rejected}개 제거)` : '';
      setAiStatus(`${res.count}개 영상 준비 완료!${rejectedMsg} 분석 중...`);

      const analysis = await analyzeVideos(pid);
      onSetVideos(analysis.videos || []);
      setAiStatus(`완료! ${analysis.videos?.length || 0}개 영상 준비됨`);
      setSearchProgress(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'AI 영상 검색 실패');
      setAiStatus('');
      setSearchProgress(null);
    } finally {
      setLoading(false);
    }
  }

  function addUrlRow() {
    onSetYoutubeUrls([...youtubeUrls, { url: '', name: '' }]);
  }

  function removeUrlRow(idx: number) {
    onSetYoutubeUrls(youtubeUrls.filter((_, i) => i !== idx));
  }

  function updateUrlRow(idx: number, field: 'url' | 'name', value: string) {
    const updated = [...youtubeUrls];
    updated[idx] = { ...updated[idx], [field]: value };
    onSetYoutubeUrls(updated);
  }

  const canNext = videos.length > 0;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold mb-2">영상 소스</h2>
        <p className="text-muted">영상을 직접 제공하거나, AI가 대본에 맞는 영상을 자동으로 찾아줍니다.</p>
      </div>

      {/* 소스 선택 - 4가지 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <button
          onClick={() => onChangeSource('pexels')}
          className={`p-4 rounded-lg border text-left transition-all ${
            videoSource === 'pexels'
              ? 'border-teal-500 bg-teal-500/10 ring-1 ring-teal-500'
              : 'border-border bg-surface hover:bg-surface-hover'
          }`}
        >
          <div className="font-medium mb-1 text-teal-400">Pexels 스톡</div>
          <div className="text-xs text-muted">무료 HD 스톡영상 자동 검색</div>
        </button>
        <button
          onClick={() => onChangeSource('ai')}
          className={`p-4 rounded-lg border text-left transition-all ${
            videoSource === 'ai'
              ? 'border-primary bg-primary/10 ring-1 ring-primary'
              : 'border-border bg-surface hover:bg-surface-hover'
          }`}
        >
          <div className="font-medium mb-1">Gemini 검색</div>
          <div className="text-xs text-muted">Gemini 검색어 기반 자동 검색</div>
        </button>
        <button
          onClick={() => onChangeSource('upload')}
          className={`p-4 rounded-lg border text-left transition-all ${
            videoSource === 'upload'
              ? 'border-primary bg-primary/10 ring-1 ring-primary'
              : 'border-border bg-surface hover:bg-surface-hover'
          }`}
        >
          <div className="font-medium mb-1">파일 업로드</div>
          <div className="text-xs text-muted">내 컴퓨터에서 영상 파일 선택</div>
        </button>
        <button
          onClick={() => onChangeSource('youtube')}
          className={`p-4 rounded-lg border text-left transition-all ${
            videoSource === 'youtube'
              ? 'border-primary bg-primary/10 ring-1 ring-primary'
              : 'border-border bg-surface hover:bg-surface-hover'
          }`}
        >
          <div className="font-medium mb-1">유튜브 URL</div>
          <div className="text-xs text-muted">유튜브 URL을 직접 입력</div>
        </button>
      </div>

      {/* Pexels 스톡 영상 모드 */}
      {videoSource === 'pexels' && (
        <div className="space-y-4">
          <div className="p-4 bg-teal-500/5 border border-teal-500/20 rounded-lg">
            <div className="text-sm mb-3">
              <span className="text-teal-400 font-medium">Pexels 무료 스톡 영상</span> 검색 과정:
            </div>
            <ol className="text-xs text-muted space-y-1 list-decimal list-inside">
              <li>Gemini가 대본을 분석하여 영어 키워드 5개 생성 (무료)</li>
              <li>Pexels API로 HD 스톡 영상 검색 (무료)</li>
              <li>고화질 영상 자동 다운로드 (무료, 상업적 사용 가능)</li>
            </ol>
            <div className="mt-3 text-xs text-teal-400/70">
              비용 0원 | 소요시간 5~10초 | 저작권 안전 (Pexels 라이선스)
            </div>
          </div>

          <button
            onClick={handlePexelsSearch}
            disabled={loading}
            className="w-full py-3 bg-teal-500 text-white font-medium rounded-lg hover:bg-teal-600 disabled:opacity-40 transition-colors"
          >
            {loading ? 'Pexels 스톡 영상 검색 중...' : 'Pexels 스톡 영상 자동 검색 시작'}
          </button>

          {/* 진행 상태 */}
          {aiStatus && (
            <div className="p-3 bg-teal-500/5 border border-teal-500/20 rounded-lg text-sm text-teal-300 space-y-2">
              <div className="flex items-center">
                {loading && <span className="inline-block animate-pulse mr-2">●</span>}
                {aiStatus}
              </div>
              {searchProgress && loading && (
                <div className="space-y-1">
                  <div className="w-full bg-zinc-800 rounded-full h-2">
                    <div
                      className="bg-teal-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${Math.round((searchProgress.current / searchProgress.total) * 100)}%` }}
                    />
                  </div>
                  <div className="text-xs text-muted">
                    {searchProgress.step} {searchProgress.current}/{searchProgress.total}
                    {searchProgress.detail && ` — ${searchProgress.detail.length > 40 ? searchProgress.detail.slice(0, 40) + '...' : searchProgress.detail}`}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 생성된 키워드 칩 */}
          {aiQueries.length > 0 && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted">생성된 키워드</label>
              <div className="flex flex-wrap gap-2">
                {aiQueries.map((q, i) => (
                  <span
                    key={i}
                    className="px-3 py-1 bg-teal-500/10 border border-teal-500/30 rounded-full text-xs text-teal-300"
                  >
                    {q}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Gemini AI 자동 검색 */}
      {videoSource === 'ai' && (
        <div className="space-y-4">
          <div className="p-4 bg-surface border border-border rounded-lg">
            <div className="text-sm mb-3">
              <span className="text-primary font-medium">Gemini AI 검색</span>이 하는 일:
            </div>
            <ol className="text-xs text-muted space-y-1 list-decimal list-inside">
              <li>Gemini가 대본을 분석하여 유튜브 검색어 5개 생성</li>
              <li>각 검색어로 유튜브에서 고화질 영상 검색 + 다운로드</li>
              <li>AI가 다운로드된 영상을 확인하여 주제에 맞는지 검증</li>
              <li>적합한 영상만 남기고 클립으로 자동 추출</li>
            </ol>
          </div>

          <button
            onClick={handleAISearch}
            disabled={loading}
            className="w-full py-3 bg-primary text-black font-medium rounded-lg hover:bg-primary-hover disabled:opacity-40 transition-colors"
          >
            {loading ? 'AI 검색 진행 중...' : 'Gemini AI 영상 자동 검색 시작'}
          </button>

          {/* 진행 상태 */}
          {aiStatus && (
            <div className="p-3 bg-primary/5 border border-primary/20 rounded-lg text-sm text-primary space-y-2">
              <div className="flex items-center">
                {loading && <span className="inline-block animate-pulse mr-2">●</span>}
                {aiStatus}
              </div>
              {searchProgress && loading && (
                <div className="space-y-1">
                  <div className="w-full bg-zinc-800 rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full transition-all duration-500"
                      style={{ width: `${Math.round((searchProgress.current / searchProgress.total) * 100)}%` }}
                    />
                  </div>
                  <div className="text-xs text-muted">
                    {searchProgress.step} {searchProgress.current}/{searchProgress.total}
                    {searchProgress.detail && ` — ${searchProgress.detail.length > 40 ? searchProgress.detail.slice(0, 40) + '...' : searchProgress.detail}`}
                  </div>
                </div>
              )}
            </div>
          )}

          {aiQueries.length > 0 && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted">AI 생성 검색어</label>
              <div className="flex flex-wrap gap-2">
                {aiQueries.map((q, i) => (
                  <span
                    key={i}
                    className="px-3 py-1 bg-surface border border-border rounded-full text-xs"
                  >
                    {q}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 파일 업로드 */}
      {videoSource === 'upload' && (
        <div className="space-y-4">
          <input
            ref={fileRef}
            type="file"
            accept="video/*"
            multiple
            className="hidden"
            onChange={(e) => e.target.files && handleUpload(e.target.files)}
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={loading}
            className="w-full p-8 border-2 border-dashed border-border rounded-lg text-center text-muted hover:border-primary hover:text-primary transition-colors"
          >
            {loading ? '업로드 중...' : '클릭하여 영상 파일 선택 (복수 가능)'}
          </button>
        </div>
      )}

      {/* 유튜브 URL */}
      {videoSource === 'youtube' && (
        <div className="space-y-4">
          {youtubeUrls.map((item, idx) => (
            <div key={idx} className="flex gap-2">
              <input
                type="text"
                value={item.url}
                onChange={(e) => updateUrlRow(idx, 'url', e.target.value)}
                placeholder="유튜브 URL"
                className="flex-1 px-3 py-2 bg-surface border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary text-sm"
              />
              <input
                type="text"
                value={item.name}
                onChange={(e) => updateUrlRow(idx, 'name', e.target.value)}
                placeholder="파일명"
                className="w-36 px-3 py-2 bg-surface border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary text-sm"
              />
              {youtubeUrls.length > 1 && (
                <button
                  onClick={() => removeUrlRow(idx)}
                  className="px-3 py-2 text-danger hover:bg-danger/10 rounded-lg transition-colors"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
          <div className="flex gap-3">
            <button
              onClick={addUrlRow}
              className="px-4 py-2 text-sm border border-border rounded-lg hover:bg-surface-hover transition-colors"
            >
              + URL 추가
            </button>
            <button
              onClick={handleYoutubeDownload}
              disabled={loading || youtubeUrls.every((u) => !u.url.trim())}
              className="px-4 py-2 text-sm bg-primary text-black rounded-lg hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '다운로드 중...' : '다운로드 시작'}
            </button>
          </div>
        </div>
      )}

      {/* 에러 */}
      {error && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger text-sm">
          {error}
        </div>
      )}

      {/* 영상 목록 */}
      {videos.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-muted">
            준비된 영상 ({videos.length}개)
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {videos.map((v, i) => (
              <div
                key={i}
                className="p-3 bg-surface border border-border rounded-lg text-sm"
              >
                <div className="font-medium truncate">{v.filename}</div>
                <div className="text-muted text-xs mt-1">
                  {v.width}x{v.height} · {v.duration.toFixed(1)}초 · {v.size_mb.toFixed(1)}MB
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 네비게이션 */}
      <div className="flex justify-between">
        <button
          onClick={onPrev}
          className="px-6 py-2.5 border border-border rounded-lg hover:bg-surface-hover transition-colors"
        >
          ← 이전
        </button>
        <button
          onClick={onNext}
          disabled={!canNext}
          className="px-6 py-2.5 bg-primary text-black font-medium rounded-lg hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          다음 단계 →
        </button>
      </div>
    </div>
  );
}
