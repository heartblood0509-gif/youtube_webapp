'use client';

import { useEffect, useState } from 'react';
import { getGallery, type GalleryVideo } from '@/lib/api';

const BACKEND = 'http://localhost:8000';

export default function Gallery({ onClose }: { onClose: () => void }) {
  const [videos, setVideos] = useState<GalleryVideo[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<GalleryVideo | null>(null);

  useEffect(() => {
    getGallery()
      .then((res) => setVideos(res.videos || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function formatDate(ts: number) {
    const d = new Date(ts * 1000);
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">완성 영상 갤러리</h2>
          <p className="text-muted text-sm mt-1">이전에 제작한 영상을 미리보기 및 다운로드할 수 있습니다.</p>
        </div>
        <button
          onClick={onClose}
          className="px-4 py-2 border border-border rounded-lg hover:bg-surface-hover transition-colors text-sm"
        >
          닫기
        </button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="text-muted animate-pulse">불러오는 중...</div>
        </div>
      )}

      {!loading && videos.length === 0 && (
        <div className="text-center py-16 text-muted">
          완성된 영상이 없습니다. 영상을 먼저 제작해주세요.
        </div>
      )}

      {/* 선택된 영상 플레이어 */}
      {selected && (
        <div className="p-4 bg-surface border border-primary/30 rounded-xl space-y-4">
          <div className="flex justify-center">
            <div className="w-full max-w-xs">
              <div
                className="relative rounded-xl overflow-hidden border border-border bg-black"
                style={{ aspectRatio: '9/16' }}
              >
                <video
                  key={selected.url}
                  src={`${BACKEND}${selected.url}`}
                  controls
                  autoPlay
                  playsInline
                  className="w-full h-full object-contain"
                />
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between text-sm">
            <div className="text-muted space-x-3">
              <span>{selected.width}x{selected.height}</span>
              <span>{selected.duration}s</span>
              <span>{selected.size_mb}MB</span>
            </div>
            <a
              href={`${BACKEND}${selected.url}`}
              download={selected.filename}
              className="px-4 py-1.5 bg-primary text-black font-medium rounded-lg hover:bg-primary-hover transition-colors text-sm"
            >
              다운로드
            </a>
          </div>
        </div>
      )}

      {/* 갤러리 그리드 */}
      {!loading && videos.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {videos.map((v) => {
            const isActive = selected?.url === v.url;
            return (
              <button
                key={v.url}
                onClick={() => setSelected(isActive ? null : v)}
                className={`group relative rounded-xl overflow-hidden border transition-all ${
                  isActive
                    ? 'border-primary ring-2 ring-primary/30'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                <div className="bg-black" style={{ aspectRatio: '9/16' }}>
                  <video
                    src={`${BACKEND}${v.url}#t=1`}
                    muted
                    playsInline
                    preload="metadata"
                    className="w-full h-full object-contain"
                    onMouseEnter={(e) => (e.target as HTMLVideoElement).play().catch(() => {})}
                    onMouseLeave={(e) => {
                      const el = e.target as HTMLVideoElement;
                      el.pause();
                      el.currentTime = 1;
                    }}
                  />
                </div>
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                  <div className="text-white text-xs font-medium">{v.duration}s / {v.size_mb}MB</div>
                  <div className="text-white/60 text-[10px]">{formatDate(v.created_at)}</div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
