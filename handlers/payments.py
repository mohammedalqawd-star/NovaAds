import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.connection import Database
from keyboards.main_menu import get_main_menu, get_owner_menu
from config import Config

logger = logging.getLogger(__name__)
router = Router()
db = Database()

class WithdrawalStates(StatesGroup):
    waiting_account = State()
    waiting_amount = State()

@router.callback_query(F.data == "earnings")
async def earnings_menu(callback: CallbackQuery):
    user = await db.fetchone("SELECT * FROM users WHERE telegram_id = ?", (callback.from_user.id,))
    
    if not user:
        await callback.answer("❌ سجل أولاً", show_alert=True)
        return
    
    total_earned = await db.fetchone(
        "SELECT SUM(amount) as total FROM wallet WHERE user_id = ? AND transaction_type = 'ad_revenue'",
        (user['id'],)
    )
    
    completed_ads = await db.fetchone(
        """SELECT COUNT(*) as count FROM campaign_channels cc
        JOIN channels c ON cc.channel_id = c.id
        WHERE c.owner_id = ? AND cc.status = 'published'""",
        (user['id'],)
    )
    
    total_earned_amount = total_earned['total'] if total_earned and total_earned['total'] else 0
    
    text = f"""
💵 <b>الأرباح</b>

💰 رصيدك الحالي: <b>{user['balance']} ريال</b>
📊 إجمالي الأرباح: <b>{total_earned_amount} ريال</b>
📢 الإعلانات المنفذة: <b>{completed_ads['count'] if completed_ads else 0}</b>
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 سحب الأرباح", callback_data="withdraw_earnings")],
        [InlineKeyboardButton(text="📋 سجل المعاملات", callback_data="transaction_history")],
        [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()

@router.callback_query(F.data == "withdraw_earnings")
async def withdraw_start(callback: CallbackQuery, state: FSMContext):
    user = await db.fetchone("SELECT * FROM users WHERE telegram_id = ?", (callback.from_user.id,))
    
    if not user:
        await callback.answer("❌ سجل أولاً", show_alert=True)
        return
    
    if user['balance'] < Config.MIN_WITHDRAWAL:
        await callback.answer(
            f"❌ الحد الأدنى للسحب هو {Config.MIN_WITHDRAWAL} ريال. رصيدك: {user['balance']} ريال",
            show_alert=True
        )
        return
    
    await state.update_data(user_balance=user['balance'])
    await state.set_state(WithdrawalStates.waiting_account)
    
    await callback.message.edit_text(
        f"💵 <b>سحب الأرباح</b>\n\n"
        f"📱 <b>التحويل عبر جوالي</b>\n\n"
        f"أدخل رقم جوالي الخاص بك:\n"
        f"مثال: <code>7XXXXXXXX</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="earnings")]
        ])
    )
    await callback.answer()

@router.message(WithdrawalStates.waiting_account)
async def process_withdrawal_account(message: Message, state: FSMContext):
    account = message.text.strip()
    
    if not account.isdigit() or len(account) < 9:
        await message.answer("❌ رقم جوالي غير صحيح. أعد المحاولة:")
        return
    
    await state.update_data(withdraw_account=account)
    await state.set_state(WithdrawalStates.waiting_amount)
    
    data = await state.get_data()
    
    await message.answer(
        f"💰 <b>كم تريد سحب؟</b>\n\n"
        f"رصيدك المتاح: <b>{data['user_balance']} ريال</b>\n"
        f"الحد الأدنى: <b>{Config.MIN_WITHDRAWAL} ريال</b>\n\n"
        "أدخل المبلغ:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 كل الرصيد", callback_data=f"wd_all_{data['user_balance']}")],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="earnings")],
        ])
    )

@router.callback_query(F.data.startswith("wd_all_"), WithdrawalStates.waiting_amount)
async def withdraw_all(callback: CallbackQuery, state: FSMContext):
    amount = float(callback.data.replace("wd_all_", ""))
    await state.update_data(withdraw_amount=amount)
    await confirm_withdrawal(callback, state)

@router.message(WithdrawalStates.waiting_amount)
async def process_withdrawal_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ أدخل رقماً صحيحاً:")
        return
    
    data = await state.get_data()
    
    if amount < Config.MIN_WITHDRAWAL:
        await message.answer(f"❌ الحد الأدنى للسحب هو {Config.MIN_WITHDRAWAL} ريال:")
        return
    
    if amount > data['user_balance']:
        await message.answer(f"❌ رصيدك غير كاف. رصيدك: {data['user_balance']} ريال:")
        return
    
    await state.update_data(withdraw_amount=amount)
    await confirm_withdrawal(message, state)

async def confirm_withdrawal(event, state: FSMContext):
    data = await state.get_data()
    
    confirm_text = f"""
⚠️ <b>تأكيد طلب السحب</b>

📱 الطريقة: <b>جوالي</b>
📱 الحساب: <code>{data['withdraw_account']}</code>
💰 المبلغ: <b>{data['withdraw_amount']} ريال</b>

هل تؤكد الطلب؟
    """
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تأكيد", callback_data="confirm_withdrawal")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="earnings")],
    ])
    
    if isinstance(event, Message):
        await event.answer(confirm_text, reply_markup=buttons)
    else:
        await event.message.edit_text(confirm_text, reply_markup=buttons)
        await event.answer()

@router.callback_query(F.data == "confirm_withdrawal")
async def execute_withdrawal(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await db.fetchone("SELECT * FROM users WHERE telegram_id = ?", (callback.from_user.id,))
    
    if not user:
        await callback.answer("❌ خطأ", show_alert=True)
        return
    
    await db.execute(
        """INSERT INTO withdrawals 
        (user_id, amount, method, account_details, status) 
        VALUES (?, ?, 'jawali', ?, 'pending')""",
        (user['id'], data['withdraw_amount'], data['withdraw_account'])
    )
    
    new_balance = user['balance'] - data['withdraw_amount']
    await db.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user['id']))
    
    await db.execute(
        """INSERT INTO wallet 
        (user_id, amount, transaction_type, description, balance_before, balance_after) 
        VALUES (?, ?, 'withdrawal', ?, ?, ?)""",
        (user['id'], -data['withdraw_amount'], f"طلب سحب عبر جوالي", user['balance'], new_balance)
    )
    
    await state.clear()
    
    # إشعار المدراء
    for admin_id in Config.ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"💵 <b>طلب سحب جديد</b>\n"
                f"👤 {callback.from_user.full_name}\n"
                f"💰 {data['withdraw_amount']} ريال\n"
                f"📱 جوالي: {data['withdraw_account']}"
            )
        except:
            pass
    
    await callback.message.edit_text(
        f"✅ <b>تم تقديم طلب السحب!</b>\n\n"
        f"💰 المبلغ: <b>{data['withdraw_amount']} ريال</b>\n"
        f"📱 جوالي: {data['withdraw_account']}\n\n"
        "سيتم مراجعة طلبك وتحويل المبلغ خلال 24-48 ساعة.",
        reply_markup=get_owner_menu()
    )
    await callback.answer("✅ تم تقديم الطلب", show_alert=True)

@router.callback_query(F.data == "transaction_history")
async def transaction_history(callback: CallbackQuery):
    user = await db.fetchone("SELECT id FROM users WHERE telegram_id = ?", (callback.from_user.id,))
    
    if not user:
        await callback.answer("❌ سجل أولاً", show_alert=True)
        return
    
    transactions = await db.fetchall(
        "SELECT * FROM wallet WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
        (user['id'],)
    )
    
    if not transactions:
        text = "📭 لا توجد معاملات بعد."
    else:
        text = "📋 <b>سجل المعاملات:</b>\n\n"
        for t in transactions:
            amount_text = f"+{t['amount']}" if t['amount'] > 0 else str(t['amount'])
            text += f"{amount_text} ريال - {t['description'][:60]}\n"
            text += f"   📅 {t['created_at'][:16]}\n\n"
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 الأرباح", callback_data="earnings")],
        [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="main_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer()
