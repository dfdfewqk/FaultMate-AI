# FaultMate AI — BJTU 분할 압축 원본 데이터 자원/무결성 사전검사 (2026-11-05)

## 이유와 지금까지 검증된 근거

BJTU-RAO 원저자 공개 폴더에는 `Data/BJTU_RAO_Bogie_Datasets.z01`, `.z02`, `.zip`의 **3개 압축 조각**이 있으며, 작은 `ReadMe-Google Drive.txt`는 GitHub 임시 실행 환경에서 **실제로 다운로드·읽기·삭제** 완료했다. 전체 대용량 압축 데이터 본체 및 원본 센서 CSV는 **실제로 다운로드한 적이 없으며**, 현재 실험용 모델에도 입력하지 않았다.

[원저자 안내 문서](https://www.researchgate.net/profile/Biao-Wang-27/publication/385618713_Introduction_to_BJTU-RAO_Bogie_Datasets/data/672c86c577b63d1220e21cdc/Introduction-to-BJTU-RAO-Bogie-Datasets.pdf)는 정상 상태 레이블 1종(`M0_G0_LA0_RA0`) × 운전조건 9개 × 센서 그룹 CSV 4개 = **정상 상태의 문서상 CSV 36개**라는 구조를 설명한다. 이 수치는 **정상 물리 베어링 36개나 9개라는 의미가 절대 아니다**. 실제 독립 정상 베어링의 ID/수는 확인되지 않았다.

[원본 데이터 정리 프로젝트 BearingDatasets](https://github.com/VictorBauler/BearingDatasets)는 전체 다운로드를 **약 30.4GB**로 안내하지만, 이 값은 **원저자 파일별 공식 바이트 크기나 체크섬이 아닌 제3자 추정/보고 값**이다. GitHub Actions에서 확인한 당시 임시 디스크 여유 공간은 약 92GB였으며 디스크 여유 공간만으로 데이터 수집의 적합성이 증명되지는 않는다. 자동 다운로드 안전 예산은 **6GB**로 설정하고, 예산을 넘는 대용량 원본은 별도 근거 없이 일괄 전송하지 않는다.

## 이번 코드와 검사

### 1. 공개 링크의 실제 헤더만 검사

`scripts/preflight_bjtu_split_archive_size.py`

- **정확히 3개** 공개 원저자 파일만 Google Drive `gdown --json` 디렉터리 목록에서 찾는다.
- 잘못된 호스트, 가짜 다운로드 URL, 이름 중복은 거절한다.
- 먼저 HTTPS `HEAD` 요청을 보낸다. 응답 헤더에서 크기를 확정할 수 없으면 **`Range: bytes=0-0` GET**을 최대 한 번 시도한다. **응답 본문은 읽지 않고 즉시 닫으며**, 어떤 파일도 저장하지 않는다.
- Google Drive가 303을 보낼 경우 처음에는 크기를 확인하지 못했다. 이후 **Google 소유 HTTPS 다운로드 도메인만 최대 두 번** 따라가도록 보완했다. 외부 임의 도메인 리다이렉트는 거절하고, 인증 쿠키·사용자 키를 전송하지 않는다.
- 파일 크기는 전체 다운로드의 `Content-Length`나 Google Drive의 HTML 미리보기 페이지 길이로 추측하지 않는다. **실제 206 + 정확한 `Content-Range: bytes 0-0/전체크기`**가 입증될 때만 공식 서버 응답의 파일 크기로 보존한다. 이 조건이 아니면 `null` (미확인).
- 파일 목록만 있어도 원본 ZIP의 압축 완결성, 개별 측정 파일 SHA256, 실제 정상 개체 수나 외부 검증 자격을 인정하지 않는다.
- 인터넷 연결/리다이렉트 상황과 관계없이 `safe_to_auto_download_or_extract_large_archive=false` 유지.

### 2. 이미 존재하는 원본의 압축 **파일 목록만** 검사하는 별도 절차

`scripts/audit_bjtu_local_split_zip_intake.py`

- **이미 별도 경로에 원저자 분할 압축파일 3개가 모두 존재할 때에만** 마지막 `.zip` 파일로 `7z l -slt -ba` 실행. 이는 디렉터리/파일명 **목록 조회**이지 압축 해제(`7z x`/`e`)나 신호 내용 검증이 아니다.
- 조각이 하나라도 빠졌거나 심볼릭 링크, 빈 파일, 취약한 경로/중복 파일명, 목록 실패가 발견되면 즉시 차단한다.
- 7z 출력 길이, 명령 실행 시간, 메타데이터 경로의 크기·수와 악의적인 `../` 경로를 제한한다.
- 파일 목록이 나오더라도 정상 `M0_G0_LA0_RA0`에 해당하는 CSV의 **파일명 개수만** 계산하고, 실제 독립 정상 물리 베어링 ID·원본 신호 해시·현장 모델 성능은 인정하지 않는다.
- 실제 압축 조각이 현재 저장소/실행 환경에 없으면 **검증되지 않은 정상 상태**로 보고하며, 새 다운로드나 사용자 파일 변경을 하지 않는다.

### 3. 회귀검사

- `tests/test_bjtu_split_archive_feasibility.py`: 206 이외 응답/Google HTML/301~303 리다이렉트/악성 호스트/원본 다운로드 방지/알 수 없는 크기를 0으로 오판 금지/세 조각 완전성/저장 용량 예산.
- `tests/test_bjtu_split_zip_intake.py`: 결손 압축 조각, 목록 파일 중복·경로 탐색, 7z 실행 명령의 읽기 전용성, 정상 CSV 파일명 36개를 독립 물리 베어링 36개로 허위 표기하지 않는지 확인.
- `.github/workflows/stage7-bjtu-split-archive-feasibility.yml`: Linux·Windows·Chromium 기존 앱 전체 회귀 + **실제 공개 원저자 Drive 3개 파일 헤더 요청**. 신호 ZIP/CSV 다운로드나 유료 DeepSeek 실호출 없음.

[최종 Github Actions](https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/stage7-bjtu-split-archive-feasibility.yml).

## 확인됐지만 아직 해결되지 않은 제약

원저자 공개 파일 3개와 README는 확인됐으나, 원본 대용량 측정 데이터의 개별 체크섬·압축 내부 CSV 1,836개 실존·실제 정상 베어링 개체 ID·데이터 상업적 사용 허가는 아직 검증할 수 없다. **유효한 새로운 정상 베어링 자산 0개가 입증된 것이 아니라, 신규 정상 베어링으로 인정할 수 있을 만큼 검증된 개체가 0개**이다.

기존 Paderborn 냉동 연구 모델의 새로운 손상 베어링 8개 시험에서는 7개 손상을 검출하고 **KI21을 놓쳤으며**, 새 독립 정상 베어링은 없으므로 오경보율·전체 정확도는 확인하지 못했다. 원본 모델은 **미승인/프로그램 추론 비활성화**, 유료 API/최종 EXE·ZIP/사용자 자신의 PC 실기동 미완료.

**다음 개발 방향:** 대형 원본을 전부 받는 데 집착하기보다 원저자 자료에 실제 서로 다른 건강 베어링 식별 근거가 존재하는지 확인하고, 사용할 수 있는 경우에만 수집·무결성 검사·별도 도메인 평가를 사전 정의한다. 이미 사용한 정상 기록을 새 외부 시험 데이터로 재사용하지 않는다. 사용자에게 현 단계에서 직접 할 일은 없다.

`main`과 기존 실측 MAT/RAR·SQLite·기존 모델·Draft PR은 보존한다.
