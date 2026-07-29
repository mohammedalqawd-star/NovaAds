import logging
from datetime import datetime, timedelta
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

class SubscriptionStates(StatesGroup):
    waiting_payment_receipt = State()
    waiting_coupon = State()

@router.callback_query(F.data == "subscriptions_menu")
async def subscriptions_menu(callback: CallbackQuery):
    user = await db.fetchone("SELECT * FROM users WHERE telegram_id = ?", (callback.from_user.id,))
    
    current_sub = await db.fetchone(
        """SELECT us.*, s.name, s.features, s.price, s.channels_limit, s.ads_limit
        FROM user_subscriptions us
        JOIN subscriptions s ON us.subscription_id = s.id
        WHERE us.user_id = ? AND us.status = 'active'
        ORDER BY us.end_date DESC LIMIT 1""",
        (user['id'],) if user else (0,)
    )
    
    if current_sub:
        expiry_date = datetime.strptime(current_sub['end_date'], '%Y-%m-%d %H:%M:%S')
        days_left = (expiry_date - datetime.now()).days
        
        text = f"""
💎 <b>اشتراكك الحالي</b>

⭐ الخطة: <b>{current_sub['name']}</b>
📅 ينتهي في: <b>{current_sub['end_date'][:10]}</b>
⏳ المتبقي: <b>{days_left} يوم</b>

📊 <b>مميزاتك:</b>
• القنوات: <b>{current_sub['channels_limit']}</b>
• الإعلانات الشهرية: <b>{current_sub['ads_limit']}</b>
        """
        
        buttons = [
            [InlineKeyboardButton(text="🔄 ترقية الاشتراك", callback_data="show_plans")],
            [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")],
        ]
    else:
        text = "💎 <b>الاشتراكات</b>\n\nاختر الباقة المناسبة لك!"
        buttons = [
            [InlineKeyboardButton(text="📋 عرض الباقات", callback_data="show_plans")],
            [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")],
        ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data == "show_plans")
async def show_plans(callback: CallbackQuery):
    plans = await db.fetchall("SELECT * FROM subscriptions WHERE is_active = 1 ORDER BY price ASC")
    
    text = "💎 <b>الباقات المتاحة:</b>\n\n"
    buttons = []
    
    plan_emoji = {"مجاني": "🆓", "فضي": "🥈", "ذهبي": "🥇", "شركات": "👑"}
    
    for plan in plans:
        emoji = plan_emoji.get(plan['name'], "💎")
        text += f"{emoji} <b>{plan['name']}</b>\n"
        text += f"💰 السعر: <b>{plan['price']} ريال/شهر</b>\n"
        text += f"📢 القنوات: <b>{plan['channels_limit']}</b>\n"
        text += f"📊 الإعلانات: <b>{plan['ads_limit']}</b>\n"
        text += f"📝 المميزات:\n{plan['features']}\n\n"
        
        if plan['price'] > 0:
            buttons.append([InlineKeyboardButton(
                text=f"{emoji} {plan['name']} - {plan['price']} ريال",
                callback_data=f"subscribe_{plan['id']}"
            )])
    
    buttons.append([InlineKeyboardButton(text="🔙 الاشتراكات", callback_data="subscriptions_menu")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("subscribe_"))
async def subscribe_to_plan(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.replace("subscribe_", ""))
    plan = await db.fetchone("SELECT * FROM subscriptions WHERE id = ?", (plan_id,))
    
    if not plan:
        await callback.answer("❌ الباقة غير متوفرة", show_alert=True)
        return
    
    await state.update_data(plan_id=plan_id, plan_price=plan['price'])
    await state.set_state(SubscriptionStates.waiting_payment_receipt)
    
    # عرض معلومات الدفع بجوالي
    payment_text = f"""
💳 <b>الاشتراك في {plan['name']}</b>
💰 المبلغ: <b>{plan['price']} ريال</b>

📱 <b>الدفع عبر جوالي:</b>
📱 الرقم: <code>{Config.JAWALI_NUMBER}</code>
👤 الاسم: {Config.JAWALI_NAME}

📸 أرسل صورة الحوالة للمتابعة.
    """
    
    await callback.message.edit_text(
        payment_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="subscriptions_menu")]
        ])
    )
    await callback.answer()

@router.message(SubscriptionStates.waiting_payment_receipt)
async def process_sub_receipt(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("❌ أرسل صورة الإيصال.")
        return
    
    data = await state.get_data()
    user = await db.fetchone("SELECT * FROM users WHERE telegram_id = ?", (message.from_user.id,))
    
    if not user:
        await message.answer("❌ خطأ. أعد البدء بـ /start")
        return
    
    await db.execute(
        """INSERT INTO payments 
        (user_id, subscription_id, amount, method, receipt_image_id, status) 
        VALUES (?, ?, ?, 'jawali', ?, 'pending')""",
        (user['id'], data['plan_id'], data['plan_price'], message.photo[-1].file_id)
    )
    
    await state.clear()
    
    # إشعار المدراء
    for admin_id in Config.ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"🔔 <b>طلب اشتراك جديد!</b>\n\n"
                f"👤 {message.from_user.full_name}\n"
                f"💰 {data['plan_price']} ريال\n"
                f"📱 جوالي\n\n"
                "للمراجعة: /admin"
            )
        except:
            pass
    
    await message.answer(
        "✅ <b>تم استلام طلب الاشتراك!</b>\n\n"
        "طلبك قيد المراجعة. سيتم تفعيل اشتراكك خلال 24 ساعة.\n"
        "شكراً لثقتك بـ Nova Ads! 🚀",
        reply_markup=get_main_menu(message.from_user.id)
    )

@router.callback_query(F.data == "my_subscription")
async def my_subscription_status(callback: CallbackQuery):
    user = await db.fetchone("SELECT id FROM users WHERE telegram_id = ?", (callback.from_user.id,))
    
    if not user:
        await callback.answer("❌ سجل أولاً", show_alert=True)
        return
    
    current = await db.fetchone(
        """SELECT us.*, s.name, s.features, s.price, s.channels_limit, s.ads_limit
        FROM user_subscriptions us
        JOIN subscriptions s ON us.subscription_id = s.id
        WHERE us.user_id = ? AND us.status = 'active'
        ORDER BY us.end_date DESC LIMIT 1""",
        (user['id'],)
    )
    
    if not current:
        await callback.message.edit_text(
            "📭 ليس لديك اشتراك نشط.\n\nاشترك الآن من 💎 الاشتراكات",
            reply_markup=get_main_menu(callback.from_user.id)
        )
        return
    
    expiry = datetime.strptime(current['end_date'], '%Y-%m-%d %H:%M:%S')
    days_left = max(0, (expiry - datetime.now()).days)
    
    text = f"""
💎 <b>اشتراكي</b>

⭐ الخطة: <b>{current['name']}</b>
💰 السعر: <b>{current['price']} ريال/شهر</b>
📅 البداية: {current['start_date'][:10]}
📅 النهاية: {current['end_date'][:10]}
⏳ المتبقي: <b>{days_left} يوم</b>

📊 <b>المميزات:</b>
• القنوات: <b>{current['channels_limit']}</b>
• الإعلانات: <b>{current['ads_limit']}</b>

{current['features']}
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ترقية", callback_data="show_plans")],
        [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()
