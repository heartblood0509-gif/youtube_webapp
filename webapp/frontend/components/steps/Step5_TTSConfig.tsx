'use client';

import { useState, useEffect, useRef } from 'react';
import type { TTSEngine, VideoInfo, ClipConfig } from '@/types';
import { autoGenerateClips, smartGenerateClips, startBuild } from '@/lib/api';

const BACKEND = 'http://localhost:8000';

interface Props {
  projectId: string;
  geminiKey: string;
  title: string;
  script: string[];
  ttsEngine: TTSEngine;
  ttsLanguage: string;
  bgmVolume: number;
  videos: VideoInfo[];
  clips: ClipConfig[];
  videoSource?: string;
  onSetTTSEngine: (e: TTSEngine) => void;
  onSetTTSLanguage: (l: string) => void;
  onSetBgmVolume: (v: number) => void;
  onSetClips: (c: ClipConfig[]) => void;
  onStartBuild: (jobId: string) => void;
  onNext: () => void;
  onPrev: () => void;
}

const TTS_ENGINES: { value: TTSEngine; label: string; desc: string }[] = [
  { value: 'edge', label: 'Edge TTS', desc: '빠르고 무료, 기본 품질' },
  { value: 'typecast', label: 'Typecast', desc: '고품질 한국어 음성 (API 키 필요)' },
];

const LANGUAGES = [
  { value: 'ko', label: '한국어' },
  { value: 'en', label: '영어' },
  { value: 'ja', label: '일본어' },
];

export default function Step5_TTSConfig({
  projectId,
  geminiKey,
  title,
  script,
  ttsEngine,
  ttsLanguage,
  bgmVolume,
  videos,
  clips,
  videoSource,
  onSetTTSEngine,
  onSetTTSLanguage,
  onSetBgmVolume,
  onSetClips,
  onStartBuild,
  onNext,
  onPrev,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [autoClipsLoading, setAutoClipsLoading] = useState(false);
  const [smartClipsLoading, setSmartClipsLoading] = useState(false);
  const [clipMode, setClipMode] = useState<'none' | 'smart' | 'auto'>('none');
  const [previewIdx, setPreviewIdx] = useState<number | null>(null);

  const isVeo = videoSource === 'veo';
  const isImagen = videoSource === 'imagen';

  // Veo/Imagen 영상일 때 자동 클립 생성 (각 영상 = 1문장)
  useEffect(() => {
    if ((isVeo || isImagen) && clips.length === 0 && videos.length > 0) {
      const prefix = isVeo ? 'veo_' : 'imagen_';
      const matchedVideos = videos
        .filter(v => v.filename.startsWith(prefix))
        .sort((a, b) => a.filename.localeCompare(b.filename));
      if (matchedVideos.length > 0) {
        const autoClips: ClipConfig[] = matchedVideos.map(v => ({
          source: `input/${v.filename}`,
          start: 0,
          end: v.duration,
        }));
        onSetClips(autoClips);
        setClipMode('auto');
      }
    }
  }, [isVeo, isImagen, clips.length, videos, onSetClips]);

  async function handleSmartClips() {
    setSmartClipsLoading(true);
    setError('');
    try {
      const res = await smartGenerateClips(projectId, geminiKey, script);
      if (res.error) throw new Error(res.error);
      onSetClips(res.clips || []);
      setClipMode(res.smart ? 'smart' : 'auto');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'AI 스마트 클립 매칭 실패');
    } finally {
      setSmartClipsLoading(false);
    }
  }

  async function handleAutoClips() {
    setAutoClipsLoading(true);
    setError('');
    try {
      const res = await autoGenerateClips(projectId, script.length);
      if (res.error) throw new Error(res.error);
      onSetClips(res.clips || []);
      setClipMode('auto');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '클립 자동 생성 실패');
    } finally {
      setAutoClipsLoading(false);
    }
  }

  async function handleBuild() {
    setLoading(true);
    setError('');
    try {
      const buildClips = clips.length > 0 ? clips : undefined;
      if (!buildClips || buildClips.length === 0) {
        throw new Error('클립을 먼저 생성하세요.');
      }
      const res = await startBuild({
        project_id: projectId,
        title_text: title,
        narration_sentences: script,
        tts_engine: ttsEngine,
        tts_speed: 1.0,
        tts_language: ttsLanguage,
        bgm_volume: bgmVolume,
        clips: buildClips,
      });
      if (res.error) throw new Error(res.error);
      onStartBuild(res.job_id);
      onNext();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '빌드 시작 실패');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold mb-2">TTS 설정 & 빌드 준비</h2>
        <p className="text-muted">음성 엔진을 선택하고 영상 빌드를 시작하세요.</p>
      </div>

      {/* TTS 엔진 */}
      <div className="space-y-3">
        <label className="text-sm font-medium text-muted">TTS 엔진</label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {TTS_ENGINES.map((eng) => (
            <button
              key={eng.value}
              onClick={() => onSetTTSEngine(eng.value)}
              className={`p-4 rounded-lg border text-left transition-all ${
                ttsEngine === eng.value
                  ? 'border-primary bg-primary/10 ring-1 ring-primary'
                  : 'border-border bg-surface hover:bg-surface-hover'
              }`}
            >
              <div className="font-medium">{eng.label}</div>
              <div className="text-xs text-muted mt-1">{eng.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 언어 */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-muted">언어</label>
        <div className="flex gap-2">
          {LANGUAGES.map((lang) => (
            <button
              key={lang.value}
              onClick={() => onSetTTSLanguage(lang.value)}
              className={`px-4 py-2 rounded-lg border text-sm transition-all ${
                ttsLanguage === lang.value
                  ? 'border-primary bg-primary/10'
                  : 'border-border bg-surface hover:bg-surface-hover'
              }`}
            >
              {lang.label}
            </button>
          ))}
        </div>
      </div>

      {/* BGM 볼륨 */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-muted">
          BGM 볼륨: {bgmVolume.toFixed(1)}
        </label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.1}
          value={bgmVolume}
          onChange={(e) => onSetBgmVolume(parseFloat(e.target.value))}
          className="w-full accent-primary"
        />
        <div className="flex justify-between text-xs text-muted">
          <span>음소거</span>
          <span>최대</span>
        </div>
      </div>

      {/* 클립 매칭 */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-muted">
              영상 클립 ({clips.length}개)
            </label>
            {clipMode !== 'none' && clips.length > 0 && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                clipMode === 'smart'
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-zinc-500/20 text-zinc-400'
              }`}>
                {clipMode === 'smart' ? 'AI 매칭' : '순서 분배'}
              </span>
            )}
          </div>
          {!isVeo && !isImagen && (
            <div className="flex gap-2">
              <button
                onClick={handleSmartClips}
                disabled={smartClipsLoading || autoClipsLoading || videos.length === 0 || !geminiKey}
                className="text-sm px-4 py-1.5 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 disabled:opacity-40 transition-colors"
              >
                {smartClipsLoading ? 'AI 분석 중...' : 'AI 스마트 매칭'}
              </button>
              <button
                onClick={handleAutoClips}
                disabled={autoClipsLoading || smartClipsLoading || videos.length === 0}
                className="text-sm px-4 py-1.5 bg-surface border border-border text-foreground rounded-lg hover:bg-surface-hover disabled:opacity-40 transition-colors"
              >
                {autoClipsLoading ? '생성 중...' : '자동 분배'}
              </button>
            </div>
          )}
          {isVeo && clips.length > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 font-medium">
              Veo AI 자동 매칭
            </span>
          )}
          {isImagen && clips.length > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400 font-medium">
              Imagen AI 자동 매칭
            </span>
          )}
        </div>

        {/* 스마트 매칭 설명 */}
        {clipMode === 'smart' && clips.length > 0 && (
          <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-xs text-emerald-400">
            Gemini Vision이 영상 장면을 분석하여 각 문장에 맞는 클립을 매칭했습니다.
          </div>
        )}

        {clips.length > 0 && (
          <div className="space-y-2 max-h-[500px] overflow-y-auto">
            {clips.map((clip, i) => {
              const videoUrl = `${BACKEND}/files/${projectId}/${clip.source}`;
              const isOpen = previewIdx === i;
              return (
                <div
                  key={i}
                  className={`rounded-lg border text-xs overflow-hidden ${
                    clipMode === 'smart'
                      ? 'bg-emerald-500/5 border-emerald-500/20'
                      : 'bg-surface border-border'
                  }`}
                >
                  <div
                    className="p-3 cursor-pointer hover:bg-white/5 transition-colors"
                    onClick={() => setPreviewIdx(isOpen ? null : i)}
                  >
                    {/* 문장 */}
                    {script[i] && (
                      <div className="text-foreground mb-1.5 text-sm leading-snug">
                        <span className="text-muted mr-1.5">{i + 1}.</span>
                        {script[i].length > 50 ? script[i].slice(0, 50) + '...' : script[i]}
                      </div>
                    )}
                    {/* 매칭된 영상 구간 */}
                    <div className="flex items-center gap-2 text-muted">
                      <span className="text-primary/80">{isOpen ? '▾' : '▸'} 미리보기</span>
                      <span className="truncate">{clip.source.replace('input/', '')}</span>
                      <span className="shrink-0">{clip.start.toFixed(1)}s ~ {clip.end.toFixed(1)}s</span>
                    </div>
                  </div>
                  {/* 비디오 미리보기 */}
                  {isOpen && (
                    <div className="px-3 pb-3">
                      <div className="rounded-lg overflow-hidden bg-black border border-border/50"
                        style={{ maxHeight: '280px' }}
                      >
                        <video
                          src={`${videoUrl}#t=${clip.start}`}
                          controls
                          playsInline
                          autoPlay
                          muted
                          className="w-full h-full object-contain"
                          style={{ maxHeight: '280px' }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 요약 */}
      <div className="p-4 bg-surface border border-border rounded-lg space-y-2 text-sm">
        <div className="font-medium mb-2">빌드 요약</div>
        <div className="flex justify-between">
          <span className="text-muted">타이틀</span>
          <span className="text-primary">{title}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">나레이션</span>
          <span>{script.length}개 문장</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">TTS</span>
          <span>{ttsEngine === 'edge' ? 'Edge TTS' : 'Typecast'} ({LANGUAGES.find(l => l.value === ttsLanguage)?.label})</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">클립</span>
          <span>
            {clips.length}개
            {clipMode === 'smart' && <span className="ml-1 text-emerald-400">(AI 매칭)</span>}
            {clipMode === 'auto' && <span className="ml-1 text-zinc-400">(순서 분배)</span>}
          </span>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger text-sm">
          {error}
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
          onClick={handleBuild}
          disabled={loading || clips.length === 0}
          className="px-8 py-2.5 bg-primary text-black font-bold rounded-lg hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-lg"
        >
          {loading ? '시작 중...' : '영상 제작 시작'}
        </button>
      </div>
    </div>
  );
}
