# FaultMate AI P7.2 — 4단계 자료실 지연 로딩·화면 반응 개선

기준 소스: P7.2 3단계 ZIP (`FaultMate_AI_P7_2_Step3_20261030.zip`)
기존 기준 버전은 변경하지 않고 새 ZIP으로 제공.

## 변경 내용
1. 시작 시 `/api/knowledge/sources`, `/api/knowledge/cases`, 사례 상세 요청을 하지 않음.
2. 진단 옵션을 읽고 증상 추천·진단 UI를 구성하는 흐름은 자료실 및 `/api/status`, `/api/integration/capabilities` 요청이 느려도 대기하지 않음.
3. 자료실을 열 때 최초 로드. 접었다 펼쳐도 이미 가져온 사례는 재사용.
4. 출처 요청 실패 시에도 사례를 볼 수 있고 자료실을 다시 열면 재시도. 진단 기능에는 영향 없음.
5. 필터 변경 시 이전 응답이 뒤늦게 표시되지 않게 버전 검증, 불필요한 중복 요청 최소화.
6. 기존 P7.2 1~3단계 진단/위험 차단/결과 보기/AI·ML 계약 유지.

## 검증 방법
- `python -m pytest -q tests`
- `node --check web/app.js`
- `PYTHONPATH=. python tests/browser_smoke.py`
- `PYTHONPATH=. python tests/browser_step1.py` ... `browser_step4.py`
- `PYTHONPATH=. python tests/live_http_smoke.py`

Playwright 브라우저는 로컬 직접 접속 대신 실제 FastAPI TestClient 응답을 라우팅한 테스트 환경임. Windows 실기기 실행 미검증. 외부 API·실측 ML 학습은 미완료.

## 다음 작업
P7.2 5단계: 결과 요약 복사 및 덜 쓰는 기술 정보 숨기기. 이후 6단계 전체 통합 검증만 수행. 추가 기능 확장은 하지 않음.
