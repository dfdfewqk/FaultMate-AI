# FaultMate AI — Antigravity 최소 작업 지시서 (P7.1 디버깅 통합본 기준)

현재 `FaultMate-AI` P7.1 ZIP이 **유일한 통합 기준**이다. MicroLoss AI와 P0~P5 ZIP 코드를 섞지 말 것. 새로운 프론트엔드/백엔드/ML 파이프라인을 재개발하지 말 것.

## ChatGPT에서 이미 구현 및 모의 검증

- 규칙 기반 진단·근거·긴급 차단 및 P5 UI 통합
- AI 전송 자료 미리보기, 요청별 명시 동의, 서버 환경변수 `DEEPSEEK_API_KEY`, DeepSeek 공식 HTTPS 호출 코드
- AI 출력 인덱스만 검증한 뒤 로컬 출처 근거로 표시. 모델이 임의 조치를 지시해도 화면에 표시하지 않음
- CSV 특성 검증, 독립 베어링 그룹 train/validation/test 분할, 전처리·LogisticRegression·성능 평가 코드
- 검증되지 않은 모델은 서비스에 로드되지 않음. CSV 입력과 결과는 로컬 처리
- `python -m pytest -q tests` 및 브라우저 스모크 회귀 테스트

## Antigravity에 남기는 최소 작업 (요청 전 임의 확장 금지)

1. **Paderborn 실제 공개 데이터 변환**: 원본 `.mat` 구조와 진동 가속도·전류 물리 단위, 라벨 기록·실험 조건을 확인하고 `docs/P6_AI_ML_IMPLEMENTATION.md`의 동일 단위 특성 CSV로 변환. 개인·회사 실설비 데이터를 무단 사용하지 말 것. 라이선스는 CC BY-NC 4.0이며 상업적 사용 금지 조건 확인.
2. **실제 모델 시험**: `python scripts/train_ml.py ...` 실행. 서로 다른 베어링 그룹의 데이터 누출 확인, 독립 시험셋·오탐·미탐 검토, 라이선스 준수 후 모델 활성화 승인 여부를 사람에게 보고. 임의로 `status=validated`로 바꾸지 말 것.
3. **실제 API 통신 확인**: 환경변수로 키를 넣은 Windows 환경에서 시험. 사용자 동의 없음/긴급 위험에서 외부 요청 0회, 동의 있을 때만 요청, 키/429/500/timeout 실패 시 로컬 진단 유지. 키·민감 자료는 로그·GitHub·제출물에 넣지 말 것.
4. **Windows 실행 최종 확인**: `start_windows.bat` 더블클릭, 진단·AI 미연결·ML 미검증·CSV 오류·초기화·긴급 차단 확인. 결과를 사실대로 보고.

### 금지 사항

- 기존 7개 사례를 실측 ML 라벨로 사용하는 행위, 합성 데이터 성능을 실측 성능으로 발표
- 설비 제어, PLC/Modbus 연결, 인터록 우회, 자동 재가동, 원인 확정, 작업 안전 승인
- 기능을 새로 만들었다고 허위 완료 보고, API 키를 코드/화면/응답에 포함
- P2/P3/P5 계약 삭제 또는 작동하는 UI를 다른 프로젝트로 덮어쓰기

`docs/P3_AGENT_INTEGRATION_CONTRACT.md`, `docs/P4_ML_INTEGRATION_CONTRACT.md`의 안전 조건은 유지. 최종 제출 보고에는 실제 동작 증빙, 실패 내용, Windows 환경과 데이터 출처를 구분해서 기록할 것.
