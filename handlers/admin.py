import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.connection import Database
from keyboards.main_menu import get_admin_menu, get_main_menu
from config import Config

logger = logging.getLogger(__name__)
router = Router()
db = Database()

class AdminStates(StatesGroup):
    waiting_broadcast_message = State()
    waiting_reply_ticket = State()
    waiting_reject_payment_reason = State()
    waiting_post_to_channel = State()

def is_admin(telegram_id: int) -> bool:
    return telegram_id in Config.ADMIN_IDS

# ============ دخول لوحة المدير ============

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ ليس لديك صلاحية الوصول للوحة الإدارة.")
        return
    
    admin_text = f"""
👑 <b>لوحة إدارة Nova Ads</b>

مرحباً بك <b>{message.from_user.full_name}</b>.
اختر العملية:
    """
    await message.answer(admin_text, reply_markup=get_admin_menu())

# ============ إدارة المستخدمين ============

@router.callback_query(F.data == "admin_users")
async def admin_users_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    total_users = await db.fetchone("SELECT COUNT(*) as count FROM users")
    active_today = await db.fetchone(
        "SELECT COUNT(*) as count FROM users WHERE date(last_seen) = date('now')"
    )
    
    stats_text = f"""
👥 <b>إدارة المستخدمين</b>

• إجمالي: <b>{total_users['count']}</b>
• نشطون اليوم: <b>{active_today['count']}</b>
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 آخر المستخدمين", callback_data="admin_last_users")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(stats_text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data == "admin_last_users")
async def admin_last_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    users = await db.fetchall(
        "SELECT * FROM users ORDER BY created_at DESC LIMIT 10"
    )
    
    if not users:
        await callback.message.edit_text("📋 لا يوجد مستخدمون بعد.")
        return
    
    text = "📋 <b>آخر 10 مستخدمين:</b>\n\n"
    buttons = []
    for u in users:
        role_emoji = {"admin": "👑", "owner": "📢", "advertiser": "💰"}.get(u['role'], "👤")
        text += f"{role_emoji} <b>{u['full_name']}</b> | ID: <code>{u['telegram_id']}</code>\n"
        text += f"   رصيد: {u['balance']} | دور: {u['role']}\n\n"
        
        buttons.append([InlineKeyboardButton(
            text=f"{role_emoji} {u['full_name']}",
            callback_data=f"user_detail_{u['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_users")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("user_detail_"))
async def user_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_detail_", ""))
    user = await db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return
    
    channels_count = await db.fetchone("SELECT COUNT(*) as c FROM channels WHERE owner_id = ?", (user_id,))
    campaigns_count = await db.fetchone("SELECT COUNT(*) as c FROM campaigns WHERE advertiser_id = ?", (user_id,))
    
    text = f"""
👤 <b>{user['full_name']}</b>

📋 <b>معلومات:</b>
• ID: <code>{user['telegram_id']}</code>
• معرف: @{user['username'] or 'بدون'}
• دور: {user['role']}
• رصيد: <b>{user['balance']} ريال</b>
• محظور: {"🚫 نعم" if user['is_banned'] else "✅ لا"}
• القنوات: {channels_count['c'] if channels_count else 0}
• الحملات: {campaigns_count['c'] if campaigns_count else 0}
• تاريخ التسجيل: {user['created_at'][:10]}
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 مراسلة", callback_data=f"msg_user_{user['telegram_id']}")],
        [
            InlineKeyboardButton(
                text="🚫 إلغاء الحظر" if user['is_banned'] else "🚫 حظر",
                callback_data=f"toggle_ban_{user_id}"
            )
        ],
        [InlineKeyboardButton(text="🔙 المستخدمين", callback_data="admin_last_users")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_ban_"))
async def toggle_user_ban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    user_id = int(callback.data.replace("toggle_ban_", ""))
    user = await db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    
    if not user:
        await callback.answer("❌ غير موجود", show_alert=True)
        return
    
    new_status = 0 if user['is_banned'] else 1
    await db.execute("UPDATE users SET is_banned = ? WHERE id = ?", (new_status, user_id))
    
    await callback.answer(f"✅ {'تم إلغاء حظر' if new_status == 0 else 'تم حظر'} المستخدم", show_alert=True)
    await user_detail(callback)

@router.callback_query(F.data.startswith("msg_user_"))
async def msg_user_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    user_telegram_id = int(callback.data.replace("msg_user_", ""))
    await state.update_data(msg_target=user_telegram_id)
    await state.set_state(AdminStates.waiting_reply_ticket)
    
    await callback.message.edit_text(
        "💬 <b>أرسل الرسالة التي تريد إرسالها للمستخدم:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_last_users")]
        ])
    )
    await callback.answer()

@router.message(AdminStates.waiting_reply_ticket)
async def send_msg_to_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    target_id = data.get("msg_target")
    
    try:
        await message.copy_to(chat_id=target_id)
        await message.answer("✅ تم إرسال الرسالة بنجاح")
    except Exception as e:
        await message.answer(f"❌ فشل الإرسال: {e}")
    
    await state.clear()

# ============ إدارة القنوات (النشر الفعلي) ============

@router.callback_query(F.data == "admin_channels")
async def admin_channels_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    total_channels = await db.fetchone("SELECT COUNT(*) as count FROM channels")
    active_channels = await db.fetchone(
        "SELECT COUNT(*) as count FROM channels WHERE status = 'active'"
    )
    
    stats_text = f"""
📢 <b>إدارة القنوات</b>

• إجمالي القنوات: <b>{total_channels['count']}</b>
• نشطة: <b>{active_channels['count']}</b>
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 كل القنوات", callback_data="admin_all_channels")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(stats_text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data == "admin_all_channels")
async def admin_all_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    channels = await db.fetchall(
        """SELECT c.*, u.full_name, u.username as owner_username 
        FROM channels c 
        JOIN users u ON c.owner_id = u.id 
        ORDER BY c.created_at DESC LIMIT 20"""
    )
    
    if not channels:
        await callback.message.edit_text(
            "📭 لا توجد قنوات مسجلة بعد.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_channels")]
            ])
        )
        return
    
    text = "📢 <b>جميع القنوات:</b>\n\n"
    buttons = []
    
    for ch in channels:
        status_emoji = {"active": "🟢", "paused": "🟡", "banned": "🔴"}.get(ch['status'], "⚪")
        text += f"{status_emoji} <b>{ch['title']}</b>\n"
        text += f"   👤 {ch['full_name']} | 👥 {ch['subscribers']} | 💰 {ch['ad_price']} ريال\n\n"
        
        buttons.append([InlineKeyboardButton(
            text=f"{status_emoji} {ch['title'][:30]}",
            callback_data=f"admin_channel_detail_{ch['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_channels")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("admin_channel_detail_"))
async def admin_channel_detail(callback: CallbackQuery):
    """تفاصيل قناة للمدير - مع زر النشر الفعلي"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    channel_id = int(callback.data.replace("admin_channel_detail_", ""))
    channel = await db.fetchone(
        """SELECT c.*, u.full_name, u.telegram_id 
        FROM channels c 
        JOIN users u ON c.owner_id = u.id 
        WHERE c.id = ?""",
        (channel_id,)
    )
    
    if not channel:
        await callback.answer("❌ القناة غير موجودة", show_alert=True)
        return
    
    status_text = {"active": "🟢 نشطة", "paused": "🟡 موقوفة", "banned": "🔴 محظورة"}
    
    detail_text = f"""
📢 <b>{channel['title']}</b>

📊 <b>معلومات القناة:</b>
• Chat ID: <code>{channel['chat_id']}</code>
• الرابط: @{channel['username']}
• المالك: {channel['full_name']} (<code>{channel['telegram_id']}</code>)
• التصنيف: {channel['category']}
• المشتركين: <b>{channel['subscribers']}</b>
• سعر الإعلان: <b>{channel['ad_price']} ريال</b>
• الحالة: {status_text.get(channel['status'], channel['status'])}
• التقييم: ⭐ {channel['rating']}/5
• الإعلانات المنفذة: {channel['total_ads_completed']}
• الأرباح: <b>{channel['total_earnings']} ريال</b>
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 نشر في القناة", callback_data=f"post_to_channel_{channel_id}")],
        [
            InlineKeyboardButton(
                text="⏸ إيقاف" if channel['status'] == 'active' else "▶️ تفعيل",
                callback_data=f"admin_toggle_ch_{channel_id}"
            ),
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"admin_delete_ch_{channel_id}")
        ],
        [InlineKeyboardButton(text="🔙 كل القنوات", callback_data="admin_all_channels")],
    ])
    
    await callback.message.edit_text(detail_text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data.startswith("post_to_channel_"))
async def post_to_channel_start(callback: CallbackQuery, state: FSMContext):
    """بدء النشر في قناة محددة"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    channel_id = int(callback.data.replace("post_to_channel_", ""))
    channel = await db.fetchone("SELECT * FROM channels WHERE id = ?", (channel_id,))
    
    if not channel:
        await callback.answer("❌ القناة غير موجودة", show_alert=True)
        return
    
    await state.update_data(post_channel_id=channel_id, post_chat_id=channel['chat_id'])
    await state.set_state(AdminStates.waiting_post_to_channel)
    
    await callback.message.edit_text(
        f"📢 <b>نشر في: {channel['title']}</b>\n\n"
        "أرسل الرسالة التي تريد نشرها الآن:\n"
        "(نص، صورة، فيديو، ملف...)\n\n"
        "سيتم نشرها مباشرة في القناة.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_channel_detail_{channel_id}")]
        ])
    )
    await callback.answer()

@router.message(AdminStates.waiting_post_to_channel)
async def execute_post_to_channel(message: Message, state: FSMContext):
    """تنفيذ النشر الفعلي في القناة"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    chat_id = data.get("post_chat_id")
    channel_id = data.get("post_channel_id")
    
    try:
        # نشر الرسالة فعلياً في القناة
        sent_message = await message.copy_to(chat_id=chat_id)
        
        # استخراج رابط المنشور
        chat_id_str = str(chat_id)
        if chat_id_str.startswith("-100"):
            clean_id = chat_id_str[4:]
        else:
            clean_id = chat_id_str.replace("-", "")
        
        post_link = f"https://t.me/c/{clean_id}/{sent_message.message_id}"
        
        await message.answer(
            f"✅ <b>تم النشر بنجاح في القناة!</b>\n\n"
            f"🔗 <a href='{post_link}'>رابط المنشور</a>",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 تفاصيل القناة", callback_data=f"admin_channel_detail_{channel_id}")]
            ])
        )
        
        # تحديث عداد الإعلانات
        await db.execute(
            "UPDATE channels SET total_ads_completed = total_ads_completed + 1 WHERE id = ?",
            (channel_id,)
        )
        
    except Exception as e:
        error_msg = str(e)
        if "not enough rights" in error_msg.lower() or "forbidden" in error_msg.lower():
            await message.answer(
                "❌ <b>البوت ليس لديه صلاحية النشر في هذه القناة!</b>\n\n"
                "تأكد أن البوت مشرف في القناة ولديه صلاحية نشر الرسائل.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 تفاصيل القناة", callback_data=f"admin_channel_detail_{channel_id}")]
                ])
            )
        else:
            await message.answer(
                f"❌ فشل النشر: {error_msg[:200]}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 تفاصيل القناة", callback_data=f"admin_channel_detail_{channel_id}")]
                ])
            )
    
    await state.clear()

@router.callback_query(F.data.startswith("admin_toggle_ch_"))
async def admin_toggle_channel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    channel_id = int(callback.data.replace("admin_toggle_ch_", ""))
    channel = await db.fetchone("SELECT * FROM channels WHERE id = ?", (channel_id,))
    
    if not channel:
        await callback.answer("❌ غير موجودة", show_alert=True)
        return
    
    new_status = "paused" if channel['status'] == "active" else "active"
    await db.execute("UPDATE channels SET status = ? WHERE id = ?", (new_status, channel_id))
    
    await callback.answer(f"✅ {'تم إيقاف' if new_status == 'paused' else 'تم تفعيل'} القناة", show_alert=True)
    await admin_channel_detail(callback)

@router.callback_query(F.data.startswith("admin_delete_ch_"))
async def admin_delete_channel_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    channel_id = int(callback.data.replace("admin_delete_ch_", ""))
    channel = await db.fetchone("SELECT * FROM channels WHERE id = ?", (channel_id,))
    
    await callback.message.edit_text(
        f"⚠️ <b>حذف قناة</b>\n\n"
        f"القناة: <b>{channel['title']}</b>\n"
        f"الرابط: @{channel['username']}\n\n"
        f"❌ لا يمكن التراجع!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ نعم احذف", callback_data=f"admin_confirm_delete_ch_{channel_id}")],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_channel_detail_{channel_id}")],
        ])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_confirm_delete_ch_"))
async def admin_execute_delete_channel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    channel_id = int(callback.data.replace("admin_confirm_delete_ch_", ""))
    await db.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    
    await callback.answer("🗑 تم حذف القناة", show_alert=True)
    await admin_all_channels(callback)

# ============ المدفوعات ============

@router.callback_query(F.data == "admin_payments")
async def admin_payments_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    pending_payments = await db.fetchall(
        """SELECT p.*, u.full_name, u.username, u.telegram_id,
        COALESCE(c.title, s.name) as item_name
        FROM payments p 
        JOIN users u ON p.user_id = u.id 
        LEFT JOIN campaigns c ON p.campaign_id = c.id
        LEFT JOIN subscriptions s ON p.subscription_id = s.id
        WHERE p.status = 'pending' 
        ORDER BY p.created_at DESC 
        LIMIT 20"""
    )
    
    if not pending_payments:
        text = "📭 لا توجد مدفوعات معلقة حالياً."
    else:
        text = f"💳 <b>طلبات الدفع المعلقة ({len(pending_payments)}):</b>\n\n"
        for p in pending_payments:
            item_type = "حملة" if p['campaign_id'] else "اشتراك"
            text += f"🔑 <b>#{p['id']}</b> | {item_type}: {p['item_name'] or 'غير معروف'}\n"
            text += f"👤 {p['full_name']} | 💰 <b>{p['amount']} ريال</b>\n"
            text += f"🏦 {p['method']} | 📅 {p['created_at'][:16]}\n\n"
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ مراجعة المدفوعات", callback_data="admin_review_payments")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data == "admin_review_payments")
async def admin_review_payments(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    pending = await db.fetchall(
        """SELECT p.*, u.full_name, u.username, u.telegram_id,
        COALESCE(c.title, s.name) as item_name
        FROM payments p 
        JOIN users u ON p.user_id = u.id 
        LEFT JOIN campaigns c ON p.campaign_id = c.id
        LEFT JOIN subscriptions s ON p.subscription_id = s.id
        WHERE p.status = 'pending' 
        ORDER BY p.created_at ASC 
        LIMIT 1"""
    )
    
    if not pending:
        await callback.message.edit_text(
            "✅ لا توجد مدفوعات معلقة.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_payments")]
            ])
        )
        return
    
    p = pending[0]
    item_type = "حملة إعلانية" if p['campaign_id'] else "اشتراك"
    
    text = f"""
💳 <b>مراجعة دفعة #{p['id']}</b>

👤 <b>المستخدم:</b> {p['full_name']}
   ID: <code>{p['telegram_id']}</code>
   @{p['username'] or 'بدون'}

📋 <b>النوع:</b> {item_type}
📝 <b>العنوان:</b> {p['item_name'] or 'غير معروف'}

💰 <b>المبلغ:</b> {p['amount']} ريال
🏦 <b>طريقة الدفع:</b> {p['method']}
📅 <b>التاريخ:</b> {p['created_at'][:16]}
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 عرض الحوالة", callback_data=f"view_receipt_{p['id']}")],
        [
            InlineKeyboardButton(text="✅ قبول", callback_data=f"approve_payment_{p['id']}"),
            InlineKeyboardButton(text="❌ رفض", callback_data=f"reject_payment_{p['id']}")
        ],
        [InlineKeyboardButton(text="⏭ تخطي", callback_data="admin_review_payments")],
        [InlineKeyboardButton(text="🔙 المدفوعات", callback_data="admin_payments")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data.startswith("view_receipt_"))
async def view_receipt(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    payment_id = int(callback.data.replace("view_receipt_", ""))
    payment = await db.fetchone("SELECT * FROM payments WHERE id = ?", (payment_id,))
    
    if payment and payment['receipt_image_id']:
        try:
            await callback.bot.send_photo(
                callback.message.chat.id,
                payment['receipt_image_id'],
                caption=f"📸 إيصال الدفعة #{payment_id}"
            )
            await callback.answer("✅ تم إرسال الصورة")
        except Exception as e:
            await callback.answer(f"❌ لا يمكن عرض الصورة: {e}", show_alert=True)
    else:
        await callback.answer("❌ لا توجد صورة مرفقة", show_alert=True)

@router.callback_query(F.data.startswith("approve_payment_"))
async def approve_payment(callback: CallbackQuery):
    """قبول الدفعة وتفعيل الاشتراك أو الحملة"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    payment_id = int(callback.data.replace("approve_payment_", ""))
    payment = await db.fetchone("SELECT * FROM payments WHERE id = ?", (payment_id,))
    
    if not payment:
        await callback.answer("❌ الدفعة غير موجودة", show_alert=True)
        return
    
    # تحديث حالة الدفع
    await db.execute(
        "UPDATE payments SET status = 'approved', admin_id = ? WHERE id = ?",
        (callback.from_user.id, payment_id)
    )
    
    # إذا كان اشتراك
    if payment['subscription_id']:
        plan = await db.fetchone("SELECT * FROM subscriptions WHERE id = ?", (payment['subscription_id'],))
        
        now = datetime.now()
        end_date = now + timedelta(days=30)
        
        # إلغاء القديم
        await db.execute(
            "UPDATE user_subscriptions SET status = 'expired' WHERE user_id = ? AND status = 'active'",
            (payment['user_id'],)
        )
        
        # تفعيل الجديد
        await db.execute(
            """INSERT INTO user_subscriptions 
            (user_id, subscription_id, start_date, end_date, status) 
            VALUES (?, ?, ?, ?, 'active')""",
            (payment['user_id'], payment['subscription_id'], 
             now.strftime('%Y-%m-%d %H:%M:%S'), 
             end_date.strftime('%Y-%m-%d %H:%M:%S'))
        )
        
        # إشعار المستخدم
        try:
            await callback.bot.send_message(
                payment['user_id'],
                f"🎉 <b>تم تفعيل اشتراكك!</b>\n\n"
                f"⭐ الخطة: <b>{plan['name']}</b>\n"
                f"📅 صالح حتى: <b>{end_date.strftime('%Y-%m-%d')}</b>\n\n"
                "شكراً لثقتك بـ Nova Ads!"
            )
        except:
            pass
    
    # إذا كان حملة
    elif payment['campaign_id']:
        await db.execute(
            "UPDATE campaigns SET status = 'pending_admin' WHERE id = ?",
            (payment['campaign_id'],)
        )
        
        try:
            await callback.bot.send_message(
                payment['user_id'],
                f"✅ <b>تم تأكيد الدفع!</b>\n\n"
                "حملتك قيد المراجعة الآن وسيتم البدء في تنفيذها قريباً."
            )
        except:
            pass
    
    await callback.answer("✅ تم قبول الدفعة", show_alert=True)
    await admin_review_payments(callback)

@router.callback_query(F.data.startswith("reject_payment_"))
async def reject_payment(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    payment_id = int(callback.data.replace("reject_payment_", ""))
    await state.update_data(reject_payment_id=payment_id)
    await state.set_state(AdminStates.waiting_reject_payment_reason)
    
    await callback.message.edit_text(
        "❌ <b>سبب الرفض:</b>\n\nأرسل سبب رفض الدفعة:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 تراجع", callback_data="admin_review_payments")]
        ])
    )
    await callback.answer()

@router.message(AdminStates.waiting_reject_payment_reason)
async def execute_reject_payment(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    payment_id = data.get("reject_payment_id")
    reason = message.text.strip()
    
    await db.execute(
        "UPDATE payments SET status = 'rejected', admin_comment = ?, admin_id = ? WHERE id = ?",
        (reason, message.from_user.id, payment_id)
    )
    
    payment = await db.fetchone("SELECT * FROM payments WHERE id = ?", (payment_id,))
    
    if payment:
        try:
            await message.bot.send_message(
                payment['user_id'],
                f"❌ <b>تم رفض الدفعة #{payment_id}</b>\n\n"
                f"السبب: {reason}\n\n"
                "يرجى مراجعة البيانات والمحاولة مرة أخرى."
            )
        except:
            pass
    
    await state.clear()
    await message.answer("✅ تم رفض الدفعة وإشعار المستخدم.", reply_markup=get_admin_menu())

# ============ الإحصائيات ============

@router.callback_query(F.data == "admin_statistics")
async def admin_statistics(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    total_users = await db.fetchone("SELECT COUNT(*) as count FROM users")
    total_channels = await db.fetchone("SELECT COUNT(*) as count FROM channels")
    total_campaigns = await db.fetchone("SELECT COUNT(*) as count FROM campaigns")
    
    total_earnings = await db.fetchone(
        "SELECT SUM(amount) as total FROM wallet WHERE transaction_type = 'commission'"
    )
    
    today_users = await db.fetchone(
        "SELECT COUNT(*) as count FROM users WHERE date(created_at) = date('now')"
    )
    
    stats_text = f"""
📊 <b>إحصائيات المنصة</b>

👥 المستخدمون: <b>{total_users['count']}</b>
📢 القنوات: <b>{total_channels['count']}</b>
💰 الحملات: <b>{total_campaigns['count']}</b>
💵 إجمالي الأرباح: <b>{total_earnings['total'] or 0} ريال</b>

📈 <b>اليوم:</b>
• مستخدمون جدد: <b>+{today_users['count']}</b>
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(stats_text, reply_markup=buttons)
    await callback.answer()

# ============ الإرسال الجماعي ============

@router.callback_query(F.data == "broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_broadcast_message)
    await state.update_data(is_test_post=False)
    
    await callback.message.edit_text(
        "📢 <b>إرسال جماعي</b>\n\n"
        "أرسل الرسالة التي تريد إرسالها لجميع المستخدمين.\n\n"
        "أو اضغط /cancel للإلغاء.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 إلغاء", callback_data="main_menu")]
        ])
    )
    await callback.answer()

@router.message(AdminStates.waiting_broadcast_message)
async def broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    
    # إذا كان نشر في قناة
    if data.get("is_test_post"):
        await execute_post_to_channel(message, state)
        return
    
    # إرسال جماعي
    users = await db.fetchall("SELECT telegram_id FROM users WHERE is_banned = 0")
    
    success = 0
    failed = 0
    
    await message.answer(f"🔄 جاري الإرسال إلى {len(users)} مستخدم...")
    
    for user in users:
        try:
            await message.copy_to(chat_id=user['telegram_id'])
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>تم الإرسال الجماعي</b>\n\n"
        f"✅ ناجح: <b>{success}</b>\n"
        f"❌ فشل: <b>{failed}</b>",
        reply_markup=get_admin_menu()
    )

# ============ التذاكر ============

@router.message(Command("tickets"))
async def cmd_tickets(message: Message):
    """عرض التذاكر المفتوحة للمدير"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ غير مصرح")
        return
    
    open_tickets = await db.fetchall(
        """SELECT t.*, u.full_name, u.telegram_id, u.username
        FROM support_tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.status = 'open'
        ORDER BY t.created_at DESC"""
    )
    
    if not open_tickets:
        await message.answer("📭 لا توجد تذاكر مفتوحة حالياً.")
        return
    
    text = f"📧 <b>التذاكر المفتوحة ({len(open_tickets)}):</b>\n\n"
    buttons = []
    
    for t in open_tickets:
        text += f"🔑 <b>#{t['id']}</b> - {t['subject'][:50]}\n"
        text += f"👤 {t['full_name']} | 📅 {t['created_at'][:10]}\n\n"
        
        buttons.append([InlineKeyboardButton(
            text=f"🔑 #{t['id']} - {t['subject'][:30]}",
            callback_data=f"admin_ticket_{t['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_users")])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ============ نشر الحملات في القنوات ============

@router.callback_query(F.data == "admin_campaigns")
async def admin_campaigns_list(callback: CallbackQuery):
    """عرض الحملات للمدير"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    # الحملات الجاهزة للنشر (تم الدفع والموافقة)
    ready_campaigns = await db.fetchall(
        """SELECT c.*, u.full_name, u.username
        FROM campaigns c
        JOIN users u ON c.advertiser_id = u.id
        WHERE c.status IN ('pending_admin', 'active')
        ORDER BY c.created_at DESC"""
    )
    
    if not ready_campaigns:
        text = "📭 لا توجد حملات جاهزة للنشر."
    else:
        text = f"💰 <b>الحملات الجاهزة ({len(ready_campaigns)}):</b>\n\n"
        for c in ready_campaigns:
            status_emoji = {"pending_admin": "🟡", "active": "🟢"}.get(c['status'], "⚪")
            text += f"{status_emoji} <b>#{c['id']}</b> - {c['title']}\n"
            text += f"   👤 {c['full_name']} | 💰 {c['budget']} ريال\n"
            text += f"   📢 {c['channels_count']} قناة | 📂 {c['target_categories']}\n\n"
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 عرض الحملات الجاهزة", callback_data="admin_ready_campaigns")],
        [InlineKeyboardButton(text="📋 كل الحملات", callback_data="admin_all_campaigns")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data == "admin_ready_campaigns")
async def admin_ready_campaigns(callback: CallbackQuery):
    """عرض الحملات الجاهزة للنشر"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    campaigns = await db.fetchall(
        """SELECT c.*, u.full_name, u.username, u.telegram_id
        FROM campaigns c
        JOIN users u ON c.advertiser_id = u.id
        WHERE c.status IN ('pending_admin', 'active')
        ORDER BY c.created_at ASC"""
    )
    
    if not campaigns:
        await callback.message.edit_text(
            "📭 لا توجد حملات جاهزة للنشر.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_campaigns")]
            ])
        )
        return
    
    text = "🚀 <b>اختر حملة للنشر:</b>\n\n"
    buttons = []
    
    for c in campaigns:
        text += f"🔑 <b>#{c['id']}</b> - {c['title']}\n"
        text += f"   👤 {c['full_name']} | 💰 {c['budget']} ريال | 📢 {c['channels_count']} قناة\n\n"
        
        buttons.append([InlineKeyboardButton(
            text=f"🚀 نشر #{c['id']} - {c['title'][:30]}",
            callback_data=f"publish_campaign_{c['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_campaigns")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("publish_campaign_"))
async def publish_campaign_start(callback: CallbackQuery):
    """بدء نشر الحملة في القنوات المناسبة"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    campaign_id = int(callback.data.replace("publish_campaign_", ""))
    campaign = await db.fetchone(
        """SELECT c.*, u.full_name, u.telegram_id
        FROM campaigns c
        JOIN users u ON c.advertiser_id = u.id
        WHERE c.id = ?""",
        (campaign_id,)
    )
    
    if not campaign:
        await callback.answer("❌ الحملة غير موجودة", show_alert=True)
        return
    
    # البحث عن القنوات المناسبة
    categories = campaign['target_categories'].split(',') if campaign['target_categories'] else []
    
    # بناء استعلام البحث
    if categories and categories[0]:
        placeholders = ','.join(['?' for _ in categories])
        channels = await db.fetchall(
            f"""SELECT c.*, u.full_name as owner_name, u.telegram_id as owner_tg
            FROM channels c
            JOIN users u ON c.owner_id = u.id
            WHERE c.status = 'active' 
            AND c.category IN ({placeholders})
            AND c.id NOT IN (
                SELECT channel_id FROM campaign_channels WHERE campaign_id = ?
            )
            ORDER BY c.subscribers DESC, c.rating DESC
            LIMIT ?""",
            (*categories, campaign_id, campaign['channels_count'])
        )
    else:
        channels = await db.fetchall(
            """SELECT c.*, u.full_name as owner_name, u.telegram_id as owner_tg
            FROM channels c
            JOIN users u ON c.owner_id = u.id
            WHERE c.status = 'active'
            AND c.id NOT IN (
                SELECT channel_id FROM campaign_channels WHERE campaign_id = ?
            )
            ORDER BY c.subscribers DESC, c.rating DESC
            LIMIT ?""",
            (campaign_id, campaign['channels_count'])
        )
    
    if not channels:
        await callback.message.edit_text(
            f"❌ <b>لا توجد قنوات متاحة!</b>\n\n"
            f"الحملة: {campaign['title']}\n"
            f"التصنيفات المطلوبة: {campaign['target_categories']}\n"
            f"عدد القنوات المطلوب: {campaign['channels_count']}\n\n"
            "لم يتم العثور على قنوات نشطة في هذه التصنيفات.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 الحملات", callback_data="admin_ready_campaigns")]
            ])
        )
        return
    
    # حساب التكلفة لكل قناة
    budget_per_channel = campaign['budget'] / campaign['channels_count'] if campaign['channels_count'] > 0 else 0
    
    # عرض ملخص القنوات المختارة
    text = f"""
🚀 <b>نشر الحملة #{campaign['id']}</b>

📋 <b>معلومات الحملة:</b>
• العنوان: <b>{campaign['title']}</b>
• المعلن: {campaign['full_name']}
• الميزانية: <b>{campaign['budget']} ريال</b>
• القنوات المطلوبة: <b>{campaign['channels_count']}</b>
• القنوات المتاحة: <b>{len(channels)}</b>

📢 <b>القنوات المختارة:</b>
    """
    
    buttons = []
    for i, ch in enumerate(channels[:10], 1):
        text += f"\n{i}. <b>{ch['title']}</b> (@{ch['username']})"
        text += f"\n   👥 {ch['subscribers']} | 💰 {ch['ad_price']} ريال | ⭐ {ch['rating']}"
    
    if len(channels) > 10:
        text += f"\n\n... و {len(channels) - 10} قناة أخرى"
    
    text += f"""
\n💰 <b>التكلفة التقديرية:</b>
• متوسط سعر القناة: <b>{budget_per_channel:.0f} ريال</b>
• إجمالي التكلفة: <b>{campaign['budget']} ريال</b>
• عمولة المنصة: <b>{campaign['platform_fee']} ريال</b>
    """
    
    buttons = [
        [InlineKeyboardButton(text="✅ تأكيد النشر في كل القنوات", callback_data=f"confirm_publish_all_{campaign_id}")],
        [InlineKeyboardButton(text="👁 معاينة الإعلان", callback_data=f"preview_campaign_{campaign_id}")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_ready_campaigns")],
    ]
    
    # تخزين القنوات المختارة مؤقتاً
    # نحتاج لتخزينها في قاعدة البيانات أولاً
    for ch in channels:
        # التحقق من عدم وجود مسبق
        existing = await db.fetchone(
            "SELECT id FROM campaign_channels WHERE campaign_id = ? AND channel_id = ?",
            (campaign_id, ch['id'])
        )
        if not existing:
            await db.execute(
                """INSERT INTO campaign_channels 
                (campaign_id, channel_id, price, status) 
                VALUES (?, ?, ?, 'pending')""",
                (campaign_id, ch['id'], budget_per_channel)
            )
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("preview_campaign_"))
async def preview_campaign_content(callback: CallbackQuery):
    """معاينة محتوى الإعلان"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    campaign_id = int(callback.data.replace("preview_campaign_", ""))
    campaign = await db.fetchone("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
    
    if not campaign:
        await callback.answer("❌ الحملة غير موجودة", show_alert=True)
        return
    
    # إرسال معاينة الإعلان
    try:
        if campaign['media_file_id']:
            if campaign['content_type'] == 'photo':
                await callback.bot.send_photo(
                    callback.message.chat.id,
                    campaign['media_file_id'],
                    caption=f"📋 <b>معاينة الإعلان</b>\n\n{campaign['message_text'] or ''}",
                    reply_markup=get_campaign_button(campaign) if campaign['button_text'] else None
                )
            elif campaign['content_type'] == 'video':
                await callback.bot.send_video(
                    callback.message.chat.id,
                    campaign['media_file_id'],
                    caption=f"📋 <b>معاينة الإعلان</b>\n\n{campaign['message_text'] or ''}",
                    reply_markup=get_campaign_button(campaign) if campaign['button_text'] else None
                )
            elif campaign['content_type'] == 'document':
                await callback.bot.send_document(
                    callback.message.chat.id,
                    campaign['media_file_id'],
                    caption=f"📋 <b>معاينة الإعلان</b>\n\n{campaign['message_text'] or ''}",
                    reply_markup=get_campaign_button(campaign) if campaign['button_text'] else None
                )
        else:
            await callback.message.answer(
                f"📋 <b>معاينة الإعلان</b>\n\n{campaign['message_text']}",
                reply_markup=get_campaign_button(campaign) if campaign['button_text'] else None
            )
        
        await callback.answer("✅ تم إرسال المعاينة")
    except Exception as e:
        await callback.answer(f"❌ خطأ: {e}", show_alert=True)

def get_campaign_button(campaign):
    """إنشاء زر الإعلان"""
    if campaign['button_text'] and campaign['button_url']:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=campaign['button_text'], url=campaign['button_url'])]
        ])
    return None

@router.callback_query(F.data.startswith("confirm_publish_all_"))
async def confirm_publish_all(callback: CallbackQuery):
    """تأكيد ونشر الإعلان في جميع القنوات المختارة"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    campaign_id = int(callback.data.replace("confirm_publish_all_", ""))
    campaign = await db.fetchone("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
    
    if not campaign:
        await callback.answer("❌ الحملة غير موجودة", show_alert=True)
        return
    
    # الحصول على القنوات المرتبطة
    campaign_channels = await db.fetchall(
        """SELECT cc.*, c.chat_id, c.title, c.username, c.owner_id, u.telegram_id as owner_tg
        FROM campaign_channels cc
        JOIN channels c ON cc.channel_id = c.id
        JOIN users u ON c.owner_id = u.id
        WHERE cc.campaign_id = ? AND cc.status = 'pending'""",
        (campaign_id,)
    )
    
    if not campaign_channels:
        await callback.answer("❌ لا توجد قنوات معلقة للنشر", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"🔄 <b>جاري نشر الإعلان في {len(campaign_channels)} قناة...</b>\n\n"
        "يرجى الانتظار..."
    )
    
    success_count = 0
    failed_count = 0
    failed_list = []
    
    for cc in campaign_channels:
        try:
            # نشر الإعلان في القناة
            if campaign['media_file_id']:
                if campaign['content_type'] == 'photo':
                    sent = await callback.bot.send_photo(
                        chat_id=cc['chat_id'],
                        photo=campaign['media_file_id'],
                        caption=campaign['message_text'] or "",
                        reply_markup=get_campaign_button(campaign) if campaign['button_text'] else None
                    )
                elif campaign['content_type'] == 'video':
                    sent = await callback.bot.send_video(
                        chat_id=cc['chat_id'],
                        video=campaign['media_file_id'],
                        caption=campaign['message_text'] or "",
                        reply_markup=get_campaign_button(campaign) if campaign['button_text'] else None
                    )
                elif campaign['content_type'] == 'document':
                    sent = await callback.bot.send_document(
                        chat_id=cc['chat_id'],
                        document=campaign['media_file_id'],
                        caption=campaign['message_text'] or "",
                        reply_markup=get_campaign_button(campaign) if campaign['button_text'] else None
                    )
                else:
                    sent = await callback.bot.send_message(
                        chat_id=cc['chat_id'],
                        text=campaign['message_text'] or "",
                        reply_markup=get_campaign_button(campaign) if campaign['button_text'] else None
                    )
            else:
                sent = await callback.bot.send_message(
                    chat_id=cc['chat_id'],
                    text=campaign['message_text'] or "",
                    reply_markup=get_campaign_button(campaign) if campaign['button_text'] else None
                )
            
            # تحديث حالة النشر
            chat_id_str = str(cc['chat_id'])
            if chat_id_str.startswith("-100"):
                clean_id = chat_id_str[4:]
            else:
                clean_id = chat_id_str.replace("-", "")
            
            post_link = f"https://t.me/c/{clean_id}/{sent.message_id}"
            
            await db.execute(
                """UPDATE campaign_channels 
                SET status = 'published', publish_time = CURRENT_TIMESTAMP, post_link = ? 
                WHERE id = ?""",
                (post_link, cc['id'])
            )
            
            # إضافة الأرباح لصاحب القناة
            owner = await db.fetchone("SELECT * FROM users WHERE id = ?", (cc['owner_id'],))
            if owner:
                new_balance = owner['balance'] + cc['price']
                await db.execute(
                    "UPDATE users SET balance = ? WHERE id = ?",
                    (new_balance, cc['owner_id'])
                )
                await db.execute(
                    """INSERT INTO wallet 
                    (user_id, amount, transaction_type, description, balance_before, balance_after) 
                    VALUES (?, ?, 'ad_revenue', ?, ?, ?)""",
                    (cc['owner_id'], cc['price'], 
                     f"أرباح إعلان في {cc['title']} (حملة #{campaign_id})",
                     owner['balance'], new_balance)
                )
            
            # تحديث إحصائيات القناة
            await db.execute(
                "UPDATE channels SET total_ads_completed = total_ads_completed + 1, total_earnings = total_earnings + ? WHERE id = ?",
                (cc['price'], cc['channel_id'])
            )
            
            success_count += 1
            await asyncio.sleep(0.5)  # تأخير بين النشر لتجنب حظر تيليجرام
            
        except Exception as e:
            failed_count += 1
            failed_list.append(f"• {cc['title']} (@{cc['username']}): {str(e)[:100]}")
            await db.execute(
                "UPDATE campaign_channels SET status = 'failed' WHERE id = ?",
                (cc['id'],)
            )
    
    # تحديث حالة الحملة
    if success_count > 0:
        await db.execute(
            "UPDATE campaigns SET status = 'active' WHERE id = ?",
            (campaign_id,)
        )
    
    # إشعار المعلن
    if campaign['advertiser_id']:
        try:
            await callback.bot.send_message(
                campaign['advertiser_id'],
                f"🎉 <b>تم بدء نشر حملتك!</b>\n\n"
                f"📋 الحملة: {campaign['title']}\n"
                f"✅ تم النشر في: <b>{success_count} قناة</b>\n"
                f"❌ فشل في: <b>{failed_count} قناة</b>\n\n"
                "تابع نتائج حملتك من 📋 حملاتي"
            )
        except:
            pass
    
    # عرض النتيجة
    result_text = f"""
✅ <b>تم الانتهاء من النشر!</b>

📋 <b>نتائج الحملة #{campaign_id}:</b>
• العنوان: {campaign['title']}
• ✅ نجح في: <b>{success_count} قناة</b>
• ❌ فشل في: <b>{failed_count} قناة</b>
• 📊 المجموع: {len(campaign_channels)} قناة
    """
    
    if failed_list:
        result_text += "\n⚠️ <b>القنوات التي فشل النشر فيها:</b>\n"
        result_text += "\n".join(failed_list[:10])
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 عرض تفاصيل الحملة", callback_data=f"admin_campaign_detail_{campaign_id}")],
        [InlineKeyboardButton(text="🔙 الحملات", callback_data="admin_ready_campaigns")],
    ])
    
    await callback.message.edit_text(result_text, reply_markup=buttons, disable_web_page_preview=True)
    await callback.answer(f"✅ تم النشر في {success_count} قناة")

@router.callback_query(F.data.startswith("admin_campaign_detail_"))
async def admin_campaign_detail_view(callback: CallbackQuery):
    """عرض تفاصيل حملة للمدير"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    campaign_id = int(callback.data.replace("admin_campaign_detail_", ""))
    campaign = await db.fetchone(
        """SELECT c.*, u.full_name, u.telegram_id
        FROM campaigns c
        JOIN users u ON c.advertiser_id = u.id
        WHERE c.id = ?""",
        (campaign_id,)
    )
    
    if not campaign:
        await callback.answer("❌ الحملة غير موجودة", show_alert=True)
        return
    
    # القنوات المرتبطة
    channels = await db.fetchall(
        """SELECT cc.*, c.title, c.username, c.chat_id
        FROM campaign_channels cc
        JOIN channels c ON cc.channel_id = c.id
        WHERE cc.campaign_id = ?
        ORDER BY cc.status, c.title""",
        (campaign_id,)
    )
    
    status_emoji = {
        "pending": "🟡", "accepted": "🟢", "published": "✅",
        "rejected": "❌", "failed": "⚠️"
    }
    
    text = f"""
📋 <b>تفاصيل الحملة #{campaign['id']}</b>

📝 العنوان: <b>{campaign['title']}</b>
👤 المعلن: {campaign['full_name']}
💰 الميزانية: <b>{campaign['budget']} ريال</b>
📊 الحالة: {campaign['status']}
📅 تاريخ الإنشاء: {campaign['created_at'][:10]}

📢 <b>القنوات ({len(channels)}):</b>
    """
    
    for ch in channels[:20]:
        emoji = status_emoji.get(ch['status'], "⚪")
        text += f"\n{emoji} {ch['title']} (@{ch['username']})"
        if ch['post_link']:
            text += f"\n   🔗 {ch['post_link']}"
    
    if len(channels) > 20:
        text += f"\n\n... و {len(channels) - 20} قناة أخرى"
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 إعادة نشر المعلقة", callback_data=f"republish_campaign_{campaign_id}")] if any(c['status'] in ['pending', 'failed'] for c in channels) else None,
        [InlineKeyboardButton(text="🔙 الحملات", callback_data="admin_ready_campaigns")],
    ])
    
    # إزالة الأزرار الفارغة
    buttons.inline_keyboard = [row for row in buttons.inline_keyboard if row[0] is not None]
    
    await callback.message.edit_text(text, reply_markup=buttons, disable_web_page_preview=True)
    await callback.answer()

@router.callback_query(F.data.startswith("republish_campaign_"))
async def republish_campaign(callback: CallbackQuery):
    """إعادة نشر القنوات المعلقة أو الفاشلة"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    campaign_id = int(callback.data.replace("republish_campaign_", ""))
    
    # إعادة تعيين القنوات الفاشلة إلى معلقة
    await db.execute(
        "UPDATE campaign_channels SET status = 'pending' WHERE campaign_id = ? AND status IN ('failed', 'pending')",
        (campaign_id,)
    )
    
    await callback.answer("✅ تم إعادة تعيين القنوات. اضغط نشر مرة أخرى.", show_alert=True)
    await publish_campaign_start(callback)

@router.callback_query(F.data == "admin_all_campaigns")
async def admin_all_campaigns(callback: CallbackQuery):
    """عرض كل الحملات"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    
    campaigns = await db.fetchall(
        """SELECT c.*, u.full_name
        FROM campaigns c
        JOIN users u ON c.advertiser_id = u.id
        ORDER BY c.created_at DESC LIMIT 30"""
    )
    
    if not campaigns:
        await callback.message.edit_text("📭 لا توجد حملات.")
        return
    
    text = "📋 <b>جميع الحملات:</b>\n\n"
    buttons = []
    
    status_emoji = {
        "draft": "📝", "pending_payment": "💳", "pending_admin": "🟡",
        "active": "🟢", "completed": "✅", "rejected": "❌"
    }
    
    for c in campaigns:
        emoji = status_emoji.get(c['status'], "📋")
        text += f"{emoji} <b>#{c['id']}</b> - {c['title'][:40]}\n"
        text += f"   {c['full_name']} | 💰 {c['budget']} | 📢 {c['channels_count']} قناة\n\n"
        
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} #{c['id']} - {c['title'][:30]}",
            callback_data=f"admin_campaign_detail_{c['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_campaigns")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()
