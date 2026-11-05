# FaultMate AI — 7단계 로컬 브라우저/API 접근 보호 및 신규 정상 데이터 재조사 (2026-11-05)

## 실제 구현 범위

기존 P7.2 프로그램과 DeepSeek 요청별 동의/미리보기 SHA 검증은 유지하고, **외부 웹사이트에서 로컬 실행 중인 FaultMate API를 임의 호출하는 경로를 차단**했다. 본 변경은 `main`, 기존 RAR/MAT·SQLite/모델 계수, 사용자 입력을 수정하지 않는다. 최종 EXE·ZIP 제작, 유료 DeepSeek 실호출 없음.

- `faultmate/local_request_boundary.py`:
  - 요청 `Host`는 `127.0.0.1`, `localhost` 또는 **기존 FastAPI 테스트 도메인** `testserver`만 허용. 타 도메인의 DNS-rebinding 요청은 `/`, 정적 자산, `/api/*`에서 HTTP 403.
  - 외부 웹사이트가 `POST /api/agent/review`, `/api/integration/evidence-preview`, `/api/diagnostics/evaluate`, `/api/ml/inspect` 등에 요청할 때, `Origin`이 현재 `Host`와 동일하지 않거나 `Sec-Fetch-Site=cross-site`이면 라우트보다 먼저 403. `Origin: null`, 누락/다중 Host, 잘못된 포트·URL·사용자 정보 포함 Origin 거절.
  - 사용자의 정상 `http://127.0.0.1:8787/` 및 `http://localhost:8787/` 브라우저 접근은 유지. `Origin` 헤더가 없는 정상 로컬 CLI 호출은 유지. 운영체제 내부의 **악성 프로세스까지 막는 접근 인증 기능은 아님**; 시스템 방화벽/로컬 보안은 별도 문제.
  - 교차 출처/Host 차단 시 캐시 금지 및 상세 사용자 입력/토큰을 노출하지 않는 고정 `local_same_origin_required` 오류 반환.
- `faultmate/app.py`은 기존 요청 라우트·UI를 변경하지 않고 초기에 로컬 요청 검증 미들웨어만 추가.
- `tests/test_local_browser_request_boundary.py`는 Host/DNS 공격 문자열, 외부 Origin, `Sec-Fetch-Site:cross-site`, 정확한 미리보기 SHA+동의가 위조돼도 외부 호출 0회 보장, 정상 브라우저/CLI 입력의 동작 보존을 테스트. 테스트용 가짜 API 키 외 실제 DeepSeek 접속 없음.
- `.github/workflows/stage7-local-api-boundary.yml`은 전체 Linux Python/로컬 HTTP, Windows 원래 배치 실행/Python, Chromium P7.2 UI 회귀를 돌린다.

## 독립 정상 베어링 데이터 재조사: 현황은 변경 없음

원본 출처: [Paderborn University 공식 데이터 안내](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download).

- **정상 6개·손상 26개 물리 베어링**, 4개 운전 조건 × 20회 기록, 동기화된 진동/모터 전류. 기존 정상 K001~K006는 모두 연구 학습·개발 또는 이전 열린 시험에 사용해 **새 정상 외부시험 자산이 0개**.
- [KAIST 다양한 부하 조건 자료와 공식 논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC10036499/)에는 정상 데이터가 있지만 실험 장비·신호 수집주파수·운전조건이 Paderborn의 4조건×20회 및 동기 64kHz 채널과 다름. 다른 연구실에서 새 수집한 정상 데이터는 **새 도메인 연구용 검증**으로 접근해야 함.
- 임의 재표본화, 3조건을 4조건으로 보이게 만들기, 원본 반복 기록 수를 독립 물리 베어링 수로 세기, 이미 확인한 정상 기록을 '새 시험'이라 주장하는 행위 금지.
- 2026-11-05 실제 원본 검증된 손상 8개 고정 모델 추가시험 결과는 **7/8 검출, KI21 미탐**. 독립 정상 오경보율 미측정, 모델 정식 승인 금지.
- 모델 원본 Paderborn 자료 [CC BY-NC 4.0 사용조건](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter). 비상업용 교육·연구와 상업 배포 구분 필요.

## 자동검사와 실제 사용자 조건

GitHub Actions: https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/stage7-local-api-boundary.yml

- 현재까지 자동화된 AI 무과금 로컬 HTTP, 314개 이상의 Python 검사, Windows 배치 런처, Chromium 앱 경로는 유지.
- 실사용용 모델 자동 활성화 없음. 실제 독립 정상 자산/오경보 검증은 **완료했다고 표시하지 않음**.
- 유료 DeepSeek 실제 요청은 사용자 명시 동의 및 사용자 로컬 키·과금 설정이 있을 때만 실행 가능. 여기서는 수행하지 않음.
- 사용자 개인 Windows PC의 마지막 실제 실행 확인은 GitHub Windows runner 통과와 구분. 직접 사용자 조작이 필요할 때만 사용자에게 안내.

## 다음 단계

이미 확보한 정상 자료를 새 외부시험으로 위장하지 않고, **새로운 독립 물리 베어링의 원본 데이터 + 센서 수집 계약이 증명된 소스**를 별도 확보할 수 있을 때까지 모델 승인을 차단한다. 프로그램 쪽은 원본·동의·브라우저 경계를 포함한 회귀 자동화로 유지한다. 패키징은 사용자가 원했던 완성/검증 단계 이전에 수행하지 않는다.
