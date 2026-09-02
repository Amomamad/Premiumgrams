import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"❌ متغیر {name} تو فایل .env تنظیم نشده. اول اسکریپت setup.py رو اجرا کن یا دستی .env رو بساز.")
        sys.exit(1)
    return val


BOT_TOKEN = _required("BOT_TOKEN")
BOT_USERNAME = _required("BOT_USERNAME")
ADMIN_IDS = [int(x) for x in _required("ADMIN_IDS").split(",") if x.strip()]
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "")
WALLET_TRX = os.getenv("WALLET_TRX", "")
WALLET_TON = os.getenv("WALLET_TON", "")
TON_API_KEY = os.getenv("TON_API_KEY", "")
DB_PATH = os.getenv("DB_PATH", "bot.db")
REFERRAL_PERCENT = int(os.getenv("REFERRAL_PERCENT", "5"))
NFT_GIFT_FEE_PERCENT = int(os.getenv("NFT_GIFT_FEE_PERCENT", "5"))
MIN_STARS_AMOUNT = int(os.getenv("MIN_STARS_AMOUNT", "50"))
MIN_REACTION_AMOUNT = int(os.getenv("MIN_REACTION_AMOUNT", "10"))
CARD_NUMBER = os.getenv("CARD_NUMBER", "کارت تنظیم نشده")
CARD_OWNER = os.getenv("CARD_OWNER", "تنظیم نشده")
ORDER_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID", "")
REPORT_CHANNEL_ID = os.getenv("REPORT_CHANNEL_ID", "")
REPORT_TOPIC_ID = os.getenv("REPORT_TOPIC_ID", "")
MINIAPP_DOMAIN = os.getenv("MINIAPP_DOMAIN", "")
