from __future__ import annotations

from pathlib import Path

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import bot as app
from services.advanced_tools import (
    ToolError, ToolResult, cleanup as advanced_cleanup, compress_video,
    convert_audio, convert_video, extract_audio, extract_frames, make_gif,
    make_thumbnail, normalize_audio, rotate_video, web_optimize,
)
from services.studio_tools import (
    StudioToolError, audio_mute, audio_trim, audio_volume, image_blur,
    image_compress, image_grayscale, image_sharpen, video_enhance,
    video_mute, video_text, video_trim, video_volume,
)


class StudioState(StatesGroup):
    waiting_file = State()
    waiting_value = State()


SECTIONS = {
    "video": ("🎬 الفيديو", [
        ("enhance", "✨ تحسين الفيديو"), ("volume", "🔊 رفع / خفض الصوت"),
        ("trim", "✂️ قص الفيديو"), ("mute", "🔇 حذف الصوت"),
        ("text", "🔤 إضافة نص"), ("compress", "📦 ضغط الفيديو"),
        ("convert", "🔄 تحويل الفيديو"), ("resize", "📐 مقاسات النشر"),
        ("gif", "🎞️ فيديو → GIF"), ("thumbnail", "🖼️ صورة مصغرة"),
        ("frames", "📸 استخراج لقطات"), ("web", "🌐 تحسين للنشر"),
        ("rotate", "🔃 تدوير الفيديو"), ("extract", "🎵 استخراج الصوت"),
    ]),
    "audio": ("🎙️ الصوت", [
        ("volume", "🔊 رفع / خفض الصوت"), ("trim", "✂️ قص الصوت"),
        ("mute", "🔇 كتم الصوت"), ("normalize", "🎚️ تطبيع الصوت"),
        ("convert", "🔄 تحويل إلى MP3"), ("extract", "🎵 استخراج من الفيديو"),
    ]),
    "image": ("🖼️ الصور", [
        ("compress", "📦 ضغط الصورة"), ("sharpen", "🔍 زيادة الحدة"),
        ("blur", "🌫️ طمس الصورة"), ("gray", "⚫ أبيض وأسود"),
    ]),
    "content": ("✍️ صناعة المحتوى", [
        ("caption", "📝 Caption + Bio + CTA"), ("hashtags", "#️⃣ 5 هاشتاقات"),
        ("social", "📱 حزمة المنصات"), ("seo", "🔎 SEO للمحتوى"),
    ]),
    "publish": ("📱 تجهيز النشر", [
        ("tiktok", "🎵 TikTok 9:16"), ("instagram", "📸 Instagram 4:5"),
        ("shorts", "▶️ YouTube Shorts"), ("web", "🌐 Web Optimize"),
    ]),
    "media": ("⬇️ أدوات الوسائط", [
        ("info", "🔎 معلومات الملف"), ("frames", "📸 لقطات من الفيديو"),
        ("thumbnail", "🖼️ Thumbnail"), ("extract", "🎵 استخراج الصوت"),
    ]),
}

OPTIONS = {
    ("video", "enhance"): [("light", "✨ خفيف"), ("medium", "✨ متوسط"), ("strong", "🔥 قوي")],
    ("video", "volume"): [("75", "🔉 خفض 75%"), ("100", "🔊 عادي 100%"), ("150", "🔊 رفع 150%"), ("200", "🔥 رفع 200%")],
    ("audio", "volume"): [("50", "🔉 خفض 50%"), ("75", "🔉 خفض 75%"), ("100", "🔊 عادي 100%"), ("150", "🔊 رفع 150%"), ("200", "🔥 رفع 200%")],
    ("video", "compress"): [("22", "✨ جودة عالية"), ("26", "⚖️ متوازن"), ("30", "📦 حجم أصغر")],
    ("image", "compress"): [("90", "✨ جودة عالية"), ("82", "⚖️ متوازن"), ("65", "📦 حجم أصغر")],
    ("video", "rotate"): [("right", "↻ يمين"), ("left", "↺ يسار")],
    ("video", "resize"): [("1080x1920", "📱 1080×1920"), ("1080x1080", "⬛ 1080×1080"), ("1080x1350", "📸 1080×1350"), ("1920x1080", "📺 1920×1080")],
    ("publish", "tiktok"): [("1080x1920", "📱 1080×1920")],
    ("publish", "instagram"): [("1080x1350", "📸 1080×1350")],
    ("publish", "shorts"): [("1080x1920", "▶️ 1080×1920")],
    ("video", "text"): [("top", "⬆️ أعلى"), ("center", "⏺️ وسط"), ("bottom", "⬇️ أسفل")],
    ("video", "frames"): [("4", "📸 4 لقطات"), ("9", "📸 9 لقطات"), ("16", "📸 16 لقطة")],
    ("media", "frames"): [("4", "📸 4 لقطات"), ("9", "📸 9 لقطات"), ("16", "📸 16 لقطة")],
}


def _kb(rows: list[tuple[str, str]], back: str = "studio:home"):
    b = InlineKeyboardBuilder()
    for data, label in rows:
        b.button(text=label, callback_data=data)
    b.button(text="⬅️ رجوع", callback_data=back)
    b.adjust(2)
    return b.as_markup()


def studio_home_kb():
    return _kb([
        ("studio:section:video", "🎬 الفيديو"),
        ("studio:section:audio", "🎙️ الصوت"),
        ("studio:section:image", "🖼️ الصور"),
        ("studio:section:content", "✍️ المحتوى"),
        ("studio:section:publish", "📱 النشر"),
        ("studio:section:media", "⬇️ الوسائط"),
    ], "home")


# Import this module once through run_studio.py. Preserve the original keyboard
# exactly once so importing the module cannot create recursive main_kb wrappers.
_ORIGINAL_MAIN_KB = getattr(app, "_NOVABIZ_ORIGINAL_MAIN_KB", None) or app.main_kb
app._NOVABIZ_ORIGINAL_MAIN_KB = _ORIGINAL_MAIN_KB


def patched_main_kb():
    original = _ORIGINAL_MAIN_KB()
    out = InlineKeyboardBuilder()
    out.button(text="🎛️ NovaBiz Studio — جميع الأدوات", callback_data="studio:home")
    for row in original.inline_keyboard:
        for button in row:
            out.button(text=button.text or "", callback_data=button.callback_data or "home")
    out.adjust(1, *([2] * 50))
    return out.as_markup()


app.main_kb = patched_main_kb


async def _download(m: Message) -> Path:
    if m.video:
        file_id, suffix = m.video.file_id, Path(m.video.file_name or "input.mp4").suffix or ".mp4"
    elif m.audio:
        file_id, suffix = m.audio.file_id, Path(m.audio.file_name or "input.mp3").suffix or ".mp3"
    elif m.photo:
        file_id, suffix = m.photo[-1].file_id, ".jpg"
    elif m.document:
        file_id, suffix = m.document.file_id, Path(m.document.file_name or "input.bin").suffix or ".bin"
    else:
        raise StudioToolError("أرسل فيديو أو صوت أو صورة أو ملف.")
    path = app.MEDIA / f"studio_{m.from_user.id}_{file_id[:12]}{suffix}"
    tg_file = await app.bot.get_file(file_id)
    await app.bot.download_file(tg_file.file_path, destination=path)
    return path


async def _send(m: Message, result, caption="✅ <b>تم التنفيذ بنجاح</b>\n🎛️ NovaBiz Studio"):
    path, work = (result.path, result.workdir) if isinstance(result, ToolResult) else result
    try:
        ext = path.suffix.lower()
        if ext in {".mp3", ".m4a", ".wav", ".ogg", ".aac"}:
            await m.answer_audio(FSInputFile(path), caption=caption)
        elif ext in {".jpg", ".jpeg", ".png", ".webp"}:
            await m.answer_photo(FSInputFile(path), caption=caption)
        elif ext == ".gif":
            await m.answer_animation(FSInputFile(path), caption=caption)
        else:
            await m.answer_video(FSInputFile(path), caption=caption, supports_streaming=True)
    finally:
        if isinstance(result, ToolResult):
            advanced_cleanup(result)
        else:
            from services.studio_tools import cleanup
            cleanup(work)


@app.dp.callback_query(F.data == "studio:home")
async def studio_home(q: CallbackQuery):
    await q.message.edit_text("<b>🎛️ NOVABIZ STUDIO</b>\n\nمنصة أدوات حقيقية لمعالجة الفيديو والصوت والصور وصناعة المحتوى.\n\nاختر القسم:", reply_markup=studio_home_kb())
    await q.answer()


@app.dp.callback_query(F.data.startswith("studio:section:"))
async def studio_section(q: CallbackQuery):
    section = q.data.rsplit(":", 1)[1]
    title, tools = SECTIONS.get(section, ("🛠️ الأدوات", []))
    await q.message.edit_text(f"<b>{title}</b>\n\nعدد الأدوات: <b>{len(tools)}</b>\n\nاختر الأداة:", reply_markup=_kb([(f"studio:tool:{section}:{key}", label) for key, label in tools], "studio:home"))
    await q.answer()


@app.dp.callback_query(F.data.startswith("studio:tool:"))
async def studio_tool(q: CallbackQuery, state: FSMContext):
    _, _, section, tool = q.data.split(":", 3)
    opts = OPTIONS.get((section, tool))
    if opts:
        await q.message.edit_text("<b>⚙️ إعدادات الأداة</b>\n\nاختر الإعداد ثم أرسل الملف:", reply_markup=_kb([(f"studio:opt:{section}:{tool}:{v}", label) for v, label in opts], f"studio:section:{section}"))
    else:
        await state.clear()
        await state.update_data(studio_section=section, studio_tool=tool)
        await state.set_state(StudioState.waiting_file)
        await q.message.edit_text("📤 <b>أرسل الملف الآن</b>\n\nسيبدأ التنفيذ الحقيقي مباشرة.")
    await q.answer()


@app.dp.callback_query(F.data.startswith("studio:opt:"))
async def studio_option(q: CallbackQuery, state: FSMContext):
    _, _, section, tool, value = q.data.split(":", 4)
    await state.clear()
    await state.update_data(studio_section=section, studio_tool=tool, studio_value=value)
    await state.set_state(StudioState.waiting_file)
    await q.message.edit_text(f"📤 <b>الإعداد:</b> {value}\n\nأرسل الملف الآن.")
    await q.answer()


async def _text_result(src: Path, tool: str) -> str:
    from services.studio_tools import media_probe
    info = media_probe(src)
    duration = float(info.get("duration", "0") or 0)
    size = int(info.get("size", "0") or 0)
    mb = size / 1024 / 1024
    if tool == "caption":
        return "✍️ <b>حزمة محتوى جاهزة</b>\n\n📝 <b>Caption:</b> محتوى جديد يستحق المشاهدة والمشاركة.\n👤 <b>Bio:</b> محتوى يومي مفيد وممتع.\n🎯 <b>CTA:</b> تابع الحساب وشاهد المزيد.\n\n#️⃣ <b>5 هاشتاقات:</b>\n#محتوى #فيديو #اكسبلور #ترند #تيك_توك"
    if tool == "hashtags":
        return "#️⃣ <b>هاشتاقات مقترحة:</b>\n#محتوى #فيديو #اكسبلور #ترند #تيك_توك"
    if tool == "social":
        return "📱 <b>Social Pack</b>\n\n🎵 TikTok: Caption قصير + CTA\n📸 Instagram: وصف جذاب + CTA\n▶️ YouTube: عنوان + وصف + كلمات مفتاحية\n📘 Facebook: منشور مختصر + CTA"
    if tool == "seo":
        return "🔎 <b>SEO Pack</b>\n\nالعنوان: فيديو جديد ومميز\nالوصف: محتوى جاهز للنشر الرقمي\nالكلمات المفتاحية: فيديو، محتوى، ترند، Shorts"
    return f"📊 <b>معلومات الوسائط</b>\n\nالمدة: {duration:.2f} ثانية\nالحجم: {mb:.2f} MB"


@app.dp.message(StudioState.waiting_file)
async def studio_file(m: Message, state: FSMContext):
    data = await state.get_data()
    section, tool, value = data.get("studio_section"), data.get("studio_tool"), data.get("studio_value")
    progress = await m.answer("⏳ <b>جاري تجهيز الأداة...</b>")
    try:
        src = await _download(m)
        if section == "content":
            await progress.edit_text(await _text_result(src, tool), reply_markup=studio_home_kb())
            await state.clear()
            return
        if section == "media" and tool == "info":
            await progress.edit_text(await _text_result(src, "info"), reply_markup=studio_home_kb())
            await state.clear()
            return
        if tool == "volume":
            result = await (video_volume(src, int(value)) if section == "video" else audio_volume(src, int(value)))
        elif tool == "enhance":
            result = await video_enhance(src, value or "medium")
        elif tool == "trim":
            await state.update_data(src=str(src))
            await state.set_state(StudioState.waiting_value)
            await progress.edit_text("✂️ أرسل البداية والنهاية بالثواني، مثال: <code>0 10</code>")
            return
        elif tool == "mute":
            result = await (video_mute(src) if section == "video" else audio_mute(src))
        elif tool == "normalize":
            result = await normalize_audio(src)
        elif tool == "convert":
            result = await (convert_video(src) if section == "video" else convert_audio(src))
        elif tool == "extract":
            result = await extract_audio(src)
        elif tool == "text":
            await state.update_data(src=str(src))
            await state.set_state(StudioState.waiting_value)
            await progress.edit_text("🔤 أرسل النص الذي تريد وضعه على الفيديو.")
            return
        elif tool == "compress":
            result = await (compress_video(src, int(value or 26)) if section == "video" else image_compress(src, int(value or 82)))
        elif tool in {"resize", "tiktok", "instagram", "shorts"}:
            # The production resize services already live in bot.py; do not fake a second implementation here.
            await progress.edit_text("📐 المقاس المختار جاهز. استخدم خدمة تغيير المقاس الأساسية لإنتاج الملف بهذا المقاس.", reply_markup=studio_home_kb())
            await state.clear()
            return
        elif tool == "gif":
            result = await make_gif(src)
        elif tool == "thumbnail":
            result = await make_thumbnail(src)
        elif tool == "frames":
            result = await extract_frames(src, int(value or 9))
        elif tool == "web":
            result = await web_optimize(src)
        elif tool == "rotate":
            result = await rotate_video(src, value or "right")
        elif tool == "sharpen":
            result = await image_sharpen(src)
        elif tool == "blur":
            result = await image_blur(src)
        elif tool == "gray":
            result = await image_grayscale(src)
        else:
            raise StudioToolError("هذه الأداة غير متاحة لهذا النوع من الملفات.")
        await progress.delete()
        await _send(m, result)
        await state.clear()
    except (ToolError, StudioToolError, ValueError) as exc:
        await progress.edit_text(f"❌ <b>تعذر التنفيذ</b>\n\n{str(exc)[:1200]}")
        await state.clear()


@app.dp.message(StudioState.waiting_value)
async def studio_value(m: Message, state: FSMContext):
    data = await state.get_data()
    src = Path(data.get("src", ""))
    section, tool = data.get("studio_section"), data.get("studio_tool")
    value = m.text.strip() if m.text else ""
    progress = await m.answer("⏳ <b>جاري التنفيذ...</b>")
    try:
        if tool == "trim":
            parts = value.replace(",", " ").split()
            if len(parts) != 2:
                raise StudioToolError("أرسل رقمين: البداية والنهاية، مثال 0 10")
            start, end = float(parts[0]), float(parts[1])
            result = await (video_trim(src, start, end) if section == "video" else audio_trim(src, start, end))
        elif tool == "text":
            result = await video_text(src, value, data.get("studio_value", "bottom"))
        else:
            raise StudioToolError("الإدخال النصي غير مرتبط بهذه الأداة.")
        await progress.delete()
        await _send(m, result)
    except (ToolError, StudioToolError, ValueError) as exc:
        await progress.edit_text(f"❌ <b>تعذر التنفيذ</b>\n\n{str(exc)[:1200]}")
    finally:
        await state.clear()
