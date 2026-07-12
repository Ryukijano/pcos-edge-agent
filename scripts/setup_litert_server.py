"""One-command setup for local LiteRT-LM server with model import.

Usage:
    python scripts/setup_litert_server.py --models e2b e4b --include-12b --serve

This script:
1. Detects system RAM (skips 12B if < 16GB)
2. Imports models from HuggingFace via `litert-lm import`
3. Optionally starts `litert-lm serve` on port 9379

Requires: litert-lm CLI installed (pip install litert-lm)
"""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys

try:
    import psutil
except ImportError:
    print("Installing psutil…")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "psutil"])
    import psutil

MODELS = [
    ("gemma4-e2b", "litert-community/gemma-4-E2B-it-litert-lm", "gemma-4-E2B-it.litertlm"),
    ("gemma4-e4b", "litert-community/gemma-4-E4B-it-litert-lm", "gemma-4-E4B-it.litertlm"),
    ("gemma4-12b", "litert-community/gemma-4-12B-it-litert-lm", "gemma-4-12B-it.litertlm"),
]

RAM_THRESHOLD_12B = 16384  # 16GB in MB


def check_litert_lm() -> bool:
    """Check if litert-lm CLI is installed."""
    return shutil.which("litert-lm") is not None


def get_ram_mb() -> int:
    """Get total system RAM in MB."""
    return psutil.virtual_memory().total // (1024 * 1024)


def get_os_type() -> str:
    """Get normalized OS type string."""
    return {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(
        platform.system(), platform.system().lower()
    )


def detect_gpu() -> bool:
    """Best-effort GPU detection."""
    os_type = get_os_type()
    if os_type == "linux":
        try:
            result = subprocess.run(["lspci"], capture_output=True, timeout=2)
            return b"VGA" in result.stdout or b"3D" in result.stdout
        except Exception:
            return False
    elif os_type == "macos":
        # macOS always has Metal GPU
        return True
    elif os_type == "windows":
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "getName"],
                capture_output=True, timeout=2,
            )
            return result.returncode == 0 and result.stdout.strip()
        except Exception:
            return False
    return False


def import_model(model_id: str, hf_repo: str, filename: str) -> bool:
    """Import a model from HuggingFace via litert-lm CLI.

    Returns True if import succeeded (or model already exists).
    """
    print(f"  Importing {model_id} from {hf_repo}…")
    try:
        result = subprocess.run(
            [
                "litert-lm", "import",
                f"--from-huggingface-repo={hf_repo}",
                filename, model_id,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout for large downloads
        )
        print(f"  ✅ {model_id} imported successfully")
        return True
    except subprocess.CalledProcessError as e:
        if "already exists" in (e.stderr or "").lower():
            print(f"  ✅ {model_id} already imported")
            return True
        print(f"  ❌ Failed to import {model_id}: {e.stderr or e}")
        return False
    except subprocess.TimeoutExpired:
        print(f"  ❌ Import of {model_id} timed out")
        return False
    except FileNotFoundError:
        print("  ❌ litert-lm CLI not found. Install with: pip install litert-lm")
        return False


def serve(port: int = 9379, api: str = "openai") -> None:
    """Start litert-lm serve (blocking)."""
    print(f"\nStarting litert-lm serve on port {port} ({api} API)…")
    print("  Press Ctrl+C to stop.\n")
    try:
        subprocess.run([
            "litert-lm", "serve",
            f"--api={api}", "--host", "localhost", "--port", str(port),
        ])
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except FileNotFoundError:
        print("❌ litert-lm CLI not found. Install with: pip install litert-lm")


def main():
    parser = argparse.ArgumentParser(
        description="One-command setup for local LiteRT-LM server."
    )
    parser.add_argument(
        "--models", nargs="*", default=["e2b", "e4b"],
        help="Model variants to import (e2b, e4b). Default: e2b e4b",
    )
    parser.add_argument(
        "--port", type=int, default=9379,
        help="Port for litert-lm serve. Default: 9379",
    )
    parser.add_argument(
        "--serve", action="store_true",
        help="Start server after import",
    )
    parser.add_argument(
        "--include-12b", action="store_true",
        help="Import 12B model (requires 16GB+ RAM)",
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="Only check environment, don't import or serve",
    )
    args = parser.parse_args()

    # Environment checks
    print("=" * 60)
    print("PCOS LiteRT-LM Desktop Setup")
    print("=" * 60)

    ram_mb = get_ram_mb()
    os_type = get_os_type()
    has_gpu = detect_gpu()
    has_cli = check_litert_lm()

    print(f"  OS:       {os_type}")
    print(f"  RAM:      {ram_mb} MB")
    print(f"  GPU:      {'Yes' if has_gpu else 'No'}")
    print(f"  litert-lm: {'installed' if has_cli else 'NOT FOUND'}")

    if not has_cli:
        print("\n❌ litert-lm CLI not installed.")
        print("   Install with: pip install litert-lm")
        sys.exit(1)

    if args.check_only:
        print(f"\n12B eligible: {'Yes' if ram_mb >= RAM_THRESHOLD_12B else 'No (need 16GB+)'}")
        sys.exit(0)

    # Determine which models to import
    to_import: list[tuple[str, str, str]] = []
    for mid, repo, fn in MODELS:
        if "12b" in mid:
            if not args.include_12b:
                print(f"\nSkipping {mid} (use --include-12b to enable)")
                continue
            if ram_mb < RAM_THRESHOLD_12B:
                print(f"\n⚠️  Skipping {mid}: only {ram_mb} MB RAM (need {RAM_THRESHOLD_12B}+)")
                continue
            print(f"\n✅ 12B eligible: {ram_mb} MB RAM ≥ {RAM_THRESHOLD_12B} MB threshold")
        else:
            # Check if model variant was requested
            variant = mid.split("-")[-1]  # e2b, e4b, 12b
            if variant not in args.models and not args.include_12b:
                continue

        to_import.append((mid, repo, fn))

    if not to_import:
        print("\nNo models to import. Check --models flag.")
        sys.exit(0)

    # Import models
    print(f"\n{'─' * 40}")
    print(f"Importing {len(to_import)} model(s)…")
    print(f"{'─' * 40}")

    success_count = 0
    for mid, repo, fn in to_import:
        if import_model(mid, repo, fn):
            success_count += 1

    print(f"\n{'─' * 40}")
    print(f"Imported {success_count}/{len(to_import)} models successfully")

    # Start server
    if args.serve:
        serve(port=args.port)
    else:
        print(f"\nTo start the server:")
        print(f"  litert-lm serve --api openai --host localhost --port {args.port}")
        print(f"\nOr re-run with --serve flag")


if __name__ == "__main__":
    main()
