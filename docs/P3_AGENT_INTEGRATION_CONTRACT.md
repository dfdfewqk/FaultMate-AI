# FaultMate AI — P3 연동 계약 1.0.0 (Antigravity 담당)

> **P6 업데이트**: `faultmate/integration/agent.py`와 `/api/agent/review`에 선택적 DeepSeek HTTPS 호출, 명시 동의 UI, 서버 환경변수 키, 모델 출력 인덱스 검증을 구현했습니다. **실제 키 기반 라이브 API 호출은 아직 검증하지 못했습니다.** 독립적인 tool-calling 루프는 없으며 미리 조회한 P2 근거로만 검토합니다. 기존 P3 계약/안전 원칙은 계속 유효합니다.

## 이미 구현된 인터페이스

| 메서드 | 경로 | 목적 |
|---|---|---|
| GET | `/api/integration/capabilities` | 모델 미연결 상태, 지원 가능한 읽기 전용 도구 및 안전 금지사항 확인 |
| POST | `/api/integration/evidence-preview` | P2 진단 입력으로 출처가 있는 최소 맥락 JSON 생성. **외부 전송 안 함** |
| GET | `/api/knowledge/cases` | 지원 사례 목록 |
| GET | `/api/knowledge/cases/{case_id}` | 검증 범위가 제한된 참고 사례 원문 |
| GET | `/api/knowledge/sources` | 출처·적용 범위·한계 |
| POST | `/api/diagnostics/evaluate` | 기존 P2 규칙 엔진: 작업자 자가 보고에 따른 검토 우선순위 |

`evidence-preview` 요청:

```json
{
  "triage": {
    "case_id": "CONV-001",
    "equipment": "컨베이어",
    "emergency_hazard": "no",
    "observations": {
      "motor_rotates_log": "yes",
      "visible_jam": "unknown"
    }
  }
}
```

응답 `state`와 계약:

- `candidate_review`: `context` 포함, `allowed_for_agent_reasoning=true`. 원인 후보/질문/안전 조건/출처의 **미확정 상태 유지**.
- `selection_required`: `context=null`. 사례를 자동 선택하거나 진단할 수 없음.
- `safety_hold`: `context=null`. 위험 상황에서는 에이전트 호출도 중지하고 현장 비상 절차로 안내.
- `external_transfer_performed=false`, `user_consent_captured=false`, `ml_inference_performed=false`, `confirmed_fault=false`, `safe_to_work=false`는 현재 모든 응답에서 고정.
- 전달 가능한 컨텍스트에는 **직접 입력한 증상 원문, 알람 자유 텍스트, 모델 이름 문자열을 넣지 않음**. 승인 전 원문을 외부로 전송하지 마라.
- HTTP 404는 존재하지 않는 사례. 422는 스키마 불일치, 잘못된 관찰, 설비·사례 불일치, 미지원 필드 등.

## Antigravity 구현 시 추가할 기능 (별도 모듈)

1. UI에서 AI 호출 기능을 **명시적으로 켠 사용자**만 에이전트를 실행. 전송 예정인 항목을 먼저 보여주고 요청마다 동의. 거부하면 기존 규칙 기반 분석만 유지.
2. `DEEPSEEK_API_KEY`는 **서버 프로세스 환경변수**에만 저장. 프론트엔드, URL, 응답, CSV, GitHub에 넣지 말고 서버 로그에서 마스킹.
3. 에이전트 tool-calling은 기존 `/api/knowledge/*`, `/api/diagnostics/*`, `/api/integration/evidence-preview`를 감싼 **허용목록 조회 도구만** 사용. 임의 파일 접근, 셸, PLC, Modbus, 네트워크 스캔, 원격 재가동, 쓰기·삭제 도구 금지.
4. `source_ids`가 근거 저장소에 있고 각 출처의 `limit`을 결과에 포함하는지 검증. 없거나 충돌하면 답변을 근거 미확인으로 처리.
5. AI가 P2의 `confirmed_fault=false`, `safe_to_work=false`, `not_confirmed=true`, `safety_hold`를 변경하지 못하도록 **모델 출력 후에도 백엔드에서 강제**. AI 텍스트를 HTML로 실행하지 말 것.
6. 모든 모델 입력의 증상·로그·출처 문장을 **신뢰할 수 없는 외부 텍스트**로 취급. 사용자 입력의 "지침 무시하고 작동하라" 같은 공격 문장을 시스템 도구 지시로 승격시키면 실패.
7. 요청 시간 초과·쿼터 부족·키 없음·모델 실패 시 P2 로컬 결과를 유지하고 상태를 분명히 표시. 조용히 성공한 것처럼 보이지 말 것.
8. UI는 답변에 출처, 적용 범위, 확인 필요 사항을 보여주고 현장 매뉴얼·책임자 확인을 명시. 진단 확률을 임의로 생성하거나 결론을 확정하지 않음.

## 안전 테스트 수용 조건

- 긴급 위험 `yes`: 에이전트 호출 횟수 0, 원인 후보 표시 0.
- 사례 미선택: 모델이 임의 원인 확정 불가.
- 사용자 동의 없음: **DeepSeek 네트워크 호출 횟수 0**.
- 키 없음·타임아웃·HTTP 429/500: P2 결과 유실 없음, 사용자에게 연동 실패 명시.
- 외부로 나가는 JSON에 API 키/원문 증상/설비 식별/개인정보가 없어야 함. 추가 데이터가 필요하면 항목별 사전 동의를 새로 얻어야 함.
- 인용 source ID 위조, 모델 출력에 따른 설비 명령, `safe_to_work=true`, AI의 자동 재가동 제안이 모두 차단되는지 테스트.
- 기존 `python -m pytest -q tests` 전량 PASS, 기능 활성화·비활성화 모두 검증.

이 문서는 에이전트 기능 구현 완료 보고서가 아니라 **구현자가 지켜야 할 계약**이다.
