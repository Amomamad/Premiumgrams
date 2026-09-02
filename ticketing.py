import sqlite3
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import ADMIN_IDS
from keyboards import main_menu

ticket_router = Router()


def init_ticket_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            message TEXT,
            response TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()


init_ticket_db()


class TicketState(StatesGroup):
    waiting_for_message = State()
    waiting_for_reply = State()


SUPPORT_BUTTON_TEXT = "☎️ پشتیبانی"

MAIN_MENU_TEXTS = [
    "🛍 خرید محصول", "👤 حساب کاربری", "💳 شارژ حساب",
    "📦 سفارش‌های من", "🧑‍🤝‍🧑 زیرمجموعه‌گیری", SUPPORT_BUTTON_TEXT,
    "🛠 پنل مدیریت",
]


@ticket_router.message(F.text == SUPPORT_BUTTON_TEXT)
async def ticket_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ارسال تیکت جدید", callback_data="ticket_create_new", style="success", icon_custom_emoji_id="5444856076954520455")],
        [InlineKeyboardButton(text="تیکت‌های من", callback_data="ticket_list_my", style="primary", icon_custom_emoji_id="5224450179368767019")]
    ])
    await message.answer("بخش پشتیبانی و مدیریت تیکت‌ها:\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=kb)


@ticket_router.callback_query(F.data == "ticket_create_new")
async def ticket_create_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TicketState.waiting_for_message)
    await callback.message.answer(
        "لطفاً پیام یا مشکل خود را ارسال کنید (کیبورد شما بسته شد):",
        reply_markup=ReplyKeyboardRemove()
    )
    await callback.message.answer(
        "برای لغو عملیات روی دکمه زیر بزنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="انصراف", callback_data="ticket_cancel_action", style="danger", icon_custom_emoji_id="5875208759176860365")]
        ])
    )
    await callback.answer()


@ticket_router.callback_query(F.data == "ticket_cancel_action")
async def ticket_cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("عملیات لغو شد.")
    await callback.message.answer("به منوی اصلی بازگشتید:", reply_markup=main_menu())
    await callback.answer()


@ticket_router.callback_query(F.data == "ticket_list_my")
async def ticket_list_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, message, response, status FROM tickets WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
    tickets = cursor.fetchall()
    conn.close()

    if not tickets:
        await callback.message.answer("📂 شما تاکنون هیچ تیکتی ثبت نکرده‌اید.")
        await callback.answer()
        return

    text = "📂 **آخرین تیکت‌های شما:**\n\n"
    for t_id, msg, resp, status in tickets:
        status_str = "⏳ در انتظار پاسخ ادمین" if status == 'pending' else "✅ پاسخ داده شده"
        text += f'<tg-emoji emoji-id="5875345931842360057">🆔</tg-emoji> تیکت شماره #{t_id}\n<tg-emoji emoji-id="5873134015094985005">💬</tg-emoji> پیام شما: {msg}\n'
        if resp:
            text += f"↩️ پاسخ پشتیبانی: {resp}\n"
        text += f"وضعیت: {status_str}\n-------------------\n"

    await callback.message.answer(text.replace("**", "<b>", 1).replace("**", "</b>", 1), parse_mode="HTML")
    await callback.answer()


@ticket_router.message(TicketState.waiting_for_message)
async def ticket_receive_message(message: Message, state: FSMContext):
    if message.text in MAIN_MENU_TEXTS:
        await state.clear()
        return

    await state.clear()
    user = message.from_user
    msg_text = message.text

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tickets (user_id, user_name, message, status) VALUES (?, ?, ?, 'pending')",
                   (user.id, user.full_name, msg_text))
    t_id = cursor.lastrowid
    conn.commit()
    conn.close()

    admin_text = f"📩 تیکت جدید شماره #{t_id}:\n👤 نام: {user.full_name}\n🆔 آیدی: @{user.username or 'ندارد'}\n🔢 شناسه: `{user.id}`\n\n💬 متن پیام:\n{msg_text}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="پاسخ به کاربر", callback_data=f"ticket_adm_reply_{t_id}_{user.id}")]
    ])

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, admin_text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

    await message.answer(f"✅ تیکت شما با شماره پیگیری #{t_id} با موفقیت ثبت شد و به پشتیبانی ارسال گردید.", reply_markup=main_menu())


@ticket_router.callback_query(F.data.startswith("ticket_adm_reply_"))
async def admin_reply_init(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    t_id = parts[3]
    target_id = parts[4]

    await state.update_data(t_id=t_id, target_id=target_id)
    await state.set_state(TicketState.waiting_for_reply)
    await callback.message.answer(f"لطفاً پاسخ خود را برای تیکت شماره #{t_id} ارسال کنید:")
    await callback.answer()


@ticket_router.message(TicketState.waiting_for_reply)
async def admin_reply_send(message: Message, state: FSMContext):
    data = await state.get_data()
    t_id = data.get("t_id")
    target_id = data.get("target_id")
    resp_text = message.text
    await state.clear()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET response = ?, status = 'answered' WHERE id = ?", (resp_text, t_id))
    conn.commit()
    conn.close()

    try:
        await message.bot.send_message(target_id, f"📩 پاسخ پشتیبانی برای تیکت شماره #{t_id}:\n\n{resp_text}")
        await message.answer("پاسخ با موفقیت به کاربر ارسال شد و وضعیت تیکت به حالت پاسخ‌داده‌شده تغییر کرد.")
    except Exception as e:
        await message.answer(f"خطا در ارسال پیام به کاربر: {e}")
