from __future__ import annotations

import asyncio
import html
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

BASE = Path(__file__).resolve().parent
BOT_PATH = BASE / "bot.py"
spec = importlib.util.spec_from_file_location("novabiz_app", BOT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"تعذر تحميل {BOT_PATH}")
app = importlib.util.module_from_spec(spec)
sys.modules["novabiz_app"] = app
spec.loader.exec_module(app)

from services.advanced_tools import (
    ToolError, ToolResult, cleanup, compress_video, convert_audio, convert_video,
    extract_audio, extract_frames, make_gif, make_thumbnail, media_info,
    mute_video, normalize_audio, rotate_video, web_optimize,
)
from services.mega_tools import (
    audio_m4a, audio_volume, audio_wav, grayscale_video, image_blur,
    image_grayscale, image_jpg, image_resize, image_sharpen, image_webp,
    mirror_video, resize_video, sharpen_video, speed_video, video_snapshot,
)
from services.video_intelligence import VideoIntelligenceError, analyze_video


class ProForm(StatesGroup):
    waiting_file = State()
    waiting_video_ai = State()


PRO_SERVICES = {
    "video_ai": ("🧠 فهم الفيديو + Caption + 5 Hashtags", "video"),
    "compress": ("📦 ضغط فيديو سريع", "video"),
    "convert": ("🔄 تحويل فيديو عالي الجودة", "video"),
    "resize": ("📐 تغيير مقاس الفيديو", "video"),
    "speed": ("⚡ تغيير سرعة الفيديو", "video"),
    "mirror": ("🪞 عكس الفيديو", "video"),
    "grayvideo": ("⚫ فيديو أبيض وأسود", "video"),
    "sharpenvideo": ("✨ تحسين حدة الفيديو", "video"),
    "snapshot": ("📸 لقطة من الفيديو", "video"),
    "gif": ("🎞️ فيديو إلى GIF", "video"),
    "thumbnail": ("🖼️ غلاف HD", "video"),
    "frames": ("🎬 استخراج لقطات", "video"),
    "mute": ("🔇 إزالة صوت الفيديو", "video"),
    "web": ("🌐 تجهيز للنشر السريع", "video"),
    "rotate": ("🔃 تدوير الفيديو", "video"),
    "extract_audio": ("🎵 استخراج MP3", "audio"),
    "convert_audio": ("🎧 تحويل إلى MP3", "audio"),
    "normalize": ("🎚️ تحسين مستوى الصوت", "audio"),
    "volume": ("🔊 رفع/خفض الصوت", "audio"),
    "wav": ("🎙️ تحويل إلى WAV", "audio"),
    "m4a": ("🎼 تحويل إلى M4A", "audio"),
    "info": ("🔎 معلومات الملف الدقيقة", "all"),
    "imageresize": ("🖼️ تغيير مقاس الصورة", "image"),
    "jpg": ("📷 تحويل الصورة إلى JPG", "image"),
    "webp": ("🌐 تحويل الصورة إلى WebP", "image"),
    "imagegray": ("⚫ صورة أبيض وأسود", "image"),
    "imagesharp": ("✨ تحسين حدة الصورة", "image"),
    "imageblur": ("🌫️ تمويه الصورة", "image"),
}


def pro_kb():
    b = InlineKeyboardBuilder()
    for key, (label, _) in PRO_SERVICES.items():
        b.button(text=label, callback_data=f"pro:{key}")
    b.button(text="⬅️ الرئيسية", callback_data="home")
    b.adjust(2)
    return b.as_markup()


_original_main_kb = app.main_kb


def pro_home_kb():
    original = _original_main_kb()
    rows = [list(row) for row in original.inline_keyboard]
    rows.insert(0, [InlineKeyboardButton(text="⚡ Pro Studio", callback_data="pro_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


app.main_kb = pro_home_kb


def file_from_message(message: Message):
    return message.video or message.document or message.audio or (message.photo[-1] if message.photo else None)


async def save_input(message: Message, workdir: Path) -> Path:
    obj = file_from_message(message)
    if not obj:
        raise ToolError("أرسل فيديو أو ملفاً صوتياً أو صورة مناسبة للخدمة.")
    size = getattr(obj, "file_size", None)
    if size and size > app.MAX_FILE_MB * 1024 * 1024:
        raise ToolError(f"الحد الأقصى للملف هو {app.MAX_FILE_MB}MB.")
    info = await app.bot.get_file(obj.file_id)
    src = workdir / "input.bin"
    await app.bot.download_file(info.file_path, src)
    return src


async def send_result(message: Message, result: ToolResult, service: str, jid: str):
    suffix = result.path.suffix.lower()
    caption = f"✅ <b>{html.escape(PRO_SERVICES[service][0])}</b>\n🆔 Job: <code>{jid}</code>"
    if service == "frames":
        frames = sorted(result.workdir.glob("frame_*.jpg"))
        for frame in frames:
            await message.answer_photo(FSInputFile(frame))
        await message.answer(f"✅ تم استخراج {len(frames)} لقطات\n🆔 Job: <code>{jid}</code>", reply_markup=app.main_kb())
        return
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        await message.answer_photo(FSInputFile(result.path), caption=caption, reply_markup=app.main_kb())
    elif suffix in {".mp3", ".wav", ".m4a"}:
        await message.answer_audio(FSInputFile(result.path), caption=caption, reply_markup=app.main_kb())
    elif suffix == ".gif":
        await message.answer_document(FSInputFile(result.path), caption=caption, reply_markup=app.main_kb())
    else:
        await message.answer_video(FSInputFile(result.path), caption=caption, reply_markup=app.main_kb())


@app.dp.message(F.text.in_({"/pro", "/tools"}))
async def pro_menu(message: Message):
    app.ensure_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "<b>⚡ NovaBiz Pro Studio</b>\n\n"
        "🚀 خدمات معالجة حقيقية وسريعة عبر FFmpeg.\n"
        "🧠 تحليل فيديو بالذكاء الاصطناعي وإنشاء محتوى للنشر.\n"
        "🎯 فيديو + صوت + صور في لوحة واحدة.\n"
        "📤 النتيجة تُرسل مباشرة بعد اكتمال المعالجة.\n\n"
        "اختر الخدمة:", reply_markup=pro_kb())


@app.dp.callback_query(F.data == "pro_menu")
async def pro_menu_button(query: CallbackQuery):
    app.ensure_user(query.from_user.id, query.from_user.username)
    await query.message.edit_text("<b>⚡ NovaBiz Pro Studio</b>\n\nاختر الأداة التي تريد تشغيلها:", reply_markup=pro_kb())
    await query.answer()


@app.dp.callback_query(F.data.startswith("pro:"))
async def pro_start(query: CallbackQuery, state: FSMContext):
    key = query.data.split(":", 1)[1]
    if key not in PRO_SERVICES:
        return await query.answer("الخدمة غير موجودة", show_alert=True)
    await state.clear()
    await state.update_data(pro_service=key)
    if key == "video_ai":
        await state.set_state(ProForm.waiting_video_ai)
        await query.message.edit_text(
            "<b>🧠 فهم الفيديو + تجهيز المحتوى</b>\n\n"
            "📤 أرسل الفيديو الآن.\n\n"
            "سيتم تحليل لقطات حقيقية من الفيديو ثم إنشاء:\n"
            "📝 Caption مناسب\n"
            "👤 Bio/وصف مناسب للنشر\n"
            "#️⃣ خمسة هاشتاقات مرتبطة بالمحتوى\n"
            "🎯 الموضوع والجمهور والأسلوب\n"
            "🪝 Hook و CTA\n\n"
            "⚡ ستصلك النتيجة بعد التحليل."
        )
    else:
        await state.set_state(ProForm.waiting_file)
        label = PRO_SERVICES[key][0]
        prompt = "📤 أرسل الملف للحصول على معلوماته." if key == "info" else "📤 أرسل الملف الآن وسيبدأ التنفيذ مباشرة."
        await query.message.edit_text(f"<b>{html.escape(label)}</b>\n\n{prompt}\n\n⚡ المعالجة محسّنة للسرعة.")
    await query.answer()


@app.dp.message(ProForm.waiting_video_ai)
async def video_ai_file(message: Message, state: FSMContext):
    app.ensure_user(message.from_user.id, message.from_user.username)
    cost = 1
    if not app.charge(message.from_user.id, cost):
        await state.clear()
        return await message.answer("❌ رصيدك غير كافٍ.", reply_markup=app.main_kb())

    jid = app.job_start(message.from_user.id, "pro_video_intelligence", cost)
    progress = await message.answer(
        "⏳ <b>جاري فهم الفيديو...</b>\n\n"
        "🎞️ استخراج لقطات ممثلة\n"
        "🧠 تحليل المحتوى\n"
        "📝 تجهيز النص والهاشتاقات..."
    )
    workdir = Path(tempfile.mkdtemp(prefix="novabiz_video_ai_input_"))
    frames_dir: Path | None = None
    try:
        src = await save_input(message, workdir)
        result, frames, frames_dir = await analyze_video(src, frame_count=6)
        hashtags = result.get("hashtags", [])[:5]
        tags = " ".join(str(x) for x in hashtags)
        text = (
            "<b>🧠 تحليل الفيديو مكتمل</b>\n\n"
            f"🎯 <b>الموضوع:</b> {html.escape(str(result.get('topic', 'غير محدد')))}\n"
            f"👥 <b>الجمهور:</b> {html.escape(str(result.get('audience', 'غير محدد')))}\n"
            f"🎭 <b>الأسلوب:</b> {html.escape(str(result.get('tone', 'غير محدد')))}\n"
            f"⏱️ <b>المدة:</b> {html.escape(str(result.get('duration', '?')))} ثانية\n"
            f"📐 <b>الدقة:</b> {html.escape(str(result.get('resolution', '?')))}\n\n"
            f"📝 <b>Caption:</b>\n{html.escape(str(result.get('caption', '')))}\n\n"
            f"👤 <b>Bio / الوصف:</b>\n{html.escape(str(result.get('bio', '')))}\n\n"
            f"🪝 <b>Hook:</b> {html.escape(str(result.get('hook', '')))}\n"
            f"📣 <b>CTA:</b> {html.escape(str(result.get('cta', '')))}\n\n"
            f"#️⃣ <b>الهاشتاقات:</b>\n{html.escape(tags)}\n\n"
            f"🆔 Job: <code>{jid}</code>"
        )
        app.job_end(jid, True)
        await state.clear()
        await progress.edit_text(text, reply_markup=app.main_kb())
        if frames:
            await message.answer_photo(FSInputFile(frames[0]), caption="🖼️ لقطة مقترحة كغلاف")
    except Exception as exc:
        app.refund(message.from_user.id, cost)
        app.job_end(jid, False, str(exc))
        await state.clear()
        await progress.edit_text(
            "❌ <b>فشل تحليل الفيديو</b>\n\n"
            f"السبب: {html.escape(str(exc))}\n\n"
            "💳 تم إرجاع الرصيد تلقائياً.",
            reply_markup=app.main_kb(),
        )
    finally:
        if frames_dir:
            shutil.rmtree(frames_dir, ignore_errors=True)
        shutil.rmtree(workdir, ignore_errors=True)


async def run_service(service: str, src: Path) -> ToolResult | None:
    if service == "compress": return await compress_video(src, crf=26)
    if service == "convert": return await convert_video(src)
    if service == "resize": return await resize_video(src, 1080, 1920)
    if service == "speed": return await speed_video(src, 1.5)
    if service == "mirror": return await mirror_video(src)
    if service == "grayvideo": return await grayscale_video(src)
    if service == "sharpenvideo": return await sharpen_video(src)
    if service == "snapshot": return await video_snapshot(src, 1.0)
    if service == "gif": return await make_gif(src)
    if service == "thumbnail": return await make_thumbnail(src)
    if service == "frames": return await extract_frames(src)
    if service == "mute": return await mute_video(src)
    if service == "web": return await web_optimize(src)
    if service == "rotate": return await rotate_video(src)
    if service == "extract_audio": return await extract_audio(src)
    if service == "convert_audio": return await convert_audio(src)
    if service == "normalize": return await normalize_audio(src)
    if service == "volume": return await audio_volume(src)
    if service == "wav": return await audio_wav(src)
    if service == "m4a": return await audio_m4a(src)
    if service == "imageresize": return await image_resize(src, 1080, 1080)
    if service == "jpg": return await image_jpg(src)
    if service == "webp": return await image_webp(src)
    if service == "imagegray": return await image_grayscale(src)
    if service == "imagesharp": return await image_sharpen(src)
    if service == "imageblur": return await image_blur(src)
    return None


@app.dp.message(ProForm.waiting_file)
async def pro_file(message: Message, state: FSMContext):
    data = await state.get_data()
    service = data.get("pro_service")
    if service not in PRO_SERVICES:
        await state.clear()
        return await message.answer("❌ انتهت جلسة الخدمة.", reply_markup=app.main_kb())

    app.ensure_user(message.from_user.id, message.from_user.username)
    cost = 1
    if not app.charge(message.from_user.id, cost):
        await state.clear()
        return await message.answer("❌ رصيدك غير كافٍ.", reply_markup=app.main_kb())

    jid = app.job_start(message.from_user.id, f"pro_{service}", cost)
    progress = await message.answer("⏳ <b>جاري تجهيز العملية...</b>\n\n⚙️ المعالجة تعمل الآن...")
    input_workdir = Path(tempfile.mkdtemp(prefix="novabiz_pro_input_"))
    result: ToolResult | None = None
    try:
        src = await save_input(message, input_workdir)
        if service == "info":
            details = media_info(src)
            app.job_end(jid, True)
            await state.clear()
            await progress.edit_text(
                "<b>🔎 معلومات الملف</b>\n\n"
                f"📦 الحجم: {html.escape(details.get('size', 'غير متاح'))} bytes\n"
                f"⏱️ المدة: {html.escape(details.get('duration', 'غير متاح'))} ثانية\n"
                f"🎞️ الصيغة: {html.escape(details.get('format_name', 'غير متاح'))}\n"
                f"📡 Bitrate: {html.escape(details.get('bit_rate', 'غير متاح'))}\n\n"
                f"🆔 Job: <code>{jid}</code>", reply_markup=app.main_kb())
            return
        result = await run_service(service, src)
        if result is None:
            raise ToolError("الخدمة غير مفعلة.")
        app.job_end(jid, True)
        await state.clear()
        await progress.edit_text("✅ <b>اكتملت المعالجة.</b>\n\n📤 إرسال الناتج الآن...")
        await send_result(message, result, service, jid)
    except Exception as exc:
        app.refund(message.from_user.id, cost)
        app.job_end(jid, False, str(exc))
        await state.clear()
        await progress.edit_text("❌ <b>فشلت العملية</b>\n\n" + f"السبب: {html.escape(str(exc))}\n\n💳 تم إرجاع الرصيد تلقائياً.", reply_markup=app.main_kb())
    finally:
        if result is not None:
            cleanup(result)
        shutil.rmtree(input_workdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(app.main())
