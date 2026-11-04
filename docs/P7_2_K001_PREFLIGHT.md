# K001 실측 데이터 사전검사 — Antigravity 1회 실행

기준 브랜치: `work/faultmate-ml-converter-fix-20261030`

## 범위

`K001.rar`를 7-Zip으로 전체 무결성 검사하고 파일목록에서 **K001 기록 1개만** 임시로 추출하여 실제 MATLAB 채널명·배열 형태·원본 Unit 값을 JSON으로 보고한다. **단위를 확정하거나 학습 CSV를 만드는 단계가 아니다.** 임시 추출 파일은 자동 정리된다. 압축 원본·기존 `.venv`·P7.2 앱 변경 없음.

## Windows PowerShell — 저장소 루트에서 실행

```powershell
# 기존 .venv-ml 환경에 scipy/numpy가 설치되어 있어야 한다.
& ".\.venv-ml\Scripts\python.exe" ".\scripts\inspect_paderborn_archive.py" --archive "C:\Users\User\Downloads\FaultMate-AI-main\K001.rar"
```

다른 위치에서 받은 파일이라면 `--archive`만 실제 전체 경로로 바꾼다. 7-Zip은 PATH 또는 `C:\Program Files\7-Zip\7z.exe`에서 자동 발견한다. 다른 위치에 설치했다면 `--sevenzip "전체 경로\7z.exe"`를 추가한다. **기존 Antigravity 로컬 파일을 덮어쓰지 말고** 검증된 GitHub 브랜치를 별도 작업 폴더에 받아 실행한다.

## 결과 해석

- `archive_integrity: 7zip_test_passed`: 전체 아카이브 검사 통과. 파일 크기만 확인한 것이 아니다.
- `recording_count_mat`: 아카이브 내 `.mat` 기록 수.
- `inspected_recording`: 실제 검사한 파일 이름. **K001.mat이라는 파일명을 가정하지 않는다.**
- `channels`: 실제 `Name`, 배열 shape, **원본 파일에 있는 Unit 그대로** 표시.
- `physical_units_verified: false`: 단위 근거 확인은 별도 작업. `Unit: unknown`이면 값이 물리 SI 단위라고 주장하지 않는다.
- `csv_generated: false`, `model_trained: false`: 어떤 경우에도 이 도구는 학습 자료를 생성하거나 모델을 실행하지 않는다.

## 다음 판단

- 신호가 누락되거나 파일을 읽지 못하면 원본 MATLAB 구조 및 추출 로그를 보고하고 여기서 중단한다.
- `Unit`이 비었거나 불확실하면 공식 문서·센서 보정 계수를 확인하고 별도의 검토 자료를 남긴다. 단순한 문자열 `unit_evidence`만으로 SI 단위가 실제로 검증되는 것은 아니다.
- 공식 기록 단위와 라벨 출처가 검증된 다음에만 변환기 `scripts/convert_mat_to_csv.py` 및 기존 `scripts/train_ml.py`를 사용한다.
- Paderborn 자료는 CC BY-NC 4.0 (비상업적 연구/교육 사용 시 출처 표시 필요). 원본 RAR·MAT·실측 CSV는 GitHub에 올리지 않는다.

참고: [Paderborn University Bearing DataCenter](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter) 및 [Data Sets and Download](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download).
