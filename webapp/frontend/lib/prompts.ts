export function buildTitlePrompt(category: string, topic: string): string {
  const categoryGuide: Record<string, string> = {
    cosmetics: '화장품/스킨케어 - "이거 안 바르면 손해", 성분 폭로, 충격 비교, 뷰티 업계 비밀',
    cruise: '크루즈 여행 - "이 가격 실화?", 충격 후기, 숨겨진 꿀팁, 럭셔리 체험',
    other: '일반 주제 - 충격 반전, 비밀 폭로, "아직도 모름?", 경고성 제목',
  };

  return `당신은 유튜브 쇼츠 바이럴 제목 전문가입니다. 스크롤을 멈추게 만드는 제목만 만듭니다.

카테고리: ${category}
주제: ${topic}
톤: ${categoryGuide[category] || categoryGuide.other}

=== 반드시 지켜야 할 글자수 규칙 ===
- 띄어쓰기를 제외한 순수 글자수가 16자 이하여야 합니다
- 예시: "이거 모르면 손해봄" → 띄어쓰기 제외 9자 ✅
- 예시: "크루즈 100만원에 가는 법" → 띄어쓰기 제외 12자 ✅
- 16자 초과 시 무조건 탈락

=== 후킹 기법 (반드시 1개 이상 활용) ===
1. 충격/경고: "절대 하지마", "큰일남", "난리났다"
2. 비밀 폭로: "아무도 안 알려주는", "업계 비밀"
3. FOMO: "이거 모르면 손해", "지금 안 하면 늦음"
4. 궁금증 유발: "이게 된다고?", "왜 아무도 안 함?"
5. 숫자 활용: "3가지 이유", "1분만에", "100만원"
6. 반전/의외: "알고보니", "진짜 이유는"
7. 명령형: "당장 확인해", "지금 바꿔"

=== 나쁜 예시 (절대 이렇게 쓰지 마세요) ===
- "크루즈 여행의 매력" ❌ (밋밋함, 클릭 욕구 0)
- "화장품 추천 영상" ❌ (검색어지 제목이 아님)
- "아름다운 바다 풍경" ❌ (감상문, 후킹 없음)

=== 좋은 예시 ===
- "크루즈 50만원이면 됨" ✅ (충격 가격)
- "이 성분 피부 망침" ✅ (경고 + 궁금증)
- "여행사가 숨기는 것" ✅ (비밀 폭로)
- "이거 안 보면 후회함" ✅ (FOMO)

4개의 제목을 JSON으로 반환하세요. 각 제목은 띄어쓰기 제외 16자 이내:
{"titles": ["제목1", "제목2", "제목3", "제목4"]}`;
}

export function buildScriptPrompt(
  category: string,
  topic: string,
  title: string,
): string {
  return `당신은 한국 유튜브 쇼츠 나레이션 대본 작가입니다.

제목: ${title}
카테고리: ${category}
주제: ${topic}

규칙:
- 7~10개의 짧은 문장
- 각 문장은 20자 이내 (자막 가독성)
- 쉼표로 자연스러운 끊김점 확보
- 구조: 후킹(공감) → 문제/맥락 → 상세 → CTA
- 한국어, 대화체
- 긴 문장은 반드시 쉼표로 분할

JSON으로 반환하세요:
{"sentences": ["문장1", "문장2", "문장3", ...]}`;
}

export function buildPexelsKeywordPrompt(
  category: string,
  topic: string,
  sentences: string[],
): string {
  return `You are a stock footage keyword expert for Pexels.

Category: ${category}
Topic: ${topic}
Script:
${sentences.map((s, i) => `${i + 1}. ${s}`).join('\n')}

Generate simple English keywords for searching FREE stock videos on Pexels.

Rules:
- Generate exactly 5 keywords
- Each keyword should be 2-3 words maximum
- Use simple, visual nouns (e.g., "ocean waves", "city skyline", "sunset beach")
- Do NOT use technical terms like "4K", "cinematic", "footage", "B-roll"
- Do NOT use abstract concepts - only concrete, filmable subjects
- Keywords should cover different visual scenes from the script
- Prioritize landscape/scenic shots

Return JSON:
{"keywords": ["keyword 1", "keyword 2", "keyword 3", "keyword 4", "keyword 5"]}`;
}

export function buildSearchQueryPrompt(
  category: string,
  topic: string,
  sentences: string[],
): string {
  return `당신은 유튜브 영상 소스 검색 전문가입니다.

아래 나레이션 대본에 어울리는 유튜브 B-roll 영상을 찾기 위한 검색어를 생성하세요.

카테고리: ${category}
주제: ${topic}
대본:
${sentences.map((s, i) => `${i + 1}. ${s}`).join('\n')}

규칙:
- 대본의 전체 흐름을 포괄하는 대표 검색어를 생성
- 검색어는 영어로 작성 (유튜브 영문 검색 결과가 더 풍부)
- **반드시 정확히 5개의 검색어만 생성 (5개 초과 절대 금지)**
- 각 검색어는 구체적이고 시각적인 장면을 묘사
- "4K", "cinematic", "footage", "B-roll" 같은 키워드를 적절히 포함
- 워터마크 없는 고화질 영상을 찾을 수 있도록
- 검색어끼리 중복되지 않도록 다양한 장면을 커버

중요: queries 배열에는 반드시 5개 이하의 항목만 포함하세요.

JSON으로 반환하세요:
{"queries": ["search query 1", "search query 2", "search query 3", "search query 4", "search query 5"]}`;
}
