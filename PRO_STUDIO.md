# NovaBiz Pro Studio

## التشغيل

```bash
cd ~/NovaAds/NovaAds
source venv/bin/activate
set -a
source .env
set +a
python run_upgraded.py
```

## الخدمات

- ضغط فيديو Pro
- تحويل فيديو عالي الجودة إلى MP4
- تحويل فيديو إلى GIF
- استخراج غلاف HD
- استخراج لقطات
- إزالة صوت الفيديو
- تجهيز الفيديو للنشر عبر H.264 + faststart
- تدوير الفيديو
- استخراج الصوت MP3
- تحويل الصوت إلى MP3
- تحسين مستوى الصوت Loudness
- معلومات الملف عبر ffprobe

كل عملية تستخدم Job ID، وتخصم رصيداً واحداً، وتعيد الرصيد تلقائياً عند الفشل.

زر **⚡ Pro Studio** يظهر في لوحة NovaBiz الرئيسية عند تشغيل `run_upgraded.py`.
