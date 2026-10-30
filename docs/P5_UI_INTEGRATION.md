# FaultMate AI — P5 로컬 UI 통합 작업

## 현재 실제 구현
- 서버: FastAPI P2 규칙 엔진, P3 읽기 전용 근거 미리보기. AI나 ML 추론 없음.
- 화면: 가상 사례 입력, 사례별 질문 선택, 근거·한계 표시, 자료실→진단 작업 이동, AI/ML 연결 상태 조회.
- 안정성: 클라이언트 비동기 요청 버전과 `AbortController`로 오래된 응답이 새 입력/긴급 위험 상태를 덮어쓰지 않게 함.
- API: `/api/diagnostics/evaluate` POST 응답에 `Cache-Control: no-store, private` 및 `Pragma: no-cache`.
- 보안: 텍스트 `textContent` 기반 표시, 외부 서비스 전송 없음, 설비 제어 없음.

## Antigravity 합류 전제
1. `GET /api/integration/capabilities` 계약 유지. 연결 `false`인 동안 화면은 AI/ML 미연결 표시.
2. `POST /api/integration/evidence-preview`는 민감한 원문 제외하고 읽기 전용 근거 전달 (외부 전송 아님).
3. Agent/ML은 각각 새 모듈로 분리하고 실제 동의·데이터 보호·품질 검증 없이 UI에서 `사용 가능` 처리하지 말 것.
4. UI 신규 연결 버튼 및 화면 구성 시 사용자의 긴급위험 선택 후 모든 비동기 결과 처리 차단 기준 준수.
5. 포장 작업 시 구버전 P2/P3 ZIP에 덮어쓰지 말고 신규 릴리스로 배포.

## 사용 안내
- Windows: `start_windows.bat` 실행(초회 환경 준비 시 인터넷 필요 가능).
- Demo: `가상 고장 사례 채워 보기` -> `원인 후보 · 질문 검토`.
- 단순 진단 및 P1 근거 자료실은 API 키 없이 이용 가능. 결과는 고장 확정이 아닌 작업자 검토용.

## 테스트 명령
```bash
python -m pip install -r requirements.txt pytest httpx
python -m pytest -q tests
node --check web/app.js
```

## 미검증
- Windows 실기기 실행, 실제 제조사 모델별 고장 진단 정확도, DeepSeek 실제 연결, ML 학습 및 평가.
- Chromium은 실행 환경 보안정책으로 직접 로컬 HTTP 주소 접속이 차단됨. 따라서 브라우저 UI 테스트는 실제 백엔드에서 얻은 API 결과를 브라우저에 주입하여 검증했으며, 실제 네트워크 HTTP 검사는 별도 Python 클라이언트로 수행.
