import asyncio, logging, os, re
from pathlib import Path
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from .config import settings
from .db import DB
from .media import text_to_video, images_to_video, edit_video, extract_audio, download

logging.basicConfig(level=logging.INFO)
log=logging.getLogger("hamelha")
router=Router(); db=DB()

class ImgState(StatesGroup): collecting=State()

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="✍️ نص → فيديو",callback_data="text")],
      [InlineKeyboardButton(text="🖼️ صور → فيديو",callback_data="images")],
      [InlineKeyboardButton(text="🎬 تحرير فيديو",callback_data="edit")],
      [InlineKeyboardButton(text="🎵 فيديو → MP3",callback_data="audio")],
      [InlineKeyboardButton(text="⬇️ تحميل من رابط",callback_data="download")],
      [InlineKeyboardButton(text="💎 رصيدي",callback_data="balance")],
    ])

async def user(msg): return await db.user(msg.from_user.id,msg.from_user.username)

@router.message(CommandStart())
async def start(m:Message):
    u=await user(m); await m.answer("🚀 <b>Hamelha AI Studio</b>\n\nمنصة فيديو داخل تيليجرام: نص → فيديو، صور → فيديو، تحرير، استخراج صوت وتحميل الروابط.\n\n🎁 رصيدك المجاني: <b>%s</b> عمليات."%u[2],reply_markup=menu())

@router.message(Command("help"))
async def help_(m:Message): await m.answer("أرسل نصًا لصنع فيديو، أو استخدم الأزرار. لإضافة صور: اختر 🖼️ ثم أرسل الصور واحدة تلو الأخرى ثم /done.")

@router.callback_query(F.data=="balance")
async def balance(c:CallbackQuery):
    u=await db.user(c.from_user.id,c.from_user.username); await c.answer(); await c.message.answer(f"💎 رصيدك الحالي: <b>{u[2]}</b> عملية\n\n👥 الإحالات: {u[3]}\n\nيمكن إضافة نظام الباقات والدفع من إعدادات المشروع لاحقًا.")

async def consume(m):
    await db.user(m.from_user.id,m.from_user.username)
    if not await db.spend(m.from_user.id):
        await m.answer("⛔ انتهى رصيدك المجاني. اطلب من الإدارة تفعيل باقة مدفوعة.")
        return False
    return True

@router.callback_query(F.data=="text")
async def text_mode(c:CallbackQuery): await c.answer(); await c.message.answer("✍️ أرسل النص الآن وسأحوله إلى فيديو عمودي 9:16.")

@router.message(F.text)
async def text_handler(m:Message):
    if m.text.startswith("/") or re.match(r"^https?://",m.text.strip()):
        if re.match(r"^https?://",m.text.strip()): await do_download(m,m.text.strip())
        return
    if len(m.text)<3: return
    if not await consume(m): return
    await m.answer("⏳ جاري إنشاء الفيديو... قد يستغرق ذلك قليلًا.")
    jid=await db.job(m.from_user.id,"text_to_video", "text")
    try:
        out=await text_to_video(m.text,m.from_user.id); await db.set_job(jid,"done",str(out)); await m.answer_video(FSInputFile(out),caption="✅ تم إنشاء الفيديو")
    except Exception as e:
        await db.set_job(jid,"failed",error=str(e)); await m.answer("❌ فشل إنشاء الفيديو. جرّب نصًا أقصر."); log.exception(e)

@router.callback_query(F.data=="images")
async def images_mode(c:CallbackQuery,state:FSMContext): await c.answer(); await state.set_state(ImgState.collecting); await state.update_data(paths=[]); await c.message.answer("🖼️ أرسل الصور واحدة تلو الأخرى. عند الانتهاء أرسل /done")

@router.message(ImgState.collecting, F.photo)
async def collect_photo(m:Message,state:FSMContext,bot:Bot):
    data=await state.get_data(); paths=data.get("paths",[]); p=Path(settings.work_dir)/str(m.from_user.id)/f"upload_{m.photo[-1].file_id}.jpg"; p.parent.mkdir(parents=True,exist_ok=True); await bot.download(m.photo[-1],destination=p); paths.append(str(p)); await state.update_data(paths=paths); await m.answer(f"✅ تم استلام الصورة {len(paths)}")

@router.message(ImgState.collecting, Command("done"))
async def finish_images(m:Message,state:FSMContext):
    data=await state.get_data(); paths=data.get("paths",[]); await state.clear()
    if len(paths)<1: await m.answer("أرسل صورة واحدة على الأقل."); return
    if not await consume(m): return
    await m.answer("⏳ جاري تحويل الصور إلى فيديو...")
    jid=await db.job(m.from_user.id,"images_to_video",str(paths))
    try:
        out=await images_to_video(paths,m.from_user.id); await db.set_job(jid,"done",str(out)); await m.answer_video(FSInputFile(out),caption="✅ تم إنشاء فيديو الصور")
    except Exception as e: await db.set_job(jid,"failed",error=str(e)); await m.answer("❌ حدث خطأ أثناء إنشاء الفيديو.")

@router.callback_query(F.data=="edit")
async def edit_mode(c:CallbackQuery): await c.answer(); await c.message.answer("🎬 أرسل فيديو وسأجهزه تلقائيًا بصيغة Shorts/Reels (9:16).")

@router.message(F.video)
async def video_handler(m:Message,bot:Bot):
    if not await consume(m): return
    p=Path(settings.work_dir)/str(m.from_user.id)/f"input_{m.video.file_unique_id}.mp4"; p.parent.mkdir(parents=True,exist_ok=True); await bot.download(m.video,destination=p); await m.answer("⏳ جاري تحرير الفيديو إلى 9:16...")
    jid=await db.job(m.from_user.id,"edit_video",str(p))
    try:
        out=await edit_video(p,m.from_user.id); await db.set_job(jid,"done",str(out)); await m.answer_video(FSInputFile(out),caption="✅ تم تجهيز الفيديو")
    except Exception as e: await db.set_job(jid,"failed",error=str(e)); await m.answer("❌ تعذر تحرير الفيديو.")

@router.callback_query(F.data=="audio")
async def audio_mode(c:CallbackQuery): await c.answer(); await c.message.answer("🎵 أرسل فيديو وسأستخرج الصوت MP3.")

@router.message(F.document)
async def document_handler(m:Message):
    if m.document.mime_type and m.document.mime_type.startswith("video/"): await m.answer("أرسل الفيديو كفيديو من تيليجرام ليتم تحريره بشكل أفضل.")

async def do_download(m,url):
    if not await consume(m): return
    await m.answer("⬇️ جاري تحميل الفيديو...")
    jid=await db.job(m.from_user.id,"download",url)
    try:
        out=await download(url,m.from_user.id); await db.set_job(jid,"done",str(out)); await m.answer_video(FSInputFile(out),caption="✅ تم التحميل")
    except Exception as e: await db.set_job(jid,"failed",error=str(e)); await m.answer("❌ تعذر التحميل. تأكد من الرابط.")

@router.message(Command("admin"))
async def admin(m:Message):
    if m.from_user.id!=settings.admin_id: return
    await m.answer("🛠️ لوحة الإدارة الأساسية\n• قاعدة البيانات تعمل\n• محرك الفيديو يعمل\n• لإدارة الرصيد استخدم قاعدة البيانات أو أضف لوحة دفع لاحقًا.")

async def main():
    if not settings.bot_token: raise RuntimeError("BOT_TOKEN is missing")
    os.makedirs(settings.work_dir,exist_ok=True); await db.init()
    bot=Bot(settings.bot_token,default=DefaultBotProperties(parse_mode=ParseMode.HTML)); dp=Dispatcher(); dp.include_router(router)
    log.info("Hamelha AI Studio started")
    await dp.start_polling(bot)

if __name__=="__main__": asyncio.run(main())
