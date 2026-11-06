# FaultMate AI — 연구용 모델 보존 영역

여기의 JSON은 **실제 Paderborn 원본에서 얻은 교육·연구용 실험 모델**입니다. 정상·손상 상태를 진단하는 검증·승인된 제품 모델이 **아닙니다.**

- `PADERBORN_REAL_UNITLESS_MODEL_UNAPPROVED_20261105.json`: 2026-11-05 실제 12베어링/956개 고유 기록을 검증한 뒤, 개발 10개 베어링으로 학습한 실험용 표준화 통계와 로지스틱 회귀 계수.
- 실제 독립 개발 교차검증 **Macro-F1 0.5833 / 정확도 60%**; 단 2개 홀드아웃 실험은 맞혔지만 일반화 근거가 아님.
- 원본 SI 단위/물리 보정이 미확정이고 현장 외부검증도 없음. `faultmate/integration/ml.py`의 정식 모델 로더에 사용하거나 `bearing_validated.json`으로 이름만 바꾸는 것을 금지합니다.
- 원본 재현 증거 및 설명: `../REAL_PADERBORN_ML_EVALUATION_RESULTS_20261105.md`.
- 실제 학습 CI: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41965647928
- 원본 이용조건 CC BY-NC 4.0: 상업적 사용 금지(별도 허가 필요).

기본 FaultMate 앱은 여기에 저장한 모델을 자동으로 읽거나 고장 확정에 이용하지 않습니다.
