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
spec = importlib.util.spec_from_file_location("novabiz_app", BASE / "bot.py")
if spec is None or spec.loader is None: raise RuntimeError("تعذر تحميل bot.py")
app = importlib.util.module_from_spec(spec)
sys.modules["novabiz_app"] = app
spec.loader.exec_module(app)

from services.advanced_tools import ToolError, ToolResult
from services.options_engine import (
    audio_convert, cleanup, compress, convert, frames, gif, grayscale, image_convert,
    image_filter, image_resize, info, mirror, normalize, resize, rotate, sharpen,
    snapshot, speed, thumbnail, volume_video,
)
from services.video_intelligence import analyze_video


class Form(StatesGroup):
    waiting_file = State()
    waiting_ai_video = State()


SERVICES = {
    "compress": "📦 ضغط الفيديو",
    "convert": "🔄 تحويل الفيديو",
    "resize": "📐 مقاس الفيديو",
    "speed": "⚡ سرعة الفيديو",
    "volume": "🔊 رفع/خفض صوت الفيديو",
    "mirror": "🪞 عكس الفيديو",
    "gray": "⚫ أبيض وأسود للفيديو",
    "sharpen": "✨ حدة الفيديو",
    "snapshot": "📸 لقطة من الفيديو",
    "gif": "🎞️ فيديو إلى GIF",
    "thumbnail": "🖼️ غلاف الفيديو",
    "frames": "🎬 استخراج لقطات",
    "rotate": "🔃 تدوير الفيديو",
    "audio": "🎵 تحويل الصوت",
    "normalize": "🎚️ تحسين الصوت",
    "imageresize": "🖼️ مقاس الصورة",
    "jpg": "📷 صورة JPG",
    "webp": "🌐 صورة WebP",
    "imagegray": "⚫ صورة أبيض وأسود",
    "imagesharp": "✨ حدة الصورة",
    "imageblur": "🌫️ تمويه الصورة",
    "info": "🔎 معلومات الملف",
    "video_ai": "🧠 فهم الفيديو + Caption + Bio + 5 Hashtags",
}

OPTIONS = {
    "compress": [("💎 أعلى جودة", "20"), ("⚖️ متوازن", "26"), ("🚀 ضغط أقوى", "30")],
    "convert": [("⚡ سريع", "fast"), ("⚖️ متوازن", "balanced"), ("💎 جودة عالية", "quality")],
    "resize": [("📱 TikTok/Reels 1080×1920", "1080x1920"), ("▶️ YouTube 1920×1080", "1920x1080"), ("⬛ Instagram 1080×1080", "1080x1080"), ("📱 HD عمودي 720×1280", "720x1280")],
    "speed": [("🐢 0.5×", "0.5"), ("🐢 0.75×", "0.75"), ("▶️ 1.25×", "1.25"), ("🚀 1.5×", "1.5"), ("⚡ 2×", "2.0")],
    "volume": [("🔉 خفض قوي 0.5×", "0.5"), ("🔉 خفض بسيط 0.75×", "0.75"), ("🔊 رفع 1.5×", "1.5"), ("🔊 رفع قوي 2×", "2.0"), ("🚀 رفع أقصى 3×", "3.0")],
    "mirror": [("↔️ أفقي", "horizontal"), ("↕️ عمودي", "vertical")],
    "gray": [("🌫️ خفيف", "light"), ("⚫ متوسط", "medium"), ("⚫ قوي", "full")],
    "sharpen": [("✨ خفيف", "light"), ("✨ متوسط", "medium"), ("💎 قوي", "strong")],
    "snapshot": [("⏱️ 1 ثانية", "1"), ("⏱️ 3 ثوانٍ", "3"), ("⏱️ 5 ثوانٍ", "5"), ("⏱️ 10 ثوانٍ", "10")],
    "gif": [("🎞️ 8fps / 360px", "8,360"), ("🎞️ 12fps / 480px", "12,480"), ("🎞️ 18fps / 720px", "18,720")],
    "thumbnail": [("🖼️ 720px", "720"), ("🖼️ 1280px HD", "1280"), ("🖼️ 1920px Full HD", "1920")],
    "frames": [("🎬 5 لقطات", "5"), ("🎬 10 لقطات", "10"), ("🎬 20 لقطة", "20")],
    "rotate": [("↪️ يمين 90°", "right"), ("↩️ يسار 90°", "left"), ("🔄 180°", "180")],
    "audio": [("🎵 MP3 128k", "mp3,128k"), ("🎵 MP3 192k", "mp3,192k"), ("🎵 MP3 320k", "mp3,320k"), ("🎼 M4A 192k", "m4a,192k"), ("🎙️ WAV", "wav,0")],
    "normalize": [("🎚️ -14 LUFS", "-14"), ("🎚️ -16 LUFS", "-16"), ("🎚️ -18 LUFS", "-18")],
    "imageresize": [("📱 1080×1080", "1080x1080"), ("🖼️ 1920×1080", "1920x1080"), ("📱 1080×1920", "1080x1920"), ("🖼️ 2048×2048", "2048x2048")],
    "jpg": [("📷 جودة 70%", "70"), ("📷 جودة 85%", "85"), ("💎 جودة 95%", "95")],
    "webp": [("🌐 جودة 70%", "70"), ("🌐 جودة 85%", "85"), ("💎 جودة 95%", "95")],
    "imagegray": [("⚫ تطبيق", "medium")],
    "imagesharp": [("✨ خفيف", "light"), ("✨ متوسط", "medium"), ("💎 قوي", "strong")],
    "imageblur": [("🌫️ خفيف", "light"), ("🌫️ متوسط", "medium"), ("🌫️ قوي", "strong")],
    "info": [("🔎 فحص الملف", "run")],
}


def menu_kb():
    b = InlineKeyboardBuilder()
    for key, label in SERVICES.items(): b.button(text=label, callback_data=f"opt:{key}")
    b.button(text="⬅️ الرئيسية", callback_data="home")
    b.adjust(2)
    return b.as_markup()


def options_kb(service: str):
    b = InlineKeyboardBuilder()
    for label, value in OPTIONS[service]: b.button(text=label, callback_data=f"choice:{service}:{value}")
    b.button(text="⬅️ الأدوات", callback_data="options_menu")
    b.adjust(2)
    return b.as_markup()


_original_main = app.main_kb

def main_with_options():
    markup = _original_main()
    rows = [list(row) for row in markup.inline_keyboard]
    rows.insert(0, [InlineKeyboardButton(text="🧰 Pro Studio — كل الأدوات بخيارات", callback_data="options_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

app.main_kb = main_with_options


def get_obj(m: Message):
    return m.video or m.document or m.audio or (m.photo[-1] if m.photo else None)


async def save_file(m: Message, work: Path) -> Path:
    obj = get_obj(m)
    if not obj: raise ToolError("📤 أرسل الملف المناسب للخدمة.")
    size = getattr(obj, "file_size", None)
    if size and size > app.MAX_FILE_MB * 1024 * 1024: raise ToolError(f"الحد الأقصى {app.MAX_FILE_MB}MB")
    info_file = await app.bot.get_file(obj.file_id)
    src = work / "input.bin"
    await app.bot.download_file(info_file.file_path, src)
    return src


async def send_result(m: Message, result: ToolResult, service: str, jid):
    if service == "frames":
        images = sorted(result.workdir.glob("frame_*.jpg"))
        for image in images: await m.answer_photo(FSInputFile(image))
        await m.answer(f"✅ تم استخراج {len(images)} لقطات\n🆔 Job: <code>{jid}</code>", reply_markup=app.main_kb())
        return
    suffix = result.path.suffix.lower()
    caption = f"✅ <b>{html.escape(SERVICES[service])}</b>\n🆔 Job: <code>{jid}</code>"
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}: await m.answer_photo(FSInputFile(result.path), caption=caption, reply_markup=app.main_kb())
    elif suffix in {".mp3", ".wav", ".m4a"}: await m.answer_audio(FSInputFile(result.path), caption=caption, reply_markup=app.main_kb())
    elif suffix == ".gif": await m.answer_document(FSInputFile(result.path), caption=caption, reply_markup=app.main_kb())
    else: await m.answer_video(FSInputFile(result.path), caption=caption, reply_markup=app.main_kb())


async def execute(service: str, option: str, src: Path) -> ToolResult | None:
    if service == "compress": return await compress(src, int(option))
    if service == "convert": return await convert(src, option, {"fast": 24, "balanced": 20, "quality": 18}[option])
    if service == "resize":
        w, h = map(int, option.split("x")); return await resize(src, w, h)
    if service == "speed": return await speed(src, float(option))
    if service == "volume": return await volume_video(src, float(option))
    if service == "mirror": return await mirror(src, option)
    if service == "gray": return await grayscale(src, option)
    if service == "sharpen": return await sharpen(src, option)
    if service == "snapshot": return await snapshot(src, float(option))
    if service == "gif":
        fps, width = map(int, option.split(",")); return await gif(src, fps, width)
    if service == "thumbnail": return await thumbnail(src, int(option))
    if service == "frames": return await frames(src, int(option))
    if service == "rotate": return await rotate(src, option)
    if service == "audio":
        fmt, bitrate = option.split(","); return await audio_convert(src, fmt, bitrate)
    if service == "normalize": return await normalize(src, option)
    if service == "imageresize":
        w, h = map(int, option.split("x")); return await image_resize(src, w, h)
    if service == "jpg": return await image_convert(src, "jpg", int(option))
    if service == "webp": return await image_convert(src, "webp", int(option))
    if service == "imagegray": return await image_filter(src, "gray", option)
    if service == "imagesharp": return await image_filter(src, "sharp", option)
    if service == "imageblur": return await image_filter(src, "blur", option)
    return None


@app.dp.message(F.text == "/pro")
async def pro_command(m: Message):
    app.ensure_user(m.from_user.id, m.from_user.username)
    await m.answer("<b>🧰 NovaBiz Pro Studio</b>\n\nكل أداة تعرض خياراتها قبل التنفيذ.\n\nاختر الخدمة:", reply_markup=menu_kb())


@app.dp.callback_query(F.data == "options_menu")
async def options_menu(q: CallbackQuery):
    await q.message.edit_text("<b>🧰 NovaBiz Pro Studio</b>\n\nاختر الأداة ثم اختر إعدادها:", reply_markup=menu_kb())
    await q.answer()


@app.dp.callback_query(F.data.startswith("opt:"))
async def choose_service(q: CallbackQuery, state: FSMContext):
    service = q.data.split(":", 1)[1]
    if service == "video_ai":
        await state.clear(); await state.set_state(Form.waiting_ai_video)
        await q.message.edit_text("<b>🧠 فهم الفيديو</b>\n\n📤 أرسل الفيديو.\n\nسيتم استخراج لقطات حقيقية وتحليلها وإنشاء Caption وBio وخمسة هاشتاقات وHook وCTA.")
    else:
        await state.clear(); await state.update_data(service=service)
        await q.message.edit_text(f"<b>{html.escape(SERVICES[service])}</b>\n\n⚙️ اختر الإعداد:", reply_markup=options_kb(service))
    await q.answer()


@app.dp.callback_query(F.data.startswith("choice:"))
async def choose_option(q: CallbackQuery, state: FSMContext):
    _, service, option = q.data.split(":", 2)
    if service not in OPTIONS: return await q.answer("الخيار غير متاح", show_alert=True)
    await state.update_data(service=service, option=option)
    await state.set_state(Form.waiting_file)
    label = dict(OPTIONS[service]).get(option, option)
    await q.message.edit_text(f"<b>{html.escape(SERVICES[service])}</b>\n\n⚙️ <b>الإعداد المختار:</b> {html.escape(label)}\n\n📤 أرسل الملف الآن.\n⏳ سيظهر لك التقدم ثم يرسل الناتج بنفس نوعه قدر الإمكان.")
    await q.answer()


@app.dp.message(Form.waiting_ai_video)
async def ai_video(m: Message, state: FSMContext):
    app.ensure_user(m.from_user.id, m.from_user.username)
    if not m.video and not m.document: return await m.answer("📤 أرسل فيديو.")
    cost = 1
    if not app.charge(m.from_user.id, cost): return await m.answer("❌ رصيدك غير كافٍ.")
    jid = app.job_start(m.from_user.id, "video_ai", cost)
    work = Path(tempfile.mkdtemp(prefix="novabiz_ai_input_"))
    progress = await m.answer("⏳ <b>جاري فهم الفيديو...</b>\n\n🧠 تحليل المشاهد وتجهيز المحتوى...")
    try:
        src = await save_file(m, work)
        data, frames_out, frames_dir = await analyze_video(src, frame_count=6)
        hashtags = data.get("hashtags", [])[:5]
        text = (
            "🧠 <b>تحليل الفيديو جاهز</b>\n\n"
            f"🎯 <b>الموضوع:</b> {html.escape(str(data.get('topic','')))}\n"
            f"👤 <b>الجمهور:</b> {html.escape(str(data.get('audience','')))}\n"
            f"🎭 <b>الأسلوب:</b> {html.escape(str(data.get('tone','')))}\n\n"
            f"📝 <b>Caption:</b>\n{html.escape(str(data.get('caption','')))}\n\n"
            f"👤 <b>Bio:</b>\n{html.escape(str(data.get('bio','')))}\n\n"
            f"🪝 <b>Hook:</b> {html.escape(str(data.get('hook','')))}\n"
            f"📣 <b>CTA:</b> {html.escape(str(data.get('cta','')))}\n\n"
            f"#️⃣ <b>الهاشتاقات:</b> {' '.join(map(str, hashtags))}\n\n"
            f"🆔 Job: <code>{jid}</code>"
        )
        app.job_end(jid, True); await state.clear(); await progress.edit_text(text, reply_markup=app.main_kb())
        if frames_out: await m.answer_photo(FSInputFile(frames_out[0]), caption="🖼️ الغلاف المقترح")
        shutil.rmtree(frames_dir, ignore_errors=True)
    except Exception as exc:
        app.refund(m.from_user.id, cost); app.job_end(jid, False, str(exc)); await state.clear()
        await progress.edit_text("❌ <b>فشل فهم الفيديو</b>\n\n" + html.escape(str(exc)) + "\n\n💳 تم إرجاع الرصيد.", reply_markup=app.main_kb())
    finally: shutil.rmtree(work, ignore_errors=True)


@app.dp.message(Form.waiting_file)
async def process_file(m: Message, state: FSMContext):
    data = await state.get_data(); service = data.get("service"); option = data.get("option")
    if service not in OPTIONS or option is None:
        await state.clear(); return await m.answer("❌ انتهت جلسة الأداة.", reply_markup=app.main_kb())
    app.ensure_user(m.from_user.id, m.from_user.username)
    cost = 1
    if not app.charge(m.from_user.id, cost):
        await state.clear(); return await m.answer("❌ رصيدك غير كافٍ.", reply_markup=app.main_kb())
    jid = app.job_start(m.from_user.id, f"options_{service}", cost)
    progress = await m.answer("⏳ <b>جاري تجهيز العملية...</b>\n\n⚙️ تنفيذ الإعداد المختار الآن...")
    work = Path(tempfile.mkdtemp(prefix="novabiz_options_input_")); result = None
    try:
        src = await save_file(m, work)
        if service == "info":
            details = info(src)
            app.job_end(jid, True); await state.clear()
            body = "\n".join(f"<b>{html.escape(k)}</b>: {html.escape(v)}" for k, v in details.items())
            return await progress.edit_text(f"🔎 <b>معلومات الملف</b>\n\n{body}\n\n🆔 Job: <code>{jid}</code>", reply_markup=app.main_kb())
        result = await execute(service, option, src)
        if result is None: raise ToolError("الخدمة غير مفعلة")
        app.job_end(jid, True); await state.clear()
        await progress.edit_text("✅ <b>اكتملت العملية</b>\n\n📤 إرسال الناتج الآن...")
        await send_result(m, result, service, jid)
    except Exception as exc:
        app.refund(m.from_user.id, cost); app.job_end(jid, False, str(exc)); await state.clear()
        await progress.edit_text("❌ <b>فشلت العملية</b>\n\n" + f"السبب: {html.escape(str(exc))}\n\n💳 تم إرجاع الرصيد تلقائياً.", reply_markup=app.main_kb())
    finally:
        if result: cleanup(result)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__": asyncio.run(app.main())
