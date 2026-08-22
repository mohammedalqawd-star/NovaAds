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
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message
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
    ToolError,
    ToolResult,
    cleanup,
    compress_video,
    convert_audio,
    convert_video,
    extract_audio,
    extract_frames,
    make_gif,
    make_thumbnail,
    media_info,
    mute_video,
    normalize_audio,
    rotate_video,
    web_optimize,
)


class ProForm(StatesGroup):
    waiting_file = State()


PRO_SERVICES = {
    "compress": ("📦 ضغط فيديو Pro", "video"),
    "convert": ("🔄 تحويل فيديو عالي الجودة", "video"),
    "gif": ("🎞️ تحويل فيديو إلى GIF", "video"),
    "thumbnail": ("🖼️ استخراج صورة غلاف HD", "video"),
    "frames": ("🎬 استخراج لقطات ذكية", "video"),
    "mute": ("🔇 إزالة صوت الفيديو", "video"),
    "web": ("🌐 تجهيز الفيديو للنشر", "video"),
    "rotate": ("🔃 تدوير الفيديو", "video"),
    "extract_audio": ("🎵 استخراج الصوت MP3", "audio"),
    "convert_audio": ("🎧 تحويل الصوت إلى MP3", "audio"),
    "normalize": ("🎚️ تحسين مستوى الصوت", "audio"),
    "info": ("🔎 معلومات الملف الدقيقة", "all"),
}


def pro_kb():
    b = InlineKeyboardBuilder()
    for key, (label, _) in PRO_SERVICES.items():
        b.button(text=label, callback_data=f"pro:{key}")
    b.button(text="⬅️ الرئيسية", callback_data="home")
    b.adjust(2)
    return b.as_markup()


# احتفظ بالمرجع الأصلي قبل استبدال main_kb لتجنب الاستدعاء الذاتي.
_original_main_kb = app.main_kb


def pro_home_kb():
    original = _original_main_kb()
    rows = [list(row) for row in original.inline_keyboard]
    rows.insert(0, [])
    rows[0].append(__import__("aiogram").types.InlineKeyboardButton(text="⚡ Pro Studio", callback_data="pro_menu"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


# اجعل زر Pro Studio يظهر في لوحة NovaBiz الرئيسية بدون كسر الخدمات الأصلية.
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
    if service == "frames":
        frames = sorted(result.workdir.glob("frame_*.jpg"))
        for frame in frames:
            await message.answer_photo(FSInputFile(frame))
        await message.answer(f"✅ تم استخراج {len(frames)} لقطات\n🆔 Job: <code>{jid}</code>", reply_markup=app.main_kb())
        return
    if service in {"normalize", "extract_audio", "convert_audio"}:
        await message.answer_audio(FSInputFile(result.path), caption=f"✅ {PRO_SERVICES[service][0]}\n🆔 Job: <code>{jid}</code>", reply_markup=app.main_kb())
        return
    if result.path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        await message.answer_photo(FSInputFile(result.path), caption=f"✅ تم تجهيز الصورة\n🆔 Job: <code>{jid}</code>", reply_markup=app.main_kb())
        return
    if result.path.suffix.lower() == ".gif":
        await message.answer_document(FSInputFile(result.path), caption=f"✅ تم إنشاء GIF\n🆔 Job: <code>{jid}</code>", reply_markup=app.main_kb())
        return
    await message.answer_video(FSInputFile(result.path), caption=f"✅ {PRO_SERVICES[service][0]}\n🆔 Job: <code>{jid}</code>", reply_markup=app.main_kb())


@app.dp.message(F.text.in_({"/pro", "/tools"}))
async def pro_menu(message: Message):
    app.ensure_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "<b>⚡ NovaBiz Pro Studio</b>\n\n"
        "🛠️ أدوات معالجة حقيقية عبر FFmpeg/ffprobe.\n"
        "📦 معالجة محلية للملفات بدون رفعها لخدمة خارجية.\n"
        "💳 كل عملية تسجل في سجل الوظائف، ويعاد الرصيد تلقائياً عند الفشل.\n\n"
        "اختر الخدمة:",
        reply_markup=pro_kb(),
    )


@app.dp.callback_query(F.data == "pro_menu")
async def pro_menu_button(query: CallbackQuery):
    app.ensure_user(query.from_user.id, query.from_user.username)
    await query.message.edit_text(
        "<b>⚡ NovaBiz Pro Studio</b>\n\nاختر الأداة التي تريد تشغيلها:",
        reply_markup=pro_kb(),
    )
    await query.answer()


@app.dp.callback_query(F.data.startswith("pro:"))
async def pro_start(query: CallbackQuery, state: FSMContext):
    key = query.data.split(":", 1)[1]
    if key not in PRO_SERVICES:
        return await query.answer("الخدمة غير موجودة", show_alert=True)
    await state.update_data(pro_service=key)
    await state.set_state(ProForm.waiting_file)
    label = PRO_SERVICES[key][0]
    prompt = "📤 أرسل الملف الآن للحصول على معلوماته." if key == "info" else "📤 أرسل الفيديو أو الملف الآن."
    await query.message.edit_text(f"<b>{html.escape(label)}</b>\n\n{prompt}\n\n⏳ عند وصول الملف يبدأ التنفيذ مباشرة.")
    await query.answer()


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
    progress = await message.answer("⏳ <b>جاري تجهيز العملية...</b>\n\n⚙️ تتم معالجة الملف الآن.")
    input_workdir = Path(tempfile.mkdtemp(prefix="novabiz_pro_input_"))
    result: ToolResult | None = None

    try:
        src = await save_input(message, input_workdir)
        if service == "compress":
            result = await compress_video(src)
        elif service == "convert":
            result = await convert_video(src)
        elif service == "gif":
            result = await make_gif(src)
        elif service == "thumbnail":
            result = await make_thumbnail(src)
        elif service == "frames":
            result = await extract_frames(src)
        elif service == "mute":
            result = await mute_video(src)
        elif service == "web":
            result = await web_optimize(src)
        elif service == "rotate":
            result = await rotate_video(src)
        elif service == "extract_audio":
            result = await extract_audio(src)
        elif service == "convert_audio":
            result = await convert_audio(src)
        elif service == "normalize":
            result = await normalize_audio(src)
        elif service == "info":
            details = media_info(src)
            app.job_end(jid, True)
            await state.clear()
            await progress.edit_text(
                "<b>🔎 معلومات الملف</b>\n\n"
                f"📦 الحجم: {html.escape(details.get('size', 'غير متاح'))} bytes\n"
                f"⏱️ المدة: {html.escape(details.get('duration', 'غير متاح'))} ثانية\n"
                f"🎞️ الصيغة: {html.escape(details.get('format_name', 'غير متاح'))}\n"
                f"📡 Bitrate: {html.escape(details.get('bit_rate', 'غير متاح'))}\n\n"
                f"🆔 Job: <code>{jid}</code>",
                reply_markup=app.main_kb(),
            )
            return
        else:
            raise ToolError("الخدمة غير مفعلة.")

        if result is None:
            raise ToolError("لم يتم إنشاء الناتج.")

        app.job_end(jid, True)
        await state.clear()
        await progress.edit_text("✅ <b>اكتملت المعالجة بنجاح.</b>\n\n📤 إرسال الناتج...")
        await send_result(message, result, service, jid)

    except Exception as exc:
        app.refund(message.from_user.id, cost)
        app.job_end(jid, False, str(exc))
        await state.clear()
        await progress.edit_text(
            "❌ <b>فشلت العملية</b>\n\n"
            f"السبب: {html.escape(str(exc))}\n\n"
            "💳 تم إرجاع الرصيد لك تلقائياً.",
            reply_markup=app.main_kb(),
        )
    finally:
        if result is not None:
            cleanup(result)
        shutil.rmtree(input_workdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(app.main())
