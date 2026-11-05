# FaultMate AI — 5단계 DeepSeek 연동 및 오류·안전 검증
작성일: 2026-11-05 (KST)
브랜치: work/faultmate-stage5-deepseek-transport-20261105
이전 4단계 브랜치: work/faultmate-stage4-ml-readiness-20261105

## 결론
**코드 호환성·오류·안전 검증 완료. 실제 유료 DeepSeek API 호출 및 통신 성공은 미검증.**
실제 키를 사용하거나 API 이용료가 발생할 수 있는 네트워크 호출은 사용자 명시 동의 전에는 실행하지 않는다.

## 공식 API와 기존 코드 대조
- DeepSeek는 2026-04-24 공지에서 legacy deepseek-chat/deepseek-reasoner 종료일을 2026-07-24로 지정했다.
  출처: https://api-docs.deepseek.com/updates/
- 공식 현행 모델명 deepseek-flash, 엔드포인트 https://api.deepseek.com/chat/completions.
  출처: https://api-docs.deepseek.com/api/create-chat-completion/
- 문서상 JSON 출력에는 response_format={"type":"json_object"} 와 시스템/사용자 메시지에 JSON 출력 명시가 요구된다. 일부 응답은 공백 문자열 또는 길이 초과로 끝날 수 있어 유효한 JSON과 finish_reason=stop을 확인해야 한다.
  출처: https://api-docs.deepseek.com/guides/json_mode/
- HTTP 401 (인증), 402 (잔액), 429 (제한), 500/503 (서비스 오류). 숫자 코드로 제한된 오류 상태만 브라우저에 노출한다.
  출처: https://api-docs.deepseek.com/quick_start/error_codes/

## 실제 변경 사항
1. faultmate/integration/agent.py
   - deprecated deepseek-chat → deepseek-flash.
   - thinking disabled, max_tokens 600, JSON-only 비스트리밍 응답, 20초 타임아웃 유지.
   - 응답 128KB 제한, 근거 프리뷰 64KB 제한, redirect 차단, 서버 env의 DEEPSEEK_API_KEY 유지.
   - HTTP 400, 401, 402, 422, 429, 500, 503/timeout/network 오류를 모의 응답으로 검증.
   - 오류 코드 외 API 키, 오류 응답 원문, 운영자 원시 증상·장비명 등은 브라우저로 반환하지 않는다.
   - 실패 시 자동 재시도 없음 (인증/잔액/쿼터/중복 비용 위험 방지). 외부 전송 성사 여부가 불명확하면 None을 유지해 허위 안전 상태를 표시하지 않는다.
   - 모델의 임의 설명·지침은 폐기하고 근거 목록의 정수 인덱스만 수용한다. 안전 중지, 미선택 사례, 요청별 동의 없음은 외부 호출 차단.
2. tests/test_agent_transport_safety.py
   - current Flash 모델명, 최대 토큰, 단일 요청, 시스템의 JSON 지시 검증.
   - 400/401/402/422/429/500/503, 네트워크 오류, timeout, 이상한 JSON, Boolean/중복 인덱스, truncation 상태 시험.
   - Fake opener/TestClient만 사용, 실제 API 호출 없음. 실패해도 로컬 진단 HTTP endpoint는 사용 가능함을 확인.
3. .github/workflows/stage5-agent-transport-safety.yml
   - CI에 API 키 값을 빈 문자열로 고정. 실호출 없이 기존 개발 자동검사와 ML·AI 회귀 전부 확인.
   - 사용자 파일, 저장 데이터, 모델, EXE, ZIP, main 변경 없음.

## 검증 증거
- https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41961579587
- 241 tests passed, one Starlette/httpx deprecation warning. Compileall 및 model/endpoint no-key contract PASS.
- 이 테스트는 공식 네트워크의 인증·청구·실제 API 응답을 직접 검증하는 것이 아님.

## 실제 유료 API 실증 이후에만 완료 판정할 범위
- 사용자 명시 승인 + 실제 계정의 키/잔액/비용 한도 확인 (키를 채팅·GitHub·로그에 넣지 말 것).
- 테스트는 사용자가 제공한 분리된 환경변수로 단 한 번, 선택된 공개 사례와 관찰만 전송.
- 실패·시간초과 시 중복 요청/자동 재시도 없이 로컬 진단은 정상 동작해야 하며, 외부 전송 성공 여부를 확실히 단정하지 말 것.
- 유효한 응답은 원인 확정/작업 허가로 사용하지 않고 P2의 근거 순서 참고에만 사용한다.

## 다음 순서
6단계 프로그램 통합은 동일 작업 브랜치 기반으로 코드 검증 가능. 7단계 Windows/Linux/UI 종합검증은 실제 테스트 증거 필요. 8단계 EXE·ZIP은 개발/검증이 완료된 뒤에만 제작.
