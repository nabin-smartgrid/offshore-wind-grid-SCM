# 변경 이력

## v0.2 (2026-10-29)

- Streamlit 앱에 케이블 길이별 시나리오 비교 화면 추가
- 리액터/STATCOM/케이블 조달 검토 우선순위를 계산 지표에 따라 다르게 표시
- 시나리오 비교 결과의 Gemini API 분석(명시적 동의 및 API 키 필요) 추가
- 보고서에 비교 그래프와 구조화된 표를 넣은 PDF 출력 추가
- 6개 추가 테스트를 포함하여 총 26개 단위 테스트 통과

## v0.1

- 교육용 간이 계산, 문서 검색, 5개 화면, 규칙 기반 요약, 선택적 Gemini 연결

## v0.3 (2026-10-29)

- Streamlit Cloud에서 한국어가 누락되는 문제를 방지하기 위해 실행 환경에 설치된 NanumGothic TrueType 폰트를 PDF에 내장 (koreanize-matplotlib 의존성)
- 한글 폰트가 없으면 잘못된 PDF 대신 명확한 오류 표시
- 시나리오 비교 PDF 1페이지에 그래프·전체 비교표를 묶고, 2페이지에 SCM/일정 검토사항 배치
- 길이 변화에 따른 리액터·케이블 검토 수준별 조달 후속 조치를 구체화 (납기/가격/COD 임의 산정 금지)
- LLM API 실행 여부를 PDF에서 명확히 구분

## v0.4 (2026-10-29)
- Gemini API key stored in Streamlit Cloud Secrets (never in GitHub).
- Default Gemini model ID with manual override.
- Numerical Mvar/SCR consistency check and document-ID check on LLM output.
- LLM output failing automatic checks is excluded from downloadable PDFs.
- 5 new unit tests and deployment guide.
