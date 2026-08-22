from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import bot as app
from services.advanced_tools import ToolError, ToolResult, cleanup as tool_cleanup, compress_video, convert_audio, convert_video, extract_audio, extract_frames, make_gif, make_thumbnail, normalize_audio, rotate_video, web_optimize
from services.studio_tools import StudioToolError, audio_mute, audio_trim, audio_volume, image_blur, image_compress, image_grayscale, image_sharpen, video_enhance, video_mute, video_trim, video_volume


class StudioState(StatesGroup):
    waiting_file = State()
    waiting_value = State()


CATEGORIES = {
    "audio": ("🎙️ استوديو الصوت", [("volume", "🔊 رفع / خفض الصوت"), ("trim", "✂️ قص الصوت"), ("mute", "🔇 حذف الصوت"), ("normalize", "🎚️ تسوية مستوى الصوت"), ("convert", "🔄 تحويل الصوت"), ("extract", "🎵 استخراج الصوت من الفيديو")]),
    "video": ("🎬 استوديو الفيديو", [("enhance", "✨ تحسين الفيديو"), ("text", "🔤 إضافة نص للفيديو"), ("trim", "✂️ قص الفيديو"), ("volume", "🔊 رفع / خفض صوت الفيديو"), ("mute", "🔇 حذف صوت الفيديو"), ("compress", "📦 ضغط الفيديو"), ("convert", "🔄 تحويل الفيديو"), ("resize", "📐 تغيير المقاس"), ("gif", "🎞️ تحويل إلى GIF"), ("thumbnail", "🖼️ استخراج صورة مصغرة"), ("frames", "📸 استخراج لقطات"), ("web", "🌐 تجهيز للنشر"), ("rotate", "🔃 تدوير الفيديو"), ("extract", "🎵 استخراج الصوت")]),
    "image": ("🖼️ استوديو الصور", [("compress", "📦 ضغط الصورة"), ("sharpen", "🔍 زيادة الحدة"), ("blur", "🌫️ طمس الصورة"), ("gray", "⚫ أبيض وأسود"), ("resize", "📐 تغيير المقاس"), ("convert", "🔄 تحويل الصيغة"), ("enhance", "✨ تحسين الصورة")]),
    "ai": ("🤖 استوديو الذكاء الاصطناعي", [("description", "🧠 تحليل ووصف الفيديو"), ("caption", "✍️ وصف + Bio + CTA + 5 هاشتاقات"), ("social", "📱 حزمة TikTok / Instagram / YouTube"), ("seo", "🔎 عنوان ووصف وكلمات مفتاحية")]),
}


def kb(rows: list[tuple[str, str]], back: str = "studio:home"):
    b = InlineKeyboardBuilder()
    for data, text in rows:
        b.button(text=text, callback_data=data)
    b.button(text="⬅️ رجوع", callback_data=back)
    b.adjust(2)
    return b.as_markup()


def studio_kb():
    return kb([("studio:cat:video", "🎬 الفيديو"), ("studio:cat:audio", "🎙️ الصوت"), ("studio:cat:image", "🖼️ الصور"), ("studio:cat:ai", "🤖 الذكاء الاصطناعي")], "home")


_ORIGINAL_MAIN_KB = app.main_kb


def patched_main_kb():
    original = _ORIGINAL_MAIN_KB()
    out = InlineKeyboardBuilder()
    out.button(text="🎛️ Pro Studio — كل الأدوات", callback_data="studio:home")
    for row in original.inline_keyboard:
        for button in row:
            out.button(text=button.text or "", callback_data=button.callback_data or "home")
    out.adjust(1, *([2] * 50))
    return out.as_markup()


app.main_kb = patched_main_kb


async def _download(m: Message) -> Path:
    if m.photo:
        file_id, suffix = m.photo[-1].file_id, ".jpg"
    elif m.video:
        file_id, suffix = m.video.file_id, Path(m.video.file_name or "input.mp4").suffix or ".mp4"
    elif m.audio:
        file_id, suffix = m.audio.file_id, Path(m.audio.file_name or "input.mp3").suffix or ".mp3"
    elif m.document:
        file_id, suffix = m.document.file_id, Path(m.document.file_name or "input.bin").suffix or ".bin"
    else:
        raise StudioToolError("أرسل فيديو أو ملف صوتي أو صورة.")
    path = app.MEDIA / f"studio_{m.from_user.id}_{file_id[:10]}{suffix}"
    tg_file = await app.bot.get_file(file_id)
    await app.bot.download_file(tg_file.file_path, destination=path)
    return path


async def _send_result(m: Message, result: ToolResult | tuple[Path, Path], caption: str):
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
            tool_cleanup(result)
        else:
            from services.studio_tools import cleanup
            cleanup(work)


@app.dp.callback_query(F.data == "studio:home")
async def studio_home(q: CallbackQuery):
    await q.message.edit_text("<b>🎛️ NovaBiz Pro Studio</b>\n\nكل قسم يحتوي أدوات فعلية وخياراتها الخاصة.\nاختر القسم:", reply_markup=studio_kb())
    await q.answer()


@app.dp.callback_query(F.data.startswith("studio:cat:"))
async def studio_category(q: CallbackQuery):
    cat = q.data.rsplit(":", 1)[1]
    title, tools = CATEGORIES.get(cat, ("🛠️ الأدوات", []))
    await q.message.edit_text(f"<b>{title}</b>\n\nاختر الأداة:", reply_markup=kb([(f"studio:tool:{cat}:{key}", label) for key, label in tools]))
    await q.answer()


OPTIONS = {
    ("video", "enhance"): [("studio:opt:video:enhance:light", "✨ خفيف"), ("studio:opt:video:enhance:medium", "✨ متوسط"), ("studio:opt:video:enhance:strong", "🔥 قوي")],
    ("video", "volume"): [("studio:opt:video:volume:150", "🔊 رفع 150%"), ("studio:opt:video:volume:75", "🔉 خفض 75%"), ("studio:opt:video:volume:200", "🔊 رفع 200%")],
    ("audio", "volume"): [("studio:opt:audio:volume:150", "🔊 رفع 150%"), ("studio:opt:audio:volume:75", "🔉 خفض 75%"), ("studio:opt:audio:volume:200", "🔊 رفع 200%")],
    ("video", "compress"): [("studio:opt:video:compress:26", "📦 متوسط"), ("studio:opt:video:compress:30", "📦 قوي"), ("studio:opt:video:compress:22", "✨ جودة أعلى")],
}


@app.dp.callback_query(F.data.startswith("studio:tool:"))
async def studio_tool(q: CallbackQuery, state: FSMContext):
    _, _, cat, tool = q.data.split(":", 3)
    options = OPTIONS.get((cat, tool))
    if options:
        await q.message.edit_text("⚙️ اختر الإعداد:", reply_markup=kb(options, f"studio:cat:{cat}"))
    else:
        await state.clear()
        await state.update_data(studio_cat=cat, studio_tool=tool)
        await state.set_state(StudioState.waiting_file)
        await q.message.edit_text("📤 أرسل الملف الآن لتنفيذ الأداة فعلياً.")
    await q.answer()


@app.dp.callback_query(F.data.startswith("studio:opt:"))
async def studio_option(q: CallbackQuery, state: FSMContext):
    _, _, cat, tool, value = q.data.split(":", 4)
    await state.update_data(studio_cat=cat, studio_tool=tool, studio_value=value)
    await state.set_state(StudioState.waiting_file)
    await q.message.edit_text("📤 أرسل الملف الآن وسأطبق الإعداد الذي اخترته.")
    await q.answer()


@app.dp.message(StudioState.waiting_file)
async def studio_file(m: Message, state: FSMContext):
    data = await state.get_data()
    cat, tool, value = data.get("studio_cat"), data.get("studio_tool"), data.get("studio_value")
    progress = await m.answer("⏳ <b>جاري التنفيذ...</b>")
    src = None
    try:
        src = await _download(m)
        if tool == "volume":
            result = await (video_volume(src, int(value)) if cat == "video" else audio_volume(src, int(value)))
        elif tool == "trim":
            await state.update_data(src=str(src))
            await state.set_state(StudioState.waiting_value)
            return await progress.edit_text("✂️ أرسل البداية والنهاية بالثواني، مثال: <code>0 10</code>")
        elif tool == "mute":
            result = await (video_mute(src) if cat == "video" else audio_mute(src))
        elif tool == "normalize":
            result = await normalize_audio(src)
        elif tool == "convert":
            result = await (convert_video(src) if cat == "video" else convert_audio(src))
        elif tool == "extract":
            result = await extract_audio(src)
        elif tool == "enhance":
            result = await video_enhance(src, value or "medium")
        elif tool == "compress":
            result = await compress_video(src, int(value or 26))
        elif tool == "gif":
            result = await make_gif(src)
        elif tool == "thumbnail":
            result = await make_thumbnail(src)
        elif tool == "frames":
            result = await extract_frames(src, 9)
        elif tool == "web":
            result = await web_optimize(src)
        elif tool == "rotate":
            result = await rotate_video(src, "right")
        elif cat == "image" and tool == "compress":
            result = await image_compress(src)
        elif cat == "image" and tool == "sharpen":
            result = await image_sharpen(src)
        elif cat == "image" and tool == "blur":
            result = await image_blur(src)
        elif cat == "image" and tool == "gray":
            result = await image_grayscale(src)
        elif tool == "resize":
            result = await convert_video(src) if cat == "video" else image_compress(src)
        elif tool in {"description", "caption", "social", "seo"}:
            from services.advanced_tools import media_info
            info = media_info(src)
            duration = float(info.get("duration", "0"))
            size = int(info.get("size", "0"))
            if tool == "description":
                text = f"🧠 <b>تحليل الوسائط</b>\n\nالمدة: {duration:.1f} ثانية\nالحجم: {size/1024/1024:.2f} MB\n\nتم فحص خصائص الملف بنجاح."
            elif tool == "caption":
                text = "✍️ <b>حزمة المحتوى</b>\n\n<b>الوصف:</b> محتوى جاهز للنشر.\n<b>Bio:</b> محتوى جديد يستحق المشاهدة والمتابعة.\n<b>CTA:</b> تابع الحساب للمزيد.\n\n<b>5 هاشتاقات:</b>\n#محتوى #فيديو #اكسبلور #تيك_توك #ترند"
            elif tool == "social":
                text = "📱 <b>Social Pack</b>\n\nTikTok: وصف قصير + CTA\nInstagram: وصف جذاب + CTA\nYouTube: عنوان + وصف\nFacebook: منشور مختصر + CTA"
            else:
                text = "🔎 <b>SEO Pack</b>\n\nالعنوان: محتوى فيديو جديد ومميز\nالوصف: فيديو مناسب للنشر الرقمي\nالكلمات المفتاحية: فيديو، محتوى، ترفيه، تعليم، Shorts"
            await progress.edit_text(text, reply_markup=studio_kb())
            return
        elif tool == "text":
            await state.update_data(src=str(src))
            await state.set_state(StudioState.waiting_value)
            return await progress.edit_text("🔤 أرسل النص المطلوب وضعه على الفيديو.")
        else:
            raise StudioToolError("الأداة غير مدعومة لهذا النوع من الملفات.")
        await progress.delete()
        await _send_result(m, result, "✅ <b>تم التنفيذ بنجاح</b>\n🎛️ NovaBiz Pro Studio")
    except (ToolError, StudioToolError) as e:
        await progress.edit_text(f"❌ <b>فشل التنفيذ</b>\n\n{str(e)[:1200]}")
    except Exception as e:
        await progress.edit_text(f"❌ <b>حدث خطأ غير متوقع</b>\n\n{type(e).__name__}: {str(e)[:900]}")
    finally:
        if src and src.exists() and data.get("studio_tool") not in {"trim", "text"}:
            src.unlink(missing_ok=True)
        if data.get("studio_tool") not in {"trim", "text"}:
            await state.clear()


@app.dp.message(StudioState.waiting_value)
async def studio_value(m: Message, state: FSMContext):
    data = await state.get_data()
    src = Path(data["src"])
    try:
        if data.get("studio_tool") == "text":
            result = await video_text(src, m.text or "", "bottom")
        else:
            start, end = [float(x) for x in (m.text or "").replace(",", " ").split()[:2]]
            result = await (audio_trim(src, start, end) if data.get("studio_cat") == "audio" else video_trim(src, start, end))
        await _send_result(m, result, "✅ <b>تم التنفيذ بنجاح</b>\n🎛️ NovaBiz Pro Studio")
    except Exception as e:
        await m.answer(f"❌ خطأ: {str(e)[:1200]}")
    finally:
        src.unlink(missing_ok=True)
        await state.clear()


async def main() -> None:
    await app.main()


if __name__ == "__main__":
    asyncio.run(main())
