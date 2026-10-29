WindGrid SCM v0.4.2 — Gemini 연결 진단 수정

1. app.py와 evidence.py 두 파일만 기존 GitHub 저장소 최상위 폴더에 덮어쓰기
2. GitHub Desktop → Commit to main → Push origin
3. Streamlit Cloud 재배포 완료 후 ⑤ AI 보고서 → API 연결 진단
4. API 버전 v1beta/v1 각각 모델 목록 및 짧은 생성 호출 테스트(12초 제한, 재시도 없음)
5. 호출 성공한 버전/모델에서 실제 AI 분석 실행. 실제 분석은 공개 가능한 자료만 전송.

404/429/503/시간 초과는 서로 다른 원인일 수 있으며 모델 목록 조회 성공이 생성 호출 성공을 보장하지 않습니다.
오류 메시지는 Google 응답의 유형 및 제한된 일부 메시지만 표시하고, 키/URL/응답 원문은 출력하지 않습니다.
이 수정은 API 서버에서 성공을 보장하지 않으며 Google 실서버 호출은 수행하지 않았습니다.
