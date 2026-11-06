# FaultMate AI — 원저자 BJTU 실제 데이터 폴더 구조와 독립 정상 자산 확인 (2026-11-05)

## 출처: 원저자 배포 설명서 확인

[Beijing Jiaotong University · Introduction to BJTU-RAO Bogie Datasets, 원저자 공식 안내](https://www.researchgate.net/profile/Biao-Wang-27/publication/385618713_Introduction_to_BJTU-RAO_Bogie_Datasets/data/672c86c577b63d1220e21cdc/Introduction-to-BJTU-RAO-Bogie-Datasets.pdf)

확인한 원저자 문서 섹션:
- **1쪽, Datasets overview:** 학계 연구자가 출처를 표시하면 공개 데이터를 이용할 수 있다는 취지의 사용 안내. **별도의 원본 CSV 상업적 재배포 허가나 구체적 SPDX 라이선스는 확인되지 않음.** 이 부분을 무조건적인 제품 상업 사용권으로 해석하지 않는다.
- **2~4쪽, Equipment & channels:** 1:2 축소 철도 대차 모터·기어박스·좌/우 차축 베어링, **HRB 352213** 차축 베어링(기존 Paderborn **6203**과 다름). 진동 가속도·3상 전류·회전속도·음향 등 **24개 채널**을 **64kHz**로 기록.
- **3쪽, Table 2:** 모터 속도 20·40·60Hz × 횡하중 0·+10·−10kN = **서로 다른 9개 운전조건**.
- **6~7쪽, Table 6:** 총 **51개 상태 코드** 중 정상 구동계는 **정확히 `M0_G0_LA0_RA0` 하나의 상태 레이블**. 나머지 50개는 고장/복합 고장 상태.
- **8쪽, §4.5 Folder structures:** 원본 구조 설명은 **상태별 1폴더 × 9조건(Sample_1...Sample_9) × 조건별 모터/기어박스/좌/우 차축상자 센서 CSV 4개**, 각 10초.
- **21쪽, §5 Download and contact:** 원저자 [Google Drive 공개 원본 폴더](https://drive.google.com/drive/folders/1RlZvFw-v07VvsL2Ni9cS7iFrTPDIhn2r?usp=sharing)와 [Baidu 원본 링크](https://pan.baidu.com/s/1S5F8URapHPArX2mV6FzDfA?pwd=9t74) 안내.

### **물리 독립성에 대한 핵심 결론**

| 문서상 구조 | 수량 | 독립 정상 베어링으로 취급할 수 있는가 |
|---|---:|---|
| 구동계 완전 정상 상태 레이블 | 1개 | **독립 물리 개체를 뜻하지 않음** |
| 해당 상태의 **운전조건별 측정 세션** | 9개 | **아니오** — 9조건은 9개 베어링이 아님 |
| 정상 상태의 **센서별 CSV** | 9×4 = 36개 | **아니오** — 장비 부위별 센서 CSV임 |
| 문서 설명의 전체 상태×조건×센서별 CSV | 51×9×4 = 1,836개(설계상) | **측정 원본 실제 수, 파일 무결성을 뜻하지 않음** |
| **서로 다른 물리적 정상 베어링 ID** | 미확인 | **독립성 검증 불가** |

이 숫자는 **원저자 문서상 기대되는 폴더 구조**만 계산한 것이고, Google Drive 폴더 실제 파일 개수/원본 해시/물리 ID를 검증했다는 뜻이 아니다. 공개 저장소에서 PHM24와 BJTU-RAO 기록이 겹친다는 분석도 있어 같은 측정 신호가 다른 벤치마크에서 반복 출현할 위험이 있다. [외부 재현 매핑 참고](https://github.com/jonathanadamrico/BJTU_PHM_Beijing_Benchmark).

## 공개 원본 Google Drive에 실제 접속하여 확인한 사항

GitHub Actions [실제 공개 폴더 목록·원저자 ReadMe 확인 실행](https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41984280266)에서 **gdown의 파일 목록 조회(`--json`)**를 수행했고, 로그인·개인 API 키 없이 다음 **20개 공개 메타데이터 항목**의 경로를 조회했다. 이것은 파일 목록 **메타데이터 조회**이며 51개 상태 폴더가 실제로 모두 들어 있다는 완전한 원본 감사가 아니다.

특히 `Data/` 폴더에 3분할 데이터 압축파일이 각각 목록에 존재한다.

```text
Data/BJTU_RAO_Bogie_Datasets.zip
Data/BJTU_RAO_Bogie_Datasets.z01
Data/BJTU_RAO_Bogie_Datasets.z02
ReadMe-Google Drive.txt
Introduction to BJTU-RAO Bogie Datasets NEW.pdf
```

별도의 **작은 공개 `ReadMe-Google Drive.txt` 파일만 실제 다운로드하여 읽기**에 성공했다. 안내에는 모든 `Data` 폴더 분할 ZIP을 받아 압축을 풀어야 한다는 설명, 일부 다운로드 프로그램이 `-001.zip`, `-002.z01`처럼 파일명을 바꾸는 경우의 주의 사항이 포함되어 있다. 원본 README의 출처·SHA256·파일 크기·암호 관련 줄을 가린 요약은 GitHub Actions의 7일짜리 소형 아티팩트 `bjtu-public-drive-metadata-probe-no-original-data`로 보관한다.

**센서 데이터 ZIP/Z01/Z02, 원본 CSV 및 실험 신호는 다운로드·압축 해제·검증하지 않았다.** 정상 물리 베어링별 개체 ID, 다른 시험과의 데이터 중복/독립성, 상업용 이용권은 여전히 미확인이다. 따라서 독립 정상 자산 수는 **0개라고 입증한 것이 아니라, 독립 정상 자산으로 검증된 수가 0개**인 상태다.

## 추가한 자동검증

- `docs/BJTU_PRIMARY_AUTHOR_LAYOUT_20261105.json`: 출처 및 51/1/50 상태, 9운전조건, 4센서 CSV, 레이블·실험 채널·라이선스 권리 미확정 상태를 사람이 확인 가능한 구조로 기록.
- `scripts/audit_bjtu_primary_layout.py`: 원저자 설명의 불변 계약 점검. 임의 조작된 정상 개체 수·원본 검증·상업 라이선스·외부 ML 정확도를 발견하면 즉시 실패. 나중에 파일명 목록이 입수되면 **기본 CSV 폴더/이름/9조건×4센서** 형태는 검사하지만, 파일명만으로 물리 베어링 9개라는 결과는 절대 내놓지 않음.
- `tests/test_bjtu_primary_layout.py`: 원본 구조·이용조건·가짜 정상 베어링 ID·조건 중복·정상 레이블 오용·파일명 스푸핑/경로 탐색·기존 모델 자동승인 방지 테스트.
- `scripts/probe_bjtu_author_readme.py`, `tests/test_bjtu_public_readme.py`: 원저자 공개 폴더 목록의 `ReadMe-Google Drive.txt`만 임시 디렉터리로 받아 요약하고 즉시 삭제. URL 호스트·원본 파일 용량·분할 압축파일 이름을 확인하며, 센서 ZIP/CSV의 다운로드는 막고 GitHub에 원문 전체/외부 인증정보를 보존하지 않는다.
- `.github/workflows/stage7-bjtu-original-layout.yml`: Linux Python/HTTP, Windows 원래 배치 실행, Chromium P7.2/모의 AI 전체 회귀. 별도 **원저자 Google Drive의 메타데이터만 조회**하는 실험을 실행하여 폴더 접근 가능성을 기록(별도 7일 보관 아티팩트). 원본 CSV를 내려받거나 사전 요청 없이 외부 모델/유료 API를 실행하지 않는다. 폴더의 파일목록을 불러오더라도 **전체 원본/개체 ID/라이선스 검증 성공을 선언할 수 없음.**

## 실제 원본 다운로드가 확인되지 않으면

접근 실패는 ‘원본이 없다’는 뜻이 아니다. Google Drive 로그인·공유제한·한도·메타데이터 API 제한 때문에 자동 목록 조회가 불가능할 수 있다. 그런 경우 **실제 파일 구조 0개 검증, 별도 외부 정상 개체 수 미확인**으로 기록한다.

외부 데이터의 정상/고장 분류를 연구할 경우 반드시 실측 CSV 원본, 센서/조건, 동일 장비의 반복 측정/중복 여부와 **실제 다른 물리 베어링 ID**를 먼저 확보해야 한다. 기존 Paderborn **4개 조건×20회** 모델에 BJTU 9조건 측정을 임의로 대입하지 않는다.

## 현재 기능의 안전선

- 기존 Paderborn 실제 ML: 정상 6+손상 6 베어링 학습·개발, 후속 독립 손상 8개 시험 **7/8 검출, KI21 미탐**. 새 독립 정상 오경보율 미확정.
- **실험 모델 미승인·앱 ML 추론 비활성화**, 유료 DeepSeek 호출 없음.
- main 직접 수정, 기존 원본/모델/SQLite 덮어쓰기, Windows 최종 EXE·ZIP 배포 없음.
- **사용자가 지금 직접 해야 할 일은 없음.** 추가 자료/실제 사용자 PC 확인이 불가피해지는 마지막 단계에서만 안내한다.
