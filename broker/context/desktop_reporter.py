"""Desktop capability reporter — detects RAM, GPU, and LiteRT-LM server state.

Populates DesktopContext fields so the router can make informed decisions
about 12B model routing (requires 16GB+ RAM) and local server usage.

Usage:
    from broker.context.desktop_reporter import detect_desktop_context
    ctx = await detect_desktop_context()
    # ctx["litert_server_available"], ctx["total_ram_mb"], ctx["has_12b_model"]
"""
from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from typing import Any

import httpx

log = logging.getLogger("pcos.desktop_reporter")

RAM_THRESHOLD_12B = 16384  # 16GB in MB


def _get_ram_mb() -> int:
    """Get total system RAM in MB."""
    try:
        import psutil
        return psutil.virtual_memory().total // (1024 * 1024)
    except ImportError:
        return 0


def _get_os_type() -> str:
    """Get normalized OS type string."""
    return {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(
        platform.system(), platform.system().lower()
    )


def _detect_gpu() -> bool:
    """Best-effort GPU detection."""
    os_type = _get_os_type()
    if os_type == "linux":
        try:
            result = subprocess.run(
                ["lspci"], capture_output=True, timeout=2,
            )
            return b"VGA" in result.stdout or b"3D" in result.stdout
        except Exception:
            return False
    elif os_type == "macos":
        return True  # All macOS devices have Metal
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


def _detect_gpu_name() -> str:
    """Best-effort GPU name detection."""
    os_type = _get_os_type()
    if os_type == "linux":
        try:
            result = subprocess.run(
                ["lspci"], capture_output=True, timeout=2, text=True,
            )
            for line in result.stdout.splitlines():
                if "VGA" in line or "3D" in line:
                    return line.split(":")[-1].strip()
        except Exception:
            pass
    elif os_type == "macos":
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True, timeout=3, text=True,
            )
            for line in result.stdout.splitlines():
                if "Chipset" in line or "Metal" in line:
                    return line.strip()
        except Exception:
            pass
    return ""


async def detect_desktop_context(
    server_url: str = "http://localhost:9379",
) -> dict[str, Any]:
    """Detect desktop capabilities and available models from lit serve.

    Returns a dict matching DesktopContext fields:
        litert_server_available: bool
        litert_server_url: str
        total_ram_mb: int
        has_12b_model: bool
        has_gpu: bool
        gpu_name: str
        os_type: str
    """
    ram_mb = _get_ram_mb()
    has_gpu = _detect_gpu()
    gpu_name = _detect_gpu_name()
    os_type = _get_os_type()
    litert_available = False
    has_12b = False

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{server_url}/v1/models")
            if resp.status_code == 200:
                litert_available = True
                models = resp.json().get("data", [])
                has_12b = any(
                    "12b" in m.get("id", "").lower()
                    for m in models
                )
    except Exception:
        pass

    log.debug(
        "desktop_context_detected",
        extra={
            "ram_mb": ram_mb,
            "has_gpu": has_gpu,
            "litert_available": litert_available,
            "has_12b": has_12b,
            "os_type": os_type,
        },
    )

    return {
        "litert_server_available": litert_available,
        "litert_server_url": server_url,
        "total_ram_mb": ram_mb,
        "has_12b_model": has_12b,
        "has_gpu": has_gpu,
        "gpu_name": gpu_name,
        "os_type": os_type,
    }


def detect_desktop_context_sync(
    server_url: str = "http://localhost:9379",
) -> dict[str, Any]:
    """Synchronous version of detect_desktop_context."""
    ram_mb = _get_ram_mb()
    has_gpu = _detect_gpu()
    gpu_name = _detect_gpu_name()
    os_type = _get_os_type()
    litert_available = False
    has_12b = False

    try:
        resp = httpx.get(f"{server_url}/v1/models", timeout=3.0)
        if resp.status_code == 200:
            litert_available = True
            models = resp.json().get("data", [])
            has_12b = any(
                "12b" in m.get("id", "").lower()
                for m in models
            )
    except Exception:
        pass

    return {
        "litert_server_available": litert_available,
        "litert_server_url": server_url,
        "total_ram_mb": ram_mb,
        "has_12b_model": has_12b,
        "has_gpu": has_gpu,
        "gpu_name": gpu_name,
        "os_type": os_type,
    }


def is_12b_eligible(total_ram_mb: int) -> bool:
    """Check if the system has enough RAM for the 12B model."""
    return total_ram_mb >= RAM_THRESHOLD_12B
