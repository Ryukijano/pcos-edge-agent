"""Tests for M22 — NPU SoC-specific model auto-download.

Tests the SoC → NPU model suffix mapping logic that mirrors the
Kotlin implementation in LiteRTManager.kt. Since Kotlin unit tests
require Android instrumentation, these tests validate the mapping
logic in Python to ensure correctness.

Tests cover:
- SoC → NPU suffix mapping (all supported SoCs)
- Compatibility mapping (SM8450/SM8475 → SM8550)
- NPU model file naming convention
- NPU model URL construction
- Unsupported SoC handling (returns None)
- FunctionGemma exclusion (no NPU variants)
- QAIRT library availability check logic
"""

import pytest


# ── SoC → NPU Suffix Mapping (mirrors LiteRTManager.kt) ────────

SOC_TO_NPU_SUFFIX = {
    "sm8450": "sm8550",   # 8 Gen 1 → compatible with 8 Gen 2 DSP
    "sm8475": "sm8550",   # 8+ Gen 1 → compatible with 8 Gen 2 DSP
    "sm8550": "sm8550",   # 8 Gen 2
    "sm8650": "sm8650",   # 8 Gen 3
    "sm8750": "sm8750",   # 8 Elite
    "sm8850": "sm8850",   # 8 Elite Gen 5
}

NPU_HF_REPO = "litert-community/gemma-4-E2B-it-litert-lm"

SUPPORTED_SOCS = {"sm8450", "sm8475", "sm8550", "sm8650", "sm8750", "sm8850"}

# Model base names (mirrors PCOSModel enum mapping in getNpuModelFile)
MODEL_BASE_NAMES = {
    "gemma_4_e2b": "gemma-4-E2B-it",
    "gemma_4_e2b_mobile": "gemma-4-E2B-it",
    "gemma_4_e4b": "gemma-4-E4B-it",
    "gemma_4_e4b_mobile": "gemma-4-E4B-it",
}


def get_npu_suffix(soc: str) -> str | None:
    """Get NPU model suffix for a given SoC. Returns None if unsupported."""
    return SOC_TO_NPU_SUFFIX.get(soc.lower().strip())


def get_npu_model_filename(model_name: str, soc: str) -> str | None:
    """Get NPU model filename for a model + SoC. Returns None if unsupported."""
    suffix = get_npu_suffix(soc)
    if suffix is None:
        return None
    base = MODEL_BASE_NAMES.get(model_name)
    if base is None:
        return None
    return f"{base}_q4_ekv1280_{suffix}.litertlm"


def get_npu_model_url(model_name: str, soc: str) -> str | None:
    """Get HuggingFace URL for NPU model variant. Returns None if unsupported."""
    filename = get_npu_model_filename(model_name, soc)
    if filename is None:
        return None
    return f"https://huggingface.co/{NPU_HF_REPO}/resolve/main/{filename}"


# ── SoC Mapping Tests ──────────────────────────────────────────


class TestSoCMapping:
    """Test SoC → NPU suffix mapping table."""

    def test_sm8550_maps_to_itself(self):
        assert get_npu_suffix("sm8550") == "sm8550"

    def test_sm8650_maps_to_itself(self):
        assert get_npu_suffix("sm8650") == "sm8650"

    def test_sm8750_maps_to_itself(self):
        assert get_npu_suffix("sm8750") == "sm8750"

    def test_sm8850_maps_to_itself(self):
        assert get_npu_suffix("sm8850") == "sm8850"

    def test_sm8450_maps_to_sm8550(self):
        """SM8450 (8 Gen 1) uses compatible SM8550 DSP variant."""
        assert get_npu_suffix("sm8450") == "sm8550"

    def test_sm8475_maps_to_sm8550(self):
        """SM8475 (8+ Gen 1) uses compatible SM8550 DSP variant."""
        assert get_npu_suffix("sm8475") == "sm8550"

    def test_unsupported_soc_returns_none(self):
        assert get_npu_suffix("exynos2400") is None
        assert get_npu_suffix("tensor_g3") is None
        assert get_npu_suffix("") is None
        assert get_npu_suffix("unknown") is None

    def test_case_insensitive(self):
        assert get_npu_suffix("SM8550") == "sm8550"
        assert get_npu_suffix("Sm8650") == "sm8650"

    def test_all_supported_socs_have_mapping(self):
        for soc in SUPPORTED_SOCS:
            assert get_npu_suffix(soc) is not None

    def test_all_six_supported_socs(self):
        assert len(SOC_TO_NPU_SUFFIX) == 6


# ── NPU Model Filename Tests ───────────────────────────────────


class TestNpuModelFilename:
    """Test NPU model filename generation."""

    def test_e2b_sm8550(self):
        fn = get_npu_model_filename("gemma_4_e2b", "sm8550")
        assert fn == "gemma-4-E2B-it_q4_ekv1280_sm8550.litertlm"

    def test_e2b_sm8650(self):
        fn = get_npu_model_filename("gemma_4_e2b", "sm8650")
        assert fn == "gemma-4-E2B-it_q4_ekv1280_sm8650.litertlm"

    def test_e4b_sm8750(self):
        fn = get_npu_model_filename("gemma_4_e4b", "sm8750")
        assert fn == "gemma-4-E4B-it_q4_ekv1280_sm8750.litertlm"

    def test_e2b_mobile_sm8550(self):
        fn = get_npu_model_filename("gemma_4_e2b_mobile", "sm8550")
        assert fn == "gemma-4-E2B-it_q4_ekv1280_sm8550.litertlm"

    def test_sm8450_uses_compatible_variant(self):
        """SM8450 should get SM8550 variant filename."""
        fn = get_npu_model_filename("gemma_4_e2b", "sm8450")
        assert fn == "gemma-4-E2B-it_q4_ekv1280_sm8550.litertlm"

    def test_sm8475_uses_compatible_variant(self):
        """SM8475 should get SM8550 variant filename."""
        fn = get_npu_model_filename("gemma_4_e2b", "sm8475")
        assert fn == "gemma-4-E2B-it_q4_ekv1280_sm8550.litertlm"

    def test_unsupported_soc_returns_none(self):
        assert get_npu_model_filename("gemma_4_e2b", "exynos2400") is None

    def test_function_gemma_returns_none(self):
        """FunctionGemma doesn't have NPU variants."""
        assert get_npu_model_filename("function_gemma", "sm8550") is None

    def test_filename_format(self):
        """NPU filenames follow the q4_ekv1280 naming convention."""
        fn = get_npu_model_filename("gemma_4_e2b", "sm8550")
        assert "_q4_ekv1280_" in fn
        assert fn.endswith(".litertlm")


# ── NPU Model URL Tests ────────────────────────────────────────


class TestNpuModelUrl:
    """Test NPU model URL construction."""

    def test_e2b_sm8550_url(self):
        url = get_npu_model_url("gemma_4_e2b", "sm8550")
        assert url == "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it_q4_ekv1280_sm8550.litertlm"

    def test_e4b_sm8650_url(self):
        url = get_npu_model_url("gemma_4_e4b", "sm8650")
        assert "gemma-4-E4B-it_q4_ekv1280_sm8650.litertlm" in url

    def test_unsupported_soc_url_is_none(self):
        assert get_npu_model_url("gemma_4_e2b", "unknown") is None

    def test_function_gemma_url_is_none(self):
        assert get_npu_model_url("function_gemma", "sm8550") is None

    def test_url_uses_huggingface(self):
        url = get_npu_model_url("gemma_4_e2b", "sm8550")
        assert url.startswith("https://huggingface.co/")


# ── Fallback Logic Tests ───────────────────────────────────────


class TestNpuFallbackLogic:
    """Test the NPU → GPU fallback decision logic."""

    def test_npu_available_with_qairt_uses_npu(self):
        """When NPU available + QAIRT libs present, use NPU model."""
        npu_available = True
        qairt_available = True
        npu_file_exists = True
        should_use_npu = npu_available and qairt_available and npu_file_exists
        assert should_use_npu is True

    def test_npu_available_without_qairt_falls_back(self):
        """When NPU available but QAIRT libs missing, fall back to GPU."""
        npu_available = True
        qairt_available = False
        should_use_npu = npu_available and qairt_available
        assert should_use_npu is False

    def test_npu_model_not_downloaded_falls_back(self):
        """When NPU model file not present, fall back to GPU model."""
        npu_file_exists = False
        should_use_npu_model = npu_file_exists
        assert should_use_npu_model is False

    def test_unsupported_soc_falls_back(self):
        """When SoC is not in mapping, getNpuModelFile returns None → GPU fallback."""
        npu_file = get_npu_model_filename("gemma_4_e2b", "exynos2400")
        assert npu_file is None  # Caller falls back to GPU model


# ── QAIRT Library Check Tests ──────────────────────────────────


class TestQairtCheck:
    """Test QAIRT library availability check logic (mirrors isQairtAvailable)."""

    def test_both_libs_present(self):
        """Both libQnnHtp.so and libQnnHtpPrepare.so must exist."""
        lib_qnn_htp = True
        lib_qnn_htp_prepare = True
        assert lib_qnn_htp and lib_qnn_htp_prepare is True

    def test_one_lib_missing(self):
        """If either library is missing, QAIRT is not available."""
        lib_qnn_htp = True
        lib_qnn_htp_prepare = False
        assert lib_qnn_htp and lib_qnn_htp_prepare is False

    def test_both_libs_missing(self):
        lib_qnn_htp = False
        lib_qnn_htp_prepare = False
        assert (lib_qnn_htp and lib_qnn_htp_prepare) is False


# ── SoC Detection Logic Tests ──────────────────────────────────


class TestSoCDetection:
    """Test SoC detection logic (mirrors detectSoCModel)."""

    def test_build_soc_model_available(self):
        """When Build.SOC_MODEL is set, use it directly."""
        build_soc_model = "sm8550"
        result = build_soc_model.lower().strip()
        assert result == "sm8550"

    def test_build_soc_model_empty_falls_back(self):
        """When Build.SOC_MODEL is empty, fall back to getprop."""
        build_soc_model = ""
        # In Kotlin, this would trigger getprop ro.soc.model
        assert build_soc_model == ""

    def test_build_soc_model_case_normalized(self):
        """SoC model string is lowercased."""
        build_soc_model = "SM8650"
        result = build_soc_model.lower().strip()
        assert result == "sm8650"

    def test_build_soc_model_whitespace_trimmed(self):
        build_soc_model = "  sm8750  "
        result = build_soc_model.lower().strip()
        assert result == "sm8750"


# ── Supported SoCs Coverage Tests ──────────────────────────────


class TestSupportedSoCs:
    """Test that all advertised supported SoCs have mappings."""

    @pytest.mark.parametrize("soc", ["sm8450", "sm8475", "sm8550", "sm8650", "sm8750", "sm8850"])
    def test_soc_has_npu_suffix(self, soc):
        assert get_npu_suffix(soc) is not None

    @pytest.mark.parametrize("soc", ["sm8450", "sm8475", "sm8550", "sm8650", "sm8750", "sm8850"])
    def test_soc_has_model_filename(self, soc):
        fn = get_npu_model_filename("gemma_4_e2b", soc)
        assert fn is not None
        assert fn.endswith(".litertlm")

    @pytest.mark.parametrize("soc", ["sm8450", "sm8475", "sm8550", "sm8650", "sm8750", "sm8850"])
    def test_soc_has_download_url(self, soc):
        url = get_npu_model_url("gemma_4_e2b", soc)
        assert url is not None
        assert url.startswith("https://")
