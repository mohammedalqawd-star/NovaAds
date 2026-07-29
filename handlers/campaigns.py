import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.connection import Database
from keyboards.main_menu import get_advertiser_menu, get_main_menu
from config import Config

logger = logging.getLogger(__name__)
router = Router()
db = Database()

class CampaignStates(StatesGroup):
    waiting_title = State()
    waiting_content_type = State()
    waiting_content = State()
    waiting_button = State()
    waiting_button_text = State()
    waiting_button_url = State()
    waiting_categories = State()
    waiting_channels_count = State()
    waiting_budget = State()
    waiting_payment_method = State()
    waiting_payment_receipt = State()

# ============ إنشاء حملة جديدة ============

@router.callback_query(F.data == "create_campaign")
async def create_campaign_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(CampaignStates.waiting_title)
    
    text = """
💰 <b>إنشاء حملة إعلانية جديدة</b>

📝 <b>الخطوة 1:</b> ما اسم الحملة؟
مثال: <code>إعلان متجر الهواتف</code>

أو اضغط /cancel للإلغاء.
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
        ])
    )
    await callback.answer()

@router.message(CampaignStates.waiting_title)
async def process_campaign_title(message: Message, state: FSMContext):
    title = message.text.strip()
    
    if len(title) < 3:
        await message.answer("❌ اسم الحملة قصير جداً. أعد المحاولة:")
        return
    
    if len(title) > 100:
        await message.answer("❌ اسم الحملة طويل جداً. أعد المحاولة:")
        return
    
    await state.update_data(campaign_title=title)
    await state.set_state(CampaignStates.waiting_content_type)
    
    text = f"""
✅ اسم الحملة: <b>{title}</b>

📝 <b>الخطوة 2:</b> اختر نوع الإعلان:
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 نص", callback_data="type_text")],
        [InlineKeyboardButton(text="🖼 صورة", callback_data="type_photo")],
        [InlineKeyboardButton(text="🎥 فيديو", callback_data="type_video")],
        [InlineKeyboardButton(text="📂 ملف", callback_data="type_document")],
        [InlineKeyboardButton(text="📢 رسالة منقولة", callback_data="type_forward")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")],
    ])
    
    await message.answer(text, reply_markup=buttons)

@router.callback_query(F.data.startswith("type_"), CampaignStates.waiting_content_type)
async def process_content_type(callback: CallbackQuery, state: FSMContext):
    content_type = callback.data.replace("type_", "")
    await state.update_data(content_type=content_type)
    await state.set_state(CampaignStates.waiting_content)
    
    type_instructions = {
        "text": "أرسل نص الإعلان:",
        "photo": "أرسل صورة الإعلان مع تعليق:",
        "video": "أرسل فيديو الإعلان مع تعليق:",
        "document": "أرسل ملف الإعلان مع تعليق:",
        "forward": "أرسل الرسالة التي تريد إعادة توجيهها:"
    }
    
    await callback.message.edit_text(
        f"📝 <b>الخطوة 3:</b> {type_instructions.get(content_type, 'أرسل المحتوى:')}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
        ])
    )
    await callback.answer()

@router.message(CampaignStates.waiting_content)
async def process_content(message: Message, state: FSMContext):
    data = await state.get_data()
    content_type = data.get("content_type", "text")
    
    if content_type == "text":
        await state.update_data(message_text=message.text, media_file_id=None)
    elif content_type == "photo":
        if not message.photo:
            await message.answer("❌ أرسل صورة من فضلك.")
            return
        await state.update_data(
            message_text=message.caption or "",
            media_file_id=message.photo[-1].file_id
        )
    elif content_type == "video":
        if not message.video:
            await message.answer("❌ أرسل فيديو من فضلك.")
            return
        await state.update_data(
            message_text=message.caption or "",
            media_file_id=message.video.file_id
        )
    elif content_type == "document":
        if not message.document:
            await message.answer("❌ أرسل ملفاً من فضلك.")
            return
        await state.update_data(
            message_text=message.caption or "",
            media_file_id=message.document.file_id
        )
    elif content_type == "forward":
        await state.update_data(
            message_text="",
            media_file_id=None,
            forward_from=message.forward_from.id if message.forward_from else None,
            forward_message_id=message.forward_from_message_id if message.forward_from_message_id else None,
            forward_chat_id=message.forward_from_chat.id if message.forward_from_chat else None
        )
    
    await state.set_state(CampaignStates.waiting_button)
    
    await message.answer(
        "🔘 <b>الخطوة 4:</b> هل تريد إضافة زر للإعلان؟",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ نعم", callback_data="add_button_yes")],
            [InlineKeyboardButton(text="❌ لا", callback_data="add_button_no")],
        ])
    )

@router.callback_query(F.data.startswith("add_button_"), CampaignStates.waiting_button)
async def process_button_choice(callback: CallbackQuery, state: FSMContext):
    if callback.data == "add_button_yes":
        await state.set_state(CampaignStates.waiting_button_text)
        await callback.message.edit_text(
            "🔘 <b>اسم الزر:</b>\nمثال: <code>اطلب الآن</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ تخطي", callback_data="skip_button")]
            ])
        )
    else:
        await state.update_data(button_text=None, button_url=None)
        await show_categories_selection(callback, state)
    await callback.answer()

@router.message(CampaignStates.waiting_button_text)
async def process_button_text(message: Message, state: FSMContext):
    button_text = message.text.strip()
    await state.update_data(button_text=button_text)
    await state.set_state(CampaignStates.waiting_button_url)
    
    await message.answer(
        f"🔗 <b>رابط الزر:</b>\nمثال: <code>https://example.com</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
        ])
    )

@router.message(CampaignStates.waiting_button_url)
async def process_button_url(message: Message, state: FSMContext):
    button_url = message.text.strip()
    await state.update_data(button_url=button_url)
    await show_categories_selection(message, state)

@router.callback_query(F.data == "skip_button")
async def skip_button(callback: CallbackQuery, state: FSMContext):
    await state.update_data(button_text=None, button_url=None)
    await show_categories_selection(callback, state)
    await callback.answer()

async def show_categories_selection(event, state: FSMContext):
    await state.set_state(CampaignStates.waiting_categories)
    await state.update_data(selected_categories=[])
    
    text = "📂 <b>الخطوة 5:</b> اختر تصنيفات القنوات المستهدفة:"
    
    buttons = []
    row = []
    for cat in Config.CATEGORIES:
        row.append(InlineKeyboardButton(text=cat, callback_data=f"select_cat_{cat}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="✅ تم الاختيار", callback_data="categories_done")])
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    else:
        await event.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("select_cat_"), CampaignStates.waiting_categories)
async def toggle_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("select_cat_", "")
    data = await state.get_data()
    selected = data.get("selected_categories", [])
    
    if category in selected:
        selected.remove(category)
    else:
        selected.append(category)
    
    await state.update_data(selected_categories=selected)
    
    text = "📂 <b>اختر تصنيفات القنوات المستهدفة:</b>\n\n"
    if selected:
        text += "✅ <b>المختار:</b>\n"
        for cat in selected:
            text += f"  • {cat}\n"
    
    await callback.answer(f"📂 {category} - {'✅ تمت الإضافة' if category in selected else '❌ تمت الإزالة'}")
    await callback.message.edit_text(text, reply_markup=callback.message.reply_markup)

@router.callback_query(F.data == "categories_done", CampaignStates.waiting_categories)
async def categories_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_categories", [])
    
    if not selected:
        await callback.answer("❌ اختر تصنيفاً واحداً على الأقل", show_alert=True)
        return
    
    await state.set_state(CampaignStates.waiting_channels_count)
    
    await callback.message.edit_text(
        "📢 <b>الخطوة 6:</b> كم عدد القنوات التي تريد الإعلان فيها؟\n"
        "مثال: <code>20</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
        ])
    )
    await callback.answer()

@router.message(CampaignStates.waiting_channels_count)
async def process_channels_count(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 1:
            await message.answer("❌ أقل عدد هو 1. أعد المحاولة:")
            return
        if count > 100:
            await message.answer("❌ أقصى عدد هو 100. أعد المحاولة:")
            return
    except ValueError:
        await message.answer("❌ أدخل رقماً صحيحاً:")
        return
    
    await state.update_data(channels_count=count)
    await state.set_state(CampaignStates.waiting_budget)
    
    await message.answer(
        "💰 <b>الخطوة 7:</b> كم ميزانيتك؟\n"
        "أدخل المبلغ بالريال اليمني.\n"
        "مثال: <code>100000</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
        ])
    )

@router.message(CampaignStates.waiting_budget)
async def process_budget(message: Message, state: FSMContext):
    try:
        budget = float(message.text.strip())
        if budget < 1000:
            await message.answer("❌ أقل ميزانية 1,000 ريال. أعد المحاولة:")
            return
    except ValueError:
        await message.answer("❌ أدخل رقماً صحيحاً:")
        return
    
    data = await state.get_data()
    
    commission_rate = Config.PLATFORM_COMMISSION / 100
    platform_fee = budget * commission_rate
    channels_budget = budget - platform_fee
    
    await state.update_data(
        budget=budget,
        platform_fee=platform_fee,
        channels_budget=channels_budget
    )
    
    summary_text = f"""
📋 <b>ملخص الحملة</b>

📝 الاسم: <b>{data['campaign_title']}</b>
📂 النوع: {data.get('content_type', 'نص')}
📂 التصنيفات: {', '.join(data.get('selected_categories', []))}
📢 عدد القنوات: <b>{data['channels_count']}</b>

💰 <b>التكاليف:</b>
• ميزانية القنوات: <b>{channels_budget} ريال</b>
• عمولة المنصة ({Config.PLATFORM_COMMISSION}%): <b>{platform_fee} ريال</b>
• الإجمالي: <b>{budget} ريال</b>

هل تريد المتابعة؟
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ متابعة للدفع", callback_data="campaign_proceed")],
        [InlineKeyboardButton(text="✏ تعديل", callback_data="create_campaign")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")],
    ])
    
    await state.set_state(CampaignStates.waiting_payment_method)
    await message.answer(summary_text, reply_markup=buttons)

@router.callback_query(F.data == "campaign_proceed", CampaignStates.waiting_payment_method)
async def show_payment_methods(callback: CallbackQuery, state: FSMContext):
    """عرض طرق الدفع مع رقم جوالي"""
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 جوالي", callback_data="pay_jawali")],
        [InlineKeyboardButton(text="🏦 الكريمي - قريباً", callback_data="pay_soon")],
        [InlineKeyboardButton(text="💳 فلوسك - قريباً", callback_data="pay_soon")],
        [InlineKeyboardButton(text="🏧 تحويل بنكي - قريباً", callback_data="pay_soon")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(
        "💳 <b>اختر طريقة الدفع:</b>\n\n"
        "طرق الدفع المتاحة حالياً: جوالي فقط\n"
        "باقي الطرق ستتوفر قريباً.",
        reply_markup=buttons
    )
    await callback.answer()

@router.callback_query(F.data == "pay_soon")
async def pay_soon(callback: CallbackQuery):
    await callback.answer("🕐 هذه الطريقة ستتوفر قريباً. استخدم جوالي حالياً.", show_alert=True)

@router.callback_query(F.data.startswith("pay_"), CampaignStates.waiting_payment_method)
async def process_payment_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.replace("pay_", "")
    
    if method == "soon":
        return
    
    await state.update_data(payment_method=method)
    await state.set_state(CampaignStates.waiting_payment_receipt)
    
    # عرض معلومات الدفع حسب الطريقة
    if method == "jawali":
        payment_info = f"""
📱 <b>الدفع عبر جوالي</b>

📱 <b>رقم جوالي:</b> <code>{Config.JAWALI_NUMBER}</code>
👤 <b>الاسم:</b> {Config.JAWALI_NAME}

📋 <b>الخطوات:</b>
1️⃣ قم بالتحويل إلى الرقم أعلاه
2️⃣ أرسل صورة الحوالة هنا

⚠️ <b>ملاحظة:</b> سيتم مراجعة طلبك وتأكيده خلال 24 ساعة.
    """
    else:
        payment_info = f"""
💳 <b>الدفع عبر {method}</b>

📸 أرسل صورة الحوالة أو الإيصال.
    """
    
    await callback.message.edit_text(
        payment_info,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu")]
        ])
    )
    await callback.answer()

@router.message(CampaignStates.waiting_payment_receipt)
async def process_receipt(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("❌ أرسل صورة الإيصال من فضلك.")
        return
    
    data = await state.get_data()
    user = await db.fetchone(
        "SELECT id FROM users WHERE telegram_id = ?",
        (message.from_user.id,)
    )
    
    if not user:
        await message.answer("❌ خطأ. أعد البدء بـ /start")
        return
    
    cursor = await db.execute(
        """INSERT INTO campaigns 
        (advertiser_id, title, content_type, message_text, media_file_id, 
        button_text, button_url, target_categories, channels_count, budget, platform_fee, total_cost, status) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_payment')""",
        (
            user['id'],
            data['campaign_title'],
            data.get('content_type', 'text'),
            data.get('message_text', ''),
            data.get('media_file_id', ''),
            data.get('button_text', ''),
            data.get('button_url', ''),
            ','.join(data.get('selected_categories', [])),
            data['channels_count'],
            data['budget'],
            data['platform_fee'],
            data['budget']
        )
    )
    
    campaign_id = cursor.lastrowid
    
    await db.execute(
        """INSERT INTO payments 
        (user_id, campaign_id, amount, method, receipt_image_id, status) 
        VALUES (?, ?, ?, ?, ?, 'pending')""",
        (
            user['id'],
            campaign_id,
            data['budget'],
            data.get('payment_method', 'jawali'),
            message.photo[-1].file_id
        )
    )
    
    await state.clear()
    
    # إشعار المدراء
    for admin_id in Config.ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"🔔 <b>دفعة جديدة!</b>\n\n"
                f"👤 {message.from_user.full_name}\n"
                f"💰 {data['budget']} ريال\n"
                f"📱 {data.get('payment_method', 'jawali')}\n"
                f"📋 حملة: {data['campaign_title']}\n\n"
                "للمراجعة: /admin",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 عرض المدفوعات", callback_data="admin_payments")]
                ])
            )
        except:
            pass
    
    await message.answer(
        "✅ <b>تم إنشاء الحملة بنجاح!</b>\n\n"
        "📋 طلبك قيد المراجعة من قبل الإدارة.\n"
        "سيتم إشعارك عند الموافقة على الدفع.\n\n"
        "يمكنك متابعة حالة حملتك من زر 📋 حملاتي",
        reply_markup=get_advertiser_menu()
    )

# ============ عرض حملاتي ============

@router.callback_query(F.data == "my_campaigns")
async def my_campaigns_list(callback: CallbackQuery):
    user = await db.fetchone(
        "SELECT id FROM users WHERE telegram_id = ?",
        (callback.from_user.id,)
    )
    
    if not user:
        await callback.answer("❌ سجل أولاً بـ /start", show_alert=True)
        return
    
    campaigns = await db.fetchall(
        "SELECT * FROM campaigns WHERE advertiser_id = ? ORDER BY created_at DESC LIMIT 20",
        (user['id'],)
    )
    
    if not campaigns:
        await callback.message.edit_text(
            "📭 ليس لديك أي حملات.\n\nأنشئ حملتك الأولى من زر 💰 إنشاء حملة",
            reply_markup=get_advertiser_menu()
        )
        return
    
    text = "📋 <b>حملاتي:</b>\n\n"
    buttons = []
    
    status_emoji = {
        "draft": "📝", "pending_payment": "💳", "pending_admin": "🟡",
        "active": "🟢", "completed": "✅", "rejected": "❌", "cancelled": "🚫"
    }
    status_names = {
        "draft": "مسودة", "pending_payment": "بانتظار الدفع", "pending_admin": "بانتظار الموافقة",
        "active": "نشطة", "completed": "مكتملة", "rejected": "مرفوضة", "cancelled": "ملغية"
    }
    
    for c in campaigns:
        emoji = status_emoji.get(c['status'], "📋")
        name = status_names.get(c['status'], c['status'])
        text += f"{emoji} <b>{c['title']}</b>\n"
        text += f"   الحالة: {name} | 💰 {c['budget']} ريال | 📢 {c['channels_count']} قناة\n\n"
        
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {c['title']}",
            callback_data=f"campaign_detail_{c['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="➕ حملة جديدة", callback_data="create_campaign")])
    buttons.append([InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("campaign_detail_"))
async def campaign_detail(callback: CallbackQuery):
    campaign_id = int(callback.data.replace("campaign_detail_", ""))
    
    campaign = await db.fetchone("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
    
    if not campaign:
        await callback.answer("❌ الحملة غير موجودة", show_alert=True)
        return
    
    channel_stats = await db.fetchone(
        """SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
        FROM campaign_channels WHERE campaign_id = ?""",
        (campaign_id,)
    )
    
    status_emoji = {
        "draft": "📝", "pending_payment": "💳", "pending_admin": "🟡",
        "active": "🟢", "completed": "✅", "rejected": "❌"
    }
    
    detail_text = f"""
📋 <b>{campaign['title']}</b>

📊 <b>معلومات الحملة:</b>
• الحالة: {status_emoji.get(campaign['status'], '📋')} {campaign['status']}
• النوع: {campaign['content_type']}
• التصنيفات: {campaign['target_categories']}

📢 <b>القنوات:</b>
• المطلوب: <b>{campaign['channels_count']}</b>
• تم النشر: <b>{channel_stats['published'] if channel_stats else 0}</b>
• معلقة: <b>{channel_stats['pending'] if channel_stats else 0}</b>

💰 <b>التكاليف:</b>
• الميزانية: <b>{campaign['budget']} ريال</b>
• العمولة: <b>{campaign['platform_fee']} ريال</b>

📅 تاريخ الإنشاء: {campaign['created_at'][:10]}
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 حملاتي", callback_data="my_campaigns")],
    ])
    
    await callback.message.edit_text(detail_text, reply_markup=buttons)
    await callback.answer()
