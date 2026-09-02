import sqlite3
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS

stats_router = Router()


async def send_stats(message: Message):
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at, 'unixepoch') = DATE('now')")
    today_users = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(price), 0) FROM orders WHERE status IN ('approved','fulfilled')")
    order_row = cursor.fetchone()
    total_orders = order_row[0] or 0
    total_revenue = order_row[1] or 0

    cursor.execute(
        "SELECT COUNT(*), COALESCE(SUM(price), 0) FROM orders "
        "WHERE status IN ('approved','fulfilled') AND DATE(created_at, 'unixepoch') = DATE('now')"
    )
    today_order_row = cursor.fetchone()
    today_orders = today_order_row[0] or 0
    today_revenue = today_order_row[1] or 0

    cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
    total_user_balance = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'pending'")
    open_tickets = cursor.fetchone()[0] or 0

    conn.close()

    text = (
        "📊 <b>گزارش و آمار جامع ربات</b>\n\n"
        "👥 <b>آمار کاربران:</b>\n"
        f"├ کل کاربران: <code>{total_users:,}</code> نفر\n"
        f"└ کاربران جدید امروز: <code>{today_users:,}</code> نفر\n\n"
        "💰 <b>آمار فروش و درآمد:</b>\n"
        f"├ درآمد امروز: <code>{today_revenue:,}</code> تومان ({today_orders} سفارش)\n"
        f"└ درآمد کل: <code>{total_revenue:,}</code> تومان ({total_orders} سفارش)\n\n"
        "💳 <b>موجودی کیف‌پول‌ها:</b>\n"
        f"└ مجموع شارژ کیف‌پول کاربران: <code>{total_user_balance:,}</code> تومان\n\n"
        f"📩 <b>تیکت‌های باز:</b> <code>{open_tickets}</code> عدد"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 به‌روزرسانی آمار", callback_data="refresh_stats")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@stats_router.message(F.text == "📊 آمار و گزارشات")
async def show_advanced_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await send_stats(message)


@stats_router.callback_query(F.data == "refresh_stats")
async def cb_refresh_stats(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ دسترسی غیرمجاز", show_alert=True)
        return
    await call.answer("✅ آمار به‌روزرسانی شد")
    await send_stats(call.message)


@stats_router.callback_query(F.data == "adm:advanced_stats")
async def cb_advanced_stats_from_panel(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ دسترسی غیرمجاز", show_alert=True)
        return
    await call.answer()
    await send_stats(call.message)
