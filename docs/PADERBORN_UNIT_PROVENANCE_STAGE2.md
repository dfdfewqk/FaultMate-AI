# FaultMate AI — Paderborn 센서 단위 근거 검증 (2단계)

**상태 (2026-11-05): 안전 검증 모듈 및 합성 테스트 완료. 실제 .mat 물리 단위 변환은 보정 근거가 없어 차단 상태.**

## 검증한 사실

- Paderborn University의 공식 자료는 모터 전류와 베어링 하우징 진동을 동기 측정했다고 설명한다. 정상 베어링 6개, 손상 베어링 26개, 4개 운전 조건, 조건별 20회의 약 4초 측정이 제공된다.
- 공식 장비 자료에 전류 변환기 LEM CKSR 15-NP와 진동 센서 PCB 336C04가 제시된다.
- 그러나 센서의 측정 대상이 전류/가속도라는 사실만으로 .mat 저장값이 곧 A 또는 m/s²라고 결론낼 수 없다.
- 실제 측정 체인에 적용된 감도, 영점 오프셋, DAQ 변환 및 기록 단계의 스케일은 별도 근거가 필요하다. 샘플링 레이트만으로 단위 보정은 불가능하다.
- 과거 로컬 조사에서 .mat Unit 메타데이터가 비어 있다고 보고되었지만, 이 단계에서 원본 파일을 다시 읽은 것은 아니다.
- 기존 로컬 feature/ml-data-integration 브랜치의 MAT→CSV 변환 스크립트는 원격 main에 없다. 따라서 원격 신규 파일로만 작업하고 기존 Windows 로컬 코드에 덮어쓰지 않는다.

공식 출처:
- https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download
- https://mb.uni-paderborn.de/en/kat/forschung/bearing-datacenter/test-rig-and-measurement-equipment
- https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter

## 물리 단위 게이트

- scripts/sensor_unit_gate.py 는 vibration_1 → m/s^2, phase_current_1 → A 두 채널을 검사한다.
- 이미 물리 단위로 저장되었다는 근거가 있으면 mode=already_physical 와 source_unit=목표단위를 기록한다.
- 저장값이 센서 출력 전압이면 mode=calibrated_voltage, source_unit=V 를 기록하고 적용 가능한 실제 sensitivity_v_per_unit, zero_offset_v 와 1차 증거를 요구한다.
- 전압 변환은 반드시 (raw_voltage - zero_offset_v) / sensitivity_v_per_unit 순서다. 전류 센서의 기준 전압을 생략하지 않는다.
- raw_mat_sha256 을 실제 원본 .mat 파일 해시와 확인한다.
- 채널별 evidence.file, evidence.sha256, evidence.source_url, evidence.calibration_scope를 확인한다. 근거 파일이 존재하고 해시가 일치해야 한다.
- physical_unit_review.approved=true, reviewer, UTC reviewed_utc를 요구한다.
- 모든 조건을 만족하면 ready_for_physical_csv라는 검토 상태가 된다. 이는 인간이 문서 적용 범위를 확인했다는 메타데이터 조건을 만족했다는 뜻이지 과학적 진실을 자동으로 증명한 것은 아니다.
- 누락/불일치가 있으면 blocked 및 physical_csv_allowed=false. 원시 기록만 보존한다. 물리 단위 특성 CSV와 학습 모델을 생성하지 않는다.
- 이 검증 통과와 별도로, 원본 라벨/베어링 그룹 중복/데이터 누출 검증 및 실제 ML 독립평가가 필요하다.

## 로컬에서 확인할 때

원본과 보정 근거 파일이 실제 준비된 환경에서 다음 명령을 실행한다.

    python scripts/sensor_unit_gate.py --manifest data/provenance/K001_1.json --mat data/raw/N15_M07_F10_K001_1.mat --evidence-root data/evidence

필수 JSON 키는 dataset, asset_id, raw_mat_sha256, channels, physical_unit_review 이다.
각 채널의 source_unit, target_unit, mode, evidence 정보가 필요하고,
calibrated_voltage 방식은 sensitivity_v_per_unit 와 zero_offset_v를 추가 요구한다.
검증되지 않은 임의 숫자나 다른 장비의 카탈로그 보정계수로 승인 기록을 생성하지 않는다.

과거 로컬 MAT 변환기를 통합할 때는 기존 이력을 보존하고 evaluate_manifest()의 physical_csv_allowed가 참인 경우에만 쓰기를 허용한다. 실제 원본이 확인되기 전 ML 상태는 unavailable로 유지한다.

## 검사 범위와 제한

- tests/test_sensor_unit_gate.py: 합성 파일/보정 문서 픽스처 10개 테스트.
- 과거 로컬 변환기 수정 및 통합, 실측 .mat 파싱, 실제 보정계수 확인은 아직 아니다.
- Paderborn 원본 데이터는 CC BY-NC 4.0. 상업적 적용은 별도 허가 확인이 필요하다.
