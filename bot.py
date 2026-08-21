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
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

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
log = logging.getLogger("novaads")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def db_init() -> None:
    with sqlite3.connect(DB) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, credits INTEGER NOT NULL DEFAULT 10, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, user_id INTEGER, service TEXT, status TEXT, credits INTEGER, error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, proof TEXT, status TEXT DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS services(key TEXT PRIMARY KEY, name TEXT, category TEXT, enabled INTEGER DEFAULT 1, credits INTEGER DEFAULT 1);
        """)
        defaults = [
            ("compress_video", "📦 ضغط الفيديو", "media", 1, 1),
            ("convert_video", "🔄 تحويل الفيديو", "media", 1, 1),
            ("extract_audio", "🎵 استخراج الصوت", "media", 1, 1),
            ("extract_frames", "🎞️ استخراج Frames", "media", 1, 1),
            ("resize_video", "📐 تغيير مقاس الفيديو", "video", 1, 1),
            ("ai_writer", "✍️ AI Writer", "writer", 1, 1),
        ]
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
        c.execute("INSERT INTO jobs(id,user_id,service,status,credits) VALUES(?,?,?,?,?)", (jid, uid, service, "processing", cost))
    return jid


def job_end(jid: str, ok: bool, error: str | None = None) -> None:
    with sqlite3.connect(DB) as c:
        c.execute("UPDATE jobs SET status=?,error=? WHERE id=?", ("completed" if ok else "failed", error, jid))


class Form(StatesGroup):
    writer = State()
    waiting_media = State()
    waiting_payment = State()


def main_kb():
    b = InlineKeyboardBuilder()
    items = [
        ("🎬 استوديو الفيديو", "cat:video"), ("🖼️ استوديو الصور", "cat:image"),
        ("🎙️ استوديو الصوت", "cat:audio"), ("📝 استوديو النصوص", "cat:writer"),
        ("🤖 AI Marketing", "cat:marketing"), ("🎞️ محرر الفيديو", "cat:editor"),
        ("🧠 AI Shorts Maker", "cat:shorts"), ("🌍 الترجمة", "cat:translate"),
        ("📱 Social Media", "cat:social"), ("🏪 Business Studio", "cat:business"),
        ("⬇️ Media Tools", "cat:media"), ("🪄 Photo AI", "cat:photo"),
        ("🏭 Content Factory", "cat:factory"), ("👤 حسابي", "account"),
        ("💳 شراء الرصيد", "buy"), ("📊 سجل العمليات", "jobs"), ("🆘 الدعم", "support")]
    for text, data in items:
        b.button(text=text, callback_data=data)
    b.adjust(2)
    if ADMIN_IDS:
        b.button(text="👑 لوحة المدير", callback_data="admin")
    return b.as_markup()


def back_kb():
    b = InlineKeyboardBuilder(); b.button(text="⬅️ الرئيسية", callback_data="home"); return b.as_markup()


def cat_kb(category: str):
    b = InlineKeyboardBuilder()
    if category in {"media", "video", "editor"}:
        tools = [("📦 ضغط الفيديو", "tool:compress_video"), ("🔄 تحويل الصيغة", "tool:convert_video"), ("🎵 استخراج الصوت", "tool:extract_audio"), ("🎞️ استخراج Frames", "tool:extract_frames"), ("📐 تغيير المقاس", "tool:resize_video")]
        for t, d in tools: b.button(text=t, callback_data=d)
    elif category == "writer":
        for t, d in [("✍️ كتابة محتوى", "writer"), ("📢 إعلان", "writer:ad"), ("📱 منشور TikTok", "writer:tiktok"), ("▶️ وصف YouTube", "writer:youtube"), ("🔥 Hook + CTA", "writer:hook")]: b.button(text=t, callback_data=d)
    else:
        b.button(text="✍️ مولد المحتوى", callback_data="writer")
        b.button(text="🖥️ حالة الأدوات", callback_data="status")
    b.button(text="⬅️ الرئيسية", callback_data="home"); b.adjust(1); return b.as_markup()


@dp.message(CommandStart())
async def start(m: Message):
    ensure_user(m.from_user.id, m.from_user.username)
    await m.answer(f"<b>🚀 NovaAds AI ULTRA MAX</b>\n\nاستوديو محتوى داخل Telegram.\n💎 رصيدك: <b>{get_credits(m.from_user.id)}</b> عملية\n\nاختر القسم:", reply_markup=main_kb())


@dp.callback_query(F.data == "home")
async def home(q: CallbackQuery):
    await q.message.edit_text(f"<b>🚀 NovaAds AI ULTRA MAX</b>\n\n💎 رصيدك: <b>{get_credits(q.from_user.id)}</b> عملية\n\nاختر القسم:", reply_markup=main_kb()); await q.answer()


@dp.callback_query(F.data.startswith("cat:"))
async def category(q: CallbackQuery):
    cat = q.data.split(":", 1)[1]
    names = {"video":"🎬 استوديو الفيديو","image":"🖼️ استوديو الصور","audio":"🎙️ استوديو الصوت","writer":"📝 استوديو النصوص","marketing":"🤖 AI Marketing","editor":"🎞️ محرر الفيديو","shorts":"🧠 AI Shorts Maker","translate":"🌍 الترجمة","social":"📱 Social Media","business":"🏪 Business Studio","media":"⬇️ Media Tools","photo":"🪄 Photo AI","factory":"🏭 Content Factory"}
    await q.message.edit_text(f"<b>{names.get(cat, '🛠️ الأدوات')}</b>\n\nتظهر هنا الخدمات التي لها تنفيذ فعلي في هذه النسخة.", reply_markup=cat_kb(cat)); await q.answer()


@dp.callback_query(F.data == "account")
async def account(q: CallbackQuery):
    ensure_user(q.from_user.id, q.from_user.username)
    await q.message.edit_text(f"<b>👤 حسابي</b>\n\n🆔 <code>{q.from_user.id}</code>\n💎 الرصيد: <b>{get_credits(q.from_user.id)}</b>\n👤 @{html.escape(q.from_user.username or 'بدون اسم')}", reply_markup=back_kb()); await q.answer()


@dp.callback_query(F.data == "support")
async def support(q: CallbackQuery):
    await q.message.edit_text(f"<b>🆘 الدعم</b>\n\nتواصل مع الدعم: @{html.escape(SUPPORT)}", reply_markup=back_kb()); await q.answer()


@dp.callback_query(F.data == "buy")
async def buy(q: CallbackQuery):
    b = InlineKeyboardBuilder(); b.button(text="📤 إرسال صورة التحويل", callback_data="payment_proof"); b.button(text="⬅️ الرئيسية", callback_data="home")
    await q.message.edit_text(f"<b>💳 شراء الرصيد</b>\n\n⭐ 20 عملية — 500 ريال يمني\n\nمحفظة جوالي:\n<code>{PAYMENT_WALLET}</code>\n\nبعد التحويل أرسل صورة التحويل.", reply_markup=b.as_markup()); await q.answer()


@dp.callback_query(F.data == "payment_proof")
async def payment_proof(q: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_payment); await q.message.answer("📤 أرسل صورة التحويل الآن."); await q.answer()


@dp.message(Form.waiting_payment, F.photo)
async def receive_payment(m: Message, state: FSMContext):
    ensure_user(m.from_user.id, m.from_user.username)
    file = await bot.get_file(m.photo[-1].file_id)
    path = MEDIA / f"payment_{m.from_user.id}_{uuid.uuid4().hex}.jpg"
    await bot.download_file(file.file_path, path)
    with sqlite3.connect(DB) as c: c.execute("INSERT INTO payments(user_id,amount,proof) VALUES(?,?,?)", (m.from_user.id, 500, str(path)))
    for aid in ADMIN_IDS:
        try: await bot.send_photo(aid, FSInputFile(path), caption=f"💳 طلب دفع جديد\n👤 {m.from_user.id}\n💰 500 ريال")
        except Exception: log.exception("payment notification")
    await state.clear(); await m.answer("✅ تم استلام التحويل وإرساله للمدير للمراجعة.", reply_markup=main_kb())


@dp.callback_query(F.data == "writer")
async def writer(q: CallbackQuery, state: FSMContext):
    await state.update_data(kind="general"); await state.set_state(Form.writer); await q.message.answer("📝 اكتب فكرتك أو المنتج الذي تريد إنشاء محتوى له:"); await q.answer()


@dp.callback_query(F.data.startswith("writer:"))
async def writer_type(q: CallbackQuery, state: FSMContext):
    await state.update_data(kind=q.data.split(":", 1)[1]); await state.set_state(Form.writer); await q.message.answer("📝 اكتب الموضوع أو المنتج:"); await q.answer()


def generate_content(text: str, kind: str) -> str:
    safe = html.escape(text.strip())
    hooks = {"ad":"🔥 عرض يستحق الانتباه!", "tiktok":"🔥 توقف لحظة… عندنا شيء يستحق المشاهدة!", "youtube":"🎬 إليك أهم التفاصيل بشكل واضح.", "hook":"🔥 هل تبحث عن طريقة أفضل؟ إليك الفكرة.", "general":"✨ فكرة جديدة، محتوى أوضح، ونتيجة أقوى."}
    return f"<b>{hooks.get(kind, hooks['general'])}</b>\n\n<b>الموضوع:</b> {safe}\n\n<b>📌 العنوان:</b> {safe[:80]}\n\n<b>📝 الوصف:</b> محتوى مرتب ومباشر يركز على الفائدة ويشجع المتابع على اتخاذ خطوة واضحة.\n\n<b>🎯 CTA:</b> تواصل معنا الآن لمعرفة التفاصيل.\n\n<b>#️⃣ Hashtags:</b> #NovaAds #AI #محتوى #تسويق"


@dp.message(Form.writer)
async def writer_input(m: Message, state: FSMContext):
    ensure_user(m.from_user.id, m.from_user.username); data = await state.get_data(); cost = 1
    if not charge(m.from_user.id, cost): await state.clear(); return await m.answer("❌ رصيدك غير كافٍ.", reply_markup=main_kb())
    jid = job_start(m.from_user.id, "ai_writer", cost)
    try:
        result = generate_content(m.text or "", data.get("kind", "general")); job_end(jid, True); await state.clear(); await m.answer(result, reply_markup=main_kb())
    except Exception as e:
        refund(m.from_user.id, cost); job_end(jid, False, str(e)); await state.clear(); await m.answer("❌ فشلت العملية وتم إرجاع الرصيد.", reply_markup=main_kb())


@dp.callback_query(F.data.startswith("tool:"))
async def tool(q: CallbackQuery, state: FSMContext):
    tool_name = q.data.split(":", 1)[1]
    await state.update_data(tool=tool_name); await state.set_state(Form.waiting_media); await q.message.answer("📤 أرسل الفيديو/الملف المطلوب. الحد الأقصى: 100MB."); await q.answer()


async def run_ffmpeg(args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec("ffmpeg", "-y", *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0: raise RuntimeError(err.decode(errors="ignore")[-1000:])


@dp.message(Form.waiting_media, F.video | F.document)
async def media_input(m: Message, state: FSMContext):
    obj = m.video or m.document
    if not obj: return
    if obj.file_size and obj.file_size > MAX_FILE_MB * 1024 * 1024: return await m.answer(f"❌ الحد الأقصى {MAX_FILE_MB}MB.")
    data = await state.get_data(); tool_name = data.get("tool"); cost = 1
    if not charge(m.from_user.id, cost): await state.clear(); return await m.answer("❌ رصيدك غير كافٍ.", reply_markup=main_kb())
    jid = job_start(m.from_user.id, tool_name, cost); work = MEDIA / f"job_{jid}"; work.mkdir(exist_ok=True)
    try:
        info = await bot.get_file(obj.file_id); src = work / "input"; await bot.download_file(info.file_path, src); out = work / "output"
        if tool_name == "compress_video": await run_ffmpeg(["-i", str(src), "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", "-c:a", "aac", str(out)+".mp4"]); result = Path(str(out)+".mp4")
        elif tool_name == "convert_video": await run_ffmpeg(["-i", str(src), str(out)+".mp4"]); result = Path(str(out)+".mp4")
        elif tool_name == "extract_audio": await run_ffmpeg(["-i", str(src), "-vn", "-c:a", "mp3", str(out)+".mp3"]); result = Path(str(out)+".mp3")
        elif tool_name == "resize_video": await run_ffmpeg(["-i", str(src), "-vf", "scale=-2:720", "-c:a", "copy", str(out)+".mp4"]); result = Path(str(out)+".mp4")
        elif tool_name == "extract_frames":
            await run_ffmpeg(["-i", str(src), "-vf", "fps=1", "-frames:v", "10", str(work/"frame_%02d.jpg")])
            for frame in sorted(work.glob("frame_*.jpg")): await m.answer_photo(FSInputFile(frame))
            job_end(jid, True); await state.clear(); return await m.answer(f"✅ اكتملت العملية\n🆔 Job: <code>{jid}</code>", reply_markup=main_kb())
        else: raise RuntimeError("الأداة غير مفعلة")
        job_end(jid, True); await state.clear(); await m.answer_document(FSInputFile(result), caption=f"✅ اكتملت العملية\n🆔 Job: <code>{jid}</code>", reply_markup=main_kb())
    except Exception as e:
        refund(m.from_user.id, cost); job_end(jid, False, str(e)); await state.clear(); await m.answer(f"❌ فشلت العملية وتم إرجاع الرصيد.\n<code>{html.escape(str(e)[:500])}</code>", reply_markup=main_kb())


@dp.callback_query(F.data == "jobs")
async def jobs(q: CallbackQuery):
    with sqlite3.connect(DB) as c: rows = c.execute("SELECT id,service,status,credits FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (q.from_user.id,)).fetchall()
    text = "<b>📊 آخر العمليات</b>\n\n" + ("\n".join(f"<code>{r[0]}</code> · {r[1]} · {r[2]} · 💎{r[3]}" for r in rows) if rows else "لا توجد عمليات بعد.")
    await q.message.edit_text(text, reply_markup=back_kb()); await q.answer()


@dp.callback_query(F.data == "status")
async def status(q: CallbackQuery):
    ff = "🟢 متاح" if subprocess.run(["bash", "-lc", "command -v ffmpeg"], capture_output=True).returncode == 0 else "🔴 غير متاح"
    await q.message.edit_text(f"<b>🖥️ حالة الأدوات</b>\n\nFFmpeg: {ff}\nقاعدة البيانات: 🟢 SQLite\nAI API Keys: غير مطلوبة للأدوات المحلية", reply_markup=back_kb()); await q.answer()


@dp.callback_query(F.data == "admin")
async def admin(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS: return await q.answer("غير مصرح", show_alert=True)
    with sqlite3.connect(DB) as c:
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]; jobs_count = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]; pending = c.execute("SELECT COUNT(*) FROM payments WHERE status='pending'").fetchone()[0]
    b = InlineKeyboardBuilder(); b.button(text="💳 المدفوعات", callback_data="admin:payments"); b.button(text="⬅️ الرئيسية", callback_data="home"); b.adjust(1)
    await q.message.edit_text(f"<b>👑 SUPER ADMIN</b>\n\n👥 المستخدمون: {users}\n📊 العمليات: {jobs_count}\n💳 طلبات معلقة: {pending}", reply_markup=b.as_markup()); await q.answer()


@dp.callback_query(F.data == "admin:payments")
async def admin_payments(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS: return await q.answer("غير مصرح", show_alert=True)
    with sqlite3.connect(DB) as c: rows = c.execute("SELECT id,user_id FROM payments WHERE status='pending' ORDER BY id DESC LIMIT 10").fetchall()
    b = InlineKeyboardBuilder()
    for pid, uid in rows: b.button(text=f"✅ موافقة #{pid} — {uid}", callback_data=f"approve:{pid}")
    b.button(text="⬅️ المدير", callback_data="admin"); b.adjust(1)
    await q.message.edit_text("<b>💳 طلبات الدفع المعلقة</b>\n\n" + ("لا توجد طلبات." if not rows else "اختر طلبًا للموافقة:"), reply_markup=b.as_markup()); await q.answer()


@dp.callback_query(F.data.startswith("approve:"))
async def approve(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS: return await q.answer("غير مصرح", show_alert=True)
    pid = int(q.data.split(":")[1])
    with sqlite3.connect(DB) as c:
        row = c.execute("SELECT user_id,status FROM payments WHERE id=?", (pid,)).fetchone()
        if not row or row[1] != "pending": return await q.answer("تمت معالجة الطلب", show_alert=True)
        c.execute("UPDATE payments SET status='approved' WHERE id=?", (pid,)); c.execute("UPDATE users SET credits=credits+20 WHERE id=?", (row[0],))
    await bot.send_message(row[0], "✅ تمت الموافقة على التحويل وإضافة <b>20 عملية</b> إلى رصيدك."); await q.answer("تمت الموافقة"); await admin(q)


async def main():
    db_init(); log.info("NovaAds AI ULTRA MAX started"); await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
