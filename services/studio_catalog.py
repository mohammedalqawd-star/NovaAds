"""Catalog of grouped Studio services and their option buttons."""

STUDIO_CATEGORIES = {
    "audio": {
        "title": "🎙️ استوديو الصوت",
        "tools": {
            "audio_volume": ("🔊 رفع/خفض الصوت", ["🔊 150%", "🔉 75%", "🔇 كتم الصوت"]),
            "audio_trim": ("✂️ قص الصوت", ["⏱️ تحديد البداية والنهاية"]),
            "audio_convert": ("🔄 تحويل الصوت", ["MP3", "M4A", "WAV", "AAC", "OGG"]),
            "audio_clean": ("🧹 تحسين الصوت", ["تنقية", "تطبيع", "رفع الوضوح"]),
            "audio_extract": ("🎵 استخراج الصوت", ["MP3", "M4A", "WAV"]),
        },
    },
    "video": {
        "title": "🎬 استوديو الفيديو",
        "tools": {
            "video_enhance": ("✨ تحسين الفيديو", ["خفيف", "متوسط", "قوي"]),
            "video_text": ("🔤 إضافة نص للفيديو", ["أعلى", "وسط", "أسفل"]),
            "video_trim": ("✂️ قص الفيديو", ["تحديد البداية والنهاية"]),
            "video_volume": ("🔊 صوت الفيديو", ["رفع", "خفض", "كتم"]),
            "video_resize": ("📐 تغيير المقاس", ["1080p", "720p", "1080×1920", "1080×1080"]),
            "video_compress": ("📦 ضغط الفيديو", ["خفيف", "متوسط", "قوي"]),
            "video_convert": ("🔄 تحويل الفيديو", ["MP4", "MOV", "WEBM", "MKV"]),
            "video_gif": ("🎞️ GIF", ["جودة عادية", "جودة عالية"]),
            "video_thumbnail": ("🖼️ صورة مصغرة", ["تلقائي", "اختيار لقطة"]),
            "video_frames": ("📸 استخراج اللقطات", ["5", "10", "20"]),
            "video_description": ("🧠 فهم وشرح الفيديو", ["ملخص", "شرح مفصل", "نقاط مهمة"]),
            "video_caption": ("📝 تجهيز محتوى الفيديو", ["وصف", "Bio", "CTA", "5 هاشتاقات"]),
        },
    },
    "image": {
        "title": "🖼️ استوديو الصور",
        "tools": {
            "image_compress": ("📦 ضغط الصورة", ["خفيف", "متوسط", "قوي"]),
            "image_resize": ("📐 تغيير المقاس", ["1080×1080", "1080×1350", "1920×1080", "1080×1920"]),
            "image_convert": ("🔄 تحويل الصيغة", ["JPG", "PNG", "WEBP"]),
            "image_enhance": ("✨ تحسين الصورة", ["خفيف", "متوسط", "قوي"]),
            "image_sharpen": ("🔍 زيادة الحدة", ["خفيف", "متوسط"]),
            "image_blur": ("🌫️ طمس", ["خفيف", "متوسط", "قوي"]),
            "image_gray": ("⚫ أبيض وأسود", ["تطبيق"]),
            "image_thumbnail": ("🖼️ صورة مصغرة", ["YouTube", "TikTok", "Instagram"]),
        },
    },
    "ai": {
        "title": "🤖 أدوات الذكاء الاصطناعي",
        "tools": {
            "video_understanding": ("🧠 فهم الفيديو", ["ملخص", "شرح", "مشاهد مهمة"]),
            "content_writer": ("✍️ كتابة المحتوى", ["وصف", "Bio", "عنوان", "CTA", "5 هاشتاقات"]),
            "social_pack": ("📱 حزمة السوشيال", ["TikTok", "Instagram", "YouTube", "Facebook"]),
            "seo": ("🔎 SEO", ["كلمات مفتاحية", "عنوان SEO", "وصف SEO"]),
        },
    },
}


def category_buttons(category: str) -> list[tuple[str, str, list[str]]]:
    data = STUDIO_CATEGORIES.get(category, {"tools": {}})
    return [(key, label, options) for key, (label, options) in data["tools"].items()]
