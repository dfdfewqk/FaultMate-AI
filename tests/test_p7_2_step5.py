"""Clipboard copy opt-in and technical details under advanced panel."""
from pathlib import Path
from fastapi.testclient import TestClient
from faultmate.app import app

ROOT = Path(__file__).resolve().parents[1]


def test_copy_is_local_opt_in_and_result_scoped():
    js = (ROOT / 'web/app.js').read_text(encoding='utf-8')
    assert 'copyTextToClipboard(summary)' in js
    assert "data.state === 'candidate_review'" in js
    assert 'reviewVersion !== triageRequestVersion' in js
    assert "triageHazard.value === 'yes'" in js
    assert 'buildLocalReviewSummary(data, reviewedPayload, fromDemo)' in js
    assert "if (fromDemo) lines.push('주의: 가상 시험 입력" in js
    assert 'AI·ML 분석 결과는 포함하지 않습니다.' in js
    assert '정비 작업 허가 아님' in js
    assert 'payload.symptom_text.trim()' in js
    summary = js[js.index('function buildLocalReviewSummary'):js.index('async function copyTextToClipboard')]
    assert 'model_name' not in summary and 'alarm_text' not in summary


def test_technical_status_removed_from_first_screen_not_from_advanced():
    with TestClient(app) as client:
        html = client.get('/').text
    assert 'id="agent-status"' in html
    assert html.index('id="agent-status"') > html.index('id="integration-panel"')
    assert 'AI 연결:' not in html.split('<h1>')[0]
    assert 'id="integration-ml"' in html
    assert 'id="triage-result"' in html
