# Gemma Models

This folder holds configs and notes for the trained Gemma models used in PCOS.

## Models in use

| Model | Size | Use | Surface |
|---|---|---|---|
| FunctionGemma | 270M | On-device function calling | Android |
| Gemma 4 (trained) | variable | General local inference | Android / Chrome |
| Gemma Nano (built-in) | ~1.7B | Chrome Built-in AI | Chrome Canary |

## Notes

- FunctionGemma is 270M parameters, designed specifically for fast on-device function calling.
- Chrome's built-in Gemma 4 backend is accessed via `window.ai` — no model file needed.
- Your trained Gemma model should be exported to `.task` or `.tflite` format for LiteRT-LM on Android.
