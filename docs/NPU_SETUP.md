# NPU Backend Setup — Qualcomm Snapdragon

## Supported SoCs

| SoC | Device Examples | Status |
|---|---|---|
| SM8450 (8 Gen 1) | Galaxy S23, OnePlus 11 | ✅ Supported |
| SM8475 (8+ Gen 1) | OnePlus 11R, Galaxy S22 Ultra | ✅ Supported |
| SM8550 (8 Gen 2) | Galaxy S23 Ultra, OnePlus 11 | ✅ Supported |
| SM8650 (8 Gen 3) | Galaxy S24, OnePlus 12 | ✅ Supported |
| SM8750 (8 Elite) | Galaxy S25, OnePlus 13 | ✅ Supported |
| SM8850 (8 Elite Gen 5) | Pixel 10 Pro | ✅ Supported |

## Setup

### 1. Download QAIRT SDK

Download the Qualcomm AI Runtime (QAIRT) SDK from Qualcomm's developer site.

```bash
# Extract QAIRT
unzip qairt.zip
export QAIRT_ROOT=/path/to/qairt-2.42.0.251225
```

### 2. Bundle NPU Libraries

Push the QAIRT libraries to the device:

```bash
DEVICE_FOLDER=/data/local/tmp/litert_npu
adb shell mkdir -p $DEVICE_FOLDER

# Push QAIRT libraries
adb push $QAIRT_ROOT/lib/aarch64-android/libQnnHtp*Stub.so $DEVICE_FOLDER
adb push $QAIRT_ROOT/lib/aarch64-android/libQnnHtp.so $DEVICE_FOLDER
adb push $QAIRT_ROOT/lib/aarch64-android/libQnnSystem.so $DEVICE_FOLDER
adb push $QAIRT_ROOT/lib/aarch64-android/libQnnHtpPrepare.so $DEVICE_FOLDER
adb push $QAIRT_ROOT/lib/hexagon-*/unsigned/libQnnHtp*Skel.so $DEVICE_FOLDER
```

### 3. App Integration

In your Android app, bundle the NPU libraries via `jniLibs`:

```kotlin
val engineConfig = EngineConfig(
    modelPath = modelPath,
    backend = Backend.NPU(nativeLibraryDir = context.applicationInfo.nativeLibraryDir)
)
```

### 4. Gradle Configuration

```kotlin
android {
    ndk {
        abiFilters.add("arm64-v8a")  // NPU only supports arm64
    }
    packaging {
        jniLibs {
            useLegacyPackaging = true  // Needed for Qualcomm NPU
        }
    }
}
```

### 5. AndroidManifest

```xml
<uses-native-library android:name="libQnnHtp.so" android:required="false" />
```

## Auto-Fallback

LiteRT-LM automatically falls back to GPU → CPU if NPU initialization fails. The `backendPriority` list in `LiteRTManager.kt` handles this:

```kotlin
val backendPriority = when {
    isNpuAvailable() -> listOf(Backend.NPU(nativeLibraryDir), Backend.GPU(), Backend.CPU())
    isGpuAvailable() -> listOf(Backend.GPU(), Backend.CPU())
    else -> listOf(Backend.CPU())
}
```

## NPU-Specific Models

NPU models are SoC-specific. Download the correct variant from HuggingFace:

- `gemma-4-E2B-it_q4_ekv1280_sm8550.litertlm` (for SM8550)
- `gemma-4-E2B-it_q4_ekv1280_sm8650.litertlm` (for SM8650)
- `gemma-4-E2B-it_q4_ekv1280_sm8750.litertlm` (for SM8750)
- `gemma-4-E2B-it_q4_ekv1280_sm8850.litertlm` (for SM8850)

The model file name encodes the SoC. Using the wrong SoC variant will fail at runtime.

### SoC Compatibility Mapping

Older SoCs use a compatible DSP variant from newer chips:

| Device SoC | NPU Model Suffix | Reason |
|---|---|---|
| SM8450 (8 Gen 1) | `sm8550` | Compatible DSP architecture |
| SM8475 (8+ Gen 1) | `sm8550` | Compatible DSP architecture |
| SM8550 (8 Gen 2) | `sm8550` | Native |
| SM8650 (8 Gen 3) | `sm8650` | Native |
| SM8750 (8 Elite) | `sm8750` | Native |
| SM8850 (8 Elite Gen 5) | `sm8850` | Native |

## Auto-Download (M22)

`LiteRTManager` automatically detects the SoC and downloads the correct NPU model variant.

### How It Works

1. **SoC Detection**: `detectSoCModel()` reads `Build.SOC_MODEL` (Android 12+) or falls back to `getprop ro.soc.model`
2. **QAIRT Check**: `isQairtAvailable()` checks for `libQnnHtp.so` and `libQnnHtpPrepare.so` in `nativeLibraryDir`
3. **NPU Model Selection**: `getNpuModelFile(model)` maps SoC → NPU suffix → file name (e.g. `gemma-4-E2B-it_q4_ekv1280_sm8550.litertlm`)
4. **Download**: `ensureModelDownloaded(model, useNpu=true)` fetches the SoC-specific variant from HuggingFace
5. **Load**: `loadModel()` tries NPU model file first, falls back to GPU model if NPU file not present

### Usage

```kotlin
val manager = LiteRTManager(context)

// Check NPU availability
if (manager.isNpuAvailable() && manager.isQairtAvailable()) {
    val soc = manager.detectSoCModel()  // e.g. "sm8550"
    Log.i(TAG, "NPU ready for SoC: $soc")

    // Download SoC-specific NPU model
    manager.ensureModelDownloaded(PCOSModel.GEMMA_4_E2B, useNpu = true)

    // Load — automatically uses NPU variant if available
    manager.loadModel(PCOSModel.GEMMA_4_E2B)
}
```

### Fallback Chain

```
NPU model (SoC-specific) → GPU model (standard) → CPU model (fallback)
```

If the NPU variant download fails or the file is corrupt, the app automatically falls back to the standard GPU model. If NPU init fails at runtime, LiteRT-LM falls back to GPU → CPU.

## Troubleshooting

### "No usable Dispatch runtime found"
- Ensure QAIRT libraries are bundled in `jniLibs/arm64-v8a/`
- Check `useLegacyPackaging = true` in Gradle
- Verify `Backend.NPU(nativeLibraryDir = context.applicationInfo.nativeLibraryDir)` is set

### NPU init fails but GPU works
- The app auto-falls back to GPU → CPU
- Check `adb logcat | grep litert` for detailed error messages
- Ensure the model file matches your SoC
