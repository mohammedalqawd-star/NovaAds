from __future__ import annotations

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import Settings
from bot.services.catalog import ServiceCatalog
from bot.services.jobs import Job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = Settings.from_env()
bot = Bot(settings.telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
catalog = ServiceCatalog()

CATEGORIES = {
    "video": "🎬 استوديو الفيديو", "image": "🖼️ استوديو الصور", "audio": "🎙️ استوديو الصوت",
    "writer": "📝 AI Writer", "marketing": "📈 AI Marketing", "editor": "🎞️ محرر الفيديو",
    "shorts": "🧠 AI Shorts Maker", "translate": "🌍 الترجمة", "social": "📱 Social Media",
    "business": "🏪 Business Studio", "media": "⬇️ Media Tools", "photo": "🪄 Photo AI",
    "factory": "🏭 Content Factory"
}


def home_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="👤 حسابي", callback_data="account"), InlineKeyboardButton(text="🛠️ الخدمات", callback_data="services")],
        [InlineKeyboardButton(text="💳 شراء رصيد", callback_data="credits"), InlineKeyboardButton(text="📊 سجل العمليات", callback_data="jobs")],
        [InlineKeyboardButton(text="👥 دعوة الأصدقاء", callback_data="referrals"), InlineKeyboardButton(text="🆘 الدعم", url=f"https://t.me/{settings.support_username}")],
        [InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_keyboard() -> InlineKeyboardMarkup:
    keys = list(CATEGORIES.items())
    rows = [[InlineKeyboardButton(text=name, callback_data=f"cat:{key}")] for key, name in keys]
    rows.append([InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "🚀 <b>NovaAds AI ULTRA MAX</b>\n\nAI Content Super Platform\n\n💎 رصيدك: 10 عملية\n\nاختر القسم الذي تريد استخدامه:",
        reply_markup=home_keyboard(),
    )


@dp.callback_query()
async def callbacks(callback: CallbackQuery) -> None:
    data = callback.data or ""
    if data == "home":
        await callback.message.edit_text("🚀 <b>NovaAds AI ULTRA MAX</b>\n\nاختر من القائمة الرئيسية:", reply_markup=home_keyboard())
    elif data == "services":
        await callback.message.edit_text("🛠️ <b>الخدمات</b>\n\nتظهر هنا الخدمات المفعلة فعليًا فقط.", reply_markup=category_keyboard())
    elif data.startswith("cat:"):
        key = data.split(":", 1)[1]
        services = catalog.enabled_by_category(key)
        if not services:
            await callback.answer("هذه الخدمة غير متاحة حاليًا", show_alert=True)
        else:
            rows = [[InlineKeyboardButton(text=f"{s.name} • {s.credits} 💎", callback_data=f"service:{s.key}")] for s in services]
            rows.append([InlineKeyboardButton(text="⬅️ الخدمات", callback_data="services")])
            await callback.message.edit_text(f"{CATEGORIES.get(key, key)}\n\nاختر أداة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    elif data == "credits":
        await callback.message.edit_text(f"💳 <b>شراء الرصيد</b>\n\n🎁 مجاني: 10 عمليات\n⭐ 20 عملية: 500 ريال يمني\n\nالمحفظة: <code>{settings.payment_wallet}</code>\n\nأرسل صورة التحويل بعد الدفع للمراجعة.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")]]))
    elif data == "account":
        await callback.message.edit_text(f"👤 <b>حسابي</b>\n\n🆔 Telegram ID: <code>{callback.from_user.id}</code>\n💎 الرصيد: يتم جلبه من قاعدة البيانات\n📅 الحساب: فعال", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")]]))
    elif data == "jobs":
        await callback.message.edit_text("📊 <b>سجل العمليات</b>\n\nسيتم عرض Job ID والحالة والتكلفة من قاعدة البيانات.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")]]))
    elif data == "referrals":
        await callback.message.edit_text("👥 <b>دعوة الأصدقاء</b>\n\nنظام الإحالة يُحتسب من الخادم فقط لمنع التلاعب.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")]]))
    elif data == "settings":
        await callback.message.edit_text("⚙️ <b>الإعدادات</b>\n\nاللغة، الإشعارات، والخصوصية.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")]]))
    elif data.startswith("service:"):
        service = catalog.get(data.split(":", 1)[1])
        if service is None:
            await callback.answer("الخدمة غير متاحة", show_alert=True)
        else:
            await callback.message.answer(f"⚙️ {service.name}\n\nالخدمة مفعلة فعليًا. أرسل المدخل المطلوب للبدء.")
    await callback.answer()


async def main() -> None:
    logging.info("NovaAds starting with %d admins", len(settings.admin_ids))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
