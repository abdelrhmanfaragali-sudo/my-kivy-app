[app]

# عنوان التطبيق
title = YouTube Playlist Downloader

# اسم الحزمة (Package name)
package.name = youtubedownloader

# اسم المجال (Domain)
package.domain = com.youtubedownloader

# إصدار التطبيق
version = 2.0.0

# متطلبات التطبيق
requirements = python3,kivy==2.1.0,kivymd==1.1.1,yt-dlp==2023.10.13,requests==2.31.0,pyjnius==1.5.0,android==1.0,openssl

# المسار الرئيسي
source.dir = .

# الملفات الرئيسية
source.include_exts = py,png,jpg,kv,atlas

# المجلدات المستثناة
source.exclude_exts = spec,zip,db,git

# مجلدات المستثناة
source.exclude_dirs = tests,bin,lib,include,build,dist,__pycache__,.git

# الملفات المستثناة
source.exclude_patterns = *.pyc,*.pyo,*.pyd

# الإذن للقراءة/الكتابة
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE

# أذونات إضافية للأندرويد 11+
android.api = 30
android.minapi = 21
android.targetapi = 30

# اسم النشاط الرئيسي
android.entrypoint = org.kivy.android.PythonActivity

# اللغة الافتراضية
android.resdir = ./android_res

# الأيقونة
android.icon = icon.png

# عرض ملء الشاشة
android.fullscreen = 0

# السماح بالدوران
android.allow_rotation = True

# اتجاه الشاشة
android.orientation = portrait

# دعم ملء الشاشة
android.window_soft_input_mode = 16

# Java class للتصريحات الإضافية
android.add_src =

# الإذن للوصول لملفات
android.gradle_dependencies =

# استثناءات Proguard
android.proguard_whitelist =

# خدمات للخلفية
android.services =

# موردين إضافيين
android.add_assets =

# النشاطات
android.add_activities =

# تصاريح خاصة للأندرويد 13+
android.extra_permissions = 

# دعم مودم الأندرويد
android.add_manifest_meta =

# دعم اتصالات الإنترنت
android.add_manifest_element = <uses-permission android:name="android.permission.INTERNET" />

# إعدادات التطبيق الإضافية
android.gradle_dependencies = implementation 'androidx.core:core:1.9.0'
android.gradle_dependencies += implementation 'androidx.appcompat:appcompat:1.6.1'

# دعم البناء المتسارع
android.accelerate_code_compilation = True

# دعم AndroidX
android.use_androidx = True

# إصدار SDK للأندرويد
android.sdk = 30
android.ndk = 23b
android.ant = False

# دعم البناء المتوازي
android.gradle_parallel = True

# طلب التوقيع للتطبيق
android.debug = True
android.release = False

# ملف التوقيع (للتوزيع)
android.keystore = 
android.keystore_password = 
android.keystore_alias = 
android.keystore_alias_password = 

# إعدادات البناء
build.max_processes = 4
build.log = True
build.verbose = False

# دعم الحزم الخاصة
ios.codesign.allowed = False
ios.codesign.debug = 
ios.codesign.release = 

# إعدادات التوزيع
dist.name = youtubedownloader

[buildozer]

# إعدادات البناء العامة
log_level = 2
warn_on_root = True

# الأنظمة المستهدفة
osx.python_version = 3
osx.kivy_version = 2.1.0

# إعدادات Windows
win.python_version = 3
win.kivy_version = 2.1.0

# إعدادات الأندرويد
android.python_version = 3
android.kivy_version = 2.1.0

# إعدادات iOS
ios.python_version = 3
ios.kivy_version = 2.1.0

# مسارات الأدوات
android.sdk_path = 
android.ndk_path = 
android.ant_path = 

# إعدادات المحاكي
android.emulator_path = 
android.emulator_avd = 

# إعدادات التصحيح
android.debug = 1
android.release = 0
