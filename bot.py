import sqlite3
import asyncio
import logging
import random
import io
import os
import math
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import ExtBot
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cbtn(
    text: str,
    callback_data: str = None,
    url: str = None,
    style: str = None,
    **kwargs
) -> InlineKeyboardButton:
    if style is None and callback_data is not None:
        cd = callback_data.lower()
        if any(x in cd for x in ["cancel"]):
            style = "danger"
        elif any(x in cd for x in [
            "buy", "collect", "interest", "sell", "upgrade", "rankup",
            "feed", "feeddog", "donate", "confirm",
            "lottery_join", "lottery_draw", "produce", "factory_sell",
            "stray_", "bail", "bank_interest", "bank_deposit",
            "buyhook", "buydog",
        ]):
            style = "success"
        else:
            style = "primary"

    build_kwargs = {"text": text}
    if callback_data is not None:
        build_kwargs["callback_data"] = callback_data
    if url is not None:
        build_kwargs["url"] = url
    build_kwargs.update(kwargs)
    if style is not None:
        try:
            build_kwargs["style"] = style
        except TypeError:
            pass
    return InlineKeyboardButton(**build_kwargs)

BOT_TOKEN = "8835237722:AAFJDvXb6o48DMTPrcJPv5HwsMa97tkSj2Q"
BOT_USERNAME = "woofdoggybot"

# ═══════════════════════════════════════════════════════════════
# 🎨 Professional UI / Media Layer
# تصاویر مرحله‌ها اختیاری هستند؛ با URL یا Telegram file_id تنظیم می‌شوند.
# اگر خالی باشند، ربات به‌صورت خودکار از کارت متنی حرفه‌ای استفاده می‌کند.
# ═══════════════════════════════════════════════════════════════
STAGE_IMAGES = {
    "start": os.getenv("BOT_IMG_START", "").strip(),
    "hop": os.getenv("BOT_IMG_HOP", "").strip(),
    "levelup": os.getenv("BOT_IMG_LEVELUP", "").strip(),
    "dog": os.getenv("BOT_IMG_DOG", "").strip(),
    "hook": os.getenv("BOT_IMG_HOOK", "").strip(),
    "city": os.getenv("BOT_IMG_CITY", "").strip(),
    "auction": os.getenv("BOT_IMG_AUCTION", "").strip(),
    "lottery": os.getenv("BOT_IMG_LOTTERY", "").strip(),
    "error": os.getenv("BOT_IMG_ERROR", "").strip(),
}

UI = {
    "ok": "✅", "fail": "❌", "warn": "⚠️", "info": "💠",
    "money": "💰", "hop": "🦴", "dog": "🐕", "level": "⭐️",
    "gift": "🎁", "fire": "🔥", "city": "🏙️", "auction": "🏪",
    "lottery": "🎟️", "clock": "⏳", "lock": "🔐", "spark": "✨",
}

def ui_bar(current: int, total: int, size: int = 10) -> str:
    if total <= 0:
        return "░" * size
    ratio = max(0.0, min(1.0, current / total))
    filled = int(round(ratio * size))
    return "█" * filled + "░" * (size - filled)

async def send_stage_message(message, text: str, stage: str = None, **kwargs):
    """Send a polished text card, optionally with a configured stage image."""
    image = STAGE_IMAGES.get(stage or "", "")
    if image:
        try:
            if os.path.isfile(image):
                with open(image, "rb") as fh:
                    return await message.reply_photo(photo=fh, caption=text, **kwargs)
            return await message.reply_photo(photo=image, caption=text, **kwargs)
        except Exception:
            logger.warning("Stage image failed for %s; falling back to text", stage, exc_info=True)
    return await message.reply_text(text, **kwargs)


REFERRAL_ENABLED       = True
REFERRAL_REWARD_SENDER = 5_000
REFERRAL_REWARD_JOINER = 1_000
ADMIN_IDS = [7424803325]                              # لیست آیدی عددی مدیران


HOP_COOLDOWN    = 300
HOP_BASE_POINTS = 50

CITY_LEVELS = {
    1:  (0,       0,    0,   0,   0),
    2:  (5_000,   50,   5,   10,  5),
    3:  (20_000,  150,  15,  30,  15),
    4:  (60_000,  400,  35,  80,  40),
    5:  (150_000, 900,  80,  200, 100),
    6:  (400_000, 2000, 180, 500, 250),
    7:  (1_000_000, 5000, 400, 1200, 600),
    8:  (3_000_000, 12000, 900, 3000, 1500),
    9:  (8_000_000, 30000, 2000, 8000, 4000),
    10: (20_000_000, 80000, 5000, 20000, 10000),
}
CITY_MAX_LEVEL = 10
CITY_ADV_MAX_BUILDING_LEVEL = 5
CITY_ADV_TAX_MIN = 0
CITY_ADV_TAX_MAX = 15
CITY_ADV_DAILY_BASE = 250
CITY_ADV_POP_CAP = 5000

# 🧹 پاکسازی خودکار پیام‌های ربات در گروه‌ها
# فقط پیام‌هایی که خود ربات ارسال کرده‌اند حذف می‌شوند؛ پیام کاربران دست‌نخورده می‌ماند.
BOT_AUTO_CLEANUP_ENABLED = True
BOT_AUTO_CLEANUP_SECONDS = 300  # 5 دقیقه
BOT_AUTO_CLEANUP_BATCH = 200
# پیام‌هایی که شامل این کلیدواژه‌ها باشند مهم محسوب می‌شوند و خودکار پاک نمی‌شوند.
BOT_AUTO_CLEANUP_KEEP_KEYWORDS = (
    "آگهی", "اعلامیه", "اطلاعیه", "جنگ", "نبرد", "صلح",
    "نتیجه جنگ", "نتیجه نبرد", "اعلام جنگ", "اعلام صلح",
)
CITY_ADV_BUILDINGS = {
    "market": {"name": "🏪 بازار شهری", "base_cost": 25_000, "desc": "درآمد روزانه شهر را افزایش می‌دهد."},
    "bank": {"name": "🏦 بانک مرکزی", "base_cost": 40_000, "desc": "درآمد خزانه و پایداری اقتصاد را بیشتر می‌کند."},
    "factory": {"name": "🏭 مجتمع صنعتی", "base_cost": 50_000, "desc": "پاداش فعالیت‌های اقتصادی شهر را افزایش می‌دهد."},
    "shelter": {"name": "🐕 پناهگاه هاپوها", "base_cost": 30_000, "desc": "رضایت شهروندان را بالا می‌برد."},
    "fishing": {"name": "🎣 اسکله ماهیگیری", "base_cost": 35_000, "desc": "درآمد شهر از فعالیت‌های ماهیگیری را افزایش می‌دهد."},
}

CITY_HOP_BUFF        = 5
CITY_FISH_BUFF       = 30
CITY_STRAY_BUFF      = 0.05
HOP_LEVEL_BONUS = 0.20

LEVEL_THRESHOLDS = []
hops = 10
for i in range(1000):
    LEVEL_THRESHOLDS.append(hops)
    if i < 9:      hops += 20
    elif i < 49:   hops += 50
    elif i < 199:  hops += 100
    else:          hops += 200

DOG_MIN_LEVEL = 3
DOG_COST      = 1000
DOG_LEVEL_DATA = {
    1:  (0.10,   5_000,     1_000),
    2:  (0.20,   10_000,    2_400),
    3:  (0.35,   18_000,    5_000),
    4:  (0.55,   28_000,    9_000),
    5:  (0.80,   40_000,    16_000),
    6:  (1.10,   55_000,    26_000),
    7:  (1.50,   75_000,    40_000),
    8:  (2.00,   100_000,   60_000),
    9:  (2.60,   130_000,   90_000),
    10: (3.30,   170_000,   130_000),
    11: (4.10,   215_000,   180_000),
    12: (5.00,   265_000,   240_000),
    13: (6.00,   320_000,   316_000),
    14: (7.20,   380_000,   410_000),
    15: (8.50,   450_000,   520_000),
    16: (10.00,  530_000,   650_000),
    17: (11.80,  620_000,   800_000),
    18: (13.80,  720_000,   980_000),
    19: (16.00,  830_000,   1_180_000),
    20: (18.50,  950_000,   1_400_000),
}
DOG_MAX_LEVEL = 20
DOG_RANKS = {
    1:  ("سگ خیابونی 🐾",        1.0),
    2:  ("سگ تازه‌کار 🐶",        1.3),
    3:  ("سگ باتجربه 🐕",         1.6),
    4:  ("سگ آموزش‌دیده 🦮",      2.0),
    5:  ("سگ ماهر 🐕‍🦺",          2.5),
    6:  ("سگ نخبه 🌟🐕",          3.2),
    7:  ("سگ قهرمان 🏆🐕",        4.0),
    8:  ("سگ اسطوره 💎🐕",        5.0),
    9:  ("سگ افسانه‌ای 👑🐕",      6.5),
    10: ("سگ جاودان ✨👑🐕",      8.5),
}
BONE_COST     = 14_000
FEED_DURATION = 7200

FEED_BASE_BY_RARITY = {
    "⚪": 10 * 60,
    "🟢": 25 * 60,
    "🔵": 45 * 60,
    "🟣": 65 * 60,
    "🟠": 85 * 60,
    "🔴": 105 * 60,
    "🔥": 120 * 60,
}
FEED_WEIGHT_BONUS = 15 * 60


HOOK_MIN_LEVEL = 2
HOOK_DATA = {
    1:  (600,   3600,  0),
    2:  (0,     3300,  1_600),
    3:  (0,     2700,  3_600),
    4:  (0,     2400,  7_000),
    5:  (0,     2100,  12_000),
    6:  (0,     1800,  20_000),
    7:  (0,     1500,  32_000),
    8:  (0,     1200,  50_000),
    9:  (0,     1050,  76_000),
    10: (0,     900,   110_000),
    11: (0,     750,   160_000),
    12: (0,     600,   230_000),
    13: (0,     480,   320_000),
    14: (0,     360,   440_000),
    15: (0,     300,   600_000),
}
HOOK_MAX_LEVEL = 15
BONE_SELL_TIME = 120

CRISIS_TYPES = {
    "fire": {
        "name": "🔥 آتش‌سوزی",
        "desc": "بخشی از شهر آتش گرفته! باید سریع اقدام کنی.",
        "penalty": "کاهش ۲۰٪ خزانه و ضعف ۳۰ دقیقه کولداون هاپ",
        "treasury_cost": 0.15,
        "fix_cooldown": 1800,
        "penalty_type": "hop_cooldown",
        "penalty_value": 60,
        "reward": 8_000,
        "timeout": 600,
    },
    "blackout": {
        "name": "⚡ قطعی برق",
        "desc": "برق کل شهر قطع شده! کارخانه‌ها متوقف شدن.",
        "penalty": "توقف تولید کارخانه‌ها به مدت ۴۵ دقیقه",
        "treasury_cost": 0.10,
        "fix_cooldown": 2700,
        "penalty_type": "factory_freeze",
        "penalty_value": 2700,
        "reward": 6_000,
        "timeout": 600,
    },
    "pollution": {
        "name": "☣️ آلودگی شهر",
        "desc": "آلودگی شدید! سگ‌ها نمی‌تونن کار کنن.",
        "penalty": "توقف درآمد سگ‌ها به مدت ۱ ساعت",
        "treasury_cost": 0.08,
        "fix_cooldown": 3600,
        "penalty_type": "dog_freeze",
        "penalty_value": 3600,
        "reward": 5_000,
        "timeout": 600,
    },
    "factory_breakdown": {
        "name": "🏭 خرابی کارخانه‌ها",
        "desc": "ماشین‌آلات کارخانه‌ها خراب شدن!",
        "penalty": "۵۰٪ کاهش سرعت تولید برای ۱ ساعت",
        "treasury_cost": 0.12,
        "fix_cooldown": 3600,
        "penalty_type": "factory_slow",
        "penalty_value": 3600,
        "reward": 7_000,
        "timeout": 600,
    },
    "dog_disease": {
        "name": "🤒 بیماری سگ‌ها",
        "desc": "یه بیماری واگیر بین سگ‌های شهر پخش شده!",
        "penalty": "۳۰٪ کاهش درآمد سگ‌ها برای ۴۵ دقیقه",
        "treasury_cost": 0.06,
        "fix_cooldown": 2700,
        "penalty_type": "dog_slow",
        "penalty_value": 2700,
        "reward": 4_000,
        "timeout": 600,
    },
}

CRISIS_TRIGGER_CHANCE = 0.08
CRISIS_MIN_TREASURY   = 2_000

BONES_TABLE = [
    ("استخوان کوچیک 🦴",              0.1,   0.3,    1,    50, "⚪"),
    ("استخوان مرغ 🍗",                0.2,   0.5,    1,    80, "⚪"),
    ("استخوان گربه 🐱",               0.2,   0.6,    1,    110, "⚪"),
    ("استخوان سگ 🐩",                 0.3,   0.8,    1,    150, "⚪"),
    ("استخوان گاو 🐄",                0.4,   1.2,    1,    200, "⚪"),
    ("استخوان خوک 🐷",                0.5,   1.5,    1,    250, "⚪"),
    ("استخوان بز 🐐",                 0.5,   1.6,    1,    280, "⚪"),
    ("استخوان گوسفند 🐑",             0.6,   1.8,    2,    320, "⚪"),
    ("استخوان دنده 🦷",               0.7,   2.0,    2,    370, "⚪"),
    ("استخوان ران 🦵",                0.8,   2.3,    2,    430, "⚪"),
    ("استخوان آهو 🦌",                1.0,   2.8,    2,    500, "⚪"),
    ("استخوان گراز 🐗",               1.1,   3.0,    2,    560, "⚪"),
    ("استخوان اسب 🐴",                0.9,   2.5,    2,    520, "⚪"),
    ("استخوان خرگوش 🐇",              0.1,   0.3,    1,    70, "⚪"),
    ("استخوان روباه 🦊",              0.4,   1.0,    1,    170, "⚪"),

    ("استخوان خرس 🐻",               1.3,   3.5,    3,    750, "🟢"),
    ("استخوان پلنگ 🐆",              1.5,   4.0,    3,    950, "🟢"),
    ("استخوان کروکودیل 🐊",          1.8,   4.5,    3,    1_200, "🟢"),
    ("استخوان شیر 🦁",               2.0,   5.0,    3,    1_500, "🟢"),
    ("استخوان کرگدن 🦏",             2.2,   5.5,    3,    1_800, "🟢"),
    ("استخوان فیل 🐘",               2.5,   6.0,    4,    2_200, "🟢"),
    ("استخوان دایناسور 🦕",          2.8,   6.5,    4,    2_700, "🟢"),
    ("استخوان ماستادون 🦣",          3.2,   7.5,    4,    3_300, "🟢"),
    ("استخوان گوریل غول‌پیکر 🦍",    3.5,   8.0,    4,    4_000, "🟢"),
    ("استخوان هیپوپوتاموس 🦛",       2.8,   7.0,    4,    3_600, "🟢"),
    ("استخوان عقاب طلایی 🦅",        1.8,   4.8,    3,    1_600, "🟢"),

    ("استخوان نهنگ 🐋",              4.0,   9.0,    5,    5_000, "🔵"),
    ("استخوان کوسه 🦈",              4.5,   10.0,   5,    6_200, "🔵"),
    ("استخوان مارماهی غول‌آسا 🐍",   5.0,   11.0,   5,    7_500, "🔵"),
    ("استخوان کراکن 🐙",             5.5,   12.0,   5,    9_000, "🔵"),
    ("استخوان ماموت 🦣",             6.0,   13.0,   6,    11_000, "🔵"),
    ("استخوان گرگ عظیم 🐺",          6.5,   14.0,   6,    13_500, "🔵"),
    ("استخوان ببر دندان‌شمشیری 🐯",  7.0,   15.0,   6,    16_000, "🔵"),
    ("استخوان مگالودون 🦷",          7.5,   16.0,   6,    19_000, "🔵"),
    ("استخوان اژدمار دریایی 🌊",     6.8,   14.5,   6,    17_000, "🔵"),
    ("استخوان غول غار 🗿",           5.8,   12.5,   5,    8_200, "🔵"),

    ("استخوان غول 👾",               8.0,   17.0,   7,    23_000, "🟣"),
    ("استخوان سیمرغ 🦅",            9.0,   19.0,   7,    28_000, "🟣"),
    ("استخوان گریفین 🦁",            10.0,  21.0,   7,    34_000, "🟣"),
    ("استخوان هیدرا 🐲",             11.0,  23.0,   7,    41_000, "🟣"),
    ("استخوان اژدها 🐉",             12.0,  25.0,   8,    50_000, "🟣"),
    ("استخوان ققنوس 🔥",             13.5,  28.0,   8,    60_000, "🟣"),
    ("استخوان لویاتان 🌊",           15.0,  31.0,   8,    72_000, "🟣"),
    ("استخوان فضایی 🛸",             16.5,  34.0,   9,    86_000, "🟣"),
    ("استخوان موجود فضایی 👽",       18.0,  37.0,   9,    102_000, "🟣"),
    ("استخوان بهموت 🔱",             20.0,  40.0,   9,    120_000, "🟣"),
    ("استخوان اژدهای یخ 🧊",         14.0,  29.0,   8,    65_000, "🟣"),
    ("استخوان ققنوس تاریک 🖤",        17.0,  35.0,   9,    95_000, "🟣"),

    ("استخوان افسانه‌ای ✨",          23.0,  46.0,   10,   145_000, "🟠"),
    ("استخوان تایتان ⚙️",            26.0,  52.0,   10,   175_000, "🟠"),
    ("استخوان خدایان 👑",            30.0,  60.0,   10,   210_000, "🟠"),
    ("استخوان دیو باستانی 🏺",       34.0,  68.0,   11,   250_000, "🟠"),
    ("استخوان کیهانی 🌌",            38.0,  76.0,   11,   300_000, "🟠"),
    ("استخوان سیاهچاله 🕳️",          43.0,  86.0,   11,   360_000, "🟠"),
    ("استخوان اهریمن 😈",            48.0,  95.0,   12,   430_000, "🟠"),
    ("استخوان شیطان بزرگ 🩸",        54.0,  105.0,  12,   510_000, "🟠"),
    ("استخوان نمرود 🏛️",             60.0,  115.0,  12,   600_000, "🟠"),
    ("استخوان جن عظیم 🧿",           42.0,  82.0,   11,   340_000, "🟠"),
    ("استخوان ستاره مرده ⭐",         56.0,  108.0,  12,   570_000, "🟠"),

    ("استخوان فرشته 😇",             68.0,  128.0,  13,   700_000, "🔴"),
    ("استخوان سرافیم 🌠",            76.0,  144.0,  13,   850_000, "🔴"),
    ("استخوان آغازین ⚡️",            85.0,  160.0,  13,   1_020_000, "🔴"),
    ("استخوان ازلی 🌀",              95.0,  180.0,  14,   1_220_000, "🔴"),
    ("استخوان خالق 🌟",              108.0, 200.0,  14,   1_450_000, "🔴"),
    ("استخوان عرش 🕊️",              122.0, 225.0,  14,   1_720_000, "🔴"),
    ("استخوان آتش ازلی 🔥",          140.0, 260.0,  15,   2_100_000, "🔥"),
    ("استخوان فنا 💀",               162.0, 300.0,  15,   2_600_000, "🔥"),
    ("استخوان هستی ☀️",              188.0, 350.0,  15,   3_200_000, "🔥"),
    ("استخوان خدای خدایان 🌋",       220.0, 420.0,  15,   4_200_000, "🔥"),
    ("استخوان ملک‌الموت ☠️",          72.0,  136.0,  13,   790_000, "🔴"),
    ("استخوان نور ابدی 💫",           100.0, 190.0,  14,   1_350_000, "🔴"),
    ("استخوان اژدهای کیهانی 🌠",     250.0, 480.0,  15,   5_500_000, "🔥"),
]

RARITY_ICON_MAP = {
    "⚪": "عادی",
    "🟢": "غیرمعمول",
    "🔵": "نادر",
    "🟣": "حماسی",
    "🟠": "اسطوره‌ای",
    "🔴": "کمیاب",
    "🔥": "آتشی",
}

RARITY_WEIGHTS_BY_LEVEL = {
    1:  (100, 0,  0,  0,  0,  0,  0),
    2:  (90,  10, 0,  0,  0,  0,  0),
    3:  (75,  20, 5,  0,  0,  0,  0),
    4:  (65,  22, 10, 3,  0,  0,  0),
    5:  (55,  25, 13, 5,  2,  0,  0),
    6:  (48,  25, 15, 8,  4,  0,  0),
    7:  (40,  24, 18, 11, 5,  2,  0),
    8:  (35,  22, 18, 13, 7,  4,  1),
    9:  (30,  21, 18, 14, 9,  5,  3),
    10: (28,  20, 17, 14, 10, 7,  4),
    11: (25,  20, 16, 14, 11, 8,  6),
    12: (22,  19, 16, 14, 12, 10, 7),
    13: (20,  18, 15, 14, 13, 11, 9),
    14: (17,  17, 15, 14, 13, 13, 11),
    15: (15,  15, 14, 13, 13, 13, 17),
}
RARITY_ORDER = ["⚪", "🟢", "🔵", "🟣", "🟠", "🔴", "🔥"]

def get_bone_rarity(bone_name: str) -> str:
    for bone in BONES_TABLE:
        if bone[0] == bone_name:
            return bone[5]
    return "⚪"

def calc_feed_duration(bone_name: str, weight: float) -> int:
    rarity_icon = get_bone_rarity(bone_name)
    base = FEED_BASE_BY_RARITY.get(rarity_icon, FEED_BASE_BY_RARITY["⚪"])
    bonus = int(weight * FEED_WEIGHT_BONUS)
    return base + bonus

def catch_bone(hook_level: int):
    weights = RARITY_WEIGHTS_BY_LEVEL.get(hook_level, RARITY_WEIGHTS_BY_LEVEL[15])
    available_icons = []
    available_weights = []
    for i, icon in enumerate(RARITY_ORDER):
        if weights[i] == 0:
            continue
        has_bone = any(b[5] == icon and b[3] <= hook_level for b in BONES_TABLE)
        if has_bone:
            available_icons.append(icon)
            available_weights.append(weights[i])

    chosen_rarity = random.choices(available_icons, weights=available_weights, k=1)[0]

    pool = [b for b in BONES_TABLE if b[5] == chosen_rarity and b[3] <= hook_level]
    max_price = max(b[4] for b in pool)
    inner_weights = [max(1.0, (max_price / b[4]) ** 1.5) for b in pool]
    bone = random.choices(pool, weights=inner_weights, k=1)[0]

    name, w_min, w_max, _, base_price, rarity_icon = bone
    weight = round(random.uniform(w_min, w_max), 2)
    price  = int(base_price * (weight / w_min))
    rarity_name = RARITY_ICON_MAP.get(chosen_rarity, "")
    return name, weight, price, chosen_rarity, rarity_name

BANK_MIN_LEVEL       = 4
BANK_OPEN_COST       = 10_000
BANK_INTEREST_RATE   = 0.03
BANK_MAX_INTEREST    = 325_000
BANK_NUM_CHANGE_COST = 1_250
BANK_NUM_CHANGE_CD   = 72 * 3600

TRANSFER_MIN       = 50
TRANSFER_MAX       = 500_000
TRANSFER_MIN_LEVEL = 2
TRANSFER_COOLDOWN  = 30

STRAY_CHANCE       = 0.30
STRAY_MAX_TRIES    = 3
STRAY_BASE_COST    = 600
STRAY_COST_MULT    = 2.0
STRAY_TRIGGER_HOPS = 20

JAIL_DURATION     = 1800
BAIL_COST_PER_MIN = 100
JAIL_WORK_INTERVAL  = 300
JAIL_WORK_EARN      = 50
JAIL_ESCAPE_CHANCE  = 0.25

SPAM_WINDOW    = 3
SPAM_THRESHOLD = 3
SPAM_JAIL_BASE = 300

SMUGGLE_BASE_CATCH  = 0.10
SMUGGLE_CATCH_PER   = 0.10
SMUGGLE_REWARD_EACH = 800
SMUGGLE_JAIL_MINS   = 30

FACTORY_MIN_LEVEL  = 7
FACTORY_BUILD_COST = 20_000
FACTORY_WORKER_COST = 5_000

WAREHOUSE_LEVELS = {
    1:  (20,   0),
    2:  (40,   6_000),
    3:  (80,   16_000),
    4:  (150,  36_000),
    5:  (280,  80_000),
    6:  (500,  180_000),
    7:  (900,  400_000),
    8:  (1600, 900_000),
    9:  (2800, 2_000_000),
    10: (5000, 5_000_000),
}
WAREHOUSE_MAX_LEVEL = 10

MACHINE_LEVELS = {
    1:  (120, 0),
    2:  (90,  10_000),
    3:  (70,  24_000),
    4:  (55,  50_000),
    5:  (42,  110_000),
    6:  (32,  240_000),
    7:  (24,  520_000),
    8:  (18,  1_160_000),
    9:  (13,  2_600_000),
    10: (9,   6_000_000),
}
MACHINE_MAX_LEVEL = 10

FACTORY_LEVEL_EXP = {
    1:  100,
    2:  300,
    3:  700,
    4:  1_500,
    5:  3_000,
    6:  6_000,
    7:  12_000,
    8:  25_000,
    9:  50_000,
    10: 0,
}
FACTORY_MAX_LEVEL = 10
FACTORY_DAILY_CAP   = 5_000_000
FACTORY_SELL_TAX    = 0.10

FACTORY_PRODUCTS = [
    ("نخ میویی 🧵",            200,     400,     1,  5),
    ("پشمک پیشی 🍭",           350,     700,     1,  8),
    ("چرم گربه 🐾",            500,     950,     1,  10),
    ("جوراب پیشی 🧦",          800,     1_600,   2,  16),
    ("کلاه میویی 🎩",          1_200,   2_400,   2,  22),
    ("عطر پیشی 🌸",            2_000,   4_200,   3,  38),
    ("صابون میویی 🧼",         1_500,   3_100,   3,  28),
    ("کنسرو ماهی 🐟",          3_000,   6_500,   4,  58),
    ("شامپو پشمالو 🛁",        2_500,   5_200,   4,  46),
    ("ابزار چنگول 🔧",         5_000,   11_000,  5,  95),
    ("دستکش میویی 🧤",         4_000,   8_500,   5,  76),
    ("باتری پیشی ⚡",          8_000,   17_500,  6,  150),
    ("چیپ میویی 💾",           12_000,  26_000,  6,  220),
    ("ربات پیشی 🤖",           20_000,  45_000,  7,  380),
    ("موشک میویی 🚀",          35_000,  78_000,  7,  650),
    ("فضاپیمای پشمالو 🛸",    60_000,  45_000,  8,  1_100),
    ("کریستال میویی 💎",       80_000,  60_000,  8,  1_500),
    ("پورتال پیشی 🌀",         150_000, 113_000, 9,  2_800),
    ("قلب میویی افسانه‌ای ✨", 300_000, 230_000, 10, 6_000),
]

MARKET_PRICE_MIN = 0.6
MARKET_PRICE_MAX = 2.2

def get_db():
    conn = sqlite3.connect("happy_bot.db", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

class db_conn:
    def __enter__(self):
        self.conn = get_db()
        return self.conn
    def __exit__(self, *_):
        try:
            self.conn.close()
        except Exception:
            pass

def init_economy_ledger():
    """Create an append-only economy ledger used for auditing critical movements."""
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS economy_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            asset TEXT NOT NULL,
            amount REAL NOT NULL,
            balance_before REAL,
            balance_after REAL,
            action TEXT NOT NULL,
            counterparty_id INTEGER,
            reference_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_economy_ledger_user_time ON economy_ledger(user_id, created_at)")
        conn.commit()

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER PRIMARY KEY,
        username   TEXT,
        first_name TEXT,
        hop_points REAL DEFAULT 0,
        total_hops INTEGER DEFAULT 0,
        level      INTEGER DEFAULT 1,
        last_hop   TEXT DEFAULT NULL,
        joined_at  TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS dogs (
        user_id      INTEGER PRIMARY KEY,
        name         TEXT DEFAULT 'سگولو',
        level        INTEGER DEFAULT 1,
        rank         INTEGER DEFAULT 1,
        points_box   REAL DEFAULT 0,
        fed_until    TEXT DEFAULT NULL,
        last_collect TEXT DEFAULT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS groups (
        group_id    INTEGER PRIMARY KEY,
        title       TEXT,
        level       INTEGER DEFAULT 1,
        treasury    REAL DEFAULT 0,
        total_hops  INTEGER DEFAULT 0,
        total_dogs  INTEGER DEFAULT 0,
        total_bones INTEGER DEFAULT 0,
        total_fish  INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS hooks (
        user_id   INTEGER PRIMARY KEY,
        level     INTEGER DEFAULT 1,
        last_cast TEXT DEFAULT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS pending_bones (
        user_id   INTEGER PRIMARY KEY,
        bone_name TEXT,
        weight    REAL,
        price     INTEGER,
        caught_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS bank (
        user_id         INTEGER PRIMARY KEY,
        balance         REAL DEFAULT 0,
        account_number  TEXT UNIQUE,
        opened_at       TEXT DEFAULT CURRENT_TIMESTAMP,
        last_interest   TEXT DEFAULT NULL,
        last_num_change TEXT DEFAULT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS transfers (
        user_id       INTEGER PRIMARY KEY,
        last_transfer TEXT DEFAULT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS stray_dogs (
        group_id     INTEGER PRIMARY KEY,
        tries_left   INTEGER DEFAULT 3,
        current_cost INTEGER DEFAULT 300,
        appeared_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        rescuer_ids  TEXT DEFAULT ''
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_strays (
        user_id INTEGER PRIMARY KEY,
        count   INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS jail (
        user_id     INTEGER PRIMARY KEY,
        jailed_at   TEXT,
        release_at  TEXT,
        reason      TEXT DEFAULT 'قاچاق',
        work_points INTEGER DEFAULT 0,
        last_work   TEXT    DEFAULT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS factories (
        user_id         INTEGER PRIMARY KEY,
        level           INTEGER DEFAULT 1,
        exp             INTEGER DEFAULT 0,
        warehouse_level INTEGER DEFAULT 1,
        machine_level   INTEGER DEFAULT 1,
        stock           INTEGER DEFAULT 0,
        last_produced   TEXT    DEFAULT NULL,
        producing       INTEGER DEFAULT 0,
        product_idx     INTEGER DEFAULT 0,
        production_end  TEXT    DEFAULT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS market_prices (
        product_idx INTEGER PRIMARY KEY,
        multiplier  REAL    DEFAULT 1.0,
        updated_at  TEXT    DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS bot_cleanup_messages (
        chat_id    INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        delete_at  TEXT NOT NULL,
        PRIMARY KEY (chat_id, message_id)
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bot_cleanup_delete_at ON bot_cleanup_messages(delete_at)")
    conn.commit()
    conn.close()

    conn = get_db()
    for table, col, definition in [
        ("groups", "total_fish", "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            conn.commit()
        except Exception:
            pass
    conn.close()
    conn2 = get_db()
    conn2.execute("""CREATE TABLE IF NOT EXISTS sub_admins (
        user_id    INTEGER PRIMARY KEY,
        username   TEXT,
        first_name TEXT,
        added_by   INTEGER,
        added_at   TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn2.execute("""CREATE TABLE IF NOT EXISTS lotteries (
        lottery_id   TEXT PRIMARY KEY,
        title        TEXT,
        prize        INTEGER DEFAULT 0,
        winner_count INTEGER DEFAULT 1,
        state        TEXT DEFAULT 'open',
        created_by   INTEGER,
        created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
        end_at       TEXT DEFAULT NULL
    )""")
    conn2.execute("""CREATE TABLE IF NOT EXISTS lottery_entries (
        lottery_id TEXT,
        user_id    INTEGER,
        username   TEXT,
        first_name TEXT,
        joined_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (lottery_id, user_id)
    )""")
    conn2.commit()
    conn2.close()

    conn3 = get_db()
    conn3.execute("""CREATE TABLE IF NOT EXISTS user_market (
        listing_id   TEXT PRIMARY KEY,
        seller_id    INTEGER,
        seller_name  TEXT,
        title        TEXT,
        description  TEXT,
        content      TEXT,
        price        INTEGER,
        max_buyers   INTEGER DEFAULT 1,
        buyer_count  INTEGER DEFAULT 0,
        status       TEXT DEFAULT 'pending',
        created_at   TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn3.execute("""CREATE TABLE IF NOT EXISTS user_market_buyers (
        listing_id TEXT,
        buyer_id   INTEGER,
        bought_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (listing_id, buyer_id)
    )""")
    conn3.execute("""CREATE TABLE IF NOT EXISTS bot_settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )""")
    conn3.execute("""CREATE TABLE IF NOT EXISTS referrals (
        user_id    INTEGER PRIMARY KEY,
        inviter_id INTEGER,
        rewarded   INTEGER DEFAULT 0,
        joined_at  TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn3.commit()
    conn3.close()

    conn4 = get_db()
    conn4.execute("""CREATE TABLE IF NOT EXISTS mayor (
        group_id    INTEGER PRIMARY KEY,
        user_id     INTEGER,
        username    TEXT,
        first_name  TEXT,
        elected_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        term_end    TEXT
    )""")
    conn4.execute("""CREATE TABLE IF NOT EXISTS mayor_decrees (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id    INTEGER,
        user_id     INTEGER,
        decree_type TEXT,
        decree_name TEXT,
        issued_at   TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at  TEXT
    )""")
    conn4.execute("""CREATE TABLE IF NOT EXISTS mayor_elections (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id    INTEGER,
        status      TEXT DEFAULT 'candidacy',
        started_by  INTEGER,
        started_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        ended_at    TEXT DEFAULT NULL
    )""")
    conn4.execute("""CREATE TABLE IF NOT EXISTS mayor_candidates (
        election_id INTEGER,
        user_id     INTEGER,
        username    TEXT,
        first_name  TEXT,
        joined_at   TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (election_id, user_id)
    )""")
    conn4.execute("""CREATE TABLE IF NOT EXISTS mayor_election_votes (
        election_id    INTEGER,
        voter_id       INTEGER,
        candidate_id   INTEGER,
        voted_at       TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (election_id, voter_id)
    )""")
    conn4.execute("""CREATE TABLE IF NOT EXISTS mayor_protests (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id    INTEGER,
        user_id     INTEGER,
        username    TEXT,
        first_name  TEXT,
        reason      TEXT,
        status      TEXT DEFAULT 'pending',
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn4.execute("""CREATE TABLE IF NOT EXISTS mayor_protest_votes (
        protest_id  INTEGER,
        user_id     INTEGER,
        vote        TEXT,
        voted_at    TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (protest_id, user_id)
    )""")
    conn4.commit()
    conn4.close()

    conn5 = get_db()
    conn5.execute("""CREATE TABLE IF NOT EXISTS mayor_project_settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )""")
    conn5.execute("""CREATE TABLE IF NOT EXISTS mayor_projects (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id    INTEGER,
        project_key TEXT,
        level       INTEGER DEFAULT 1,
        started_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        done_at     TEXT,
        status      TEXT DEFAULT 'building'
    )""")
    conn5.execute("""CREATE TABLE IF NOT EXISTS mayor_contracts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id     INTEGER,
        contract_key TEXT,
        started_at   TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at   TEXT,
        status       TEXT DEFAULT 'active'
    )""")
    conn5.execute("""CREATE TABLE IF NOT EXISTS mayor_contract_settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )""")
    conn5.commit()
    conn5.close()

    conn6 = get_db()
    conn6.execute("""CREATE TABLE IF NOT EXISTS city_crises (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id     INTEGER,
        crisis_type  TEXT,
        status       TEXT DEFAULT 'active',
        started_at   TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at   TEXT,
        resolved_by  INTEGER DEFAULT NULL,
        decision     TEXT DEFAULT NULL,
        resolved_at  TEXT DEFAULT NULL
    )""")
    conn6.execute("""CREATE TABLE IF NOT EXISTS city_crisis_penalties (
        group_id     INTEGER PRIMARY KEY,
        penalty_type TEXT,
        penalty_value INTEGER,
        expires_at   TEXT
    )""")
    conn6.commit()
    conn6.close()

    logger.info("✅ دیتابیس آماده شد")
    init_mayor_full_tables()
    init_leader_tables()
    migrate_db()
    init_progression_tables()
    init_collection_tables()
    init_collection_reward_tables()
    init_trade_auction_tables()
    init_clan_tables()

def init_city_advanced_tables():
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS city_state (
            group_id INTEGER PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            population INTEGER DEFAULT 0,
            satisfaction INTEGER DEFAULT 70,
            tax_rate INTEGER DEFAULT 5,
            last_income TEXT DEFAULT NULL,
            total_income INTEGER DEFAULT 0,
            total_expense INTEGER DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS city_buildings (
            group_id INTEGER,
            building_key TEXT,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (group_id, building_key)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS city_residents (
            group_id INTEGER,
            user_id INTEGER,
            last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, user_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS city_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            kind TEXT,
            amount INTEGER DEFAULT 0,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        for gid in conn.execute("SELECT group_id FROM groups").fetchall():
            conn.execute("INSERT OR IGNORE INTO city_state (group_id) VALUES (?)", (gid[0],))
            for key in CITY_ADV_BUILDINGS:
                conn.execute("INSERT OR IGNORE INTO city_buildings (group_id, building_key, level) VALUES (?,?,0)", (gid[0], key))
        conn.commit()

def city_adv_ensure(group_id: int):
    ensure_group(group_id, "شهر هاپو")
    with db_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO city_state (group_id) VALUES (?)", (group_id,))
        for key in CITY_ADV_BUILDINGS:
            conn.execute("INSERT OR IGNORE INTO city_buildings (group_id, building_key, level) VALUES (?,?,0)", (group_id, key))
        conn.commit()

def city_adv_touch(group_id: int, user_id: int):
    city_adv_ensure(group_id)
    with db_conn() as conn:
        row = conn.execute("SELECT population FROM city_state WHERE group_id=?", (group_id,)).fetchone()
        conn.execute("INSERT OR REPLACE INTO city_residents (group_id,user_id,last_seen) VALUES (?,?,CURRENT_TIMESTAMP)", (group_id,user_id))
        count = conn.execute("SELECT COUNT(*) FROM city_residents WHERE group_id=?", (group_id,)).fetchone()[0]
        pop = min(CITY_ADV_POP_CAP, max(int(row["population"] if row else 0), count))
        conn.execute("UPDATE city_state SET population=? WHERE group_id=?", (pop,group_id))
        conn.commit()

def city_adv_building_level(group_id: int, key: str) -> int:
    city_adv_ensure(group_id)
    with db_conn() as conn:
        row=conn.execute("SELECT level FROM city_buildings WHERE group_id=? AND building_key=?",(group_id,key)).fetchone()
        return int(row["level"] if row else 0)

def city_adv_xp_needed(level: int) -> int:
    return 2500 * level * level

def city_adv_add_xp(group_id: int, amount: int):
    city_adv_ensure(group_id)
    with db_conn() as conn:
        conn.execute("UPDATE city_state SET xp=MAX(0,xp+?) WHERE group_id=?",(max(0,int(amount)),group_id))
        conn.commit()

def city_adv_income_preview(group_id: int):
    city_adv_ensure(group_id)
    with db_conn() as conn:
        st=conn.execute("SELECT * FROM city_state WHERE group_id=?",(group_id,)).fetchone()
        bs={r["building_key"]:r["level"] for r in conn.execute("SELECT * FROM city_buildings WHERE group_id=?",(group_id,)).fetchall()}
    pop=int(st["population"]); sat=int(st["satisfaction"]); tax=int(st["tax_rate"])
    market=bs.get("market",0); bank=bs.get("bank",0); factory=bs.get("factory",0); fishing=bs.get("fishing",0)
    base=CITY_ADV_DAILY_BASE + pop*20 + tax*100
    mult=1 + market*0.12 + bank*0.10 + factory*0.08 + fishing*0.06
    mult*=max(0.50,min(1.20,sat/100))
    return max(0,int(base*mult)), st, bs

async def city_adv_panel(message_obj, group_id: int, user_id: int):
    city_adv_touch(group_id,user_id)
    with db_conn() as conn:
        grp=conn.execute("SELECT * FROM groups WHERE group_id=?",(group_id,)).fetchone()
        st=conn.execute("SELECT * FROM city_state WHERE group_id=?",(group_id,)).fetchone()
        bs=conn.execute("SELECT building_key,level FROM city_buildings WHERE group_id=?",(group_id,)).fetchall()
    lvl=get_city_level(grp); income,_,_=city_adv_income_preview(group_id)
    xp=int(st["xp"]); next_xp=city_adv_xp_needed(lvl) if lvl < CITY_MAX_LEVEL else None
    bmap={r["building_key"]:r["level"] for r in bs}
    pop=int(st["population"]); sat=int(st["satisfaction"]); tax=int(st["tax_rate"])
    txt=(f"🏙️ *شهر هاپو — نسخه پیشرفته*\n\n"
         f"🎖 سطح شهر: *{lvl}/{CITY_MAX_LEVEL}*\n"
         f"👥 جمعیت فعال: *{pop:,}*\n"
         f"😊 رضایت: *{sat}%*\n"
         f"💰 خزانه: *{grp['treasury']:,.0f}* هاپ\n"
         f"🧾 مالیات شهری: *{tax}%*\n"
         f"📈 XP مدیریت: *{xp:,}*" + (f" / {next_xp:,}" if next_xp else " (MAX)") + "\n\n"
         f"📊 درآمد تقریبی روزانه: *{income:,}* هاپ\n\n"
         f"🏗 ساختمان‌ها:\n"
         f"🏪 بازار: {bmap.get('market',0)}/5 | 🏦 بانک: {bmap.get('bank',0)}/5\n"
         f"🏭 صنعت: {bmap.get('factory',0)}/5 | 🐕 پناهگاه: {bmap.get('shelter',0)}/5\n"
         f"🎣 اسکله: {bmap.get('fishing',0)}/5")
    kb=[[cbtn("🏗 ساختمان‌ها",callback_data=f"cityadv_build_{group_id}"),cbtn("💰 خزانه",callback_data=f"cityadv_treasury_{group_id}")],
        [cbtn("📊 اقتصاد",callback_data=f"cityadv_economy_{group_id}"),cbtn("😊 رضایت",callback_data=f"cityadv_sat_{group_id}")],
        [cbtn("🧾 مالیات",callback_data=f"cityadv_tax_{group_id}"),cbtn("📜 تاریخچه",callback_data=f"cityadv_log_{group_id}")]]
    await message_obj.reply_text(txt,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))

async def city_adv_cmd(update, context):
    chat=update.effective_chat; user=update.effective_user
    if chat.type=="private":
        await update.message.reply_text("🏙️ سیستم شهر فقط داخل گروه فعاله!"); return True
    city_adv_touch(chat.id,user.id)
    parts=update.message.text.strip().replace("\u200c"," ").split()
    if len(parts)==1:
        await city_adv_panel(update.message,chat.id,user.id); return True
    action=parts[1].lower()
    if action in ("ساختمان","build","ساخت"):
        if len(parts)<3:
            await update.message.reply_text("🏗 مثال: *شهر ساختمان بازار*",parse_mode="Markdown"); return True
        key=parts[2]
        aliases={"بازار":"market","بانک":"bank","صنعت":"factory","کارخانه":"factory","پناهگاه":"shelter","سگ":"shelter","اسکله":"fishing","ماهیگیری":"fishing"}
        key=aliases.get(key,key)
        if key not in CITY_ADV_BUILDINGS:
            await update.message.reply_text("❌ ساختمان ناشناخته. گزینه‌ها: بازار، بانک، صنعت، پناهگاه، اسکله"); return True
        lvl=city_adv_building_level(chat.id,key)
        if lvl>=CITY_ADV_MAX_BUILDING_LEVEL:
            await update.message.reply_text("🏆 این ساختمان به حداکثر سطح رسیده!"); return True
        cost=CITY_ADV_BUILDINGS[key]["base_cost"]*(lvl+1)**2
        with db_conn() as conn:
            grp=conn.execute("SELECT treasury FROM groups WHERE group_id=?",(chat.id,)).fetchone()
            if grp["treasury"]<cost:
                await update.message.reply_text(f"❌ خزانه کافی نیست.\n💰 لازم: {cost:,}\n🏦 موجود: {grp['treasury']:,.0f}"); return True
            conn.execute("UPDATE groups SET treasury=treasury-? WHERE group_id=?",(cost,chat.id))
            conn.execute("UPDATE city_buildings SET level=level+1 WHERE group_id=? AND building_key=?",(chat.id,key))
            conn.execute("UPDATE city_state SET xp=xp+?,satisfaction=MIN(100,satisfaction+2),total_expense=total_expense+? WHERE group_id=?",(cost//100,cost,chat.id))
            conn.execute("INSERT INTO city_ledger(group_id,user_id,kind,amount,description) VALUES(?,?,?,?,?)",(chat.id,user.id,"expense",cost,f"ارتقای {CITY_ADV_BUILDINGS[key]['name']} به سطح {lvl+1}"))
            conn.commit()
        await update.message.reply_text(f"🏗 *ساختمان ارتقا یافت!*\n\n{CITY_ADV_BUILDINGS[key]['name']} → سطح *{lvl+1}*\n💸 هزینه: {cost:,} هاپ\n😊 رضایت +2",parse_mode="Markdown"); return True
    if action in ("مالیات","tax"):
        if len(parts)<3:
            with db_conn() as conn: st=conn.execute("SELECT tax_rate FROM city_state WHERE group_id=?",(chat.id,)).fetchone()
            await update.message.reply_text(f"🧾 مالیات فعلی شهر: *{st['tax_rate']}%*\nبرای تغییر: *شهر مالیات 8*",parse_mode="Markdown"); return True
        try: rate=int(parts[2])
        except: await update.message.reply_text("❌ عدد وارد کن."); return True
        if not CITY_ADV_TAX_MIN<=rate<=CITY_ADV_TAX_MAX:
            await update.message.reply_text(f"❌ مالیات باید بین {CITY_ADV_TAX_MIN}% تا {CITY_ADV_TAX_MAX}% باشد."); return True
        with db_conn() as conn:
            old=conn.execute("SELECT tax_rate FROM city_state WHERE group_id=?",(chat.id,)).fetchone()["tax_rate"]
            conn.execute("UPDATE city_state SET tax_rate=? WHERE group_id=?",(rate,chat.id)); conn.commit()
        delta=rate-old
        with db_conn() as conn: conn.execute("UPDATE city_state SET satisfaction=MAX(0,MIN(100,satisfaction-?)) WHERE group_id=?",(max(0,delta*2),chat.id)); conn.commit()
        await update.message.reply_text(f"🧾 مالیات شهر روی *{rate}%* تنظیم شد.\n{'😊 رضایت افزایش یافت.' if delta<0 else '⚠️ مالیات بالاتر رضایت را کاهش می‌دهد.'}",parse_mode="Markdown"); return True
    if action in ("خزانه","treasury"):
        income,st,bs=city_adv_income_preview(chat.id)
        await update.message.reply_text(f"🏦 *گزارش خزانه*\n\n💰 موجودی: *{(grp:=get_db().execute('SELECT treasury FROM groups WHERE group_id=?',(chat.id,)).fetchone())['treasury']:,.0f}*\n📈 درآمد تخمینی روزانه: *{income:,}*\n💵 کل درآمد ثبت‌شده: *{st['total_income']:,}*\n💸 کل هزینه: *{st['total_expense']:,}*",parse_mode="Markdown"); return True
    await city_adv_panel(update.message,chat.id,user.id); return True

async def city_adv_callback(update, context):
    q=update.callback_query; data=q.data; user=q.from_user
    if not data.startswith("cityadv_"): return False
    await q.answer(); parts=data.split("_"); action=parts[1]; gid=int(parts[2])
    city_adv_touch(gid,user.id)
    if action=="build":
        lines=[]; kb=[]
        for key,d in CITY_ADV_BUILDINGS.items():
            lvl=city_adv_building_level(gid,key); nxt=lvl+1
            cost=d["base_cost"]*nxt*nxt if lvl<5 else 0
            lines.append(f"{d['name']}: *{lvl}/5* — {cost:,} هاپ" if lvl<5 else f"{d['name']}: *MAX*")
            if lvl<5: kb.append([cbtn(f"⬆️ {d['name']}",callback_data=f"cityadv_up_{gid}_{key}")])
        kb.append([cbtn("🔙 شهر",callback_data=f"cityadv_home_{gid}")])
        await q.edit_message_text("🏗 *مدیریت ساختمان‌ها*\n\n"+"\n".join(lines),parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb)); return True
    if action=="up":
        if not update.effective_chat or update.effective_chat.type not in ("group", "supergroup"):
            await q.answer("❌ این عملیات فقط داخل گروه مجاز است.", show_alert=True); return True
        if not await _is_group_admin(context, gid, user.id):
            await q.answer("❌ فقط مدیر/رهبر گروه می‌تواند ساختمان را ارتقا دهد.", show_alert=True); return True
        key=parts[3]
        if key not in CITY_ADV_BUILDINGS:
            await q.answer("❌ ساختمان نامعتبر است.", show_alert=True); return True
        with db_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row=conn.execute("SELECT level FROM city_buildings WHERE group_id=? AND building_key=?",(gid,key)).fetchone()
                lvl=int(row["level"] if row else 0)
                if lvl>=5:
                    conn.rollback(); await q.answer("این ساختمان به حداکثر سطح رسیده.",show_alert=True); return True
                cost=CITY_ADV_BUILDINGS[key]["base_cost"]*(lvl+1)**2
                cur=conn.execute("UPDATE groups SET treasury=treasury-? WHERE group_id=? AND treasury>=?",(cost,gid,cost))
                if cur.rowcount != 1:
                    conn.rollback(); await q.answer(f"خزانه کافی نیست: {cost:,}",show_alert=True); return True
                cur=conn.execute("UPDATE city_buildings SET level=level+1 WHERE group_id=? AND building_key=? AND level=?",(gid,key,lvl))
                if cur.rowcount != 1:
                    conn.rollback(); await q.answer("❌ ارتقا همزمان انجام شد؛ دوباره تلاش کن.",show_alert=True); return True
                conn.execute("UPDATE city_state SET xp=xp+?,satisfaction=MIN(100,satisfaction+2),total_expense=total_expense+? WHERE group_id=?",(cost//100,cost,gid))
                conn.commit()
            except Exception:
                conn.rollback(); raise
        await q.answer("ساختمان ارتقا یافت!",show_alert=True); await city_adv_panel(q.message,gid,user.id); return True
    if action=="economy":
        income,st,bs=city_adv_income_preview(gid)
        await q.edit_message_text(f"📊 *اقتصاد شهر*\n\n📈 درآمد تخمینی روزانه: *{income:,}*\n🧾 مالیات: *{st['tax_rate']}%*\n👥 جمعیت: *{st['population']:,}*\n😊 رضایت: *{st['satisfaction']}%*\n\n🏗 بازار {bs.get('market',0)} | بانک {bs.get('bank',0)} | صنعت {bs.get('factory',0)} | اسکله {bs.get('fishing',0)}",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 شهر",callback_data=f"cityadv_home_{gid}")]])); return True
    if action=="sat":
        with db_conn() as conn: st=conn.execute("SELECT * FROM city_state WHERE group_id=?",(gid,)).fetchone()
        await q.edit_message_text(f"😊 *رضایت شهروندان: {st['satisfaction']}%*\n\nمالیات بالا رضایت را کم می‌کند. ساخت پناهگاه و مدیریت اقتصادی خوب رضایت را بالا می‌برد.",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 شهر",callback_data=f"cityadv_home_{gid}")]])); return True
    if action=="tax":
        with db_conn() as conn: st=conn.execute("SELECT tax_rate FROM city_state WHERE group_id=?",(gid,)).fetchone()
        await q.edit_message_text(f"🧾 *مالیات شهری*\n\nنرخ فعلی: *{st['tax_rate']}%*\n\nبرای تغییر در گروه بنویس: *شهر مالیات 8*\nمحدوده مجاز: 0 تا 15٪",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 شهر",callback_data=f"cityadv_home_{gid}")]])); return True
    if action=="treasury":
        income,st,_=city_adv_income_preview(gid)
        with db_conn() as conn: grp=conn.execute("SELECT treasury FROM groups WHERE group_id=?",(gid,)).fetchone()
        await q.edit_message_text(f"🏦 *خزانه شهر*\n\n💰 موجودی: *{grp['treasury']:,.0f}*\n📈 درآمد تخمینی روزانه: *{income:,}*\n💵 کل درآمد: *{st['total_income']:,}*\n💸 کل هزینه: *{st['total_expense']:,}",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 شهر",callback_data=f"cityadv_home_{gid}")]])); return True
    if action=="log":
        with db_conn() as conn: rows=conn.execute("SELECT * FROM city_ledger WHERE group_id=? ORDER BY id DESC LIMIT 10",(gid,)).fetchall()
        txt="📜 *تاریخچه اقتصاد شهر*\n\n"+("\n".join(f"• {r['description']} | {r['amount']:,}" for r in rows) if rows else "هنوز تراکنشی ثبت نشده.")
        await q.edit_message_text(txt,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 شهر",callback_data=f"cityadv_home_{gid}")]])); return True
    if action=="home": await city_adv_panel(q.message,gid,user.id); return True
    return True

async def city_adv_daily_job(context):
    with db_conn() as conn:
        states=conn.execute("SELECT group_id FROM city_state").fetchall()
        for row in states:
            gid=row["group_id"]; income,st,bs=city_adv_income_preview(gid)
            if not income: continue
            conn.execute("UPDATE groups SET treasury=treasury+? WHERE group_id=?",(income,gid))
            conn.execute("UPDATE city_state SET last_income=CURRENT_TIMESTAMP,total_income=total_income+?,xp=xp+? WHERE group_id=?",(income,max(1,income//1000),gid))
            conn.execute("INSERT INTO city_ledger(group_id,kind,amount,description) VALUES(?,?,?,?)",(gid,"income",income,"درآمد روزانه شهر"))
            if bs.get("shelter",0):
                conn.execute("UPDATE city_state SET satisfaction=MIN(100,satisfaction+1) WHERE group_id=?",(gid,))
        conn.commit()

def migrate_db():
    logger.info("🔧 migrate_db شروع شد...")
    with db_conn() as conn:

        conn.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            type       TEXT,
            amount     REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()

        REQUIRED_COLUMNS = {
            "users": [
                ("hop_points",  "REAL    DEFAULT 0"),
                ("total_hops",  "INTEGER DEFAULT 0"),
                ("xp",          "INTEGER DEFAULT 0"),
                ("login_streak", "INTEGER DEFAULT 0"),
                ("last_login_date", "TEXT DEFAULT NULL"),
                ("level",       "INTEGER DEFAULT 1"),
                ("last_hop",    "TEXT    DEFAULT NULL"),
                ("joined_at",   "TEXT    DEFAULT CURRENT_TIMESTAMP"),
                ("username",    "TEXT"),
                ("first_name",  "TEXT"),
                ("hop_boost_until", "TEXT DEFAULT NULL"),
                ("hop_boost_mult", "REAL DEFAULT 1.0"),
                ("fish_luck_until", "TEXT DEFAULT NULL"),
                ("fish_luck_mult", "REAL DEFAULT 1.0"),
            ],
            "dogs": [
                ("name",         "TEXT    DEFAULT 'سگولو'"),
                ("level",        "INTEGER DEFAULT 1"),
                ("rank",         "INTEGER DEFAULT 1"),
                ("points_box",   "REAL    DEFAULT 0"),
                ("fed_until",    "TEXT    DEFAULT NULL"),
                ("last_collect", "TEXT    DEFAULT NULL"),
                ("dog_type",     "TEXT    DEFAULT 'stray'"),
                ("boost_until",  "TEXT    DEFAULT NULL"),
                ("boost_mult",   "REAL DEFAULT 1.0"),
            ],
            "groups": [
                ("title",       "TEXT"),
                ("level",       "INTEGER DEFAULT 1"),
                ("treasury",    "REAL    DEFAULT 0"),
                ("total_hops",  "INTEGER DEFAULT 0"),
                ("total_dogs",  "INTEGER DEFAULT 0"),
                ("total_bones", "INTEGER DEFAULT 0"),
                ("total_fish",  "INTEGER DEFAULT 0"),
            ],
            "hooks": [
                ("level",     "INTEGER DEFAULT 1"),
                ("last_cast", "TEXT    DEFAULT NULL"),
            ],
            "pending_bones": [
                ("bone_name", "TEXT"),
                ("weight",    "REAL"),
                ("price",     "INTEGER"),
                ("caught_at", "TEXT"),
            ],
            "bank": [
                ("balance",         "REAL DEFAULT 0"),
                ("account_number",  "TEXT UNIQUE"),
                ("opened_at",       "TEXT DEFAULT CURRENT_TIMESTAMP"),
                ("last_interest",   "TEXT DEFAULT NULL"),
                ("last_num_change", "TEXT DEFAULT NULL"),
            ],
            "factories": [
                ("level",           "INTEGER DEFAULT 1"),
                ("exp",             "INTEGER DEFAULT 0"),
                ("warehouse_level", "INTEGER DEFAULT 1"),
                ("machine_level",   "INTEGER DEFAULT 1"),
                ("stock",           "INTEGER DEFAULT 0"),
                ("last_produced",   "TEXT    DEFAULT NULL"),
                ("producing",       "INTEGER DEFAULT 0"),
                ("product_idx",     "INTEGER DEFAULT 0"),
                ("production_end",  "TEXT    DEFAULT NULL"),
                ("boost_until",      "TEXT    DEFAULT NULL"),
                ("boost_mult",       "REAL DEFAULT 1.0"),
            ],
            "jail": [
                ("jailed_at",   "TEXT"),
                ("release_at",  "TEXT"),
                ("reason",      "TEXT    DEFAULT 'قاچاق'"),
                ("work_points", "INTEGER DEFAULT 0"),
                ("last_work",   "TEXT    DEFAULT NULL"),
            ],
            "user_strays": [
                ("count", "INTEGER DEFAULT 0"),
            ],
            "market_prices": [
                ("multiplier",  "REAL DEFAULT 1.0"),
                ("updated_at",  "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ],
            "transactions": [
                ("user_id",    "INTEGER"),
                ("type",       "TEXT"),
                ("amount",     "REAL"),
                ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ],
        }

        for table, columns in REQUIRED_COLUMNS.items():
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                logger.warning(f"⚠️ جدول {table} وجود نداره — رد میشه")
                continue

            current_cols = {
                row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }

            for col_name, col_def in columns:
                if col_name not in current_cols:
                    try:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                        conn.commit()
                        logger.info(f"✅ ستون '{col_name}' به جدول '{table}' اضافه شد")
                    except Exception as e:
                        logger.warning(f"⚠️ نتونست ستون {col_name} رو به {table} اضافه کنه: {e}")

        conn.execute("""
            INSERT OR IGNORE INTO factories (user_id)
            SELECT u.user_id FROM users u
            WHERE u.level >= ? AND u.user_id NOT IN (SELECT user_id FROM factories)
        """, (FACTORY_MIN_LEVEL,))
        restored = conn.execute("SELECT changes()").fetchone()[0]
        if restored:
            logger.info(f"✅ {restored} کارخونه برای کاربرای ریست‌شده دوباره ساخته شد")
        conn.commit()

    logger.info("✅ migrate_db تموم شد")

def get_user(user_id):
    with db_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

def ensure_user(user_id, username, first_name):
    with db_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO users (user_id,username,first_name) VALUES (?,?,?)",
                     (user_id, username, first_name))
        conn.execute("UPDATE users SET username=?,first_name=? WHERE user_id=?",
                     (username, first_name, user_id))
        conn.commit()

def ensure_group(group_id, title):
    with db_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO groups (group_id,title) VALUES (?,?)", (group_id, title))
        conn.execute("UPDATE groups SET title=? WHERE group_id=?", (title, group_id))
        conn.commit()

def get_level(total_hops):
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if total_hops >= threshold:
            level = i + 2
        else:
            break
    return min(level, 1000)

def hops_for_next_level(level):
    if level >= 1000: return 0
    return LEVEL_THRESHOLDS[level - 1]

def calc_hop_reward(level):
    _base  = 56.74
    _ratio = 1.2336
    max_reward = int(_base * (_ratio ** (level - 1)))
    min_reward = 20
    if level >= 43:
        mid = int(max_reward * 0.60)
        if random.random() < 0.60:
            return random.randint(min_reward, mid)
        else:
            return random.randint(mid, max_reward)
    return random.randint(min_reward, max_reward)

def calc_dog_points(dog):
    if not dog["last_collect"]: return 0.0
    fed_until = dog["fed_until"]
    if not fed_until or datetime.fromisoformat(fed_until) < datetime.now(): return 0.0
    last    = datetime.fromisoformat(dog["last_collect"])
    seconds = (datetime.now() - last).total_seconds()
    rate, capacity, _ = DOG_LEVEL_DATA.get(dog["level"], (0.1, 5000, 500))
    rank_mult = DOG_RANKS.get(dog["rank"], ("", 1.0))[1]
    type_mult = DOG_TYPES.get(dog["dog_type"], DOG_TYPES["stray"])["mult"] if "dog_type" in dog.keys() else 1.0
    boost_mult = 1.0
    if "boost_until" in dog.keys() and dog["boost_until"]:
        try:
            if datetime.fromisoformat(dog["boost_until"]) > datetime.now():
                boost_mult = float(dog["boost_mult"] or 1.0)
        except Exception:
            pass
    seasonal_mult = get_seasonal_event()[1].get("dog_mult", 1.0)
    return min(seconds * rate * rank_mult * type_mult * boost_mult * seasonal_mult, capacity)

def parse_amount(text):
    text = text.strip().replace(",", "").replace("_", "")
    multipliers = {"k": 1_000, "کی": 1_000, "کا": 1_000, "m": 1_000_000, "میل": 1_000_000}
    for suffix, mult in multipliers.items():
        if text.lower().endswith(suffix):
            try:
                value=float(text[:-len(suffix)]) * mult
                return int(value) if math.isfinite(value) else -1
            except Exception: return -1
    try:
        value=float(text)
        return int(value) if math.isfinite(value) else -1
    except Exception: return -1

def is_in_jail(user_id):
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM jail WHERE user_id=?", (user_id,)).fetchone()
        if not row: return False, None
        if datetime.fromisoformat(row["release_at"]) > datetime.now(): return True, row
        conn.execute("DELETE FROM jail WHERE user_id=?", (user_id,))
        conn.commit()
    return False, None

def jail_user(user_id, reason="قاچاق", duration_seconds=None):
    now = datetime.now()
    secs = duration_seconds if duration_seconds else JAIL_DURATION
    release = now + timedelta(seconds=secs)
    with db_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO jail (user_id,jailed_at,release_at,reason,work_points,last_work) VALUES (?,?,?,?,0,NULL)",
            (user_id, now.isoformat(), release.isoformat(), reason)
        )
        conn.commit()


def get_factory(user_id):
    with db_conn() as conn:
        return conn.execute("SELECT * FROM factories WHERE user_id=?", (user_id,)).fetchone()

def refresh_market_prices():
    now = datetime.now()
    with db_conn() as conn:
        for idx in range(len(FACTORY_PRODUCTS)):
            row = conn.execute(
                "SELECT updated_at FROM market_prices WHERE product_idx=?", (idx,)
            ).fetchone()
            should_update = True
            if row and row["updated_at"]:
                diff = (now - datetime.fromisoformat(row["updated_at"])).total_seconds()
                if diff < 3600:
                    should_update = False
            if should_update:
                mult = round(random.uniform(MARKET_PRICE_MIN, MARKET_PRICE_MAX), 2)
                conn.execute(
                    "INSERT OR REPLACE INTO market_prices (product_idx, multiplier, updated_at) VALUES (?,?,?)",
                    (idx, mult, now.isoformat())
                )
        conn.commit()

def get_market_price(product_idx):
    refresh_market_prices()
    with db_conn() as conn:
        row = conn.execute(
            "SELECT multiplier FROM market_prices WHERE product_idx=?", (product_idx,)
        ).fetchone()
    base_price = FACTORY_PRODUCTS[product_idx][2]
    mult = row["multiplier"] if row else 1.0
    return int(base_price * mult), mult

def get_available_products(factory_level):
    return [
        (idx, p) for idx, p in enumerate(FACTORY_PRODUCTS)
        if p[3] <= factory_level
    ]

def get_stray_count_factory(user_id):
    with db_conn() as conn:
        row = conn.execute("SELECT count FROM user_strays WHERE user_id=?", (user_id,)).fetchone()
    return row["count"] if row else 0

def check_production_done(factory):
    if not factory["producing"] or not factory["production_end"]:
        return False
    return datetime.now() >= datetime.fromisoformat(factory["production_end"])

def collect_production(user_id):
    # Atomic collection: only one concurrent request can consume the finished batch.
    with db_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        factory = conn.execute("SELECT * FROM factories WHERE user_id=?", (user_id,)).fetchone()
        if not factory or not check_production_done(factory):
            conn.rollback(); return 0
        stray_row = conn.execute("SELECT count FROM user_strays WHERE user_id=?", (user_id,)).fetchone()
        workers = max(1, stray_row["count"] if stray_row else 0)
        cap = WAREHOUSE_LEVELS[factory["warehouse_level"]][0]
        added = min(workers, max(0, cap - factory["stock"]))
        if added <= 0:
            conn.rollback(); return 0
        product = FACTORY_PRODUCTS[factory["product_idx"]]
        exp_gain = product[4] * added
        new_exp = factory["exp"] + exp_gain
        new_level = factory["level"]
        while new_level < FACTORY_MAX_LEVEL and FACTORY_LEVEL_EXP.get(new_level, 0) > 0 and new_exp >= FACTORY_LEVEL_EXP[new_level]:
            new_exp -= FACTORY_LEVEL_EXP[new_level]
            new_level += 1
        cur = conn.execute("""UPDATE factories SET stock=stock+?, exp=?, level=?, producing=0, production_end=NULL, last_produced=?
            WHERE user_id=? AND producing=1 AND production_end IS NOT NULL""",
            (added, new_exp, new_level, datetime.now().isoformat(), user_id))
        if cur.rowcount != 1:
            conn.rollback(); return 0
        conn.commit()
        return added


# =========================
# Happy Doggy 2.1 - Inventory + Dog Types + Rare Items
# =========================
DOG_TYPES = {
    "stray":   {"name": "🐾 سگ خیابونی", "desc": "ارزان و متعادل؛ مناسب شروع", "cost": 1000, "mult": 1.00, "ability": "بدون قابلیت ویژه", "rarity": "Common", "rarity_icon": "⚪"},
    "guard":   {"name": "🛡️ سگ نگهبان", "desc": "درآمد سگ کمی بیشتر", "cost": 5000, "mult": 1.12, "ability": "درآمد سگ +۱۲٪", "rarity": "Uncommon", "rarity_icon": "🟢"},
    "hunter":  {"name": "🎯 سگ شکارچی", "desc": "شانس بیشتری برای آیتم کمیاب", "cost": 12000, "mult": 1.08, "ability": "شانس آیتم کمیاب +۸٪", "rarity": "Rare", "rarity_icon": "🔵"},
    "royal":   {"name": "👑 سگ سلطنتی", "desc": "گران، قدرتمند و ویژه", "cost": 30000, "mult": 1.25, "ability": "درآمد سگ +۲۵٪", "rarity": "Epic", "rarity_icon": "🟣"},
    "cosmic":  {"name": "🌌 سگ کیهانی", "desc": "کمیاب‌ترین نوع سگ", "cost": 100000, "mult": 1.50, "ability": "درآمد سگ +۵۰٪", "rarity": "Legendary", "rarity_icon": "🟠"},
}

# Mythic dogs are not directly purchasable; they can be obtained from special/cosmic events.
DOG_TYPES.update({
    "phoenix": {"name": "🔥 سگ ققنوس", "desc": "درآمد بسیار بالا؛ هنگام برداشت شانس پاداش اضافه دارد.", "cost": 0, "mult": 1.80, "ability": "هر برداشت ۷٪ شانس دریافت ۲۵٪ پاداش اضافه", "rarity": "Mythic", "rarity_icon": "🔴", "obtain": "cosmic"},
    "oracle":  {"name": "🔮 سگ پیشگو", "desc": "حس ششم قدرتمند برای پیدا کردن آیتم‌های کمیاب.", "cost": 0, "mult": 1.65, "ability": "شانس آیتم کمیاب +۲۵٪", "rarity": "Mythic", "rarity_icon": "🔴", "obtain": "cosmic"},
    "chronos":  {"name": "⏳ سگ کرونوس", "desc": "زمان را برای کارخانه خم می‌کند.", "cost": 0, "mult": 1.55, "ability": "زمان تولید کارخانه ۲۰٪ کمتر", "rarity": "Mythic", "rarity_icon": "🔴", "obtain": "cosmic"},
})

RARE_ITEMS = {
    "gold_collar": {"name": "🏅 قلاده طلایی", "desc": "درآمد سگ را برای ۶۰ دقیقه ۲۰٪ بیشتر می‌کند.", "use": "dog", "duration": 3600, "mult": 1.20},
    "lucky_bone":  {"name": "🍀 استخوان شانس", "desc": "شانس پیدا کردن آیتم کمیاب را برای ۶۰ دقیقه افزایش می‌دهد.", "use": "luck", "duration": 3600, "mult": 1.75},
    "factory_gear": {"name": "⚙️ چرخ‌دنده طلایی", "desc": "سرعت تولید کارخانه را برای ۶۰ دقیقه ۱۵٪ بیشتر می‌کند.", "use": "factory", "duration": 3600, "mult": 1.15},
    "golden_paw":   {"name": "🐾 پنجه طلایی", "desc": "پاداش هاپ را برای ۳۰ دقیقه ۱۵٪ بیشتر می‌کند.", "use": "hop", "duration": 1800, "mult": 1.15},
    "mystery_tag":  {"name": "🎫 تگ مرموز", "desc": "یک آیتم کلکسیونی فوق‌العاده کمیاب.", "use": "collectible", "duration": 0, "mult": 1.0},
    "mythic_essence": {"name": "💠 عصاره Mythic", "desc": "یادگار کمیاب یک سگ Mythic؛ برای سیستم‌های ویژه آینده قابل استفاده است.", "use": "collectible", "duration": 0, "mult": 1.0},
}

DOG_RARITY_ORDER = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic"]

MYSTERY_BOXES = {
    "basic": {"name": "🎁 جعبه مرموز", "cost": 3500, "desc": "یک جایزه تصادفی از آیتم‌های معمولی تا کمیاب.", "weights": [("Common", 55), ("Uncommon", 28), ("Rare", 12), ("Epic", 5)]},
    "royal": {"name": "👑 جعبه سلطنتی", "cost": 25000, "desc": "شانس بیشتر برای آیتم‌ها و سگ‌های ارزشمند.", "weights": [("Uncommon", 30), ("Rare", 35), ("Epic", 25), ("Legendary", 10)]},
    "cosmic": {"name": "🌌 جعبه کیهانی", "cost": 120000, "desc": "جعبه فوق‌کمیاب با شانس واقعی برای جایزه Mythic.", "weights": [("Rare", 20), ("Epic", 35), ("Legendary", 35), ("Mythic", 10)]},
}

# A rotating 24-hour event. The active event changes automatically each day.
SEASONAL_EVENTS = {
    "golden_paws": {"name": "🐾 پنجه‌های طلایی", "desc": "پاداش هاپ +۲۵٪ و شانس آیتم کمیاب +۲۰٪", "hop_mult": 1.25, "luck_mult": 1.20, "dog_mult": 1.0, "factory_mult": 1.0, "reward": 1200},
    "dog_week": {"name": "🐕 روز سگ‌ها", "desc": "درآمد سگ‌ها +۵۰٪", "hop_mult": 1.0, "luck_mult": 1.0, "dog_mult": 1.50, "factory_mult": 1.0, "reward": 1800},
    "factory_rush": {"name": "🏭 هجوم کارخانه", "desc": "زمان تولید کارخانه ۲۵٪ کمتر", "hop_mult": 1.0, "luck_mult": 1.0, "dog_mult": 1.0, "factory_mult": 1.25, "reward": 1800},
    "bone_hunt": {"name": "🦴 شکار بزرگ استخوان", "desc": "شانس آیتم کمیاب +۷۵٪", "hop_mult": 1.0, "luck_mult": 1.75, "dog_mult": 1.0, "factory_mult": 1.0, "reward": 2200},
    "royal_day": {"name": "👑 روز سلطنتی", "desc": "همه درآمدها +۲۰٪", "hop_mult": 1.20, "luck_mult": 1.20, "dog_mult": 1.20, "factory_mult": 1.20, "reward": 2500},
}

def get_seasonal_event():
    # Stable daily rotation; no scheduler or manual database state is required.
    day_index = (datetime.now().date() - datetime(2026, 1, 1).date()).days
    keys = list(SEASONAL_EVENTS.keys())
    key = keys[day_index % len(keys)]
    return key, SEASONAL_EVENTS[key]

def seasonal_event_text():
    key, ev = get_seasonal_event()
    tomorrow = datetime.now().date() + timedelta(days=1)
    midnight = datetime.combine(tomorrow, datetime.min.time())
    left = max(0, int((midnight - datetime.now()).total_seconds()))
    h, rem = divmod(left, 3600); m, _ = divmod(rem, 60)
    return f"{ev['name']}\n\n✨ {ev['desc']}\n\n⏱️ حدود {h} ساعت و {m} دقیقه تا تغییر رویداد\n🎁 پاداش اولین مشارکت امروز: +{ev['reward']:,} هاپ"

DOG_COLLECTION_REWARDS = {
    "2": 3000,
    "3": 10000,
    "5": 50000,
}

RARITY_ITEM_CHANCE = {
    "⚪": 0.002,
    "🟢": 0.006,
    "🔵": 0.015,
    "🟣": 0.035,
    "🟠": 0.080,
    "🔴": 0.160,
    "🔥": 0.280,
}


def init_collection_tables():
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER NOT NULL,
            item_key TEXT NOT NULL,
            quantity INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, item_key)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS collection (
            user_id INTEGER NOT NULL,
            collection_key TEXT NOT NULL,
            first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            count INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, collection_key)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS mystery_opens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            box_key TEXT NOT NULL,
            reward_key TEXT NOT NULL,
            reward_type TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS seasonal_claims (
            user_id INTEGER NOT NULL,
            event_date TEXT NOT NULL,
            event_key TEXT NOT NULL,
            PRIMARY KEY(user_id, event_date)
        )""")
        conn.commit()


def add_inventory_item(user_id, item_key, quantity=1):
    if item_key not in RARE_ITEMS or quantity <= 0:
        return 0
    with db_conn() as conn:
        conn.execute("""INSERT INTO inventory(user_id,item_key,quantity,updated_at)
                       VALUES(?,?,?,?)
                       ON CONFLICT(user_id,item_key) DO UPDATE SET
                       quantity=quantity+excluded.quantity, updated_at=CURRENT_TIMESTAMP""",
                     (user_id, item_key, quantity, datetime.now().isoformat()))
        conn.commit()
    add_collection(user_id, "item:" + item_key)
    return quantity


def remove_inventory_item(user_id, item_key, quantity=1):
    try:
        quantity=int(quantity)
    except (TypeError, ValueError):
        return False
    if quantity <= 0:
        return False
    with db_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur=conn.execute("UPDATE inventory SET quantity=quantity-?,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND item_key=? AND quantity>=?",
                         (quantity, user_id, item_key, quantity))
        if cur.rowcount != 1:
            conn.rollback()
            return False
        conn.execute("DELETE FROM inventory WHERE user_id=? AND item_key=? AND quantity<=0", (user_id, item_key))
        conn.commit()
    return True


def grant_rare_item_from_catch(user_id, rarity_icon):
    base = RARITY_ITEM_CHANCE.get(rarity_icon, 0.0)
    with db_conn() as conn:
        dog = conn.execute("SELECT dog_type FROM dogs WHERE user_id=?", (user_id,)).fetchone()
        user = conn.execute("SELECT fish_luck_until,fish_luck_mult FROM users WHERE user_id=?", (user_id,)).fetchone()
    if dog:
        dog_type = dog["dog_type"]
        if dog_type == "hunter":
            base *= 1.08
        elif dog_type == "oracle":
            base *= 1.25
    seasonal_key, seasonal = get_seasonal_event()
    base *= float(seasonal.get("luck_mult", 1.0))
    if user and user["fish_luck_until"] and datetime.fromisoformat(user["fish_luck_until"]) > datetime.now():
        base *= float(user["fish_luck_mult"] or 1.0)
    if random.random() >= min(base, 0.95):
        return None
    # بالاتر رفتن rarity، آیتم‌های جذاب‌تر را محتمل‌تر می‌کند.
    pools = {
        "⚪": ["mystery_tag"], "🟢": ["mystery_tag"], "🔵": ["lucky_bone", "mystery_tag"],
        "🟣": ["lucky_bone", "gold_collar"], "🟠": ["gold_collar", "factory_gear"],
        "🔴": ["gold_collar", "factory_gear", "golden_paw"],
        "🔥": ["golden_paw", "factory_gear", "gold_collar", "mystery_tag"],
    }
    item_key = random.choice(pools.get(rarity_icon, ["mystery_tag"]))
    add_inventory_item(user_id, item_key, 1)
    return item_key


COLLECTION_REWARDS = {
    2: (2500, "🥉 کلکسیونر تازه‌کار"),
    5: (10000, "🥈 کلکسیونر حرفه‌ای"),
    8: (30000, "🥇 شکارچی گنج"),
    12: (75000, "💎 استاد کالکشن"),
    15: (150000, "👑 افسانه‌ی Happy Doggy"),
}

def init_collection_reward_tables():
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS collection_rewards_claimed (
            user_id INTEGER NOT NULL,
            milestone INTEGER NOT NULL,
            claimed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id,milestone)
        )""")
        conn.commit()

def collection_reward_status(user_id):
    count=collection_count(user_id)
    with db_conn() as conn:
        claimed={r['milestone'] for r in conn.execute("SELECT milestone FROM collection_rewards_claimed WHERE user_id=?",(user_id,)).fetchall()}
    return count, claimed

def collection_rewards_text(user_id):
    count, claimed=collection_reward_status(user_id)
    lines=["🎁 *جوایز کالکشن*",f"📚 کشف‌شده: *{count}/{len(DOG_TYPES)+len(RARE_ITEMS)}*",""]
    for milestone,(reward,title) in COLLECTION_REWARDS.items():
        mark='✅' if milestone in claimed else ('🎁' if count>=milestone else '🔒')
        state='دریافت شده' if milestone in claimed else ('آماده دریافت' if count>=milestone else f'نیاز: {milestone}')
        lines.append(f"{mark} *{title}* — {milestone} کشف | +{reward:,} هاپ | {state}")
    return "\n".join(lines)

async def collection_rewards_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; ensure_user(u.id,u.username or '',u.first_name)
    count,claimed=collection_reward_status(u.id)
    ready=[m for m in COLLECTION_REWARDS if count>=m and m not in claimed]
    if ready:
        total=sum(COLLECTION_REWARDS[m][0] for m in ready)
        with db_conn() as conn:
            for m in ready:
                conn.execute("INSERT OR IGNORE INTO collection_rewards_claimed(user_id,milestone) VALUES(?,?)",(u.id,m))
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?",(total,u.id)); conn.commit()
        await update.effective_message.reply_text(f"🎉 *جوایز کالکشن دریافت شد!*\n\n📚 {len(ready)} جایزه\n💰 +{total:,} هاپ",parse_mode='Markdown')
        return
    await update.effective_message.reply_text(collection_rewards_text(u.id),parse_mode='Markdown')

def add_collection(user_id, collection_key):
    with db_conn() as conn:
        row = conn.execute("SELECT count FROM collection WHERE user_id=? AND collection_key=?", (user_id, collection_key)).fetchone()
        if row:
            conn.execute("UPDATE collection SET count=count+1 WHERE user_id=? AND collection_key=?", (user_id, collection_key))
            first = False
        else:
            conn.execute("INSERT INTO collection(user_id,collection_key,count) VALUES(?,?,1)", (user_id, collection_key))
            first = True
        conn.commit()
    return first

def collection_count(user_id):
    with db_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM collection WHERE user_id=?", (user_id,)).fetchone()["c"]

def collection_text(user_id):
    with db_conn() as conn:
        rows = {r["collection_key"]: r["count"] for r in conn.execute("SELECT collection_key,count FROM collection WHERE user_id=?", (user_id,)).fetchall()}
    lines = ["🏆 *کالکشن Happy Doggy*", ""]
    total = len(DOG_TYPES) + len(RARE_ITEMS)
    found = len(rows)
    lines.append(f"📚 کشف‌شده: *{found}/{total}*")
    lines.append("")
    lines.append("🐕 *سگ‌ها*")
    for key, d in DOG_TYPES.items():
        ck = "dog:" + key
        mark = "✅" if ck in rows else "🔒"
        count = f" × {rows[ck]}" if ck in rows else ""
        lines.append(f"{mark} {d['rarity_icon']} {d['name']} — {d['rarity']}{count}")
    lines.append("")
    lines.append("💎 *آیتم‌ها*")
    for key, item in RARE_ITEMS.items():
        ck = "item:" + key
        mark = "✅" if ck in rows else "🔒"
        count = f" × {rows[ck]}" if ck in rows else ""
        lines.append(f"{mark} {item['name']}{count}")
    return "\n".join(lines)

def weighted_rarity(weights):
    names = [x[0] for x in weights]
    vals = [x[1] for x in weights]
    return random.choices(names, weights=vals, k=1)[0]

def reward_for_rarity(rarity):
    dogs = [k for k,d in DOG_TYPES.items() if d["rarity"] == rarity]
    if rarity == "Mythic":
        return ("dog", random.choice(dogs)) if dogs else ("item", "mythic_essence")
    if dogs and random.random() < 0.35:
        return ("dog", random.choice(dogs))
    pools = {
        "Common": ["mystery_tag"],
        "Uncommon": ["mystery_tag", "lucky_bone"],
        "Rare": ["lucky_bone", "gold_collar"],
        "Epic": ["gold_collar", "factory_gear", "golden_paw"],
        "Legendary": ["golden_paw", "factory_gear", "gold_collar"],
        "Mythic": ["mystery_tag", "golden_paw", "factory_gear"],
    }
    return ("item", random.choice(pools.get(rarity, ["mystery_tag"])))

def mystery_box_buttons(user_id):
    return InlineKeyboardMarkup([
        [cbtn(f"🎁 جعبه مرموز — {MYSTERY_BOXES['basic']['cost']:,}", f"box_basic_{user_id}" )],
        [cbtn(f"👑 جعبه سلطنتی — {MYSTERY_BOXES['royal']['cost']:,}", f"box_royal_{user_id}" )],
        [cbtn(f"🌌 جعبه کیهانی — {MYSTERY_BOXES['cosmic']['cost']:,}", f"box_cosmic_{user_id}" )],
        [cbtn("🏆 کالکشن", f"collection_{user_id}")],
    ])

async def mystery_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "", user.first_name)
    text = "🎁 *جعبه‌های مرموز*\n\n" + "\n\n".join(f"{b['name']}\n💰 {b['cost']:,} هاپ\n✨ {b['desc']}" for b in MYSTERY_BOXES.values())
    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=mystery_box_buttons(user.id))

def inventory_text(user_id):
    with db_conn() as conn:
        rows = conn.execute("SELECT item_key,quantity FROM inventory WHERE user_id=? AND quantity>0 ORDER BY quantity DESC,item_key",
                            (user_id,)).fetchall()
    if not rows:
        return "🎒 *کیفت خالیه!*\n\n🦴 با صید استخوان‌های کمیاب می‌تونی آیتم‌های ویژه جمع کنی."
    text = "🎒 *کیف آیتم‌ها*\n\n"
    for r in rows:
        item = RARE_ITEMS.get(r["item_key"])
        if item:
            text += f"{item['name']} × {r['quantity']}\n└ {item['desc']}\n\n"
    return text


async def seasonal_event_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "", user.first_name)
    key, ev = get_seasonal_event()
    # One participation reward per calendar day.
    today = datetime.now().date().isoformat()
    with db_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS seasonal_claims (user_id INTEGER NOT NULL, event_date TEXT NOT NULL, event_key TEXT NOT NULL, PRIMARY KEY(user_id,event_date))")
        row = conn.execute("SELECT 1 FROM seasonal_claims WHERE user_id=? AND event_date=?", (user.id, today)).fetchone()
        if not row:
            conn.execute("INSERT INTO seasonal_claims(user_id,event_date,event_key) VALUES(?,?,?)", (user.id, today, key))
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (ev["reward"], user.id))
            claimed = True
        else:
            claimed = False
        conn.commit()
    reward_line = f"\n\n🎁 جایزه رویداد دریافت شد: +{ev['reward']:,} هاپ" if claimed else "\n\n✅ جایزه امروزت رو قبلاً گرفتی."
    await update.effective_message.reply_text("🎪 *رویداد محدود امروز*\n\n" + seasonal_event_text() + reward_line, parse_mode="Markdown")


async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "", user.first_name)
    with db_conn() as conn:
        rows = conn.execute("SELECT item_key,quantity FROM inventory WHERE user_id=? AND quantity>0 ORDER BY item_key", (user.id,)).fetchall()
    text = inventory_text(user.id)
    kb = []
    for r in rows:
        item = RARE_ITEMS.get(r["item_key"])
        if item and item["use"] != "collectible":
            kb.append([cbtn(f"استفاده: {item['name']} × {r['quantity']}", callback_data=f"invuse_{r['item_key']}_{user.id}")])
    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb) if kb else None)


def dog_type_buttons(user_id):
    keys = list(DOG_TYPES.keys())
    kb = []
    for i in range(0, len(keys), 2):
        row = []
        for key in keys[i:i+2]:
            d = DOG_TYPES[key]
            if d.get("obtain") == "cosmic":
                row.append(cbtn(f"{d['name']} | 🔒 جعبه کیهانی", callback_data=f"mythicinfo_{key}_{user_id}"))
            else:
                row.append(cbtn(f"{d['name']} | {d['cost']:,}", callback_data=f"buydog_{key}_{user_id}"))
        kb.append(row)
    kb.append([cbtn("🎒 کیف آیتم‌ها", callback_data=f"inventory_{user_id}"), cbtn("❌ انصراف", callback_data="cancel")])
    return InlineKeyboardMarkup(kb)


async def collection_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "", user.first_name)
    kb = InlineKeyboardMarkup([[cbtn("🎁 جوایز کالکشن", f"collectionrewards_{user.id}"), cbtn("🎁 جعبه مرموز", f"mystery_{user.id}")]])
    await update.effective_message.reply_text(collection_text(user.id), parse_mode="Markdown", reply_markup=kb)

async def dog_types_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.effective_chat.type == "private":
        await update.effective_message.reply_text("🐕 انواع سگ فقط توی گروه قابل خریدنه!")
        return
    ensure_user(user.id, user.username or "", user.first_name)
    with db_conn() as conn:
        dog = conn.execute("SELECT 1 FROM dogs WHERE user_id=?", (user.id,)).fetchone()
    if dog:
        await update.effective_message.reply_text("🐕 تو از قبل سگ داری؛ برای دیدنش بنویس «سگ». ")
        return
    text = "🐕 *انتخاب نوع سگ*\n\n"
    for d in DOG_TYPES.values():
        cost_text = f"💰 {d['cost']:,} هاپ" if d.get("obtain") != "cosmic" else "🔒 فقط از جعبه کیهانی / رویداد ویژه"
        text += f"{d['rarity_icon']} *{d['rarity']}* — {d['name']}\n{cost_text} | ⚡️ ضریب {d['mult']}x\n✨ {d['ability']}\n\n"
    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=dog_type_buttons(user.id))


# =========================
# Happy Doggy 2.3 - Trading + Auction House
# =========================
TRADE_EXPIRE_MINUTES = 10
AUCTION_MINUTES = 24 * 60
AUCTION_FEE = 0.05
BARter_EXPIRE_MINUTES = 10
AUCTION_MIN_BID_INCREMENT = 0.05

# =========================
# Happy Doggy 2.6 - Clan System
# =========================
CLAN_CREATE_COST = 25_000
CLAN_MAX_LEVEL = 20
CLAN_WEEKLY_REWARD_BASE = 2_500


def init_clan_tables():
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            tag TEXT NOT NULL UNIQUE,
            owner_id INTEGER NOT NULL,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            treasury REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS clan_members (
            clan_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'member',
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            contribution REAL DEFAULT 0,
            PRIMARY KEY (clan_id, user_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS clan_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clan_id INTEGER NOT NULL,
            inviter_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS clan_rewards_claimed (
            clan_id INTEGER NOT NULL,
            week TEXT NOT NULL,
            PRIMARY KEY (clan_id, week)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clan_members_user ON clan_members(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clan_invites_target ON clan_invites(target_id,status)")
        conn.commit()
    init_clan_war_tables()


def clan_level_xp(level):
    return 5000 * level * level


def clan_max_members(level):
    return min(40, 5 + level * 2)


def clan_role_name(role):
    return {'owner': '👑 رهبر', 'officer': '🛡 معاون', 'member': '🐾 عضو'}.get(role, '🐾 عضو')


def get_user_clan(user_id):
    with db_conn() as conn:
        return conn.execute("""SELECT c.*, cm.role, cm.contribution
            FROM clans c JOIN clan_members cm ON cm.clan_id=c.clan_id
            WHERE cm.user_id=? LIMIT 1""", (user_id,)).fetchone()


def clan_add_xp(conn, clan_id, amount):
    row = conn.execute("SELECT level,xp FROM clans WHERE clan_id=?", (clan_id,)).fetchone()
    if not row:
        return 0, False
    level = int(row['level'])
    xp = int(row['xp']) + int(amount)
    leveled = False
    while level < CLAN_MAX_LEVEL and xp >= clan_level_xp(level):
        xp -= clan_level_xp(level)
        level += 1
        leveled = True
    conn.execute("UPDATE clans SET level=?,xp=? WHERE clan_id=?", (level, xp, clan_id))
    return level, leveled


def clan_text(clan_id):
    with db_conn() as conn:
        c = conn.execute("SELECT * FROM clans WHERE clan_id=?", (clan_id,)).fetchone()
        if not c:
            return '❌ کلن پیدا نشد.'
        members = conn.execute("""SELECT cm.*,u.username,u.first_name
            FROM clan_members cm LEFT JOIN users u ON u.user_id=cm.user_id
            WHERE cm.clan_id=?
            ORDER BY CASE cm.role WHEN 'owner' THEN 0 WHEN 'officer' THEN 1 ELSE 2 END,
                     cm.contribution DESC""", (clan_id,)).fetchall()
    text = (
        f"🏰 *کلن {c['name']}* `[{c['tag']}]`\n\n"
        f"👑 رهبر: `{c['owner_id']}`\n"
        f"⭐ سطح: *{c['level']}* | XP: `{c['xp']:,}/{clan_level_xp(c['level']):,}`\n"
        f"👥 اعضا: *{len(members)}/{clan_max_members(c['level'])}*\n"
        f"🏦 خزانه: *{c['treasury']:,.0f}* هاپ\n\n"
        "👥 *اعضا:*\n"
    )
    for m in members[:20]:
        name = m['first_name'] or m['username'] or str(m['user_id'])
        text += f"{clan_role_name(m['role'])} {name} — `{m['contribution']:,.0f}`\n"
    if len(members) > 20:
        text += f"… و {len(members)-20} عضو دیگر\n"
    return text


async def clan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or '', user.first_name)
    parts = (update.effective_message.text or '').strip().split()
    current = get_user_clan(user.id)

    if len(parts) == 1:
        if not current:
            await update.effective_message.reply_text(
                "🏰 *هنوز عضو کلنی نیستی.*\n\n"
                "ساخت: `کلن ساخت نامکلن TAG`\n"
                "دعوت: روی پیام بازیکن ریپلای کن و `کلن دعوت` بنویس.\n"
                "کمک به خزانه: `کلن کمک 5000`\n"
                "رتبه‌بندی: `کلن رتبه`",
                parse_mode='Markdown')
            return
        kb = InlineKeyboardMarkup([
            [cbtn('👥 اعضا', f"clan_members_{current['clan_id']}"), cbtn('🏦 خزانه', f"clan_treasury_{current['clan_id']}")],
            [cbtn('🎁 جایزه هفتگی', f"clan_reward_{current['clan_id']}"), cbtn('⚔️ جنگ کلنی', f"clan_war_panel_{current['clan_id']}")],
            [cbtn('🏆 رتبه کلن‌ها', 'clan_top')]
        ])
        await update.effective_message.reply_text(clan_text(current['clan_id']), parse_mode='Markdown', reply_markup=kb)
        return

    action = parts[1].lower()
    if action in ('جنگ', 'war'):
        return await clan_war_cmd(update, context)
    if action in ('ساخت', 'create'):
        if current:
            await update.effective_message.reply_text('❌ تو همین الان عضو یک کلن هستی.')
            return
        if len(parts) != 4:
            await update.effective_message.reply_text('فرمت: `کلن ساخت نامکلن TAG`', parse_mode='Markdown')
            return
        name, tag = parts[2], parts[3].upper()
        if len(name) > 24 or len(tag) > 6 or not tag.isalnum():
            await update.effective_message.reply_text('❌ نام حداکثر ۲۴ کاراکتر و تگ حداکثر ۶ حرف/عدد باشد.')
            return
        with db_conn() as conn:
            u = conn.execute('SELECT hop_points FROM users WHERE user_id=?', (user.id,)).fetchone()
            if not u or float(u['hop_points']) < CLAN_CREATE_COST:
                await update.effective_message.reply_text(f'❌ ساخت کلن {CLAN_CREATE_COST:,} هاپ هزینه دارد.')
                return
            try:
                cur = conn.execute('INSERT INTO clans(name,tag,owner_id) VALUES(?,?,?)', (name, tag, user.id))
                cid = cur.lastrowid
                conn.execute('INSERT INTO clan_members(clan_id,user_id,role) VALUES(?,?,?)', (cid, user.id, 'owner'))
                conn.execute('UPDATE users SET hop_points=hop_points-? WHERE user_id=?', (CLAN_CREATE_COST, user.id))
                conn.commit()
            except sqlite3.IntegrityError:
                await update.effective_message.reply_text('❌ نام یا تگ کلن قبلاً استفاده شده.')
                return
        await update.effective_message.reply_text(f'🏰 کلن *{name}* ساخته شد!\n🏷 تگ: `{tag}`', parse_mode='Markdown')
        return

    if action in ('دعوت', 'invite'):
        if not current or current['role'] not in ('owner', 'officer'):
            await update.effective_message.reply_text('❌ فقط رهبر یا معاون می‌تواند دعوت کند.')
            return
        target = _trade_target_from_reply(update)
        if not target or target.id == user.id:
            await update.effective_message.reply_text('❌ روی پیام بازیکن موردنظر ریپلای کن.')
            return
        if get_user_clan(target.id):
            await update.effective_message.reply_text('❌ این بازیکن عضو یک کلن است.')
            return
        with db_conn() as conn:
            cnt = conn.execute('SELECT COUNT(*) n FROM clan_members WHERE clan_id=?', (current['clan_id'],)).fetchone()['n']
            if cnt >= clan_max_members(current['level']):
                await update.effective_message.reply_text('❌ ظرفیت کلن پر است.')
                return
            expires = (datetime.now() + timedelta(minutes=15)).isoformat()
            conn.execute("INSERT INTO clan_invites(clan_id,inviter_id,target_id,expires_at) VALUES(?,?,?,?)", (current['clan_id'], user.id, target.id, expires))
            conn.commit()
        kb = InlineKeyboardMarkup([[cbtn('✅ پیوستن', f"clan_accept_{current['clan_id']}_{target.id}"), cbtn('❌ رد', f"clan_reject_{current['clan_id']}_{target.id}")]])
        try:
            await context.bot.send_message(target.id, f"🏰 به کلن *{current['name']}* دعوت شدی!\n🏷 تگ: `{current['tag']}`\n⏱ دعوت ۱۵ دقیقه اعتبار دارد.", parse_mode='Markdown', reply_markup=kb)
        except Exception:
            await update.effective_message.reply_text('⚠️ دعوت ثبت شد، ولی ارسال پیام خصوصی ممکن است به‌خاطر باز نبودن چت با ربات انجام نشود.')
            return
        await update.effective_message.reply_text('✅ دعوت ارسال شد.')
        return

    if action in ('کمک', 'donate'):
        if not current:
            await update.effective_message.reply_text('❌ اول عضو کلن شو.')
            return
        if len(parts) != 3:
            await update.effective_message.reply_text('فرمت: `کلن کمک 5000`', parse_mode='Markdown')
            return
        amount = parse_amount(parts[2])
        if amount <= 0:
            await update.effective_message.reply_text('❌ مبلغ نامعتبر است.')
            return
        with db_conn() as conn:
            u = conn.execute('SELECT hop_points FROM users WHERE user_id=?', (user.id,)).fetchone()
            if not u or float(u['hop_points']) < amount:
                await update.effective_message.reply_text('❌ موجودی کافی نیست.')
                return
            cur = conn.execute('UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?', (amount, user.id, amount))
            if cur.rowcount != 1:
                conn.rollback(); await update.effective_message.reply_text('❌ موجودی همزمان تغییر کرد.'); return
            conn.execute('UPDATE clans SET treasury=treasury+? WHERE clan_id=?', (amount, current['clan_id']))
            conn.execute('UPDATE clan_members SET contribution=contribution+? WHERE clan_id=? AND user_id=?', (amount, current['clan_id'], user.id))
            lvl, up = clan_add_xp(conn, current['clan_id'], max(1, amount // 100))
            conn.commit()
        msg = f'💰 {amount:,} هاپ به خزانه کلن واریز شد!\n⭐ +{max(1, amount//100)} XP کلن'
        if up:
            msg += f'\n🎉 کلن به سطح *{lvl}* رسید! ظرفیت: {clan_max_members(lvl)} نفر'
        await update.effective_message.reply_text(msg, parse_mode='Markdown')
        return

    if action in ('معاون', 'officer'):
        if not current or current['role'] != 'owner' or not update.effective_message.reply_to_message:
            await update.effective_message.reply_text('❌ فقط رهبر و با ریپلای می‌تواند معاون تعیین کند.')
            return
        target = update.effective_message.reply_to_message.from_user
        with db_conn() as conn:
            row = conn.execute('SELECT role FROM clan_members WHERE clan_id=? AND user_id=?', (current['clan_id'], target.id)).fetchone()
            if not row:
                await update.effective_message.reply_text('❌ این بازیکن عضو کلن نیست.')
                return
            if target.id == user.id:
                await update.effective_message.reply_text('❌ خودت رهبر هستی.')
                return
            conn.execute("UPDATE clan_members SET role='officer' WHERE clan_id=? AND user_id=?", (current['clan_id'], target.id))
            conn.commit()
        await update.effective_message.reply_text(f'🛡 {target.first_name} معاون کلن شد.')
        return

    if action in ('اخراج', 'kick'):
        if not current or current['role'] != 'owner' or not update.effective_message.reply_to_message:
            await update.effective_message.reply_text('❌ فقط رهبر و با ریپلای می‌تواند عضو را اخراج کند.')
            return
        target = update.effective_message.reply_to_message.from_user
        with db_conn() as conn:
            row = conn.execute('SELECT role FROM clan_members WHERE clan_id=? AND user_id=?', (current['clan_id'], target.id)).fetchone()
            if not row or row['role'] == 'owner':
                await update.effective_message.reply_text('❌ این کاربر عضو قابل اخراج نیست.')
                return
            conn.execute('DELETE FROM clan_members WHERE clan_id=? AND user_id=?', (current['clan_id'], target.id))
            conn.commit()
        await update.effective_message.reply_text(f'👢 {target.first_name} از کلن اخراج شد.')
        return

    if action in ('ترک', 'leave'):
        if not current:
            await update.effective_message.reply_text('❌ عضو هیچ کلنی نیستی.')
            return
        if current['role'] == 'owner':
            await update.effective_message.reply_text('❌ رهبر باید کلن را منحل کند؛ فعلاً انتقال رهبری انجام نشده است.')
            return
        with db_conn() as conn:
            conn.execute('DELETE FROM clan_members WHERE clan_id=? AND user_id=?', (current['clan_id'], user.id))
            conn.commit()
        await update.effective_message.reply_text('👋 از کلن خارج شدی.')
        return

    if action in ('انحلال', 'disband'):
        if not current or current['role'] != 'owner':
            await update.effective_message.reply_text('❌ فقط رهبر می‌تواند کلن را منحل کند.')
            return
        with db_conn() as conn:
            c = conn.execute('SELECT treasury FROM clans WHERE clan_id=?', (current['clan_id'],)).fetchone()
            refund = float(c['treasury'] or 0)
            conn.execute('UPDATE users SET hop_points=hop_points+? WHERE user_id=?', (refund, user.id))
            conn.execute('DELETE FROM clan_members WHERE clan_id=?', (current['clan_id'],))
            conn.execute('DELETE FROM clan_invites WHERE clan_id=?', (current['clan_id'],))
            conn.execute('DELETE FROM clan_rewards_claimed WHERE clan_id=?', (current['clan_id'],))
            conn.execute('DELETE FROM clans WHERE clan_id=?', (current['clan_id'],))
            conn.commit()
        await update.effective_message.reply_text(f'🗑 کلن منحل شد و {refund:,.0f} هاپ خزانه به رهبر برگشت.')
        return

    if action in ('رتبه', 'top'):
        with db_conn() as conn:
            rows = conn.execute('SELECT name,tag,level,xp,treasury FROM clans ORDER BY level DESC,xp DESC,treasury DESC LIMIT 15').fetchall()
        text = '🏆 *برترین کلن‌ها*\n\n'
        for i, r in enumerate(rows, 1):
            text += f"{i}. 🏰 {r['name']} `[{r['tag']}]` — Lv.{r['level']} | XP {r['xp']:,}\n"
        await update.effective_message.reply_text(text if rows else 'هنوز کلنی ساخته نشده.', parse_mode='Markdown')
        return

    await update.effective_message.reply_text('📖 `کلن` | `کلن ساخت نام TAG` | `کلن دعوت` | `کلن کمک مبلغ` | `کلن معاون` | `کلن اخراج` | `کلن ترک` | `کلن رتبه`', parse_mode='Markdown')


async def clan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data or ''
    user = q.from_user
    if not data.startswith('clan_'):
        return False
    parts = data.split('_')
    action = parts[1] if len(parts) > 1 else ''
    try:
        cid = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        cid = 0

    if action == 'war':
        sub = parts[2] if len(parts) > 2 else 'panel'
        if sub == 'attack':
            try:
                war_id = int(parts[3])
            except (ValueError, IndexError):
                await q.answer('نبرد نامعتبر است.', show_alert=True)
                return True
            return await clan_war_attack_callback(update, context, war_id)
        if sub == 'panel':
            c = get_user_clan(user.id)
            if not c:
                await q.answer('عضو کلن نیستی.', show_alert=True)
                return True
            active = clan_war_active_for(c['clan_id'])
            if not active:
                await q.edit_message_text('⚔️ *جنگ کلنی*\n\nهنوز در جنگ نیستی.\nبرای شروع: `کلن جنگ شروع ID`\nبرای دیدن کلن‌ها: `کلن جنگ لیست`', parse_mode='Markdown')
                return True
            kb = InlineKeyboardMarkup([[cbtn('⚔️ حمله کلنی', f'clan_war_attack_{active["war_id"]}')]])
            await q.edit_message_text(clan_war_text(active['war_id'], c['clan_id']), parse_mode='Markdown', reply_markup=kb)
            return True

    if action in ('accept', 'reject'):
        try:
            target_id = int(parts[3])
        except (ValueError, IndexError):
            target_id = 0
        if target_id != user.id:
            await q.answer('این دعوت برای تو نیست.', show_alert=True)
            return True
        with db_conn() as conn:
            inv = conn.execute("""SELECT * FROM clan_invites
                WHERE clan_id=? AND target_id=? AND status='pending' AND expires_at>?
                ORDER BY id DESC LIMIT 1""", (cid, user.id, datetime.now().isoformat())).fetchone()
            if not inv:
                await q.answer('دعوت منقضی یا نامعتبر است.', show_alert=True)
                return True
            if action == 'reject':
                conn.execute("UPDATE clan_invites SET status='rejected' WHERE id=?", (inv['id'],))
                conn.commit()
                await q.edit_message_text('❌ دعوت کلن رد شد.')
                return True
            if get_user_clan(user.id):
                await q.answer('اول از کلن فعلی خارج شو.', show_alert=True)
                return True
            c = conn.execute('SELECT * FROM clans WHERE clan_id=?', (cid,)).fetchone()
            n = conn.execute('SELECT COUNT(*) n FROM clan_members WHERE clan_id=?', (cid,)).fetchone()['n']
            if not c or n >= clan_max_members(c['level']):
                await q.answer('ظرفیت کلن پر شده.', show_alert=True)
                return True
            conn.execute("INSERT INTO clan_members(clan_id,user_id,role) VALUES(?,?,?)", (cid, user.id, 'member'))
            conn.execute("UPDATE clan_invites SET status='accepted' WHERE id=?", (inv['id'],))
            conn.commit()
        await q.edit_message_text(f"🎉 به کلن *{c['name']}* پیوستی!\n🏷 `{c['tag']}`", parse_mode='Markdown')
        return True

    c = get_user_clan(user.id)
    if action in ('members', 'treasury', 'reward') and (not c or c['clan_id'] != cid):
        await q.answer('دسترسی نداری.', show_alert=True)
        return True
    if action == 'members':
        await q.answer()
        await q.edit_message_text(clan_text(cid), parse_mode='Markdown')
        return True
    if action == 'treasury':
        await q.answer(f"خزانه: {c['treasury']:,.0f} هاپ", show_alert=True)
        return True
    if action == 'top':
        with db_conn() as conn:
            rows = conn.execute('SELECT name,tag,level,xp FROM clans ORDER BY level DESC,xp DESC LIMIT 15').fetchall()
        text = '🏆 *برترین کلن‌ها*\n\n' + ''.join(f"{i}. 🏰 {r['name']} `[{r['tag']}]` — Lv.{r['level']} | {r['xp']:,} XP\n" for i, r in enumerate(rows, 1))
        await q.edit_message_text(text or 'هنوز کلنی ساخته نشده.', parse_mode='Markdown')
        return True
    if action == 'reward':
        week = datetime.now().strftime('%Y-W%W')
        with db_conn() as conn:
            if conn.execute('SELECT 1 FROM clan_rewards_claimed WHERE clan_id=? AND week=?', (cid, week)).fetchone():
                await q.answer('جایزه این هفته قبلاً گرفته شده.', show_alert=True)
                return True
            members = conn.execute('SELECT user_id FROM clan_members WHERE clan_id=?', (cid,)).fetchall()
            reward = int(CLAN_WEEKLY_REWARD_BASE * c['level'])
            if not members:
                await q.answer('کلن عضو ندارد.', show_alert=True)
                return True
            conn.execute("BEGIN IMMEDIATE")
            fresh_c = conn.execute('SELECT treasury FROM clans WHERE clan_id=?', (cid,)).fetchone()
            if not fresh_c or float(fresh_c['treasury']) < reward:
                conn.rollback(); await q.answer(f'خزانه کافی نیست؛ نیاز: {reward:,} هاپ', show_alert=True); return True
            per = reward // len(members)
            spent = conn.execute('UPDATE clans SET treasury=treasury-? WHERE clan_id=? AND treasury>=?', (reward, cid, reward))
            if spent.rowcount != 1:
                conn.rollback(); await q.answer('⚠️ خزانه همزمان تغییر کرد؛ دوباره تلاش کن.', show_alert=True); return True
            for m in members:
                conn.execute('UPDATE users SET hop_points=hop_points+? WHERE user_id=?', (per, m['user_id']))
            conn.execute('INSERT INTO clan_rewards_claimed(clan_id,week) VALUES(?,?)', (cid, week))
            conn.commit()
        await q.edit_message_text(f'🎁 جایزه هفتگی توزیع شد!\n💰 مجموع: {reward:,} هاپ\n👥 سهم هر عضو: {per:,} هاپ')
        return True
    return False


# =========================
# Happy Doggy 2.7 - Clan Wars
# =========================
CLAN_WAR_DURATION_HOURS = 24
CLAN_WAR_ENTRY = 25_000
CLAN_WAR_ACTION_COOLDOWN_HOURS = 6
CLAN_WAR_MAX_ACTIONS_PER_DAY = 4
CLAN_WAR_FEE_RATE = 0.05


def init_clan_war_tables():
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS clan_wars (
            war_id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenger_id INTEGER NOT NULL,
            defender_id INTEGER NOT NULL,
            challenger_score INTEGER DEFAULT 0,
            defender_score INTEGER DEFAULT 0,
            pot REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            winner_id INTEGER
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS clan_war_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            war_id INTEGER NOT NULL,
            clan_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            points INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clan_wars_active ON clan_wars(status,expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clan_war_actions_user ON clan_war_actions(war_id,user_id,created_at)")
        conn.commit()


def clan_war_active_for(clan_id):
    with db_conn() as conn:
        row = conn.execute("""SELECT * FROM clan_wars
            WHERE status='active' AND (challenger_id=? OR defender_id=?)
            ORDER BY war_id DESC LIMIT 1""", (clan_id, clan_id)).fetchone()
    return row


def clan_war_text(war_id, viewer_clan_id=None):
    with db_conn() as conn:
        w = conn.execute("SELECT * FROM clan_wars WHERE war_id=?", (war_id,)).fetchone()
        if not w:
            return '❌ نبرد پیدا نشد.'
        a = conn.execute("SELECT name,tag,level FROM clans WHERE clan_id=?", (w['challenger_id'],)).fetchone()
        b = conn.execute("SELECT name,tag,level FROM clans WHERE clan_id=?", (w['defender_id'],)).fetchone()
    left = a['name'] if a else f"#{w['challenger_id']}"
    right = b['name'] if b else f"#{w['defender_id']}"
    remaining = max(0, int((datetime.fromisoformat(w['expires_at']) - datetime.now()).total_seconds()))
    h, rem = divmod(remaining, 3600)
    m = rem // 60
    return (
        f"⚔️ *نبرد کلنی #{war_id}*\n\n"
        f"🏰 {left} `[{a['tag'] if a else '?'}]`  *{w['challenger_score']:,}*\n"
        f"🆚\n"
        f"🏰 {right} `[{b['tag'] if b else '?'}]`  *{w['defender_score']:,}*\n\n"
        f"💰 جایزه: *{w['pot']:,.0f}* هاپ\n"
        f"⏳ زمان باقی‌مانده: *{h}س {m}د*\n\n"
        "هر عضو می‌تواند هر ۶ ساعت یک بار برای کلنش امتیاز کسب کند."
    )


def settle_clan_wars():
    """Finish expired wars and distribute the pot to the winning clan's treasury."""
    settled = []
    season_events = []
    with db_conn() as conn:
        rows = conn.execute("SELECT * FROM clan_wars WHERE status='active' AND expires_at<=?", (datetime.now().isoformat(),)).fetchall()
        for w in rows:
            cs, ds = int(w['challenger_score']), int(w['defender_score'])
            if cs == ds:
                # Draw: refund both entry fees through treasury and close the war.
                conn.execute("UPDATE clans SET treasury=treasury+? WHERE clan_id IN (?,?)", (CLAN_WAR_ENTRY, w['challenger_id'], w['defender_id']))
                conn.execute("UPDATE clan_wars SET status='draw',winner_id=NULL WHERE war_id=?", (w['war_id'],))
                season_events.extend([(w['challenger_id'], 60, 'draw'), (w['defender_id'], 60, 'draw')])
                settled.append((w['war_id'], 'draw', None, cs, ds))
                continue
            winner = w['challenger_id'] if cs > ds else w['defender_id']
            fee = int(float(w['pot']) * CLAN_WAR_FEE_RATE)
            reward = int(float(w['pot'])) - fee
            conn.execute("UPDATE clans SET treasury=treasury+? WHERE clan_id=?", (reward, winner))
            conn.execute("UPDATE clan_wars SET status='settled',winner_id=? WHERE war_id=?", (winner, w['war_id']))
            loser = w['defender_id'] if winner == w['challenger_id'] else w['challenger_id']
            season_events.extend([(winner, 120, 'win'), (loser, 30, 'loss')])
            settled.append((w['war_id'], 'settled', winner, cs, ds))
        conn.commit()
    for cid, delta, result in season_events:
        season_record_clan(cid, delta, result)
    return settled


async def clan_war_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or '', user.first_name)
    settle_clan_wars()
    current = get_user_clan(user.id)
    msg = update.effective_message
    if not current:
        await msg.reply_text('❌ برای استفاده از نبرد کلنی باید عضو کلن باشی.')
        return
    parts = (msg.text or '').strip().split()
    active = clan_war_active_for(current['clan_id'])

    if len(parts) == 1:
        if not active:
            await msg.reply_text(
                '⚔️ *جنگ کلنی*\n\n'
                f'هزینه ورود هر کلن: *{CLAN_WAR_ENTRY:,}* هاپ\n'
                f'مدت: *{CLAN_WAR_DURATION_HOURS} ساعت*\n'
                'شروع: `کلن جنگ شروع ID`\n'
                'مثال: `کلن جنگ شروع 12`', parse_mode='Markdown')
            return
        kb = InlineKeyboardMarkup([[cbtn('⚔️ حمله کلنی', f'clan_war_attack_{active["war_id"]}')]])
        await msg.reply_text(clan_war_text(active['war_id'], current['clan_id']), parse_mode='Markdown', reply_markup=kb)
        return

    action = parts[1].lower()
    if action in ('شروع', 'start'):
        if current['role'] not in ('owner', 'officer'):
            await msg.reply_text('❌ فقط رهبر یا معاون می‌تواند جنگ را شروع کند.')
            return
        if active:
            await msg.reply_text('❌ کلن شما همین حالا در یک جنگ است.')
            return
        if len(parts) != 4:
            await msg.reply_text('فرمت: `کلن جنگ شروع ID_کلن`', parse_mode='Markdown')
            return
        try:
            target_cid = int(parts[3])
        except ValueError:
            await msg.reply_text('❌ شناسه کلن نامعتبر است.')
            return
        if target_cid == current['clan_id']:
            await msg.reply_text('❌ نمی‌توانی با کلن خودت بجنگی.')
            return
        with db_conn() as conn:
            target = conn.execute('SELECT * FROM clans WHERE clan_id=?', (target_cid,)).fetchone()
            if not target:
                await msg.reply_text('❌ کلن موردنظر پیدا نشد.')
                return
            target_war = conn.execute("SELECT 1 FROM clan_wars WHERE status='active' AND (challenger_id=? OR defender_id=?) LIMIT 1", (target_cid, target_cid)).fetchone()
            if target_war:
                await msg.reply_text('❌ آن کلن در حال حاضر در جنگ است.')
                return
            conn.execute("BEGIN IMMEDIATE")
            target_war = conn.execute("SELECT 1 FROM clan_wars WHERE status='active' AND (challenger_id=? OR defender_id=?) LIMIT 1", (target_cid, target_cid)).fetchone()
            me = conn.execute('SELECT treasury FROM clans WHERE clan_id=?', (current['clan_id'],)).fetchone()
            my_war = conn.execute("SELECT 1 FROM clan_wars WHERE status='active' AND (challenger_id=? OR defender_id=?) LIMIT 1", (current['clan_id'], current['clan_id'])).fetchone()
            if target_war or my_war or not me or float(me['treasury']) < CLAN_WAR_ENTRY:
                conn.rollback(); await msg.reply_text('❌ خزانه کافی نیست یا یکی از کلن‌ها هم‌اکنون در جنگ است.'); return
            expires = (datetime.now() + timedelta(hours=CLAN_WAR_DURATION_HOURS)).isoformat()
            spend = conn.execute('UPDATE clans SET treasury=treasury-? WHERE clan_id=? AND treasury>=?', (CLAN_WAR_ENTRY, current['clan_id'], CLAN_WAR_ENTRY))
            if spend.rowcount != 1:
                conn.rollback(); await msg.reply_text('❌ خزانه کلن تغییر کرده؛ دوباره تلاش کن.'); return
            cur = conn.execute("INSERT INTO clan_wars(challenger_id,defender_id,pot,expires_at) VALUES(?,?,?,?)", (current['clan_id'], target_cid, CLAN_WAR_ENTRY, expires))
            war_id = cur.lastrowid
            conn.commit()
        await msg.reply_text(f'⚔️ درخواست جنگ با *{target["name"]}* ثبت شد!\n🆔 نبرد: `{war_id}`\n💰 ورود: {CLAN_WAR_ENTRY:,} هاپ', parse_mode='Markdown')
        return

    if action in ('لیست', 'list'):
        with db_conn() as conn:
            rows = conn.execute('SELECT clan_id,name,tag,level FROM clans ORDER BY level DESC,xp DESC LIMIT 20').fetchall()
        text = '🏰 *کلن‌ها برای جنگ*\n\n' + ''.join(f"`{r['clan_id']}` — {r['name']} `[{r['tag']}]` Lv.{r['level']}\n" for r in rows)
        await msg.reply_text(text or 'کلنی وجود ندارد.', parse_mode='Markdown')
        return

    await msg.reply_text('فرمت: `کلن جنگ` یا `کلن جنگ شروع ID` یا `کلن جنگ لیست`', parse_mode='Markdown')


async def clan_war_attack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, war_id: int) -> bool:
    q = update.callback_query
    user = q.from_user
    settle_clan_wars()
    clan = get_user_clan(user.id)
    if not clan:
        await q.answer('عضو کلن نیستی.', show_alert=True)
        return True
    with db_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        w = conn.execute("SELECT * FROM clan_wars WHERE war_id=? AND status='active'", (war_id,)).fetchone()
        if not w or clan['clan_id'] not in (w['challenger_id'], w['defender_id']):
            await q.answer('این جنگ فعال نیست یا کلن تو در آن نیست.', show_alert=True)
            return True
        since = (datetime.now() - timedelta(hours=CLAN_WAR_ACTION_COOLDOWN_HOURS)).isoformat()
        recent = conn.execute("SELECT 1 FROM clan_war_actions WHERE war_id=? AND user_id=? AND created_at>? LIMIT 1", (war_id, user.id, since)).fetchone()
        if recent:
            await q.answer('⏳ هر ۶ ساعت یک بار می‌توانی حمله کنی.', show_alert=True)
            return True
        today = datetime.now().strftime('%Y-%m-%d')
        count = conn.execute("SELECT COUNT(*) n FROM clan_war_actions WHERE war_id=? AND user_id=? AND created_at LIKE ?", (war_id, user.id, today+'%')).fetchone()['n']
        if count >= CLAN_WAR_MAX_ACTIONS_PER_DAY:
            await q.answer('سقف حمله امروزت پر شده.', show_alert=True)
            return True
        # Score is based on the player's progression, with a small random tactical factor.
        u = conn.execute('SELECT level FROM users WHERE user_id=?', (user.id,)).fetchone()
        d = conn.execute('SELECT level FROM dogs WHERE user_id=? LIMIT 1', (user.id,)).fetchone()
        base = max(10, int((u['level'] if u else 1) * 4) + int((d['level'] if d else 1) * 3))
        points = random.randint(max(5, base - 8), base + 12)
        conn.execute('INSERT INTO clan_war_actions(war_id,clan_id,user_id,points) VALUES(?,?,?,?)', (war_id, clan['clan_id'], user.id, points))
        if clan['clan_id'] == w['challenger_id']:
            conn.execute('UPDATE clan_wars SET challenger_score=challenger_score+? WHERE war_id=?', (points, war_id))
        else:
            conn.execute('UPDATE clan_wars SET defender_score=defender_score+? WHERE war_id=?', (points, war_id))
        conn.execute('UPDATE clan_members SET contribution=contribution+? WHERE clan_id=? AND user_id=?', (points * 10, clan['clan_id'], user.id))
        conn.execute('UPDATE clans SET treasury=treasury WHERE clan_id=?', (clan['clan_id'],))
        conn.commit()
    season_record_user(user.id, 'clan_war', 1)
    season_record_clan(clan['clan_id'], max(1, points // 2))
    await q.answer(f'⚔️ حمله موفق! +{points} امتیاز', show_alert=True)
    try:
        await q.edit_message_text(clan_war_text(war_id, clan['clan_id']), parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[cbtn('⚔️ حمله کلنی', f'clan_war_attack_{war_id}')]]))
    except Exception:
        logger.warning("Non-fatal exception was suppressed", exc_info=True)
    return True


def init_trade_auction_tables():
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS barter_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposer_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            offer_item TEXT NOT NULL,
            offer_qty INTEGER NOT NULL,
            want_item TEXT NOT NULL,
            want_qty INTEGER NOT NULL,
            offer_hop INTEGER NOT NULL DEFAULT 0,
            want_hop INTEGER NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_barter_active ON barter_offers(status,expires_at)")
        conn.execute("""CREATE TABLE IF NOT EXISTS trade_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            item_key TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS auctions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_key TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            current_bid REAL DEFAULT 0,
            current_bidder_id INTEGER DEFAULT NULL,
            bid_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
        )""")
        auction_cols = {r[1] for r in conn.execute("PRAGMA table_info(auctions)").fetchall()}
        if "current_bid" not in auction_cols:
            conn.execute("ALTER TABLE auctions ADD COLUMN current_bid REAL DEFAULT 0")
        if "current_bidder_id" not in auction_cols:
            conn.execute("ALTER TABLE auctions ADD COLUMN current_bidder_id INTEGER DEFAULT NULL")
        if "bid_count" not in auction_cols:
            conn.execute("ALTER TABLE auctions ADD COLUMN bid_count INTEGER DEFAULT 0")
        conn.execute("""CREATE TABLE IF NOT EXISTS auction_bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auction_id INTEGER NOT NULL,
            bidder_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auction_bids_active ON auction_bids(auction_id,status)")
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_auctions_active ON auctions(status, expires_at)""")
        conn.commit()

def barter_expire_old():
    now=datetime.now()
    with db_conn() as conn:
        conn.execute("UPDATE barter_offers SET status='expired' WHERE status='pending' AND expires_at<=?",(now.isoformat(),))
        conn.commit()

def auction_expire_old():
    # Settle expired auctions. The highest bidder's escrow becomes the seller's payment;
    # auctions without bids return the reserved item to the seller.
    with db_conn() as conn:
        rows = conn.execute("SELECT * FROM auctions WHERE status='active' AND expires_at <= ?", (datetime.now().isoformat(),)).fetchall()
        for row in rows:
            bidder_id = row['current_bidder_id']
            bid = float(row['current_bid'] or 0)
            if bidder_id and bid > 0:
                fee = int(bid * AUCTION_FEE)
                seller_net = int(bid) - fee
                conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (seller_net, row['seller_id']))
                conn.execute("INSERT INTO inventory(user_id,item_key,quantity) VALUES(?,?,?) ON CONFLICT(user_id,item_key) DO UPDATE SET quantity=quantity+excluded.quantity,updated_at=CURRENT_TIMESTAMP", (bidder_id,row['item_key'],row['quantity']))
                conn.execute("UPDATE auction_bids SET status='won' WHERE auction_id=? AND bidder_id=? AND amount=? AND status='active'", (row['id'],bidder_id,bid))
                conn.execute("UPDATE auctions SET status='sold' WHERE id=?", (row['id'],))
            else:
                conn.execute("UPDATE inventory SET quantity=quantity+? WHERE user_id=? AND item_key=?", (row['quantity'],row['seller_id'],row['item_key']))
                conn.execute("UPDATE auctions SET status='expired' WHERE id=?", (row['id'],))
        conn.commit()

async def auction_cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    parts = (update.message.text or '').strip().split()
    if len(parts) != 3 or parts[1] not in ('لغو', 'cancel'):
        await update.message.reply_text("فرمت: `حراج لغو شماره_آگهی`", parse_mode='Markdown')
        return
    try:
        aid = int(parts[2])
    except ValueError:
        await update.message.reply_text("❌ شماره آگهی نامعتبر است.")
        return
    auction_expire_old()
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM auctions WHERE id=?", (aid,)).fetchone()
        if not row or row['status'] != 'active':
            await update.message.reply_text("❌ آگهی فعال پیدا نشد.")
            return
        if row['seller_id'] != user.id:
            await update.message.reply_text("❌ فقط صاحب آگهی می‌تواند آن را لغو کند.")
            return
        if row['current_bidder_id'] and float(row['current_bid'] or 0) > 0:
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (row['current_bid'], row['current_bidder_id']))
            conn.execute("UPDATE auction_bids SET status='refunded' WHERE auction_id=? AND status='active'", (aid,))
        conn.execute("UPDATE auctions SET status='cancelled' WHERE id=?", (aid,))
        if row['item_type'] == 'item':
            conn.execute("""INSERT INTO inventory(user_id,item_key,quantity) VALUES(?,?,?)
                ON CONFLICT(user_id,item_key) DO UPDATE SET quantity=quantity+excluded.quantity, updated_at=CURRENT_TIMESTAMP""",
                (user.id, row['item_key'], row['quantity']))
        conn.commit()
    await update.message.reply_text(f"✅ آگهی #{aid} لغو شد و آیتم به کیفت برگشت.")

def _find_user_by_username(username):
    username = username.lstrip('@').strip()
    with db_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE lower(username)=lower(?) LIMIT 1", (username,)).fetchone()

def _trade_target_from_reply(update):
    if not update.message or not update.message.reply_to_message:
        return None
    return update.message.reply_to_message.from_user

def _trade_offer_text(row):
    item = RARE_ITEMS.get(row['item_key'], {})
    return (
        "🤝 *پیشنهاد معامله*\n\n"
        f"👤 فروشنده: `{row['seller_id']}`\n"
        f"📦 آیتم: {item.get('name', row['item_key'])} × {row['quantity']}\n"
        f"💰 قیمت: {row['price']:,.0f} هاپ\n"
        f"⏳ اعتبار: {TRADE_EXPIRE_MINUTES} دقیقه\n\n"
        "اگر قبول کنی، آیتم به تو و هاپ به فروشنده منتقل می‌شود."
    )

async def trade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or '', user.first_name)
    msg = update.message
    if not msg or not msg.text:
        return
    parts = msg.text.strip().split()
    target = _trade_target_from_reply(update)
    if not target:
        await msg.reply_text("🤝 برای معامله، روی پیام طرف مقابل ریپلای کن.\nمثال: `معامله قلاده_طلایی 1 50000`", parse_mode='Markdown')
        return
    if target.id == user.id:
        await msg.reply_text("❌ نمی‌توانی با خودت معامله کنی!")
        return
    if target.is_bot:
        await msg.reply_text("❌ با ربات نمی‌توان معامله کرد!")
        return
    if len(parts) == 1:
        await msg.reply_text("📦 فرمت: `معامله ITEM تعداد قیمت`\nمثال: `معامله gold_collar 1 50000`", parse_mode='Markdown')
        return
    item_key = parts[1].strip().lower()
    aliases = {
        'قلاده': 'gold_collar', 'قلاده_طلایی': 'gold_collar', 'استخوان_شانس': 'lucky_bone',
        'چرخدنده': 'factory_gear', 'چرخ_دنده': 'factory_gear', 'پنجه_طلایی': 'golden_paw',
        'تگ': 'mystery_tag', 'تگ_مرموز': 'mystery_tag', 'عصاره': 'mythic_essence'
    }
    item_key = aliases.get(item_key, item_key)
    if item_key not in RARE_ITEMS:
        await msg.reply_text("❌ این آیتم قابل معامله نیست یا وجود ندارد.\nبرای دیدن کلید آیتم‌ها: `کیف`", parse_mode='Markdown')
        return
    if len(parts) < 4:
        await msg.reply_text("❌ فرمت درست: `معامله ITEM تعداد قیمت`", parse_mode='Markdown')
        return
    try:
        qty = int(parts[2])
    except ValueError:
        qty = -1
    price = parse_amount(parts[3])
    if qty <= 0 or price <= 0 or qty > 1000:
        await msg.reply_text("❌ تعداد یا قیمت نامعتبر است.")
        return
    with db_conn() as conn:
        inv = conn.execute("SELECT quantity FROM inventory WHERE user_id=? AND item_key=?", (user.id, item_key)).fetchone()
    if not inv or inv['quantity'] < qty:
        await msg.reply_text(f"❌ موجودی کافی نداری. موجودی فعلی: {inv['quantity'] if inv else 0}")
        return
    expires = (datetime.now() + timedelta(minutes=TRADE_EXPIRE_MINUTES)).isoformat()
    with db_conn() as conn:
        conn.execute("INSERT INTO trade_offers(seller_id,buyer_id,item_key,quantity,price,expires_at) VALUES(?,?,?,?,?,?)",
                     (user.id, target.id, item_key, qty, price, expires))
        trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
    kb = InlineKeyboardMarkup([[
        cbtn('✅ قبول معامله', f'trade_accept_{trade_id}'),
        cbtn('❌ رد', f'trade_reject_{trade_id}')
    ]])
    await msg.reply_text(f"{_trade_offer_text({'seller_id':user.id,'item_key':item_key,'quantity':qty,'price':price})}", parse_mode='Markdown', reply_markup=kb)

async def barter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Two-sided item/hop barter. Must reply to target's message.
    Syntax: مبادله ITEM1 QTY1 ITEM2 QTY2 [هاپ_من] [هاپ_طرف]
    """
    msg = update.effective_message
    user = update.effective_user
    ensure_user(user.id, user.username or '', user.first_name)
    barter_expire_old()
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("🔄 برای مبادله باید روی پیام طرف مقابل Reply کنی.\n\nمثال:\n`مبادله gold_collar 1 lucky_bone 2 5000 0`", parse_mode='Markdown')
        return
    target = msg.reply_to_message.from_user
    if target.id == user.id or target.is_bot:
        await msg.reply_text("❌ مبادله با خودت یا ربات‌ها ممکن نیست.")
        return
    parts = (msg.text or '').strip().split()
    if len(parts) not in (5, 7):
        await msg.reply_text("❌ فرمت:\n`مبادله ITEM1 تعداد1 ITEM2 تعداد2 [هاپ_من] [هاپ_طرف]`", parse_mode='Markdown')
        return
    aliases = {
        'قلاده':'gold_collar','قلاده_طلایی':'gold_collar','استخوان_شانس':'lucky_bone',
        'چرخدنده':'factory_gear','چرخ_دنده':'factory_gear','پنجه_طلایی':'golden_paw',
        'تگ':'mystery_tag','تگ_مرموز':'mystery_tag','عصاره':'mythic_essence'
    }
    a = aliases.get(parts[1].lower(), parts[1].lower())
    b = aliases.get(parts[3].lower(), parts[3].lower())
    if a not in RARE_ITEMS or b not in RARE_ITEMS:
        await msg.reply_text("❌ هر دو آیتم باید از آیتم‌های قابل معامله باشند. برای دیدنشان «کیف» را بزن.")
        return
    try:
        aq, bq = int(parts[2]), int(parts[4])
        my_hop = parse_amount(parts[5]) if len(parts) == 7 else 0
        their_hop = parse_amount(parts[6]) if len(parts) == 7 else 0
    except Exception:
        aq = bq = -1; my_hop = their_hop = -1
    if aq <= 0 or bq <= 0 or aq > 1000 or bq > 1000 or my_hop < 0 or their_hop < 0:
        await msg.reply_text("❌ تعداد یا مقدار هاپ نامعتبر است.")
        return
    with db_conn() as conn:
        inv = conn.execute("SELECT quantity FROM inventory WHERE user_id=? AND item_key=?", (user.id,a)).fetchone()
        target_inv = conn.execute("SELECT quantity FROM inventory WHERE user_id=? AND item_key=?", (target.id,b)).fetchone()
        me = conn.execute("SELECT hop_points FROM users WHERE user_id=?", (user.id,)).fetchone()
        them = conn.execute("SELECT hop_points FROM users WHERE user_id=?", (target.id,)).fetchone()
    if not inv or inv['quantity'] < aq:
        await msg.reply_text(f"❌ آیتم پیشنهادی کافی نداری: {RARE_ITEMS[a]['name']} × {aq}")
        return
    if my_hop > (me['hop_points'] if me else 0):
        await msg.reply_text("❌ هاپ پیشنهادی تو کافی نیست.")
        return
    # We do not reserve either side until acceptance, so both sides are rechecked atomically.
    expires=(datetime.now()+timedelta(minutes=BARter_EXPIRE_MINUTES)).isoformat()
    with db_conn() as conn:
        conn.execute("INSERT INTO barter_offers(proposer_id,target_id,offer_item,offer_qty,want_item,want_qty,offer_hop,want_hop,expires_at) VALUES(?,?,?,?,?,?,?,?,?)",
                     (user.id,target.id,a,aq,b,bq,my_hop,their_hop,expires))
        bid=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
    kb=InlineKeyboardMarkup([[cbtn('✅ قبول مبادله',f'barter_accept_{bid}'),cbtn('❌ رد',f'barter_reject_{bid}')]])
    await msg.reply_text(
        f"🔄 *پیشنهاد مبادله #{bid}*\n\n"
        f"📤 تو می‌دهی: {RARE_ITEMS[a]['name']} × {aq}"
        f"{' + ' + format(my_hop, ',.0f') + ' هاپ' if my_hop else ''}\n"
        f"📥 می‌گیری: {RARE_ITEMS[b]['name']} × {bq}"
        f"{' + ' + format(their_hop, ',.0f') + ' هاپ' if their_hop else ''}\n\n"
        f"⏳ اعتبار: {BARter_EXPIRE_MINUTES} دقیقه", parse_mode='Markdown', reply_markup=kb)

async def barter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q=update.callback_query; data=q.data
    if not data.startswith('barter_'): return False
    try: bid=int(data.rsplit('_',1)[1])
    except: await q.answer('پیشنهاد نامعتبر است.',show_alert=True); return True
    with db_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row=conn.execute("SELECT * FROM barter_offers WHERE id=?",(bid,)).fetchone()
        if not row or row['status']!='pending':
            await q.answer('این پیشنهاد دیگر فعال نیست.',show_alert=True); return True
        uid=q.from_user.id
        if uid not in (row['target_id'],row['proposer_id']):
            await q.answer('این پیشنهاد برای تو نیست!',show_alert=True); return True
        if data.startswith('barter_reject_'):
            conn.execute("UPDATE barter_offers SET status='rejected' WHERE id=?",(bid,)); conn.commit()
            await q.edit_message_text('❌ پیشنهاد مبادله رد شد.'); return True
        if uid != row['target_id']:
            await q.answer('فقط طرف مقابل می‌تواند مبادله را قبول کند.',show_alert=True); return True
        if datetime.fromisoformat(row['expires_at']) <= datetime.now():
            conn.execute("UPDATE barter_offers SET status='expired' WHERE id=?",(bid,)); conn.commit()
            await q.answer('⏳ مهلت مبادله تمام شده.',show_alert=True); return True
        # Re-check all assets under one transaction.
        proposer_inv=conn.execute("SELECT quantity FROM inventory WHERE user_id=? AND item_key=?",(row['proposer_id'],row['offer_item'])).fetchone()
        target_inv=conn.execute("SELECT quantity FROM inventory WHERE user_id=? AND item_key=?",(row['target_id'],row['want_item'])).fetchone()
        proposer=conn.execute("SELECT hop_points FROM users WHERE user_id=?",(row['proposer_id'],)).fetchone()
        target=conn.execute("SELECT hop_points FROM users WHERE user_id=?",(row['target_id'],)).fetchone()
        if not proposer_inv or proposer_inv['quantity']<row['offer_qty'] or not target_inv or target_inv['quantity']<row['want_qty']:
            conn.execute("UPDATE barter_offers SET status='cancelled' WHERE id=?",(bid,)); conn.commit()
            await q.answer('❌ یکی از طرفین دیگر موجودی لازم را ندارد.',show_alert=True); return True
        if proposer['hop_points']<row['offer_hop'] or target['hop_points']<row['want_hop']:
            await q.answer('❌ موجودی هاپ یکی از طرفین کافی نیست.',show_alert=True); return True
        # swap items
        conn.execute("UPDATE inventory SET quantity=quantity-? WHERE user_id=? AND item_key=?",(row['offer_qty'],row['proposer_id'],row['offer_item']))
        conn.execute("DELETE FROM inventory WHERE user_id=? AND item_key=? AND quantity<=0",(row['proposer_id'],row['offer_item']))
        conn.execute("UPDATE inventory SET quantity=quantity-? WHERE user_id=? AND item_key=?",(row['want_qty'],row['target_id'],row['want_item']))
        conn.execute("DELETE FROM inventory WHERE user_id=? AND item_key=? AND quantity<=0",(row['target_id'],row['want_item']))
        conn.execute("INSERT INTO inventory(user_id,item_key,quantity) VALUES(?,?,?) ON CONFLICT(user_id,item_key) DO UPDATE SET quantity=quantity+excluded.quantity,updated_at=CURRENT_TIMESTAMP",(row['target_id'],row['offer_item'],row['offer_qty']))
        conn.execute("INSERT INTO inventory(user_id,item_key,quantity) VALUES(?,?,?) ON CONFLICT(user_id,item_key) DO UPDATE SET quantity=quantity+excluded.quantity,updated_at=CURRENT_TIMESTAMP",(row['proposer_id'],row['want_item'],row['want_qty']))
        if row['offer_hop']:
            cur = conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?",(row['offer_hop'],row['proposer_id'],row['offer_hop']))
            if cur.rowcount != 1:
                conn.rollback(); await q.answer('❌ موجودی هاپ پیشنهاددهنده در لحظه قبول کافی نبود.',show_alert=True); return True
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?",(row['offer_hop'],row['target_id']))
        if row['want_hop']:
            cur = conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?",(row['want_hop'],row['target_id'],row['want_hop']))
            if cur.rowcount != 1:
                conn.rollback(); await q.answer('❌ موجودی هاپ تو در لحظه قبول کافی نبود.',show_alert=True); return True
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?",(row['want_hop'],row['proposer_id']))
        cur = conn.execute("UPDATE barter_offers SET status='accepted' WHERE id=? AND status='pending'",(bid,))
        if cur.rowcount != 1:
            conn.rollback(); await q.answer('⚠️ این مبادله همزمان تغییر کرد.',show_alert=True); return True
        conn.commit()
    add_collection(row['target_id'],'item:'+row['offer_item']); add_collection(row['proposer_id'],'item:'+row['want_item'])
    await q.edit_message_text(f"✅ *مبادله #{bid} انجام شد!*\n\n🔄 آیتم‌ها و هاپ طبق پیشنهاد جابه‌جا شدند.",parse_mode='Markdown')
    return True

async def auction_bid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or '', user.first_name)
    parts = (update.effective_message.text or '').strip().split()
    if len(parts) != 3:
        await update.effective_message.reply_text("💹 فرمت: `پیشنهاد شماره_آگهی مبلغ`\nمثال: `پیشنهاد 12 75000`", parse_mode='Markdown')
        return
    try:
        aid = int(parts[1]); amount = parse_amount(parts[2])
    except Exception:
        await update.effective_message.reply_text("❌ شماره یا مبلغ نامعتبر است.")
        return
    if amount <= 0:
        await update.effective_message.reply_text("❌ مبلغ پیشنهاد باید مثبت باشد.")
        return
    auction_expire_old()
    with db_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM auctions WHERE id=? AND status='active'", (aid,)).fetchone()
        if not row:
            await update.effective_message.reply_text("❌ آگهی فعال پیدا نشد.")
            return
        if row['seller_id'] == user.id:
            await update.effective_message.reply_text("❌ نمی‌توانی روی آگهی خودت پیشنهاد بدهی.")
            return
        current = float(row['current_bid'] or 0)
        minimum = max(current + 1, int(current * (1 + AUCTION_MIN_BID_INCREMENT))) if current > 0 else max(1, int(row['price'] * 0.10))
        if amount < minimum:
            await update.effective_message.reply_text(f"❌ حداقل پیشنهاد بعدی: {minimum:,.0f} هاپ")
            return
        buyer = conn.execute("SELECT hop_points FROM users WHERE user_id=?", (user.id,)).fetchone()
        if not buyer or buyer['hop_points'] < amount:
            await update.effective_message.reply_text("💰 هاپ کافی برای این پیشنهاد نداری.")
            return
        # Escrow: deduct new bid, refund the previous highest bidder atomically.
        if row['current_bidder_id'] and current > 0:
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (current, row['current_bidder_id']))
            conn.execute("UPDATE auction_bids SET status='outbid' WHERE auction_id=? AND status='active'", (aid,))
        debit = conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?", (amount, user.id, amount))
        if debit.rowcount != 1:
            conn.rollback(); await update.effective_message.reply_text("💰 موجودی هاپ کافی نیست؛ دوباره تلاش کن."); return
        conn.execute("INSERT INTO auction_bids(auction_id,bidder_id,amount) VALUES(?,?,?)", (aid,user.id,amount))
        changed = conn.execute("""UPDATE auctions SET current_bid=?, current_bidder_id=?, bid_count=COALESCE(bid_count,0)+1
            WHERE id=? AND status='active' AND current_bid < ?""", (amount,user.id,aid,amount))
        if changed.rowcount != 1:
            conn.rollback(); await update.effective_message.reply_text("⚠️ آگهی همزمان تغییر کرد؛ دوباره پیشنهاد بده."); return
        conn.commit()
    await update.effective_message.reply_text(f"✅ پیشنهاد #{aid} ثبت شد: 💰 {amount:,.0f} هاپ\nاگر پیشنهاد بالاتری ثبت شود، مبلغت خودکار برمی‌گردد.")

async def auction_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or '', user.first_name)
    auction_expire_old()
    parts = (update.message.text or '').strip().split()
    if len(parts) >= 2 and parts[1] in ('لغو', 'cancel'):
        await auction_cancel_cmd(update, context)
        return
    if len(parts) == 1:
        with db_conn() as conn:
            rows = conn.execute("SELECT * FROM auctions WHERE status='active' ORDER BY id DESC LIMIT 15").fetchall()
        if not rows:
            await update.message.reply_text("🏪 *حراج‌خانه خالی است!*\n\nهنوز آگهی فعالی وجود ندارد.", parse_mode='Markdown')
            return
        lines = ["🏪 *حراج‌خانه Happy Doggy*\n"]
        kb=[]
        for r in rows:
            item = RARE_ITEMS.get(r['item_key'], {})
            name = item.get('name', r['item_key'])
            current = float(r['current_bid'] or 0)
            bid_text = f" | 🔥 پیشنهاد فعلی: {current:,.0f}" if current > 0 else " | 💹 پیشنهاد باز است"
            lines.append(f"#{r['id']} — {name} × {r['quantity']} | 💰 خرید فوری: {r['price']:,.0f} هاپ{bid_text}")
            kb.append([cbtn(f"💹 پیشنهاد #{r['id']}", f'auction_bidinfo_{r["id"]}'), cbtn(f"🛒 خرید فوری", f'auction_buy_{r["id"]}')])
        await update.message.reply_text('\n'.join(lines), parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        return
    if len(parts) < 3:
        await update.message.reply_text("🏪 فرمت: `حراج ITEM قیمت [تعداد]`\nمثال: `حراج gold_collar 50000 1`", parse_mode='Markdown')
        return
    item_key = parts[1].strip().lower()
    aliases = {'قلاده':'gold_collar','قلاده_طلایی':'gold_collar','استخوان_شانس':'lucky_bone','چرخدنده':'factory_gear','پنجه_طلایی':'golden_paw','تگ':'mystery_tag','عصاره':'mythic_essence'}
    item_key = aliases.get(item_key,item_key)
    if item_key not in RARE_ITEMS:
        await update.message.reply_text("❌ این آیتم قابل حراج نیست.")
        return
    price = parse_amount(parts[2])
    qty = 1
    if len(parts) >= 4:
        try: qty = int(parts[3])
        except ValueError: qty = -1
    if price <= 0 or qty <= 0 or qty > 1000:
        await update.message.reply_text("❌ قیمت یا تعداد نامعتبر است.")
        return
    with db_conn() as conn:
        inv = conn.execute("SELECT quantity FROM inventory WHERE user_id=? AND item_key=?", (user.id,item_key)).fetchone()
    if not inv or inv['quantity'] < qty:
        await update.message.reply_text(f"❌ موجودی کافی نداری. موجودی: {inv['quantity'] if inv else 0}")
        return
    # Reserve the item while auction is active. It is returned if the seller cancels/auction expires.
    if not remove_inventory_item(user.id, item_key, qty):
        await update.message.reply_text("❌ موجودی آیتم تغییر کرده؛ دوباره تلاش کن.")
        return
    expires=(datetime.now()+timedelta(minutes=AUCTION_MINUTES)).isoformat()
    with db_conn() as conn:
        conn.execute("INSERT INTO auctions(seller_id,item_type,item_key,quantity,price,expires_at) VALUES(?,?,?,?,?,?)",
                     (user.id,'item',item_key,qty,price,expires))
        aid=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
    item=RARE_ITEMS[item_key]
    await update.message.reply_text(f"🏪 *آگهی ثبت شد!*\n\n{item['name']} × {qty}\n💰 قیمت کل: {price:,.0f} هاپ\n⏳ اعتبار: ۲۴ ساعت\n🆔 شماره آگهی: #{aid}",parse_mode='Markdown')

async def trade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q=update.callback_query
    data=q.data
    if data.startswith('trade_reject_'):
        tid=int(data.rsplit('_',1)[1])
        with db_conn() as conn:
            row=conn.execute("SELECT * FROM trade_offers WHERE id=?",(tid,)).fetchone()
            if not row or row['status']!='pending': await q.answer('این معامله دیگر فعال نیست.',show_alert=True); return True
            if q.from_user.id != row['buyer_id'] and q.from_user.id != row['seller_id']:
                await q.answer('این پیشنهاد برای تو نیست!',show_alert=True); return True
            conn.execute("UPDATE trade_offers SET status='rejected' WHERE id=?",(tid)); conn.commit()
        await q.edit_message_text('❌ معامله رد شد.')
        return True
    if data.startswith('trade_accept_'):
        tid=int(data.rsplit('_',1)[1])
        with db_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row=conn.execute("SELECT * FROM trade_offers WHERE id=?",(tid,)).fetchone()
                if not row or row['status']!='pending': conn.rollback(); await q.answer('این معامله دیگر فعال نیست.',show_alert=True); return True
                if q.from_user.id != row['buyer_id']:
                    conn.rollback(); await q.answer('فقط گیرنده می‌تواند معامله را قبول کند.',show_alert=True); return True
                if datetime.fromisoformat(row['expires_at']) <= datetime.now():
                    conn.execute("UPDATE trade_offers SET status='expired' WHERE id=? AND status='pending'",(tid,)); conn.commit(); await q.answer('⏳ مهلت معامله تمام شده.',show_alert=True); return True
                inv=conn.execute("SELECT quantity FROM inventory WHERE user_id=? AND item_key=?",(row['seller_id'],row['item_key'])).fetchone()
                buyer=conn.execute("SELECT hop_points FROM users WHERE user_id=?",(row['buyer_id'],)).fetchone()
                if not inv or inv['quantity']<row['quantity']:
                    conn.execute("UPDATE trade_offers SET status='cancelled' WHERE id=? AND status='pending'",(tid,)); conn.commit(); await q.answer('فروشنده دیگر این مقدار آیتم را ندارد.',show_alert=True); return True
                if not buyer or buyer['hop_points']<row['price']:
                    conn.rollback(); await q.answer('هاپ کافی برای خرید نداری.',show_alert=True); return True
                cur=conn.execute("UPDATE inventory SET quantity=quantity-? WHERE user_id=? AND item_key=? AND quantity>=?",(row['quantity'],row['seller_id'],row['item_key'],row['quantity']))
                if cur.rowcount != 1: conn.rollback(); await q.answer('موجودی فروشنده تغییر کرد؛ دوباره تلاش کن.',show_alert=True); return True
                conn.execute("DELETE FROM inventory WHERE user_id=? AND item_key=? AND quantity<=0",(row['seller_id'],row['item_key']))
                conn.execute("INSERT INTO inventory(user_id,item_key,quantity) VALUES(?,?,?) ON CONFLICT(user_id,item_key) DO UPDATE SET quantity=quantity+excluded.quantity,updated_at=CURRENT_TIMESTAMP",(row['buyer_id'],row['item_key'],row['quantity']))
                cur=conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?",(row['price'],row['buyer_id'],row['price']))
                if cur.rowcount != 1: conn.rollback(); await q.answer('هاپ کافی نداری؛ معامله لغو شد.',show_alert=True); return True
                conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?",(row['price'],row['seller_id']))
                cur=conn.execute("UPDATE trade_offers SET status='accepted' WHERE id=? AND status='pending'",(tid,))
                if cur.rowcount != 1: conn.rollback(); await q.answer('این معامله همزمان تغییر کرد.',show_alert=True); return True
                conn.commit()
            except Exception:
                conn.rollback(); raise
        add_collection(q.from_user.id,'item:'+row['item_key'])
        await q.edit_message_text(f"✅ *معامله انجام شد!*\n\n📦 {RARE_ITEMS.get(row['item_key'],{}).get('name',row['item_key'])} × {row['quantity']}\n💰 {row['price']:,.0f} هاپ پرداخت شد.",parse_mode='Markdown')
        return True
    return False

async def auction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q=update.callback_query
    data=q.data
    if data.startswith('auction_bidinfo_'):
        try: aid=int(data.rsplit('_',1)[1])
        except: await q.answer('آگهی نامعتبر است.',show_alert=True); return True
        auction_expire_old()
        with db_conn() as conn:
            row=conn.execute("SELECT * FROM auctions WHERE id=? AND status='active'",(aid,)).fetchone()
        if not row:
            await q.answer('این آگهی دیگر فعال نیست.',show_alert=True); return True
        current=float(row['current_bid'] or 0)
        minimum=max(current+1,int(current*(1+AUCTION_MIN_BID_INCREMENT))) if current>0 else max(1,int(row['price']*0.10))
        await q.answer(f'💹 حداقل پیشنهاد: {minimum:,.0f} هاپ\nبا «پیشنهاد {aid} مبلغ» ثبت کن.',show_alert=True)
        return True
    if not data.startswith('auction_buy_'): return False
    aid=int(data.rsplit('_',1)[1])
    auction_expire_old()
    with db_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row=conn.execute("SELECT * FROM auctions WHERE id=?",(aid,)).fetchone()
            if not row or row['status']!='active': conn.rollback(); await q.answer('این آگهی دیگر فعال نیست.',show_alert=True); return True
            if q.from_user.id==row['seller_id']:
                conn.rollback(); await q.answer('❌ نمی‌توانی آگهی خودت را بخری.',show_alert=True); return True
            buyer=conn.execute("SELECT hop_points FROM users WHERE user_id=?",(q.from_user.id,)).fetchone()
            if not buyer or buyer['hop_points']<row['price']:
                conn.rollback(); await q.answer('💰 هاپ کافی نداری.',show_alert=True); return True
            fee=int(row['price']*AUCTION_FEE); seller_net=row['price']-fee
            current_bidder=row['current_bidder_id']; current_bid=float(row['current_bid'] or 0)
            if current_bidder and current_bid>0:
                conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?",(current_bid,current_bidder))
                conn.execute("UPDATE auction_bids SET status='refunded' WHERE auction_id=? AND status='active'",(aid,))
            cur=conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?",(row['price'],q.from_user.id,row['price']))
            if cur.rowcount != 1: conn.rollback(); await q.answer('💰 موجودی تغییر کرده؛ دوباره تلاش کن.',show_alert=True); return True
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?",(seller_net,row['seller_id']))
            conn.execute("INSERT INTO inventory(user_id,item_key,quantity) VALUES(?,?,?) ON CONFLICT(user_id,item_key) DO UPDATE SET quantity=quantity+excluded.quantity,updated_at=CURRENT_TIMESTAMP",(q.from_user.id,row['item_key'],row['quantity']))
            cur=conn.execute("UPDATE auctions SET status='sold' WHERE id=? AND status='active'",(aid,))
            if cur.rowcount != 1: conn.rollback(); await q.answer('این آگهی همزمان خریداری شد.',show_alert=True); return True
            conn.commit()
        except Exception:
            conn.rollback(); raise
    add_collection(q.from_user.id,'item:'+row['item_key'])
    await q.answer('🎉 خرید موفق بود!',show_alert=True)
    await q.edit_message_text(f"🛒 *فروخته شد!*\n\n📦 {RARE_ITEMS.get(row['item_key'],{}).get('name',row['item_key'])} × {row['quantity']}\n💰 مبلغ: {row['price']:,.0f} هاپ\n🏪 کارمزد حراج: {fee:,.0f} هاپ",parse_mode='Markdown')
    return True

# =========================
# Happy Doggy 2.0 - Progression
# XP + Daily Missions + Login Streak + Achievements
# =========================
MISSION_DEFS = {
    "hop_3":     {"title": "🐾 ۳ بار هاپ بزن", "action": "hop", "target": 3, "xp": 120, "points": 500},
    "hop_5":     {"title": "🐾 ۵ بار هاپ بزن", "action": "hop", "target": 5, "xp": 200, "points": 900},
    "bone_1":    {"title": "🦴 یک استخوان صید کن", "action": "bone", "target": 1, "xp": 180, "points": 700},
    "dog_1":     {"title": "🐕 بخش سگ را فعال کن", "action": "dog", "target": 1, "xp": 100, "points": 400},
    "game_1":    {"title": "🎲 یک بازی انجام بده", "action": "game", "target": 1, "xp": 150, "points": 600},
    "factory_1": {"title": "🏭 یک بار کارخانه را بررسی کن", "action": "factory", "target": 1, "xp": 150, "points": 600},
    "bank_1":    {"title": "🏦 یک بار بانک را بررسی کن", "action": "bank", "target": 1, "xp": 150, "points": 600},
}

ACHIEVEMENT_DEFS = {
    "first_hop":   {"title": "🐾 اولین هاپ", "desc": "اولین هاپ خودت را ثبت کن", "xp": 100},
    "hop_10":      {"title": "🔥 هاپ‌زن حرفه‌ای", "desc": "۱۰ هاپ ثبت کن", "xp": 250},
    "hop_100":     {"title": "👑 سلطان هاپ", "desc": "۱۰۰ هاپ ثبت کن", "xp": 1000},
    "level_10":    {"title": "⭐️ سطح ۱۰", "desc": "به سطح ۱۰ برس", "xp": 500},
    "streak_7":    {"title": "🔥 هفته طلایی", "desc": "۷ روز پشت سر هم وارد شو", "xp": 700},
}


def init_progression_tables():
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS daily_missions (
            user_id INTEGER NOT NULL,
            mission_date TEXT NOT NULL,
            slot INTEGER NOT NULL,
            mission_key TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            target INTEGER NOT NULL,
            reward_xp INTEGER DEFAULT 0,
            reward_points REAL DEFAULT 0,
            claimed INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, mission_date, slot)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS achievements (
            user_id INTEGER NOT NULL,
            achievement_key TEXT NOT NULL,
            unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, achievement_key)
        )""")
        conn.commit()


def _today_key():
    return datetime.now().date().isoformat()


def _xp_for_next_level(level):
    # رشد ملایم تا لول‌های بالا؛ XP مستقل از پول بازی است.
    if level >= 1000:
        return 0
    return 250 + (level * 125)


def get_progression_level(xp):
    level = 1
    needed = _xp_for_next_level(level)
    while level < 1000 and xp >= needed:
        xp -= needed
        level += 1
        needed = _xp_for_next_level(level)
    return level, xp, needed


def add_xp(user_id, amount):
    if amount <= 0:
        return None
    with db_conn() as conn:
        row = conn.execute("SELECT xp FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return None
        old_level, _, _ = get_progression_level(int(row["xp"] or 0))
        new_xp = int(row["xp"] or 0) + int(amount)
        new_level, progress, needed = get_progression_level(new_xp)
        conn.execute("UPDATE users SET xp=? WHERE user_id=?", (new_xp, user_id))
        conn.commit()
    return {"old_level": old_level, "level": new_level, "progress": progress, "needed": needed, "xp": new_xp}


def ensure_daily_login(user_id):
    today = _today_key()
    with db_conn() as conn:
        row = conn.execute("SELECT login_streak,last_login_date FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return None
        if row["last_login_date"] == today:
            return {"streak": int(row["login_streak"] or 0), "reward": 0, "new_day": False}
        streak = int(row["login_streak"] or 0) + 1
        # اگر بیش از یک روز فاصله افتاده باشد، streak از نو شروع می‌شود.
        if row["last_login_date"]:
            try:
                gap = (datetime.fromisoformat(today).date() - datetime.fromisoformat(row["last_login_date"]).date()).days
                if gap > 1:
                    streak = 1
            except Exception:
                streak = 1
        reward = min(1000 + (streak * 250), 10000)
        conn.execute("UPDATE users SET login_streak=?, last_login_date=?, hop_points=hop_points+? WHERE user_id=?",
                     (streak, today, reward, user_id))
        conn.commit()
    add_xp(user_id, 50)
    season_record_user(user_id, "daily_login")
    check_achievements(user_id)
    return {"streak": streak, "reward": reward, "new_day": True}


def ensure_daily_missions(user_id):
    today = _today_key()
    with db_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM daily_missions WHERE user_id=? AND mission_date=?",
                             (user_id, today)).fetchone()["c"]
        if count >= 3:
            return
        keys = list(MISSION_DEFS.keys())
        # deterministic per user/day, بدون نیاز به ذخیره RNG
        seed = sum(ord(c) for c in f"{user_id}:{today}")
        rng = random.Random(seed)
        rng.shuffle(keys)
        selected = keys[:3]
        conn.execute("DELETE FROM daily_missions WHERE user_id=? AND mission_date=?", (user_id, today))
        for slot, key in enumerate(selected, 1):
            m = MISSION_DEFS[key]
            conn.execute("INSERT INTO daily_missions(user_id,mission_date,slot,mission_key,target,reward_xp,reward_points) VALUES(?,?,?,?,?,?,?)",
                         (user_id, today, slot, key, m["target"], m["xp"], m["points"]))
        conn.commit()


def record_mission_action(user_id, action, amount=1):
    ensure_daily_missions(user_id)
    today = _today_key()
    with db_conn() as conn:
        rows = conn.execute("SELECT * FROM daily_missions WHERE user_id=? AND mission_date=? AND claimed=0",
                            (user_id, today)).fetchall()
        changed = []
        for r in rows:
            m = MISSION_DEFS.get(r["mission_key"])
            if not m or m["action"] != action:
                continue
            new_progress = min(r["target"], r["progress"] + amount)
            if new_progress != r["progress"]:
                conn.execute("UPDATE daily_missions SET progress=? WHERE user_id=? AND mission_date=? AND slot=?",
                             (new_progress, user_id, today, r["slot"]))
                changed.append((r["mission_key"], new_progress, r["target"]))
        conn.commit()
    return changed


def claim_completed_missions(user_id):
    ensure_daily_missions(user_id)
    today = _today_key()
    total_xp = 0
    total_points = 0
    titles = []
    with db_conn() as conn:
        rows = conn.execute("SELECT * FROM daily_missions WHERE user_id=? AND mission_date=? AND claimed=0 AND progress>=target",
                            (user_id, today)).fetchall()
        for r in rows:
            conn.execute("UPDATE daily_missions SET claimed=1 WHERE user_id=? AND mission_date=? AND slot=?",
                         (user_id, today, r["slot"]))
            total_xp += int(r["reward_xp"] or 0)
            total_points += int(r["reward_points"] or 0)
            titles.append(MISSION_DEFS.get(r["mission_key"], {}).get("title", r["mission_key"]))
        if total_points:
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (total_points, user_id))
        conn.commit()
    if total_xp:
        add_xp(user_id, total_xp)
    if titles:
        season_record_user(user_id, "mission", len(titles))
    return titles, total_xp, total_points


def check_achievements(user_id):
    with db_conn() as conn:
        u = conn.execute("SELECT total_hops,level,login_streak FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not u:
            return []
        candidates = []
        if u["total_hops"] >= 1: candidates.append("first_hop")
        if u["total_hops"] >= 10: candidates.append("hop_10")
        if u["total_hops"] >= 100: candidates.append("hop_100")
        if u["level"] >= 10: candidates.append("level_10")
        if u["login_streak"] >= 7: candidates.append("streak_7")
        unlocked = []
        for key in candidates:
            exists = conn.execute("SELECT 1 FROM achievements WHERE user_id=? AND achievement_key=?", (user_id, key)).fetchone()
            if exists:
                continue
            conn.execute("INSERT INTO achievements(user_id,achievement_key) VALUES(?,?)", (user_id, key))
            unlocked.append(key)
        conn.commit()
    for key in unlocked:
        add_xp(user_id, ACHIEVEMENT_DEFS[key]["xp"])
    return unlocked


async def missions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "", user.first_name)
    login = ensure_daily_login(user.id)
    ensure_daily_missions(user.id)
    claimed, cxp, cpoints = claim_completed_missions(user.id)
    with db_conn() as conn:
        u = conn.execute("SELECT * FROM users WHERE user_id=?", (user.id,)).fetchone()
        rows = conn.execute("SELECT * FROM daily_missions WHERE user_id=? AND mission_date=? ORDER BY slot", (user.id, _today_key())).fetchall()
        ach = conn.execute("SELECT achievement_key FROM achievements WHERE user_id=? ORDER BY unlocked_at DESC", (user.id,)).fetchall()
    lvl, progress, needed = get_progression_level(int(u["xp"] or 0))
    text = "🎯 *مأموریت‌های امروز*\n\n"
    for r in rows:
        status = "✅ انجام شد" if r["progress"] >= r["target"] else f"{r['progress']}/{r['target']}"
        if r["claimed"]:
            status = "🎁 دریافت شد"
        text += f"{status} — {MISSION_DEFS[r['mission_key']]['title']}\n"
        text += f"   ⭐️ +{r['reward_xp']} XP | 🦴 +{int(r['reward_points']):,}\n"
    text += f"\n⭐️ XP: {u['xp']:,}\n🏅 Level: {lvl} ({progress}/{needed})\n🔥 Streak: {u['login_streak']} روز"
    if login and login["new_day"]:
        text += f"\n\n🎁 ورود امروز: +{login['reward']:,} هاپ"
    if claimed:
        text += f"\n\n🎉 مأموریت تکمیل شد: {len(claimed)} مورد\n⭐️ +{cxp} XP | 🦴 +{cpoints:,}"
    if ach:
        text += f"\n\n🏆 دستاوردها: {len(ach)}"
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type == "private":
        ensure_user(user.id, user.username or "", user.first_name)
        ensure_daily_login(user.id)
        ensure_daily_missions(user.id)

        args = context.args
        if args and args[0].startswith("ref_"):
            try:
                inviter_id = int(args[0].split("_")[1])
                if inviter_id != user.id:
                    with db_conn() as conn:
                        exists = conn.execute("SELECT 1 FROM referrals WHERE user_id=?", (user.id,)).fetchone()
                        if not exists:
                            conn.execute(
                                "INSERT OR IGNORE INTO referrals (user_id, inviter_id, rewarded) VALUES (?,?,0)",
                                (user.id, inviter_id)
                            )
                            conn.commit()
            except (ValueError, IndexError):
                logger.warning("Invalid referral start payload for user %s", user.id, exc_info=True)

        keyboard = ReplyKeyboardMarkup([
            ["🎁 دعوت دوستان", "🐾 هاپوهام"],
            ["🎒 کیف", "🐕 انواع سگ"],
            ["🛒 مارکت", "📖 راهنما"],
            ["📊 لیدربرد"],
        ], resize_keyboard=True)

        await send_stage_message(
            update.message,
            f"🐕 *سلام {user.first_name} عزیز!*\n\n"
            f"به *Happy Doggy* خوش اومدی 🦴✨\n\n"
            f"📌 بازی اصلی داخل گروهه — منو به گروهت اضافه کن.\n"
            f"🎯 از دکمه‌های پایین برای شروع استفاده کن!",
            stage="start",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return

    ensure_user(user.id, user.username or "", user.first_name)
    ensure_group(chat.id, chat.title or "")
    await send_stage_message(
        update.message,
        "🐕 *Happy Doggy فعال شد!*\n\n"
        "🦴 توی گروه بنویس *هاپ* تا هاپ پوینت بگیری!\n"
        "⏳ هر چند دقیقه یک‌بار می‌تونی هاپ کنی.\n\n"
        "📖 *پروفایل* — وضعیت تو\n"
        "🏆 *برترین* — لیدربرد\n"
        "❓ *راهنما* — راهنمای بازی",
        stage="start",
        parse_mode="Markdown")

async def handle_hop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text(f"🐕 هاپ فقط توی گروه کار می‌کنه!\nمنو به گروهت اضافه کن 👉 @{BOT_USERNAME}")
        return

    ensure_user(user.id, user.username or "", user.first_name)
    ensure_group(chat.id, chat.title or "")

    _jailed, _jail_row = is_in_jail(user.id)
    if _jailed:
        _rel = datetime.fromisoformat(_jail_row["release_at"])
        _left = max(0, int((_rel - datetime.now()).total_seconds()))
        _m, _s = divmod(_left, 60)
        await update.message.reply_text(
            f"⛓️ *{user.first_name}، تو زندانی هستی!*\n"
            f"📌 دلیل: {_jail_row['reason']}\n"
            f"⌛️ {_m} دقیقه و {_s} ثانیه تا آزادی",
            parse_mode="Markdown"
        )
        return

    try:
        with db_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            u = conn.execute("SELECT * FROM users WHERE user_id=?", (user.id,)).fetchone()
            grp = conn.execute("SELECT * FROM groups WHERE group_id=?", (chat.id,)).fetchone()
            if not u or not grp:
                conn.rollback()
                await update.message.reply_text("⚠️ اطلاعات کاربر/گروه آماده نیست؛ دوباره تلاش کن.")
                return

            now = datetime.now()
            city_lvl = get_city_level(grp)
            effective_cd = city_hop_cooldown(city_lvl) + crisis_hop_penalty(chat.id)
            if u["last_hop"]:
                try:
                    diff = (now - datetime.fromisoformat(u["last_hop"])).total_seconds()
                except (TypeError, ValueError):
                    logger.warning("Invalid last_hop for user %s", user.id, exc_info=True)
                    diff = effective_cd
                if diff < effective_cd:
                    remaining = int(effective_cd - diff)
                    m, s = divmod(remaining, 60)
                    conn.rollback()
                    await update.message.reply_text(
                        f"⏳ {user.first_name}، هنوز باید صبر کنی!\n"
                        f"⌛️ {m} دقیقه و {s} ثانیه دیگه می‌تونی هاپ کنی 🐾"
                    )
                    return

            current_level = u["level"]
            reward = calc_hop_reward(current_level)
            try:
                if "hop_boost_until" in u.keys() and u["hop_boost_until"] and datetime.fromisoformat(u["hop_boost_until"]) > now:
                    reward = int(reward * float(u["hop_boost_mult"] or 1.0))
            except (TypeError, ValueError):
                logger.warning("Invalid hop boost data for user %s", user.id, exc_info=True)

            decree_mult = get_decree_hop_multiplier(chat.id)
            if decree_mult != 1.0:
                reward = int(reward * decree_mult)
            seasonal_key, seasonal = get_seasonal_event()
            reward = int(reward * float(seasonal.get("hop_mult", 1.0)))
            daily_prize = get_decree_daily_prize(chat.id)
            reward += daily_prize

            new_hops = u["total_hops"] + 1
            new_level = get_level(new_hops)
            leveled_up = new_level > current_level

            changed = conn.execute(
                "UPDATE users SET hop_points=hop_points+?, total_hops=total_hops+1, level=?, last_hop=? "
                "WHERE user_id=?",
                (reward, new_level, now.isoformat(), user.id)
            )
            if changed.rowcount != 1:
                conn.rollback()
                await update.message.reply_text("⏳ هاپ همزمان ثبت شد؛ چند ثانیه دیگه دوباره تلاش کن.")
                return

            conn.execute("UPDATE groups SET total_hops=total_hops+1 WHERE group_id=?", (chat.id,))
            new_points = float(u["hop_points"]) + reward
            conn.execute(
                "INSERT INTO economy_ledger(user_id,asset,amount,balance_before,balance_after,action,reference_id) VALUES(?,?,?,?,?,?,?)",
                (user.id, "hop", reward, float(u["hop_points"]), new_points, "hop_reward", str(update.message.message_id))
            )
            conn.commit()

    except sqlite3.Error:
        logger.exception("Database error during hop: user=%s group=%s", user.id, chat.id)
        await update.message.reply_text("🚨 خطای موقت دیتابیس؛ هاپ ثبت نشد. دوباره تلاش کن.")
        return

    record_mission_action(user.id, "hop")
    season_record_user(user.id, "hop")
    xp_info = add_xp(user.id, 25)
    unlocked = check_achievements(user.id)
    next_lvl_hops = hops_for_next_level(new_level)
    progress = f"{new_hops}/{next_lvl_hops}" if new_level < 1000 else "MAX"
    decree_tag = " 🎉" if decree_mult != 1.0 else ""
    prize_tag = f"\n🎁 جایزه روزانه: +{daily_prize:,}" if daily_prize > 0 else ""
    event_tag = f"\n🎪 رویداد: {seasonal['name']}" if seasonal.get("hop_mult", 1.0) != 1.0 else ""
    msg = (
        f"🐕 *HOP!* {user.first_name}\n\n"
        f"🦴 +*{reward:,}* هاپ پوینت{decree_tag}\n"
        f"💰 موجودی: *{new_points:,.0f}*\n"
        f"⭐️ سطح: *{new_level}* | هاپ: *{progress}*\n"
        f"{ui_bar(new_hops, next_lvl_hops if new_level < 1000 else max(new_hops, 1))}"
        f"{prize_tag}{event_tag}"
    )
    if leveled_up:
        msg += f"\n\n🎉 *LEVEL UP!* رسیدی به سطح *{new_level}* ✨"
    if xp_info:
        msg += f"\n⭐️ +25 XP | XP Level {xp_info['level']}"
    if unlocked:
        msg += "\n🏆 *دستاورد جدید:* " + "، ".join(ACHIEVEMENT_DEFS[k]["title"] for k in unlocked)

    await send_stage_message(update.message, msg, stage="levelup" if leveled_up else "hop", parse_mode="Markdown")

    if new_hops == 1 and is_referral_enabled():
        with db_conn() as rconn:
            ref = rconn.execute(
                "SELECT * FROM referrals WHERE user_id=? AND rewarded=0", (user.id,)
            ).fetchone()
            if ref:
                inviter_id = ref["inviter_id"]
                reward_s = get_referral_reward_sender()
                reward_j = get_referral_reward_joiner()
                rconn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (reward_j, user.id))
                inviter = rconn.execute("SELECT user_id FROM users WHERE user_id=?", (inviter_id,)).fetchone()
                if inviter:
                    rconn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (reward_s, inviter_id))
                rconn.execute("UPDATE referrals SET rewarded=1 WHERE user_id=?", (user.id,))
                rconn.commit()
                await update.message.reply_text(
                    f"🎁 *جایزه دعوت!*\n\n+{reward_j:,} هاپ پوینت به خاطر ورود با لینک دعوت دریافت کردی!",
                    parse_mode="Markdown"
                )
                if inviter:
                    try:
                        await context.bot.send_message(
                            chat_id=inviter_id,
                            text=f"🎉 *دعوت موفق!*\n\n{user.first_name} با لینک دعوت تو وارد شد و اولین هاپش رو زد!\n💰 +{reward_s:,} هاپ پوینت به حسابت واریز شد 🦴",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        logger.warning("Could not notify inviter %s", inviter_id, exc_info=True)

    with db_conn() as conn:
        fresh_grp = conn.execute("SELECT * FROM groups WHERE group_id=?", (chat.id,)).fetchone()
    expire_old_crises()
    await trigger_city_crisis(update, context, chat.id, fresh_grp)
    await check_stray_dog(update, context)


async def hook_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🦴 این دستور فقط توی گروه کار می‌کنه!")
        return
    ensure_user(user.id, user.username or "", user.first_name)
    conn = get_db()
    u    = conn.execute("SELECT * FROM users WHERE user_id=?", (user.id,)).fetchone()
    hook = conn.execute("SELECT * FROM hooks WHERE user_id=?", (user.id,)).fetchone()
    conn.close()
    if u["level"] < HOOK_MIN_LEVEL:
        await update.message.reply_text(f"🔒 برای خرید قلاب باید حداقل سطح {HOOK_MIN_LEVEL} باشی!\nسطح فعلیت: {u['level']} ⭐️")
        return
    cost_buy, cooldown, _ = HOOK_DATA[1]
    if not hook:
        kb = InlineKeyboardMarkup([[
            cbtn(f"✅ خرید قلاب ({cost_buy:,} پوینت)", callback_data=f"buyhook_{user.id}"),
            cbtn("❌ انصراف", callback_data="cancel"),
        ]])
        await update.message.reply_text(
            f"🦴 *قلاب استخوان‌گیری*\n\n💰 هزینه: {cost_buy:,} هاپ پوینت\n"
            f"⌛️ cooldown اولیه: {cooldown} ثانیه\n📦 موجودیت: {u['hop_points']:,.0f}\n\nبعد از خرید بنویس *استخوان* تا بندازی!",
            parse_mode="Markdown", reply_markup=kb)
        return
    lvl = hook["level"]
    _, cd, upgrade_cost = HOOK_DATA[lvl]
    now  = datetime.now()
    last = hook["last_cast"]
    if last:
        diff  = (now - datetime.fromisoformat(last)).total_seconds()
        ready = diff >= cd
        left  = max(0, int(cd - diff))
        status = "✅ آماده صید!" if ready else f"⌛️ {left} ثانیه مونده"
    else:
        status = "✅ آماده صید!"
    text = (f"🦴 *قلاب استخوان‌گیری*\n\n⭐️ سطح قلاب: {lvl}/{HOOK_MAX_LEVEL}\n"
            f"⌛️ cooldown: {cd} ثانیه\n🎯 وضعیت: {status}\n")
    if lvl < HOOK_MAX_LEVEL:
        text += f"\n💰 هزینه ارتقا: {upgrade_cost:,} هاپ پوینت"
    kb = []
    if lvl < HOOK_MAX_LEVEL:
        kb.append([cbtn(f"⬆️ ارتقا قلاب ({upgrade_cost:,})", callback_data=f"upgradehook_{user.id}")])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb) if kb else None)

async def cast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🦴 این دستور فقط توی گروه کار می‌کنه!")
        return
    ensure_user(user.id, user.username or "", user.first_name)
    conn = get_db()
    hook = conn.execute("SELECT * FROM hooks WHERE user_id=?", (user.id,)).fetchone()
    if not hook:
        conn.close()
        await update.message.reply_text("❌ هنوز قلاب نداری!\n📌 بنویس *قلاب* تا بخری 🦴", parse_mode="Markdown")
        return
    pending = conn.execute("SELECT * FROM pending_bones WHERE user_id=?", (user.id,)).fetchone()
    if pending:
        age = (datetime.now() - datetime.fromisoformat(pending["caught_at"])).total_seconds()
        if age < BONE_SELL_TIME:
            conn.close()
            left = int(BONE_SELL_TIME - age)
            kb = InlineKeyboardMarkup([[
                cbtn("💰 فروش", callback_data=f"sellbone_{user.id}"),
                cbtn("🍖 غذای سگ", callback_data=f"feeddog_{user.id}"),
            ]])
            _p_icon = get_bone_rarity(pending['bone_name'])
            _p_rarity = RARITY_ICON_MAP.get(_p_icon, "")
            await update.message.reply_text(
                f"⚠️ هنوز روی صید قبلیت تصمیم نگرفتی!\n\n"
                f"🦴 *{pending['bone_name']}*\n"
                f"🏷️ دسته: {_p_icon} {_p_rarity}\n"
                f"⚖️ وزن: {pending['weight']} kg\n"
                f"💰 ارزش: {pending['price']:,} هاپ پوینت\n\n"
                f"⌛️ {left} ثانیه فرصت داری!",
                parse_mode="Markdown", reply_markup=kb)
            return
        else:
            conn.execute("DELETE FROM pending_bones WHERE user_id=?", (user.id,))
    lvl = hook["level"]
    _, cd, _ = HOOK_DATA[lvl]
    grp = conn.execute("SELECT * FROM groups WHERE group_id=?", (chat.id,)).fetchone()
    cd  = city_fish_cooldown(get_city_level(grp), cd) if grp else cd
    now = datetime.now()
    if hook["last_cast"]:
        diff = (now - datetime.fromisoformat(hook["last_cast"])).total_seconds()
        if diff < cd:
            left = int(cd - diff)
            conn.close()
            left_m = left // 60
            left_s = left % 60
            if left_m > 0:
                time_str = f"{left_m} دقیقه و {left_s} ثانیه"
            else:
                time_str = f"{left_s} ثانیه"
            await update.message.reply_text(f"⌛️ قلابت هنوز توی آبه!\n🕐 {time_str} دیگه می‌تونی دوباره بندازی 🦴")
            return
    bone_name, weight, price, rarity_icon, rarity_name = catch_bone(lvl)
    caught_at = now.isoformat()
    rare_item_key = grant_rare_item_from_catch(user.id, rarity_icon)
    conn.execute("UPDATE hooks SET last_cast=? WHERE user_id=?", (caught_at, user.id))
    conn.execute("INSERT OR REPLACE INTO pending_bones (user_id,bone_name,weight,price,caught_at) VALUES (?,?,?,?,?)",
                 (user.id, bone_name, weight, price, caught_at))
    conn.execute("UPDATE groups SET total_bones=total_bones+1, total_fish=total_fish+1 WHERE group_id=?", (chat.id,))
    conn.commit()
    conn.close()
    kb = InlineKeyboardMarkup([[
        cbtn("💰 فروش", callback_data=f"sellbone_{user.id}"),
        cbtn("🍖 غذای سگ", callback_data=f"feeddog_{user.id}"),
    ]])
    if rarity_icon == "🔥":
        header = f"🔥🔥🔥 *{user.first_name} یه استخوان آتشی صید کرد!* 🔥🔥🔥"
    elif rarity_icon == "🔴":
        header = f"💥 *{user.first_name} یه استخوان کمیاب صید کرد!* 💥"
    elif rarity_icon == "🟠":
        header = f"✨ *{user.first_name} یه استخوان اسطوره‌ای صید کرد!* ✨"
    else:
        header = f"🎣 *{user.first_name} یه استخوان صید کرد!*"
    await send_stage_message(
        update.message,
        f"{header}\n\n"
        f"🦴 {bone_name}\n"
        f"🏷️ دسته: {rarity_icon} {rarity_name}\n"
        f"⚖️ وزن: {weight} kg\n"
        f"💰 ارزش فروش: {price:,} هاپ پوینت\n\n"
        f"⌛️ {BONE_SELL_TIME} ثانیه فرصت داری تصمیم بگیری!"
        + (f"\n\n🎁 *آیتم کمیاب پیدا کردی:* {RARE_ITEMS[rare_item_key]['name']}\n🎒 به کیفت اضافه شد!" if rare_item_key else ""),
        stage="hook", parse_mode="Markdown", reply_markup=kb)

async def dog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🐕 این دستور فقط توی گروه کار می‌کنه!")
        return
    ensure_user(user.id, user.username or "", user.first_name)
    conn = get_db()
    u   = conn.execute("SELECT * FROM users WHERE user_id=?", (user.id,)).fetchone()
    dog = conn.execute("SELECT * FROM dogs WHERE user_id=?", (user.id,)).fetchone()
    conn.close()
    if dog:
        await show_dog_panel(update, user, u, dog)
        return
    if u["level"] < DOG_MIN_LEVEL:
        await update.message.reply_text(f"🔒 برای خرید سگ باید حداقل سطح {DOG_MIN_LEVEL} باشی!\nسطح فعلیت: {u['level']} ⭐️")
        return
    if u["hop_points"] < DOG_COST:
        await update.message.reply_text(f"💸 برای خرید سگ به {DOG_COST:,} هاپ پوینت نیاز داری!\nموجودیت: {u['hop_points']:,.0f} 🦴")
        return
    await update.message.reply_text(
        "🐕 *خرید سگ*\n\n"
        "نوع سگت رو انتخاب کن؛ هر نوع ویژگی و قیمت متفاوتی داره.\n"
        "🍖 هر ۲ ساعت باید بهش غذا (استخوان) بدی!",
        parse_mode="Markdown", reply_markup=dog_type_buttons(user.id))

async def show_dog_panel(update, user, u, dog):
    now       = datetime.now()
    fed_until = dog["fed_until"]
    is_fed    = fed_until and datetime.fromisoformat(fed_until) > now
    pending   = calc_dog_points(dog) + dog["points_box"]
    rate, capacity, upgrade_cost = DOG_LEVEL_DATA.get(dog["level"], (0.1, 5000, 500))
    rank_name, rank_mult = DOG_RANKS.get(dog["rank"], ("نامشخص", 1.0))
    dog_type = DOG_TYPES.get(dog["dog_type"], DOG_TYPES["stray"]) if "dog_type" in dog.keys() else DOG_TYPES["stray"]
    effective_rate = rate * rank_mult
    if is_fed:
        fed_left = int((datetime.fromisoformat(fed_until) - now).total_seconds())
        fm, fs = divmod(fed_left, 60)
        fh, fm = divmod(fm, 60)
        fed_str = f"✅ سیر ({fh}:{fm:02d}:{fs:02d} مونده)"
    else:
        fed_str = "😋 گشنه — تولید متوقفه!"
    text = (f"🐕 *سگت: {dog['name']}*\n\n🐾 نوع: {dog_type['name']}\n🎖 مقام: {rank_name}\n⭐️ سطح سگ: {dog['level']}/{DOG_MAX_LEVEL}\n"
            f"⚡️ تولید: {effective_rate:.2f} هاپ‌پوینت/ثانیه\n📦 جعبه: {pending:,.0f} / {capacity:,}\n🍖 شکم: {fed_str}\n")
    if dog["level"] < DOG_MAX_LEVEL:
        text += f"\n💰 هزینه ارتقا سطح: {upgrade_cost:,} هاپ‌پوینت"
    if dog["rank"] < 10:
        text += f"\n🌟 ارتقا مقام هر ۲ سطح یه بار"
    uid = user.id
    kb  = [
        [cbtn("📦 برداشت پوینت‌ها", callback_data=f"collect_{uid}")],
        [cbtn("🍖 خرید استخوان (غذا)", callback_data=f"feed_{uid}")],
    ]
    if dog["level"] < DOG_MAX_LEVEL:
        kb.append([cbtn(f"⬆️ ارتقا سطح ({upgrade_cost:,})", callback_data=f"upgradedog_{uid}")])
    if dog["rank"] < 10 and dog["level"] >= dog["rank"] * 2:
        kb.append([cbtn("🏅 ارتقا مقام", callback_data=f"rankup_{uid}")])
    kb.append([cbtn("✏️ تغییر اسم", callback_data=f"rename_{uid}")])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid_self = query.from_user.id

    def check_owner(uid):
        return uid_self == uid
    
    if data.startswith("vmeow_"):
        target_id = int(data.split("_")[1])
        voter_id = query.from_user.id
        
        if voter_id == target_id:
            await query.answer("❌ داداش نمیتونی به خودت رای بدی!", show_alert=True)
            return

        if "meow_votes" not in context.bot_data:
            context.bot_data["meow_votes"] = {}
        if target_id not in context.bot_data["meow_votes"]:
            context.bot_data["meow_votes"][target_id] = set()
            
        votes_set = context.bot_data["meow_votes"][target_id]
        
        if voter_id in votes_set:
            await query.answer("❌ شما قبلاً رای داده‌اید!", show_alert=True)
            return
            
        votes_set.add(voter_id)
        current_votes = len(votes_set)
        
        if current_votes >= 3:
            await query.answer("🔒 کاربر به زندان فرستاده شد!", show_alert=True)
            
            conn = get_db()
            now = datetime.now()
            release_time = (now + timedelta(minutes=15)).isoformat()
            conn.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?,?,?)", 
                        (target_id, "", "کاربر"))
            conn.execute(
                "INSERT OR REPLACE INTO jail (user_id, jailed_at, release_at, reason) VALUES (?, ?, ?, ?)",
                (target_id, now.isoformat(), release_time, "گفتن کلمه ممنوعه میو")
            )
            conn.commit()
            conn.close()
            
            del context.bot_data["meow_votes"][target_id]
            
            await query.edit_message_text(
                f"🔒 کاربر به دلیل گفتن «میو» با ۳ رای موافق به مدت ۱۵ دقیقه زندانی شد! 😾",
                parse_mode="Markdown"
            )
            return
        else:
            await query.answer("✅ رای شما ثبت شد.")
            keyboard = [[
                cbtn(f"رای به زندانی شدن ({current_votes}/3) ⚖️", callback_data=f"vmeow_{target_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_reply_markup(reply_markup=reply_markup)
            return

        
    if data.startswith("buyhook_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid): await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        conn = get_db()
        u    = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        cost, _, _ = HOOK_DATA[1]
        if u["hop_points"] < cost: conn.close(); await query.answer(f"پوینت کافی نداری! لازم: {cost:,}", show_alert=True); return
        conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (cost, uid))
        conn.execute("INSERT OR IGNORE INTO hooks (user_id,level) VALUES (?,1)", (uid,))
        conn.commit(); conn.close()
        await query.edit_message_text("🎉 *قلاب استخوان‌گیری خریدی!*\n\n🦴 حالا توی گروه بنویس *استخوان* تا بندازی!\n\n⏳ در حال بازگشت به پنل قلاب...", parse_mode="Markdown")
        await asyncio.sleep(2)
        await hook_cmd_for_user(query, uid)
        return

    if data.startswith("upgradehook_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid): await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        conn = get_db()
        u    = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        hook = conn.execute("SELECT * FROM hooks WHERE user_id=?", (uid,)).fetchone()
        if not hook or hook["level"] >= HOOK_MAX_LEVEL: conn.close(); await query.answer("قلابت ماکسه!", show_alert=True); return
        _, _, upgrade_cost = HOOK_DATA[hook["level"]]
        if u["hop_points"] < upgrade_cost: conn.close(); await query.answer(f"پوینت کافی نداری! لازم: {upgrade_cost:,}", show_alert=True); return
        new_lvl = hook["level"] + 1
        _, new_cd, _ = HOOK_DATA[new_lvl]
        conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (upgrade_cost, uid))
        conn.execute("UPDATE hooks SET level=? WHERE user_id=?", (new_lvl, uid))
        conn.commit(); conn.close()
        await query.edit_message_text(f"⬆️ *قلاب ارتقا پیدا کرد!*\n\n⭐️ سطح جدید: {new_lvl}\n⌛️ cooldown جدید: {new_cd} ثانیه\n\n⏳ در حال بازگشت به پنل قلاب...", parse_mode="Markdown")
        await asyncio.sleep(2)
        await hook_cmd_for_user(query, uid)
        return

    if data.startswith("sellbone_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid): await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        conn    = get_db()
        pending = conn.execute("SELECT * FROM pending_bones WHERE user_id=?", (uid,)).fetchone()
        if not pending: conn.close(); await query.answer("استخوانی برای فروش نیست!", show_alert=True); return
        age = (datetime.now() - datetime.fromisoformat(pending["caught_at"])).total_seconds()
        if age > BONE_SELL_TIME:
            conn.execute("DELETE FROM pending_bones WHERE user_id=?", (uid,))
            conn.commit(); conn.close(); await query.answer("⌛️ وقتت تموم شد! استخوان از دست رفت.", show_alert=True); return
        price = pending["price"]
        conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (price, uid))
        conn.execute("DELETE FROM pending_bones WHERE user_id=?", (uid,))
        conn.commit(); conn.close()
        await query.edit_message_text(f"💰 *{pending['bone_name']}* رو فروختی!\n\n⚖️ وزن: {pending['weight']} kg\n🦴 +{price:,} هاپ پوینت دریافت کردی!", parse_mode="Markdown")
        return

    if data.startswith("feeddog_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid): await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        conn    = get_db()
        pending = conn.execute("SELECT * FROM pending_bones WHERE user_id=?", (uid,)).fetchone()
        dog     = conn.execute("SELECT * FROM dogs WHERE user_id=?", (uid,)).fetchone()
        if not pending: conn.close(); await query.answer("استخوانی نداری!", show_alert=True); return
        if not dog: conn.close(); await query.answer("سگی نداری! اول سگ بخر 🐕", show_alert=True); return
        age = (datetime.now() - datetime.fromisoformat(pending["caught_at"])).total_seconds()
        if age > BONE_SELL_TIME:
            conn.execute("DELETE FROM pending_bones WHERE user_id=?", (uid,))
            conn.commit(); conn.close(); await query.answer("⌛️ وقتت تموم شد! استخوان از دست رفت.", show_alert=True); return
        now       = datetime.now()
        fed_until = dog["fed_until"]
        duration  = calc_feed_duration(pending["bone_name"], pending["weight"])
        new_fed   = (datetime.fromisoformat(fed_until) + timedelta(seconds=duration)) if (fed_until and datetime.fromisoformat(fed_until) > now) else (now + timedelta(seconds=duration))
        rarity_icon = get_bone_rarity(pending["bone_name"])
        rarity_name = RARITY_ICON_MAP.get(rarity_icon, "")
        duration_min = duration // 60
        conn.execute("UPDATE dogs SET fed_until=? WHERE user_id=?", (new_fed.isoformat(), uid))
        conn.execute("DELETE FROM pending_bones WHERE user_id=?", (uid,))
        conn.commit(); conn.close()
        await query.edit_message_text(
            f"🍖 *{pending['bone_name']}* رو به سگت دادی!\n\n"
            f"⚖️ وزن: {pending['weight']} kg\n"
            f"🏷️ دسته: {rarity_icon} {rarity_name}\n"
            f"⏱️ مدت سیری: {duration_min} دقیقه\n"
            f"😋 سگت تا {new_fed.strftime('%H:%M')} سیره! 🐕",
            parse_mode="Markdown"
        )
        return

    if data.startswith("confirm_delete_user_"):
        if not is_admin(uid_self):
            await query.answer("فقط ادمین اصلی!", show_alert=True); return
        target_id = int(data.split("_")[3])
        if target_id in ADMIN_IDS:
            await query.answer("❌ نمیشه ادمین اصلی رو حذف کرد!", show_alert=True); return
        conn = get_db()
        tu = conn.execute("SELECT first_name FROM users WHERE user_id=?", (target_id,)).fetchone()
        if not tu:
            conn.close()
            await query.edit_message_text("❌ کاربر پیدا نشد!")
            return
        name = tu["first_name"]
        for table in ["users", "dogs", "hooks", "pending_bones", "inventory", "trade_offers", "auctions", "bank", "transfers",
                      "user_strays", "jail", "factories", "sub_admins"]:
            conn.execute(f"DELETE FROM {table} WHERE user_id=?", (target_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(
            f"🗑 *کاربر {name} از دیتابیس حذف شد!*\n\n"
            f"🪪 آیدی: `{target_id}`\n"
            f"تمام اطلاعاتش پاک شد.",
            parse_mode="Markdown"
        )
        return

    if data == "cancel":
        await query.edit_message_text("❌ عملیات لغو شد.")
        return

    if data.startswith("mythicinfo_"):
        parts = data.split("_")
        key = parts[1]; uid = int(parts[2])
        if not check_owner(uid):
            await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        d = DOG_TYPES.get(key)
        if not d:
            await query.answer("سگ نامعتبره!", show_alert=True); return
        await query.answer(f"{d['name']}\n✨ {d['ability']}", show_alert=True)
        return

    if data.startswith("buydog_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid): await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        conn = get_db()
        u    = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if u["hop_points"] < DOG_COST: conn.close(); await query.answer("پوینت کافی نداری!", show_alert=True); return
        conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (DOG_COST, uid))
        conn.execute("INSERT OR IGNORE INTO dogs (user_id,name,level,rank,points_box,last_collect) VALUES (?,'سگولو',1,1,0,?)", (uid, datetime.now().isoformat()))
        chat_id = query.message.chat_id
        conn.execute("UPDATE groups SET total_dogs=total_dogs+1 WHERE group_id=?", (chat_id,))
        conn.commit(); conn.close()
        await query.edit_message_text("🎉 *تبریک! سگت رو خریدی!*\n\n🐕 اسمش *سگولو* ه — می‌تونی عوضش کنی!\n🍖 یادت باشه هر ۲ ساعت استخوان بهش بدی!\n\n⏳ در حال بازگشت به پنل سگ...", parse_mode="Markdown")
        await asyncio.sleep(2)
        await dog_cmd_for_user(query, uid)
        return

    if data.startswith("collect_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid): await query.answer("این دکمه برای تو نیست! 🐕", show_alert=True); return
        conn = get_db()
        dog  = conn.execute("SELECT * FROM dogs WHERE user_id=?", (uid,)).fetchone()
        if not dog: conn.close(); await query.answer("سگی نداری!", show_alert=True); return
        pending = calc_dog_points(dog) + dog["points_box"]
        if pending < 1: conn.close(); await query.answer("📦 جعبه خالیه!", show_alert=True); return
        amount = int(pending)
        bonus = 0
        if dog["dog_type"] == "phoenix" and random.random() < 0.07:
            bonus = max(1, int(amount * 0.25))
            amount += bonus
        conn.execute("UPDATE dogs SET points_box=0,last_collect=? WHERE user_id=?", (datetime.now().isoformat(), uid))
        conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (amount, uid))
        conn.commit(); conn.close()
        bonus_text = f"\n🔥 پاداش ویژه ققنوس: +{bonus:,}" if bonus else ""
        await query.edit_message_text(f"✅ *{amount:,}* هاپ پوینت از جعبه سگت برداشت شد! 🦴{bonus_text}\n\n⏳ در حال بازگشت به پنل سگ...", parse_mode="Markdown")
        await asyncio.sleep(2)
        await dog_cmd_for_user(query, uid)
        return

    if data.startswith("feed_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid): await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        conn = get_db()
        u    = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        dog  = conn.execute("SELECT * FROM dogs WHERE user_id=?", (uid,)).fetchone()
        if not dog: conn.close(); await query.answer("سگی نداری!", show_alert=True); return
        if u["hop_points"] < BONE_COST: conn.close(); await query.answer(f"پوینت کافی نداری! لازم: {BONE_COST}", show_alert=True); return
        now       = datetime.now()
        fed_until = dog["fed_until"]
        duration  = calc_feed_duration("استخوان کوچیک 🦴", 0.2)
        new_fed   = (datetime.fromisoformat(fed_until) + timedelta(seconds=duration)) if (fed_until and datetime.fromisoformat(fed_until) > now) else (now + timedelta(seconds=duration))
        conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (BONE_COST, uid))
        conn.execute("UPDATE dogs SET fed_until=? WHERE user_id=?", (new_fed.isoformat(), uid))
        conn.commit(); conn.close()
        duration_min = duration // 60
        await query.edit_message_text(
            f"🍖 *استخوان کوچیک خریدی!*\n\n"
            f"💰 هزینه: {BONE_COST:,} هاپ پوینت\n"
            f"⏱️ مدت سیری: {duration_min} دقیقه\n"
            f"⏰ سگت تا {new_fed.strftime('%H:%M')} سیره! 🐕\n\n"
            f"⏳ در حال بازگشت به پنل سگ...",
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)
        await dog_cmd_for_user(query, uid)
        return

    if data.startswith("upgradedog_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid): await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        conn = get_db()
        u    = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        dog  = conn.execute("SELECT * FROM dogs WHERE user_id=?", (uid,)).fetchone()
        if not dog or dog["level"] >= DOG_MAX_LEVEL: conn.close(); await query.answer("سگت ماکسه!", show_alert=True); return
        _, _, cost = DOG_LEVEL_DATA[dog["level"]]
        if u["hop_points"] < cost: conn.close(); await query.answer(f"پوینت کافی نداری! لازم: {cost:,}", show_alert=True); return
        new_level = dog["level"] + 1
        conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (cost, uid))
        conn.execute("UPDATE dogs SET level=? WHERE user_id=?", (new_level, uid))
        conn.commit(); conn.close()
        new_rate, new_cap, _ = DOG_LEVEL_DATA[new_level]
        await query.edit_message_text(f"⬆️ *سگت ارتقا پیدا کرد!*\n\n⭐️ سطح جدید: {new_level}\n⚡️ تولید جدید: {new_rate:.2f} هاپ‌پوینت/ثانیه\n📦 ظرفیت جدید: {new_cap:,}\n\n⏳ در حال بازگشت به پنل سگ...", parse_mode="Markdown")
        await asyncio.sleep(2)
        await dog_cmd_for_user(query, uid)
        return

    if data.startswith("rankup_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid): await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        conn = get_db()
        dog  = conn.execute("SELECT * FROM dogs WHERE user_id=?", (uid,)).fetchone()
        if not dog or dog["rank"] >= 10: conn.close(); await query.answer("مقام سگت ماکسه!", show_alert=True); return
        if dog["level"] < dog["rank"] * 2: conn.close(); await query.answer(f"سگت باید حداقل سطح {dog['rank']*2} باشه!", show_alert=True); return
        new_rank = dog["rank"] + 1
        conn.execute("UPDATE dogs SET rank=?,level=1,points_box=0 WHERE user_id=?", (new_rank, uid))
        conn.commit(); conn.close()
        rank_name, rank_mult = DOG_RANKS[new_rank]
        await query.edit_message_text(f"🏅 *مقام ارتقا پیدا کرد!*\n\n🎖 مقام جدید: {rank_name}\n✨ ضریب تولید: {rank_mult}x\n\n⚠️ سطح سگ به ۱ برگشت اما قوی‌تر از قبله!\n\n⏳ در حال بازگشت به پنل سگ...", parse_mode="Markdown")
        await asyncio.sleep(2)
        await dog_cmd_for_user(query, uid)
        return

    if data.startswith("rename_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid): await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        context.user_data["waiting_rename"] = uid
        await query.edit_message_text("✏️ *اسم جدید سگت رو بنویس:*\n(حداکثر ۱۵ کاراکتر)", parse_mode="Markdown")
        return

async def handle_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    waiting = context.user_data.get("waiting_rename")
    if not waiting or waiting != user.id: return False
    new_name = update.message.text.strip()
    if len(new_name) > 15:
        await update.message.reply_text("❌ اسم نباید بیشتر از ۱۵ کاراکتر باشه!")
        return True
    if len(new_name) < 1:
        await update.message.reply_text("❌ اسم نمی‌تونه خالی باشه!")
        return True
    conn = get_db()
    conn.execute("UPDATE dogs SET name=? WHERE user_id=?", (new_name, user.id))
    conn.commit(); conn.close()
    context.user_data.pop("waiting_rename", None)
    await update.message.reply_text(f"✅ اسم سگت به *{new_name}* تغییر پیدا کرد! 🐕", parse_mode="Markdown")
    class _FakeQuery:
        def __init__(self, msg): self.message = msg
    await dog_cmd_for_user(_FakeQuery(update.message), user.id)
    return True

async def bank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🏦 بانک فقط توی گروه کار می‌کنه!")
        return

    jailed, jail_row = is_in_jail(user.id)
    if jailed:
        rel = datetime.fromisoformat(jail_row["release_at"])
        left = int((rel - datetime.now()).total_seconds())
        m, s = divmod(left, 60)
        await update.message.reply_text(
            f"⛓️ تو زندانی! نمی‌تونی به بانک دسترسی داشته باشی!\n"
            f"⌛️ {m} دقیقه و {s} ثانیه تا آزادی"
        )
        return

    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (user.id,)).fetchone()
    bank = conn.execute("SELECT * FROM bank WHERE user_id=?", (user.id,)).fetchone()
    conn.close()

    if not u:
        await update.message.reply_text("❌ اول توی گروه هاپ کن تا ثبت‌نام بشی!")
        return

    if u["level"] < BANK_MIN_LEVEL:
        await update.message.reply_text(
            f"🔒 برای باز کردن حساب بانکی باید حداقل سطح {BANK_MIN_LEVEL} باشی!\n"
            f"سطح فعلیت: {u['level']} ⭐️"
        )
        return

    if bank:
        await show_bank_panel(update, user, u, bank)
        return

    kb = InlineKeyboardMarkup([[
        cbtn(f"✅ افتتاح حساب ({BANK_OPEN_COST:,} پوینت)", callback_data=f"openbank_{user.id}"),
        cbtn("❌ انصراف", callback_data="cancel"),
    ]])
    await update.message.reply_text(
        f"🏦 *بانک هاپی*\n\n"
        f"💰 هزینه افتتاح: {BANK_OPEN_COST:,} هاپ پوینت\n"
        f"📈 سود روزانه: ۳٪ (حداکثر {BANK_MAX_INTEREST:,})\n"
        f"💳 شماره حساب ۱۲ رقمی اختصاصی\n"
        f"🔄 امکان کارت به کارت\n\n"
        f"موجودیت: {u['hop_points']:,.0f} 🦴",
        parse_mode="Markdown", reply_markup=kb
    )

async def show_bank_panel(update, user, u, bank):
    now = datetime.now()
    interest_ready = False
    if bank["last_interest"]:
        last_int = datetime.fromisoformat(bank["last_interest"])
        interest_ready = (now - last_int).total_seconds() >= 86400
    else:
        interest_ready = True

    interest_amount = min(bank["balance"] * BANK_INTEREST_RATE, BANK_MAX_INTEREST)

    text = (
        f"🏦 *بانک هاپی*\n\n"
        f"💳 شماره حساب: `{bank['account_number']}`\n"
        f"💰 موجودی بانک: {bank['balance']:,.0f} هاپ پوینت\n"
        f"👛 موجودی کیف: {u['hop_points']:,.0f} هاپ پوینت\n\n"
        f"📈 سود روزانه (۳٪): {interest_amount:,.0f}\n"
        f"{'✅ سود آماده دریافته!' if interest_ready else '⌛️ سود فردا قابل دریافته'}"
    )

    kb = [
        [cbtn("➕ واریز", callback_data=f"bank_deposit_{user.id}"),
         cbtn("➖ برداشت", callback_data=f"bank_withdraw_{user.id}")],
    ]
    if interest_ready and bank["balance"] > 0:
        kb.append([cbtn("💸 دریافت سود", callback_data=f"bank_interest_{user.id}")])
    kb.append([cbtn("🔄 تغییر شماره حساب", callback_data=f"bank_changenum_{user.id}")])

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

def parse_amount(text: str) -> int:
    text = text.strip().replace(",", "").replace("_", "")
    multipliers = {
        "k": 1_000, "کی": 1_000, "کا": 1_000,
        "m": 1_000_000, "میل": 1_000_000,
    }
    for suffix, mult in multipliers.items():
        if text.lower().endswith(suffix):
            try:
                return int(float(text[:-len(suffix)]) * mult)
            except:
                return -1
    try:
        return int(float(text))
    except:
        return -1

async def transfer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🧲 انتقال فقط توی گروه کار می‌کنه!")
        return

    jailed, _ = is_in_jail(user.id)
    if jailed:
        await update.message.reply_text("⛓️ تو زندانی! نمی‌تونی انتقال بدی!")
        return

    ensure_user(user.id, user.username or "", user.first_name)
    args = (update.message.text or "").split()
    target_user = None
    amount = -1

    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        if len(args) >= 2:
            amount = parse_amount(args[1])
    elif len(args) >= 3:
        amount = parse_amount(args[1])
        username = args[2].lstrip("@")
        with db_conn() as conn:
            row = conn.execute("SELECT user_id, first_name FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            await update.message.reply_text("❌ کاربری با این یوزرنیم پیدا نشد!")
            return
        class FakeUser:
            id = row["user_id"]
            first_name = row["first_name"]
        target_user = FakeUser()
    else:
        await update.message.reply_text(
            "📌 *انتقال هاپ*\n\n"
            "`انتقال {مبلغ} @یوزرنیم`\n"
            "یا روی پیام کاربر ریپلای کن و بنویس: `انتقال {مبلغ}`",
            parse_mode="Markdown"
        )
        return

    if not target_user or target_user.id == user.id:
        await update.message.reply_text("❌ نمی‌تونی به خودت انتقال بدی!")
        return
    if amount <= 0:
        await update.message.reply_text("❌ مبلغ نامعتبره!")
        return
    if amount < TRANSFER_MIN:
        await update.message.reply_text(f"❌ حداقل مبلغ انتقال: {TRANSFER_MIN:,} هاپ پوینت")
        return
    if amount > TRANSFER_MAX:
        await update.message.reply_text(f"❌ حداکثر مبلغ انتقال: {TRANSFER_MAX:,} هاپ پوینت")
        return

    # Atomic transaction: level, cooldown, balance and transfer timestamp are
    # all checked under BEGIN IMMEDIATE. This prevents double-spending races.
    try:
        with db_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            sender = conn.execute(
                "SELECT user_id, first_name, level, hop_points FROM users WHERE user_id=?",
                (user.id,)
            ).fetchone()
            if not sender or sender["level"] < TRANSFER_MIN_LEVEL:
                conn.rollback()
                await update.message.reply_text(f"🔒 برای انتقال باید حداقل سطح {TRANSFER_MIN_LEVEL} باشی!")
                return

            tr = conn.execute("SELECT last_transfer FROM transfers WHERE user_id=?", (user.id,)).fetchone()
            now = datetime.now()
            if tr and tr["last_transfer"]:
                try:
                    diff = (now - datetime.fromisoformat(tr["last_transfer"])).total_seconds()
                except (TypeError, ValueError):
                    logger.warning("Invalid transfer timestamp for user %s", user.id, exc_info=True)
                    diff = TRANSFER_COOLDOWN
                if diff < TRANSFER_COOLDOWN:
                    left = int(TRANSFER_COOLDOWN - diff)
                    conn.rollback()
                    await update.message.reply_text(f"⌛️ {left} ثانیه تا انتقال بعدی صبر کن!")
                    return

            target = conn.execute(
                "SELECT user_id, first_name, level FROM users WHERE user_id=?",
                (target_user.id,)
            ).fetchone()
            if not target or target["level"] < TRANSFER_MIN_LEVEL:
                conn.rollback()
                await update.message.reply_text(f"❌ کاربر مقصد باید حداقل سطح {TRANSFER_MIN_LEVEL} باشه!")
                return

            debit = conn.execute(
                "UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?",
                (amount, user.id, amount)
            )
            if debit.rowcount != 1:
                conn.rollback()
                await update.message.reply_text(
                    f"💰 موجودی کافی نداری!\nموجودی فعلی: {sender['hop_points']:,.0f}"
                )
                return

            credit = conn.execute(
                "UPDATE users SET hop_points=hop_points+? WHERE user_id=?",
                (amount, target_user.id)
            )
            if credit.rowcount != 1:
                conn.rollback()
                logger.error("Transfer credit failed: sender=%s target=%s amount=%s", user.id, target_user.id, amount)
                await update.message.reply_text("⚠️ انتقال انجام نشد؛ موجودی شما تغییر نکرده است.")
                return

            conn.execute(
                "INSERT INTO transfers (user_id, last_transfer) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET last_transfer=excluded.last_transfer",
                (user.id, now.isoformat())
            )
            new_balance = float(sender["hop_points"]) - amount
            conn.execute(
                "INSERT INTO economy_ledger(user_id,asset,amount,balance_before,balance_after,action,counterparty_id,reference_id) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (user.id, "hop", -amount, float(sender["hop_points"]), new_balance, "transfer_out", target_user.id, str(update.message.message_id))
            )
            conn.execute(
                "INSERT INTO economy_ledger(user_id,asset,amount,balance_before,balance_after,action,counterparty_id,reference_id) "
                "SELECT user_id, ?, ?, hop_points-?, hop_points, ?, ?, ? FROM users WHERE user_id=?",
                ("hop", amount, amount, "transfer_in", user.id, str(update.message.message_id), target_user.id)
            )
            conn.commit()

    except sqlite3.Error:
        logger.exception("Database error during transfer: user=%s target=%s amount=%s", user.id, target_user.id, amount)
        await update.message.reply_text("🚨 خطای موقت دیتابیس؛ انتقال انجام نشد. دوباره تلاش کن.")
        return

    await send_stage_message(
        update.message,
        f"💸 *انتقال با موفقیت انجام شد*\n\n"
        f"{UI['money']} مبلغ: *{amount:,}* هاپ پوینت\n"
        f"👤 گیرنده: *{target['first_name']}*\n"
        f"👛 موجودی جدید: *{new_balance:,.0f}*",
        stage="hop",
        parse_mode="Markdown"
    )


def get_active_crisis(group_id: int):
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM city_crises WHERE group_id=? AND status='active' ORDER BY id DESC LIMIT 1",
            (group_id,)
        ).fetchone()

def get_active_penalty(group_id: int):
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM city_crisis_penalties WHERE group_id=?", (group_id,)
        ).fetchone()
        if not row:
            return None
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now():
            conn.execute("DELETE FROM city_crisis_penalties WHERE group_id=?", (group_id,))
            conn.commit()
            return None
        return row

def apply_crisis_penalty(group_id: int, crisis_key: str):
    c = CRISIS_TYPES[crisis_key]
    expires = (datetime.now() + timedelta(seconds=c["fix_cooldown"])).isoformat()
    with db_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO city_crisis_penalties
               (group_id, penalty_type, penalty_value, expires_at)
               VALUES (?,?,?,?)""",
            (group_id, c["penalty_type"], c["penalty_value"], expires)
        )
        conn.commit()

def resolve_crisis(crisis_id: int, decision: str, resolver_id: int = None):
    with db_conn() as conn:
        conn.execute(
            """UPDATE city_crises SET status=?, decision=?, resolved_by=?, resolved_at=?
               WHERE id=?""",
            ("resolved" if decision != "ignore" else "ignored",
             decision, resolver_id, datetime.now().isoformat(), crisis_id)
        )
        conn.commit()

def expire_old_crises():
    with db_conn() as conn:
        old = conn.execute(
            """SELECT * FROM city_crises WHERE status='active' AND datetime(replace(expires_at,'T',' ')) <= datetime('now')"""
        ).fetchall()
        for row in old:
            conn.execute(
                "UPDATE city_crises SET status='ignored', decision='timeout' WHERE id=?",
                (row["id"],)
            )
            apply_crisis_penalty(row["group_id"], row["crisis_type"])
        if old:
            conn.commit()
    return old

def crisis_hop_penalty(group_id: int) -> int:
    p = get_active_penalty(group_id)
    if p and p["penalty_type"] == "hop_cooldown":
        return p["penalty_value"]
    return 0

def crisis_dog_multiplier(group_id: int) -> float:
    p = get_active_penalty(group_id)
    if not p:
        return 1.0
    if p["penalty_type"] == "dog_freeze":
        return 0.0
    if p["penalty_type"] == "dog_slow":
        return 0.70
    return 1.0

def crisis_factory_multiplier(group_id: int) -> float:
    p = get_active_penalty(group_id)
    if not p:
        return 1.0
    if p["penalty_type"] == "factory_freeze":
        return 0.0
    if p["penalty_type"] == "factory_slow":
        return 0.50
    return 1.0

async def trigger_city_crisis(update, context, group_id: int, grp: dict):
    if get_active_crisis(group_id):
        return
    if grp["treasury"] < CRISIS_MIN_TREASURY:
        return
    if random.random() > CRISIS_TRIGGER_CHANCE:
        return

    crisis_key = random.choice(list(CRISIS_TYPES.keys()))
    c = CRISIS_TYPES[crisis_key]
    max_cost = int(grp["treasury"] * c["treasury_cost"])
    expires_at = (datetime.now() + timedelta(seconds=c["timeout"])).isoformat()

    with db_conn() as conn:
        conn.execute(
            """INSERT INTO city_crises (group_id, crisis_type, status, expires_at)
               VALUES (?,?,'active',?)""",
            (group_id, crisis_key, expires_at)
        )
        conn.commit()
        crisis_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    mayor = get_mayor(group_id)
    mayor_mention = ""
    if mayor:
        mayor_mention = f"📣 شهردار @{mayor['username'] or mayor['first_name']} باید تصمیم بگیره!\n\n"

    kb = InlineKeyboardMarkup([
        [cbtn(f"💰 پرداخت از خزانه ({max_cost:,} هاپ)", callback_data=f"crisis_pay_{crisis_id}_{group_id}")],
        [cbtn("🏛 استفاده از منابع شهر", callback_data=f"crisis_resource_{crisis_id}_{group_id}")],
        [cbtn("😤 نادیده گرفتن (خطرناک!)", callback_data=f"crisis_ignore_{crisis_id}_{group_id}")],
    ])

    await update.message.reply_text(
        f"🚨 *بحران شهری!*\n\n"
        f"{c['name']}\n\n"
        f"📋 {c['desc']}\n\n"
        f"{mayor_mention}"
        f"⏳ *۱۰ دقیقه* فرصت تصمیم‌گیری دارید!\n\n"
        f"━━━━━━━━━━━━\n"
        f"✅ پرداخت از خزانه: حل کامل + {c['reward']:,} پاداش\n"
        f"🔧 استفاده از منابع: حل جزئی، بدون پاداش\n"
        f"❌ نادیده گرفتن: {c['penalty']}",
        parse_mode="Markdown",
        reply_markup=kb
    )

async def handle_crisis_callback(query, data, user, context) -> bool:
    if not data.startswith("crisis_"):
        return False

    parts = data.split("_")
    if len(parts) < 4:
        return False

    action = parts[1]
    crisis_id = int(parts[2])
    group_id = int(parts[3])

    with db_conn() as conn:
        crisis = conn.execute(
            "SELECT * FROM city_crises WHERE id=?", (crisis_id,)
        ).fetchone()

    if not crisis or crisis["status"] != "active":
        await query.answer("❌ این بحران دیگه فعال نیست!", show_alert=True)
        return True

    if datetime.fromisoformat(crisis["expires_at"]) <= datetime.now():
        resolve_crisis(crisis_id, "timeout")
        apply_crisis_penalty(group_id, crisis["crisis_type"])
        await query.edit_message_text(
            "⏰ *وقت تموم شد!*\n\nبحران مدیریت نشد و شهر جریمه گرفت.",
            parse_mode="Markdown"
        )
        return True

    mayor = get_mayor(group_id)
    c = CRISIS_TYPES[crisis["crisis_type"]]

    if action == "pay":
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار می‌تونه تصمیم بگیره!", show_alert=True)
            return True

        with db_conn() as conn:
            grp = conn.execute("SELECT * FROM groups WHERE group_id=?", (group_id,)).fetchone()

        cost = int(grp["treasury"] * c["treasury_cost"])
        if grp["treasury"] < cost:
            await query.answer(f"❌ خزانه کافی نیست! لازم: {cost:,}", show_alert=True)
            return True

        with db_conn() as conn:
            conn.execute(
                "UPDATE groups SET treasury=treasury-? WHERE group_id=?", (cost, group_id)
            )
            conn.execute(
                "UPDATE users SET hop_points=hop_points+? WHERE user_id=?",
                (c["reward"], mayor["user_id"])
            )
            conn.commit()

        resolve_crisis(crisis_id, "pay", user.id)

        await query.edit_message_text(
            f"✅ *بحران مدیریت شد!*\n\n"
            f"{c['name']}\n\n"
            f"💰 {cost:,} هاپ از خزانه پرداخت شد.\n"
            f"🏆 شهردار {c['reward']:,} پاداش گرفت!\n\n"
            f"🏙 شهر دوباره آروم شد 🐾",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                group_id,
                f"🏛 *شهردار بحران رو مدیریت کرد!*\n\n{c['name']} حل شد.\n💰 {cost:,} از خزانه هزینه شد.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return True

    if action == "resource":
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار می‌تونه تصمیم بگیره!", show_alert=True)
            return True

        half_penalty = c["fix_cooldown"] // 2
        expires = (datetime.now() + timedelta(seconds=half_penalty)).isoformat()
        with db_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO city_crisis_penalties
                   (group_id, penalty_type, penalty_value, expires_at)
                   VALUES (?,?,?,?)""",
                (group_id, c["penalty_type"], c["penalty_value"] // 2, expires)
            )
            conn.commit()

        resolve_crisis(crisis_id, "resource", user.id)

        mins = half_penalty // 60
        await query.edit_message_text(
            f"🔧 *بحران تا حدی کنترل شد!*\n\n"
            f"{c['name']}\n\n"
            f"📉 جریمه نصف شد: {mins} دقیقه اثر می‌ذاره.\n"
            f"💡 دفعه بعد از خزانه پرداخت کن تا کامل حل بشه!",
            parse_mode="Markdown"
        )
        return True

    if action == "ignore":
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار می‌تونه تصمیم بگیره!", show_alert=True)
            return True

        resolve_crisis(crisis_id, "ignore", user.id)
        apply_crisis_penalty(group_id, crisis["crisis_type"])

        mins = c["fix_cooldown"] // 60
        await query.edit_message_text(
            f"😤 *بحران نادیده گرفته شد!*\n\n"
            f"{c['name']}\n\n"
            f"⚠️ جریمه فعال شد: {c['penalty']}\n"
            f"⏳ مدت: {mins} دقیقه\n\n"
            f"دفعه بعد بهتر تصمیم بگیر! 🏛",
            parse_mode="Markdown"
        )
        return True

    return False

async def crisis_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🚨 این دستور فقط توی گروه کار می‌کنه!")
        return

    crisis = get_active_crisis(chat.id)
    penalty = get_active_penalty(chat.id)

    if not crisis and not penalty:
        await update.message.reply_text("✅ *شهر در آرامشه!* هیچ بحران یا جریمه‌ای فعال نیست 🏙", parse_mode="Markdown")
        return

    text = "🚨 *وضعیت بحران شهر*\n\n"

    if crisis:
        c = CRISIS_TYPES.get(crisis["crisis_type"], {})
        exp = datetime.fromisoformat(crisis["expires_at"])
        left = max(0, int((exp - datetime.now()).total_seconds()))
        m, s = divmod(left, 60)
        text += (
            f"🔴 *بحران فعال:*\n"
            f"{c.get('name', crisis['crisis_type'])}\n"
            f"⏳ {m} دقیقه و {s} ثانیه فرصت باقیه\n\n"
        )

    if penalty:
        exp_p = datetime.fromisoformat(penalty["expires_at"])
        left_p = max(0, int((exp_p - datetime.now()).total_seconds()))
        mp, sp = divmod(left_p, 60)
        penalty_labels = {
            "hop_cooldown": "🐾 کولداون هاپ بیشتر",
            "factory_freeze": "🏭 کارخانه متوقف",
            "factory_slow": "🏭 کارخانه کند",
            "dog_freeze": "🐕 سگ‌ها متوقف",
            "dog_slow": "🐕 سگ‌ها کند",
        }
        label = penalty_labels.get(penalty["penalty_type"], penalty["penalty_type"])
        text += (
            f"⚠️ *جریمه فعال:*\n"
            f"{label}\n"
            f"⏳ {mp} دقیقه و {sp} ثانیه مونده\n"
        )

    await update.message.reply_text(text, parse_mode="Markdown")

async def check_stray_dog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    conn = get_db()
    grp = conn.execute("SELECT * FROM groups WHERE group_id=?", (chat.id,)).fetchone()
    stray = conn.execute("SELECT * FROM stray_dogs WHERE group_id=?", (chat.id,)).fetchone()
    conn.close()

    if not grp:
        return

    if stray:
        return

    if grp["total_hops"] % STRAY_TRIGGER_HOPS != 0:
        return

    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO stray_dogs (group_id, tries_left, current_cost, appeared_at, rescuer_ids)
        VALUES (?, ?, ?, ?, '')
    """, (chat.id, STRAY_MAX_TRIES, STRAY_BASE_COST, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([[
        cbtn(f"🐕 نجات ({STRAY_BASE_COST:,} پوینت)", callback_data=f"rescue_{chat.id}"),
    ]])
    await update.message.reply_text(
        f"🐕 *یه سگ خیابونی ظاهر شد!*\n\n"
        f"😿 این سگ بیچاره کنار خیابونه و به کمک نیاز داره!\n"
        f"🍀 شانس نجات: ۳۰٪\n"
        f"💰 هزینه تلاش: {STRAY_BASE_COST:,} هاپ پوینت\n"
        f"🔁 تعداد تلاش باقی‌مونده: {STRAY_MAX_TRIES}\n\n"
        f"کی اول نجاتش میده؟",
        parse_mode="Markdown", reply_markup=kb
    )

async def rescue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    group_id = int(data.split("_")[1])
    uid = query.from_user.id

    jailed, _ = is_in_jail(uid)
    if jailed:
        await query.answer("⛓️ تو زندانی! نمی‌تونی کمک کنی!", show_alert=True)
        return

    conn = get_db()
    stray = conn.execute("SELECT * FROM stray_dogs WHERE group_id=?", (group_id,)).fetchone()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()

    if not stray:
        conn.close()
        await query.answer("❌ این سگ دیگه اینجا نیست!", show_alert=True)
        return

    rescuers = stray["rescuer_ids"].split(",") if stray["rescuer_ids"] else []
    if str(uid) in rescuers:
        conn.close()
        await query.answer("❌ تو قبلاً تلاش کردی!", show_alert=True)
        return

    cost = stray["current_cost"]

    if not u or u["hop_points"] < cost:
        conn.close()
        await query.answer(f"❌ پوینت کافی نداری! لازم: {cost:,}", show_alert=True)
        return

    conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (cost, uid))

    success = random.random() < STRAY_CHANCE
    tries_left = stray["tries_left"] - 1
    rescuers.append(str(uid))
    new_cost = int(cost * STRAY_COST_MULT)

    if success:
        conn.execute("DELETE FROM stray_dogs WHERE group_id=?", (group_id,))
        conn.execute("""
            INSERT OR IGNORE INTO user_strays (user_id, count) VALUES (?, 0)
        """, (uid,))
        conn.execute("UPDATE user_strays SET count=count+1 WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        await query.edit_message_text(
            f"🎉 *{query.from_user.first_name} سگ رو نجات داد!*\n\n"
            f"🐕 سگ خیابونی الان در امنیته!\n"
            f"🏅 +۱ به آمار نجات سگت اضافه شد!",
            parse_mode="Markdown"
        )
    elif tries_left <= 0:
        conn.execute("DELETE FROM stray_dogs WHERE group_id=?", (group_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(
            f"😢 *سگ خیابونی فرار کرد!*\n\n"
            f"متأسفانه هیچ‌کس نتونست این سگ رو نجات بده...\n"
            f"شاید دفعه بعد شانس بیشتری داشته باشید 🐾",
            parse_mode="Markdown",
            reply_markup=None
        )
    else:
        conn.execute("""
            UPDATE stray_dogs SET tries_left=?, current_cost=?, rescuer_ids=?
            WHERE group_id=?
        """, (tries_left, new_cost, ",".join(rescuers), group_id))
        conn.commit()
        conn.close()

        kb = InlineKeyboardMarkup([[
            cbtn(f"🐕 تلاش دوباره ({new_cost:,} پوینت)", callback_data=f"rescue_{group_id}"),
        ]])
        await query.edit_message_text(
            f"😿 *{query.from_user.first_name} موفق نشد!*\n\n"
            f"سگ هنوز اینجاست ولی ترسیده‌تره...\n"
            f"🔁 تلاش باقی‌مونده: {tries_left}\n"
            f"💰 هزینه بعدی: {new_cost:,} هاپ پوینت",
            parse_mode="Markdown", reply_markup=kb
        )

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_sub_admin(user_id: int) -> bool:
    with db_conn() as conn:
        return conn.execute("SELECT 1 FROM sub_admins WHERE user_id=?", (user_id,)).fetchone() is not None

def is_any_admin(user_id: int) -> bool:
    return is_admin(user_id) or is_sub_admin(user_id)

async def add_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ باید روی پیام فرد موردنظر ریپلای کنی!")
        return
    target = update.message.reply_to_message.from_user
    if target.id in ADMIN_IDS:
        await update.message.reply_text("⚠️ این کاربر ادمین اصلیه!")
        return
    if is_sub_admin(target.id):
        await update.message.reply_text(f"⚠️ {target.first_name} قبلاً ادمین شده!")
        return
    ensure_user(target.id, target.username or "", target.first_name)
    with db_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sub_admins (user_id, username, first_name, added_by) VALUES (?,?,?,?)",
            (target.id, target.username or "", target.first_name, user.id)
        )
        conn.commit()
    await update.message.reply_text(
        f"✅ *{target.first_name}* به عنوان ادمین اضافه شد!\n\n"
        f"🔑 دسترسی‌ها:\n"
        f"• افزایش/کاهش پوینت\n"
        f"• افزایش/کاهش لول",
        parse_mode="Markdown"
    )

async def remove_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ باید روی پیام فرد موردنظر ریپلای کنی!")
        return
    target = update.message.reply_to_message.from_user
    if target.id in ADMIN_IDS:
        await update.message.reply_text("❌ نمیشه ادمین اصلی رو حذف کرد!")
        return
    if not is_sub_admin(target.id):
        await update.message.reply_text(f"⚠️ {target.first_name} ادمین نیست!")
        return
    with db_conn() as conn:
        conn.execute("DELETE FROM sub_admins WHERE user_id=?", (target.id,))
        conn.commit()
    await update.message.reply_text(f"✅ دسترسی ادمین *{target.first_name}* حذف شد!", parse_mode="Markdown")

async def delete_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ باید روی پیام کاربر موردنظر ریپلای کنی!")
        return
    target = update.message.reply_to_message.from_user
    if target.id in ADMIN_IDS:
        await update.message.reply_text("❌ نمیشه ادمین اصلی رو حذف کرد!")
        return
    tu = get_user(target.id)
    if not tu:
        await update.message.reply_text("❌ این کاربر در دیتابیس نیست!")
        return
    kb = InlineKeyboardMarkup([[
        cbtn("✅ بله، حذف کن", callback_data=f"confirm_delete_user_{target.id}"),
        cbtn("❌ انصراف", callback_data="cancel"),
    ]])
    await update.message.reply_text(
        f"⚠️ *آیا مطمئنی؟*\n\n"
        f"👤 کاربر: {target.first_name}\n"
        f"🪪 آیدی: `{target.id}`\n"
        f"💰 موجودی: {tu['hop_points']:,.0f}\n"
        f"⭐️ سطح: {tu['level']}\n\n"
        f"تمام اطلاعات این کاربر (پوینت، سگ، قلاب، بانک و ...) حذف میشه!",
        parse_mode="Markdown", reply_markup=kb
    )

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_any_admin(user.id):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ باید روی پیام فرد موردنظر ریپلای کنی!\n\n"
            "📋 دستورات:\n"
            "• افزایش پوینت [عدد]\n"
            "• کاهش پوینت [عدد]\n"
            "• افزایش لول [عدد]\n"
            "• کاهش لول [عدد]"
        )
        return
    target = update.message.reply_to_message.from_user
    tu = get_user(target.id)
    if not tu:
        await update.message.reply_text("❌ این کاربر هنوز ثبت‌نام نکرده!")
        return
    parts = update.message.text.strip().split()
    if len(parts) < 3:
        await update.message.reply_text("❌ عدد رو هم بنویس! مثلاً: افزایش پوینت 500")
        return
    try:
        amount = int(parts[2].replace(",", ""))
        if amount <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ عدد نامعتبره!")
        return

    action = f"{parts[0]} {parts[1]}"
    conn = get_db()

    if action == "افزایش پوینت":
        conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (amount, target.id))
        conn.commit(); conn.close()
        await update.message.reply_text(
            f"✅ *{amount:,}* هاپ پوینت به *{target.first_name}* اضافه شد!\n"
            f"💰 موجودی جدید: {tu['hop_points'] + amount:,.0f}",
            parse_mode="Markdown"
        )
    elif action == "کاهش پوینت":
        conn.execute("UPDATE users SET hop_points=MAX(0,hop_points-?) WHERE user_id=?", (amount, target.id))
        conn.commit(); conn.close()
        await update.message.reply_text(
            f"✅ *{amount:,}* هاپ پوینت از *{target.first_name}* کم شد!\n"
            f"💰 موجودی جدید: {max(0, tu['hop_points'] - amount):,.0f}",
            parse_mode="Markdown"
        )
    elif action == "افزایش لول":
        new_lvl = min(1000, tu["level"] + amount)
        new_hops = LEVEL_THRESHOLDS[new_lvl - 2] if new_lvl >= 2 else 0
        conn.execute("UPDATE users SET level=?, total_hops=? WHERE user_id=?", (new_lvl, new_hops, target.id))
        conn.commit(); conn.close()
        await update.message.reply_text(
            f"⭐️ لول *{target.first_name}* از {tu['level']} به *{new_lvl}* رسید!",
            parse_mode="Markdown"
        )
    elif action == "کاهش لول":
        new_lvl = max(1, tu["level"] - amount)
        new_hops = LEVEL_THRESHOLDS[new_lvl - 2] if new_lvl >= 2 else 0
        conn.execute("UPDATE users SET level=?, total_hops=? WHERE user_id=?", (new_lvl, new_hops, target.id))
        conn.commit(); conn.close()
        await update.message.reply_text(
            f"⬇️ لول *{target.first_name}* از {tu['level']} به *{new_lvl}* رسید!",
            parse_mode="Markdown"
        )
    else:
        conn.close()

async def factory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🏭 کارخونه فقط توی گروه کار می‌کنه!")
        return
    ensure_user(user.id, user.username or "", user.first_name)
    u = get_user(user.id)
    if not u or u["level"] < FACTORY_MIN_LEVEL:
        await update.message.reply_text(
            f"🔒 *کارخونه میویی*\n\n"
            f"برای ساخت کارخونه باید حداقل *سطح {FACTORY_MIN_LEVEL}* باشی!\n"
            f"⭐️ سطح فعلیت: {u['level'] if u else 1}\n\n"
            f"💪 بیشتر میو بزن تا سطحت بالا بره!",
            parse_mode="Markdown"
        )
        return
    factory = get_factory(user.id)
    if not factory:
        kb = InlineKeyboardMarkup([[
            cbtn(
                f"🏗️ ساخت کارخونه ({FACTORY_BUILD_COST:,} پوینت)",
                callback_data=f"factory_build_{user.id}"
            ),
            cbtn("❌ انصراف", callback_data="cancel"),
        ]])
        await update.message.reply_text(
            f"🏭 *کارخونه میویی*\n\n"
            f"هنوز کارخونه نداری! 😿\n\n"
            f"💰 هزینه ساخت: {FACTORY_BUILD_COST:,} پوینت\n"
            f"👛 موجودیت: {u['hop_points']:,.0f}\n"
            f"🐕 کارگرهات (هاپوهای نجات‌داده): {get_stray_count_factory(user.id)}\n\n"
            f"✨ با کارخونه میتونی محصول تولید کنی و بفروشی!",
            parse_mode="Markdown", reply_markup=kb
        )
        return
    await show_factory_panel(update.message, user, u, factory)

async def show_factory_panel(message_obj, user, u, factory):
    workers = get_stray_count_factory(user.id)
    cap = WAREHOUSE_LEVELS[factory["warehouse_level"]][0]
    machine_cd = MACHINE_LEVELS[factory["machine_level"]][0]
    producing_status = "💤 بیکار"
    time_left_str = ""
    if check_production_done(factory):
        producing_status = "✅ محصول آماده جمع‌آوری!"
    elif factory["producing"] and factory["production_end"]:
        end = datetime.fromisoformat(factory["production_end"])
        left = int((end - datetime.now()).total_seconds())
        m, s = divmod(left, 60)
        producing_status = "⚙️ در حال تولید"
        time_left_str = f"\n└─ ⌛️ {m} دقیقه و {s} ثانیه تا آماده شدن"
    exp_needed = FACTORY_LEVEL_EXP.get(factory["level"], 0)
    if exp_needed > 0:
        filled = min(5, int((factory["exp"] / exp_needed) * 5))
        bar = "▰" * filled + "▱" * (5 - filled)
        exp_str = f"{factory['exp']}/{exp_needed} {bar}"
    else:
        exp_str = "MAX 🏆"
    product_name = FACTORY_PRODUCTS[factory["product_idx"]][0] if factory["producing"] else "—"
    text = (
        f"╮──「 🏭 کارخونه هاپویی 🐾 」\n\n"
        f"┐─ ⭐️ سطح کارخونه : {factory['level']}/{FACTORY_MAX_LEVEL}\n"
        f"└─ 📊 تجربه : {exp_str}\n\n"
        f"┐─ 🏗️ دستگاه : سطح {factory['machine_level']} | ⌛️ {machine_cd} ثانیه\n"
        f"┐─ 🧳 انبار : سطح {factory['warehouse_level']} | {factory['stock']}/{cap} محصول\n"
        f"└─ 🐕 کارگرها : {workers} هاپو\n\n"
        f"┐─ 🔄 وضعیت : {producing_status}\n"
        f"└─ 📦 محصول فعلی : {product_name}"
        f"{time_left_str}"
    )
    kb = []
    if check_production_done(factory):
        kb.append([cbtn(
            "📦 جمع‌آوری محصولات ✅", callback_data=f"factory_collect_{user.id}"
        )])
    kb.append([
        cbtn("🛒 تولید محصول", callback_data=f"factory_produce_{user.id}"),
        cbtn("💹 فروش در بازار", callback_data=f"factory_sell_{user.id}"),
    ])
    kb.append([
        cbtn("⬆️ ارتقا دستگاه", callback_data=f"factory_upgrade_machine_{user.id}"),
        cbtn("⬆️ ارتقا انبار",   callback_data=f"factory_upgrade_warehouse_{user.id}"),
    ])
    kb.append([
        cbtn("🐕 استخدام هاپوی خیابونی", callback_data=f"factory_hire_{user.id}"),
        cbtn(f"💰 خرید کارگر ({FACTORY_WORKER_COST:,})", callback_data=f"factory_buy_worker_{user.id}"),
    ])
    await message_obj.reply_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(kb))

async def factory_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data  = query.data
    uid_self = query.from_user.id

    def check_owner(uid):
        return uid_self == uid

    if data.startswith("factory_build_"):
        uid = int(data.split("_")[2])
        if not check_owner(uid):
            await query.answer("این دکمه برای تو نیست!", show_alert=True); return True
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if u["hop_points"] < FACTORY_BUILD_COST:
            conn.close()
            await query.answer(f"❌ پوینت کافی نداری! لازم: {FACTORY_BUILD_COST:,}", show_alert=True); return True
        if conn.execute("SELECT user_id FROM factories WHERE user_id=?", (uid,)).fetchone():
            conn.close()
            await query.answer("❌ قبلاً کارخونه ساختی!", show_alert=True); return True
        conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (FACTORY_BUILD_COST, uid))
        conn.execute("""
            INSERT INTO factories (user_id,level,exp,warehouse_level,machine_level,stock,producing,product_idx)
            VALUES (?,1,0,1,1,0,0,0)
        """, (uid,))
        conn.commit(); conn.close()
        await query.answer("✅ کارخونه ساخته شد!")
        await query.edit_message_text(
            f"🎉 *کارخونه‌ات ساخته شد!*\n\n"
            f"🏭 حالا می‌تونی محصول تولید کنی!\n"
            f"🐕 هر هاپوی خیابونی که نجات بدی = یه کارگر بیشتر\n"
            f"💰 یا با هاپ پوینت ({FACTORY_WORKER_COST:,} تا) کارگر بخر!\n\n"
            f"📌 بنویس *کارخونه* تا پنل رو ببینی",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("factory_produce_"):
        uid = int(data.split("_")[2])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        factory = get_factory(uid)
        if not factory:
            await query.answer("❌ کارخونه نداری!", show_alert=True); return True
        if factory["producing"] and factory["production_end"]:
            end = datetime.fromisoformat(factory["production_end"])
            if datetime.now() < end:
                left = int((end - datetime.now()).total_seconds())
                m, s = divmod(left, 60)
                await query.answer(f"⚙️ کارخونه داره کار می‌کنه! {m} دقیقه و {s} ثانیه مونده.", show_alert=True)
                return True
        if check_production_done(factory):
            await query.answer("📦 اول محصولات آماده رو جمع‌آوری کن!", show_alert=True)
            return True
        workers = get_stray_count_factory(uid)
        if workers == 0:
            await query.answer("❌ هیچ کارگری نداری! از دکمه «استخدام» هاپوی خیابونی بیار یا با پوینت بخر 🐕", show_alert=True)
            return True
        available = get_available_products(factory["level"])
        kb = []
        for idx, product in available:
            name, cost, base_price, min_lvl, exp_gain = product
            market_p, mult = get_market_price(idx)
            trend = "📈" if mult >= 1.2 else ("📉" if mult <= 0.75 else "➡️")
            kb.append([cbtn(
                f"{name} | {cost:,}🪙 | {market_p:,}{trend}",
                callback_data=f"factory_start_{uid}_{idx}"
            )])
        kb.append([cbtn("❌ انصراف", callback_data="cancel")])
        await query.answer()
        await query.edit_message_text(
            f"🛒 *انتخاب محصول برای تولید*\n\n"
            f"🐈 کارگران: {workers} | هر دوره {workers} محصول\n"
            f"⌛️ زمان هر دوره: {MACHINE_LEVELS[factory['machine_level']][0]} ثانیه\n\n"
            f"📊 قیمت‌های بازار هر ساعت عوض میشن!",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
        )
        return True

    if data.startswith("factory_start_"):
        parts = data.split("_")
        uid = int(parts[2])
        product_idx = int(parts[3])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        factory = get_factory(uid)
        u = get_user(uid)
        name, cost, base_price, min_lvl, exp_gain = FACTORY_PRODUCTS[product_idx]
        if u["hop_points"] < cost:
            await query.answer(f"❌ پوینت کافی نداری! هزینه: {cost:,}", show_alert=True); return True
        cap = WAREHOUSE_LEVELS[factory["warehouse_level"]][0]
        if factory["stock"] >= cap:
            await query.answer("❌ انبارت پره! اول بفروش!", show_alert=True); return True
        machine_cd = MACHINE_LEVELS[factory["machine_level"]][0]
        seasonal_factory_mult = get_seasonal_event()[1].get("factory_mult", 1.0)
        if seasonal_factory_mult > 1.0:
            machine_cd = max(1, int(machine_cd / seasonal_factory_mult))
        with db_conn() as _c:
            _dog = _c.execute("SELECT dog_type FROM dogs WHERE user_id=?", (uid,)).fetchone()
        if _dog and _dog["dog_type"] == "chronos":
            machine_cd = max(1, int(machine_cd * 0.80))
        try:
            if factory["boost_until"] and datetime.fromisoformat(factory["boost_until"]) > datetime.now():
                machine_cd = max(1, int(machine_cd / float(factory["boost_mult"] or 1.0)))
        except Exception:
            pass
        production_end = (datetime.now() + timedelta(seconds=machine_cd)).isoformat()
        with db_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            debit = conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?", (cost, uid, cost))
            if debit.rowcount != 1:
                conn.rollback(); await query.answer("❌ موجودی کافی نیست!", show_alert=True); return True
            cap2 = WAREHOUSE_LEVELS[factory["warehouse_level"]][0]
            started = conn.execute("""UPDATE factories SET producing=1, product_idx=?, production_end=?, last_produced=?
                WHERE user_id=? AND producing=0 AND stock < ?""",
                (product_idx, production_end, datetime.now().isoformat(), uid, cap2))
            if started.rowcount != 1:
                conn.rollback(); await query.answer("❌ کارخونه هم‌اکنون در حال تولید است یا انبار پر شده!", show_alert=True); return True
            conn.commit()
        workers = get_stray_count_factory(uid)
        m2, s2 = divmod(machine_cd, 60)
        await query.answer("⚙️ تولید شروع شد!")
        await query.edit_message_text(
            f"⚙️ *تولید شروع شد!*\n\n"
            f"📦 محصول: {name}\n"
            f"💰 هزینه: {cost:,} پوینت\n"
            f"🐈 کارگران: {workers}\n"
            f"⌛️ زمان دوره: {m2} دقیقه و {s2} ثانیه\n\n"
            f"بنویس *کارخونه* تا محصولات رو جمع‌آوری کنی!",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("factory_collect_"):
        uid = int(data.split("_")[2])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        factory = get_factory(uid)
        if not factory or not check_production_done(factory):
            await query.answer("⌛️ هنوز تولید تموم نشده!", show_alert=True); return True
        added = collect_production(uid)
        factory = get_factory(uid)
        product_name = FACTORY_PRODUCTS[factory["product_idx"]][0]
        await query.answer(f"📦 {added} محصول جمع‌آوری شد!")
        await query.edit_message_text(
            f"📦 *{added} عدد {product_name} به انبار اضافه شد!*\n\n"
            f"🧳 موجودی انبار: {factory['stock']}/{WAREHOUSE_LEVELS[factory['warehouse_level']][0]}\n"
            f"⭐️ سطح کارخونه: {factory['level']}\n\n"
            f"💹 بنویس *کارخونه* ← فروش در بازار",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("factory_sell_"):
        uid = int(data.split("_")[2])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        factory = get_factory(uid)
        if not factory:
            await query.answer("❌ کارخونه نداری!", show_alert=True); return True
        if factory["stock"] <= 0:
            await query.answer("❌ انبارت خالیه! اول محصول تولید کن.", show_alert=True); return True
        market_price, mult = get_market_price(factory["product_idx"])
        total_earn = market_price * factory["stock"]
        name = FACTORY_PRODUCTS[factory["product_idx"]][0]
        trend = "📈 بازار داغه!" if mult >= 1.5 else ("📉 بازار سرده..." if mult <= 0.7 else "➡️ بازار معمولیه")
        with db_conn() as conn:
            mp_row = conn.execute(
                "SELECT updated_at FROM market_prices WHERE product_idx=?", (factory["product_idx"],)
            ).fetchone()
        time_left_market = ""
        if mp_row and mp_row["updated_at"]:
            diff = (datetime.now() - datetime.fromisoformat(mp_row["updated_at"])).total_seconds()
            left = max(0, int(3600 - diff))
            m2, s2 = divmod(left, 60)
            time_left_market = f"\n🕐 قیمت تا {m2} دقیقه دیگه ثابته"
        kb = InlineKeyboardMarkup([[
            cbtn(
                f"✅ فروش همه ({total_earn:,} پوینت)",
                callback_data=f"factory_confirm_sell_{uid}"
            ),
            cbtn("❌ صبر می‌کنم", callback_data="cancel"),
        ]])
        await query.answer()
        await query.edit_message_text(
            f"💹 *بازار میویی*\n\n"
            f"📦 محصول: {name}\n"
            f"🧳 موجودی: {factory['stock']} عدد\n\n"
            f"💰 قیمت هر عدد: {market_price:,} (×{mult})\n"
            f"🤑 درآمد کل: {total_earn:,} پوینت\n"
            f"{trend}{time_left_market}\n\n"
            f"⚠️ قیمت‌ها هر ساعت عوض میشن!",
            parse_mode="Markdown", reply_markup=kb
        )
        return True

    if data.startswith("factory_confirm_sell_"):
        uid = int(data.split("_")[3])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        factory = get_factory(uid)
        if not factory or factory["stock"] <= 0:
            await query.answer("❌ انباری برای فروش نیست!", show_alert=True); return True
        market_price, mult = get_market_price(factory["product_idx"])
        total_earn = market_price * factory["stock"]
        product_name = FACTORY_PRODUCTS[factory["product_idx"]][0]
        sold_count = factory["stock"]

        today = datetime.now().strftime("%Y-%m-%d")
        with db_conn() as conn:
            sold_today_row = conn.execute(
                "SELECT COALESCE(SUM(amount),0) as total FROM transactions "
                "WHERE user_id=? AND type='factory_sell' AND DATE(created_at)=?",
                (uid, today)
            ).fetchone()
            sold_today = sold_today_row["total"] if sold_today_row else 0

        remaining_cap = max(0, FACTORY_DAILY_CAP - sold_today)
        if remaining_cap <= 0:
            await query.answer(f"❌ سقف فروش روزانه ({FACTORY_DAILY_CAP:,}) تموم شده! فردا بیا.", show_alert=True)
            return True
        if total_earn > remaining_cap:
            ratio = remaining_cap / total_earn
            sold_count = max(1, int(factory["stock"] * ratio))
            total_earn = market_price * sold_count

        tax = int(total_earn * FACTORY_SELL_TAX)
        net_earn = total_earn - tax

        with db_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            fresh = conn.execute("SELECT * FROM factories WHERE user_id=?", (uid,)).fetchone()
            if not fresh or fresh["stock"] < sold_count or fresh["product_idx"] != factory["product_idx"]:
                conn.rollback(); await query.answer("❌ موجودی کارخانه تغییر کرده؛ دوباره پنل را باز کن.", show_alert=True); return True
            sold_cur = conn.execute("UPDATE factories SET stock=stock-? WHERE user_id=? AND stock>=?", (sold_count, uid, sold_count))
            if sold_cur.rowcount != 1:
                conn.rollback(); await query.answer("❌ فروش انجام نشد؛ موجودی تغییر کرده.", show_alert=True); return True
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (net_earn, uid))
            conn.execute("INSERT INTO transactions (user_id, type, amount, created_at) VALUES (?,?,?,?)",
                         (uid, "factory_sell", total_earn, datetime.now().isoformat()))
            conn.commit()

        remaining_after = remaining_cap - total_earn
        cap_msg = f"\n📊 باقی‌مونده سقف امروز: {remaining_after:,}" if remaining_after > 0 else "\n🔴 سقف فروش امروز تموم شد!"
        profit_msg = "🤑 سود خوبی کردی!" if mult >= 1.2 else ("😿 ضرر کردی..." if mult < 1.0 else "😊 معامله منصفانه‌ای بود!")
        await query.answer(f"✅ {sold_count} عدد فروخته شد!")
        await query.edit_message_text(
            f"✅ *فروش انجام شد!*\n\n"
            f"📦 {sold_count} عدد {product_name} فروخته شد\n"
            f"💰 درآمد کل: {total_earn:,}\n"
            f"🏛 مالیات ۱۰٪: -{tax:,}\n"
            f"💵 خالص دریافتی: +{net_earn:,}\n"
            f"📊 ضریب بازار: ×{mult}\n\n"
            f"{profit_msg}{cap_msg}",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("factory_upgrade_machine_"):
        uid = int(data.split("_")[3])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        factory = get_factory(uid)
        u = get_user(uid)
        if factory["machine_level"] >= MACHINE_MAX_LEVEL:
            await query.answer("🏆 دستگاهت ماکسه!", show_alert=True); return True
        next_lvl = factory["machine_level"] + 1
        _, next_cost = MACHINE_LEVELS[next_lvl]
        if u["hop_points"] < next_cost:
            await query.answer(f"❌ پوینت کافی نداری! لازم: {next_cost:,}", show_alert=True); return True
        new_cd = MACHINE_LEVELS[next_lvl][0]
        conn = get_db()
        conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (next_cost, uid))
        conn.execute("UPDATE factories SET machine_level=? WHERE user_id=?", (next_lvl, uid))
        conn.commit(); conn.close()
        await query.answer(f"⬆️ دستگاه به سطح {next_lvl} ارتقا پیدا کرد!")
        await query.edit_message_text(
            f"⬆️ *دستگاه ارتقا پیدا کرد!*\n\n"
            f"⭐️ سطح جدید: {next_lvl}/{MACHINE_MAX_LEVEL}\n"
            f"⌛️ زمان تولید جدید: {new_cd} ثانیه\n\n"
            f"🏭 کارخونه‌ات سریع‌تر شد!",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("factory_upgrade_warehouse_"):
        uid = int(data.split("_")[3])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        factory = get_factory(uid)
        u = get_user(uid)
        if factory["warehouse_level"] >= WAREHOUSE_MAX_LEVEL:
            await query.answer("🏆 انبارت ماکسه!", show_alert=True); return True
        next_wh_lvl = factory["warehouse_level"] + 1
        _, upgrade_cost = WAREHOUSE_LEVELS[next_wh_lvl]
        if u["hop_points"] < upgrade_cost:
            await query.answer(f"❌ پوینت کافی نداری! لازم: {upgrade_cost:,}", show_alert=True); return True
        new_cap = WAREHOUSE_LEVELS[next_wh_lvl][0]
        conn = get_db()
        conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (upgrade_cost, uid))
        conn.execute("UPDATE factories SET warehouse_level=? WHERE user_id=?", (next_wh_lvl, uid))
        conn.commit(); conn.close()
        await query.answer(f"⬆️ انبار به سطح {next_wh_lvl} ارتقا پیدا کرد!")
        await query.edit_message_text(
            f"⬆️ *انبار ارتقا پیدا کرد!*\n\n"
            f"⭐️ سطح جدید: {next_wh_lvl}/{WAREHOUSE_MAX_LEVEL}\n"
            f"🧳 ظرفیت جدید: {new_cap} محصول\n\n"
            f"📦 حالا می‌تونی بیشتر ذخیره کنی!",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("factory_hire_") and not data.startswith("factory_hire_confirm_"):
        uid = int(data.split("_")[2])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        with db_conn() as conn:
            row = conn.execute("SELECT count FROM user_strays WHERE user_id=?", (uid,)).fetchone()
        stray_count = row["count"] if row else 0
        if stray_count <= 0:
            await query.answer("❌ هیچ هاپوی خیابونی نداری!\nاول با دستور «هاپو» هاپوی خیابونی نجات بده.", show_alert=True)
            return True
        kb = []
        row_btns = []
        for n in range(1, min(stray_count, 10) + 1):
            row_btns.append(cbtn(
                f"🐈 {n} کارگر", callback_data=f"factory_hire_confirm_{uid}_{n}"
            ))
            if len(row_btns) == 3:
                kb.append(row_btns)
                row_btns = []
        if row_btns:
            kb.append(row_btns)
        kb.append([cbtn("❌ انصراف", callback_data="cancel")])
        await query.answer()
        await query.edit_message_text(
            f"🐕 *استخدام هاپوی خیابونی*\n\n"
            f"هاپوهای خیابونی موجود: *{stray_count}* تا\n\n"
            f"چند تا می‌خوای به کارخونه بیاری؟\n"
            f"_(هر کارگر = یه محصول بیشتر در هر دوره تولید)_",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
        )
        return True

    if data.startswith("factory_hire_confirm_"):
        parts = data.split("_")
        uid = int(parts[3])
        n = int(parts[4])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        with db_conn() as conn:
            row = conn.execute("SELECT count FROM user_strays WHERE user_id=?", (uid,)).fetchone()
            stray_count = row["count"] if row else 0
            if stray_count < n:
                await query.answer("❌ هاپوی خیابونی کافی نداری!", show_alert=True); return True
            conn.execute(
                "UPDATE user_strays SET count = count - ? WHERE user_id=?", (n, uid)
            )
            conn.commit()
        await query.answer(f"✅ {n} کارگر استخدام شد!")
        await query.edit_message_text(
            f"✅ *{n} هاپوی خیابونی استخدام شد!*\n\n"
            f"🐕 این هاپوها الان توی کارخونه‌ات کار می‌کنن\n"
            f"⚙️ هر دوره تولید، {n} محصول بیشتر می‌گیری!\n\n"
            f"بنویس *کارخونه* تا پنل رو ببینی.",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("factory_buy_worker_") and not data.startswith("factory_buy_worker_confirm_"):
        uid = int(data.split("_")[3])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        u = get_user(uid)
        kb = []
        row_btns = []
        for n in [1, 2, 3, 5, 10]:
            total = n * FACTORY_WORKER_COST
            if u["hop_points"] >= total:
                row_btns.append(cbtn(
                    f"🐕 {n} نفر ({total:,})",
                    callback_data=f"factory_buy_worker_confirm_{uid}_{n}"
                ))
            if len(row_btns) == 2:
                kb.append(row_btns)
                row_btns = []
        if row_btns:
            kb.append(row_btns)
        if not kb:
            await query.answer(f"❌ پوینت کافی نداری! حداقل {FACTORY_WORKER_COST:,} لازمه.", show_alert=True)
            return True
        kb.append([cbtn("❌ انصراف", callback_data="cancel")])
        await query.answer()
        await query.edit_message_text(
            f"💰 *خرید کارگر با هاپ پوینت*\n\n"
            f"قیمت هر کارگر: {FACTORY_WORKER_COST:,} هاپ پوینت\n"
            f"👛 موجودی: {u['hop_points']:,.0f}\n\n"
            f"چند تا کارگر میخوای بخری؟",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
        )
        return True

    if data.startswith("factory_buy_worker_confirm_"):
        parts = data.split("_")
        uid = int(parts[4])
        n = int(parts[5])
        if not check_owner(uid):
            await query.answer("❌ این دکمه برای تو نیست!", show_alert=True); return True
        total = n * FACTORY_WORKER_COST
        u = get_user(uid)
        if u["hop_points"] < total:
            await query.answer(f"❌ پوینت کافی نداری! لازم: {total:,}", show_alert=True); return True
        conn = get_db()
        conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (total, uid))
        conn.execute("INSERT OR IGNORE INTO user_strays (user_id, count) VALUES (?, 0)", (uid,))
        conn.execute("UPDATE user_strays SET count=count+? WHERE user_id=?", (n, uid))
        conn.commit(); conn.close()
        await query.answer(f"✅ {n} کارگر خریداری شد!")
        await query.edit_message_text(
            f"✅ *{n} کارگر جدید به کارخونه‌ات اضافه شد!*\n\n"
            f"💰 هزینه: {total:,} هاپ پوینت\n"
            f"🐕 الان توی کارخونه‌ات کار می‌کنن\n"
            f"⚙️ هر دوره تولید، {n} محصول بیشتر می‌گیری!\n\n"
            f"بنویس *کارخونه* تا پنل رو ببینی.",
            parse_mode="Markdown"
        )
        return True

    return False

async def jail_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if update.message and update.message.text and user.id in ADMIN_IDS:
        parts = update.message.text.strip().split()
        target = None
        mins = 30

        if update.message.reply_to_message:
            reply_user = update.message.reply_to_message.from_user
            mins_str = parts[1] if len(parts) >= 2 and parts[1].isdigit() else "30"
            mins = int(mins_str)
            with db_conn() as conn:
                target = conn.execute(
                    "SELECT * FROM users WHERE user_id=?", (reply_user.id,)
                ).fetchone()
            if not target:
                jail_user(reply_user.id, reason="زندان توسط ادمین", duration_seconds=mins*60)
                await update.message.reply_text(
                    f"⛓️ *{reply_user.first_name} به زندان فرستاده شد!*\n⌛️ مدت: {mins} دقیقه",
                    parse_mode="Markdown"
                )
                return

        elif len(parts) >= 2:
            target_username = parts[1].lstrip("@")
            mins = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 30
            with db_conn() as conn:
                target = conn.execute(
                    "SELECT * FROM users WHERE username=? OR CAST(user_id AS TEXT)=?",
                    (target_username, target_username)
                ).fetchone()
            if not target:
                await update.message.reply_text("❌ کاربر پیدا نشد!")
                return

        if target:
            jail_user(target["user_id"], reason="زندان توسط ادمین", duration_seconds=mins*60)
            await update.message.reply_text(
                f"⛓️ *{target['first_name']} به زندان فرستاده شد!*\n⌛️ مدت: {mins} دقیقه",
                parse_mode="Markdown"
            )
            return

    jailed, jail_row = is_in_jail(user.id)
    if not jailed:
        await update.message.reply_text("✅ تو آزادی! توی زندان نیستی 🐕")
        return

    rel = datetime.fromisoformat(jail_row["release_at"])
    left_sec = max(0, int((rel - datetime.now()).total_seconds()))
    m, s = divmod(left_sec, 60)
    bail_cost = int((left_sec / 60) * BAIL_COST_PER_MIN)
    work_pts = jail_row["work_points"] if "work_points" in jail_row.keys() else 0

    with db_conn() as conn:
        u = conn.execute("SELECT * FROM users WHERE user_id=?", (user.id,)).fetchone()

    kb = InlineKeyboardMarkup([
        [cbtn(f"💸 آزادی ({bail_cost:,} پوینت)", callback_data=f"bail_{user.id}"),
         cbtn("🗝 فرار!", callback_data=f"jail_escape_{user.id}")],
        [cbtn(f"⛏ کار در زندان (+{JAIL_WORK_EARN} پوینت)", callback_data=f"jail_work_{user.id}")],
    ])

    await update.message.reply_text(
        f"⛓️ *تو زندانی!*\n\n"
        f"📌 دلیل: {jail_row['reason']}\n"
        f"⌛️ زمان آزادی: {m} دقیقه و {s} ثانیه دیگه\n"
        f"💸 آزادی با پوینت: {bail_cost:,}\n"
        f"⛏ پوینت جمع‌شده از کار: {work_pts:,}\n"
        f"👛 موجودی: {u['hop_points']:,.0f}\n\n"
        f"🗝 فرار: ۲۵٪ شانس — اگه گرفتن، +۱۵ دقیقه اضافه میشه!",
        parse_mode="Markdown", reply_markup=kb
    )

async def new_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("smuggle_"):
        parts = data.split("_")
        count = int(parts[1])
        uid   = int(parts[2])
        if query.from_user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        jailed, _ = is_in_jail(uid)
        if jailed:
            await query.answer("⛓️ الان زندانی هستی!", show_alert=True)
            return True
        conn = get_db()
        row = conn.execute("SELECT count FROM user_strays WHERE user_id=?", (uid,)).fetchone()
        stray_count = row["count"] if row else 0
        if stray_count < count:
            conn.close()
            await query.answer("❌ پیشی خیابونی کافی نداری!", show_alert=True)
            return True
        catch_chance = SMUGGLE_BASE_CATCH + (count * SMUGGLE_CATCH_PER)
        caught = random.random() < catch_chance
        if caught:
            now = datetime.now()
            release = (now + timedelta(minutes=SMUGGLE_JAIL_MINS)).isoformat()
            conn.execute("INSERT OR REPLACE INTO jail (user_id,jailed_at,release_at,reason) VALUES (?,?,?,?)",
                        (uid, now.isoformat(), release, f"قاچاق {count} سگ خیابونی"))
            conn.commit(); conn.close()
            await query.edit_message_text(
                f"🚔 *لو رفتی!*\n\n"
                f"پلیس هاپو {count} تا از سگ‌هات رو مصادره کرد!\n"
                f"⛓️ {SMUGGLE_JAIL_MINS} دقیقه زندان منتظرته...",
                parse_mode="Markdown"
            )
        else:
            reward = count * SMUGGLE_REWARD_EACH
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (reward, uid))
            conn.commit(); conn.close()
            await query.edit_message_text(
                f"🥷 *محموله سالم رسید!*\n\n"
                f"🐕 {count} تا سگ قاچاق شدن!\n"
                f"💰 +{reward:,} هاپ پوینت به جیبت رفت!\n"
                f"⚠️ شانس لو رفتن بود: {catch_chance*100:.0f}٪",
                parse_mode="Markdown"
            )
        return True

    if data.startswith("openbank_"):
        uid = int(data.split("_")[1])
        if query.from_user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if u["hop_points"] < BANK_OPEN_COST:
            conn.close()
            await query.answer(f"پوینت کافی نداری! لازم: {BANK_OPEN_COST:,}", show_alert=True)
            return True
        import random as _r
        acc_num = "".join([str(_r.randint(0, 9)) for _ in range(12)])
        conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (BANK_OPEN_COST, uid))
        conn.execute("""
            INSERT OR IGNORE INTO bank (user_id, balance, account_number, last_interest)
            VALUES (?, 0, ?, NULL)
        """, (uid, acc_num))
        conn.commit()
        conn.close()
        await query.edit_message_text(
            f"🎉 *حساب بانکی افتتاح شد!*\n\n"
            f"💳 شماره حساب: `{acc_num}`\n"
            f"📈 سود روزانه ۳٪ از موجودی\n\n"
            f"برای مدیریت بانکت بنویس *بانک*",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("bank_deposit_"):
        uid = int(data.split("_")[2])
        if query.from_user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        context.user_data["bank_action"] = ("deposit", uid)
        await query.edit_message_text(
            "➕ *چقدر می‌خوای واریز کنی؟*\n"
            "مبلغ رو بنویس (مثلاً: 1000 یا 5k):",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("bank_withdraw_"):
        uid = int(data.split("_")[2])
        if query.from_user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        context.user_data["bank_action"] = ("withdraw", uid)
        await query.edit_message_text(
            "➖ *چقدر می‌خوای برداشت کنی؟*\n"
            "مبلغ رو بنویس (مثلاً: 1000 یا 5k):",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("bank_interest_"):
        uid = int(data.split("_")[2])
        if query.from_user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        conn = get_db()
        bank = conn.execute("SELECT * FROM bank WHERE user_id=?", (uid,)).fetchone()
        if not bank:
            conn.close()
            await query.answer("حساب بانکی نداری!", show_alert=True)
            return True
        if bank["last_interest"]:
            diff = (datetime.now() - datetime.fromisoformat(bank["last_interest"])).total_seconds()
            if diff < 86400:
                conn.close()
                left = int(86400 - diff)
                h, r = divmod(left, 3600)
                m2, s2 = divmod(r, 60)
                await query.answer(f"⌛️ {h}:{m2:02d}:{s2:02d} تا سود بعدی", show_alert=True)
                return True
        interest = min(bank["balance"] * BANK_INTEREST_RATE, BANK_MAX_INTEREST)
        if interest < 1:
            conn.close()
            await query.answer("موجودی خیلی کمه!", show_alert=True)
            return True
        interest = int(interest)
        old_last = bank["last_interest"]
        if old_last:
            cur = conn.execute("""UPDATE bank SET balance=balance+?, last_interest=?
                WHERE user_id=? AND last_interest=? AND datetime(replace(last_interest,'T',' ')) <= datetime('now','-1 day')""",
                (interest, datetime.now().isoformat(), uid, old_last))
        else:
            cur = conn.execute("UPDATE bank SET balance=balance+?, last_interest=? WHERE user_id=? AND last_interest IS NULL",
                               (interest, datetime.now().isoformat(), uid))
        if cur.rowcount != 1:
            conn.close(); await query.answer("⌛️ سود قبلاً دریافت شده؛ دوباره پنل بانک را باز کن.", show_alert=True); return True
        conn.commit()
        conn.close()
        await query.edit_message_text(
            f"💸 *سود دریافت شد!*\n\n"
            f"📈 +{interest:,} هاپ پوینت به بانکت اضافه شد!\n"
            f"📅 سود بعدی: ۲۴ ساعت دیگه\n\n⏳ در حال بازگشت به پنل بانک...",
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)
        await bank_cmd_for_user(query, uid)
        return True

    if data.startswith("bank_changenum_"):
        uid = int(data.split("_")[2])
        if query.from_user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        conn = get_db()
        bank = conn.execute("SELECT * FROM bank WHERE user_id=?", (uid,)).fetchone()
        u = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if bank["last_num_change"]:
            diff = (datetime.now() - datetime.fromisoformat(bank["last_num_change"])).total_seconds()
            if diff < BANK_NUM_CHANGE_CD:
                conn.close()
                left = int(BANK_NUM_CHANGE_CD - diff)
                h2, r2 = divmod(left, 3600)
                await query.answer(f"⌛️ {h2} ساعت دیگه میتونی عوض کنی", show_alert=True)
                return True
        if u["hop_points"] < BANK_NUM_CHANGE_COST:
            conn.close()
            await query.answer(f"پوینت کافی نداری! لازم: {BANK_NUM_CHANGE_COST:,}", show_alert=True)
            return True
        import random as _r2
        new_num = "".join([str(_r2.randint(0, 9)) for _ in range(12)])
        cur=conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?", (BANK_NUM_CHANGE_COST, uid, BANK_NUM_CHANGE_COST))
        if cur.rowcount != 1:
            conn.rollback(); conn.close(); await query.answer("پوینت کافی نیست یا موجودی همزمان تغییر کرده.",show_alert=True); return True
        conn.execute("UPDATE bank SET account_number=?, last_num_change=? WHERE user_id=? AND account_number=?",
                     (new_num, datetime.now().isoformat(), uid, u["account_number"]))
        conn.commit()
        conn.close()
        await query.edit_message_text(
            f"🔄 *شماره حساب تغییر کرد!*\n\n"
            f"💳 شماره جدید: `{new_num}`\n\n⏳ در حال بازگشت به پنل بانک...",
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)
        await bank_cmd_for_user(query, uid)
        return True

    if data.startswith("bail_"):
        uid = int(data.split("_")[1])
        if query.from_user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        jailed, jail_row = is_in_jail(uid)
        if not jailed:
            await query.answer("تو آزادی!", show_alert=True)
            return True
        rel = datetime.fromisoformat(jail_row["release_at"])
        left_sec = int((rel - datetime.now()).total_seconds())
        bail_cost = int((left_sec / 60) * BAIL_COST_PER_MIN)
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if u["hop_points"] < bail_cost:
            conn.close()
            await query.answer(f"پوینت کافی نداری! لازم: {bail_cost:,}", show_alert=True)
            return True
        jail_row2 = conn.execute("SELECT work_points FROM jail WHERE user_id=?", (uid,)).fetchone()
        work_pts = jail_row2["work_points"] if jail_row2 and jail_row2["work_points"] else 0
        conn.execute("UPDATE users SET hop_points=hop_points-?+? WHERE user_id=?", (bail_cost, work_pts, uid))
        conn.execute("DELETE FROM jail WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        msg = (
            f"🎉 *آزاد شدی!*\n\n"
            f"💸 {bail_cost:,} هاپ پوینت پرداخت کردی\n"
        )
        if work_pts > 0:
            msg += f"⛏ +{work_pts:,} پوینت از کار در زندان هم دریافت کردی!\n"
        msg += "🐕 حالا می‌تونی دوباره هاپ کنی!"
        await query.edit_message_text(msg, parse_mode="Markdown")
        return True

    if data.startswith("jail_escape_"):
        uid = int(data.split("_")[2])
        if query.from_user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        jailed, jail_row = is_in_jail(uid)
        if not jailed:
            await query.answer("تو آزادی!", show_alert=True)
            return True
        if random.random() < JAIL_ESCAPE_CHANCE:
            with db_conn() as conn:
                conn.execute("DELETE FROM jail WHERE user_id=?", (uid,))
                conn.commit()
            await query.edit_message_text(
                "🏃 *فرار موفق!*\n\nتونستی از زندان فرار کنی! 🎉",
                parse_mode="Markdown"
            )
        else:
            rel = datetime.fromisoformat(jail_row["release_at"])
            new_rel = rel + timedelta(minutes=15)
            with db_conn() as conn:
                conn.execute("UPDATE jail SET release_at=? WHERE user_id=?", (new_rel.isoformat(), uid))
                conn.commit()
            left = int((new_rel - datetime.now()).total_seconds())
            m, s = divmod(left, 60)
            await query.answer(f"❌ گرفتن! +۱۵ دقیقه اضافه شد. ({m}:{s:02d} مونده)", show_alert=True)
        return True

    if data.startswith("jail_work_"):
        uid = int(data.split("_")[2])
        if query.from_user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        jailed, jail_row = is_in_jail(uid)
        if not jailed:
            await query.answer("تو آزادی!", show_alert=True)
            return True
        now = datetime.now()
        last_work = jail_row["last_work"] if jail_row["last_work"] else None
        if last_work:
            elapsed = (now - datetime.fromisoformat(last_work)).total_seconds()
            if elapsed < JAIL_WORK_INTERVAL:
                left = int(JAIL_WORK_INTERVAL - elapsed)
                m, s = divmod(left, 60)
                await query.answer(f"⌛️ {m}:{s:02d} تا کار بعدی!", show_alert=True)
                return True
        with db_conn() as conn:
            conn.execute(
                "UPDATE jail SET work_points=work_points+?, last_work=? WHERE user_id=?",
                (JAIL_WORK_EARN, now.isoformat(), uid)
            )
            new_wp = conn.execute("SELECT work_points FROM jail WHERE user_id=?", (uid,)).fetchone()["work_points"]
            conn.commit()
        await query.answer(f"⛏ +{JAIL_WORK_EARN} پوینت جمع کردی! (جمع: {new_wp:,})", show_alert=True)
        return True

    if data.startswith("rescue_"):
        await rescue_callback(update, context)
        return True

    if data.startswith("factory_"):
        return await factory_callback_handler(update, context)

    return False

async def handle_bank_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    bank_action = context.user_data.get("bank_action")
    if not bank_action:
        return False

    action, uid = bank_action
    user = update.effective_user
    if user.id != uid:
        return False

    amount = parse_amount(update.message.text.strip())
    if amount <= 0:
        await update.message.reply_text("❌ مبلغ نامعتبره!")
        context.user_data.pop("bank_action", None)
        return True

    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    bank = conn.execute("SELECT * FROM bank WHERE user_id=?", (uid,)).fetchone()

    if not bank:
        conn.close()
        context.user_data.pop("bank_action", None)
        await update.message.reply_text("❌ حساب بانکی نداری!")
        return True

    if action == "deposit":
        cur = conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?", (amount, uid, amount))
        if cur.rowcount != 1:
            conn.close(); context.user_data.pop("bank_action", None)
            await update.message.reply_text(f"❌ موجودی کافی نداری! موجودی: {u['hop_points']:,.0f}")
            return True
        conn.execute("UPDATE bank SET balance=balance+? WHERE user_id=?", (amount, uid))
        conn.commit(); conn.close()
        context.user_data.pop("bank_action", None)
        await update.message.reply_text(
            f"✅ *{amount:,} هاپ پوینت واریز شد!*\n"
            f"🏦 موجودی بانک: {bank['balance'] + amount:,.0f}",
            parse_mode="Markdown"
        )

    elif action == "withdraw":
        cur = conn.execute("UPDATE bank SET balance=balance-? WHERE user_id=? AND balance>=?", (amount, uid, amount))
        if cur.rowcount != 1:
            conn.close(); context.user_data.pop("bank_action", None)
            await update.message.reply_text(f"❌ موجودی بانک کافی نیست! موجودی: {bank['balance']:,.0f}")
            return True
        conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (amount, uid))
        conn.commit(); conn.close()
        context.user_data.pop("bank_action", None)
        await update.message.reply_text(
            f"✅ *{amount:,} هاپ پوینت برداشت شد!*\n"
            f"👛 موجودی کیف: {u['hop_points'] + amount:,.0f}",
            parse_mode="Markdown"
        )

    return True


GAME_MIN_LEVEL      = 2
TABLE_MIN_LEVEL     = 3
CASINO_MIN_LEVEL    = 4
CASINO_TABLE_LEVEL  = 5

XO_COOLDOWN         = 600
DICE_COOLDOWN       = 600
WHEEL_COOLDOWN      = 600
GAMBLE_COOLDOWN     = 600

XO_TIMEOUT          = 60
TABLE_WAIT_TIMEOUT  = 60

def init_casino_tables():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS game_tables (
            table_id    TEXT PRIMARY KEY,
            group_id    INTEGER,
            game_type   TEXT,
            creator_id  INTEGER,
            player2_id  INTEGER DEFAULT NULL,
            bet         INTEGER,
            state       TEXT DEFAULT 'waiting',
            board       TEXT DEFAULT NULL,
            current_turn INTEGER DEFAULT NULL,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS game_cooldowns (
            user_id     INTEGER,
            game_type   TEXT,
            last_play   TEXT,
            PRIMARY KEY (user_id, game_type)
        )
    """)

    conn.commit()
    conn.close()

def check_cooldown(user_id: int, game_type: str, seconds: int) -> int:
    with db_conn() as conn:
        row = conn.execute(
            "SELECT last_play FROM game_cooldowns WHERE user_id=? AND game_type=?",
            (user_id, game_type)
        ).fetchone()
    if not row:
        return 0
    diff = (datetime.now() - datetime.fromisoformat(row["last_play"])).total_seconds()
    return max(0, int(seconds - diff))

def set_cooldown(user_id: int, game_type: str):
    with db_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO game_cooldowns (user_id, game_type, last_play)
            VALUES (?, ?, ?)
        """, (user_id, game_type, datetime.now().isoformat()))
        conn.commit()

def get_user(user_id):
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return u

class InsufficientPointsError(RuntimeError):
    pass

def add_points(user_id, amount):
    if amount == 0:
        return True
    with db_conn() as conn:
        cur = conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (amount, user_id))
        conn.commit()
        return cur.rowcount == 1

def deduct_points(user_id, amount):
    if amount <= 0:
        raise ValueError("amount must be positive")
    with db_conn() as conn:
        cur = conn.execute(
            "UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?",
            (amount, user_id, amount)
        )
        if cur.rowcount != 1:
            conn.rollback()
            raise InsufficientPointsError(f"User {user_id} has insufficient hop balance")
        conn.commit()
        return True

async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_mission_action(update.effective_user.id, "game")
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🕹 بازی‌ها فقط توی گروه کار می‌کنن!")
        return

    u = get_user(user.id)
    if not u or u["level"] < GAME_MIN_LEVEL:
        await update.message.reply_text(f"🔒 برای بازی باید حداقل سطح {GAME_MIN_LEVEL} باشی!")
        return

    kb = InlineKeyboardMarkup([
        [cbtn("🧩 XO", callback_data=f"game_xo_menu_{user.id}")],
        [cbtn("🃏 کازینو", callback_data=f"casino_menu_{user.id}")],
    ])
    await update.message.reply_text(
        f"🕹 *بازی‌های هاپی*\n\n"
        f"🧩 XO — نبرد استراتژیک ۳x۳\n"
        f"🃏 کازینو — قمار، تاس، گردونه\n\n"
        f"👛 موجودیت: {u['hop_points']:,.0f} 🦴",
        parse_mode="Markdown", reply_markup=kb
    )

async def casino_menu_show(update_or_query, user, u, edit=False):
    kb = InlineKeyboardMarkup([
        [cbtn("🍷 قمار گروهی", callback_data=f"casino_gamble_{user.id}"),
         cbtn("🎰 گردونه شانس", callback_data=f"casino_wheel_{user.id}")],
        [cbtn("🎲 تاس", callback_data=f"casino_dice_{user.id}")],
    ])
    text = (
        f"🃏 *کازینو هاپی*\n\n"
        f"🍷 قمار گروهی — ۲-۵ نفره، برنده همه رو میبره\n"
        f"🎰 گردونه شانس — تکی یا چندنفره\n"
        f"🎲 تاس — زوج/فرد یا عدد دقیق\n\n"
        f"👛 موجودیت: {u['hop_points']:,.0f} 🦴"
    )
    if edit:
        await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

def render_xo_board(board: list) -> str:
    symbols = {0: "⬜", 1: "❌", 2: "⭕"}
    rows = []
    for i in range(0, 9, 3):
        rows.append(" ".join(symbols[board[i+j]] for j in range(3)))
    return "\n".join(rows)

def check_xo_winner(board: list) -> int:
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in wins:
        if board[a] == board[b] == board[c] != 0:
            return board[a]
    if all(x != 0 for x in board):
        return -1
    return 0

def xo_board_keyboard(board: list, table_id: str) -> InlineKeyboardMarkup:
    symbols = {0: "⬜", 1: "❌", 2: "⭕"}
    rows = []
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            idx = i + j
            row.append(cbtn(
                symbols[board[idx]],
                callback_data=f"xo_move_{table_id}_{idx}" if board[idx] == 0 else f"xo_noop"
            ))
        rows.append(row)
    return InlineKeyboardMarkup(rows)

async def xo_create(update: Update, context: ContextTypes.DEFAULT_TYPE, bet: int):
    user = update.effective_user
    chat = update.effective_chat

    left = check_cooldown(user.id, "xo", XO_COOLDOWN)
    if left:
        await update.message.reply_text(f"⌛️ {left} ثانیه تا بازی بعدی صبر کن!")
        return

    u = get_user(user.id)
    if u["hop_points"] < bet:
        await update.message.reply_text(f"❌ موجودی کافی نداری! موجودی: {u['hop_points']:,.0f}")
        return

    table_id = f"xo_{user.id}_{int(datetime.now().timestamp())}"
    deduct_points(user.id, bet)

    conn = get_db()
    conn.execute("""
        INSERT INTO game_tables (table_id, group_id, game_type, creator_id, bet, state, board, current_turn)
        VALUES (?, ?, 'xo', ?, ?, 'waiting', ?, ?)
    """, (table_id, chat.id, user.id, bet, "0"*9, user.id))
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([[
        cbtn(f"✋ پیوستن ({bet:,} پوینت)", callback_data=f"xo_join_{table_id}"),
        cbtn("❌ لغو", callback_data=f"xo_cancel_{table_id}"),
    ]])
    await update.message.reply_text(
        f"🧩 *{user.first_name} میز XO ساخت!*\n\n"
        f"💰 شرط: {bet:,} هاپ پوینت\n"
        f"⌛️ {TABLE_WAIT_TIMEOUT} ثانیه فرصت پیوستن",
        parse_mode="Markdown", reply_markup=kb
    )


async def dice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🎲 تاس فقط توی گروه کار می‌کنه!")
        return

    u = get_user(user.id)
    if not u or u["level"] < CASINO_MIN_LEVEL:
        await update.message.reply_text(f"🔒 برای تاس باید سطح {CASINO_MIN_LEVEL} باشی!")
        return

    left = check_cooldown(user.id, "dice", DICE_COOLDOWN)
    if left:
        m, s = divmod(left, 60)
        await update.message.reply_text(f"⌛️ {m} دقیقه و {s} ثانیه تا تاس بعدی!")
        return

    context.user_data["dice_state"] = {"user_id": user.id, "step": "bet"}
    await update.message.reply_text(
        f"🎲 *تاس هاپی*\n\n"
        f"💰 شرط چقدر؟ (موجودی: {u['hop_points']:,.0f})\n"
        f"مبلغ رو بنویس:",
        parse_mode="Markdown"
    )

async def handle_dice_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message:
        return False

    state = context.user_data.get("dice_state")
    if not state or state["user_id"] != update.effective_user.id:
       return False

    user = update.effective_user

    text = update.message.text.strip() if update.message.text else ""
    if update.message.dice:
        return False

    if state["step"] == "bet":
       try:
           bet = int(text.replace(",", ""))
       except:
           await update.message.reply_text("❌ عدد معتبر وارد کن!")
           return True
       u = get_user(user.id)
       if bet <= 0 or u["hop_points"] < bet:
           await update.message.reply_text("❌ مبلغ نامعتبر یا موجودی کافی نیست!")
           return True
       state["bet"] = bet
       state["step"] = "mode"
       context.user_data["dice_state"] = state
       kb = InlineKeyboardMarkup([
           [cbtn("زوج یا فرد (1.7x)", callback_data=f"dice_mode_evenodd_{user.id}"),
            cbtn("عدد دقیق (4x)", callback_data=f"dice_mode_exact_{user.id}")],
       ])
       await update.message.reply_text("🎲 چه نوع شرطی؟", reply_markup=kb)
       return True

    if state["step"] == "guess_exact":
       try:
           guess = int(text)
           if guess < 1 or guess > 6:
               raise ValueError
       except:
           await update.message.reply_text("❌ عدد ۱ تا ۶ وارد کن!")
           return True

       bet = state["bet"]
       u = get_user(user.id)
       if u["hop_points"] < bet:
           await update.message.reply_text("❌ موجودی کافی نداری!")
           context.user_data.pop("dice_state", None)
           return True

       context.user_data.pop("dice_state", None)
       deduct_points(user.id, bet)
       set_cooldown(user.id, "dice")

       await update.message.reply_text(
           f"🎲 حدست: *{guess}* | شرط: {bet:,}\n\n⏳ در حال پرتاب تاس...",
           parse_mode="Markdown"
       )

       dice_msg = await update.message.chat.send_dice(emoji="🎲")
       roll = dice_msg.dice.value
       await asyncio.sleep(4)

       if roll == guess:
           win = int(bet * 4)
           add_points(user.id, win)
           await update.message.reply_text(
               f"🎯 عدد {roll}!\n\n"
               f"🎉 درست حدس زدی! +{win:,} هاپ پوینت"
           )
       else:
           await update.message.reply_text(
               f"💀 عدد {roll} (تو گفتی {guess})!\n\n"
               f"😢 اشتباه بود. -{bet:,} هاپ پوینت"
           )
       return True

    return False

async def handle_slot_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.dice:
        return False
    if update.message.dice.emoji != "🎰":
        return False

    wheel_state = context.user_data.get("wheel_state")
    if not wheel_state or wheel_state["user_id"] != update.effective_user.id:
        return False
    if wheel_state.get("step") != "waiting_slot":
        return False

    user = update.effective_user
    bet = wheel_state["bet"]
    slot_value = update.message.dice.value

    u = get_user(user.id)
    if u["hop_points"] < bet:
        await update.message.reply_text("❌ موجودی کافی نداری!")
        context.user_data.pop("wheel_state", None)
        return True

    context.user_data.pop("wheel_state", None)
    set_cooldown(user.id, "wheel")
    deduct_points(user.id, bet)

    await asyncio.sleep(3)

    mult, label = get_wheel_result(slot_value)
    win = int(bet * mult)

    if mult == 0.0:
        result = f"💀 {label}\n-{bet:,} هاپ پوینت"
    elif mult < 1.0:
        add_points(user.id, win)
        result = f"😬 {label} (×{mult})\n+{win:,} برگشت (باختی {bet-win:,})"
    else:
        add_points(user.id, win)
        result = f"{'🎰' if mult >= 15 else '🎉'} {label} (×{mult})\n+{win:,} هاپ پوینت"

    await update.message.reply_text(
        f"🎰 *نتیجه گردونه!*\n\n{result}",
        parse_mode="Markdown"
    )
    return True

WHEEL_MULTIPLIERS = [0.0, 0.0, 0.5, 0.5, 0.8, 1.2, 1.5, 2.0, 3.0, 5.0]
WHEEL_WEIGHTS     = [12,  10,  15,  12,  18,  14,  10,  6,   2,   1  ]

def get_wheel_result(slot_value: int) -> tuple:
    if slot_value == 64:
        return (15.0, "🎰 جکپات! 7️⃣7️⃣7️⃣")
    elif slot_value >= 49:
        return (2.5, "🎉 برنده!")
    elif slot_value >= 29:
        return (0.5, "😬 نصفه...")
    else:
        return (0.0, "💀 باختی!")

async def wheel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🎰 گردونه فقط توی گروه!")
        return

    u = get_user(user.id)
    if not u or u["level"] < CASINO_MIN_LEVEL:
        await update.message.reply_text(f"🔒 سطح {CASINO_MIN_LEVEL} لازمه!")
        return

    left = check_cooldown(user.id, "wheel", WHEEL_COOLDOWN)
    if left:
        m, s = divmod(left, 60)
        await update.message.reply_text(f"⌛️ {m} دقیقه و {s} ثانیه تا گردونه بعدی!")
        return

    kb = InlineKeyboardMarkup([
        [cbtn("👤 تکی", callback_data=f"wheel_solo_{user.id}"),
         cbtn("👥 چندنفره", callback_data=f"wheel_multi_{user.id}")],
    ])
    await update.message.reply_text(
        f"🎰 *گردونه شانس*\n\n"
        f"ضرایب: 0x❌ | 0.5x | 1.5x | 2x | 3x | 5x🌟\n"
        f"👛 موجودی: {u['hop_points']:,.0f}\n\n"
        f"چه حالتی؟",
        parse_mode="Markdown", reply_markup=kb
    )

async def gamble_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🍷 قمار فقط توی گروه!")
        return

    u = get_user(user.id)
    if not u or u["level"] < CASINO_MIN_LEVEL:
        await update.message.reply_text(f"🔒 سطح {CASINO_MIN_LEVEL} لازمه!")
        return

    left = check_cooldown(user.id, "gamble", GAMBLE_COOLDOWN)
    if left:
        m, s = divmod(left, 60)
        await update.message.reply_text(f"⌛️ {m} دقیقه و {s} ثانیه تا قمار بعدی!")
        return

    context.user_data["gamble_state"] = {"user_id": user.id, "step": "bet", "group_id": chat.id}
    await update.message.reply_text(
        f"🍷 *قمار گروهی*\n\n"
        f"💰 شرط چقدر؟ (موجودی: {u['hop_points']:,.0f})\n"
        f"مبلغ رو بنویس:",
        parse_mode="Markdown"
    )

async def handle_gamble_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    state = context.user_data.get("gamble_state")
    if not state or state["user_id"] != update.effective_user.id:
        return False
    if state["step"] != "bet":
        return False

    user = update.effective_user
    text = update.message.text.strip()
    try:
        bet = int(text.replace(",", ""))
    except:
        await update.message.reply_text("❌ عدد معتبر وارد کن!")
        return True

    u = get_user(user.id)
    if bet <= 0 or u["hop_points"] < bet:
        await update.message.reply_text("❌ مبلغ نامعتبر یا موجودی کافی نیست!")
        return True

    group_id = state["group_id"]
    table_id = f"gamble_{user.id}_{int(datetime.now().timestamp())}"
    deduct_points(user.id, bet)
    context.user_data.pop("gamble_state", None)

    conn = get_db()
    conn.execute("""
        INSERT INTO game_tables (table_id, group_id, game_type, creator_id, bet, state, board)
        VALUES (?, ?, 'gamble', ?, ?, 'waiting', ?)
    """, (table_id, group_id, user.id, bet, f"{user.id}:{bet}"))
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([[
        cbtn(f"🍷 پیوستن ({bet:,} پوینت)", callback_data=f"gamble_join_{table_id}"),
        cbtn("🎯 شروع بازی!", callback_data=f"gamble_start_{table_id}"),
    ]])
    await update.message.reply_text(
        f"🍷 *{user.first_name} میز قمار ساخت!*\n\n"
        f"💰 شرط: {bet:,} هاپ پوینت\n"
        f"👥 بازیکن‌ها: 1 نفر\n"
        f"⌛️ منتظر بقیه...\n\n"
        f"(بعد از جمع شدن ۲-۵ نفر، سازنده دکمه شروع رو بزنه)",
        parse_mode="Markdown", reply_markup=kb
    )
    return True

async def casino_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data = query.data
    user = query.from_user

    if data.startswith("game_xo_menu_"):
        uid = int(data.split("_")[3])
        u = get_user(uid)
        if not u or u["level"] < TABLE_MIN_LEVEL:
            await query.answer(f"سطح {TABLE_MIN_LEVEL} لازمه!", show_alert=True)
            return True
        context.user_data["create_game"] = ("xo", uid)
        await query.edit_message_text(
            "🧩 *میز XO*\n\nشرط چقدر؟ مبلغ رو بنویس:",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("casino_menu_"):
        uid = int(data.split("_")[2])
        u = get_user(uid)
        if not u or u["level"] < CASINO_MIN_LEVEL:
            await query.answer(f"سطح {CASINO_MIN_LEVEL} لازمه!", show_alert=True)
            return True
        await casino_menu_show(query, user, u, edit=True)
        return True

    if data.startswith("casino_dice_"):
        uid = int(data.split("_")[2])
        if user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        left = check_cooldown(uid, "dice", DICE_COOLDOWN)
        if left:
            m, s = divmod(left, 60)
            await query.answer(f"⌛️ {m}:{s:02d} تا تاس بعدی!", show_alert=True)
            return True
        context.user_data["dice_state"] = {"user_id": uid, "step": "bet"}
        u = get_user(uid)
        await query.edit_message_text(
            f"🎲 *تاس*\n\n💰 موجودی: {u['hop_points']:,.0f} هاپ\n\nشرط چقدر؟ مبلغ رو بنویس:",
            parse_mode="Markdown"
        )
        return True

    if data.startswith("casino_wheel_"):
        uid = int(data.split("_")[2])
        if user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        left = check_cooldown(uid, "wheel", WHEEL_COOLDOWN)
        if left:
            m, s = divmod(left, 60)
            await query.answer(f"⌛️ {m}:{s:02d} تا گردونه بعدی!", show_alert=True)
            return True
        u = get_user(uid)
        await query.edit_message_text(
            f"🎰 *گردونه شانس*\n\n💰 موجودی: {u['hop_points']:,.0f} هاپ\n\nشرط چقدر؟ مبلغ رو بنویس:",
            parse_mode="Markdown"
        )
        context.user_data["wheel_state"] = {"user_id": uid, "step": "bet", "mode": "solo"}
        return True

    if data.startswith("casino_gamble_"):
        uid = int(data.split("_")[2])
        if user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        left = check_cooldown(uid, "gamble", GAMBLE_COOLDOWN)
        if left:
            m, s = divmod(left, 60)
            await query.answer(f"⌛️ {m}:{s:02d} تا قمار بعدی!", show_alert=True)
            return True
        u = get_user(uid)
        await query.edit_message_text(
            f"🃏 *قمار گروهی*\n\n💰 موجودی: {u['hop_points']:,.0f} هاپ\n\nشرط چقدر؟ مبلغ رو بنویس:",
            parse_mode="Markdown"
        )
        context.user_data["gamble_state"] = {"user_id": uid, "step": "bet", "group_id": query.message.chat_id}
        return True

    if data.startswith("dice_mode_"):
        parts = data.split("_")
        mode = parts[2]
        uid = int(parts[3])
        if user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        state = context.user_data.get("dice_state")
        if not state:
            return True
        bet = state.get("bet", 0)
        u = get_user(uid)

        if mode == "evenodd":
            kb = InlineKeyboardMarkup([[
                cbtn("زوج", callback_data=f"dice_guess_even_{uid}_{bet}"),
                cbtn("فرد", callback_data=f"dice_guess_odd_{uid}_{bet}"),
            ]])
            await query.edit_message_text("🎲 زوج یا فرد؟", reply_markup=kb)
            context.user_data.pop("dice_state", None)
        else:
            state["step"] = "guess_exact"
            context.user_data["dice_state"] = state
            await query.edit_message_text("🎲 عدد دقیق (۱ تا ۶) رو بنویس:")
        return True

    if data.startswith("dice_guess_"):
        parts = data.split("_")
        guess_type = parts[2]
        uid = int(parts[3])
        bet = int(parts[4])
        if user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        u = get_user(uid)
        if u["hop_points"] < bet:
            await query.answer("پوینت کافی نداری!", show_alert=True)
            return True

        u = get_user(uid)
        if u["hop_points"] < bet:
            await query.answer("پوینت کافی نداری!", show_alert=True)
            return True

        await query.edit_message_text(
            f"🎲 انتخابت: *{'زوج' if guess_type == 'even' else 'فرد'}* | شرط: {bet:,}\n\n"
            f"⏳ در حال پرتاب تاس...",
            parse_mode="Markdown"
        )

        deduct_points(uid, bet)
        set_cooldown(uid, "dice")
        context.user_data.pop("dice_state", None)

        dice_msg = await query.message.chat.send_dice(emoji="🎲")
        roll = dice_msg.dice.value
        await asyncio.sleep(4)

        is_even = roll % 2 == 0
        if (guess_type == "even" and is_even) or (guess_type == "odd" and not is_even):
            win = int(bet * 1.7)
            add_points(uid, win)
            await query.message.reply_text(
                f"✅ عدد {roll} ({'زوج' if is_even else 'فرد'})!\n\n"
                f"🎉 بردی! +{win:,} هاپ پوینت"
            )
        else:
            await query.message.reply_text(
                f"💀 عدد {roll} ({'زوج' if is_even else 'فرد'})!\n\n"
                f"😢 باختی! -{bet:,} هاپ پوینت"
            )
        return True

    if data.startswith("wheel_solo_"):
        uid = int(data.split("_")[2])
        if user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        context.user_data["wheel_state"] = {"user_id": uid, "step": "bet", "mode": "solo"}
        await query.edit_message_text("🎰 شرط چقدر؟ مبلغ رو بنویس:")
        return True

    if data.startswith("wheel_multi_"):
        uid = int(data.split("_")[2])
        if user.id != uid:
            await query.answer("این دکمه برای تو نیست!", show_alert=True)
            return True
        u = get_user(uid)
        if u["level"] < CASINO_TABLE_LEVEL:
            await query.answer(f"سطح {CASINO_TABLE_LEVEL} لازمه!", show_alert=True)
            return True
        context.user_data["wheel_state"] = {"user_id": uid, "step": "bet", "mode": "multi"}
        await query.edit_message_text("🎰 شرط چقدر؟ مبلغ رو بنویس:")
        return True

    if data.startswith("xo_join_"):
        table_id = data[8:]
        conn = get_db()
        table = conn.execute("SELECT * FROM game_tables WHERE table_id=?", (table_id,)).fetchone()

        if not table or table["state"] != "waiting":
            conn.close()
            await query.answer("این میز دیگه موجود نیست!", show_alert=True)
            return True
        if table["creator_id"] == user.id:
            conn.close()
            await query.answer("نمی‌تونی با خودت بازی کنی!", show_alert=True)
            return True

        u = get_user(user.id)
        bet = table["bet"]
        if u["hop_points"] < bet:
            conn.close()
            await query.answer(f"پوینت کافی نداری! لازم: {bet:,}", show_alert=True)
            return True

        deduct_points(user.id, bet)
        board = [0]*9
        conn.execute("""
            UPDATE game_tables SET player2_id=?, state='playing', board=?, current_turn=?
            WHERE table_id=?
        """, (user.id, ",".join(map(str, board)), table["creator_id"], table_id))
        conn.commit()

        creator = conn.execute("SELECT first_name FROM users WHERE user_id=?", (table["creator_id"],)).fetchone()
        conn.close()

        kb = xo_board_keyboard(board, table_id)
        await query.edit_message_text(
            f"🧩 *بازی XO شروع شد!*\n\n"
            f"❌ {creator['first_name']} vs ⭕ {user.first_name}\n"
            f"💰 جایزه: {bet*2:,} هاپ پوینت\n\n"
            f"نوبت: ❌ {creator['first_name']}\n\n"
            f"{render_xo_board(board)}",
            parse_mode="Markdown", reply_markup=kb
        )
        return True

    if data.startswith("xo_move_"):
        parts = data.split("_")
        idx = int(parts[-1])
        table_id = "_".join(parts[2:-1])

        conn = get_db()
        table = conn.execute("SELECT * FROM game_tables WHERE table_id=?", (table_id,)).fetchone()
        if not table or table["state"] != "playing":
            conn.close()
            await query.answer("بازی تموم شده!", show_alert=True)
            return True
        if table["current_turn"] != user.id:
            conn.close()
            await query.answer("نوبت تو نیست!", show_alert=True)
            return True

        board = list(map(int, table["board"].split(",")))
        if board[idx] != 0:
            conn.close()
            await query.answer("این خونه پره!", show_alert=True)
            return True

        player_num = 1 if user.id == table["creator_id"] else 2
        board[idx] = player_num

        winner = check_xo_winner(board)
        next_turn = table["player2_id"] if user.id == table["creator_id"] else table["creator_id"]

        conn2 = get_db()
        p1 = conn2.execute("SELECT first_name FROM users WHERE user_id=?", (table["creator_id"],)).fetchone()
        p2 = conn2.execute("SELECT first_name FROM users WHERE user_id=?", (table["player2_id"],)).fetchone()
        conn2.close()

        if winner == 0:
            conn.execute("""
                UPDATE game_tables SET board=?, current_turn=? WHERE table_id=?
            """, (",".join(map(str, board)), next_turn, table_id))
            conn.commit()
            conn.close()
            next_name = p1["first_name"] if next_turn == table["creator_id"] else p2["first_name"]
            next_sym = "❌" if next_turn == table["creator_id"] else "⭕"
            kb = xo_board_keyboard(board, table_id)
            await query.edit_message_text(
                f"🧩 *بازی XO*\n\n"
                f"❌ {p1['first_name']} vs ⭕ {p2['first_name']}\n\n"
                f"{render_xo_board(board)}\n\n"
                f"نوبت: {next_sym} {next_name}",
                parse_mode="Markdown", reply_markup=kb
            )
        elif winner == -1:
            conn.execute("UPDATE game_tables SET state='done' WHERE table_id=?", (table_id,))
            conn.commit()
            conn.close()
            add_points(table["creator_id"], table["bet"])
            add_points(table["player2_id"], table["bet"])
            set_cooldown(table["creator_id"], "xo")
            set_cooldown(table["player2_id"], "xo")
            await query.edit_message_text(
                f"🤝 *مساوی!*\n\n"
                f"{render_xo_board(board)}\n\n"
                f"پوینت‌ها برگشت داده شد!",
                parse_mode="Markdown"
            )
        else:
            winner_id = table["creator_id"] if winner == 1 else table["player2_id"]
            loser_id = table["player2_id"] if winner == 1 else table["creator_id"]
            prize = table["bet"] * 2
            conn.execute("UPDATE game_tables SET state='done' WHERE table_id=?", (table_id,))
            conn.commit()
            conn.close()
            add_points(winner_id, prize)
            set_cooldown(table["creator_id"], "xo")
            set_cooldown(table["player2_id"], "xo")
            winner_name = p1["first_name"] if winner_id == table["creator_id"] else p2["first_name"]
            await query.edit_message_text(
                f"🏆 *{winner_name} برنده شد!*\n\n"
                f"{render_xo_board(board)}\n\n"
                f"🎉 +{prize:,} هاپ پوینت",
                parse_mode="Markdown"
            )
        return True

    if data == "xo_noop":
        await query.answer()
        return True

    if data.startswith("xo_cancel_"):
        table_id = data[10:]
        conn = get_db()
        table = conn.execute("SELECT * FROM game_tables WHERE table_id=?", (table_id,)).fetchone()
        if not table:
            conn.close()
            await query.answer("میز پیدا نشد!", show_alert=True)
            return True
        if table["creator_id"] != user.id:
            conn.close()
            await query.answer("فقط سازنده میز میتونه لغو کنه!", show_alert=True)
            return True
        if table["state"] != "waiting":
            conn.close()
            await query.answer("بازی شروع شده!", show_alert=True)
            return True
        add_points(user.id, table["bet"])
        conn.execute("DELETE FROM game_tables WHERE table_id=?", (table_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("❌ میز لغو شد. پوینتت برگشت داده شد.")
        return True

    if data.startswith("gamble_join_"):
        table_id = data[12:]
        conn = get_db()
        table = conn.execute("SELECT * FROM game_tables WHERE table_id=?", (table_id,)).fetchone()
        if not table or table["state"] != "waiting":
            conn.close()
            await query.answer("این میز دیگه موجود نیست!", show_alert=True)
            return True

        players = [p for p in table["board"].split(",") if p]
        player_ids = [int(p.split(":")[0]) for p in players]

        if user.id in player_ids:
            conn.close()
            await query.answer("قبلاً پیوستی!", show_alert=True)
            return True
        if len(players) >= 5:
            conn.close()
            await query.answer("میز پره! (حداکثر ۵ نفر)", show_alert=True)
            return True

        bet = table["bet"]
        u = get_user(user.id)
        if u["hop_points"] < bet:
            conn.close()
            await query.answer(f"پوینت کافی نداری! لازم: {bet:,}", show_alert=True)
            return True

        deduct_points(user.id, bet)
        players.append(f"{user.id}:{bet}")
        conn.execute("UPDATE game_tables SET board=? WHERE table_id=?", (",".join(players), table_id))
        conn.commit()
        conn.close()

        kb = InlineKeyboardMarkup([[
            cbtn(f"🍷 پیوستن ({bet:,} پوینت)", callback_data=f"gamble_join_{table_id}"),
            cbtn("🎯 شروع!", callback_data=f"gamble_start_{table_id}"),
        ]])
        await query.edit_message_text(
            f"🍷 *میز قمار*\n\n"
            f"💰 شرط: {bet:,} هاپ پوینت\n"
            f"👥 بازیکن‌ها: {len(players)} نفر\n"
            f"(سازنده دکمه شروع رو بزنه)",
            parse_mode="Markdown", reply_markup=kb
        )
        return True

    if data.startswith("gamble_start_"):
        table_id = data[13:]
        conn = get_db()
        table = conn.execute("SELECT * FROM game_tables WHERE table_id=?", (table_id,)).fetchone()
        if not table:
            conn.close()
            await query.answer("میز پیدا نشد!", show_alert=True)
            return True
        if table["creator_id"] != user.id:
            conn.close()
            await query.answer("فقط سازنده میتونه شروع کنه!", show_alert=True)
            return True

        players = [p for p in table["board"].split(",") if p]
        if len(players) < 2:
            conn.close()
            await query.answer("حداقل ۲ نفر لازمه!", show_alert=True)
            return True

        winner_entry = random.choice(players)
        winner_id = int(winner_entry.split(":")[0])
        total_pot = sum(int(p.split(":")[1]) for p in players)

        add_points(winner_id, total_pot)
        conn.execute("UPDATE game_tables SET state='done' WHERE table_id=?", (table_id,))
        conn.commit()

        winner_row = conn.execute("SELECT first_name FROM users WHERE user_id=?", (winner_id,)).fetchone()
        conn.close()

        for p in players:
            set_cooldown(int(p.split(":")[0]), "gamble")

        await query.edit_message_text(
            f"🍀 *نتیجه قمار!*\n\n"
            f"🏆 *{winner_row['first_name']}* برنده شد!\n"
            f"💰 +{total_pot:,} هاپ پوینت برنده برد!",
            parse_mode="Markdown"
        )
        return True

    return False

async def handle_casino_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user

    game_state = context.user_data.get("create_game")
    if game_state:
        game_type, uid = game_state
        if user.id != uid:
            return False
        text = update.message.text.strip()
        try:
            bet = int(text.replace(",", ""))
            if bet <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ عدد معتبر وارد کن!")
            return True
        context.user_data.pop("create_game", None)
        if game_type == "xo":
            await xo_create(update, context, bet)
        return True

    wheel_state = context.user_data.get("wheel_state")
    if wheel_state and wheel_state["user_id"] == user.id:
        text = update.message.text.strip() if update.message.text else ""

        if wheel_state.get("step") == "waiting_slot":
            return False

        try:
            bet = int(text.replace(",", ""))
            if bet <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ عدد معتبر وارد کن!")
            return True
        u = get_user(user.id)
        if u["hop_points"] < bet:
            context.user_data.pop("wheel_state", None)
            await update.message.reply_text("❌ موجودی کافی نداری!")
            return True

        left = check_cooldown(user.id, "wheel", WHEEL_COOLDOWN)
        if left:
            context.user_data.pop("wheel_state", None)
            await update.message.reply_text(f"⌛️ {left} ثانیه تا گردونه بعدی!")
            return True

        context.user_data.pop("wheel_state", None)
        deduct_points(user.id, bet)
        set_cooldown(user.id, "wheel")

        await update.message.reply_text(
            f"🎰 شرط: *{bet:,}*\n\n⏳ در حال چرخوندن گردونه...",
            parse_mode="Markdown"
        )

        slot_msg = await update.message.chat.send_dice(emoji="🎰")
        slot_value = slot_msg.dice.value
        await asyncio.sleep(3)

        mult, label = get_wheel_result(slot_value)
        win = int(bet * mult)

        if mult == 0.0:
            result = f"💀 {label}\n-{bet:,} هاپ پوینت"
        elif mult < 1.0:
            add_points(user.id, win)
            result = f"😬 {label} (×{mult})\n+{win:,} برگشت (باختی {bet-win:,})"
        else:
            add_points(user.id, win)
            result = f"{'🎰' if mult >= 15 else '🎉'} {label} (×{mult})\n+{win:,} هاپ پوینت"

        await update.message.reply_text(
            f"🎰 *نتیجه گردونه!*\n\n{result}",
            parse_mode="Markdown"
        )
        return True

    if await handle_dice_input(update, context):
        return True

    if await handle_gamble_input(update, context):
        return True

    return False


def get_city_level(grp: dict) -> int:
    lvl = 1
    for i in range(2, CITY_MAX_LEVEL + 1):
        req = CITY_LEVELS[i]
        if (grp["treasury"]    >= req[0] and
            grp["total_hops"]  >= req[1] and
            grp["total_dogs"]  >= req[2] and
            grp["total_bones"] >= req[3] and
            grp["total_fish"]  >= req[4]):
            lvl = i
    return lvl

def city_hop_cooldown(city_level: int) -> int:
    return max(30, HOP_COOLDOWN - (city_level - 1) * CITY_HOP_BUFF)

def city_fish_cooldown(city_level: int, base_cd: int) -> int:
    return max(60, base_cd - (city_level - 1) * CITY_FISH_BUFF)

async def city_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🏰 دستور شهر فقط توی گروه کار می‌کنه!")
        return

    ensure_group(chat.id, chat.title or "گروه")
    conn = get_db()
    grp = conn.execute("SELECT * FROM groups WHERE group_id=?", (chat.id,)).fetchone()
    city_lvl = get_city_level(grp)

    all_groups = conn.execute("SELECT group_id, treasury, total_hops, total_dogs, total_bones, total_fish FROM groups").fetchall()
    conn.close()

    def group_sort_key(g):
        lvl = get_city_level(g)
        return (lvl, g["treasury"])

    sorted_groups = sorted(all_groups, key=group_sort_key, reverse=True)
    r_city = next((i+1 for i, g in enumerate(sorted_groups) if g["group_id"] == chat.id), 1)

    title = grp["title"] or "شهر هاپو"

    def bar(val, need):
        if need == 0: return "▰▰▰▰▰"
        f = min(5, int((val / need) * 5))
        return "▰" * f + "▱" * (5 - f)

    if city_lvl < CITY_MAX_LEVEL:
        nxt = CITY_LEVELS[city_lvl + 1]
        progress = (
            f"\n📊 *پیشرفت به سطح {city_lvl + 1}:*\n"
            f"┐─ 🏦 خزانه : {grp['treasury']:,.0f} / {nxt[0]:,}  {bar(grp['treasury'], nxt[0])}\n"
            f"┐─ 🐾 هاپ‌های کل : {grp['total_hops']:,} / {nxt[1]:,}  {bar(grp['total_hops'], nxt[1])}\n"
            f"┐─ 🐕 سگ‌های خریداری شده : {grp['total_dogs']:,} / {nxt[2]:,}  {bar(grp['total_dogs'], nxt[2])}\n"
            f"┐─ 🦴 استخوان‌ها : {grp['total_bones']:,} / {nxt[3]:,}  {bar(grp['total_bones'], nxt[3])}\n"
            f"└─ 🎣 ماهی‌ها : {grp['total_fish']:,} / {nxt[4]:,}  {bar(grp['total_fish'], nxt[4])}"
        )
    else:
        progress = "\n🏆 *شهر به سطح ماکس رسیده!*"

    hop_cd   = city_hop_cooldown(city_lvl)
    fish_red = (city_lvl - 1) * CITY_FISH_BUFF
    stray_red = int((city_lvl - 1) * CITY_STRAY_BUFF * 100)

    stars = "⭐️" * city_lvl if city_lvl <= 5 else "⭐️" * 5 + f" +{city_lvl-5}"

    text = (
        f"╮──「 🏰 شهر هاپو 🐾 」\n\n"
        f"┐─ 🏙️ نام : {title}\n"
        f"┐─ 🎖️ رتبه جهانی : #{r_city}\n"
        f"└─ {stars}\n\n"
        f"📈 *آمار شهر:*\n"
        f"┐─ ⭐️ سطح : {city_lvl} / {CITY_MAX_LEVEL}\n"
        f"┐─ 🏦 خزانه : {grp['treasury']:,.0f} 🦴\n"
        f"┐─ 🐾 کل هاپ : {grp['total_hops']:,}\n"
        f"┐─ 🐕 کل سگ : {grp['total_dogs']:,}\n"
        f"┐─ 🦴 کل استخوان : {grp['total_bones']:,}\n"
        f"└─ 🎣 کل ماهی : {grp['total_fish']:,}\n"
        f"\n✨ *باف‌های فعال (سطح {city_lvl}):*\n"
        f"┐─ 🐾 کولداون هاپ : {hop_cd}s (اصلی {HOP_COOLDOWN}s)\n"
        f"┐─ 🎣 کاهش کولداون ماهیگیری : {fish_red}s\n"
        f"└─ 🐈 کاهش آستانه پیشی خیابونی : {stray_red}%\n"
        f"{progress}\n\n"
        f"💡 برای کمک به خزانه بنویس: *اهدا [مقدار]*"
    )
    await send_stage_message(update.message, text, stage="city", parse_mode="Markdown")

async def donate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        await update.message.reply_text("🏦 این دستور فقط توی گروه کار می‌کنه!")
        return

    parts = (update.message.text or "").strip().split()
    if len(parts) < 2:
        await update.message.reply_text("✍️ فرمت درست: *اهدا 500*", parse_mode="Markdown")
        return
    try:
        amount = int(parts[1].replace(",", "").replace("،", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ مقدار نامعتبره! یه عدد مثبت بنویس.")
        return

    ensure_user(user.id, user.username or "", user.first_name)
    ensure_group(chat.id, chat.title or "گروه")
    try:
        with db_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            u = conn.execute("SELECT hop_points FROM users WHERE user_id=?", (user.id,)).fetchone()
            grp = conn.execute("SELECT * FROM groups WHERE group_id=?", (chat.id,)).fetchone()
            if not u or not grp:
                conn.rollback()
                await update.message.reply_text("❌ اطلاعات کاربر یا شهر پیدا نشد.")
                return
            old_lvl = get_city_level(grp)
            cur = conn.execute(
                "UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?",
                (amount, user.id, amount)
            )
            if cur.rowcount != 1:
                conn.rollback()
                await update.message.reply_text(f"❌ پوینت کافی نداری!\n💰 موجودی: {u['hop_points']:,.0f} هاپ پوینت")
                return
            conn.execute("UPDATE groups SET treasury=treasury+? WHERE group_id=?", (amount, chat.id))
            new_grp = conn.execute("SELECT * FROM groups WHERE group_id=?", (chat.id,)).fetchone()
            new_lvl = get_city_level(new_grp)
            conn.execute(
                "INSERT INTO economy_ledger(user_id,asset,amount,balance_before,balance_after,action,counterparty_id,reference_id) VALUES(?,?,?,?,?,?,?,?)",
                (user.id, "hop", -amount, float(u["hop_points"]), float(u["hop_points"]) - amount, "city_donation", chat.id, str(update.message.message_id))
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error during city donation: user=%s group=%s amount=%s", user.id, chat.id, amount)
        await update.message.reply_text("🚨 خطای موقت دیتابیس؛ اهدا انجام نشد.")
        return

    msg = (
        f"🏦 *{user.first_name}* {amount:,} هاپ پوینت به خزانه شهر اهدا کرد! 🎉\n"
        f"💰 خزانه فعلی: {new_grp['treasury']:,.0f}"
    )
    if new_lvl > old_lvl:
        msg += f"\n\n🎊 *شهر به سطح {new_lvl} ارتقا پیدا کرد!* 🏰"
    await send_stage_message(update.message, msg, stage="city", parse_mode="Markdown")

async def hapoha_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()

    u = conn.execute("SELECT * FROM users WHERE user_id=?", (user.id,)).fetchone()
    if not u:
        conn.close()
        await update.message.reply_text("🐾 هنوز هاپو نزدی! اول بنویس *هاپ* تا ثبت بشی!", parse_mode="Markdown")
        return

    dog    = conn.execute("SELECT * FROM dogs WHERE user_id=?",        (user.id,)).fetchone()
    hook   = conn.execute("SELECT * FROM hooks WHERE user_id=?",       (user.id,)).fetchone()
    strays = conn.execute("SELECT count FROM user_strays WHERE user_id=?", (user.id,)).fetchone()
    jailed, jail_row = is_in_jail(user.id)

    r_pts = conn.execute(
        "SELECT COUNT(*)+1 FROM users WHERE hop_points > ?", (u["hop_points"],)
    ).fetchone()[0]
    r_hops = conn.execute(
        "SELECT COUNT(*)+1 FROM users WHERE total_hops > ?", (u["total_hops"],)
    ).fetchone()[0]
    stray_count = strays["count"] if strays else 0
    r_stray = conn.execute(
        "SELECT COUNT(*)+1 FROM user_strays WHERE count > ?", (stray_count,)
    ).fetchone()[0]
    conn.close()

    lvl       = u["level"]
    hops      = u["total_hops"]
    next_hops = hops_for_next_level(lvl)
    if next_hops > 0 and lvl > 1:
        prev_hops  = hops_for_next_level(lvl - 1)
        progress   = hops - prev_hops
        needed     = next_hops - prev_hops
        filled     = int((progress / needed) * 5) if needed > 0 else 5
    else:
        filled, needed, progress = 5, 0, hops
    bar = "▰" * filled + "▱" * (5 - filled)

    dog_line = ""
    if dog:
        dog_rank_name, _ = DOG_RANKS.get(dog["rank"], ("نامشخص", 1))
        dog_line = (
            f"\n┐─ 🐕 سگ : {dog['name']}\n"
            f"└─ 🎖️ سطح {dog['level']} | مقام {dog_rank_name}"
        )

    hook_line = ""
    if hook:
        hook_line = f"\n└─ 🎣 قلاب : سطح {hook['level']}"

    jail_line = ""
    if jailed:
        release = datetime.fromisoformat(jail_row["release_at"])
        mins    = int((release - datetime.now()).total_seconds() // 60)
        jail_line = f"\n\n⛓️ *در زندان!* — {mins} دقیقه تا آزادی"

    display_name = f"@{user.username}" if user.username else user.first_name

    caption = (
        f"╮──「 🐾 پروفایل هاپو 🐾 」\n\n"
        f"┐─ 👤 کاربر : {display_name}\n"
        f"└─ 🪪 آیدی : `{user.id}`\n\n"
        f"┐─ 💰 هاپ پوینت : {u['hop_points']:,.0f} 🦴\n"
        f"└─ 🎖️ رتبه ({r_pts:,})\n"
        f"┐─ 🐾 هاپ‌های کل : {hops:,}\n"
        f"└─ 🎖️ رتبه ({r_hops:,})\n\n"
        f"┐─ 🐈 پیشی‌های خیابونی : {stray_count}\n"
        f"└─ 🎖️ رتبه ({r_stray:,})\n"
        f"{dog_line}"
        f"{hook_line}\n\n"
        f"╯─ ⭐️ سطح : {lvl} | {progress} / {needed if needed else '∞'} {bar}"
        f"{jail_line}"
    )

    photo_buf = None
    try:
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count > 0:
            file = await photos.photos[0][-1].get_file()
            photo_buf = io.BytesIO()
            await file.download_to_memory(photo_buf)
            photo_buf.seek(0)
    except Exception:
        logger.warning("Non-fatal exception was suppressed", exc_info=True)

    if photo_buf:
        await update.message.reply_photo(
            photo=photo_buf,
            caption=caption,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(caption, parse_mode="Markdown")

async def hapoha_profile_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ باید روی پیام کسی ریپلای کنی!")
        return

    target = update.message.reply_to_message.from_user
    if target.is_bot:
        await update.message.reply_text("🤖 پروفایل ربات؟ نه بابا!")
        return

    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (target.id,)).fetchone()
    if not u:
        conn.close()
        await update.message.reply_text(
            f"🐾 *{target.first_name}* هنوز هاپو نزده و ثبت نشده!",
            parse_mode="Markdown"
        )
        return

    dog    = conn.execute("SELECT * FROM dogs WHERE user_id=?",            (target.id,)).fetchone()
    hook   = conn.execute("SELECT * FROM hooks WHERE user_id=?",           (target.id,)).fetchone()
    strays = conn.execute("SELECT count FROM user_strays WHERE user_id=?", (target.id,)).fetchone()
    jailed, jail_row = is_in_jail(target.id)

    r_pts = conn.execute(
        "SELECT COUNT(*)+1 FROM users WHERE hop_points > ?", (u["hop_points"],)
    ).fetchone()[0]
    r_hops = conn.execute(
        "SELECT COUNT(*)+1 FROM users WHERE total_hops > ?", (u["total_hops"],)
    ).fetchone()[0]
    stray_count = strays["count"] if strays else 0
    r_stray = conn.execute(
        "SELECT COUNT(*)+1 FROM user_strays WHERE count > ?", (stray_count,)
    ).fetchone()[0]
    conn.close()

    lvl       = u["level"]
    hops      = u["total_hops"]
    next_hops = hops_for_next_level(lvl)
    if next_hops > 0 and lvl > 1:
        prev_hops = hops_for_next_level(lvl - 1)
        progress  = hops - prev_hops
        needed    = next_hops - prev_hops
        filled    = int((progress / needed) * 5) if needed > 0 else 5
    else:
        filled, needed, progress = 5, 0, hops
    bar = "▰" * filled + "▱" * (5 - filled)

    dog_line = ""
    if dog:
        dog_rank_name, _ = DOG_RANKS.get(dog["rank"], ("نامشخص", 1))
        dog_line = (
            f"\n┐─ 🐕 سگ : {dog['name']}\n"
            f"└─ 🎖️ سطح {dog['level']} | مقام {dog_rank_name}"
        )

    hook_line = ""
    if hook:
        hook_line = f"\n└─ 🎣 قلاب : سطح {hook['level']}"

    jail_line = ""
    if jailed:
        release = datetime.fromisoformat(jail_row["release_at"])
        mins    = int((release - datetime.now()).total_seconds() // 60)
        jail_line = f"\n\n⛓️ *در زندان!* — {mins} دقیقه تا آزادی"

    display_name = f"@{target.username}" if target.username else target.first_name

    caption = (
        f"╮──「 🐾 پروفایل هاپو 🐾 」\n\n"
        f"┐─ 👤 کاربر : {display_name}\n"
        f"└─ 🪪 آیدی : `{target.id}`\n\n"
        f"┐─ 💰 هاپ پوینت : {u['hop_points']:,.0f} 🦴\n"
        f"└─ 🎖️ رتبه ({r_pts:,})\n"
        f"┐─ 🐾 هاپ‌های کل : {hops:,}\n"
        f"└─ 🎖️ رتبه ({r_hops:,})\n\n"
        f"┐─ 🐈 پیشی‌های خیابونی : {stray_count}\n"
        f"└─ 🎖️ رتبه ({r_stray:,})\n"
        f"{dog_line}"
        f"{hook_line}\n\n"
        f"╯─ ⭐️ سطح : {lvl} | {progress} / {needed if needed else '∞'} {bar}"
        f"{jail_line}"
    )

    photo_buf = None
    try:
        photos = await context.bot.get_user_profile_photos(target.id, limit=1)
        if photos.total_count > 0:
            file = await photos.photos[0][-1].get_file()
            photo_buf = io.BytesIO()
            await file.download_to_memory(photo_buf)
            photo_buf.seek(0)
    except Exception:
        logger.warning("Non-fatal exception was suppressed", exc_info=True)

    if photo_buf:
        await update.message.reply_photo(photo=photo_buf, caption=caption, parse_mode="Markdown")
    else:
        await update.message.reply_text(caption, parse_mode="Markdown")

MEOW_REPLIES = [
    "اینجا قلمرو هاپوهاست، صدای گربه میاد بار آخرت باشه! 🐕☠️",
    "اشتباهی اومدی داداش، گربه‌ها رو اینجا سگ‌خور می‌کنیم! 🐕",
    "میو؟ مگه تو هاپو نیستی؟ داری جاسوسی گربه‌ها رو می‌کنی؟ 🤨",
    "یک بار دیگه صدا گربه در بیاری بچه‌ها می‌فرستنت انفرادی! 😾"
]

async def handle_meow_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    if not message or not message.text:
        return False

    text = message.text.strip()
    
    if text != "میو":
        return False

    target_user = message.from_user
    chat_id = update.effective_chat.id
    
    reply_text = random.choice(MEOW_REPLIES)
    
    keyboard = [[
        cbtn("رای به زندانی شدن (0/3) ⚖️", callback_data=f"vmeow_{target_user.id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    vote_msg = await message.reply_text(
        f"{reply_text}\n\n🚨 <b>رای‌گیری برای زندانی کردن {target_user.mention_html()} شروع شد!</b>\nاگر تا ۱ دقیقه دیگر ۳ رای جمع بشه، میره زندان!",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    context.job_queue.run_once(
        delete_meow_vote_msg, 
        60, 
        chat_id=chat_id, 
        message_id=vote_msg.message_id,
        data={"target_id": target_user.id}
    )
    
    return True

async def delete_meow_vote_msg(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    target_id = job.data["target_id"]
    if "meow_votes" in context.bot_data and target_id in context.bot_data["meow_votes"]:
        del context.bot_data["meow_votes"][target_id]
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=job.chat_id,
            message_id=job.message_id,
            reply_markup=None
        )
    except Exception:
        logger.warning("Non-fatal exception was suppressed", exc_info=True)
    try:
        await context.bot.delete_message(chat_id=job.chat_id, message_id=job.message_id)
    except Exception:
        logger.warning("Non-fatal exception was suppressed", exc_info=True)


def get_referral_setting(key, default):
    with db_conn() as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (key,)).fetchone()
        if not row: return default
        return row["value"]

def set_referral_setting(key, value):
    with db_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO bot_settings (key,value) VALUES (?,?)", (key, str(value)))
        conn.commit()

def is_referral_enabled() -> bool:
    return get_referral_setting("referral_enabled", "1") == "1"

def get_referral_reward_sender() -> int:
    return int(get_referral_setting("referral_reward_sender", str(REFERRAL_REWARD_SENDER)))

def get_referral_reward_joiner() -> int:
    return int(get_referral_setting("referral_reward_joiner", str(REFERRAL_REWARD_JOINER)))

def get_referral_count(user_id: int) -> int:
    with db_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM referrals WHERE inviter_id=? AND rewarded=1", (user_id,)
        ).fetchone()
        return row[0] if row else 0

async def referral_invite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type != "private":
        await update.message.reply_text("🔗 لینک دعوت رو توی پیوی بهت میدم! ربات رو توی پیوی باز کن.")
        return
    if not is_referral_enabled():
        await update.message.reply_text("❌ سیستم دعوت دوستان فعلاً غیرفعاله.")
        return
    invite_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
    count = get_referral_count(user.id)
    reward_sender = get_referral_reward_sender()
    reward_joiner = get_referral_reward_joiner()
    text = (
        f"🎁 *دعوت دوستان*\n\n"
        f"لینک اختصاصی تو:\n`{invite_link}`\n\n"
        f"👥 تعداد دعوت‌های موفق: *{count} نفر*\n\n"
        f"💰 جوایز:\n"
        f"┐─ دعوت‌کننده (تو): *{reward_sender:,} هاپ پوینت*\n"
        f"└─ دعوت‌شده (دوستت): *{reward_joiner:,} هاپ پوینت*\n\n"
        f"⚡️ جایزه بعد از اولین هاپ دوستت واریز میشه!"
    )
    kb = InlineKeyboardMarkup([
        [cbtn("📤 اشتراک‌گذاری لینک", url=f"https://t.me/share/url?url={invite_link}&text=بیا%20هاپ%20داگ%20بازی%20کن!")],
        [cbtn("👥 تعداد دعوت‌هام", callback_data="ref_mystats")],
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def referral_admin_panel(message_or_query, edit=False):
    enabled = is_referral_enabled()
    reward_s = get_referral_reward_sender()
    reward_j = get_referral_reward_joiner()
    with db_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM referrals WHERE rewarded=1").fetchone()[0]
    status = "🟢 فعال" if enabled else "🔴 غیرفعال"
    toggle_label = "🔴 غیرفعال کردن دعوت" if enabled else "🟢 فعال کردن دعوت"
    text = (
        f"🎁 *پنل مدیریت دعوت دوستان*\n\n"
        f"وضعیت: {status}\n"
        f"💰 جایزه دعوت‌کننده: {reward_s:,}\n"
        f"💰 جایزه دعوت‌شده: {reward_j:,}\n"
        f"👥 کل دعوت‌های موفق: {total}\n\n"
        f"یه گزینه انتخاب کن:"
    )
    kb = InlineKeyboardMarkup([
        [cbtn(toggle_label, callback_data="ref_admin_toggle")],
        [cbtn("✏️ تغییر جایزه دعوت‌کننده", callback_data="ref_admin_set_sender")],
        [cbtn("✏️ تغییر جایزه دعوت‌شده", callback_data="ref_admin_set_joiner")],
    ])
    if edit:
        await message_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await message_or_query.reply_text(text, parse_mode="Markdown", reply_markup=kb)

REFERRAL_ADMIN_CONV = {}

async def handle_referral_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user.id not in REFERRAL_ADMIN_CONV:
        return False
    if update.effective_chat.type != "private":
        return False
    if not is_admin(user.id):
        del REFERRAL_ADMIN_CONV[user.id]
        return False
    text = update.message.text.strip()
    field = REFERRAL_ADMIN_CONV[user.id]
    try:
        amount = int(text.replace(",", "").replace("،", ""))
        if amount < 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ عدد معتبر وارد کن!")
        return True
    if field == "sender":
        set_referral_setting("referral_reward_sender", amount)
        await update.message.reply_text(f"✅ جایزه دعوت‌کننده به *{amount:,}* تغییر کرد!", parse_mode="Markdown")
    else:
        set_referral_setting("referral_reward_joiner", amount)
        await update.message.reply_text(f"✅ جایزه دعوت‌شده به *{amount:,}* تغییر کرد!", parse_mode="Markdown")
    del REFERRAL_ADMIN_CONV[user.id]
    return True

async def handle_referral_callbacks(query, data, user, context) -> bool:
    uid = user.id

    if data == "ref_mystats":
        count = get_referral_count(uid)
        reward_s = get_referral_reward_sender()
        await query.answer()
        await query.edit_message_text(
            f"👥 *دعوت‌های موفق تو: {count} نفر*\n\n"
            f"💰 جمع جایزه دریافتی: {count * reward_s:,} هاپ پوینت\n\n"
            f"هر دوستی که با لینک تو بیاد و اولین هاپش رو بزنه = +{reward_s:,} برای تو!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data="ref_back")]])
        )
        return True

    if data == "ref_back":
        await query.answer()
        await referral_invite_cmd_query(query, user, context)
        return True

    if data == "ref_admin_toggle":
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        current = is_referral_enabled()
        set_referral_setting("referral_enabled", "0" if current else "1")
        await query.answer("✅ وضعیت تغییر کرد!")
        await referral_admin_panel(query, edit=True)
        return True

    if data == "ref_admin_set_sender":
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        REFERRAL_ADMIN_CONV[uid] = "sender"
        await query.edit_message_text(
            "✏️ مقدار جدید جایزه دعوت‌کننده رو بنویس (هاپ پوینت):\n\nبرای لغو بنویس: لغو"
        )
        return True

    if data == "ref_admin_set_joiner":
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        REFERRAL_ADMIN_CONV[uid] = "joiner"
        await query.edit_message_text(
            "✏️ مقدار جدید جایزه دعوت‌شده رو بنویس (هاپ پوینت):\n\nبرای لغو بنویس: لغو"
        )
        return True

    return False

async def referral_invite_cmd_query(query, user, context):
    if not is_referral_enabled():
        await query.edit_message_text("❌ سیستم دعوت دوستان فعلاً غیرفعاله.")
        return
    invite_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
    count = get_referral_count(user.id)
    reward_sender = get_referral_reward_sender()
    reward_joiner = get_referral_reward_joiner()
    text = (
        f"🎁 *دعوت دوستان*\n\n"
        f"لینک اختصاصی تو:\n`{invite_link}`\n\n"
        f"👥 تعداد دعوت‌های موفق: *{count} نفر*\n\n"
        f"💰 جوایز:\n"
        f"┐─ دعوت‌کننده (تو): *{reward_sender:,} هاپ پوینت*\n"
        f"└─ دعوت‌شده (دوستت): *{reward_joiner:,} هاپ پوینت*\n\n"
        f"⚡️ جایزه بعد از اولین هاپ دوستت واریز میشه!"
    )
    kb = InlineKeyboardMarkup([
        [cbtn("📤 اشتراک‌گذاری لینک", url=f"https://t.me/share/url?url={invite_link}&text=بیا%20هاپ%20داگ%20بازی%20کن!")],
        [cbtn("👥 تعداد دعوت‌هام", callback_data="ref_mystats")],
    ])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


import uuid as _uuid

def market_id_gen():
    return _uuid.uuid4().hex[:10]

def is_market_open() -> bool:
    with db_conn() as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key='market_open'").fetchone()
        if not row: return True
        return row["value"] == "1"

def set_market_open(val: bool):
    with db_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_settings (key,value) VALUES ('market_open',?)",
            ("1" if val else "0",)
        )
        conn.commit()

def get_listing(listing_id):
    with db_conn() as conn:
        return conn.execute("SELECT * FROM user_market WHERE listing_id=?", (listing_id,)).fetchone()

def get_active_listings():
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM user_market WHERE status='active' ORDER BY created_at DESC"
        ).fetchall()

def get_seller_listings(seller_id):
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM user_market WHERE seller_id=? ORDER BY created_at DESC", (seller_id,)
        ).fetchall()

def get_pending_listings():
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM user_market WHERE status='pending' ORDER BY created_at ASC"
        ).fetchall()

async def market_admin_panel(update_or_query, edit=False):
    pendings = get_pending_listings()
    actives  = get_active_listings()
    market_status = "🟢 باز" if is_market_open() else "🔴 تعطیل"
    text = (
        f"🛒 *پنل مدیریت مارکت*\n\n"
        f"وضعیت مارکت: {market_status}\n"
        f"⏳ در انتظار تأیید: {len(pendings)} آگهی\n"
        f"✅ فعال: {len(actives)} آگهی\n\n"
        f"یه گزینه انتخاب کن:"
    )
    toggle_label = "🔴 تعطیل کردن مارکت" if is_market_open() else "🟢 باز کردن مارکت"
    kb = InlineKeyboardMarkup([
        [cbtn(f"⏳ بررسی آگهی‌های در انتظار ({len(pendings)})", callback_data="mkt_admin_pending")],
        [cbtn(f"📋 لیست آگهی‌های فعال", callback_data="mkt_admin_active")],
        [cbtn(toggle_label, callback_data="mkt_admin_toggle")],
    ])
    if edit:
        await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update_or_query.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    user = update.effective_user

    if chat_type == "private":
        await market_private_panel(update.message, user, context)
    else:
        if not is_market_open():
            await update.message.reply_text("🔴 مارکت در حال حاضر تعطیله!")
            return
        listings = get_active_listings()
        if not listings:
            await update.message.reply_text("🛒 مارکت خالیه! هنوز آگهی فعالی ثبت نشده.")
            return
        text = "🛒 *مارکت هاپ‌داگ*\n\n"
        kb_rows = []
        for l in listings:
            remaining = l["max_buyers"] - l["buyer_count"]
            text += (
                f"🏷 *{l['title']}*\n"
                f"👤 فروشنده: {l['seller_name']}\n"
                f"💰 قیمت: {l['price']:,} هاپ پوینت\n"
                f"📦 ظرفیت باقی‌مانده: {remaining}\n"
                f"───────────────\n"
            )
            kb_rows.append([cbtn(f"🛍 خرید «{l['title']}»", callback_data=f"mkt_buy_{l['listing_id']}")])
        await update.message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )

async def market_private_panel(message, user, context):
    my_listings = get_seller_listings(user.id)
    active = [l for l in my_listings if l["status"] == "active"]
    pending = [l for l in my_listings if l["status"] == "pending"]
    cancelled = [l for l in my_listings if l["status"] == "cancelled"]
    text = (
        f"🛒 *پنل مارکت شخصی*\n\n"
        f"✅ فعال: {len(active)} آگهی\n"
        f"⏳ در انتظار تأیید: {len(pending)} آگهی\n"
        f"❌ لغو‌شده: {len(cancelled)} آگهی\n\n"
        f"یه گزینه انتخاب کن:"
    )
    kb = [[cbtn("➕ ثبت آگهی جدید", callback_data="mkt_new")]]
    if active or pending:
        kb.append([cbtn("📋 آگهی‌های من", callback_data="mkt_my_listings")])
    await message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

MARKET_CONV = {}

async def handle_market_private_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user.id not in MARKET_CONV:
        return False
    if update.effective_chat.type != "private":
        return False
    if not update.message or not update.message.text:
        return False

    text = update.message.text.strip()
    state = MARKET_CONV[user.id]
    step = state["step"]

    if text == "لغو" or text == "انصراف":
        del MARKET_CONV[user.id]
        await update.message.reply_text("❌ ثبت آگهی لغو شد.")
        return True

    if step == "title":
        if len(text) > 50:
            await update.message.reply_text("❌ اسم محصول حداکثر ۵۰ کاراکتر!")
            return True
        state["title"] = text
        state["step"] = "description"
        await update.message.reply_text(
            "📝 *توضیح محصول:*\nیه توضیح کوتاه بنویس که خریدار قبل از خرید بخونه.\n_(محتوای اصلی بعداً پرسیده میشه)_\n\nبرای لغو بنویس: لغو",
            parse_mode="Markdown"
        )

    elif step == "description":
        if len(text) > 200:
            await update.message.reply_text("❌ توضیح حداکثر ۲۰۰ کاراکتر!")
            return True
        state["description"] = text
        state["step"] = "price"
        await update.message.reply_text(
            "💰 *قیمت (هاپ پوینت):*\nچند هاپ پوینت میخوای بفروشی؟\n\nبرای لغو بنویس: لغو",
            parse_mode="Markdown"
        )

    elif step == "price":
        try:
            price = int(text.replace(",", "").replace("،", ""))
            if price < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ قیمت باید یه عدد مثبت باشه!")
            return True
        state["price"] = price
        state["step"] = "max_buyers"
        await update.message.reply_text(
            "👥 *حداکثر تعداد خریدار:*\nچند نفر میتونن این آگهی رو بخرن؟\n_(بعد از رسیدن به این تعداد، آگهی خودکار حذف میشه)_\n\nبرای لغو بنویس: لغو",
            parse_mode="Markdown"
        )

    elif step == "max_buyers":
        try:
            max_b = int(text)
            if max_b < 1 or max_b > 1000:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ عدد بین ۱ تا ۱۰۰۰ وارد کن!")
            return True
        state["max_buyers"] = max_b
        state["step"] = "content"
        await update.message.reply_text(
            "📦 *محتوای آگهی:*\nاین چیزیه که بعد از خرید، توی پیوی خریدار فرستاده میشه.\n"
            "میتونه لینک، آیدی، متن یا هر چیزی باشه.\n\n"
            "⚠️ این محتوا فقط برای ادمین و خریدار قابل دیدنه.\n\nبرای لغو بنویس: لغو",
            parse_mode="Markdown"
        )

    elif step == "content":
        state["content"] = text
        state["step"] = "confirm"
        d = state
        await update.message.reply_text(
            f"✅ *بررسی آگهی:*\n\n"
            f"🏷 نام: {d['title']}\n"
            f"📝 توضیح: {d['description']}\n"
            f"💰 قیمت: {d['price']:,} هاپ پوینت\n"
            f"👥 حداکثر خریدار: {d['max_buyers']} نفر\n"
            f"📦 محتوا: {d['content']}\n\n"
            f"آیا تأیید میکنی؟",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [cbtn("✅ ارسال برای تأیید ادمین", callback_data="mkt_submit_confirm")],
                [cbtn("❌ لغو", callback_data="mkt_submit_cancel")],
            ])
        )

    return True

async def handle_market_callbacks(query, data, user, context) -> bool:
    uid = user.id

    if data == "mkt_admin_toggle":
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین اصلی!", show_alert=True); return True
        current = is_market_open()
        set_market_open(not current)
        await query.answer("✅ وضعیت مارکت تغییر کرد!")
        await market_admin_panel(query, edit=True)
        return True

    if data == "mkt_admin_pending":
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        pendings = get_pending_listings()
        if not pendings:
            await query.edit_message_text("✅ هیچ آگهی در انتظاری نیست!", reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data="mkt_admin_back")]]))
            return True
        kb = []
        for l in pendings:
            kb.append([cbtn(f"👁 {l['title']} — {l['seller_name']}", callback_data=f"mkt_admin_review_{l['listing_id']}")])
        kb.append([cbtn("🔙 برگشت", callback_data="mkt_admin_back")])
        await query.edit_message_text(
            f"⏳ *آگهی‌های در انتظار تأیید ({len(pendings)} عدد):*",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
        )
        return True

    if data.startswith("mkt_admin_review_"):
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        lid = data.split("_", 3)[3]
        l = get_listing(lid)
        if not l:
            await query.edit_message_text("❌ آگهی پیدا نشد!"); return True
        await query.edit_message_text(
            f"📋 *بررسی آگهی*\n\n"
            f"🏷 نام: {l['title']}\n"
            f"👤 فروشنده: {l['seller_name']} (آیدی: `{l['seller_id']}`)\n"
            f"📝 توضیح: {l['description']}\n"
            f"💰 قیمت: {l['price']:,} هاپ پوینت\n"
            f"👥 حداکثر خریدار: {l['max_buyers']}\n"
            f"📦 محتوا (برای خریدار): {l['content']}\n"
            f"📅 ثبت شده: {l['created_at'][:16]}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [cbtn("✅ تأیید", callback_data=f"mkt_admin_approve_{lid}"),
                 cbtn("❌ رد", callback_data=f"mkt_admin_reject_{lid}")],
                [cbtn("🔙 برگشت", callback_data="mkt_admin_pending")],
            ])
        )
        return True

    if data.startswith("mkt_admin_approve_"):
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        lid = data.split("_", 3)[3]
        with db_conn() as conn:
            conn.execute("UPDATE user_market SET status='active' WHERE listing_id=?", (lid,))
            conn.commit()
        l = get_listing(lid)
        await query.edit_message_text(f"✅ آگهی *{l['title']}* تأیید و در مارکت منتشر شد!", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data="mkt_admin_pending")]]))
        try:
            await context.bot.send_message(
                chat_id=l["seller_id"],
                text=f"✅ *آگهیت تأیید شد!*\n\n🏷 «{l['title']}» الان توی مارکت فعاله و قابل خریده.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return True

    if data.startswith("mkt_admin_reject_"):
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        lid = data.split("_", 3)[3]
        with db_conn() as conn:
            conn.execute("UPDATE user_market SET status='rejected' WHERE listing_id=?", (lid,))
            conn.commit()
        l = get_listing(lid)
        await query.edit_message_text(f"❌ آگهی *{l['title']}* رد شد.", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data="mkt_admin_pending")]]))
        try:
            await context.bot.send_message(
                chat_id=l["seller_id"],
                text=f"❌ *آگهیت رد شد!*\n\n🏷 «{l['title']}» توسط ادمین تأیید نشد.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return True

    if data == "mkt_admin_active":
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        actives = get_active_listings()
        if not actives:
            await query.edit_message_text("📋 هیچ آگهی فعالی وجود نداره!", reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data="mkt_admin_back")]]))
            return True
        kb = []
        for l in actives:
            remaining = l["max_buyers"] - l["buyer_count"]
            kb.append([cbtn(f"🏷 {l['title']} | {remaining} باقی", callback_data=f"mkt_admin_deactivate_{l['listing_id']}")])
        kb.append([cbtn("🔙 برگشت", callback_data="mkt_admin_back")])
        await query.edit_message_text("📋 *آگهی‌های فعال* (برای لغو انتخاب کن):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return True

    if data.startswith("mkt_admin_deactivate_"):
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        lid = data.split("_", 3)[3]
        with db_conn() as conn:
            conn.execute("UPDATE user_market SET status='cancelled' WHERE listing_id=?", (lid,))
            conn.commit()
        l = get_listing(lid)
        await query.answer(f"❌ آگهی {l['title']} لغو شد!")
        await query.edit_message_text(f"❌ آگهی *{l['title']}* لغو شد.", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data="mkt_admin_active")]]))
        try:
            await context.bot.send_message(chat_id=l["seller_id"],
                text=f"⚠️ آگهیت «{l['title']}» توسط ادمین لغو شد.", parse_mode="Markdown")
        except Exception:
            pass
        return True

    if data == "mkt_admin_back":
        if not is_admin(uid):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        await market_admin_panel(query, edit=True)
        return True

    if data == "mkt_new":
        if not is_market_open():
            await query.answer("🔴 مارکت الان تعطیله!", show_alert=True); return True
        MARKET_CONV[uid] = {"step": "title", "data": {}}
        await query.edit_message_text(
            "🏷 *اسم محصول:*\nیه اسم کوتاه و واضح برای آگهیت بنویس.\n\nبرای لغو بنویس: لغو",
            parse_mode="Markdown"
        )
        return True

    if data == "mkt_submit_confirm":
        if uid not in MARKET_CONV:
            await query.answer("❌ اطلاعات پیدا نشد!", show_alert=True); return True
        state = MARKET_CONV[uid]
        lid = market_id_gen()
        with db_conn() as conn:
            conn.execute(
                "INSERT INTO user_market (listing_id,seller_id,seller_name,title,description,content,price,max_buyers,status) VALUES (?,?,?,?,?,?,?,?,'pending')",
                (lid, uid, user.full_name, state["title"], state["description"], state["content"], state["price"], state["max_buyers"])
            )
            conn.commit()
        del MARKET_CONV[uid]
        await query.edit_message_text(
            f"✅ *آگهیت ثبت شد!*\n\n«{state['title']}» برای تأیید ادمین فرستاده شد.\nبعد از تأیید، توی مارکت منتشر میشه و بهت خبر میدم.",
            parse_mode="Markdown"
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔔 *آگهی جدید در انتظار تأیید*\n\n🏷 {state['title']}\n👤 {user.full_name}\n💰 {state['price']:,} هاپ پوینت\n\nبرای بررسی بنویس: مارکت",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return True

    if data == "mkt_submit_cancel":
        if uid in MARKET_CONV:
            del MARKET_CONV[uid]
        await query.edit_message_text("❌ ثبت آگهی لغو شد.")
        return True

    if data == "mkt_my_listings":
        listings = get_seller_listings(uid)
        if not listings:
            await query.edit_message_text("📋 هنوز هیچ آگهیی نداری!", reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data="mkt_my_back")]]))
            return True
        kb = []
        for l in listings:
            emoji = {"active": "✅", "pending": "⏳", "cancelled": "❌", "rejected": "🚫"}.get(l["status"], "❓")
            kb.append([cbtn(f"{emoji} {l['title']} | {l['buyer_count']}/{l['max_buyers']} خریدار", callback_data=f"mkt_my_detail_{l['listing_id']}")])
        kb.append([cbtn("🔙 برگشت", callback_data="mkt_my_back")])
        await query.edit_message_text("📋 *آگهی‌های من:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return True

    if data.startswith("mkt_my_detail_"):
        lid = data.split("_", 3)[3]
        l = get_listing(lid)
        if not l or l["seller_id"] != uid:
            await query.answer("❌ آگهی پیدا نشد!", show_alert=True); return True
        status_text = {"active": "✅ فعال", "pending": "⏳ در انتظار تأیید", "cancelled": "❌ لغو شده", "rejected": "🚫 رد شده"}.get(l["status"], "؟")
        text = (
            f"🏷 *{l['title']}*\n\n"
            f"📊 وضعیت: {status_text}\n"
            f"💰 قیمت: {l['price']:,} هاپ پوینت\n"
            f"👥 خریداران: {l['buyer_count']} از {l['max_buyers']} نفر\n"
            f"📝 توضیح: {l['description']}\n"
            f"📅 ثبت شده: {l['created_at'][:16]}"
        )
        kb = []
        if l["status"] == "active":
            kb.append([cbtn("❌ لغو آگهی", callback_data=f"mkt_my_cancel_{lid}")])
        kb.append([cbtn("🔙 برگشت", callback_data="mkt_my_listings")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return True

    if data.startswith("mkt_my_cancel_"):
        lid = data.split("_", 3)[3]
        l = get_listing(lid)
        if not l or l["seller_id"] != uid:
            await query.answer("❌ مجاز نیستی!", show_alert=True); return True
        with db_conn() as conn:
            conn.execute("UPDATE user_market SET status='cancelled' WHERE listing_id=?", (lid,))
            conn.commit()
        await query.answer("❌ آگهی لغو شد!")
        await query.edit_message_text(f"❌ آگهی *{l['title']}* لغو شد.", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data="mkt_my_listings")]]))
        return True

    if data == "mkt_my_back":
        from telegram import Message
        await query.edit_message_text(
            "🛒 *پنل مارکت شخصی*\n\nیه گزینه انتخاب کن:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [cbtn("➕ ثبت آگهی جدید", callback_data="mkt_new")],
                [cbtn("📋 آگهی‌های من", callback_data="mkt_my_listings")],
            ])
        )
        return True

    if data.startswith("mkt_buy_") and not data.startswith("mkt_buy_confirm_"):
        if not is_market_open():
            await query.answer("🔴 مارکت الان تعطیله!", show_alert=True); return True
        lid = data.split("_", 2)[2]
        l = get_listing(lid)
        if not l or l["status"] != "active":
            await query.answer("❌ این آگهی دیگه فعال نیست!", show_alert=True); return True
        if l["seller_id"] == uid:
            await query.answer("❌ نمیتونی محصول خودت رو بخری!", show_alert=True); return True
        with db_conn() as conn:
            already = conn.execute("SELECT 1 FROM user_market_buyers WHERE listing_id=? AND buyer_id=?", (lid, uid)).fetchone()
        if already:
            await query.answer("❌ قبلاً این رو خریدی!", show_alert=True); return True
        u = get_user(uid)
        if not u or u["hop_points"] < l["price"]:
            await query.answer(f"❌ پوینت کافی نداری! لازم: {l['price']:,}", show_alert=True); return True
        await query.answer()
        await query.message.reply_text(
            f"🛍 *تأیید خرید*\n\n"
            f"🏷 {l['title']}\n"
            f"💰 قیمت: {l['price']:,} هاپ پوینت\n"
            f"📝 {l['description']}\n\n"
            f"مطمئنی؟",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [cbtn("✅ بله، خریدم!", callback_data=f"mkt_buy_confirm_{lid}"),
                 cbtn("❌ انصراف", callback_data="cancel")],
            ])
        )
        return True

    if data.startswith("mkt_buy_confirm_"):
        lid = data.split("_", 3)[3]
        l = get_listing(lid)
        if not l or l["status"] != "active":
            await query.answer("❌ آگهی دیگه فعال نیست!", show_alert=True); return True
        if l["seller_id"] == uid:
            await query.answer("❌ نمیتونی محصول خودت رو بخری!", show_alert=True); return True
        with db_conn() as conn:
            already = conn.execute("SELECT 1 FROM user_market_buyers WHERE listing_id=? AND buyer_id=?", (lid, uid)).fetchone()
            if already:
                await query.answer("❌ قبلاً خریدی!", show_alert=True); return True
            u = conn.execute("SELECT hop_points FROM users WHERE user_id=?", (uid,)).fetchone()
            if not u or u["hop_points"] < l["price"]:
                await query.answer(f"❌ پوینت کافی نداری!", show_alert=True); return True
            conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (l["price"], uid))
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (l["price"], l["seller_id"]))
            conn.execute("INSERT INTO user_market_buyers (listing_id,buyer_id) VALUES (?,?)", (lid, uid))
            new_count = l["buyer_count"] + 1
            if new_count >= l["max_buyers"]:
                conn.execute("UPDATE user_market SET buyer_count=?, status='done' WHERE listing_id=?", (new_count, lid))
            else:
                conn.execute("UPDATE user_market SET buyer_count=? WHERE listing_id=?", (new_count, lid))
            conn.commit()
        await query.edit_message_text(
            f"✅ *خرید موفق!*\n\n💰 {l['price']:,} هاپ پوینت کسر شد.\nمحتوای آگهی توی پیوی برات فرستاده شد 📩",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📦 *محتوای خریدت:*\n\n🏷 {l['title']}\n\n{l['content']}",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=l["seller_id"],
                text=f"🛍 *یه نفر آگهیت رو خرید!*\n\n🏷 {l['title']}\n💰 +{l['price']:,} هاپ پوینت دریافت کردی\n👥 خریداران: {new_count}/{l['max_buyers']}",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return True

    return False


def lottery_id_gen():
    import uuid
    return uuid.uuid4().hex[:10]

def get_lottery(lottery_id):
    with db_conn() as conn:
        return conn.execute("SELECT * FROM lotteries WHERE lottery_id=?", (lottery_id,)).fetchone()

def get_all_lotteries():
    with db_conn() as conn:
        return conn.execute("SELECT * FROM lotteries ORDER BY created_at DESC").fetchall()

def get_lottery_entries(lottery_id):
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM lottery_entries WHERE lottery_id=? ORDER BY joined_at ASC",
            (lottery_id,)
        ).fetchall()

def get_lottery_entry(lottery_id, user_id):
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM lottery_entries WHERE lottery_id=? AND user_id=?",
            (lottery_id, user_id)
        ).fetchone()

def lottery_participant_text(entries):
    if not entries:
        return "هنوز کسی شرکت نکرده 😿"
    lines = []
    for i, e in enumerate(entries, 1):
        uname = f"@{e['username']}" if e['username'] else "—"
        lines.append(f"{i}. {e['first_name']} ({uname})")
    return "\n".join(lines)

def lottery_announce_text(lot, entries):
    return (
        f"🎰 *قرعه‌کشی: {lot['title']}*\n\n"
        f"🎁 جایزه: {lot['prize']:,} هاپ پوینت\n"
        f"🏆 تعداد برنده: {lot['winner_count']} نفر\n\n"
        f"👥 شرکت‌کنندگان ({len(entries)} نفر):\n"
        f"{lottery_participant_text(entries)}"
    )

async def lottery_admin_panel(message_obj, edit=False):
    lotteries = get_all_lotteries()
    open_lots = [l for l in lotteries if l['state'] == 'open']
    done_lots = [l for l in lotteries if l['state'] == 'done']
    cancelled = [l for l in lotteries if l['state'] == 'cancelled']

    text = (
        f"🎰 *پنل مدیریت قرعه‌کشی*\n\n"
        f"🟢 باز: {len(open_lots)}\n"
        f"✅ انجام‌شده: {len(done_lots)}\n"
        f"❌ لغو‌شده: {len(cancelled)}\n\n"
        f"یه گزینه انتخاب کن:"
    )
    kb = InlineKeyboardMarkup([
        [cbtn("➕ ساخت قرعه‌کشی جدید", callback_data="lot_new")],
        [cbtn("📋 لیست همه قرعه‌کشی‌ها", callback_data="lot_list_0")],
        [cbtn("🟢 قرعه‌کشی‌های باز", callback_data="lot_open")],
    ])
    if edit:
        await message_obj.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await message_obj.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def lottery_panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return
    await lottery_admin_panel(update.message)

async def do_lottery_draw(lottery_id, context):
    lot = get_lottery(lottery_id)
    if not lot or lot['state'] != 'open':
        return
    entries = get_lottery_entries(lottery_id)
    if not entries:
        with db_conn() as conn:
            conn.execute("UPDATE lotteries SET state='cancelled' WHERE lottery_id=?", (lottery_id,))
            conn.commit()
        return

    import random as _random
    winner_count = min(lot['winner_count'], len(entries))
    winners = _random.sample(list(entries), winner_count)
    prize_each = lot['prize'] // winner_count

    with db_conn() as conn:
        for w in winners:
            conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?",
                         (prize_each, w['user_id']))
        conn.execute("UPDATE lotteries SET state='done' WHERE lottery_id=?", (lottery_id,))
        conn.commit()

    winner_lines = []
    for w in winners:
        uname = f"@{w['username']}" if w['username'] else "—"
        winner_lines.append(
            f"🏆 *{w['first_name']}*\n"
            f"   🆔 آیدی: `{w['user_id']}`\n"
            f"   👤 یوزرنیم: {uname}\n"
            f"   💰 جایزه: {prize_each:,} هاپ پوینت"
        )
    announce = (
        f"🎉 *نتیجه قرعه‌کشی: {lot['title']}*\n\n"
        f"از بین {len(entries)} نفر شرکت‌کننده، "
        f"{winner_count} نفر انتخاب شدن:\n\n"
        + "\n\n".join(winner_lines) +
        f"\n\n✨ تبریک به برندگان!"
    )

    with db_conn() as conn:
        groups = conn.execute("SELECT group_id FROM groups").fetchall()
    for g in groups:
        try:
            await context.bot.send_message(
                chat_id=g['group_id'],
                text=announce,
                parse_mode="Markdown"
            )
        except Exception:
            pass

async def lottery_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data = query.data
    user = query.from_user

    if data == "lot_panel":
        if user.id not in ADMIN_IDS:
            await query.answer("فقط ادمین!", show_alert=True); return True
        await query.answer()
        await lottery_admin_panel(query, edit=True)
        return True

    if data == "lot_new":
        if user.id not in ADMIN_IDS:
            await query.answer("فقط ادمین!", show_alert=True); return True
        await query.answer()
        context.user_data["lot_create"] = {"step": "title"}
        await query.edit_message_text(
            "🎰 *ساخت قرعه‌کشی جدید*\n\n"
            "📝 اسم قرعه‌کشی رو بنویس:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                cbtn("❌ انصراف", callback_data="lot_panel")
            ]])
        )
        return True

    if data.startswith("lot_list_"):
        if user.id not in ADMIN_IDS:
            await query.answer("فقط ادمین!", show_alert=True); return True
        await query.answer()
        page = int(data.split("_")[2])
        lotteries = get_all_lotteries()
        per_page = 5
        total = len(lotteries)
        start = page * per_page
        page_lots = lotteries[start:start+per_page]
        state_emoji = {"open": "🟢", "done": "✅", "cancelled": "❌"}
        lines = []
        kb_rows = []
        for i, l in enumerate(page_lots):
            emoji = state_emoji.get(l['state'], "❓")
            entries = get_lottery_entries(l['lottery_id'])
            lines.append(f"{emoji} *{l['title']}* — {len(entries)} نفر — جایزه: {l['prize']:,}")
            kb_rows.append([cbtn(
                f"{emoji} {l['title']}", callback_data=f"lot_view_{l['lottery_id']}"
            )])
        nav = []
        if page > 0:
            nav.append(cbtn("◀️ قبلی", callback_data=f"lot_list_{page-1}"))
        if start + per_page < total:
            nav.append(cbtn("بعدی ▶️", callback_data=f"lot_list_{page+1}"))
        if nav:
            kb_rows.append(nav)
        kb_rows.append([cbtn("🔙 پنل", callback_data="lot_panel")])
        text = f"📋 *همه قرعه‌کشی‌ها* ({total} تا)\n\n" + ("\n".join(lines) if lines else "هیچ قرعه‌کشی‌ای نیست!")
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb_rows))
        return True

    if data == "lot_open":
        if user.id not in ADMIN_IDS:
            await query.answer("فقط ادمین!", show_alert=True); return True
        await query.answer()
        lotteries = [l for l in get_all_lotteries() if l['state'] == 'open']
        kb_rows = []
        for l in lotteries:
            entries = get_lottery_entries(l['lottery_id'])
            kb_rows.append([cbtn(
                f"🟢 {l['title']} — {len(entries)} نفر", callback_data=f"lot_view_{l['lottery_id']}"
            )])
        kb_rows.append([cbtn("🔙 پنل", callback_data="lot_panel")])
        text = f"🟢 *قرعه‌کشی‌های باز* ({len(lotteries)} تا)"
        if not lotteries:
            text += "\n\nهیچ قرعه‌کشی بازی نیست!"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb_rows))
        return True

    if data.startswith("lot_view_"):
        if user.id not in ADMIN_IDS:
            await query.answer("فقط ادمین!", show_alert=True); return True
        await query.answer()
        lot_id = data[9:]
        lot = get_lottery(lot_id)
        if not lot:
            await query.edit_message_text("❌ قرعه‌کشی پیدا نشد!")
            return True
        entries = get_lottery_entries(lot_id)
        state_map = {"open": "🟢 باز", "done": "✅ انجام‌شده", "cancelled": "❌ لغو"}
        text = (
            f"🎰 *{lot['title']}*\n\n"
            f"📌 وضعیت: {state_map.get(lot['state'], lot['state'])}\n"
            f"🎁 جایزه کل: {lot['prize']:,} هاپ پوینت\n"
            f"🏆 تعداد برنده: {lot['winner_count']} نفر\n"
            f"👥 شرکت‌کنندگان: {len(entries)} نفر\n\n"
            f"{lottery_participant_text(entries)}"
        )
        kb_rows = []
        if lot['state'] == 'open':
            kb_rows.append([
                cbtn("🎲 قرعه‌کشی همین الان!", callback_data=f"lot_draw_{lot_id}"),
                cbtn("❌ لغو", callback_data=f"lot_cancel_{lot_id}"),
            ])
        kb_rows.append([cbtn("🔙 برگشت", callback_data="lot_list_0")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb_rows))
        return True

    if data.startswith("lot_cancel_"):
        if user.id not in ADMIN_IDS:
            await query.answer("فقط ادمین!", show_alert=True); return True
        lot_id = data[11:]
        lot = get_lottery(lot_id)
        if not lot or lot['state'] != 'open':
            await query.answer("❌ نمیشه لغو کرد!", show_alert=True); return True
        await query.answer()
        kb = InlineKeyboardMarkup([[
            cbtn("✅ بله، لغو کن", callback_data=f"lot_cancel_confirm_{lot_id}"),
            cbtn("❌ نه", callback_data=f"lot_view_{lot_id}"),
        ]])
        await query.edit_message_text(
            f"⚠️ مطمئنی میخوای قرعه‌کشی *{lot['title']}* رو لغو کنی?",
            parse_mode="Markdown", reply_markup=kb
        )
        return True

    if data.startswith("lot_cancel_confirm_"):
        if user.id not in ADMIN_IDS:
            await query.answer("فقط ادمین!", show_alert=True); return True
        lot_id = data[19:]
        with db_conn() as conn:
            conn.execute("UPDATE lotteries SET state='cancelled' WHERE lottery_id=?", (lot_id,))
            conn.commit()
        await query.answer("❌ قرعه‌کشی لغو شد!")
        await query.edit_message_text("❌ *قرعه‌کشی لغو شد.*", parse_mode="Markdown",
                                       reply_markup=InlineKeyboardMarkup([[
                                           cbtn("🔙 پنل", callback_data="lot_panel")
                                       ]]))
        return True

    if data.startswith("lot_draw_"):
        if user.id not in ADMIN_IDS:
            await query.answer("فقط ادمین!", show_alert=True); return True
        lot_id = data[9:]
        lot = get_lottery(lot_id)
        if not lot or lot['state'] != 'open':
            await query.answer("❌ قرعه‌کشی باز نیست!", show_alert=True); return True
        entries = get_lottery_entries(lot_id)
        if not entries:
            await query.answer("❌ هیچ شرکت‌کننده‌ای نیست!", show_alert=True); return True
        await query.answer("🎲 در حال قرعه‌کشی...")
        await query.edit_message_text("⏳ *در حال قرعه‌کشی...*", parse_mode="Markdown")
        await do_lottery_draw(lot_id, context)
        await query.edit_message_text(
            "✅ *قرعه‌کشی انجام شد! نتایج به همه گروه‌ها ارسال شد.*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                cbtn("🔙 پنل", callback_data="lot_panel")
            ]])
        )
        return True

    if data.startswith("lot_join_"):
        lot_id = data[9:]
        lot = get_lottery(lot_id)
        if not lot or lot['state'] != 'open':
            await query.answer("❌ این قرعه‌کشی دیگه باز نیست!", show_alert=True); return True
        if get_lottery_entry(lot_id, user.id):
            await query.answer("✅ قبلاً ثبت‌نام کردی!", show_alert=True); return True
        ensure_user(user.id, user.username or "", user.first_name)
        with db_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO lottery_entries (lottery_id,user_id,username,first_name) VALUES (?,?,?,?)",
                (lot_id, user.id, user.username or "", user.first_name)
            )
            conn.commit()
        entries = get_lottery_entries(lot_id)
        lot = get_lottery(lot_id)
        await query.answer(f"✅ ثبت‌نام شدی! ({len(entries)} نفر تا الان)")
        new_text = lottery_announce_text(lot, entries)
        kb = InlineKeyboardMarkup([[
            cbtn(f"✋ شرکت در قرعه‌کشی ({len(entries)} نفر)", callback_data=f"lot_join_{lot_id}")
        ]])
        try:
            await query.edit_message_text(new_text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass
        return True

    return False

async def lottery_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    lot_state = context.user_data.get("lot_create")
    if not lot_state:
        return False
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return False
    text = update.message.text.strip()

    if lot_state["step"] == "title":
        context.user_data["lot_create"]["title"] = text
        context.user_data["lot_create"]["step"] = "prize"
        await update.message.reply_text(
            f"✅ اسم: *{text}*\n\n💰 حالا مبلغ جایزه رو بنویس (عدد، هاپ پوینت):",
            parse_mode="Markdown"
        )
        return True

    if lot_state["step"] == "prize":
        try:
            prize = int(text.replace(",", ""))
            if prize <= 0: raise ValueError
        except ValueError:
            await update.message.reply_text("❌ عدد معتبر وارد کن!")
            return True
        context.user_data["lot_create"]["prize"] = prize
        context.user_data["lot_create"]["step"] = "winner_count"
        await update.message.reply_text(
            f"✅ جایزه: *{prize:,}* هاپ پوینت\n\n🏆 چند نفر برنده بشن؟ (عدد بنویس):",
            parse_mode="Markdown"
        )
        return True

    if lot_state["step"] == "winner_count":
        try:
            wc = int(text)
            if wc <= 0: raise ValueError
        except ValueError:
            await update.message.reply_text("❌ عدد معتبر وارد کن!")
            return True
        lot_state["winner_count"] = wc
        context.user_data.pop("lot_create", None)

        title = lot_state["title"]
        prize = lot_state["prize"]
        lot_id = lottery_id_gen()

        with db_conn() as conn:
            conn.execute(
                "INSERT INTO lotteries (lottery_id,title,prize,winner_count,state,created_by) VALUES (?,?,?,?,?,?)",
                (lot_id, title, prize, wc, 'open', user.id)
            )
            conn.commit()

        lot = get_lottery(lot_id)
        entries = []
        announce_text = lottery_announce_text(lot, entries)
        kb = InlineKeyboardMarkup([[
            cbtn("✋ شرکت در قرعه‌کشی (0 نفر)", callback_data=f"lot_join_{lot_id}")
        ]])
        with db_conn() as conn:
            groups = conn.execute("SELECT group_id FROM groups").fetchall()
        sent_count = 0
        for g in groups:
            try:
                await context.bot.send_message(
                    chat_id=g['group_id'],
                    text=announce_text,
                    parse_mode="Markdown",
                    reply_markup=kb
                )
                sent_count += 1
            except Exception:
                pass

        await update.message.reply_text(
            f"🎉 *قرعه‌کشی ساخته شد!*\n\n"
            f"🎰 اسم: {title}\n"
            f"🎁 جایزه: {prize:,} هاپ پوینت\n"
            f"🏆 تعداد برنده: {wc} نفر\n"
            f"📢 ارسال به {sent_count} گروه\n\n"
            f"کد قرعه‌کشی: `{lot_id}`",
            parse_mode="Markdown"
        )
        return True

    return False

async def callback_handler_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user
    def check_owner(uid):
        return user.id == uid
    if data.startswith("clan_"):
        if await clan_callback(update, context): return
    if data.startswith("barter_"):
        if await barter_callback(update, context): return
    if data.startswith("trade_"):
        if await trade_callback(update, context): return
    if data.startswith("auction_"):
        if await auction_callback(update, context): return
    if data.startswith("ref_"):
        if await handle_referral_callbacks(query, data, user, context): return
    if data.startswith("mkt_"):
        if await handle_market_callbacks(query, data, user, context): return
    if data.startswith("factory_"):
        await factory_callback_handler(update, context)
        return
    if data.startswith("lot_"):
        await lottery_callback_handler(update, context)
        return
    if data.startswith(("cityadv_", "mayor_", "melec_")):
        if data.startswith("cityadv_") and await city_adv_callback(update, context): return
        if await mayor_callback(update, context): return
        return
    if data.startswith("mproj_"):
        if await mayor_projects_callback(update, context): return
        return
    if data.startswith("crisis_"):
        query = update.callback_query
        user = query.from_user
        if await handle_crisis_callback(query, data, user, context): return
        return
    if data.startswith("adm_reset_"):
        if not is_admin(user.id):
            await query.answer("فقط ادمین اصلی!", show_alert=True)
            return

        if data == "adm_reset_by_balance":
            await query.answer()
            context.user_data["admin_reset_step"] = "awaiting_threshold"
            await show_reset_balance_input(query)
            return

        if data == "adm_reset_set_exclude":
            await query.answer()
            context.user_data["admin_reset_step"] = "awaiting_exclude_nums"
            rows = context.bot_data.get("reset_rows", [])
            excluded = context.bot_data.get("reset_excluded_ids", set())
            ex_nums = [str(i+1) for i, r in enumerate(rows) if r[0] in excluded]
            current = f"استثناهای فعلی: `{', '.join(ex_nums)}`\n\n" if ex_nums else ""
            await query.edit_message_text(
                f"🚫 *استثنا کردن کاربر*\n\n"
                f"{current}"
                "شماره‌های کاربرانی که نباید ریست بشن رو بفرست.\n"
                "مثال: `3,7,12` یا `5` یا `همه` برای پاک کردن استثناها\n\n"
                "✏️ بنویس:",
                parse_mode="Markdown"
            )
            return

        if data == "adm_reset_confirm":
            await query.answer()
            threshold = context.bot_data.get("pending_reset_threshold", 0)
            excluded  = context.bot_data.get("reset_excluded_ids", set())
            excl_count = len(excluded)
            context.user_data["admin_reset_step"] = "awaiting_init_points"
            await query.edit_message_text(
                f"✅ تأیید شد — آستانه: `{threshold:,}`\n"
                f"🚫 استثناها: `{excl_count}` کاربر\n\n"
                "حالا *موجودی اولیه* که به همه داده بشه رو بفرست (مثلاً `0` یا `1000`):",
                parse_mode="Markdown"
            )
            return

        if data == "adm_reset_cancel":
            await query.answer()
            context.bot_data.pop("pending_reset_threshold", None)
            context.bot_data.pop("reset_excluded_ids", None)
            context.user_data.pop("admin_reset_step", None)
            context.user_data.pop("reset_init_points", None)
            await query.edit_message_text("❌ ریست لغو شد.")
            return

    if data.startswith("mystery_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid):
            await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        await query.answer()
        await query.edit_message_text("🎁 *جعبه مرموز*\n\nانتخاب کن کدوم جعبه رو باز کنی:", parse_mode="Markdown", reply_markup=mystery_box_buttons(uid))
        return

    if data.startswith("collection_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid):
            await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        await query.answer()
        await query.edit_message_text(collection_text(uid), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[cbtn("🎁 جوایز کالکشن", f"collectionrewards_{uid}"), cbtn("🎁 جعبه مرموز", f"mystery_{uid}")]]))
        return

    if data.startswith("box_"):
        parts = data.split("_")
        box_key, uid = parts[1], int(parts[2])
        if not check_owner(uid):
            await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        box = MYSTERY_BOXES.get(box_key)
        if not box:
            await query.answer("جعبه نامعتبره!", show_alert=True); return
        with db_conn() as conn:
            u = conn.execute("SELECT hop_points FROM users WHERE user_id=?", (uid,)).fetchone()
            if not u or u["hop_points"] < box["cost"]:
                await query.answer(f"هاپ کافی نداری! لازم: {box['cost']:,}", show_alert=True); return
            conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=?", (box["cost"], uid))
            rarity = weighted_rarity(box["weights"])
            reward_type, reward_key = reward_for_rarity(rarity)
            conn.execute("INSERT INTO mystery_opens(user_id,box_key,reward_key,reward_type) VALUES(?,?,?,?)", (uid, box_key, reward_key, reward_type))
            conn.commit()
        if reward_type == "item":
            add_inventory_item(uid, reward_key, 1)
            reward_name = RARE_ITEMS[reward_key]["name"]
            add_collection(uid, "item:" + reward_key)
        else:
            dog_cfg = DOG_TYPES[reward_key]
            with db_conn() as _c:
                existing = _c.execute("SELECT 1 FROM dogs WHERE user_id=?", (uid,)).fetchone()
                if not existing:
                    _c.execute("INSERT INTO dogs (user_id,name,level,rank,points_box,last_collect,dog_type) VALUES (?, ?,1,1,0,?,?)",
                               (uid, dog_cfg["name"].split(" ",1)[-1], datetime.now().isoformat(), reward_key))
                    try:
                        _c.execute("UPDATE groups SET total_dogs=total_dogs+1 WHERE group_id=?", (query.message.chat_id,))
                    except Exception:
                        pass
                    _c.commit()
                    reward_name = dog_cfg["name"] + " 🎉"
                    add_collection(uid, "dog:" + reward_key)
                else:
                    # A player can own one active dog; duplicate Mythic rewards become essence.
                    add_inventory_item(uid, "mythic_essence", 1)
                    reward_type = "item"
                    reward_key = "mythic_essence"
                    reward_name = RARE_ITEMS[reward_key]["name"] + " (سگ تکراری)"
        await query.answer("🎉 جایزه پیدا شد!", show_alert=True)
        await query.edit_message_text(f"🎁 *جعبه باز شد!*\n\n✨ Rare: *{rarity}*\n🏆 جایزه: *{reward_name}*\n\n🏆 با «کالکشن» مجموعه‌ات رو ببین.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[cbtn("🏆 کالکشن", f"collection_{uid}"), cbtn("🎁 جعبه بعدی", f"mystery_{uid}")]]))
        return

    if data.startswith("inventory_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid):
            await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        with db_conn() as conn:
            rows = conn.execute("SELECT item_key,quantity FROM inventory WHERE user_id=? AND quantity>0 ORDER BY item_key", (uid,)).fetchall()
        kb = []
        for r in rows:
            item = RARE_ITEMS.get(r["item_key"])
            if item and item["use"] != "collectible":
                kb.append([cbtn(f"استفاده: {item['name']} × {r['quantity']}", callback_data=f"invuse_{r['item_key']}_{uid}")])
        kb.append([cbtn("🐕 بازگشت به سگ", callback_data=f"dogback_{uid}")])
        await query.answer()
        await query.edit_message_text(inventory_text(uid), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("invuse_"):
        parts = data.split("_")
        item_key = parts[1]
        uid = int(parts[2])
        if not check_owner(uid):
            await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        item = RARE_ITEMS.get(item_key)
        if not item or item["use"] == "collectible":
            await query.answer("این آیتم قابل استفاده نیست.", show_alert=True); return
        if item["use"] == "dog":
            with db_conn() as conn:
                if not conn.execute("SELECT 1 FROM dogs WHERE user_id=?", (uid,)).fetchone():
                    await query.answer("اول باید سگ داشته باشی!", show_alert=True); return
        if item["use"] == "factory":
            with db_conn() as conn:
                if not conn.execute("SELECT 1 FROM factories WHERE user_id=?", (uid,)).fetchone():
                    await query.answer("اول باید کارخانه داشته باشی!", show_alert=True); return
        if not remove_inventory_item(uid, item_key, 1):
            await query.answer("این آیتم رو نداری!", show_alert=True); return
        until = datetime.now() + timedelta(seconds=item["duration"])
        with db_conn() as conn:
            if item["use"] == "dog":
                conn.execute("UPDATE dogs SET boost_until=?,boost_mult=? WHERE user_id=?", (until.isoformat(), item["mult"], uid))
            elif item["use"] == "luck":
                conn.execute("UPDATE users SET fish_luck_until=?,fish_luck_mult=? WHERE user_id=?", (until.isoformat(), item["mult"], uid))
            elif item["use"] == "hop":
                conn.execute("UPDATE users SET hop_boost_until=?,hop_boost_mult=? WHERE user_id=?", (until.isoformat(), item["mult"], uid))
            elif item["use"] == "factory":
                conn.execute("UPDATE factories SET boost_until=?,boost_mult=? WHERE user_id=?", (until.isoformat(), item["mult"], uid))
            conn.commit()
        await query.answer("✨ آیتم فعال شد!")
        await query.edit_message_text(f"✨ *{item['name']} فعال شد!*\n\n{item['desc']}\n\n⏱️ تا {until.strftime('%H:%M')} فعال است.", parse_mode="Markdown")
        return

    if data.startswith("dogback_"):
        uid = int(data.split("_")[1])
        if not check_owner(uid):
            await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        conn_tmp = get_db()
        u = conn_tmp.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        dog = conn_tmp.execute("SELECT * FROM dogs WHERE user_id=?", (uid,)).fetchone()
        conn_tmp.close()
        if dog:
            await query.answer(); await dog_cmd_for_user(query, uid)
        else:
            await query.answer("سگی نداری!", show_alert=True)
        return

    if data.startswith("buydog_"):
        parts = data.split("_")
        if len(parts) == 2:
            uid = int(parts[1]); dog_type_key = "stray"
        else:
            dog_type_key = parts[1]; uid = int(parts[2])
        if not check_owner(uid):
            await query.answer("این دکمه برای تو نیست!", show_alert=True); return
        dog_type = DOG_TYPES.get(dog_type_key)
        if not dog_type:
            await query.answer("نوع سگ نامعتبره!", show_alert=True); return
        if dog_type.get("obtain") == "cosmic":
            await query.answer("🔒 این سگ Mythic فقط از جعبه کیهانی یا رویداد ویژه به دست میاد!", show_alert=True); return
        with db_conn() as conn:
            u = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
            dog = conn.execute("SELECT 1 FROM dogs WHERE user_id=?", (uid,)).fetchone()
            if dog:
                await query.answer("تو از قبل سگ داری!", show_alert=True); return
            if u["level"] < DOG_MIN_LEVEL:
                await query.answer(f"سطح {DOG_MIN_LEVEL} لازمه!", show_alert=True); return
            if u["hop_points"] < dog_type["cost"]:
                await query.answer(f"پوینت کافی نداری! لازم: {dog_type['cost']:,}", show_alert=True); return
            cur=conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?", (dog_type["cost"], uid, dog_type["cost"]))
            if cur.rowcount != 1:
                conn.rollback(); await query.answer("موجودی همزمان تغییر کرد؛ دوباره تلاش کن.", show_alert=True); return
            try:
                conn.execute("INSERT INTO dogs (user_id,name,level,rank,points_box,last_collect,dog_type) VALUES (?, 'سگولو',1,1,0,?,?)",
                             (uid, datetime.now().isoformat(), dog_type_key))
            except sqlite3.IntegrityError:
                conn.rollback(); await query.answer("تو از قبل سگ داری!", show_alert=True); return
            conn.execute("INSERT INTO collection(user_id,collection_key,count) VALUES(?,?,1) ON CONFLICT(user_id,collection_key) DO UPDATE SET count=count+1", (uid, 'dog:'+dog_type_key))
            chat_id = query.message.chat_id
            conn.execute("UPDATE groups SET total_dogs=total_dogs+1 WHERE group_id=?", (chat_id,))
            conn.commit()
        await query.answer("🐕 سگ خریداری شد!")
        await query.edit_message_text(f"🎉 *سگ جدیدت آماده‌ست!*\n\n{dog_type['name']}\n✨ {dog_type['ability']}\n💰 هزینه: {dog_type['cost']:,} هاپ\n\n📌 بنویس «سگ» تا پنلش رو ببینی.", parse_mode="Markdown")
        return

    if await new_callback_handler(update, context): return
    if await casino_callback_handler(update, context): return
    if await handle_leader_callback(query, user, data, context): return
    await callback_handler(update, context)

async def contraband_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user_id = update.effective_user.id
    
    user = get_user(user_id)
    if not user or user["level"] < 4:
        await message.reply_text("❌ داداش برای ورود به دنیای سیاه و پرخطر قاچاق، باید حداقل به *سطح ۴* رسیده باشی! 🥷", parse_mode="Markdown")
        return
        
    jailed, jail_row = is_in_jail(user_id)
    if jailed:
        rel = datetime.fromisoformat(jail_row["release_at"])
        left = int((rel - datetime.now()).total_seconds())
        m, s = divmod(left, 60)
        await message.reply_text(f"⛓️ تو خودت الان زندانی هستی! نمی‌تونی باند قاچاق راه بندازی!\n⌛️ {m} دقیقه و {s} ثانیه تا آزادی")
        return
        
    conn = get_db()
    row = conn.execute("SELECT count FROM user_strays WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    stray_count = row["count"] if row else 0
    if stray_count < 3:
        await message.reply_text("❌ برای راهی کردن محموله، باید حداقل *۳ تا سگ خیابانی* نجات داده باشی! 🐕", parse_mode="Markdown")
        return
        
    max_smuggle = min(stray_count, 15)
    keyboard = []
    row_buttons = []
    for count in range(3, max_smuggle + 1):
        row_buttons.append(cbtn(f"🐕 {count} سگ", callback_data=f"smuggle_{count}_{user_id}"))
        if len(row_buttons) == 2:
            keyboard.append(row_buttons)
            row_buttons = []
    if row_buttons:
        keyboard.append(row_buttons)
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(
        "🥷 *به بخش قاچاق زیرزمینی هاپویی خوش آمدی!*\n\n"
        f"انتخاب کن چند تا از سگ‌های خیابانیت (موجودی شما: {stray_count}) رو می‌خوای قاچاق کنی؟\n"
        "⚠️ _هر چی تعداد بالاتر بره، شانس لو رفتن و رفتن به انفرادی بیشتر میشه!_",
        reply_markup=reply_markup, parse_mode="Markdown"
    )


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await hapoha_profile(update, context)

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    rows = conn.execute(
        "SELECT first_name, hop_points, level FROM users ORDER BY hop_points DESC LIMIT 10"
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("هنوز کسی هاپو نزده!")
        return
    text = "🏆 *برترین هاپوها* 🐾\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {r['first_name']} — {r['hop_points']:,.0f} 🦴 | سطح {r['level']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "╮──「 🐾 راهنمای هاپو 🐾 」\n\n"
        "┐─ 🐾 *هاپ* — جمع پوینت (کولداون ۵ دقیقه)\n"
        "┐─ 🐕 *سگ* — خرید و مدیریت سگ\n"
        "┐─ 🎣 *قلاب* — خرید قلاب ماهیگیری\n"
        "┐─ 🦴 *استخوان* — صید استخوان\n"
        "┐─ 🏦 *بانک* — مدیریت حساب بانکی\n"
        "┐─ 🏭 *کارخونه* — مدیریت کارخونه\n"
        "┐─ 🛍 *بازار* — قیمت‌های بازار\n"
        "┐─ 🏰 *شهر* — وضعیت شهر گروه\n"
        "┐─ 🎲 *بازی* — منوی بازی‌ها\n"
        "┐─ 💳 *انتقال [عدد] @یوزر* — انتقال پوینت\n"
        "┐─ 🎯 *ماموریت* — مأموریت روزانه و XP\n"
        "┐─ 🤝 *معامله* — معامله آیتم با بازیکن (ریپلای)\n"
        "┐─ 🏪 *حراج* — مشاهده و ثبت آگهی در حراج‌خانه\n"
        "┐─ 🐾 *هاپوهام* — پروفایل خودت\n"
        "└─ 🐾 *هاپ هاش* — پروفایل نفر ریپلای‌شده\n\n"
        "پروفایل — پروفایل\n"
        "برترین — لیدربرد"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def handle_group_text_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_meow_logic(update, context): return
    if not update.message or not update.message.text:
        return

    _u = update.effective_user
    _chat = update.effective_chat
    text = update.message.text.strip().replace("\u200c", " ").replace("\u200b", "").strip()
    if await handle_rename(update, context): return
    if await handle_mayor_protest_input(update, context): return
    if await handle_mayor_project_input(update, context): return
    if await handle_bank_input(update, context): return
    if await handle_dice_input(update, context): return
    if await handle_gamble_input(update, context): return
    if await handle_casino_text_input(update, context): return
    if await lottery_text_handler(update, context): return
    if await handle_leader_text_input(update, context): return

    admin_triggers = ["افزایش لول", "کاهش لول", "افزایش پوینت", "کاهش پوینت"]
    if any(text.startswith(t) for t in admin_triggers):
        await admin_cmd(update, context); return

    if text == "افزودن ادمین": await add_admin_cmd(update, context); return
    if text == "حذف ادمین": await remove_admin_cmd(update, context); return
    if text == "حذف کاربر": await delete_user_cmd(update, context); return

    JAIL_BLOCKED_CMDS = ["هاپ", "هاپو", "hop", "سگ", "dog", "Dog",
                         "قلاب", "hook", "Hook", "استخوان", "bone", "Bone",
                         "بانک", "bank", "قاچاق", "کازینو", "casino",
                         "تاس", "گردونه", "قمار"]
    if text in JAIL_BLOCKED_CMDS and update.effective_user.id not in ADMIN_IDS:
        _jailed2, _jail_row2 = is_in_jail(update.effective_user.id)
        if _jailed2:
            _rel2 = datetime.fromisoformat(_jail_row2["release_at"])
            _left2 = max(0, int((_rel2 - datetime.now()).total_seconds()))
            _m2, _s2 = divmod(_left2, 60)
            await update.message.reply_text(
                f"⛓️ تو زندانی هستی! نمی‌تونی این کار رو بکنی.\n"
                f"⌛️ {_m2} دقیقه و {_s2} ثانیه تا آزادی\n"
                f"بنویس *زندان* برای گزینه‌های آزادی.",
                parse_mode="Markdown"
            )
            return

    if text in ["هاپ", "هاپو", "hop"]: await handle_hop(update, context)
    elif text in ["کیف", "inventory", "Inventory"]: await inventory_cmd(update, context)
    elif text in ["جعبه", "جعبه مرموز", "mystery"]: await mystery_cmd(update, context)
    elif text in ["کالکشن", "کالکسیون", "مجموعه", "collection"]: await collection_cmd(update, context)
    elif text in ["جوایز کالکشن", "جوایز مجموعه", "collection rewards"]: await collection_rewards_cmd(update, context)
    elif text in ["رویداد", "ایونت", "event", "events", "🎪 رویداد"]: await seasonal_event_cmd(update, context)
    elif text in ["معامله", "trade"] or text.startswith("معامله "): await trade_cmd(update, context)
    elif text in ["مبادله", "barter"] or text.startswith("مبادله "): await barter_cmd(update, context)
    elif text in ["پیشنهاد", "bid"] or text.startswith("پیشنهاد "): await auction_bid_cmd(update, context)
    elif text in ["حراج", "حراجخانه", "حراج‌خانه", "auction"] or text.startswith("حراج "): await auction_cmd(update, context)
    elif text in ["انواع سگ", "سگ‌ها", "سگ ها", "dog types"]: await dog_types_cmd(update, context)
    elif text in ["سگ", "dog", "Dog"]: await dog_cmd(update, context)
    elif text in ["قلاب", "hook", "Hook"]: await hook_cmd(update, context)
    elif text in ["استخوان", "bone", "Bone"]: await cast_cmd(update, context)
    elif text in ["بانک", "bank"]: await bank_cmd(update, context)
    elif text in ["زندان", "jail"]: await jail_cmd(update, context)
    elif text in ["بازی", "games"]: await games_menu(update, context)
    elif text == "قاچاق": await contraband_cmd(update, context)
    elif text in ["کازینو", "casino"]:
        u = get_user(update.effective_user.id)
        if u and u["level"] >= CASINO_MIN_LEVEL:
            await casino_menu_show(update, update.effective_user, u)
        else:
            await update.message.reply_text(f"🔒 سطح {CASINO_MIN_LEVEL} لازمه!")
    elif text in ["تاس"]: await dice_cmd(update, context)
    elif text in ["گردونه"]: await wheel_cmd(update, context)
    elif text in ["قمار"]: await gamble_cmd(update, context)
    elif text == "شهر" or text == "city" or text.startswith("شهر "): await city_adv_cmd(update, context)
    elif text.startswith("اهدا"): await donate_cmd(update, context)
    elif text.startswith("انتقال"): await transfer_cmd(update, context)
    elif text in ["هاپوهام", "هاپو هام", "هاپ هام", "هاپ‌هام", "هاپوهام", "هاپوهامم", "هاپو‌هام", "hapoham"]: await hapoha_profile(update, context)
    elif text in ["هاپ هاش", "هاپ‌هاش", "هاپو هاش", "هاپوهاش", "هاپو‌هاش", "hapohash"]: await hapoha_profile_other(update, context)
    elif text in ["کارخونه", "factory"]: await factory_cmd(update, context)
    elif text in ["مارکت", "market"]: await market_cmd(update, context)
    elif text in ["پنل", "قرعه کشی", "قرعه‌کشی"]: await lottery_panel_cmd(update, context)
    elif text in ["شهرداری", "شهردار"]: await mayor_cmd(update, context)
    elif text in ["بحران", "وضعیت بحران", "crisis"]: await crisis_status_cmd(update, context)
    elif text in ["رهبر", "رهبری", "leader"]: await leader_panel_cmd(update, context)
    elif text in ["نامزد رهبر", "نامزد رهبری"]: await leaderjoin_cmd(update, context)
    elif text in ["رای رهبر", "رأی رهبر", "vote رهبر"]: await leadervote_cmd(update, context)
    elif text in ["برترین", "لیدربرد", "top", "Top"]: await top_cmd(update, context)
    elif text in ["ماموریت", "مأموریت", "ماموریت‌ها", "مأموریت‌ها", "mission", "missions"]: await missions_cmd(update, context)


async def show_reset_panel(message):
    kb = InlineKeyboardMarkup([
        [cbtn("🔴 ریست کاربران بر اساس موجودی", callback_data="adm_reset_by_balance")],
        [cbtn("❌ بستن پنل", callback_data="cancel")],
    ])
    await message.reply_text(
        "🔴 *پنل ریست ادمین اصلی*\n\n"
        "⚠️ این عملیات برگشت‌پذیر نیست!\n"
        "موجودی، قلاب، سگ، بانک، کارخانه و لول ریست می‌شن.\n"
        "جدول کاربران پاک *نمی‌شه*.",
        parse_mode="Markdown",
        reply_markup=kb
    )

async def show_reset_balance_input(query):
    await query.edit_message_text(
        "🔴 *ریست بر اساس موجودی*\n\n"
        "عدد مرز رو بفرست — هر کاربری که موجودی‌اش *بیشتر یا مساوی* این عدد باشه ریست می‌شه.\n\n"
        "مثال: `5000000000` (۵ میلیارد)\n\n"
        "✏️ عدد رو بنویس:",
        parse_mode="Markdown"
    )


def _build_reset_table_msg(context) -> tuple:
    threshold = context.bot_data.get("pending_reset_threshold", 0)
    excluded  = context.bot_data.get("reset_excluded_ids", set())
    rows = context.bot_data.get("reset_rows", [])

    will_reset = [r for r in rows if r[0] not in excluded]

    lines = [
        f"🔴 *لیست ریست*\n"
        f"آستانه: `{threshold:,}`\n"
        f"✅ ریست می‌شن: *{len(will_reset)}* | 🚫 استثنا: *{len(excluded)}*\n"
    ]
    for i, (uid, fname, uname, pts, lvl) in enumerate(rows, 1):
        status = "🚫" if uid in excluded else "🔴"
        uname_str = f"@{uname}" if uname else f"#{uid}"
        lines.append(f"{status} `{i}.` {fname} ({uname_str}) — {int(pts):,} | لول {lvl}")

    lines.append("\n📌 برای استثنا کردن، شماره‌ها رو بفرست (مثلاً `3,7,12`)")

    kb = InlineKeyboardMarkup([
        [cbtn("🚫 استثنا کردن", callback_data="adm_reset_set_exclude")],
        [cbtn(f"✅ تأیید ریست {len(will_reset)} کاربر", callback_data="adm_reset_confirm")],
        [cbtn("❌ لغو", callback_data="adm_reset_cancel")],
    ])
    return "\n".join(lines), kb


async def show_reset_confirm_table(message, threshold: int, context):
    context.bot_data["pending_reset_threshold"] = threshold
    context.bot_data["reset_excluded_ids"] = set()

    with db_conn() as conn:
        rows = conn.execute(
            "SELECT user_id, first_name, username, hop_points, level FROM users "
            "WHERE hop_points >= ? ORDER BY hop_points DESC",
            (threshold,)
        ).fetchall()

    if not rows:
        await message.reply_text(f"✅ هیچ کاربری بالای {threshold:,} موجودی نداره.")
        return

    context.bot_data["reset_rows"] = [
        (r["user_id"], r["first_name"], r["username"] or "", r["hop_points"], r["level"])
        for r in rows
    ]

    text, kb = _build_reset_table_msg(context)
    await message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def do_reset_users(threshold: int, init_points: int, init_level: int, excluded: set) -> int:
    with db_conn() as conn:
        targets = conn.execute(
            "SELECT user_id FROM users WHERE hop_points >= ?", (threshold,)
        ).fetchall()
        ids = [r["user_id"] for r in targets if r["user_id"] not in excluded]
        if not ids:
            return 0

        placeholders = ",".join("?" * len(ids))

        conn.execute(
            f"UPDATE users SET hop_points=?, total_hops=0, level=?, last_hop=NULL WHERE user_id IN ({placeholders})",
            [init_points, init_level] + ids
        )
        conn.execute(f"DELETE FROM hooks WHERE user_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM dogs WHERE user_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM pending_bones WHERE user_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM bank WHERE user_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM transfers WHERE user_id IN ({placeholders})", ids)
        conn.execute(
            f"UPDATE factories SET stock=0, exp=0, level=1, producing=0, "
            f"production_end=NULL, machine_level=1, warehouse_level=1, last_produced=NULL "
            f"WHERE user_id IN ({placeholders})", ids
        )
        conn.execute(f"DELETE FROM jail WHERE user_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM user_strays WHERE user_id IN ({placeholders})", ids)
        conn.commit()
    return len(ids)

async def handle_reset_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not is_admin(user.id):
        return False

    step = context.user_data.get("admin_reset_step")
    if not step:
        return False

    text = update.message.text.strip().replace(",", "").replace("_", "").replace(" ", "")

    if step == "awaiting_exclude_nums":
        context.user_data.pop("admin_reset_step", None)
        rows = context.bot_data.get("reset_rows", [])
        if text.strip() in ["همه", "all", "0"]:
            context.bot_data["reset_excluded_ids"] = set()
            await update.message.reply_text("✅ همه استثناها پاک شدن.")
        else:
            nums = []
            for part in text.replace("،", ",").split(","):
                part = part.strip()
                if part.isdigit():
                    nums.append(int(part))
            valid = [n for n in nums if 1 <= n <= len(rows)]
            if not valid:
                await update.message.reply_text("❌ شماره معتبری پیدا نشد، دوباره امتحان کن.")
                context.user_data["admin_reset_step"] = "awaiting_exclude_nums"
                return True
            excluded = set()
            for n in valid:
                excluded.add(rows[n - 1][0])
            context.bot_data["reset_excluded_ids"] = excluded
            names = ", ".join(rows[n-1][1] for n in valid)
            await update.message.reply_text(f"🚫 استثنا شدن: {names}")
        text_tbl, kb = _build_reset_table_msg(context)
        await update.message.reply_text(text_tbl, parse_mode="Markdown", reply_markup=kb)
        return True

    if step == "awaiting_threshold":
        try:
            threshold = int(float(text))
        except ValueError:
            await update.message.reply_text("❌ عدد معتبر وارد کن!")
            return True
        if threshold <= 0:
            await update.message.reply_text("❌ عدد باید مثبت باشه!")
            return True
        context.user_data.pop("admin_reset_step", None)
        await show_reset_confirm_table(update.message, threshold, context)
        return True

    if step == "awaiting_init_points":
        try:
            init_points = int(float(text))
        except ValueError:
            await update.message.reply_text("❌ عدد معتبر وارد کن!")
            return True
        context.user_data["reset_init_points"] = init_points
        context.user_data["admin_reset_step"] = "awaiting_init_level"
        await update.message.reply_text(
            f"✅ موجودی اولیه: `{init_points:,}`\n\n"
            "حالا *لول اولیه* رو بفرست (مثلاً `1`):",
            parse_mode="Markdown"
        )
        return True

    if step == "awaiting_init_level":
        try:
            init_level = int(text)
        except ValueError:
            await update.message.reply_text("❌ عدد معتبر وارد کن!")
            return True
        if init_level < 1:
            init_level = 1

        init_points = context.user_data.pop("reset_init_points", 0)
        threshold   = context.bot_data.pop("pending_reset_threshold", None)
        excluded    = context.bot_data.pop("reset_excluded_ids", set())
        context.user_data.pop("admin_reset_step", None)

        if threshold is None:
            await update.message.reply_text("❌ خطا: آستانه‌ای ذخیره نشده، دوباره از اول شروع کن.")
            return True

        await update.message.reply_text("⏳ در حال ریست...")
        count = await do_reset_users(threshold, init_points, init_level, excluded)
        await update.message.reply_text(
            f"✅ *ریست کامل شد!*\n\n"
            f"👥 تعداد ریست‌شده: `{count}` کاربر\n"
            f"🚫 استثناها: `{len(excluded)}` کاربر\n"
            f"💰 موجودی اولیه: `{init_points:,}`\n"
            f"⭐️ لول اولیه: `{init_level}`\n"
            f"📊 آستانه: بالای `{threshold:,}`",
            parse_mode="Markdown"
        )
        return True

    return False


async def private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_reset_text_input(update, context): return
    if await handle_bank_input(update, context): return
    if await handle_mayor_project_input(update, context): return
    if await lottery_text_handler(update, context): return
    if await handle_market_private_input(update, context): return
    if await handle_referral_admin_input(update, context): return
    if await handle_leader_text_input(update, context): return
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip().replace("\u200c", " ").replace("\u200b", "").strip()
    user = update.effective_user

    if text in ["ریست", "reset", "🔴 ریست"] and is_admin(user.id):
        await show_reset_panel(update.message); return

    if text in ["مارکت", "market", "🛒 مارکت"]:
        await market_cmd(update, context); return
    if text == "مارکت ادمین" and is_admin(user.id):
        await market_admin_panel(update.message); return
    if text in ["دعوت دوستان", "🎁 دعوت دوستان", "دعوت", "invite"]:
        await referral_invite_cmd(update, context); return
    if text in ["پنل دعوت", "دعوت ادمین"] and is_admin(user.id):
        await referral_admin_panel(update.message); return
    if text in ["هاپوهام", "هاپو هام", "🐾 هاپوهام"]:
        await hapoha_profile(update, context); return
    if text in ["راهنما", "📖 راهنما"]:
        await help_cmd(update, context); return
    if text in ["لیدربرد", "📊 لیدربرد"]:
        await top_cmd(update, context); return
    if text in ["ماموریت", "مأموریت", "ماموریت‌ها", "مأموریت‌ها", "🎯 ماموریت"]:
        await missions_cmd(update, context); return

    await update.message.reply_text(
        "🐾 دستورات اصلی فقط توی گروه کار می‌کنن!\nاز دکمه‌های زیر استفاده کن 👇"
    )


MAYOR_DECREES_DEF = {
    "hop_festival":    {"name": "🎉 جشنواره هاپ",          "desc": "+۳۰٪ پوینت هاپ برای کل گروه",       "effect": "hop_boost",     "value": 0.30},
    "factory_boost":   {"name": "🏭 افزایش تولید کارخانه", "desc": "+۴۰٪ سرعت تولید کارخانه",           "effect": "factory_boost", "value": 0.40},
    "dog_income":      {"name": "🐕 افزایش درآمد سگ‌ها",   "desc": "+۳۵٪ درآمد سگ‌های گروه",            "effect": "dog_boost",     "value": 0.35},
    "tax_cut":         {"name": "💰 کاهش مالیات شهر",      "desc": "اهدای ۵٪ خزانه به همه کاربران",     "effect": "tax_cut",       "value": 0.05},
    "bank_profit":     {"name": "🏦 افزایش سود بانک",      "desc": "+۵۰٪ سود بانکی امروز",               "effect": "bank_boost",    "value": 0.50},
    "daily_prize":     {"name": "🎁 رویداد جایزه روزانه",  "desc": "جایزه تصادفی ۵۰۰-۵۰۰۰ برای هر هاپ", "effect": "daily_prize",   "value": 0},
}

MAYOR_PLEDGES_DEF = {
    "tax_cut":       "کاهش مالیات (اجرای فرمان کاهش مالیات)",
    "build_project": "ساخت پروژه جدید (ساخت حداقل یک پروژه)",
    "bank_boost":    "افزایش سود بانک (اجرای فرمان سود بانک)",
    "hop_festival":  "برگزاری جشنواره (اجرای فرمان جشنواره هاپ)",
    "factory_up":    "افزایش تولید (اجرای فرمان تولید کارخانه)",
}


def init_mayor_full_tables():
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS mayor (
            group_id    INTEGER PRIMARY KEY,
            user_id     INTEGER,
            username    TEXT,
            first_name  TEXT,
            elected_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            term_end    TEXT,
            popularity  INTEGER DEFAULT 100
        )""")
        try:
            conn.execute("ALTER TABLE mayor ADD COLUMN popularity INTEGER DEFAULT 100")
        except Exception:
            pass

        conn.execute("""CREATE TABLE IF NOT EXISTS mayor_decrees (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER,
            user_id     INTEGER,
            decree_type TEXT,
            decree_name TEXT,
            issued_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at  TEXT
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS mayor_pledges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER,
            election_id INTEGER,
            user_id     INTEGER,
            pledge_key  TEXT,
            pledge_text TEXT,
            fulfilled   INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        try:
            conn.execute("ALTER TABLE mayor_pledges ADD COLUMN election_id INTEGER")
        except Exception:
            pass

        conn.execute("""CREATE TABLE IF NOT EXISTS mayor_elections (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER,
            status      TEXT DEFAULT 'candidacy',
            started_by  INTEGER,
            started_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            ended_at    TEXT DEFAULT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS mayor_candidates (
            election_id INTEGER,
            group_id    INTEGER,
            user_id     INTEGER,
            username    TEXT,
            first_name  TEXT,
            pledges     TEXT DEFAULT '',
            joined_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (election_id, user_id)
        )""")
        try:
            conn.execute("ALTER TABLE mayor_candidates ADD COLUMN pledges TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE mayor_candidates ADD COLUMN group_id INTEGER")
        except Exception:
            pass
        conn.execute("UPDATE mayor_candidates SET group_id=(SELECT group_id FROM mayor_elections WHERE mayor_elections.id=mayor_candidates.election_id) WHERE group_id IS NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mayor_candidates_group_election ON mayor_candidates(group_id, election_id)")
        conn.execute("""CREATE TABLE IF NOT EXISTS mayor_election_votes (
            election_id    INTEGER,
            group_id       INTEGER,
            voter_id       INTEGER,
            candidate_id   INTEGER,
            voted_at       TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (election_id, voter_id)
        )""")
        try:
            conn.execute("ALTER TABLE mayor_election_votes ADD COLUMN group_id INTEGER")
        except Exception:
            pass
        conn.execute("UPDATE mayor_election_votes SET group_id=(SELECT group_id FROM mayor_elections WHERE mayor_elections.id=mayor_election_votes.election_id) WHERE group_id IS NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mayor_votes_group_election ON mayor_election_votes(group_id, election_id)")

        conn.execute("""CREATE TABLE IF NOT EXISTS mayor_protests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER,
            user_id     INTEGER,
            username    TEXT,
            first_name  TEXT,
            reason      TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS mayor_protest_votes (
            protest_id  INTEGER,
            user_id     INTEGER,
            vote        TEXT,
            voted_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (protest_id, user_id)
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS mayor_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER,
            user_id     INTEGER,
            action_type TEXT,
            action_desc TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        conn.commit()

def get_mayor(group_id: int):
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM mayor WHERE group_id=?", (group_id,)
        ).fetchone()

def set_mayor(group_id: int, user_id: int, username: str, first_name: str, term_days: int = 7):
    term_end = (datetime.now() + timedelta(days=term_days)).isoformat()
    with db_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO mayor (group_id, user_id, username, first_name, elected_at, term_end, popularity)
               VALUES (?, ?, ?, ?, ?, ?, 100)""",
            (group_id, user_id, username, first_name, datetime.now().isoformat(), term_end)
        )
        conn.commit()

def get_mayor_popularity(group_id: int) -> int:
    with db_conn() as conn:
        row = conn.execute("SELECT popularity FROM mayor WHERE group_id=?", (group_id,)).fetchone()
        return row["popularity"] if row else 0

def change_mayor_popularity(group_id: int, delta: int):
    with db_conn() as conn:
        conn.execute(
            "UPDATE mayor SET popularity=MAX(0,MIN(100,popularity+?)) WHERE group_id=?",
            (delta, group_id)
        )
        conn.commit()

def log_mayor_action(group_id: int, user_id: int, action_type: str, desc: str):
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO mayor_log (group_id, user_id, action_type, action_desc) VALUES (?,?,?,?)",
            (group_id, user_id, action_type, desc)
        )
        conn.commit()

def get_active_decree(group_id: int):
    with db_conn() as conn:
        return conn.execute(
            """SELECT * FROM mayor_decrees WHERE group_id=? AND datetime(replace(expires_at,'T',' ')) > datetime('now')
               ORDER BY id DESC LIMIT 1""",
            (group_id,)
        ).fetchone()

def issue_decree(group_id: int, user_id: int, decree_type: str):
    d = MAYOR_DECREES_DEF[decree_type]
    expires = (datetime.now() + timedelta(hours=24)).isoformat()
    with db_conn() as conn:
        conn.execute(
            """INSERT INTO mayor_decrees (group_id, user_id, decree_type, decree_name, expires_at)
               VALUES (?,?,?,?,?)""",
            (group_id, user_id, decree_type, d["name"], expires)
        )
        conn.commit()

def get_decree_hop_multiplier(group_id: int) -> float:
    d = get_active_decree(group_id)
    if d and d["decree_type"] == "hop_festival":
        return 1.0 + MAYOR_DECREES_DEF["hop_festival"]["value"]
    return 1.0

def get_decree_dog_multiplier(group_id: int) -> float:
    d = get_active_decree(group_id)
    if d and d["decree_type"] == "dog_income":
        return 1.0 + MAYOR_DECREES_DEF["dog_income"]["value"]
    return 1.0

def get_decree_factory_multiplier(group_id: int) -> float:
    d = get_active_decree(group_id)
    if d and d["decree_type"] == "factory_boost":
        return 1.0 + MAYOR_DECREES_DEF["factory_boost"]["value"]
    return 1.0

def get_decree_bank_multiplier(group_id: int) -> float:
    d = get_active_decree(group_id)
    if d and d["decree_type"] == "bank_profit":
        return 1.0 + MAYOR_DECREES_DEF["bank_profit"]["value"]
    return 1.0

def get_decree_daily_prize(group_id: int) -> int:
    d = get_active_decree(group_id)
    if d and d["decree_type"] == "daily_prize":
        return random.randint(500, 5000)
    return 0

def get_active_election(group_id: int):
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM mayor_elections WHERE group_id=? AND status NOT IN ('done','cancelled') ORDER BY id DESC LIMIT 1",
            (group_id,)
        ).fetchone()

def get_active_protest(group_id: int):
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM mayor_protests WHERE group_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
            (group_id,)
        ).fetchone()

def get_mayor_pledges(group_id: int, user_id: int):
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM mayor_pledges WHERE group_id=? AND user_id=?",
            (group_id, user_id)
        ).fetchall()

def check_pledge_fulfilled(group_id: int, user_id: int, pledge_key: str) -> bool:
    with db_conn() as conn:
        row = conn.execute(
            "SELECT fulfilled FROM mayor_pledges WHERE group_id=? AND user_id=? AND pledge_key=?",
            (group_id, user_id, pledge_key)
        ).fetchone()
        return bool(row and row["fulfilled"])

def fulfill_pledge(group_id: int, user_id: int, pledge_key: str):
    with db_conn() as conn:
        conn.execute(
            "UPDATE mayor_pledges SET fulfilled=1 WHERE group_id=? AND user_id=? AND pledge_key=?",
            (group_id, user_id, pledge_key)
        )
        conn.commit()


async def mayor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("🏛 شهرداری فقط توی گروه کار می‌کنه!")
        return
    ensure_user(user.id, user.username or "", user.first_name)
    ensure_group(chat.id, chat.title or "گروه")
    await _send_mayor_panel(update.message, chat.id, user)

async def _send_mayor_panel(message_obj, group_id: int, user):
    mayor = get_mayor(group_id)
    election = get_active_election(group_id)
    decree = get_active_decree(group_id)
    is_mayor = mayor and mayor["user_id"] == user.id
    pop = get_mayor_popularity(group_id) if mayor else 0
    pop_bar = "🟢" * (pop // 20) + "⚪️" * (5 - pop // 20)

    if mayor:
        term = datetime.fromisoformat(mayor["term_end"])
        days_left = max(0, (term - datetime.now()).days)
        mayor_line = f"👑 شهردار: {mayor['first_name']} | محبوبیت: {pop}٪ {pop_bar}\n⏳ {days_left} روز تا پایان دوره"
    else:
        mayor_line = "⚠️ این گروه شهردار ندارد!"

    decree_line = f"📜 فرمان فعال: {decree['decree_name']}" if decree else "📜 فرمانی فعال نیست"

    text = (
        f"🏛 *شهرداری هاپو*\n\n"
        f"{mayor_line}\n"
        f"{decree_line}\n\n"
    )

    kb = []
    if is_mayor:
        kb.append([cbtn("📜 صدور فرمان روزانه", callback_data=f"mayor_decree_{group_id}")])
        kb.append([cbtn("📊 پنل مدیریت شهردار", callback_data=f"mayor_panel_{group_id}")])
    kb.append([cbtn("🗳 انتخابات", callback_data=f"mayor_election_{group_id}")])
    kb.append([cbtn("📋 وضعیت شهرداری", callback_data=f"mayor_status_{group_id}")])
    if mayor and not is_mayor:
        kb.append([cbtn("📢 اعتراض به شهردار", callback_data=f"mayor_protest_{group_id}")])
    kb.append([cbtn("📜 تاریخچه تصمیمات", callback_data=f"mayor_log_{group_id}")])

    await message_obj.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def mayor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data  = query.data
    user  = query.from_user
    await query.answer()

    if data.startswith("mayor_status_"):
        group_id = int(data.split("_")[2])
        mayor = get_mayor(group_id)
        election = get_active_election(group_id)
        decree = get_active_decree(group_id)
        protest = get_active_protest(group_id)
        pop = get_mayor_popularity(group_id) if mayor else 0
        pop_bar = "🟢" * (pop // 20) + "⚪️" * (5 - pop // 20)

        txt = "📊 *وضعیت شهرداری*\n\n"
        if mayor:
            term = datetime.fromisoformat(mayor["term_end"])
            days_left = max(0, (term - datetime.now()).days)
            txt += (f"👑 شهردار: {mayor['first_name']}\n"
                    f"📅 پایان دوره: {term.strftime('%Y-%m-%d')}\n"
                    f"⏳ باقی‌مانده: {days_left} روز\n"
                    f"📊 محبوبیت: {pop}٪ {pop_bar}\n\n")
            pledges = get_mayor_pledges(group_id, mayor["user_id"])
            if pledges:
                txt += "📌 *وعده‌های انتخاباتی:*\n"
                for p in pledges:
                    icon = "✅" if p["fulfilled"] else "⏳"
                    txt += f"{icon} {p['pledge_text']}\n"
                txt += "\n"
        else:
            txt += "⚠️ شهرداری خالیه — انتخابات برگزار نشده!\n\n"

        if decree:
            exp = datetime.fromisoformat(decree["expires_at"])
            h = int((exp - datetime.now()).total_seconds() // 3600)
            txt += f"📜 فرمان فعال: {decree['decree_name']} ({h} ساعت باقی)\n"
        if election:
            txt += f"🗳 انتخابات در جریان: {election['status']}\n"
        if protest:
            with db_conn() as conn:
                yes = conn.execute("SELECT COUNT(*) FROM mayor_protest_votes WHERE protest_id=? AND vote='yes'", (protest["id"],)).fetchone()[0]
                no  = conn.execute("SELECT COUNT(*) FROM mayor_protest_votes WHERE protest_id=? AND vote='no'",  (protest["id"],)).fetchone()[0]
            txt += f"\n📢 اعتراض فعال: {protest['reason'][:40]}\n✅ {yes} | ❌ {no}\n"

        await query.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت", callback_data=f"mayor_back_{group_id}")]]))
        return True

    if data.startswith("mayor_log_"):
        group_id = int(data.split("_")[2])
        with db_conn() as conn:
            logs = conn.execute(
                "SELECT * FROM mayor_log WHERE group_id=? ORDER BY id DESC LIMIT 15",
                (group_id,)
            ).fetchall()
        txt = "📜 *تاریخچه تصمیمات شهرداری*\n\n"
        if not logs:
            txt += "هنوز هیچ رویدادی ثبت نشده."
        for lg in logs:
            dt = lg["created_at"][:16]
            txt += f"• [{dt}] {lg['action_desc']}\n"
        await query.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت", callback_data=f"mayor_back_{group_id}")]]))
        return True

    if data.startswith("mayor_back_"):
        group_id = int(data.split("_")[2])
        await _edit_mayor_panel(query, group_id, user)
        return True

    if data.startswith("mayor_decree_"):
        group_id = int(data.split("_")[2])
        mayor = get_mayor(group_id)
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار می‌تونه فرمان بده!", show_alert=True); return True
        existing = get_active_decree(group_id)
        if existing:
            exp = datetime.fromisoformat(existing["expires_at"])
            h = int((exp - datetime.now()).total_seconds() // 3600)
            await query.answer(f"❌ فرمان فعال داری! {h} ساعت دیگه منقضی میشه.", show_alert=True); return True
        kb = []
        for key, d in MAYOR_DECREES_DEF.items():
            kb.append([cbtn(f"{d['name']}", callback_data=f"mayor_issue_{group_id}_{key}")])
        kb.append([cbtn("❌ انصراف", callback_data=f"mayor_back_{group_id}")])
        await query.edit_message_text(
            "📜 *صدور فرمان روزانه*\n\nهر ۲۴ ساعت فقط یک فرمان می‌تونی صادر کنی:\n",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return True

    if data.startswith("mayor_issue_"):
        parts = data.split("_")
        group_id = int(parts[2])
        decree_key = "_".join(parts[3:])
        mayor = get_mayor(group_id)
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار!", show_alert=True); return True
        if get_active_decree(group_id):
            await query.answer("❌ فرمان فعال داری!", show_alert=True); return True
        if decree_key not in MAYOR_DECREES_DEF:
            await query.answer("❌ فرمان نامعتبر!", show_alert=True); return True

        d = MAYOR_DECREES_DEF[decree_key]
        issue_decree(group_id, user.id, decree_key)

        if decree_key == "tax_cut":
            with db_conn() as conn:
                grp = conn.execute("SELECT * FROM groups WHERE group_id=?", (group_id,)).fetchone()
                if grp and grp["treasury"] > 0:
                    pool = int(grp["treasury"] * MAYOR_DECREES_DEF["tax_cut"]["value"])
                    users_in_grp = conn.execute(
                        "SELECT u.user_id FROM users u "
                        "JOIN city_residents cr ON cr.user_id=u.user_id "
                        "WHERE cr.group_id=? ORDER BY u.total_hops DESC LIMIT 50", (group_id,)
                    ).fetchall()
                    if users_in_grp:
                        share = pool // len(users_in_grp)
                        if share > 0:
                            for ur in users_in_grp:
                                conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?",
                                             (share, ur["user_id"]))
                            conn.execute("UPDATE groups SET treasury=treasury-? WHERE group_id=?",
                                         (share * len(users_in_grp), group_id))
                    conn.commit()

        log_mayor_action(group_id, user.id, "decree", f"فرمان صادر شد: {d['name']}")

        pledge_map = {
            "tax_cut": "tax_cut",
            "bank_profit": "bank_boost",
            "hop_festival": "hop_festival",
            "factory_boost": "factory_up",
        }
        if decree_key in pledge_map:
            fulfill_pledge(group_id, user.id, pledge_map[decree_key])
            change_mayor_popularity(group_id, +5)

        try:
            await query.bot.send_message(
                group_id,
                f"📣 *فرمان شهردار صادر شد!*\n\n{d['name']}\n📋 {d['desc']}\n\n⏳ ۲۴ ساعت فعال است!",
                parse_mode="Markdown"
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"✅ *فرمان صادر شد!*\n\n{d['name']}\n{d['desc']}\n\n⏳ ۲۴ ساعت فعاله!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 پنل شهرداری", callback_data=f"mayor_back_{group_id}")]]))
        return True

    if data.startswith("mayor_panel_"):
        group_id = int(data.split("_")[2])
        mayor = get_mayor(group_id)
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار!", show_alert=True); return True
        pop = get_mayor_popularity(group_id)
        pop_bar = "🟢" * (pop // 20) + "⚪️" * (5 - pop // 20)
        pledges = get_mayor_pledges(group_id, user.id)
        done = sum(1 for p in pledges if p["fulfilled"])
        total = len(pledges)
        txt = (f"📊 *پنل مدیریت شهردار*\n\n"
               f"👑 {mayor['first_name']}\n"
               f"📊 محبوبیت: {pop}٪ {pop_bar}\n"
               f"📌 وعده‌ها: {done}/{total} انجام شده\n\n"
               f"از اینجا می‌تونی شهر رو مدیریت کنی.")
        kb = [
            [cbtn("📜 صدور فرمان", callback_data=f"mayor_decree_{group_id}")],
            [cbtn("📌 وعده‌های من", callback_data=f"mayor_mypledges_{group_id}")],
            [cbtn("📊 گزارش عملکرد", callback_data=f"mayor_report_{group_id}")],
            [cbtn("🔙 بازگشت", callback_data=f"mayor_back_{group_id}")],
        ]
        await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return True

    if data.startswith("mayor_mypledges_"):
        group_id = int(data.split("_")[2])
        mayor = get_mayor(group_id)
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار!", show_alert=True); return True
        pledges = get_mayor_pledges(group_id, user.id)
        txt = "📌 *وعده‌های انتخاباتی من*\n\n"
        if not pledges:
            txt += "وعده‌ای ثبت نشده."
        for p in pledges:
            icon = "✅" if p["fulfilled"] else "⏳"
            txt += f"{icon} {p['pledge_text']}\n"
        await query.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت", callback_data=f"mayor_panel_{group_id}")]]))
        return True

    if data.startswith("mayor_report_"):
        group_id = int(data.split("_")[2])
        mayor = get_mayor(group_id)
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار!", show_alert=True); return True
        with db_conn() as conn:
            decree_count = conn.execute(
                "SELECT COUNT(*) FROM mayor_decrees WHERE group_id=? AND user_id=?",
                (group_id, user.id)
            ).fetchone()[0]
        pledges = get_mayor_pledges(group_id, user.id)
        done = sum(1 for p in pledges if p["fulfilled"])
        total = len(pledges)
        pop = get_mayor_popularity(group_id)
        txt = (f"📊 *گزارش عملکرد شهردار*\n\n"
               f"📜 فرمان‌های صادرشده: {decree_count}\n"
               f"📌 وعده‌های انجام‌شده: {done}/{total}\n"
               f"📊 محبوبیت فعلی: {pop}٪\n\n"
               f"💡 هر وعده انجام‌نشده در پایان دوره محبوبیت رو کم می‌کنه!")
        await query.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت", callback_data=f"mayor_panel_{group_id}")]]))
        return True


    if data.startswith("mayor_election_"):
        group_id = int(data.split("_")[2])
        election = get_active_election(group_id)
        mayor = get_mayor(group_id)
        txt = "🗳 *انتخابات شهرداری*\n\n"
        if election:
            if election["status"] == "candidacy":
                with db_conn() as conn:
                    cands = conn.execute(
                        "SELECT * FROM mayor_candidates WHERE group_id=? AND election_id=?", (group_id, election["id"],)
                    ).fetchall()
                txt += f"📋 مرحله: ثبت‌نام نامزدها\n👥 نامزدها: {len(cands)} نفر\n\n"
                for c in cands:
                    txt += f"• {c['first_name']}\n"
                kb = [[cbtn("✋ ثبت‌نام نامزدی", callback_data=f"melec_join_{group_id}_{election['id']}")]]
                if await _is_group_admin(context, group_id, user.id):
                    kb.append([cbtn("🗳 شروع رای‌گیری", callback_data=f"melec_startvote_{group_id}_{election['id']}")])
                    kb.append([cbtn("❌ لغو انتخابات", callback_data=f"melec_cancel_{group_id}_{election['id']}")])
            elif election["status"] == "voting":
                with db_conn() as conn:
                    cands = conn.execute(
                        "SELECT mc.*, COUNT(mev.voter_id) as votes FROM mayor_candidates mc "
                        "LEFT JOIN mayor_election_votes mev ON mev.candidate_id=mc.user_id AND mev.election_id=mc.election_id AND mev.group_id=mc.group_id "
                        "WHERE mc.group_id=? AND mc.election_id=? GROUP BY mc.user_id",
                        (group_id, election["id"])
                    ).fetchall()
                txt += "📊 مرحله: رای‌گیری\n\n"
                for c in cands:
                    txt += f"• {c['first_name']} — {c['votes']} رای\n"
                kb = [[cbtn(f"🗳 رای به {c['first_name']}", callback_data=f"melec_vote_{group_id}_{election['id']}_{c['user_id']}")]
                      for c in cands]
                if await _is_group_admin(context, group_id, user.id):
                    kb.append([cbtn("🏁 اعلام نتیجه", callback_data=f"melec_finish_{group_id}_{election['id']}")])
                    kb.append([cbtn("❌ لغو انتخابات", callback_data=f"melec_cancel_{group_id}_{election['id']}")])
            else:
                txt += "انتخابات تموم شده!"
                kb = []
        else:
            txt += "انتخاباتی در جریان نیست."
            kb = []
            if await _is_group_admin(context, group_id, user.id):
                kb.append([cbtn("🚀 شروع انتخابات جدید", callback_data=f"melec_start_{group_id}")])

        kb.append([cbtn("🔙 بازگشت", callback_data=f"mayor_back_{group_id}")])
        await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return True

    if data.startswith("melec_start_"):
        group_id = int(data.split("_")[2])
        if not await _is_group_admin(context, group_id, user.id):
            await query.answer("❌ فقط ادمین همین گروه می‌تونه انتخابات رو شروع کنه!", show_alert=True); return True
        if get_active_election(group_id):
            await query.answer("❌ انتخابات در جریانه!", show_alert=True); return True
        with db_conn() as conn:
            conn.execute(
                "INSERT INTO mayor_elections (group_id, status, started_by) VALUES (?,?,?)",
                (group_id, "candidacy", user.id)
            )
            conn.commit()
        log_mayor_action(group_id, user.id, "election", "انتخابات جدید شروع شد")
        try:
            await query.bot.send_message(
                group_id,
                "🗳 *انتخابات شهرداری شروع شد!*\n\n"
                "👤 برای نامزد شدن بنویسید *شهرداری* و دکمه ثبت‌نام رو بزنید.\n"
                "⏳ مرحله نامزدی آغاز شد.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await query.edit_message_text("✅ انتخابات شروع شد! کاربران می‌تونن ثبت‌نام کنن.",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data=f"mayor_election_{group_id}")]]))
        return True

    if data.startswith("melec_join_"):
        parts = data.split("_")
        group_id = int(parts[2])
        election_id = int(parts[3])
        with db_conn() as conn:
            elec = conn.execute("SELECT * FROM mayor_elections WHERE id=? AND group_id=?", (election_id, group_id)).fetchone()
            if not elec or elec["status"] != "candidacy":
                await query.answer("❌ ثبت‌نام این انتخابات فعال نیست!", show_alert=True); return True
            exists = conn.execute(
                "SELECT user_id FROM mayor_candidates WHERE group_id=? AND election_id=? AND user_id=?",
                (group_id, election_id, user.id)
            ).fetchone()
            if exists:
                await query.answer("❌ قبلاً ثبت‌نام کردی!", show_alert=True); return True
            conn.execute(
                "INSERT INTO mayor_candidates (election_id, group_id, user_id, username, first_name) VALUES (?,?,?,?,?)",
                (election_id, group_id, user.id, user.username or "", user.first_name)
            )
            conn.commit()

        context.user_data["pledge_election_id"] = election_id
        context.user_data["pledge_group_id"] = group_id
        context.user_data["waiting_pledges"] = True

        kb = []
        for key, txt_p in MAYOR_PLEDGES_DEF.items():
            kb.append([cbtn(txt_p, callback_data=f"melec_pledge_{group_id}_{election_id}_{key}")])
        kb.append([cbtn("✅ تمام، ثبت وعده‌ها", callback_data=f"melec_donepledge_{group_id}_{election_id}")])

        await query.edit_message_text(
            f"✅ *{user.first_name}* ثبت‌نام شد!\n\nحالا ۱ تا ۳ وعده انتخاباتی انتخاب کن:",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return True

    if data.startswith("melec_pledge_"):
        parts = data.split("_")
        group_id = int(parts[2])
        election_id = int(parts[3])
        pledge_key = "_".join(parts[4:])
        if pledge_key not in MAYOR_PLEDGES_DEF:
            await query.answer("وعده نامعتبر!", show_alert=True); return True
        with db_conn() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM mayor_pledges WHERE group_id=? AND election_id=? AND user_id=?",
                (group_id, election_id, user.id)
            ).fetchone()[0]
            if existing >= 3:
                await query.answer("❌ حداکثر ۳ وعده!", show_alert=True); return True
            already = conn.execute(
                "SELECT id FROM mayor_pledges WHERE group_id=? AND election_id=? AND user_id=? AND pledge_key=?",
                (group_id, election_id, user.id, pledge_key)
            ).fetchone()
            if already:
                await query.answer("این وعده قبلاً ثبت شده!", show_alert=True); return True
            conn.execute(
                "INSERT INTO mayor_pledges (group_id, election_id, user_id, pledge_key, pledge_text) VALUES (?,?,?,?,?)",
                (group_id, election_id, user.id, pledge_key, MAYOR_PLEDGES_DEF[pledge_key])
            )
            conn.commit()
        await query.answer(f"✅ وعده ثبت شد: {MAYOR_PLEDGES_DEF[pledge_key]}")
        return True

    if data.startswith("melec_donepledge_"):
        parts = data.split("_")
        group_id = int(parts[2])
        election_id = int(parts[3])
        with db_conn() as conn:
            cand = conn.execute("SELECT 1 FROM mayor_candidates WHERE group_id=? AND election_id=? AND user_id=?", (group_id, election_id, user.id)).fetchone()
            if not cand:
                await query.answer("❌ اول باید در همین انتخابات ثبت‌نام کنی!", show_alert=True); return True
            pledges = conn.execute(
                "SELECT pledge_text FROM mayor_pledges WHERE group_id=? AND election_id=? AND user_id=?",
                (group_id, election_id, user.id)
            ).fetchall()
        pledge_list = "\n".join(f"• {p['pledge_text']}" for p in pledges) or "بدون وعده"
        try:
            await query.bot.send_message(
                group_id,
                f"✋ *{user.first_name}* نامزد شهرداری شد!\n\n"
                f"📌 *وعده‌های انتخاباتی:*\n{pledge_list}\n\n"
                f"🗳 برای رای دادن منتظر شروع رای‌گیری باشید.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await query.edit_message_text(
            f"✅ ثبت‌نام کامل شد!\n\n📌 وعده‌هات:\n{pledge_list}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data=f"mayor_election_{group_id}")]]))
        return True

    if data.startswith("melec_startvote_"):
        parts = data.split("_")
        group_id = int(parts[2])
        election_id = int(parts[3])
        if not await _is_group_admin(context, group_id, user.id):
            await query.answer("❌ فقط ادمین همین گروه می‌تونه رای‌گیری رو شروع کنه!", show_alert=True); return True
        with db_conn() as conn:
            cands = conn.execute(
                "SELECT * FROM mayor_candidates WHERE group_id=? AND election_id=?", (group_id, election_id)
            ).fetchall()
            elec = conn.execute("SELECT * FROM mayor_elections WHERE id=? AND group_id=?", (election_id, group_id)).fetchone()
            if not elec or elec["status"] != "candidacy":
                await query.answer("❌ این انتخابات فعال نیست!", show_alert=True); return True
            if len(cands) < 1:
                await query.answer("❌ حداقل یه نامزد لازمه!", show_alert=True); return True
            conn.execute(
                "UPDATE mayor_elections SET status='voting' WHERE id=? AND group_id=?", (election_id, group_id)
            )
            conn.commit()
        log_mayor_action(group_id, user.id, "election", "رای‌گیری شروع شد")
        try:
            cand_list = "\n".join(f"• {c['first_name']}" for c in cands)
            await query.bot.send_message(
                group_id,
                f"🗳 *رای‌گیری شهرداری شروع شد!*\n\n"
                f"👥 نامزدها:\n{cand_list}\n\n"
                f"برای رای دادن بنویسید *شهرداری* و نامزد مورد نظر رو انتخاب کنید!",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await query.edit_message_text("✅ رای‌گیری شروع شد!",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data=f"mayor_election_{group_id}")]]))
        return True

    if data.startswith("melec_vote_"):
        parts = data.split("_")
        group_id = int(parts[2])
        election_id = int(parts[3])
        candidate_id = int(parts[4])
        try:
            cm = await context.bot.get_chat_member(group_id, user.id)
            if cm.status not in ("creator", "administrator", "member") and not getattr(cm, "is_member", False):
                await query.answer("❌ فقط اعضای همین گروه حق رأی دارند.", show_alert=True); return True
        except Exception:
            await query.answer("❌ عضویت شما در گروه قابل تأیید نیست.", show_alert=True); return True
        with db_conn() as conn:
            elec = conn.execute("SELECT * FROM mayor_elections WHERE id=? AND group_id=?", (election_id, group_id)).fetchone()
            if not elec or elec["status"] != "voting":
                await query.answer("❌ رای‌گیری فعال نیست!", show_alert=True); return True
            candidate = conn.execute(
                "SELECT user_id FROM mayor_candidates WHERE group_id=? AND election_id=? AND user_id=?",
                (group_id, election_id, candidate_id)
            ).fetchone()
            if not candidate:
                await query.answer("❌ نامزد نامعتبره!", show_alert=True); return True
            already = conn.execute(
                "SELECT voter_id FROM mayor_election_votes WHERE group_id=? AND election_id=? AND voter_id=?",
                (group_id, election_id, user.id)
            ).fetchone()
            if already:
                await query.answer("❌ قبلاً رای دادی!", show_alert=True); return True
            conn.execute(
                "INSERT INTO mayor_election_votes (election_id, group_id, voter_id, candidate_id) VALUES (?,?,?,?)",
                (election_id, group_id, user.id, candidate_id)
            )
            conn.commit()
        await query.answer("✅ رای ثبت شد!")
        return True

    if data.startswith("melec_finish_"):
        parts = data.split("_")
        group_id = int(parts[2])
        election_id = int(parts[3])
        if not await _is_group_admin(context, group_id, user.id):
            await query.answer("❌ فقط ادمین همین گروه می‌تونه نتیجه رو اعلام کنه!", show_alert=True); return True
        with db_conn() as conn:
            elec = conn.execute("SELECT * FROM mayor_elections WHERE id=? AND group_id=?", (election_id, group_id)).fetchone()
            if not elec or elec["status"] != "voting":
                await query.answer("❌ رای‌گیری فعال نیست!", show_alert=True); return True
            winner = conn.execute(
                """SELECT mc.user_id, mc.username, mc.first_name, COUNT(mev.voter_id) as votes
                   FROM mayor_candidates mc
                   LEFT JOIN mayor_election_votes mev ON mev.candidate_id=mc.user_id AND mev.election_id=? AND mev.group_id=mc.group_id
                   WHERE mc.group_id=? AND mc.election_id=?
                   GROUP BY mc.user_id ORDER BY votes DESC LIMIT 1""",
                (election_id, group_id, election_id)
            ).fetchone()
            conn.execute(
                "UPDATE mayor_elections SET status='done', ended_at=? WHERE id=? AND group_id=?",
                (datetime.now().isoformat(), election_id, group_id)
            )
            conn.commit()

        if not winner:
            await query.answer("❌ نامزدی وجود نداره!", show_alert=True); return True

        old_mayor = get_mayor(group_id)
        if old_mayor:
            old_pledges = get_mayor_pledges(group_id, old_mayor["user_id"])
            unfulfilled = sum(1 for p in old_pledges if not p["fulfilled"])
            if unfulfilled > 0:
                change_mayor_popularity(group_id, -unfulfilled * 10)

        set_mayor(group_id, winner["user_id"], winner["username"], winner["first_name"])
        log_mayor_action(group_id, winner["user_id"], "elected", f"{winner['first_name']} شهردار شد با {winner['votes']} رای")

        try:
            await query.bot.send_message(
                group_id,
                f"🎉 *انتخابات تموم شد!*\n\n👑 شهردار جدید: *{winner['first_name']}*\n🗳 با {winner['votes']} رای\n\nمبارک باشه! 🏛",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await query.edit_message_text(
            f"🎉 *{winner['first_name']}* شهردار جدید شد!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 پنل شهرداری", callback_data=f"mayor_back_{group_id}")]]))
        return True

    if data.startswith("melec_cancel_"):
        parts = data.split("_")
        group_id = int(parts[2])
        election_id = int(parts[3])
        if not await _is_group_admin(context, group_id, user.id):
            await query.answer("❌ فقط ادمین همین گروه!", show_alert=True); return True
        with db_conn() as conn:
            conn.execute("UPDATE mayor_elections SET status='cancelled' WHERE id=? AND group_id=?", (election_id, group_id))
            conn.commit()
        log_mayor_action(group_id, user.id, "election", "انتخابات توسط ادمین لغو شد")
        try:
            await query.bot.send_message(
                group_id,
                "❌ *انتخابات شهرداری لغو شد.*\n\nادمین انتخابات را لغو کرد.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await query.edit_message_text("✅ انتخابات لغو شد.",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 برگشت", callback_data=f"mayor_election_{group_id}")]]))
        return True


    if data.startswith("mayor_protest_"):
        group_id = int(data.split("_")[2])
        mayor = get_mayor(group_id)
        if not mayor:
            await query.answer("❌ شهرداری نداریم!", show_alert=True); return True
        if mayor["user_id"] == user.id:
            await query.answer("❌ نمی‌تونی به خودت اعتراض کنی!", show_alert=True); return True
        existing = get_active_protest(group_id)
        if existing:
            await query.answer("❌ یه اعتراض فعال داریم! صبر کن.", show_alert=True); return True
        context.user_data["protest_group_id"] = group_id
        context.user_data["waiting_protest"] = True
        await query.edit_message_text(
            "📢 *اعتراض به شهردار*\n\nدلیل اعتراضت رو بنویس (حداکثر ۱۰۰ کاراکتر):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[cbtn("❌ انصراف", callback_data=f"mayor_back_{group_id}")]])
        )
        return True

    if data.startswith("mayor_pvote_"):
        parts = data.split("_")
        group_id = int(parts[2])
        protest_id = int(parts[3])
        vote = parts[4]
        with db_conn() as conn:
            already = conn.execute(
                "SELECT user_id FROM mayor_protest_votes WHERE protest_id=? AND user_id=?",
                (protest_id, user.id)
            ).fetchone()
            if already:
                await query.answer("قبلاً رای دادی!", show_alert=True); return True
            conn.execute(
                "INSERT INTO mayor_protest_votes (protest_id, user_id, vote) VALUES (?,?,?)",
                (protest_id, user.id, vote)
            )
            yes = conn.execute("SELECT COUNT(*) FROM mayor_protest_votes WHERE protest_id=? AND vote='yes'", (protest_id,)).fetchone()[0]
            no  = conn.execute("SELECT COUNT(*) FROM mayor_protest_votes WHERE protest_id=? AND vote='no'",  (protest_id,)).fetchone()[0]
            conn.commit()
        if yes >= 10:
            fired_mayor = get_mayor(group_id)
            mayor_name = fired_mayor["first_name"] if fired_mayor else "شهردار"
            with db_conn() as conn:
                conn.execute("UPDATE mayor_protests SET status='accepted' WHERE id=?", (protest_id,))
                conn.execute("DELETE FROM mayor WHERE group_id=?", (group_id,))
                conn.commit()
            log_mayor_action(group_id, user.id, "protest", "شهردار با رای اعتراض برکنار شد")
            try:
                await query.bot.send_message(
                    group_id,
                    f"⚠️ *اعتراض پذیرفته شد!*\n\n"
                    f"👤 {mayor_name} با رای مردم از شهرداری برکنار شد.\n"
                    f"🗳 انتخابات جدید برگزار کنید!",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        await query.answer(f"✅ رای ثبت شد | ✅{yes} ❌{no}")
        return True

    return False

async def _edit_mayor_panel(query, group_id: int, user):
    mayor = get_mayor(group_id)
    election = get_active_election(group_id)
    decree = get_active_decree(group_id)
    is_mayor = mayor and mayor["user_id"] == user.id
    pop = get_mayor_popularity(group_id) if mayor else 0
    pop_bar = "🟢" * (pop // 20) + "⚪️" * (5 - pop // 20)

    if mayor:
        term = datetime.fromisoformat(mayor["term_end"])
        days_left = max(0, (term - datetime.now()).days)
        mayor_line = f"👑 شهردار: {mayor['first_name']} | محبوبیت: {pop}٪ {pop_bar}\n⏳ {days_left} روز تا پایان دوره"
    else:
        mayor_line = "⚠️ این گروه شهردار ندارد!"

    decree_line = f"📜 فرمان فعال: {decree['decree_name']}" if decree else "📜 فرمانی فعال نیست"

    text = (f"🏛 *شهرداری هاپو*\n\n{mayor_line}\n{decree_line}\n\n")

    kb = []
    if is_mayor:
        kb.append([cbtn("📜 صدور فرمان روزانه", callback_data=f"mayor_decree_{group_id}")])
        kb.append([cbtn("📊 پنل مدیریت شهردار", callback_data=f"mayor_panel_{group_id}")])
    kb.append([cbtn("🗳 انتخابات", callback_data=f"mayor_election_{group_id}")])
    kb.append([cbtn("📋 وضعیت شهرداری", callback_data=f"mayor_status_{group_id}")])
    if mayor and not is_mayor:
        kb.append([cbtn("📢 اعتراض به شهردار", callback_data=f"mayor_protest_{group_id}")])
    kb.append([cbtn("📜 تاریخچه تصمیمات", callback_data=f"mayor_log_{group_id}")])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def handle_mayor_protest_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.text:
        return False
    if not context.user_data.get("waiting_protest"):
        return False

    group_id = context.user_data.pop("protest_group_id", None)
    context.user_data.pop("waiting_protest", None)

    if not group_id:
        return False

    user = update.effective_user
    reason = update.message.text.strip()[:100]
    mayor = get_mayor(group_id)
    if not mayor:
        await update.message.reply_text("❌ شهرداری نداریم!")
        return True

    with db_conn() as conn:
        conn.execute(
            "INSERT INTO mayor_protests (group_id, user_id, username, first_name, reason) VALUES (?,?,?,?,?)",
            (group_id, user.id, user.username or "", user.first_name, reason)
        )
        conn.commit()
        protest_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_mayor_action(group_id, user.id, "protest", f"اعتراض ثبت شد: {reason[:40]}")

    kb = InlineKeyboardMarkup([
        [cbtn("✅ موافقم", callback_data=f"mayor_pvote_{group_id}_{protest_id}_yes"),
         cbtn("❌ مخالفم", callback_data=f"mayor_pvote_{group_id}_{protest_id}_no")],
    ])

    try:
        await context.bot.send_message(
            group_id,
            f"📢 *اعتراض جدید!*\n\n👤 {user.first_name}: {reason}\n\n"
            f"⚠️ اگه ۱۰ نفر موافق باشن، شهردار برکنار میشه!",
            parse_mode="Markdown", reply_markup=kb
        )
    except Exception:
        logger.warning("Non-fatal exception was suppressed", exc_info=True)

    await update.message.reply_text("✅ اعتراضت ثبت شد و به گروه اعلام شد!")
    return True


CITY_PROJECTS = {
    "bank":      {"name": "🏦 توسعه بانک",         "desc": "+۱۵٪ سود بانک",              "effect": "bank_boost",    "build_hours": 24, "max_level": 3},
    "factory":   {"name": "🏭 منطقه صنعتی",         "desc": "+۲۰٪ تولید کارخانه",         "effect": "factory_boost", "build_hours": 24, "max_level": 3},
    "dog":       {"name": "🐕 پناهگاه سگ‌ها",       "desc": "+۲۰٪ درآمد سگ",             "effect": "dog_boost",     "build_hours": 12, "max_level": 3},
    "park":      {"name": "🌳 پارک شهر",             "desc": "+۱۰٪ پاداش فعالیت روزانه",  "effect": "daily_boost",   "build_hours": 18, "max_level": 2},
    "power":     {"name": "⚡ نیروگاه",              "desc": "-۲۰٪ زمان انتظار",           "effect": "cooldown_cut",  "build_hours": 36, "max_level": 2},
}

CITY_CONTRACTS = {
    "industrial": {"name": "🏭 قرارداد صنعتی",  "pros": "+۲۰٪ تولید کارخانه", "cons": "-۱۰٪ سود بانک",    "pro_effect": "factory_boost", "con_effect": "bank_cut"},
    "banking":    {"name": "🏦 قرارداد بانکی",   "pros": "+۱۵٪ سود بانک",      "cons": "-۵٪ درآمد هاپ",    "pro_effect": "bank_boost",    "con_effect": "hop_cut"},
    "welfare":    {"name": "🤝 قرارداد رفاهی",   "pros": "+۱۰٪ درآمد سگ",      "cons": "-۵٪ تولید کارخانه","pro_effect": "dog_boost",     "con_effect": "factory_cut"},
}

def get_project_setting(key, default=None):
    with db_conn() as conn:
        r = conn.execute("SELECT value FROM mayor_project_settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default

def set_project_setting(key, value):
    with db_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO mayor_project_settings (key,value) VALUES (?,?)", (key, str(value)))
        conn.commit()

def get_contract_setting(key, default=None):
    with db_conn() as conn:
        r = conn.execute("SELECT value FROM mayor_contract_settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default

def set_contract_setting(key, value):
    with db_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO mayor_contract_settings (key,value) VALUES (?,?)", (key, str(value)))
        conn.commit()

def get_project_cost(project_key, level=1):
    raw = get_project_setting(f"cost_{project_key}_lv{level}", 50000)
    return int(raw)

def get_contract_min_days():
    raw = get_contract_setting("min_days", 3)
    return int(raw)

def get_active_project(group_id, project_key):
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM mayor_projects WHERE group_id=? AND project_key=? ORDER BY id DESC LIMIT 1",
            (group_id, project_key)
        ).fetchone()

def get_active_contract(group_id):
    with db_conn() as conn:
        return conn.execute(
            "SELECT * FROM mayor_contracts WHERE group_id=? AND status='active' AND datetime(replace(expires_at,'T',' ')) > datetime('now') ORDER BY id DESC LIMIT 1",
            (group_id,)
        ).fetchone()

def project_effect_multiplier(group_id, effect_key) -> float:
    from datetime import datetime
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM mayor_projects WHERE group_id=? AND status='done'",
            (group_id,)
        ).fetchall()
    mult = 1.0
    for p in rows:
        proj = CITY_PROJECTS.get(p["project_key"])
        if proj and proj["effect"] == effect_key:
            mult += 0.15 * p["level"]
    return mult

def contract_effect(group_id, effect_key) -> float:
    c = get_active_contract(group_id)
    if not c:
        return 1.0
    contract = CITY_CONTRACTS.get(c["contract_key"])
    if not contract:
        return 1.0
    boosts = {"factory_boost": 1.2, "bank_boost": 1.15, "dog_boost": 1.1}
    cuts   = {"bank_cut": 0.9, "hop_cut": 0.95, "factory_cut": 0.95}
    if contract["pro_effect"] == effect_key:
        return boosts.get(effect_key, 1.0)
    if contract["con_effect"] == effect_key:
        return cuts.get(effect_key, 1.0)
    return 1.0

async def projects_panel(query, group_id, user):
    mayor = get_mayor(group_id)
    is_mayor = mayor and mayor["user_id"] == user.id

    txt = "🏗 *پروژه‌های شهری*\n\n"
    kb = []

    for key, p in CITY_PROJECTS.items():
        proj = get_active_project(group_id, key)
        if not proj:
            status = "⬜ ساخته نشده"
            lv = 0
        elif proj["status"] == "building":
            from datetime import datetime
            done = datetime.fromisoformat(proj["done_at"])
            rem = done - datetime.now()
            h = int(rem.total_seconds() // 3600)
            m = int((rem.total_seconds() % 3600) // 60)
            status = f"🔨 در حال ساخت ({h}:{m:02d} مانده)"
            lv = proj["level"] - 1
        else:
            lv = proj["level"]
            status = f"✅ سطح {lv}"

        max_lv = p["max_level"]
        txt += f"{p['name']} — {status}\n📋 {p['desc']}\n\n"

        if is_mayor and lv < max_lv and (not proj or proj["status"] == "done"):
            cost = get_project_cost(key, lv + 1)
            kb.append([cbtn(f"🔨 {p['name']} سطح {lv+1} ({cost:,} پوینت)", f"mproj_build_{key}")])

    contract = get_active_contract(group_id)
    if contract:
        c = CITY_CONTRACTS[contract["contract_key"]]
        from datetime import datetime
        exp = datetime.fromisoformat(contract["expires_at"])
        rem = exp - datetime.now()
        d = int(rem.total_seconds() // 86400)
        txt += f"📜 *قرارداد فعال:* {c['name']}\n✅ {c['pros']} | ❌ {c['cons']}\n⏳ {d} روز مانده\n"
    else:
        txt += "📜 *قرارداد:* ندارد\n"
        if is_mayor:
            kb.append([cbtn("📜 امضای قرارداد", "mproj_contract_menu")])

    kb.append([cbtn("🔙 بازگشت", "mayor_back")])
    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def mayor_projects_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data = query.data
    user = update.effective_user
    group_id = update.effective_chat.id if update.effective_chat else None

    if not data.startswith("mproj_"):
        return False

    await query.answer()

    if data == "mproj_panel":
        await projects_panel(query, group_id, user)
        return True

    if data.startswith("mproj_build_"):
        key = data.replace("mproj_build_", "")
        mayor = get_mayor(group_id)
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار!", show_alert=True); return True

        proj = get_active_project(group_id, key)
        p = CITY_PROJECTS[key]
        cur_level = proj["level"] if proj and proj["status"] == "done" else 0
        if cur_level >= p["max_level"]:
            await query.answer("❌ حداکثر سطح!", show_alert=True); return True
        if proj and proj["status"] == "building":
            await query.answer("❌ در حال ساخته!", show_alert=True); return True

        cost = get_project_cost(key, cur_level + 1)
        half = cost // 2

        u = get_user(user.id)
        if not u or u["hop_points"] < half:
            await query.answer(f"❌ پوینت کافی نداری! نیاز: {half:,}", show_alert=True); return True

        from datetime import datetime, timedelta
        build_hours = p["build_hours"]
        done_at = (datetime.now() + timedelta(hours=build_hours)).isoformat()

        with db_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            fresh_proj = conn.execute("SELECT * FROM mayor_projects WHERE group_id=? AND project_key=? ORDER BY id DESC LIMIT 1", (group_id, key)).fetchone()
            fresh_level = fresh_proj["level"] if fresh_proj and fresh_proj["status"] == "done" else 0
            if fresh_proj and fresh_proj["status"] == "building":
                conn.rollback(); await query.answer("❌ این پروژه همین حالا در حال ساخت است.", show_alert=True); return True
            if fresh_level >= p["max_level"]:
                conn.rollback(); await query.answer("❌ حداکثر سطح پروژه رسیده.", show_alert=True); return True
            debit_user = conn.execute("UPDATE users SET hop_points=hop_points-? WHERE user_id=? AND hop_points>=?", (half, user.id, half))
            if debit_user.rowcount != 1:
                conn.rollback(); await query.answer(f"❌ پوینت کافی نداری! نیاز: {half:,}", show_alert=True); return True
            debit_city = conn.execute("UPDATE groups SET treasury=treasury-? WHERE group_id=? AND treasury>=?", (half, group_id, half))
            if debit_city.rowcount != 1:
                conn.rollback(); await query.answer(f"❌ خزانه کافی نیست! نیاز: {half:,}", show_alert=True); return True
            conn.execute("INSERT INTO mayor_projects (group_id, project_key, level, done_at, status) VALUES (?,?,?,?,'building')",
                         (group_id, key, fresh_level + 1, done_at))
            conn.commit()

        await query.edit_message_text(
            f"✅ *ساخت {p['name']} شروع شد!*\n\n"
            f"💰 هزینه: {half:,} از شما + {half:,} از خزانه\n"
            f"⏳ زمان ساخت: {build_hours} ساعت\n\n"
            f"بعد از اتمام، مزیت فعال میشه.",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                group_id,
                f"🏗 *پروژه جدید شهری!*\n\n{p['name']} در حال ساخت...\n⏳ {build_hours} ساعت دیگه آماده میشه!",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return True

    if data == "mproj_contract_menu":
        mayor = get_mayor(group_id)
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار!", show_alert=True); return True
        min_days = get_contract_min_days()
        kb = []
        for key, c in CITY_CONTRACTS.items():
            kb.append([cbtn(f"{c['name']}", f"mproj_sign_{key}")])
        kb.append([cbtn("🔙 بازگشت", "mproj_panel")])
        await query.edit_message_text(
            f"📜 *امضای قرارداد*\n\n"
            f"⚠️ در هر زمان فقط یک قرارداد فعاله.\n"
            f"⏳ حداقل مدت: {min_days} روز\n\n"
            + "\n".join([f"{c['name']}\n✅ {c['pros']} | ❌ {c['cons']}" for c in CITY_CONTRACTS.values()]),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return True

    if data.startswith("mproj_sign_"):
        key = data.replace("mproj_sign_", "")
        mayor = get_mayor(group_id)
        if not mayor or mayor["user_id"] != user.id:
            await query.answer("❌ فقط شهردار!", show_alert=True); return True
        if get_active_contract(group_id):
            await query.answer("❌ قرارداد فعال دارید!", show_alert=True); return True
        if key not in CITY_CONTRACTS:
            return True

        min_days = get_contract_min_days()
        context.user_data["signing_contract"] = key
        context.user_data["signing_contract_group"] = group_id
        context.user_data["waiting_contract_days"] = True
        c = CITY_CONTRACTS[key]
        await query.edit_message_text(
            f"📜 *{c['name']}*\n\n✅ {c['pros']}\n❌ {c['cons']}\n\n"
            f"چند روز؟ (حداقل {min_days} روز)\nعدد رو بنویس:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 انصراف", "mproj_contract_menu")]])
        )
        return True

    if data == "mproj_admin_panel":
        if not is_admin(user.id):
            await query.answer("❌ فقط ادمین!", show_alert=True); return True
        min_days = get_contract_min_days()
        txt = "⚙️ *تنظیمات پروژه‌ها*\n\n"
        txt += f"📅 حداقل مدت قرارداد: {min_days} روز\n\n"
        txt += "💰 *هزینه پروژه‌ها:*\n"
        for key, p in CITY_PROJECTS.items():
            for lv in range(1, p["max_level"] + 1):
                cost = get_project_cost(key, lv)
                txt += f"• {p['name']} سطح {lv}: {cost:,}\n"
        kb = [
            [cbtn("✏️ تغییر هزینه پروژه", "mproj_admin_setcost")],
            [cbtn("✏️ تغییر حداقل روز قرارداد", "mproj_admin_setdays")],
        ]
        await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return True

    if data == "mproj_admin_setdays":
        if not is_admin(user.id): return True
        context.user_data["admin_setting"] = "contract_min_days"
        await query.edit_message_text(
            "عدد حداقل روز قرارداد رو بنویس:",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 انصراف", "mproj_admin_panel")]])
        )
        return True

    if data == "mproj_admin_setcost":
        if not is_admin(user.id): return True
        kb = []
        for key, p in CITY_PROJECTS.items():
            for lv in range(1, p["max_level"] + 1):
                kb.append([cbtn(f"{p['name']} سطح {lv}", f"mproj_admin_cost_{key}_{lv}")])
        kb.append([cbtn("🔙 بازگشت", "mproj_admin_panel")])
        await query.edit_message_text("کدوم پروژه رو میخوای؟", reply_markup=InlineKeyboardMarkup(kb))
        return True

    if data.startswith("mproj_admin_cost_"):
        if not is_admin(user.id): return True
        parts = data.replace("mproj_admin_cost_", "").rsplit("_", 1)
        key, lv = parts[0], parts[1]
        context.user_data["admin_setting"] = f"project_cost_{key}_lv{lv}"
        context.user_data["admin_setting_label"] = f"{CITY_PROJECTS[key]['name']} سطح {lv}"
        await query.edit_message_text(
            f"هزینه {CITY_PROJECTS[key]['name']} سطح {lv} رو بنویس:",
            reply_markup=InlineKeyboardMarkup([[cbtn("🔙 انصراف", "mproj_admin_panel")]])
        )
        return True

    if data == "mayor_back":
        await query.edit_message_text("🏛 پنل بسته شد.")
        return True

    return False

async def handle_mayor_project_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.text:
        return False

    if context.user_data.get("admin_setting") and is_admin(update.effective_user.id):
        setting = context.user_data.pop("admin_setting")
        label = context.user_data.pop("admin_setting_label", setting)
        text = update.message.text.strip()
        if not text.isdigit():
            await update.message.reply_text("❌ عدد بنویس!")
            return True
        val = int(text)
        if setting == "contract_min_days":
            set_contract_setting("min_days", val)
            await update.message.reply_text(f"✅ حداقل روز قرارداد: {val} روز")
        else:
            pk = setting.replace("project_cost_", "")
            parts = pk.rsplit("_lv", 1)
            set_project_setting(f"cost_{parts[0]}_lv{parts[1]}", val)
            await update.message.reply_text(f"✅ هزینه {label}: {val:,} پوینت")
        return True

    if context.user_data.get("waiting_contract_days"):
        contract_key = context.user_data.get("signing_contract")
        group_id = context.user_data.get("signing_contract_group")
        if not contract_key or not group_id:
            return False
        text = update.message.text.strip()
        if not text.isdigit():
            await update.message.reply_text("❌ عدد بنویس!")
            return True
        days = int(text)
        min_days = get_contract_min_days()
        if days < min_days:
            await update.message.reply_text(f"❌ حداقل {min_days} روز!")
            return True

        context.user_data.pop("waiting_contract_days", None)
        context.user_data.pop("signing_contract", None)
        context.user_data.pop("signing_contract_group", None)

        from datetime import datetime, timedelta
        expires = (datetime.now() + timedelta(days=days)).isoformat()
        with db_conn() as conn:
            conn.execute(
                "INSERT INTO mayor_contracts (group_id, contract_key, expires_at, status) VALUES (?,?,?,'active')",
                (group_id, contract_key, expires)
            )
            conn.commit()

        c = CITY_CONTRACTS[contract_key]
        await update.message.reply_text(
            f"✅ *قرارداد امضا شد!*\n\n{c['name']}\n✅ {c['pros']}\n❌ {c['cons']}\n⏳ {days} روز",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                group_id,
                f"📜 *قرارداد جدید!*\n\n{c['name']}\n✅ {c['pros']}\n❌ {c['cons']}\n⏳ {days} روز",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return True

    return False


LEADER_COMMAND_COOLDOWN   = 86_400
LEADER_COMMAND_DURATION   = 43_200
LEADER_TERM_DAYS          = 30
LEADER_ELECTION_DAYS      = 3
LEADER_MIN_CANDIDATES     = 1

NATIONAL_COMMANDS = {
    "hop_boost":      {"name": "🦴 افزایش درآمد هاپ",           "hop_mult": 1.5,  "desc": "درآمد هاپ همه بازیکنان ۵۰٪ بیشتر میشه"},
    "factory_boost":  {"name": "🏭 افزایش تولید کارخانه‌ها",    "factory_mult": 1.4, "desc": "سرعت تولید کارخانه‌ها ۴۰٪ بیشتر میشه"},
    "dog_boost":      {"name": "🐕 افزایش درآمد سگ‌ها",          "dog_mult": 1.5,  "desc": "درآمد سگ‌ها ۵۰٪ بیشتر میشه"},
    "bank_boost":     {"name": "🏦 افزایش سود بانک",             "bank_mult": 1.3, "desc": "سود بانک ۳۰٪ بیشتر میشه"},
    "tax_cut":        {"name": "💸 کاهش مالیات",                 "tax_mult": 0.5,  "desc": "مالیات کشور ۵۰٪ کمتر میشه"},
    "daily_bonus":    {"name": "🎁 افزایش جایزه مأموریت روزانه", "daily_bonus": 500, "desc": "+۵۰۰ جایزه اضافه به هاپ روزانه"},
    "cd_cut":         {"name": "⚡ کاهش کولداون",                "cd_mult": 0.8,   "desc": "زمان انتظار ۲۰٪ کمتر میشه"},
    "all_boost":      {"name": "✨ افزایش درآمد همه مشاغل",      "all_mult": 1.25, "desc": "کل درآمدها ۲۵٪ بیشتر میشه"},
}

NATIONAL_LAWS = {
    "tax_5":          {"name": "⚖️ مالیات کشور ۵٪",         "tax_rate": 0.05},
    "tax_2":          {"name": "⚖️ مالیات کشور ۲٪",         "tax_rate": 0.02},
    "bank_bonus":     {"name": "🏦 افزایش سود بانک",         "bank_rate_bonus": 0.01},
    "factory_bonus":  {"name": "🏭 درآمد کارخانه بیشتر",    "factory_rate": 1.15},
    "upgrade_disc":   {"name": "🔧 کاهش هزینه ارتقا",        "upgrade_disc": 0.85},
    "item_disc":      {"name": "🛒 کاهش هزینه آیتم",         "item_disc": 0.90},
}

NATIONAL_PROJECTS = {
    "central_bank":   {"name": "🏦 بانک مرکزی",      "cost": 5_000_000,  "build_hours": 24, "effect": "bank_mult:1.2",  "desc": "سود بانک ۲۰٪ بیشتر میشه"},
    "industrial_zone":{"name": "🏭 شهرک صنعتی",      "cost": 8_000_000,  "build_hours": 36, "effect": "factory_mult:1.3","desc": "تولید کارخانه ۳۰٪ بیشتر میشه"},
    "airport":        {"name": "🛫 فرودگاه",           "cost": 12_000_000, "build_hours": 48, "effect": "hop_mult:1.15",  "desc": "درآمد هاپ ۱۵٪ بیشتر میشه"},
    "seaport":        {"name": "🚢 بندر",              "cost": 10_000_000, "build_hours": 42, "effect": "trade_mult:1.25","desc": "درآمد تجارت ۲۵٪ بیشتر میشه"},
    "powerplant":     {"name": "⚡ نیروگاه ملی",      "cost": 6_000_000,  "build_hours": 30, "effect": "cd_mult:0.85",   "desc": "کولداون همه ۱۵٪ کمتر میشه"},
    "tech_center":    {"name": "📡 مرکز فناوری",      "cost": 15_000_000, "build_hours": 72, "effect": "all_mult:1.1",   "desc": "درآمد همه مشاغل ۱۰٪ بیشتر میشه"},
}

MINISTER_ROLES = {
    "economy":    {"name": "وزیر اقتصاد 💹",      "effect": "all_mult:1.05",    "desc": "+۵٪ درآمد کل کشور"},
    "industry":   {"name": "وزیر صنعت 🏭",        "effect": "factory_mult:1.1", "desc": "+۱۰٪ تولید کارخانه"},
    "bank":       {"name": "وزیر بانک 🏦",         "effect": "bank_mult:1.03",   "desc": "+۳٪ سود بانک"},
    "agriculture":{"name": "وزیر کشاورزی 🌾",     "effect": "dog_mult:1.08",    "desc": "+۸٪ درآمد سگ‌ها"},
    "livestock":  {"name": "وزیر دامداری 🐄",      "effect": "dog_mult:1.06",    "desc": "+۶٪ درآمد سگ‌ها"},
    "trade":      {"name": "وزیر تجارت 🤝",        "effect": "hop_mult:1.08",    "desc": "+۸٪ درآمد هاپ"},
}

NATIONAL_EVENTS = {
    "hop_festival":   {"name": "🎉 جشنواره هاپ",    "hours": 6,  "hop_mult": 2.0,  "cost": 500_000},
    "industry_week":  {"name": "🏭 هفته صنعت",       "hours": 24, "factory_mult":1.5,"cost": 800_000},
    "dog_party":      {"name": "🐕 جشن سگ‌ها",       "hours": 6,  "dog_mult": 2.0,  "cost": 400_000},
    "login_bonus":    {"name": "🎁 پاداش ورود",       "hours": 12, "daily_bonus": 1000,"cost": 300_000},
    "golden_friday":  {"name": "🌟 جمعه طلایی",      "hours": 8,  "all_mult": 1.5,  "cost": 1_000_000},
    "double_income":  {"name": "💰 دو برابر درآمد",  "hours": 4,  "all_mult": 2.0,  "cost": 1_500_000},
}

EMERGENCY_TYPES = {
    "war":          {"name": "⚔️ جنگ",            "hours": 12, "tax_mult": 0.3, "all_mult": 0.8},
    "recession":    {"name": "📉 رکود اقتصادی",    "hours": 24, "tax_mult": 0.5, "factory_mult": 0.7},
    "crisis":       {"name": "💥 بحران مالی",       "hours": 12, "bank_mult": 0.5,"all_mult": 0.9},
    "special":      {"name": "🚨 وضعیت ویژه",      "hours": 6,  "cd_mult": 0.7,  "all_mult": 1.1},
}

def _leader_group_id(obj=None, context=None, default=None):
    """Return the Telegram group id for the current government context."""
    try:
        if obj is not None:
            chat = getattr(obj, "effective_chat", None)
            if chat and getattr(chat, "type", None) in ("group", "supergroup"):
                return chat.id
            message = getattr(obj, "message", None)
            chat = getattr(message, "chat", None)
            if chat and getattr(chat, "type", None) in ("group", "supergroup"):
                return chat.id
            if getattr(obj, "chat", None) and getattr(obj.chat, "type", None) in ("group", "supergroup"):
                return obj.chat.id
    except Exception:
        logger.warning("Non-fatal exception was suppressed", exc_info=True)
    try:
        if context is not None:
            gid = context.user_data.get("leader_group_id")
            if gid:
                return int(gid)
    except Exception:
        logger.warning("Non-fatal exception was suppressed", exc_info=True)
    return default


def _add_column_if_missing(conn, table, column, definition):
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _rebuild_table_if_needed(conn, table, create_sql, copy_sql):
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if not cols or "group_id" in cols:
        return
    backup = table + "_legacy"
    conn.execute(f"ALTER TABLE {table} RENAME TO {backup}")
    conn.execute(create_sql)
    conn.execute(copy_sql.format(backup=backup))


def init_leader_tables():
    with db_conn() as conn:
        # Group-scoped government tables. Existing single-government data is kept
        # as legacy group 0 so upgrading the bot does not destroy old records.
        _rebuild_table_if_needed(conn, "leader", """CREATE TABLE leader (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            elected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            term_end TEXT,
            popularity INTEGER DEFAULT 100,
            UNIQUE(group_id)
        )""", """INSERT OR IGNORE INTO leader(group_id,user_id,username,first_name,elected_at,term_end,popularity)
            SELECT 0,user_id,username,first_name,elected_at,term_end,popularity FROM {backup}""")
        conn.execute("""CREATE TABLE IF NOT EXISTS leader (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            elected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            term_end TEXT,
            popularity INTEGER DEFAULT 100,
            UNIQUE(group_id)
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS leader_elections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            status TEXT DEFAULT 'candidacy',
            started_by INTEGER,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            vote_start TEXT DEFAULT NULL,
            ended_at TEXT DEFAULT NULL
        )""")
        _add_column_if_missing(conn, "leader_elections", "group_id", "INTEGER NOT NULL DEFAULT 0")

        conn.execute("""CREATE TABLE IF NOT EXISTS leader_candidates (
            election_id INTEGER,
            group_id INTEGER NOT NULL,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            pledges TEXT DEFAULT '',
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (election_id, user_id)
        )""")
        _add_column_if_missing(conn, "leader_candidates", "group_id", "INTEGER NOT NULL DEFAULT 0")

        conn.execute("""CREATE TABLE IF NOT EXISTS leader_votes (
            election_id INTEGER,
            group_id INTEGER NOT NULL,
            voter_id INTEGER,
            candidate_id INTEGER,
            voted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (election_id, voter_id)
        )""")
        _add_column_if_missing(conn, "leader_votes", "group_id", "INTEGER NOT NULL DEFAULT 0")

        conn.execute("""CREATE TABLE IF NOT EXISTS leader_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            command_key TEXT,
            issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            is_active INTEGER DEFAULT 1
        )""")
        _add_column_if_missing(conn, "leader_commands", "group_id", "INTEGER NOT NULL DEFAULT 0")

        conn.execute("""CREATE TABLE IF NOT EXISTS leader_laws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            law_key TEXT,
            law_name TEXT,
            enacted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            is_active INTEGER DEFAULT 1
        )""")
        _add_column_if_missing(conn, "leader_laws", "group_id", "INTEGER NOT NULL DEFAULT 0")

        _rebuild_table_if_needed(conn, "national_treasury", """CREATE TABLE national_treasury (
            group_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0
        )""", """INSERT OR IGNORE INTO national_treasury(group_id,balance)
            SELECT 0,balance FROM {backup} WHERE id=1""")
        conn.execute("""CREATE TABLE IF NOT EXISTS national_treasury (
            group_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS treasury_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            amount REAL,
            reason TEXT,
            user_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        _add_column_if_missing(conn, "treasury_log", "group_id", "INTEGER NOT NULL DEFAULT 0")

        conn.execute("""CREATE TABLE IF NOT EXISTS city_budgets (
            group_id INTEGER PRIMARY KEY,
            amount REAL DEFAULT 0,
            assigned_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        _rebuild_table_if_needed(conn, "national_projects", """CREATE TABLE national_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            project_key TEXT,
            status TEXT DEFAULT 'building',
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            done_at TEXT,
            UNIQUE(group_id, project_key)
        )""", """INSERT OR IGNORE INTO national_projects(group_id,project_key,status,started_at,done_at)
            SELECT 0,project_key,status,started_at,done_at FROM {backup}""")
        conn.execute("""CREATE TABLE IF NOT EXISTS national_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            project_key TEXT,
            status TEXT DEFAULT 'building',
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            done_at TEXT,
            UNIQUE(group_id, project_key)
        )""")

        _rebuild_table_if_needed(conn, "ministers", """CREATE TABLE ministers (
            group_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            appointed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, role)
        )""", """INSERT OR IGNORE INTO ministers(group_id,role,user_id,username,first_name,appointed_at)
            SELECT 0,role,user_id,username,first_name,appointed_at FROM {backup}""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ministers (
            group_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            appointed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, role)
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS national_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            event_key TEXT,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            is_active INTEGER DEFAULT 1
        )""")
        _add_column_if_missing(conn, "national_events", "group_id", "INTEGER NOT NULL DEFAULT 0")

        _rebuild_table_if_needed(conn, "emergency_state", """CREATE TABLE emergency_state (
            group_id INTEGER PRIMARY KEY,
            etype TEXT DEFAULT NULL,
            started_at TEXT DEFAULT NULL,
            expires_at TEXT DEFAULT NULL,
            is_active INTEGER DEFAULT 0
        )""", """INSERT OR IGNORE INTO emergency_state(group_id,etype,started_at,expires_at,is_active)
            SELECT 0,etype,started_at,expires_at,is_active FROM {backup} WHERE id=1""")
        conn.execute("""CREATE TABLE IF NOT EXISTS emergency_state (
            group_id INTEGER PRIMARY KEY,
            etype TEXT DEFAULT NULL,
            started_at TEXT DEFAULT NULL,
            expires_at TEXT DEFAULT NULL,
            is_active INTEGER DEFAULT 0
        )""")

        # leader_ratings needs a composite primary key after the per-group migration.
        # Simply ADD COLUMN group_id is not enough because an old PRIMARY KEY(user_id)
        # would still prevent the same user from rating leaders in different groups.
        lr_cols = {r[1] for r in conn.execute("PRAGMA table_info(leader_ratings)").fetchall()}
        lr_pk = {r[1] for r in conn.execute("PRAGMA table_info(leader_ratings)").fetchall() if r[5]}
        if lr_cols and ("group_id" not in lr_cols or lr_pk != {"group_id", "user_id"}):
            backup = "leader_ratings_legacy"
            # Recover safely if an earlier interrupted migration left the backup behind.
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (backup,)).fetchone():
                conn.execute(f"DROP TABLE {backup}")
            conn.execute("ALTER TABLE leader_ratings RENAME TO leader_ratings_legacy")
            conn.execute("""CREATE TABLE leader_ratings (
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating TEXT,
                rated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (group_id, user_id)
            )""")
            conn.execute("""INSERT OR IGNORE INTO leader_ratings(group_id,user_id,rating,rated_at)
                SELECT 0,user_id,rating,rated_at FROM leader_ratings_legacy""")
        conn.execute("""CREATE TABLE IF NOT EXISTS leader_ratings (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating TEXT,
            rated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, user_id)
        )""")

        for table in ("leader_log", "leader_pledges"):
            if table == "leader_log":
                conn.execute("""CREATE TABLE IF NOT EXISTS leader_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    user_id INTEGER,
                    action_type TEXT,
                    action_desc TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )""")
                _add_column_if_missing(conn, table, "group_id", "INTEGER NOT NULL DEFAULT 0")
            else:
                conn.execute("""CREATE TABLE IF NOT EXISTS leader_pledges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    election_id INTEGER,
                    user_id INTEGER,
                    pledge_text TEXT,
                    fulfilled INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )""")
                _add_column_if_missing(conn, table, "group_id", "INTEGER NOT NULL DEFAULT 0")

        conn.commit()


def get_leader(group_id=None):
    if group_id is None: return None
    with db_conn() as conn:
        return conn.execute("SELECT * FROM leader WHERE group_id=? LIMIT 1", (group_id,)).fetchone()


def set_leader(group_id, user_id, username, first_name, term_days=LEADER_TERM_DAYS):
    term_end = (datetime.now() + timedelta(days=term_days)).isoformat()
    with db_conn() as conn:
        conn.execute("DELETE FROM leader WHERE group_id=?", (group_id,))
        conn.execute("""INSERT INTO leader(group_id,user_id,username,first_name,elected_at,term_end,popularity)
            VALUES (?,?,?,?,?,?,100)""", (group_id,user_id,username,first_name,datetime.now().isoformat(),term_end))
        conn.commit()


def remove_leader(group_id):
    with db_conn() as conn:
        conn.execute("DELETE FROM leader WHERE group_id=?", (group_id,))
        conn.commit()


def is_leader(group_id, user_id):
    ld = get_leader(group_id)
    return ld is not None and ld["user_id"] == user_id


def log_leader(group_id, user_id, action_type, desc):
    with db_conn() as conn:
        conn.execute("INSERT INTO leader_log(group_id,user_id,action_type,action_desc,created_at) VALUES(?,?,?,?,?)",
                     (group_id,user_id,action_type,desc,datetime.now().isoformat()))
        conn.commit()


def get_treasury(group_id=None) -> float:
    if group_id is None: return 0.0
    with db_conn() as conn:
        row = conn.execute("SELECT balance FROM national_treasury WHERE group_id=?", (group_id,)).fetchone()
        if not row:
            conn.execute("INSERT OR IGNORE INTO national_treasury(group_id,balance) VALUES(?,0)", (group_id,))
            conn.commit()
            return 0.0
        return row["balance"]


def change_treasury(group_id, amount: float, reason: str, user_id: int = 0):
    with db_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO national_treasury(group_id,balance) VALUES(?,0)", (group_id,))
        conn.execute("UPDATE national_treasury SET balance=MAX(0,balance+?) WHERE group_id=?", (amount,group_id))
        conn.execute("INSERT INTO treasury_log(group_id,amount,reason,user_id,created_at) VALUES(?,?,?,?,?)",
                     (group_id,amount,reason,user_id,datetime.now().isoformat()))
        conn.commit()


def try_spend_treasury(group_id, amount: float, reason: str, user_id: int = 0) -> bool:
    """Atomically spend from a group's treasury without allowing overdrafts."""
    amount = float(amount)
    if not math.isfinite(amount) or amount <= 0:
        return False
    now = datetime.now().isoformat()
    with db_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO national_treasury(group_id,balance) VALUES(?,0)", (group_id,))
        cur = conn.execute(
            "UPDATE national_treasury SET balance=balance-? WHERE group_id=? AND balance>=?",
            (amount, group_id, amount)
        )
        if cur.rowcount != 1:
            conn.rollback()
            return False
        conn.execute("INSERT INTO treasury_log(group_id,amount,reason,user_id,created_at) VALUES(?,?,?,?,?)",
                     (group_id,-amount,reason,user_id,now))
        conn.commit()
        return True


def get_active_command(group_id):
    with db_conn() as conn:
        return conn.execute("SELECT * FROM leader_commands WHERE group_id=? AND is_active=1 AND datetime(replace(expires_at,'T',' '))>datetime('now') ORDER BY id DESC LIMIT 1", (group_id,)).fetchone()


def get_active_laws(group_id):
    with db_conn() as conn:
        return conn.execute("SELECT * FROM leader_laws WHERE group_id=? AND is_active=1 AND (expires_at IS NULL OR datetime(replace(expires_at,'T',' '))>datetime('now'))", (group_id,)).fetchall()


def get_active_events(group_id):
    with db_conn() as conn:
        return conn.execute("SELECT * FROM national_events WHERE group_id=? AND is_active=1 AND datetime(replace(expires_at,'T',' '))>datetime('now')", (group_id,)).fetchall()


def get_emergency(group_id):
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM emergency_state WHERE group_id=?", (group_id,)).fetchone()
        if row and row["is_active"] and row["expires_at"]:
            if datetime.fromisoformat(row["expires_at"]) > datetime.now(): return row
            conn.execute("UPDATE emergency_state SET is_active=0,etype=NULL WHERE group_id=?", (group_id,)); conn.commit()
        return None


def can_issue_command(group_id):
    with db_conn() as conn:
        row = conn.execute("SELECT issued_at FROM leader_commands WHERE group_id=? ORDER BY id DESC LIMIT 1", (group_id,)).fetchone()
    if not row: return True,0
    diff=(datetime.now()-datetime.fromisoformat(row["issued_at"])).total_seconds()
    left=max(0,int(LEADER_COMMAND_COOLDOWN-diff)); return left==0,left


def get_national_hop_multiplier(group_id):
    mult=1.0; cmd=get_active_command(group_id)
    if cmd:
        cfg=NATIONAL_COMMANDS.get(cmd["command_key"],{}); mult*=cfg.get("hop_mult",1.0)*cfg.get("all_mult",1.0)
    for ev in get_active_events(group_id):
        cfg=NATIONAL_EVENTS.get(ev["event_key"],{}); mult*=cfg.get("hop_mult",1.0)*cfg.get("all_mult",1.0)
    em=get_emergency(group_id)
    if em:
        cfg=EMERGENCY_TYPES.get(em["etype"],{}); mult*=cfg.get("all_mult",1.0)*cfg.get("hop_mult",1.0)
    return mult


def get_national_daily_bonus(group_id):
    bonus=0; cmd=get_active_command(group_id)
    if cmd: bonus+=NATIONAL_COMMANDS.get(cmd["command_key"],{}).get("daily_bonus",0)
    for ev in get_active_events(group_id): bonus+=NATIONAL_EVENTS.get(ev["event_key"],{}).get("daily_bonus",0)
    return bonus


def get_national_cd_multiplier(group_id):
    mult=1.0; cmd=get_active_command(group_id)
    if cmd: mult*=NATIONAL_COMMANDS.get(cmd["command_key"],{}).get("cd_mult",1.0)
    em=get_emergency(group_id)
    if em: mult*=EMERGENCY_TYPES.get(em["etype"],{}).get("cd_mult",1.0)
    return mult


def get_national_dog_multiplier(group_id):
    mult=1.0; cmd=get_active_command(group_id)
    if cmd:
        cfg=NATIONAL_COMMANDS.get(cmd["command_key"],{}); mult*=cfg.get("dog_mult",1.0)*cfg.get("all_mult",1.0)
    for ev in get_active_events(group_id):
        cfg=NATIONAL_EVENTS.get(ev["event_key"],{}); mult*=cfg.get("dog_mult",1.0)*cfg.get("all_mult",1.0)
    em=get_emergency(group_id)
    if em: mult*=EMERGENCY_TYPES.get(em["etype"],{}).get("all_mult",1.0)
    return mult


def get_national_factory_multiplier(group_id):
    mult=1.0; cmd=get_active_command(group_id)
    if cmd:
        cfg=NATIONAL_COMMANDS.get(cmd["command_key"],{}); mult*=cfg.get("factory_mult",1.0)*cfg.get("all_mult",1.0)
    for ev in get_active_events(group_id):
        cfg=NATIONAL_EVENTS.get(ev["event_key"],{}); mult*=cfg.get("factory_mult",1.0)*cfg.get("all_mult",1.0)
    em=get_emergency(group_id)
    if em:
        cfg=EMERGENCY_TYPES.get(em["etype"],{}); mult*=cfg.get("factory_mult",1.0)*cfg.get("all_mult",1.0)
    return mult


async def _is_group_admin(context, group_id, user_id):
    if is_admin(user_id): return True
    try:
        member = await context.bot.get_chat_member(group_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False


async def leader_panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; chat=update.effective_chat
    if not chat or chat.type not in ("group","supergroup"):
        await update.effective_message.reply_text("👑 سیستم حکومت برای هر گروه جداست؛ این دستور را داخل گروه اجرا کن."); return
    gid=chat.id; context.user_data["leader_group_id"]=gid
    ensure_user(user.id,user.username or "",user.first_name); ld=get_leader(gid)
    if await _is_group_admin(context,gid,user.id): await _send_admin_leader_panel(update,context,ld,gid); return
    if ld and ld["user_id"]==user.id: await _send_leader_panel(update,context,ld,gid); return
    if not ld: txt="👑 *رهبر گروه*\n\nهنوز رهبری انتخاب نشده.\nادمین‌های همین گروه می‌تونن انتخابات رهبری رو برگزار کنن."
    else:
        days_left=max(0,(datetime.fromisoformat(ld["term_end"])-datetime.now()).days); cmd=get_active_command(gid); em=get_emergency(gid)
        txt=f"👑 *رهبر گروه*\n\n👤 {ld['first_name']}\n📊 محبوبیت: {ld['popularity']}٪\n⏳ {days_left} روز تا پایان دوره"
        if cmd: txt+=f"\n👑 *فرمان فعال:* {NATIONAL_COMMANDS.get(cmd['command_key'],{}).get('name','—')}"
        if em: txt+=f"\n🚨 *وضعیت اضطراری:* {EMERGENCY_TYPES.get(em['etype'],{}).get('name','—')}"
    kb=[[cbtn("👍 رضایت",f"leader_rate_up_{gid}"),cbtn("👎 نارضایتی",f"leader_rate_down_{gid}")]] if ld else []
    await update.message.reply_text(txt,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb) if kb else None)


async def _send_admin_leader_panel(update_or_query, context, ld, gid):
    is_query=hasattr(update_or_query,"edit_message_text"); send=update_or_query.edit_message_text if is_query else update_or_query.message.reply_text
    has_election=_get_active_election(gid); treasury=get_treasury(gid); ld_txt=f"👤 {ld['first_name']} | محبوبیت: {ld['popularity']}٪" if ld else "❌ رهبری وجود ندارد"
    txt=f"⚙️ *پنل ادمین — حکومت این گروه*\n\n👑 رهبر فعلی: {ld_txt}\n🏦 خزانه: {treasury:,.0f} هاپ‌پوینت\n🗳️ انتخابات: {'فعال ✅' if has_election else 'غیرفعال ❌'}"
    kb=[]
    if not has_election: kb.append([cbtn("🗳️ برگزاری انتخابات رهبری",f"ladmin_start_election_{gid}")])
    else:
        if has_election["status"]=="candidacy": kb.append([cbtn("🗳️ شروع رأی‌گیری",f"ladmin_start_voting_{gid}_{has_election['id']}")])
        elif has_election["status"]=="voting": kb.append([cbtn("✅ اعلام نتیجه و پایان",f"ladmin_end_election_{gid}_{has_election['id']}")])
        kb.append([cbtn("❌ لغو انتخابات",f"ladmin_cancel_election_{gid}_{has_election['id']}")])
    if ld: kb.append([cbtn("🚫 برکناری رهبر",f"ladmin_remove_leader_{gid}")])
    kb += [[cbtn("💰 واریز به خزانه",f"ladmin_treasury_add_{gid}")],[cbtn("📜 لاگ تصمیمات",f"ladmin_view_log_{gid}")]]
    await send(txt,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))


async def _send_leader_panel(update_or_query, context, ld, gid):
    is_query=hasattr(update_or_query,"edit_message_text"); send=update_or_query.edit_message_text if is_query else update_or_query.message.reply_text
    treasury=get_treasury(gid); cmd=get_active_command(gid); em=get_emergency(gid); days_left=max(0,(datetime.fromisoformat(ld["term_end"])-datetime.now()).days); can_cmd,left=can_issue_command(gid)
    cmd_txt=f"فعال: {NATIONAL_COMMANDS.get(cmd['command_key'],{}).get('name','—')}" if cmd else ("✅ آماده" if can_cmd else f"⌛️ {left//3600}:{(left%3600)//60:02d}:00")
    em_txt=f"\n🚨 اضطراری: {EMERGENCY_TYPES.get(em['etype'],{}).get('name','—')}" if em else ""
    txt=f"👑 *پنل رهبر گروه*\n\n📊 محبوبیت: {ld['popularity']}٪\n⏳ {days_left} روز تا پایان دوره\n🏦 خزانه: {treasury:,.0f}\n🎖️ فرمان: {cmd_txt}{em_txt}"
    kb=[[cbtn("👑 فرمان",f"ldr_cmd_menu_{gid}"),cbtn("⚖️ قانون‌گذاری",f"ldr_law_menu_{gid}")],[cbtn("🏦 خزانه",f"ldr_treasury_{gid}"),cbtn("🏛️ بودجه شهرها",f"ldr_budget_{gid}")],[cbtn("🏗️ پروژه‌ها",f"ldr_projects_{gid}"),cbtn("🎉 رویدادها",f"ldr_events_{gid}")],[cbtn("👥 وزیران",f"ldr_ministers_{gid}"),cbtn("🚨 اضطراری",f"ldr_emergency_{gid}")],[cbtn("🏛️ شهرداران",f"ldr_mayors_menu_{gid}"),cbtn("📊 گزارش",f"ldr_report_{gid}")]]
    await send(txt,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))


def _get_active_election(group_id):
    with db_conn() as conn: return conn.execute("SELECT * FROM leader_elections WHERE group_id=? AND status IN ('candidacy','voting') ORDER BY id DESC LIMIT 1",(group_id,)).fetchone()


def _start_election(group_id,started_by):
    with db_conn() as conn:
        conn.execute("INSERT INTO leader_elections(group_id,status,started_by,started_at) VALUES(?, 'candidacy', ?, ?)",(group_id,started_by,datetime.now().isoformat())); conn.commit(); return conn.execute("SELECT last_insert_rowid() id").fetchone()["id"]


def _cancel_election(group_id,election_id=None):
    with db_conn() as conn:
        if election_id is None: conn.execute("UPDATE leader_elections SET status='cancelled',ended_at=? WHERE group_id=? AND status IN ('candidacy','voting')",(datetime.now().isoformat(),group_id))
        else: conn.execute("UPDATE leader_elections SET status='cancelled',ended_at=? WHERE group_id=? AND id=?",(datetime.now().isoformat(),group_id,election_id))
        conn.commit()


def _move_to_voting(group_id,election_id):
    with db_conn() as conn: conn.execute("UPDATE leader_elections SET status='voting',vote_start=? WHERE group_id=? AND id=?",(datetime.now().isoformat(),group_id,election_id)); conn.commit()


def _get_candidates(group_id,election_id):
    with db_conn() as conn: return conn.execute("SELECT * FROM leader_candidates WHERE group_id=? AND election_id=?",(group_id,election_id)).fetchall()


def _get_votes(group_id,election_id):
    with db_conn() as conn: return conn.execute("SELECT candidate_id,COUNT(*) cnt FROM leader_votes WHERE group_id=? AND election_id=? GROUP BY candidate_id ORDER BY cnt DESC",(group_id,election_id)).fetchall()


def _finish_election(group_id,election_id):
    votes=_get_votes(group_id,election_id); candidates={r["user_id"]:r for r in _get_candidates(group_id,election_id)}; winner=None
    if votes:
        top=votes[0]; c=candidates.get(top["candidate_id"])
        if c:
            set_leader(group_id,c["user_id"],c["username"] or "",c["first_name"]); log_leader(group_id,c["user_id"],"elected",f"با {top['cnt']} رأی به رهبری انتخاب شد"); winner=c
    with db_conn() as conn: conn.execute("UPDATE leader_elections SET status='done',ended_at=? WHERE group_id=? AND id=?",(datetime.now().isoformat(),group_id,election_id)); conn.commit()
    return winner


async def handle_leader_callback(query,user,data:str,context)->bool:
    # Every callback carries the group id after the per-group conversion.
    def parts_after(prefix): return data[len(prefix):].split("_")
    gid=_leader_group_id(query,context)

    if data.startswith("ldr_vote_"):
        parts=parts_after("ldr_vote_");
        if len(parts)>=3: gid=int(parts[0]); eid=int(parts[1]); candidate_id=int(parts[2])
        else: return True
        try:
            cm = await context.bot.get_chat_member(gid, user.id)
            if cm.status not in ("creator", "administrator", "member") and not getattr(cm, "is_member", False):
                await query.answer("❌ فقط اعضای همین گروه حق رأی دارند.", show_alert=True); return True
        except Exception:
            await query.answer("❌ عضویت شما در گروه قابل تأیید نیست.", show_alert=True); return True
        with db_conn() as conn:
            elec=conn.execute("SELECT status FROM leader_elections WHERE group_id=? AND id=?",(gid,eid)).fetchone()
            if not elec or elec["status"] != "voting":
                await query.answer("❌ این رأی‌گیری فعال نیست!",show_alert=True); return True
            candidate=conn.execute("SELECT first_name,username FROM leader_candidates WHERE group_id=? AND election_id=? AND user_id=?",(gid,eid,candidate_id)).fetchone()
            if not candidate:
                await query.answer("❌ نامزد نامعتبره!",show_alert=True); return True
            voted=conn.execute("SELECT 1 FROM leader_votes WHERE group_id=? AND election_id=? AND voter_id=?",(gid,eid,user.id)).fetchone()
            if voted: await query.answer("قبلاً رأی دادی!",show_alert=True); return True
            conn.execute("INSERT INTO leader_votes(group_id,election_id,voter_id,candidate_id,voted_at) VALUES(?,?,?,?,?)",(gid,eid,user.id,candidate_id,datetime.now().isoformat())); target=conn.execute("SELECT first_name FROM users WHERE user_id=?",(candidate_id,)).fetchone(); conn.commit()
        name=target["first_name"] if target else str(candidate_id); await query.answer(f"✅ رأیت به {name} ثبت شد!",show_alert=True); return True

    # Admin actions for the current group.
    if data.startswith("ladmin_"):
        raw=data[len("ladmin_"):].split("_"); action=raw[0]; gid2=int(raw[1]) if len(raw)>1 and raw[1].lstrip('-').isdigit() else gid
        if not await _is_group_admin(context,gid2,user.id): await query.answer("❌ فقط ادمین همین گروه!",show_alert=True); return True
        if action=="start" and len(raw)>=3 and raw[1]=="election":
            gid2=int(raw[2])
            if _get_active_election(gid2): await query.answer("انتخابات قبلاً فعاله!",show_alert=True); return True
            eid=_start_election(gid2,user.id); log_leader(gid2,user.id,"start_election",f"انتخابات رهبری #{eid} شروع شد")
            await query.edit_message_text("🗳️ *انتخابات رهبری این گروه شروع شد!*\n\nبا /leaderjoin نامزد شوید.",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 پنل",f"ladmin_panel_{gid2}")]])); return True
        if action=="cancel" and len(raw)>=4 and raw[1]=="election":
            gid2=int(raw[2]); eid=int(raw[3])
            if not await _is_group_admin(context,gid2,user.id): await query.answer("❌ فقط ادمین همین گروه!",show_alert=True); return True
            elec=_get_active_election(gid2)
            if not elec or elec["id"] != eid:
                await query.answer("❌ این انتخابات دیگر فعال نیست!",show_alert=True); return True
            _cancel_election(gid2,eid); log_leader(gid2,user.id,"cancel_election","انتخابات لغو شد"); await _send_admin_leader_panel(query,context,get_leader(gid2),gid2); return True
        if action=="start" and len(raw)>=4 and raw[1]=="voting":
            gid2=int(raw[2]); eid=int(raw[3]);
            if not await _is_group_admin(context,gid2,user.id): await query.answer("❌ فقط ادمین همین گروه!",show_alert=True); return True
            elec=_get_active_election(gid2)
            if not elec or elec["id"] != eid or elec["status"] != "candidacy":
                await query.answer("❌ این مرحله از انتخابات دیگر فعال نیست!",show_alert=True); return True
            candidates=_get_candidates(gid2,eid)
            if len(candidates)<LEADER_MIN_CANDIDATES: await query.answer(f"❌ حداقل {LEADER_MIN_CANDIDATES} نامزد لازمه!",show_alert=True); return True
            _move_to_voting(gid2,eid); await query.edit_message_text("🗳️ *رأی‌گیری رهبری شروع شد!*\n\nبا /leadervote رأی دهید.",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("✅ اعلام نتیجه",f"ladmin_end_election_{gid2}_{eid}")]])); return True
        if action=="end" and len(raw)>=4 and raw[1]=="election":
            gid2=int(raw[2]); eid=int(raw[3]);
            if not await _is_group_admin(context,gid2,user.id): await query.answer("❌ فقط ادمین همین گروه!",show_alert=True); return True
            elec=_get_active_election(gid2)
            if not elec or elec["id"] != eid or elec["status"] != "voting":
                await query.answer("❌ رأی‌گیری این انتخابات فعال نیست!",show_alert=True); return True
            winner=_finish_election(gid2,eid); txt=f"🎉 *رهبر جدید:* {winner['first_name']}" if winner else "⚠️ برنده‌ای مشخص نشد."; await query.edit_message_text(txt,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 پنل",f"ladmin_panel_{gid2}")]])); return True
        if action=="remove" and len(raw)>=3 and raw[1]=="leader":
            gid2=int(raw[2])
            if not await _is_group_admin(context,gid2,user.id): await query.answer("❌ فقط ادمین همین گروه!",show_alert=True); return True
            ld=get_leader(gid2); remove_leader(gid2); await query.edit_message_text(f"✅ {ld['first_name'] if ld else 'رهبر'} برکنار شد.",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 پنل",f"ladmin_panel_{gid2}")]])); return True
        if action=="treasury" and len(raw)>=3 and raw[1]=="add":
            try:
                gid2=int(raw[2])
            except ValueError:
                await query.answer("❌ گروه نامعتبر است!",show_alert=True); return True
            if not await _is_group_admin(context,gid2,user.id):
                await query.answer("❌ فقط ادمین همین گروه!",show_alert=True); return True
            context.user_data.update(leader_input="admin_treasury_add",leader_group_id=gid2,leader_input_chat_id=gid2)
            await query.edit_message_text("💰 مبلغ واریز به خزانه را بنویس:",reply_markup=InlineKeyboardMarkup([[cbtn("❌ انصراف",f"ladmin_panel_{gid2}")]]))
            return True
        if action=="panel": await _send_admin_leader_panel(query,context,get_leader(gid2),gid2); return True
        if action=="view" and len(raw)>=3 and raw[1]=="log":
            try:
                gid2=int(raw[2])
            except ValueError:
                await query.answer("❌ گروه نامعتبر است!",show_alert=True); return True
            if not await _is_group_admin(context,gid2,user.id):
                await query.answer("❌ فقط ادمین همین گروه!",show_alert=True); return True
            with db_conn() as conn: rows=conn.execute("SELECT * FROM leader_log WHERE group_id=? ORDER BY id DESC LIMIT 10",(gid2,)).fetchall()
            txt="📜 *آخرین تصمیمات این گروه:*\n\n"+"\n".join(f"• {r['created_at'][:16]} — {r['action_type']}: {r['action_desc']}" for r in rows) if rows else "📜 لاگی ثبت نشده."; await query.edit_message_text(txt,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 پنل",f"ladmin_panel_{gid2}")]])); return True
        return True

    # All normal leader callbacks use gid encoded in the button.
    if data.startswith("ldr_"):
        tail=data[4:].split("_");
        if tail and tail[-1].lstrip('-').isdigit(): gid=int(tail[-1])
        if not is_leader(gid,user.id) and not await _is_group_admin(context,gid,user.id): await query.answer("❌ فقط رهبر همین گروه!",show_alert=True); return True

    if data.startswith("ldr_back_"):
        ld=get_leader(gid); await _send_leader_panel(query,context,ld,gid) if ld else await _send_admin_leader_panel(query,context,None,gid); return True
    if data.startswith("ldr_cmd_menu_"):
        can,left=can_issue_command(gid); cmd=get_active_command(gid)
        if cmd: await query.edit_message_text(f"👑 *فرمان فعال:* {NATIONAL_COMMANDS.get(cmd['command_key'],{}).get('name','—')}",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت",f"ldr_back_{gid}")]])); return True
        if not can: await query.answer(f"⌛️ {left//3600} ساعت و {(left%3600)//60} دقیقه",show_alert=True); return True
        kb=[[cbtn(cfg["name"],f"ldr_issue_cmd_{gid}_{key}")] for key,cfg in NATIONAL_COMMANDS.items()]; kb.append([cbtn("🔙 بازگشت",f"ldr_back_{gid}")]); await query.edit_message_text("👑 *فرمان این گروه را انتخاب کن:*",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb)); return True
    if data.startswith("ldr_issue_cmd_"):
        x=data.replace("ldr_issue_cmd_","").split("_"); gid=int(x[0]); key="_".join(x[1:]); cfg=NATIONAL_COMMANDS.get(key)
        if not cfg: return True
        can_cmd,left=can_issue_command(gid)
        if not can_cmd:
            await query.answer(f"⌛️ هنوز {left//3600} ساعت و {(left%3600)//60} دقیقه تا فرمان بعدی مونده!",show_alert=True); return True
        now=datetime.now(); expires=(now+timedelta(seconds=LEADER_COMMAND_DURATION)).isoformat()
        with db_conn() as conn: conn.execute("UPDATE leader_commands SET is_active=0 WHERE group_id=?",(gid,)); conn.execute("INSERT INTO leader_commands(group_id,command_key,issued_at,expires_at,is_active) VALUES(?,?,?,?,1)",(gid,key,now.isoformat(),expires)); conn.commit()
        log_leader(gid,user.id,"command",f"فرمان ملی: {cfg['name']}"); await query.edit_message_text(f"✅ *فرمان صادر شد!*\n\n{cfg['name']}\n📢 {cfg['desc']}",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت",f"ldr_back_{gid}")]])); return True
    if data.startswith("ldr_law_menu_"):
        active={r["law_key"] for r in get_active_laws(gid)}; kb=[[cbtn(("✅ " if k in active else "")+c["name"],f"ldr_revoke_law_{gid}_{k}" if k in active else f"ldr_enact_law_{gid}_{k}")] for k,c in NATIONAL_LAWS.items()]; kb.append([cbtn("🔙 بازگشت",f"ldr_back_{gid}")]); await query.edit_message_text("⚖️ *قوانین این گروه*",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb)); return True
    if data.startswith("ldr_enact_law_") or data.startswith("ldr_revoke_law_"):
        pre="ldr_enact_law_" if data.startswith("ldr_enact_law_") else "ldr_revoke_law_"; x=data[len(pre):].split("_"); gid=int(x[0]); key="_".join(x[1:])
        with db_conn() as conn:
            if pre.startswith("ldr_enact"):
                active=conn.execute("SELECT 1 FROM leader_laws WHERE group_id=? AND law_key=? AND is_active=1",(gid,key)).fetchone()
                if active:
                    await query.answer("این قانون از قبل فعاله!",show_alert=True); return True
                conn.execute("INSERT INTO leader_laws(group_id,law_key,law_name,enacted_at,is_active) VALUES(?,?,?,?,1)",(gid,key,NATIONAL_LAWS.get(key,{}).get("name",key),datetime.now().isoformat()))
            else: conn.execute("UPDATE leader_laws SET is_active=0 WHERE group_id=? AND law_key=?",(gid,key))
            conn.commit()
        await query.answer("✅ انجام شد",show_alert=True); return await handle_leader_callback(query,user,f"ldr_law_menu_{gid}",context)
    if data.startswith("ldr_treasury_spend_"):
        context.user_data.update(leader_input="treasury_spend",leader_group_id=gid,leader_input_chat_id=gid); await query.edit_message_text("💸 مقدار و دلیل را بنویس: مقدار|دلیل",reply_markup=InlineKeyboardMarkup([[cbtn("❌ انصراف",f"ldr_treasury_{gid}")]])); return True
    if data.startswith("ldr_treasury_"):
        bal=get_treasury(gid); await query.edit_message_text(f"🏦 *خزانه این گروه*\n\n💰 {bal:,.0f} هاپ",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("💸 مصرف",f"ldr_treasury_spend_{gid}")],[cbtn("🔙 بازگشت",f"ldr_back_{gid}")]])); return True
    if data.startswith("ldr_projects_"):
        with db_conn() as conn: rows={r["project_key"]:r for r in conn.execute("SELECT * FROM national_projects WHERE group_id=?",(gid,)).fetchall()}
        kb=[]
        for key,cfg in NATIONAL_PROJECTS.items(): kb.append([cbtn(("✅ " if key in rows and rows[key]["status"]=="done" else "🏗️ ")+cfg["name"],f"ldr_build_proj_{gid}_{key}")])
        kb.append([cbtn("🔙 بازگشت",f"ldr_back_{gid}")]); await query.edit_message_text("🏗️ *پروژه‌های این گروه*",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb)); return True
    if data.startswith("ldr_build_proj_"):
        x=data.replace("ldr_build_proj_","").split("_"); gid=int(x[0]); key="_".join(x[1:]); cfg=NATIONAL_PROJECTS.get(key)
        if not cfg: return True
        with db_conn() as conn:
            existing=conn.execute("SELECT status FROM national_projects WHERE group_id=? AND project_key=?",(gid,key)).fetchone()
        if existing:
            if existing["status"] == "building":
                await query.answer("⏳ این پروژه همین الان در حال ساخته شدنه!",show_alert=True); return True
            if existing["status"] == "done":
                await query.answer("✅ این پروژه قبلاً تکمیل شده!",show_alert=True); return True
        bal=get_treasury(gid)
        if bal<cfg["cost"]: await query.answer(f"❌ خزانه کافی نیست: {bal:,.0f}",show_alert=True); return True
        now=datetime.now(); done=(now+timedelta(hours=cfg["build_hours"])).isoformat()
        if not try_spend_treasury(gid,cfg["cost"],f"ساخت {cfg['name']}",user.id):
            await query.answer("❌ موجودی خزانه در همین لحظه کافی نیست!",show_alert=True); return True
        with db_conn() as conn: conn.execute("INSERT OR REPLACE INTO national_projects(group_id,project_key,status,started_at,done_at) VALUES(?,?,?,?,?)",(gid,key,"building",now.isoformat(),done)); conn.commit()
        await query.edit_message_text(f"🏗️ *ساخت شروع شد:* {cfg['name']}",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت",f"ldr_projects_{gid}")]])); return True
    if data.startswith("ldr_events_"):
        active={e["event_key"] for e in get_active_events(gid)}; kb=[[cbtn(("✅ " if k in active else "🎉 ")+c["name"],f"ldr_event_info_{gid}_{k}" if k in active else f"ldr_launch_event_{gid}_{k}")] for k,c in NATIONAL_EVENTS.items()]; kb.append([cbtn("🔙 بازگشت",f"ldr_back_{gid}")]); await query.edit_message_text("🎉 *رویدادهای این گروه*",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb)); return True
    if data.startswith("ldr_launch_event_"):
        x=data.replace("ldr_launch_event_","").split("_"); gid=int(x[0]); key="_".join(x[1:]); cfg=NATIONAL_EVENTS.get(key)
        if not cfg: return True
        if any(e["event_key"] == key for e in get_active_events(gid)):
            await query.answer("❌ این رویداد همین الان فعاله!",show_alert=True); return True
        bal=get_treasury(gid)
        if bal<cfg["cost"]: await query.answer("❌ خزانه کافی نیست!",show_alert=True); return True
        now=datetime.now(); exp=(now+timedelta(hours=cfg["hours"])).isoformat()
        if not try_spend_treasury(gid,cfg["cost"],f"رویداد {cfg['name']}",user.id):
            await query.answer("❌ موجودی خزانه در همین لحظه کافی نیست!",show_alert=True); return True
        with db_conn() as conn: conn.execute("INSERT INTO national_events(group_id,event_key,started_at,expires_at,is_active) VALUES(?,?,?,?,1)",(gid,key,now.isoformat(),exp)); conn.commit()
        await query.edit_message_text(f"🎉 *رویداد شروع شد:* {cfg['name']}",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت",f"ldr_events_{gid}")]])); return True
    if data.startswith("ldr_event_info_"):
        return True
    if data.startswith("ldr_ministers_"):
        with db_conn() as conn: mrows={r["role"]:r for r in conn.execute("SELECT * FROM ministers WHERE group_id=?",(gid,)).fetchall()}
        kb=[[cbtn(("✏️ تغییر " if role in mrows else "➕ انتصاب ")+cfg["name"],f"ldr_set_minister_{gid}_{role}")] for role,cfg in MINISTER_ROLES.items()]; kb.append([cbtn("🔙 بازگشت",f"ldr_back_{gid}")]); txt="👥 *شورای وزیران این گروه*\n\n"+"\n".join(f"• {c['name']}: {mrows[r]['first_name'] if r in mrows else 'خالی'}" for r,c in MINISTER_ROLES.items()); await query.edit_message_text(txt,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb)); return True
    if data.startswith("ldr_set_minister_"):
        x=data.replace("ldr_set_minister_","").split("_"); gid=int(x[0]); role="_".join(x[1:])
        if role not in MINISTER_ROLES:
            await query.answer("❌ سمت وزیر نامعتبر است.", show_alert=True); return True
        context.user_data.update(leader_input="set_minister",leader_group_id=gid,leader_minister_role=role,leader_input_chat_id=gid); await query.edit_message_text("👤 یوزرنیم یا آیدی عددی بازیکن را بنویس:",reply_markup=InlineKeyboardMarkup([[cbtn("❌ انصراف",f"ldr_ministers_{gid}")]])); return True
    if data.startswith("ldr_emergency_"):
        em=get_emergency(gid)
        if em: await query.edit_message_text(f"🚨 *{EMERGENCY_TYPES.get(em['etype'],{}).get('name','—')}*",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت",f"ldr_back_{gid}")]])); return True
        kb=[[cbtn(c["name"],f"ldr_declare_emergency_{gid}_{k}")] for k,c in EMERGENCY_TYPES.items()]; kb.append([cbtn("🔙 بازگشت",f"ldr_back_{gid}")]); await query.edit_message_text("🚨 *وضعیت اضطراری*",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb)); return True
    if data.startswith("ldr_declare_emergency_"):
        x=data.replace("ldr_declare_emergency_","").split("_"); gid=int(x[0]); etype="_".join(x[1:]); cfg=EMERGENCY_TYPES.get(etype)
        if not cfg: return True
        if get_emergency(gid):
            await query.answer("❌ یک وضعیت اضطراری از قبل فعاله!",show_alert=True); return True
        now=datetime.now(); exp=(now+timedelta(hours=cfg["hours"])).isoformat()
        with db_conn() as conn: conn.execute("INSERT OR REPLACE INTO emergency_state(group_id,etype,started_at,expires_at,is_active) VALUES(?,?,?,?,1)",(gid,etype,now.isoformat(),exp)); conn.commit()
        await query.edit_message_text(f"🚨 *وضعیت اعلام شد:* {cfg['name']}",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت",f"ldr_back_{gid}")]])); return True
    if data.startswith("ldr_mayors_menu_"):
        with db_conn() as conn: m=conn.execute("SELECT * FROM mayor WHERE group_id=?",(gid,)).fetchone()
        kb=[]
        if m:
            kb.append([cbtn(f"🏙️ {m['first_name']}",f"ldr_mayor_action_{gid}")]); txt=f"🏛️ *شهردار این گروه:* {m['first_name']}"
        else:
            txt="🏛️ *شهردار این گروه*\n\n⚠️ هنوز شهرداری انتخاب نشده."
        kb.append([cbtn("🔙 بازگشت",f"ldr_back_{gid}")]); await query.edit_message_text(txt,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb)); return True
    if data.startswith("ldr_mayor_action_"):
        with db_conn() as conn: m=conn.execute("SELECT * FROM mayor WHERE group_id=?",(gid,)).fetchone()
        if not m: await query.answer("شهردار پیدا نشد",show_alert=True); return True
        kb=[[cbtn("⚠️ اخطار به شهردار",f"ldr_warn_mayor_{gid}")],[cbtn("💸 کاهش بودجه",f"ldr_cut_budget_{gid}")],[cbtn("🗳️ انتخابات زودهنگام",f"ldr_early_election_{gid}")],[cbtn("🚫 برکناری شهردار",f"ldr_fire_mayor_{gid}")],[cbtn("🔙 بازگشت",f"ldr_mayors_menu_{gid}")]]
        await query.edit_message_text(f"🏙️ *شهردار:* {m['first_name']}\n📊 محبوبیت: {m['popularity'] if 'popularity' in m.keys() else 100}٪",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb)); return True
    if data.startswith("ldr_report_"):
        with db_conn() as conn:
            cc=conn.execute("SELECT COUNT(*) c FROM leader_commands WHERE group_id=?",(gid,)).fetchone()["c"]; lc=conn.execute("SELECT COUNT(*) c FROM leader_laws WHERE group_id=? AND is_active=1",(gid,)).fetchone()["c"]; pc=conn.execute("SELECT COUNT(*) c FROM national_projects WHERE group_id=? AND status='done'",(gid,)).fetchone()["c"]; ec=conn.execute("SELECT COUNT(*) c FROM national_events WHERE group_id=?",(gid,)).fetchone()["c"]; spent=conn.execute("SELECT SUM(ABS(amount)) s FROM treasury_log WHERE group_id=? AND amount<0",(gid,)).fetchone()["s"] or 0
        ld=get_leader(gid); await query.edit_message_text(f"📊 *گزارش حکومت این گروه*\n\n👑 فرمان‌ها: {cc}\n⚖️ قوانین فعال: {lc}\n🏗️ پروژه‌های تکمیل‌شده: {pc}\n🎉 رویدادها: {ec}\n💸 هزینه‌ها: {spent:,.0f}\n📊 محبوبیت: {ld['popularity'] if ld else 0}٪",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([[cbtn("🔙 بازگشت",f"ldr_back_{gid}")]])); return True
    if data.startswith("leader_rate_up_") or data.startswith("leader_rate_down_"):
        try:
            gid=int(data.rsplit("_",1)[1])
        except (ValueError, IndexError):
            await query.answer("❌ دکمه نامعتبر است!",show_alert=True); return True
        if getattr(query.message, "chat", None) and query.message.chat.type in ("group","supergroup") and query.message.chat.id != gid:
            await query.answer("❌ این دکمه متعلق به این گروه نیست!",show_alert=True); return True
        ld=get_leader(gid)
        if not ld: await query.answer("رهبری وجود ندارد",show_alert=True); return True
        with db_conn() as conn:
            if conn.execute("SELECT 1 FROM leader_ratings WHERE group_id=? AND user_id=?",(gid,user.id)).fetchone(): await query.answer("قبلاً رأی دادی!",show_alert=True); return True
            rating="up" if data.startswith("leader_rate_up_") else "down"; conn.execute("INSERT INTO leader_ratings(group_id,user_id,rating,rated_at) VALUES(?,?,?,?)",(gid,user.id,rating,datetime.now().isoformat())); conn.execute("UPDATE leader SET popularity=MAX(0,MIN(100,popularity+?)) WHERE group_id=?",(2 if rating=="up" else -2,gid)); conn.commit()
        await query.answer("✅ رضایت ثبت شد!",show_alert=True); return True
    return False


async def handle_leader_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.text: return False
    user=update.effective_user; text=update.message.text.strip(); inp=context.user_data.get("leader_input"); gid=context.user_data.get("leader_group_id"); origin_chat=context.user_data.get("leader_input_chat_id")
    if not inp or not gid: return False
    current_chat=getattr(update.effective_chat,"id",None)
    if origin_chat is not None and current_chat != origin_chat:
        await update.message.reply_text("❌ این پاسخ باید داخل همان گروهی ارسال شود که درخواست را شروع کردی.")
        return True
    if inp=="admin_treasury_add" and await _is_group_admin(context,gid,user.id):
        context.user_data.pop("leader_input",None); context.user_data.pop("leader_input_chat_id",None)
        try: amount=float(text.replace(",",""))
        except ValueError: await update.message.reply_text("❌ عدد معتبر وارد کن!"); return True
        if not math.isfinite(amount) or amount <= 0:
            await update.message.reply_text("❌ مبلغ باید یک عدد مثبت و معتبر باشد!"); return True
        change_treasury(gid,amount,"واریز ادمین",user.id); await update.message.reply_text(f"✅ {amount:,.0f} به خزانه این گروه اضافه شد!"); return True
    if inp=="treasury_spend" and is_leader(gid,user.id):
        context.user_data.pop("leader_input",None); context.user_data.pop("leader_input_chat_id",None); parts=text.split("|",1)
        if len(parts)!=2: await update.message.reply_text("❌ فرمت: مقدار|دلیل"); return True
        try: amount=float(parts[0].strip().replace(",",""))
        except ValueError: await update.message.reply_text("❌ مقدار معتبر نیست"); return True
        if not math.isfinite(amount) or amount <= 0:
            await update.message.reply_text("❌ مقدار باید یک عدد مثبت و معتبر باشد!"); return True
        reason=parts[1].strip()
        if not reason:
            await update.message.reply_text("❌ دلیل برداشت را هم وارد کن!"); return True
        if not try_spend_treasury(gid,amount,reason,user.id):
            bal=get_treasury(gid); await update.message.reply_text(f"❌ موجودی کافی نیست! {bal:,.0f}"); return True
        log_leader(gid,user.id,"spend",f"{amount:,.0f} برای {reason}"); await update.message.reply_text(f"✅ {amount:,.0f} از خزانه برداشت شد."); return True
    if inp=="set_minister" and is_leader(gid,user.id):
        role=context.user_data.pop("leader_minister_role",None); context.user_data.pop("leader_input",None); context.user_data.pop("leader_input_chat_id",None); cfg=MINISTER_ROLES.get(role,{})
        with db_conn() as conn:
            target=conn.execute("SELECT * FROM users WHERE user_id=?",(int(text),)).fetchone() if text.isdigit() else conn.execute("SELECT * FROM users WHERE username=?",(text.lstrip("@"),)).fetchone()
            if not target: await update.message.reply_text("❌ کاربر پیدا نشد!"); return True
            conn.execute("INSERT OR REPLACE INTO ministers(group_id,role,user_id,username,first_name,appointed_at) VALUES(?,?,?,?,?,?)",(gid,role,target["user_id"],target["username"],target["first_name"],datetime.now().isoformat())); conn.commit()
        await update.message.reply_text(f"✅ {target['first_name']} به عنوان {cfg.get('name',role)} منصوب شد!"); return True
    return False


async def leaderjoin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; gid=_leader_group_id(update,context)
    if gid is None: await update.message.reply_text("❌ این دستور را داخل گروه اجرا کن."); return
    elec=_get_active_election(gid)
    if not elec or elec["status"]!="candidacy": await update.message.reply_text("❌ الان انتخابات رهبری این گروه در جریان نیست."); return
    eid=elec["id"]
    with db_conn() as conn:
        if conn.execute("SELECT 1 FROM leader_candidates WHERE group_id=? AND election_id=? AND user_id=?",(gid,eid,user.id)).fetchone(): await update.message.reply_text("✅ قبلاً ثبت‌نام کردی!"); return
        conn.execute("INSERT INTO leader_candidates(group_id,election_id,user_id,username,first_name) VALUES(?,?,?,?,?)",(gid,eid,user.id,user.username or "",user.first_name)); conn.commit()
    await update.message.reply_text(f"✅ {user.first_name}، نامزدیت در انتخابات رهبری این گروه ثبت شد!")


async def leadervote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; gid=_leader_group_id(update,context)
    if gid is None: await update.message.reply_text("❌ این دستور را داخل گروه اجرا کن."); return
    elec=_get_active_election(gid)
    if not elec or elec["status"]!="voting": await update.message.reply_text("❌ الان رأی‌گیری این گروه در جریان نیست."); return
    eid=elec["id"]
    with db_conn() as conn:
        if conn.execute("SELECT 1 FROM leader_votes WHERE group_id=? AND election_id=? AND voter_id=?",(gid,eid,user.id)).fetchone(): await update.message.reply_text("✅ قبلاً رأی دادی!"); return
    candidates=_get_candidates(gid,eid); kb=[[cbtn(f"👤 {c['first_name']}",f"ldr_vote_{gid}_{eid}_{c['user_id']}")] for c in candidates]
    await update.message.reply_text("🗳️ *رأی‌گیری رهبری این گروه*\n\nنامزد مورد نظرت رو انتخاب کن:",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))


async def leader_auto_jobs(context):
    now=datetime.now()
    with db_conn() as conn:
        done=conn.execute("SELECT * FROM national_projects WHERE status='building' AND done_at<=?",(now.isoformat(),)).fetchall()
        for p in done:
            conn.execute("UPDATE national_projects SET status='done' WHERE id=?",(p["id"],)); cfg=NATIONAL_PROJECTS.get(p["project_key"],{}); gid=p["group_id"]
            try: await context.bot.send_message(gid,f"🎉 *پروژه این گروه تکمیل شد!*\n\n{cfg.get('name','—')}\n✅ {cfg.get('desc','')}",parse_mode="Markdown")
            except Exception:
                logger.warning("Non-fatal exception was suppressed", exc_info=True)
        conn.execute("UPDATE leader_commands SET is_active=0 WHERE is_active=1 AND expires_at<=?",(now.isoformat(),)); conn.execute("UPDATE national_events SET is_active=0 WHERE is_active=1 AND expires_at<=?",(now.isoformat(),)); conn.commit()


# =========================
# Happy Doggy 2.8 - Seasons & Leagues
# =========================
SEASON_REWARDS = {
    "bronze": 5_000,
    "silver": 15_000,
    "gold": 35_000,
    "platinum": 75_000,
    "diamond": 150_000,
    "master": 300_000,
}
SEASON_LEAGUES = [
    (0, "bronze", "🥉 برنز", "Bronze"),
    (1000, "silver", "🥈 نقره", "Silver"),
    (2000, "gold", "🥇 طلا", "Gold"),
    (3500, "platinum", "💠 پلاتین", "Platinum"),
    (5000, "diamond", "💎 الماس", "Diamond"),
    (7000, "master", "👑 مستر", "Master"),
]
SEASON_ACTIVITY = {
    "hop": 2,
    "daily_login": 8,
    "mission": 12,
    "clan_war": 20,
    "dog": 5,
    "fishing": 5,
}


def season_key_for(dt=None):
    dt = dt or datetime.now()
    return dt.strftime("%Y-%m")


def season_bounds(key):
    y, m = map(int, key.split("-"))
    start = datetime(y, m, 1)
    if m == 12:
        end = datetime(y + 1, 1, 1)
    else:
        end = datetime(y, m + 1, 1)
    return start, end


def season_league(rating):
    league = SEASON_LEAGUES[0]
    for row in SEASON_LEAGUES:
        if rating >= row[0]:
            league = row
    return league[1], league[2], league[3]



# ==================== 2.9 SEASON PASS ====================
SEASON_PASS_TIERS = [
    (1, 0, 1500, None), (2, 150, 2000, None), (3, 300, 2500, "golden_paw"),
    (4, 450, 3000, None), (5, 600, 3500, None), (6, 800, 4000, "lucky_bone"),
    (7, 1000, 5000, None), (8, 1200, 5500, None), (9, 1400, 6000, "mystery_tag"),
    (10, 1600, 7500, None), (11, 1800, 8000, None), (12, 2000, 9000, "gold_collar"),
    (13, 2250, 10000, None), (14, 2500, 11000, None), (15, 2750, 12500, "factory_gear"),
    (16, 3000, 14000, None), (17, 3250, 15000, None), (18, 3500, 17000, "lucky_bone"),
    (19, 3750, 18000, None), (20, 4000, 20000, None), (21, 4300, 22500, "golden_paw"),
    (22, 4600, 25000, None), (23, 4900, 27500, None), (24, 5200, 30000, "gold_collar"),
    (25, 5500, 35000, None), (26, 6000, 40000, "factory_gear"), (27, 6500, 50000, None),
    (28, 7000, 65000, "mythic_essence"), (29, 7600, 80000, None),
    (30, 8300, 120000, "mystery_tag"),
]


def season_pass_level(rating):
    level = 0
    for tier, needed, *_ in SEASON_PASS_TIERS:
        if rating >= needed:
            level = tier
        else:
            break
    return level


def init_season_pass_tables():
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS season_pass_claims (
            season_key TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            tier INTEGER NOT NULL,
            claimed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (season_key, user_id, tier)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_season_pass_claims_user ON season_pass_claims(season_key,user_id)")
        conn.commit()


def season_pass_claim(user_id, key, tier):
    if tier < 1 or tier > len(SEASON_PASS_TIERS):
        return None, "شماره مرحله باید بین ۱ تا ۳۰ باشد."
    with db_conn() as conn:
        season = conn.execute("SELECT status FROM seasons WHERE season_key=?", (key,)).fetchone()
        if not season or season['status'] != 'active':
            return None, "فقط در فصل فعال می‌توان پاداش پاس فصل را گرفت."
        stats = conn.execute("SELECT rating FROM season_user_stats WHERE season_key=? AND user_id=?", (key,user_id)).fetchone()
        rating = int(stats['rating']) if stats else 0
        row = next(x for x in SEASON_PASS_TIERS if x[0] == tier)
        _, needed, hops, item = row
        if rating < needed:
            return None, f"برای مرحله {tier} به {needed:,} امتیاز فصل نیاز داری."
        if conn.execute("SELECT 1 FROM season_pass_claims WHERE season_key=? AND user_id=? AND tier=?", (key,user_id,tier)).fetchone():
            return None, "این پاداش قبلاً دریافت شده است."
        conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (hops,user_id))
        if item and item in RARE_ITEMS:
            conn.execute("""INSERT INTO inventory(user_id,item_key,quantity) VALUES(?,?,1)
                ON CONFLICT(user_id,item_key) DO UPDATE SET quantity=quantity+1""", (user_id,item))
        elif item:
            # Keep unknown/removed item keys from breaking the claim flow.
            item = None
        conn.execute("INSERT INTO season_pass_claims(season_key,user_id,tier) VALUES(?,?,?)", (key,user_id,tier))
        conn.commit()
    return (tier, hops, item), None


async def season_pass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or '', user.first_name)
    key = ensure_current_season()
    parts = (update.effective_message.text or '').strip().split()
    stats = season_user_stats(user.id, key)
    rating = int(stats['rating']) if stats else 0
    level = season_pass_level(rating)
    if len(parts) >= 2 and parts[1].lower() in ('دریافت','claim','گرفتن'):
        try:
            tier = int(parts[2]) if len(parts) >= 3 else level
        except ValueError:
            tier = level
        if tier <= 0:
            await update.effective_message.reply_text('❌ هنوز به اولین مرحله پاس فصل نرسیده‌ای.')
            return
        result, err = season_pass_claim(user.id, key, tier)
        if err:
            await update.effective_message.reply_text('❌ ' + err)
            return
        t, hops, item = result
        extra = f"\n🎁 آیتم: {RARE_ITEMS[item]['name']}" if item else ''
        await update.effective_message.reply_text(f'🎉 مرحله {t} پاس فصل دریافت شد!\n💰 +{hops:,} هاپ{extra}')
        return
    claimed = set()
    with db_conn() as conn:
        rows = conn.execute("SELECT tier FROM season_pass_claims WHERE season_key=? AND user_id=?", (key,user.id)).fetchall()
        claimed = {int(r['tier']) for r in rows}
    lines=[]
    for tier, needed, hops, item in SEASON_PASS_TIERS:
        if tier <= level and tier not in claimed:
            status='🎁 آماده دریافت'
        elif tier in claimed:
            status='✅ دریافت شد'
        else:
            status='🔒 قفل'
        item_name = f" + {RARE_ITEMS[item]['name']}" if item and item in RARE_ITEMS else ''
        lines.append(f"{tier:02d}. {needed:,} امتیاز → 💰 {hops:,}{item_name} — {status}")
    await update.effective_message.reply_text(
        f"🎫 *پاس فصل {key}*\n\n📊 امتیاز: *{rating:,}*\n🏅 سطح پاس: *{level}/30*\n\n" + '\n'.join(lines) +
        "\n\n🎁 `فصل پاس دریافت` — دریافت آخرین پاداش قابل‌گرفتن\n🎁 `فصل پاس دریافت 10` — دریافت مرحله مشخص",
        parse_mode='Markdown')

def init_season_tables():
    with db_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS seasons (
            season_key TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ends_at TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS season_user_stats (
            season_key TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER DEFAULT 0,
            activity_points INTEGER DEFAULT 0,
            last_activity TEXT,
            PRIMARY KEY (season_key, user_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS season_clan_stats (
            season_key TEXT NOT NULL,
            clan_id INTEGER NOT NULL,
            rating INTEGER DEFAULT 0,
            war_wins INTEGER DEFAULT 0,
            war_losses INTEGER DEFAULT 0,
            war_draws INTEGER DEFAULT 0,
            PRIMARY KEY (season_key, clan_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS season_user_claims (
            season_key TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            claimed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (season_key, user_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS season_clan_claims (
            season_key TEXT NOT NULL,
            clan_id INTEGER NOT NULL,
            claimed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (season_key, clan_id)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_season_user_rating ON season_user_stats(season_key,rating DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_season_clan_rating ON season_clan_stats(season_key,rating DESC)")
        conn.commit()
    ensure_current_season()


def ensure_current_season():
    key = season_key_for()
    start, end = season_bounds(key)
    with db_conn() as conn:
        conn.execute("UPDATE seasons SET status='ended' WHERE status='active' AND ends_at<=?", (datetime.now().isoformat(),))
        row = conn.execute("SELECT * FROM seasons WHERE season_key=?", (key,)).fetchone()
        if not row:
            conn.execute("INSERT INTO seasons(season_key,title,started_at,ends_at,status) VALUES(?,?,?,?, 'active')",
                         (key, f"فصل {key}", start.isoformat(), end.isoformat()))
        else:
            conn.execute("UPDATE seasons SET status='active' WHERE season_key=?", (key,))
        conn.commit()
    return key


def season_record_user(user_id, action="hop", amount=1):
    if amount <= 0:
        return
    key = ensure_current_season()
    pts = int(SEASON_ACTIVITY.get(action, 1) * amount)
    with db_conn() as conn:
        conn.execute("""INSERT INTO season_user_stats(season_key,user_id,rating,activity_points,last_activity)
            VALUES(?,?,?, ?,?)
            ON CONFLICT(season_key,user_id) DO UPDATE SET
                rating=rating+excluded.rating,
                activity_points=activity_points+excluded.activity_points,
                last_activity=excluded.last_activity""",
            (key, user_id, pts, pts, datetime.now().isoformat()))
        conn.commit()


def season_record_clan(clan_id, delta, result=None):
    if not clan_id or delta == 0:
        return
    key = ensure_current_season()
    with db_conn() as conn:
        conn.execute("""INSERT INTO season_clan_stats(season_key,clan_id,rating)
            VALUES(?,?,?) ON CONFLICT(season_key,clan_id) DO UPDATE SET rating=rating+excluded.rating""",
            (key, clan_id, int(delta)))
        if result in ("win", "loss", "draw"):
            conn.execute(f"UPDATE season_clan_stats SET war_{result}s=war_{result}s+1 WHERE season_key=? AND clan_id=?" if result != 'loss' else
                         "UPDATE season_clan_stats SET war_losses=war_losses+1 WHERE season_key=? AND clan_id=?", (key, clan_id))
        conn.commit()


def season_user_stats(user_id, key=None):
    key = key or ensure_current_season()
    with db_conn() as conn:
        return conn.execute("SELECT * FROM season_user_stats WHERE season_key=? AND user_id=?", (key, user_id)).fetchone()


def season_clan_stats(clan_id, key=None):
    key = key or ensure_current_season()
    with db_conn() as conn:
        return conn.execute("SELECT * FROM season_clan_stats WHERE season_key=? AND clan_id=?", (key, clan_id)).fetchone()


def season_reward_for_rating(rating):
    league, label, _ = season_league(int(rating or 0))
    return league, label, SEASON_REWARDS[league]


def season_user_rank(user_id, key=None):
    key = key or ensure_current_season()
    with db_conn() as conn:
        row = conn.execute("SELECT rating FROM season_user_stats WHERE season_key=? AND user_id=?", (key, user_id)).fetchone()
        if not row:
            return 0
        rank = conn.execute("SELECT COUNT(*)+1 AS r FROM season_user_stats WHERE season_key=? AND rating>?", (key, row['rating'])).fetchone()['r']
        return int(rank)


def season_clan_rank(clan_id, key=None):
    key = key or ensure_current_season()
    with db_conn() as conn:
        row = conn.execute("SELECT rating FROM season_clan_stats WHERE season_key=? AND clan_id=?", (key, clan_id)).fetchone()
        if not row:
            return 0
        rank = conn.execute("SELECT COUNT(*)+1 AS r FROM season_clan_stats WHERE season_key=? AND rating>?", (key, row['rating'])).fetchone()['r']
        return int(rank)


def season_claim_user(user_id, key):
    with db_conn() as conn:
        season = conn.execute("SELECT * FROM seasons WHERE season_key=? AND status='ended'", (key,)).fetchone()
        if not season:
            return None, "این فصل هنوز تمام نشده."
        stats = conn.execute("SELECT * FROM season_user_stats WHERE season_key=? AND user_id=?", (key, user_id)).fetchone()
        if not stats:
            return None, "برای این فصل سابقه‌ای نداری."
        if conn.execute("SELECT 1 FROM season_user_claims WHERE season_key=? AND user_id=?", (key, user_id)).fetchone():
            return None, "جایزه این فصل قبلاً دریافت شده."
        league, label, reward = season_reward_for_rating(stats['rating'])
        conn.execute("UPDATE users SET hop_points=hop_points+? WHERE user_id=?", (reward, user_id))
        conn.execute("INSERT INTO season_user_claims(season_key,user_id) VALUES(?,?)", (key, user_id))
        conn.commit()
    return (league, label, reward, int(stats['rating'])), None


def season_claim_clan(clan_id, key):
    with db_conn() as conn:
        season = conn.execute("SELECT * FROM seasons WHERE season_key=? AND status='ended'", (key,)).fetchone()
        if not season:
            return None, "این فصل هنوز تمام نشده."
        stats = conn.execute("SELECT * FROM season_clan_stats WHERE season_key=? AND clan_id=?", (key, clan_id)).fetchone()
        if not stats:
            return None, "کلن برای این فصل سابقه‌ای ندارد."
        if conn.execute("SELECT 1 FROM season_clan_claims WHERE season_key=? AND clan_id=?", (key, clan_id)).fetchone():
            return None, "جایزه کلن این فصل قبلاً دریافت شده."
        league, label, reward = season_reward_for_rating(stats['rating'])
        reward *= 3
        conn.execute("UPDATE clans SET treasury=treasury+? WHERE clan_id=?", (reward, clan_id))
        conn.execute("INSERT INTO season_clan_claims(season_key,clan_id) VALUES(?,?)", (key, clan_id))
        conn.commit()
    return (league, label, reward, int(stats['rating'])), None


async def season_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or '', user.first_name)
    key = ensure_current_season()
    parts = (update.effective_message.text or '').strip().split()
    if len(parts) >= 2 and parts[1].lower() in ('رتبه', 'top', 'leaderboard'):
        with db_conn() as conn:
            users = conn.execute("""SELECT s.rating,u.first_name,u.username FROM season_user_stats s
                LEFT JOIN users u ON u.user_id=s.user_id WHERE s.season_key=? ORDER BY s.rating DESC LIMIT 10""", (key,)).fetchall()
            clans = conn.execute("""SELECT s.rating,c.name,c.tag FROM season_clan_stats s
                LEFT JOIN clans c ON c.clan_id=s.clan_id WHERE s.season_key=? ORDER BY s.rating DESC LIMIT 10""", (key,)).fetchall()
        txt = f"🏆 *لیدربرد فصل {key}*\n\n👤 *بازیکنان*\n"
        txt += ''.join(f"{i}. {r['first_name'] or r['username'] or 'بازیکن'} — {r['rating']:,} امتیاز | {season_league(r['rating'])[2]}\n" for i,r in enumerate(users,1)) or "هنوز رکوردی ثبت نشده.\n"
        txt += "\n🏰 *کلن‌ها*\n"
        txt += ''.join(f"{i}. {r['name']} [{r['tag']}] — {r['rating']:,} امتیاز | {season_league(r['rating'])[2]}\n" for i,r in enumerate(clans,1)) or "هنوز کلنی در جدول نیست."
        await update.effective_message.reply_text(txt, parse_mode='Markdown')
        return
    if len(parts) >= 2 and parts[1].lower() in ('جایزه', 'reward', 'claim'):
        target_key = parts[2] if len(parts) >= 3 else None
        if not target_key:
            with db_conn() as conn:
                prev = conn.execute("SELECT season_key FROM seasons WHERE status='ended' ORDER BY season_key DESC LIMIT 1").fetchone()
            target_key = prev['season_key'] if prev else None
        if not target_key:
            await update.effective_message.reply_text('❌ هنوز فصل قبلی وجود ندارد.')
            return
        result, err = season_claim_user(user.id, target_key)
        if err:
            await update.effective_message.reply_text('❌ ' + err)
        else:
            league, label, reward, rating = result
            await update.effective_message.reply_text(f'🎉 *جایزه فصل {target_key} دریافت شد!*\n\n{label}\n📊 امتیاز: {rating:,}\n💰 +{reward:,} هاپ', parse_mode='Markdown')
        return
    stats = season_user_stats(user.id, key)
    rating = int(stats['rating']) if stats else 0
    league, label, reward = season_reward_for_rating(rating)
    rank = season_user_rank(user.id, key)
    _, end = season_bounds(key)
    remaining = max(0, int((end - datetime.now()).total_seconds()))
    days = remaining // 86400
    hours = (remaining % 86400) // 3600
    await update.effective_message.reply_text(
        f"🏆 *فصل {key}*\n\n{label}\n📊 امتیاز فصل: *{rating:,}*\n🏅 رتبه: *#{rank}*\n\n"
        f"🎁 جایزه پایان فصل فعلی: *{reward:,}* هاپ\n⏳ زمان باقی‌مانده: *{days} روز و {hours} ساعت*\n\n"
        "📈 با فعالیت، مأموریت، هاپ و جنگ کلنی امتیاز بگیر.\n"
        "🏆 `فصل رتبه` — جدول\n🎁 `فصل جایزه` — دریافت جایزه فصل تمام‌شده",
        parse_mode='Markdown')


async def season_league_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or '', user.first_name)
    key = ensure_current_season()
    with db_conn() as conn:
        stats = conn.execute("SELECT rating FROM season_user_stats WHERE season_key=? AND user_id=?", (key,user.id)).fetchone()
    rating = int(stats['rating']) if stats else 0
    league, label, _ = season_reward_for_rating(rating)
    lines=[]
    for threshold, lk, lbl, en in SEASON_LEAGUES:
        reward=SEASON_REWARDS[lk]
        next_threshold=None
        for t,*_ in SEASON_LEAGUES:
            if t>threshold: next_threshold=t; break
        target=f"تا {next_threshold-1:,}" if next_threshold else "+"
        lines.append(f"{lbl}: {threshold:,} {target} → 🎁 {reward:,}")
    await update.effective_message.reply_text(
        f"🏅 *لیگ فصل {key}*\n\nلیگ فعلی تو: *{label}*\nامتیاز: *{rating:,}*\n\n" + '\n'.join(lines), parse_mode='Markdown')


def season_settle_jobs():
    # Ensure the monthly season exists and automatically close expired seasons.
    return ensure_current_season()

def _is_important_bot_message(message):
    """پیام‌های مهم مثل آگهی و رویدادهای جنگ را از پاکسازی خودکار مستثنی می‌کند."""
    try:
        text = (getattr(message, "text", "") or getattr(message, "caption", "") or "").strip().lower()
        if not text:
            return False
        return any(keyword.lower() in text for keyword in BOT_AUTO_CLEANUP_KEEP_KEYWORDS)
    except Exception:
        return False


async def _track_bot_message_for_cleanup(message):
    """ثبت پیام‌های غیرمهم ربات در گروه‌ها برای حذف خودکار."""
    if not BOT_AUTO_CLEANUP_ENABLED or not message:
        return
    try:
        chat = message.chat
        if not chat or chat.type not in ("group", "supergroup"):
            return
        # پیام‌های مهم را نگه می‌داریم و اصلاً وارد صف حذف نمی‌کنیم.
        if _is_important_bot_message(message):
            return
        delete_at = (datetime.now() + timedelta(seconds=BOT_AUTO_CLEANUP_SECONDS)).isoformat()
        with db_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO bot_cleanup_messages(chat_id, message_id, delete_at) VALUES (?,?,?)",
                (chat.id, message.message_id, delete_at)
            )
            conn.commit()
    except Exception:
        logger.exception("Failed to track bot message for cleanup")


async def bot_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """حذف پیام‌های قدیمی ربات و پاک کردن رکوردهای مصرف‌شده."""
    if not BOT_AUTO_CLEANUP_ENABLED:
        return

    now_iso = datetime.now().isoformat()
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT chat_id, message_id FROM bot_cleanup_messages WHERE delete_at <= ? ORDER BY delete_at LIMIT ?",
            (now_iso, BOT_AUTO_CLEANUP_BATCH)
        ).fetchall()

    for row in rows:
        try:
            await context.bot.delete_message(chat_id=row["chat_id"], message_id=row["message_id"])
        except Exception as exc:
            # پیام ممکن است قبلاً توسط ادمین/تلگرام حذف شده باشد یا ربات دسترسی حذف نداشته باشد.
            logger.debug("Could not delete bot message %s/%s: %s", row["chat_id"], row["message_id"], exc)
        finally:
            with db_conn() as conn:
                conn.execute(
                    "DELETE FROM bot_cleanup_messages WHERE chat_id=? AND message_id=?",
                    (row["chat_id"], row["message_id"])
                )
                conn.commit()


class CleanupTrackingBot(ExtBot):
    """ExtBot سازگار با python-telegram-bot که پیام‌های ارسالی ربات را ثبت می‌کند.

    در نسخه‌های جدید PTB، متدهای Bot روی نمونه قابل جایگزینی نیستند؛ بنابراین
    به‌جای monkey-patch کردن app.bot، از subclass استفاده می‌کنیم.
    """

    async def _track_result(self, result):
        if result is not None and hasattr(result, "message_id"):
            await _track_bot_message_for_cleanup(result)
        return result

    async def send_message(self, *args, **kwargs):
        return await self._track_result(await super().send_message(*args, **kwargs))

    async def send_photo(self, *args, **kwargs):
        return await self._track_result(await super().send_photo(*args, **kwargs))

    async def send_video(self, *args, **kwargs):
        return await self._track_result(await super().send_video(*args, **kwargs))

    async def send_document(self, *args, **kwargs):
        return await self._track_result(await super().send_document(*args, **kwargs))

    async def send_animation(self, *args, **kwargs):
        return await self._track_result(await super().send_animation(*args, **kwargs))

    async def send_audio(self, *args, **kwargs):
        return await self._track_result(await super().send_audio(*args, **kwargs))

    async def send_voice(self, *args, **kwargs):
        return await self._track_result(await super().send_voice(*args, **kwargs))

    async def send_sticker(self, *args, **kwargs):
        return await self._track_result(await super().send_sticker(*args, **kwargs))


_INSTANCE_LOCK_HANDLE = None

def acquire_instance_lock(path: str = "happy_bot.lock"):
    """Prevent accidental duplicate bot/job workers on the same host."""
    global _INSTANCE_LOCK_HANDLE
    try:
        import fcntl
        handle = open(path, "w", encoding="utf-8")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        handle.write(str(os.getpid()))
        handle.flush()
        _INSTANCE_LOCK_HANDLE = handle
        return True
    except ImportError:
        logger.warning("fcntl is unavailable; single-instance protection is disabled on this platform")
        return True
    except BlockingIOError:
        logger.error("Another Happy Doggy instance is already running")
        return False
    except OSError:
        logger.exception("Could not acquire instance lock")
        return False

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, InsufficientPointsError):
        logger.info("Rejected insufficient-balance operation: %s", context.error)
        text = "💰 موجودی هاپ کافی نیست؛ عملیات انجام نشد و موجودی شما تغییر نکرد."
    else:
        logger.error("Unhandled Telegram update error", exc_info=context.error)
        text = "⚠️ یک خطای موقت رخ داد. عملیات شما ثبت نشد؛ دوباره تلاش کن."
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(text)
    except Exception:
        logger.debug("Could not send global error message", exc_info=True)

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set")
    if not acquire_instance_lock():
        raise RuntimeError("Another Happy Doggy instance is already running")
    init_db()
    init_economy_ledger()
    init_city_advanced_tables()
    init_casino_tables()
    init_season_tables()
    init_season_pass_tables()

    cleanup_bot = CleanupTrackingBot(token=BOT_TOKEN)
    app = Application.builder().bot(cleanup_bot).build()
    app.add_error_handler(global_error_handler)

    # 🧹 پیام‌های غیرمهم ربات در گروه ثبت می‌شوند تا بعد از ۵ دقیقه پاک شوند؛ آگهی و جنگ مستثنی هستند.
    app.job_queue.run_repeating(bot_cleanup_job, interval=30, first=30)

    async def complete_projects(context):
        from datetime import datetime
        with db_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM mayor_projects WHERE status='building' AND datetime(replace(done_at,'T',' ')) <= datetime('now')"
            ).fetchall()
            for p in rows:
                conn.execute("UPDATE mayor_projects SET status='done' WHERE id=? AND status='building'", (p["id"],))
                proj = CITY_PROJECTS.get(p["project_key"])
                if proj:
                    try:
                        await context.bot.send_message(
                            p["group_id"],
                            f"🎉 *پروژه تکمیل شد!*\n\n{proj['name']} سطح {p['level']}\n✅ {proj['desc']} فعال شد!",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        logger.warning("Could not announce completed project %s", p["id"], exc_info=True)
            conn.commit()

    app.job_queue.run_repeating(complete_projects, interval=300, first=10)
    app.job_queue.run_repeating(leader_auto_jobs, interval=300, first=15)
    async def auto_settle_clan_wars(context):
        settle_clan_wars()
    app.job_queue.run_repeating(auto_settle_clan_wars, interval=300, first=60)

    async def auto_season_job(context):
        season_settle_jobs()
    app.job_queue.run_repeating(auto_season_job, interval=3600, first=120)
    app.job_queue.run_repeating(city_adv_daily_job, interval=86400, first=86400)

    async def auto_expire_crises(context):
        expired = expire_old_crises()
        for row in expired:
            c = CRISIS_TYPES.get(row["crisis_type"], {})
            try:
                await context.bot.send_message(
                    row["group_id"],
                    f"⚠️ *بحران بدون مدیریت ماند!*\n\n"
                    f"{c.get('name', row['crisis_type'])}\n\n"
                    f"شهردار تصمیم نگرفت و شهر جریمه شد:\n"
                    f"❌ {c.get('penalty', '—')}",
                    parse_mode="Markdown"
                )
            except Exception:
                logger.warning("Could not announce expired crisis for group %s", row["group_id"], exc_info=True)

    app.job_queue.run_repeating(auto_expire_crises, interval=60, first=30)

    async def daily_economy_jobs(context):
        with db_conn() as conn:
            rich_users = conn.execute(
                "SELECT user_id, hop_points FROM users WHERE hop_points > 600_000_000"
            ).fetchall()
            for u in rich_users:
                tax = int(u["hop_points"] * 0.01)
                conn.execute(
                    "UPDATE users SET hop_points = hop_points - ? WHERE user_id = ?",
                    (tax, u["user_id"])
                )
            conn.commit()

    from datetime import time as dtime
    app.job_queue.run_daily(daily_economy_jobs, time=dtime(3, 0, 0))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("missions", missions_cmd))
    app.add_handler(CommandHandler("inventory", inventory_cmd))
    app.add_handler(CommandHandler("mystery", mystery_cmd))
    app.add_handler(CommandHandler("collection", collection_cmd))
    app.add_handler(CommandHandler("kalakshan", collection_cmd))
    app.add_handler(CommandHandler("collectionrewards", collection_rewards_cmd))
    app.add_handler(CommandHandler("event", seasonal_event_cmd))
    app.add_handler(CommandHandler("trade", trade_cmd))
    app.add_handler(CommandHandler("barter", barter_cmd))
    app.add_handler(CommandHandler("auction", auction_cmd))
    app.add_handler(CommandHandler("bid", auction_bid_cmd))
    app.add_handler(CommandHandler("events", seasonal_event_cmd))
    app.add_handler(CommandHandler("dogtypes", dog_types_cmd))
    app.add_handler(CommandHandler("clan", clan_cmd))
    app.add_handler(CommandHandler("clanwar", clan_war_cmd))
    app.add_handler(CommandHandler("season", season_cmd))
    app.add_handler(CommandHandler("league", season_league_cmd))
    app.add_handler(CommandHandler("seasonpass", season_pass_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("lottery", lottery_panel_cmd))
    app.add_handler(CommandHandler("panel", lottery_panel_cmd))
    app.add_handler(CommandHandler("invite", referral_invite_cmd))
    app.add_handler(CommandHandler("ref", referral_invite_cmd))
    app.add_handler(CommandHandler("leaderjoin", leaderjoin_cmd))
    app.add_handler(CommandHandler("leadervote", leadervote_cmd))

    app.add_handler(MessageHandler(
        filters.Regex(r"^[هH][اa][پp]$") & filters.ChatType.GROUPS,
        handle_hop
    ))


    app.add_handler(MessageHandler(
        filters.Regex(r"^کلن(?:\s+.*)?$") & filters.ChatType.GROUPS,
        clan_cmd
    ))

    app.add_handler(MessageHandler(
        filters.Regex(r"^فصل(?:\s+.*)?$") & filters.ChatType.GROUPS,
        season_cmd
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r"^فصل پاس(?:\s+.*)?$") & filters.ChatType.GROUPS,
        season_pass_cmd
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r"^لیگ$") & filters.ChatType.GROUPS,
        season_league_cmd
    ))

    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
        handle_group_text_full
    ))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & ~filters.COMMAND,
        private_message
    ))
    app.add_handler(CallbackQueryHandler(callback_handler_full))

    logger.info("🐕 ربات هاپی شروع به کار کرد!")
    app.run_polling()

if __name__ == "__main__":
    main()
