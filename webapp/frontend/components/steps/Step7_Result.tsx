'use client';

import { useEffect, useState } from 'react';
import type { VideoResult } from '@/types';
import { getBuildResult } from '@/lib/api';

const BACKEND = 'http://localhost:8000';

interface Props {
  projectId: string;
  result: VideoResult | null;
  onSetResult: (r: VideoResult) => void;
  onReset: () => void;
}

export default function Step7_Result({ projectId, result, onSetResult, onReset }: Props) {
  const [loading, setLoading] = useState(!result);

  useEffect(() => {
    if (result) return;
    async function fetch_result() {
      try {
        const res = await getBuildResult(projectId);
        if (res.result) {
          onSetResult(res.result);
        }
      } catch {
        // 재시도
      } finally {
        setLoading(false);
      }
    }
    fetch_result();
  }, [projectId, result, onSetResult]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-muted">결과를 불러오는 중...</div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="space-y-8">
        <div className="p-6 bg-danger/10 border border-danger/30 rounded-lg text-center">
          <div className="text-danger text-xl font-bold mb-2">결과를 찾을 수 없습니다</div>
          <div className="text-muted text-sm">빌드가 실패했거나 결과 파일을 찾을 수 없습니다.</div>
        </div>
        <div className="flex justify-center">
          <button
            onClick={onReset}
            className="px-6 py-2.5 bg-primary text-black font-medium rounded-lg hover:bg-primary-hover transition-colors"
          >
            처음부터 다시 시작
          </button>
        </div>
      </div>
    );
  }

  const fileUrl = result.url || `/files/${projectId}/output/${result.filename}`;
  const videoUrl = fileUrl.startsWith('http') ? fileUrl : `${BACKEND}${fileUrl}`;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold mb-2">영상 완성!</h2>
        <p className="text-muted">YouTube Shorts 영상이 성공적으로 제작되었습니다.</p>
      </div>

      {/* 영상 플레이어 */}
      <div className="flex justify-center">
        <div className="w-full max-w-sm">
          <div className="relative rounded-xl overflow-hidden border border-border bg-black"
            style={{ aspectRatio: '9/16' }}
          >
            <video
              src={videoUrl}
              controls
              className="w-full h-full object-contain"
              playsInline
            />
          </div>
        </div>
      </div>

      {/* 영상 정보 */}
      <div className="p-4 bg-surface border border-border rounded-lg space-y-2 text-sm">
        <div className="font-medium mb-2">영상 정보</div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="text-muted">파일명: </span>
            <span>{result.filename}</span>
          </div>
          <div>
            <span className="text-muted">해상도: </span>
            <span>{result.width}x{result.height}</span>
          </div>
          <div>
            <span className="text-muted">길이: </span>
            <span>{result.duration.toFixed(1)}초</span>
          </div>
          <div>
            <span className="text-muted">크기: </span>
            <span>{result.size_mb.toFixed(1)}MB</span>
          </div>
        </div>
      </div>

      {/* 액션 버튼 */}
      <div className="flex gap-4 justify-center">
        <a
          href={videoUrl}
          download={result.filename}
          className="px-8 py-3 bg-primary text-black font-bold rounded-lg hover:bg-primary-hover transition-colors text-lg"
        >
          다운로드
        </a>
        <button
          onClick={onReset}
          className="px-8 py-3 border border-border rounded-lg hover:bg-surface-hover transition-colors"
        >
          새 영상 제작
        </button>
      </div>
    </div>
  );
}
