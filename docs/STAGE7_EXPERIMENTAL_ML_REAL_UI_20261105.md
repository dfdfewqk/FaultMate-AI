# FaultMate AI — 실험용 12특징 베어링 ML 실제 프로그램 UI 연결 (2026-11-05)

## 이번 변경으로 실제 연결된 경로

원본 Paderborn 데이터 `K001.rar` → 원본 MD5 검사 및 80개 MATLAB(.mat) 실측 진동·모터전류 데이터 추출 → 각 12개 무차원 특징 → 실제 고정 모델 로지스틱 점수.

이제 같은 실행에서 **추출한 특징 보고서를 별도 JSON으로 저장**한 후, FaultMate의 기존 P7.2 "고급 분석" 화면에서 **새로운 'Paderborn 베어링 실험용 ML · 미승인' 입력칸**으로 업로드하여 **동일한 고정 모델 점수를 로컬에서 다시 계산**할 수 있다.

`main`과 기존 원본/학습 모델 계수는 변경하지 않으며 기존 `CSV 검증·ML 실행` 버튼은 정식 검증 모델이 없으므로 **예측 없이 계속 중단**한다.

### 파일 생성 예시 (자동검사는 GitHub Windows runner에서 수행)

```powershell
python scripts/run_experimental_paderborn_ml.py `
  --archive "D:\\datasets\\K001.rar" `
  --bearing-id K001 `
  --features-out "D:\\reports\\K001_original_80_unitless_features.json" `
  --out "D:\\reports\\K001_experimental_ml_score.json"
```

**위 명령은 나중에 해당 원본 파일이 이미 저장된 실행 환경에서만 사용**하면 된다. 현재 사용자에게 원본 RAR 다운로드/7-Zip/개별 설치를 부탁하는 단계가 아니다.

브라우저 UI에서는 `--features-out`으로 생성된 **80개 특징 JSON**만 선택한다. 원본 100MB 이상 RAR를 브라우저에 업로드하지 않으며 JSON도 **외부 DeepSeek 서버로 전송하지 않는다**. 신규 경로 `POST /api/ml/experimental-unitless-report`는 로컬 서버에서 연구용 점수만 계산한다. 업로드 JSON은 언제든 조작될 수 있어 **원본 archive MD5가 실제로 확인되었다는 사실을 JSON만으로 재확인했다고 표시하지 않는다**. 원본 검증은 RAR을 실제로 읽었던 앞선 CLI 실행에서만 참으로 인정한다.

### UI에서 확인할 수 있는 것

- 80회 기록의 Paderborn 4가지 조건, 진동/전류 12개 특징과 중복 여부가 형식적으로 맞으면 기존 SHA256 동결 모델로 실제 **로지스틱 점수**를 계산한다.
- 점수에 따라 "정상 쪽" / "손상 쪽"의 **실험용 분류**와 0~1 범위의 **모델 점수**를 표시한다. 이는 특정 현장 설비의 실질 고장 확률, 안전 작업 승인, 수리 계획 지시가 아니다.
- SHA256 모델 해시·원본 연구 모델의 미승인 상태·실제 신규 독립 정상 베어링 특이도 미측정을 계속 유지한다.
- `/api/ml/inspect` 정식 입력은 기존 3개 SI 특징 CSV만 받고, 새로운 연구용 JSON을 적용하지 않는다.
- 파일 변경 또는 긴급 위험 선택 시 연구용 요청을 취소하고 이전 화면 결과를 삭제한다. 다른 외부 웹사이트가 JSON POST를 보내려고 하면 기존 Origin/Host 검증에서 HTTP 403.

### 의존성

기존 Windows `setup_windows.bat`이 사용하는 `requirements.txt`에 `numpy`와 `scipy`를 명시적으로 추가했다. 기존 CLI의 MATLAB reader/특징 추출과 로컬 연구 추론에 실제 필요한 의존성이며, 자동 설치 실행이나 EXE/ZIP 배포를 이 개발 단계에서 수행하지 않는다. 테스트는 GitHub의 일회용 Windows·Linux runner에만 설치한다.

## 검증

- `tests/test_experimental_ml_api.py`: 실제 앱 API의 모델 계산과 CLI 연구용 점수 일치, 입력 80회 제약, 오염/조작 입력 차단, 용량·형식 제한, 외부 Origin 접근 차단, 기존 3개 특징 CSV 경로 불변.
- `tests/windows_native_browser_acceptance.py`: Windows의 **실제 배치파일→로컬 Uvicorn→Chromium 브라우저**에서 합성 80회 특징 업로드·모델 점수 표시·경고문·긴급 위험 시 결과 삭제까지 점검. 이 합성 데이터는 실제 독립 성능 검증으로 절대 취급하지 않는다.
- `scripts/check_real_ml_app_research.py`와 `.github/workflows/stage7-experimental-ml-ui-integration.yml`: **실제 원본 K001 RAR/80개 MAT를 읽고 특징 JSON 생성→CLI 고정 모델 예측→로컬 FastAPI 연구용 엔드포인트 재입력→점수·레이블 완전 일치** 확인. 기존 제품 모델은 계속 비활성화. Windows/Linux 전체 회귀, 기존 Chromium UI와 Windows 네이티브 Chromium E2E 포함.

[실행 기록](https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/stage7-experimental-ml-ui-integration.yml)

**K001은 기존 학습용 정상 베어링**이기 때문에 성공해도 신규 정상 정확도나 외부 환경 성능을 뜻하지 않는다. 앞서 별도 측정한 추가 손상 베어링 8개 중 7개를 검출했고 KI21을 놓친 결과를 그대로 유지한다. 새로운 독립 정상 베어링·실측 SI 단위·도메인 호환성 검증 및 원본 CC BY-NC 비상업 조건은 아직 미해결이므로 **현장용 ML 승인 및 배포는 불가**이다.

현재 사용자 직접 조작 요청 없음, 실제 DeepSeek 유료 호출 0회, `main`·원본 파일·SQLite·학습 모델 계수 변경 없음, 최종 EXE/ZIP 제작 안 함.
