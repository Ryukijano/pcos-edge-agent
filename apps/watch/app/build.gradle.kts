plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.pcos.watch"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.pcos.watch"
        minSdk = 30          // Wear OS 3+ required for Health Services
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    // Compose for Wear OS
    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
    implementation("androidx.wear.compose:compose-material:1.3.1")
    implementation("androidx.wear.compose:compose-foundation:1.3.1")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.2")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.2")

    // Health Services
    implementation("androidx.health:health-services-client:1.1.0-alpha02")

    // Data Layer API (phone ↔ watch sync)
    implementation("com.google.android.gms:play-services-wearable:18.2.0")

    // Tiles
    implementation("androidx.wear.tiles:tiles:1.6.0")
    implementation("androidx.wear.protolayout:protolayout:1.4.0")
    implementation("androidx.wear.protolayout:protolayout-material:1.4.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-play-services:1.8.1")

    // Lifecycle (for WearableListenerService)
    implementation("androidx.lifecycle:lifecycle-service:2.8.2")
    implementation("androidx.core:core-ktx:1.13.1")
}
