#!/usr/bin/env python3
"""Automated benchmark runner for LiteRT-LM models via CLI.

Wraps `litert-lm benchmark` to run regression tests across models and backends,
collects results, and outputs a structured report.

Usage:
    python scripts/run_benchmarks.py --model gemma4-e2b --backends cpu,gpu
    python scripts/run_benchmarks.py --all-models --backend gpu
    python scripts/run_benchmarks.py --model gemma4-e2b --android --device pixel10

Requirements:
    litert-lm CLI installed: pip install litert-lm
    Or via uvx: uvx litert-lm benchmark --help
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class BenchmarkResult:
    model: str
    backend: str
    prefill_tokens: int
    decode_tokens: int
    ttft_seconds: float = 0.0
    prefill_tps: float = 0.0
    decode_tps: float = 0.0
    peak_mem_mb: float = 0.0
    elapsed_seconds: float = 0.0
    success: bool = False
    error: str = ""
    raw_output: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# Model registry — maps friendly names to litert-lm model IDs or paths
MODEL_REGISTRY = {
    "gemma4-e2b": {
        "id": "gemma4-e2b",
        "hf_repo": "litert-community/gemma-4-E2B-it-litert-lm",
        "file": "gemma-4-E2B-it.litertlm",
    },
    "gemma4-e4b": {
        "id": "gemma4-e4b",
        "hf_repo": "litert-community/gemma-4-E4B-it-litert-lm",
        "file": "gemma-4-E4B-it.litertlm",
    },
    "gemma4-e2b-mobile": {
        "id": "gemma4-e2b-mobile",
        "hf_repo": "litert-community/gemma-4-E2B-it-litert-lm",
        "file": "gemma-4-E2B-it-mobile.litertlm",
    },
    "gemma4-e4b-mobile": {
        "id": "gemma4-e4b-mobile",
        "hf_repo": "litert-community/gemma-4-E4B-it-litert-lm",
        "file": "gemma-4-E4B-it-mobile.litertlm",
    },
    "functiongemma": {
        "id": "functiongemma",
        "hf_repo": "litert-community/functiongemma-270m-ft-mobile-actions",
        "file": "functiongemma-270m-ft-mobile-actions.litertlm",
    },
}

BACKENDS = ["cpu", "gpu", "npu"]


def run_benchmark(
    model_ref: str,
    backend: str = "cpu",
    prefill_tokens: int = 256,
    decode_tokens: int = 256,
    android: bool = False,
    from_hf: Optional[str] = None,
    hf_file: Optional[str] = None,
) -> BenchmarkResult:
    """Run a single benchmark via litert-lm CLI."""
    cmd = ["litert-lm", "benchmark", model_ref]
    cmd.extend(["--backend", backend])
    cmd.extend(["--prefill_tokens", str(prefill_tokens)])
    cmd.extend(["--decode_tokens", str(decode_tokens)])

    if android:
        cmd.append("--android")

    if from_hf:
        cmd.extend(["--from-huggingface-repo", from_hf])
        if hf_file:
            cmd.append(hf_file)

    start = time.time()
    result = BenchmarkResult(
        model=model_ref,
        backend=backend,
        prefill_tokens=prefill_tokens,
        decode_tokens=decode_tokens,
    )

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        result.raw_output = proc.stdout + proc.stderr
        result.elapsed_seconds = time.time() - start

        if proc.returncode == 0:
            result.success = True
            _parse_benchmark_output(result)
        else:
            result.error = proc.stderr.strip() or proc.stdout.strip()
    except subprocess.TimeoutExpired:
        result.error = "Benchmark timed out after 300s"
        result.elapsed_seconds = time.time() - start
    except FileNotFoundError:
        result.error = "litert-lm CLI not found. Install with: pip install litert-lm"
        result.elapsed_seconds = time.time() - start

    return result


def _parse_benchmark_output(result: BenchmarkResult) -> None:
    """Parse TTFT, prefill TPS, decode TPS from litert-lm benchmark output."""
    output = result.raw_output
    for line in output.splitlines():
        line = line.strip()
        if "Time to first token:" in line:
            try:
                val = line.split(":")[-1].strip().rstrip("s").strip()
                result.ttft_seconds = float(val)
            except ValueError:
                pass
        elif "Prefill" in line and "tokens/sec" in line:
            try:
                val = line.split(":")[-1].strip().split()[0]
                result.prefill_tps = float(val)
            except (ValueError, IndexError):
                pass
        elif "Decode" in line and "tokens/sec" in line:
            try:
                val = line.split(":")[-1].strip().split()[0]
                result.decode_tps = float(val)
            except (ValueError, IndexError):
                pass
        elif "Peak" in line and "MB" in line:
            try:
                val = line.split(":")[-1].strip().split()[0]
                result.peak_mem_mb = float(val)
            except (ValueError, IndexError):
                pass


def run_suite(
    models: list[str],
    backends: list[str],
    prefill_tokens: int = 256,
    decode_tokens: int = 256,
    android: bool = False,
) -> list[BenchmarkResult]:
    """Run benchmarks across multiple models and backends."""
    results = []
    for model_name in models:
        model_info = MODEL_REGISTRY.get(model_name)
        if not model_info:
            print(f"  ⚠ Unknown model: {model_name}, skipping")
            continue

        for backend in backends:
            print(f"  → Benchmarking {model_name} on {backend}…")
            result = run_benchmark(
                model_ref=model_info["id"],
                backend=backend,
                prefill_tokens=prefill_tokens,
                decode_tokens=decode_tokens,
                android=android,
                from_hf=model_info.get("hf_repo"),
                hf_file=model_info.get("file"),
            )
            results.append(result)

            if result.success:
                print(
                    f"    ✅ TTFT: {result.ttft_seconds:.2f}s | "
                    f"Prefill: {result.prefill_tps:.1f} tk/s | "
                    f"Decode: {result.decode_tps:.1f} tk/s"
                )
            else:
                print(f"    ❌ {result.error}")

    return results


def print_report(results: list[BenchmarkResult]) -> None:
    """Print a formatted benchmark report."""
    print("\n" + "=" * 80)
    print("Benchmark Report")
    print("=" * 80)
    print(f"{'Model':<25} {'Backend':<8} {'TTFT(s)':<10} {'Prefill':<12} {'Decode':<12} {'Status'}")
    print("-" * 80)

    for r in results:
        status = "✅" if r.success else "❌"
        ttft = f"{r.ttft_seconds:.2f}" if r.success else "-"
        prefill = f"{r.prefill_tps:.1f} tk/s" if r.success else "-"
        decode = f"{r.decode_tps:.1f} tk/s" if r.success else "-"
        print(f"{r.model:<25} {r.backend:<8} {ttft:<10} {prefill:<12} {decode:<12} {status}")

    print("=" * 80)
    succeeded = sum(1 for r in results if r.success)
    print(f"Total: {len(results)} | Passed: {succeeded} | Failed: {len(results) - succeeded}")


def main():
    parser = argparse.ArgumentParser(description="Run LiteRT-LM benchmarks")
    parser.add_argument(
        "--model", nargs="+", default=["gemma4-e2b"],
        help="Model names from registry (or 'all')",
    )
    parser.add_argument(
        "--backends", default="gpu",
        help="Comma-separated backends (cpu,gpu,npu)",
    )
    parser.add_argument("--prefill-tokens", type=int, default=256)
    parser.add_argument("--decode-tokens", type=int, default=256)
    parser.add_argument("--android", action="store_true", help="Run on Android via ADB")
    parser.add_argument("--output", type=str, help="Save results as JSON to this path")
    args = parser.parse_args()

    models = MODEL_REGISTRY.keys() if "all" in args.model else args.model
    backends = args.backends.split(",")

    print(f"Running benchmarks: models={list(models)}, backends={backends}")
    results = run_suite(
        models=list(models),
        backends=backends,
        prefill_tokens=args.prefill_tokens,
        decode_tokens=args.decode_tokens,
        android=args.android,
    )

    print_report(results)

    if args.output:
        Path(args.output).write_text(
            json.dumps([r.to_dict() for r in results], indent=2)
        )
        print(f"\nResults saved to {args.output}")

    if any(not r.success for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
