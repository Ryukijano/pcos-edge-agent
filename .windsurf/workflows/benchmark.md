---
description: Run LiteRT-LM benchmarks on connected Android device or local server
---

1. Check if an Android device is connected:
   ```bash
   adb devices
   ```

2. If a device is connected, run the benchmark script:
   ```bash
   python scripts/run_benchmarks.py --model all --backends cpu,gpu --android --output benchmark_results.json
   ```

3. If no device, run against local litert_server:
   ```bash
   python scripts/run_benchmarks.py --model gemma4-e2b --backends gpu --output benchmark_results.json
   ```

4. Read and summarize the results from `benchmark_results.json`:
   - TTFT (time to first token)
   - Prefill TPS (tokens per second)
   - Decode TPS
   - Peak memory usage

5. Compare results against the benchmarks in README.md and report any regressions.
