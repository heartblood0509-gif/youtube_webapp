export function buildTitlePrompt(category: string, topic: string): string {
  const categoryGuide: Record<string, string> = {
    cosmetics_info: '화장품 정보성 - 증상의 진짜 원인 폭로, "이거 안 바르면 손해", 업계가 숨기는 메커니즘, 충격 사실',
    cosmetics_ad: '화장품 광고성 - 성분 충격, "이 성분 없으면 소용없음", 제품 궁금증 유발, FOMO',
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
  const templates: Record<string, string> = {
    cosmetics_info: `당신은 한국 유튜브 쇼츠 나레이션 대본 작가입니다. "화장품 정보성" 영상 대본을 작성합니다.

제목: ${title}
주제: ${topic}

=== 절대 규칙: 글자수 ===
- 각 문장은 반드시 25자 이내 (띄어쓰기 포함)
- 25자 초과 문장은 무조건 탈락
- 짧고 임팩트 있게, 군더더기 없이

=== 대본 구조 (6단계, 총 6~8문장) ===

[1단계: 후킹/공감] (1문장)
- "~하는 분들 많으시죠?" 패턴
- 예시: "밤만 되면 가려움 심해지시죠?"

[2단계: 일반적 오해] (1~2문장)
- 흔한 잘못된 대처법 지적
- 예시: "보습제로 해결하려는 분 많죠"

[3단계: 필터링] (1문장)
- "~로 나았다면 이 영상 패스하세요"
- 예시: "보습제로 나았으면 안 보셔도 돼요"

[4단계: 근본 원인] (1~2문장)
- 진짜 원인을 짧게 밝힘
- 예시: "진짜 원인은 혈액 순환 부족이에요"

[5단계: 핵심 원리] (1문장)
- 단정적 톤으로 정리
- 예시: "혈액 공급이 답입니다, 끝이에요"

[6단계: CTA] (1문장)
- 방향만 제시 (제품 추천 X)
- 예시: "혈액 순환 개선 치료가 필요합니다"

=== 공통 규칙 ===
- 25자 이내 엄수 (가장 중요!)
- 한국어, 권위 있는 대화체
- 특정 제품명 언급 금지
- 쉼표로 끊김점 확보

JSON으로 반환하세요:
{"sentences": ["문장1", "문장2", ...]}`,

    cosmetics_ad: `당신은 한국 유튜브 쇼츠 나레이션 대본 작가입니다. "화장품 광고성" 영상 대본을 작성합니다.

제목: ${title}
주제: ${topic}

=== 절대 규칙: 글자수 ===
- 각 문장은 반드시 25자 이내 (띄어쓰기 포함)
- 25자 초과 문장은 무조건 탈락
- 짧고 펀치 있게, 군더더기 삭제

=== 대본 구조 (3섹션 × 3문장 = 9문장) ===

[섹션1: 후킹] (3문장)
① 극단적 공감
- 예시: "밤마다 긁어야 잠드는 고통, 아시죠?"
② 기존 해결책 실패 이유
- 예시: "보습제가 안 듣는 이유 따로 있어요"
③ 문제 리프레이밍
- 예시: "겉이 아니라 장벽을 고쳐야 합니다"

[섹션2: 성분 정보] (3문장)
④ 솔루션 전환
- 예시: "꼭 확인할 성분 두 가지 있어요"
⑤ 성분 1 + 효능
- 예시: "세라마이드, 장벽을 메우는 핵심이에요"
⑥ 성분 2 + 효능
- 예시: "병풀잎수, 가려움을 즉각 진정시킵니다"

[섹션3: 제품 공개] (3문장)
⑦ 제품 공개
- 예시: "이 조합을 담은 게 '미르엔'입니다"
⑧ 효과 요약
- 예시: "장벽 복구에 진정까지, 한 통이면 끝"
⑨ 감성 CTA
- 예시: "더 이상 긁지 마세요, 미르엔이 지켜줍니다"

=== 공통 규칙 ===
- 25자 이내 엄수 (가장 중요!)
- 한국어, 전문가 톤 대화체
- 가상 제품명 자연스럽게 생성
- 실제 화장품 성분 활용
- 쉼표로 끊김점 확보

JSON으로 반환하세요:
{"sentences": ["문장1", "문장2", ..., "문장9"]}`,
  };

  // 기본 프롬프트 (cruise, other 등)
  const defaultPrompt = `당신은 한국 유튜브 쇼츠 나레이션 대본 작가입니다.

제목: ${title}
카테고리: ${category}
주제: ${topic}

규칙:
- 7~10개의 짧은 문장
- 쉼표로 자연스러운 끊김점 확보
- 구조: 후킹(공감) → 문제/맥락 → 상세 → CTA
- 한국어, 대화체
- 긴 문장은 반드시 쉼표로 분할

JSON으로 반환하세요:
{"sentences": ["문장1", "문장2", "문장3", ...]}`;

  return templates[category] || defaultPrompt;
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
