// PCOS Side Panel — main interaction logic

const BROKER_URL = 'http://localhost:8000';

// ── DOM refs ───────────────────────────────────────────────────

const taskInput = document.getElementById('task-input');
const taskTypeSelect = document.getElementById('task-type');
const privateMode = document.getElementById('private-mode');
const executeBtn = document.getElementById('execute-btn');
const stopBtn = document.getElementById('stop-btn');
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
    { name: 'prompt', ctor: 'LanguageModel' },
    { name: 'summarizer', ctor: 'Summarizer' },
    { name: 'rewriter', ctor: 'Rewriter' },
    { name: 'proofreader', ctor: 'Proofreader' },
    { name: 'translator', ctor: 'Translator' },
    { name: 'language_detector', ctor: 'LanguageDetector' },
    { name: 'writer', ctor: 'Writer' },
  ];

  for (const api of apis) {
    const badge = apiStrip.querySelector(`[data-api="${api.name}"]`);
    if (!badge) continue;
    const status = await ChromeAI.checkAvailability(api.ctor);
    if (status === 'available') {
      badge.classList.add('available');
    } else if (status === 'downloadable' || status === 'downloading') {
      badge.classList.add('downloadable');
    }
  }
}

// ── Execute task ───────────────────────────────────────────────

async function executeTask() {
  const text = taskInput.value.trim();
  if (!text) return;

  executeBtn.disabled = true;
  stopBtn.style.display = 'inline-block';
  output.textContent = 'Routing…';
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
        stopBtn.style.display = 'none';
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
  } else if (decision.surface === 'chrome_webgpu') {
    executeViaWebGPU(task, decision, plan);
  } else if (decision.surface.startsWith('android_litert')) {
    relayToAndroid(task, decision, result);
  } else if (decision.surface === 'cloud_llm_escalation') {
    output.textContent = `Cloud escalation: ${decision.reason}`;
  } else if (decision.surface === 'piecesos_memory_then_local') {
    output.textContent = 'Querying PiecesOS memory…';
  } else {
    output.textContent = JSON.stringify(result, null, 2);
  }
}

// ── Chrome Built-in AI execution ───────────────────────────────

// ── WebGPU execution (LiteRT-LM JS API) ─────────────────────────

async function executeViaWebGPU(task, decision, plan) {
  output.textContent = '';
  const statusEl = document.createElement('p');
  statusEl.className = 'placeholder';
  statusEl.textContent = `Initializing WebGPU (${decision.reason})…`;
  output.appendChild(statusEl);

  try {
    const { isWebGPUAvailable, initEngine, inferWebGPU, E2B_WEB_URL, E4B_WEB_URL } =
      await import('./webgpu-engine.js');

    const webgpuOk = await isWebGPUAvailable();
    if (!webgpuOk) {
      statusEl.textContent = 'WebGPU not available. Falling back to Chrome Built-in AI.';
      // Fallback to Chrome LanguageModel API
      if (window.LanguageModel) {
        executeViaChromeAI('prompt', plan, task);
      } else {
        output.textContent = 'WebGPU not available and Chrome AI not supported.';
      }
      return;
    }

    // Pick model: E2B for transforms, E4B for reasoning
    const modelUrl = task.task_type === 'reasoning' ? E4B_WEB_URL : E2B_WEB_URL;
    const modelName = modelUrl === E4B_WEB_URL ? 'Gemma 4 E4B' : 'Gemma 4 E2B';

    statusEl.textContent = `Loading ${modelName} via WebGPU…`;
    const initialized = await initEngine(modelUrl, (msg) => {
      statusEl.textContent = msg;
    });
    if (!initialized) {
      statusEl.textContent = 'WebGPU engine init failed. Try Chrome Built-in AI instead.';
      return;
    }

    // Build prompt with context prefix
    const prefix = plan?.context_prefix || plan?.system_prompt || '';
    const fullPrompt = prefix ? `${prefix}\n\n${task.text}` : task.text;

    output.textContent = '';
    const resultEl = document.createElement('div');
    resultEl.className = 'output-text';
    output.appendChild(resultEl);

    statusEl.textContent = `${modelName} generating…`;
    const result = await inferWebGPU(fullPrompt, (chunk) => {
      resultEl.textContent += chunk;
    }, (msg) => {
      statusEl.textContent = msg;
    });

    if (statusEl.textContent.includes('generating')) {
      statusEl.textContent = `${modelName} complete via WebGPU`;
    }
  } catch (e) {
    statusEl.textContent = `WebGPU error: ${e.message}`;
    console.error('[PCOS WebGPU]', e);
  }
}

// ── Relay to Android via bridge ────────────────────────────────

async function relayToAndroid(task, decision, brokerResult) {
  output.textContent = '';
  const statusEl = document.createElement('p');
  statusEl.className = 'placeholder';
  statusEl.textContent = `Relaying to Android (${decision.reason})…`;
  output.appendChild(statusEl);

  const plan = brokerResult.plan || {};
  const relayPayload = {
    type: 'pcos-execute',
    task: task,
    plan: plan,
    decision: { surface: decision.surface, reason: decision.reason },
  };

  // Send via bridge WebSocket
  chrome.runtime.sendMessage(
    { type: 'pcos-bridge-send', message: { type: 'relay', payload: relayPayload } },
    (resp) => {
      if (chrome.runtime.lastError) {
        statusEl.textContent = 'Bridge not connected. Waiting for Android…';
      } else {
        statusEl.textContent = 'Task relayed to Android. Waiting for result…';
      }
    }
  );

  // Result will arrive via 'pcos-bridge-message' listener (setupListeners)
  // Timeout after 30s
  setTimeout(() => {
    if (statusEl.parentNode && statusEl.textContent.includes('Waiting')) {
      statusEl.textContent = 'Android did not respond within 30s. Is the app running?';
    }
  }, 30000);
}

// ── Chrome Built-in AI execution (continued) ───────────────────

async function executeViaChromeAI(apiName, plan, task) {
  output.textContent = '';
  const progressEl = document.createElement('p');
  progressEl.className = 'placeholder';
  progressEl.textContent = 'Loading model…';
  output.appendChild(progressEl);

  try {
    const result = await ChromeAI.dispatchStream(
      apiName,
      plan.user_prompt || task.text,
      {
        systemPrompt: plan.system_prompt || '',
        preference: 'auto',
        tone: 'as-is',
        context: plan.context_prefix || '',
        onProgress: (pct) => {
          if (pct < 100) progressEl.textContent = `Downloading model: ${pct}%`;
          else progressEl.remove();
        },
      },
      (chunk) => {
        if (progressEl.parentNode) progressEl.remove();
        output.textContent += chunk;
      }
    );
    if (progressEl.parentNode) progressEl.remove();
    output.textContent = result;
  } catch (e) {
    progressEl.remove();
    output.textContent = `Chrome AI error: ${e.message}`;
  }
}

// ── Fallback (no broker) ───────────────────────────────────────

async function fallbackToChromeAI(task) {
  const api = task.task_type === 'transform' ? guessChromeAPI(task.text) : 'prompt';
  routingBadge.style.display = 'flex';
  badgeSurface.textContent = 'chrome_builtin_ai (fallback)';
  badgeModel.textContent = api;
  badgeLatency.textContent = 'local';

  output.textContent = '';
  try {
    const result = await ChromeAI.dispatchStream(
      api, task.text, { systemPrompt: '' },
      (chunk) => { output.textContent += chunk; }
    );
    output.textContent = result;
  } catch (e) {
    output.textContent = `No Chrome AI available: ${e.message}`;
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

  stopBtn.addEventListener('click', () => {
    ChromeAI.abort();
    stopBtn.style.display = 'none';
    executeBtn.disabled = false;
  });

  taskInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      executeTask();
    }
  });

  // Receive results from context menu and bridge
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === 'pcos-result') {
      displayResult(msg.result, msg.task);
      taskInput.value = msg.task.text;
    }
    if (msg.type === 'pcos-bridge-message') {
      const m = msg.message;
      if (m.type === 'result') {
        // Final result from Android
        const resultText = m.payload?.result || JSON.stringify(m.payload, null, 2);
        output.textContent = resultText;
        executeBtn.disabled = false;
        stopBtn.style.display = 'none';
      } else if (m.type === 'relay') {
        // Streaming chunk or intermediate status from Android
        const payload = m.payload || {};
        if (payload.type === 'streaming-chunk' && payload.chunk) {
          output.textContent += payload.chunk;
        } else if (payload.type === 'status') {
          output.textContent = payload.message || 'Processing on Android…';
        }
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
