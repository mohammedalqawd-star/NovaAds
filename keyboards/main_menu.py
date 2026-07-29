from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.connection import Database
from config import Config

db = Database()

def get_main_menu(telegram_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📢 تسجيل قناة", callback_data="register_channel")],
        [InlineKeyboardButton(text="💰 إنشاء حملة إعلانية", callback_data="create_campaign")],
        [InlineKeyboardButton(text="🔎 البحث عن قنوات", callback_data="search_channels")],
        [InlineKeyboardButton(text="💎 الاشتراكات", callback_data="subscriptions_menu")],
        [InlineKeyboardButton(text="❓ المساعدة", callback_data="help")],
        [InlineKeyboardButton(text="📞 الدعم", callback_data="support")],
    ]
    
    # إذا كان المستخدم مديراً
    if telegram_id in Config.ADMIN_IDS:
        buttons.append([InlineKeyboardButton(text="👑 لوحة الإدارة", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_owner_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🏠 الرئيسية", callback_data="main_menu")],
        [InlineKeyboardButton(text="📢 قنواتي", callback_data="my_channels")],
        [InlineKeyboardButton(text="📅 جدولة منشور", callback_data="schedule_post")],
        [InlineKeyboardButton(text="💰 الإعلانات", callback_data="owner_ads")],
        [InlineKeyboardButton(text="💵 الأرباح", callback_data="earnings")],
        [InlineKeyboardButton(text="📈 الإحصائيات", callback_data="statistics")],
        [InlineKeyboardButton(text="💎 الاشتراك", callback_data="my_subscription")],
        [InlineKeyboardButton(text="⚙ الإعدادات", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_advertiser_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="➕ إنشاء حملة", callback_data="create_campaign")],
        [InlineKeyboardButton(text="📋 حملاتي", callback_data="my_campaigns")],
        [InlineKeyboardButton(text="❤️ المفضلة", callback_data="favorites")],
        [InlineKeyboardButton(text="💳 رصيدي", callback_data="my_balance")],
        [InlineKeyboardButton(text="⭐ الاشتراك", callback_data="subscriptions_menu")],
        [InlineKeyboardButton(text="⚙ الإعدادات", callback_data="settings")],
        [InlineKeyboardButton(text="🏠 الرئيسية", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="👥 المستخدمون", callback_data="admin_users")],
        [InlineKeyboardButton(text="📢 القنوات", callback_data="admin_channels")],
        [InlineKeyboardButton(text="💰 الإعلانات", callback_data="admin_campaigns")],
        [InlineKeyboardButton(text="💳 المدفوعات", callback_data="admin_payments")],
        [InlineKeyboardButton(text="💎 الاشتراكات", callback_data="admin_subscriptions")],
        [InlineKeyboardButton(text="💵 الأرباح", callback_data="admin_earnings")],
        [InlineKeyboardButton(text="📊 الإحصائيات", callback_data="admin_statistics")],
        [InlineKeyboardButton(text="📢 إرسال جماعي", callback_data="broadcast")],
        [InlineKeyboardButton(text="⚙ الإعدادات", callback_data="admin_settings")],
        [InlineKeyboardButton(text="📝 السجل", callback_data="admin_logs")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
