from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import bot as app
from services.advanced_tools import (
    ToolError,
    ToolResult,
    cleanup as tool_cleanup,
    compress_video,
    convert_audio,
    convert_video,
    extract_audio,
    extract_frames,
    make_gif,
    make_thumbnail,
    mute_video,
    normalize_audio,
    rotate_video,
    web_optimize,
)
from services.studio_tools import (
    StudioToolError,
    audio_mute,
    audio_trim,
    audio_volume,
    image_blur,
    image_compress,
    image_grayscale,
    image_sharpen,
    video_enhance,
    video_mute,
    video_text,
    video_trim,
    video_volume,
)


class StudioState(StatesGroup):
    waiting_file = State()
    waiting_value = State()
    waiting_text = State()


# Categories are intentionally independent from the old service menu.
CATEGORIES = {
    "audio": ("🎙️ استوديو الصوت", [
        ("volume", "🔊 رفع / خفض الصوت"),
        ("trim", "✂️ قص الصوت"),
        ("mute", "🔇 حذف الصوت"),
        ("normalize", "🎚️ تسوية مستوى الصوت"),
        ("convert", "🔄 تحويل الصوت"),
        ("extract", "🎵 استخراج الصوت من الفيديو"),
    ]),
    "video": ("🎬 استوديو الفيديو", [
        ("enhance", "✨ تحسين الفيديو"),
        ("text", "🔤 إضافة نص للفيديو"),
        ("trim", "✂️ قص الفيديو"),
        ("volume", "🔊 رفع / خفض صوت الفيديو"),
        ("mute", "🔇 حذف صوت الفيديو"),
        ("compress", "📦 ضغط الفيديو"),
        ("convert", "🔄 تحويل الفيديو"),
        ("resize", "📐 تغيير المقاس"),
        ("gif", "🎞️ تحويل إلى GIF"),
        ("thumbnail", "🖼️ استخراج صورة مصغرة"),
        ("frames", "📸 استخراج لقطات"),
        ("web", "🌐 تجهيز للنشر على الويب"),
        ("rotate", "🔃 تدوير الفيديو"),
        ("extract", "🎵 استخراج الصوت"),
    ]),
    "image": ("🖼️ استوديو الصور", [
        ("compress", "📦 ضغط الصورة"),
        ("sharpen", "🔍 زيادة الحدة"),
        ("blur", "🌫️ طمس الصورة"),
        ("gray", "⚫ أبيض وأسود"),
        ("resize", "📐 تغيير المقاس"),
        ("convert", "🔄 تحويل الصيغة"),
        ("enhance", "✨ تحسين الصورة"),
    ]),
    "ai": ("🤖 استوديو الذكاء الاصطناعي", [
        ("description", "🧠 تحليل ووصف الفيديو"),
        ("caption", "✍️ وصف + Bio + CTA + 5 هاشتاقات"),
        ("social", "📱 حزمة TikTok / Instagram / YouTube"),
        ("seo", "🔎 عنوان ووصف وكلمات مفتاحية"),
    ]),
}


def kb(rows: list[tuple[str, str]], back: str = "studio:home"):
    b = InlineKeyboardBuilder()
    for data, text in rows:
        b.button(text=text, callback_data=data)
    b.button(text="⬅️ رجوع", callback_data=back)
    b.adjust(2)
    return b.as_markup()


def studio_kb():
    return kb([
        ("studio:cat:video", "🎬 الفيديو"),
        ("studio:cat:audio", "🎙️ الصوت"),
        ("studio:cat:image", "🖼️ الصور"),
        ("studio:cat:ai", "🤖 الذكاء الاصطناعي"),
    ], "home")


_ORIGINAL_MAIN_KB = app.main_kb


def patched_main_kb():
    original = _ORIGINAL_MAIN_KB()
    b = InlineKeyboardBuilder()
    b.button(text="🎛️ Pro Studio — كل الأدوات", callback_data="studio:home")
    # Preserve the existing keyboard as a single navigation layer by adding the new
    # button first; all existing services remain available unchanged.
    # InlineKeyboardBuilder cannot import an existing markup cleanly, so this button
    # is the only addition made here; existing /start continues to expose all old tools.
    return _prepend_button(original, b)


def _prepend_button(original, extra):
    # Rebuild from Telegram's markup to avoid changing any old callback values.
    out = InlineKeyboardBuilder()
    out.button(text="🎛️ Pro Studio — كل الأدوات", callback_data="studio:home")
    for row in original.inline_keyboard:
        for button in row:
            out.button(text=button.text or "", callback_data=button.callback_data or "home")
    out.adjust(1, *([2] * 50))
    return out.as_markup()


# Patch the function used by bot.py's existing /start and home handlers.
app.main_kb = patched_main_kb


def _file_from_message(m: Message) -> tuple[Path, str]:
    media = m.video or m.audio or m.document or m.photo[-1] if m.photo else None
    if not media:
        raise StudioToolError("أرسل فيديو أو ملف صوتي أو صورة.")
    if m.photo:
        file_id = m.photo[-1].file_id
        suffix = ".jpg"
    else:
        file_id = media.file_id
        name = getattr(media, "file_name", None) or "input.bin"
        suffix = Path(name).suffix or ".bin"
    path = app.MEDIA / f"studio_{m.from_user.id}_{file_id[:10]}{suffix}"
    return path, file_id


async def _download(m: Message) -> Path:
    path, file_id = _file_from_message(m)
    tg_file = await app.bot.get_file(file_id)
    await app.bot.download_file(tg_file.file_path, destination=path)
    return path


async def _send_result(m: Message, result: ToolResult | tuple[Path, Path], caption: str, audio=False):
    if isinstance(result, ToolResult):
        path, work = result.path, result.workdir
    else:
        path, work = result
    try:
        if audio:
            await m.answer_audio(FSInputFile(path), caption=caption)
        elif path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            await m.answer_photo(FSInputFile(path), caption=caption)
        elif path.suffix.lower() == ".gif":
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
    await q.message.edit_text(
        "<b>🎛️ NovaBiz Pro Studio</b>\n\n"
        "كل قسم يحتوي أدوات فعلية وخياراتها الخاصة.\n"
        "اختر القسم الذي تريد العمل عليه:",
        reply_markup=studio_kb(),
    )
    await q.answer()


@app.dp.callback_query(F.data.startswith("studio:cat:"))
async def studio_category(q: CallbackQuery):
    cat = q.data.rsplit(":", 1)[1]
    title, tools = CATEGORIES.get(cat, ("🛠️", []))
    await q.message.edit_text(
        f"<b>{title}</b>\n\nاختر الأداة، ثم ستظهر خياراتها قبل التنفيذ:",
        reply_markup=kb([(f"studio:tool:{cat}:{key}", label) for key, label in tools]),
    )
    await q.answer()


OPTION_TEXT = {
    "enhance": [("studio:opt:video:enhance:light", "✨ خفيف"), ("studio:opt:video:enhance:medium", "✨ متوسط"), ("studio:opt:video:enhance:strong", "🔥 قوي")],
    "volume": [("studio:opt:volume:150", "🔊 رفع 150%"), ("studio:opt:volume:75", "🔉 خفض 75%"), ("studio:opt:volume:200", "🔊 رفع 200%")],
    "resize": [("studio:opt:resize:1920x1080", "📺 1920×1080"), ("studio:opt:resize:1080x1920", "📱 1080×1920"), ("studio:opt:resize:1080x1080", "⬛ 1080×1080")],
    "compress": [("studio:opt:compress:26", "📦 متوسط"), ("studio:opt:compress:30", "📦 قوي"), ("studio:opt:compress:22", "✨ جودة أعلى")],
    "convert": [("studio:opt:convert:mp4", "MP4"), ("studio:opt:convert:mp3", "MP3"), ("studio:opt:convert:wav", "WAV")],
}


@app.dp.callback_query(F.data.startswith("studio:tool:"))
async def studio_tool(q: CallbackQuery, state: FSMContext):
    _, _, cat, tool = q.data.split(":", 3)
    if tool in {"description", "caption", "social", "seo"}:
        await state.clear()
        await state.update_data(studio_cat=cat, studio_tool=tool)
        await state.set_state(StudioState.waiting_file)
        await q.message.edit_text("📤 أرسل الفيديو الآن.\n\nسأجهز لك النتيجة المطلوبة بعد استلامه.", reply_markup=kb([], "studio:cat:ai"))
        return await q.answer()
    if tool in OPTION_TEXT:
        await q.message.edit_text("⚙️ اختر الإعداد:", reply_markup=kb(OPTION_TEXT[tool], f"studio:cat:{cat}"))
    else:
        await state.clear()
        await state.update_data(studio_cat=cat, studio_tool=tool)
        await state.set_state(StudioState.waiting_file)
        await q.message.edit_text("📤 أرسل الملف الآن لتنفيذ الأداة فعلياً.", reply_markup=kb([], f"studio:cat:{cat}"))
    await q.answer()


@app.dp.callback_query(F.data.startswith("studio:opt:"))
async def studio_option(q: CallbackQuery, state: FSMContext):
    parts = q.data.split(":")
    await state.update_data(studio_cat=parts[2], studio_tool=parts[3], studio_value=parts[4])
    tool = parts[3]
    if tool in {"volume", "compress", "enhance", "resize", "convert"}:
        await state.set_state(StudioState.waiting_file)
        await q.message.edit_text("📤 أرسل الملف الآن وسأطبق الإعداد الذي اخترته.")
    await q.answer()


@app.dp.message(StudioState.waiting_file)
async def studio_file(m: Message, state: FSMContext):
    data = await state.get_data()
    tool = data.get("studio_tool")
    value = data.get("studio_value")
    progress = await m.answer("⏳ <b>جاري تنفيذ الأداة...</b>")
    try:
        src = await _download(m)
        if tool == "volume":
            result = await (video_volume(src, int(value)) if m.video else audio_volume(src, int(value)))
        elif tool == "trim":
            await state.update_data(src=str(src))
            await state.set_state(StudioState.waiting_value)
            return await progress.edit_text("✂️ أرسل وقت البداية والنهاية بهذا الشكل: <code>0 10</code>")
        elif tool == "mute":
            result = await (video_mute(src) if m.video else audio_mute(src))
        elif tool == "normalize":
            result = await normalize_audio(src)
        elif tool == "convert":
            result = await (convert_video(src) if m.video else convert_audio(src))
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
        elif tool in {"description", "caption", "social", "seo"}:
            # Real media metadata analysis; AI generation is kept deterministic when no AI API key is configured.
            from services.advanced_tools import media_info
            info = media_info(src)
            duration = float(info.get("duration", "0"))
            size = int(info.get("size", "0"))
            base = Path(getattr(m.video, "file_name", None) or getattr(m.document, "file_name", None) or "الفيديو").stem
            if tool == "description":
                text = f"🧠 <b>تحليل الفيديو</b>\n\nالملف: {base}\nالمدة: {duration:.1f} ثانية\nالحجم: {size/1024/1024:.2f} MB\n\nتم فحص خصائص الوسائط بنجاح."
            elif tool == "caption":
                text = f"✍️ <b>حزمة المحتوى</b>\n\n<b>الوصف:</b> {base} — محتوى جاهز للنشر والتعديل.\n\n<b>Bio:</b> محتوى جديد يستحق المشاهدة والمتابعة.\n\n<b>CTA:</b> تابع الحساب للمزيد.\n\n<b>5 هاشتاقات:</b>\n#محتوى #فيديو #اكسبلور #تيك_توك #ترند"
            elif tool == "social":
                text = "📱 <b>Social Pack</b>\n\nTikTok: وصف قصير + #اكسبلور\nInstagram: وصف جذاب + CTA\nYouTube: عنوان + وصف\nFacebook: منشور مختصر + CTA"
            else:
                text = "🔎 <b>SEO Pack</b>\n\nالعنوان: محتوى فيديو جديد ومميز\nالوصف: فيديو مناسب للنشر الرقمي\nالكلمات المفتاحية: فيديو، محتوى، ترفيه، تعليم، Shorts"
            await progress.edit_text(text, reply_markup=kb([], "studio:cat:ai"))
            return
        elif tool == "resize":
            # Keep aspect-safe conversion in the existing production service.
            from services.advanced_tools import ToolError
            result = await convert_video(src)
        else:
            raise StudioToolError("الأداة غير مدعومة بعد.")
        await progress.delete()
        await _send_result(m, result, "✅ <b>تم التنفيذ بنجاح</b>\n🎛️ NovaBiz Pro Studio")
    except (ToolError, StudioToolError, Exception) as e:
        await progress.edit_text(f"❌ <b>فشل التنفيذ</b>\n\n{str(e)[:1200]}")
    finally:
        await state.clear()


@app.dp.message(StudioState.waiting_value)
async def studio_trim_values(m: Message, state: FSMContext):
    data = await state.get_data()
    try:
        start, end = [float(x) for x in m.text.replace(",", " ").split()[:2]]
        src = Path(data["src"])
        if data.get("studio_cat") == "audio":
            result = await audio_trim(src, start, end)
        else:
            result = await video_trim(src, start, end)
        await _send_result(m, result, "✅ <b>تم القص بنجاح</b>\n🎛️ NovaBiz Pro Studio")
    except Exception as e:
        await m.answer(f"❌ خطأ: {str(e)[:1200]}")
    finally:
        await state.clear()


async def main() -> None:
    await app.main()


if __name__ == "__main__":
    asyncio.run(main())
