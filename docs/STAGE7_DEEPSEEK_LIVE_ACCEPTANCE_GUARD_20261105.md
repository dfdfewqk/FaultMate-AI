# FaultMate AI — DeepSeek ③단계 유료 실연동 1회 수용 절차 (2026-11-05)

## 목표와 현재 상태

기존 FaultMate AI P7.2는 사용자 미리보기 SHA256, 요청별 명시 동의, 최소한의 공개 사례·근거만 외부로 전송, 결과의 **원인 확정·작업허가 금지**, 유료 API 단일 호출·무재시도, 리다이렉트/오류/키 유출 방지까지 이미 구현되어 있고 Linux·Windows에서 **실제 로컬 TCP/HTTP** 통합 검사를 통과했다.

[DeepSeek 공식 Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)는 `deepseek-flash`, `thinking.type=disabled`, `response_format.type=json_object`, `max_tokens`를 지원한다. [JSON Output 공식 안내](https://api-docs.deepseek.com/guides/json_mode/)에는 공백 출력과 길이 초과에 주의하도록 명시한다. 기존 앱은 이를 오류로 처리하고 유료 자동 재시도를 하지 않는다.

**그러나 실제 DeepSeek 서버에 본인 키로 연결·결제 가능한 요청을 보내는 최종 수용검사는 아직 실행하지 않았다.** 이 부분은 사용자 계정의 별도 과금 동의가 필요한 작업이므로 사용자가 직접 승인하기 전에는 호출하지 않는다. 일반 ChatGPT 구독료가 DeepSeek API 호출료를 포함하지는 않는다.

## 새로 추가한 도구

`scripts/optional_deepseek_one_call_acceptance.py` 는 **기본적으로 완전 오프라인**으로 실행한다.

```powershell
.\.venv\Scripts\python.exe scripts/optional_deepseek_one_call_acceptance.py
```

기본 동작은 API 키 내용조차 읽지 않고 기존 P7.2의 고정 공개 예제 `CONV-001`이 미리보기를 생성하는지, 원래 DeepSeek HTTPS 엔드포인트/모델/출력 600토큰 제한이 변경되지 않았는지 **로컬 확인만** 한다. 네트워크 요청 0건, 비용 0원, 보고서나 DB를 만들지 않는다.

### 유료 실제 서버 검증은 **사용자 선택사항**

사용자가 나중에 DeepSeek API 실연동을 **명시적으로 허용하고 결제/키를 본인 환경에 설정한 경우에만** 다음 세 조건을 모두 충족해야 1회 실요청이 가능하다.

1. `--one-paid-request` 플래그.
2. `--confirm-public-demo-evidence` 플래그 — 실험용 공개 사례를 외부 서버에 전송하는 데 명시 동의.
3. 사용자의 PC에서만 `FAULTMATE_LIVE_TEST_APPROVED=YES_ONE_PAID_REQUEST` 환경변수 및 자신의 `DEEPSEEK_API_KEY` 설정.

**지금 해당 플래그/실키를 설정하거나 실요청을 실행할 필요는 없다.** 승인 후에도 기존 AgentReview의 미리보기 SHA/동의 검사·한 번만 보내는 전송 규칙을 그대로 이용한다. 응답이 실패·타임아웃·잔액 부족일 때도 **자동 재전송 0회**, 외부 전송 가능성을 `null`로 표시하고 이전 로컬 진단은 유지한다.

### 보고서에 노출하지 않는 것

- API 키 원문, 외부 제공자의 원문 응답, 유료 요청의 전체 프롬프트, 사용자의 자유 입력 증상·장비명·알람.
- 정확한 원화 결제금액은 API 회선/입출력 사용량/시점별 요금이 없으면 알 수 없으므로 계산하지 않는다.
- 실제 설비 안전 여부/고장 확정/ML 베어링 모델 승인을 반환하지 않는다.
- **1회 명시 동의 = 언제든 자동 전송 승인**으로 해석하지 않는다.

## 테스트·변경 범위

`tests/test_optional_deepseek_live_acceptance.py` 는 합성 테스트 키와 모의 `agent.review`를 이용해:
- 기본 호출, 유료 플래그만 있고 전송 동의 누락, 사용자 환경 승인 누락, 키 누락일 때 전송하지 않는지;
- 세 승인 조건이 존재할 때 정확한 공개 예제·SHA256·동의만 외부 호출에 실리는지;
- 응답 실패 시 외부 전송 여부를 거짓으로 '미전송' 표시하지 않는지;
- 예상한 HTTPS 서버와 `deepseek-flash`의 설정이 바뀌면 실호출 전에 막는지;
- 키·원본 응답 등이 출력되지 않는지 검증한다.

`.github/workflows/stage7-deepseek-live-acceptance-gates.yml`는 Linux·Windows·Chromium 기존 전체 코드/화면/실제 로컬 HTTP 검사를 다시 수행하며, 새 도구는 **오프라인 플래그 없이만 실행**한다.

GitHub Actions: https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/stage7-deepseek-live-acceptance-gates.yml

## 분리된 최종 인수검사

- **자동 개발·무과금 검증:** 완성되면 해당 Draft PR에서 보존.
- **실제 유료 DeepSeek 서버 1회 실연동:** **사용자 직접 승인 + 본인 PC 키 + 별도 API 과금 가능성 인지** 이후에만 가능. 사용자가 이 기능을 원하지 않으면 기존 로컬 진단은 AI 없이도 작동한다.
- **ML 승인:** 독립 정상 베어링/원본 검증·SI 단위·앱 입력 계약이 미해결인 별개 제한. DeepSeek를 연결해도 미승인 ML이 승격되지 않음.
- **실제 사용자 Windows PC 수용검사:** GitHub Windows runner와 별개, 사용자가 직접 수행하는 마지막 단계.
- **EXE/ZIP 배포:** 원래 합의대로 완성/수용검사 전 임의 생성하지 않음.

기존 `main`/사용자 데이터/원본 Paderborn RAR/MAT/연구 모델 JSON/SQLite 변경 없음.
