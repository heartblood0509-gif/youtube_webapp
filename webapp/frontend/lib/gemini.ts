const MAX_RETRIES = 3;

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function callGemini(apiKey: string, prompt: string): Promise<string> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: {
          temperature: 0.8,
          maxOutputTokens: 8192,
        },
      }),
    });

    if (res.status === 429) {
      // Rate limit - 재시도
      const waitSec = Math.min(2 ** attempt * 2, 10);
      if (attempt < MAX_RETRIES) {
        await sleep(waitSec * 1000);
        continue;
      }
      throw new Error(`API 요청 한도 초과 - ${waitSec}초 후 다시 시도해 주세요`);
    }

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error?.message || `Gemini API 오류: ${res.status}`);
    }

    const data = await res.json();
    return data.candidates?.[0]?.content?.parts?.[0]?.text || '';
  }

  throw new Error('Gemini API 요청 실패 - 잠시 후 다시 시도해 주세요');
}
