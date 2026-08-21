from __future__ import annotations

import asyncio
import html
import logging
import os
import sqlite3
import subprocess
import uuid
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.downloader import DownloadError, available_video_formats, cleanup, download_media, get_media_info

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
MEDIA = DATA / "media"
DATA.mkdir(exist_ok=True)
MEDIA.mkdir(exist_ok=True)
DB = DATA / "novaads.sqlite3"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
SUPPORT = os.getenv("SUPPORT_USERNAME", "NovaAdsSupport1")
PAYMENT_WALLET = os.getenv("PAYMENT_WALLET", "783421319")
FREE_CREDITS = int(os.getenv("FREE_CREDITS", "10"))
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "100"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("novabiz")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


SERVICE_INFO = {
    "media_downloader": {
        "name": "⬇️ تنزيل الفيديو من الرابط",
        "category": "media",
        "desc": "تنزيل الوسائط من الروابط المدعومة عبر yt-dlp مع اختيار جودة الفيديو أو تنزيل الصوت MP3.",
        "how": "اضغط بدء الخدمة، ثم أرسل رابط الفيديو. سيحلل NovaBiz الرابط ويجهز خيارات التنزيل المتاحة.",
    },
    "compress_video": {
        "name": "📦 ضغط الفيديو",
        "category": "video",
        "desc": "يقلل حجم الفيديو مع الحفاظ على جودة مناسبة للنشر والمشاركة.",
        "how": "اضغط بدء الخدمة ثم أرسل الفيديو. سيعاد لك ملف MP4 مضغوط.",
    },
    "convert_video": {
        "name": "🔄 تحويل الفيديو",
        "category": "video",
        "desc": "يعيد ترميز الفيديو إلى MP4 متوافق وسهل التشغيل والمشاركة.",
        "how": "اضغط بدء الخدمة ثم أرسل الفيديو أو الملف.",
    },
    "extract_audio": {
        "name": "🎵 استخراج الصوت",
        "category": "audio",
        "desc": "يفصل المسار الصوتي من الفيديو ويحوله إلى MP3.",
        "how": "ابدأ الخدمة وأرسل الفيديو، وسيصلك ملف الصوت.",
    },
    "extract_frames": {
        "name": "🎞️ استخراج الصور من الفيديو",
        "category": "video",
        "desc": "يستخرج لقطات ثابتة من الفيديو كصور JPG للمراجعة أو الاستخدام في المحتوى.",
        "how": "أرسل الفيديو بعد بدء الخدمة، وسيستخرج البوت مجموعة لقطات تلقائياً.",
    },
    "resize_video": {
        "name": "📐 تغيير مقاس الفيديو",
        "category": "video",
        "desc": "يحوّل الفيديو إلى مقاس محدد فعلياً مع الحفاظ على التناسب وإضافة حواف عند الحاجة حتى يطابق المقاس المختار.",
        "how": "ابدأ الخدمة، اختر المقاس من القائمة، ثم أرسل الفيديو.",
    },
    "resize_image": {
        "name": "🖼️ تغيير مقاس الصورة",
        "category": "image",
        "desc": "يغيّر أبعاد الصورة إلى المقاس الذي تختاره.",
        "how": "ابدأ الخدمة، اختر المقاس، ثم أرسل الصورة.",
    },
    "convert_image": {
        "name": "🧾 تحويل الصورة",
        "category": "image",
        "desc": "يحوّل الصور إلى JPG أو PNG للاستخدام في المنصات المختلفة.",
        "how": "ابدأ الخدمة، اختر الصيغة، ثم أرسل الصورة.",
    },
    "enhance_image": {
        "name": "✨ تحسين الصورة",
        "category": "image",
        "desc": "تحسين محلي للصورة عبر ضبط التباين والحدة باستخدام FFmpeg، بدون ادعاء توليد صورة بالذكاء الاصطناعي.",
        "how": "ابدأ الخدمة ثم أرسل الصورة.",
    },
    "convert_audio": {
        "name": "🎧 تحويل الصوت",
        "category": "audio",
        "desc": "يحوّل الملفات الصوتية المدعومة إلى MP3.",
        "how": "ابدأ الخدمة ثم أرسل ملف الصوت.",
    },
}

SIZE_OPTIONS = {
    "1920x1080": "📺 1920×1080 — 16:9 Full HD",
    "1280x720": "📺 1280×720 — 16:9 HD",
    "1080x1920": "📱 1080×1920 — 9:16 Full HD",
    "720x1280": "📱 720×1280 — 9:16 HD",
    "1080x1080": "⬛ 1080×1080 — 1:1 مربع",
    "1080x1350": "🖼️ 1080×1350 — 4:5 Instagram",
    "1200x1500": "🖼️ 1200×1500 — 4:5",
    "1280x960": "🖥️ 1280×960 — 4:3",
    "1920x1440": "🖥️ 1920×1440 — 4:3",
    "2560x1440": "🖥️ 2560×1440 — 16:9 2K",
}

IMAGE_SIZE_OPTIONS = {
    "1080x1080": "⬛ 1080×1080 — 1:1",
    "1080x1350": "🖼️ 1080×1350 — 4:5",
    "1920x1080": "📺 1920×1080 — 16:9",
    "1080x1920": "📱 1080×1920 — 9:16",
    "1280x720": "📺 1280×720 — 16:9",
    "720x1280": "📱 720×1280 — 9:16",
}


class Form(StatesGroup):
    media_url = State()
    writer = State()
    waiting_media = State()
    waiting_payment = State()
    admin_target = State()
    admin_user_message = State()
    admin_broadcast = State()


def db_init() -> None:
    with sqlite3.connect(DB) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY,
                username TEXT,
                credits INTEGER NOT NULL DEFAULT 10,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                service TEXT,
                status TEXT,
                credits INTEGER,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS payments(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                proof TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS services(
                key TEXT PRIMARY KEY,
                name TEXT,
                category TEXT,
                enabled INTEGER DEFAULT 1,
                credits INTEGER DEFAULT 1
            );
            """
        )
        defaults = [(key, value["name"], value["category"], 1, 1) for key, value in SERVICE_INFO.items()]
        defaults.append(("ai_writer", "✍️ AI Writer", "writer", 1, 1))
        c.executemany("INSERT OR IGNORE INTO services VALUES (?,?,?,?,?)", defaults)


def ensure_user(uid: int, username: str | None = None) -> None:
    with sqlite3.connect(DB) as c:
        c.execute("INSERT OR IGNORE INTO users(id,username,credits) VALUES(?,?,?)", (uid, username, FREE_CREDITS))
        if username is not None:
            c.execute("UPDATE users SET username=? WHERE id=?", (username, uid))


def get_credits(uid: int) -> int:
    with sqlite3.connect(DB) as c:
        row = c.execute("SELECT credits FROM users WHERE id=?", (uid,)).fetchone()
        return int(row[0]) if row else 0


def charge(uid: int, amount: int) -> bool:
    with sqlite3.connect(DB) as c:
        row = c.execute("SELECT credits FROM users WHERE id=?", (uid,)).fetchone()
        if not row or row[0] < amount:
            return False
        c.execute("UPDATE users SET credits=credits-? WHERE id=?", (amount, uid))
        return True


def refund(uid: int, amount: int) -> None:
    with sqlite3.connect(DB) as c:
        c.execute("UPDATE users SET credits=credits+? WHERE id=?", (amount, uid))


def job_start(uid: int, service: str, cost: int) -> str:
    jid = uuid.uuid4().hex[:12]
    with sqlite3.connect(DB) as c:
        c.execute(
            "INSERT INTO jobs(id,user_id,service,status,credits) VALUES(?,?,?,?,?)",
            (jid, uid, service, "processing", cost),
        )
    return jid


def job_end(jid: str, ok: bool, error: str | None = None) -> None:
    with sqlite3.connect(DB) as c:
        c.execute("UPDATE jobs SET status=?,error=? WHERE id=?", ("completed" if ok else "failed", error, jid))


def main_kb():
    b = InlineKeyboardBuilder()
    items = [
        ("🎬 استوديو الفيديو", "cat:video"),
        ("🖼️ استوديو الصور", "cat:image"),
        ("🎙️ استوديو الصوت", "cat:audio"),
        ("📝 استوديو النصوص", "cat:writer"),
        ("🤖 AI Marketing", "cat:marketing"),
        ("🎞️ محرر الفيديو", "cat:editor"),
        ("🧠 AI Shorts Maker", "cat:shorts"),
        ("📱 Social Media", "cat:social"),
        ("🏪 Business Studio", "cat:business"),
        ("⬇️ Media Tools", "cat:media"),
        ("🪄 Photo AI", "cat:photo"),
        ("🏭 Content Factory", "cat:factory"),
        ("👤 حسابي", "account"),
        ("💳 شراء الرصيد", "buy"),
        ("📊 سجل العمليات", "jobs"),
        ("🖥️ حالة الأدوات", "status"),
        ("🆘 الدعم", "support"),
    ]
    for text, data in items:
        b.button(text=text, callback_data=data)
    b.adjust(2)
    if ADMIN_IDS:
        b.button(text="👑 لوحة المدير", callback_data="admin")
    return b.as_markup()


def back_kb():
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ الرئيسية", callback_data="home")
    return b.as_markup()


def service_info_kb(tool_name: str):
    b = InlineKeyboardBuilder()
    b.button(text="🚀 بدء الخدمة", callback_data=f"starttool:{tool_name}")
    b.button(text="ℹ️ كيف تعمل؟", callback_data=f"help:{tool_name}")
    b.button(text="⬅️ رجوع", callback_data=f"cat:{SERVICE_INFO[tool_name]['category']}")
    b.adjust(2, 1)
    return b.as_markup()


def size_kb(options: dict[str, str], prefix: str):
    b = InlineKeyboardBuilder()
    for value, label in options.items():
        b.button(text=label, callback_data=f"{prefix}:{value}")
    b.button(text="⬅️ الرئيسية", callback_data="home")
    b.adjust(2)
    return b.as_markup()


def category_tools(category: str) -> list[str]:
    mapping = {
        "video": ["compress_video", "convert_video", "extract_frames", "resize_video"],
        "editor": ["compress_video", "convert_video", "extract_audio", "resize_video"],
        "media": list(SERVICE_INFO.keys()),
        "image": ["resize_image", "convert_image", "enhance_image"],
        "photo": ["resize_image", "convert_image", "enhance_image"],
        "audio": ["extract_audio", "convert_audio"],
        "writer": ["ai_writer"],
        "marketing": ["ai_writer"],
        "social": ["ai_writer"],
        "business": ["ai_writer"],
        "factory": ["ai_writer", "resize_video", "extract_audio"],
        "shorts": ["resize_video", "extract_frames", "extract_audio", "ai_writer"],
    }
    return mapping.get(category, ["ai_writer"])


def category_title(category: str) -> str:
    return {
        "video": "🎬 استوديو الفيديو",
        "image": "🖼️ استوديو الصور",
        "audio": "🎙️ استوديو الصوت",
        "writer": "📝 استوديو النصوص",
        "marketing": "🤖 AI Marketing",
        "editor": "🎞️ محرر الفيديو",
        "shorts": "🧠 AI Shorts Maker",
        "social": "📱 Social Media",
        "business": "🏪 Business Studio",
        "media": "⬇️ Media Tools",
        "photo": "🪄 Photo AI",
        "factory": "🏭 Content Factory",
    }.get(category, "🛠️ الأدوات")


def category_kb(category: str):
    b = InlineKeyboardBuilder()
    for key in category_tools(category):
        if key == "ai_writer":
            b.button(text="✍️ مولد المحتوى", callback_data="service:ai_writer")
        else:
            b.button(text=SERVICE_INFO[key]["name"], callback_data=f"service:{key}")
    b.button(text="⬅️ الرئيسية", callback_data="home")
    b.adjust(1)
    return b.as_markup()


@dp.message(CommandStart())
async def start(m: Message):
    ensure_user(m.from_user.id, m.from_user.username)
    await m.answer(
        f"<b>🚀 NovaBiz AI ULTRA MAX</b>\n\n"
        f"منصة أدوات عملية داخل Telegram.\n"
        f"كل خدمة لها شرح واضح، زر بدء، وحالة تنفيذ.\n\n"
        f"💎 رصيدك: <b>{get_credits(m.from_user.id)}</b> عملية\n\n"
        f"اختر القسم:",
        reply_markup=main_kb(),
    )


@dp.callback_query(F.data == "home")
async def home(q: CallbackQuery, state: FSMContext):
    await state.clear()
    ensure_user(q.from_user.id, q.from_user.username)
    await q.message.edit_text(
        f"<b>🚀 NovaBiz AI ULTRA MAX</b>\n\n💎 رصيدك: <b>{get_credits(q.from_user.id)}</b> عملية\n\nاختر القسم:",
        reply_markup=main_kb(),
    )
    await q.answer()


@dp.callback_query(F.data.startswith("cat:"))
async def category(q: CallbackQuery):
    cat = q.data.split(":", 1)[1]
    lines = [f"<b>{category_title(cat)}</b>", "", "🛠️ <b>الخدمات المتاحة:</b>", ""]

    for key in category_tools(cat):
        if key == "ai_writer":
            lines.append(
                "✍️ <b>مولد المحتوى</b>\n"
                "إنشاء نصوص تسويقية ومنشورات وأوصاف وهاشتاقات من فكرتك."
            )
        elif key in SERVICE_INFO:
            info = SERVICE_INFO[key]
            lines.append(
                f"{info['name']}\n"
                f"{info['desc']}"
            )
        lines.append("")

    lines.append("👇 اضغط على اسم الخدمة لعرض شرحها الكامل وطريقة استخدامها.")

    await q.message.edit_text(
        "\n".join(lines),
        reply_markup=category_kb(cat),
    )
    await q.answer()


@dp.callback_query(F.data.startswith("service:"))
async def service(q: CallbackQuery):
    key = q.data.split(":", 1)[1]
    if key == "ai_writer":
        text = (
            "<b>✍️ مولد المحتوى</b>\n\n"
            "يُنشئ عنواناً ووصفاً ونداءً للإجراء وهاشتاقات من فكرتك.\n\n"
            "<b>طريقة الاستخدام:</b> اضغط بدء الخدمة ثم اكتب المنتج أو الموضوع.\n"
            "💎 التكلفة: عملية واحدة"
        )
        b = InlineKeyboardBuilder()
        b.button(text="🚀 بدء الخدمة", callback_data="start_writer")
        b.button(text="ℹ️ كيف تعمل؟", callback_data="help:ai_writer")
        b.button(text="⬅️ رجوع", callback_data="cat:writer")
        b.adjust(2, 1)
        await q.message.edit_text(text, reply_markup=b.as_markup())
    else:
        info = SERVICE_INFO[key]
        await q.message.edit_text(
            f"<b>{info['name']}</b>\n\n"
            f"<b>ماذا تفعل؟</b>\n{info['desc']}\n\n"
            f"<b>طريقة الاستخدام:</b>\n{info['how']}\n\n"
            "💎 التكلفة: عملية واحدة",
            reply_markup=service_info_kb(key),
        )
    await q.answer()


@dp.callback_query(F.data.startswith("help:"))
async def help_service(q: CallbackQuery):
    key = q.data.split(":", 1)[1]
    if key == "ai_writer":
        text = (
            "<b>ℹ️ شرح مولد المحتوى</b>\n\n"
            "الأداة تستقبل فكرتك أو اسم المنتج ثم تبني لك نصاً منظماً مناسباً للنشر.\n\n"
            "<b>الخطوات:</b>\n1️⃣ اضغط بدء الخدمة.\n2️⃣ اكتب الفكرة.\n3️⃣ انتظر النتيجة.\n4️⃣ ستصلك النتيجة مع العنوان والوصف وCTA والهاشتاقات."
        )
    else:
        info = SERVICE_INFO[key]
        text = f"<b>ℹ️ {info['name']}</b>\n\n{info['desc']}\n\n<b>الخطوات:</b>\n{info['how']}"
    await q.message.edit_text(text, reply_markup=service_info_kb(key) if key != "ai_writer" else back_kb())
    await q.answer()


@dp.callback_query(F.data.startswith("starttool:"))
async def start_tool(q: CallbackQuery, state: FSMContext):
    key = q.data.split(":", 1)[1]
    if key not in SERVICE_INFO:
        return await q.answer("الخدمة غير موجودة", show_alert=True)
    if key == "media_downloader":
        await state.clear()
        await state.set_state(Form.media_url)
        await q.message.answer(
            "⏳ <b>جاري تجهيز العملية...</b>\n\n"
            "⬇️ <b>تنزيل الفيديو من الرابط</b>\n\n"
            "🔗 أرسل رابط الفيديو الآن.\n"
            "📌 بعد إرسال الرابط سأحلله وأعرض لك الجودات المتاحة وخيار تنزيل الصوت MP3."
        )
        await q.answer()
        return

    if key == "resize_video":
        await state.update_data(tool=key)
        await q.message.edit_text(
            "<b>📐 اختر مقاس الفيديو</b>\n\n"
            "سيتم تنفيذ الأبعاد التي تختارها فعلياً، مع الحفاظ على تناسب المحتوى وإضافة حواف عند الحاجة.\n\n"
            "اختر المقاس المناسب:",
            reply_markup=size_kb(SIZE_OPTIONS, "resize"),
        )
    elif key == "resize_image":
        await state.update_data(tool=key)
        await q.message.edit_text(
            "<b>🖼️ اختر مقاس الصورة</b>\n\nسيتم تنفيذ الأبعاد المختارة فعلياً.",
            reply_markup=size_kb(IMAGE_SIZE_OPTIONS, "resizeimg"),
        )
    elif key == "convert_image":
        await state.update_data(tool=key)
        b = InlineKeyboardBuilder()
        b.button(text="🖼️ JPG", callback_data="imgfmt:jpg")
        b.button(text="🧾 PNG", callback_data="imgfmt:png")
        b.button(text="⬅️ رجوع", callback_data="cat:image")
        b.adjust(2, 1)
        await q.message.edit_text("<b>🧾 اختر صيغة الصورة</b>\n\nثم أرسل الصورة.", reply_markup=b.as_markup())
    else:
        await state.update_data(tool=key)
        await q.message.answer(
            f"⏳ <b>جاري تجهيز العملية...</b>\n\n{SERVICE_INFO[key]['name']}\n📤 أرسل الملف الآن.\n📦 الحد الأقصى: {MAX_FILE_MB}MB."
        )
        await state.set_state(Form.waiting_media)
    await q.answer()


@dp.callback_query(F.data.startswith("resize:"))
async def choose_video_size(q: CallbackQuery, state: FSMContext):
    size = q.data.split(":", 1)[1]
    if size not in SIZE_OPTIONS:
        return await q.answer("المقاس غير صالح", show_alert=True)
    await state.update_data(tool="resize_video", size=size)
    await state.set_state(Form.waiting_media)
    await q.message.edit_text(
        f"<b>✅ تم اختيار المقاس {size}</b>\n\n"
        "📤 أرسل الفيديو الآن.\n"
        "⏳ عند وصوله سيبدأ التنفيذ مباشرة ويظهر لك إشعار <b>جاري تجهيز العملية...</b>."
    )
    await q.answer()


@dp.callback_query(F.data.startswith("resizeimg:"))
async def choose_image_size(q: CallbackQuery, state: FSMContext):
    size = q.data.split(":", 1)[1]
    if size not in IMAGE_SIZE_OPTIONS:
        return await q.answer("المقاس غير صالح", show_alert=True)
    await state.update_data(tool="resize_image", size=size)
    await state.set_state(Form.waiting_media)
    await q.message.edit_text(f"<b>✅ المقاس المختار: {size}</b>\n\n📤 أرسل الصورة الآن.")
    await q.answer()


@dp.callback_query(F.data.startswith("imgfmt:"))
async def choose_image_format(q: CallbackQuery, state: FSMContext):
    fmt = q.data.split(":", 1)[1]
    if fmt not in {"jpg", "png"}:
        return await q.answer("الصيغة غير صالحة", show_alert=True)
    await state.update_data(tool="convert_image", image_format=fmt)
    await state.set_state(Form.waiting_media)
    await q.message.edit_text(f"<b>✅ الصيغة المختارة: {fmt.upper()}</b>\n\n📤 أرسل الصورة الآن.")
    await q.answer()


@dp.callback_query(F.data == "start_writer")
async def start_writer(q: CallbackQuery, state: FSMContext):
    await state.update_data(kind="general")
    await state.set_state(Form.writer)
    await q.message.answer("⏳ <b>جاري تجهيز العملية...</b>\n\n📝 اكتب المنتج أو الفكرة التي تريد إنشاء المحتوى لها.")
    await q.answer()


@dp.callback_query(F.data.startswith("writer:"))
async def writer_type(q: CallbackQuery, state: FSMContext):
    await state.update_data(kind=q.data.split(":", 1)[1])
    await state.set_state(Form.writer)
    await q.message.answer("⏳ <b>جاري تجهيز العملية...</b>\n\n📝 اكتب الموضوع أو المنتج الآن.")
    await q.answer()


def generate_content(text: str, kind: str) -> str:
    safe = html.escape(text.strip())
    hooks = {
        "ad": "🔥 عرض يستحق الانتباه!",
        "tiktok": "🔥 توقف لحظة… عندنا شيء يستحق المشاهدة!",
        "youtube": "🎬 إليك أهم التفاصيل بشكل واضح.",
        "hook": "🔥 هل تبحث عن طريقة أفضل؟ إليك الفكرة.",
        "general": "✨ فكرة جديدة، محتوى أوضح، ونتيجة أقوى.",
    }
    return (
        f"<b>{hooks.get(kind, hooks['general'])}</b>\n\n"
        f"<b>الموضوع:</b> {safe}\n\n"
        f"<b>📌 العنوان:</b> {safe[:80]}\n\n"
        "<b>📝 الوصف:</b> محتوى مرتب ومباشر يركز على الفائدة ويشجع المتابع على اتخاذ خطوة واضحة.\n\n"
        "<b>🎯 CTA:</b> تواصل معنا الآن لمعرفة التفاصيل.\n\n"
        "<b>#️⃣ Hashtags:</b> #NovaBiz #AI #محتوى #تسويق"
    )


@dp.callback_query(F.data == "writer")
async def writer(q: CallbackQuery, state: FSMContext):
    await state.update_data(kind="general")
    await state.set_state(Form.writer)
    await q.message.answer("⏳ <b>جاري تجهيز العملية...</b>\n\n📝 اكتب فكرتك أو المنتج:")
    await q.answer()


@dp.message(Form.writer)
async def writer_input(m: Message, state: FSMContext):
    ensure_user(m.from_user.id, m.from_user.username)
    data = await state.get_data()
    cost = 1
    if not charge(m.from_user.id, cost):
        await state.clear()
        return await m.answer("❌ رصيدك غير كافٍ.", reply_markup=main_kb())
    jid = job_start(m.from_user.id, "ai_writer", cost)
    try:
        result = generate_content(m.text or "", data.get("kind", "general"))
        job_end(jid, True)
        await state.clear()
        await m.answer(result, reply_markup=main_kb())
    except Exception as e:
        refund(m.from_user.id, cost)
        job_end(jid, False, str(e))
        await state.clear()
        await m.answer("❌ فشلت العملية وتم إرجاع الرصيد.", reply_markup=main_kb())


async def run_ffmpeg(args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(err.decode(errors="ignore")[-1500:] or "FFmpeg failed")


def ffmpeg_exists() -> bool:
    return subprocess.run(["bash", "-lc", "command -v ffmpeg"], capture_output=True).returncode == 0


def size_parts(size: str) -> tuple[int, int]:
    w, h = size.split("x", 1)
    return int(w), int(h)


def is_image_message(m: Message) -> bool:
    return bool(m.photo)


async def download_input(obj, work: Path) -> Path:
    info = await bot.get_file(obj.file_id)
    src = work / "input.bin"
    await bot.download_file(info.file_path, src)
    return src


@dp.message(Form.media_url)
async def media_url_input(m: Message, state: FSMContext):
    """استقبال رابط الوسائط وتحليل الجودات المتاحة."""
    url = (m.text or "").strip()

    if not url.startswith(("http://", "https://")):
        return await m.answer(
            "❌ أرسل رابطاً صحيحاً يبدأ بـ <code>http://</code> أو <code>https://</code>."
        )

    ensure_user(m.from_user.id, m.from_user.username)

    progress = await m.answer(
        "⏳ <b>جاري تحليل الرابط...</b>\n\n"
        "🔎 يتم البحث عن الوسائط والجودات المتاحة."
    )

    try:
        info = await get_media_info(url)

        title = html.escape(str(info.get("title") or "بدون عنوان"))
        formats = available_video_formats(info)

        await state.update_data(
            media_url=url,
            media_formats=formats,
            media_title=title,
        )

        b = InlineKeyboardBuilder()

        # عرض أعلى الجودات المتاحة فقط لتجنب ازدحام الأزرار.
        seen = set()
        for fmt in reversed(formats):
            height = fmt.get("height")
            if not height or height in seen:
                continue

            seen.add(height)
            b.button(
                text=f"🎬 {height}p",
                callback_data=f"mediaquality:{fmt['format_id']}",
            )

            if len(seen) >= 6:
                break

        b.button(
            text="🎵 تنزيل الصوت MP3",
            callback_data="mediaaudio",
        )
        b.button(
            text="❌ إلغاء",
            callback_data="media_cancel",
        )
        b.adjust(2, 1)

        await progress.edit_text(
            f"🎬 <b>{title}</b>\n\n"
            "✅ تم تحليل الرابط بنجاح.\n"
            "👇 اختر الجودة المطلوبة:",
            reply_markup=b.as_markup(),
        )

    except DownloadError as e:
        await state.clear()
        await progress.edit_text(
            "❌ <b>تعذر تحليل الرابط</b>\n\n"
            f"السبب: {html.escape(str(e))}"
        )


@dp.callback_query(F.data.startswith("mediaquality:"))
async def media_quality(q: CallbackQuery, state: FSMContext):
    """تنزيل الفيديو بالجودة التي اختارها المستخدم."""
    data = await state.get_data()
    url = data.get("media_url")

    if not url:
        await state.clear()
        return await q.answer("انتهت جلسة التنزيل، أرسل الرابط من جديد.", show_alert=True)

    format_id = q.data.split(":", 1)[1]

    ensure_user(q.from_user.id, q.from_user.username)

    cost = 1
    if not charge(q.from_user.id, cost):
        await state.clear()
        return await q.answer("❌ رصيدك غير كافٍ.", show_alert=True)

    jid = job_start(q.from_user.id, "media_downloader", cost)

    await q.message.edit_text(
        "⏳ <b>جاري تجهيز العملية...</b>\n\n"
        "⬇️ يتم تنزيل الفيديو الآن.\n"
        "📦 قد يستغرق ذلك بعض الوقت حسب حجم الفيديو."
    )

    try:
        result, workdir = await download_media(
            url,
            format_id=format_id,
            audio_only=False,
        )

        if not result.exists() or result.stat().st_size == 0:
            raise DownloadError("لم يتم إنشاء ملف الفيديو.")

        job_end(jid, True)
        await state.clear()

        await q.message.answer_document(
            FSInputFile(result),
            caption=(
                "✅ <b>تم تنزيل الفيديو بنجاح</b>\n"
                f"🆔 Job: <code>{jid}</code>"
            ),
            reply_markup=main_kb(),
        )

        cleanup(workdir)

    except Exception as e:
        refund(q.from_user.id, cost)
        job_end(jid, False, str(e))
        await state.clear()

        await q.message.answer(
            "❌ <b>فشلت عملية التنزيل</b>\n\n"
            "💳 تم إرجاع الرصيد لك تلقائياً.",
            reply_markup=main_kb(),
        )

    await q.answer()


@dp.callback_query(F.data == "mediaaudio")
async def media_audio(q: CallbackQuery, state: FSMContext):
    """تنزيل الصوت MP3 من الرابط."""
    data = await state.get_data()
    url = data.get("media_url")

    if not url:
        await state.clear()
        return await q.answer("انتهت جلسة التنزيل، أرسل الرابط من جديد.", show_alert=True)

    ensure_user(q.from_user.id, q.from_user.username)

    cost = 1
    if not charge(q.from_user.id, cost):
        await state.clear()
        return await q.answer("❌ رصيدك غير كافٍ.", show_alert=True)

    jid = job_start(q.from_user.id, "media_downloader_audio", cost)

    await q.message.edit_text(
        "⏳ <b>جاري تجهيز العملية...</b>\n\n"
        "🎵 يتم استخراج الصوت وتحويله إلى MP3."
    )

    try:
        result, workdir = await download_media(
            url,
            audio_only=True,
        )

        if not result.exists() or result.stat().st_size == 0:
            raise DownloadError("لم يتم إنشاء ملف الصوت.")

        job_end(jid, True)
        await state.clear()

        await q.message.answer_audio(
            FSInputFile(result),
            caption=(
                "✅ <b>تم استخراج الصوت بنجاح</b>\n"
                f"🆔 Job: <code>{jid}</code>"
            ),
        )

        cleanup(workdir)

    except Exception as e:
        refund(q.from_user.id, cost)
        job_end(jid, False, str(e))
        await state.clear()

        await q.message.answer(
            "❌ <b>فشلت عملية التنزيل</b>\n\n"
            "💳 تم إرجاع الرصيد لك تلقائياً.",
            reply_markup=main_kb(),
        )

    await q.answer()


@dp.callback_query(F.data == "media_cancel")
async def media_cancel(q: CallbackQuery, state: FSMContext):
    await state.clear()
    await q.message.edit_text(
        "❌ تم إلغاء عملية التنزيل.",
        reply_markup=main_kb(),
    )
    await q.answer()


@dp.message(Form.waiting_media)
async def media_input(m: Message, state: FSMContext):
    data = await state.get_data()
    tool_name = data.get("tool")
    if not tool_name:
        await state.clear()
        return await m.answer("❌ لم يتم تحديد الخدمة.", reply_markup=main_kb())

    obj = m.video or m.document or m.audio or (m.photo[-1] if m.photo else None)
    if not obj:
        return await m.answer("📤 أرسل الملف المطلوب لهذه الخدمة.")
    if getattr(obj, "file_size", None) and obj.file_size > MAX_FILE_MB * 1024 * 1024:
        return await m.answer(f"❌ الحد الأقصى للملف هو {MAX_FILE_MB}MB.")

    ensure_user(m.from_user.id, m.from_user.username)
    cost = 1
    if not charge(m.from_user.id, cost):
        await state.clear()
        return await m.answer("❌ رصيدك غير كافٍ.", reply_markup=main_kb())

    jid = job_start(m.from_user.id, tool_name, cost)
    progress = await m.answer("⏳ <b>جاري تجهيز العملية...</b>\n\n⚙️ يتم تنفيذ الخدمة الآن، انتظر قليلاً.")
    work = MEDIA / f"job_{jid}"
    work.mkdir(exist_ok=True)

    try:
        src = await download_input(obj, work)
        out_base = work / "output"
        result: Path | None = None

        if tool_name == "compress_video":
            result = Path(str(out_base) + ".mp4")
            await run_ffmpeg([
                "-i", str(src), "-c:v", "libx264", "-crf", "28", "-preset", "veryfast",
                "-c:a", "aac", "-movflags", "+faststart", str(result)
            ])

        elif tool_name == "convert_video":
            result = Path(str(out_base) + ".mp4")
            await run_ffmpeg(["-i", str(src), "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(result)])

        elif tool_name == "extract_audio":
            result = Path(str(out_base) + ".mp3")
            await run_ffmpeg(["-i", str(src), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(result)])

        elif tool_name == "convert_audio":
            result = Path(str(out_base) + ".mp3")
            await run_ffmpeg(["-i", str(src), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(result)])

        elif tool_name == "resize_video":
            size = data.get("size")
            if size not in SIZE_OPTIONS:
                raise RuntimeError("يجب اختيار مقاس الفيديو أولاً")
            w, h = size_parts(size)
            result = Path(str(out_base) + ".mp4")
            vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
            await run_ffmpeg(["-i", str(src), "-vf", vf, "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(result)])

        elif tool_name == "resize_image":
            size = data.get("size")
            if size not in IMAGE_SIZE_OPTIONS:
                raise RuntimeError("يجب اختيار مقاس الصورة أولاً")
            w, h = size_parts(size)
            result = Path(str(out_base) + ".png")
            vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
            await run_ffmpeg(["-i", str(src), "-vf", vf, "-frames:v", "1", str(result)])

        elif tool_name == "convert_image":
            fmt = data.get("image_format", "jpg")
            result = Path(str(out_base) + f".{fmt}")
            args = ["-i", str(src), "-frames:v", "1"]
            if fmt == "jpg":
                args += ["-q:v", "2"]
            args.append(str(result))
            await run_ffmpeg(args)

        elif tool_name == "enhance_image":
            result = Path(str(out_base) + ".jpg")
            await run_ffmpeg([
                "-i", str(src), "-vf", "eq=contrast=1.08:saturation=1.04,unsharp=5:5:0.55:5:5:0.0",
                "-frames:v", "1", "-q:v", "2", str(result)
            ])

        elif tool_name == "extract_frames":
            await run_ffmpeg(["-i", str(src), "-vf", "fps=1", "-frames:v", "10", str(work / "frame_%02d.jpg")])
            frames = sorted(work.glob("frame_*.jpg"))
            if not frames:
                raise RuntimeError("لم يتم استخراج أي لقطة")
            for frame in frames:
                await m.answer_photo(FSInputFile(frame))
            job_end(jid, True)
            await state.clear()
            await progress.edit_text(f"✅ <b>اكتملت العملية</b>\n🎞️ تم استخراج {len(frames)} لقطات.\n🆔 Job: <code>{jid}</code>")
            return await m.answer("اختر خدمة أخرى:", reply_markup=main_kb())

        else:
            raise RuntimeError("الخدمة غير مفعلة")

        if not result or not result.exists() or result.stat().st_size == 0:
            raise RuntimeError("لم يتم إنشاء ملف الناتج")

        job_end(jid, True)
        await state.clear()
        await progress.edit_text(f"✅ <b>اكتملت العملية بنجاح</b>\n🆔 Job: <code>{jid}</code>")
        await m.answer_document(FSInputFile(result), caption=f"📦 الناتج جاهز\n🆔 Job: <code>{jid}</code>", reply_markup=main_kb())
    except Exception as e:
        refund(m.from_user.id, cost)
        job_end(jid, False, str(e))
        await state.clear()
        try:
            await progress.edit_text("❌ <b>فشلت العملية</b>\n\nتم إرجاع الرصيد لك تلقائياً.")
        except Exception:
            pass
        await m.answer(f"❌ تعذر تنفيذ الخدمة.\n<code>{html.escape(str(e)[:700])}</code>", reply_markup=main_kb())


@dp.callback_query(F.data == "account")
async def account(q: CallbackQuery):
    ensure_user(q.from_user.id, q.from_user.username)
    await q.message.edit_text(
        f"<b>👤 حسابي</b>\n\n🆔 <code>{q.from_user.id}</code>\n"
        f"💎 الرصيد: <b>{get_credits(q.from_user.id)}</b>\n"
        f"👤 @{html.escape(q.from_user.username or 'بدون اسم')}",
        reply_markup=back_kb(),
    )
    await q.answer()


@dp.callback_query(F.data == "support")
async def support(q: CallbackQuery):
    await q.message.edit_text(f"<b>🆘 الدعم</b>\n\nتواصل مع الدعم: @{html.escape(SUPPORT)}", reply_markup=back_kb())
    await q.answer()


@dp.callback_query(F.data == "buy")
async def buy(q: CallbackQuery):
    b = InlineKeyboardBuilder()
    b.button(text="📤 إرسال صورة التحويل", callback_data="payment_proof")
    b.button(text="⬅️ الرئيسية", callback_data="home")
    await q.message.edit_text(
        f"<b>💳 شراء الرصيد</b>\n\n⭐ 20 عملية — 500 ريال يمني\n\nمحفظة جوالي:\n<code>{PAYMENT_WALLET}</code>\n\nبعد التحويل أرسل صورة التحويل.",
        reply_markup=b.as_markup(),
    )
    await q.answer()


@dp.callback_query(F.data == "payment_proof")
async def payment_proof(q: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_payment)
    await q.message.answer("📤 أرسل صورة التحويل الآن.")
    await q.answer()


@dp.message(Form.waiting_payment, F.photo)
async def receive_payment(m: Message, state: FSMContext):
    ensure_user(m.from_user.id, m.from_user.username)
    file = await bot.get_file(m.photo[-1].file_id)
    path = MEDIA / f"payment_{m.from_user.id}_{uuid.uuid4().hex}.jpg"
    await bot.download_file(file.file_path, path)
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO payments(user_id,amount,proof) VALUES(?,?,?)", (m.from_user.id, 500, str(path)))
    for aid in ADMIN_IDS:
        try:
            await bot.send_photo(aid, FSInputFile(path), caption=f"💳 طلب دفع جديد\n👤 {m.from_user.id}\n💰 500 ريال")
        except Exception:
            log.exception("payment notification")
    await state.clear()
    await m.answer("✅ تم استلام التحويل وإرساله للمدير للمراجعة.", reply_markup=main_kb())


@dp.callback_query(F.data == "jobs")
async def jobs(q: CallbackQuery):
    with sqlite3.connect(DB) as c:
        rows = c.execute(
            "SELECT id,service,status,credits FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
            (q.from_user.id,),
        ).fetchall()
    text = "<b>📊 آخر العمليات</b>\n\n" + (
        "\n".join(f"<code>{r[0]}</code> · {r[1]} · {r[2]} · 💎{r[3]}" for r in rows)
        if rows else "لا توجد عمليات بعد."
    )
    await q.message.edit_text(text, reply_markup=back_kb())
    await q.answer()


@dp.callback_query(F.data == "status")
async def status(q: CallbackQuery):
    ff = "🟢 متاح" if ffmpeg_exists() else "🔴 غير متاح"
    with sqlite3.connect(DB) as c:
        active = c.execute("SELECT COUNT(*) FROM services WHERE enabled=1").fetchone()[0]
    await q.message.edit_text(
        f"<b>🖥️ حالة الأدوات</b>\n\n"
        f"FFmpeg: {ff}\n"
        f"قاعدة البيانات: 🟢 SQLite\n"
        f"الخدمات المسجلة: <b>{active}</b>\n"
        "الصور والفيديو والصوت: معالجة محلية بدون API خارجي.",
        reply_markup=back_kb(),
    )
    await q.answer()


# ========================= ADMIN =========================

def admin_only(uid: int) -> bool:
    return uid in ADMIN_IDS


def admin_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📨 رسالة لمستخدم", callback_data="admin:message")
    b.button(text="📢 رسالة للجميع", callback_data="admin:broadcast")
    b.button(text="💳 المدفوعات", callback_data="admin:payments")
    b.button(text="👥 المستخدمون", callback_data="admin:users")
    b.button(text="⬅️ الرئيسية", callback_data="home")
    b.adjust(1)
    return b.as_markup()


@dp.callback_query(F.data == "admin")
async def admin(q: CallbackQuery):
    if not admin_only(q.from_user.id):
        return await q.answer("غير مصرح", show_alert=True)
    with sqlite3.connect(DB) as c:
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        jobs_count = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        pending = c.execute("SELECT COUNT(*) FROM payments WHERE status='pending'").fetchone()[0]
    await q.message.edit_text(
        f"<b>👑 SUPER ADMIN — NovaBiz</b>\n\n"
        f"👥 المستخدمون: <b>{users}</b>\n"
        f"📊 العمليات: <b>{jobs_count}</b>\n"
        f"💳 طلبات معلقة: <b>{pending}</b>\n\n"
        "اختر الإجراء الإداري:",
        reply_markup=admin_kb(),
    )
    await q.answer()


@dp.callback_query(F.data == "admin:message")
async def admin_message_start(q: CallbackQuery, state: FSMContext):
    if not admin_only(q.from_user.id):
        return await q.answer("غير مصرح", show_alert=True)
    await state.set_state(Form.admin_target)
    await q.message.answer("📨 أرسل <b>رقم ID المستخدم</b> الذي تريد مراسلته.")
    await q.answer()


@dp.message(Form.admin_target)
async def admin_target_input(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id):
        return await state.clear()
    try:
        target = int((m.text or "").strip())
    except ValueError:
        return await m.answer("❌ أرسل ID رقمي صحيح، مثال: <code>123456789</code>")
    with sqlite3.connect(DB) as c:
        exists = c.execute("SELECT 1 FROM users WHERE id=?", (target,)).fetchone()
    if not exists:
        return await m.answer("❌ هذا المستخدم غير مسجل في قاعدة بيانات البوت.")
    await state.update_data(admin_target=target)
    await state.set_state(Form.admin_user_message)
    await m.answer("✍️ الآن أرسل الرسالة. يمكنك إرسال نص أو صورة أو فيديو أو ملف، وسيتم نسخها للمستخدم.")


@dp.message(Form.admin_user_message)
async def admin_user_message(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id):
        return await state.clear()
    data = await state.get_data()
    target = int(data["admin_target"])
    try:
        await m.send_copy(chat_id=target)
        await m.answer(f"✅ تم إرسال الرسالة إلى المستخدم <code>{target}</code>.", reply_markup=admin_kb())
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        await m.answer(f"❌ تعذر الإرسال للمستخدم.\n<code>{html.escape(str(e)[:500])}</code>")
    finally:
        await state.clear()


@dp.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(q: CallbackQuery, state: FSMContext):
    if not admin_only(q.from_user.id):
        return await q.answer("غير مصرح", show_alert=True)
    with sqlite3.connect(DB) as c:
        count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    await state.set_state(Form.admin_broadcast)
    await q.message.answer(
        f"📢 <b>البث للجميع</b>\n\nسيتم إرسال الرسالة إلى <b>{count}</b> مستخدم مسجل.\n"
        "أرسل الآن النص أو الصورة أو الفيديو أو الملف الذي تريد نشره."
    )
    await q.answer()


@dp.message(Form.admin_broadcast)
async def admin_broadcast(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id):
        return await state.clear()
    with sqlite3.connect(DB) as c:
        users = [row[0] for row in c.execute("SELECT id FROM users ORDER BY id").fetchall()]

    sent = 0
    failed = 0
    for uid in users:
        try:
            await m.send_copy(chat_id=uid)
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(max(1, e.retry_after))
            try:
                await m.send_copy(chat_id=uid)
                sent += 1
            except Exception:
                failed += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception:
            failed += 1

    await state.clear()
    await m.answer(
        f"<b>📢 اكتمل البث</b>\n\n✅ تم الإرسال: <b>{sent}</b>\n❌ فشل: <b>{failed}</b>",
        reply_markup=admin_kb(),
    )


@dp.callback_query(F.data == "admin:users")
async def admin_users(q: CallbackQuery):
    if not admin_only(q.from_user.id):
        return await q.answer("غير مصرح", show_alert=True)
    with sqlite3.connect(DB) as c:
        rows = c.execute("SELECT id,username,credits FROM users ORDER BY created_at DESC LIMIT 15").fetchall()
    text = "<b>👥 آخر المستخدمين</b>\n\n" + (
        "\n".join(f"<code>{uid}</code> · @{html.escape(username or 'بدون') } · 💎{credits}" for uid, username, credits in rows)
        if rows else "لا يوجد مستخدمون."
    )
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ المدير", callback_data="admin")
    await q.message.edit_text(text, reply_markup=b.as_markup())
    await q.answer()


@dp.callback_query(F.data == "admin:payments")
async def admin_payments(q: CallbackQuery):
    if not admin_only(q.from_user.id):
        return await q.answer("غير مصرح", show_alert=True)
    with sqlite3.connect(DB) as c:
        rows = c.execute("SELECT id,user_id FROM payments WHERE status='pending' ORDER BY id DESC LIMIT 10").fetchall()
    b = InlineKeyboardBuilder()
    for pid, uid in rows:
        b.button(text=f"✅ موافقة #{pid} — {uid}", callback_data=f"approve:{pid}")
    b.button(text="⬅️ المدير", callback_data="admin")
    b.adjust(1)
    await q.message.edit_text(
        "<b>💳 طلبات الدفع المعلقة</b>\n\n" + ("لا توجد طلبات." if not rows else "اختر طلباً للموافقة:"),
        reply_markup=b.as_markup(),
    )
    await q.answer()


@dp.callback_query(F.data.startswith("approve:"))
async def approve(q: CallbackQuery):
    if not admin_only(q.from_user.id):
        return await q.answer("غير مصرح", show_alert=True)
    pid = int(q.data.split(":", 1)[1])
    with sqlite3.connect(DB) as c:
        row = c.execute("SELECT user_id,status FROM payments WHERE id=?", (pid,)).fetchone()
        if not row or row[1] != "pending":
            return await q.answer("تمت معالجة الطلب", show_alert=True)
        c.execute("UPDATE payments SET status='approved' WHERE id=?", (pid,))
        c.execute("UPDATE users SET credits=credits+20 WHERE id=?", (row[0],))
    await bot.send_message(row[0], "✅ تمت الموافقة على التحويل وإضافة <b>20 عملية</b> إلى رصيدك.")
    await q.answer("تمت الموافقة")
    await admin(q)


async def main():
    db_init()
    log.info("🚀 NovaBiz AI ULTRA MAX started")
    log.info("👑 Admin IDs loaded: %s", len(ADMIN_IDS))
    log.info("🖥️ FFmpeg available: %s", ffmpeg_exists())
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("⏹ stopped")
