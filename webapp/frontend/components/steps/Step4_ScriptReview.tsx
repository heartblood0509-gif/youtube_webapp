'use client';

import { useState } from 'react';
import { callGemini } from '@/lib/gemini';
import { buildScriptPrompt } from '@/lib/prompts';

interface Props {
  geminiKey: string;
  category: string;
  topic: string;
  title: string;
  generatedScript: string[];
  onSetScript: (s: string[]) => void;
  onNext: () => void;
  onPrev: () => void;
}

export default function Step4_ScriptReview({
  geminiKey,
  category,
  topic,
  title,
  generatedScript,
  onSetScript,
  onNext,
  onPrev,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  async function generateScript() {
    if (!geminiKey) {
      setError('Gemini API 키를 입력하세요.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const prompt = buildScriptPrompt(category, topic, title);
      const raw = await callGemini(geminiKey, prompt);
      const jsonMatch = raw.match(/\{[\s\S]*\}/);
      if (!jsonMatch) throw new Error('JSON 파싱 실패');
      const parsed = JSON.parse(jsonMatch[0]);
      const sentences: string[] = parsed.sentences || [];
      if (sentences.length === 0) throw new Error('생성된 대본이 없습니다');
      onSetScript(sentences);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '대본 생성 실패');
    } finally {
      setLoading(false);
    }
  }

  function startEdit(idx: number) {
    setEditIdx(idx);
    setEditValue(generatedScript[idx]);
  }

  function saveEdit() {
    if (editIdx === null) return;
    const updated = [...generatedScript];
    updated[editIdx] = editValue;
    onSetScript(updated);
    setEditIdx(null);
  }

  function removeSentence(idx: number) {
    onSetScript(generatedScript.filter((_, i) => i !== idx));
  }

  function addSentence() {
    onSetScript([...generatedScript, '']);
    setEditIdx(generatedScript.length);
    setEditValue('');
  }

  const canNext = generatedScript.length >= 3;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold mb-2">나레이션 대본</h2>
        <p className="text-muted">
          AI가 나레이션 대본을 생성합니다. 각 문장을 수정하거나 삭제할 수 있습니다.
        </p>
      </div>

      {/* 타이틀 표시 */}
      <div className="p-3 bg-surface border border-border rounded-lg">
        <span className="text-xs text-muted">타이틀: </span>
        <span className="text-primary font-medium">{title}</span>
      </div>

      {/* 생성 버튼 */}
      <button
        onClick={generateScript}
        disabled={loading}
        className="w-full py-3 bg-primary text-black font-medium rounded-lg hover:bg-primary-hover disabled:opacity-40 transition-colors"
      >
        {loading ? 'AI가 대본 생성 중...' : generatedScript.length > 0 ? '대본 다시 생성' : 'AI 대본 생성'}
      </button>

      {error && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger text-sm">
          {error}
        </div>
      )}

      {/* 대본 문장 목록 */}
      {generatedScript.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-muted">
              나레이션 ({generatedScript.length}개 문장)
            </label>
            <button
              onClick={addSentence}
              className="text-xs px-3 py-1 border border-border rounded hover:bg-surface-hover transition-colors"
            >
              + 문장 추가
            </button>
          </div>
          {generatedScript.map((sentence, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="w-6 h-8 flex items-center justify-center text-xs text-muted shrink-0">
                {i + 1}
              </span>
              {editIdx === i ? (
                <div className="flex-1 flex gap-2">
                  <input
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && saveEdit()}
                    autoFocus
                    className="flex-1 px-3 py-1.5 bg-surface border border-primary rounded text-sm focus:outline-none"
                  />
                  <button
                    onClick={saveEdit}
                    className="px-3 py-1.5 text-xs bg-primary text-black rounded hover:bg-primary-hover transition-colors"
                  >
                    저장
                  </button>
                </div>
              ) : (
                <div className="flex-1 flex items-center gap-2 group">
                  <div
                    className="flex-1 px-3 py-1.5 bg-surface border border-border rounded text-sm cursor-pointer hover:border-primary transition-colors"
                    onClick={() => startEdit(i)}
                  >
                    {sentence}
                    <span className="ml-2 text-xs text-muted">({sentence.length}자)</span>
                  </div>
                  <button
                    onClick={() => removeSentence(i)}
                    className="opacity-0 group-hover:opacity-100 px-2 py-1 text-danger text-xs hover:bg-danger/10 rounded transition-all"
                  >
                    삭제
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 수락 / 다시 작성 */}
      {generatedScript.length > 0 && (
        <div className="flex gap-3 justify-center">
          <button
            onClick={generateScript}
            disabled={loading}
            className="px-6 py-2.5 border border-border rounded-lg hover:bg-surface-hover disabled:opacity-40 transition-colors"
          >
            {loading ? '생성 중...' : '다시 작성하기'}
          </button>
          <button
            onClick={onNext}
            disabled={!canNext}
            className="px-8 py-2.5 bg-primary text-black font-bold rounded-lg hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            대본 수락
          </button>
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
        {generatedScript.length === 0 && (
          <button
            onClick={onNext}
            disabled={!canNext}
            className="px-6 py-2.5 bg-primary text-black font-medium rounded-lg hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            다음 단계 →
          </button>
        )}
      </div>
    </div>
  );
}
