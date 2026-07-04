# PCOS Android ProGuard rules

# Keep LiteRT-LM native bridge classes
-keep class com.google.ai.edge.litert.** { *; }

# Keep Kotlin metadata
-keepattributes *Annotation*, SourceFile, LineNumberTable

# Keep model config classes
-keep class com.pcos.edge.** { *; }
