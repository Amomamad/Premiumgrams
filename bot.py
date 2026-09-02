from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from admin_handlers import admin_router
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, Message,
)

import db
import keyboards as kb
from ticketing import ticket_router
from admin_stats import stats_router
from lucky_wheel import wheel_router
import crypto_verify
import marketapp
from gift_pricing import fragment_sticker_id
from config import ORDER_CHANNEL_ID

REPORT_GROUP_ID = -1004301315378

async def send_report(bot: Bot, topic_key: str, text: str, reply_markup=None):
    thread_id = db.get_text(topic_key, "")
    try:
        await bot.send_message(
            REPORT_GROUP_ID, text,
            message_thread_id=int(thread_id) if thread_id else None,
            reply_markup=reply_markup,
        )
    except Exception as e:
        log.warning("report send failed (%s): %s", topic_key, e)
import jdatetime

CATEGORY_LABELS = {
    "premium": "🌟 پرمیوم | تلگرام پرمیوم",
    "gift": "🎁 گیفت | هدیه تلگرام",
    "stars": "⭐️ استارز | استارز تلگرام",
    "reaction": "❤️ ریاکشن | ریاکشن استارزی",
    "ton": "💎 تون | ارز TON",
    "trx": "🔺 ترون | ارز TRX",
    "nft_gift": "🖼 گیفت NFT | گیفت NFT",
    "mystery": "📦 جعبه اسرارآمیز",
}

def mask_id(user_id: int) -> str:
    s = str(user_id)
    return s[:4] + "*" * max(0, len(s) - 4)

def topic_purchase_text(user_id: int, username: str, title: str, quantity, price: int) -> str:
    import datetime as _dt2
    now_utc = _dt2.datetime.utcnow()
    now_tehran = now_utc + _dt2.timedelta(hours=3, minutes=30)
    now = jdatetime.datetime.fromgregorian(datetime=now_tehran)
    time_str = now.strftime("%Y/%m/%d - %H:%M:%S")
    return (
        f"🛒 #سفارش_تکمیل_شد\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"یوزرنیم: @{username or 'ندارد'}\n"
        f"📦 محصول: {title}\n"
        f"🔢 تعداد: {quantity}\n"
        f"💰 مبلغ: {price:,} تومان\n"
        f"⏳ زمان: {time_str}"
    )


def channel_order_text(status_emoji: str, status_word: str, user_id: int, category: str, quantity, price: int) -> str:
    label = CATEGORY_LABELS.get(category, category)
    import datetime as _dt
    now_utc = _dt.datetime.utcnow()
    now_tehran = now_utc + _dt.timedelta(hours=3, minutes=30)
    now = jdatetime.datetime.fromgregorian(datetime=now_tehran)
    time_str = now.strftime("%Y/%m/%d - %H:%M:%S")
    return (
        f"{status_emoji} #سفارش ( {label} ) {status_word}\n\n"
        f"👤 ID : {mask_id(user_id)}\n"
        f"🔢 Count : {quantity}\n"
        f"⏳ Time : {time_str}\n"
        f"💰 Price : {price:,}"
    )
from config import (
    BOT_TOKEN, BOT_USERNAME, ADMIN_IDS, SUPPORT_USERNAME,
    WALLET_TRX, WALLET_TON, CARD_NUMBER, CARD_OWNER, TON_API_KEY,
    REFERRAL_PERCENT, NFT_GIFT_FEE_PERCENT,
    MIN_STARS_AMOUNT, MIN_REACTION_AMOUNT,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("shop_bot")

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def fmt_money(n: int) -> str:
    return f"{n:,} تومان"


# ---------- FSM States ----------

class Purchase(StatesGroup):
    collecting = State()


class Topup(StatesGroup):
    amount = State()
    proof = State()


class AdminEdit(StatesGroup):
    price = State()
    desc = State()


class NftPay(StatesGroup):
    proof = State()


class AdminChannel(StatesGroup):
    waiting_ch1 = State()
    waiting_ch2 = State()


class AdminUserLookup(StatesGroup):
    waiting_id = State()
    waiting_amount = State()
    waiting_message = State()


class AccountFlow(StatesGroup):
    waiting_track_id = State()


class AdminCategory(StatesGroup):
    new_input = State()
    rename = State()


class AdminNewProduct(StatesGroup):
    input = State()
    desc = State()


class AdminText(StatesGroup):
    edit = State()


TEXT_DEFAULTS = {
    "menu_buy": "<tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji> خرید محصول",
    "menu_account": "<tg-emoji emoji-id=\"5332724926216428039\">📇</tg-emoji> حساب کاربری",
    "menu_topup": "<tg-emoji emoji-id=\"5445353829304387411\">💳</tg-emoji> شارژ حساب",
    "menu_orders": "<tg-emoji emoji-id=\"5278702045883292456\"><tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji></tg-emoji> سفارش‌های من",
    "menu_referral": "🧑‍🤝‍🧑 زیرمجموعه‌گیری",
    "menu_wheel": "🎰 گردونه شانس",
    "menu_support": "☎️ پشتیبانی",
    "txt_catalog_prompt": "یکی از دسته‌بندی‌های زیر رو انتخاب کن:",
    "pay_wallet_label": "👛 کیف‌پول داخلی",
    "pay_card_label": "کارت به کارت (ریالی)",
    "pay_trx_label": "ترون (TRX)",
    "pay_ton_label": "تون (TON)",
    "txt_welcome": "سلام <tg-emoji emoji-id=\"5192959294470895031\">💐</tg-emoji> خوش اومدی به فروشگاه پرمیوم، استارز و گیفت تلگرام <tg-emoji emoji-id=\"5978808726180600960\">⭐️</tg-emoji>\n\nاز منوی پایین می‌تونی محصول بخری، حساب کاربریت رو ببینی، حسابت رو شارژ کنی یا با معرفی دوستات کسب درآمد کنی.",
    "txt_insufficient_balance": "<tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji> موجودی کیف‌پولت کافی نیست!",
    "txt_payment_prompt": "روش پرداخت رو انتخاب کن:",
    "wallet_trx": WALLET_TRX,
    "wallet_ton": WALLET_TON,
    "card_number": CARD_NUMBER,
    "card_owner": CARD_OWNER,
    "min_topup": "10000",
    "txt_price_label": "قیمت:",
}


STEP_FLOWS = {
    "premium": ["recipient", "discount", "payment", "proof"],
    "gift": ["recipient", "hide_sender", "gift_comment", "discount", "payment", "proof"],
    "stars": ["quantity_stars", "recipient", "discount", "payment", "proof"],
    "reaction": ["channel_link", "quantity_reaction", "discount", "payment", "proof"],
    "ton": ["quantity_coin", "wallet_address", "discount", "payment", "proof"],
    "trx": ["quantity_coin", "wallet_address", "discount", "payment", "proof"],
    "nft_gift": ["nft_link"],
}


# ---------- Start & General ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    payload = message.text.split(maxsplit=1)
    referred_by = None
    live_gift_address = None
    if len(payload) > 1 and payload[1].startswith("ref_"):
        try:
            referred_by = int(payload[1].split("_", 1)[1])
        except ValueError:
            referred_by = None
    elif len(payload) > 1 and payload[1].startswith("buylive_"):
        live_gift_address = payload[1].split("_", 1)[1]

    if not is_admin(message.from_user.id):
        missing = await check_forced_join(message.from_user.id, message.bot)
        if missing:
            await state.update_data(pending_ref=referred_by)
            await send_join_prompt(message, missing)
            return

    existing_user = db.get_user(message.from_user.id)
    is_new_user = db.get_user(message.from_user.id) is None
    db.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        referred_by=referred_by,
    )
    if is_new_user:
        await send_report(message.bot, "topic_access", f"👋 #ورود_جدید\n\n👤 ID: <code>{message.from_user.id}</code>\nیوزرنیم: @{message.from_user.username or 'ندارد'}")
    if existing_user is None:
        db.change_balance(message.from_user.id, 25000)
        await message.answer(
            "🎁 به‌عنوان هدیه‌ی خوش‌آمدگویی، <b>۲۵,۰۰۰ تومان</b> به کیف‌پولت اضافه شد!"
        )

    if live_gift_address:
        await start_live_gift_order(message, state, live_gift_address, message.from_user.id, message.from_user.username or "")
        return
    menu = kb.admin_extra_button() if is_admin(message.from_user.id) else kb.main_menu()
    await message.answer(db.get_text("txt_welcome", TEXT_DEFAULTS["txt_welcome"]), reply_markup=menu)




@router.message(lambda m: m.text == db.get_text("menu_account", "<tg-emoji emoji-id=\"5332724926216428039\">📇</tg-emoji> حساب کاربری"))
async def account(message: Message):
    user = db.get_or_create_user(message.from_user.id, message.from_user.username or "")
    orders_count = len(db.list_orders(user_id=message.from_user.id, limit=1000))
    refs = db.count_referrals(message.from_user.id)
    level = db.purchase_level(message.from_user.id)
    spent = db.total_spent(message.from_user.id)

    acc_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 چالش روزانه", callback_data="acc_challenge", style="success")],
        [InlineKeyboardButton(text="📦 سفارش‌های اخیر من", callback_data="acc_recent_orders", style="primary")],
        [InlineKeyboardButton(text="🔍 پیگیری سفارش", callback_data="acc_track_order", style="primary")],
    ])

    await message.answer(
        f"<tg-emoji emoji-id=\"5433758796289685818\">👤</tg-emoji> <b>حساب کاربری شما</b>\n\n"
        f"<tg-emoji emoji-id=\"5257960214291823402\">🆔</tg-emoji> آیدی عددی: <code>{message.from_user.id}</code>\n"
        f"👤 یوزرنیم: @{message.from_user.username or 'ندارد'}\n"
        f"<tg-emoji emoji-id=\"5224257782013769471\">💰</tg-emoji> موجودی کیف‌پول: <b>{fmt_money(user['balance'])}</b>\n"
        f"<tg-emoji emoji-id=\"5197434882321567830\">📦</tg-emoji> تعداد سفارش‌ها: {orders_count}\n"
        f"<tg-emoji emoji-id=\"5449816553727998023\">🧑‍🤝‍🧑</tg-emoji> تعداد زیرمجموعه‌ها: {refs}\n"
        f"🏅 سطح خرید: <b>{level}</b> (مجموع خرید: {fmt_money(spent)})\n",
        reply_markup=acc_kb,
    )


@router.message(lambda m: m.text == db.get_text("menu_referral", "🧑‍🤝‍🧑 زیرمجموعه‌گیری"))
async def referral(message: Message):
    refs = db.count_referrals(message.from_user.id)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"
    ref_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 رده‌بندی برترین‌ها", callback_data="ref_leaderboard", style="primary")],
        [InlineKeyboardButton(text="🖼 دریافت بنر تبلیغاتی", callback_data="ref_banner", style="success")],
    ])
    await message.answer(
        f"<tg-emoji emoji-id=\"5449816553727998023\">🧑‍🤝‍🧑</tg-emoji> <b>سیستم زیرمجموعه‌گیری</b>\n\n"
        f"لینک اختصاصی خودت رو برای دوستات بفرست. با هر شارژ حسابی که زیرمجموعه‌ت انجام بده، "
        f"<b>{REFERRAL_PERCENT}٪</b> از مبلغ شارژ مستقیم به کیف‌پول خودت اضافه می‌شه!\n\n"
        f"<tg-emoji emoji-id=\"5257980374868311346\">💌</tg-emoji> لینک دعوت شما:\n<code>{link}</code>\n\n"
        f"<tg-emoji emoji-id=\"5257960214291823402\">👥</tg-emoji> تعداد زیرمجموعه‌های فعلی: {refs}",
        reply_markup=ref_kb,
    )


@router.callback_query(F.data == "ref_leaderboard")
async def ref_leaderboard(callback: CallbackQuery):
    top = db.top_referrers(10)
    if not top:
        await callback.answer("هنوز کسی زیرمجموعه نگرفته.", show_alert=True)
        return
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    palette = ["primary", "success", "danger"]
    rows = []
    for i, u in enumerate(top):
        lvl = db.purchase_level(u["user_id"])
        uname = f"@{u['username']}" if u["username"] else f"کاربر {u['user_id']}"
        label = f"\u200f{medals[i]} {uname}  •  \u200f👥 {u['count']} زیرمجموعه  •  \u200f🏅 سطح {lvl}"
        rows.append([InlineKeyboardButton(text=label, callback_data="noop", style=palette[i % 3])])
    await callback.message.answer("🏆 <b>برترین زیرمجموعه‌گیرها</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "ref_banner")
async def ref_banner(callback: CallbackQuery):
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{callback.from_user.id}"
    banner_text = (
        "🌟 <b>فروشگاه پرمیوم، استارز و گیفت تلگرام</b> 🌟\n\n"
        "✅ تحویل سریع و مطمئن\n"
        "✅ پرداخت ریالی و ارزی (TON/TRX)\n"
        "✅ پشتیبانی ۲۴ ساعته\n"
        "✅ گیفت، استارز، پرمیوم و ری‌اکشن با بهترین قیمت\n\n"
        f"👇 همین الان بزن و شروع کن:\n{link}"
    )
    await callback.message.answer(banner_text)
    await callback.answer()


@router.message(lambda m: m.text == db.get_text("menu_orders", "<tg-emoji emoji-id=\"5278702045883292456\"><tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji></tg-emoji> سفارش‌های من"))
async def my_orders(message: Message):
    orders = db.list_orders(user_id=message.from_user.id, limit=10)
    if not orders:
        await message.answer("هنوز سفارشی ثبت نکردی.")
        return

    status_titles = {
        "pending": "<tg-emoji emoji-id=\"5875338604628152304\">🟡</tg-emoji> در انتظار بررسی/پرداخت",
        "approved": "<tg-emoji emoji-id=\"5872801180899348885\">🟢</tg-emoji> پرداخت تایید شد (در حال انجام)",
        "fulfilled": "<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> تحویل داده شد",
        "rejected": "<tg-emoji emoji-id=\"5875208759176860365\">🔴</tg-emoji> رد شده",
        "pending_price": "<tg-emoji emoji-id=\"5875338604628152304\">🟡</tg-emoji> در انتظار تعیین قیمت توسط ادمین",
    }

    lines = ["<tg-emoji emoji-id=\"5278702045883292456\"><tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji></tg-emoji> <b>۱۰ سفارش اخیر شما:</b>\n"]
    for o in orders:
        lines.append(
            f"<b>#{o['id']}</b> — {o['title']}\n"
            f"وضعیت: {status_titles.get(o['status'], o['status'])}\n"
            f"مبلغ: {fmt_money(o['price'])}\n"
        )
    await message.answer("\n".join(lines))


# ---------- شارژ حساب ----------

@router.message(lambda m: m.text == db.get_text("menu_topup", "<tg-emoji emoji-id=\"5445353829304387411\">💳</tg-emoji> شارژ حساب"))
async def topup_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("روش پرداخت رو انتخاب کن:", reply_markup=kb.topup_method_kb())


@router.message(Topup.amount)
async def topup_amount(message: Message, state: FSMContext):
    if await try_menu_nav(message, state):
        return
    text = (message.text or "").strip().replace(",", "")
    min_topup = int(db.get_text("min_topup", "10000"))
    if not text.isdigit() or int(text) < min_topup:
        await message.answer(f"مبلغ نامعتبره. حداقل مبلغ {min_topup:,} تومان هست. دوباره بفرست:")
        return

    WALLET_TRX = db.get_text("wallet_trx", TEXT_DEFAULTS["wallet_trx"])
    WALLET_TON = db.get_text("wallet_ton", TEXT_DEFAULTS["wallet_ton"])
    CARD_NUMBER = db.get_text("card_number", TEXT_DEFAULTS["card_number"])
    CARD_OWNER = db.get_text("card_owner", TEXT_DEFAULTS["card_owner"])
    amount = int(text)
    await state.update_data(amount=amount)
    data = await state.get_data()
    method = data.get("method", "card")

    if method == "card":
        await state.set_state(Topup.proof)
        await message.answer(
            "<tg-emoji emoji-id=\"5443127283898405358\">💳</tg-emoji> مبلغ رو به کارت زیر واریز کن:\n\n"
            f"<code>{CARD_NUMBER}</code>\n"
            f"به نام: <b>{CARD_OWNER}</b>\n\n"
            "بعد از واریز، عکس رسید یا شماره پیگیری رو همین‌جا بفرست."
        )
        return

    if method == "trx":
        price = crypto_verify.get_bitpin_price("TRX_IRT")
        if not price:
            await message.answer("<tg-emoji emoji-id=\"5812171360964714209\">🔄</tg-emoji>️ قیمت لحظه‌ای در دسترس نبود، چند لحظه دیگه دوباره امتحان کن.")
            return
        import random as _r
        crypto_amount = round(amount / price, 2) + round(_r.uniform(0.0003, 0.0099), 4)
        await state.update_data(expected_crypto_amount=crypto_amount)
        kb_check = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ واریز کردم، بررسی کن", callback_data="check_trx_topup", style="success")]])
        await message.answer(
            f"<tg-emoji emoji-id=\"4997067511137567958\">🪙</tg-emoji> <b>جزئیات فاکتور شارژ ترون (TRX)</b>\n\n"
            f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> آدرس پرداخت:\n<code>{WALLET_TRX}</code>\n\n"
            f"<tg-emoji emoji-id=\"5345804987123378599\">➕</tg-emoji> مقدار قابل پرداخت: <b>{crypto_amount} TRX</b>\n"
            f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> مبلغ کل: <b>{fmt_money(amount)}</b>\n\n"
            f"<tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> شبکه انتقال: TRC20\n\n"
            f"<tg-emoji emoji-id=\"5812171360964714209\">🔄</tg-emoji>️ حتماً دقیقاً همین مقدار اعشاری رو واریز کن (نه گرد شده).\n\n"
            f"بعد از واریز، فقط دکمه زیر رو بزن:",
            reply_markup=kb_check,
        )
        return

    import random, string
    ton_memo = "TOP" + "".join(random.choices(string.digits, k=6))
    await state.update_data(ton_memo=ton_memo)
    price = crypto_verify.get_bitpin_price("GRAM_IRT")
    if not price:
        await message.answer("<tg-emoji emoji-id=\"5812171360964714209\">🔄</tg-emoji>️ قیمت لحظه‌ای در دسترس نبود، چند لحظه دیگه دوباره امتحان کن.")
        return
    crypto_amount = round(amount / price, 4)
    await state.update_data(expected_crypto_amount=crypto_amount)
    kb_check = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ واریز کردم، بررسی کن", callback_data="check_ton_topup", style="success")]])
    await message.answer(
        f"<tg-emoji emoji-id=\"5377620962390857342\">🪙</tg-emoji> <b>جزئیات فاکتور شارژ تون (TON)</b>\n\n"
        f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> آدرس پرداخت:\n<code>{WALLET_TON}</code>\n\n"
        f"<tg-emoji emoji-id=\"5345804987123378599\">➕</tg-emoji> مقدار قابل پرداخت: <b>{crypto_amount} TON</b>\n"
        f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> مبلغ کل: <b>{fmt_money(amount)}</b>\n\n"
        f"<tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> شبکه انتقال: TON\n\n"
        f"<tg-emoji emoji-id=\"5875208759176860365\"><tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji></tg-emoji> Memo/Comment (اجباری، وگرنه پولت گم می‌شه):\n<code>{ton_memo}</code>\n\n"
        f"بعد از واریز، فقط دکمه زیر رو بزن:",
        reply_markup=kb_check,
    )


@router.callback_query(F.data.startswith("topup:"))
async def topup_method(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    method = callback.data.split(":", 1)[1]
    await state.update_data(method=method)
    await state.set_state(Topup.amount)
    await callback.message.answer("چه مبلغی (به تومان) می‌خوای به کیف‌پولت اضافه کنی؟\n\nعدد رو بفرست، مثلا: <code>500000</code>")
    await callback.answer()
    return

    if method == "card":
        text = (
            f"<tg-emoji emoji-id=\"5443127283898405358\">💳</tg-emoji> مبلغ رو به کارت زیر واریز کن:\n\n"
            f"<code>{CARD_NUMBER}</code>\n"
            f"به نام: <b>{CARD_OWNER}</b>\n\n"
            f"بعد از واریز، عکس رسید یا شماره پیگیری رو همین‌جا بفرست."
        )
    elif method == "trx":
        price = crypto_verify.get_bitpin_price("TRX_IRT")
        if not price:
            await callback.message.answer("<tg-emoji emoji-id=\"5812171360964714209\">🔄</tg-emoji>️ قیمت لحظه‌ای در دسترس نبود، چند لحظه دیگه دوباره امتحان کن.")
            await callback.answer()
            return
        import random as _r
        crypto_amount = round(amount / price, 2) + round(_r.uniform(0.0003, 0.0099), 4)
        await state.update_data(expected_crypto_amount=crypto_amount)
        kb_check = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ واریز کردم، بررسی کن", callback_data="check_trx_topup", style="success")]])
        await callback.message.answer(
            f"<tg-emoji emoji-id=\"4997067511137567958\">🪙</tg-emoji> <b>شارژ با ترون (TRX)</b>\n\n"
            f"مبلغ: <b>{fmt_money(amount)}</b>\n\n"
            f"<tg-emoji emoji-id=\"5345804987123378599\">➕</tg-emoji> دقیقاً این مقدار رو واریز کن: <b>{crypto_amount} TRX</b>\n"
            f"(عدد اعشاری دقیق مهمه، این‌جوری بدون نیاز به Memo شناسایی می‌شه)\n\n"
            f"آدرس کیف‌پول:\n<code>{WALLET_TRX}</code>\n\n"
            f"بعد از واریز، دکمه زیر رو بزن:",
            reply_markup=kb_check,
        )
        await callback.answer()
        return
    else:
        import random, string
        ton_memo = "TOP" + "".join(random.choices(string.digits, k=6))
        await state.update_data(ton_memo=ton_memo)
        price = crypto_verify.get_bitpin_price("GRAM_IRT")
        if price:
            crypto_amount = round(amount / price, 4)
            await state.update_data(expected_crypto_amount=crypto_amount)
            amount_line = f"مقدار قابل واریز: <b>{crypto_amount} TON</b>\n\n"
        else:
            amount_line = "<tg-emoji emoji-id=\"5812171360964714209\">🔄</tg-emoji>️ قیمت لحظه‌ای در دسترس نبود، از سایت صرافی معادلش رو حساب کن.\n\n"
        kb_check = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ واریز کردم، بررسی کن", callback_data="check_ton_topup", style="success")]])
        await callback.message.answer(
            f"<tg-emoji emoji-id=\"5377620962390857342\">🪙</tg-emoji> <b>شارژ با تون (TON)</b>\n\n"
            f"مبلغ: <b>{fmt_money(amount)}</b>\n\n"
            f"{amount_line}"
            f"آدرس کیف‌پول:\n<code>{WALLET_TON}</code>\n\n"
            f"<tg-emoji emoji-id=\"5875208759176860365\"><tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji></tg-emoji><tg-emoji emoji-id=\"5875208759176860365\"><tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji></tg-emoji> Memo/Tag رو دقیقاً همین بفرست، وگرنه پولت گم می‌شه و قابل برگشت نیست:\n<code>{ton_memo}</code>\n\n"
            f"بعد از واریز، دکمه زیر رو بزن (نیازی به فرستادن هش نیست):",
            reply_markup=kb_check,
        )
        await callback.answer()
        return

    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "check_trx_topup")
async def check_trx_topup(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount", 0)
    expected_amount = data.get("expected_crypto_amount")
    await callback.answer("در حال بررسی...")
    tx_ref = await asyncio.to_thread(crypto_verify.find_trx_payment, WALLET_TRX, expected_amount)
    if not tx_ref:
        await callback.message.answer("هنوز واریزی پیدا نشد. چند دقیقه صبر کن و دوباره دکمه رو بزن.")
        return
    if is_tx_used(tx_ref):
        await callback.message.answer("این تراکنش قبلاً استفاده شده.")
        return

    topup_id = db.create_topup(user_id=callback.from_user.id, username=callback.from_user.username or "", amount=amount, method="trx", proof=tx_ref)
    db.update_topup(topup_id, status="approved")
    db.change_balance(callback.from_user.id, amount)
    user = db.get_user(callback.from_user.id)
    if user and user.get("referred_by"):
        reward = int(amount * REFERRAL_PERCENT / 100)
        if reward > 0:
            db.change_balance(user["referred_by"], reward)
            try:
                await bot.send_message(user["referred_by"], f"🎁 زیرمجموعه‌ات شارژ کرد و {fmt_money(reward)} پورسانت گرفتی!")
            except Exception: pass
    await state.clear()
    await callback.message.answer(f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> تراکنش تایید شد و {fmt_money(amount)} به کیف‌پولت اضافه شد!")


@router.callback_query(F.data == "check_ton_topup")
async def check_ton_topup(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount", 0)
    expected_amount = data.get("expected_crypto_amount")
    ton_memo = data.get("ton_memo", "")
    await callback.answer("در حال بررسی...")
    tx_ref = await asyncio.to_thread(crypto_verify.verify_ton_payment, WALLET_TON, expected_amount, TON_API_KEY, ton_memo)
    if not tx_ref:
        await callback.message.answer("هنوز واریزی پیدا نشد. چند دقیقه صبر کن و دوباره دکمه رو بزن.")
        return
    if is_tx_used(tx_ref):
        await callback.message.answer("این تراکنش قبلاً استفاده شده.")
        return

    topup_id = db.create_topup(user_id=callback.from_user.id, username=callback.from_user.username or "", amount=amount, method="ton", proof=tx_ref)
    db.update_topup(topup_id, status="approved")
    db.change_balance(callback.from_user.id, amount)
    user = db.get_user(callback.from_user.id)
    if user and user.get("referred_by"):
        reward = int(amount * REFERRAL_PERCENT / 100)
        if reward > 0:
            db.change_balance(user["referred_by"], reward)
            try:
                await bot.send_message(user["referred_by"], f"🎁 زیرمجموعه‌ات شارژ کرد و {fmt_money(reward)} پورسانت گرفتی!")
            except Exception: pass
    await state.clear()
    await callback.message.answer(f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> تراکنش تایید شد و {fmt_money(amount)} به کیف‌پولت اضافه شد!")


@router.message(Topup.proof, F.photo | F.text)
async def topup_proof(message: Message, state: FSMContext, bot: Bot):
    if await try_menu_nav(message, state):
        return
    data = await state.get_data()
    method = data.get("method", "card")
    amount = data.get("amount", 0)
    text = (message.text or "").strip()

    if method == "card" and not message.photo:
        await message.answer("برای پرداخت ریالی فقط عکس رسید قبوله. عکسشو بفرست:")
        return

    auto_verified = False
    if method in ("trx", "ton") and not message.photo:
        _persian_digits = set("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩")
        _has_fa_letter = any("\u0600" <= ch <= "\u06FF" and ch not in _persian_digits for ch in text)
        _has_fa_digit = any(ch in _persian_digits for ch in text)
        _has_en_letter = any(ch.isascii() and ch.isalpha() for ch in text)
        _valid = len(text) >= 10 and not _has_fa_letter and (not _has_fa_digit or _has_en_letter)
        if not _valid:
            await message.answer("رسید نامعتبره. هش تراکنش (فقط حروف/اعداد انگلیسی، بیشتر از ۱۰ کاراکتر) یا عکس رسید رو بفرست:")
            return
        expected_amount = data.get("expected_crypto_amount")
        if expected_amount:
            if method == "trx":
                if is_tx_used(text):
                    await message.answer("این تراکنش قبلاً استفاده شده. هش تراکنش جدید بفرست:")
                    return
                await message.answer("⏳ در حال بررسی تراکنش رو بلاکچین...")
                is_real = await asyncio.to_thread(crypto_verify.verify_trx_payment, text, WALLET_TRX, expected_amount)
                tx_ref = text if is_real else None
            else:
                ton_memo = data.get("ton_memo", "")
                await message.answer("⏳ در حال بررسی تراکنش رو بلاکچین...")
                tx_ref = await asyncio.to_thread(crypto_verify.verify_ton_payment, WALLET_TON, expected_amount, TON_API_KEY, ton_memo)
                if tx_ref and is_tx_used(tx_ref):
                    await message.answer("این تراکنش قبلاً استفاده شده. یه واریزی جدید انجام بده:")
                    return
            if not tx_ref:
                await message.answer("این هش تراکنش پیدا نشد یا با مبلغ مطابقت نداره. دوباره بررسی کن، یا عکس رسید بفرست:")
                return
            auto_verified = True

    proof = message.photo[-1].file_id if message.photo else text

    topup_id = db.create_topup(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        amount=amount,
        method=method,
        proof=proof,
    )

    if auto_verified:
        db.update_topup(topup_id, status="approved")
        db.change_balance(message.from_user.id, amount)
        user = db.get_user(message.from_user.id)
        if user and user.get("referred_by"):
            reward = int(amount * REFERRAL_PERCENT / 100)
            if reward > 0:
                db.change_balance(user["referred_by"], reward)
                try:
                    await bot.send_message(user["referred_by"], f"🎁 زیرمجموعه‌ات شارژ کرد و {fmt_money(reward)} پورسانت گرفتی!")
                except Exception: pass
        await state.clear()
        import datetime as _dt_topup
        now_str_t = (_dt_topup.datetime.utcnow() + _dt_topup.timedelta(hours=3, minutes=30)).strftime("%Y/%m/%d - %H:%M")
        new_balance = db.get_user(message.from_user.id)["balance"]
        await message.answer(
            f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> <b>شارژ حساب با موفقیت انجام شد!</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"🆔 شماره تراکنش: <b>#{topup_id}</b>\n"
            f"💳 روش پرداخت: {method}\n"
            f"💰 مبلغ شارژ: <b>{fmt_money(amount)}</b>\n"
            f"📅 تاریخ: {now_str_t}\n"
            f"📌 وضعیت: 🟢 تایید خودکار\n"
            f"👛 موجودی جدید: <b>{fmt_money(new_balance)}</b>\n"
            f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"می‌تونی همین الان خریدتو انجام بدی 🛍"
        )
        return

    await state.clear()
    import datetime as _dt_topup2
    now_str_t2 = (_dt_topup2.datetime.utcnow() + _dt_topup2.timedelta(hours=3, minutes=30)).strftime("%Y/%m/%d - %H:%M")
    await message.answer(
        f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> <b>درخواست شارژ حساب ثبت شد!</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🆔 شماره درخواست: <b>#{topup_id}</b>\n"
        f"💳 روش پرداخت: {method}\n"
        f"💰 مبلغ: <b>{fmt_money(amount)}</b>\n"
        f"📅 تاریخ: {now_str_t2}\n"
        f"📌 وضعیت: 🟡 در انتظار بررسی ادمین\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"به محض تایید، موجودی کیف‌پولت به‌روزرسانی می‌شه."
    )

    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> <b>درخواست شارژ جدید #{topup_id}</b>\n\n"
                f"کاربر: {message.from_user.id} (@{message.from_user.username or 'ندارد'})\n"
                f"مبلغ: {fmt_money(amount)}\n"
                f"روش: {method}"
            )
            if message.photo:
                await bot.send_photo(
                    admin_id, proof, caption=caption,
                    reply_markup=kb.admin_topup_actions_kb(topup_id),
                )
            else:
                await bot.send_message(
                    admin_id, f"{caption}\nرسید: {proof}",
                    reply_markup=kb.admin_topup_actions_kb(topup_id),
                )
        except Exception as e:
            log.warning("failed to notify admin %s: %s", admin_id, e)


# ---------- کاتالوگ و خرید ----------

@router.message(lambda m: m.text == db.get_text("menu_buy", "<tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji> خرید محصول"))
async def catalog(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(db.get_text("txt_catalog_prompt", "یکی از دسته‌بندی‌های زیر رو انتخاب کن:"), reply_markup=kb.catalog_categories_kb(db.list_categories()))


@router.callback_query(F.data == "back_categories")
async def back_categories(callback: CallbackQuery):
    await callback.message.edit_text(db.get_text("txt_catalog_prompt", "یکی از دسته‌بندی‌های زیر رو انتخاب کن:"), reply_markup=kb.catalog_categories_kb(db.list_categories()))
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def choose_category(callback: CallbackQuery):
    category = callback.data.split(":", 1)[1]
    products = db.list_products(category=category)
    if not products:
        await callback.answer("فعلا محصولی تو این دسته فعال نیست.", show_alert=True)
        return

    cat_obj = db.get_category(category)
    cat_title = cat_obj["title"] if cat_obj else category
    cat_desc = (cat_obj.get("description") or "").strip() if cat_obj else ""
    desc_line = f"\n{cat_desc}\n" if cat_desc else ""
    await callback.message.edit_text(
        f"<b>{cat_title}</b>\n{desc_line}\nمحصول مورد نظرت رو انتخاب کن:",
        reply_markup=kb.products_kb(products),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod:"))
async def choose_product(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    product = db.get_product(key)
    if not product:
        await callback.answer("محصول پیدا نشد.", show_alert=True)
        return

    flow = STEP_FLOWS.get(product["category"], ["recipient", "discount", "payment", "proof"])

    await state.update_data(
        category=product["category"],
        product_key=key,
        title=product["title"],
        unit_price=product["price"],
        steps=list(flow),
        step_idx=0,
        quantity=1,
        recipient=None,
        discount_code=None,
        discount_percent=0,
        extra={},
        buyer_id=callback.from_user.id,
        buyer_username=callback.from_user.username or "",
    )

    price_label = db.get_text("txt_price_label", "قیمت:")
    price_line = f"\n\n<tg-emoji emoji-id=\"5429651785352501917\">💰</tg-emoji> {price_label} <b>{product['price']:,} تومان</b>" if product['price'] > 0 else ""
    await callback.message.answer(f"<tg-emoji emoji-id=\"5444856076954520455\">📋</tg-emoji> <b>{product['title']}</b>\n\n{product['description']}{price_line}")
    await advance_step(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "step_back")
async def step_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    data = await state.get_data()
    if "step_idx" not in data or "steps" not in data:
        await callback.answer()
        return
    idx = data["step_idx"]
    if idx <= 0:
        await state.clear()
        await catalog(callback.message, state)
        await callback.answer()
        return
    await state.update_data(step_idx=idx - 1)
    await state.set_state(None)
    await advance_step(callback.message, state)
    await callback.answer()


async def advance_step(message: Message, state: FSMContext):
    WALLET_TRX = db.get_text("wallet_trx", TEXT_DEFAULTS["wallet_trx"])
    WALLET_TON = db.get_text("wallet_ton", TEXT_DEFAULTS["wallet_ton"])
    CARD_NUMBER = db.get_text("card_number", TEXT_DEFAULTS["card_number"])
    CARD_OWNER = db.get_text("card_owner", TEXT_DEFAULTS["card_owner"])
    data = await state.get_data()
    steps = data["steps"]
    idx = data["step_idx"]

    if idx >= len(steps):
        await finalize_order(message, state)
        return

    step = steps[idx]

    if step == "recipient":
        await state.set_state(None)
        await message.answer("این محصول رو برای خودت می‌خوای یا هدیه به شخص دیگه؟", reply_markup=kb.recipient_choice_kb())
    elif step == "hide_sender":
        await state.set_state(None)
        kb_hs = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="بله، مخفی باشه", callback_data="hide_sender:yes", style="primary")],
            [InlineKeyboardButton(text="نه، لازم نیست", callback_data="hide_sender:no", style="primary")],
        ])
        await message.answer("می‌خوای فرستنده‌ی این هدیه مخفی بمونه؟", reply_markup=kb_hs)
    elif step == "gift_comment":
        await state.set_state(Purchase.collecting)
        await state.update_data(_awaiting="gift_comment")
        kb_skip = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="رد کن", callback_data="skip_gift_comment", style="danger")]])
        await message.answer("می‌خوای یه پیام/کامنت همراه هدیه بفرستی؟ متنشو بنویس، یا رد کن:", reply_markup=kb_skip)

    elif step == "quantity_stars":
        await state.set_state(Purchase.collecting)
        await message.answer(f"تعداد استارز مورد نظرت رو بفرست (حداقل {MIN_STARS_AMOUNT} عدد):")

    elif step == "channel_link":
        await state.set_state(Purchase.collecting)
        await message.answer("لینک عمومی پست کانال رو بفرست (مثلا https://t.me/example/123):")

    elif step == "quantity_reaction":
        await state.set_state(Purchase.collecting)
        await message.answer(f"تعداد ری‌اکشن استارزی مورد نظرت رو بفرست (حداقل {MIN_REACTION_AMOUNT} عدد):")

    elif step == "quantity_coin":
        await state.set_state(Purchase.collecting)
        unit = "TON" if data["category"] == "ton" else "TRX"
        await message.answer(f"مقدار {unit} مورد نظرت رو بفرست (مثلا 2.5):")

    elif step == "wallet_address":
        await state.set_state(Purchase.collecting)
        await message.answer(
            "آدرس کیف‌پول مقصد رو بفرست:\n\n"
            "<tg-emoji emoji-id=\"5812171360964714209\">🔄</tg-emoji>️ اگه کیف‌پولت (مثلاً صرافی) نیاز به Memo/Tag داره، حتماً اونو هم همراه آدرس بفرست، "
            "وگرنه امکان داره واریز به دستت نرسه."
        )

    elif step == "nft_link":
        await state.set_state(Purchase.collecting)
        await message.answer("لینک گیفت NFT مورد نظرت رو بفرست تا قیمتش رو بررسی و اعلام کنیم:")

    elif step == "discount":
        await state.set_state(None)
        await message.answer("کد تخفیف داری؟", reply_markup=kb.discount_choice_kb())

    elif step == "payment":
        await state.set_state(None)
        total = compute_total(data)
        await message.answer(
            f"<tg-emoji emoji-id=\"5197434882321567830\">💵</tg-emoji> مبلغ قابل پرداخت: <b>{fmt_money(total)}</b>\n\nروش پرداخت رو انتخاب کن:",
            reply_markup=kb.payment_method_kb(),
        )

    elif step == "proof":
        pm = data.get("payment_method")
        if pm == "wallet":
            await finalize_order(message, state)
            return

        total = compute_total(data)
        await state.set_state(Purchase.collecting)
        if pm == "card":
            txt = (
                f"<tg-emoji emoji-id=\"5445353829304387411\">💳</tg-emoji> مبلغ رو به کارت زیر واریز کن و عکس رسید رو همین‌جا بفرست:\n\n"
                f"<code>{CARD_NUMBER}</code>\n"
                f"به نام: <b>{CARD_OWNER}</b>"
            )
        elif pm == "trx":
            price = crypto_verify.get_bitpin_price("TRX_IRT")
            if not price:
                await message.answer("<tg-emoji emoji-id=\"5812171360964714209\">🔄</tg-emoji>️ قیمت لحظه‌ای در دسترس نبود، چند لحظه دیگه دوباره امتحان کن.")
                return
            import random as _r
            crypto_amount = round(total / price, 2) + round(_r.uniform(0.0003, 0.0099), 4)
            await state.update_data(expected_crypto_amount=crypto_amount)
            kb_check = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ واریز کردم، بررسی کن", callback_data="check_trx_purchase", style="success")]])
            await message.answer(
                f"<tg-emoji emoji-id=\"4997067511137567958\">🪙</tg-emoji> <b>جزئیات فاکتور پرداخت ترون (TRX)</b>\n\n"
                f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> آدرس پرداخت:\n<code>{WALLET_TRX}</code>\n\n"
                f"<tg-emoji emoji-id=\"5345804987123378599\">➕</tg-emoji> مقدار قابل پرداخت: <b>{crypto_amount} TRX</b>\n"
                f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> مبلغ کل: <b>{fmt_money(total)}</b>\n\n"
                f"<tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> شبکه انتقال: TRC20\n\n"
                f"<tg-emoji emoji-id=\"5812171360964714209\">🔄</tg-emoji>️ حتماً دقیقاً همین مقدار اعشاری رو واریز کن (نه گرد شده)، این‌جوری بدون نیاز به Memo شناسایی می‌شه.\n\n"
                f"بعد از واریز، فقط دکمه زیر رو بزن:",
                reply_markup=kb_check,
            )
            return
        else:
            import random, string
            ton_memo = "ORD" + "".join(random.choices(string.digits, k=6))
            await state.update_data(ton_memo=ton_memo)
            price = crypto_verify.get_bitpin_price("GRAM_IRT")
            if price:
                crypto_amount = round(total / price, 4)
                await state.update_data(expected_crypto_amount=crypto_amount)
                amount_line = f"مقدار قابل واریز: <b>{crypto_amount} TON</b>\n\n"
            else:
                amount_line = "<tg-emoji emoji-id=\"5812171360964714209\">🔄</tg-emoji>️ قیمت لحظه‌ای در دسترس نبود، لطفاً از سایت صرافی معادلش رو محاسبه کن.\n\n"
            kb_check = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ واریز کردم، بررسی کن", callback_data="check_ton_purchase", style="success")]])
            await message.answer(
                f"<tg-emoji emoji-id=\"5377620962390857342\">🪙</tg-emoji> <b>جزئیات فاکتور پرداخت تون (TON)</b>\n\n"
                f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> آدرس پرداخت:\n<code>{WALLET_TON}</code>\n\n"
                f"<tg-emoji emoji-id=\"5345804987123378599\">➕</tg-emoji> مقدار قابل پرداخت: <b>{crypto_amount} TON</b>\n"
                f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> مبلغ کل: <b>{fmt_money(total)}</b>\n\n"
                f"<tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> شبکه انتقال: TON\n\n"
                f"<tg-emoji emoji-id=\"5875208759176860365\"><tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji></tg-emoji> Memo/Comment (اجباری، وگرنه پولت گم می‌شه):\n<code>{ton_memo}</code>\n\n"
                f"بعد از واریز، فقط دکمه زیر رو بزن:",
                reply_markup=kb_check,
            )
            return
        await message.answer(txt)


def compute_total(data: dict) -> int:
    unit_price = data.get("unit_price", 0)
    qty = data.get("quantity", 1)
    base = int(unit_price * qty)
    percent = data.get("discount_percent", 0)
    if percent > 0:
        base = int(base * (100 - percent) / 100)
    return max(0, base)


@router.callback_query(F.data.startswith("recipient:"))
async def recipient_choice(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    data = await state.get_data()
    if "steps" not in data or data.get("step_idx", -1) >= len(data.get("steps", [])) or data["steps"][data["step_idx"]] != "recipient":
        await callback.answer("این دکمه منقضی شده، از «خرید محصول» دوباره شروع کن.", show_alert=True)
        return
    choice = callback.data.split(":", 1)[1]

    if choice == "self":
        username = callback.from_user.username
        rec = f"@{username}" if username else str(callback.from_user.id)
        await state.update_data(recipient=rec, step_idx=data["step_idx"] + 1)
        await advance_step(callback.message, state)
    else:
        await state.set_state(Purchase.collecting)
        await state.update_data(_awaiting="recipient_username")
        await callback.message.answer("یوزرنیم شخص مورد نظر رو با @ بفرست (مثلا @username):")

    await callback.answer()


@router.callback_query(F.data.startswith("hide_sender:"))
async def hide_sender_choice(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    choice = callback.data.split(":", 1)[1]
    data = await state.get_data()
    extra = data.get("extra") or {}
    extra["hide_sender"] = (choice == "yes")
    await state.update_data(extra=extra, step_idx=data["step_idx"] + 1)
    await advance_step(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "skip_gift_comment")
async def skip_gift_comment(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    data = await state.get_data()
    await state.update_data(_awaiting=None, step_idx=data["step_idx"] + 1)
    await advance_step(callback.message, state)
    await callback.answer()


@router.callback_query(F.data.startswith("discount:"))
async def discount_choice(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    data = await state.get_data()
    if "steps" not in data or data.get("step_idx", -1) >= len(data.get("steps", [])) or data["steps"][data["step_idx"]] != "discount":
        await callback.answer("این دکمه منقضی شده، از «خرید محصول» دوباره شروع کن.", show_alert=True)
        return
    choice = callback.data.split(":", 1)[1]

    if choice == "no":
        await state.update_data(discount_code=None, discount_percent=0, step_idx=data["step_idx"] + 1)
        await advance_step(callback.message, state)
    else:
        await state.set_state(Purchase.collecting)
        await state.update_data(_awaiting="discount_code")
        await callback.message.answer("کد تخفیف رو بفرست:")

    await callback.answer()


@router.callback_query(F.data.startswith("pay:"))
async def payment_choice(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    method = callback.data.split(":", 1)[1]
    data = await state.get_data()

    if "step_idx" not in data or "steps" not in data or data["step_idx"] >= len(data["steps"]) or data["steps"][data["step_idx"]] != "payment":
        await state.clear()
        await callback.message.answer(
            "<tg-emoji emoji-id=\"5812171360964714209\">🔄</tg-emoji>️ فرآیند خرید منقضی شده (شاید مدت زیادی صبر کردی). "
            "لطفاً از «<tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji> خرید محصول» دوباره شروع کن."
        )
        await callback.answer()
        return

    total = compute_total(data)

    if method == "wallet":
        user = db.get_or_create_user(callback.from_user.id, callback.from_user.username or "")
        if user["balance"] < total:
            await callback.message.answer(
                f"<tg-emoji emoji-id=\"5429518319243775957\">📉</tg-emoji> موجودی کیف‌پولت کافی نیست!\n"
                f"موجودی فعلی: {fmt_money(user['balance'])}\n"
                f"مبلغ سفارش: {fmt_money(total)}\n\n"
                f"از منوی اصلی دکمه «<tg-emoji emoji-id=\"5445353829304387411\">💳</tg-emoji> شارژ حساب» رو بزن."
            )
            await callback.answer()
            return

    await state.update_data(payment_method=method, step_idx=data["step_idx"] + 1)
    await advance_step(callback.message, state)
    await callback.answer()


def is_tx_used(ref: str) -> bool:
    import sqlite3
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS used_crypto_tx (ref TEXT PRIMARY KEY, order_id INTEGER, created_at TEXT)")
    cur.execute("SELECT 1 FROM used_crypto_tx WHERE ref = ?", (ref,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def mark_tx_used(ref: str, order_id: int = None):
    import sqlite3
    from datetime import datetime
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS used_crypto_tx (ref TEXT PRIMARY KEY, order_id INTEGER, created_at TEXT)")
    cur.execute(
        "INSERT OR IGNORE INTO used_crypto_tx (ref, order_id, created_at) VALUES (?, ?, ?)",
        (ref, order_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


LIVE_GIFTS_PAGE_SIZE = 5
LIVE_GIFTS_MARKUP = 1.15  # ۱۵٪ حاشیه سود


def diversify_gifts(items: list) -> list:
    import random
    groups = {}
    for it in items:
        base_name = it.get("name", "").split("#")[0].strip()
        groups.setdefault(base_name, []).append(it)
    for g in groups.values():
        random.shuffle(g)
    keys = list(groups.keys())
    random.shuffle(keys)
    result = []
    idx = 0
    remaining = True
    while remaining:
        remaining = False
        for k in keys:
            if idx < len(groups[k]):
                result.append(groups[k][idx])
                remaining = True
        idx += 1
    return result


async def build_live_gifts_page(page: int, tier_idx: int = 0):
    label, lo_ton, hi_ton = LIVE_GIFTS_PRICE_TIERS[tier_idx]
    raw_items = await marketapp.get_gifts_onsale()
    lo_nano = lo_ton * 1_000_000_000
    hi_nano = hi_ton * 1_000_000_000
    filtered = [it for it in raw_items if lo_nano <= int(it.get("min_bid", 0)) < hi_nano]
    items = diversify_gifts(filtered)
    price = crypto_verify.get_bitpin_price("GRAM_IRT")
    total_items = len(items)
    start = page * LIVE_GIFTS_PAGE_SIZE
    page_items = items[start:start + LIVE_GIFTS_PAGE_SIZE]
    text = f"<tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji> <b>گیفت‌های ویژه — {label}</b>\nصفحه {page + 1} — رو هرکدوم بزن برای جزئیات\n"
    if not page_items:
        text += "\nفعلاً گیفتی تو این بازه موجود نیست."
    rows = []
    for it in page_items:
        gram_amount = int(it.get("min_bid", 0)) / 1_000_000_000
        toman_price = int(gram_amount * (price or 0) * LIVE_GIFTS_MARKUP) if price else 0
        label_txt = f"{it.get('name', 'گیفت')} — {fmt_money(toman_price) if toman_price else 'نامشخص'}"
        if len(label_txt) > 60:
            label_txt = label_txt[:57] + "..."
        rows.append([InlineKeyboardButton(text=label_txt, callback_data=f"live_gift:{it['address']}:{page}:{tier_idx}", style="primary")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"live_gifts_page:{page - 1}:{tier_idx}", style="primary"))
    if start + LIVE_GIFTS_PAGE_SIZE < total_items:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"live_gifts_page:{page + 1}:{tier_idx}", style="primary"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 تغییر بازه قیمتی", callback_data="browse_live_gifts", style="danger")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows), items


LIVE_GIFTS_PRICE_TIERS = [
    ("زیر ۵ تون", 0, 5),
    ("زیر ۱۰ تون", 5, 10),
    ("زیر ۱۵ تون", 10, 15),
    ("زیر ۲۰ تون", 15, 20),
    ("۲۰ تا ۱۰۰ تون", 20, 100),
]


@router.callback_query(F.data == "browse_live_gifts")
async def browse_live_gifts(callback: CallbackQuery):
    await callback.answer()
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"live_gifts_tier:{i}", style="primary")]
        for i, (label, lo, hi) in enumerate(LIVE_GIFTS_PRICE_TIERS)
    ]
    await callback.message.answer(
        "🎁 <b>گیفت‌های ویژه</b>\nیه بازه‌ی قیمتی انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("live_gifts_tier:"))
async def browse_live_gifts_tier(callback: CallbackQuery):
    tier_idx = int(callback.data.split(":", 1)[1])
    await callback.answer()
    try:
        text, kb_, _ = await build_live_gifts_page(0, tier_idx)
    except marketapp.MarketappError as e:
        await callback.message.answer(f"⚠️ در حال حاضر امکان دریافت لیست گیفت‌ها نیست:\n{e}")
        return
    await callback.message.answer(text, reply_markup=kb_)


@router.callback_query(F.data.startswith("live_gifts_page:"))
async def live_gifts_page_nav(callback: CallbackQuery):
    _, page_str, tier_str = callback.data.split(":")
    page, tier_idx = int(page_str), int(tier_str)
    try:
        text, kb_, _ = await build_live_gifts_page(page, tier_idx)
    except marketapp.MarketappError as e:
        await callback.answer(f"خطا: {e}", show_alert=True)
        return
    await callback.message.edit_text(text, reply_markup=kb_)
    await callback.answer()


def fragment_sticker_url(name: str) -> str | None:
    if "#" not in name:
        return None
    label, num = name.rsplit("#", 1)
    slug = label.strip().lower().replace(" ", "")
    return f"https://nft.fragment.com/gift/{slug}-{num.strip()}.tgs"


def fragment_image_url(name: str) -> str | None:
    if "#" not in name:
        return None
    label, num = name.rsplit("#", 1)
    slug = label.strip().lower().replace(" ", "")
    return f"https://nft.fragment.com/gift/{slug}-{num.strip()}.large.jpg"


@router.callback_query(F.data.startswith("live_gift:"))
async def live_gift_detail(callback: CallbackQuery):
    _, nft_address, page_str, tier_str = callback.data.split(":")
    page, tier_idx = int(page_str), int(tier_str)
    try:
        items = await marketapp.get_gifts_onsale()
    except marketapp.MarketappError as e:
        await callback.answer(f"خطا: {e}", show_alert=True)
        return
    item = next((it for it in items if it.get("address") == nft_address), None)
    if not item:
        await callback.answer("این گیفت دیگه موجود نیست.", show_alert=True)
        return
    price = crypto_verify.get_bitpin_price("GRAM_IRT")
    gram_amount = int(item.get("min_bid", 0)) / 1_000_000_000
    base_toman = int(gram_amount * (price or 0)) if price else 0
    toman_price = int(base_toman * LIVE_GIFTS_MARKUP)
    attrs = "\n".join(f"• {a['trait_type']}: {a['value']}" for a in item.get("attributes", []))
    text = (
        f"🎁 <b>{item.get('name')}</b>\n\n"
        f"{attrs}\n\n"
        f"قیمت پایه: {fmt_money(base_toman)}\n"
        f"سود ما (۱۰٪): {fmt_money(toman_price - base_toman)}\n"
        f"💰 قیمت نهایی: <b>{fmt_money(toman_price) if toman_price else 'نامشخص'}</b>"
    )
    rows = [
        [InlineKeyboardButton(text="🛒 خرید", callback_data=f"buy_live_gift:{nft_address}", style="success")],
        [InlineKeyboardButton(text="🔙 برگشت به لیست", callback_data=f"live_gifts_page:{page}:{tier_idx}", style="primary")],
    ]
    kb_ = InlineKeyboardMarkup(inline_keyboard=rows)
    sticker_url = fragment_sticker_url(item.get("name", ""))
    sent_sticker = False
    if sticker_url:
        try:
            import httpx as _httpx
            from aiogram.types import BufferedInputFile
            async with _httpx.AsyncClient(timeout=8) as _client:
                resp = await _client.get(sticker_url)
            is_valid_tgs = resp.status_code == 200 and resp.content[:2] == b"\x1f\x8b"
            if is_valid_tgs:
                tgs_file = BufferedInputFile(resp.content, filename="gift.tgs")
                await callback.message.answer_sticker(sticker=tgs_file)
                sent_sticker = True
        except Exception as e:
            log.warning("failed to send gift sticker: %s", e)
            sent_sticker = False
    if not sent_sticker:
        image_url = fragment_image_url(item.get("name", ""))
        if image_url:
            try:
                await callback.message.answer_photo(photo=image_url, caption=text, reply_markup=kb_)
                await callback.answer()
                return
            except Exception:
                pass
    await callback.message.answer(text, reply_markup=kb_)
    await callback.answer()


async def start_live_gift_order(message: Message, state: FSMContext, nft_address: str, user_id: int, username: str) -> bool:
    try:
        item = await marketapp.get_nft_info(nft_address)
    except marketapp.MarketappError as e:
        await message.answer(f"⚠️ خطا: {e}")
        return False
    if not item or item.get("status") != "for_sale":
        await message.answer("این گیفت دیگه موجود نیست.")
        return False
    status_details = item.get("status_details", {})
    if status_details.get("currency") != "GRAM":
        await message.answer("این گیفت با ارز دیگه‌ای لیست شده و فعلاً پشتیبانی نمیشه.")
        return False
    price = crypto_verify.get_bitpin_price("GRAM_IRT")
    gram_amount = int(status_details.get("price", 0)) / 1_000_000_000
    toman_price = int(gram_amount * (price or 0) * LIVE_GIFTS_MARKUP) if price else 0
    if toman_price <= 0:
        await message.answer("قیمت این گیفت الان در دسترس نیست، بعداً امتحان کن.")
        return False
    await state.update_data(
        category="live_gift",
        product_key=None,
        title=f"گیفت ویژه ({nft_address[:10]}...)",
        unit_price=toman_price,
        steps=["payment", "proof"],
        step_idx=0,
        quantity=1,
        recipient=None,
        discount_code=None,
        discount_percent=0,
        extra={"nft_address": nft_address, "gift_name": item.get("name", "")},
        buyer_id=user_id,
        buyer_username=username,
    )
    await message.answer(f"🎁 در حال ثبت سفارش گیفت...")
    await advance_step(message, state)
    return True


@router.callback_query(F.data.startswith("buy_live_gift:"))
async def buy_live_gift(callback: CallbackQuery, state: FSMContext):
    nft_address = callback.data.split(":", 1)[1]
    await start_live_gift_order(callback.message, state, nft_address, callback.from_user.id, callback.from_user.username or "")
    await callback.answer()


ADMIN_COMPLETED_PAGE_SIZE = 10


def build_admin_completed_orders_page(page: int):
    total = db.count_orders(status="fulfilled")
    offset = page * ADMIN_COMPLETED_PAGE_SIZE
    orders = db.list_orders(status="fulfilled", limit=ADMIN_COMPLETED_PAGE_SIZE, offset=offset)
    text = f"📜 <b>سفارش‌های تکمیل‌شده</b>\nصفحه {page + 1} — جدیدترین اول\n"
    if not orders:
        text += "\nهنوز سفارش تکمیل‌شده‌ای نیست."
    for o in orders:
        text += f"\n✅ #{o['id']} — <code>{o['user_id']}</code> — {o['title']} — {fmt_money(o['price'])}"
    rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"adm_completed_orders:{page - 1}", style="primary"))
    if offset + ADMIN_COMPLETED_PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"adm_completed_orders:{page + 1}", style="primary"))
    if nav:
        rows.append(nav)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("adm_completed_orders:"))
async def adm_completed_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    page = int(callback.data.split(":", 1)[1])
    text, kb_ = build_admin_completed_orders_page(page)
    await callback.message.answer(text, reply_markup=kb_)
    await callback.answer()


async def try_menu_nav(message: Message, state: FSMContext) -> bool:
    """اگه پیام دقیقاً یکی از متن‌های دکمه منو باشه، ناوبری می‌کنه و True برمی‌گردونه"""
    if not message.text:
        return False
    nav_texts = {
        db.get_text("menu_buy", "<tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji> خرید محصول"): "buy",
        db.get_text("menu_account", "<tg-emoji emoji-id=\"5332724926216428039\">📇</tg-emoji> حساب کاربری"): "account",
        db.get_text("menu_topup", "<tg-emoji emoji-id=\"5445353829304387411\">💳</tg-emoji> شارژ حساب"): "topup",
        db.get_text("menu_orders", "<tg-emoji emoji-id=\"5278702045883292456\"><tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji></tg-emoji> سفارش‌های من"): "orders",
        db.get_text("menu_referral", "🧑‍🤝‍🧑 زیرمجموعه‌گیری"): "referral",
        db.get_text("menu_wheel", "🎰 گردونه شانس"): "ignore",
        db.get_text("menu_support", "☎️ پشتیبانی"): "ignore",
    }
    action = nav_texts.get(message.text)
    if not action:
        return False
    await state.clear()
    if action == "buy":
        await catalog(message, state)
    elif action == "account":
        await account(message)
    elif action == "topup":
        await topup_start(message, state)
    elif action == "orders":
        await my_orders(message)
    elif action == "referral":
        await referral(message)
    # برای wheel/support چون تو Router دیگه‌ای هندل می‌شن، فقط state رو پاک کردیم کافیه
    return True


@router.callback_query(F.data == "check_trx_purchase")
async def check_trx_purchase(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    expected_amount = data.get("expected_crypto_amount")
    await callback.answer("در حال بررسی...")
    tx_ref = await asyncio.to_thread(crypto_verify.find_trx_payment, WALLET_TRX, expected_amount)
    if not tx_ref:
        await callback.message.answer("هنوز واریزی پیدا نشد. چند دقیقه صبر کن و دوباره دکمه رو بزن.")
        return
    if is_tx_used(tx_ref):
        await callback.message.answer("این تراکنش قبلاً استفاده شده.")
        return
    await state.update_data(verified_tx_ref=tx_ref, proof=tx_ref)
    await finalize_order(callback.message, state)


@router.callback_query(F.data == "check_ton_purchase")
async def check_ton_purchase(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    expected_amount = data.get("expected_crypto_amount")
    ton_memo = data.get("ton_memo", "")
    await callback.answer("در حال بررسی...")
    tx_ref = await asyncio.to_thread(crypto_verify.verify_ton_payment, WALLET_TON, expected_amount, TON_API_KEY, ton_memo)
    if not tx_ref:
        await callback.message.answer("هنوز واریزی پیدا نشد. چند دقیقه صبر کن و دوباره دکمه رو بزن.")
        return
    if is_tx_used(tx_ref):
        await callback.message.answer("این تراکنش قبلاً استفاده شده.")
        return
    await state.update_data(verified_tx_ref=tx_ref, proof=tx_ref)
    await finalize_order(callback.message, state)


@router.message(Purchase.collecting, F.photo | F.text)
async def collecting_input(message: Message, state: FSMContext):
    if await try_menu_nav(message, state):
        return

    data = await state.get_data()
    awaiting = data.get("_awaiting")
    steps = data["steps"]
    idx = data["step_idx"]
    step = steps[idx] if idx < len(steps) else None

    text = (message.text or "").strip()

    if awaiting == "recipient_username":
        if not text.startswith("@") or len(text) < 3:
            await message.answer("یوزرنیم نامعتبره. حتما با @ شروع کن (مثلا @username):")
            return
        await state.update_data(recipient=text, _awaiting=None, step_idx=idx + 1)
        await advance_step(message, state)
        return

    if awaiting == "gift_comment":
        extra = data.get("extra") or {}
        extra["comment"] = text
        await state.update_data(extra=extra, _awaiting=None, step_idx=idx + 1)
        await advance_step(message, state)
        return
    if awaiting == "discount_code":
        disc = db.get_discount(text.upper())
        if not disc or disc["max_uses"] > 0 and disc["used_count"] >= disc["max_uses"]:
            await message.answer("کد تخفیف نامعتبر یا منقضی شده. دوباره وارد کن یا منصرف شو:")
            return
        await state.update_data(
            discount_code=disc["code"],
            discount_percent=disc["percent"],
            _awaiting=None,
            step_idx=idx + 1,
        )
        await message.answer(f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> کد تخفیف {disc['percent']}٪ اعمال شد.")
        await send_report(message.bot, "topic_purchase", f"🎫 #کد_تخفیف\n\n👤 ID: <code>{message.from_user.id}</code>\nکد: {disc['code']} ({disc['percent']}٪)")
        await advance_step(message, state)
        return

    if step == "quantity_stars":
        if not text.isdigit() or int(text) < MIN_STARS_AMOUNT:
            await message.answer(f"تعداد نامعتبره. حداقل {MIN_STARS_AMOUNT} استارز وارد کن:")
            return
        await state.update_data(quantity=int(text), step_idx=idx + 1)
        await advance_step(message, state)

    elif step == "channel_link":
        if not text.startswith("http"):
            await message.answer("لینک معتبر فرستاده نشد. دوباره بفرست:")
            return
        extra = data.get("extra", {})
        extra["channel_link"] = text
        await state.update_data(extra=extra, step_idx=idx + 1)
        await advance_step(message, state)

    elif step == "quantity_reaction":
        if not text.isdigit() or int(text) < MIN_REACTION_AMOUNT:
            await message.answer(f"تعداد نامعتبره. حداقل {MIN_REACTION_AMOUNT} ری‌اکشن وارد کن:")
            return
        await state.update_data(quantity=int(text), step_idx=idx + 1)
        await advance_step(message, state)

    elif step == "quantity_coin":
        try:
            qty = float(text)
            if qty <= 0:
                raise ValueError
        except ValueError:
            await message.answer("عدد معتبر وارد کن (مثلا 1.5):")
            return
        if data["category"] == "ton" and qty < 0.15:
            await message.answer("حداقل مقدار قابل سفارش برای TON برابر 0.15 هست. یه عدد بزرگ‌تر بفرست:")
            return
        await state.update_data(quantity=qty, step_idx=idx + 1)
        await advance_step(message, state)

    elif step == "wallet_address":
        if len(text) < 10:
            await message.answer("آدرس ولت نامعتبره. دوباره بفرست:")
            return
        await state.update_data(recipient=text, step_idx=idx + 1)
        await advance_step(message, state)

    elif step == "nft_link":
        if not text.startswith("http"):
            await message.answer("لینک نامعتبره. دوباره بفرست:")
            return
        order_id = db.create_order(
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            category="nft_gift",
            product_key="nft_gift",
            title="خرید گیفت NFT",
            recipient=None,
            quantity=1,
            price=0,
            extra={"nft_link": text},
        )
        db.update_order(order_id, status="pending_price")
        await state.clear()

        await message.answer(
            f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> درخواست شما با شماره سفارش <b>#{order_id}</b> ثبت شد.\n"
            f"ادمین لینک رو بررسی می‌کنه و قیمتش رو برات بفرستیم."
        )

        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"<tg-emoji emoji-id=\"5444856076954520455\">🖼</tg-emoji> <b>درخواست گیفت NFT جدید #{order_id}</b>\n\n"
                    f"کاربر: {message.from_user.id} (@{message.from_user.username or 'ندارد'})\n"
                    f"لینک: {text}\n\n"
                    f"جهت قیمت‌گذاری دستور زیر رو بزن:\n"
                    f"<code>/setprice_{order_id} قیمت_به_تومان</code>"
                )
            except Exception as e:
                log.warning("failed to notify admin: %s", e)

    elif step == "proof":
        if data.get("payment_method") == "card" and not message.photo:
            await message.answer("برای پرداخت ریالی فقط عکس رسید قبوله. عکسشو بفرست:")
            return
        if data.get("payment_method") in ("ton", "trx") and not message.photo:
            _persian_digits = set("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩")
            _has_fa_letter = any("\u0600" <= ch <= "\u06FF" and ch not in _persian_digits for ch in text)
            _has_fa_digit = any(ch in _persian_digits for ch in text)
            _has_en_letter = any(ch.isascii() and ch.isalpha() for ch in text)
            _valid = len(text) >= 10 and not _has_fa_letter and (not _has_fa_digit or _has_en_letter)
            if not _valid:
                await message.answer("رسید نامعتبره. هش تراکنش (فقط حروف/اعداد انگلیسی، بیشتر از ۱۰ کاراکتر) یا عکس رسید رو بفرست:")
                return
            expected_amount = data.get("expected_crypto_amount")
            if expected_amount:
                if data.get("payment_method") == "trx":
                    if is_tx_used(text):
                        await message.answer("این تراکنش قبلاً برای یه سفارش دیگه استفاده شده. هش تراکنش جدید بفرست:")
                        return
                    await message.answer("⏳ در حال بررسی تراکنش رو بلاکچین...")
                    is_real = await asyncio.to_thread(crypto_verify.verify_trx_payment, text, WALLET_TRX, expected_amount)
                    tx_ref = text if is_real else None
                else:
                    ton_memo = data.get("ton_memo", "")
                    await message.answer("⏳ در حال بررسی تراکنش رو بلاکچین...")
                    tx_ref = await asyncio.to_thread(crypto_verify.verify_ton_payment, WALLET_TON, expected_amount, TON_API_KEY, ton_memo)
                    if tx_ref and is_tx_used(tx_ref):
                        await message.answer("این تراکنش قبلاً برای یه سفارش دیگه استفاده شده. یه واریزی جدید انجام بده:")
                        return
                if not tx_ref:
                    await message.answer("این هش تراکنش پیدا نشد یا با مبلغ سفارش مطابقت نداره. دوباره بررسی کن و هش درست رو بفرست، یا عکس رسید بفرست:")
                    return
                await state.update_data(verified_tx_ref=tx_ref)
        proof = message.photo[-1].file_id if message.photo else text
        await state.update_data(proof=proof)
        await finalize_order(message, state)


def format_extra_details(extra: dict) -> str:
    if not extra:
        return ""
    lines = []
    if extra.get("channel_link"):
        lines.append(f"📢 کانال: {extra['channel_link']}")
    if extra.get("wallet_address"):
        lines.append(f"👛 آدرس ولت: <code>{extra['wallet_address']}</code>")
    if extra.get("nft_link"):
        lines.append(f"🖼 لینک گیفت: {extra['nft_link']}")
    if extra.get("nft_address"):
        lines.append(f"🖼 آدرس NFT: <code>{extra['nft_address']}</code>")
        gift_slug = fragment_sticker_id(extra.get("gift_name", ""))
        if gift_slug:
            lines.append(f"🔗 لینک گیفت: https://t.me/nft/{gift_slug}")
        else:
            lines.append(f"🔗 خرید از فرگمنت: https://fragment.com/gift/{extra['nft_address']}")
    if extra.get("hide_sender"):
        lines.append("🙈 فرستنده مخفی باشه")
    if extra.get("comment"):
        lines.append(f"💬 کامنت: {extra['comment']}")
    return "\n".join(lines)


async def finalize_order(message: Message, state: FSMContext):
    data = await state.get_data()
    total = compute_total(data)
    pm = data.get("payment_method", "wallet")

    buyer_id = data.get("buyer_id") or message.from_user.id
    buyer_username = data.get("buyer_username") or (message.from_user.username or "")

    if pm == "wallet":
        db.change_balance(buyer_id, -total)

    order_id = db.create_order(
        user_id=buyer_id,
        username=buyer_username,
        category=data["category"],
        product_key=data.get("product_key"),
        title=data["title"],
        recipient=data.get("recipient"),
        quantity=data.get("quantity", 1),
        price=total,
        discount_code=data.get("discount_code"),
        payment_method=pm,
        extra=data.get("extra"),
    )

    if data.get("discount_code"):
        db.use_discount(data["discount_code"])

    status = "approved" if pm == "wallet" else "pending"
    verified_tx_ref = data.get("verified_tx_ref")
    if verified_tx_ref and pm in ("trx", "ton"):
        status = "approved"
        mark_tx_used(verified_tx_ref, order_id)
    db.update_order(order_id, status=status)

    proof = data.get("proof")
    if proof:
        db.update_order(order_id, admin_note=f"proof: {proof}")

    await state.clear()

    import datetime as _dtinv
    now_tehran_inv = _dtinv.datetime.utcnow() + _dtinv.timedelta(hours=3, minutes=30)
    inv_time = jdatetime.datetime.fromgregorian(datetime=now_tehran_inv).strftime("%Y/%m/%d - %H:%M")
    pm_labels = {"wallet": "👛 کیف‌پول داخلی", "card": "💳 کارت به کارت", "trx": "🔺 ترون (TRX)", "ton": "💎 تون (TON)"}
    status_fa = "✅ تایید و در حال پردازش" if status == "approved" else "🟡 در انتظار بررسی"

    invoice_text = (
        f"🧾━━━━━━━━━━━━━━━━━━\n"
        f"   <b>فاکتور خرید</b> ✅\n"
        f"━━━━━━━━━━━━━━━━━━🧾\n\n"
        f"🔖 شماره سفارش: <code>#{order_id}</code>\n"
        f"📦 محصول: <b>{data['title']}</b>\n"
        f"🔢 تعداد: {data.get('quantity', 1)}\n"
        f"👤 گیرنده: {data.get('recipient') or 'خودم'}\n"
        f"{pm_labels.get(pm, pm)}\n"
        f"💰 مبلغ پرداختی: <b>{fmt_money(total)}</b>\n"
        f"📅 تاریخ: {inv_time}\n"
        f"📌 وضعیت: {status_fa}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🌟 از خرید شما متشکریم!\n"
        f"پیگیری از «🛍 سفارش‌های من»"
    )
    track_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📦 پیگیری سفارش", callback_data=f"order_detail:{order_id}:0", style="primary")]])
    await message.answer(invoice_text, reply_markup=track_kb)

    ch_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 برای خرید از ربات کلیک کن", url=f"https://t.me/{BOT_USERNAME}")]])
    if ORDER_CHANNEL_ID:
        try:
            await message.bot.send_message(ORDER_CHANNEL_ID, channel_order_text("✅", "ثبت شد", buyer_id, data["category"], data.get("quantity", 1), total), reply_markup=ch_kb)
        except Exception as e:
            log.warning("channel notify (new order) failed: %s", e)

    for admin_id in ADMIN_IDS:
        try:
            extra_text = format_extra_details(data.get("extra") or {})
            caption = (
                f"<tg-emoji emoji-id=\"5444856076954520455\">🧾</tg-emoji> <b>سفارش جدید #{order_id}</b>\n\n"
                f"کاربر: <code>{buyer_id}</code> (@{buyer_username or 'ندارد'})\n"
                f"محصول: {data['title']}\n"
                f"دسته‌بندی: {data.get('category', '-')}\n"
                f"گیرنده/توضیحات: {data.get('recipient') or '-'}\n"
                + (f"{extra_text}\n" if extra_text else "")
                + f"تعداد: {data.get('quantity', 1)}\n"
                f"مبلغ: {fmt_money(total)}\n"
                f"روش پرداخت: {pm}"
            )

            kb_admin = kb.admin_order_actions_kb(order_id)
            if proof and isinstance(proof, str) and not proof.startswith("http"):
                await message.bot.send_photo(admin_id, proof, caption=caption, reply_markup=kb_admin)
            else:
                if proof:
                    caption += f"\nرسید/توضیح: {proof}"
                await message.bot.send_message(admin_id, caption, reply_markup=kb_admin)

        except Exception as e:
            log.warning("failed to notify admin: %s", e)


# ---------- ادمین دستورات ----------

@router.message(Command("newcode"))
async def cmd_newcode(message: Message):
    if not is_admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("فرمت ناخوناست. مثال:\n`/newcode OFF20 20 100`\n(کد / درصد / حداکثر استفاده)")
        return
    code = parts[1].upper()
    percent = int(parts[2])
    max_uses = int(parts[3]) if len(parts) > 3 else 0

    db.create_discount(code, percent, max_uses)
    await message.answer(f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> کد تخفیف `{code}` با {percent}٪ تخفیف و سقف {max_uses} استفاده ساخته شد.")


@router.message(F.text.startswith("/setprice_"))
async def cmd_setprice(message: Message, bot: Bot):
    if not is_admin(message.from_user.id): return
    try:
        header, price_str = message.text.split(maxsplit=1)
        order_id = int(header.split("_")[1])
        price = int(price_str)
    except Exception:
        await message.answer("فرمت نادرست. مثال:\n`/setprice_12 350000`")
        return

    order = db.get_order(order_id)
    if not order:
        await message.answer("سفارش یافت نشد.")
        return

    db.update_order(order_id, price=price)

    await message.answer(f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> قیمت سفارش #{order_id} روی {fmt_money(price)} تنظیم شد.")
    try:
        nft_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🛒 خرید این گیفت — {price:,} تومان", callback_data=f"buy_nft:{order_id}", style="success")]
        ])
        await bot.send_message(
            order["user_id"],
            f"🔔 قیمت سفارش گیفت NFT شما (<b>#{order_id}</b>) مشخص شد:\n\n"
            f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> مبلغ: <b>{fmt_money(price)}</b>\n\n"
            f"برای پرداخت رو دکمه زیر بزن:",
            reply_markup=nft_kb,
        )
    except Exception as e:
        log.warning("failed to alert user: %s", e)


@router.callback_query(F.data.startswith("buy_nft:"))
async def buy_nft_start(callback: CallbackQuery):
    order_id = int(callback.data.split(":", 1)[1])
    order = db.get_order(order_id)
    if not order or order["user_id"] != callback.from_user.id or order["status"] != "pending_price":
        await callback.answer("این سفارش دیگه معتبر نیست.", show_alert=True)
        return
    kb_ = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👛 کیف‌پول داخلی", callback_data=f"nftpay:wallet:{order_id}", style="primary", icon_custom_emoji_id="5332455502917949981")],
        [InlineKeyboardButton(text="<tg-emoji emoji-id=\"5445353829304387411\">💳</tg-emoji> کارت به کارت", callback_data=f"nftpay:card:{order_id}", style="primary", icon_custom_emoji_id="5445353829304387411")],
        [InlineKeyboardButton(text="<tg-emoji emoji-id=\"4997067511137567958\">🪙</tg-emoji> ترون (TRX)", callback_data=f"nftpay:trx:{order_id}", style="primary")],
        [InlineKeyboardButton(text="<tg-emoji emoji-id=\"5377620962390857342\">🪙</tg-emoji> تون (TON)", callback_data=f"nftpay:ton:{order_id}", style="primary")],
    ])
    await callback.message.answer(f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> مبلغ: {fmt_money(order['price'])}\nروش پرداخت رو انتخاب کن:", reply_markup=kb_)
    await callback.answer()


@router.callback_query(F.data.startswith("nftpay:"))
async def nft_payment_choice(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    _, method, order_id_str = callback.data.split(":")
    order_id = int(order_id_str)
    order = db.get_order(order_id)
    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("نامعتبر", show_alert=True)
        return
    total = order["price"]

    if method == "wallet":
        user = db.get_or_create_user(callback.from_user.id, callback.from_user.username or "")
        if user["balance"] < total:
            await callback.message.answer(f"<tg-emoji emoji-id=\"5429518319243775957\">📉</tg-emoji> موجودی کافی نیست. موجودی: {fmt_money(user['balance'])}")
            await callback.answer()
            return
        db.change_balance(callback.from_user.id, -total)
        db.update_order(order_id, status="approved", payment_method="wallet")
        await callback.message.answer(f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> خریداری شد! سفارش #{order_id} در حال آماده‌سازیه.")
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"<tg-emoji emoji-id=\"5444856076954520455\">🧾</tg-emoji> سفارش گیفت NFT #{order_id} پرداخت شد (کیف‌پول).", reply_markup=kb.admin_order_actions_kb(order_id))
            except Exception: pass
    else:
        db.update_order(order_id, status="pending", payment_method=method)
        if method == "card":
            txt = (f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> مبلغ: <b>{fmt_money(total)}</b>\n\n"
                   f"<tg-emoji emoji-id=\"5445353829304387411\">💳</tg-emoji> این مبلغ رو به کارت زیر واریز کن:\n<code>{CARD_NUMBER}</code>\n"
                   f"به نام: {CARD_OWNER}\n\n"
                   f"بعد عکس رسید یا کد پیگیری رو همینجا بفرست:")
        elif method == "trx":
            txt = (f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> مبلغ: <b>{fmt_money(total)}</b>\n\n"
                   f"<tg-emoji emoji-id=\"4997067511137567958\">🪙</tg-emoji> معادلش رو به کیف‌پول ترون زیر بفرست:\n<code>{WALLET_TRX}</code>\n\n"
                   f"بعد عکس یا هش تراکنش رو همینجا بفرست:")
        else:
            txt = (f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> مبلغ: <b>{fmt_money(total)}</b>\n\n"
                   f"<tg-emoji emoji-id=\"5377620962390857342\">🪙</tg-emoji> معادلش رو به کیف‌پول TON زیر بفرست:\n<code>{WALLET_TON}</code>\n\n"
                   f"بعد عکس یا هش تراکنش رو همینجا بفرست:")
        await state.update_data(nft_order_id=order_id)
        await state.set_state(NftPay.proof)
        await callback.message.answer(txt)
    await callback.answer()


@router.message(NftPay.proof, F.photo | F.text)
async def nft_proof_received(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order = db.get_order(data["nft_order_id"])
    if order and order["payment_method"] == "card" and not message.photo:
        await message.answer("برای پرداخت ریالی فقط عکس رسید قبوله. عکسشو بفرست:")
        return
    order_id = data["nft_order_id"]
    proof = message.photo[-1].file_id if message.photo else message.text
    db.update_order(order_id, admin_note=f"proof: {proof}")
    await state.clear()
    order = db.get_order(order_id)

    await message.answer("<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> رسید دریافت شد و برای بررسی به ادمین فرستاده شد.")
    for admin_id in ADMIN_IDS:
        try:
            caption = f"<tg-emoji emoji-id=\"5444856076954520455\">🧾</tg-emoji> رسید سفارش گیفت NFT #{order_id}\nمبلغ: {fmt_money(order['price'])}"
            if message.photo:
                await bot.send_photo(admin_id, proof, caption=caption, reply_markup=kb.admin_order_actions_kb(order_id))
            else:
                await bot.send_message(admin_id, f"{caption}\nرسید: {proof}", reply_markup=kb.admin_order_actions_kb(order_id))
        except Exception:
            pass


# ---------- پنل مدیریت ----------

@router.message(F.text == "🛠 پنل مدیریت")
async def admin_panel(message: Message):
    if is_admin(message.from_user.id):
        await message.answer("🛠 <b>پنل مدیریت ربات</b>", reply_markup=kb.admin_panel_kb())


@router.callback_query(F.data == "adm:back")
async def adm_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("🛠 <b>پنل مدیریت ربات</b>", reply_markup=kb.admin_panel_kb())
    await callback.answer()


@router.callback_query(F.data == "adm:stats")
async def adm_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    st = db.stats()
    await callback.message.edit_text(
        f"📊 <b>آمار کل ربات:</b>\n\n"
        f"👥 تعداد کاربران: {st['users']}\n"
        f"<tg-emoji emoji-id=\"5278702045883292456\"><tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji></tg-emoji> تعداد کل سفارش‌ها: {st['orders']}\n"
        f"<tg-emoji emoji-id=\"5197269100878907942\">✍️</tg-emoji> سفارش‌های در انتظار: {st['pending_orders']}\n"
        f"<tg-emoji emoji-id=\"5197269100878907942\">✍️</tg-emoji> شارژهای در انتظار: {st['pending_topups']}\n"
        f"<tg-emoji emoji-id=\"5201691993775818138\">🛫</tg-emoji> مجموع فروش موفق: {fmt_money(st['total_sales'])}",
        reply_markup=kb.admin_panel_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:pending_orders")
async def adm_pending_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    orders = db.list_orders(status="pending", limit=10)
    if not orders:
        await callback.answer("هیچ سفارشی در انتظار نیست.", show_alert=True)
        return
    import json as _json
    for o in orders:
        extra_dict = _json.loads(o.get("extra") or "{}")
        extra_text = format_extra_details(extra_dict)
        msg_text = (
            f"<tg-emoji emoji-id=\"5444856076954520455\">🧾</tg-emoji> سفارش #{o['id']}\n"
            f"کاربر: <code>{o['user_id']}</code> (@{o['username']})\n"
            f"محصول: {o['title']}\n"
            f"دسته‌بندی: {o.get('category', '-')}\n"
            f"گیرنده/توضیحات: {o.get('recipient') or '-'}\n"
            + (f"{extra_text}\n" if extra_text else "")
            + f"تعداد: {o.get('quantity', 1)}\n"
            f"مبلغ: {fmt_money(o['price'])}\n"
            f"روش پرداخت: {o.get('payment_method') or '-'}"
        )
        await callback.message.answer(msg_text, reply_markup=kb.admin_order_actions_kb(o['id']))
    await callback.answer()


@router.callback_query(F.data == "adm:pending_topups")
async def adm_pending_topups(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    with db.get_conn() as conn:
        rows = conn.execute("SELECT * FROM topups WHERE status='pending' LIMIT 10").fetchall()
        topups = [dict(r) for r in rows]

    if not topups:
        await callback.answer("هیچ شارژی در انتظار نیست.", show_alert=True)
        return

    for t in topups:
        await callback.message.answer(
            f"<tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji> شارژ #{t['id']}\nکاربر: {t['user_id']} (@{t['username']})\nمبلغ: {fmt_money(t['amount'])}\nروش: {t['method']}",
            reply_markup=kb.admin_topup_actions_kb(t['id']),
        )
    await callback.answer()


@router.callback_query(F.data == "adm:products")
async def adm_products(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    products = db.list_products(only_active=False)
    await callback.message.edit_text("برای ویرایش هر محصول روش کلیک کن:", reply_markup=kb.admin_products_kb(products))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_prod:"))
async def adm_prod_manage(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    prod = db.get_product(key)
    if not prod: return

    status_str = "<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> فعال" if prod["active"] else "<tg-emoji emoji-id=\"5875208759176860365\"><tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji></tg-emoji> غیرفعال"
    await callback.message.edit_text(
        f"<tg-emoji emoji-id=\"5278702045883292456\"><tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji></tg-emoji> <b>{prod['title']}</b>\n\n"
        f"قیمت فعلی: {fmt_money(prod['price'])}\n"
        f"وضعیت: {status_str}\n"
        f"توضیحات:\n{prod['description']}",
        reply_markup=kb.admin_product_edit_kb(key, prod["active"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_prod_toggle:"))
async def adm_prod_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    prod = db.get_product(key)
    if not prod: return

    new_status = 0 if prod["active"] else 1
    db.update_product(key, active=new_status)
    await adm_prod_manage(callback)


@router.callback_query(F.data.startswith("adm_prod_title:"))
async def adm_prod_title_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    await state.set_state(AdminEdit.desc)
    await state.update_data(edit_key=key, edit_title=True)
    await callback.message.answer("اسم جدید محصول رو بفرست:")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_prod_price:"))
async def adm_prod_price_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    await state.set_state(AdminEdit.price)
    await state.update_data(edit_key=key)
    await callback.message.answer("قیمت جدید (به تومان) رو وارد کن:")
    await callback.answer()


@router.message(AdminEdit.price)
async def adm_prod_price_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.text.isdigit():
        await message.answer("عدد معتبر بفرست.")
        return
    data = await state.get_data()
    key = data["edit_key"]
    db.update_product(key, price=int(message.text))
    await state.clear()
    await message.answer(f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> قیمت جدید روی {fmt_money(int(message.text))} تنظیم شد.")


@router.callback_query(F.data.startswith("adm_prod_desc:"))
async def adm_prod_desc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    await state.set_state(AdminEdit.desc)
    await state.update_data(edit_key=key)
    await callback.message.answer("توضیحات جدید رو بفرست:")
    await callback.answer()


@router.message(AdminEdit.desc)
async def adm_prod_desc_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    key = data["edit_key"]
    if data.get("edit_title"):
        db.update_product(key, title=message.text)
        await message.answer("<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> اسم محصول به‌روزرسانی شد.")
    else:
        db.update_product(key, description=message.text)
        await message.answer("<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> توضیحات محصول به‌روزرسانی شد.")
    await state.clear()


@router.callback_query(F.data.startswith("adm_order:"))
async def adm_order_action(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    _, action, order_id_str = callback.data.split(":")
    order_id = int(order_id_str)
    order = db.get_order(order_id)
    if not order: return

    if action == "approve":
        if order["status"] != "pending":
            await callback.answer("این سفارش قبلاً پردازش شده.", show_alert=True)
            return
        db.update_order(order_id, status="approved")
        await callback.answer("سفارش تایید شد <tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji>")
        await callback.message.edit_reply_markup(reply_markup=kb.admin_order_after_approve_kb(order_id))
        try:
            await bot.send_message(
                order["user_id"],
                f"<tg-emoji emoji-id=\"5873206621517124461\">🟢</tg-emoji> <b>پرداخت سفارش #{order_id} تایید شد!</b>\n\n"
                f"محصول شما به‌زودی تحویل داده می‌شه."
            )
        except Exception: pass

        recipient = (order.get("recipient") or "").lstrip("@")
        auto_ok, auto_err = False, None
        try:
            if order["category"] == "stars" and recipient:
                await marketapp.purchase_stars(recipient, order.get("quantity") or 50)
                auto_ok = True
            elif order["category"] == "premium" and recipient:
                PREMIUM_MONTHS_MAP = {"premium_1m": 6, "premium_3m": 3, "premium_12m": 12, "vip_1m": 3}
                months = PREMIUM_MONTHS_MAP.get(order.get("product_key"), 3)
                await marketapp.purchase_premium(recipient, months)
                auto_ok = True
        except Exception as e:
            auto_err = str(e)

        if auto_ok:
            db.update_order(order_id, status="fulfilled")
            try:
                await bot.send_message(order["user_id"], f"✅ سفارش #{order_id} خودکار تحویل داده شد!")
            except Exception: pass
            try:
                await bot.send_message(callback.from_user.id, f"🤖 سفارش #{order_id} با موفقیت خودکار (Marketapp) تحویل داده شد.")
            except Exception: pass
        elif auto_err:
            try:
                await bot.send_message(callback.from_user.id, f"⚠️ تحویل خودکار سفارش #{order_id} شکست خورد:\n{auto_err}\nلطفاً دستی بررسی کن.")
            except Exception: pass

    elif action == "reject":
        if order["status"] != "pending":
            await callback.answer("این سفارش قبلاً پردازش شده.", show_alert=True)
            return
        db.update_order(order_id, status="rejected")
        await callback.answer("سفارش رد شد <tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji>")
        await callback.message.edit_reply_markup(reply_markup=None)
        try:
            await bot.send_message(
                order["user_id"],
                f"<tg-emoji emoji-id=\"5875208759176860365\">🔴</tg-emoji> <b>سفارش #{order_id} رد شد.</b>\n"
                f"در صورت نیاز با پشتیبانی در ارتباط باش."
            )
        except Exception: pass

    elif action == "done":
        if order["status"] != "approved":
            await callback.answer("اول باید تایید بشه.", show_alert=True)
            return

        recipient = (order.get("recipient") or "").lstrip("@")
        auto_ok, auto_err = False, None
        try:
            if order["category"] == "stars" and recipient:
                await marketapp.purchase_stars(recipient, order.get("quantity") or 50)
                auto_ok = True
            elif order["category"] == "premium" and recipient:
                PREMIUM_MONTHS_MAP = {"premium_1m": 6, "premium_3m": 3, "premium_12m": 12, "vip_1m": 3}
                months = PREMIUM_MONTHS_MAP.get(order.get("product_key"), 3)
                await marketapp.purchase_premium(recipient, months)
                auto_ok = True
        except Exception as e:
            auto_err = str(e)

        if auto_err:
            log.error("marketapp auto-fulfill failed for order %s: %s", order_id, auto_err)
            await callback.answer("خطا تو تحویل خودکار! پایین رو بخون.", show_alert=True)
            try:
                import html as _html
                await bot.send_message(callback.from_user.id, f"⚠️ تحویل خودکار سفارش #{order_id} شکست خورد:\n{_html.escape(str(auto_err))}")
            except Exception as e2:
                log.error("failed to notify admin of marketapp error: %s", e2)
            return

        db.update_order(order_id, status="fulfilled")
        await callback.answer("تحویل تایید شد <tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji>")
        await callback.message.edit_reply_markup(reply_markup=None)
        try:
            await bot.send_message(
                order["user_id"],
                f"<tg-emoji emoji-id=\"5875345931842360057\">✅</tg-emoji> <b>سفارش #{order_id} با موفقیت تحویل داده شد!</b>\n"
                f"از خریدت متشکریم."
            )
        except Exception: pass
        ch_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 برای خرید از ربات کلیک کن", url=f"https://t.me/{BOT_USERNAME}")]])
        if ORDER_CHANNEL_ID:
            try:
                await bot.send_message(ORDER_CHANNEL_ID, channel_order_text("🎉", "تکمیل شد", order["user_id"], order["category"], order.get("quantity", 1), order["price"]), reply_markup=ch_kb)
            except Exception as e:
                log.warning("channel notify (done) failed: %s", e)
        await send_report(bot, "topic_purchase", topic_purchase_text(order["user_id"], order.get("username", ""), order["title"], order.get("quantity", 1), order["price"]))


@router.callback_query(F.data.startswith("adm_topup:"))
async def adm_topup_action(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    _, action, topup_id_str = callback.data.split(":")
    topup_id = int(topup_id_str)
    topup = db.get_topup(topup_id)
    if not topup or topup["status"] != "pending":
        await callback.answer("این درخواست قبلا تعیین تکلیف شده.", show_alert=True)
        return

    if action == "approve":
        db.update_topup(topup_id, status="approved")
        db.change_balance(topup["user_id"], topup["amount"])

        # پورسانت معرف
        user = db.get_user(topup["user_id"])
        if user and user.get("referred_by"):
            ref_id = user["referred_by"]
            reward = int(topup["amount"] * REFERRAL_PERCENT / 100)
            if reward > 0:
                db.change_balance(ref_id, reward)
                try:
                    await bot.send_message(
                        ref_id,
                        f"🎁 <b>مژده!</b> یکی از زیرمجموعه‌هات حسابشو شارژ کرد و "
                        f"مبلغ <b>{fmt_money(reward)}</b> به کیف‌پولت اضافه شد!"
                    )
                except Exception: pass

        await callback.answer("شارژ تایید شد <tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji>")
        try:
            await bot.send_message(
                topup["user_id"],
                f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> <b>کیف‌پول شما شارژ شد!</b>\n\n"
                f"مبلغ: {fmt_money(topup['amount'])}"
            )
        except Exception: pass

    elif action == "reject":
        db.update_topup(topup_id, status="rejected")
        await callback.answer("درخواست رد شد <tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji>")
        try:
            await bot.send_message(
                topup["user_id"],
                f"<tg-emoji emoji-id=\"5875208759176860365\"><tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji></tg-emoji> <b>درخواست شارژ #{topup_id} رد شد.</b>"
            )
        except Exception: pass


# ---------- مدیریت دسته‌بندی‌ها ----------

@router.callback_query(F.data == "adm:categories")
async def adm_categories(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cats = db.list_categories(only_active=False)
    await callback.message.edit_text("🗂 <b>مدیریت دسته‌بندی‌ها</b>\n\nروی هرکدوم بزن برای ویرایش:", reply_markup=kb.admin_categories_kb(cats))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cat:"))
async def adm_cat_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    cat = db.get_category(key)
    if not cat: return
    status_str = "<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> فعال" if cat["active"] else "<tg-emoji emoji-id=\"5875208759176860365\"><tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji></tg-emoji> غیرفعال"
    await callback.message.edit_text(
        f"🗂 <b>{cat['title']}</b>\n\nکلید: <code>{cat['key']}</code>\nوضعیت: {status_str}",
        reply_markup=kb.admin_category_edit_kb(key, cat["active"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cat_toggle:"))
async def adm_cat_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    cat = db.get_category(key)
    if not cat: return
    db.update_category(key, active=0 if cat["active"] else 1)
    await adm_cat_detail(callback)


@router.callback_query(F.data.startswith("adm_cat_desc:"))
async def adm_cat_desc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    await state.set_state(AdminCategory.rename)
    await state.update_data(cat_key=key, cat_desc_mode=True)
    await callback.message.answer("توضیحات جدید دسته‌بندی رو بفرست:")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cat_desc:"))
async def adm_cat_desc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    await state.set_state(AdminCategory.rename)
    await state.update_data(cat_key=key, cat_desc_mode=True)
    await callback.message.answer("توضیحات جدید دسته‌بندی رو بفرست:")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cat_rename:"))
async def adm_cat_rename_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    await state.set_state(AdminCategory.rename)
    await state.update_data(cat_key=key)
    await callback.message.answer("اسم جدید دسته‌بندی رو بفرست (می‌تونی ایموجی هم بذاری):")
    await callback.answer()


@router.message(AdminCategory.rename)
async def adm_cat_rename_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    if data.get("cat_desc_mode"):
        db.update_category(data["cat_key"], description=message.text.strip())
        await message.answer("<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> توضیحات دسته‌بندی به‌روزرسانی شد.")
    else:
        db.update_category(data["cat_key"], title=message.text.strip())
        await message.answer("<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> اسم دسته‌بندی به‌روزرسانی شد.")
    await state.clear()


@router.callback_query(F.data == "adm:add_category")
async def adm_add_category_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(AdminCategory.new_input)
    await callback.message.answer(
        "برای ساخت دسته‌بندی جدید، به این فرمت بفرست:\n"
        "<code>کلید_انگلیسی|عنوان نمایشی</code>\n\n"
        "مثال:\n<code>crypto_usdt|<tg-emoji emoji-id=\"5201691993775818138\">🛫</tg-emoji> خرید تتر</code>"
    )
    await callback.answer()


@router.message(AdminCategory.new_input)
async def adm_add_category_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    parts = message.text.split("|", 1)
    if len(parts) != 2 or not parts[0].strip():
        await message.answer("فرمت اشتباهه. دوباره به این شکل بفرست:\n<code>کلید|عنوان</code>")
        return
    key = parts[0].strip().lower().replace(" ", "_")
    title = parts[1].strip()
    ok = db.create_category(key, title)
    await state.clear()
    if ok:
        await message.answer(f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> دسته‌بندی «{title}» ساخته شد.")
    else:
        await message.answer("<tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji> این کلید قبلاً استفاده شده. یه کلید دیگه امتحان کن.")


# ---------- افزودن محصول جدید ----------

@router.callback_query(F.data == "adm:add_product")
async def adm_add_product_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cats = db.list_categories(only_active=False)
    if not cats:
        await callback.answer("اول باید حداقل یه دسته‌بندی بسازی.", show_alert=True)
        return
    await callback.message.edit_text("اول دسته‌بندی محصول جدید رو انتخاب کن:", reply_markup=kb.category_pick_kb(cats))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_newprod_cat:"))
async def adm_add_product_category_chosen(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    category = callback.data.split(":", 1)[1]
    await state.set_state(AdminNewProduct.input)
    await state.update_data(new_prod_category=category)
    await callback.message.answer(
        "مشخصات محصول رو به این فرمت بفرست:\n"
        "<code>کلید_انگلیسی|عنوان نمایشی|قیمت به تومان</code>\n\n"
        "مثال:\n<code>vip_1m|<tg-emoji emoji-id=\"5377620962390857342\">🪙</tg-emoji> اشتراک ویژه ۱ ماهه|500000</code>"
    )
    await callback.answer()


@router.message(AdminNewProduct.input)
async def adm_add_product_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    parts = message.text.split("|")
    if len(parts) != 3 or not parts[2].strip().isdigit():
        await message.answer("فرمت اشتباهه. دوباره به این شکل بفرست:\n<code>کلید|عنوان|قیمت</code>")
        return
    key = parts[0].strip().lower().replace(" ", "_")
    title = parts[1].strip()
    price = int(parts[2].strip())
    await state.update_data(new_prod_key=key, new_prod_title=title, new_prod_price=price)
    await state.set_state(AdminNewProduct.desc)
    await message.answer("حالا توضیحات و مزایای محصول رو بفرست (هرچقدر جذاب‌تر بهتر):")


@router.message(AdminNewProduct.desc)
async def adm_add_product_desc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    ok = db.create_product(
        key=data["new_prod_key"],
        category=data["new_prod_category"],
        title=data["new_prod_title"],
        description=message.text.strip(),
        price=data["new_prod_price"],
    )
    await state.clear()
    if ok:
        await message.answer(f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> محصول «{data['new_prod_title']}» با موفقیت ساخته شد.")
    else:
        await message.answer("<tg-emoji emoji-id=\"4994791839895651680\">❌</tg-emoji> این کلید محصول قبلاً استفاده شده. با کلید دیگه‌ای دوباره امتحان کن.")


# ---------- بتل گروهی پیشرفته با سطح و انتقال امتیاز ----------

PENDING_BATTLES = {}

def init_battle_db():
    with db.get_conn() as conn:
        conn.execute("DROP TABLE IF EXISTS battles")
        conn.execute("""CREATE TABLE battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER, winner_id INTEGER, winner_name TEXT,
            loser_id INTEGER, loser_name TEXT, day TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS battle_points (
            user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0)""")
        conn.commit()

def get_points(user_id: int) -> int:
    with db.get_conn() as conn:
        row = conn.execute("SELECT points FROM battle_points WHERE user_id=?", (user_id,)).fetchone()
        return row[0] if row else 0

def add_points(user_id: int, delta: int):
    with db.get_conn() as conn:
        conn.execute("INSERT INTO battle_points (user_id, points) VALUES (?, 0) ON CONFLICT(user_id) DO NOTHING", (user_id,))
        conn.execute("UPDATE battle_points SET points = MAX(0, points + ?) WHERE user_id=?", (delta, user_id))
        conn.commit()

def get_level(points: int) -> int:
    return points // 10 + 1

BATTLE_PENDING_SETUP = {}

@router.message(Command("battle"))
async def cmd_battle(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("این دستور فقط تو گروه کار می‌کنه.")
        return
    import time
    init_battle_db()
    token = str(int(time.time() * 1000))
    target = message.reply_to_message.from_user if (message.reply_to_message and message.reply_to_message.from_user.id != message.from_user.id) else None
    BATTLE_PENDING_SETUP[token] = {"creator": message.from_user, "target": target, "chat_id": message.chat.id}
    kb_ = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="<tg-emoji emoji-id=\"5197371802136892976\">⛏</tg-emoji>️ با سرباز", callback_data=f"battletype:soldier:{token}", style="primary")],
        [InlineKeyboardButton(text="🎳 با بولینگ", callback_data=f"battletype:bowl:{token}", style="success")],
        [InlineKeyboardButton(text="⚽ با فوتبال", callback_data=f"battletype:foot:{token}", style="danger")],
    ])
    await message.answer("نوع بتل رو انتخاب کن:", reply_markup=kb_)


@router.callback_query(F.data.startswith("battletype:"))
async def battle_type_choice(callback: CallbackQuery):
    _, btype, token = callback.data.split(":")
    setup = BATTLE_PENDING_SETUP.pop(token, None)
    if not setup or callback.from_user.id != setup["creator"].id:
        await callback.answer("این برای تو نیست.", show_alert=True)
        return
    if setup["target"]:
        PENDING_BATTLES[token] = {**setup, "open": False, "type": btype}
        kb2 = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="قبول می‌کنم", callback_data=f"battle_accept:{token}", style="success")]])
        await callback.message.edit_text(f"<tg-emoji emoji-id=\"5197371802136892976\">⛏</tg-emoji>️ {setup['creator'].full_name} به {setup['target'].full_name} چالش داد!\nفقط {setup['target'].full_name} می‌تونه قبول کنه.", reply_markup=kb2)
    else:
        PENDING_BATTLES[token] = {**setup, "open": True, "type": btype}
        kb2 = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="شرکت در بتل", callback_data=f"battle_join:{token}", style="primary")]])
        await callback.message.edit_text(f"<tg-emoji emoji-id=\"5197371802136892976\">⛏</tg-emoji>️ {setup['creator'].full_name} درخواست بتل باز فرستاد!\nهرکی دوست داره شرکت کنه:", reply_markup=kb2)
    await callback.answer()

async def resolve_battle(callback: CallbackQuery, p1, p2, chat_id: int, btype: str = "soldier"):
    import random, asyncio as aio
    from datetime import date

    if btype in ("bowl", "foot"):
        emoji = "🎳" if btype == "bowl" else "⚽"
        await callback.message.edit_text(f"{emoji} {p1.full_name} 🆚 {p2.full_name}\n\nهر دو باید بندازن، بیشترین امتیاز می‌بره!", reply_markup=None)
        d1 = await callback.bot.send_dice(chat_id, emoji=emoji)
        await aio.sleep(1)
        d2 = await callback.bot.send_dice(chat_id, emoji=emoji)
        await aio.sleep(3.5)
        v1, v2 = d1.dice.value, d2.dice.value
        if v1 == v2:
            await callback.message.answer(f"{emoji} {p1.full_name}: {v1} | {p2.full_name}: {v2}\n\n🤝 مساوی شد!")
            return
        winner, loser = (p1, p2) if v1 > v2 else (p2, p1)
        add_points(winner.id, 2)
        add_points(loser.id, -2)
        with db.get_conn() as conn:
            conn.execute("INSERT INTO battles (chat_id, winner_id, winner_name, loser_id, loser_name, day) VALUES (?,?,?,?,?,?)",
                          (chat_id, winner.id, winner.full_name, loser.id, loser.full_name, str(__import__("datetime").date.today())))
            conn.commit()
        wl, ll = get_level(get_points(winner.id)), get_level(get_points(loser.id))
        await callback.message.answer(f"{emoji} {p1.full_name}: {v1} | {p2.full_name}: {v2}\n\n<tg-emoji emoji-id=\"5451814216031809603\">🍾</tg-emoji> برنده: {winner.full_name} (+۲ سرباز، سطح {wl})\n💀 بازنده: {loser.full_name} (-۲ سرباز، سطح {ll})")
        return

    pts1, pts2 = get_points(p1.id), get_points(p2.id)
    w1, w2 = pts1 + 10, pts2 + 10
    winner, loser = random.choices([(p1, p2), (p2, p1)], weights=[w1, w2], k=1)[0]

    steps = [
        f"<tg-emoji emoji-id=\"5197371802136892976\">⛏</tg-emoji>️ {p1.full_name} ({pts1} سرباز) 🆚 {p2.full_name} ({pts2} سرباز)\n\n🥁 دو سپاه رو به روی هم صف کشیدن...",
        f"<tg-emoji emoji-id=\"5197371802136892976\">⛏</tg-emoji>️ {p1.full_name} 🆚 {p2.full_name}\n\n💥 حمله شروع شد! صدای شمشیرها می‌پیچه...",
        f"<tg-emoji emoji-id=\"5197371802136892976\">⛏</tg-emoji>️ {p1.full_name} 🆚 {p2.full_name}\n\n🔥 نبرد به اوج رسیده، هیچ‌کس عقب نمی‌کشه...",
        f"<tg-emoji emoji-id=\"5197371802136892976\">⛏</tg-emoji>️ {p1.full_name} 🆚 {p2.full_name}\n\n🌫 گرد و غبار میدون داره فرو می‌شینه...",
    ]
    for s in steps:
        await callback.message.edit_text(s, reply_markup=None)
        await aio.sleep(1.5)  # 4 مرحله × 1.5 = 6 ثانیه

    add_points(winner.id, 2)
    add_points(loser.id, -2)
    with db.get_conn() as conn:
        conn.execute("INSERT INTO battles (chat_id, winner_id, winner_name, loser_id, loser_name, day) VALUES (?,?,?,?,?,?)",
                      (chat_id, winner.id, winner.full_name, loser.id, loser.full_name, str(date.today())))
        conn.commit()

    wl, ll = get_level(get_points(winner.id)), get_level(get_points(loser.id))
    await callback.message.answer(
        f"<tg-emoji emoji-id=\"5451814216031809603\">🍾</tg-emoji> برنده: {winner.full_name} (+۲ سرباز، سطح {wl})\n"
        f"💀 بازنده: {loser.full_name} (-۲ سرباز، سطح {ll})"
    )


@router.message(Command("train"))
async def cmd_train(message: Message):
    import time
    init_battle_db()
    with db.get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS train_cooldown (user_id INTEGER PRIMARY KEY, last_time INTEGER)")
        row = conn.execute("SELECT last_time FROM train_cooldown WHERE user_id=?", (message.from_user.id,)).fetchone()
        now = int(time.time())
        if row and now - row[0] < 3600:
            remain = 3600 - (now - row[0])
            await message.answer(f"<tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> کارخونه هنوز کار می‌کنه، {remain // 60} دقیقه دیگه صبر کن.")
            return
        conn.execute("INSERT OR REPLACE INTO train_cooldown (user_id, last_time) VALUES (?, ?)", (message.from_user.id, now))
        conn.commit()
    add_points(message.from_user.id, 1)
    lvl = get_level(get_points(message.from_user.id))
    await message.answer(f"<tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> یه سرباز آموزش دیدی! +۱ امتیاز (سطح {lvl})\nهر ۱ ساعت یه‌بار می‌تونی آموزش بدی.")

@router.callback_query(F.data.startswith("battle_join:"))
async def battle_join(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    b_ = PENDING_BATTLES.get(token)
    if not b_ or not b_["open"]:
        await callback.answer("این درخواست دیگه معتبر نیست.", show_alert=True)
        return
    if callback.from_user.id == b_["creator"].id:
        await callback.answer("نمی‌تونی با خودت بتل کنی!", show_alert=True)
        return
    del PENDING_BATTLES[token]
    await callback.answer("وارد بتل شدی! <tg-emoji emoji-id=\"5197371802136892976\">⛏</tg-emoji>️")
    await resolve_battle(callback, b_["creator"], callback.from_user, b_["chat_id"], b_.get("type", "soldier"))

@router.callback_query(F.data.startswith("battle_accept:"))
async def battle_accept(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    b_ = PENDING_BATTLES.get(token)
    if not b_:
        await callback.answer("این چالش دیگه معتبر نیست.", show_alert=True)
        return
    if callback.from_user.id != b_["target"].id:
        await callback.answer("این چالش برای تو نیست!", show_alert=True)
        return
    del PENDING_BATTLES[token]
    await callback.answer("چالش رو قبول کردی! <tg-emoji emoji-id=\"5197371802136892976\">⛏</tg-emoji>️")
    await resolve_battle(callback, b_["creator"], b_["target"], b_["chat_id"], b_.get("type", "soldier"))

@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    init_battle_db()
    with db.get_conn() as conn:
        rows = conn.execute("SELECT user_id, points FROM battle_points ORDER BY points DESC LIMIT 10").fetchall()
    if not rows:
        await message.answer("هنوز کسی بتل نکرده.")
        return
    medals = ["🥇","🥈","🥉"] + ["🔹"]*7
    text = "<tg-emoji emoji-id=\"5451814216031809603\">🍾</tg-emoji> <b>برترین‌های بتل</b>\n\n"
    for i, (uid, pts) in enumerate(rows):
        text += f"{medals[i]} <a href='tg://user?id={uid}'>کاربر</a> — امتیاز: {pts} | سطح {get_level(pts)}\n"
    await message.answer(text, disable_web_page_preview=True)

@router.message(Command("transfer"))
async def cmd_transfer(message: Message):
    if not message.reply_to_message:
        await message.answer("رو پیام کسی که می‌خوای بهش امتیاز بدی ریپلای کن:\n/transfer 5")
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("فرمت درست: /transfer 5")
        return
    amount = int(parts[1])
    target = message.reply_to_message.from_user
    if target.id == message.from_user.id:
        await message.answer("نمی‌تونی به خودت انتقال بدی.")
        return
    init_battle_db()
    if get_points(message.from_user.id) < amount:
        await message.answer("امتیاز کافی نداری.")
        return
    add_points(message.from_user.id, -amount)
    add_points(target.id, amount)
    await message.answer(f"<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> {amount} امتیاز از {message.from_user.full_name} به {target.full_name} منتقل شد.")


# ---------- ویرایش متن‌های ربات ----------

@router.callback_query(F.data == "adm:texts")
async def adm_texts_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    rows = []
    buttons = []
    for key, default in TEXT_DEFAULTS.items():
        current = db.get_text(key, default)
        label = (current[:20] + "…") if len(current) > 20 else current
        buttons.append(InlineKeyboardButton(text=label, callback_data=f"adm_text:{key}", style="primary"))
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm:back", style="danger")])
    await callback.message.edit_text("✏️ روی هر متن بزن تا تغییرش بدی:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_text:"))
async def adm_text_edit_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split(":", 1)[1]
    current = db.get_text(key, TEXT_DEFAULTS.get(key, ""))
    await state.set_state(AdminText.edit)
    await state.update_data(text_key=key)
    await callback.message.answer(f"متن فعلی:\n{current}\n\nمتن جدید رو بفرست:")
    await callback.answer()


@router.message(AdminText.edit)
async def adm_text_edit_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    db.set_text(data["text_key"], message.text)
    await state.clear()
    await message.answer("<tg-emoji emoji-id=\"5872801180899348885\">✅</tg-emoji> متن به‌روزرسانی شد.")


# ---------- جوین اجباری ----------

async def check_forced_join(user_id: int, bot: Bot) -> list[str]:
    """کانال‌هایی که کاربر عضو نیست رو برمی‌گردونه"""
    missing = []
    for key in ("force_channel_1", "force_channel_2"):
        ch = db.get_text(key, "")
        if not ch:
            continue
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception:
            missing.append(ch)
    return missing


async def send_join_prompt(message: Message, missing: list[str]):
    rows = []
    for ch in missing:
        uname = ch.lstrip("@")
        rows.append([InlineKeyboardButton(text=f"📢 عضویت در {ch}", url=f"https://t.me/{uname}")])
    rows.append([InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_join_again", style="success")])
    await message.answer(
        "برای استفاده از ربات، اول باید عضو کانال(های) زیر بشی:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "check_join_again")
async def check_join_again(callback: CallbackQuery, state: FSMContext):
    missing = await check_forced_join(callback.from_user.id, callback.bot)
    if missing:
        await callback.answer("هنوز عضو نشدی!", show_alert=True)
        return
    await callback.answer("عضویت تایید شد ✅")
    await callback.message.delete()

    data = await state.get_data()
    pending_ref = data.get("pending_ref")
    existing_user = db.get_user(callback.from_user.id)
    db.get_or_create_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username or "",
        referred_by=pending_ref,
    )
    if existing_user is None:
        db.change_balance(callback.from_user.id, 25000)
        await callback.message.answer(
            "🎁 به‌عنوان هدیه‌ی خوش‌آمدگویی، <b>۲۵,۰۰۰ تومان</b> به کیف‌پولت اضافه شد!"
        )
    menu = kb.admin_extra_button() if is_admin(callback.from_user.id) else kb.main_menu()
    await callback.message.answer(db.get_text("txt_welcome", TEXT_DEFAULTS["txt_welcome"]), reply_markup=menu)


@router.callback_query(F.data == "btn_set_channel")
async def adm_set_channel_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    ch1 = db.get_text("force_channel_1", "تنظیم‌نشده")
    ch2 = db.get_text("force_channel_2", "تنظیم‌نشده")
    kb_ = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"کانال ۱: {ch1}", callback_data="setch:1", style="primary")],
        [InlineKeyboardButton(text=f"کانال ۲: {ch2}", callback_data="setch:2", style="primary")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm:back", style="danger")],
    ])
    await callback.message.answer("📢 کانال‌های عضویت اجباری (برای غیرفعال کردن یکی، بنویس: خالی)", reply_markup=kb_)
    await callback.answer()


@router.callback_query(F.data.startswith("setch:"))
async def adm_set_channel_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    num = callback.data.split(":", 1)[1]
    await state.set_state(AdminChannel.waiting_ch1 if num == "1" else AdminChannel.waiting_ch2)
    await state.update_data(ch_num=num)
    await callback.message.answer("آیدی کانال رو با @ بفرست (مثال: @mychannel)، یا بنویس «خالی» برای غیرفعال کردن:")
    await callback.answer()


@router.message(AdminChannel.waiting_ch1)
@router.message(AdminChannel.waiting_ch2)
async def adm_set_channel_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    num = data.get("ch_num", "1")
    val = "" if message.text.strip() in ("خالی", "-", "none") else message.text.strip()
    db.set_text(f"force_channel_{num}", val)
    await state.clear()
    await message.answer(f"✅ کانال {num} به‌روزرسانی شد.")


# ---------- شارژ/جستجوی کاربر (پیشرفته) ----------

@router.callback_query(F.data == "btn_set_balance")
async def adm_user_lookup_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(AdminUserLookup.waiting_id)
    await callback.message.answer("آیدی عددی کاربر رو بفرست:")
    await callback.answer()


@router.message(AdminUserLookup.waiting_id)
async def adm_user_lookup_show(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.text.strip().isdigit():
        await message.answer("فقط آیدی عددی بفرست.")
        return
    uid = int(message.text.strip())
    user = db.get_user(uid)
    if not user:
        await message.answer("همچین کاربری تو دیتابیس نیست.")
        return
    orders = db.list_orders(user_id=uid, limit=1000)
    total_spent = sum(o["price"] for o in orders if o["status"] in ("approved", "fulfilled"))
    refs = db.count_referrals(uid)

    await state.update_data(target_uid=uid)
    await state.set_state(AdminUserLookup.waiting_amount)
    kb_ = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزایش موجودی", callback_data=f"chguser:add:{uid}", style="success")],
        [InlineKeyboardButton(text="➖ کاهش موجودی", callback_data=f"chguser:sub:{uid}", style="danger")],
        [InlineKeyboardButton(text="📩 پیام به کاربر", callback_data=f"admsend:{uid}", style="primary")],
        [InlineKeyboardButton(text="📦 سفارش‌های کاربر", callback_data=f"admorders:{uid}:0", style="primary")],
    ])
    await message.answer(
        f"👤 <b>کاربر #{uid}</b>\n\n"
        f"یوزرنیم: @{user.get('username') or 'ندارد'}\n"
        f"💰 موجودی فعلی: {fmt_money(user['balance'])}\n"
        f"📦 تعداد سفارش: {len(orders)}\n"
        f"💵 مجموع خرید موفق: {fmt_money(total_spent)}\n"
        f"🧑‍🤝‍🧑 تعداد زیرمجموعه: {refs}",
        reply_markup=kb_,
    )


@router.callback_query(F.data.startswith("admsend:"))
async def admsend_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    uid = int(callback.data.split(":", 1)[1])
    await state.update_data(target_uid=uid)
    await state.set_state(AdminUserLookup.waiting_message)
    await callback.message.answer(f"متنی که می‌خوای برای کاربر #{uid} بفرستی رو بنویس:")
    await callback.answer()


@router.message(AdminUserLookup.waiting_message)
async def admsend_apply(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    uid = data.get("target_uid")
    await state.clear()
    try:
        await message.bot.send_message(uid, f"📩 <b>پیام از پشتیبانی:</b>\n\n{message.text}")
        await message.answer("✅ پیام ارسال شد.")
    except Exception as e:
        await message.answer(f"❌ ارسال نشد: {e}")


def build_admin_user_orders_page(target_uid: int, page: int):
    total = db.count_orders(user_id=target_uid)
    offset = page * ORDERS_PAGE_SIZE
    orders = db.list_orders(user_id=target_uid, limit=ORDERS_PAGE_SIZE, offset=offset)
    text = f"📦 <b>سفارش‌های کاربر #{target_uid}</b>\nصفحه {page + 1}\n"
    for o in orders:
        icon = ORDER_STATUS_ICON.get(o["status"], "⚪️")
        text += f"\n{icon} #{o['id']} — {o['title']} — {fmt_money(o['price'])} — {o['status']}"
    rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"admorders:{target_uid}:{page - 1}", style="primary"))
    if offset + ORDERS_PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"admorders:{target_uid}:{page + 1}", style="primary"))
    if nav:
        rows.append(nav)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("admorders:"))
async def admorders_show(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    _, uid_str, page_str = callback.data.split(":")
    target_uid, page = int(uid_str), int(page_str)
    if db.count_orders(user_id=target_uid) == 0:
        await callback.answer("این کاربر سفارشی نداره.", show_alert=True)
        return
    text, kb_ = build_admin_user_orders_page(target_uid, page)
    await callback.message.answer(text, reply_markup=kb_)
    await callback.answer()


@router.callback_query(F.data.startswith("chguser:"))
async def adm_user_change_balance_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    _, mode, uid = callback.data.split(":")
    await state.update_data(target_uid=int(uid), chg_mode=mode)
    await state.set_state(AdminUserLookup.waiting_amount)
    await callback.message.answer("مبلغ (تومان) رو بفرست:")
    await callback.answer()


@router.message(AdminUserLookup.waiting_amount)
async def adm_user_change_balance_apply(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.text.strip().isdigit():
        await message.answer("فقط عدد بفرست.")
        return
    data = await state.get_data()
    uid = data.get("target_uid")
    mode = data.get("chg_mode")
    amount = int(message.text.strip())
    if not uid or not mode:
        await message.answer("یه چیزی گم شد، از اول امتحان کن.")
        await state.clear()
        return
    delta = amount if mode == "add" else -amount
    db.change_balance(uid, delta)
    await state.clear()
    await message.answer(f"✅ موجودی کاربر #{uid} به میزان {fmt_money(amount)} {'اضافه' if mode == 'add' else 'کم'} شد.")
    try:
        await message.bot.send_message(uid, f"💰 موجودی حسابت توسط پشتیبانی {'اضافه' if mode == 'add' else 'کم'} شد: {fmt_money(amount)}")
    except Exception: pass
    await send_report(message.bot, "topic_financial", f"💳 #گزارش_مالی\n\n👤 ID: <code>{uid}</code>\n{'افزایش' if mode == 'add' else 'کاهش'} دستی موجودی: {fmt_money(amount)}")


# ---------- بخش‌های جدید حساب کاربری ----------

@router.callback_query(F.data == "acc_challenge")
async def acc_challenge_menu(callback: CallbackQuery):
    kb_ = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 تاس", callback_data="do_challenge:dice", style="primary")],
        [InlineKeyboardButton(text="🎳 بولینگ", callback_data="do_challenge:bowl", style="success")],
    ])
    await callback.message.answer("یکی رو انتخاب کن، هر ۲۴ ساعت فقط یه‌بار می‌تونی بندازی:", reply_markup=kb_)
    await callback.answer()


@router.callback_query(F.data.startswith("do_challenge:"))
async def acc_challenge_roll(callback: CallbackQuery):
    import time
    game = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    with db.get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS daily_challenge (user_id INTEGER PRIMARY KEY, last_time INTEGER)")
        row = conn.execute("SELECT last_time FROM daily_challenge WHERE user_id=?", (uid,)).fetchone()
        now = int(time.time())
        if row and now - row["last_time"] < 86400:
            remain = 86400 - (now - row["last_time"])
            await callback.answer(f"⏳ {remain // 3600} ساعت دیگه صبر کن.", show_alert=True)
            return
        conn.execute("INSERT OR REPLACE INTO daily_challenge (user_id, last_time) VALUES (?, ?)", (uid, now))
        conn.commit()

    await callback.answer()
    emoji = "🎲" if game == "dice" else "🎳"
    dice_msg = await callback.message.answer_dice(emoji=emoji)
    await asyncio.sleep(4)
    value = dice_msg.dice.value
    if game == "bowl":
        value = 6 if value == 6 else (value - 1 if value > 1 else 1)
    reward = value * 1000
    db.change_balance(uid, reward)
    await callback.message.answer(f"🎉 عدد {value} اومد! {reward:,} تومان به کیف‌پولت اضافه شد.")


ORDERS_PAGE_SIZE = 5

ORDER_STATUS_ICON = {
    "fulfilled": "✅",
    "pending": "🟡",
    "approved": "🟢",
    "rejected": "🔴",
    "pending_price": "🟡",
}


def build_orders_page(user_id: int, page: int):
    total = db.count_orders(user_id=user_id)
    offset = page * ORDERS_PAGE_SIZE
    orders = db.list_orders(user_id=user_id, limit=ORDERS_PAGE_SIZE, offset=offset)
    text = f"<tg-emoji emoji-id=\"5451937962629544243\">🛍</tg-emoji> <b>سفارش‌های شما</b>\nصفحه {page + 1} — رو هر سفارش بزن برای جزئیات\n"
    rows = []
    for o in orders:
        icon = ORDER_STATUS_ICON.get(o["status"], "⚪️")
        label = f"{icon} #{o['id']} — {o['title']} — {fmt_money(o['price'])}"
        if len(label) > 60:
            label = label[:57] + "..."
        rows.append([InlineKeyboardButton(text=label, callback_data=f"order_detail:{o['id']}:{page}", style="primary")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"acc_orders_page:{page - 1}", style="primary"))
    if offset + ORDERS_PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"acc_orders_page:{page + 1}", style="primary"))
    if nav:
        rows.append(nav)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "acc_recent_orders")
async def acc_recent_orders(callback: CallbackQuery):
    if db.count_orders(user_id=callback.from_user.id) == 0:
        await callback.answer("سفارشی نداری.", show_alert=True)
        return
    await callback.answer()
    text, kb_ = build_orders_page(callback.from_user.id, 0)
    await callback.message.answer(text, reply_markup=kb_)


@router.callback_query(F.data.startswith("acc_orders_page:"))
async def acc_orders_page_nav(callback: CallbackQuery):
    page = int(callback.data.split(":", 1)[1])
    text, kb_ = build_orders_page(callback.from_user.id, page)
    await callback.message.edit_text(text, reply_markup=kb_)
    await callback.answer()


@router.callback_query(F.data.startswith("order_detail:"))
async def acc_order_detail(callback: CallbackQuery):
    _, order_id_str, page_str = callback.data.split(":")
    order_id, page = int(order_id_str), int(page_str)
    o = db.get_order(order_id)
    if not o or o["user_id"] != callback.from_user.id:
        await callback.answer("سفارش پیدا نشد.", show_alert=True)
        return
    icon = ORDER_STATUS_ICON.get(o["status"], "⚪️")
    status_titles = {
        "pending": "در انتظار بررسی/پرداخت",
        "approved": "پرداخت تایید شد (در حال انجام)",
        "fulfilled": "تحویل داده شد",
        "rejected": "رد شده",
        "pending_price": "در انتظار تعیین قیمت توسط ادمین",
    }
    text = (
        f"{icon} <b>سفارش #{o['id']}</b>\n\n"
        f"محصول: {o['title']}\n"
        f"گیرنده/کیف‌پول: {o.get('recipient') or '-'}\n"
        f"مبلغ: {fmt_money(o['price'])}\n"
        f"وضعیت: {status_titles.get(o['status'], o['status'])}\n"
        f"روش پرداخت: {o.get('payment_method') or '-'}"
    )
    rows = []
    if o.get("product_key"):
        rows.append([InlineKeyboardButton(text="🔁 سفارش مجدد", callback_data=f"reorder:{o['product_key']}:{o['id']}", style="success")])
    rows.append([InlineKeyboardButton(text="🔙 برگشت به لیست", callback_data=f"acc_orders_page:{page}", style="primary")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("reorder:"))
async def acc_reorder(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    key = parts[1]
    old_order_id = int(parts[2]) if len(parts) > 2 else None
    product = db.get_product(key)
    if not product or not product["active"]:
        await callback.answer("این محصول دیگه موجود نیست.", show_alert=True)
        return
    flow = STEP_FLOWS.get(product["category"], ["recipient", "discount", "payment", "proof"])
    flow = list(flow)
    reused_recipient = None
    if old_order_id:
        old_order = db.get_order(old_order_id)
        if old_order:
            reused_recipient = old_order.get("recipient")
    start_idx = flow.index("payment") if "payment" in flow else 0
    await state.update_data(
        category=product["category"], product_key=key, title=product["title"], unit_price=product["price"],
        steps=flow, step_idx=start_idx, quantity=1, recipient=reused_recipient, discount_code=None, discount_percent=0, extra={},
        buyer_id=callback.from_user.id, buyer_username=callback.from_user.username or "",
    )
    await callback.message.answer(f"📋 <b>{product['title']}</b>\n\n{product['description']}")
    await advance_step(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "acc_track_order")
async def acc_track_order_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AccountFlow.waiting_track_id)
    await callback.message.answer("شماره سفارشت رو بفرست (مثلا 42):")
    await callback.answer()


@router.message(AccountFlow.waiting_track_id)
async def acc_track_order_show(message: Message, state: FSMContext):
    await state.clear()
    if not message.text.strip().isdigit():
        await message.answer("فقط شماره سفارش (عدد) بفرست.")
        return
    order = db.get_order(int(message.text.strip()))
    if not order or order["user_id"] != message.from_user.id:
        await message.answer("همچین سفارشی برای تو پیدا نشد.")
        return
    status_map = {"pending": "🟡 در انتظار", "approved": "🟢 تایید شده", "fulfilled": "✅ تحویل شده", "rejected": "🔴 رد شده", "pending_price": "🟡 در انتظار قیمت‌گذاری"}
    await message.answer(
        f"📦 سفارش #{order['id']}\n"
        f"محصول: {order['title']}\n"
        f"وضعیت: {status_map.get(order['status'], order['status'])}\n"
        f"مبلغ: {fmt_money(order['price'])}"
    )


# ---------- Run Bot ----------

async def nightly_report_task(bot: Bot):
    import datetime as _dt
    while True:
        now = _dt.datetime.utcnow() + _dt.timedelta(hours=3, minutes=30)
        target = now.replace(hour=23, minute=55, second=0, microsecond=0)
        if now >= target:
            target += _dt.timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        try:
            s = db.today_stats()
            with db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT title, COUNT(*) c, SUM(price) s FROM orders "
                    "WHERE status IN ('approved','fulfilled') AND DATE(created_at,'unixepoch','+3 hours','+30 minutes')=DATE('now','+3 hours','+30 minutes') "
                    "GROUP BY title ORDER BY s DESC LIMIT 10"
                ).fetchall()
            lines = [f"🌙 <b>گزارش شبانه</b>\n", f"👥 کاربر جدید: {s['new_users']}", f"📦 سفارش موفق: {s['orders']}", f"💰 مجموع فروش: {s['revenue']:,} تومان\n", "🏆 محصولات پرفروش:"]
            for row in rows:
                lines.append(f"• {row['title']} — {row['c']} عدد — {row['s']:,} تومان")
            await send_report(bot, "topic_nightly", "\n".join(lines))
        except Exception as e:
            log.warning("nightly report failed: %s", e)


async def backup_task(bot: Bot):
    from aiogram.types import FSInputFile
    while True:
        await asyncio.sleep(4 * 60 * 60)
        try:
            thread_id = db.get_text("topic_backup", "")
            await bot.send_document(
                REPORT_GROUP_ID,
                FSInputFile("bot.db"),
                caption=f"💾 بک‌آپ خودکار ربات — {jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}",
                message_thread_id=int(thread_id) if thread_id else None,
            )
        except Exception as e:
            log.warning("backup task failed: %s", e)


async def main():
    db.init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    @dp.error()
    async def global_error_handler(event):
        exception = event.exception
        log.exception("Unhandled error: %s", exception)
        return True

    dp.include_router(router)

    log.info("Starting Bot...")
    dp.include_router(admin_router)
    dp.include_router(ticket_router)
    dp.include_router(stats_router)
    dp.include_router(wheel_router)
    asyncio.create_task(backup_task(bot))
    asyncio.create_task(nightly_report_task(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
