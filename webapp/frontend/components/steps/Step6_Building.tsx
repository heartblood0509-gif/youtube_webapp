'use client';

import { useEffect, useRef } from 'react';
import type { BuildProgressEvent } from '@/types';
import { subscribeBuildProgress } from '@/lib/api';

interface Props {
  jobId: string;
  buildProgress: BuildProgressEvent[];
  onProgressEvent: (e: BuildProgressEvent) => void;
  onDone: () => void;
}

export default function Step6_Building({ jobId, buildProgress, onProgressEvent, onDone }: Props) {
  const onProgressRef = useRef(onProgressEvent);
  const onDoneRef = useRef(onDone);
  onProgressRef.current = onProgressEvent;
  onDoneRef.current = onDone;

  useEffect(() => {
    if (!jobId) return;

    const source = subscribeBuildProgress(jobId, (event) => {
      onProgressRef.current(event);
      if (event.type === 'done') {
        setTimeout(() => onDoneRef.current(), 1000);
      }
    });

    return () => {
      source.close();
    };
  }, [jobId]);

  const latestEvent = buildProgress[buildProgress.length - 1];
  const percent = latestEvent?.progress_percent ?? 0;
  const isDone = latestEvent?.type === 'done';
  const isError = latestEvent?.type === 'error';

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold mb-2">영상 제작 중</h2>
        <p className="text-muted">잠시만 기다려 주세요. 영상을 빌드하고 있습니다.</p>
      </div>

      {/* 프로그레스 바 */}
      <div className="space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-muted">진행률</span>
          <span className={isDone ? 'text-success font-bold' : isError ? 'text-danger' : 'text-primary'}>
            {Math.round(percent)}%
          </span>
        </div>
        <div className="w-full h-3 bg-surface border border-border rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isDone ? 'bg-success' : isError ? 'bg-danger' : 'bg-primary progress-pulse'
            }`}
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      {/* 현재 단계 */}
      {latestEvent && (
        <div className={`p-4 rounded-lg border ${
          isDone ? 'bg-success/10 border-success/30' :
          isError ? 'bg-danger/10 border-danger/30' :
          'bg-surface border-border'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
              isDone ? 'bg-success text-black' :
              isError ? 'bg-danger text-white' :
              'bg-primary text-black'
            }`}>
              {isDone ? '✓' : isError ? '!' : latestEvent.step_number}
            </div>
            <div>
              <div className="font-medium">
                {isDone ? '완료!' : isError ? '오류 발생' : latestEvent.step}
              </div>
              <div className="text-sm text-muted">{latestEvent.message}</div>
            </div>
          </div>
        </div>
      )}

      {/* 빌드 로그 */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-muted">빌드 로그</label>
        <div className="max-h-60 overflow-y-auto bg-surface border border-border rounded-lg p-3 space-y-1">
          {buildProgress.filter(e => e.type !== 'heartbeat').map((event, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span className={`shrink-0 ${
                event.type === 'done' ? 'text-success' :
                event.type === 'error' ? 'text-danger' :
                'text-primary'
              }`}>
                {event.type === 'done' ? '✓' : event.type === 'error' ? '✕' : '▸'}
              </span>
              <span className="text-muted">
                [{event.step_number}/{event.total_steps}]
              </span>
              <span>{event.message}</span>
            </div>
          ))}
          {!isDone && !isError && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <span className="animate-pulse">●</span> 진행 중...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
