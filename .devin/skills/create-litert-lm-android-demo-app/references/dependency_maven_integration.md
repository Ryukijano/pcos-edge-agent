# Dependency: Maven Integration

## Setup

Add the LiteRT-LM Maven dependency to `app/build.gradle.kts`:

```kotlin
dependencies {
    implementation("com.google.ai.edge.litertlm:litertlm-android:0.14.0")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
}
```

## Repository Configuration

Ensure `settings.gradle.kts` includes Maven Central:

```kotlin
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
}
```

## Minimum SDK

```kotlin
android {
    namespace = "com.example.litertlm"
    compileSdk = 35

    defaultConfig {
        minSdk = 26  // Android 8.0+ required for LiteRT-LM
        targetSdk = 35
    }
}
```

## Compliance Checklist

- [ ] Maven dependency version is 0.14.0 or later
- [ ] minSdk is 26 or higher
- [ ] Maven Central repository configured
- [ ] No conflicting LiteRT dependencies
- [ ] ProGuard rules exclude LiteRT-LM classes
