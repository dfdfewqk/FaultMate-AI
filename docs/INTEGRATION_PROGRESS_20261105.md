# FaultMate AI — 2026-11-05 통합 개발·근거 검증 상태

## 범위

**개발 브랜치**: `work/faultmate-final-integration-20261105`, 기준 `work/faultmate-ml-converter-fix-20261030`. 기존 PR #3 (Windows), #4 (AI), #5 (ML 원시 자료 감사)를 합쳐 Draft PR #6으로 별도 리뷰한다. **main 직접 수정, 자동 병합, ZIP/EXE 제작, 다운로드본 배포는 하지 않았다.**

## 구현 및 회귀 검증

- 기존 P7.2: 컨베이어·모터·센서 사례 검토, 근거 자료실, 안전 차단, 요약 복사 기능 유지.
- Windows: 기존 `setup_windows.bat` Python 선택 안정화, 실제 `start_windows.bat` → localhost HTTP 스모크, OS 공통 임시 경로 테스트.
- 선택적 DeepSeek: 동의 없는 호출 금지, 무단 원문 전송 방지, Bearer 토큰이 외부 redirect에 전달되지 않도록 차단, 송수신 크기 제한, JSON/인덱스 유효성 검증. **실제 유료 API 연결은 테스트하지 않았으며 모의 응답만 사용했다.**
- ML: 기존 소스 기반 변환기·자산 단위 분할·학습/평가·별도 수동 승인 구조 보존. 새로운 `audit_paderborn_raw_recordings.py`는 원본 체크섬·4조건×20 MAT 목록·샘플 수준 진동/전류 중복을 검증한다. `combine_paderborn_raw_audits.py`는 생성된 여러 감사 JSON의 원본 MD5/카탈로그 SHA·신호 SHA·베어링 ID·라벨·교차 자산 중복의 정합성을 검사한다. 단독 JSON만으로 원본 데이터 재검증을 대체할 수 없으므로 실제 원본 확인은 별도 선행해야 한다.
- 통합 자동 검사: [Windows + Linux 개발 회귀](https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41941414421) 통과, 기본 194개 Python 테스트; 이후 추가 데이터 감사 검사를 포함하는 최신 실행 기록은 PR #6 체크에서 확인. [Chromium UI/HTTP 회귀](https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41941492008)도 통과. 개발 검증일 뿐 사용자 PC 실기기 검증은 아니다.
- 실제 원본 검증: [KA04 공식 Zenodo RAR(임시 Windows runner) 재검사](https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41942462085) 성공. 선택된 8 MAT 기록에서 서로 다른 원시 진동+전류 신호 7개, 동일 측정 1쌍(`N09_M07_F10_KA04_17`/`18`) 검출. 신규 코호트 감사 JSON에는 KA04만 들어가므로 다른 11개 자산 감사가 누락으로 보고된다. 이전 K001 실측 사전검사는 별도로 완료했지만 새 감사 JSON에는 포함하지 않았다.
- 원본이 서술된 대학교 출처: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter, https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/test-rig-and-measurement-equipment. 공식 Zenodo 보관: https://zenodo.org/records/15845309. **라이선스 CC BY-NC 4.0 (비상업적 목적 제한).**

## 해결되지 않은 핵심 차단

공식 자료는 센서 유형과 측정 주파수를 알려 주지만 MATLAB 원시 `vibration_1`/ `phase_current_1` 샘플의 수치 스케일이 이미 `m/s²`/ `A`인지, 센서 출력 `V`인지 명확하게 입증하지 않는다. 실제 확인한 MAT의 `Unit` 항목이 공란이다.

그러므로 **raw RMS ≠ 검증된 SI RMS**이며, raw 값에서 `vibration_rms_m_s2`, `current_rms_a`라는 컬럼을 생성하거나 학습·모델 활성화를 허용하지 않는다. 데이터 감사가 12개 자산으로 완성되더라도 단위 및 보정 검토 전에는 이 차단을 해제하지 않는다.

K001 실제 자료 이전 검사와 KA04 검사 이외의 모든 선정 원본 베어링을 독립 다운로드·무결성 검증했다고 주장하지 않는다. 사용자 라벨도 베어링 단위로만 부여하고 동일 물리 베어링의 반복 80개 파일을 80개 독립 자산으로 세지 않는다.

## 다음 개발 단계

1. 공식 기관·보정 문서가 원본 MAT 저장 수치에 적용되는 **구체적인 수치 단위/보정 계수**를 확인하고 원본 해시에 결합해 검토한다. 센서 모델명·데이터 제목만으로 증명된 것으로 처리하지 않는다.
2. 공식 원본 베어링 12개 각각에 대해 출처 체크섬/원시 중복/물리 자산 독립성 검사, 감사 JSON 수집 및 코호트 종합 검사를 수행한다. 원본·가공 데이터는 로컬/일시적 저장소에만 보관한다.
3. 단위가 검증된 자료만 SI CSV로 변환하고, 독립 자산 단위 train/validation/test 분할 → 실측 성능·오류 평가 → 사람의 검토 승인을 거쳐서만 모델 활성화를 고려한다.
4. DeepSeek 유료 API 실제 호출은 **사용자의 명시적 동의와 비용 확인** 뒤 1회 제한된 테스트로 검증한다. 호출 없이 '실연동 완료'로 표시하지 않는다.
5. 개발 기능 완성 후 통합 검증·Windows 사용자 PC 실기기 확인. 이후 사용자가 원할 때만 배포/다운로드본 준비.

현재의 시험·PR은 개발 검증이며 최종 배포 승인이나 완성 판정이 아니다.
