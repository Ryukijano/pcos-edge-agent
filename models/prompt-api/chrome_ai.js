/**
 * PCOS Chrome Built-in AI wrapper.
 * Selects the correct Chrome API based on task type.
 * Requires Chrome Canary with Built-in AI flags enabled.
 */

const ChromeAI = {
  async summarize(text, preference = 'auto') {
    const summarizer = await window.ai.summarizer.create({
      type: 'key-points',
      format: 'plain-text',
      length: 'short',
      preference,
    });
    return await summarizer.summarize(text);
  },

  async classify(text) {
    const classifier = await window.ai.classifier.create();
    return await classifier.classify(text);
  },

  async rewrite(text, tone = 'as-is') {
    const rewriter = await window.ai.rewriter.create({ tone });
    return await rewriter.rewrite(text);
  },

  async proofread(text) {
    const proofreader = await window.ai.proofreader.create();
    return await proofreader.proofread(text);
  },

  async prompt(text, systemPrompt = '') {
    const session = await window.ai.languageModel.create({
      systemPrompt,
    });
    return await session.prompt(text);
  },

  async write(prompt, context = '') {
    const writer = await window.ai.writer.create({ sharedContext: context });
    return await writer.write(prompt);
  },

  // Route to the right API based on task type string
  async dispatch(taskType, text, options = {}) {
    switch (taskType) {
      case 'summarizer':  return this.summarize(text, options.preference);
      case 'classifier':  return this.classify(text);
      case 'rewriter':    return this.rewrite(text, options.tone);
      case 'proofreader': return this.proofread(text);
      case 'writer':      return this.write(text, options.context);
      default:            return this.prompt(text, options.systemPrompt);
    }
  }
};

export default ChromeAI;
