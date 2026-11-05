# FaultMate AI — ④ Windows 실제 브라우저/배치 런처 자동 수용검사 (2026-11-05)

## 개발 목표와 검증 범위

기존 `start_windows.bat` → 기존 Python `scripts/start.py` → 실제 `127.0.0.1` Uvicorn → Windows에서 설치한 테스트용 Chromium 브라우저의 네트워크·DOM 조작을 **하나의 E2E 테스트**로 검증한다.

이전 Linux Chromium 회귀검사는 Playwright 브라우저 요청을 FastAPI `TestClient`로 흉내 내는 경로여서 실 HTTP 포트, 원래 Windows 배치 런처 및 브라우저 조합을 한 번에 증명하지는 않았다. 이전 Windows `windows_launcher_smoke.py`는 실제 배치와 TCP HTTP를 검증했지만 **브라우저 화면 DOM 클릭과 사용자 흐름**까지 검증하진 않았다.

새 `tests/windows_native_browser_acceptance.py`는 실제 Windows runner에서 다음 항목을 수행한다.

| 실제 수용 경로 | 검증 |
|---|---|
| 임의 작업 디렉터리에서 원래 `start_windows.bat` 실행 | Windows 상대경로·환경/포트 설정·실 Uvicorn 서비스 정상 기동 |
| 127.0.0.1 포트에서 실제 브라우저 HTML·CSS·JS 로드 | 로컬 서버 상태 표시·콘솔 JavaScript 오류 없음 |
| 실제 화면에서 컨베이어, 증상·모델/알람·사례·관찰 선택 후 버튼 클릭 | 7개 원래 사례 규칙 기반 진단, **고장 확정이 아니라 원인 후보**로 표시 |
| AI 근거 미리보기 열기 | 사용자 원문 증상·모델/알람은 전송 미리보기에서 제외 |
| AI 동의 전 버튼 비활성화 및 요청별 동의 후 클릭 | **DeepSeek 키가 없는 환경에서 실제 로컬 API가 전송 없음을 표시**하고 동의를 자동 초기화 |
| CSV 업로드·ML 실행 | 미승인 연구용 모델로 예측값을 꾸며내지 않고 기존 `unavailable` 상태 유지 |
| 위험 징후를 “예”로 변경 | AI/ML 버튼 비활성화, 이전 진단을 긴급 정지 상태로 전환 |
| 근거 자료실 열기 | 7개 사례 항목 로드 |
| 다른 웹사이트 Origin·가짜 Host로 실제 로컬 HTTP 전송 | 각각 HTTP 403 반환; 사용자 동의나 API 키에 무관하게 브라우저 경계 보호 |
| 테스트 종료 | 하위 Windows 배치·Python 서버 프로세스 트리 강제 종료 후 **127.0.0.1 포트가 더는 열려 있지 않은지 확인** |

### 환경·원본·사용자 데이터 보호

- GitHub Actions `windows-2025` **일회용 테스트 머신**의 `.venv`를 원래 `setup_windows.bat`으로 구성한 뒤, `playwright` 및 테스트용 Chromium만 **그 실행기 내부**에 설치한다. 기존 프로젝트 개발/사용자 설치 파일은 수정하지 않는다.
- 자식 프로세스에서 `DEEPSEEK_API_KEY` 및 유료 승인 환경변수를 **제거**하고 로컬 바인딩·브라우저 자동 실행 비활성화 후 검사한다. 실제 `/api/agent/review` 클릭은 앱의 로컬 Python 함수까지 실행될 수 있지만, **외부 DeepSeek로 전송되지 않는 `unavailable` 결과**만 검사한다.
- 사용자 입력 예제는 **합성 값**만 사용한다. 3개 센서 특성 CSV도 가짜 예제 바이트이며 원본 Paderborn RAR/MAT·BJTU ZIP 파일을 열지 않는다.
- 실행 로그는 임시 폴더에만 저장하고 종료 시 삭제. 백그라운드 서버가 남지 않도록 프로세스 종료와 포트 닫힘을 검사한다.
- GitHub Actions 검사는 **사용자 자신의 Windows PC에서 브라우저·방화벽·설치 경로·포트 충돌**에 대해 수용검사를 완료했다는 뜻이 아니다. 실제 개인 컴퓨터에서의 최종 조작은 별도로 필요하다.

## 자동화

`.github/workflows/stage7-windows-native-browser-acceptance.yml`:

1. Linux **전체 Python/로컬 HTTP/ML NO-GO/DeepSeek 오프라인** 검사.
2. Windows 기존 `setup_windows.bat`/Python 전체 테스트/기존 실행 연동 검사.
3. Windows 네이티브 Chromium 설치 후 **위 새 실제 TCP·UI E2E 검사**.
4. Linux Chromium 전체 P7.2·동의·외부 AI 모의 오류·미승인 ML 회귀검사.

GitHub Actions: https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/stage7-windows-native-browser-acceptance.yml

### 아직 승인되지 않은 것

- 실제 베어링 손상 모델은 **독립 신규 정상 베어링/오경보율, SI 단위, 4조건×20회 수집 vs 앱 3특징 CSV 계약**이 미해결. 8개 신규 손상 중 7개 검출·KI21 미탐.
- 실제 유료 DeepSeek 서버 1회 연결 검사는 **별도 본인 계정 결제·API 키·명시 승인**이 필요한 선택 작업. 새 E2E에서 수행하지 않는다.
- GitHub Windows runner 통과는 **실제 사용자 PC 최종 확인과 다름**.
- 원래 합의대로 제품 최종 EXE/ZIP은 수용검사 및 승인 전 제작하지 않는다.

`main` 직접 수정, 기존 원본·사용자 SQLite/기록, 연구 ML 모델 원본 계수, 과거 PR 병합/삭제를 일절 하지 않는다. **현재 사용자 직접 할 일 없음.**
