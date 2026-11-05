# FaultMate AI — 6단계 단일 프로그램 통합 및 안전 계약

작성: 2026-11-05 KST. 정리본 `work/faultmate-preintegration-cleanup-20261105` 기반.
작업 브랜치: `work/faultmate-stage6-program-integration-20261105`.

## 현재 기능이 실제로 연결되는 경로

1. 기존 P7.2 `web/` UI에서 설비 종류·증상·공개 사례·관찰을 직접 선택한다.
2. `POST /api/diagnostics/evaluate`로 읽기 전용 규칙 기반 후보·안전 조건을 보여 준다.
3. 사용자가 고급 분석을 열고 `POST /api/integration/evidence-preview` 호출 시 기존 공개 출처와 미확정 후보만 화면에 표시한다. 이때 **실제 외부 전송은 0회**다.
4. 새 `context_sha256`은 미리보기에 실제 표시된 객체의 정규화된 UTF-8 JSON 바이트 SHA-256이다. `agent_context_wire`을 유일한 외부 본문 직렬화 경로로 재사용하여 화면에서 동의한 맥락과 실제 보내는 맥락을 결속한다.
5. 사용자 요청별 체크박스 동의 후 `POST /api/agent/review`은 같은 `triage`, `consent=true` 및 해당 `context_sha256`을 제출한다. 전송 직전 **서버가 미리보기와 토큰을 다시 계산**해 비교한다.
6. 토큰 부재·변조·구형 토큰·관찰/사례/공개 근거 변경은 `status=preview_mismatch`, `external_transfer_attempted=false`로 차단한다. 긴급 위험에서는 토큰 상태와 무관하게 `safety_hold`를 우선한다.
7. 동의와 토큰이 일치하고 서버에 실제 `DEEPSEEK_API_KEY`가 있을 때만 DeepSeek Flash에 요청을 보낼 수 있다. 키가 없으면 `status=unavailable`. 실제 모델은 원인 후보/추가 질문의 **기존 인덱스**만 재정렬할 수 있다. 모델의 임의 작업 지시나 위험 판단은 폐기한다.
8. 별도 `POST /api/ml/inspect`는 실제 단위·라벨·독립 베어링 시험 근거와 사람이 승인한 JSON 모델이 없다면 `unavailable` 유지. 4단계 자료 검증을 우회하지 않는다.
9. 입력 변경·미리보기 재조회·동의 취소·요청 실패/성공·긴급 위험 시 브라우저의 이전 미리보기 해시와 체크박스를 비운다. 기존 로컬 진단과 화면은 유지한다.

**중요한 한계:** SHA-256 토큰은 전송 직전 컨텍스트 동일성 확인일 뿐, 사람이 실제 화면을 읽었음을 암호학적으로 증명하거나 HTTP API 호출자 본인의 승인 증명을 제공하지 않는다. 실제 앱은 로컬 호스트 `127.0.0.1`에서만 실행하며, UI의 명시 동의 절차를 계속 사용한다.

## API 흐름

```json
// 1) POST /api/integration/evidence-preview
{"triage":{"case_id":"CONV-001","equipment":"컨베이어","emergency_hazard":"no"}}
```

응답 `context_sha256`은 선택한 데이터에 따라 서버가 계산한다. 다음 요청에는 **서버가 방금 돌려준 실제 값만** 그대로 사용한다. 64자리 값을 임의로 생성하거나 하드코딩하지 않는다.

```json
// 2) POST /api/agent/review
{"triage":{"case_id":"CONV-001","equipment":"컨베이어","emergency_hazard":"no"},
 "consent":true,
 "context_sha256":"<the actual sha256 from step 1>"}
```

실행할 때마다 공개 자료와 관찰 정보를 다시 확인하고 동의한다. AI 결과는 진단 승인이나 안전 확인이 아니다.

## 변경 파일

- `faultmate/integration/context.py`: 정규 직렬화 함수와 SHA-256 반환, 계약 1.1.0.
- `faultmate/integration/agent.py`: 검토된 SHA-256 없으면 외부 전송 차단, `hmac.compare_digest` 사용, 기존 리다이렉트·공개 정보 허용목록 유지.
- `web/app.js`: 전송 예정 맥락 해시 수신·보관·요청 연결 및 입력 변경·완료 시 즉시 무효화.
- `tests/test_agent_transport_safety.py`, `tests/test_p6_agent_ml.py`: 기존 mock 요청의 실제 서버 미리보기 해시 검증.
- `tests/test_stage6_integration.py`: 일곱 개 사례, 상태, 프리뷰와 실제 전송 내용 동일성, 변조/구형 해시·동의 없는 요청·긴급 중단·ML 미학습 안전 차단.
- `tests/browser_stage6_integrated.py`: 인프로세스 FastAPI와 Chromium에서 화면 → 근거 미리보기 → 동의 → **모의 DeepSeek** → ML 미학습 → 긴급 중단까지 검증. 실제 유료 API 사용 없음.
- `.github/workflows/stage6-program-integration.yml`: Linux Python/HTTP/JS, Windows CI 배치 실행, 기존 Chromium P7.2 화면 + 신규 브라우저 연동 검사.

## 안전하게 보존된 범위

- `main` 및 기존 Draft PR 1·6·8·9·10·11·12, 과거 커밋 이력은 보존; 자동 병합/강제 푸시 없음.
- 공식 Paderborn 12개 원본 RAR·960 MAT 검증 근거 및 4개 KA04 중복 기록 보존.
- ML 실학습은 센서 `vibration_1`·`phase_current_1`의 원본 숫자가 물리 SI인지 확인되지 않아 **여전히 차단**. 실제 정확도·성능 수치 없음.
- 사용자 로컬 데이터·SQLite·업로드 자료 삭제 또는 덮어쓰기 없음.
- DeepSeek 유료 실호출·키 공유 없음. 설치·배포용 EXE/ZIP 또는 새로운 모델 파일 생성 없음.

## 검증

새로운 통합 회귀 실행: https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/stage6-program-integration.yml

Stage 6의 자동 통합 검사 결과와 Stage 7 최종 사용자 환경 수용 검사는 다르다. Windows CI runner의 통과를 사용자 본인의 Windows PC에서 실제 API 키·외부 호출·일상 사용 완료로 오인하지 않는다.

남은 단계: 7단계 Windows/Linux/UI·안전 종합 수용 검사, 8단계 최종 배포는 **보정 근거/실제 ML 학습/선택적 실제 API 실험과 전반 검증이 완료된 경우에만** 검토한다.
