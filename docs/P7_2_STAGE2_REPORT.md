# FaultMate AI P7.2 — 2단계 안전 안내 개선

## 변경 범위
- `web/index.html`: 안전 확인을 추천·사례 선택 앞에 배치; 항상 표시되는 안전 상태 안내 추가.
- `web/app.js`: `unknown`, `no`, `yes`별 안내 및 결과 요약, 초기화 후 상태 복원. 긴급 위험에서는 AI 미리보기와 ML 파일 선택도 비활성화.
- `web/style.css`: 세 상태를 구별하는 접근성 대비를 고려한 경고 스타일 및 모바일 대응.
- `tests/test_p7_2_step2.py`, `tests/browser_step2.py`: 순서·상태 구분·위험 차단·초기화·모바일 검증.

## 경계
- 정보 검토와 안전한 작업의 허가는 별개입니다. '위험 없음'은 앱에 입력된 관찰이며 안전 인증이 아닙니다.
- 실제 정비 작업 전 승인·잠금·에너지 차단·잔류 에너지 확인은 사업장 및 장비별 절차를 따라야 합니다.
- P7.2-1 기존 추천 및 사례 7개, P7.1 안전 로직, DeepSeek/ML API 계약은 변경하지 않았습니다.
- 실제 API 호출·실제 ML 모델·Windows 사용자 장치 테스트는 이 단계의 결과에 포함되지 않습니다.

## 검증 실행
```sh
python -m pytest -q tests
node --check web/app.js
PYTHONPATH=. python tests/browser_smoke.py
PYTHONPATH=. python tests/browser_step1.py
PYTHONPATH=. python tests/browser_step2.py
PYTHONPATH=. python tests/live_http_smoke.py
```
