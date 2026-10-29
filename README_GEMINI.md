# Gemini API 연결 — WindGrid SCM v0.4

## Streamlit Cloud에서 설정

1. Google AI Studio(https://aistudio.google.com/apikey)에서 본인 Google 계정으로 Gemini API 키 생성.
2. Streamlit Cloud(https://share.streamlit.io/) → offshore-wind-grid-and-scm → Manage app → Settings / App settings → **Secrets**.
3. 아래 설정을 붙여넣고 `YOUR_KEY_HERE`를 본인 키로 교체(키를 GitHub에 올리거나 채팅에 보내지 말 것).

```toml
GEMINI_API_KEY = "YOUR_KEY_HERE"
GEMINI_MODEL = "gemini-2.5-flash"
```

4. Save 후 앱이 재시작되면 ⑤ AI 보고서 또는 ⑥ 시나리오 비교의 LLM 영역에서 키 설정 상태를 확인.
5. 공개 자료만 사용하고, **외부 전송 동의** 후 AI 분석 생성 버튼 클릭.
6. 생성 결과에서 문서 ID와 수치 대조 확인. 이상이 있으면 PDF에는 AI 문단이 제외됨.

## 검증 범위

- 코드가 계산한 충전 무효전력(Mvar), MW 및 SCR을 AI 텍스트에 나온 수치와 대조.
- AI가 인용한 문서 ID가 선택된 문서에 있는지 확인.
- **원문이 실제로 해당 주장을 뒷받침하는지, AI가 다른 숫자나 일정을 꾸며냈는지는 별도 검토가 필요.**
- 기본 제공 [PLAN-*] 문서는 과제 계획이며 공식 Grid Code가 아님.
- API 사용량과 과금은 Google 계정의 현재 조건을 확인.
- `.streamlit/secrets.toml`은 `.gitignore`로 제외되어야 함.
