import requests

TRONSCAN_API = "https://apilist.tronscanapi.com/api/transaction-info"
TONCENTER_API = "https://toncenter.com/api/v2/getTransactions"
BITPIN_TICKERS_API = "https://api.bitpin.ir/api/v1/mkt/tickers/"


def get_bitpin_price(symbol: str):
    try:
        resp = requests.get(BITPIN_TICKERS_API, timeout=10)
        data = resp.json()
        for item in data:
            if item.get("symbol") == symbol:
                return float(item.get("price"))
        return None
    except Exception:
        return None


def verify_trx_payment(txid: str, expected_wallet: str, expected_amount_trx: float, tolerance: float = 0.02) -> bool:
    try:
        resp = requests.get(TRONSCAN_API, params={"hash": txid}, timeout=10)
        data = resp.json()
        if not data or not data.get("confirmed"):
            return False
        if data.get("toAddress") != expected_wallet:
            return False
        amount_sun = (data.get("contractData") or {}).get("amount", 0)
        amount_trx = amount_sun / 1_000_000
        return amount_trx >= (expected_amount_trx - tolerance)
    except Exception:
        return False


def verify_ton_payment(expected_wallet: str, expected_amount_ton: float, api_key: str, expected_memo: str,
                        window_minutes: int = 120, tolerance: float = 0.02):
    """
    فقط تراکنشی رو قبول می‌کنه که هم مبلغش مچ باشه هم Memo/Comment اون دقیقاً برابر کد یکتای سفارش باشه.
    چون Memo رو خود سیستم تولید می‌کنه (نه کاربر)، دیگه با متن دلخواه قابل تقلب نیست.
    اگه پیدا شد، شناسه‌ی یکتای تراکنش (hash) رو برمی‌گردونه؛ وگرنه None.
    """
    import time
    try:
        resp = requests.get(
            TONCENTER_API,
            params={"address": expected_wallet, "limit": 30, "api_key": api_key},
            timeout=10,
        )
        data = resp.json()
        if not data.get("ok"):
            return None
        cutoff = time.time() - (window_minutes * 60)
        for tx in data.get("result", []):
            if tx.get("utime", 0) < cutoff:
                continue
            in_msg = tx.get("in_msg", {}) or {}
            msg_text = (in_msg.get("message") or "").strip()
            if msg_text != expected_memo.strip():
                continue
            try:
                value_nano = int(in_msg.get("value", 0))
            except (TypeError, ValueError):
                continue
            value_ton = value_nano / 1_000_000_000
            if value_ton >= (expected_amount_ton - tolerance):
                tx_ref = (tx.get("transaction_id") or {}).get("hash")
                if tx_ref:
                    return tx_ref
        return None
    except Exception:
        return None


TRONSCAN_TRANSFER_API = "https://apilist.tronscanapi.com/api/transfer/trx"


def find_trx_payment(expected_wallet: str, expected_amount_trx: float, window_minutes: int = 60, tolerance: float = 0.00005):
    """
    چون TRX ممو نداره، به‌جای هش، دنبال تراکنشی می‌گرده که مبلغش (با اعشار یکتا) دقیقاً مچ باشه.
    اگه پیدا شد هش تراکنش رو برمی‌گردونه، وگرنه None.
    """
    import time
    try:
        resp = requests.get(
            TRONSCAN_TRANSFER_API,
            params={"address": expected_wallet, "start": 0, "limit": 20, "direction": 1, "reverse": "true"},
            timeout=10,
        )
        data = resp.json()
        cutoff = time.time() - (window_minutes * 60)
        for tx in data.get("data", []):
            if tx.get("to") != expected_wallet:
                continue
            if not tx.get("confirmed"):
                continue
            ts = (tx.get("block_timestamp") or 0) / 1000
            if ts < cutoff:
                continue
            try:
                amount_trx = int(tx.get("amount", 0)) / 1_000_000
            except (TypeError, ValueError):
                continue
            if abs(amount_trx - expected_amount_trx) <= tolerance:
                return tx.get("hash")
        return None
    except Exception:
        return None
