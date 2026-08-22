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
from services.video_intelligence import analyze_video
from services.studio_catalog import STUDIO_CATEGORIES


class ProForm(StatesGroup):
    waiting_file = State()
    waiting_video_ai = State()


def category_kb():
    b = InlineKeyboardBuilder()
    for key, (title, _) in STUDIO_CATEGORIES.items():
        b.button(text=title, callback_data=f"studio:{key}")
    b.button(text="⬅️ الرئيسية", callback_data="home")
    b.adjust(2)
    return b.as_markup()


def tool_kb(category: str):
    b = InlineKeyboardBuilder()
    data = STUDIO_CATEGORIES.get(category, {}).get("tools", {})
    for key, (label, _) in data.items():
        b.button(text=label, callback_data=f"tool:{category}:{key}")
    b.button(text="⬅️ الأقسام", callback_data="pro_menu")
    b.adjust(2)
    return b.as_markup()


def option_kb(category: str, service: str):
    b = InlineKeyboardBuilder()
    data = STUDIO_CATEGORIES[category]["tools"].get(service)
    if not data:
        return b.as_markup()
    _, options = data
    for label, value in options:
        b.button(text=label, callback_data=f"opt:{category}:{service}:{value}")
    b.button(text="⬅️ الأدوات", callback_data=f"studio:{category}")
    b.adjust(2)
    return b.as_markup()


_original_main_kb = app.main_kb


def pro_home_kb():
    original = _original_main_kb()
    rows = [list(row) for row in original.inline_keyboard]
    rows.insert(0, [InlineKeyboardButton(text="👑 استديو NovaBiz", callback_data="pro_menu")])
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
    labels = {label_key: label for cat in STUDIO_CATEGORIES.values() for label_key, (label, _) in cat.get("tools", {}).items()}
    caption = f"✅ <b>{html.escape(labels.get(service, service))}</b>\n🆔 Job: <code>{jid}</code>"
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


@app.dp.message(F.text.in_({"/pro", "/tools", "/studio"}))
async def pro_menu(message: Message):
    app.ensure_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "<b>👑 NovaBiz Studio</b>\n\n"
        "اختر القسم أولاً. كل قسم يحتوي أدوات حقيقية، وكل أداة تعرض خياراتها قبل التنفيذ.\n\n"
        "⚡ المعالجة عبر FFmpeg\n🧠 تحليل الفيديو عبر وحدة الذكاء\n📤 إرسال النتيجة بالنوع المناسب",
        reply_markup=category_kb(),
    )


@app.dp.callback_query(F.data == "pro_menu")
async def pro_menu_button(query: CallbackQuery):
    app.ensure_user(query.from_user.id, query.from_user.username)
    await query.message.edit_text("<b>👑 NovaBiz Studio</b>\n\nاختر القسم:", reply_markup=category_kb())
    await query.answer()


@app.dp.callback_query(F.data.startswith("studio:"))
async def studio_category(query: CallbackQuery):
    category = query.data.split(":", 1)[1]
    if category not in STUDIO_CATEGORIES:
        return await query.answer("القسم غير موجود", show_alert=True)
    title, desc = STUDIO_CATEGORIES[category]["title"], STUDIO_CATEGORIES[category].get("description", "")
    await query.message.edit_text(
        f"<b>{html.escape(title)}</b>\n\n{html.escape(desc)}\n\nاختر الأداة:",
        reply_markup=tool_kb(category),
    )
    await query.answer()


@app.dp.callback_query(F.data.startswith("tool:"))
async def studio_tool(query: CallbackQuery, state: FSMContext):
    _, category, service = query.data.split(":", 2)
    data = STUDIO_CATEGORIES.get(category, {}).get("tools", {}).get(service)
    if not data:
        return await query.answer("الأداة غير موجودة", show_alert=True)
    label, options = data
    await state.clear()
    await state.update_data(pro_category=category, pro_service=service)
    if service == "video_ai":
        await state.set_state(ProForm.waiting_video_ai)
        await query.message.edit_text(
            "<b>🧠 فهم الفيديو وتجهيز المحتوى</b>\n\n"
            "أرسل الفيديو، وسيتم تحليل لقطات حقيقية منه وإنتاج:\n"
            "📝 وصف/Caption\n👤 Bio مناسب\n🎯 موضوع وجمهور\n🪝 Hook\n📣 CTA\n#️⃣ خمسة هاشتاقات\n\n"
            "⚡ التحليل يتم على الفيديو المرسل، وليس على اسم الملف فقط."
        )
    else:
        await query.message.edit_text(
            f"<b>{html.escape(label)}</b>\n\n"
            "⚙️ اختر الإعداد المطلوب:",
            reply_markup=option_kb(category, service),
        )
    await query.answer()


@app.dp.callback_query(F.data.startswith("opt:"))
async def studio_option(query: CallbackQuery, state: FSMContext):
    _, category, service, value = query.data.split(":", 3)
    if service not in STUDIO_CATEGORIES.get(category, {}).get("tools", {}):
        return await query.answer("الخيار غير متاح", show_alert=True)
    await state.clear()
    await state.update_data(pro_category=category, pro_service=service, pro_option=value)
    await state.set_state(ProForm.waiting_file)
    label = STUDIO_CATEGORIES[category]["tools"][service][0]
    option_label = next((x[0] for x in STUDIO_CATEGORIES[category]["tools"][service][1] if x[1] == value), value)
    await query.message.edit_text(
        f"<b>{html.escape(label)}</b>\n\n"
        f"⚙️ الاختيار: <b>{html.escape(option_label)}</b>\n\n"
        "📤 أرسل الملف الآن.\n"
        "⏳ سيظهر لك أولاً أنه جاري التجهيز ثم سيتم إرسال الناتج."
    )
    await query.answer()


@app.dp.message(ProForm.waiting_video_ai)
async def video_ai_file(message: Message, state: FSMContext):
    app.ensure_user(message.from_user.id, message.from_user.username)
    cost = 1
    if not app.charge(message.from_user.id, cost):
        await state.clear()
        return await message.answer("❌ رصيدك غير كافٍ.", reply_markup=app.main_kb())
    jid = app.job_start(message.from_user.id, "pro_video_intelligence", cost)
    progress = await message.answer("⏳ <b>جاري فهم الفيديو...</b>\n\n🎞️ استخراج لقطات\n🧠 تحليل المحتوى\n📝 تجهيز النص والهاشتاقات...")
    workdir = Path(tempfile.mkdtemp(prefix="novabiz_video_ai_input_"))
    frames_dir: Path | None = None
    try:
        src = await save_input(message, workdir)
        result, frames, frames_dir = await analyze_video(src, frame_count=6)
        tags = " ".join(str(x) for x in result.get("hashtags", [])[:5])
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
        await progress.edit_text("❌ <b>فشل تحليل الفيديو</b>\n\n" + f"السبب: {html.escape(str(exc))}\n\n💳 تم إرجاع الرصيد تلقائياً.", reply_markup=app.main_kb())
    finally:
        if frames_dir:
            shutil.rmtree(frames_dir, ignore_errors=True)
        shutil.rmtree(workdir, ignore_errors=True)


async def run_service(service: str, src: Path, option: str | None = None) -> ToolResult | None:
    if service == "compress": return await compress_video(src, crf=int(option or 26))
    if service == "convert": return await convert_video(src)
    if service == "resize":
        w, h = (int(x) for x in (option or "1080x1920").split("x", 1))
        return await resize_video(src, w, h)
    if service == "speed": return await speed_video(src, float(option or 1.5))
    if service == "mirror": return await mirror_video(src, option or "horizontal")
    if service == "grayvideo": return await grayscale_video(src)
    if service == "sharpenvideo": return await sharpen_video(src)
    if service == "snapshot": return await video_snapshot(src, float(option or 1))
    if service == "gif": return await make_gif(src, fps=int(option or 12))
    if service == "thumbnail": return await make_thumbnail(src, width=int(option or 1280))
    if service == "frames": return await extract_frames(src, count=int(option or 9))
    if service == "mute": return await mute_video(src)
    if service == "web": return await web_optimize(src)
    if service == "rotate": return await rotate_video(src, option or "right")
    if service == "volume": return await audio_volume(src, float(option or 1.5))
    if service == "extract_audio": return await extract_audio(src)
    if service == "convert_audio": return await convert_audio(src)
    if service == "normalize": return await normalize_audio(src)
    if service == "wav": return await audio_wav(src)
    if service == "m4a": return await audio_m4a(src)
    if service == "imageresize":
        w, h = (int(x) for x in (option or "1080x1080").split("x", 1))
        return await image_resize(src, w, h)
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
    option = data.get("pro_option")
    if not service:
        await state.clear()
        return await message.answer("❌ انتهت جلسة الخدمة.", reply_markup=app.main_kb())
    app.ensure_user(message.from_user.id, message.from_user.username)
    cost = 1
    if not app.charge(message.from_user.id, cost):
        await state.clear()
        return await message.answer("❌ رصيدك غير كافٍ. لا يمكن تشغيل الخدمات حتى يضاف رصيد جديد.", reply_markup=app.main_kb())
    jid = app.job_start(message.from_user.id, f"pro_{service}", cost)
    progress = await message.answer("⏳ <b>جاري تجهيز العملية...</b>\n\n⚙️ تنفيذ الخدمة فعلياً الآن...\n📤 سيتم إرسال النتيجة عند الانتهاء.")
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
        result = await run_service(service, src, option)
        if result is None:
            raise ToolError("الخدمة غير مفعلة أو لا يوجد تنفيذ حقيقي لها.")
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
