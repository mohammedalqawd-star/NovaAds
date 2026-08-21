import asyncio, logging, os, re
from pathlib import Path
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from .config import settings
from .db import DB
from .media import text_to_video, images_to_video, edit_video, extract_audio, download

logging.basicConfig(level=logging.INFO); log=logging.getLogger("hamelha")
router=Router(); db=DB()

class ImgState(StatesGroup): collecting=State()
class ModeState(StatesGroup): mode=State()

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="✍️ نص → فيديو",callback_data="text"),InlineKeyboardButton(text="🖼️ صور → فيديو",callback_data="images")],
      [InlineKeyboardButton(text="🎬 تحرير فيديو",callback_data="edit"),InlineKeyboardButton(text="🎵 فيديو → MP3",callback_data="audio")],
      [InlineKeyboardButton(text="⬇️ تحميل من رابط",callback_data="download"),InlineKeyboardButton(text="💎 رصيدي",callback_data="balance")],
      [InlineKeyboardButton(text="👥 دعوة أصدقاء",callback_data="ref"),InlineKeyboardButton(text="ℹ️ المساعدة",callback_data="help")]
    ])

def format_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📱 9:16 Shorts",callback_data="fmt:shorts"),InlineKeyboardButton(text="⬛ 1:1 مربع",callback_data="fmt:square")],[InlineKeyboardButton(text="🖥️ أفقي",callback_data="fmt:landscape")]])

async def user(msg): return await db.user(msg.from_user.id,msg.from_user.username)
async def consume(m):
    await db.user(m.from_user.id,m.from_user.username)
    if not await db.spend(m.from_user.id): await m.answer("⛔ انتهى رصيدك. استخدم 👥 دعوة أصدقاء أو اطلب باقة مدفوعة عند تفعيل الدفع."); return False
    return True

@router.message(CommandStart())
async def start(m:Message):
    u=await user(m); await m.answer(f"🚀 <b>Hamelha AI Studio</b>\n\n🎥 استوديو فيديو كامل داخل Telegram.\n\n✍️ نص → فيديو + صوت عربي\n🖼️ صور → فيديو\n🎬 تجهيز Shorts / Reels\n🎵 فيديو → MP3\n⬇️ تحميل من الروابط\n👥 نظام إحالة\n\n🎁 رصيدك: <b>{u[2]}</b>",reply_markup=menu())

@router.callback_query(F.data=="help")
async def help_cb(c:CallbackQuery): await c.answer(); await c.message.answer("📚 <b>طريقة الاستخدام</b>\n\n1) اختر الخدمة.\n2) أرسل النص/الصور/الفيديو.\n3) انتظر المعالجة.\n4) استلم الفيديو.\n\n🎁 لديك رصيد مجاني. لا تضع أي مفتاح سري داخل GitHub.")

@router.callback_query(F.data=="balance")
async def balance(c:CallbackQuery):
    u=await db.user(c.from_user.id,c.from_user.username); await c.answer(); await c.message.answer(f"💎 <b>رصيدك</b>: {u[2]} عملية\n👥 الإحالات: {u[3]}\n🔗 كود الإحالة: <code>{u[4]}</code>",reply_markup=menu())

@router.callback_query(F.data=="ref")
async def ref(c:CallbackQuery):
    u=await db.user(c.from_user.id,c.from_user.username); await c.answer(); await c.message.answer(f"👥 <b>دعوة الأصدقاء</b>\n\nشارك رابط البوت بهذا الشكل:\n<code>https://t.me/USERNAME?start=ref_{u[4]}</code>\n\nعند تفعيل نظام المكافآت الكامل سنضيف الرصيد تلقائيًا لكل إحالة مؤكدة.")

@router.callback_query(F.data=="text")
async def text_mode(c:CallbackQuery,state:FSMContext): await c.answer(); await state.set_state(ModeState.mode); await state.update_data(mode="text"); await c.message.answer("✍️ أرسل النص الآن. سأصنع فيديو عموديًا مع صوت عربي تلقائيًا.")

@router.message(F.text)
async def text_handler(m:Message,state:FSMContext):
    t=m.text.strip()
    if t.startswith("/"):
        return
    if re.match(r"^https?://",t): return await do_download(m,t)
    data=await state.get_data()
    if data.get("mode")!="text": return await m.answer("اختر خدمة من القائمة أولًا 👇",reply_markup=menu())
    await state.clear()
    if len(t)<3: return await m.answer("أرسل نصًا أطول قليلًا.")
    if not await consume(m): return
    await m.answer("⏳ جاري إنشاء الفيديو والصوت العربي...")
    jid=await db.job(m.from_user.id,"text_to_video","text")
    try:
        out=await text_to_video(t,m.from_user.id,voice=True); await db.set_job(jid,"done",str(out)); await m.answer_video(FSInputFile(out),caption="✅ تم إنشاء الفيديو")
    except Exception as e: await db.set_job(jid,"failed",error=str(e)); await m.answer("❌ فشل إنشاء الفيديو. جرّب نصًا أقصر."); log.exception(e)

@router.callback_query(F.data=="images")
async def images_mode(c:CallbackQuery,state:FSMContext): await c.answer(); await state.set_state(ImgState.collecting); await state.update_data(paths=[]); await c.message.answer("🖼️ أرسل الصور واحدة تلو الأخرى. عند الانتهاء أرسل /done")

@router.message(ImgState.collecting,F.photo)
async def collect_photo(m:Message,state:FSMContext,bot:Bot):
    data=await state.get_data(); paths=data.get("paths",[])
    if len(paths)>=40: return await m.answer("⚠️ الحد الأقصى 40 صورة.")
    p=Path(settings.work_dir)/str(m.from_user.id)/f"upload_{m.photo[-1].file_id}.jpg"; p.parent.mkdir(parents=True,exist_ok=True); await bot.download(m.photo[-1],destination=p); paths.append(str(p)); await state.update_data(paths=paths); await m.answer(f"✅ الصورة {len(paths)} — أرسل المزيد أو /done")

@router.message(ImgState.collecting,Command("done"))
async def finish_images(m:Message,state:FSMContext):
    data=await state.get_data(); paths=data.get("paths",[]); await state.clear()
    if not paths: return await m.answer("لم تصل أي صورة.")
    if not await consume(m): return
    await m.answer("⏳ جاري صنع الفيديو من الصور..."); jid=await db.job(m.from_user.id,"images_to_video",str(paths))
    try:
        out=await images_to_video(paths,m.from_user.id); await db.set_job(jid,"done",str(out)); await m.answer_video(FSInputFile(out),caption="✅ تم إنشاء فيديو الصور")
    except Exception as e: await db.set_job(jid,"failed",error=str(e)); await m.answer("❌ حدث خطأ أثناء إنشاء الفيديو.")

@router.callback_query(F.data=="edit")
async def edit_mode(c:CallbackQuery,state:FSMContext): await c.answer(); await state.set_state(ModeState.mode); await state.update_data(mode="edit"); await c.message.answer("🎬 أرسل الفيديو، وبعده سأعطيك خيارات المقاس.",reply_markup=format_menu())

@router.callback_query(F.data.startswith("fmt:"))
async def fmt(c:CallbackQuery,state:FSMContext): await c.answer(); mode= c.data.split(":",1)[1]; await state.update_data(format=mode,mode="edit"); await c.message.answer("✅ تم اختيار المقاس. أرسل الفيديو الآن.")

@router.callback_query(F.data=="audio")
async def audio_mode(c:CallbackQuery,state:FSMContext): await c.answer(); await state.set_state(ModeState.mode); await state.update_data(mode="audio"); await c.message.answer("🎵 أرسل الفيديو الآن لاستخراج MP3.")

@router.message(F.video)
async def video_handler(m:Message,state:FSMContext,bot:Bot):
    data=await state.get_data(); mode=data.get("mode","edit"); fmt=data.get("format","shorts"); await state.clear()
    if not await consume(m): return
    p=Path(settings.work_dir)/str(m.from_user.id)/f"input_{m.video.file_unique_id}.mp4"; p.parent.mkdir(parents=True,exist_ok=True); await bot.download(m.video,destination=p); await m.answer("⏳ جاري المعالجة...")
    kind="extract_audio" if mode=="audio" else "edit_video"; jid=await db.job(m.from_user.id,kind,str(p))
    try:
        out=await extract_audio(p,m.from_user.id) if mode=="audio" else await edit_video(p,m.from_user.id,fmt)
        await db.set_job(jid,"done",str(out))
        if mode=="audio": await m.answer_document(FSInputFile(out),caption="✅ تم استخراج الصوت MP3")
        else: await m.answer_video(FSInputFile(out),caption=f"✅ تم تجهيز الفيديو — {fmt}")
    except Exception as e: await db.set_job(jid,"failed",error=str(e)); await m.answer("❌ تعذرت المعالجة."); log.exception(e)

@router.callback_query(F.data=="download")
async def download_mode(c:CallbackQuery,state:FSMContext): await c.answer(); await state.set_state(ModeState.mode); await state.update_data(mode="download"); await c.message.answer("⬇️ أرسل رابط الفيديو الآن.")

async def do_download(m,url):
    if not await consume(m): return
    await m.answer("⬇️ جاري التحميل..."); jid=await db.job(m.from_user.id,"download",url)
    try:
        out=await download(url,m.from_user.id); await db.set_job(jid,"done",str(out)); await m.answer_video(FSInputFile(out),caption="✅ تم التحميل")
    except Exception as e: await db.set_job(jid,"failed",error=str(e)); await m.answer("❌ تعذر التحميل. تحقق من الرابط.")

@router.message(Command("admin"))
async def admin(m:Message):
    if m.from_user.id!=settings.admin_id: return
    users,jobs,done=await db.stats(); await m.answer(f"🛠️ <b>لوحة الإدارة</b>\n\n👥 المستخدمون: {users}\n⚙️ العمليات: {jobs}\n✅ الناجحة: {done}\n\nالرصيد: استخدم قاعدة البيانات أو أضف نظام الدفع بعد تحديد طريقة الدفع.")

@router.message(F.document)
async def document_handler(m:Message):
    if m.document.mime_type and m.document.mime_type.startswith("video/"): await m.answer("📹 أرسل الفيديو كـ Video وليس Document لتتم معالجته بشكل أفضل.")

async def main():
    if not settings.bot_token: raise RuntimeError("BOT_TOKEN is missing")
    os.makedirs(settings.work_dir,exist_ok=True); await db.init(); bot=Bot(settings.bot_token,default=DefaultBotProperties(parse_mode=ParseMode.HTML)); dp=Dispatcher(); dp.include_router(router); log.info("Hamelha AI Studio started"); await dp.start_polling(bot)
if __name__=="__main__": asyncio.run(main())
