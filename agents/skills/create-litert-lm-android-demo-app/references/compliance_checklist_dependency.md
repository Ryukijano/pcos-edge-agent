# Compliance Checklist: Dependencies

- [ ] LiteRT-LM dependency version is 0.14.0 or later
- [ ] minSdk is 26 (Android 8.0) or higher
- [ ] compileSdk is 35 or higher
- [ ] Maven Central repository configured in settings.gradle.kts
- [ ] No conflicting LiteRT or TensorFlow Lite dependencies
- [ ] ProGuard/R8 rules exclude LiteRT-LM classes:
  ```proguard
  -keep class com.google.ai.edge.litertlm.** { *; }
  -keepclassmembers class com.google.ai.edge.litertlm.** { *; }
  ```
- [ ] Compose BOM version is 2024.12.01 or later
- [ ] AndroidX Core KTX 1.15.0 or later
- [ ] Lifecycle ViewModel Compose 2.8.7 or later
- [ ] Java 17+ configured in Gradle
- [ ] ABI filters include arm64-v8a (required for LiteRT-LM native libs)
