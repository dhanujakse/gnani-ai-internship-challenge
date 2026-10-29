# WebRTC uses JNI callbacks into these classes
-keep class org.webrtc.** { *; }
-dontwarn org.webrtc.**
# kotlinx.serialization
-keepattributes *Annotation*, InnerClasses
-keepclassmembers class ai.mack.sarvagyan.** { *** Companion; }
-keepclasseswithmembers class ai.mack.sarvagyan.** { kotlinx.serialization.KSerializer serializer(...); }
-dontwarn okhttp3.internal.platform.**
