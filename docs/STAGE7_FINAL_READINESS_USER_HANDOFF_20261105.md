# FaultMate AI — 7단계 로컬 사전검증과 사용자 인계 기준 (2026-11-05)

## 목적

기존 `dfdfewqk/FaultMate-AI`의 P7.2 화면·로컬 진단·DeepSeek 요청별 근거 미리보기/동의·미승인 ML 차단을 그대로 유지하고, **코드로 확인할 수 있는 것**과 **사용자 Windows PC 및 실제 유료 API에서만 확인할 수 있는 것**을 한 번에 구분한다.

이번 작업은 **검증 보조 자동화이지 최종 EXE 배포, 새 ML 모델 승인, 실제 유료 DeepSeek 호출이 아니다.**

## 신규 명령

```shell
python scripts/preflight_final_acceptance.py
```

출력은 JSON 한 개이며 기본적으로 파일·DB를 만들지 않는다. 별도 신규 보고서를 남기려는 경우에만:

```shell
python scripts/preflight_final_acceptance.py --out my_new_readiness_report.json
```

이미 같은 이름의 파일이 있다면 덮어쓰지 않고 실패한다. 원본 데이터·SQLite·환경변수 값을 출력하거나 읽지 않는다.

### 자동 판정 항목

| 자동 점검 | 확인 내용 |
|---|---|
| Python | 기존 실행 요구 조건 3.10 이상 |
| 프로젝트 경로 | 원래 FaultMate 프로젝트의 FastAPI 앱을 불러왔는지 |
| 서버 바인딩 | 127.0.0.1 로컬 전용 기존 런처 설정 |
| 기존 화면 | P7.2 HTML·JS·CSS가 존재하고 비어 있지 않은지 |
| 기존 상태 | 앱 이름·UI P7.2, 과거 호환 `phase=P2` |
| 기존 7개 사례 | 설비 규칙 기반 사례가 전부 유지되는지 |
| 긴급 위험 차단 | 급박한 위험에서 원인 후보 차단, AI 전송 0건 |
| AI 동의 보안 | 미리보기 SHA 누락·동의 거절 시 외부 요청 0건 |
| 제어 방지 | 원격 제어·인터록 우회·자동 재시작 불가 |
| ML 오승인 방지 | 현재 실사용용 검증 모델 없음, 실험 모델 자동 추론 불가 |
| 실측 모델 원본 | 10개 개발 베어링 실험용 모델의 SHA-256 내용 보존 |
| 정상 데이터 정직성 | 새로 검증된 독립 정상 베어링은 0개, 전체 정확도·오경보율을 임의 계산하지 않음 |

모든 자동 점검을 통과해도 `automatic_local_checks_passed=true`일 뿐, `release_ready=false`와 `release_gate=BLOCKED_PENDING_EXTERNAL_VALIDATION_AND_USER_ACCEPTANCE`는 그대로 유지한다. **준비상태 프로그램이 실제 네트워크·사용자 PC·외부 실측 데이터의 진위를 자동으로 확인했다고 주장하지 않는다.**

### 이제 개발자가 처리 가능한 범위

- Linux 전체 Python·HTTP, Windows 실제 배치 실행 및 Python, Chromium P7.2 화면 통합 테스트를 계속 자동화.
- 실제 Paderborn 원본 960개에서 956개 중복 제외·실제 학습 및 추가 손상 8개 고정 모델 평가 기록 보존. 손상 베어링 7/8 검출, KI21 한 개 미탐.
- 추가 독립 정상 베어링 자료가 나오면 별도 원본 체크섬·물리 베어링 ID·채널/속도·운전조건 비교 후 기존 모델에 바로 적용 가능한지 보수적으로 확인.
- 무과금 DeepSeek 로컬 HTTP 모의 서버 검증 결과 보존. 과금 발생 가능성 있는 API는 사용자 동의 없이 절대 요청하지 않음.

### 사용자에게 **직접 요구할 수 있는 단계만** 별도 기록

1. 최종 Windows PC에서 기존 `start_windows.bat`을 실제로 실행하여 화면·진단·긴급 중단·종료 확인. GitHub Windows runner 통과는 사용자 자신의 PC 실행 성공과 다르다.
2. DeepSeek **실제 유료 API 검증을 꼭 원하는 경우에만** 사전에 API 비용과 호출 범위에 명시적으로 동의하고 키를 자신의 Windows 환경변수에만 설정. 이 키를 대화나 GitHub에 보내지 않기.

새로운 외부 정상 베어링은 **연구/검증의 외부 데이터 의존조건**이지 사용자가 반드시 직접 측정하라고 떠넘기는 작업이 아니다. 확보하기 전에는 ML 현장 적용 승인을 보류한다.

### 기존 소스 및 데이터 보존

`main`, 기존 Draft PR, 원본 Paderborn RAR/MAT, 학습 모델 실측 데이터, SQLite/사용자 파일, 기존 프로그램 API와 UI를 덮어쓰지 않는다. 새 배포 스크립트/EXE/ZIP 제작·유료 DeepSeek 호출·DeepSeek 키 저장/유출 없음.

## CI 검증

`.github/workflows/stage7-final-readiness-gates.yml`은 Linux, Windows, Chromium을 각각 독립적으로 돌린다. 특히 Python 자동검사 후 `scripts/preflight_final_acceptance.py`를 실행해 자동 통과와 **출시 차단**의 구분을 시험한다.

[GitHub Actions 최신 실행](https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/stage7-final-readiness-gates.yml)

사용자가 직접 실행하기 전까지는 사용자 PC 최종 수용검사 **미완료**, 실측 ML의 새 정상 외부검증 **미완료**, 유료 DeepSeek 실연동 **미완료**로 기록한다.
