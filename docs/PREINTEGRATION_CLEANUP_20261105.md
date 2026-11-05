# FaultMate AI — 통합 전 불필요한 파일 및 데이터 정리 기록
기준일: 2026-11-05 KST

## 기준 브랜치와 대상 범위
- 기반: work/faultmate-stage5-deepseek-transport-20261105
- 정리 전용: work/faultmate-preintegration-cleanup-20261105
- main 직접 변경 없음. 원본/사용자 로컬 데이터를 찾아서 삭제하는 작업은 실시하지 않음.
- 기준 브랜치 Git 트리: 119개 추적 파일(파일 자체 합계 556279바이트, Git 내부 객체/이력 크기는 제외).
- 실제 .mat, .rar, .exe, .zip, 가공된 모델 파일은 현재 **Git 추적 파일 목록에 없음**. GitHub Actions runner의 임시 원본 및 로컬 PC 데이터는 Git 트리와 별개다.
- 당시 원격 브랜치 14개, 열린 PR 9개. 서로 연결된 개발 근거가 있어 무작정 브랜치/PR을 삭제하지 않는다.

## 실제 제거된 파일 (전용 정리 브랜치에서만)
1. test_commit.txt: 실제 앱 기능과 무관한 GitHub 쓰기 권한 확인용 파일.
2. .github/workflows/qa-ka04-duplicate.yml: KA04의 단일 17/18 재현용 과거 1회성 CI.
3. .github/workflows/ka04-raw-audit.yml: 8 MAT 부분 측정 감사용 과거 1회성 CI.
4. .github/workflows/ka04-integrated-audit.yml: 8 MAT 부분 감사 + 11개 미확인 판정용 과거 1회성 CI.
5. .github/workflows/agent-safety-regression.yml: 구형 특정 브랜치만 대상으로 한 AI 모의 검증 CI. Stage 5 최신 CI가 전체 안전 회귀를 포함한다.
6. .github/workflows/raw-audit-regression.yml: 과거 특정 브랜치만 대상으로 한 초기 원본 감사 CI. 최신 전체 코호트 및 앱 회귀가 해당 코드도 검사한다.
7. .github/workflows/paderborn-catalog-preflight.yml: 구형 분기에서만 돌던 메타데이터 사전검사 CI. 공식 카탈로그 검증기·테스트 자체는 보존한다.

과거 검증 결과 링크 및 커밋은 원래 브랜치·PR·Git 히스토리에 그대로 남는다. 실제 데이터 및 원본 감사 JSON은 삭제하지 않는다.

## 추가 정리
.gitignore의 누락된 경로를 보강:
- data/provenance/, data/evidence/, data/raw_audit_reports/, data/cohort_raw_audit.json
- audit-reports/, cohort_raw_audit.json
- .env.*, 로그, 커버리지, 브라우저 임시 파일
- 미완성 EXE, ZIP, 7z

위는 **앞으로 Git에서 추적하지 않도록 하는 설정**이며 기존 사용자의 PC나 CI 기록을 삭제하지 않는다.
현재 docs/PADERBORN_TRAINING_ASSETS.json은 공식 원본 MD5+라벨 카탈로그이므로 반드시 추적 상태로 유지한다.

## 유지해야 하는 필수 데이터·코드
- faultmate/ 전체: 규칙 기반 고장 검토, 지식 카탈로그, 로컬/AI/ML 읽기 전용 API 및 안전 차단.
- web/ 전체, setup_windows.bat, start_windows.bat: 기존 P7.2 화면과 실행 경로.
- scripts/ 아래 원본 MD5 확인/960 MAT 신호·중복 확인/센서 보정 근거 검증/CSV 변환/ML 학습·평가/리뷰 승인 스크립트.
- tests/ 전체: Python·브라우저·Windows/HTTP 회귀, AI 안전 검사, MAT 출처 검증. 과거 단계별 테스트도 P7.2의 퇴행 방지용이므로 삭제하지 않음.
- docs/ 아래 공식 라이선스·체크섬·라벨·시스템 계약·원본 감사 근거.
- .github/workflows/official-paderborn-12-full-audit.yml 및 recombine-12-raw-audits.yml: 960개 실원본 감사 재현 경로. 일부 원본 증거 Artifact는 7일 보관 정책 때문에 만료될 수 있다.
- .github/workflows/stage4-ml-regression.yml 및 stage5-agent-transport-safety.yml: 최신 위험 차단 검증의 근거.
- 기존 히스토리/연결 PR/브랜치는 코드 리뷰가 완료되기 전 일괄 제거하지 않음.

## 역사적 기록(현재 기능 설명으로 오인하지 말 것)
- docs/P0_* ~ docs/P7_* 및 docs/ANTIGRAVITY_*: 당시 설계/단계별 보고 기록. 당시 시점에 실측 학습, API 실호출 또는 Windows 직접 검증이 끝났다고 믿는 근거로 사용하지 않는다.
- docs/ML_DEVELOPMENT_COMPLETION.md: ML **개발 코드의 구현 기록**이지 실제 검증된 Paderborn 실측 모델이 만들어졌다는 증거가 아님.
- README.md 의 과거 P7.2 개발 보고 구간: 역사적 참고. 최신 개발 상태는 아래 링크가 우선.

## 실제 확인된 최신 상태 (2026-11-05)
- Paderborn 12개 베어링 × 80 MAT = 960개 원본 감사: PASS (github.com/dfdfewqk/FaultMate-AI/actions/runs/41958473911).
- KA04 내부 원시 신호 중복 4개 확인. 고유 956개 기록.
- MAT 수치의 SI 단위/감도/오프셋에 대한 출처 지정 근거는 미확정: 실제 학습/모델 활성화 차단.
- Stage 4 학습 경계·독립 베어링 단위 평가 코드 및 소프트웨어 테스트 준비. 실제 실측 모델 없음.
- Stage 5 최신 DeepSeek 모델 deepseek-flash에 맞춘 모의 HTTP 오류·쿼터·타임아웃·동의 검증: 241 테스트 통과 (github.com/dfdfewqk/FaultMate-AI/actions/runs/41961852370), **실제 유료 호출 없음**.
- 6단계 최종 프로그램 통합 및 7단계 사용자 Windows/Linux/UI 종합 검증은 아직 미수행.
- 8단계 최종 배포용 EXE·ZIP 제작 없음.

## 통합 직전 검증 및 되돌리기
- 별도 브랜치에서만 정리했으며 main/원래 Stage 5 브랜치/PR을 변경하지 않았다.
- 새 전체 회귀와 Windows/HTTP/JS 테스트 통과 후 Draft PR로 보관.
- 제거한 파일은 해당 경로의 원래 Stage 5 커밋 dac7fd1d81c3f4b2ef987dd054e6c0cb1cd0dcdd에서 복구 가능.
- 기존 Windows 로컬 폴더, .gitignored 자료, 연결된 클라우드 저장소, 오래된 Actions artifact, Git 객체의 실제 사용/용량은 여기서 지우거나 재검증하지 않았다. 따라서 실제 디스크 공간을 많이 확보했다고 주장하지 않는다.
