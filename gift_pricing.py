LIVE_GIFTS_MARKUP = 1.15  # باید همیشه با مقدار bot.py هماهنگ باشه

LIVE_GIFTS_PRICE_TIERS = [
    ("زیر ۵ تون", 0, 5),
    ("زیر ۱۰ تون", 5, 10),
    ("زیر ۱۵ تون", 10, 15),
    ("زیر ۲۰ تون", 15, 20),
    ("۲۰ تا ۱۰۰ تون", 20, 100),
]


def fragment_image_url(name: str):
    if "#" not in name:
        return None
    label, num = name.rsplit("#", 1)
    slug = label.strip().lower().replace(" ", "")
    return f"https://nft.fragment.com/gift/{slug}-{num.strip()}.large.jpg"


def fragment_sticker_id(name: str):
    if "#" not in name:
        return None
    label, num = name.rsplit("#", 1)
    slug = label.strip().lower().replace(" ", "")
    return f"{slug}-{num.strip()}"
