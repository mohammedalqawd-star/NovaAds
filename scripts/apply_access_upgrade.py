from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "bot.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"❌ لم أجد موضع {label}")
    return text.replace(old, new, 1)


s = BOT.read_text(encoding="utf-8")

s = replace_once(
    s,
    "from services.downloader import DownloadError, available_video_formats, cleanup, download_media, get_media_info\n",
    "from services.downloader import DownloadError, available_video_formats, cleanup, download_media, get_media_info\nfrom services.access_control import AccessDenied, approve_payment, consume, grant, refund as access_refund\n",
    "استيراد access control",
)

s = replace_once(
    s,
    "    admin_broadcast = State()\n",
    "    admin_broadcast = State()\n    admin_credit_target = State()\n    admin_credit_amount = State()\n",
    "حالات إضافة الرصيد",
)

charge_pattern = re.compile(r"def charge\(uid: int, amount: int\) -> bool:\n(?:    .*\n)+?\n\ndef refund\(uid: int, amount: int\) -> None:\n(?:    .*\n)+?\n", re.MULTILINE)
new_charge = '''def charge(uid: int, amount: int) -> bool:\n    """Atomic legacy-compatible credit check/debit."""\n    try:\n        result = consume(DB, uid, "__legacy__", default_cost=amount)\n        return result.allowed\n    except AccessDenied:\n        return False\n\n\ndef refund(uid: int, amount: int) -> None:\n    access_refund(DB, uid, amount)\n\n'''
if not charge_pattern.search(s):
    raise SystemExit("❌ لم أجد دوال charge/refund")
s = charge_pattern.sub(new_charge, s, count=1)

# The generic legacy charge path must still work even when the service registry has no __legacy__ row.
# Add a service-specific helper and switch all known service charges to it.
marker = "def job_start(uid: int, service: str, cost: int) -> str:\n"
helper = '''def service_charge(uid: int, service: str, default_cost: int = 1) -> tuple[bool, int, str]:\n    try:\n        result = consume(DB, uid, service, default_cost=default_cost)\n        return result.allowed, max(0, result.credits_after), result.reason\n    except AccessDenied as exc:\n        return False, get_credits(uid), str(exc)\n\n\n'''
s = replace_once(s, marker, helper + marker, "دالة service_charge")

# Replace direct charge calls in the three paid execution paths with service-aware charging.
s = s.replace(
    '    if not charge(m.from_user.id, cost):\n        await state.clear()\n        return await m.answer("❌ رصيدك غير كافٍ.", reply_markup=main_kb())\n',
    '    allowed, _, reason = service_charge(m.from_user.id, "ai_writer", cost)\n    if not allowed:\n        await state.clear()\n        return await m.answer(f"❌ {html.escape(reason or \'رصيدك غير كافٍ.\')}", reply_markup=main_kb())\n',
    1,
)
s = s.replace(
    '    if not charge(q.from_user.id, cost):\n        await state.clear()\n        return await q.answer("❌ رصيدك غير كافٍ.", show_alert=True)\n',
    '    allowed, _, reason = service_charge(q.from_user.id, "media_downloader", cost)\n    if not allowed:\n        await state.clear()\n        return await q.answer(f"❌ {reason or \'رصيدك غير كافٍ.\'}", show_alert=True)\n',
    1,
)
s = s.replace(
    '    if not charge(q.from_user.id, cost):\n        await state.clear()\n        return await q.answer("❌ رصيدك غير كافٍ.", show_alert=True)\n',
    '    allowed, _, reason = service_charge(q.from_user.id, "media_downloader_audio", cost)\n    if not allowed:\n        await state.clear()\n        return await q.answer(f"❌ {reason or \'رصيدك غير كافٍ.\'}", show_alert=True)\n',
    1,
)
s = s.replace(
    '    if not charge(m.from_user.id, cost):\n        await state.clear()\n        return await m.answer("❌ رصيدك غير كافٍ.", reply_markup=main_kb())\n',
    '    allowed, _, reason = service_charge(m.from_user.id, tool_name, cost)\n    if not allowed:\n        await state.clear()\n        return await m.answer(f"❌ {html.escape(reason or \'رصيدك غير كافٍ.\')}", reply_markup=main_kb())\n',
    1,
)

# Add an admin credit-management button.
s = replace_once(
    s,
    '    b.button(text="💳 المدفوعات", callback_data="admin:payments")\n',
    '    b.button(text="💳 المدفوعات", callback_data="admin:payments")\n    b.button(text="💎 إضافة رصيد لمستخدم", callback_data="admin:credits")\n',
    "زر إضافة الرصيد",
)

credit_handlers = '''\n\n@dp.callback_query(F.data == "admin:credits")\nasync def admin_credits_start(q: CallbackQuery, state: FSMContext):\n    if not admin_only(q.from_user.id):\n        return await q.answer("غير مصرح", show_alert=True)\n    await state.set_state(Form.admin_credit_target)\n    await q.message.answer("💎 أرسل ID المستخدم الذي تريد إضافة الرصيد له.")\n    await q.answer()\n\n\n@dp.message(Form.admin_credit_target)\nasync def admin_credit_target_input(m: Message, state: FSMContext):\n    if not admin_only(m.from_user.id):\n        return await state.clear()\n    try:\n        target = int((m.text or "").strip())\n    except ValueError:\n        return await m.answer("❌ أرسل ID رقمي صحيح.")\n    ensure_user(target)\n    await state.update_data(admin_credit_target=target)\n    await state.set_state(Form.admin_credit_amount)\n    await m.answer("🔢 أرسل عدد العمليات التي تريد إضافتها، مثال: 20")\n\n\n@dp.message(Form.admin_credit_amount)\nasync def admin_credit_amount_input(m: Message, state: FSMContext):\n    if not admin_only(m.from_user.id):\n        return await state.clear()\n    try:\n        amount = int((m.text or "").strip())\n        if amount <= 0 or amount > 100000:\n            raise ValueError\n    except ValueError:\n        return await m.answer("❌ أرسل رقماً صحيحاً بين 1 و100000.")\n    data = await state.get_data()\n    target = int(data["admin_credit_target"])\n    new_balance = grant(DB, target, amount)\n    await state.clear()\n    try:\n        await bot.send_message(target, f"✅ تمت إضافة <b>{amount}</b> عملية إلى حسابك من المدير.\\n💎 رصيدك الحالي: <b>{new_balance}</b>")\n    except Exception:\n        pass\n    await m.answer(f"✅ تمت إضافة {amount} عملية للمستخدم <code>{target}</code>.\\n💎 الرصيد الحالي: <b>{new_balance}</b>", reply_markup=admin_kb())\n\n'''
s = replace_once(s, '\n@dp.callback_query(F.data == "admin:users")\n', credit_handlers + '\n@dp.callback_query(F.data == "admin:users")\n', "معالجات إضافة الرصيد")

# Replace fixed 20-credit approval with the transactional payment helper.
approve_pattern = re.compile(r'@dp\.callback_query\(F\.data\.startswith\("approve:"\)\)\nasync def approve\(q: CallbackQuery\):\n.*?\n\n\nasync def main\(\):', re.S)
new_approve = '''@dp.callback_query(F.data.startswith("approve:"))\nasync def approve(q: CallbackQuery):\n    if not admin_only(q.from_user.id):\n        return await q.answer("غير مصرح", show_alert=True)\n    try:\n        pid = int(q.data.split(":", 1)[1])\n        user_id, credits = approve_payment(DB, pid, default_credits=20)\n    except (ValueError, AccessDenied) as exc:\n        return await q.answer(str(exc), show_alert=True)\n    try:\n        await bot.send_message(\n            user_id,\n            f"✅ تمت الموافقة على التحويل وإضافة <b>{credits} عملية</b> إلى رصيدك.\\n"\n            f"💎 رصيدك الحالي: <b>{get_credits(user_id)}</b>",\n        )\n    except Exception:\n        log.exception("credit approval notification")\n    await q.answer(f"تمت الموافقة وإضافة {credits} عملية")\n    await admin(q)\n\n\nasync def main():'''
if not approve_pattern.search(s):
    raise SystemExit("❌ لم أجد معالج موافقة الدفع")
s = approve_pattern.sub(new_approve, s, count=1)

BOT.write_text(s, encoding="utf-8")
print("✅ تم تطبيق نظام الرصيد والوصول على bot.py")
''