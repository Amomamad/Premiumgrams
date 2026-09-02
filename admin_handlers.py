import sqlite3
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

admin_router = Router()
ADMIN_ID = 5136501808
DB_PATH = "bot.db"

class AdminStates(StatesGroup):
    waiting_for_makecode = State()
    waiting_for_setbalance = State()
    waiting_for_sendall = State()
    waiting_for_direct_msg = State()
    waiting_for_channel = State()
    waiting_for_discount = State()

class UserStates(StatesGroup):
    waiting_for_redeem = State()
    waiting_for_card_withdraw = State()

# ساخت جدول کدهای تخفیف
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS discounts (
        code TEXT PRIMARY KEY,
        percent INTEGER DEFAULT 0,
        amount INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()
except Exception as e:
    print(f"DB Discount Error: {e}")

def admin_gift_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ساخت کد هدیه", callback_data="btn_make_code")],
        [InlineKeyboardButton(text="💰 تغییر موجودی کاربر", callback_data="btn_set_balance")],
        [InlineKeyboardButton(text="📢 ارسال پیام همگانی", callback_data="btn_send_all")],
        [InlineKeyboardButton(text="🎁 ثبت کد هدیه (تست کاربر)", callback_data="btn_redeem_gift")]
    ])

# منوی ابزارهای هدیه
@admin_router.callback_query(F.data == "admin_gift_menu")
async def cb_admin_gift_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.answer("⚙️ **بخش مدیریت کدهای هدیه و ابزارها**\nیک گزینه را انتخاب کنید:", reply_markup=admin_gift_keyboard(), parse_mode="Markdown")
    await call.answer()

# --- ۱. مدیریت کدهای تخفیف ---
@admin_router.callback_query(F.data == "adm:discounts")
async def cb_adm_discounts(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ساخت کد تخفیف جدید", callback_data="btn_make_discount")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm:back")]
    ])
    await call.message.answer("🎫 **مدیریت کدهای تخفیف**\nاز این بخش می‌توانید کدهای تخفیف خریداران را مدیریت کنید:", reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@admin_router.callback_query(F.data == "btn_make_discount")
async def cb_make_discount(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.answer("🎫 لطفاً کد تخفیف و درصد تخفیف را وارد کنید:\n\n`کد درصد`\nمثال: `OFF20 20` (یعنی کد OFF20 با ۲۰٪ تخفیف)", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_discount)
    await call.answer()

@admin_router.message(AdminStates.waiting_for_discount)
async def process_discount(message: Message, state: FSMContext):
    try:
        code, percent = message.text.split()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO discounts (code, percent) VALUES (?, ?)", (code.upper(), int(percent)))
        conn.commit()
        conn.close()
        await message.reply(f"✅ کد تخفیف `{code.upper()}` با {percent}٪ تخفیف فعال شد.", parse_mode="Markdown")
    except Exception:
        await message.reply("❌ فرمت اشتباه است. مثال: `OFF20 20`", parse_mode="Markdown")
    await state.clear()

# --- ۲. درخواست‌های تسویه زیرمجموعه‌گیری (برای ادمین) ---
@admin_router.callback_query(F.data == "btn_withdraw_list")
async def cb_withdraw_list(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, amount, card_number FROM withdraw_requests WHERE status = 'pending'")
    reqs = cursor.fetchall()
    conn.close()

    if not reqs:
        await call.message.answer("🟢 هیچ درخواست تسویه‌ای در انتظار وجود ندارد.")
        await call.answer()
        return

    msg = "💸 **درخواست‌های تسویه حساب زیرمجموعه:**\n\n"
    for r in reqs:
        msg += f"🆔 کد درخواست: `{r[0]}`\n👤 آیدی کاربر: `{r[1]}`\n💰 مبلغ: `{r[2]:,}` تومان\n💳 شماره کارت: `{r[3]}`\n---------------------\n"
    
    await call.message.answer(msg, parse_mode="Markdown")
    await call.answer()

# --- ۳. تسویه حساب پورسانت توسط کاربر ---
@admin_router.message(F.text == "🧑‍🤝‍🧑 زیرمجموعه‌گیری")
async def btn_referral_menu(message: Message):
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    ref_bal = res[0] if res and res[0] else 0
    conn.close()

    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 انتقال درآمد به کیف‌پول اصلی", callback_data="ref_to_wallet")],
        [InlineKeyboardButton(text="💳 درخواست واریز به کارت", callback_data="ref_to_card")]
    ])

    msg = f"🧑‍🤝‍🧑 **سیستم کسب درآمد و زیرمجموعه‌گیری**\n\n" \
          f"🔗 لینک اختصاصی شما:\n`{ref_link}`\n\n" \
          f"💰 درآمد شما از پورسانت زیرمجموعه‌ها: `{ref_bal:,}` تومان"
    
    await message.reply(msg, reply_markup=kb, parse_mode="Markdown")

# انتقال به کیف پول
@admin_router.callback_query(F.data == "ref_to_wallet")
async def cb_ref_to_wallet(call: CallbackQuery):
    user_id = call.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    ref_bal = res[0] if res and res[0] else 0

    if ref_bal <= 0:
        await call.answer("❌ شما موجودی درآمدی برای انتقال ندارید.", show_alert=True)
        conn.close()
        return

    cursor.execute("UPDATE users SET balance = balance + ?, ref_balance = 0 WHERE user_id = ?", (ref_bal, user_id))
    conn.commit()
    conn.close()

    await call.message.answer(f"✅ مبلغ `{ref_bal:,}` تومان از درآمد زیرمجموعه‌گیری به کیف‌پول اصلی شما منتقل شد.", parse_mode="Markdown")
    await call.answer()

# درخواست واریز به کارت
@admin_router.callback_query(F.data == "ref_to_card")
async def cb_ref_to_card(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    ref_bal = res[0] if res and res[0] else 0
    conn.close()

    if ref_bal < 50000:
        await call.answer("❌ حداقل مبلغ برای برداشت به کارت ۵۰,۰۰۰ تومان است.", show_alert=True)
        return

    await call.message.answer(f"💳 شما قصد برداشت `{ref_bal:,}` تومان را دارید.\nلطفاً **شماره کارت ۱۶ رقمی** خود را ارسال کنید:", parse_mode="Markdown")
    await state.set_state(UserStates.waiting_for_card_withdraw)
    await call.answer()

@admin_router.message(UserStates.waiting_for_card_withdraw)
async def process_card_withdraw(message: Message, state: FSMContext):
    user_id = message.from_user.id
    card_num = message.text.strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    ref_bal = res[0] if res and res[0] else 0

    if ref_bal >= 50000:
        cursor.execute("INSERT INTO withdraw_requests (user_id, amount, card_number) VALUES (?, ?, ?)", (user_id, ref_bal, card_num))
        cursor.execute("UPDATE users SET ref_balance = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        await message.reply("✅ درخواست تسویه شما ثبت شد و به مدیریت ارسال گردید.")
    else:
        await message.reply("❌ موجودی کافی نیست.")

    conn.close()
    await state.clear()

# --- ۴. سایر هندلرها (آمار، ارسال همگانی، مستقیم و...) ---
# هندلر قدیمی آمار حذف شد (وضعیت اشتباه 'completed' چک می‌کرد) - نسخه‌ی درست تو admin_stats.py هست

@admin_router.callback_query(F.data == "btn_direct_msg")
async def cb_direct_msg(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.answer("📥 `آیدی_عددی متن پیام` را وارد کنید:", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_direct_msg)
    await call.answer()

@admin_router.message(AdminStates.waiting_for_direct_msg)
async def process_direct_msg(message: Message, state: FSMContext):
    try:
        parts = message.text.split(maxsplit=1)
        target_id, text = int(parts[0]), parts[1]
        await message.bot.send_message(target_id, f"✉️ **پیام از مدیریت:**\n\n{text}", parse_mode="Markdown")
        await message.reply("✅ پیام ارسال شد.")
    except Exception as e:
        await message.reply(f"❌ خطا: {e}")
    await state.clear()

@admin_router.callback_query(F.data == "btn_set_channel")
async def cb_set_channel(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.answer("📢 آیدی عمومی کانال را وارد کنید (مثال: `@MyChannel`):")
    await state.set_state(AdminStates.waiting_for_channel)
    await call.answer()

@admin_router.message(AdminStates.waiting_for_channel)
async def process_set_channel(message: Message, state: FSMContext):
    ch_name = message.text.strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'force_channel'", (ch_name,))
    conn.commit()
    conn.close()
    await message.reply(f"✅ کانال به `{ch_name}` تغییر یافت.", parse_mode="Markdown")
    await state.clear()

@admin_router.callback_query(F.data == "btn_make_code")
async def cb_make_code(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.answer("📝 `کد مبلغ ظرفیت` را وارد کنید:", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_makecode)
    await call.answer()

@admin_router.message(AdminStates.waiting_for_makecode)
async def process_makecode(message: Message, state: FSMContext):
    try:
        code, amount, capacity = message.text.split()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO gift_codes (code, amount, capacity) VALUES (?, ?, ?)", (code.upper(), int(amount), int(capacity)))
        conn.commit()
        conn.close()
        await message.reply(f"✅ کد هدیه `{code.upper()}` ساخته شد.", parse_mode="Markdown")
    except Exception:
        await message.reply("❌ فرمت اشتباه است.")
    await state.clear()

@admin_router.callback_query(F.data == "btn_set_balance_disabled_old")
async def cb_set_balance(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.answer("💰 `آیدی_عددی مبلغ` را وارد کنید:", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_setbalance)
    await call.answer()

@admin_router.message(AdminStates.waiting_for_setbalance)
async def process_setbalance(message: Message, state: FSMContext):
    try:
        user_id, amount = message.text.split()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (int(amount), int(user_id)))
        conn.commit()
        conn.close()
        await message.reply(f"✅ موجودی تغییر یافت.")
    except Exception:
        await message.reply("❌ فرمت اشتباه است.")
    await state.clear()

@admin_router.callback_query(F.data == "btn_send_all")
async def cb_send_all(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.answer("📢 پیام همگانی را ارسال کنید:")
    await state.set_state(AdminStates.waiting_for_sendall)
    await call.answer()

@admin_router.message(AdminStates.waiting_for_sendall)
async def process_sendall(message: Message, state: FSMContext):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    success, failed = 0, 0
    for user in users:
        try:
            await message.copy_to(chat_id=user[0])
            success += 1
        except Exception:
            failed += 1
    await message.reply(f"✅ پایان ارسال.\nموفق: {success} | ناموفق: {failed}")
    await state.clear()

@admin_router.message(F.text == "🎁 ثبت کد هدیه")
@admin_router.callback_query(F.data == "btn_redeem_gift")
async def cb_redeem_gift(event, state: FSMContext):
    msg_target = event.message if isinstance(event, CallbackQuery) else event
    await msg_target.answer("🎁 لطفاً کد هدیه خود را ارسال کنید:")
    await state.set_state(UserStates.waiting_for_redeem)
    if isinstance(event, CallbackQuery):
        await event.answer()

@admin_router.message(UserStates.waiting_for_redeem)
async def process_redeem(message: Message, state: FSMContext):
    user_id = message.from_user.id
    code_input = message.text.strip().upper()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT amount, capacity, used_count FROM gift_codes WHERE code = ?", (code_input,))
    code_data = cursor.fetchone()

    if not code_data:
        conn.close()
        await message.reply("❌ کد هدیه وارد شده نامعتبر است.")
        await state.clear()
        return

    amount, capacity, used_count = code_data
    if used_count >= capacity:
        conn.close()
        await message.reply("❌ ظرفیت این کد هدیه به پایان رسیده است.")
        await state.clear()
        return

    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("UPDATE gift_codes SET used_count = used_count + 1 WHERE code = ?", (code_input,))
    conn.commit()
    conn.close()

    await message.reply(f"🎉 تبریک! حساب شما به میزان {amount:,} تومان شارژ شد.")
    await state.clear()

# ==========================================
# بخش برداشت و تسویه حساب زیرمجموعه‌گیری
# ==========================================
from keyboards import ref_wallet_kb

@admin_router.message(F.text == "🧑‍🤝‍🧑 زیرمجموعه‌گیری")
async def show_referral_panel(message: Message):
    user_id = message.from_user.id
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    ref_balance = row[0] if row and row[0] else 0
    conn.close()

    text = f"🧑‍🤝‍🧑 **پنل زیرمجموعه‌گیری**\n\n" \
           f"🔗 لینک اختصاصی شما:\n`{ref_link}`\n\n" \
           f"💰 موجودی پورسانت شما: `{ref_balance:,}` تومان\n\n" \
           f"میتوانید این موجودی را به کیف‌پول اصلی منتقل کنید یا درخواست واریز به کارت ثبت کنید."

    await message.reply(text, reply_markup=ref_wallet_kb(), parse_mode="Markdown")

# کلیک روی گزینه انتقال به کیف‌پول اصلی
@admin_router.callback_query(F.data == "ref_to_wallet")
async def cb_ref_to_wallet(call: CallbackQuery):
    user_id = call.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    ref_balance = row[0] if row and row[0] else 0

    if ref_balance <= 0:
        conn.close()
        await call.answer("❌ موجودی پورسانت شما صفر است.", show_alert=True)
        return

    cursor.execute("UPDATE users SET balance = balance + ?, ref_balance = 0 WHERE user_id = ?", (ref_balance, user_id))
    conn.commit()
    conn.close()

    await call.message.answer(f"✅ مبلغ `{ref_balance:,}` تومان با موفقیت به کیف‌پول اصلی شما منتقل شد.", parse_mode="Markdown")
    await call.answer()

# کلیک روی گزینه درخواست واریز به کارت
@admin_router.callback_query(F.data == "ref_to_card")
async def cb_ref_to_card(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    ref_balance = row[0] if row and row[0] else 0

    if ref_balance < 50000:
        conn.close()
        await call.answer("❌ حداقل مبلغ جهت تسویه حساب به کارت ۵۰,۰۰۰ تومان است.", show_alert=True)
        return

    await call.message.answer("💳 لطفاً شماره کارت ۱۶ رقمی و نام صاحب حساب را ارسال کنید:")
    await state.set_state(UserStates.waiting_for_card_withdraw)
    await call.answer()

@admin_router.message(UserStates.waiting_for_card_withdraw)
async def process_card_withdraw(message: Message, state: FSMContext):
    user_id = message.from_user.id
    card_info = message.text.strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    ref_balance = row[0] if row and row[0] else 0

    if ref_balance < 50000:
        conn.close()
        await message.reply("❌ موجودی کافی نیست.")
        await state.clear()
        return

    cursor.execute("INSERT INTO withdraw_requests (user_id, amount, card_number) VALUES (?, ?, ?)", (user_id, ref_balance, card_info))
    cursor.execute("UPDATE users SET ref_balance = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    # اطلاع به ادمین
    await message.bot.send_message(
        ADMIN_ID,
        f"🚨 **درخواست تسویه حساب جدید!**\n\n"
        f"👤 کاربر: `{user_id}`\n"
        f"💰 مبلغ: `{ref_balance:,}` تومان\n"
        f"💳 شماره کارت: `{card_info}`",
        parse_mode="Markdown"
    )

    await message.reply("✅ درخواست تسویه شما ثبت شد و به مدیریت ارسال گردید.")
    await state.clear()
