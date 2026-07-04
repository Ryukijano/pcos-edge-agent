/**
 * PCOS Chrome Built-in AI wrapper.
 * Selects the correct Chrome API based on task type.
 * Requires Chrome 138+ with Built-in AI flags enabled.
 *
 * Verified APIs (Jul 2026):
 * - LanguageModel (Prompt API) — Gemma 4 backend, speculative decoding
 * - Summarizer API — speed/capability preference
 * - Writer / Rewriter / Proofreader APIs
 * - Translator API — translate text between languages
 * - Language Detector API — detect the language of input text
 */

const ChromeAI = {
  // ── Availability checks ──────────────────────────────────────

  async checkAvailability(api = 'languageModel') {
    try {
      if (!window.ai?.[api]) return 'unavailable';
      const availability = await window.ai[api].availability();
      return availability; // 'available' | 'downloadable' | 'downloading' | 'unavailable'
    } catch (e) {
      return 'unavailable';
    }
  },

  async ensureAvailable(api = 'languageModel') {
    const status = await this.checkAvailability(api);
    if (status === 'available') return true;
    if (status === 'downloadable' || status === 'downloading') {
      // Trigger download
      if (window.ai[api]?.create) return true;
    }
    return false;
  },

  // ── Summarizer ───────────────────────────────────────────────

  async summarize(text, preference = 'auto') {
    const summarizer = await window.ai.summarizer.create({
      type: 'key-points',
      format: 'plain-text',
      length: 'short',
      preference,
    });
    const result = await summarizer.summarize(text);
    summarizer.destroy();
    return result;
  },

  async summarizeStream(text, preference = 'auto', onChunk) {
    const summarizer = await window.ai.summarizer.create({
      type: 'key-points',
      format: 'plain-text',
      length: 'short',
      preference,
    });
    let result = '';
    const stream = await summarizer.summarizeStreaming(text);
    for await (const chunk of stream) {
      result += chunk;
      if (onChunk) onChunk(chunk);
    }
    summarizer.destroy();
    return result;
  },

  // ── Translator ───────────────────────────────────────────────

  async translate(text, targetLanguage = 'en', sourceLanguage = 'auto') {
    const translator = await window.ai.translator.create({
      sourceLanguage,
      targetLanguage,
    });
    const result = await translator.translate(text);
    translator.destroy();
    return result;
  },

  // ── Language Detector ────────────────────────────────────────

  async detectLanguage(text) {
    const detector = await window.ai.languageDetector.create();
    const results = await detector.detect(text);
    detector.destroy();
    return results;
  },

  // ── Rewriter ─────────────────────────────────────────────────

  async rewrite(text, tone = 'as-is') {
    const rewriter = await window.ai.rewriter.create({ tone });
    const result = await rewriter.rewrite(text);
    rewriter.destroy();
    return result;
  },

  // ── Proofreader ──────────────────────────────────────────────

  async proofread(text) {
    const proofreader = await window.ai.proofreader.create();
    const result = await proofreader.proofread(text);
    proofreader.destroy();
    return result;
  },

  // ── Prompt API (general) ─────────────────────────────────────

  async prompt(text, systemPrompt = '') {
    const session = await window.ai.languageModel.create({ systemPrompt });
    const result = await session.prompt(text);
    session.destroy();
    return result;
  },

  async promptStream(text, systemPrompt = '', onChunk) {
    const session = await window.ai.languageModel.create({ systemPrompt });
    let result = '';
    const stream = await session.promptStreaming(text);
    for await (const chunk of stream) {
      result += chunk;
      if (onChunk) onChunk(chunk);
    }
    session.destroy();
    return result;
  },

  // ── Writer ───────────────────────────────────────────────────

  async write(prompt, context = '') {
    const writer = await window.ai.writer.create({ sharedContext: context });
    const result = await writer.write(prompt);
    writer.destroy();
    return result;
  },

  // ── Dispatch ─────────────────────────────────────────────────

  async dispatch(taskType, text, options = {}) {
    switch (taskType) {
      case 'summarizer':         return this.summarize(text, options.preference);
      case 'translator':         return this.translate(text, options.targetLanguage, options.sourceLanguage);
      case 'language_detector':  return this.detectLanguage(text);
      case 'rewriter':           return this.rewrite(text, options.tone);
      case 'proofreader':        return this.proofread(text);
      case 'writer':             return this.write(text, options.context);
      default:                   return this.prompt(text, options.systemPrompt);
    }
  },

  async dispatchStream(taskType, text, options = {}, onChunk) {
    switch (taskType) {
      case 'summarizer':  return this.summarizeStream(text, options.preference, onChunk);
      default:            return this.promptStream(text, options.systemPrompt, onChunk);
    }
  },
};

// No ES module export — this file is loaded as a plain script in the extension.
// For ES module usage, import from the extension's copy (chrome_ai.js).
