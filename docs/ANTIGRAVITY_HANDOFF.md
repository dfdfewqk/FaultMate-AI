# FaultMate AI — 최소 인수인계

P7.1 디버깅 통합 ZIP의 `FaultMate-AI`를 통합 기준으로 한다. 기존 P5와 P2/P3 원본을 바꾸거나 섞지 않는다.

**완료**: 7개 로컬 고장 근거 사례, P2 규칙 진단·긴급 차단, P5 UI 안전화, P6 DeepSeek 선택적 호출 및 동의·검증 코드, ML CSV/학습/평가/추론 기반 코드, Python 및 Chromium 모의 통합 테스트.

**미완료**: 실제 DeepSeek API 요청 성공 검증, Paderborn `.mat` 신호의 CSV 변환·실제 모델 학습·현장 일반화 검증, P7.1 Windows 실기기 실행. 모델이 없어 기본 `connected=false`, `inference_enabled=false`가 정상이다.

Antigravity는 **`docs/ANTIGRAVITY_IMPLEMENTATION_ORDER.md`의 4개 실증 작업에만 집중**한다. 이미 구현한 코드를 재작성하거나 다른 기능을 추가하지 않는다.
