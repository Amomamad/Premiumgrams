"""
اتصال به Marketapp API برای خرید خودکار استارز و پرمیوم تلگرام.
مستندات: https://api.marketapp.org/docs

نحوه کار:
1. قیمت رو از API می‌گیریم
2. درخواست خرید می‌دیم، API یه تراکنش آماده (امضا‌نشده) برمی‌گردونه
3. با کیف‌پول خودمون (از MNEMONIC تو .env) امضا و به بلاک‌چین TON ارسالش می‌کنیم

⚠️ نکته امنیتی: MNEMONIC رمز کامل کیف‌پولته. هیچ‌وقت جایی جز .env سرور خودت ذخیره‌ش نکن.
"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

MARKETAPP_BASE = "https://api.marketapp.org"
MARKETAPP_TOKEN = os.getenv("MARKETAPP_TOKEN", "")
WALLET_MNEMONIC = os.getenv("MARKETAPP_WALLET_MNEMONIC", "")


class MarketappError(Exception):
    pass


import time as _time
_gifts_cache = {"items": None, "ts": 0}
_GIFTS_CACHE_TTL = 45  # ثانیه


async def get_gifts_onsale() -> list:
    """لیست گیفت‌های واقعی موجود برای فروش رو از بازار Marketapp برمی‌گردونه (با کش کوتاه‌مدت)."""
    now = _time.time()
    if _gifts_cache["items"] is not None and (now - _gifts_cache["ts"]) < _GIFTS_CACHE_TTL:
        return _gifts_cache["items"]
    url = f"{MARKETAPP_BASE}/v1/gifts/onsale/"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(url, headers=_headers())
        except httpx.RequestError as e:
            raise MarketappError(f"خطای شبکه: {e}") from e
    if resp.status_code >= 400:
        raise MarketappError(f"Marketapp خطا داد ({resp.status_code}): {resp.text}")
    data = resp.json()
    items = data.get("items", data if isinstance(data, list) else [])
    _gifts_cache["items"] = items
    _gifts_cache["ts"] = now
    return items


_tier_cache = {}  # key -> {"items": [...], "ts": ...}
_TIER_CACHE_TTL = 45  # ثانیه
MAX_REASONABLE_TON = 500000  # بالاتر از این یعنی لیستینگ ترول/تستی (مثل قیمت‌های میلیاردی)، نادیده می‌گیریم


async def _fetch_page(sort_by: str, cursor: str = None, retries: int = 5) -> dict:
    import asyncio as _asyncio
    params = {"sort_by": sort_by}
    if cursor:
        params["cursor"] = cursor
    url = f"{MARKETAPP_BASE}/v1/gifts/onsale/"
    last_error = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=_headers(), params=params)
            if resp.status_code >= 400:
                last_error = MarketappError(f"Marketapp خطا داد ({resp.status_code}): {resp.text}")
                await _asyncio.sleep(2 * (attempt + 1))
                continue
            return resp.json()
        except httpx.RequestError as e:
            last_error = e
            await _asyncio.sleep(2 * (attempt + 1))
            continue
    raise MarketappError(f"خطای شبکه بعد از {retries} تلاش: {last_error}")


_ALL_TIERS_CACHE = {"buckets": None, "ts": 0}
_ALL_TIERS_CACHE_TTL = 45  # ثانیه


async def build_tier_buckets_progressive(tiers: list, on_tier_ready, max_pages: int = 3000):
    """
    یه‌بار مسیر صعودی رو طی می‌کنه و هر تیر محدود رو همین که کامل شد
    (نه صبر کردن برای بقیه) از طریق on_tier_ready(lo, hi, items) اعلام می‌کنه.
    بعد تیر نامحدود («بالای X تون») رو با پاس نزولی جدا می‌گیره.
    """
    bounded_tiers = sorted([(lo, hi) for (_, lo, hi) in tiers if hi < 999999], key=lambda x: x[1])
    unbounded_tiers = [(lo, hi) for (_, lo, hi) in tiers if hi >= 999999]

    buckets = {f"{lo}:{hi}": [] for lo, hi in bounded_tiers + unbounded_tiers}
    remaining = list(bounded_tiers)

    if remaining:
        cursor = None
        for _ in range(max_pages):
            data = await _fetch_page("min_bid_asc", cursor)
            items = data.get("items", [])
            if not items:
                break
            page_vals = [int(it.get("min_bid", 0)) / 1_000_000_000 for it in items]
            for it, v in zip(items, page_vals):
                if it.get("currency") not in ("GRAM", "TON") or v > MAX_REASONABLE_TON:
                    continue
                for lo, hi in remaining:
                    if lo <= v < hi:
                        buckets[f"{lo}:{hi}"].append(it)
                        break

            page_max = max(page_vals)
            still_pending = []
            for lo, hi in remaining:
                if page_max >= hi:
                    on_tier_ready(lo, hi, buckets[f"{lo}:{hi}"])
                else:
                    still_pending.append((lo, hi))
            remaining = still_pending
            if not remaining:
                break

            new_cursor = data.get("cursor")
            if not new_cursor or new_cursor == cursor:
                break
            cursor = new_cursor
        for lo, hi in remaining:
            on_tier_ready(lo, hi, buckets[f"{lo}:{hi}"])

    for lo, hi in unbounded_tiers:
        cursor = None
        for _ in range(max_pages):
            data = await _fetch_page("min_bid_desc", cursor)
            items = data.get("items", [])
            if not items:
                break
            page_vals = [int(it.get("min_bid", 0)) / 1_000_000_000 for it in items]
            for it, v in zip(items, page_vals):
                if it.get("currency") not in ("GRAM", "TON") or v > MAX_REASONABLE_TON:
                    continue
                if lo <= v < hi:
                    buckets[f"{lo}:{hi}"].append(it)
            if min(page_vals) < lo:
                break
            new_cursor = data.get("cursor")
            if not new_cursor or new_cursor == cursor:
                break
            cursor = new_cursor
        on_tier_ready(lo, hi, buckets[f"{lo}:{hi}"])

    return buckets


async def get_gifts_for_tier(lo: float, hi: float, all_tiers: list) -> list:
    """گیفت‌های یه تیر خاص رو از باکت مشترک (کش‌شده) برمی‌گردونه."""
    buckets = await get_all_tiers_buckets(all_tiers)
    return buckets.get(f"{lo}:{hi}", [])


def _headers():
    return {"Authorization": MARKETAPP_TOKEN, "Content-Type": "application/json"}


async def _post(path: str, json_body: dict | None = None) -> dict:
    url = f"{MARKETAPP_BASE}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(url, headers=_headers(), json=json_body or {})
        except httpx.RequestError as e:
            raise MarketappError(f"خطای شبکه: {e}") from e
    if resp.status_code >= 400:
        raise MarketappError(f"Marketapp خطا داد ({resp.status_code}): {resp.text}")
    return resp.json()


# ---------- قیمت و بررسی گیرنده ----------

async def get_nft_info(nft_address: str) -> dict:
    """اطلاعات یه NFT خاص رو مستقیم با آدرسش می‌گیره (بدون نیاز به گشتن تو لیست)."""
    url = f"{MARKETAPP_BASE}/v1/nfts/{nft_address}/"
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(url, headers=_headers())
        except httpx.RequestError as e:
            raise MarketappError(f"خطای شبکه: {e}") from e
    if resp.status_code >= 400:
        raise MarketappError(f"Marketapp خطا داد ({resp.status_code}): {resp.text}")
    return resp.json()


async def get_stars_price(quantity: int) -> dict:
    return await _post("/v1/fragment/stars/price/", {"quantity": quantity})


async def get_premium_price() -> dict:
    return await _post("/v1/fragment/premium/price/")


async def search_stars_recipient(username: str) -> dict:
    return await _post("/v1/fragment/stars/recipient/", {"username": username.lstrip("@")})


async def search_premium_recipient(username: str) -> dict:
    return await _post("/v1/fragment/premium/recipient/", {"username": username.lstrip("@")})


# ---------- خرید (برمی‌گردونه تراکنش آماده امضا) ----------

async def buy_stars(username: str, quantity: int, currency: str = "GRAM") -> dict:
    return await _post("/v1/fragment/stars/buy/", {
        "username": username.lstrip("@"), "quantity": quantity, "currency": currency,
    })


async def buy_premium(username: str, months: int, currency: str = "GRAM") -> dict:
    return await _post("/v1/fragment/premium/buy/", {
        "username": username.lstrip("@"), "months": months, "currency": currency,
    })


# ---------- امضا و ارسال تراکنش رو بلاک‌چین TON ----------

async def sign_and_send_transaction(api_response: dict):
    """
    خروجی buy_stars / buy_premium رو می‌گیره، با کیف‌پول ما امضا و به شبکه TON می‌فرسته.
    نیاز داره: pip install pytoniq --break-system-packages
    """
    from pytoniq.liteclient import LiteBalancer
    from pytoniq.contract import WalletV5R1
    from pytoniq_core import Cell, StateInit

    if not WALLET_MNEMONIC:
        raise MarketappError("MARKETAPP_WALLET_MNEMONIC تو .env تنظیم نشده.")

    message = api_response["transaction"]["messages"][0]
    address = message["address"]
    amount = int(message["amount"])
    body = Cell.one_from_boc(message["payload"])
    state_init = (
        StateInit.deserialize(Cell.one_from_boc(message["stateInit"]).begin_parse())
        if message.get("stateInit") else None
    )

    client = LiteBalancer.from_mainnet_config(trust_level=2)
    await client.start_up()
    try:
        wallet: WalletV5R1 = await WalletV5R1.from_mnemonic(client, mnemonics=WALLET_MNEMONIC.split(), network_global_id=-239)
        try:
            balance = await wallet.get_balance()
        except Exception:
            balance = None
        fee_buffer = 50_000_000  # حدود ۰.۰۵ TON برای کارمزد شبکه
        if balance is not None and balance < (amount + fee_buffer):
            raise MarketappError(
                f"موجودی کیف‌پول کافی نیست. موجودی فعلی: {balance / 1e9:.4f} TON، "
                f"مبلغ لازم: {(amount + fee_buffer) / 1e9:.4f} TON"
            )
        await wallet.transfer(destination=address, amount=amount, body=body, state_init=state_init)
    finally:
        await client.close_all()


async def purchase_stars(username: str, quantity: int) -> None:
    """کل فرآیند: خرید + امضا + ارسال. اگه خطا بده Exception پرتاب می‌کنه."""
    resp = await buy_stars(username, quantity)
    await sign_and_send_transaction(resp)


async def purchase_premium(username: str, months: int) -> None:
    resp = await buy_premium(username, months)
    await sign_and_send_transaction(resp)
