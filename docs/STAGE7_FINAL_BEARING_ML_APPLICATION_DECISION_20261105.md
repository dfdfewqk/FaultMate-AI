# FaultMate AI — 실측 베어링 ML ②단계 최종 적용 판단 (2026-11-05)

## 결론

**실제 Paderborn ML 학습 자체는 완료. 현장 및 FaultMate API의 정식 ML 적용은 지금 승인할 수 없다.** 이 결론은 프로그램 통합 실패가 아니라 원본 증거·검증 범위와 API 입력 계약의 불일치에 근거한다. 별도 사용자 수동 작업 없이 지금 검증 가능한 부분을 모두 자동 판단하도록 `scripts/decide_bearing_ml_application.py`를 추가했다.

`python scripts/decide_bearing_ml_application.py` 명령은 로컬 원본 모델/출처 메타데이터의 일치 여부를 확인하고 `production_model_decision=NO_GO_MISSING_INDEPENDENT_NORMAL_EVIDENCE_AND_INPUT_CONTRACT`를 반환한다. 선택적 `--out`은 새 JSON 문서만 생성하고 기존 증거를 덮어쓰지 않는다. 모든 외부 모델·유료 API·파일 다운로드 호출 및 추가 학습이 없다.

## 실제 보유한 증거

1. **Paderborn 원본 실측학습:** 기존 연구 파일 `docs/experiments/PADERBORN_BEARING_AGGREGATED_UNAPPROVED_20261105.json` SHA256 `84a7c059fa769d1b0e2bd0075ecba92bcd06ae24acf961e0ea2120d9d44a0ab0`. 베어링 10개 기반 개발 실험이며, 12개 무차원 특징을 베어링당 4개 운전조건×20회에서 집계함. 기존 모델 구조·추론 계약은 현재 프로그램의 **3개 SI 단위 CSV 입력**과 다르다. 원본 SI 센서 단위 보정 근거 없음.
2. **실제 독립 손상 베어링 추가 평가:** 원래 개발·열린 홀드아웃과 다른 가속수명 손상 베어링 8개로 고정 모델을 **한 번만 시험**, **7/8 검출**, KI21 **1건 미탐**. 원본 640개 MAT를 2026-11-05 CI에서 직접 검증함. [실제 원본 CI](https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41971495239). 신규 `decide` 명령은 이 CI를 참조할 뿐 8개 측정 JSON이 현재 브랜치에 없기 때문에 **점수를 재계산하거나 재시험했다고 주장하지 않음**.
3. **신규 정상 독립 시험:** Paderborn 공식 데이터에는 **정상 물리 베어링 총 6개**뿐이며 모두 이전 개발/시험에서 사용됨. [Paderborn 공식 출처](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download). 재분할하여 신규 검증이라고 주장하면 데이터 누수. 새로운 독립 정상 베어링으로 측정한 오경보율·특이도·전체 정확도는 **없음**.
4. **BJTU 원저자 배포 데이터:** 정상 상태 **레이블 1개**, 운전조건 **9개**, 조건당 센서 CSV **4개**. 문서상 36개 정상 CSV는 **36개 실제 정상 물리 베어링이 아님**. 독립 물리 ID 불명확, 다른 차축 베어링 모델·운전조건, 원본 약 30.4GB 제3자 추정, 원본 ZIP 무결성·상업적 이용권 미검증. [BJTU 원저자 IEEE Access](https://doi.org/10.1109/ACCESS.2025.3551603). [원본 폴더 구조 및 안전 접근 연구 PR #22](https://github.com/dfdfewqk/FaultMate-AI/pull/22).
5. **KAIST 부하/가변속 데이터:** 진동·전류가 있지만 Paderborn의 4운전조건×20회와 주파수/장치가 다름. [원논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC10036499/). 기존 냉동 모델의 새로운 정상 오경보 검증이라고 주장하면 안 됨.
6. **HUST 베어링 데이터 (추가 검토):** 원저자 논문에 **실제 정상 베어링 3개**가 포함된다고 보고하지만 **진동 전용 51.2 kHz**, 6204~6208 베어링, 부하 조건 3개. 모터 전류 채널이 없어 현 Paderborn 12차원 두 센서 모델 입력과 다름. 별도 *진동 전용 모델* 연구용으로는 가능하나 **현재 고정 Paderborn ML의 독립 정상 검증으로 사용할 수 없음**. [HUST 원논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC10327369/) · [원본 Mendeley](https://data.mendeley.com/datasets/cbv7jyx4p9/3).

### 적용 판단표

| 범위 | 판단 | 설명 |
|---|---|---|
| 실제 실험 원본 학습 | 수행됨 | 실측 연구 모델의 SHA256 및 개발 베어링 10개 확인 |
| 실제 손상 검출 추가시험 | 수행됨 | 8개 중 7개 검출, 미탐 KI21 1개(별도 CI 기록) |
| 정상 오경보율/특이도 | **미측정** | 신규 독립 정상 베어링/모델과 일치하는 원본 계약 확보 실패 |
| 원본 물리 센서 SI 단위 | **미확인** | 수치 단위 추측 금지 |
| 앱 3특징 SI CSV에 기존 12특징 연구모델 바로 연결 | **금지** | 특징 차원 및 베어링/측정 집계 규약 불일치 |
| 기존 규칙 기반 FaultMate P7.2 진단 | **그대로 유지** | 검증된 규칙 기반 진단·안전 홀드·사용자 동의 흐름 유지 |
| 연구 모델 자동 활성화 | **금지** | 앱 `/api/ml/inspect`는 여전히 `unavailable` |
| 실사용 모델 정식 승인 | **보류** | 본 연구는 설비 현장 사고 방지 판단/정비 허가가 아님 |

## 다음 작업 및 사용자 구분

- **① 원본 데이터·독립 정상 자산 조사:** 4개 기존 후보 + HUST를 살펴봤으나 기존 *동일 모델*에 쓰기 적합한 미개봉 정상 자산을 확보하지 못함. 자료 획득·출처 검증은 미완료, 조사 자체는 완료. 같은 기존 6개/36개 CSV를 새 베어링처럼 늘려서는 안 됨.
- **② ML 적용 여부 기술 판정:** 이 PR에서 **NO-GO 판정 자동화 완료**. 모델 재학습·무단 승인 금지. **실사용 ML 모델 완성**과는 별개.
- **③ DeepSeek 실제 유료 API 실연결:** 지금까지 모의 함수/로컬 실제 HTTP·서버 응답/보안 검사 완료. **실제 유료 API 요청은 사용자의 명시 승인과 유효한 본인 계정 키 없이는 수행하지 않음.**
- **④ 사용자 Windows PC 최종 수용검사:** GitHub Windows/Chromium 자동검사는 통과했지만 사용자 실제 PC 직접 조작만 별도 필요.
- **⑤ 최종 EXE/ZIP:** 모델/실연동/사용자 검증 완료 전 제작하지 않음.

**추가 자동검사:** `tests/test_bearing_ml_application_decision.py`은 연구모델 변조·홀드아웃 명단 바꿔치기·가짜 신규 정상/오경보 평가·사용자 동의 없는 API·미승인 모델 활성화를 모두 거절하는지 확인한다. `.github/workflows/stage7-ml-application-decision.yml`은 Linux, Windows, Chromium 전체 회귀를 재실행한다.

`main`, 기존 사용자 SQLite/원본 MAT/RAR, 모델 실험 파일, 기존 Draft PR, EXE 배포는 그대로 유지. **사용자가 지금 직접 해야 할 일은 없음.**
