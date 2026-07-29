import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.connection import Database
from keyboards.main_menu import get_main_menu
from config import Config

logger = logging.getLogger(__name__)
router = Router()
db = Database()

@router.callback_query(F.data == "settings")
async def settings_menu(callback: CallbackQuery):
    """قائمة الإعدادات"""
    user = await db.fetchone(
        "SELECT * FROM users WHERE telegram_id = ?",
        (callback.from_user.id,)
    )
    
    if not user:
        await callback.answer("❌ سجل أولاً بـ /start", show_alert=True)
        return
    
    text = f"""
⚙ <b>الإعدادات</b>

👤 <b>معلومات حسابك:</b>
• الاسم: <b>{user['full_name']}</b>
• المعرف: @{user['username'] or 'بدون'}
• الرصيد: <b>{user['balance']} ريال</b>
• الدور: {user['role']}
• اللغة: {user['language']}
• تاريخ التسجيل: {user['created_at'][:10]}
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 الملف الشخصي", callback_data="my_profile")],
        [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery):
    """الملف الشخصي"""
    user = await db.fetchone(
        "SELECT * FROM users WHERE telegram_id = ?",
        (callback.from_user.id,)
    )
    
    if not user:
        await callback.answer("❌ سجل أولاً", show_alert=True)
        return
    
    # إحصائيات إضافية
    channels_count = await db.fetchone(
        "SELECT COUNT(*) as count FROM channels WHERE owner_id = ?",
        (user['id'],)
    )
    campaigns_count = await db.fetchone(
        "SELECT COUNT(*) as count FROM campaigns WHERE advertiser_id = ?",
        (user['id'],)
    )
    
    text = f"""
👤 <b>الملف الشخصي</b>

📋 <b>المعلومات الأساسية:</b>
• الاسم: <b>{user['full_name']}</b>
• المعرف: @{user['username'] or 'بدون'}
• الرقم: {user['phone'] or 'غير مضاف'}

💰 <b>المعلومات المالية:</b>
• الرصيد: <b>{user['balance']} ريال</b>

📊 <b>إحصائيات:</b>
• القنوات: <b>{channels_count['count'] if channels_count else 0}</b>
• الحملات: <b>{campaigns_count['count'] if campaigns_count else 0}</b>

📅 عضو منذ: <b>{user['created_at'][:10]}</b>
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 الإعدادات", callback_data="settings")],
        [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data == "my_balance")
async def my_balance(callback: CallbackQuery):
    """عرض الرصيد"""
    user = await db.fetchone(
        "SELECT * FROM users WHERE telegram_id = ?",
        (callback.from_user.id,)
    )
    
    if not user:
        await callback.answer("❌ سجل أولاً", show_alert=True)
        return
    
    # آخر المعاملات
    transactions = await db.fetchall(
        "SELECT * FROM wallet WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user['id'],)
    )
    
    text = f"""
💳 <b>رصيدي</b>

💰 الرصيد الحالي: <b>{user['balance']} ريال</b>

📊 <b>آخر المعاملات:</b>
    """
    
    if transactions:
        for t in transactions:
            amount_text = f"+{t['amount']}" if t['amount'] > 0 else str(t['amount'])
            text += f"\n{amount_text} ريال - {t['description'][:50]}"
            text += f"\n   {t['created_at'][:16]}"
    else:
        text += "\nلا توجد معاملات بعد."
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):
    """المساعدة"""
    help_text = """
📚 <b>المساعدة</b>

<b>لأصحاب القنوات:</b>
📢 سجل قناتك من زر "تسجيل قناة"
💰 حدد سعر الإعلان
📊 استقبل طلبات الإعلانات

<b>للمعلنين:</b>
📝 أنشئ حملة من "إنشاء حملة"
🔍 اختر القنوات المناسبة
📈 تابع نتائج حملاتك

<b>للتواصل:</b>
📧 افتح تذكرة دعم
📞 @NovaAdsSupport
    """
    
    await callback.message.edit_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📧 فتح تذكرة", callback_data="new_ticket")],
            [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")],
        ])
    )
    await callback.answer()
