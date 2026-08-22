from __future__ import annotations

import html
from pathlib import Path

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import bot as app
from services.advanced_tools import (
    ToolError,
    cleanup as advanced_cleanup,
    compress_video,
    extract_frames,
    make_gif,
    make_thumbnail,
    media_info,
    normalize_audio,
)


class AdvancedForm(StatesGroup):
    waiting_media = State()


ADVANCED = {
    "compress": ("📦 ضغط فيديو Pro", "ضغط H.264 متوازن بجودة عالية وحجم أقل."),
    "gif": ("🎞️ تحويل فيديو إلى GIF", "تحويل مقطع الفيديو إلى GIF مناسب للمشاركة."),
    "thumbnail": ("🖼️ استخراج Thumbnail", "استخراج صورة مصغرة عالية الجودة من الفيديو."),
    "frames": ("🎯 استخراج لقطات Pro", "استخراج حتى 9 لقطات واضحة من الفيديو."),
    "normalize": ("🎵 تحسين الصوت", "توحيد مستوى الصوت وإخراج MP3 بمعدل 192kbps."),
    "info": ("🔍 معلومات الملف", "عرض مدة الملف وحجمه وصيغته باستخدام ffprobe."),
}


def advanced_menu_kb():
    b = InlineKeyboardBuilder()
    for key, (name, _) in ADVANCED.items():
        b.button(text=name, callback_data=f"adv:{key}")
    b.button(text="⬅️ الرئيسية", callback_data="home")
    b.adjust(2)
    return b.as_markup()


def install() -> None:
    original_main_kb = app.main_kb

    def upgraded_main_kb():
        markup = original_main_kb()
        # لا نعدل كائن الـ InlineKeyboard الأصلي؛ نضيف زر الخدمة في نسخة جديدة.
        b = InlineKeyboardBuilder()
        if markup and markup.inline_keyboard:
            for row in markup.inline_keyboard:
                for button in row:
                    b.button(text=button.text or "", callback_data=button.callback_data or "")
        b.button(text="🚀 Advanced Studio", callback_data="advanced_menu")
        b.adjust(2)
        return b.as_markup()

    app.main_kb = upgraded_main_kb

    @app.dp.callback_query(F.data == "advanced_menu")
    async def advanced_menu(q: CallbackQuery):
        await q.message.edit_text(
            "<b>🚀 Advanced Studio</b>\n\n"
            "خدمات معالجة متقدمة تعمل محلياً عبر FFmpeg/ffprobe.\n"
            "اختر الخدمة التي تريد تنفيذها:",
            reply_markup=advanced_menu_kb(),
        )
        await q.answer()

    @app.dp.callback_query(F.data.startswith("adv:"))
    async def advanced_start(q: CallbackQuery, state: FSMContext):
        key = q.data.split(":", 1)[1]
        if key not in ADVANCED:
            return await q.answer("الخدمة غير موجودة", show_alert=True)

        name, desc = ADVANCED[key]
        if key == "info":
            prompt = "📤 أرسل الملف الآن للحصول على معلوماته."
        elif key == "normalize":
            prompt = "📤 أرسل الفيديو أو الملف الصوتي الآن."
        else:
            prompt = "📤 أرسل الفيديو الآن."

        await state.update_data(advanced_tool=key)
        await state.set_state(AdvancedForm.waiting_media)
        await q.message.edit_text(
            f"<b>{name}</b>\n\n{html.escape(desc)}\n\n{prompt}\n"
            "⏳ عند وصول الملف تبدأ العملية مباشرة.",
            reply_markup=InlineKeyboardBuilder().button(
                text="❌ إلغاء", callback_data="adv_cancel"
            ).as_markup(),
        )
        await q.answer()

    @app.dp.callback_query(F.data == "adv_cancel")
    async def advanced_cancel(q: CallbackQuery, state: FSMContext):
        await state.clear()
        await q.message.edit_text("❌ تم إلغاء العملية.", reply_markup=app.main_kb())
        await q.answer()

    @app.dp.message(AdvancedForm.waiting_media)
    async def advanced_media(m: Message, state: FSMContext):
        data = await state.get_data()
        key = data.get("advanced_tool")
        if not key:
            await state.clear()
            return await m.answer("❌ انتهت جلسة الخدمة.", reply_markup=app.main_kb())

        obj = m.video or m.document or m.audio or (m.photo[-1] if m.photo else None)
        if not obj:
            return await m.answer("📤 أرسل الملف المطلوب للخدمة.")
        if getattr(obj, "file_size", None) and obj.file_size > app.MAX_FILE_MB * 1024 * 1024:
            return await m.answer(f"❌ الحد الأقصى للملف هو {app.MAX_FILE_MB}MB.")

        app.ensure_user(m.from_user.id, m.from_user.username)
        cost = 1
        if not app.charge(m.from_user.id, cost):
            await state.clear()
            return await m.answer("❌ رصيدك غير كافٍ.", reply_markup=app.main_kb())

        jid = app.job_start(m.from_user.id, f"advanced_{key}", cost)
        progress = await m.answer(
            "⏳ <b>جاري تجهيز العملية...</b>\n\n"
            "⚙️ يتم تنفيذ الخدمة بأفضل إعدادات متاحة، انتظر قليلاً."
        )
        workdir: Path | None = None

        try:
            work = app.MEDIA / f"advanced_{jid}"
            work.mkdir(parents=True, exist_ok=True)
            src = await app.download_input(obj, work)

            if key == "compress":
                result = await compress_video(src, crf=26)
                workdir = result.workdir
                await m.answer_document(FSInputFile(result.path), caption=f"✅ تم ضغط الفيديو\n🆔 Job: <code>{jid}</code>")

            elif key == "gif":
                result = await make_gif(src, fps=12, width=480)
                workdir = result.workdir
                await m.answer_document(FSInputFile(result.path), caption=f"✅ تم إنشاء GIF\n🆔 Job: <code>{jid}</code>")

            elif key == "thumbnail":
                result = await make_thumbnail(src, width=1280)
                workdir = result.workdir
                await m.answer_photo(FSInputFile(result.path), caption=f"✅ تم استخراج Thumbnail\n🆔 Job: <code>{jid}</code>")

            elif key == "frames":
                result = await extract_frames(src, count=9)
                workdir = result.workdir
                frames = sorted(workdir.glob("frame_*.jpg"))
                for frame in frames:
                    await m.answer_photo(FSInputFile(frame))
                await m.answer(f"✅ تم استخراج {len(frames)} لقطات\n🆔 Job: <code>{jid}</code>")

            elif key == "normalize":
                result = await normalize_audio(src)
                workdir = result.workdir
                await m.answer_audio(FSInputFile(result.path), caption=f"✅ تم تحسين الصوت\n🆔 Job: <code>{jid}</code>")

            elif key == "info":
                details = media_info(src)
                duration = details.get("duration", "غير معروف")
                size = details.get("size", "غير معروف")
                fmt = details.get("format_name", "غير معروف")
                size_mb = "غير معروف"
                try:
                    size_mb = f"{int(size) / 1024 / 1024:.2f} MB"
                except Exception:
                    pass
                await m.answer(
                    "<b>🔍 معلومات الملف</b>\n\n"
                    f"⏱️ المدة: <code>{html.escape(duration)}</code>\n"
                    f"📦 الحجم: <code>{html.escape(size_mb)}</code>\n"
                    f"🧾 الصيغة: <code>{html.escape(fmt)}</code>\n"
                    f"🆔 Job: <code>{jid}</code>"
                )

            else:
                raise ToolError("الخدمة غير مدعومة.")

            app.job_end(jid, True)
            await state.clear()
            await progress.edit_text("✅ <b>اكتملت العملية بنجاح</b>")
            await m.answer("اختر خدمة أخرى:", reply_markup=app.main_kb())

        except Exception as e:
            app.refund(m.from_user.id, cost)
            app.job_end(jid, False, str(e))
            await state.clear()
            await progress.edit_text(
                "❌ <b>فشلت العملية</b>\n\n"
                "💳 تم إرجاع الرصيد لك تلقائياً.\n"
                f"السبب: <code>{html.escape(str(e))[:900]}</code>"
            )
            await m.answer("اختر خدمة أخرى:", reply_markup=app.main_kb())
        finally:
            if workdir:
                advanced_cleanup(workdir)

    print("✅ Advanced Studio handlers installed")
