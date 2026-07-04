# LiteRT-LM Model Configs

## FunctionGemma 270M (Fast Function Calling)

- **Model**: FunctionGemma 270M
- **Format**: `.task` (MediaPipe LLM Inference API)
- **Size**: ~270MB
- **Latency target**: <300ms on OnePlus 11R
- **Use**: On-device function calling (save_note, create_task, search_memory)
- **MTP drafters**: Enabled for 2-3x inference speedup

## Gemma 4 Full (Quality Path)

- **Model**: Gemma 4
- **Format**: `.task` (LiteRT-LM)
- **Size**: ~4GB
- **Latency target**: <2s on OnePlus 11R
- **Use**: General-purpose local inference, longer responses
- **Speculative decoding**: Active
- **KV cache reuse**: Enabled across sessions

## Download

Models are not included in the repo. Download from:
- FunctionGemma: https://ai.google.dev/edge/litert-lm/models
- Gemma 4: https://ai.google.dev/edge/litert-lm/models

Place `.task` files in `apps/android/app/src/main/assets/models/`.
