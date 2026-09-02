from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
)
import db
import os as _os

_MINIAPP_HTML_PATH = "/root/shop_bot/webapp/index.html"

def miniapp_url() -> str:
    """URL مینی‌اپ رو با یه نسخه‌ی خودکار (بر اساس زمان آخرین تغییر index.html) برمی‌گردونه،
    تا کش تلگرام هر بار که فایل عوض میشه خودکار باطل بشه، بدون نیاز به دستی عوض کردن عدد."""
    try:
        mtime = int(_os.path.getmtime(_MINIAPP_HTML_PATH))
    except OSError:
        mtime = 0
    return f"https://bot.kingiran.site?v={mtime}"

MENU_DEFAULTS = {
    "menu_buy": "🛍 خرید محصول",
    "menu_account": "👤 حساب کاربری",
    "menu_topup": "💳 شارژ حساب",
    "menu_orders": "📦 سفارش‌های من",
    "menu_referral": "🧑‍🤝‍🧑 زیرمجموعه‌گیری",
    "menu_wheel": "🎰 گردونه شانس",
    "menu_support": "☎️ پشتیبانی",
}

def t(key: str) -> str:
    return db.get_text(key, MENU_DEFAULTS[key])

CATEGORY_TITLES = {
    "premium": "🌟 تلگرام پرمیوم",
    "gift": "🎁 گیفت‌ها",
    "stars": "⭐️ استارز",
    "reaction": "❤️ ری‌اکشن استارزی",
    "ton": "💎 ارز TON",
    "trx": "🔺 ارز ترون",
    "nft_gift": "🖼 گیفت NFT",
}

CATEGORY_ICONS = {
    "premium": "5875148320397070635",
    "gift": "5449800250032143374",
    "stars": "4994520423732348068",
    "reaction": "5451636889717062286",
    "ton": "5377620962390857342",
    "trx": "4997067511137567958",
    "nft_gift": "5451937962629544243",
}

def product_icon(key: str, category: str, title: str = "") -> str | None:
    if key == "premium_1m":
        return "5305642863902604489"
    if key == "premium_3m":
        return "5305783000095537258"
    if "12m" in key or "ساله" in title:
        return "5305763715692377402"
    if "6m" in key or "شیش ماهه" in title or "شش ماهه" in title or "6 ماهه" in title:
        return "5305642863902604489"
    if "3m" in key or "سه ماهه" in title or "3 ماهه" in title:
        return "5305783000095537258"
    return CATEGORY_ICONS.get(category)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("menu_buy"), style="success", icon_custom_emoji_id="5197434882321567830")],
            [KeyboardButton(text=t("menu_account"), style="primary", icon_custom_emoji_id="5332724926216428039"),
             KeyboardButton(text=t("menu_topup"), style="success", icon_custom_emoji_id="5443127283898405358")],
            [KeyboardButton(text=t("menu_orders"), style="primary", icon_custom_emoji_id="5312361253610475399"),
             KeyboardButton(text=t("menu_referral"), style="primary", icon_custom_emoji_id="5399909394525737759")],
            [KeyboardButton(text=t("menu_wheel"), style="danger", icon_custom_emoji_id="5310278924616356636")],
            [KeyboardButton(text=t("menu_support"), style="primary", icon_custom_emoji_id="5197269100878907942")],
        ],
        resize_keyboard=True,
    )

def admin_extra_button() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("menu_buy"), style="success", icon_custom_emoji_id="5197434882321567830")],
            [KeyboardButton(text=t("menu_account"), style="primary", icon_custom_emoji_id="5332724926216428039"),
             KeyboardButton(text=t("menu_topup"), style="success", icon_custom_emoji_id="5443127283898405358")],
            [KeyboardButton(text=t("menu_orders"), style="primary", icon_custom_emoji_id="5312361253610475399"),
             KeyboardButton(text=t("menu_referral"), style="primary", icon_custom_emoji_id="5399909394525737759")],
            [KeyboardButton(text=t("menu_wheel"), style="danger", icon_custom_emoji_id="5310278924616356636")],
            [KeyboardButton(text=t("menu_support"), style="primary", icon_custom_emoji_id="5197269100878907942")],
            [KeyboardButton(text="🛠 پنل مدیریت", style="danger")],
        ],
        resize_keyboard=True,
    )

def catalog_categories_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    palette = ["primary", "success", "danger"]
    buttons = [InlineKeyboardButton(text=cat["title"], callback_data=f"cat:{cat['key']}",
                                     style=palette[i % 3], icon_custom_emoji_id=CATEGORY_ICONS.get(cat["key"]))
               for i, cat in enumerate(categories)]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="🎁 گیفت‌های ویژه (موجودی زنده)", web_app=WebAppInfo(url=miniapp_url()), style="success")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def products_kb(products: list[dict]) -> InlineKeyboardMarkup:
    palette = ["primary", "success", "danger"]
    buttons = [InlineKeyboardButton(text=p["title"], callback_data=f"prod:{p['key']}", style=palette[i % 3],
                                     icon_custom_emoji_id=product_icon(p["key"], p.get("category", ""), p.get("title", "")))
               for i, p in enumerate(products)]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="بازگشت به دسته‌بندی‌ها", callback_data="back_categories", style="primary", icon_custom_emoji_id="5875257365321749131")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def recipient_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="برای خودم", callback_data="recipient:self", style="primary", icon_custom_emoji_id="5195033767969839232")],
        [InlineKeyboardButton(text="برای شخص دیگه", callback_data="recipient:other", style="primary", icon_custom_emoji_id="5257980374868311346")],
        [InlineKeyboardButton(text="🔙 برگشت", callback_data="step_back", style="primary")],
    ])

def discount_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="دارم، وارد می‌کنم", callback_data="discount:yes", style="success", icon_custom_emoji_id="5445353829304387411")],
        [InlineKeyboardButton(text="ندارم، رد شو", callback_data="discount:no", style="danger", icon_custom_emoji_id="5197269100878907942")],
        [InlineKeyboardButton(text="🔙 برگشت", callback_data="step_back", style="primary")],
    ])

def payment_method_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👛 کیف‌پول داخلی", callback_data="pay:wallet", style="primary", icon_custom_emoji_id="5332455502917949981")],
        [InlineKeyboardButton(text="کارت به کارت (ریالی)", callback_data="pay:card", style="primary", icon_custom_emoji_id="5224257782013769471")],
        [InlineKeyboardButton(text="ترون (TRX)", callback_data="pay:trx", style="primary", icon_custom_emoji_id="4997067511137567958")],
        [InlineKeyboardButton(text="تون (TON)", callback_data="pay:ton", style="primary", icon_custom_emoji_id="5377620962390857342")],
        [InlineKeyboardButton(text="🔙 برگشت", callback_data="step_back", style="primary")],
    ])

def confirm_order_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تایید و ثبت سفارش", callback_data="confirm_order", style="success")],
        [InlineKeyboardButton(text="انصراف", callback_data="cancel_order", style="danger")],
    ])

def topup_method_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="کارت به کارت (ریالی)", callback_data="topup:card", style="primary", icon_custom_emoji_id="5224257782013769471")],
        [InlineKeyboardButton(text="ترون (TRX)", callback_data="topup:trx", style="primary", icon_custom_emoji_id="4997067511137567958")],
        [InlineKeyboardButton(text="تون (TON)", callback_data="topup:ton", style="primary", icon_custom_emoji_id="5377620962390857342")],
    ])

def admin_order_actions_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="تایید پرداخت", callback_data=f"adm_order:approve:{order_id}", style="success"),
            InlineKeyboardButton(text="رد کردن", callback_data=f"adm_order:reject:{order_id}", style="danger"),
        ],
        [InlineKeyboardButton(text="تحویل داده شد", callback_data=f"adm_order:done:{order_id}", style="primary")],
    ])

def admin_order_after_approve_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تحویل داده شد", callback_data=f"adm_order:done:{order_id}", style="primary")],
    ])

def admin_topup_actions_kb(topup_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="تایید شارژ", callback_data=f"adm_topup:approve:{topup_id}", style="success"),
            InlineKeyboardButton(text="رد کردن", callback_data=f"adm_topup:reject:{topup_id}", style="danger"),
        ],
    ])

def admin_panel_kb() -> InlineKeyboardMarkup:
    items = [
        ("🎁 کدهای هدیه و ابزارها", "admin_gift_menu", "primary"),
        ("📢 پیام مستقیم به کاربر", "btn_direct_msg", "primary"),
        ("📢 کانال جوین اجباری", "btn_set_channel", "primary"),
        ("🧾 سفارش‌های در انتظار", "adm:pending_orders", "primary"),
        ("💰 شارژهای در انتظار", "adm:pending_topups", "primary"),
        ("💸 تسویه زیرمجموعه", "btn_withdraw_list", "primary"),
        ("📦 مدیریت محصولات", "adm:products", "primary"),
        ("➕ افزودن محصول", "adm:add_product", "success"),
        ("🗂 مدیریت دسته‌بندی‌ها", "adm:categories", "primary"),
        ("➕ افزودن دسته‌بندی", "adm:add_category", "success"),
        ("🎫 کدهای تخفیف", "adm:discounts", "primary"),
        ("✏️ ویرایش متن‌ها", "adm:texts", "primary"),
        ("📊 آمار پیشرفته", "adm:advanced_stats", "primary"),
        ("📜 سفارش‌های تکمیل‌شده", "adm_completed_orders:0", "primary"),
    ]
    buttons = [InlineKeyboardButton(text=t, callback_data=c, style=s) for t, c, s in items]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_products_kb(products: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        s = "success" if p["active"] else "danger"
        status = "🟢" if p["active"] else "🔴"
        rows.append([InlineKeyboardButton(text=f"{status} {p['title']} — {p['price']:,}", callback_data=f"adm_prod:{p['key']}", style=s)])
    rows.append([InlineKeyboardButton(text="بازگشت", callback_data="adm:back", style="primary", icon_custom_emoji_id="5875257365321749131")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_product_edit_kb(key: str, active: int) -> InlineKeyboardMarkup:
    toggle_text = "🔴 غیرفعال کردن" if active else "🟢 فعال کردن"
    toggle_style = "danger" if active else "success"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش اسم", callback_data=f"adm_prod_title:{key}", style="primary")],
        [InlineKeyboardButton(text="✏️ ویرایش قیمت", callback_data=f"adm_prod_price:{key}", style="primary")],
        [InlineKeyboardButton(text="✏️ ویرایش توضیحات", callback_data=f"adm_prod_desc:{key}", style="primary")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"adm_prod_toggle:{key}", style=toggle_style)],
        [InlineKeyboardButton(text="بازگشت به لیست محصولات", callback_data="adm:products", style="primary", icon_custom_emoji_id="5875257365321749131")],
    ])

def admin_categories_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for c in categories:
        s = "success" if c["active"] else "danger"
        status = "🟢" if c["active"] else "🔴"
        rows.append([InlineKeyboardButton(text=f"{status} {c['title']}", callback_data=f"adm_cat:{c['key']}", style=s)])
    rows.append([InlineKeyboardButton(text="➕ افزودن دسته‌بندی جدید", callback_data="adm:add_category", style="success")])
    rows.append([InlineKeyboardButton(text="بازگشت", callback_data="adm:back", style="primary", icon_custom_emoji_id="5875257365321749131")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_category_edit_kb(key: str, active: int) -> InlineKeyboardMarkup:
    toggle_text = "🔴 غیرفعال کردن" if active else "🟢 فعال کردن"
    toggle_style = "danger" if active else "success"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش نام", callback_data=f"adm_cat_rename:{key}", style="primary")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"adm_cat_toggle:{key}", style=toggle_style)],
        [InlineKeyboardButton(text="بازگشت به لیست دسته‌بندی‌ها", callback_data="adm:categories", style="primary", icon_custom_emoji_id="5875257365321749131")],
    ])

def category_pick_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=c["title"], callback_data=f"adm_newprod_cat:{c['key']}", style="primary")]
            for c in categories]
    rows.append([InlineKeyboardButton(text="🔙 انصراف", callback_data="adm:back", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ref_wallet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="انتقال درآمد به کیف‌پول اصلی", callback_data="ref_to_wallet", style="success")],
        [InlineKeyboardButton(text="درخواست واریز به کارت", callback_data="ref_to_card", style="primary")],
    ])
