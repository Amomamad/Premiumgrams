# ربات فروشگاهی تلگرام

فروش پرمیوم تلگرام، استارز، ری‌اکشن، ارز TON/TRX، و گیفت NFT — با تحویل خودکار، تایید پرداخت بلاکچینی، و پنل مدیریت کامل.

## نصب اولیه

### ۱. کلون کردن پروژه
```bash
git clone <لینک-ریپازیتوری-شما>
cd shop_bot
```

### ۲. ساخت محیط پایتون
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt --break-system-packages
```

### ۳. تنظیمات (اجرای ویزارد نصب)
```bash
python3 setup.py
```
این اسکریپت از تو می‌پرسه:
- توکن بات (از @BotFather بگیر)
- آیدی عددی ادمین(ها)
- آدرس کیف‌پول‌های TRX/TON برای دریافت پرداخت
- کلید API تون‌سنتر (از @tonapibot)
- شماره کارت برای پرداخت ریالی
- آیدی کانال سفارشات/گزارشات (اختیاری)
- دامین مینی‌اپ (اگه داری)
- تنظیمات Marketapp (اگه می‌خوای تحویل خودکار استارز/پرمیوم/گیفت داشته باشی)

می‌تونی به‌جاش دستی `.env.example` رو کپی کنی به `.env` و مقادیر رو ویرایش کنی:
```bash
cp .env.example .env
nano .env
```

### ۴. تست و اجرا
```bash
python3 -m py_compile bot.py && echo OK
python3 bot.py
```

### ۵. اجرای دائمی با systemd
یه فایل سرویس بساز:
```bash
sudo nano /etc/systemd/system/shopbot.service
```
محتوا:
```ini
[Unit]
Description=Telegram Shop Bot
After=network.target

[Service]
WorkingDirectory=/root/shop_bot
ExecStart=/root/shop_bot/venv/bin/python3 /root/shop_bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
بعد:
```bash
sudo systemctl daemon-reload
sudo systemctl enable shopbot
sudo systemctl start shopbot
```

## آپدیت گرفتن بعداً

هر وقت نسخه‌ی جدیدی منتشر شد:
```bash
./update.sh
```
این اسکریپت خودش آخرین تغییرات رو می‌گیره، پکیج‌ها رو آپدیت می‌کنه، سینتکس رو چک می‌کنه، و سرویس رو ری‌استارت می‌کنه.

## نکات امنیتی مهم
- فایل .env رو هرگز جایی آپلود نکن (شامل توکن بات، کلیدهای API، Mnemonic کیف‌پول Marketapp).
- فایل bot.db (دیتابیس) هم نباید عمومی بشه — اطلاعات مشتری‌ها توشه.
- این‌ها از قبل تو .gitignore هستن، ولی همیشه قبل از git push با git status چک کن که این فایل‌ها اضافه نشده باشن.
