import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.connection import Database
from keyboards.main_menu import get_main_menu, get_admin_menu
from config import Config

logger = logging.getLogger(__name__)
router = Router()
db = Database()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """أمر البداية /start"""
    await state.clear()
    
    telegram_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # التحقق من وجود المستخدم
    user = await db.fetchone(
        "SELECT * FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    
    if not user:
        await db.execute(
            """INSERT INTO users (telegram_id, username, full_name, role, created_at, last_seen) 
            VALUES (?, ?, ?, 'visitor', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (telegram_id, username, full_name)
        )
        logger.info(f"👤 مستخدم جديد: {full_name} (ID: {telegram_id})")
        
        welcome_text = f"""
🌟 <b>مرحباً بك في Nova Ads</b> 🌟

أكبر منصة يمنية لإدارة قنوات تيليجرام والإعلانات والاشتراكات.

<b>اختر ما تريد:</b>
        """
    else:
        await db.execute(
            "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE telegram_id = ?",
            (telegram_id,)
        )
        
        welcome_text = f"""
👋 <b>مرحباً بعودتك {full_name}!</b>

<b>اختر ما تريد:</b>
        """
    
    # إذا كان المستخدم مديراً، أظهر له زر لوحة الإدارة
    if telegram_id in Config.ADMIN_IDS:
        await message.answer(welcome_text, reply_markup=get_main_menu(telegram_id))
        await message.answer(
            "👑 <b>أنت مدير المنصة.</b>\nاستخدم لوحة الإدارة للتحكم الكامل.",
            reply_markup=get_admin_menu()
        )
    else:
        await message.answer(welcome_text, reply_markup=get_main_menu(telegram_id))

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """دخول لوحة المدير"""
    await state.clear()
    
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.answer("⛔ ليس لديك صلاحية الوصول للوحة الإدارة.")
        return
    
    admin_text = f"""
👑 <b>لوحة إدارة Nova Ads</b>

مرحباً بك <b>{message.from_user.full_name}</b>.
اختر العملية:
    """
    await message.answer(admin_text, reply_markup=get_admin_menu())

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
📚 <b>المساعدة</b>

<b>لأصحاب القنوات:</b>
• سجل قناتك من زر 📢 تسجيل قناة
• حدد سعر الإعلان وتصنيف القناة
• استقبل طلبات الإعلانات واربح

<b>للمعلنين:</b>
• أنشئ حملة إعلانية من زر 💰 إنشاء حملة
• اختر القنوات المناسبة
• تابع نتائج حملاتك

<b>للتواصل مع الدعم:</b>
@NovaAdsSupport
    """
    await message.answer(help_text)

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📋 <b>القائمة الرئيسية</b>\n\nاختر ما تريد:",
        reply_markup=get_main_menu(callback.from_user.id)
    )
    await callback.answer()
