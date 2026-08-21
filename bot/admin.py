from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .config import Settings

router = Router()
settings = Settings.from_env()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def admin(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("🚫 غير مصرح لك بالدخول.")
        return
    await message.answer(
        "👑 <b>SUPER ADMIN PANEL</b>\n\n"
        "📊 Dashboard\n👥 المستخدمون\n💳 طلبات الدفع\n💎 إدارة الرصيد\n"
        "🛍️ الباقات\n🛠️ الخدمات\n💰 أسعار الخدمات\n📢 Broadcast\n"
        "🚫 الحظر\n📈 الإحصائيات\n📋 سجل العمليات\n🖥️ حالة السيرفر"
    )
