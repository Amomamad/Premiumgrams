import sqlite3
import random
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

wheel_router = Router()

def init_wheel_db():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wheel_logs (
            user_id INTEGER PRIMARY KEY,
            last_spin TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_wheel_db()

PRIZES = [
    {"type": "balance", "amount": 1000, "label": "🎁 ۱,۰۰۰ تومان شارژ کیف‌پول", "chance": 40},
    {"type": "balance", "amount": 2000, "label": "🎁 ۲,۰۰۰ تومان شارژ کیف‌پول", "chance": 30},
    {"type": "balance", "amount": 5000, "label": "🎉 ۵,۰۰۰ تومان شارژ کیف‌پول", "chance": 15},
    {"type": "balance", "amount": 10000, "label": "🔥 ۱۰,۰۰۰ تومان شارژ کیف‌پول", "chance": 5},
    {"type": "empty", "amount": 0, "label": "❌ پوچ! شانس مجدد فردا", "chance": 10},
]

@wheel_router.message(F.text == "🎰 گردونه شانس")
async def show_wheel(message: Message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT last_spin FROM wheel_logs WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    can_spin = True
    if row and row[0]:
        last_spin_time = datetime.fromisoformat(row[0])
        if datetime.now() - last_spin_time < timedelta(hours=24):
            can_spin = False
            remaining = timedelta(hours=24) - (datetime.now() - last_spin_time)
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            wait_msg = f"<tg-emoji emoji-id=\"5197269100878907942\">✍️</tg-emoji> شما قبلاً گردونه را چرخانده‌اید.\nزمان باقی‌مانده تا شانس بعدی: <b>{hours} ساعت و {minutes} دقیقه</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="چرخاندن گردونه!", callback_data="spin_wheel", style="success", icon_custom_emoji_id="5310278924616356636")]
    ]) if can_spin else None

    text = "<tg-emoji emoji-id=\"5407064810040864883\">🎈</tg-emoji> <b>گردونه شانس روزانه</b>\n\nهر ۲۴ ساعت یک‌بار شانس خود را امتحان کنید و شارژ رایگان کیف‌پول برنده شوید!"
    if not can_spin:
        text += f"\n\n{wait_msg}"

    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@wheel_router.callback_query(F.data == "spin_wheel")
async def process_spin(call: CallbackQuery):
    user_id = call.from_user.id
    
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT last_spin FROM wheel_logs WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row and row[0]:
        last_spin_time = datetime.fromisoformat(row[0])
        if datetime.now() - last_spin_time < timedelta(hours=24):
            conn.close()
            await call.answer("❌ مهلت شانس امروز شما تمام شده است.", show_alert=True)
            return

    # انتخاب جایزه بر اساس شانس
    chances = [p["chance"] for p in PRIZES]
    selected_prize = random.choices(PRIZES, weights=chances, k=1)[0]

    # ثبت زمان چرخاندن
    now_str = datetime.now().isoformat()
    cursor.execute("INSERT OR REPLACE INTO wheel_logs (user_id, last_spin) VALUES (?, ?)", (user_id, now_str))

    # اعمال جایزه
    if selected_prize["type"] == "balance":
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (selected_prize["amount"], user_id))

    conn.commit()
    conn.close()

    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"5407064810040864883\">🎈</tg-emoji> <b>گردونه چرخید...</b>\n\nنتیجه: <b>{selected_prize['label']}</b>",
        parse_mode="HTML"
    )
    await call.answer()
