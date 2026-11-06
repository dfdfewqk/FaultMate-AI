# FaultMate AI — Paderborn 원본 960개 MAT Y.Data 저장 단위 실제 근거 감사 (2026-11-06)

## 감사 완료 범위와 숫자

[GitHub Actions 42189632379](https://github.com/dfdfewqk/FaultMate-AI/actions/runs/42189632379)의 성공 결과. 원본 RAW MAT 재다운로드가 아니라, **2026-11-05 원본 MAT 960개에서 검증된 원본 SHA·신호 채널 메타데이터 감사 기록을 정해진 SHA로 다시 확인**해 집계함.

- 원본 실물 베어링 **12개**, 원본 MAT 960개(4조건×20회×12), 신호 중복 4개 제외 시 유일한 원신호 956개.
- 원본 저장 `vibration_1` 채널 `Unit=unknown`: **960개**.
- 원본 저장 `phase_current_1` 채널 `Unit=unknown`: **960개**.
- 두 채널 모두 단위를 확인할 수 없는 MAT 기록: **960/960개**.
- 기존 원 MAT 감사 결과 12개 SHA256 각각이 [선행 실제 연구 실행 41965647928](https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41965647928)의 원본 연구 보고서에 고정된 SHA256과 일치. 선행 연구 보고서 SHA `f52fb71ec166d056ccad610cbbe991660c63ab98e147a7e45147f0e802a6452c`도 확인.
- 새 `scripts/audit_paderborn_960_original_mat_unit_metadata.py`와 테스트 14개로 위 원본 메타데이터 집계 재현. 더 자세한 베어링별 결과는 [워크플로 아티팩트](https://github.com/dfdfewqk/FaultMate-AI/actions/runs/42189632379)의 `paderborn-960-original-mat-raw-unit-evidence-unapproved`에 보관.

## 2016년 원저자 논문에서 **확정할 수 있는 부분**

[Lessmeier 외, *Condition Monitoring of Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals of Electric Motors*, 2016, §4.1, 종이 페이지 7](https://mb.uni-paderborn.de/fileadmin-mb/kat/PDF/Veroeffentlichungen/20160703_PHME16_CM_bearing.pdf)

- 모터 상 전류 측정: **LEM CKSR 15-NP 전류 센서**, 25kHz 저역 필터, ADC 측정 샘플율 64kHz.
- 베어링 하우징 가속도 측정: **PCB 336C04 가속도 센서**와 **Kistler 5015A 증폭기**, 30kHz 저역 필터, 동기화 샘플율 64kHz.
- 원 논문은 **측정 물리량(전류와 가속도)** 및 사용 장치/필터를 설명한다. 하지만 이 항목들은 출판된 원본 MATLAB `vibration_1.Y.Data`와 `phase_current_1.Y.Data`의 저장 숫자에 적용된 환산 계수·오프셋을 **확정하는 기술 문장이 아니다**.
- 최초 자료 공개처 [Paderborn KAt Bearing DataCenter](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter) 라이선스 **CC BY-NC 4.0**(비상업·출처표시). 상업적 운용 권리는 별도 확인이 필요.
- 현재 증거로 `vibration_rms_m_s2`/ `current_rms_a`에 임의 원신호 진폭을 넣어 SI 값으로 처리하는 건 **허용하지 않음**.

## 원저자에게 확인할 사항 (회신 전 실제 센서 SI는 미완료)

문의는 공식 기관 원저자/데이터 담당자에게 보내되, 실제 이메일은 자동 발송하지 않았다. 받는 사람 이메일은 출처에 확인한 뒤 사용.

**Subject:** Paderborn KAt Bearing DataCenter 2016 — calibration and units of stored MATLAB Y.Data channels

1. In the original bearing benchmark archive (e.g., `N09_M07_F10_K001_1.mat`), what are the **physical units of the stored numeric arrays** `vibration_1.Y.Data` and `phase_current_1.Y.Data`? Are the values already in m/s² and A, or stored as g / V / ADC counts?
2. If the stored arrays are not already SI, what **numeric scale and zero offset** must be applied to each channel? Are sensor sensitivities, the charge amplifier gain, the current transducer zero-current reference and filtering effects already included before export?
3. Are the same conversions valid for **all 32 original bearing IDs** and four measurement conditions? If there are group-specific factors, please provide the calibrated acquisition/export configuration or measuring log mapping for each group.
4. Can you cite the applicable **original acquisition settings / calibration sheet / export script** and its page or revision, or an official dated dataset-author statement?
5. Could you clarify whether additional healthy physical bearings beyond K001–K006 exist in an official publicly available version, and whether any of the 2016 reference originals have nonempty `Y.Unit` entries?

## 실제 코드와 보수적 적용 결정

- 새 `scripts/audit_paderborn_960_original_mat_unit_metadata.py`: 원본 SHA-고정 메타데이터, 채널별 `Unit` 집계. 실측 수치 원본은 덮어쓰지 않음. 유효하지 않은 SHA/수치/누락·재활용을 거부.
- 새 `tests/test_audit_paderborn_960_original_mat_unit_metadata.py` + 전용 CI: 14/14 통과, 실제 960 MAT 정보 집계 성공. 합성 테스트 데이터는 실제 SI 증거가 아님.
- 기존 `scripts/convert_mat_to_csv.py::verify_units`의 **증거문서 SHA·원 MAT SHA·검토자·공식 변환 설명·계수·오프셋** 요구 정책 유지. 회신이 오더라도 공식 문서와 원본 자료의 출처·버전 대조가 필요하며, 텍스트에 단위를 임의로 써서 우회하는 건 불가.
- 기존 Paderborn 12특징 무차원 연구용 모델, HUST 진동 전용 원본, 기존 정상·손상 물리 모델을 서로 강제 연결하지 않음.
- `source_recordings=960`, `raw_mat_unknown_pairs=960`, `si_verified=false`, `production_model_activation=false`. 연구용 ML은 유지하고 생산 모델은 미승인 상태 유지.
- **어떤 유료 DeepSeek 호출도 하지 않음**, 기존 원본 파일·학습 계수·SQLite·main 불변, ZIP/EXE 미생성.

## 결론

**단위 검증 코드는 완료, 원본 정보의 '모두 미확인'이라는 실측 상태도 재현 완료. 그러나 원저자 저장 신호 SI 수치 보정 문서가 현재 확보되지 않아 생산용 환산 및 학습 승격은 여전히 금지.** 원 저자 회신이나 원본 버전의 완전한 calibration/acquisition 기록 없이는 개발자가 수치를 창작해서 해결할 수 없다.
