(async function () {
  const badge = document.getElementById('status');
  const list = document.getElementById('knowledge-list');
  const detail = document.getElementById('knowledge-detail');
  const filter = document.getElementById('equipment-filter');
  const request = async path => {
    const response = await fetch(path, {cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.json();
  };
  const add = (parent, tag, value, cls) => {
    const node = document.createElement(tag);
    node.textContent = value;
    if (cls) node.className = cls;
    parent.appendChild(node);
    return node;
  };
  // Status is informational. A slow or failed status request must never delay
  // installation of the diagnostic handlers or retrieval of triage options.
  void (async () => {
    try {
      const status = await request('/api/status');
      if (status.app !== 'FaultMate AI' || status.api !== 'ok' || status.phase !== 'P2') throw new Error('unexpected status');
      badge.textContent = '로컬 서버 연결 정상';
      badge.classList.add('ok');
    } catch (_e) {
      badge.textContent = '서버 연결 확인 필요';
      badge.classList.add('bad');
    }
  })();
  let sources = {};
  let sourcesAvailable = false;
  let caseViewVersion = 0;
  async function showCase(id) {
    const version = ++caseViewVersion;
    for (const button of list.querySelectorAll('button[data-case]')) button.setAttribute('aria-pressed', String(button.dataset.case === id));
    detail.replaceChildren();
    add(detail, 'p', '근거 자료를 불러오는 중...', 'small-note');
    try {
      const data = await request('/api/knowledge/cases/' + encodeURIComponent(id));
      if (version !== caseViewVersion) return false;
      const c = data.case;
      detail.replaceChildren();
      add(detail,'p','미확정 사례 · 고장 원인 확정 아님','small-note');
      add(detail,'h3',c.title);
      add(detail,'h4','확인 가능한 기존 정보');
      const obs = document.createElement('ul'); detail.appendChild(obs);
      for (const o of c.observations) add(obs,'li',o.item);
      add(detail,'h4','원인 후보 (미확정)');
      for (const item of c.candidate_causes) {
        add(detail,'p',item.candidate + ' — ' + item.why_to_consider, 'case-evidence');
        for (const sid of item.source_ids) {
          const s = sources[sid]; if (!s) continue;
          addSafeSourceLink(detail, s, '근거: ' + s.organization + ' / ' + s.title);
          add(detail,'p','적용 한계: ' + s.limit,'small-note');
        }
      }
      add(detail,'h4','다음에 필요한 정보');
      const qs = document.createElement('ul'); detail.appendChild(qs);
      for (const q of c.missing_evidence_questions) add(qs,'li',q);
      add(detail,'h4','안전 조건');
      add(detail,'p',c.required_safety_gate,'safety-note');
      add(detail,'p',c.stop_escalation,'small-note');
      const useCase = add(detail, 'button', '이 사례로 진단 검토하기', 'case-use');
      useCase.type = 'button';
      useCase.addEventListener('click', () => selectCaseForTriage(c.equipment, c.case_id));
      return true;
    } catch (_e) {
      if (version !== caseViewVersion) return false;
      detail.replaceChildren(); add(detail,'p','사례를 불러오지 못했습니다. 자료실을 다시 열면 재시도합니다.');
      return false;
    }
  }
  function addSafeSourceLink(parent, source, label) {
    try {
      const url = new URL(source.url);
      if (url.protocol !== 'https:') throw new Error('unsafe source URL');
      const link = document.createElement('a');
      link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.textContent = label; parent.appendChild(link);
    } catch (_e) { add(parent, 'p', label + ' · 안전한 참고 링크 없음', 'small-note'); }
  }
  // P7.2 step 4: the knowledge room is optional and initially collapsed.
  // Do not fetch its sources or cases before the operator opens the section.
  // A failed load can be retried on the next open; repeated toggles share one
  // in-flight request and do not repeatedly contact the server.
  let listViewVersion = 0;
  let knowledgeLoaded = false;
  let knowledgeLoadPromise = null;
  let lastRenderedFilter = null;
  const knowledgePanel = document.getElementById('knowledge-panel');
  async function render() {
    const version = ++listViewVersion;
    ++caseViewVersion;
    list.replaceChildren();
    add(list, 'p', '등록된 사례를 확인하는 중...', 'small-note');
    detail.replaceChildren();
    try {
      const requestedFilter = filter.value;
      const param = requestedFilter ? '?equipment=' + encodeURIComponent(requestedFilter) : '';
      const data = await request('/api/knowledge/cases' + param);
      if (version !== listViewVersion || requestedFilter !== filter.value) return false;
      list.replaceChildren();
      for (const c of data.cases) {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'knowledge-item'; button.dataset.case = c.case_id; button.setAttribute('aria-pressed', 'false');
        add(button,'span',c.equipment + ' · ' + c.case_id,'small-note');
        add(button,'strong',c.title); list.appendChild(button);
        button.addEventListener('click',()=>showCase(c.case_id));
      }
      if (data.cases.length === 0) {
        add(list,'p','등록된 사례가 없습니다.');
        add(detail,'p','조회 가능한 사례가 없습니다.');
      } else {
        // A failed detail fetch must not mark the whole knowledge room as cached.
        // Reopening the panel should retry instead of leaving a broken case view.
        if (!await showCase(data.cases[0].case_id)) return false;
      }
      lastRenderedFilter = requestedFilter;
      return true;
    } catch (_e) {
      if (version === listViewVersion) {
        list.replaceChildren();
        add(list,'p','서버의 근거 사례집을 불러오지 못했습니다. 자료실을 닫았다가 다시 열어보세요.');
        detail.replaceChildren();
      }
      return false;
    }
  }
  async function ensureKnowledgeLoaded() {
    if (knowledgeLoaded) return;
    if (knowledgeLoadPromise) return knowledgeLoadPromise;
    knowledgeLoadPromise = (async () => {
      // A failure to fetch external source metadata never blocks local triage
      // or viewing case summaries; URLs simply won't be displayed.
      if (!sourcesAvailable) {
        try {
          const data = await request('/api/knowledge/sources');
          sources = Object.fromEntries(data.sources.map(s => [s.id,s]));
          sourcesAvailable = true;
        } catch (_e) {
          sources = {};
        }
      }
      const ok = await render();
      if (ok && !sourcesAvailable) add(detail, 'p', '출처 링크 조회에 실패했습니다. 자료실을 닫았다가 다시 열면 재시도합니다.', 'small-note');
      knowledgeLoaded = ok && sourcesAvailable;
    })().finally(() => { knowledgeLoadPromise = null; });
    return knowledgeLoadPromise;
  }
  filter.addEventListener('change', () => {
    if (!knowledgePanel.open) {
      knowledgeLoaded = false;
      return;
    }
    if (knowledgeLoadPromise) {
      // A change while the original request is pending must refresh the
      // final selection, not accidentally show the previous filter.
      ++listViewVersion;
      void knowledgeLoadPromise.then(() => {
        if (knowledgePanel.open && lastRenderedFilter !== filter.value) {
          knowledgeLoaded = false;
          void ensureKnowledgeLoaded();
        }
      });
    } else {
      knowledgeLoaded = false;
      void ensureKnowledgeLoaded();
    }
  });
  knowledgePanel.addEventListener('toggle', () => {
    if (knowledgePanel.open) void ensureKnowledgeLoaded();
  });
  if (knowledgePanel.open) void ensureKnowledgeLoaded();

  // P5 UI integration. All user/source text is inserted with textContent; no HTML injection.
  // The frontend never calls an external server. Agent and ML remain Antigravity-owned.
  const triageForm = document.getElementById('triage-form');
  const triageEquipment = document.getElementById('triage-equipment');
  const triageCase = document.getElementById('triage-case');
  const triageChecks = document.getElementById('triage-checks');
  const triageResult = document.getElementById('triage-result');
  const triageSubmit = document.getElementById('triage-submit');
  const triageHazard = document.getElementById('triage-hazard');
  const hazardStatus = document.getElementById('hazard-status');
  const hazardGate = document.getElementById('hazard-gate');
  // The three states describe *reported observations*, never permission to work.
  // Keep the summary visible even when there is no selected case/result.
  function updateHazardStatus() {
    const state = triageHazard.value;
    const messages = {
      yes: '긴급 위험 징후 있음 · 원인 후보 검토와 AI·ML 분석을 중단합니다. 안전한 곳에서 사업장 비상 절차에 따라 책임자에게 알리세요. 임의 접근·재가동 금지.',
      unknown: '안전 상태 미확인 · 원인 후보는 정보 검토용으로만 볼 수 있습니다. 위험 확인을 위해 설비에 접근하지 마세요. 실제 점검·정비 전 현장 안전 절차가 별도로 필요합니다.',
      no: '관찰된 긴급 위험 징후 없음 · 안전하다는 인증이나 정비 작업 허가가 아닙니다. 실제 작업 전 현장 승인과 설비별 에너지 차단·잠금·잔류 에너지 확인 절차가 필요합니다.',
    };
    hazardStatus.className = 'hazard-status is-' + (messages[state] ? state : 'unknown');
    hazardStatus.textContent = messages[state] || messages.unknown;
    hazardGate.dataset.hazard = messages[state] ? state : 'unknown';
  }
  updateHazardStatus();
  const triageSuggestionList = document.getElementById('triage-suggestion-list');
  const triageSymptom = document.getElementById('triage-symptom');
  const triageFeedback = document.getElementById('triage-feedback');
  const demoBanner = document.getElementById('demo-banner');
  const demoButton = document.getElementById('triage-demo');
  const addList = (parent, items) => {
    const ul = document.createElement('ul'); parent.appendChild(ul);
    for (const item of items) add(ul, 'li', item);
    return ul;
  };
  let triageOptions = null;
  let triageRequestVersion = 0;
  let activeTriageController = null;
  let suggestionVersion = 0;
  let suggestionController = null;
  let suggestionTimer = null;
  let demoMode = false;
  let agentConsent = null;
  let agentRun = null;
  let agentPreviewContent = null;
  let agentResult = null;
  let agentRequestController = null;
  let agentPreviewVersion = 0;
  let lastPreviewVersion = -1;
  const syncTriageButton = () => {
    triageSubmit.disabled = !triageOptions || !triageCase.value || triageHazard.value === 'yes' || !!activeTriageController;
    demoButton.disabled = !triageOptions || triageHazard.value === 'yes';
  };
  function invalidateTriage(message = '입력이 변경되어 이전 결과를 지웠습니다. 다시 검토하세요.') {
    ++triageRequestVersion;
    if (activeTriageController) {
      activeTriageController.abort();
      activeTriageController = null;
    }
    triageResult.replaceChildren();
    add(triageResult, 'p', message, 'small-note');
    invalidateAgentReview();
    triageFeedback.textContent = triageOptions ? '' : '진단 자료를 불러올 수 없어 검토가 불가능합니다.';
    syncTriageButton();
    if (triageHazard.value === 'yes') showEmergencyHold();
  }
  function repopulateCases() {
    triageCase.replaceChildren(new Option('사례를 선택하세요', ''));
    if (triageOptions) {
      for (const c of triageOptions.cases.filter(c => c.equipment === triageEquipment.value)) {
        triageCase.appendChild(new Option(c.title, c.case_id));
      }
    }
    renderQuestions();
  }
  function renderQuestions() {
    triageChecks.replaceChildren();
    if (!triageOptions || !triageCase.value) {
      add(triageChecks, 'p', '사례를 먼저 선택하세요.', 'small-note');
      return;
    }
    for (const q of triageOptions.questions_by_case[triageCase.value] || []) {
      const div = document.createElement('div'); div.className = 'check-item'; triageChecks.appendChild(div);
      const label = add(div, 'label', q.label); label.htmlFor = 'check-' + q.id;
      const select = document.createElement('select'); select.id = 'check-' + q.id; select.dataset.key = q.id;
      for (const [v, t] of [['unknown','확인 안 됨'], ['yes','예 (기록·관찰 있음)'], ['no','아니오 (기록·관찰 없음)']]) {
        select.add(new Option(t,v));
      }
      div.appendChild(select);
    }
  }
  // Stage P7.2-1: reuse the existing local deterministic /evaluate selection_required
  // path. Suggestions do not trigger diagnosis, AI requests or automatic selection.
  function cancelSuggestions() {
    ++suggestionVersion;
    if (suggestionTimer !== null) {
      clearTimeout(suggestionTimer);
      suggestionTimer = null;
    }
    if (suggestionController) {
      suggestionController.abort();
      suggestionController = null;
    }
  }
  function suggestionMessage(message) {
    triageSuggestionList.replaceChildren();
    add(triageSuggestionList, 'p', message, 'small-note');
  }
  function scheduleSuggestions() {
    cancelSuggestions();
    if (triageHazard.value === 'yes') {
      suggestionMessage('긴급 위험 징후가 있어 사례 추천을 중단했습니다. 현장 비상 절차를 따르세요.');
      return;
    }
    if (!triageOptions) {
      suggestionMessage('로컬 진단 자료를 불러오면 관련 사례를 확인할 수 있습니다.');
      return;
    }
    if (!triageEquipment.value) {
      suggestionMessage('설비 종류를 먼저 선택해 주세요.');
      return;
    }
    const symptom = triageSymptom.value.trim();
    if (!symptom) {
      suggestionMessage('관찰 증상을 입력하면 관련 사례를 찾아줍니다. 직접 사례를 선택해도 됩니다.');
      return;
    }
    const version = suggestionVersion;
    suggestionMessage('기존 사례와 증상을 비교하고 있습니다...');
    suggestionTimer = setTimeout(async () => {
      suggestionTimer = null;
      const controller = new AbortController();
      suggestionController = controller;
      try {
        const response = await fetch('/api/diagnostics/evaluate', {
          method: 'POST', headers: {'Content-Type': 'application/json'}, cache: 'no-store',
          signal: controller.signal,
          body: JSON.stringify({
            equipment: triageEquipment.value, case_id: null,
            symptom_text: symptom, observations: {}, emergency_hazard: triageHazard.value,
          }),
        });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const data = await response.json();
        if (version !== suggestionVersion || controller.signal.aborted || triageHazard.value === 'yes') return;
        triageSuggestionList.replaceChildren();
        if (data.state !== 'selection_required') {
          suggestionMessage('현재 사례 추천을 사용할 수 없습니다.');
          return;
        }
        const matches = (data.suggested_cases || []).filter(c =>
          triageOptions.cases.some(x => x.case_id === c.case_id && x.equipment === triageEquipment.value));
        if (!matches.length) {
          suggestionMessage('입력 증상과 일치하는 등록 사례가 없습니다. 지원 범위 밖일 수 있으므로 억지로 다른 사례를 선택하지 마세요.');
          return;
        }
        add(triageSuggestionList, 'p', '문구가 비슷한 참고 사례입니다. 실제 고장 원인이나 추천 정확도를 보증하지 않습니다.', 'small-note');
        for (const item of matches) {
          const button = document.createElement('button');
          button.type = 'button'; button.className = 'suggestion-choice';
          button.dataset.suggestCase = item.case_id;
          add(button, 'b', item.title);
          add(button, 'small', item.case_id + ' · 참고용 · 직접 선택');
          button.addEventListener('click', () => {
            // Check again to avoid selecting a stale or mismatched case.
            if (version !== suggestionVersion || triageHazard.value === 'yes' ||
                triageEquipment.value !== item.equipment) return;
            triageCase.value = item.case_id;
            renderQuestions();
            demoMode = false; demoBanner.hidden = true;
            invalidateTriage('관련 사례를 선택했습니다. 기록 확인 항목을 검토하세요.');
            triageCase.focus();
          });
          triageSuggestionList.appendChild(button);
        }
      } catch (_e) {
        if (version === suggestionVersion && !controller.signal.aborted)
          suggestionMessage('사례 추천 조회에 실패했습니다. 서버를 확인하거나 기존 목록에서 직접 선택하세요.');
      } finally {
        if (suggestionController === controller) suggestionController = null;
      }
    }, 350);
  }
  function currentPayload() {
    const observations = {};
    for (const element of triageChecks.querySelectorAll('select[data-key]')) {
      observations[element.dataset.key] = element.value;
    }
    return {
      equipment: triageEquipment.value, case_id: triageCase.value,
      symptom_text: document.getElementById('triage-symptom').value,
      model_name: document.getElementById('triage-model').value,
      alarm_text: document.getElementById('triage-alarm').value,
      emergency_hazard: triageHazard.value, observations,
    };
  }
  // P7.2 step 5: an operator-readable clipboard summary of a completed
  // LOCAL review only. No network call, persistence, or AI/ML result inclusion.
  // The summary is recreated per successful diagnosis and removed on edits,
  // emergency holds and reset together with the existing result DOM.
  function buildLocalReviewSummary(data, payload, fromDemo) {
    const lines = [
      'FaultMate AI · 로컬 고장 검토 요약',
      '판정: 교육·검토용 원인 후보 / 실제 원인 미확정 / 정비 작업 허가 아님',
    ];
    if (fromDemo) lines.push('주의: 가상 시험 입력 · 실제 설비 점검 결과 아님');
    lines.push('설비: ' + payload.equipment);
    lines.push('사례: ' + data.case_title);
    if (payload.symptom_text?.trim()) lines.push('관찰 증상(작업자 입력): ' + payload.symptom_text.trim());
    lines.push('긴급 위험 징후: ' + (payload.emergency_hazard === 'no'
      ? '관찰되지 않음(안전 인증 아님)' : '미확인(안전 확인 필요)'));
    lines.push('검토할 원인 후보(확률·우선순위·확정 아님):');
    for (const candidate of data.candidate_causes || []) {
      lines.push(' - ' + candidate.candidate + ' (' + candidate.review_group + ')');
    }
    const questions = (data.next_questions || []).map(q => q.question)
      .concat(data.additional_information_questions || []);
    if (questions.length) {
      lines.push('먼저 확인할 기존 기록:');
      for (const question of questions.slice(0, 2)) lines.push(' - ' + question);
    }
    lines.push('안전 조건: ' + data.safety_gate);
    lines.push('중단·보고 기준: ' + data.stop_escalation);
    lines.push('이 요약은 로컬 규칙 기반 검토만 포함합니다. AI·ML 분석 결과는 포함하지 않습니다.');
    lines.push('실제 현장 작업은 사업장 승인 및 설비별 안전 절차를 따르세요.');
    return lines.join('\n');
  }
  async function copyTextToClipboard(value) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return;
    }
    // Old Windows browser/non-secure context fallback; always remove the node.
    const temp = document.createElement('textarea');
    temp.value = value;
    temp.setAttribute('readonly', '');
    temp.setAttribute('aria-hidden', 'true');
    temp.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
    document.body.appendChild(temp);
    try {
      temp.focus();
      temp.select();
      if (!document.execCommand('copy')) throw new Error('clipboard_unavailable');
    } finally {
      temp.remove();
    }
  }
  // P7.2 step 3: operator-first result. All existing evidence and limits remain
  // accessible, but the first view shows only what is needed to review next.
  // Rendering is text-only: never interpret untrusted case/source text as HTML.
  function renderTriageResult(data, fromDemo, reviewedPayload) {
    triageResult.replaceChildren();
    if (data.state === 'safety_hold') {
      add(triageResult, 'div', data.message, 'result-hold'); return;
    }
    if (data.state === 'selection_required') {
      add(triageResult, 'h3', '사례를 직접 선택해야 합니다');
      add(triageResult, 'p', data.message);
      if (data.suggested_cases && data.suggested_cases.length) {
        add(triageResult, 'h4', '참고 가능한 사례 (자동 고장 판정 아님)');
        addList(triageResult, data.suggested_cases.map(c => c.title));
      }
      return;
    }
    if (fromDemo) add(triageResult, 'p', '가상 시험 입력에 대한 결과입니다. 실제 설비 진단이 아닙니다.', 'result-hold');
    const safetySummary = triageHazard.value === 'unknown'
      ? '긴급 위험 확인 전 · 정보 검토만 가능 · 정비 작업 허가 아님'
      : '긴급 위험 징후가 관찰되지 않았다는 기록 · 안전 인증·정비 작업 허가 아님';
    add(triageResult, 'p', safetySummary + ' · 원인 미확정 · AI/ML 미사용', 'result-note');
    add(triageResult, 'h3', data.case_title);
    add(triageResult, 'p', data.message, 'result-intro');

    // Preserve the complete candidate set and its original review grouping.
    add(triageResult, 'h4', '검토할 원인 후보 (확률·확정 순위가 아님)');
    for (const c of data.candidate_causes || []) {
      const div = document.createElement('div'); div.className = 'result-cause'; triageResult.appendChild(div);
      add(div, 'b', c.candidate + ' · ' + c.review_group);
      add(div, 'p', c.why_to_consider);
    }

    const questions = (data.next_questions || []).map(q => q.question)
      .concat(data.additional_information_questions || []);
    add(triageResult, 'h4', '먼저 확인할 기존 기록');
    if (questions.length) {
      addList(triageResult, questions.slice(0, 2));
      if (questions.length > 2)
        add(triageResult, 'p', '추가 질문 ' + (questions.length - 2) + '개는 아래 상세 보기에서 확인하세요.', 'small-note');
    } else {
      add(triageResult, 'p', '현재 입력 항목은 채워졌지만 고장 원인이 검증되었다는 뜻은 아닙니다.');
    }

    // Required safety conditions remain always visible; never hide them in details.
    add(triageResult, 'h4', '안전 조건 · 정비 작업 허가 아님');
    add(triageResult, 'p', data.safety_gate, 'result-hold');
    add(triageResult, 'p', data.stop_escalation, 'result-note');

    // A copy action is attached only to a valid local candidate review.
    // The callback becomes unreachable when the result is invalidated.
    if (data.state === 'candidate_review' && reviewedPayload) {
      const copyRow = document.createElement('div');
      copyRow.className = 'result-copy-actions';
      triageResult.appendChild(copyRow);
      const copyButton = add(copyRow, 'button', '진단 요약 복사', 'result-copy-button');
      copyButton.type = 'button';
      const feedback = add(copyRow, 'span', '복사 후 공유하기 전에 내용을 확인하세요.', 'result-copy-feedback');
      feedback.setAttribute('role', 'status');
      feedback.setAttribute('aria-live', 'polite');
      const summary = buildLocalReviewSummary(data, reviewedPayload, fromDemo);
      const reviewVersion = triageRequestVersion;
      copyButton.addEventListener('click', async () => {
        if (reviewVersion !== triageRequestVersion || triageHazard.value === 'yes' || !copyButton.isConnected) return;
        copyButton.disabled = true;
        try {
          await copyTextToClipboard(summary);
          if (reviewVersion === triageRequestVersion && copyButton.isConnected)
            feedback.textContent = '요약을 복사했습니다. 외부 전송·자동 저장은 하지 않았습니다.';
        } catch (_e) {
          if (reviewVersion === triageRequestVersion && copyButton.isConnected)
            feedback.textContent = '자동 복사에 실패했습니다. 브라우저 권한을 확인하거나 결과를 직접 선택해 복사하세요.';
        } finally {
          if (reviewVersion === triageRequestVersion && copyButton.isConnected) copyButton.disabled = false;
        }
      });
    }

    const details = document.createElement('details');
    details.className = 'result-details';
    details.id = 'triage-result-details';
    triageResult.appendChild(details);
    add(details, 'summary', '상세 근거·전체 확인 질문·출처 및 적용 한계 보기');
    add(details, 'h4', '입력된 관찰과 후보별 근거');
    for (const c of data.candidate_causes || []) {
      const entry = document.createElement('div'); entry.className = 'result-evidence'; details.appendChild(entry);
      add(entry, 'b', c.candidate + ' · ' + c.review_group);
      add(entry, 'p', c.reported_indicators?.length
        ? '입력된 관찰: ' + c.reported_indicators.join(' / ')
        : '이 후보를 뒷받침하는 관찰은 현재 확인되지 않았습니다.', 'small-note');
      add(entry, 'p', '근거 ID: ' + c.source_ids.join(', ') + ' · 미확정', 'small-note');
    }
    add(details, 'h4', '전체 추가 확인 질문');
    if (questions.length) addList(details, questions);
    else add(details, 'p', '현재 추가 질문이 없습니다. 고장 원인 확정은 아닙니다.', 'small-note');
    add(details, 'h4', '사례 선택 기준');
    add(details, 'p', data.selection_basis, 'result-note');
    add(details, 'h4', '참고 출처 / 적용 한계');
    for (const s of data.sources || []) {
      addSafeSourceLink(details, s, s.organization + ' — ' + s.title);
      add(details, 'p', s.limit, 'result-note');
    }
    add(details, 'p', data.notice, 'result-note');
  }

  function selectCaseForTriage(equipment, caseId) {
    if (!triageOptions) return;
    const allowed = triageOptions.cases.some(c => c.equipment === equipment && c.case_id === caseId);
    if (!allowed) return;
    triageEquipment.value = equipment;
    repopulateCases();
    triageCase.value = caseId;
    renderQuestions();
    demoMode = false;
    demoBanner.hidden = true;
    invalidateTriage('자료실에서 선택한 사례를 불러왔습니다. 관찰 항목을 확인하세요.');
    document.getElementById('diagnostic-panel').scrollIntoView({behavior:'smooth', block:'start'});
  }
  function showEmergencyHold() {
    triageResult.replaceChildren();
    add(triageResult, 'p', '긴급 위험 징후가 보고되었습니다. 진단을 중단하고 현장 비상 절차에 따라 즉시 책임자에게 알리세요. 위험 구역 접근·임의 재가동 금지.', 'result-hold');
    triageFeedback.textContent = '긴급 위험: 진단 요청 차단됨';
  }
  triageHazard.addEventListener('change', () => {
    updateHazardStatus();
    invalidateTriage();
    scheduleSuggestions();
    syncTriageButton();
  });
  triageEquipment.addEventListener('change', () => {
    repopulateCases();
    invalidateTriage('설비가 변경되었습니다. 사례와 관찰을 다시 선택하세요.');
    scheduleSuggestions();
  });
  triageCase.addEventListener('change', () => {
    renderQuestions();
    invalidateTriage('선택한 사례의 관찰 항목이 변경되었습니다.');
  });
  triageChecks.addEventListener('change', () => invalidateTriage());
  triageSymptom.addEventListener('input', () => {
    // An edited symptom must not silently reuse an earlier selected case.
    const hadCase = Boolean(triageCase.value);
    if (hadCase) {
      triageCase.value = '';
      renderQuestions();
    }
    demoMode = false; demoBanner.hidden = true;
    invalidateTriage(hadCase
      ? '증상이 변경되어 이전 사례 선택을 초기화했습니다. 추천 사례를 다시 확인하세요.'
      : '증상이 변경되었습니다. 관련 사례를 확인하세요.');
    scheduleSuggestions();
  });
  for (const field of ['triage-model','triage-alarm']) {
    document.getElementById(field).addEventListener('input', () => invalidateTriage());
  }
  demoButton.addEventListener('click', () => {
    if (!triageOptions || triageHazard.value === 'yes') return;
    triageEquipment.value = '컨베이어';
    repopulateCases();
    triageCase.value = 'CONV-001';
    renderQuestions();
    document.getElementById('triage-symptom').value = '가상 사례: HMI에 모터 회전 기록이 있으나 컨베이어 이송 정지';
    document.getElementById('triage-model').value = '';
    document.getElementById('triage-alarm').value = '';
    const motor = triageChecks.querySelector('[data-key="motor_rotates_log"]');
    if (motor) motor.value = 'yes';
    demoMode = true;
    demoBanner.hidden = false;
    invalidateTriage('가상 시나리오가 입력되었습니다. 실제 설비 자료가 아니며 검토 버튼으로 결과를 확인할 수 있습니다.');
    scheduleSuggestions();
  });
  triageForm.addEventListener('submit', async e => {
    e.preventDefault();
    if (!triageOptions || !triageCase.value || triageHazard.value === 'yes') {
      if (triageHazard.value === 'yes') showEmergencyHold();
      return;
    }
    if (activeTriageController) activeTriageController.abort();
    const reviewedPayload = currentPayload();
    const reviewedDemo = demoMode;
    const version = ++triageRequestVersion;
    const controller = new AbortController();
    activeTriageController = controller;
    syncTriageButton();
    triageResult.replaceChildren(); add(triageResult, 'p', '로컬 진단 자료 확인 중...');
    triageFeedback.textContent = '검토 중...';
    try {
      const response = await fetch('/api/diagnostics/evaluate', {
        method: 'POST', headers: {'Content-Type':'application/json'}, cache:'no-store', signal: controller.signal,
        body: JSON.stringify(reviewedPayload),
      });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const result = await response.json();
      if (version !== triageRequestVersion || triageHazard.value === 'yes') return;
      renderTriageResult(result, reviewedDemo, reviewedPayload);
      triageFeedback.textContent = '로컬 규칙 검토 완료 · 저장되지 않음 · 외부 AI 전송 없음';
    } catch (err) {
      if (version !== triageRequestVersion || controller.signal.aborted) return;
      triageResult.replaceChildren();
      add(triageResult, 'p', '진단 요청에 실패했습니다. 서버 연결과 입력 내용을 확인한 후 다시 시도하세요. (' + err.message + ')');
      triageFeedback.textContent = '진단 결과 생성 실패';
    } finally {
      if (version === triageRequestVersion) {
        activeTriageController = null;
        syncTriageButton();
      }
    }
  });
  document.getElementById('triage-reset').addEventListener('click', () => {
    triageForm.reset();
    updateHazardStatus();
    demoMode = false;
    demoBanner.hidden = true;
    repopulateCases();
    invalidateTriage('입력이 초기화되었습니다. 기존 결과는 저장되지 않습니다.');
    scheduleSuggestions();
    if (!triageOptions) triageFeedback.textContent = '진단 자료를 불러오지 못했습니다. 페이지를 새로고침하세요.';
  });
  try {
    triageOptions = await request('/api/diagnostics/options');
    triageFeedback.textContent = '설비와 사례를 선택하세요.';
    repopulateCases();
    scheduleSuggestions();
  } catch (_e) {
    scheduleSuggestions();
    triageFeedback.textContent = '진단 자료를 불러오지 못했습니다. 로컬 서버를 확인한 뒤 페이지를 새로고침하세요.';
    triageResult.replaceChildren(); add(triageResult, 'p', '진단 기능 사용 불가: 사례 및 질문 데이터 로드 실패');
  }
  syncTriageButton();
  // Open collapsed sections when navigated to via sidebar or URL hash.
  function revealHashSection() {
    let fragment;
    try { fragment = decodeURIComponent(location.hash.slice(1)); }
    catch (_e) { return; } // Ignore malformed URL fragments without breaking the form.
    const target = document.getElementById(fragment);
    if (!target) return;
    if (target.tagName === 'DETAILS') target.open = true;
    const containing = target.closest('details');
    if (containing) containing.open = true;
  }
  document.querySelectorAll('a.nav-link[href^="#"]').forEach(link => {
    link.addEventListener('click', () => {
      const target = document.querySelector(link.getAttribute('href'));
      if (target?.tagName === 'DETAILS') target.open = true;
    });
  });
  window.addEventListener('hashchange', revealHashSection);
  revealHashSection();
  // Read-only availability check: no DeepSeek/ML requests or external data transfer.
  const integrationAgent = document.getElementById('integration-agent');
  const integrationMl = document.getElementById('integration-ml');
  const integrationTransfer = document.getElementById('integration-transfer');
  const integrationDetail = document.getElementById('integration-detail');
  // The optional capabilities request may be slow; never block core diagnostic
  // controls or registration of the AI/ML event listeners while checking it.
  void (async () => {
    try {
    const caps = await request('/api/integration/capabilities');
    const agentReady = caps.agent?.connected === true;
    const agentConfigured = caps.agent?.configured === true;
    const mlReady = caps.ml?.connected === true && caps.ml?.trained === true && caps.ml?.inference_enabled === true;
    integrationAgent.textContent = agentReady ? '연결 확인됨' : (agentConfigured ? '키 설정됨 · 실제 연결 미확인' : 'API 키 없음');
    integrationMl.textContent = mlReady ? '연결 상태 보고됨' : '미연결 · 예측 불가';
    integrationTransfer.textContent = agentConfigured ? '요청별 명시 동의 후 가능' : 'API 키 미설정 · 전송 없음';
    integrationDetail.textContent = '로컬 연결 계약 ' + String(caps.contract_version || '미확인') + ' · 외부 AI는 매 요청 동의 필요. 실제 호출·모델 검증 상태를 과장하지 않습니다.';
    document.getElementById('agent-status').textContent = agentReady ? '연결됨' : (agentConfigured ? '설정됨' : '미연결');
    } catch (_e) {
    integrationAgent.textContent = '상태 확인 실패';
    integrationMl.textContent = '상태 확인 실패';
    integrationTransfer.textContent = '확인 불가';
    document.getElementById('agent-status').textContent = '상태 확인 실패';
    integrationDetail.textContent = '연동 상태 API 응답이 없습니다. AI·ML은 검증되지 않았으며 로컬 규칙 기반 검토만 이용하세요.';
  }
  })();
  // Optional AI evidence review: each request requires explicit consent and preview.
  // Demo input, safety hold, or incomplete selection never initiates an AI request.
  agentConsent = document.getElementById('agent-consent');
  const agentPreviewButton = document.getElementById('agent-preview');
  agentPreviewContent = document.getElementById('agent-preview-content');
  agentRun = document.getElementById('agent-run');
  const agentFeedback = document.getElementById('agent-feedback');
  agentResult = document.getElementById('agent-result');
  function syncAgentButton() {
    if (!agentRun || !agentConsent) return;
    agentPreviewButton.disabled = triageHazard.value === 'yes';
    agentRun.disabled = !triageCase.value || !triageOptions || demoMode || triageHazard.value === 'yes' ||
      !agentConsent.checked || lastPreviewVersion !== agentPreviewVersion || !!agentRequestController;
  }
  function invalidateAgentReview() {
    if (!agentConsent || !agentRun) return;
    ++agentPreviewVersion;
    lastPreviewVersion = -1;
    if (agentRequestController) { agentRequestController.abort(); agentRequestController = null; }
    agentPreviewContent.hidden = true;
    agentPreviewContent.textContent = '';
    agentResult.replaceChildren();
    agentConsent.checked = false;
    syncAgentButton();
  }
  agentConsent.addEventListener('change', syncAgentButton);
  agentPreviewButton.addEventListener('click', async () => {
    if (!triageOptions || !triageCase.value || triageHazard.value === 'yes' || demoMode) {
      agentFeedback.textContent = '실제 사례를 직접 선택하고 위험 상태를 확인해야 합니다. 가상 입력은 전송할 수 없습니다.';
      return;
    }
    const version = ++agentPreviewVersion;
    lastPreviewVersion = -1;
    agentConsent.checked = false;
    agentPreviewContent.hidden = true;
    agentPreviewContent.textContent = '';
    agentResult.replaceChildren();
    agentFeedback.textContent = '전송 예정 자료를 다시 확인하는 중...';
    syncAgentButton();
    const before = currentPayload();
    try {
      const response = await fetch('/api/integration/evidence-preview', {
        method: 'POST', headers: {'Content-Type':'application/json'}, cache:'no-store',
        body:JSON.stringify({triage:before}),
      });
      if (!response.ok) throw new Error('preview_unavailable');
      const data = await response.json();
      if (version !== agentPreviewVersion || triageHazard.value === 'yes' || demoMode) return;
      if (data.state !== 'candidate_review' || data.allowed_for_agent_reasoning !== true) throw new Error('preview_blocked');
      agentPreviewContent.textContent = JSON.stringify(data.context, null, 2);
      agentPreviewContent.hidden = false;
      lastPreviewVersion = agentPreviewVersion;
      agentFeedback.textContent = '공개 사례·근거·선택한 관찰값만 표시했습니다. 내용을 확인하고 요청별 동의 후 실행하세요.';
      syncAgentButton();
    } catch (_e) {
      if (version !== agentPreviewVersion) return;
      agentFeedback.textContent = '전송 예정 자료를 생성하지 못했습니다. AI 사용은 차단됩니다.';
      lastPreviewVersion = -1; syncAgentButton();
    }
  });
  agentRun.addEventListener('click', async () => {
    if (agentRun.disabled || !agentConsent.checked || demoMode || triageHazard.value === 'yes') return;
    const version = agentPreviewVersion;
    agentRequestController = new AbortController();
    const controller = agentRequestController;
    syncAgentButton();
    agentResult.replaceChildren();
    agentFeedback.textContent = 'AI 근거 검토 중...';
    try {
      const response = await fetch('/api/agent/review', {method:'POST',
        headers:{'Content-Type':'application/json'},cache:'no-store',signal:controller.signal,
        body:JSON.stringify({triage:currentPayload(),consent:true})});
      if (!response.ok) throw new Error('agent_unavailable');
      const result = await response.json();
      if (version !== agentPreviewVersion || triageHazard.value === 'yes' || controller.signal.aborted) return;
      agentResult.replaceChildren();
      add(agentResult,'p',result.message || 'AI 응답을 확인할 수 없습니다.','small-note');
      if (result.status === 'reviewed' && result.agent_review) {
        add(agentResult,'h4','AI 참고 검토 순서 · 원인 미확정');
        for (const c of result.agent_review.candidate_causes) {
          add(agentResult,'p',c.candidate + ' — ' + c.why_to_consider,'result-note');
        }
        add(agentResult,'h4','사용된 참고 자료·적용 한계');
        for (const src of result.agent_review.sources) {
          addSafeSourceLink(agentResult, src, src.organization + ' — ' + src.title);
          add(agentResult,'p',src.limit,'small-note');
        }
        if (result.agent_review.questions.length) {
          add(agentResult,'h4','추가 확인 질문');
          addList(agentResult,result.agent_review.questions);
        }
      }
      agentFeedback.textContent = result.external_transfer_performed ? '외부 AI 검토 응답 수신 · 고장 확정 아님' :
        '외부 AI 결과 없음 · 기존 로컬 진단 사용';
    } catch (_e) {
      if (version === agentPreviewVersion && !controller.signal.aborted) agentFeedback.textContent = 'AI 연결 실패 · 기존 로컬 진단 유지';
    } finally {
      if (version === agentPreviewVersion) {
        agentRequestController = null;
        agentConsent.checked = false;
        lastPreviewVersion = -1; syncAgentButton();
      }
    }
  });
  const mlInput = document.getElementById('ml-upload');
  const mlRun = document.getElementById('ml-run');
  const mlFeedback = document.getElementById('ml-feedback');
  const mlResult = document.getElementById('ml-result');
  let mlRequestVersion = 0;
  let activeMlController = null;
  function invalidateMl(message) {
    ++mlRequestVersion;
    if (activeMlController) { activeMlController.abort(); activeMlController = null; }
    mlResult.replaceChildren();
    mlFeedback.textContent = message;
    mlRun.disabled = triageHazard.value === 'yes';
    mlInput.disabled = triageHazard.value === 'yes';
  }
  mlInput.addEventListener('change', () => invalidateMl('파일이 변경되었습니다. 새 파일을 검토하세요.'));
  triageHazard.addEventListener('change', () => {
    invalidateMl(triageHazard.value === 'yes' ? '긴급 위험: 분석을 중단했습니다.' : '필요한 경우 CSV를 선택해 분석하세요.');
  });
  mlRun.disabled = triageHazard.value === 'yes';
  mlInput.disabled = triageHazard.value === 'yes';
  mlRun.addEventListener('click', async () => {
    if (triageHazard.value === 'yes') { invalidateMl('긴급 위험: 분석을 중단했습니다.'); return; }
    const file = mlInput.files && mlInput.files[0];
    if (!file || file.size > 256000) {
      invalidateMl('256KB 이하의 특성 CSV 파일을 선택하세요.'); return;
    }
    const version = ++mlRequestVersion;
    const controller = new AbortController();
    activeMlController = controller;
    mlResult.replaceChildren();
    mlRun.disabled = true;
    mlFeedback.textContent = '로컬 CSV 검토 중...';
    try {
      const response = await fetch('/api/ml/inspect',{method:'POST',headers:{'Content-Type':'text/csv'},
        body:file,cache:'no-store',signal:controller.signal});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const result = await response.json();
      if (version !== mlRequestVersion || triageHazard.value === 'yes') return;
      mlFeedback.textContent = result.message || result.warning || '처리 완료';
      if (result.inference_performed && Array.isArray(result.rows)) {
        add(mlResult,'p','실험실 모델의 비교 출력이며 현장 고장 확률·작업 허가가 아닙니다.','result-hold');
        for (const r of result.rows) add(mlResult,'p',r.asset_id + ' / ' + r.trial_id + ' — ' + r.predicted_experimental_label + ' (모델 점수 ' + r.model_score + ')','result-note');
      }
    } catch (_e) {
      if (version === mlRequestVersion && !controller.signal.aborted)
        mlFeedback.textContent = '로컬 ML 처리를 완료하지 못했습니다.';
    } finally {
      if (version === mlRequestVersion) {
        activeMlController = null;
        mlRun.disabled = triageHazard.value === 'yes';
      }
    }
  });
})();
