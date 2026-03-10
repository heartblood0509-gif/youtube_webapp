'use client';

const STEPS = [
  '주제',
  '타이틀',
  '대본',
  '영상 소스',
  'TTS 설정',
  '빌드',
  '결과',
];

interface WizardLayoutProps {
  currentStep: number;
  children: React.ReactNode;
}

export default function WizardLayout({ currentStep, children }: WizardLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      {/* 헤더 */}
      <header className="border-b border-border px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <h1 className="text-xl font-bold">
            <span className="text-primary">YouTube Shorts</span> 자동 제작기
          </h1>
          <span className="text-sm text-muted">
            {currentStep + 1} / {STEPS.length} 단계
          </span>
        </div>
      </header>

      {/* 스텝 인디케이터 */}
      <nav className="border-b border-border px-6 py-3 overflow-x-auto">
        <div className="max-w-4xl mx-auto flex gap-1">
          {STEPS.map((label, i) => (
            <div
              key={i}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm whitespace-nowrap transition-colors ${
                i === currentStep
                  ? 'bg-primary/20 text-primary font-medium'
                  : i < currentStep
                    ? 'text-success'
                    : 'text-muted'
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                  i === currentStep
                    ? 'bg-primary text-black'
                    : i < currentStep
                      ? 'bg-success text-black'
                      : 'bg-surface-hover text-muted'
                }`}
              >
                {i < currentStep ? '✓' : i + 1}
              </span>
              <span className="hidden sm:inline">{label}</span>
            </div>
          ))}
        </div>
      </nav>

      {/* 콘텐츠 */}
      <main className="flex-1 px-6 py-8">
        <div className="max-w-4xl mx-auto">{children}</div>
      </main>
    </div>
  );
}
