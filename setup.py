#!/usr/bin/env python3
"""
اسکریپت نصب اولیه.
اجرا کن: python3 setup.py
یه فایل .env می‌سازه با سوال از تو، و پروژه رو آماده‌ی اجرا می‌کنه.
"""
import os

ENV_PATH = ".env"

QUESTIONS = [
    ("BOT_TOKEN", "توکن بات (از @BotFather)", True),
    ("BOT_USERNAME", "یوزرنیم بات (بدون @)", True),
    ("ADMIN_IDS", "آیدی عددی ادمین(ها)، اگه چندتاست با کاما جدا کن", True),
    ("SUPPORT_USERNAME", "یوزرنیم پشتیبانی (بدون @)", False),
    ("WALLET_TRX", "آدرس کیف‌پول ترون (TRX) برای دریافت پرداخت", False),
    ("WALLET_TON", "آدرس کیف‌پول تون (TON) برای دریافت پرداخت", False),
    ("TON_API_KEY", "کلید API تون‌سنتر (از ربات @tonapibot بگیر)", False),
    ("CARD_NUMBER", "شماره کارت برای پرداخت ریالی", False),
    ("CARD_OWNER", "نام صاحب کارت", False),
    ("ORDER_CHANNEL_ID", "آیدی عددی کانال ثبت سفارشات (اختیاری)", False),
    ("REPORT_CHANNEL_ID", "آیدی عددی کانال گزارش‌ها (اختیاری)", False),
    ("REPORT_TOPIC_ID", "آیدی تاپیک گزارش‌ها داخل اون کانال (اختیاری)", False),
    ("MINIAPP_DOMAIN", "دامین مینی‌اپ (اگه استفاده می‌کنی، بدون https://)", False),
    ("MARKETAPP_TOKEN", "توکن Marketapp (برای خرید خودکار استارز/پرمیوم/گیفت)", False),
    ("MARKETAPP_WALLET_MNEMONIC", "24 کلمه‌ی Mnemonic کیف‌پول اختصاصی Marketapp (با فاصله از هم)", False),
]


def main():
    print("=" * 50)
    print("نصب ربات فروشگاهی - تنظیمات اولیه")
    print("=" * 50)
    print("برای هر سوال، مقدارشو بنویس و Enter بزن.")
    print("اگه سوال اختیاریه و نمی‌خوای الان پرش کنی، فقط Enter بزن (بعداً می‌تونی تو .env دستی اضافه‌ش کنی).\n")

    if os.path.exists(ENV_PATH):
        confirm = input("⚠️ فایل .env از قبل وجود داره. بازنویسی بشه؟ (y/n): ").strip().lower()
        if confirm != "y":
            print("لغو شد.")
            return

    lines = []
    for key, prompt, required in QUESTIONS:
        while True:
            suffix = " (اجباری)" if required else " (اختیاری، Enter برای رد کردن)"
            val = input(f"{prompt}{suffix}: ").strip()
            if val or not required:
                break
            print("این مورد اجباریه، لطفاً مقداری وارد کن.")
        lines.append(f'{key}="{val}"')

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n✅ فایل .env ساخته شد.")
    print("حالا این دستورات رو بزن تا بات بالا بیاد:\n")
    print("  python3 -m venv venv")
    print("  source venv/bin/activate")
    print("  pip install -r requirements.txt --break-system-packages")
    print("  python3 -m py_compile bot.py && echo OK")
    print("  # بعد سرویس systemd رو تنظیم و استارت کن (به README.md نگاه کن)")


if __name__ == "__main__":
    main()
