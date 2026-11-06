# HUST v3 원본 확보 — 공식 접근 결과 및 로컬 검증 (2026-11-06)

## 검증한 사실
- 공식 출처: https://data.mendeley.com/datasets/cbv7jyx4p9/3 (Version 3; DOI 10.17632/cbv7jyx4p9.3). 공개 라이선스 CC BY 4.0.
- 원저자 논문: https://pmc.ncbi.nlm.nih.gov/articles/PMC10327369/ (51.2kHz 진동 전용, 3부하, 정상 베어링 3개/손상 베어링 27개를 논문에서 보고). 기존 Paderborn 6203, 64kHz, 진동+전류, 4조건 입력 계약과 별개.
- 실제 GitHub CI 공식 API 접근 결과: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/42181978902 및 https://github.com/dfdfewqk/FaultMate-AI/actions/runs/42182191259 — **HTTP 401 인증 요구**. 웹페이지 공개 표시만으로 REST 파일 목록과 원본 바이트가 확보된 것이 아님.
- 로컬 검사 대체 경로: scripts/inventory_hust_original_local_files.py. 원본 MAT/RAR/ZIP/7z 파일의 **실제 SHA256/파일 길이/상대경로/중복**만 기록, 라벨과 물리 개체 ID는 추정하지 않음.
- 자동검사: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/42182763957 — 합성 파일 기반 32개 테스트 통과. 실측 원본 확보·라벨 검증을 의미하지 않음.

## 공식 원본을 사용자가 다운로드할 수 있을 때
1. https://data.mendeley.com/datasets/cbv7jyx4p9/3 의 Version 3을 확인하고 공개 페이지의 Download All로 원본 HUST bearing dataset을 받는다. 필요하면 로그인한다. API 토큰이나 비밀번호를 채팅에 공유하지 않는다.
2. 받은 원본 압축파일을 변조하지 않고 따로 보존한다. 풀었다면 별도의 폴더에서 원본 MAT 파일명과 경로를 유지한다.
3. 해당 원본 폴더를 대상으로 아래 명령 실행. 출력 파일은 기존 보고서와 이름이 겹치지 않도록 한다.

    python scripts/inventory_hust_original_local_files.py --original-root "D:\hust-original-v3" --out "D:\hust-sha-inventory-new.json"

4. 생성된 JSON은 **로컬 파일 바이트 확인**이지 **저자의 원본 공개 파일 신원 증명**이 아니다. 공인 저장소의 파일 UUID/공개 해시와 저자 문서의 물리 베어링 ID·정상/손상 라벨을 대조하기 전에는 훈련·검증 데이터로 인정할 수 없다.
5. 새로운 독립 정상·손상 물리 베어링과 정답 라벨을 검증한 뒤에도, HUST 진동 전용 데이터는 기존 Paderborn 진동+전류 모델에 연결하지 않는다. 새 도메인에서 새 모델/사전 고정된 베어링별 검증이 필요하다.

## 정확한 남은 상태
- HUST 원본 실제 다운로드·원저자 해시/라벨 대조 **미완료 (0개)**.
- Paderborn Y.Data 원래 저장값의 SI 보정 계수·영점 오프셋 공식 확인 **미완료**. 이것은 첫 번째 원본 확보 문제 다음에 처리할 별도 문제.
- 생산 ML 미활성화/기존 연구용 RAR 경로 보존. 학습 계수, SQLite, main, 로컬 파일, ZIP/EXE 미변경. 유료 DeepSeek 호출 없음.

**현재 단계 판정:** 새 원본 파일 검증을 위한 코드 완료, 실제 공식 HUST 원본 입수는 외부 인증 조건 때문에 미완료. 401을 모델 정확도나 소스 검증 성공으로 보고하지 않음.
