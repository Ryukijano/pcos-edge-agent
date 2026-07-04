// PCOS Side Panel — main interaction logic

const BROKER_URL = 'http://localhost:8000';

// ── DOM refs ───────────────────────────────────────────────────

const taskInput = document.getElementById('task-input');
const taskTypeSelect = document.getElementById('task-type');
const privateMode = document.getElementById('private-mode');
const executeBtn = document.getElementById('execute-btn');
const output = document.getElementById('output');
const routingBadge = document.getElementById('routing-badge');
const badgeSurface = document.getElementById('badge-surface');
const badgeModel = document.getElementById('badge-model');
const badgeLatency = document.getElementById('badge-latency');
const brokerStatus = document.getElementById('broker-status');
const brokerLabel = document.getElementById('broker-label');
const apiStrip = document.getElementById('api-strip');
const suggestionChip = document.getElementById('suggestion-chip');
const suggestionText = document.getElementById('suggestion-text');

// ── Init ───────────────────────────────────────────────────────

async function init() {
  await checkBrokerStatus();
  await checkChromeAIAvailability();
  setupListeners();
}

// ── Broker status ──────────────────────────────────────────────

async function checkBrokerStatus() {
  try {
    chrome.runtime.sendMessage({ type: 'pcos-check-broker' }, (resp) => {
      if (resp?.available) {
        brokerStatus.className = 'status-dot status-ok';
        brokerLabel.textContent = 'Broker connected';
      } else {
        brokerStatus.className = 'status-dot status-error';
        brokerLabel.textContent = 'Broker offline (Chrome AI only)';
      }
    });
  } catch (e) {
    brokerStatus.className = 'status-dot status-error';
    brokerLabel.textContent = 'Broker offline';
  }
}

// ── Chrome AI availability ─────────────────────────────────────

async function checkChromeAIAvailability() {
  const apis = [
    { name: 'prompt', check: () => window.ai?.languageModel },
    { name: 'summarizer', check: () => window.ai?.summarizer },
    { name: 'rewriter', check: () => window.ai?.rewriter },
    { name: 'proofreader', check: () => window.ai?.proofreader },
    { name: 'translator', check: () => window.ai?.translator },
    { name: 'language_detector', check: () => window.ai?.languageDetector },
    { name: 'writer', check: () => window.ai?.writer },
  ];

  for (const api of apis) {
    const badge = apiStrip.querySelector(`[data-api="${api.name}"]`);
    if (badge) {
      const available = await api.check();
      if (available) {
        badge.classList.add('available');
      }
    }
  }
}

// ── Execute task ───────────────────────────────────────────────

async function executeTask() {
  const text = taskInput.value.trim();
  if (!text) return;

  executeBtn.disabled = true;
  output.innerHTML = '<p class="placeholder">Routing…</p>';
  routingBadge.style.display = 'none';

  const task = {
    text,
    task_type: taskTypeSelect.value,
    sensitivity: privateMode.checked ? 'private' : 'normal',
    is_short: text.length < 2000,
    is_webpage_grounded: true, // we're in the browser
  };

  // Get page context
  chrome.runtime.sendMessage({ type: 'pcos-get-context' }, async (pageCtx) => {
    const context = { browser: pageCtx || {} };

    // Try broker first
    chrome.runtime.sendMessage(
      { type: 'pcos-execute', task, context },
      async (result) => {
        if (result && !result.error) {
          displayResult(result, task);
        } else {
          // Fallback to Chrome Built-in AI
          await fallbackToChromeAI(task);
        }
        executeBtn.disabled = false;
      }
    );
  });
}

// ── Display result with routing badge ──────────────────────────

function displayResult(result, task) {
  const decision = result.decision || {};
  const plan = result.plan || {};

  // Show routing badge
  routingBadge.style.display = 'flex';
  badgeSurface.textContent = decision.surface || 'unknown';
  badgeModel.textContent = decision.chrome_api || '';
  badgeLatency.textContent = `${decision.latency_target_ms || 0}ms target`;

  // Execute via Chrome AI if routed there
  if (decision.surface === 'chrome_builtin_ai' && decision.chrome_api) {
    executeViaChromeAI(decision.chrome_api, plan, task);
  } else if (decision.surface === 'android_litert_functiongemma' || decision.surface === 'android_litert_gemma_full') {
    output.innerHTML = `<p class="placeholder">Routed to Android (${decision.reason}). Use the bridge to relay.</p>`;
  } else if (decision.surface === 'cloud_llm_escalation') {
    output.innerHTML = `<p class="placeholder">Cloud escalation: ${decision.reason}</p>`;
  } else if (decision.surface === 'piecesos_memory_then_local') {
    output.innerHTML = `<p class="placeholder">Querying PiecesOS memory…</p>`;
  } else {
    output.textContent = JSON.stringify(result, null, 2);
  }
}

// ── Chrome Built-in AI execution ───────────────────────────────

async function executeViaChromeAI(apiName, plan, task) {
  try {
    const result = await ChromeAI.dispatch(
      apiName,
      plan.user_prompt || task.text,
      {
        systemPrompt: plan.system_prompt || '',
        preference: 'auto',
        tone: 'as-is',
        context: plan.context_prefix || '',
      }
    );
    output.textContent = result;
  } catch (e) {
    output.innerHTML = `<p class="placeholder" style="color:var(--error)">Chrome AI error: ${e.message}</p>`;
  }
}

// ── Fallback (no broker) ───────────────────────────────────────

async function fallbackToChromeAI(task) {
  const api = task.task_type === 'transform' ? guessChromeAPI(task.text) : 'prompt';
  routingBadge.style.display = 'flex';
  badgeSurface.textContent = 'chrome_builtin_ai (fallback)';
  badgeModel.textContent = api;
  badgeLatency.textContent = 'local';

  try {
    const result = await ChromeAI.dispatch(api, task.text, { systemPrompt: '' });
    output.textContent = result;
  } catch (e) {
    output.innerHTML = `<p class="placeholder" style="color:var(--error)">No Chrome AI available: ${e.message}</p>`;
  }
}

function guessChromeAPI(text) {
  const t = text.toLowerCase();
  if (t.includes('summarize') || t.includes('summary') || t.includes('tldr')) return 'summarizer';
  if (t.includes('rewrite') || t.includes('rephrase')) return 'rewriter';
  if (t.includes('proofread') || t.includes('grammar')) return 'proofreader';
  if (t.includes('translate') || t.includes('translation')) return 'translator';
  if (t.includes('detect language') || t.includes('what language')) return 'language_detector';
  if (t.includes('write') || t.includes('draft')) return 'writer';
  return 'prompt';
}

// ── Listeners ──────────────────────────────────────────────────

function setupListeners() {
  executeBtn.addEventListener('click', executeTask);

  taskInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      executeTask();
    }
  });

  // Receive results from context menu
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === 'pcos-result') {
      displayResult(msg.result, msg.task);
      taskInput.value = msg.task.text;
    }
    if (msg.type === 'pcos-bridge-message') {
      const m = msg.message;
      if (m.type === 'result') {
        output.textContent = m.payload?.result || JSON.stringify(m.payload, null, 2);
      }
    }
  });

  // Suggestion chip
  document.getElementById('suggestion-accept')?.addEventListener('click', () => {
    taskInput.value = suggestionText.textContent;
    suggestionChip.style.display = 'none';
    executeTask();
  });
  document.getElementById('suggestion-dismiss')?.addEventListener('click', () => {
    suggestionChip.style.display = 'none';
  });
}

// ── Start ──────────────────────────────────────────────────────

init();
