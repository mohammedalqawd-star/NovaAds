from __future__ import annotations

import asyncio
import html
import shutil
import tempfile
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
    cleanup,
    compress_video,
    extract_frames,
    make_gif,
    make_thumbnail,
    media_info,
    normalize_audio,
)


class ProForm(StatesGroup):
    waiting_file = State()


PRO_SERVICES = {
    "compress": "📦 ضغط فيديو Pro",
    "gif": "🎞️ تحويل فيديو إلى GIF",
    "thumbnail": "🖼️ استخراج صورة غلاف",
    "frames": "🎬 استخراج لقطات ذكية",
    "normalize": "🎚️ تحسين مستوى الصوت",
    "info": "🔎 معلومات الملف",
}


def pro_kb():
    b = InlineKeyboardBuilder()
    for key, label in PRO_SERVICES.items():
        b.button(text=label, callback_data=f"pro:{key}")
    b.button(text="⬅️ الرئيسية", callback_data="home")
    b.adjust(2)
    return b.as_markup()


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
    if result.path.name == "frame_%02d.jpg":
        frames = sorted(result.workdir.glob("frame_*.jpg"))
        for frame in frames:
            await message.answer_photo(FSInputFile(frame))
        return
    if service == "normalize":
        await message.answer_audio(
            FSInputFile(result.path),
            caption=f"✅ تم تحسين الصوت\n🆔 Job: <code>{jid}</code>",
        )
        return
    await message.answer_document(
        FSInputFile(result.path),
        caption=f"✅ اكتملت الخدمة بنجاح\n🛠️ {html.escape(PRO_SERVICES[service])}\n🆔 Job: <code>{jid}</code>",
        reply_markup=app.main_kb(),
    )


@app.dp.message(F.text == "/pro")
async def pro_menu(message: Message):
    app.ensure_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "<b>⚡ NovaBiz Pro Studio</b>\n\n"
        "مجموعة خدمات معالجة محلية عبر FFmpeg/ffprobe، بدون ادعاء ذكاء اصطناعي غير موجود.\n\n"
        "اختر الخدمة:",
        reply_markup=pro_kb(),
    )


@app.dp.callback_query(F.data.startswith("pro:"))
async def pro_start(query: CallbackQuery, state: FSMContext):
    key = query.data.split(":", 1)[1]
    if key not in PRO_SERVICES:
        return await query.answer("الخدمة غير موجودة", show_alert=True)

    await state.update_data(pro_service=key)
    await state.set_state(ProForm.waiting_file)

    if key == "info":
        prompt = "📤 أرسل الملف للحصول على معلوماته الفنية."
    elif key == "normalize":
        prompt = "🎙️ أرسل ملف الصوت أو الفيديو لتحسين مستوى الصوت."
    else:
        prompt = "📤 أرسل الفيديو الآن."

    await query.message.edit_text(
        f"<b>{PRO_SERVICES[key]}</b>\n\n{prompt}\n\n"
        f"💎 التكلفة: عملية واحدة",
    )
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
    progress = await message.answer("⏳ <b>جاري تنفيذ الخدمة...</b>\n\n⚙️ معالجة الملف الآن.")
    input_workdir = Path(tempfile.mkdtemp(prefix="novabiz_pro_input_"))
    result: ToolResult | None = None

    try:
        src = await save_input(message, input_workdir)

        if service == "compress":
            result = await compress_video(src)
        elif service == "gif":
            result = await make_gif(src)
        elif service == "thumbnail":
            result = await make_thumbnail(src)
        elif service == "frames":
            result = await extract_frames(src)
        elif service == "normalize":
            result = await normalize_audio(src)
        elif service == "info":
            details = media_info(src)
            app.job_end(jid, True)
            await state.clear()
            text = (
                "<b>🔎 معلومات الملف</b>\n\n"
                f"📦 الحجم: {details.get('size', 'غير متاح')} bytes\n"
                f"⏱️ المدة: {details.get('duration', 'غير متاح')} ثانية\n"
                f"🎞️ الصيغة: {html.escape(details.get('format_name', 'غير متاح'))}\n\n"
                f"🆔 Job: <code>{jid}</code>"
            )
            await progress.edit_text(text, reply_markup=app.main_kb())
            return
        else:
            raise ToolError("الخدمة غير مفعلة.")

        if result is None or not result.path.exists() and result.path.name != "frame_%02d.jpg":
            raise ToolError("لم يتم إنشاء الناتج.")

        app.job_end(jid, True)
        await state.clear()
        await progress.edit_text("✅ <b>اكتملت المعالجة.</b>\n\n📤 إرسال الناتج...")
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
