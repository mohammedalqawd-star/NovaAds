import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import re

from database.connection import Database
from keyboards.main_menu import get_owner_menu, get_main_menu
from config import Config

logger = logging.getLogger(__name__)
router = Router()
db = Database()

class ChannelStates(StatesGroup):
    waiting_channel_link = State()
    waiting_verify_admin = State()
    waiting_category = State()
    waiting_price = State()
    waiting_auto_accept = State()
    waiting_edit_field = State()
    waiting_edit_value = State()

# ============ تسجيل قناة جديدة ============

@router.callback_query(F.data == "register_channel")
async def register_channel_start(callback: CallbackQuery, state: FSMContext):
    """بدء تسجيل قناة جديدة"""
    await state.clear()
    await state.set_state(ChannelStates.waiting_channel_link)
    
    text = """
📢 <b>تسجيل قناة جديدة</b>

أرسل رابط قناتك.
مثال:
<code>https://t.me/MyChannel</code>
أو
<code>@MyChannel</code>

⚠️ <b>ملاحظة مهمة:</b>
يجب إضافة البوت كمشرف في القناة أولاً.
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
        ])
    )
    await callback.answer()

@router.message(ChannelStates.waiting_channel_link)
async def process_channel_link(message: Message, state: FSMContext):
    """معالجة رابط القناة"""
    link = message.text.strip()
    
    # استخراج اسم المستخدم من الرابط
    username = None
    if "t.me/" in link:
        # استخراج من الرابط الكامل
        parts = link.split("t.me/")
        if len(parts) > 1:
            username = parts[1].split("/")[0].replace("@", "").strip()
    elif link.startswith("@"):
        username = link[1:].strip()
    else:
        # ربما يكون اسم المستخدم مباشرة
        username = link.replace("@", "").strip()
    
    if not username:
        await message.answer(
            "❌ رابط غير صحيح. أعد المحاولة:\n"
            "مثال: <code>https://t.me/MyChannel</code> أو <code>@MyChannel</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
            ])
        )
        return
    
    logger.info(f"محاولة تسجيل قناة: @{username}")
    
    # التحقق من عدم تكرار القناة
    existing = await db.fetchone(
        "SELECT * FROM channels WHERE username = ? OR username = ?",
        (username, f"@{username}")
    )
    
    if existing:
        await message.answer(
            f"⚠️ القناة @{username} مسجلة مسبقاً.",
            reply_markup=get_main_menu(message.from_user.id)
        )
        await state.clear()
        return
    
    # حفظ البيانات مؤقتاً
    await state.update_data(channel_username=username)
    
    # محاولة الحصول على معلومات القناة أولاً
    try:
        chat = await message.bot.get_chat(f"@{username}")
        
        # حفظ معلومات القناة
        await state.update_data(
            chat_id=chat.id,
            channel_title=chat.title,
            channel_description=chat.description or "",
            channel_type=chat.type
        )
        
        # التحقق من أن البوت مشرف
        try:
            bot_member = await message.bot.get_chat_member(chat.id, message.bot.id)
            
            if bot_member.status in ["administrator", "creator"]:
                # البوت مشرف بالفعل - متابعة مباشرة
                await state.set_state(ChannelStates.waiting_category)
                
                categories_text = "📂 <b>اختر تصنيف القناة:</b>"
                buttons = []
                row = []
                for i, cat in enumerate(Config.CATEGORIES):
                    row.append(InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}"))
                    if len(row) == 3:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)
                
                await message.answer(
                    f"✅ تم العثور على القناة: <b>{chat.title}</b>\n\n{categories_text}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                )
                return
            else:
                # البوت ليس مشرفاً
                await state.set_state(ChannelStates.waiting_verify_admin)
                
                text = f"""
✅ تم العثور على القناة: <b>{chat.title}</b>

⚠️ <b>يجب إضافة البوت كمشرف:</b>
1. اذهب إلى قناتك
2. اضغط على اسم القناة
3. اختر <b>Administrators</b> أو <b>المشرفين</b>
4. أضف البوت: <b>@{message.bot.username}</b>
5. امنحه صلاحية <b>نشر الرسائل</b>
6. ثم اضغط <b>✅ تحقق</b>
                """
                
                await message.answer(
                    text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ تحقق", callback_data="verify_admin")],
                        [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
                    ])
                )
                
        except Exception as e:
            logger.error(f"خطأ في التحقق من صلاحيات البوت: {e}")
            await state.set_state(ChannelStates.waiting_verify_admin)
            
            text = f"""
✅ تم العثور على القناة: <b>{chat.title}</b>

⚠️ <b>يجب إضافة البوت كمشرف:</b>
1. اذهب إلى قناتك
2. أضف البوت: <b>@{message.bot.username}</b> كمشرف
3. امنحه صلاحية <b>نشر الرسائل</b>
4. ثم اضغط <b>✅ تحقق</b>
            """
            
            await message.answer(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ تحقق", callback_data="verify_admin")],
                    [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
                ])
            )
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"خطأ في الوصول للقناة: {error_msg}")
        
        if "chat not found" in error_msg.lower():
            await message.answer(
                f"❌ لم يتم العثور على القناة <b>@{username}</b>\n\n"
                "تأكد من:\n"
                "• الرابط صحيح\n"
                "• القناة عامة (public)\n"
                "• كتابة اسم المستخدم بشكل صحيح\n\n"
                "أعد المحاولة:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
                ])
            )
        else:
            await message.answer(
                f"❌ خطأ: {error_msg[:200]}\n\n"
                "تأكد أن القناة عامة وأن الرابط صحيح.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
                ])
            )

@router.callback_query(F.data == "verify_admin", ChannelStates.waiting_verify_admin)
async def verify_bot_admin(callback: CallbackQuery, state: FSMContext):
    """التحقق من أن البوت مشرف في القناة"""
    data = await state.get_data()
    username = data.get("channel_username")
    chat_id = data.get("chat_id")
    
    try:
        # إعادة التحقق من الصلاحيات
        bot_member = await callback.bot.get_chat_member(chat_id, callback.bot.id)
        
        if bot_member.status not in ["administrator", "creator"]:
            await callback.answer("❌ البوت ليس مشرفاً بعد. أضفه كمشرف أولاً.", show_alert=True)
            return
        
        # التحقق من صلاحية النشر
        if bot_member.status != "creator" and not bot_member.can_post_messages:
            await callback.answer("❌ يجب منح البوت صلاحية نشر الرسائل.", show_alert=True)
            return
        
        # البوت مشرف ولديه الصلاحيات - متابعة
        await state.set_state(ChannelStates.waiting_category)
        
        categories_text = "📂 <b>اختر تصنيف القناة:</b>"
        buttons = []
        row = []
        for i, cat in enumerate(Config.CATEGORIES):
            row.append(InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        
        await callback.message.edit_text(
            f"✅ تم التحقق! القناة: <b>{data.get('channel_title', username)}</b>\n\n{categories_text}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer("✅ تم التحقق بنجاح!")
        
    except Exception as e:
        logger.error(f"خطأ في التحقق: {e}")
        await callback.answer("❌ لم يتم التحقق. تأكد من إضافة البوت كمشرف.", show_alert=True)

@router.callback_query(F.data.startswith("cat_"), ChannelStates.waiting_category)
async def process_category(callback: CallbackQuery, state: FSMContext):
    """معالجة اختيار التصنيف"""
    category = callback.data.replace("cat_", "")
    await state.update_data(channel_category=category)
    
    await state.set_state(ChannelStates.waiting_price)
    
    await callback.message.edit_text(
        f"📂 التصنيف: <b>{category}</b>\n\n"
        "💰 <b>كم سعر إعلان 24 ساعة؟</b>\n"
        "أدخل السعر بالريال اليمني.\n"
        "مثال: <code>8000</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
        ])
    )
    await callback.answer()

@router.message(ChannelStates.waiting_price)
async def process_price(message: Message, state: FSMContext):
    """معالجة سعر الإعلان"""
    try:
        price = float(message.text.strip())
        if price < 100:
            await message.answer("❌ أقل سعر للإعلان هو 100 ريال. أعد المحاولة:")
            return
        if price > 1000000:
            await message.answer("❌ الحد الأقصى للسعر هو 1,000,000 ريال. أعد المحاولة:")
            return
    except ValueError:
        await message.answer("❌ أدخل رقماً صحيحاً. مثال: 8000")
        return
    
    await state.update_data(ad_price=price)
    await state.set_state(ChannelStates.waiting_auto_accept)
    
    await message.answer(
        f"💰 السعر: <b>{price} ريال</b>\n\n"
        "🤖 <b>هل تقبل الإعلانات تلقائياً؟</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ نعم", callback_data="auto_accept_yes")],
            [InlineKeyboardButton(text="❌ لا", callback_data="auto_accept_no")],
        ])
    )

@router.callback_query(F.data.startswith("auto_accept_"), ChannelStates.waiting_auto_accept)
async def process_auto_accept(callback: CallbackQuery, state: FSMContext):
    """معالجة القبول التلقائي وحفظ القناة"""
    auto_accept = 1 if callback.data == "auto_accept_yes" else 0
    data = await state.get_data()
    
    # الحصول على المستخدم
    user = await db.fetchone(
        "SELECT id, balance, role FROM users WHERE telegram_id = ?",
        (callback.from_user.id,)
    )
    
    if not user:
        await callback.answer("❌ خطأ: المستخدم غير موجود", show_alert=True)
        return
    
    # محاولة الحصول على عدد المشتركين
    try:
        member_count = await callback.bot.get_chat_member_count(data['chat_id'])
    except:
        member_count = 0
    
    # حفظ القناة في قاعدة البيانات
    await db.execute(
        """INSERT INTO channels 
        (owner_id, chat_id, username, title, description, category, subscribers, ad_price, auto_accept, status) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
        (
            user['id'],
            data['chat_id'],
            data['channel_username'],
            data['channel_title'],
            data.get('channel_description', ''),
            data['channel_category'],
            member_count,
            data['ad_price'],
            auto_accept
        )
    )
    
    # تحديث دور المستخدم إلى "owner" إذا كان زائراً
    if user['role'] == 'visitor':
        await db.execute(
            "UPDATE users SET role = 'owner' WHERE id = ?",
            (user['id'],)
        )
    
    # تسجيل في المحفظة
    await db.execute(
        """INSERT INTO wallet (user_id, amount, transaction_type, description, balance_before, balance_after) 
        VALUES (?, 0, 'channel_register', ?, ?, ?)""",
        (user['id'], f"تم تسجيل قناة {data['channel_title']}", user['balance'], user['balance'])
    )
    
    await state.clear()
    
    success_text = f"""
🎉 <b>تم تسجيل القناة بنجاح!</b>

📢 <b>معلومات القناة:</b>
• الاسم: <b>{data['channel_title']}</b>
• الرابط: @{data['channel_username']}
• التصنيف: {data['channel_category']}
• المشتركين: {member_count}
• السعر: {data['ad_price']} ريال
• القبول التلقائي: {"✅ نعم" if auto_accept else "❌ لا"}

📊 قناتك الآن متاحة في سوق الإعلانات!
    """
    
    await callback.message.edit_text(
        success_text,
        reply_markup=get_owner_menu()
    )
    await callback.answer("✅ تم التسجيل بنجاح", show_alert=True)

# ============ عرض قنواتي ============

@router.callback_query(F.data == "my_channels")
async def my_channels_list(callback: CallbackQuery):
    """عرض قنوات المستخدم"""
    user = await db.fetchone(
        "SELECT id FROM users WHERE telegram_id = ?",
        (callback.from_user.id,)
    )
    
    if not user:
        await callback.answer("❌ سجل أولاً باستخدام /start", show_alert=True)
        return
    
    channels = await db.fetchall(
        "SELECT * FROM channels WHERE owner_id = ? ORDER BY created_at DESC",
        (user['id'],)
    )
    
    if not channels:
        await callback.message.edit_text(
            "📭 ليس لديك أي قنوات مسجلة.\n\nسجل قناتك الآن من زر 📢 تسجيل قناة",
            reply_markup=get_main_menu(callback.from_user.id)
        )
        return
    
    text = "📢 <b>قنواتي:</b>\n\n"
    buttons = []
    for ch in channels:
        status_emoji = {"active": "🟢", "paused": "🟡", "banned": "🔴"}.get(ch['status'], "⚪")
        text += f"{status_emoji} <b>{ch['title']}</b>\n"
        text += f"   👥 {ch['subscribers']} | 💰 {ch['ad_price']} ريال | 📂 {ch['category']}\n\n"
        
        buttons.append([InlineKeyboardButton(
            text=f"{status_emoji} {ch['title'][:30]}",
            callback_data=f"channel_detail_{ch['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="➕ تسجيل قناة جديدة", callback_data="register_channel")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="main_menu")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("channel_detail_"))
async def channel_detail(callback: CallbackQuery):
    """عرض تفاصيل قناة"""
    channel_id = int(callback.data.replace("channel_detail_", ""))
    
    channel = await db.fetchone("SELECT * FROM channels WHERE id = ?", (channel_id,))
    
    if not channel:
        await callback.answer("❌ القناة غير موجودة", show_alert=True)
        return
    
    status_text = {"active": "🟢 نشطة", "paused": "🟡 موقوفة", "banned": "🔴 محظورة"}
    
    detail_text = f"""
📢 <b>{channel['title']}</b>

📊 <b>معلومات القناة:</b>
• الرابط: @{channel['username']}
• Chat ID: <code>{channel['chat_id']}</code>
• التصنيف: {channel['category']}
• المشتركين: <b>{channel['subscribers']}</b>
• سعر الإعلان: <b>{channel['ad_price']} ريال</b>
• القبول التلقائي: {"✅ نعم" if channel['auto_accept'] else "❌ لا"}
• الحالة: {status_text.get(channel['status'], channel['status'])}
• التقييم: ⭐ {channel['rating']}/5
• الإعلانات المنفذة: {channel['total_ads_completed']}
• إجمالي الأرباح: <b>{channel['total_earnings']} ريال</b>
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏ تعديل السعر", callback_data=f"edit_price_{channel_id}")],
        [
            InlineKeyboardButton(
                text="⏸ إيقاف" if channel['status'] == 'active' else "▶️ تفعيل",
                callback_data=f"toggle_channel_{channel_id}"
            ),
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"delete_channel_{channel_id}")
        ],
        [InlineKeyboardButton(text="🔙 قنواتي", callback_data="my_channels")],
    ])
    
    await callback.message.edit_text(detail_text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_channel_"))
async def toggle_channel_status(callback: CallbackQuery):
    """تغيير حالة القناة (إيقاف/تفعيل)"""
    channel_id = int(callback.data.replace("toggle_channel_", ""))
    
    channel = await db.fetchone("SELECT * FROM channels WHERE id = ?", (channel_id,))
    
    if not channel:
        await callback.answer("❌ القناة غير موجودة", show_alert=True)
        return
    
    new_status = "paused" if channel['status'] == "active" else "active"
    await db.execute("UPDATE channels SET status = ? WHERE id = ?", (new_status, channel_id))
    
    status_text = {"active": "تم تفعيل", "paused": "تم إيقاف"}
    await callback.answer(f"✅ {status_text.get(new_status, 'تم تحديث')} القناة", show_alert=True)
    await channel_detail(callback)

@router.callback_query(F.data.startswith("delete_channel_"))
async def delete_channel_confirm(callback: CallbackQuery):
    """تأكيد حذف القناة"""
    channel_id = int(callback.data.replace("delete_channel_", ""))
    
    await callback.message.edit_text(
        "⚠️ <b>هل أنت متأكد من حذف القناة؟</b>\n\n❌ لا يمكن التراجع.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ نعم، احذف", callback_data=f"confirm_delete_{channel_id}")],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"channel_detail_{channel_id}")],
        ])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def delete_channel_execute(callback: CallbackQuery):
    """تنفيذ حذف القناة"""
    channel_id = int(callback.data.replace("confirm_delete_", ""))
    
    await db.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    
    await callback.answer("🗑 تم حذف القناة", show_alert=True)
    await callback.message.edit_text(
        "✅ تم حذف القناة بنجاح.",
        reply_markup=get_main_menu(callback.from_user.id)
    )

@router.callback_query(F.data.startswith("edit_price_"))
async def edit_price_start(callback: CallbackQuery, state: FSMContext):
    """بدء تعديل السعر"""
    channel_id = int(callback.data.replace("edit_price_", ""))
    await state.update_data(edit_channel_id=channel_id)
    await state.set_state(ChannelStates.waiting_edit_value)
    
    await callback.message.edit_text(
        "💰 <b>أدخل السعر الجديد بالريال اليمني:</b>\nمثال: 8000",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"channel_detail_{channel_id}")]
        ])
    )
    await callback.answer()

@router.message(ChannelStates.waiting_edit_value)
async def process_edit_value(message: Message, state: FSMContext):
    """معالجة القيمة الجديدة"""
    data = await state.get_data()
    channel_id = data.get("edit_channel_id")
    
    try:
        value = float(message.text.strip())
        if value < 100:
            await message.answer("❌ أقل سعر 100 ريال. أعد المحاولة:")
            return
        await db.execute("UPDATE channels SET ad_price = ? WHERE id = ?", (value, channel_id))
        await message.answer(f"✅ تم تحديث السعر إلى <b>{value} ريال</b>")
    except ValueError:
        await message.answer("❌ قيمة غير صحيحة. أعد المحاولة:")
        return
    
    await state.clear()
    await message.answer(
        "✅ تم التحديث",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 عرض القناة", callback_data=f"channel_detail_{channel_id}")]
        ])
    )
