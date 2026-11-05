# FaultMate AI — Stage 7 외부 정상 베어링 자료 적합성 감사 (2026-11-05)

## 목적과 수행 범위

기존 FaultMate AI의 정상 동작을 보존하면서 **실측 ML 모델의 오경보율을 새로운 정상 베어링으로 검증할 수 있는지** 확인한다. 이 보고서는 *공개 자료의 메타데이터 및 입력 계약 점검*이며 **외부 정상 베어링의 원본 파일을 내려받아 특징을 추출하거나 모델을 평가한 보고서가 아니다.**

개발 기준:
- 연구용 frozen Paderborn 베어링 대표 특징 모델 SHA-256: `84a7c059fa769d1b0e2bd0075ecba92bcd06ae24acf961e0ea2120d9d44a0ab0`
- 이전 10개 개발 베어링: K001/K002/K003/K004/K005/KA04/KA16/KB23/KI04/KI16.
- 이미 확인된 기존 2개 시험 베어링: K006/KI18.
- 이후 처음 보는 손상 베어링 8개는 실제 640개 MAT 검증 후 **7/8 검출, KI21 1개 미탐**, 정상 0개; https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41971495239.
- 기존 Paderborn 정상 베어링은 K001~K006 총 6개로 모두 이미 사용됨. 단순한 기록/윈도 재분할은 새 독립 베어링을 만드는 방법이 아니다.
- 새 모델을 학습하거나 유료 AI 요청을 보내는 작업, 원본 데이터 삭제, 배포 파일 생성은 하지 않음.

## 공식 소스 후보 3종 비교

| 소스 | 정상 자료 포함 여부 | 센서·조건 | 입력 계약 적합성 | 이번에 새 정상 검증에 사용? |
|---|---|---|---|---|
| Paderborn 원본 K001~K006 | 정상 물리 베어링 6개 | 진동+위상전류 64kHz, 4조건×20회 | 신호 구조 동일하지만 **6개 모두 이미 개봉/사용** | 아니오 |
| KAIST (Jung et al.) 부하 변화 데이터 | 정상 상태 포함 | 진동 25.6kHz, 전류 50kHz, 3개 부하 조건 | **수집 장비·채널·운전조건이 다르고** 실제 새 독립 정상 자산 수와 원본 체크섬 미검증 | 아니오 |
| KAIST (Jung et al.) 가변속 데이터 | 정상 상태 포함 | 진동 25.6kHz, 전류 100kHz, 가변속 | **실험 속도 및 수집 계약이 다름**, 4조건×20회 베어링 입력 조건 충족 증거 없음 | 아니오 |

근거:
- [Paderborn University 공식 데이터 안내](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download) — 정상 6/손상 26, 4조건, 신호 구조.
- [Lessmeier 외 (2016) 공식 논문](https://mb.uni-paderborn.de/fileadmin-mb/kat/PDF/Veroeffentlichungen/20160703_PHME16_CM_bearing.pdf) — 수집 장치·조건·라벨.
- [KAIST/연구진 부하 변화 데이터](https://data.mendeley.com/datasets/ztmf3m7h5x) — 정상, 베어링 내륜·외륜 손상, 샤프트·로터 이상; 3부하·진동/전류 데이터.
- [KAIST/연구진 가변속 데이터](https://data.mendeley.com/datasets/vxkj334rzv) — 정상 및 손상, 가변속, 진동·전류.
- [원본 DAQ 설명 논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC10036499/) — 센서별 주파수와 장치.
- Paderborn 원본 CC BY-NC 4.0, KAIST 자료 공개 메타데이터의 CC BY 4.0. 각 데이터의 사용 조건과 상업적 재사용 가능 여부를 구분한다.

## 구현한 차단기

`docs/EXTERNAL_HEALTHY_SOURCE_CANDIDATES_20261105.json`
- 기존 모델·베어링·특징/수집 조건을 고정한 공개 메타데이터 목록.
- 메타데이터를 실측 원본의 개별 체크섬·수집 조건이 검증된 것으로 표기하지 않음.
- KAIST에서 **서로 다른 물리적 정상 베어링 몇 개인지, 원본을 실제로 검증했는지** 미확정이면 참조만 가능, 계산 불가.

`scripts/audit_external_healthy_compatibility.py`
- 세 후보의 공식 URL, 라이선스, 샘플링 주파수, 운전조건, 기존 사용된 K001~K006와의 교집합, 원본/checksum 검증 및 센서 동기화 근거 상태를 검사.
- 형식 누락·서로 다른 소스를 Paderborn 4조건이라고 허위 변경·정상 자산/원본 검증값 거짓 선언이 있으면 즉시 실패.
- **모델을 불러와 추론하거나 외부 API 호출하지 않음**. 승인 코드/정확도·오경보율을 만들지 않음.
- 3개 후보 모두 원본-수준 독립 정상 데이터 증거가 불충분하므로 `additional_original_independent_healthy_measurements_required` 반환.

`tests/test_external_healthy_compatibility.py`
- 정상 6개 재사용 차단, KAIST 부하/속도 불일치 차단, 원본 확인 없이 새 정상 자산 허위 판정 차단, 출력 수치 위조 금지 테스트.

`.github/workflows/stage7-source-readiness-regression.yml`
- 전체 Linux Python+HTTP, Windows BAT/pytest, Chromium 화면/DeepSeek **모의 호출** 통합 재검증.
- `DEEPSEEK_API_KEY` 공백, 유료 AI 없음, 모델 자동 승인 없음, 임시 배포파일 없음.
- GitHub Actions: https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/stage7-source-readiness-regression.yml

## 현재 과학적 결론

**실제 8개 새 손상 베어링에서 7/8이 검출됐지만, 새 정상 베어링이 0개이므로 독립적인 오경보율/특이도/전체 정확도는 측정할 수 없다.** 기존 Paderborn의 건강한 기록을 랜덤 분할해 정상 베어링을 늘리는 것은 데이터 누수다.

KAIST는 다음 세대를 위한 **독립 도메인 데이터 후보**다. 기존 Paderborn 연구용 모델에 일방적으로 25.6kHz/50–100kHz 자료를 정규화·재표기해 적용할 수 없다. 새로운 수집 계약, 채널 정렬, 베어링별 독립 라벨·ID, 원본 파일 해시, 운전 조건/반복측정 수준의 대응, 사전등록한 새 평가가 필요한 별도 연구 경로다. 이 요건을 충족해도 현장 사용 승인은 자동이 아니다.

## 남은 실제 작업

1. 원본 기반으로 추적 가능한 **새로운 실제 정상 물리 베어링**의 센서 측정·동시 수집/학습 계약을 확보한다. Paderborn과 다르면 독립 도메인 평가 및 적응 모델을 **구분해서 개발·검증**한다.
2. 새로운 미사용 정상 자산의 수를 확인하고, 체크섬·측정 신호·세션 ID·라벨 출처 검증과 평가 계획을 사전 고정한다.
3. 별도 정상 베어링에서 실제 **오경보 건수**를 구한 뒤, 기존 새 손상 8개에서 발생한 KI21 미탐 등과 종합하여 승인 여부를 판정한다. 이전에 이미 본 데이터로 새 정확도라고 주장하지 않는다.
4. 최종 Windows 사용자의 실기기·실제 API 연결은 별도 수용 단계다. 외부 DeepSeek 실연동은 **사용자 명시 동의와 API 요금 확인 전에는 실행하지 않는다.**
5. `main` 직접 변경·기존 사용자 데이터 삭제·원본/모델 덮어쓰기·최종 EXE/ZIP 배포는 하지 않는다.

> 이번 단계는 **검증할 수 없는 수치를 막는 작업**까지 수행한 것이고, 새 정상 베어링 데이터의 확보·측정, ML 완전 승인, 유료 AI 실호출 및 배포를 완료했다는 뜻이 아니다.
