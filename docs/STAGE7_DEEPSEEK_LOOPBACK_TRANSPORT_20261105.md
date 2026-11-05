# FaultMate AI — 7단계 DeepSeek 실제 HTTP 전송 경계 검증 (유료 API 미호출)

작성일: 2026-11-05. 기존 `work/faultmate-stage7-source-compat-and-regression-20261105`에 변경을 누적하지 않고 신규 Draft PR 브랜치로 분리.

## 구분: 모의 함수 테스트와 진짜 HTTP 통신

앞서 있던 모의 DeepSeek 검사는 `_invoke_deepseek`를 Python 함수로 가짜 처리하는 방식이었다. 그 테스트만으로는 실제 TCP/HTTP 연결 요청, POST 본문, Authorization 헤더, HTTP 402/429/503 응답, 리다이렉트 시 토큰 보호 등이 현실적인 HTTP 요청에서 정상인지 확정할 수 없다.

이번 `tests/test_deepseek_local_http_loopback.py`는 테스트가 시작한 **`127.0.0.1` 로컬 HTTP 서버**에 기존 `urllib` 전송 코드로 실제 TCP/HTTP POST를 보낸다. 테스트 안에서만 `ENDPOINT`를 loopback 주소로 바꾸고 **비용이 발생하지 않는 고정 가짜 API 키만 사용**한다.

- 외부 `api.deepseek.com`으로 접근하지 않는다. 실제 유료 API 키를 사용하거나 외부로 사용자 데이터를 보내지 않는다.
- 사용자 동의가 없으면 로컬 HTTP 요청 0건, 확인한 미리보기 SHA-256이 부정확·누락돼도 요청 0건.
- 서버가 반환한 미리보기의 정규 JSON과 실제 POST의 문맥 끝부분을 비교. 원문 증상/장비 ID/알람 및 API 키는 전송 본문에 포함되지 않는다.
- `deepseek-flash`, `thinking.disabled`, `response_format=json_object`, `max_tokens=600`, `stream=false`, 두 개 메시지 및 도구 호출 없음 확인.
- HTTP 400/401/402/429/500/503 실제 loopback 응답에 대해 1회만 요청, 응답 메시지·인증키 비노출, 고장 확정·작업 허가 항상 false.
- HTTP 302 유도 시 다른 로컬 서버로 인증키를 전달하지 않는지 실제 요청 횟수로 검증.
- 공백 JSON·토큰 제한 초과/부분 응답·128KB 이상 과대 응답은 모두 로컬 진단으로 복귀한다.
- **응답 미도착/HTTP 오류 시 외부 전송이 발생했는지 불명확**한 상태는 `external_transfer_performed=null`로 유지한다.

## 화면 수정

`web/app.js`에서 `external_transfer_performed` 결과를 불리언으로 뭉뚱그리던 부분을 다음 세 상태로 바꾼다.

1. `true`: `외부 AI 검토 응답 수신 · 고장 확정 아님`
2. `false`와 `external_transfer_attempted=false`: `외부 AI 전송 없음 · 기존 로컬 진단 사용`
3. `null` 또는 `external_transfer_attempted=true`: **`외부 AI 전송 여부 확인 불가 · 재요청 전 미리보기와 동의 재확인`**.

또한 통신 예외로 응답 내용을 모르는 경우에도 **전송 여부 확인 불가**라고 표시한다. 이는 과금 가능성이 있는 API의 오류 상황에서 사용자에게 잘못된 안전 확신을 주지 않기 위한 것이다.

`tests/browser_stage6_integrated.py`에 실제 화면에서 성공 한 번과 모의 서버 오류 후 불확실 상태 표시/동의 초기화를 확인하는 회귀 시나리오를 추가했다.

## 공식 API 규격 점검

- [DeepSeek 공식 Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/): 2026 기준 모델 `deepseek-flash`, `thinking.type=disabled`, `response_format.type=json_object`, `max_tokens` 및 비스트리밍 지원.
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/): 백엔드가 공백 또는 잘린 응답을 줄 수 있으므로 이를 오류로 처리. **자동 재시도 없음**(불필요한 추가 과금 회피).
- 프로덕션 실제 엔드포인트는 변동 없이 `https://api.deepseek.com/chat/completions`로 고정하고, 테스트 시에만 loopback 교체.

## 자동검사

GitHub Actions: https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/stage7-deepseek-offline-transport.yml

- Linux 전체 Python + 12개 실제 로컬 앱 HTTP + 브라우저 JS 문법 + 신규 loopback 검증.
- Windows 전체 Python + 기존 `setup_windows.bat` → `windows_launcher_smoke.py` + 신규 loopback 검증.
- Chromium P7.2 7개 화면 회귀 + Stage 6 UI 고급분석 동의/모의 응답/불확실 전송/긴급 차단 검사.
- 미승인 베어링 ML 자동 활성화와 외부 정상 데이터 허위 정확도 모두 계속 차단.

## 완료 기준과 남은 절차

이번 단계는 **실제 운영체제 네트워크 스택을 통한 무과금 HTTP 통합 테스트**이지, *실제 DeepSeek 서버에 인증된 유료 요청이 성공했다는 실연동 검사*가 아니다.

실제 API 검증에는 **사용자의 별도 명시적 동의와 유효한 본인 계정의 API 키·사용료 한도 확인**이 선행되어야 한다. 사용자 동의가 없는 한 이를 자동 실행하거나 키/결제 정보를 요청하지 않는다. 구독형 ChatGPT 요금과 DeepSeek API 과금은 다른 결제 체계이다.

또한 실측 Paderborn 모델은 여전히 **미승인**(새 정상 물리 베어링 미확보, 기존 새 손상 8개 7/8 검출 및 KI21 미탐). 실제 설비 고장 확정·정비 허가·원격제어는 수행하지 않는다.

`main`은 건드리지 않고, 사용자 원본 MAT/RAR·SQLite·기존 데이터·모델 계수·기존 Draft PR은 보존한다. EXE/ZIP을 미리 제작하거나 배포하지 않는다.
