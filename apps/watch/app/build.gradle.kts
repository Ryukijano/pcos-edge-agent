plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.pcos.watch"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.pcos.watch"
        minSdk = 30          // Wear OS 3+ required for Health Services
        targetSdk = 34       // Wear OS 5 (Aug 2025 Play Store requirement)
        versionCode = 2
        versionName = "0.2.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
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
    // Compose for Wear OS (latest stable)
    implementation(platform("androidx.compose:compose-bom:2025.04.01"))
    implementation("androidx.wear.compose:compose-material:1.4.1")
    implementation("androidx.wear.compose:compose-foundation:1.4.1")
    implementation("androidx.wear.compose:compose-navigation:1.4.1")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.1")

    // Health Services (near-stable RC)
    implementation("androidx.health:health-services-client:1.1.0-rc02")

    // Data Layer API (phone ↔ watch sync)
    implementation("com.google.android.gms:play-services-wearable:19.0.0")

    // Tiles (latest stable with ProtoLayout)
    implementation("androidx.wear.tiles:tiles:1.5.0")
    implementation("androidx.wear.protolayout:protolayout:1.3.0")
    implementation("androidx.wear.protolayout:protolayout-material:1.3.0")
    implementation("androidx.wear.protolayout:protolayout-expression:1.3.0")
    debugImplementation("androidx.wear.tiles:tiles-renderer:1.5.0")

    // WorkManager (for restoring passive monitoring after reboot)
    implementation("androidx.work:work-runtime-ktx:2.10.1")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-play-services:1.10.2")

    // Lifecycle (for WearableListenerService)
    implementation("androidx.lifecycle:lifecycle-service:2.9.1")
    implementation("androidx.core:core-ktx:1.16.0")

    // Ongoing Activity (Wear OS requirement WO-V4)
    implementation("androidx.wear:wear-ongoing:1.1.0")
}
