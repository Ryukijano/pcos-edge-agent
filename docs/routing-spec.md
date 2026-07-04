# PCOS Routing Specification

## Routing Decision Tree

```
Incoming Task
      │
      ├── is_private OR is_offline?
      │         └── YES → Android LiteRT-LM / FunctionGemma
      │
      ├── is_webpage_grounded AND is_short AND is_transform?
      │         └── YES → Chrome Built-in AI (Prompt/Summarizer/Translator/etc.)
      │
      ├── requires_personal_context OR workflow_memory?
      │         └── YES → PiecesOS LTM → local model
      │
      ├── is_action (tool call, function call)?
      │         └── YES → FunctionGemma on-device → MCP tool execution
      │
      ├── is_long_reasoning OR exceeds_local_context?
      │         └── YES → Cloud LLM escalation
      │
      └── default → Chrome Prompt API or Android LiteRT-LM
```

## API Selection Inside Chrome

| Task | API to use |
|---|---|
| Summarize article | Summarizer API (speed mode for quick, capability for quality) |
| Rewrite email | Rewriter API |
| Proofread text | Proofreader API |
| Translate text | Translator API |
| Detect language | Language Detector API |
| General NLP chat | Prompt API |
| Long-form writing | Writer API |

## Escalation Policy

Context sent to cloud must be:
1. Explicitly approved by the user OR
2. Anonymised / stripped of private identifiers
3. Logged in the Context Broker with timestamp

PiecesOS supports local-only and blended modes. Default should be local-only unless task explicitly requires cloud.

## Latency Targets

| Surface | Target latency |
|---|---|
| Chrome Built-in AI | < 500ms |
| Android LiteRT-LM (FunctionGemma) | < 300ms |
| Android LiteRT-LM (Gemma full) | < 2s |
| PiecesOS context retrieval | < 200ms |
| Cloud escalation | < 5s (acceptable) |
