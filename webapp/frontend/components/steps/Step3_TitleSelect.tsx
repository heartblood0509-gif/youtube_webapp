'use client';

import { useState } from 'react';
import { callGemini } from '@/lib/gemini';
import { buildTitlePrompt } from '@/lib/prompts';

interface Props {
  geminiKey: string;
  category: string;
  topic: string;
  generatedTitles: string[];
  selectedTitle: string;
  onSetTitles: (t: string[]) => void;
  onSelectTitle: (t: string) => void;
  onNext: () => void;
  onPrev: () => void;
}

export default function Step3_TitleSelect({
  geminiKey,
  category,
  topic,
  generatedTitles,
  selectedTitle,
  onSetTitles,
  onSelectTitle,
  onNext,
  onPrev,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [customTitle, setCustomTitle] = useState('');

  async function generateTitles() {
    if (!geminiKey) {
      setError('Gemini API 키를 입력하세요.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const prompt = buildTitlePrompt(category, topic);
      const raw = await callGemini(geminiKey, prompt);
      const jsonMatch = raw.match(/\{[\s\S]*\}/);
      if (!jsonMatch) throw new Error('JSON 파싱 실패');
      const parsed = JSON.parse(jsonMatch[0]);
      const titles: string[] = parsed.titles || [];
      if (titles.length === 0) throw new Error('생성된 타이틀이 없습니다');
      onSetTitles(titles);
      onSelectTitle(titles[0]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '타이틀 생성 실패');
    } finally {
      setLoading(false);
    }
  }

  function handleCustomTitle() {
    if (customTitle.trim()) {
      onSelectTitle(customTitle.trim());
    }
  }

  const canNext = selectedTitle.length > 0;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold mb-2">타이틀 선택</h2>
        <p className="text-muted">
          AI가 후킹 타이틀을 생성합니다. 마음에 드는 것을 선택하거나 직접 입력하세요.
        </p>
      </div>

      {/* 생성 버튼 */}
      <button
        onClick={generateTitles}
        disabled={loading}
        className="w-full py-3 bg-primary text-black font-medium rounded-lg hover:bg-primary-hover disabled:opacity-40 transition-colors"
      >
        {loading ? 'AI가 타이틀 생성 중...' : generatedTitles.length > 0 ? '다시 생성하기' : 'AI 타이틀 생성'}
      </button>

      {error && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger text-sm">
          {error}
        </div>
      )}

      {/* 생성된 타이틀 */}
      {generatedTitles.length > 0 && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-muted">생성된 타이틀</label>
          {generatedTitles.map((title, i) => (
            <button
              key={i}
              onClick={() => onSelectTitle(title)}
              className={`w-full p-4 text-left rounded-lg border transition-all ${
                selectedTitle === title
                  ? 'border-primary bg-primary/10 ring-1 ring-primary'
                  : 'border-border bg-surface hover:bg-surface-hover'
              }`}
            >
              <span className="text-lg">{title}</span>
              <span className="ml-2 text-xs text-muted">({title.length}자)</span>
            </button>
          ))}
        </div>
      )}

      {/* 직접 입력 */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-muted">또는 직접 입력</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={customTitle}
            onChange={(e) => setCustomTitle(e.target.value)}
            placeholder="직접 타이틀 입력..."
            className="flex-1 px-4 py-2.5 bg-surface border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button
            onClick={handleCustomTitle}
            disabled={!customTitle.trim()}
            className="px-4 py-2.5 border border-border rounded-lg hover:bg-surface-hover disabled:opacity-40 transition-colors"
          >
            적용
          </button>
        </div>
      </div>

      {/* 선택된 타이틀 */}
      {selectedTitle && (
        <div className="p-4 bg-primary/5 border border-primary/30 rounded-lg">
          <div className="text-xs text-muted mb-1">선택된 타이틀</div>
          <div className="text-xl font-bold text-primary">{selectedTitle}</div>
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
