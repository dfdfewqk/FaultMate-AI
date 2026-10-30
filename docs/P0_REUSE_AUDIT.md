# P0 — 기존 MicroLoss R4 코드 재사용 검토

기준 원본: `MicroLoss_AI_R4_AllLaunchers_FullFix.zip` (읽기 전용으로 조사). 기존 ZIP/저장소 변경 없음.

| 영역 | 판단 | 이유 및 P0 처리 |
|---|---|---|
| `scripts/start_production.py` | 패턴 재사용 | 프로젝트 루트 import, 포트 자동 선택, 서버 준비 후 브라우저 열기 패턴만 재구현 |
| `backend/app.py` | 구조 재사용 | FastAPI `/api`와 단일 로컬 서버 패턴만 가져옴; MicroLoss API는 가져오지 않음 |
| `web/src/main.css` | 디자인 원칙 재사용 | 카드·색상·반응형 레이아웃을 FaultMate용으로 재구성 |
| `web/src/main.tsx` | 미래 단계 참조 | MicroLoss 상태·예측 UI와 결합돼 P0에 직접 복사하지 않음; P4에서 React로 이전 |
| `backend/agent.py` | 실행 루프 원칙 참조 | 도구 화이트리스트·횟수 제한·사용자 동의·서버 키 분리 원칙만 보존; 기존 통계 분석 도구·시스템 프롬프트 복사 금지 |
| `backend/analysis.py` | 일부 헬퍼만 추후 검토 | 기존 미세정지·생산손실 파서가 정비 이력 스키마와 달라 그대로 재사용 불가 |
| `backend/prediction.py`·`pipeline/train_baseline.py` | 제외 | 목표 레이블과 기계학습 타깃이 완전히 다름. 신뢰 가능한 새 데이터 없이는 새 ML 학습 금지 |
| `pipeline/synthetic_hourly.csv` | 제외 | 새 고장 진단 기능과 관련 없는 미세정지 DEMO |
| MicroLoss 전용 CI/검사 | 제외 | P0부터 FaultMate 이름·실행 경로로 별도 검사 구성 |

## P0 경계

실행/상태 확인만 포함. 무상태 로컬 API. DeepSeek 네트워크 통신 또는 임의 추론 없음. 단일 주소에서 화면과 `/api/status`를 제공. Windows 실행은 소스 수준 점검, 실제 Windows 성공은 별도 확인 필요.

## 개발 게이트

P1: 검증된 고장 사례/매뉴얼 문서의 출처와 사용 권한을 확보하고, 오류 가능성을 분리할 것. P2: 안전 점검 및 확인 결과의 단계별 흐름. P3: 명시적 외부 전송 동의 및 읽기 전용 도구. P4: React UI 변경 후 실제 npm 빌드와 브라우저 검증.
