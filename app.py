from __future__ import annotations

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.admin import router as admin_router
from bot.config import Settings
from bot.db import init_db
from bot.services.registry import build_catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = Settings.from_env()
bot = Bot(settings.telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(admin_router)
catalog = build_catalog()

CATEGORIES = {
    "video": "🎬 استوديو الفيديو", "image": "🖼️ استوديو الصور", "audio": "🎙️ استوديو الصوت",
    "writer": "📝 AI Writer", "marketing": "📈 AI Marketing", "editor": "🎞️ محرر الفيديو",
    "shorts": "🧠 AI Shorts Maker", "translate": "🌍 الترجمة", "social": "📱 Social Media",
    "business": "🏪 Business Studio", "media": "⬇️ Media Tools", "photo": "🪄 Photo AI",
    "factory": "🏭 Content Factory"
}


def back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")]])


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 حسابي", callback_data="account"), InlineKeyboardButton(text="🛠️ الخدمات", callback_data="services")],
        [InlineKeyboardButton(text="💳 شراء رصيد", callback_data="credits"), InlineKeyboardButton(text="📊 سجل العمليات", callback_data="jobs")],
        [InlineKeyboardButton(text="👥 دعوة الأصدقاء", callback_data="referrals"), InlineKeyboardButton(text="🆘 الدعم", url=f"https://t.me/{settings.support_username}")],
        [InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="settings")],
    ])


def category_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=name, callback_data=f"cat:{key}")] for key, name in CATEGORIES.items()]
    rows.append([InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer("🚀 <b>NovaAds AI ULTRA MAX</b>\n\nAI Content Super Platform\n\n💎 رصيدك: 10 عملية\n\nاختر القسم:", reply_markup=home_keyboard())


@dp.callback_query()
async def callbacks(callback: CallbackQuery) -> None:
    data = callback.data or ""
    if data == "home":
        await callback.message.edit_text("🚀 <b>NovaAds AI ULTRA MAX</b>\n\nاختر من القائمة الرئيسية:", reply_markup=home_keyboard())
    elif data == "services":
        await callback.message.edit_text("🛠️ <b>الخدمات</b>\n\nيتم إظهار الأدوات المفعلة فعليًا فقط.", reply_markup=category_keyboard())
    elif data.startswith("cat:"):
        key = data.split(":", 1)[1]
        services = catalog.enabled_by_category(key)
        if not services:
            await callback.answer("لا توجد خدمة مفعلة في هذا القسم حاليًا.", show_alert=True)
        else:
            rows = [[InlineKeyboardButton(text=f"{s.name} • {s.credits} 💎", callback_data=f"service:{s.key}")] for s in services]
            rows.append([InlineKeyboardButton(text="⬅️ الخدمات", callback_data="services")])
            await callback.message.edit_text(f"{CATEGORIES.get(key, key)}\n\nاختر أداة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    elif data == "credits":
        await callback.message.edit_text(f"💳 <b>شراء الرصيد</b>\n\n🎁 مجاني: 10 عمليات\n⭐ 20 عملية: 500 ريال يمني\n\nالمحفظة: <code>{settings.payment_wallet}</code>\n\nأرسل صورة التحويل للمراجعة اليدوية.", reply_markup=back())
    elif data == "account":
        await callback.message.edit_text(f"👤 <b>حسابي</b>\n\n🆔 Telegram ID: <code>{callback.from_user.id}</code>\n💎 الرصيد: يُدار من قاعدة البيانات\n📊 العمليات: محفوظة في Job History", reply_markup=back())
    elif data == "jobs":
        await callback.message.edit_text("📊 <b>سجل العمليات</b>\n\nكل Job يسجل المعرف والخدمة والحالة والتكلفة والخطأ عند وجوده.", reply_markup=back())
    elif data == "referrals":
        await callback.message.edit_text("👥 <b>دعوة الأصدقاء</b>\n\nيتم احتساب الإحالات من الخادم فقط لمنع التلاعب.", reply_markup=back())
    elif data == "settings":
        await callback.message.edit_text("⚙️ <b>الإعدادات</b>\n\nاللغة والإشعارات والخصوصية.", reply_markup=back())
    elif data.startswith("service:"):
        service = catalog.get(data.split(":", 1)[1])
        if service is None:
            await callback.answer("الخدمة غير متاحة حاليًا.", show_alert=True)
        else:
            await callback.message.answer(f"⚙️ <b>{service.name}</b>\n\nأرسل المدخل المطلوب لبدء المهمة.")
    await callback.answer()


async def main() -> None:
    await init_db(settings.database_url)
    logging.info("NovaAds starting with %d admins", len(settings.admin_ids))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
