'use client';

import type { Category } from '@/types';

interface Props {
  category: Category;
  topic: string;
  onChange: (field: 'category' | 'topic', value: string) => void;
  onNext: () => void;
}

const CATEGORIES: { value: Category; label: string; desc: string }[] = [
  { value: 'cosmetics_info', label: '화장품 정보성', desc: '증상 공감 → 오해 지적 → 근본 원인 → 해결 원리' },
  { value: 'cosmetics_ad', label: '화장품 광고성', desc: '극단적 공감 → 성분 소개 → 제품 공개 → 감성 CTA' },
  { value: 'cruise', label: '크루즈 여행', desc: '경험/모험 강조, 놀라움 유발' },
  { value: 'other', label: '기타 주제', desc: '궁금증 유발, 명령형, 숫자 활용' },
];

export default function Step1_Category({ category, topic, onChange, onNext }: Props) {
  const canNext = topic.trim().length > 0;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold mb-2">카테고리 & 주제 선택</h2>
        <p className="text-muted">영상의 카테고리를 선택하고 주제를 입력하세요.</p>
      </div>

      {/* 카테고리 선택 */}
      <div className="space-y-3">
        <label className="text-sm font-medium text-muted">카테고리</label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              onClick={() => onChange('category', cat.value)}
              className={`p-4 rounded-lg border text-left transition-all ${
                category === cat.value
                  ? 'border-primary bg-primary/10 ring-1 ring-primary'
                  : 'border-border bg-surface hover:bg-surface-hover'
              }`}
            >
              <div className="font-medium mb-1">{cat.label}</div>
              <div className="text-xs text-muted">{cat.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 주제 입력 */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-muted">주제</label>
        <input
          type="text"
          value={topic}
          onChange={(e) => onChange('topic', e.target.value)}
          placeholder="예: 크루즈 액티비티, 여드름 패치 추천"
          className="w-full px-4 py-3 bg-surface border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent placeholder:text-zinc-600"
        />
      </div>

      {/* 다음 버튼 */}
      <div className="flex justify-end">
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
