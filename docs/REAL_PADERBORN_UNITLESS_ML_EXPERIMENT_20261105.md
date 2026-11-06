# FaultMate AI — 2026-11-05 실제 Paderborn 학습 대체 경로

## 대상
저장소 `dfdfewqk/FaultMate-AI`, 작업 브랜치 `work/faultmate-real-unitless-ml-20261105`. 기존 6단계 프로그램 통합 코드를 유지. **기존 SI 기반 변환기·출처별 단위 보정 강제 학습 및 정식 모델 승인 절차는 수정하지 않는다.**

대상 12개 독립 베어링:
- 정상: K001, K002, K003, K004, K005, K006
- 실제 가속수명 손상: KA04, KA16, KB23, KI04, KI16, KI18

**기존 공식 Zenodo RAR 각 80 MATLAB 원본 = 총 960회 측정. KA04의 4개 동일 원신호 측정을 제외하면 최대 956개의 고유 기록. 이 숫자는 956개 독립 베어링이 아니며 독립 물리 베어링은 12개뿐이다.**

원본 출처:
- https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download
- https://zenodo.org/records/15845309
- Lessmeier 등(2016) Paderborn 실험 및 표 5·6: https://mb.uni-paderborn.de/fileadmin-mb/kat/PDF/Veroeffentlichungen/20160703_PHME16_CM_bearing.pdf
- 라이선스: CC BY-NC 4.0. **상업적 사용은 별도 허가가 필요.**

## 왜 새로운 대체 경로가 필요한가
기존 `vibration_rms_m_s2` 및 `current_rms_a` 기반 선형 모델은 저장 MAT의 실제 단위와 감도/오프셋 검증이 필요하다. MAT `Unit` 필드가 빈 원본에 임의로 SI 물리 단위를 부여하지 않는다.

대신 **학습 실험 전용** `raw shape` 경로에서 각 원시 채널을 윈도별로 평균 0·RMS 1로 정규화한 후 단위 없는 통계/스펙트럼 특징만 계산한다. 이 특징은 각 채널에 상수 DC 오프셋을 더하거나 비영(양수) 게인을 곱해도 변하지 않는다. FFT의 주파수 구역은 Hz가 아니라 **각 샘플링 신호의 나이퀴스트 분율**로 정의한다.

단위가 없는 특징은 **실측 진동 가속도/전류(A)를 의미하지 않는다.** 절대 진폭 정보가 소실될 수 있으므로 모델 성능이 충분하지 않을 수도 있다. 모터/컨베이어/센서의 모든 장애를 분류하거나 실제 설비의 작업 안전 허가를 할 수 있는 모델도 아니다.

## 코드

- `scripts/extract_paderborn_unitless.py`
  - Zenodo 원본 RAR 공식 MD5, 7z 압축 무결성, 모든 80 MAT(4조건×20) 명칭 검증.
  - 기록마다 원본 MAT SHA256, 진동/전류 결합 샘플 SHA256, 원신호 샘플 수 기록.
  - 중앙/양끝 3개의 16,384샘플 구간에서 12개 차원 없는 특징(두 센서 각각 첨도, 첨두계수, 절대값 분위 비율, 스펙트럼 엔트로피, 고주파 전력 비율, 영점교차 비율)을 계산하고 중앙값으로 요약.
  - 동일 원신호 중복이면 첫 번째 기록만 특징을 보존. 이후 중복된 기록은 `duplicate_of`와 원신호 해시만 기록하고 학습값은 비운다.
  - 각 임시 MAT 추출 파일을 처리 직후 제거하며 원신호 자체를 GitHub에 업로드하지 않는다.
- `scripts/train_paderborn_unitless.py`
  - 새로 뽑은 모든 12개 특징 JSON을 **기존 12개 원본 실측 감사 JSON**과 이름·MAT SHA256·진동+전류 원신호 SHA256까지 대조.
  - 공식 원본 체크섬 및 베어링별 healthy/damaged 라벨 재확인, 정확히 960회·956개 고유 신호/KA04 중복 4개 요구. 불일치는 **학습 시작 전 실패**.
  - 미리 고정한 난수 시드로 베어링별 train 8개·검증 2개·최종 봉인 시험 2개(각 클래스 1개) 구성. 원본 기록 및 그 부분 신호를 쪼개어 다른 베어링으로 취급하지 않는다.
  - 학습 구간의 `StandardScaler` 및 고정 `LogisticRegression` 사용. 학습자산마다 전체 가중치 동일. 검증·테스트 자산은 scaler의 적합 단계에서 제외.
  - 총 10개 개발 베어링의 leave-one-bearing-out 교차검증 결과와, 개발 10개로 학습한 모델의 **별도 물리 베어링 2개 최종 시험** 결과를 구분해서 기록. 시험에 쓸 임계값은 사전에 0.5로 고정하며 test 성능을 보고 바꾸지 않는다.
  - 정상 오경보·손상 미탐·혼동행렬·macro F1·오류와 평가한 실제 베어링 ID를 평가 보고서에 포함.
  - 결과는 `real_unitless_evaluation.json`과 `experimental_unapproved_model.json`으로만 보존. 정식 `bearing_validated.json` 또는 앱의 모델 로딩 경로를 **생성하거나 변경하지 않는다.** 대상 폴더 기존 출력 덮어쓰기 금지.
- `tests/test_unitless_real_ml_pipeline.py`
  - 신호 비영 게인·DC 오프셋 불변성, 불량 신호, 12개 독립 자산/원본 MAT 해시 검증, 중복 제외, 봉인 시험 분리, 합성 테스트 결과 자동 승인 방지.
  - 테스트의 합성 결과는 실제 모델 성능이 아님.
- `.github/workflows/real-paderborn-unitless-ml.yml`
  - 전체 단위·보안 Python 검사 통과 후 **12개 Windows CI 잡이 실제 Zenodo 원본을 임시 다운로드**하고 공식 체크섬·원신호·특징을 재확인.
  - 완료된 12개만 합쳐 기존 3단계 실제 원신호 감사 증거와 교차 검증 후 실측 학습. 측정 신호 자체는 저장소나 아티팩트에 저장하지 않음.
  - 무료 API 여부와 무관하게 DeepSeek 유료 호출은 없으며, 실제 ML이 없던 상태의 프로그램 런타임은 그대로 차단된다.

## 완성 판정
- 실제 원본 추출·소스 감사 결합·학습·독립 베어링 시험까지 GitHub Actions 완료 로그에서 확인된 경우에만 **'실측 ML 실험 수행'**이라 말한다.
- 두 시험 베어링만의 정확도는 일반화 보장의 근거로 불충분하며, 높은 시험 점수도 자동 모델 활성화 조건이 아니다.
- 실제 현장 설비 배포를 위해서는 더 많은 서로 다른 베어링/현장 자료 및 사용자/안전 검토가 필요하다.
- 정식 SI 근거 없는 기존 `scripts/train_ml.py`의 차단과 합성 fixture 전용 예외 정책은 유지한다.

## CI 기록
https://github.com/dfdfewqk/FaultMate-AI/actions/workflows/real-paderborn-unitless-ml.yml

본 문서는 실측 학습의 설계·검증 요건을 설명한다. 실제 결과는 GitHub Actions의 **최종 training job** 로그에서 성공을 확인한 뒤에만 기록해야 한다.
