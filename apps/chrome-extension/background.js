// PCOS Chrome Extension — Background Service Worker
// Manages side panel, context menus, WebSocket bridge, and message routing

const BROKER_URL = 'http://localhost:8000';
const BRIDGE_WS = 'ws://localhost:8000/bridge';
const KEEPALIVE_INTERVAL_MS = 20000;
const RECONNECT_BASE_MS = 3000;
const RECONNECT_MAX_MS = 30000;

let bridgeSocket = null;
let bridgeClientId = null;
let brokerAvailable = false;
let keepaliveTimer = null;
let reconnectAttempts = 0;
let offscreenCreated = false;

// ── Side panel setup ───────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

  // Context menu entries for selection-based interactions
  chrome.contextMenus.create({
    id: 'pcos-summarize',
    title: 'PCOS: Summarize selection',
    contexts: ['selection'],
  });
  chrome.contextMenus.create({
    id: 'pcos-rewrite',
    title: 'PCOS: Rewrite selection',
    contexts: ['selection'],
  });
  chrome.contextMenus.create({
    id: 'pcos-act',
    title: 'PCOS: Act on selection (Android)',
    contexts: ['selection'],
  });
  chrome.contextMenus.create({
    id: 'pcos-remember',
    title: 'PCOS: Remember this',
    contexts: ['selection'],
  });

  // Check broker availability
  checkBroker();
});

// ── Context menu handler ───────────────────────────────────────

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const selection = info.selectionText || '';
  const pageContext = await capturePageContext(tab);

  const taskMap = {
    'pcos-summarize': { text: `summarize: ${selection}`, task_type: 'transform', is_webpage_grounded: true, is_short: true },
    'pcos-rewrite': { text: `rewrite: ${selection}`, task_type: 'transform', is_webpage_grounded: true, is_short: true },
    'pcos-act': { text: selection, task_type: 'action', requires_action: true, is_webpage_grounded: true },
    'pcos-remember': { text: `remember this: ${selection}`, task_type: 'action', requires_action: true, sensitivity: 'private' },
  };

  const task = taskMap[info.menuItemId];
  if (!task) return;

  // Route via broker
  const result = await routeViaBroker(task, pageContext);
  // Send to side panel
  chrome.runtime.sendMessage({ type: 'pcos-result', result, task });
});

// ── Page context capture ───────────────────────────────────────

async function capturePageContext(tab) {
  if (!tab) return {};
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => ({
        url: window.location.href,
        page_title: document.title,
        selection: window.getSelection().toString(),
        dom_summary: document.body?.innerText?.slice(0, 500) || '',
      }),
    });
    return results[0]?.result || {};
  } catch (e) {
    return { url: tab.url, page_title: tab.title };
  }
}

// ── Broker communication ───────────────────────────────────────

async function checkBroker() {
  try {
    const resp = await fetch(`${BROKER_URL}/health`);
    brokerAvailable = resp.ok;
  } catch (e) {
    brokerAvailable = false;
  }
  return brokerAvailable;
}

async function routeViaBroker(task, browserContext = {}) {
  const body = {
    task,
    context: { browser: browserContext },
  };

  try {
    const resp = await fetch(`${BROKER_URL}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`Broker returned ${resp.status}`);
    return await resp.json();
  } catch (e) {
    // Fallback: try Chrome Built-in AI directly
    return { error: e.message, fallback: true };
  }
}

// ── WebSocket bridge ───────────────────────────────────────────

// ── Offscreen document for MV3 keepalive ─────────────────────

async function ensureOffscreenDocument() {
  if (offscreenCreated) return;
  if (await chrome.offscreen?.hasDocument?.()) {
    offscreenCreated = true;
    return;
  }
  try {
    await chrome.offscreen.createDocument({
      url: 'offscreen.html',
      reasons: ['WEB_SOCKET'],
      justification: 'Maintain WebSocket bridge connection to PCOS broker',
    });
    offscreenCreated = true;
  } catch (e) {
    console.warn('Offscreen document creation failed:', e);
  }
}

function startKeepalive() {
  if (keepaliveTimer) clearInterval(keepaliveTimer);
  keepaliveTimer = setInterval(() => {
    if (bridgeSocket && bridgeSocket.readyState === WebSocket.OPEN) {
      bridgeSocket.send(JSON.stringify({ type: 'ping' }));
    }
  }, KEEPALIVE_INTERVAL_MS);
}

function connectBridge() {
  if (bridgeSocket && bridgeSocket.readyState === WebSocket.OPEN) return;

  bridgeSocket = new WebSocket(BRIDGE_WS);

  bridgeSocket.onopen = () => {
    reconnectAttempts = 0;
    bridgeSocket.send(JSON.stringify({ type: 'register', role: 'chrome' }));
    startKeepalive();
    ensureOffscreenDocument();
  };

  bridgeSocket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'registered') {
      bridgeClientId = msg.client_id;
      chrome.storage.session?.set?.({ bridgeClientId });
    } else if (msg.type === 'pong') {
      // Keepalive response — connection is alive
    } else if (msg.type === 'relay' || msg.type === 'result') {
      // Forward to side panel
      chrome.runtime.sendMessage({ type: 'pcos-bridge-message', message: msg });
    }
  };

  bridgeSocket.onclose = () => {
    bridgeSocket = null;
    bridgeClientId = null;
    if (keepaliveTimer) {
      clearInterval(keepaliveTimer);
      keepaliveTimer = null;
    }
    // Exponential backoff reconnect
    const delay = Math.min(RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts), RECONNECT_MAX_MS);
    reconnectAttempts++;
    setTimeout(connectBridge, delay);
  };

  bridgeSocket.onerror = (error) => {
    console.error('Bridge WebSocket error:', error);
    bridgeSocket?.close();
  };
}

// ── Message router from side panel ─────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'pcos-execute') {
    routeViaBroker(msg.task, msg.context).then(result => {
      sendResponse(result);
    });
    return true; // async response
  }

  if (msg.type === 'pcos-bridge-send') {
    if (bridgeSocket && bridgeSocket.readyState === WebSocket.OPEN) {
      bridgeSocket.send(JSON.stringify(msg.message));
    }
    return false;
  }

  if (msg.type === 'pcos-check-broker') {
    checkBroker().then(available => sendResponse({ available }));
    return true;
  }

  if (msg.type === 'pcos-get-context') {
    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      const ctx = await capturePageContext(tabs[0]);
      sendResponse(ctx);
    });
    return true;
  }
});

// Connect bridge on startup
connectBridge();

// Reconnect when service worker wakes up
chrome.runtime.onStartup?.addListener?.(() => {
  connectBridge();
});
