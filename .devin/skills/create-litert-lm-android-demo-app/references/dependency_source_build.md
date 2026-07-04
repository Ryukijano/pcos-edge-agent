# Dependency: Source Build

## Prerequisites

- Bazel 9+
- Android SDK 35
- Android NDK 27+
- Java 17+

## Setup

Clone LiteRT-LM and configure Bazel workspace:

```bash
git clone https://github.com/google-ai-edge/LiteRT-LM.git
cd LiteRT-LM
bazel sync
```

## BUILD Target

```python
android_binary(
    name = "litertlm_demo",
    srcs = glob(["**/*.kt"]),
    manifest = "AndroidManifest.xml",
    deps = [
        "//runtime:litertlm_android",
        "@maven//:androidx_core_core_ktx",
        "@maven//:androidx_activity_activity_compose",
        "@maven//:androidx_compose_material3_material3",
    ],
)
```

## Build Commands

```bash
# Debug build
bazel build //app:litertlm_demo --config=android

# Install to device
bazel mobile-install //app:litertlm_demo --config=android --start_app
```

## Compliance Checklist

- [ ] Bazel 9+ installed
- [ ] Android NDK 27+ configured
- [ ] LiteRT-LM repository cloned at stable tag
- [ ] No Maven dependencies conflicting with source build
- [ ] Native libraries built for target ABI (arm64-v8a)
