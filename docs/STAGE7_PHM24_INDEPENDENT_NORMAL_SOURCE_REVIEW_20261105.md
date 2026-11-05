# FaultMate AI — 독립 정상 베어링 후보 PHM24/BJTU-RAO 검토 (2026-11-05)

## 이번에 조사한 후보

- 기존 **Paderborn** 원본 자료: 실제 정상 K001–K006의 6개 물리 베어링이 모두 이미 학습·개발·열린 시험에 사용돼, 같은 6개를 기록 단위로 다시 나누더라도 새 독립 정상 성능을 검증할 수 없다. [대학 공식 원본 안내](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download).
- **PHM Challenge 2024 / BJTU-RAO railway bogie**: 2025·2026 연구 논문에서 **정상 상태와 여러 고장 상태**, 차축 베어링·기어박스·구동모터 및 **진동/전류 동시 64 kHz 측정**을 설명한다. Paderborn과 *샘플링 주파수*는 같지만, 지하철/철도 구동계 **총 9개 운전조건**과 차축 베어링을 사용한다. 기존 Paderborn **6203 볼베어링 4개 운전조건 × 20회**와 구조적으로 다른 데이터다.
- [Oxford Academic, Generalizable fault detection and diagnosis (2026)](https://academic.oup.com/tse/article/8/2/tdag011/8644296): PHM24 9개 조건·64 kHz 진동/전류·정상/고장 상태 출처.
- [Emerald, unsupervised domain adaptation (2025)](https://doi.org/10.1108/SRT-11-2024-0017): PHM24/BJTU의 3개 학습 조건 + 6개 다른 평가 조건, 21개 동기 측정 채널(3상 전류 포함) 설명.
- [비공식 재현 매핑 연구](https://github.com/jonathanadamrico/BJTU_PHM_Beijing_Benchmark): PHM Beijing 대회 자료가 BJTU-RAO 원본의 일부와 중복될 수 있음을 지적한다. 이 저장소의 **MIT 라이선스는 소스 코드 라이선스일 뿐 원본 데이터 재배포·상업사용 권리를 보장하지 않는다**.
- [원저자 IEEE Access 원본 데이터 안내(2025)](https://doi.org/10.1109/ACCESS.2025.3551603)에 **원본 배포 링크**가 기재되어 있다: [Google Drive 폴더](https://drive.google.com/drive/folders/1RlZvFw-v07VvsL2Ni9cS7iFrTPDIhn2r?usp=sharing) 및 [Baidu Netdisk](https://pan.baidu.com/s/1S5F8URapHPArX2mV6FzDfA?pwd=9t74). 다만 **배포 링크의 존재와 실제 파일 다운로드/원본 검증은 다르다.** 이번 작업에서는 폴더 속 개별 원본을 받거나 검사하지 않았고, 공신력 있는 **정상 물리 베어링 개별 ID, 원본 SHA/공식 체크섬, 실제 독립 개체 수, 데이터 라이선스**는 아직 확인되지 않았다. 논문의 CC BY 라이선스도 원본 데이터 사용 허가로 간주하지 않는다.

## 데이터 적합성 판단

| 검사 기준 | PHM24 확인 상태 |
|---|---|
| 정상/고장 라벨 존재 | 논문에서 보고 |
| 진동·전류 동시 측정 | 논문에서 보고 |
| 진동·전류 명목 샘플링 주파수 64 kHz | 논문에서 보고 |
| 동일 6203 베어링/센서 위치 | **아님** (철도 차축 베어링/다른 장비) |
| Paderborn 4가지 동일 운전조건 | **아님** (9개 서로 다른 조건) |
| 베어링 1개당 80회 원본 기록/라벨 | 미검증 |
| 별개의 실제 정상 물리 베어링 ID | 미확인 |
| 원본 RAR/MAT/원신호 체크섬 검증 | 미수행 |
| 원저자 배포 링크 존재 | **논문에 Google Drive·Baidu 링크 확인**, 개별 파일 접근/무결성 검사 미실시 |
| 공식 원본 데이터 이용 라이선스 | **미확인** (논문 자체의 CC BY와 구분) |
| 기존 Paderborn frozen 모델 직접 평가 | **불가 — 계약 불일치** |

**결론:** PHM24/BJTU-RAO는 **연구 가치가 있는 새로운 외부 도메인 후보**지만, 기존 Paderborn에서 개발한 12차원 무차원 특징 모델에 단순히 정상 데이터를 넣어 오경보율을 산출해서는 안 된다. 원본 자료 확보 후에도 **별도 장비·수집 조건 모델의 외부 도메인 검증 및 독립 자산 분할**이 먼저 필요하다.

## 코드 변경 (기존 모델/UI 변경 없음)

- `docs/EXTERNAL_HEALTHY_SOURCE_CANDIDATES_20261105.json`: 기존 세 후보에 네 번째 PHM24 출처 추가. 64k 두 채널/9조건, 불확정 원본 라이선스/원본 측정 미검증 상태를 명시.
- `scripts/audit_external_healthy_compatibility.py`: 공개 출처 식별·조건·주파수·데이터 권한·PHM/BJTU 중복 가능성을 고정해 원본 검증 없는 호환 판정을 차단. 네 후보 모두 `direct_frozen_model_prediction_allowed=false`.
- `tests/test_external_healthy_compatibility.py`: PHM24 64k 조건을 참조하되 **4가지 Paderborn 조건으로 허위 변환, 모델 자동 승인, 원본·라이선스 수집 완료 조작 시 실패**하는 테스트 추가.
- `scripts/preflight_final_acceptance.py`: 로컬 출시 준비 상태 점검 시 후보 4종의 근거 게이트가 모두 수행되었는지 확인. 여전히 `release_ready=false`.
- `.github/workflows/stage7-phm24-source-review.yml`: 기존 Linux/Windows/Chromium 앱 전체 회귀 및 새 근거 조건 테스트.

## 사용자에게 요구하는 작업

**지금 직접 할 일은 없다.** 외부 라이선스·개별 베어링 측정 출처 확보는 개발과 연구 증거 문제이며, 정보가 없는 상태에서 사용자에게 데이터 수집 또는 제품 설치를 요구하지 않는다.

다음 외부 단계는 원본 접근 가능 여부와 이용조건 확인 → 정상 물리 베어링별 ID·전류/진동 채널 대조 → 독립 분할 계획을 확정한 **별도 연구용 평가 경로**를 만드는 것이다. 기존 정식 사용자 앱에는 실험 모델을 활성화하지 않는다.

**미완료:** 새로운 진짜 독립 정상 Paderborn-동등 데이터의 ML 평가, 실사용 모델 승인, DeepSeek 유료 실제 요청, 사용자 자신의 Windows PC 최종 조작, EXE/ZIP 배포. `main`과 기존 원본·모델 계수·SQLite는 수정하지 않는다.
