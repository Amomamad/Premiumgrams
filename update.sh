#!/bin/bash
# اجرا کن هر وقت خواستی آخرین آپدیت‌ها رو از گیت‌هاب بگیری
set -e

echo "📥 در حال دریافت آخرین تغییرات..."
git pull

echo "📦 در حال نصب/آپدیت پکیج‌ها..."
source venv/bin/activate
pip install -r requirements.txt --break-system-packages --quiet

echo "🔍 بررسی سینتکس..."
python3 -m py_compile bot.py keyboards.py db.py crypto_verify.py marketapp.py admin_handlers.py admin_stats.py lucky_wheel.py ticketing.py

echo "🔄 ری‌استارت سرویس..."
sudo systemctl restart shopbot

echo "✅ آپدیت با موفقیت انجام شد."
sudo systemctl status shopbot --no-pager
