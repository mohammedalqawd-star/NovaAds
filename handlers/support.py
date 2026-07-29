import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.connection import Database
from keyboards.main_menu import get_main_menu
from config import Config

logger = logging.getLogger(__name__)
router = Router()
db = Database()

class SupportStates(StatesGroup):
    waiting_subject = State()
    waiting_message = State()
    replying_to_ticket = State()

@router.callback_query(F.data == "support")
async def support_menu(callback: CallbackQuery):
    """قائمة الدعم الفني"""
    text = """
📞 <b>الدعم الفني</b>

نحن هنا لمساعدتك! اختر نوع المساعدة:

📧 <b>فتح تذكرة دعم</b> - للاستفسارات والمشاكل
📋 <b>تذاكري</b> - متابعة تذاكرك السابقة
📚 <b>الأسئلة الشائعة</b> - إجابات سريعة

أو تواصل معنا مباشرة: @NovaAdsSupport
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📧 فتح تذكرة جديدة", callback_data="new_ticket")],
        [InlineKeyboardButton(text="📋 تذاكري", callback_data="my_tickets")],
        [InlineKeyboardButton(text="📚 الأسئلة الشائعة", callback_data="faq")],
        [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data == "new_ticket")
async def new_ticket_start(callback: CallbackQuery, state: FSMContext):
    """بدء تذكرة جديدة"""
    await state.set_state(SupportStates.waiting_subject)
    
    await callback.message.edit_text(
        "📧 <b>فتح تذكرة دعم جديدة</b>\n\n"
        "أرسل موضوع المشكلة أو استفسارك.\n"
        "مثال: <code>مشكلة في تسجيل القناة</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="support")]
        ])
    )
    await callback.answer()

@router.message(SupportStates.waiting_subject)
async def process_ticket_subject(message: Message, state: FSMContext):
    """معالجة موضوع التذكرة"""
    subject = message.text.strip()
    await state.update_data(ticket_subject=subject)
    await state.set_state(SupportStates.waiting_message)
    
    await message.answer(
        "📝 <b>اشرح المشكلة بالتفصيل:</b>\n\n"
        "يمكنك إرسال نص أو صورة أو فيديو.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="support")]
        ])
    )

@router.message(SupportStates.waiting_message)
async def process_ticket_message(message: Message, state: FSMContext):
    """حفظ التذكرة"""
    data = await state.get_data()
    user = await db.fetchone(
        "SELECT id FROM users WHERE telegram_id = ?",
        (message.from_user.id,)
    )
    
    if not user:
        await message.answer("❌ سجل أولاً بـ /start")
        return
    
    # إنشاء التذكرة
    cursor = await db.execute(
        "INSERT INTO support_tickets (user_id, subject, status) VALUES (?, ?, 'open')",
        (user['id'], data['ticket_subject'])
    )
    ticket_id = cursor.lastrowid
    
    # حفظ الرسالة
    file_id = None
    msg_type = "text"
    
    if message.photo:
        file_id = message.photo[-1].file_id
        msg_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        msg_type = "video"
    elif message.document:
        file_id = message.document.file_id
        msg_type = "document"
    
    await db.execute(
        """INSERT INTO support_messages 
        (ticket_id, sender_id, message_text, message_type, file_id) 
        VALUES (?, ?, ?, ?, ?)""",
        (ticket_id, message.from_user.id, message.text or message.caption or "", msg_type, file_id)
    )
    
    await state.clear()
    
    # إشعار المدراء
    for admin_id in Config.ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"📧 <b>تذكرة دعم جديدة #{ticket_id}</b>\n"
                f"👤 من: {message.from_user.full_name}\n"
                f"📝 الموضوع: {data['ticket_subject']}\n"
                f"🔑 للتذاكر: /tickets",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 عرض التذكرة", callback_data=f"admin_ticket_{ticket_id}")]
                ])
            )
        except:
            pass
    
    await message.answer(
        f"✅ <b>تم فتح التذكرة رقم #{ticket_id}</b>\n\n"
        "سيرد عليك فريق الدعم قريباً.\n"
        "تابع تذاكرك من 📋 تذاكري",
        reply_markup=get_main_menu(message.from_user.id)
    )

@router.callback_query(F.data == "my_tickets")
async def my_tickets_list(callback: CallbackQuery):
    """عرض تذاكري"""
    user = await db.fetchone(
        "SELECT id FROM users WHERE telegram_id = ?",
        (callback.from_user.id,)
    )
    
    if not user:
        await callback.answer("❌ سجل أولاً", show_alert=True)
        return
    
    tickets = await db.fetchall(
        "SELECT * FROM support_tickets WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user['id'],)
    )
    
    if not tickets:
        await callback.message.edit_text(
            "📭 ليس لديك أي تذاكر.\n\nافتح تذكرة جديدة من 📧 فتح تذكرة",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📧 تذكرة جديدة", callback_data="new_ticket")],
                [InlineKeyboardButton(text="🔙 الدعم", callback_data="support")],
            ])
        )
        return
    
    text = "📋 <b>تذاكري:</b>\n\n"
    buttons = []
    
    status_emoji = {"open": "🟢", "closed": "🔴", "in_progress": "🟡"}
    
    for t in tickets:
        emoji = status_emoji.get(t['status'], "⚪")
        text += f"{emoji} <b>#{t['id']}</b> - {t['subject'][:50]}\n"
        text += f"   التاريخ: {t['created_at'][:10]}\n\n"
        
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} #{t['id']} - {t['subject'][:30]}",
            callback_data=f"view_ticket_{t['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="📧 تذكرة جديدة", callback_data="new_ticket")])
    buttons.append([InlineKeyboardButton(text="🔙 الدعم", callback_data="support")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("view_ticket_"))
async def view_ticket(callback: CallbackQuery):
    """عرض تفاصيل تذكرة"""
    ticket_id = int(callback.data.replace("view_ticket_", ""))
    
    ticket = await db.fetchone("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))
    
    if not ticket:
        await callback.answer("❌ التذكرة غير موجودة", show_alert=True)
        return
    
    messages = await db.fetchall(
        "SELECT * FROM support_messages WHERE ticket_id = ? ORDER BY created_at ASC",
        (ticket_id,)
    )
    
    text = f"📧 <b>تذكرة #{ticket['id']}</b>\n"
    text += f"📝 الموضوع: <b>{ticket['subject']}</b>\n"
    text += f"📅 التاريخ: {ticket['created_at'][:10]}\n"
    text += f"الحالة: {ticket['status']}\n\n"
    text += "📝 <b>الرسائل:</b>\n\n"
    
    for msg in messages[:5]:
        sender = "👤 أنت" if msg['sender_id'] == callback.from_user.id else "👨‍💻 الدعم"
        text += f"{sender}: {msg['message_text'][:100]}\n"
        text += f"   {msg['created_at'][:16]}\n\n"
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 تذاكري", callback_data="my_tickets")],
        [InlineKeyboardButton(text="🔙 الدعم", callback_data="support")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data == "faq")
async def show_faq(callback: CallbackQuery):
    """عرض الأسئلة الشائعة"""
    faq_text = """
📚 <b>الأسئلة الشائعة</b>

❓ <b>كيف أسجل قناتي؟</b>
📢 اضغط "تسجيل قناة" وأرسل رابط القناة ثم اتبع التعليمات.

❓ <b>كيف أنشئ إعلاناً؟</b>
💰 اضغط "إنشاء حملة" واملأ البيانات المطلوبة.

❓ <b>متى أستلم أرباحي؟</b>
💵 يمكنك طلب السحب من قسم الأرباح، وسيتم التحويل خلال 24-48 ساعة.

❓ <b>كيف أتواصل مع الدعم؟</b>
📧 افتح تذكرة دعم أو راسل @NovaAdsSupport

❓ <b>ما هي طرق الدفع المتاحة؟</b>
💳 جوالي، الكريمي، فلوسك، تحويل بنكي
    """
    
    await callback.message.edit_text(
        faq_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📧 فتح تذكرة", callback_data="new_ticket")],
            [InlineKeyboardButton(text="🔙 الدعم", callback_data="support")],
        ])
    )
    await callback.answer()
