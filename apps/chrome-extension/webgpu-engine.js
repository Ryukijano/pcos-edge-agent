/**
 * WebGPU Engine — runs Gemma 4 E2B/E4B directly in the browser via LiteRT-LM JS API.
 *
 * Uses @litert-lm/core with WebGPU acceleration.
 * Models are fetched from HuggingFace litert-community repos.
 */

const E2B_WEB_URL = 'https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it-web.litertlm';
const E4B_WEB_URL = 'https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm/resolve/main/gemma-4-E4B-it-web.litertlm';

let engine = null;
let conversation = null;
let currentModelUrl = null;
let isInitializing = false;

/**
 * Check if WebGPU is available in this browser.
 */
async function isWebGPUAvailable() {
  if (!('gpu' in navigator)) return false;
  try {
    const adapter = await navigator.gpu.requestAdapter();
    return adapter !== null;
  } catch (e) {
    return false;
  }
}

/**
 * Initialize the LiteRT-LM WebGPU engine with a model.
 * @param {string} modelUrl - URL to the .litertlm web model file
 * @param {function} onStatus - callback for status updates
 */
async function initEngine(modelUrl, onStatus) {
  if (engine && currentModelUrl === modelUrl) return true;
  if (isInitializing) return false;
  isInitializing = true;

  try {
    // Clean up previous engine
    if (conversation) { await conversation.delete(); conversation = null; }
    if (engine) { await engine.delete(); engine = null; }

    onStatus?.('Loading model via WebGPU…');
    const { Engine } = await import('https://cdn.jsdelivr.net/npm/@litert-lm/core/+esm');

    engine = await Engine.create({
      model: modelUrl,
      mainExecutorSettings: {
        maxNumTokens: 8192,
      },
    });

    conversation = await engine.createConversation({
      preface: {
        messages: [
          { role: 'system', content: 'You are a helpful on-device assistant running in the browser via WebGPU.' }
        ]
      }
    });

    currentModelUrl = modelUrl;
    onStatus?.('WebGPU engine ready');
    isInitializing = false;
    return true;
  } catch (e) {
    console.error('[PCOS WebGPU] Engine init failed:', e);
    onStatus?.(`WebGPU init failed: ${e.message}`);
    isInitializing = false;
    return false;
  }
}

/**
 * Run streaming inference via WebGPU.
 * @param {string} prompt - user input
 * @param {function} onChunk - callback for each text chunk
 * @param {function} onStatus - callback for status updates
 */
async function inferWebGPU(prompt, onChunk, onStatus) {
  if (!conversation) {
    onStatus?.('WebGPU engine not initialized');
    return '[WebGPU engine not loaded]';
  }

  try {
    const stream = conversation.sendMessageStreaming(prompt);
    let result = '';
    for await (const chunk of stream) {
      for (const item of chunk.content) {
        if (item.type === 'text') {
          result += item.text;
          onChunk?.(item.text);
        }
      }
    }
    return result;
  } catch (e) {
    console.error('[PCOS WebGPU] Inference failed:', e);
    return `[WebGPU error: ${e.message}]`;
  }
}

/**
 * Cancel ongoing generation.
 */
async function cancelWebGPU() {
  if (conversation) {
    try { await conversation.cancel(); } catch (e) {}
  }
}

/**
 * Clean up engine resources.
 */
async function cleanupWebGPU() {
  if (conversation) { try { await conversation.delete(); } catch (e) {} conversation = null; }
  if (engine) { try { await engine.delete(); } catch (e) {} engine = null; }
  currentModelUrl = null;
}

// Export for use in sidepanel.js
export {
  isWebGPUAvailable,
  initEngine,
  inferWebGPU,
  cancelWebGPU,
  cleanupWebGPU,
  E2B_WEB_URL,
  E4B_WEB_URL,
};
