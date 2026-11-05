# FaultMate AI — 실제 센서 신호 → 기존 동결 ML 모델 실험용 추론 연결 (2026-11-05)

## 이번 작업 목적

FaultMate AI의 기존 ML 경로 `POST /api/ml/inspect`는 **검증된 3개 SI 측정값 CSV 모델이 없어서 예측을 거절**하도록 되어 있다. 반면 실제 Paderborn 원본 MATLAB 신호에서는 이미 12개 무차원 특징이 추출·학습되었고 고정 모델의 연구용 추가 평가(손상 8개 중 7개 검출)도 시행되었다.

이번에는 기존 기능을 중복 개발하지 않고, **원본 RAR → 진동+전류 80개 MAT → 정확히 동일한 12개 특징 → 기존 연구용 계수와 고정 문턱값 → 실험용 추론 결과**를 한 번의 오프라인 명령으로 연결했다.

## 실제 입력 및 출력

```shell
python scripts/run_experimental_paderborn_ml.py \
  --archive /path/to/K001.rar \
  --bearing-id K001 \
  --out /path/to/NEW_k001_experimental_result.json
```

- **실제 7-Zip 실행도구**와 `requirements-ml.txt`에 선언된 scipy/numpy가 필요한 개발/연구 명령이다. Windows에서 본인 PC에 지금 별도 설치하라고 요구하지 않으며 GitHub Actions Windows runner에서 검증한다.
- `K001.rar`는 Paderborn 대학 원본 출처가 등록한 MD5와 일치해야 하고, 크기/압축 무결성 및 **공식 4조건×20회 = 80개 MAT** 이름이 모두 맞아야 한다.
- 기존 `scripts/extract_paderborn_unitless.py`의 `vibration_1`과 `phase_current_1` 쌍으로 각 3개 창의 통계/스펙트럼으로부터 12개 **무차원** 특징을 구하고, 이미 확인된 신호 중복은 제외한다.
- 80개 기록의 조건/회차·SHA256·신호 지문·중복 처리·특징 벡터 크기·유한값 여부를 다시 확인한 뒤, **중앙값으로 베어링 1개당 12개 특징**을 집계한다.
- `scripts/evaluate_unseen_paderborn_damaged.py`의 **SHA-256 고정 연구 모델과 동일한 정규화·로지스틱 점수**를 적용한다. 모델 SHA `84a7c059fa769d1b0e2bd0075ecba92bcd06ae24acf961e0ea2120d9d44a0ab0`; 원본 계수 및 threshold **0.5**를 변경하지 않는다.
- 결과 JSON에는 `experimental_predicted_label`, `experimental_damage_model_score`, 실제 이번 실행에서 원본 RAR 및 80개 MAT를 확인했다는 근거와 중복 제외 수만 포함한다. **원본 센서 파형, 사용자의 경로, 모든 개별 신호 특징, API 키**는 포함하지 않는다.
- 기존 결과 경로는 절대 덮어쓰지 않으며 원본 RAR/MAT 파일은 읽기 전용이고 임시 추출 MAT는 자동 폐기한다.

### K001의 해석 범위

**K001은 이미 학습에 사용한 베어링**이다. 따라서 이번 실제 ML 흐름 테스트는 **제품 입력·계수·점수 계산이 실제 원본 데이터에서 작동한다는 증명**이며 새로운 독립 성능 평가가 아니다. K001 예측이 정확하더라도 그 결과를 신규 정상 베어링 특이도·오경보율·현장 정확도로 보고할 수 없다.

기존의 별도 독립 손상 8개 평가 **7/8(미탐 KI21)**도 유지한다. 정식 배포 모델은 아직 승인되지 않았고 기존 `/api/ml/inspect`는 **unavailable** 상태를 유지한다.

## 검증 방법

`tests/test_experimental_paderborn_real_inference.py`는 **합성 특징만 사용하는 소프트웨어 음성 테스트**(4×20 측정 누락, 고장 라벨·출처 MD5 변조, 신호 지문·SHA 검증, 중복·12개 특징 입력, 모델 계수 고정, 안전성/출력 파일 덮어쓰기 금지)를 포함한다. **합성 수치 예측을 실제 시험 성능으로 보고하지 않는다.**

`.github/workflows/stage7-experimental-ml-real-signal.yml`은 기존 Linux/Windows 전체 Python·Windows 배치·실브라우저/Chromium 회귀에 더해 **Paderborn 원본 K001 RAR 하나만 공식 Zenodo에서 GitHub 일회용 Windows runner 임시 폴더로 다운로드**한 후 실제 MD5·RAR 무결성·80 MAT·차원 없는 특징 및 이미 학습된 고정 모델 점수를 검사한다.

[전체 GitHub 자동검사](https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/stage7-experimental-ml-real-signal.yml)

## 아직 남은 기능

1. **완료 범위:** 실제 원본 센서 입력/80 MAT 특징 추출과 기존 연구 모델 실험 추론을 일괄 연결 (오프라인 CLI).
2. **다음 개발:** 실험용 결과를 FaultMate AI 화면과 안전하게 연동하고, 사용자가 실수로 이를 **정식 ML 고장 확정**으로 받아들이지 않도록 분리된 UI/상태를 표시한다.
3. **연결 이후 검사:** 앱에서 실험용 결과를 표시하는 Windows 실브라우저·실원본 결과 연동 E2E 확인.
4. **외부 검증:** 별도 신규 **독립 정상 물리 베어링 원본**, 4조건×20회+2채널 입력 계약, 데이터 이용조건이 확보되기 전까지 정식 베어링 ML은 사용 불가.

**상태:** 규칙 기반 FaultMate 프로그램/DeepSeek 동의 경계/기존 3개 SI CSV ML 경로/연구 모델 원본/사용자 SQLite/기타 원본 파일 및 `main`을 변경하지 않는다. 실제 유료 API 호출·최종 EXE/ZIP 배포 없음. 사용자가 지금 직접 해야 할 일 없음.
