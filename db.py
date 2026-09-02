import sqlite3
import time
import json
from contextlib import contextmanager

from config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER NOT NULL DEFAULT 0,
            referred_by INTEGER,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            key TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            price INTEGER NOT NULL DEFAULT 0,
            unit TEXT NOT NULL DEFAULT 'ثابت',
            active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            category TEXT NOT NULL,
            product_key TEXT,
            title TEXT NOT NULL,
            recipient TEXT,
            quantity INTEGER,
            price INTEGER NOT NULL,
            discount_code TEXT,
            payment_method TEXT NOT NULL DEFAULT 'wallet',
            status TEXT NOT NULL DEFAULT 'pending',
            admin_note TEXT,
            extra TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS topups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            amount INTEGER NOT NULL,
            method TEXT NOT NULL,
            proof TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bot_texts (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            key TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 100,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS discount_codes (
            code TEXT PRIMARY KEY,
            percent INTEGER NOT NULL,
            max_uses INTEGER NOT NULL DEFAULT 0,
            used_count INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        );
        """)
        conn.commit()
    seed_categories()
    seed_products()


def seed_products():
    defaults = [
        ("premium_1m", "premium", "تلگرام پرمیوم ۱ ماهه",
         "فعال‌سازی اشتراک پرمیوم یک ماهه برای یوزرنیم دلخواه.\n"
         "مزایا: بدون تبلیغات، آپلود فایل تا ۴ گیگ، استیکر و ری‌اکشن اختصاصی، دانلود سریع‌تر.",
         380000, "ثابت", 1),
        ("premium_3m", "premium", "تلگرام پرمیوم ۳ ماهه",
         "فعال‌سازی اشتراک پرمیوم سه ماهه برای یوزرنیم دلخواه.\n"
         "مزایا: بدون تبلیغات، آپلود فایل تا ۴ گیگ، استیکر و ری‌اکشن اختصاصی، دانلود سریع‌تر.",
         950000, "ثابت", 2),
        ("premium_12m", "premium", "تلگرام پرمیوم ۱۲ ماهه",
         "فعال‌سازی اشتراک پرمیوم یک‌ساله برای یوزرنیم دلخواه.\n"
         "مزایا: بدون تبلیغات، آپلود فایل تا ۴ گیگ، استیکر و ری‌اکشن اختصاصی، دانلود سریع‌تر، مقرون‌به‌صرفه‌ترین حالت.",
         2900000, "ثابت", 3),
        ("gift_teddy", "gift", "گیفت خرس تدی 🧸",
         "ارسال گیفت خرس تدی به یوزرنیم دلخواه. یک هدیه ساده و بامزه داخل تلگرام.",
         250000, "ثابت", 4),
        ("stars", "stars", "استارز تلگرام ⭐",
         "خرید استارز تلگرام با هر مقدار دلخواه (حداقل ۵۰ عدد).\n"
         "مزایا: خرج داخل بازی‌ها و ربات‌ها، تبدیل به تبلیغ کانال، هدیه به دیگران.",
         1300, "به ازای هر عدد", 5),
        ("reaction", "reaction", "ری‌اکشن استارزی روی پست ⭐️❤️",
         "ارسال ری‌اکشن استارزی برای پست یک کانال (حداقل ۵ عدد).",
         1400, "به ازای هر عدد", 6),
        ("ton", "ton", "خرید ارز TON 💎",
         "خرید ارز دیجیتال TON و واریز به کیف‌پول دلخواه شما.",
         95000, "به ازای هر عدد TON", 7),
        ("trx", "trx", "خرید ارز ترون (TRX) 🔺",
         "خرید ارز دیجیتال ترون و واریز به کیف‌پول دلخواه شما.",
         12000, "به ازای هر عدد TRX", 8),
        ("nft_gift", "nft_gift", "خرید گیفت NFT 🎁",
         "لینک گیفت NFT مورد نظرت رو بفرست، قیمتش رو با ۵٪ کارمزد بهت اعلام می‌کنیم.",
         0, "بر اساس لینک", 9),
    ]
    with get_conn() as conn:
        for key, category, title, desc, price, unit, order in defaults:
            conn.execute(
                """INSERT OR IGNORE INTO products
                   (key, category, title, description, price, unit, active, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (key, category, title, desc, price, unit, order),
            )
        conn.commit()


def get_or_create_user(user_id: int, username: str, referred_by: int | None = None) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            if username and row["username"] != username:
                conn.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
                conn.commit()
            return dict(row)
        now = int(time.time())
        ref = referred_by if (referred_by and referred_by != user_id) else None
        conn.execute(
            "INSERT INTO users (user_id, username, balance, referred_by, created_at) VALUES (?, ?, 0, ?, ?)",
            (user_id, username, ref, now),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone())


def get_user(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def change_balance(user_id: int, delta: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
        conn.commit()


def count_referrals(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) c FROM users WHERE referred_by = ?", (user_id,)).fetchone()
        return row["c"]


def list_products(category: str | None = None, only_active: bool = True) -> list[dict]:
    q = "SELECT * FROM products WHERE 1=1"
    params = []
    if category:
        q += " AND category = ?"
        params.append(category)
    if only_active:
        q += " AND active = 1"
    q += " ORDER BY sort_order ASC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_product(key: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM products WHERE key = ?", (key,)).fetchone()
        return dict(row) if row else None


def update_product(key: str, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [key]
    with get_conn() as conn:
        conn.execute(f"UPDATE products SET {keys} WHERE key = ?", values)
        conn.commit()


def create_order(user_id, username, category, product_key, title, recipient, quantity,
                  price, discount_code=None, payment_method="wallet", extra=None) -> int:
    now = int(time.time())
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO orders
               (user_id, username, category, product_key, title, recipient, quantity, price,
                discount_code, payment_method, status, extra, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (user_id, username, category, product_key, title, recipient, quantity, price,
             discount_code, payment_method, json.dumps(extra or {}), now, now),
        )
        conn.commit()
        return cur.lastrowid


def get_order(order_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None


def list_orders(user_id: int | None = None, status: str | None = None, limit: int = 20, offset: int = 0) -> list[dict]:
    q = "SELECT * FROM orders WHERE 1=1"
    params = []
    if user_id is not None:
        q += " AND user_id = ?"
        params.append(user_id)
    if status:
        q += " AND status = ?"
        params.append(status)
    q += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.append(limit)
    params.append(offset)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def count_orders(user_id: int | None = None, status: str | None = None) -> int:
    q = "SELECT COUNT(*) c FROM orders WHERE 1=1"
    params = []
    if user_id is not None:
        q += " AND user_id = ?"
        params.append(user_id)
    if status:
        q += " AND status = ?"
        params.append(status)
    with get_conn() as conn:
        return conn.execute(q, params).fetchone()["c"]


def update_order(order_id: int, **fields):
    fields["updated_at"] = int(time.time())
    keys = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [order_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE orders SET {keys} WHERE id = ?", values)
        conn.commit()


def create_topup(user_id, username, amount, method, proof=None) -> int:
    now = int(time.time())
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO topups (user_id, username, amount, method, proof, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (user_id, username, amount, method, proof, now, now),
        )
        conn.commit()
        return cur.lastrowid


def get_topup(topup_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM topups WHERE id = ?", (topup_id,)).fetchone()
        return dict(row) if row else None


def update_topup(topup_id: int, **fields):
    fields["updated_at"] = int(time.time())
    keys = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [topup_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE topups SET {keys} WHERE id = ?", values)
        conn.commit()


def get_discount(code: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM discount_codes WHERE code = ? AND active = 1", (code,)).fetchone()
        return dict(row) if row else None


def create_discount(code: str, percent: int, max_uses: int = 0):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO discount_codes (code, percent, max_uses, used_count, active) VALUES (?, ?, ?, 0, 1)",
            (code, percent, max_uses),
        )
        conn.commit()


def use_discount(code: str):
    with get_conn() as conn:
        conn.execute("UPDATE discount_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
        conn.commit()


def list_discounts() -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM discount_codes ORDER BY code").fetchall()]


def deactivate_discount(code: str):
    with get_conn() as conn:
        conn.execute("UPDATE discount_codes SET active = 0 WHERE code = ?", (code,))
        conn.commit()


def stats() -> dict:
    with get_conn() as conn:
        users_count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        orders_count = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
        pending_orders = conn.execute("SELECT COUNT(*) c FROM orders WHERE status='pending'").fetchone()["c"]
        pending_topups = conn.execute("SELECT COUNT(*) c FROM topups WHERE status='pending'").fetchone()["c"]
        total_sales = conn.execute(
            "SELECT COALESCE(SUM(price),0) s FROM orders WHERE status IN ('approved','fulfilled')"
        ).fetchone()["s"]
        return {
            "users": users_count,
            "orders": orders_count,
            "pending_orders": pending_orders,
            "pending_topups": pending_topups,
            "total_sales": total_sales,
        }


def seed_categories():
    defaults = [
        ("premium", "🌟 تلگرام پرمیوم", 1),
        ("gift", "🎁 گیفت‌ها", 2),
        ("stars", "⭐️ استارز", 3),
        ("reaction", "❤️ ری‌اکشن استارزی", 4),
        ("ton", "💎 ارز TON", 5),
        ("trx", "🔺 ارز ترون", 6),
        ("nft_gift", "🖼 گیفت NFT", 7),
    ]
    with get_conn() as conn:
        for key, title, order in defaults:
            conn.execute(
                "INSERT OR IGNORE INTO categories (key, title, sort_order, active) VALUES (?, ?, ?, 1)",
                (key, title, order),
            )
        conn.commit()


def list_categories(only_active: bool = True) -> list[dict]:
    q = "SELECT * FROM categories"
    if only_active:
        q += " WHERE active = 1"
    q += " ORDER BY sort_order ASC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q).fetchall()]


def get_category(key: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM categories WHERE key = ?", (key,)).fetchone()
        return dict(row) if row else None


def create_category(key: str, title: str, sort_order: int = 100) -> bool:
    with get_conn() as conn:
        existing = conn.execute("SELECT 1 FROM categories WHERE key = ?", (key,)).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO categories (key, title, sort_order, active) VALUES (?, ?, ?, 1)",
            (key, title, sort_order),
        )
        conn.commit()
        return True


def update_category(key: str, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [key]
    with get_conn() as conn:
        conn.execute(f"UPDATE categories SET {keys} WHERE key = ?", values)
        conn.commit()


def create_product(key: str, category: str, title: str, description: str,
                    price: int, unit: str = "ثابت", sort_order: int = 100) -> bool:
    with get_conn() as conn:
        existing = conn.execute("SELECT 1 FROM products WHERE key = ?", (key,)).fetchone()
        if existing:
            return False
        conn.execute(
            """INSERT INTO products (key, category, title, description, price, unit, active, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            (key, category, title, description, price, unit, sort_order),
        )
        conn.commit()
        return True


def get_text(key: str, default: str) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM bot_texts WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_text(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO bot_texts (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()


def list_texts(defaults: dict) -> list[dict]:
    result = []
    with get_conn() as conn:
        rows = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM bot_texts").fetchall()}
    for key, default in defaults.items():
        result.append({"key": key, "value": rows.get(key, default)})
    return result


def total_spent(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COALESCE(SUM(price),0) s FROM orders WHERE user_id=? AND status IN ('approved','fulfilled')", (user_id,)).fetchone()
        return row["s"]


def purchase_level(user_id: int) -> int:
    spent = total_spent(user_id)
    return spent // 500000 + 1


def top_referrers(limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT referred_by AS uid, COUNT(*) c FROM users WHERE referred_by IS NOT NULL "
            "GROUP BY referred_by ORDER BY c DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for r in rows:
            u = conn.execute("SELECT username FROM users WHERE user_id=?", (r["uid"],)).fetchone()
            result.append({"user_id": r["uid"], "username": u["username"] if u else "", "count": r["c"]})
        return result
