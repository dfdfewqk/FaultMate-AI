# FaultMate AI — PR #40~44 최종 통합·구형 파일 정리 (2026-11-06)

## 목적과 보존 원칙

- 기준 통합 소스: `work/faultmate-p7-operator-file-flow-20261106`, SHA `915b3e4870d1da751c1f995877a9f4dc44c5b10e` (PR #44). 현재 통합 정리 브랜치: `work/faultmate-p7-final-pr40-44-consolidation-cleanup-20261106`.
- **PR #40 → #41 → #42 → #43 → #44**는 각각 이전 SHA의 직계 후손(`compare_commits`에서 모두 `ahead`/0 behind). 따라서 마지막 SHA에 5개 단계가 이미 포함됨. `main` 직접 변경 또는 별도 기능 수동 복사는 필요 없음.
- 기본 통합 리뷰 PR #39 기준 브랜치는 `work/faultmate-final-consolidated-review-20261106`. 이 정리 브랜치는 PR #39 위의 모든 #40~44 UI/API 수정과 다음 구형 파일 제거만 담는 **새로운 단일 검토면**으로 제시할 것.
- **삭제 금지:** `faultmate/`, `web/`의 실행 코드, `scripts/` 연구·원본 추적·보정·모델 학습/평가 도구, `tests/` 과거 회귀 증거, `docs/`의 소스 MD5/라벨/라이선스·연구 및 계약 기록, `setup_windows.bat`/`start_windows.bat`. 유료 DeepSeek 외부 호출, 모델 재학습, 사용자 PC/SQLite/개인 데이터 변경, EXE·ZIP 배포 금지.

## 통합된 기능별 수정

| PR | 실제 반영 사항 | 유지되는 한계 |
|---|---|---|
| #40 | 첫 화면 목적·AI 사용 안내, 잠긴 버튼 이유 및 동의 흐름 | AI는 기존 7개 사례의 근거 검토, 범용 고장 탐색 AI 아님 |
| #41 | 이미 설정된 `DEEPSEEK_API_KEY`의 **존재 여부만** 로컬 메타데이터에서 재조회 | 서버 키 감지는 실제 API 인증 성공 증거가 아님 |
| #42 | 401·402·429·통신 실패/시간초과별 안내, 요청 중 입력 변경 시 과금 가능성 경고 | 자동 재시도 없음. 유료 실호출 미검증 |
| #43 | 모델 선택에서 빠진 원인·질문도 보존, 원인별 근거·한계·안전조건 표시 | 원인 확정/점검 허가/새 추론 학습 아님 |
| #44 | CSV 형식 검사 버튼에 파일 필요, 승인 ML 없음 안내, 로컬 RAR HTTP 오류, 파일 변경 시 오래된 결과 차단 | 생산 CSV ML 미승인, RAR 연구용 점수 미승인 |

## 이번에 실제 삭제한 Git 추적 파일 — 과거 브랜치 전용 CI 11개

다음 파일은 검토 당시 `push`/`pull_request` 트리거가 **과거 `work/faultmate-*` 개발 브랜치 전용**이고, 현재 `main` PR이나 수동 `workflow_dispatch` 진입점이 없음을 확인함. 현재 P7 통합 5-job 회귀가 각 코드 테스트를 포함하므로 워크플로 래퍼만 삭제. **스크립트/테스트/데이터는 그대로 두고 Git 이력에서 복원 가능**.

1. `.github/workflows/calibration-safety.yml`
2. `.github/workflows/cohort-coverage-safety.yml`
3. `.github/workflows/faultmate-ml-integrity.yml`
4. `.github/workflows/faultmate-regression.yml`
5. `.github/workflows/preintegration-cleanup-regression.yml`
6. `.github/workflows/stage6-program-integration.yml`
7. `.github/workflows/stage7-local-api-boundary.yml`
8. `.github/workflows/stage7-source-readiness-regression.yml`
9. `.github/workflows/stage7-windows-native-browser-acceptance.yml`
10. `.github/workflows/windows-integration.yml`
11. `.github/workflows/validate-k001.yml`

이는 **GitHub 현재 리뷰 브랜치의 파일 정리**이고 기존 Actions 이력·옛 브랜치·로컬 사용자 파일·원본 연구 자료·모델을 삭제하거나 저장공간 확보량을 보증하는 행위가 아님.

## 과거 파일 중 **삭제하지 않고 보존**한 경우

- 12개 공식 Paderborn 원본 MD5·80 MAT 전수감사와 연구용 학습 재현: `.github/workflows/official-paderborn-12-full-audit.yml`, `recombine-12-raw-audits.yml`, `real-paderborn-unitless-ml.yml` (특히 연구 CI의 수동 실행 경로 보존).
- 별도 설비용 독립 검증·원본/라이선스 조사·단위 변환 근거, 과거 개발 `docs/P0~P7` 및 `docs/experiments/`: 현 시점에 생산 승인 자료는 아니지만 **기존 근거 계보**임. 단순히 날짜가 과거라는 이유로 제거하면 안 됨.
- 실행 진입점·안전 게이트·테스트·수치 피처 및 미승인 모델 JSON. `DEEPSEEK_API_KEY` 실제 값은 읽거나 저장하지 않음.
- 최신 기준 통합 CI: `.github/workflows/stage7-known-damaged-ki21-replay.yml`의 **Linux 전체 Python/HTTP → Windows 배치 및 브라우저 → Chromium 동의/오류 → 공식 K001 원본 → 기존 KI21 손상 미탐 안전검사** 5개 작업.

## 자동화 안전 검증 및 차기 수동 검증

- `tests/test_p7_consolidated_cleanup_manifest.py`: 위 구형 CI 11개만 제거, 코드/원본/모델/감사 및 5-job 보호 워크플로 유지 확인.
- 변경 후 전체 Linux Python + Windows + Chromium + K001/KI21 실원본 CI를 **새 브랜치 최신 SHA 기준** 재실행하여 검증한다. (완료 결과는 PR 및 Actions 결과를 우선 확인)
- 계속 **미완료**: 실제 사용자 컴퓨터의 *최신 변경본* 확인, DeepSeek 유료 실인증/응답 및 계정 잔액, 독립 정상 베어링 외부 평가·SI 단위·생산 모델 승인·상업 라이선스, 최종 배포와 `main` 병합.
- 사용자가 다운로드 파일을 직접 요청하기 전까지 **ZIP/EXE 제작·전달 금지**.
