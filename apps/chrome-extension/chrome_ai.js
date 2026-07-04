/**
 * PCOS Chrome Built-in AI wrapper.
 * Uses stable Chrome 138+ Built-in AI APIs (LanguageModel, Summarizer, etc.).
 * Exposes global ChromeAI.
 * No manifest permissions required for Built-in AI in extensions.
 */

const ChromeAI = {
  _abortController: null,
  _activeSession: null,

  abort() {
    if (this._abortController) {
      this._abortController.abort();
      this._abortController = null;
    }
    if (this._activeSession) {
      this._activeSession.destroy();
      this._activeSession = null;
    }
  },

  _createAbortController() {
    this._abortController = new AbortController();
    return this._abortController.signal;
  },

  async checkAvailability(api = 'LanguageModel') {
    try {
      const ctor = self[api];
      if (!ctor) return 'unavailable';
      if (api === 'LanguageModel') {
        return await LanguageModel.availability({
          expectedInputs: [{ type: 'text', languages: ['en'] }],
          expectedOutputs: [{ type: 'text', languages: ['en'] }],
        });
      }
      return await ctor.availability();
    } catch (e) {
      return 'unavailable';
    }
  },

  async ensureAvailable(api = 'LanguageModel') {
    const status = await this.checkAvailability(api);
    return status === 'available' || status === 'downloadable' || status === 'downloading';
  },

  async summarize(text, preference = 'auto', onProgress) {
    const summarizer = await Summarizer.create({
      type: 'key-points',
      format: 'plain-text',
      length: 'short',
      preference,
      monitor: onProgress ? (m) => {
        m.addEventListener('downloadprogress', (e) => {
          onProgress(e.total ? Math.floor((e.loaded / e.total) * 100) : 0);
        });
      } : undefined,
    });
    this._activeSession = summarizer;
    const result = await summarizer.summarize(text);
    summarizer.destroy();
    this._activeSession = null;
    return result;
  },

  async summarizeStream(text, preference = 'auto', onChunk, onProgress) {
    const summarizer = await Summarizer.create({
      type: 'key-points',
      format: 'plain-text',
      length: 'short',
      preference,
      monitor: onProgress ? (m) => {
        m.addEventListener('downloadprogress', (e) => {
          onProgress(e.total ? Math.floor((e.loaded / e.total) * 100) : 0);
        });
      } : undefined,
    });
    this._activeSession = summarizer;
    let result = '';
    const stream = summarizer.summarizeStreaming(text);
    for await (const chunk of stream) {
      result += chunk;
      if (onChunk) onChunk(chunk);
    }
    summarizer.destroy();
    this._activeSession = null;
    return result;
  },

  async translate(text, targetLanguage = 'en', sourceLanguage = 'en') {
    const translator = await Translator.create({ sourceLanguage, targetLanguage });
    this._activeSession = translator;
    const result = await translator.translate(text);
    translator.destroy();
    this._activeSession = null;
    return result;
  },

  async detectLanguage(text) {
    const detector = await LanguageDetector.create();
    this._activeSession = detector;
    const results = await detector.detect(text);
    detector.destroy();
    this._activeSession = null;
    return results;
  },

  async rewrite(text, tone = 'as-is') {
    const rewriter = await Rewriter.create({ tone });
    this._activeSession = rewriter;
    const result = await rewriter.rewrite(text);
    rewriter.destroy();
    this._activeSession = null;
    return result;
  },

  async proofread(text) {
    const proofreader = await Proofreader.create();
    this._activeSession = proofreader;
    const result = await proofreader.proofread(text);
    proofreader.destroy();
    this._activeSession = null;
    return result;
  },

  async prompt(text, systemPrompt = '', onProgress) {
    const initOpts = {
      expectedInputs: [{ type: 'text', languages: ['en'] }],
      expectedOutputs: [{ type: 'text', languages: ['en'] }],
      monitor: onProgress ? (m) => {
        m.addEventListener('downloadprogress', (e) => {
          onProgress(e.total ? Math.floor((e.loaded / e.total) * 100) : 0);
        });
      } : undefined,
    };
    if (systemPrompt) {
      initOpts.initialPrompts = [{ role: 'system', content: systemPrompt }];
    }
    const session = await LanguageModel.create(initOpts);
    this._activeSession = session;
    const result = await session.prompt(text);
    session.destroy();
    this._activeSession = null;
    return result;
  },

  async promptStream(text, systemPrompt = '', onChunk, onProgress) {
    const initOpts = {
      expectedInputs: [{ type: 'text', languages: ['en'] }],
      expectedOutputs: [{ type: 'text', languages: ['en'] }],
      monitor: onProgress ? (m) => {
        m.addEventListener('downloadprogress', (e) => {
          onProgress(e.total ? Math.floor((e.loaded / e.total) * 100) : 0);
        });
      } : undefined,
    };
    if (systemPrompt) {
      initOpts.initialPrompts = [{ role: 'system', content: systemPrompt }];
    }
    const session = await LanguageModel.create(initOpts);
    this._activeSession = session;
    let result = '';
    const stream = session.promptStreaming(text);
    for await (const chunk of stream) {
      result += chunk;
      if (onChunk) onChunk(chunk);
    }
    session.destroy();
    this._activeSession = null;
    return result;
  },

  async write(prompt, context = '') {
    const writer = await Writer.create({ sharedContext: context });
    this._activeSession = writer;
    const result = await writer.write(prompt);
    writer.destroy();
    this._activeSession = null;
    return result;
  },

  async dispatch(taskType, text, options = {}) {
    switch (taskType) {
      case 'summarizer':         return this.summarize(text, options.preference, options.onProgress);
      case 'translator':         return this.translate(text, options.targetLanguage, options.sourceLanguage);
      case 'language_detector':  return this.detectLanguage(text);
      case 'rewriter':           return this.rewrite(text, options.tone);
      case 'proofreader':        return this.proofread(text);
      case 'writer':             return this.write(text, options.context);
      default:                   return this.prompt(text, options.systemPrompt, options.onProgress);
    }
  },

  async dispatchStream(taskType, text, options = {}, onChunk) {
    switch (taskType) {
      case 'summarizer':  return this.summarizeStream(text, options.preference, onChunk, options.onProgress);
      default:            return this.promptStream(text, options.systemPrompt, onChunk, options.onProgress);
    }
  },
};
