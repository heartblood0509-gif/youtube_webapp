'use client';

import { useState, useCallback } from 'react';
import type { AppState, Category, TTSEngine, VideoInfo, ClipConfig, BuildProgressEvent, VideoResult } from '@/types';
import WizardLayout from '@/components/WizardLayout';
import Step1_Category from '@/components/steps/Step1_Category';
import Step2_VideoSource from '@/components/steps/Step2_VideoSource';
import Step3_TitleSelect from '@/components/steps/Step3_TitleSelect';
import Step4_ScriptReview from '@/components/steps/Step4_ScriptReview';
import Step5_TTSConfig from '@/components/steps/Step5_TTSConfig';
import Step6_Building from '@/components/steps/Step6_Building';
import Step7_Result from '@/components/steps/Step7_Result';

const INITIAL_STATE: AppState = {
  geminiKey: process.env.NEXT_PUBLIC_GEMINI_KEY || '',
  pexelsKey: process.env.NEXT_PUBLIC_PEXELS_KEY || '',
  currentStep: 0,
  projectId: null,
  category: 'cruise',
  topic: '',
  videoSource: 'pexels',
  videos: [],
  youtubeUrls: [{ url: '', name: '' }],
  generatedTitles: [],
  selectedTitle: '',
  generatedScript: [],
  ttsEngine: 'edge',
  ttsLanguage: 'ko',
  bgmVolume: 0.3,
  clips: [],
  buildJobId: null,
  buildStatus: 'idle',
  buildProgress: [],
  result: null,
};

// 새 순서: 주제(0) → 타이틀(1) → 대본(2) → 영상소스(3) → TTS(4) → 빌드(5) → 결과(6)

export default function Home() {
  const [state, setState] = useState<AppState>(INITIAL_STATE);

  const update = useCallback(<K extends keyof AppState>(key: K, value: AppState[K]) => {
    setState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const goTo = useCallback((step: number) => {
    setState((prev) => ({ ...prev, currentStep: step }));
  }, []);

  const handleProgressEvent = useCallback((event: BuildProgressEvent) => {
    setState((prev) => ({
      ...prev,
      buildProgress: [...prev.buildProgress, event],
      buildStatus: event.type === 'done' ? 'done' : event.type === 'error' ? 'error' : 'building',
      result: event.result || prev.result,
    }));
  }, []);

  const handleReset = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  return (
    <WizardLayout currentStep={state.currentStep}>
      {/* API 키 상태 표시 (env에 키가 없을 때만 입력 필드 노출) */}
      {state.currentStep < 5 && (
        <div className="mb-6 p-3 bg-surface border border-border rounded-lg space-y-2">
          {process.env.NEXT_PUBLIC_GEMINI_KEY ? (
            <div className="flex items-center gap-3">
              <label className="text-sm text-muted whitespace-nowrap w-28">Gemini API</label>
              <span className="text-success text-xs">환경변수에서 로드됨</span>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <label className="text-sm text-muted whitespace-nowrap w-28">Gemini API 키</label>
              <input
                type="text"
                autoComplete="off"
                data-1p-ignore
                value={state.geminiKey}
                onChange={(e) => update('geminiKey', e.target.value)}
                placeholder="Gemini API 키 (타이틀/대본 생성용)"
                className="flex-1 px-3 py-1.5 bg-background border border-border rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
              {state.geminiKey && (
                <span className="text-success text-xs">연결됨</span>
              )}
            </div>
          )}
          {process.env.NEXT_PUBLIC_PEXELS_KEY ? (
            <div className="flex items-center gap-3">
              <label className="text-sm text-muted whitespace-nowrap w-28">Pexels API</label>
              <span className="text-success text-xs">환경변수에서 로드됨</span>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <label className="text-sm text-muted whitespace-nowrap w-28">Pexels API 키</label>
              <input
                type="text"
                autoComplete="off"
                data-1p-ignore
                value={state.pexelsKey}
                onChange={(e) => update('pexelsKey', e.target.value)}
                placeholder="Pexels API 키 (무료 스톡영상 검색용)"
                className="flex-1 px-3 py-1.5 bg-background border border-border rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
              {state.pexelsKey && (
                <span className="text-success text-xs">연결됨</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Step 0: 주제 */}
      {state.currentStep === 0 && (
        <Step1_Category
          category={state.category}
          topic={state.topic}
          onChange={(field, value) => update(field, value as Category & string)}
          onNext={() => goTo(1)}
        />
      )}

      {/* Step 1: 타이틀 */}
      {state.currentStep === 1 && (
        <Step3_TitleSelect
          geminiKey={state.geminiKey}
          category={state.category}
          topic={state.topic}
          generatedTitles={state.generatedTitles}
          selectedTitle={state.selectedTitle}
          onSetTitles={(t: string[]) => update('generatedTitles', t)}
          onSelectTitle={(t: string) => update('selectedTitle', t)}
          onNext={() => goTo(2)}
          onPrev={() => goTo(0)}
        />
      )}

      {/* Step 2: 대본 (수락/다시 작성) */}
      {state.currentStep === 2 && (
        <Step4_ScriptReview
          geminiKey={state.geminiKey}
          category={state.category}
          topic={state.topic}
          title={state.selectedTitle}
          generatedScript={state.generatedScript}
          onSetScript={(s: string[]) => update('generatedScript', s)}
          onNext={() => goTo(3)}
          onPrev={() => goTo(1)}
        />
      )}

      {/* Step 3: 영상 소스 (AI 자동 검색 / 직접 업로드 / URL) */}
      {state.currentStep === 3 && (
        <Step2_VideoSource
          geminiKey={state.geminiKey}
          pexelsKey={state.pexelsKey}
          projectId={state.projectId}
          category={state.category}
          topic={state.topic}
          script={state.generatedScript}
          videoSource={state.videoSource}
          videos={state.videos}
          youtubeUrls={state.youtubeUrls}
          onChangeSource={(s) => update('videoSource', s)}
          onSetProjectId={(id) => update('projectId', id)}
          onSetVideos={(v: VideoInfo[]) => update('videos', v)}
          onSetYoutubeUrls={(u: { url: string; name: string }[]) => update('youtubeUrls', u)}
          onNext={() => goTo(4)}
          onPrev={() => goTo(2)}
        />
      )}

      {/* Step 4: TTS 설정 */}
      {state.currentStep === 4 && (
        <Step5_TTSConfig
          projectId={state.projectId!}
          geminiKey={state.geminiKey}
          title={state.selectedTitle}
          script={state.generatedScript}
          ttsEngine={state.ttsEngine}
          ttsLanguage={state.ttsLanguage}
          bgmVolume={state.bgmVolume}
          videos={state.videos}
          clips={state.clips}
          onSetTTSEngine={(e: TTSEngine) => update('ttsEngine', e)}
          onSetTTSLanguage={(l: string) => update('ttsLanguage', l)}
          onSetBgmVolume={(v: number) => update('bgmVolume', v)}
          onSetClips={(c: ClipConfig[]) => update('clips', c)}
          onStartBuild={(jobId: string) => {
            update('buildJobId', jobId);
            update('buildStatus', 'building');
          }}
          onNext={() => goTo(5)}
          onPrev={() => goTo(3)}
        />
      )}

      {/* Step 5: 빌드 */}
      {state.currentStep === 5 && state.buildJobId && (
        <Step6_Building
          jobId={state.buildJobId}
          buildProgress={state.buildProgress}
          onProgressEvent={handleProgressEvent}
          onDone={() => goTo(6)}
        />
      )}

      {/* Step 6: 결과 */}
      {state.currentStep === 6 && state.projectId && (
        <Step7_Result
          projectId={state.projectId}
          result={state.result}
          onSetResult={(r: VideoResult) => update('result', r)}
          onReset={handleReset}
        />
      )}
    </WizardLayout>
  );
}
