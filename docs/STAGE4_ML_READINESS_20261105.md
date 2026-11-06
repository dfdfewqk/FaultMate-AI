# FaultMate AI — 4단계 ML 학습·독립평가 코드 점검 (2026-11-05)

## 핵심 판정: 파이프라인·자동 테스트 완료 / 실측 학습은 차단 유지

3단계 실제 원본 감사 증거:
- https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41958473911
- 정상 K001~K006 6개 / 손상 KA04·KA16·KB23·KI04·KI16·KI18 6개
- 총 960개 원본 MAT의 공식 MD5/압축/측정 구성 및 신호 중복 감사 통과
- 중복 4개 (KA04 18, 15, 19, 20번의 각각 해당 조건 첫 측정과 중복), 원시 신호 고유 956개
- sensor Unit 값이 공란이며 저장된 센서 수치의 SI 변환·보정 근거 없음

실측 원본 검증 성공이 곧 물리 단위 확정이나 ML 학습 준비 완료를 뜻하지는 않는다.

## 이번 단계 코드 변경

### 1. 실측 모델 학습 시작 전 필수 검증 (scripts/ml_stage4_preflight.py)

프로그램의 학습 함수 및 CLI는 모두 다음 다섯 입력이 존재해야 비로소 검토를 시작한다.
1. 12개 원본 감사 JSON이 있는 폴더 (--raw-audits-dir)
2. 이를 종합한 960개 전체 감사 JSON (--raw-audit-summary)
3. 데이터셋 원본 MAT 수치의 단위와 변환 관계를 실제 확인한 **독립적 사람 검토** (--source-review)
4. 위 검토가 SHA-256으로 결속한 원본 기관 문서 또는 데이터 작성자 답변 (--evidence-document)
5. 학습 CSV의 모든 행을 검증된 MAT 기록 해시와 연결하는 JSON (--feature-ledger)

검증 규칙:
- 3단계 종합 JSON을 12개 개별 감사 JSON에서 다시 계산해서 동일한지 확인한다.
- 한 행마다 알려진 베어링 ID, 공식 healthy/damaged 라벨, 공식 실측 기록명 (CSV의 trial_id가 원래 MAT 파일명과 정확히 일치), 원본 MAT SHA256, 두 센서 신호 SHA256, 특성값 행 해시를 확인한다.
- KA04 원시 신호 중복 4건, 다른 자산의 원시 데이터 재사용, 서로 다른 라벨/출처와 변조된 특성값을 차단한다.
- 진동/전류 입력 원시 단위와 SI 출력 단위, 실제 source-specific gain/offset, 적용되는 장비/운전 조건 범위가 검토 문서에 포함되어야 한다. 원본에 이미 SI 값이 저장된 경우에는 변환값 1/오프셋 0이어야 한다.
- 원본 데이터와 연구 결과를 CC BY-NC 4.0 비상업 조건으로 취급한다.
- 문서 해시와 메타데이터 검사는 검토 흔적을 보장할 뿐, 실제 센서 물리적 보정이 사실인지 사람 대신 독립적으로 증명하지 않는다. 근거를 직접 검토해야 한다.

**현재 위 조건 3·4·5를 만족하는 실제 문서는 없으므로 학습과 평가 수치 발표를 진행하지 않는다.**
3단계의 raw JSON은 physical_units_verified=false, training_permitted=false 상태로 유지된다.

### 2. train_ml.py 독립평가 개선

- 베어링(asset_id) 단위로 train/validation/test를 배타적으로 분할한다.
- StandardScaler는 train 부분에만 학습하고, validation/test에 적용만 한다.
- 검증 세트에서 기존 다수 클래스 기준 분류기와 후보 모델을 비교하며, 이제 **물리 베어링당 하나의 결과**를 내는 보조 기준도 통과해야 한다.
- 독립 test 베어링별 평균 모델 점수로 베어링 판단값을 계산한다.
- 시험 결과에는 기존 녹음 구간별 macro-F1·혼동행렬·손상 누락·정상 오경보와 **베어링 단위 macro-F1·혼동행렬·손상 누락·정상 오경보**를 함께 기록한다.
- 12개 중 시험 셋에 들어갈 독립 베어링은 매우 적다. 중복 측정 80회가 독립 자산 80개를 뜻하지 않으며 현장 일반화 성능을 보장하지 않는다.
- 학습 후에도 모델 상태는 evaluated_pending_review이다. 별도 사람 승인 전 활성화하지 않는다.
- 기존 평가 폴더/모델 파일 덮어쓰기를 금지한다.

### 3. 모델 승인 및 런타임 차단

- review_bearing_model.py는 원본 감사/단위 검토/특성 추적 해시가 모델 평가 파일과 동일한지, 베어링 단위 평가 수치와 혼동행렬이 맞는지 추가 확인한다.
- faultmate/integration/ml.py는 provenance_check와 베어링 수준의 독립평가 정보가 없는 validated 모델을 로드하지 않는다.
- 소프트웨어 테스트용 합성 데이터만 명시적인 내부 함수 test_fixture_only=True를 사용한다. **이 옵션은 CLI에서 사용할 수 없고 실제 Paderborn source_id/라이선스가 있으면 차단한다.**
- 합성 데이터 테스트의 점수는 실제 정확도, 실측 학습이나 사용자 PC 검증 결과로 인용하지 않는다.

## 이후 실제 학습 시 CLI 예시 (지금 실행하지 말 것)

다음 파일들이 원본과 보정 문서로 **진짜 검증되고 준비된 다음**에만 해당한다.

    python scripts/train_ml.py data/converted/reviewed_bearing_features.csv --output models/evaluation/new_reviewed_run --raw-audits-dir data/raw_audit_reports --raw-audit-summary data/cohort_raw_audit.json --source-review data/provenance/signed_calibration_review.json --evidence-document data/evidence/primary_source_confirmation.pdf --feature-ledger data/provenance/feature_row_ledger.json

feature_ledger.json는 dataset=paderborn_bearing_datacenter, feature_csv_sha256, records=[{asset_id, trial_id(원본 MAT 전체 파일명), source_mat_sha256, source_raw_signal_fingerprint, feature_row_sha256}, ...] 구조로 작성한다. 실제 검증을 통과한 값만 입력한다.

source_review.json는 dataset/source_id/license, feature_csv_sha256, raw_audit_summary_sha256, stored_mat_numeric_units_verified=true, calibration_applies_to_whole_cohort=true, bearing_labels_verified=true, feature_output_units(진동 m/s^2 / 전류 A), 원본 채널별 source_channel_to_si의 source_unit·scale_to_si·offset_in_source_unit, evidence_type·evidence_url·evidence_location·evidence_document_sha256·saved_numeric_mapping_explanation·reviewed_by·reviewed_utc를 요구한다. **증거를 조작하거나 승인 날짜·보정계수를 추정해 입력하지 않는다.**

## 실제 검증 결과

- GitHub 전체 회귀 검사: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41960152167 — 226/226 통과
- 추가 원본 SI 변환 경로 반영 후 회귀: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41960253551 — 통과
- 유료 DeepSeek API 실제 호출 없음. 실제 물리 단위 없는 Paderborn CSV/모델 생성 없음. 기존 main/자료/기능 삭제·재설치·배포 없음.

**4단계 상태: 학습 안전 검증·자산 단위 독립평가 구현과 자동 검사 완료. 실제 학습 및 독립 시험 결과는 물리 단위·검토 자료의 부재로 미완료.** 나중에 보정 근거가 확보되면 이 구조를 통해 실데이터를 학습하고 사람이 승인 여부를 판단한다.
