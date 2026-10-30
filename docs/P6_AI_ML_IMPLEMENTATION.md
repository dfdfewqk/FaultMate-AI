# FaultMate AI — P6 로컬 AI·ML 연결 구현 (검증 경계)

## AI 연결

- `POST /api/agent/review`: 기존 `triage` 본문 + 명시적 `consent: true` 필요. 동의가 없거나 긴급 위험, 사례 미선택이면 **모델 호출하지 않음**.
- 서버 환경변수 `DEEPSEEK_API_KEY`가 설정된 경우에만 고정된 공식 HTTPS API 엔드포인트 `https://api.deepseek.com/chat/completions` 사용. 키를 URL·프론트엔드·응답·로그에 넣지 않음.
- 전송 데이터는 `evidence-preview`에서 허용된 7개 사례의 근거·관찰 enum 데이터로 제한. 설비 모델명·증상 원문·알람 원문·개인정보·원시 CSV는 외부 전송하지 않음.
- 모델의 임의 지시·자연어·출처 위조를 표시하지 않음. 모델은 기존 후보의 **순서 인덱스**와 기존 질문의 **인덱스**만 반환. 서버에서 범위를 확인하고 로컬 근거 문구로 재구성. 로컬 P2 결과와 긴급 중지 규칙이 우선.
- 외부 AI 라이브 호출은 키가 없으므로 **이 배포본에서 미검증**. 네트워크 모의 테스트만 수행됨.

## ML 구성

- 범위: 실험실 구름베어링의 상태 `healthy`/`damaged` 분류. 컨베이어나 센서의 모든 고장 원인으로 일반화 금지.
- 공개 우선 데이터: [Paderborn Bearing DataCenter](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter) — 진동과 모터 전류 측정, 베어링 단위 독립 시험. **CC BY-NC 4.0**: 비상업적 연구·교육 사용 조건, 상업적 사용은 저자 문의 필요. 출처와 이용조건 기록.
- 원본 `.mat`은 학습용 CSV가 아니며 추출기가 필요함. 신호에서 물리 단위를 확인해 계산한 윈도우 특성을 아래 CSV로 변환한 후 학습. **무단 가상 라벨을 정답으로 넣으면 안 됨**.

### CSV (윈도우 특성)

필수 컬럼:

`asset_id,trial_id,source_id,vibration_rms_m_s2,vibration_peak_m_s2,current_rms_a`

학습 전용 필수 컬럼:

`label,label_provenance,license`

- `asset_id`: 같은 베어링 물리 개체는 모든 시험에서 같은 ID.
- `trial_id`: 같은 베어링 내 시험 ID. `(asset_id, trial_id)` 중복 금지.
- `source_id`: 원본 데이터 식별자.
- `label`: `healthy` 또는 `damaged`만 허용. 정답 출처 `label_provenance`와 라이선스 명시.
- `vibration_rms_m_s2`, `vibration_peak_m_s2`: 진동 가속도 RMS 및 peak [m/s²].
- `current_rms_a`: 모터 전류 RMS [A].
- 미확인 단위·서로 다른 설비·센서 결측치를 0으로 채워 합치지 말 것.

학습 예시(실제 라벨링 완료 데이터 보유 시):

```bash
pip install -r requirements-ml.txt
python scripts/train_ml.py real_bearing_features.csv --output models/evaluation
```

- 전체 학습 CSV 해시 기록. 서로 다른 베어링 ID별로 학습/검증/시험 분리.
- 학습세트만으로 표준화, 더미 분류기와 비교, 검증 세트에서 성능 비교 후 미사용 시험 세트 성능 산출.
- 학습 결과는 `models/evaluation/bearing_evaluated.json`에 **evaluated_pending_review**로 저장되어 서비스에 자동 배포되지 않음.
- 반드시 자료·출처·실험 단위·오류 분석을 사람이 검토하고 성능 적합성이 확인되었을 때만 `models/bearing_validated.json` 검증 판정 가능. 배포 모델 없이 `/api/ml/inspect`는 `unavailable` 및 예측 미실행.
- 검증 모델이 있어도 CSV 기능은 훈련 특징과 동일한 물리 단위만 허용하고 점수는 현장 고장 확률로 해석하지 않음.

## 남은 실제 작업

1. Paderborn 실제 `.mat` 다운로드 → 원 신호의 구조·측정 단위·라벨 메타데이터 확인 → 위 CSV로 변환.
2. 실제 학습 수행 → 시험 결과와 데이터 라이선스 검토 → 승인된 모델만 활성화.
3. 필요 시 `DEEPSEEK_API_KEY` 연결 후 명시 동의 시나리오를 Windows 실환경에서 실제 검증.
4. Windows `start_windows.bat` 실제 점검. 현장 안전·정비 책임자 검토.

자동화가 완료된 부분을 실제 AI 연결·ML 학습 완료로 표시하지 마세요.
