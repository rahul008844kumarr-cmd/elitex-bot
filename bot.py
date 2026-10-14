#!/usr/bin/env python3
"""ELITE X CONFIG — Combined Premium Telegram Store Bot (aiogram style + all PTB features).

Style: premium aiogram bot with fancy typography, tg-emoji premium IDs, FSM, FamPay + Binance gateways.
Features merged from all provided files:
- Category / Product / Plan / Key management
- Manual balance requests with proof + admin approval
- Product order QR + proof + admin approval → key delivery
- Coupon system, Daily gift, Referral system
- VIP Club, Reseller system, Co-Admin, Ownership transfer
- Payment settings (UPI, Payee, Static QR, ZapUPI, Binance Pay)
- Message editor for every public text
- Link manager, API manager, Broadcast, Maintenance mode
- User manager (add/remove balance, ban/warn, VIP toggle)
- Emoji & UI text editors
"""

import asyncio
import sqlite3
import random
import logging
import time
import os
import io
import string
import aiohttp
import hmac
import hashlib
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, BufferedInputFile
)

try:
    import qrcode
except ImportError:
    qrcode = None

# ==============================================================================
# 1. BOT CONFIGURATION & CONSTANTS
# ==============================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "elitexconfighosting_bot")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "@elitexconfig")
BRAND_NAME = os.getenv("BRAND_NAME", "ELITE X CONFIG")

FAMPAY_API_KEY = os.getenv("FAMPAY_API_KEY", "")
FAMPAY_QR_URL = os.getenv("FAMPAY_QR_URL", "https://fampay.api/qr.php")
FAMPAY_VERIFY_URL = os.getenv("FAMPAY_VERIFY_URL", "https://fampay.api/verify.php")

DB_PATH = os.getenv("DB_PATH", "Sandii.db")

USDT_TO_INR = 90.0
VIP_DISCOUNT_PERCENTAGE = 10.0
VIP_PRICE_INR = 1000.0

WELCOME_STICKER_ID = os.getenv("WELCOME_STICKER_ID", "")

FIXED_CATEGORIES = [
    "ANDROID NON ROOT PANEL",
    "ANDROID ROOT PANEL",
    "PC PANEL",
]

CATEGORY_SLOT_MAP = {
    "ANDROID NON ROOT PANEL": "category_android_non_root",
    "ANDROID ROOT PANEL": "category_android_root",
    "PC PANEL": "category_pc",
}

DEFAULT_EMOJIS = {
    'product_store': '6163205892834598715',
    'profile': '5258011929993026890',
    'add_balance': '5985630530111020079',
    'history': '6032594876506312598',
    'support': '5967280668885913944',
    'back': '5877536313623711363',
    'upi': '5807750375033278838',
    'reseller': '5886505193180239900',
    'tutorial': '6005986106703613755',
    'telegram': '5875465628285931233',
    'whatsapp': '5954224165874569584',
    'welcome': '5994502837327892086',
    'vip': '5206607081334906820',
    'category_android_non_root': '6161172706856282588',
    'category_android_root': '6161449831031118974',
    'category_pc': '5350554349074391003',
    'grid_id': '5474625972751837256',
    'name': '5215399540814781035',
    'account_level': '6129584162992034014',
    'regular_user': '5904630315946611415',
    'wallet': '6210859306602995217',
    'current_balance': '5316711376876485361',
    'global_stats': '6161437856662298090',
    'total_orders': '6160968017304888311',
    'total_spent': '5197503331215361533',
    'joined_grid': '5433614043006903194',
    'info_icon': '6037421444789440735',
    'check_icon': '6161241250239356403',
    'checkbox_icon': '6161437856662298090',
    'shield_icon': '6086672466132865380',
    'money_icon': '5890848474563352982',
    'redeem_icon': '5377624166436445368',
    'wallet_left': '6210859306602995217',
    'wallet_right': '5305699699204837855',
    'point_down': '6161302621027049305',
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot_activity.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN is missing. Set it in .env file.")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


# ==============================================================================
# 2. HELPERS
# ==============================================================================
def fmt_curr(amount: float) -> str:
    return f"₹{amount:,.2f}"


def fancy(text: str) -> str:
    bold_caps = {chr(ord("A") + i): chr(0x1D400 + i) for i in range(26)}
    small_caps = {
        "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ",
        "f": "ꜰ", "g": "ɢ", "h": "ʜ", "i": "ɪ", "j": "ᴊ",
        "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ", "o": "ᴏ",
        "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "s", "t": "ᴛ",
        "u": "ᴜ", "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ", "z": "ᴢ",
    }
    value = str(text)
    out = []
    at_word_start = True
    for ch in value:
        if ch.isascii() and ch.isalpha():
            if at_word_start:
                out.append(bold_caps.get(ch.upper(), ch))
                at_word_start = False
            else:
                out.append(small_caps.get(ch.lower(), ch))
        else:
            out.append(ch)
            if ch.isspace() or ch in "/\\|•":
                at_word_start = True
    return "".join(out)


def safe_float(val, default=0.0):
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def rand_code(n: int = 8) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))


def build_upi_link(upi_id: str, payee_name: str, amount: float, note: str = "") -> str:
    base = "upi://pay?pa=" + quote(upi_id) + "&pn=" + quote(payee_name)
    base += "&am={:.2f}&cu=INR".format(amount)
    if note:
        base += "&tn=" + quote(note)
    return base


def generate_qr_bytes(data: str):
    if qrcode is None:
        return None
    img = qrcode.make(data)
    buf = io.BytesIO()
    buf.name = "qr.png"
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ==============================================================================
# 3. DATABASE
# ==============================================================================
def db_query(query: str, params: tuple = (), fetchone: bool = False,
             fetchall: bool = False, commit: bool = True) -> Any:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetchone:
            res = c.fetchone()
        elif fetchall:
            res = c.fetchall()
        else:
            res = None
        if commit:
            conn.commit()
        return res
    except Exception as e:
        logger.error(f"DB Error: {e} | Query: {query} | Params: {params}")
        if commit:
            conn.rollback()
        return None
    finally:
        conn.close()


def get_setting(key: str, default: str = "") -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return val[0] if val and val[0] else default


def set_setting(key: str, value: str) -> None:
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


def log_activity(user_id: int, action: str, details: str = "") -> None:
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_query(
            "INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, ts),
        )
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")


def get_emoji(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    emoji_id = stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'
    return "✨"


def get_emoji_icon(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    return stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))


def get_ui_text(key: str, **kwargs) -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (f"ui_{key}",), fetchone=True)
    template = val[0] if val and val[0] else UI_TEXTS.get(key, "")

    emoji_map = {
        '{product_store}': get_emoji('product_store'),
        '{profile}': get_emoji('profile'),
        '{add_balance}': get_emoji('add_balance'),
        '{history}': get_emoji('history'),
        '{tutorial}': get_emoji('tutorial'),
        '{support}': get_emoji('support'),
        '{telegram}': get_emoji('telegram'),
        '{whatsapp}': get_emoji('whatsapp'),
        '{upi}': get_emoji('upi'),
        '{binance}': get_emoji('binance'),
        '{info_icon}': get_emoji('info_icon'),
        '{check_icon}': get_emoji('check_icon'),
        '{checkbox_icon}': get_emoji('checkbox_icon'),
        '{shield_icon}': get_emoji('shield_icon'),
        '{money_icon}': get_emoji('money_icon'),
        '{redeem_icon}': get_emoji('redeem_icon'),
        '{wallet_left}': get_emoji('wallet_left'),
        '{wallet_right}': get_emoji('wallet_right'),
        '{point_down}': get_emoji('point_down'),
        '{welcome}': get_emoji('welcome'),
        '{vip}': get_emoji('vip'),
        '{reseller}': get_emoji('reseller'),
    }
    for placeholder, emoji_tag in emoji_map.items():
        template = template.replace(placeholder, emoji_tag)

    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing formatting key for template {key}: {e}")
    return template


# ==============================================================================
# 4. STRING RESOURCES
# ==============================================================================
UI_TEXTS = {
    "start_menu": (
        "{welcome} <b>✦ ELITE X CONFIG ✦</b>\n"
        "<i>Premium Digital Marketplace</i>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "{product_store} <b>𝗣𝗿𝗼𝗱𝘂𝗰𝘁 𝗦𝘁𝗼𝗿𝗲</b>\n"
        "╰ <i>Instant key delivery, 24/7</i>\n\n"
        "{profile} <b>𝗠𝘆 𝗣𝗿𝗼𝗳𝗶𝗹𝗲</b>\n"
        "╰ <i>Account, wallet and purchase history</i>\n\n"
        "{add_balance} <b>𝗔𝗱𝗱 𝗕𝗮𝗹𝗮𝗻𝗰𝗲</b>\n"
        "╰ <i>Secure and instant UPI deposits</i>\n\n"
        "{tutorial} <b>𝗧𝘂𝘁𝗼𝗿𝗶𝗮𝗹</b>\n"
        "╰ <i>Learn how to use this bot</i>\n\n"
        "{support} <b>𝗦𝘂𝗽𝗽𝗼𝗿𝘁</b>\n"
        "╰ <i>Fast help from our team</i>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "{point_down} <i>Select an option below</i>"
    ),
    "vip_menu": (
        "{vip} <b>✦ 𝗩𝗜𝗣 𝗠𝗘𝗠𝗕𝗘𝗥𝗦𝗛𝗜𝗣 𝗖𝗟𝗨𝗕 ✦</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "<i>Unlock permanent discounts and exclusive perks.</i>\n\n"
        "💎 <b>𝗩𝗜𝗣 𝗕𝗲𝗻𝗲𝗳𝗶𝘁𝘀</b>\n"
        f"╰ Flat {VIP_DISCOUNT_PERCENTAGE:g}% off on ALL products <i>(stacks with Reseller)</i>\n"
        "╰ Priority support\n"
        "╰ Exclusive VIP-only giveaways\n\n"
        f"💳 <b>𝗩𝗜𝗣 𝗣𝗿𝗶𝗰𝗲</b> ┃ {fmt_curr(VIP_PRICE_INR)} <i>(Lifetime)</i>\n"
        "👤 <b>𝗬𝗼𝘂𝗿 𝗦𝘁𝗮𝘁𝘂𝘀</b> ┃ {vip_status}"
    ),
    "add_balance_menu": (
        "{add_balance} <b>✦ 𝗔𝗗𝗗 𝗕𝗔𝗟𝗔𝗡𝗖𝗘 ✦</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "{info_icon} <i>Choose your preferred payment method</i>\n\n"
        "{upi} <b>𝗨𝗣𝗜</b> ┃ <i>Fast Indian payments</i> {check_icon}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "{shield_icon} <i>All payments are verified securely</i>"
    ),
    "welcome_default": (
        "⚡ <b>ELITE X CONFIG</b> ⚡\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎉 Welcome to the <b>ELITE X CONFIG Store</b>!\n\n"
        "🛍️ Browse categories and products\n"
        "💰 Add balance using QR payment\n"
        "🔑 Keys delivered after admin approval\n"
        "🎧 Need help? Open Support\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 <i>Choose an option below to continue</i>"
    ),
    "category_default": "📂 <b>Select a Category</b>\n\n👇 Choose from below:",
    "product_default": "📦 <b>Select a Product</b>\n\n👇 Choose from below:",
    "key_default": "🎉 Thank you for your purchase!",
    "profile_default": "👤 <b>My Profile</b>",
    "orders_default": "📦 <b>My Orders</b>",
    "support_default": "🎧 <b>Support Center</b>\n\nClick below to contact support:",
    "balance_default": "💰 <b>Add Balance</b>\n\n👇 Select amount to add:",
    "maintenance_default": "🛠️ <b>Bot Under Maintenance</b>\n\nWe'll be back soon. Please try again later.",
}


# ==============================================================================
# 5. DB INIT & MIGRATION
# ==============================================================================
def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, phone TEXT, first_name TEXT, username TEXT,
            balance REAL DEFAULT 0.0, account_type TEXT DEFAULT 'Regular',
            orders_count INTEGER DEFAULT 0, spent REAL DEFAULT 0.0, last_spin TEXT,
            joined_date TEXT, is_reseller INTEGER DEFAULT 0, reseller_since TEXT,
            total_saved REAL DEFAULT 0.0, is_banned INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0, vip_since TEXT,
            referral_earned REAL DEFAULT 0.0, last_gift TEXT DEFAULT '',
            referred_by INTEGER DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            emoji TEXT NOT NULL DEFAULT '📂', visible INTEGER NOT NULL DEFAULT 1,
            subtitle TEXT NOT NULL DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, panel_name TEXT DEFAULT '',
            name TEXT, price_inr REAL, reseller_price REAL DEFAULT 0.0,
            stock INTEGER, apk_link TEXT, validity TEXT DEFAULT 'Lifetime',
            device_limit TEXT DEFAULT '1 Device', is_active INTEGER DEFAULT 1,
            description TEXT DEFAULT '', discount INTEGER DEFAULT 0,
            api_id INTEGER DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS product_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER,
            key_text TEXT, is_used INTEGER DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            product_name TEXT, price_paid REAL, delivered_key TEXT,
            purchase_date TEXT, status TEXT DEFAULT 'delivered',
            proof_file_id TEXT DEFAULT '', payment_method TEXT DEFAULT 'wallet',
            username TEXT DEFAULT '', reviewed_at TEXT DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS balance_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            username TEXT DEFAULT '', amount REAL, method TEXT DEFAULT 'qr',
            proof_file_id TEXT DEFAULT '', reference TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT,
            status TEXT DEFAULT 'Open', created_at TEXT
        )
    ''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY, amount REAL, uses_left INTEGER,
            discount REAL DEFAULT 0, max_uses INTEGER DEFAULT 1,
            used INTEGER DEFAULT 0, expires_at TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''CREATE TABLE IF NOT EXISTS redeemed (user_id INTEGER, code TEXT)''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            order_id TEXT PRIMARY KEY, user_id INTEGER, amount_inr REAL,
            status TEXT, timestamp INTEGER, qr_url TEXT, upi_id TEXT, expires_at INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS crypto_txns (
            txid TEXT PRIMARY KEY, user_id INTEGER, amount_usdt REAL, timestamp INTEGER
        )
    ''')

    c.execute('''CREATE TABLE IF NOT EXISTS spin_rewards (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL)''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            action TEXT, details TEXT, timestamp TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            amount_delta REAL, note TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''CREATE TABLE IF NOT EXISTS co_admins (user_id INTEGER PRIMARY KEY, name TEXT DEFAULT '', added_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS apis (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT DEFAULT '', api_key TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS broadcasts (id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT, sent_to INTEGER DEFAULT 0, failed INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance (id INTEGER PRIMARY KEY CHECK (id = 1), enabled INTEGER DEFAULT 0, message TEXT DEFAULT '')''')
    c.execute('''CREATE TABLE IF NOT EXISTS support_links (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, url TEXT, visible INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS menu_buttons (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, action TEXT, url TEXT DEFAULT '', visible INTEGER DEFAULT 1)''')

    migrations = [
        "ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN vip_since TEXT",
        "ALTER TABLE users ADD COLUMN referral_earned REAL DEFAULT 0.0",
        "ALTER TABLE users ADD COLUMN last_gift TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE products ADD COLUMN description TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN discount INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN api_id INTEGER DEFAULT 0",
        "ALTER TABLE tickets ADD COLUMN created_at TEXT",
        "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN warnings INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN panel_name TEXT DEFAULT ''",
        "ALTER TABLE transactions ADD COLUMN qr_url TEXT",
        "ALTER TABLE transactions ADD COLUMN upi_id TEXT",
        "ALTER TABLE transactions ADD COLUMN expires_at INTEGER",
    ]
    for mig in migrations:
        try:
            c.execute(mig)
        except sqlite3.OperationalError:
            pass

    default_settings = [
        ('reseller_system_status', 'ON'),
        ('bot_status', 'ON'),
        ('how_to_video', 'None'),
        ('fampay_api_key', FAMPAY_API_KEY),
        ('fampay_upi_id', ''),
        ('binance_api', ''),
        ('binance_secret', ''),
        ('binance_address', ''),
        ('vip_status', 'OFF'),
        ('reseller_setup_fee', '200.0'),
        ('reseller_min_balance', '500.0'),
        ('migration_done', '0'),
        ('support_telegram', 'https://t.me/YourSupport'),
        ('support_whatsapp', 'https://wa.me/YourNumber'),
        ('ui_start_menu', UI_TEXTS['start_menu']),
        ('ui_vip_menu', UI_TEXTS['vip_menu']),
        ('ui_add_balance_menu', UI_TEXTS['add_balance_menu']),
        ('ui_welcome', UI_TEXTS['welcome_default']),
        ('ui_category_message', UI_TEXTS['category_default']),
        ('ui_product_message', UI_TEXTS['product_default']),
        ('ui_key_message', UI_TEXTS['key_default']),
        ('ui_profile_message', UI_TEXTS['profile_default']),
        ('ui_orders_message', UI_TEXTS['orders_default']),
        ('ui_support_message', UI_TEXTS['support_default']),
        ('ui_balance_message', UI_TEXTS['balance_default']),
        ('balance_amounts', '100,200,500,1000,2000'),
        ('daily_gift_price', '0'),
        ('refer_earn_amount', '0'),
        ('owner_id', str(ADMIN_ID)),
        ('upi_id', ''),
        ('payee_name', BRAND_NAME),
        ('payment_qr_file_id', ''),
        ('zapupi_key', ''),
        ('binance_pay_id', ''),
        ('how_to_use_url', ''),
        ('payment_proof_url', ''),
        ('store_name', BRAND_NAME),
        ('support_url', 'https://t.me/elitexconfig'),
    ]
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        default_settings.append((f"emoji_{slot}", emoji_id))

    for key, val in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    c.execute("INSERT OR IGNORE INTO maintenance (id, enabled, message) VALUES (1, 0, ?)", (UI_TEXTS['maintenance_default'],))

    conn.commit()
    conn.close()


def migrate_categories() -> None:
    done = get_setting("migration_done", "0")
    logger.info("Forcing emoji and UI text updates...")

    db_query(
        "DELETE FROM settings WHERE key IN ('emoji_ludo_spin','emoji_download','ui_download_files','ui_lucky_dice_result','all_files_link','spin_status','daily_spin_limit','emoji_referral')"
    )
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        set_setting(f"emoji_{slot}", emoji_id)
    set_setting("ui_start_menu", UI_TEXTS['start_menu'])
    set_setting("ui_add_balance_menu", UI_TEXTS['add_balance_menu'])
    set_setting("ui_vip_menu", UI_TEXTS['vip_menu'])

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    products = c.execute("SELECT id, price_inr, reseller_price FROM products").fetchall()
    for prod in products:
        pid = prod[0]
        for col in ['price_inr', 'reseller_price']:
            val = prod[1] if col == 'price_inr' else prod[2]
            new_val = safe_float(val, 0.0)
            c.execute(f"UPDATE products SET {col}=? WHERE id=?", (new_val, pid))
    conn.commit()
    conn.close()

    if done == "1":
        return
    logger.info("Running category migration...")
    mapping = {
        "android non root panel": "ANDROID NON ROOT PANEL",
        "android root panel": "ANDROID ROOT PANEL",
        "pc panel": "PC PANEL",
    }
    for old, new in mapping.items():
        db_query("UPDATE products SET category = ? WHERE LOWER(category) = ?", (new, old))
    db_query(
        "UPDATE products SET category = 'ANDROID NON ROOT PANEL' WHERE LOWER(category) NOT IN (?, ?, ?)",
        ("android non root panel", "android root panel", "pc panel"),
    )
    set_setting("migration_done", "1")


# ==============================================================================
# 6. MIDDLEWARE
# ==============================================================================
class GlobalSecurityMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.last_action_times = {}

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = time.time()
        if user_id in self.last_action_times and now - self.last_action_times[user_id] < 0.3:
            return
        self.last_action_times[user_id] = now

        if user_id != ADMIN_ID:
            user_info = db_query("SELECT is_banned FROM users WHERE user_id=?", (user_id,), fetchone=True)
            if user_info and user_info[0] == 1:
                msg = "🚫 <b>✦ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 ✦</b>\n━━━━━━━━━━━━━━━━━━\nYou have been banned from using this bot.\n<i>Contact support if you think this is a mistake.</i>"
                if isinstance(event, Message):
                    await event.answer(msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(msg, show_alert=True)
                return

            status_check = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
            status = status_check[0] if status_check else 'ON'
            if status == 'OFF':
                msg = "🛠 <b>✦ 𝗦𝗧𝗢𝗥𝗘 𝗠𝗔𝗜𝗡𝗧𝗘𝗡𝗔𝗡𝗖𝗘 ✦</b>\n━━━━━━━━━━━━━━━━━━\nThe store is offline for updates.\n<i>Please check back soon!</i>"
                if isinstance(event, Message):
                    await event.answer(msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Bot is currently OFF for Maintenance.", show_alert=True)
                return

            mt = db_query("SELECT enabled FROM maintenance WHERE id=1", fetchone=True)
            if mt and mt[0] == 1:
                mt_msg_row = db_query("SELECT message FROM maintenance WHERE id=1", fetchone=True)
                mt_msg = mt_msg_row[0] if mt_msg_row else "🛠 Bot under maintenance."
                if isinstance(event, Message):
                    await event.answer(mt_msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Bot under maintenance.", show_alert=True)
                return

        return await handler(event, data)


dp.message.middleware(GlobalSecurityMiddleware())
dp.callback_query.middleware(GlobalSecurityMiddleware())


# ==============================================================================
# 7. FSM STATES
# ==============================================================================
class UserStates(StatesGroup):
    wait_for_ticket = State()
    wait_for_redeem = State()
    wait_for_crypto_txid = State()
    custom_amount_input = State()
    custom_balance_amount = State()
    awaiting_balance_proof = State()
    awaiting_order_proof = State()


class AdminStates(StatesGroup):
    # Product
    add_prod_category = State()
    add_prod_panel_name = State()
    add_prod_name = State()
    add_prod_validity = State()
    add_prod_device_limit = State()
    add_prod_price = State()
    add_prod_reseller_price = State()
    add_prod_apk = State()
    add_prod_keys = State()
    add_prod_desc = State()
    add_prod_discount = State()
    edit_prod_field = State()
    wait_for_new_value = State()
    wait_for_add_keys = State()
    wait_for_delete_key = State()

    # Category
    add_cat_name = State()
    add_cat_emoji = State()
    add_cat_subtitle = State()
    edit_cat_field = State()
    edit_cat_value = State()

    # Broadcast / coupons
    broadcast_msg = State()
    add_coupon_code = State()
    add_coupon_amount = State()
    add_coupon_uses = State()

    # Payment gateways
    wait_for_fampay_api = State()
    wait_for_fampay_upi = State()
    wait_for_binance_api = State()
    wait_for_binance_secret = State()
    wait_for_binance_address = State()
    wait_for_upi = State()
    wait_for_payee = State()
    wait_for_static_qr = State()
    wait_for_zapupi = State()
    wait_for_binance_pay = State()
    wait_for_instructions = State()

    # Tickets / users
    ticket_reply_msg = State()
    reseller_manage_id = State()
    manage_target_user = State()
    wait_for_add_money = State()
    wait_for_minus_money = State()
    wait_for_warning = State()
    bal_add_uid = State()
    bal_add_amt = State()
    bal_remove_uid = State()
    bal_remove_amt = State()
    bal_check_uid = State()
    bal_addall_amt = State()

    # Settings
    wait_for_howto_video = State()
    wait_for_support_telegram = State()
    wait_for_support_whatsapp = State()
    wait_for_howto_url = State()
    wait_for_proof_url = State()
    wait_for_support_url = State()

    # Gift/refer/owner/admin
    wait_for_gift_amount = State()
    wait_for_refer_amount = State()
    wait_for_new_owner = State()
    wait_for_coadmin_add = State()
    wait_for_coadmin_remove = State()

    # Messages editor
    edit_ui_text = State()
    wait_for_msg_welcome = State()
    wait_for_msg_category = State()
    wait_for_msg_product = State()
    wait_for_msg_key = State()
    wait_for_msg_profile = State()
    wait_for_msg_orders = State()
    wait_for_msg_support = State()
    wait_for_msg_balance = State()

    # Misc
    edit_reseller_price = State()
    wait_for_reseller_setup_fee = State()
    wait_for_reseller_min_balance = State()
    confirm_ban = State()
    wait_for_category_emoji = State()
    wait_for_panel_emoji_id = State()
    wait_for_emoji_slot = State()
    wait_for_logo = State()
    wait_for_maintenance_msg = State()
    wait_for_api_name = State()
    wait_for_api_url = State()
    wait_for_api_key = State()
    wait_for_api_del = State()
    wait_for_reseller_uid = State()
    wait_for_key_product = State()
    wait_for_key_text = State()
    wait_for_key_remove_pid = State()
    wait_for_key_remove_kid = State()
    wait_for_key_check_pid = State()


# ==============================================================================
# 8. KEYBOARDS
# ==============================================================================
def get_category_emoji(category: str) -> str:
    slot = CATEGORY_SLOT_MAP.get(category)
    if slot:
        return get_emoji_icon(slot, DEFAULT_EMOJIS.get(slot, ""))
    return ""


def get_panel_emoji(panel_name: str) -> str:
    stored = get_setting(f"panel_emoji_{panel_name}", "")
    if stored and stored.isdigit():
        return stored
    return get_emoji_icon("product_store")


def main_menu_kb(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    status_check = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    sys_status = status_check[0] if status_check else 'ON'
    vip_sys_check = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    vip_system = vip_sys_check[0] if vip_sys_check else 'OFF'

    is_reseller = False
    if user_id:
        user_check = db_query("SELECT is_reseller FROM users WHERE user_id=?", (user_id,), fetchone=True)
        if user_check:
            is_reseller = bool(user_check[0])

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text=fancy("Product Store"), callback_data="menu_shop",
            icon_custom_emoji_id=get_emoji_icon("product_store"), style="danger",
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text=fancy("My Profile"), callback_data="menu_profile",
                             icon_custom_emoji_id=get_emoji_icon("profile"), style="primary"),
        InlineKeyboardButton(text=fancy("Add Balance"), callback_data="menu_add_balance",
                             icon_custom_emoji_id=get_emoji_icon("add_balance"), style="primary"),
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text=fancy("Tutorials"), callback_data="menu_how_to",
                             icon_custom_emoji_id=get_emoji_icon("tutorial"), style="success"),
        InlineKeyboardButton(text=fancy("Support"), callback_data="menu_support",
                             icon_custom_emoji_id=get_emoji_icon("support"), style="danger"),
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🎁 " + fancy("Daily Gift"), callback_data="daily_gift", style="success"),
        InlineKeyboardButton(text="🎟️ " + fancy("Redeem"), callback_data="redeem_coupon", style="primary"),
    ])

    extras_row = []
    if sys_status == 'ON' or is_reseller:
        extras_row.append(InlineKeyboardButton(
            text=fancy("Reseller Panel"), callback_data="menu_reseller_dash",
            icon_custom_emoji_id=get_emoji_icon("reseller"), style="primary",
        ))
    if vip_system == 'ON':
        extras_row.append(InlineKeyboardButton(
            text=fancy("VIP Club"), callback_data="menu_vip_dash",
            icon_custom_emoji_id=get_emoji_icon("vip"), style="danger",
        ))
    if extras_row:
        kb.inline_keyboard.append(extras_row)
    return kb


def back_kb(callback: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=fancy("BACK"), callback_data=callback,
                             icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
    ]])


def admin_kb() -> InlineKeyboardMarkup:
    status = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    status_val = status[0] if status else 'ON'
    vip_status = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    vip_val = vip_status[0] if vip_status else 'OFF'

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 " + fancy("Bot Statistics"), callback_data="admin_view_stats", style="primary")],
        [InlineKeyboardButton(text="👥 " + fancy("User Control Panel"), callback_data="admin_user_control_start", style="primary")],
        [
            InlineKeyboardButton(text="➕ " + fancy("Add Product"), callback_data="admin_add_prod", style="primary"),
            InlineKeyboardButton(text="📦 " + fancy("Manage Products"), callback_data="admin_manage_prods", style="primary"),
        ],
        [
            InlineKeyboardButton(text="📂 " + fancy("Category Manager"), callback_data="admin_cat_menu", style="primary"),
            InlineKeyboardButton(text="🔑 " + fancy("Key Manager"), callback_data="admin_key_menu", style="primary"),
        ],
        [InlineKeyboardButton(text="💰 " + fancy("Balance Manager"), callback_data="admin_bal_menu", style="primary")],
        [InlineKeyboardButton(text="🧾 " + fancy("Balance Requests"), callback_data="admin_bal_requests", style="success")],
        [InlineKeyboardButton(text="👑 " + fancy("Reseller Mgmt"), callback_data="admin_reseller_menu", style="primary")],
        [
            InlineKeyboardButton(text="🎟 " + fancy("Create Coupon"), callback_data="admin_create_coupon", style="primary"),
            InlineKeyboardButton(text="📢 " + fancy("Broadcast"), callback_data="admin_broadcast_btn", style="primary"),
        ],
        [
            InlineKeyboardButton(text="🎫 " + fancy("View Tickets"), callback_data="admin_view_tickets", style="primary"),
            InlineKeyboardButton(text="📹 " + fancy("Tutorial Video"), callback_data="admin_set_video", style="primary"),
        ],
        [InlineKeyboardButton(text="🎨 " + fancy("Edit All Emojis"), callback_data="admin_edit_emojis", style="primary")],
        [InlineKeyboardButton(text="⚙️ " + fancy("FamPay Setup"), callback_data="admin_setup_fampay", style="primary")],
        [InlineKeyboardButton(text="💳 " + fancy("Payment Settings"), callback_data="admin_payment_menu", style="primary")],
        [
            InlineKeyboardButton(text="✏️ " + fancy("Edit UI Texts"), callback_data="admin_edit_ui_menu", style="primary"),
            InlineKeyboardButton(text="📝 " + fancy("Edit R-Price"), callback_data="admin_edit_reseller_price", style="primary"),
        ],
        [
            InlineKeyboardButton(text="📢 " + fancy("Message Editor"), callback_data="admin_msg_editor", style="primary"),
            InlineKeyboardButton(text="🌐 " + fancy("API Manager"), callback_data="admin_api_menu", style="primary"),
        ],
        [
            InlineKeyboardButton(text="🤝 " + fancy("Co-Admin Manager"), callback_data="admin_coadmin_menu", style="primary"),
            InlineKeyboardButton(text="👑 " + fancy("Transfer Owner"), callback_data="admin_transfer_owner", style="primary"),
        ],
        [
            InlineKeyboardButton(text="🔗 " + fancy("Link Manager"), callback_data="admin_link_menu", style="primary"),
            InlineKeyboardButton(text="🎁 " + fancy("Gift & Refer"), callback_data="admin_gift_menu", style="primary"),
        ],
        [
            InlineKeyboardButton(text="💰 " + fancy("Reseller Fee"), callback_data="admin_set_reseller_fee", style="primary"),
            InlineKeyboardButton(text="💳 " + fancy("Min Balance"), callback_data="admin_set_reseller_min", style="primary"),
        ],
        [
            InlineKeyboardButton(text="📞 " + fancy("Support Links"), callback_data="admin_set_support_links", style="primary"),
            InlineKeyboardButton(text="🎨 " + fancy("Category Emojis"), callback_data="admin_set_category_emojis", style="primary"),
        ],
        [InlineKeyboardButton(text="🖼 " + fancy("Set Panel Emojis"), callback_data="admin_set_panel_emojis", style="primary")],
        [InlineKeyboardButton(text="🖼️ " + fancy("Admin Logo"), callback_data="admin_set_logo", style="primary")],
        [
            InlineKeyboardButton(
                text=f"{fancy('Bot Status')}: {status_val} {'🟢' if status_val == 'ON' else '🔴'}",
                callback_data="admin_toggle_bot",
                style="success" if status_val == 'ON' else "danger",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{fancy('VIP System')}: {vip_val} {'🟢' if vip_val == 'ON' else '🔴'}",
                callback_data="admin_toggle_vip_sys",
                style="success" if vip_val == 'ON' else "danger",
            )
        ],
        [InlineKeyboardButton(text="🔧 " + fancy("Maintenance Mode"), callback_data="admin_maintenance_menu", style="danger")],
    ])


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=fancy("Back to Admin"), callback_data="admin_panel_back",
                             icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
    ]])


# ==============================================================================
# 9. NOTIFICATIONS
# ==============================================================================
async def send_advanced_notification(user_id: int, notif_type: str, amount: float,
                                     product: str = None, key: str = None,
                                     gateway: str = "FamPay") -> None:
    user_info = db_query(
        "SELECT first_name, phone, username, is_reseller, is_vip FROM users WHERE user_id=?",
        (user_id,), fetchone=True,
    )
    name = user_info[0] if user_info else "Unknown"
    phone = user_info[1] if user_info and user_info[1] else "Not Provided"
    username = f"@{user_info[2]}" if user_info and user_info[2] else "None"

    tags = []
    if user_info and user_info[3]:
        tags.append("👑 𝗥𝗲𝘀𝗲𝗹𝗹𝗲𝗿")
    if user_info and user_info[4]:
        tags.append("🌟 𝗩𝗜𝗣")
    tag_str = " | ".join(tags) if tags else "👤 𝗥𝗲𝗴𝘂𝗹𝗮𝗿"
    time_now = datetime.now().strftime("%d-%m-%Y %I:%M %p")

    if notif_type == "ORDER":
        title = "🛒 <b>✦ 𝗡𝗘𝗪 𝗢𝗥𝗗𝗘𝗥 ✦</b>"
        details = f"📦 <b>𝗣𝗿𝗼𝗱𝘂𝗰𝘁</b> ┃ {product}\n🔑 <b>𝗞𝗲𝘆</b> ┃ <code>{key}</code>\n💰 <b>𝗣𝗮𝗶𝗱</b> ┃ ₹{amount:.2f}\n📅 <b>𝗧𝗶𝗺𝗲</b> ┃ {time_now}"
    else:
        title = "💎 <b>✦ 𝗡𝗘𝗪 𝗗𝗘𝗣𝗢𝗦𝗜𝗧 ✦</b>"
        details = f"💵 <b>𝗔𝗺𝗼𝘂𝗻𝘁</b> ┃ ₹{amount:.2f}\n🧾 <b>𝗚𝗮𝘁𝗲𝘄𝗮𝘆</b> ┃ {gateway}\n🆔 <b>𝗥𝗲𝗳𝗲𝗿𝗲𝗻𝗰𝗲</b> ┃ <code>{product}</code>\n📅 <b>𝗧𝗶𝗺𝗲</b> ┃ {time_now}"

    msg = (
        f"{title}\n━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>𝗡𝗮𝗺𝗲</b> ┃ {name}\n"
        f"🆔 <b>𝗨𝘀𝗲𝗿 𝗜𝗗</b> ┃ <code>{user_id}</code>\n"
        f"📱 <b>𝗣𝗵𝗼𝗻𝗲</b> ┃ {phone}\n"
        f"🔗 <b>𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲</b> ┃ {username}\n"
        f"🏷 <b>𝗦𝘁𝗮𝘁𝘂𝘀</b> ┃ {tag_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n{details}"
    )
    try:
        await bot.send_message(ADMIN_ID, msg, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")


async def notify_all_admins(text: str, reply_markup=None, photo_id: str = ""):
    all_admins = {ADMIN_ID}
    for r in db_query("SELECT user_id FROM co_admins", fetchall=True) or []:
        all_admins.add(r[0])
    for aid in all_admins:
        try:
            if photo_id:
                await bot.send_photo(aid, photo_id, caption=text[:1024], reply_markup=reply_markup, parse_mode='HTML')
            else:
                await bot.send_message(aid, text[:4000], reply_markup=reply_markup, parse_mode='HTML')
        except Exception as e:
            logger.warning(f"Could not notify admin {aid}: {e}")


def is_co_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    return bool(db_query("SELECT 1 FROM co_admins WHERE user_id=?", (user_id,), fetchone=True))


# ==============================================================================
# 10. FAMPAY FUNCTIONS
# ==============================================================================
async def generate_fampay_qr(user_id: int, amount: float, upi_id: str = None) -> Dict[str, Any]:
    api_key = get_setting("fampay_api_key", FAMPAY_API_KEY)
    if not api_key or api_key == "YOUR_FAMPAY_API_KEY":
        return {"status": "error", "message": "FamPay API key not configured"}
    if not upi_id:
        upi_id = get_setting("fampay_upi_id", "")
        if not upi_id:
            return {"status": "error", "message": "UPI ID not configured"}
    url = f"{FAMPAY_QR_URL}?upi={upi_id}&amount={amount}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    try:
                        return await resp.json(content_type=None)
                    except Exception as e:
                        return {"status": "error", "message": f"Parse error: {e}"}
                return {"status": "error", "message": f"HTTP Error: {resp.status}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def verify_fampay_payment(order_id: str) -> Dict[str, Any]:
    api_key = get_setting("fampay_api_key", FAMPAY_API_KEY)
    if not api_key or api_key == "YOUR_FAMPAY_API_KEY":
        return {"status": "error", "message": "FamPay API key not configured"}
    url = f"{FAMPAY_VERIFY_URL}?order_id={order_id}&api_key={api_key}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    try:
                        return await resp.json(content_type=None)
                    except Exception as e:
                        return {"status": "error", "message": f"Parse error: {e}"}
                return {"status": "error", "message": f"HTTP Error: {resp.status}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def run_payment_verification(user_id: int, order_id: str, reply_target: Any) -> None:
    txn = db_query(
        "SELECT amount_inr, status, timestamp, qr_url, upi_id, expires_at FROM transactions WHERE order_id=?",
        (order_id,), fetchone=True,
    )
    if not txn:
        err = "❌ Invalid or Fake Order ID detected!"
        if isinstance(reply_target, CallbackQuery):
            await reply_target.answer(err, show_alert=True)
        else:
            await reply_target.answer(err)
        return

    if txn[5] and time.time() > txn[5]:
        db_query("UPDATE transactions SET status='expired' WHERE order_id=?", (order_id,))
        err_msg = "⏳ <b>✦ 𝗤𝗥 𝗘𝗫𝗣𝗜𝗥𝗘𝗗 ✦</b>\n━━━━━━━━━━━━━━━━━━\nThe 5-minute payment window has closed.\n<i>Please generate a new QR code.</i>"
        if isinstance(reply_target, CallbackQuery):
            await reply_target.message.edit_text(err_msg, reply_markup=back_kb(), parse_mode='HTML')
        else:
            await reply_target.answer(err_msg, reply_markup=back_kb())
        return

    if txn[1] == 'paid':
        msg = "✅ This payment has already been securely credited to your wallet."
        if isinstance(reply_target, CallbackQuery):
            await reply_target.answer(msg, show_alert=True)
        else:
            await reply_target.answer(msg)
        return
    elif txn[1] == 'expired':
        msg = "❌ This order has expired. Please create a new deposit request."
        if isinstance(reply_target, CallbackQuery):
            await reply_target.answer(msg, show_alert=True)
        else:
            await reply_target.answer(msg)
        return

    result = await verify_fampay_payment(order_id)

    if result.get("status") == "success":
        txn_data = result.get("data", {})
        transaction_id = txn_data.get("transaction_id")
        utr = txn_data.get("utr")
        sender_name = txn_data.get("sender_name")
        amount_received = txn_data.get("amount", txn[0])
        payment_time = txn_data.get("payment_time_ist")

        db_query("UPDATE transactions SET status='paid' WHERE order_id=?", (order_id,))
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount_received, user_id))

        success_msg = (
            f"✅ <b>✦ 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗩𝗘𝗥𝗜𝗙𝗜𝗘𝗗 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"💎 <b>𝗖𝗿𝗲𝗱𝗶𝘁𝗲𝗱</b> ┃ {fmt_curr(amount_received)}\n"
            f"🧾 <b>𝗨𝗧𝗥</b> ┃ <code>{utr}</code>\n"
            f"👤 <b>𝗦𝗲𝗻𝗱𝗲𝗿</b> ┃ {sender_name}\n"
            f"📅 <b>𝗧𝗶𝗺𝗲</b> ┃ {payment_time}\n"
            f"━━━━━━━━━━━━━━━━━━\n<i>Funds are now live in your wallet.</i>"
        )
        if isinstance(reply_target, CallbackQuery):
            await reply_target.message.edit_text(success_msg, reply_markup=back_kb(), parse_mode='HTML')
        else:
            await reply_target.answer(success_msg, reply_markup=back_kb())

        await send_advanced_notification(user_id, "DEPOSIT", amount_received, product=transaction_id, gateway="FamPay")
        log_activity(user_id, "DEPOSIT_SUCCESS", f"Amount: {amount_received}, Gateway: FamPay, Order: {order_id}")
    elif result.get("status") == "error":
        error_msg = result.get("message", "Payment not received yet")
        if "Transaction failed" in error_msg or "not received" in error_msg:
            fail_msg = f"❌ {error_msg}\n\n<i>Please make sure you sent the exact amount to the correct UPI ID.</i>"
            if isinstance(reply_target, CallbackQuery):
                await reply_target.answer(fail_msg, show_alert=True)
            else:
                await reply_target.answer(fail_msg)
        else:
            pending_msg = f"⏳ Payment Status: PENDING\n\n{error_msg}\n\nPlease wait and verify again."
            if isinstance(reply_target, CallbackQuery):
                await reply_target.answer(pending_msg, show_alert=True)
            else:
                await reply_target.answer(pending_msg)
    else:
        err = f"⚠️ Gateway Error: {result.get('message', 'Unknown Error')}"
        if isinstance(reply_target, CallbackQuery):
            await reply_target.answer(err, show_alert=True)
        else:
            await reply_target.answer(err)


async def auto_verify_task() -> None:
    while True:
        await asyncio.sleep(30)
        api_key = get_setting("fampay_api_key", "")
        if not api_key or api_key == "YOUR_FAMPAY_API_KEY":
            continue
        pending_txns = db_query(
            "SELECT order_id, user_id, amount_inr, timestamp, expires_at FROM transactions WHERE status='pending'",
            fetchall=True,
        )
        if not pending_txns:
            continue
        for txn in pending_txns:
            order_id, user_id, amount, ts, expires_at = txn
            if expires_at and time.time() > expires_at:
                db_query("UPDATE transactions SET status='expired' WHERE order_id=?", (order_id,))
                try:
                    await bot.send_message(
                        user_id,
                        f"⏳ <b>✦ 𝗤𝗥 𝗘𝗫𝗣𝗜𝗥𝗘𝗗 ✦</b>\n━━━━━━━━━━━━━━━━━━\nOrder <code>{order_id}</code> has timed out.\n<i>Please generate a new QR.</i>",
                        parse_mode='HTML',
                    )
                except Exception:
                    pass
                continue
            result = await verify_fampay_payment(order_id)
            if result.get("status") == "success":
                txn_data = result.get("data", {})
                amount_received = txn_data.get("amount", amount)
                utr = txn_data.get("utr")
                sender_name = txn_data.get("sender_name")
                db_query("UPDATE transactions SET status='paid' WHERE order_id=?", (order_id,))
                db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount_received, user_id))
                try:
                    await bot.send_message(
                        user_id,
                        f"✨ <b>✦ 𝗔𝗨𝗧𝗢-𝗩𝗘𝗥𝗜𝗙𝗜𝗘𝗗 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
                        f"💎 <b>𝗖𝗿𝗲𝗱𝗶𝘁𝗲𝗱</b> ┃ {fmt_curr(amount_received)}\n"
                        f"🧾 <b>𝗨𝗧𝗥</b> ┃ <code>{utr}</code>\n👤 <b>𝗦𝗲𝗻𝗱𝗲𝗿</b> ┃ {sender_name}\n"
                        f"━━━━━━━━━━━━━━━━━━\n<i>Payment detected automatically.</i>",
                        parse_mode='HTML',
                    )
                except Exception:
                    pass
                await send_advanced_notification(user_id, "DEPOSIT", amount_received, product=order_id, gateway="FamPay Auto")
                log_activity(user_id, "DEPOSIT_AUTO_SUCCESS", f"Amount: {amount_received}, Order: {order_id}")


# ==============================================================================
# 11. START / ONBOARDING
# ==============================================================================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    if WELCOME_STICKER_ID:
        try:
            await message.answer_sticker(WELCOME_STICKER_ID)
        except Exception:
            pass

    args = message.text.split()
    if len(args) > 1:
        token = args[1]
        if token.startswith("v_"):
            order_id = token.split("v_")[1]
            msg = await message.answer(
                "🔄 <b>✦ 𝗩𝗘𝗥𝗜𝗙𝗬𝗜𝗡𝗚 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 ✦</b>\n<i>Connecting to secure gateway...</i>",
                parse_mode='HTML',
            )
            await run_payment_verification(message.from_user.id, order_id, msg)
            return
        if token.startswith("ref_") and token[4:].isdigit():
            ref_id = int(token[4:])
            if ref_id != message.from_user.id:
                referrer = db_query("SELECT user_id FROM users WHERE user_id=?", (ref_id,), fetchone=True)
                if referrer:
                    db_query(
                        "INSERT OR IGNORE INTO users (user_id, first_name, username, joined_date, referred_by) VALUES (?, ?, ?, ?, ?)",
                        (message.from_user.id, message.from_user.first_name,
                         message.from_user.username or "",
                         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ref_id),
                    )
                    reward = safe_float(get_setting("refer_earn_amount", "0"), 0.0)
                    if reward > 0:
                        db_query("UPDATE users SET balance = balance + ?, referral_earned = referral_earned + ? WHERE user_id=?",
                                 (reward, reward, ref_id))
                        db_query(
                            "INSERT INTO wallet_transactions (user_id, amount_delta, note) VALUES (?, ?, ?)",
                            (ref_id, reward, f"Referral reward for user {message.from_user.id}"),
                        )
                        try:
                            await bot.send_message(ref_id, f"👥 <b>Referral Bonus!</b>\n+{fmt_curr(reward)} added to your wallet.", parse_mode='HTML')
                        except Exception:
                            pass

    user = db_query("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    current_username = message.from_user.username or ""
    db_query("UPDATE users SET username=? WHERE user_id=?", (current_username, message.from_user.id))

    if not user or not user[0]:
        db_query(
            "INSERT OR IGNORE INTO users (user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)",
            (message.from_user.id, message.from_user.first_name, current_username,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        log_activity(message.from_user.id, "ACCOUNT_CREATED")

    log_activity(message.from_user.id, "CMD_START")
    await send_main_menu(message)


async def send_main_menu(ctx: Any):
    logo = get_setting("admin_logo_file_id", "")
    text = get_setting("ui_welcome", UI_TEXTS['welcome_default'])
    kb = main_menu_kb(ctx.from_user.id)
    if isinstance(ctx, Message):
        if logo:
            try:
                await ctx.answer_photo(logo, caption=text, reply_markup=kb, parse_mode='HTML')
                return
            except Exception:
                pass
        await ctx.answer(text, reply_markup=kb, parse_mode='HTML')
    else:
        try:
            await ctx.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
        except Exception:
            try:
                await ctx.message.delete()
            except Exception:
                pass
            if logo:
                try:
                    await bot.send_photo(ctx.from_user.id, logo, caption=text, reply_markup=kb, parse_mode='HTML')
                    return
                except Exception:
                    pass
            await bot.send_message(ctx.from_user.id, text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    log_activity(call.from_user.id, "RETURN_MAIN_MENU")
    await send_main_menu(call)


# ==============================================================================
# 12. ADD BALANCE (FamPay UPI + Manual Request)
# ==============================================================================
@dp.callback_query(F.data == "menu_add_balance")
async def select_gateway_menu(call: CallbackQuery):
    log_activity(call.from_user.id, "VIEW_ADD_BALANCE")
    text = get_setting("ui_balance_message", UI_TEXTS['balance_default'])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fancy("UPI PAY"), callback_data="gateway_inr",
                              icon_custom_emoji_id=get_emoji_icon("upi"), style="primary")],
        [InlineKeyboardButton(text="📸 " + fancy("Manual Request"), callback_data="manual_balance", style="success")],
        [InlineKeyboardButton(text=fancy("My Requests"), callback_data="my_bal_requests", style="primary")],
        [InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "gateway_inr")
async def add_balance_inr(call: CallbackQuery):
    text = "💵 <b>✦ 𝗨𝗣𝗜 𝗗𝗘𝗣𝗢𝗦𝗜𝗧 ✦</b>\n━━━━━━━━━━━━━━━━━━\n\n<i>Select an amount to deposit</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₹50", callback_data="pay_50", style="primary"),
         InlineKeyboardButton(text="₹100", callback_data="pay_100", style="primary")],
        [InlineKeyboardButton(text="₹200", callback_data="pay_200", style="primary"),
         InlineKeyboardButton(text="₹500", callback_data="pay_500", style="primary")],
        [InlineKeyboardButton(text="₹1000", callback_data="pay_1000", style="primary"),
         InlineKeyboardButton(text="₹2000", callback_data="pay_2000", style="primary")],
        [InlineKeyboardButton(text="✏️ " + fancy("Custom Amount"), callback_data="custom_deposit_keypad", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="menu_add_balance",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "custom_deposit_keypad")
async def show_custom_keypad(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.custom_amount_input)
    await state.update_data(amount_str="0")
    await show_keypad(call.message)


async def show_keypad(message: Message, amount_str: str = "0"):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="      1      ", callback_data="kp_1", style="primary"),
         InlineKeyboardButton(text="      2      ", callback_data="kp_2", style="primary"),
         InlineKeyboardButton(text="      3      ", callback_data="kp_3", style="primary")],
        [InlineKeyboardButton(text="      4      ", callback_data="kp_4", style="primary"),
         InlineKeyboardButton(text="      5      ", callback_data="kp_5", style="primary"),
         InlineKeyboardButton(text="      6      ", callback_data="kp_6", style="primary")],
        [InlineKeyboardButton(text="      7      ", callback_data="kp_7", style="primary"),
         InlineKeyboardButton(text="      8      ", callback_data="kp_8", style="primary"),
         InlineKeyboardButton(text="      9      ", callback_data="kp_9", style="primary")],
        [InlineKeyboardButton(text="    ⌫    ", callback_data="kp_backspace", style="danger"),
         InlineKeyboardButton(text="      0      ", callback_data="kp_0", style="primary"),
         InlineKeyboardButton(text="    C    ", callback_data="kp_clear", style="danger")],
        [InlineKeyboardButton(text=f"✅ {fancy('Confirm')} • ₹{amount_str}", callback_data="kp_confirm", style="success")],
        [InlineKeyboardButton(text=fancy("Cancel"), callback_data="gateway_inr",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    text = f"💵 <b>✦ 𝗘𝗡𝗧𝗘𝗥 𝗔𝗠𝗢𝗨𝗡𝗧 ✦</b>\n━━━━━━━━━━━━━━━━━━\n\n💎 <b>𝗖𝘂𝗿𝗿𝗲𝗻𝘁</b> ┃ ₹{amount_str}"
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except Exception:
        await bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("kp_"), UserStates.custom_amount_input)
async def keypad_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount_str = data.get("amount_str", "0")
    action = call.data.split("_")[1]
    if action == "confirm":
        if amount_str == "0":
            await call.answer("Amount cannot be zero.", show_alert=True)
            return
        try:
            amount = float(amount_str)
            if amount < 10:
                await call.answer("Minimum deposit is ₹10.", show_alert=True)
                return
            await state.clear()
            await call.message.edit_text("⏳ <b>✦ 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗜𝗡𝗚 𝗦𝗘𝗖𝗨𝗥𝗘 𝗤𝗥 ✦</b>", parse_mode='HTML')
            await generate_fampay_order(call.from_user.id, amount, call.message)
        except ValueError:
            await call.answer("Invalid amount.", show_alert=True)
        return
    if action == "backspace":
        amount_str = amount_str[:-1] if len(amount_str) > 1 else "0"
    elif action == "clear":
        amount_str = "0"
    else:
        amount_str = action if amount_str == "0" else amount_str + action
        if len(amount_str) > 6:
            amount_str = amount_str[:6]
    await state.update_data(amount_str=amount_str)
    await show_keypad(call.message, amount_str)
    await call.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def process_fampay_payment_callback(call: CallbackQuery):
    inr_amount = float(call.data.split("_")[1])
    await call.message.edit_text("⏳ <b>✦ 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗜𝗡𝗚 𝗦𝗘𝗖𝗨𝗥𝗘 𝗤𝗥 ✦</b>", parse_mode='HTML')
    await generate_fampay_order(call.from_user.id, inr_amount, call.message)


async def generate_fampay_order(user_id: int, inr_amount: float, message_obj: Message) -> None:
    upi_id = get_setting("fampay_upi_id", "") or get_setting("upi_id", "")
    payee_name = get_setting("payee_name", BRAND_NAME)
    qr_url = None
    order_id = f"FAMPAY{user_id}{int(time.time())}"
    expires_at_str = (datetime.now() + timedelta(minutes=5)).strftime("%d-%m-%Y %H:%M:%S")
    created_at = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    expires_ts = int(time.time() + 300)

    if qrcode is not None and upi_id:
        upi_link = build_upi_link(upi_id, payee_name, inr_amount, "Balance Topup")
        buf = generate_qr_bytes(upi_link)
        if buf:
            try:
                await bot.send_photo(
                    user_id, buf,
                    caption=f"💳 Scan karke ₹{inr_amount:.2f} pay karein.\n\nUPI: <code>{upi_id}</code>",
                    parse_mode='HTML',
                )
            except Exception:
                pass
        qr_url = upi_link
    else:
        qr_url = None

    fampay_api = get_setting("fampay_api_key", "")
    if fampay_api and fampay_api != "YOUR_FAMPAY_API_KEY" and upi_id:
        result = await generate_fampay_qr(user_id, inr_amount, upi_id)
        if result.get("status") == "success":
            d = result.get("data", {})
            qr_url = d.get("qr_url") or qr_url
            order_id = d.get("order_id", order_id)
            upi_id = d.get("upi_id", upi_id)
            expires_at_str = d.get("expires_at_ist", expires_at_str)
            created_at = d.get("created_at_ist", created_at)
            try:
                et = datetime.strptime(expires_at_str, "%d-%m-%Y %H:%M:%S")
                expires_ts = int(et.timestamp())
            except Exception:
                pass

    db_query(
        "INSERT INTO transactions (order_id, user_id, amount_inr, status, timestamp, qr_url, upi_id, expires_at) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)",
        (order_id, user_id, inr_amount, int(time.time()), qr_url or "", upi_id, expires_ts),
    )

    kb_rows = [[InlineKeyboardButton(text="🔄 " + fancy("Verify Payment"),
                                     callback_data=f"verify_{order_id}", style="primary")]]
    if qr_url and qr_url.startswith("http"):
        kb_rows.append([InlineKeyboardButton(text="🖼 " + fancy("View QR Code"), url=qr_url, style="success")])
    kb_rows.append([InlineKeyboardButton(text=fancy("Cancel Transaction"), callback_data="menu_add_balance",
                                          icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])

    text = (
        f"🧾 <b>✦ 𝗦𝗘𝗖𝗨𝗥𝗘 𝗤𝗥 𝗥𝗘𝗔𝗗𝗬 ✦</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💵 <b>𝗔𝗺𝗼𝘂𝗻𝘁</b> ┃ {fmt_curr(inr_amount)}\n"
        f"🆔 <b>𝗢𝗿𝗱𝗲𝗿 𝗜𝗗</b> ┃ <code>{order_id}</code>\n"
        f"🏦 <b>𝗨𝗣𝗜 𝗜𝗗</b> ┃ <code>{upi_id or 'N/A'}</code>\n"
        f"⏳ <b>𝗘𝘅𝗽𝗶𝗿𝗲𝘀</b> ┃ {expires_at_str}\n"
        f"📅 <b>𝗖𝗿𝗲𝗮𝘁𝗲𝗱</b> ┃ {created_at}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>𝗛𝗼𝘄 𝘁𝗼 𝗣𝗮𝘆</b>\n"
        f"╰ 1️⃣ Scan QR or use UPI ID\n"
        f"╰ 2️⃣ Send exact amount: {fmt_curr(inr_amount)}\n"
        f"╰ 3️⃣ Tap <b>Verify Payment</b>\n"
        f"╰ 4️⃣ Auto-verify will detect automatically\n"
    )
    log_activity(user_id, "GENERATE_INVOICE_FAMPAY", f"Amount: {inr_amount}, Order ID: {order_id}")
    try:
        await message_obj.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode='HTML')
    except Exception:
        await bot.send_message(message_obj.chat.id, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode='HTML')


@dp.callback_query(F.data.startswith("verify_"))
async def manual_verify_callback(call: CallbackQuery):
    order_id = call.data.split("_", 1)[1]
    await run_payment_verification(call.from_user.id, order_id, call)


# ----------------- Manual Balance Request (Screenshot + Admin Approval) --------
@dp.callback_query(F.data == "manual_balance")
async def manual_balance_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.custom_balance_amount)
    await call.message.edit_text(
        "💰 <b>✦ 𝗠𝗔𝗡𝗨𝗔𝗟 𝗕𝗔𝗟𝗔𝗡𝗖𝗘 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
        "<i>Kitna balance add karna hai? Amount bhejein (₹):</i>",
        reply_markup=back_kb("menu_add_balance"), parse_mode='HTML',
    )


@dp.message(UserStates.custom_balance_amount)
async def manual_balance_amount(m: Message, state: FSMContext):
    try:
        amount = float(m.text.replace(",", "").replace("₹", "").strip())
    except ValueError:
        await m.answer("❌ Valid number bhejein, jaise 500.")
        return
    if amount <= 0 or amount > 1000000:
        await m.answer("❌ Amount 1 se 10,00,000 ke beech hona chahiye.")
        return
    await state.clear()
    await state.update_data(pending_balance_amount=amount)
    await m.answer(
        "📸 <b>Payment screenshot bhejein</b>\n\n"
        "QR scan karke ya UPI ID se payment karke screenshot isi chat mein bhejein. Admin approve karega to balance add hoga.",
        reply_markup=back_kb("menu_add_balance"), parse_mode='HTML',
    )
    await state.set_state(UserStates.awaiting_balance_proof)


@dp.callback_query(F.data == "my_bal_requests")
async def my_bal_requests(call: CallbackQuery):
    rows = db_query(
        "SELECT id, amount, method, status, created_at FROM balance_requests WHERE user_id=? ORDER BY id DESC LIMIT 15",
        (call.from_user.id,), fetchall=True,
    )
    body = "📋 <b>✦ 𝗠𝗬 𝗧𝗢𝗣-𝗨𝗣 𝗥𝗘𝗤𝗨𝗘𝗦𝗧𝗦 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
    if rows:
        for r in rows:
            body += f"#{r[0]} • {fmt_curr(r[1])} • {r[3]}\n<i>{r[4]}</i>\n\n"
    else:
        body += "📭 Abhi koi request nahi."
    await call.message.edit_text(body, reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')


# ==============================================================================
# 13. BINANCE CRYPTO PAYMENT
# ==============================================================================
@dp.callback_query(F.data == "gateway_crypto")
async def add_balance_crypto(call: CallbackQuery, state: FSMContext):
    address_check = db_query("SELECT value FROM settings WHERE key='binance_address'", fetchone=True)
    if not address_check or not address_check[0]:
        return await call.message.edit_text(
            "⚠️ Binance Gateway currently offline.",
            reply_markup=back_kb("menu_add_balance"), parse_mode='HTML',
        )
    deposit_address = address_check[0]
    msg = (
        f"🪙 <b>— BINANCE USDT DEPOSIT —</b> 🪙\n\n"
        f"💵 <b>Rate:</b> 1 USDT = ₹{USDT_TO_INR}\n"
        f"⚠️ <b>Network:</b> TRC20 / BEP20\n\n"
        f"👇 <b>Send USDT to:</b>\n<code>{deposit_address}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ After sending, reply with exact <b>TxID</b>."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=fancy("Cancel"), callback_data="menu_add_balance",
                             icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
    ]])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode='HTML')
    await state.set_state(UserStates.wait_for_crypto_txid)


@dp.message(UserStates.wait_for_crypto_txid)
async def process_crypto_txid(m: Message, state: FSMContext):
    txid = m.text.strip()
    user_id = m.from_user.id
    if len(txid) < 10:
        return await m.answer("❌ Invalid TxID.")
    if db_query("SELECT txid FROM crypto_txns WHERE txid=?", (txid,), fetchone=True):
        return await m.answer("⚠️ Already claimed!", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    api_key_check = db_query("SELECT value FROM settings WHERE key='binance_api'", fetchone=True)
    secret_key_check = db_query("SELECT value FROM settings WHERE key='binance_secret'", fetchone=True)
    if not api_key_check or not secret_key_check:
        return await m.answer("⚠️ Binance API missing.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    await m.answer("🔄 <b>Verifying TxID...</b>", parse_mode='HTML')
    api_key = api_key_check[0]
    secret_key = secret_key_check[0]
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {'X-MBX-APIKEY': api_key}
    url = f"https://api.binance.com/sapi/v1/capital/deposit/hisrec?{query_string}&signature={signature}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    try:
                        history = await resp.json(content_type=None)
                    except Exception:
                        history = []
                    for deposit in history:
                        if deposit.get("txId") == txid and deposit.get("status") == 1:
                            usdt_amount = float(deposit.get("amount"))
                            inr_amount = usdt_amount * USDT_TO_INR
                            db_query(
                                "INSERT INTO crypto_txns (txid, user_id, amount_usdt, timestamp) VALUES (?, ?, ?, ?)",
                                (txid, user_id, usdt_amount, int(time.time())),
                            )
                            db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (inr_amount, user_id))
                            await m.answer(
                                f"🎉 <b>CRYPTO DEPOSIT SUCCESS!</b>\nReceived {usdt_amount} USDT\n💰 {fmt_curr(inr_amount)} credited.",
                                reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML',
                            )
                            await send_advanced_notification(user_id, "DEPOSIT", inr_amount, product=txid, gateway="Binance")
                            log_activity(user_id, "CRYPTO_DEPOSIT", f"TxID: {txid}, Amount: {inr_amount}")
                            await state.clear()
                            return
                    await m.answer("❌ TxID not found or pending.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
                else:
                    await m.answer(f"⚠️ Binance HTTP {resp.status}", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
        except Exception as e:
            await m.answer(f"⚠️ Error: {e}", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')


# ==============================================================================
# 14. SHOP
# ==============================================================================
@dp.callback_query(F.data == "menu_shop")
async def view_shop_panels(call: CallbackQuery):
    log_activity(call.from_user.id, "VIEW_SHOP")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = (
        f"{get_emoji('product_store')} <b>✦ 𝗦𝗘𝗟𝗘𝗖𝗧 𝗣𝗥𝗢𝗗𝗨𝗖𝗧 𝗣𝗔𝗡𝗘𝗟 ✦</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{get_emoji('point_down')} <b>𝗖𝗵𝗼𝗼𝘀𝗲 𝗮 𝗽𝗮𝗻𝗲𝗹</b> <i>to view packages</i>"
    )
    for cat in FIXED_CATEGORIES:
        emoji_id = get_category_emoji(cat)
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=fancy(cat), callback_data=f"cat_{cat[:30]}",
            icon_custom_emoji_id=emoji_id, style="primary",
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("cat_"))
async def view_panel_names(call: CallbackQuery):
    category = call.data.split("cat_", 1)[1]
    panel_names = db_query(
        "SELECT DISTINCT panel_name FROM products WHERE category LIKE ? AND is_active=1 AND panel_name != ''",
        (category + '%',), fetchall=True,
    )
    if not panel_names:
        prods = db_query(
            "SELECT id, name, price_inr, stock, reseller_price, validity, device_limit FROM products WHERE category LIKE ? AND is_active=1",
            (category + '%',), fetchall=True,
        )
        if not prods:
            return await call.answer("❌ No products in this category.", show_alert=True)
        await show_products_for_panel(call, prods, category)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = (
        f"{get_emoji('product_store')} <b>✦ {fancy(category.upper() + ' PANELS')} ✦</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{get_emoji('point_down')} <b>Choose a panel</b> <i>to continue</i>"
    )
    for pn in panel_names:
        panel = pn[0]
        emoji_id = get_panel_emoji(panel) or get_emoji_icon("product_store")
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=fancy(panel), callback_data=f"pnl_{category[:30]}_{panel[:30]}",
            icon_custom_emoji_id=emoji_id, style="primary",
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK TO PANELS"), callback_data="menu_shop",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("pnl_"))
async def view_products_for_panel(call: CallbackQuery):
    parts = call.data.split("pnl_", 1)[1].split("_", 1)
    if len(parts) != 2:
        return await call.answer("Invalid selection.", show_alert=True)
    category, panel_name = parts[0], parts[1]
    prods = db_query(
        "SELECT id, name, price_inr, stock, reseller_price, validity, device_limit FROM products WHERE category LIKE ? AND panel_name LIKE ? AND is_active=1",
        (category + '%', panel_name + '%'), fetchall=True,
    )
    if not prods:
        return await call.answer("No products found.", show_alert=True)
    await show_products_for_panel(call, prods, f"{category} - {panel_name}")


async def show_products_for_panel(call: CallbackQuery, prods: List[Tuple], header: str):
    user = db_query("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_reseller = bool(user[0]) if user else False
    is_vip = bool(user[1]) if user else False
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b>✦ {fancy(header.upper() + ' PACKAGES')} ✦</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for p in prods:
        prod_id, package_name, normal_price, stock, reseller_price, validity, device = p
        normal_price = safe_float(normal_price)
        reseller_price = safe_float(reseller_price)
        base_price = reseller_price if is_reseller else normal_price
        display_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if is_vip else base_price
        stock_status = "🟢 𝗜𝗻 𝗦𝘁𝗼𝗰𝗸" if stock > 0 else "🔴 𝗢𝘂𝘁 𝗼𝗳 𝗦𝘁𝗼𝗰𝗸"
        text += f"{get_emoji('product_store')} <b>{fancy(str(package_name))}</b>\n"
        if is_reseller or is_vip:
            text += f"💰 <b>Regular</b> ┃ <s>{fmt_curr(normal_price)}</s>\n"
            if is_reseller and not is_vip:
                text += f"👑 <b>Reseller</b> ┃ <b>{fmt_curr(display_price)}</b>\n"
            elif is_vip and not is_reseller:
                text += f"🌟 <b>VIP</b> ┃ <b>{fmt_curr(display_price)}</b>\n"
            else:
                text += f"👑🌟 <b>Super</b> ┃ <b>{fmt_curr(display_price)}</b>\n"
        else:
            text += f"💰 <b>Price</b> ┃ <b>{fmt_curr(normal_price)}</b>\n"
        text += f"📱 <b>Limit</b> ┃ {device}\n📦 <b>Stock</b> ┃ {stock_status}\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        if stock > 0:
            kb.inline_keyboard.append([InlineKeyboardButton(
                text=f"{fancy('Buy')} {fancy(str(package_name))} • {fmt_curr(display_price)}",
                callback_data=f"buy_{prod_id}",
                icon_custom_emoji_id=get_emoji_icon("product_store"), style="success",
            )])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(
                text=f"❌ {fancy(str(package_name))} • {fancy('Sold Out')}",
                callback_data="ignore_stock_click", style="danger",
            )])
    text += f"{get_emoji('point_down')} <b>Select a package</b> <i>to purchase</i>"
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK TO PANELS"), callback_data="menu_shop",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "ignore_stock_click")
async def ignore_stock_click(call: CallbackQuery):
    await call.answer("⚠️ This product is out of stock!", show_alert=True)


@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(call: CallbackQuery):
    prod_id = int(call.data.split("_")[1])
    prod = db_query(
        "SELECT name, price_inr, stock, apk_link, validity, device_limit, category, reseller_price, panel_name FROM products WHERE id=?",
        (prod_id,), fetchone=True,
    )
    user = db_query("SELECT balance, is_reseller, total_saved, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if not prod:
        return await call.answer("❌ Item not found!", show_alert=True)
    normal_price = safe_float(prod[1])
    reseller_price = safe_float(prod[7])
    is_reseller = bool(user[1])
    is_vip = bool(user[3])
    base_price = reseller_price if is_reseller else normal_price
    final_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if is_vip else base_price
    savings = normal_price - final_price
    if user[0] < final_price:
        return await call.answer(f"❌ Insufficient Balance! Need {fmt_curr(final_price)}.", show_alert=True)

    db_query(
        "UPDATE users SET balance=?, spent=spent+?, orders_count=orders_count+1, total_saved=total_saved+? WHERE user_id=?",
        (user[0] - final_price, final_price, savings, call.from_user.id),
    )

    delivered_key = ""
    if prod[2] > 0:
        key_data = db_query("SELECT id, key_text FROM product_keys WHERE product_id=? AND is_used=0 LIMIT 1", (prod_id,), fetchone=True)
        if key_data:
            delivered_key = key_data[1]
            db_query("UPDATE product_keys SET is_used=1 WHERE id=?", (key_data[0],))
            db_query("UPDATE products SET stock=stock-1 WHERE id=?", (prod_id,))
        else:
            delivered_key = "OUT_OF_STOCK_CONTACT_ADMIN_CODE_01"
    else:
        delivered_key = "OUT_OF_STOCK_CONTACT_ADMIN_CODE_02"

    product_full_name = f"{prod[6]} - {prod[8]} ({prod[0]})"
    db_query(
        "INSERT INTO orders (user_id, product_name, price_paid, delivered_key, purchase_date, status) VALUES (?, ?, ?, ?, ?, 'delivered')",
        (call.from_user.id, product_full_name, final_price, delivered_key,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    log_activity(call.from_user.id, "PURCHASE_SUCCESS", f"Product: {product_full_name}, Paid: {final_price}")
    await send_advanced_notification(call.from_user.id, "ORDER", final_price, product=product_full_name, key=delivered_key)

    key_msg = get_setting("ui_key_message", UI_TEXTS['key_default'])
    msg = (
        f"{get_emoji('check_icon')} <b>✦ 𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟 ✦</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Panel</b> ┃ {prod[6]}\n"
        f"📁 <b>Panel Name</b> ┃ {prod[8]}\n"
        f"⏱ <b>Package</b> ┃ {prod[0]}\n"
        f"💰 <b>Paid</b> ┃ {fmt_curr(final_price)}\n"
        f"📱 <b>Device Limit</b> ┃ {prod[5]}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
    if prod[3] and prod[3].startswith("http"):
        msg += f"📥 <b>APK</b> ┃ <a href='{prod[3]}'>Download Now</a>\n\n"
    if "OUT_OF_STOCK" in delivered_key:
        msg += f"⚠️ <b>✦ 𝗜𝗡𝗩𝗘𝗡𝗧𝗢𝗥𝗬 𝗔𝗟𝗘𝗥𝗧 ✦</b>\nYour balance was deducted but the key vault was empty.\n<i>Contact admin:</i> <code>{ADMIN_CONTACT}</code>\n"
    else:
        msg += f"🔑 <b>Your Exclusive Key</b>\n<code>{delivered_key}</code>\n\n{key_msg}\n"
    await call.message.edit_text(msg, reply_markup=back_kb("menu_shop"), disable_web_page_preview=True, parse_mode='HTML')


# ==============================================================================
# 15. VIP / RESELLER / PROFILE / SUPPORT / TUTORIAL / ORDERS
# ==============================================================================
@dp.callback_query(F.data == "menu_vip_dash")
async def vip_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip, vip_since FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_vip = bool(u[1])
    status_str = "🟢 𝗔𝗰𝘁𝗶𝘃𝗲 (Lifetime)" if is_vip else "🔴 𝗡𝗼𝘁 𝗦𝘂𝗯𝘀𝗰𝗿𝗶𝗯𝗲𝗱"
    text = get_ui_text("vip_menu", vip_status=status_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if is_vip:
        text += f"\n📅 <b>Member Since</b> ┃ {u[2]}\n\n<i>Enjoy your permanent {VIP_DISCOUNT_PERCENTAGE:g}% discount!</i>"
    else:
        text += f"\n\n💳 <b>Your Balance</b> ┃ {fmt_curr(u[0])}\n"
        if u[0] >= VIP_PRICE_INR:
            kb.inline_keyboard.append([InlineKeyboardButton(
                text=f"✅ {fancy('Purchase VIP')} • {fmt_curr(VIP_PRICE_INR)}",
                callback_data="execute_vip_upgrade", style="success",
            )])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(
                text=f"❌ {fancy('Need')} {fmt_curr(VIP_PRICE_INR)} {fancy('to Upgrade')}",
                callback_data="ignore_stock_click", style="danger",
            )])
            kb.inline_keyboard.append([InlineKeyboardButton(text="💳 " + fancy("Add Balance Now"), callback_data="menu_add_balance", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "execute_vip_upgrade")
async def execute_vip_upgrade(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]:
        return await call.answer("⚠️ You are already VIP!", show_alert=True)
    if u[0] < VIP_PRICE_INR:
        return await call.answer(f"❌ Balance below {VIP_PRICE_INR}.", show_alert=True)
    new_balance = u[0] - VIP_PRICE_INR
    now_date = datetime.now().strftime("%Y-%m-%d")
    db_query("UPDATE users SET balance=?, is_vip=1, vip_since=? WHERE user_id=?", (new_balance, now_date, call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_VIP")
    try:
        await bot.send_message(ADMIN_ID, f"🌟 <b>NEW VIP UPGRADE</b>\nUser: <code>{call.from_user.id}</code>", parse_mode='HTML')
    except Exception:
        pass
    await call.answer("🎉 VIP Activated!", show_alert=True)
    await vip_dashboard(call)


@dp.callback_query(F.data == "menu_reseller_dash")
async def reseller_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_reseller, reseller_since, total_saved FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    sys_status_row = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    system_status = sys_status_row[0] if sys_status_row else "ON"
    setup_fee = safe_float(get_setting("reseller_setup_fee", "200.0"))
    min_balance = safe_float(get_setting("reseller_min_balance", "500.0"))
    if u[1]:
        text = (
            f"{get_emoji('shield_icon')} <b>✦ 𝗥𝗘𝗦𝗘𝗟𝗟𝗘𝗥 𝗗𝗔𝗦𝗛𝗕𝗢𝗔𝗥𝗗 ✦</b> {get_emoji('shield_icon')}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🟢 <b>Status</b> ┃ Active\n"
            f"📅 <b>Since</b> ┃ {u[2]}\n"
            f"{get_emoji('money_icon')} <b>Total Saved</b> ┃ {fmt_curr(u[3])}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>You are enjoying wholesale prices on all products.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
                                                                         icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
        await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
        return
    if system_status == "OFF":
        return await call.answer("⚠️ Reseller registrations are currently closed.", show_alert=True)
    text = (
        f"👑 <b>✦ 𝗕𝗘𝗖𝗢𝗠𝗘 𝗔 𝗥𝗘𝗦𝗘𝗟𝗟𝗘𝗥 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"<i>Upgrade to unlock wholesale Reseller Prices.</i>\n\n"
        f"📋 <b>Requirements</b>\n"
        f"╰ 1️⃣ Minimum balance: <b>{fmt_curr(min_balance)}</b>\n"
        f"╰ 2️⃣ One-time setup fee: <b>{fmt_curr(setup_fee)}</b>\n\n"
        f"💳 <b>Your Balance</b> ┃ {fmt_curr(u[0])}\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if u[0] >= min_balance:
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"✅ {fancy('Pay')} {fmt_curr(setup_fee)} {fancy('to Upgrade')}",
            callback_data="execute_reseller_upgrade", style="success",
        )])
    else:
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"❌ {fancy('Need')} {fmt_curr(min_balance)} {fancy('Balance')}",
            callback_data="ignore_stock_click", style="danger",
        )])
        kb.inline_keyboard.append([InlineKeyboardButton(text="💳 " + fancy("Add Balance"), callback_data="menu_add_balance", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "execute_reseller_upgrade")
async def execute_reseller_upgrade(call: CallbackQuery):
    setup_fee = safe_float(get_setting("reseller_setup_fee", "200.0"))
    min_balance = safe_float(get_setting("reseller_min_balance", "500.0"))
    u = db_query("SELECT balance, is_reseller FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]:
        return await call.answer("⚠️ Already a Reseller!", show_alert=True)
    if u[0] < min_balance:
        return await call.answer(f"❌ Balance below {fmt_curr(min_balance)}.", show_alert=True)
    new_balance = u[0] - setup_fee
    db_query("UPDATE users SET balance=?, is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?",
             (new_balance, datetime.now().strftime("%Y-%m-%d"), call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_RESELLER")
    try:
        await bot.send_message(ADMIN_ID, f"👑 <b>NEW RESELLER</b>\nUser: <code>{call.from_user.id}</code>", parse_mode='HTML')
    except Exception:
        pass
    await call.answer("🎉 Welcome to Reseller tier!", show_alert=True)
    await reseller_dashboard(call)


@dp.callback_query(F.data == "menu_profile")
async def show_profile(call: CallbackQuery):
    u = db_query(
        "SELECT user_id, first_name, account_type, balance, orders_count, spent, joined_date, is_reseller, reseller_since, total_saved, is_vip FROM users WHERE user_id=?",
        (call.from_user.id,), fetchone=True,
    )
    acc_type_display = []
    if u[7]:
        acc_type_display.append(f"{get_emoji('reseller')} 𝗥𝗲𝘀𝗲𝗹𝗹𝗲𝗿")
    if u[10]:
        acc_type_display.append(f"{get_emoji('vip')} 𝗩𝗜𝗣")
    type_str = " | ".join(acc_type_display) if acc_type_display else f"{get_emoji('regular_user')} 𝗥𝗲𝗴𝘂𝗹𝗮𝗿 𝗨𝘀𝗲𝗿"
    profile_header = get_setting("ui_profile_message", UI_TEXTS['profile_default'])
    text = (
        f"{get_emoji('grid_id')} <b>{profile_header}</b> {get_emoji('grid_id')}\n━━━━━━━━━━━━━━━━━━\n\n"
        f"{get_emoji('grid_id')} <b>Grid ID</b> ┃ <code>{u[0]}</code>\n"
        f"{get_emoji('name')} <b>Name</b> ┃ {u[1]}\n"
        f"{get_emoji('account_level')} <b>Account Level</b> ┃ {type_str}\n\n"
        f"{get_emoji('wallet_left')} <b>✦ 𝗪𝗔𝗟𝗟𝗘𝗧 ✦</b> {get_emoji('wallet_right')}\n"
        f"{get_emoji('wallet_left')} <b>Balance</b> ┃ {fmt_curr(u[3])} {get_emoji('wallet_right')}\n\n"
        f"{get_emoji('global_stats')} <b>✦ 𝗦𝗧𝗔𝗧𝗦 ✦</b>\n"
        f"{get_emoji('total_orders')} <b>Total Orders</b> ┃ {u[4]}\n"
        f"{get_emoji('total_spent')} <b>Total Spent</b> ┃ {fmt_curr(u[5])}\n"
    )
    if u[7]:
        text += f"{get_emoji('shield_icon')} <b>✦ 𝗥𝗘𝗦𝗘𝗟𝗟𝗘𝗥 ✦</b> {get_emoji('shield_icon')}\n{get_emoji('money_icon')} <b>Saved via Reseller</b> ┃ {fmt_curr(u[9])}\n\n"
    text += f"{get_emoji('joined_grid')} <b>Joined</b> ┃ {u[6]}\n\n"

    orders = db_query("SELECT delivered_key FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,), fetchall=True)
    text += "━━━━━━━━━━━━━━━━━━\n🧾 <b>✦ 𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘 𝗛𝗜𝗦𝗧𝗢𝗥𝗬 ✦</b>\n\n"
    if orders:
        for o in orders:
            text += f"🔑 <code>{o[0]}</code>\n"
    else:
        text += "📭 <i>No purchases yet.</i>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fancy("Redeem Promo Code"), callback_data="redeem_coupon",
                              icon_custom_emoji_id=get_emoji_icon('redeem_icon'), style="success")],
        [InlineKeyboardButton(text=fancy("My Orders"), callback_data="menu_orders", style="primary"),
         InlineKeyboardButton(text=fancy("Transactions"), callback_data="my_txns", style="primary")],
        [InlineKeyboardButton(text=fancy("My Referrals"), callback_data="my_referrals", style="primary")],
        [InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "menu_orders")
async def my_orders(call: CallbackQuery):
    orders = db_query(
        "SELECT product_name, delivered_key, purchase_date, price_paid FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (call.from_user.id,), fetchall=True,
    )
    header = get_setting("ui_orders_message", UI_TEXTS['orders_default'])
    if not orders:
        return await call.message.edit_text(
            f"{header}\n\n📭 <i>Your vault is empty.</i>",
            reply_markup=back_kb("menu_profile"), parse_mode='HTML',
        )
    text = f"{header}\n━━━━━━━━━━━━━━━━━━\n\n"
    for o in orders:
        text += f"📦 <b>{o[0]}</b> • {fmt_curr(o[3])}\n╰ 🔑 <code>{o[1]}</code>\n╰ 📅 <i>{o[2]}</i>\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    await call.message.edit_text(text, reply_markup=back_kb("menu_profile"), parse_mode='HTML')


@dp.callback_query(F.data == "my_txns")
async def my_txns(call: CallbackQuery):
    rows = db_query(
        "SELECT amount_delta, note, created_at FROM wallet_transactions WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (call.from_user.id,), fetchall=True,
    )
    body = "💳 <b>✦ 𝗪𝗔𝗟𝗟𝗘𝗧 𝗧𝗥𝗔𝗡𝗦𝗔𝗖𝗧𝗜𝗢𝗡𝗦 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
    if rows:
        for r in rows:
            sign = "+" if r[0] >= 0 else ""
            body += f"{r[2]}\n<b>{sign}{fmt_curr(r[0])}</b> • <i>{r[1]}</i>\n\n"
    else:
        body += "📭 No transactions yet."
    await call.message.edit_text(body[:4000], reply_markup=back_kb("menu_profile"), parse_mode='HTML')


@dp.callback_query(F.data == "my_referrals")
async def my_referrals(call: CallbackQuery):
    me = db_query("SELECT COUNT(*) FROM users WHERE referred_by=?", (call.from_user.id,), fetchone=True)
    ref_count = me[0] if me else 0
    reward = get_setting("refer_earn_amount", "0")
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{call.from_user.id}"
    text = (
        f"👥 <b>✦ 𝗠𝗬 𝗥𝗘𝗙𝗘𝗥𝗥𝗔𝗟𝗦 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"Total referrals: <b>{ref_count}</b>\n"
        f"Reward per new user: <b>{fmt_curr(safe_float(reward))}</b>\n\n"
        f"🔗 Your link:\n<code>{link}</code>"
    )
    await call.message.edit_text(text, reply_markup=back_kb("menu_profile"), parse_mode='HTML')


@dp.callback_query(F.data == "redeem_coupon")
async def redeem_coupon_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🎟 <b>✦ 𝗥𝗘𝗗𝗘𝗘𝗠 𝗖𝗢𝗗𝗘 ✦</b>\n━━━━━━━━━━━━━━━━━━\n<i>Send your promo / VIP code below</i>",
        reply_markup=back_kb("menu_profile"), parse_mode='HTML',
    )
    await state.set_state(UserStates.wait_for_redeem)


@dp.message(UserStates.wait_for_redeem)
async def process_redeem(m: Message, state: FSMContext):
    code = m.text.strip().upper()
    user_id = m.from_user.id
    if db_query("SELECT * FROM redeemed WHERE user_id=? AND code=?", (user_id, code), fetchone=True):
        await m.answer("❌ Already redeemed.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
        await state.clear()
        return
    coupon = db_query("SELECT amount, uses_left FROM coupons WHERE code=?", (code,), fetchone=True)
    if not coupon:
        await m.answer("❌ Invalid code.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    elif coupon[1] <= 0:
        await m.answer("❌ Code fully claimed.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    else:
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (coupon[0], user_id))
        db_query("UPDATE coupons SET uses_left = uses_left - 1 WHERE code=?", (code,))
        db_query("INSERT INTO redeemed (user_id, code) VALUES (?, ?)", (user_id, code))
        db_query("INSERT INTO wallet_transactions (user_id, amount_delta, note) VALUES (?, ?, ?)", (user_id, coupon[0], f"Promo {code}"))
        log_activity(user_id, "PROMO_REDEEMED", f"Code: {code}, Amount: {coupon[0]}")
        await m.answer(
            f"🎉 <b>✦ 𝗖𝗢𝗗𝗘 𝗥𝗘𝗗𝗘𝗘𝗠𝗘𝗗 ✦</b>\n━━━━━━━━━━━━━━━━━━\n💎 <b>Added</b> ┃ {fmt_curr(coupon[0])}",
            reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML',
        )
    await state.clear()


@dp.callback_query(F.data == "daily_gift")
async def daily_gift(call: CallbackQuery):
    gift = safe_float(get_setting("daily_gift_price", "0"), 0.0)
    if gift <= 0:
        return await call.message.edit_text("🎁 Daily gift is disabled.", reply_markup=back_kb("back_main"), parse_mode='HTML')
    user_id = call.from_user.id
    u = db_query("SELECT last_gift FROM users WHERE user_id=?", (user_id,), fetchone=True)
    today = datetime.now().strftime("%Y-%m-%d")
    if u and u[0] == today:
        return await call.message.edit_text("🎁 Aaj ka gift already claimed!", reply_markup=back_kb("back_main"), parse_mode='HTML')
    db_query("UPDATE users SET balance=balance+?, last_gift=? WHERE user_id=?", (gift, today, user_id))
    db_query("INSERT INTO wallet_transactions (user_id, amount_delta, note) VALUES (?, ?, ?)", (user_id, gift, "Daily gift"))
    await call.message.edit_text(
        f"🎁 <b>✦ 𝗗𝗔𝗜𝗟𝗬 𝗚𝗜𝗙𝗧 𝗖𝗟𝗔𝗜𝗠𝗘𝗗 ✦</b>\n━━━━━━━━━━━━━━━━━━\n💰 +{fmt_curr(gift)} credited!",
        reply_markup=back_kb("back_main"), parse_mode='HTML',
    )


@dp.callback_query(F.data == "menu_how_to")
async def tutorial_system(call: CallbackQuery):
    video_link_query = db_query("SELECT value FROM settings WHERE key='how_to_video'", fetchone=True)
    video_link = video_link_query[0] if video_link_query and video_link_query[0] != 'None' else None
    extra_url = get_setting("how_to_use_url", "")
    text = (
        f"{get_emoji('tutorial')} <b>✦ 𝗧𝗨𝗧𝗢𝗥𝗜𝗔𝗟𝗦 𝗔𝗡𝗗 𝗚𝗨𝗜𝗗𝗘 ✦</b> {get_emoji('tutorial')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"1️⃣ Add funds via <b>Add Balance</b>\n"
        f"2️⃣ Open the <b>Product Store</b>\n"
        f"3️⃣ Pick your Panel and Package\n"
        f"4️⃣ Receive your Key and APK link instantly\n"
        f"━━━━━━━━━━━━━━━━━━\n<i>Need help? Tap Support.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if video_link:
        kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Watch Video Tutorial"), url=video_link,
                                                         icon_custom_emoji_id=get_emoji_icon("tutorial"), style="primary")])
    if extra_url:
        kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Open How-To Guide"), url=extra_url, style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "menu_support")
async def support_center(call: CallbackQuery):
    telegram_link = get_setting("support_telegram", "https://t.me/YourSupport")
    whatsapp_link = get_setting("support_whatsapp", "https://wa.me/YourNumber")
    header = get_setting("ui_support_message", UI_TEXTS['support_default'])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fancy("Telegram Support"), url=telegram_link,
                              icon_custom_emoji_id=get_emoji_icon("telegram"), style="primary")],
        [InlineKeyboardButton(text=fancy("WhatsApp Support"), url=whatsapp_link,
                              icon_custom_emoji_id=get_emoji_icon("whatsapp"), style="primary")],
        [InlineKeyboardButton(text="🎫 " + fancy("New Ticket"), callback_data="open_ticket", style="primary"),
         InlineKeyboardButton(text="📋 " + fancy("My Tickets"), callback_data="my_tickets", style="primary")],
        [InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text(header, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "my_tickets")
async def view_my_tickets(call: CallbackQuery):
    tickets = db_query(
        "SELECT id, message, status, created_at FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 5",
        (call.from_user.id,), fetchall=True,
    )
    if not tickets:
        return await call.message.edit_text("📋 <b>No tickets yet.</b>", reply_markup=back_kb("menu_support"), parse_mode='HTML')
    text = "📋 <b>✦ 𝗬𝗢𝗨𝗥 𝗧𝗜𝗖𝗞𝗘𝗧𝗦 ✦</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for t in tickets:
        status_icon = "🟢" if t[2] == 'Open' else "🔴"
        text += f"🎫 <b>Ticket #{t[0]}</b> ┃ {status_icon} <b>{t[2]}</b>\n╰ 📅 <i>{t[3]}</i>\n╰ 📝 <i>{t[1][:80]}...</i>\n\n"
    await call.message.edit_text(text, reply_markup=back_kb("menu_support"), parse_mode='HTML')


@dp.callback_query(F.data == "open_ticket")
async def open_ticket_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "📝 <b>✦ 𝗡𝗘𝗪 𝗧𝗜𝗖𝗞𝗘𝗧 ✦</b>\n━━━━━━━━━━━━━━━━━━\n<i>Describe your issue below</i>",
        reply_markup=back_kb("menu_support"), parse_mode='HTML',
    )
    await state.set_state(UserStates.wait_for_ticket)


@dp.message(UserStates.wait_for_ticket)
async def process_ticket(m: Message, state: FSMContext):
    db_query(
        "INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)",
        (m.from_user.id, m.text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    await m.answer("✅ <b>Ticket submitted!</b>", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    try:
        await bot.send_message(ADMIN_ID, f"🚨 <b>NEW TICKET</b>\nFrom: <code>{m.from_user.id}</code>\nMsg: {m.text}", parse_mode='HTML')
    except Exception:
        pass
    log_activity(m.from_user.id, "OPENED_TICKET")
    await state.clear()


# ==============================================================================
# 16. PROOF HANDLER — Balance proof + Order proof
# ==============================================================================
@dp.message(UserStates.awaiting_balance_proof, F.photo)
async def handle_balance_proof(m: Message, state: FSMContext):
    user = m.from_user
    data = await state.get_data()
    amount = float(data.get("pending_balance_amount", 0))
    file_id = m.photo[-1].file_id
    req_id = db_query(
        "INSERT INTO balance_requests (user_id, username, amount, method, proof_file_id, status, created_at) VALUES (?, ?, ?, 'qr', ?, 'pending', ?)",
        (user.id, user.username or user.first_name, amount, file_id,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ) or 0
    # lastrowid via separate call:
    row = db_query("SELECT id FROM balance_requests WHERE user_id=? ORDER BY id DESC LIMIT 1", (user.id,), fetchone=True)
    req_id = row[0] if row else req_id
    await state.clear()
    await m.answer(
        f"✅ <b>✦ 𝗣𝗥𝗢𝗢𝗙 𝗦𝗨𝗕𝗠𝗜𝗧𝗧𝗘𝗗 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"📋 Request <b>#{req_id}</b> admin approval ke liye bhej di gayi.",
        reply_markup=main_menu_kb(user.id), parse_mode='HTML',
    )
    admin_msg = (
        f"💰 <b>BALANCE REQUEST #{req_id}</b>\n"
        f"👤 {user.full_name} (@{user.username or 'no_username'})\n"
        f"🆔 <code>{user.id}</code>\n"
        f"💵 Amount: <b>{fmt_curr(amount)}</b>\n\n"
        f"Verify karke approve/reject karein."
    )
    kb_btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve", callback_data=f"bappr_{req_id}", style="success"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"brej_{req_id}", style="danger"),
    ]])
    await notify_all_admins(admin_msg, kb_btn, photo_id=file_id)


@dp.callback_query(F.data.startswith("bappr_"))
async def approve_balance(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    req_id = int(call.data.split("_")[1])
    req = db_query("SELECT user_id, amount, status FROM balance_requests WHERE id=?", (req_id,), fetchone=True)
    if not req or req[2] != "pending":
        return await call.answer("Already processed.", show_alert=True)
    db_query("UPDATE balance_requests SET status='approved', reviewed_at=? WHERE id=?",
             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), req_id))
    db_query("UPDATE users SET balance=balance+? WHERE user_id=?", (req[1], req[0]))
    db_query("INSERT INTO wallet_transactions (user_id, amount_delta, note) VALUES (?, ?, ?)",
             (req[0], req[1], f"Balance request #{req_id}"))
    await call.answer("✅ Approved!", show_alert=True)
    try:
        await bot.send_message(req[0], f"✅ <b>Balance request #{req_id} approved!</b>\n+{fmt_curr(req[1])}", parse_mode='HTML')
    except Exception:
        pass
    try:
        await call.message.edit_caption(caption=f"✅ Balance request #{req_id} — APPROVED", parse_mode='HTML')
    except Exception:
        try:
            await call.message.edit_text(f"✅ Balance request #{req_id} — APPROVED", parse_mode='HTML')
        except Exception:
            pass


@dp.callback_query(F.data.startswith("brej_"))
async def reject_balance(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    req_id = int(call.data.split("_")[1])
    req = db_query("SELECT user_id, status FROM balance_requests WHERE id=?", (req_id,), fetchone=True)
    if not req or req[1] != "pending":
        return await call.answer("Already processed.", show_alert=True)
    db_query("UPDATE balance_requests SET status='rejected', reviewed_at=? WHERE id=?",
             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), req_id))
    await call.answer("❌ Rejected.", show_alert=True)
    try:
        await bot.send_message(req[0], f"❌ <b>Balance request #{req_id} rejected.</b>", parse_mode='HTML')
    except Exception:
        pass
    try:
        await call.message.edit_caption(caption=f"❌ Balance request #{req_id} — REJECTED", parse_mode='HTML')
    except Exception:
        try:
            await call.message.edit_text(f"❌ Balance request #{req_id} — REJECTED", parse_mode='HTML')
        except Exception:
            pass


@dp.message(UserStates.awaiting_balance_proof)
async def handle_balance_proof_text(m: Message, state: FSMContext):
    await m.answer("📸 Please send a screenshot (photo) as proof.")


# ==============================================================================
# 17. ADMIN PANEL
# ==============================================================================
@dp.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if not is_co_admin(message.from_user.id):
        return
    await state.clear()
    logo = get_setting("admin_logo_file_id", "")
    total_users = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    msg = (
        f"⚙️ <b>✦ 𝗔𝗗𝗠𝗜𝗡 𝗧𝗘𝗥𝗠𝗜𝗡𝗔𝗟 ✦</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Users: <b>{total_users}</b>\n"
        f"<i>Authorized access granted.</i>"
    )
    if logo:
        try:
            await message.answer_photo(logo, caption=msg, reply_markup=admin_kb(), parse_mode='HTML')
            return
        except Exception:
            pass
    await message.answer(msg, reply_markup=admin_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "admin_panel_back")
async def back_to_admin(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await state.clear()
    msg = "⚙️ <b>✦ 𝗔𝗗𝗠𝗜𝗡 𝗧𝗘𝗥𝗠𝗜𝗡𝗔𝗟 ✦</b>\n━━━━━━━━━━━━━━━━━━\n<i>Authorized access granted.</i>"
    try:
        await call.message.edit_text(msg, reply_markup=admin_kb(), parse_mode='HTML')
    except Exception:
        await call.message.edit_caption(caption=msg, reply_markup=admin_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "admin_toggle_bot")
async def toggle_bot(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    res = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_status', ?)", (new_status,))
    try:
        await call.message.edit_reply_markup(reply_markup=admin_kb())
    except Exception:
        await call.message.edit_caption(caption="⚙️ Admin Panel", reply_markup=admin_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "admin_toggle_vip_sys")
async def toggle_vip_sys(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    res = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    current = res[0] if res else 'OFF'
    new_status = 'ON' if current == 'OFF' else 'OFF'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('vip_status', ?)", (new_status,))
    try:
        await call.message.edit_reply_markup(reply_markup=admin_kb())
    except Exception:
        await call.message.edit_caption(caption="⚙️ Admin Panel", reply_markup=admin_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "admin_view_stats")
async def admin_dashboard_stats(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    t_users = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    t_resellers = db_query("SELECT COUNT(*) FROM users WHERE is_reseller=1", fetchone=True)[0]
    t_vip = db_query("SELECT COUNT(*) FROM users WHERE is_vip=1", fetchone=True)[0]
    t_prods = db_query("SELECT COUNT(*) FROM products", fetchone=True)[0]
    t_keys = db_query("SELECT COUNT(*) FROM product_keys WHERE is_used=0", fetchone=True)[0]
    t_rev = db_query("SELECT SUM(spent) FROM users", fetchone=True)[0] or 0.0
    t_pending_bal = db_query("SELECT COUNT(*) FROM balance_requests WHERE status='pending'", fetchone=True)[0]
    t_coadmins = db_query("SELECT COUNT(*) FROM co_admins", fetchone=True)[0]
    msg = (
        f"📊 <b>✦ 𝗦𝗧𝗢𝗥𝗘 𝗔𝗡𝗔𝗟𝗬𝗧𝗜𝗖𝗦 ✦</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Users</b> ┃ {t_users}\n"
        f"👑 <b>Resellers</b> ┃ {t_resellers}\n"
        f"🌟 <b>VIP Members</b> ┃ {t_vip}\n"
        f"🤝 <b>Co-Admins</b> ┃ {t_coadmins}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Products</b> ┃ {t_prods}\n"
        f"🔑 <b>Unused Keys</b> ┃ {t_keys}\n"
        f"💰 <b>Gross Revenue</b> ┃ {fmt_curr(t_rev)}\n"
        f"🧾 <b>Pending Bal Requests</b> ┃ {t_pending_bal}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    await call.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode='HTML')


# -------------------- USER CONTROL PANEL --------------------
@dp.callback_query(F.data == "admin_user_control_start")
async def admin_user_control_start(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Download Full User List", callback_data="admin_download_userlist", style="success")],
        [InlineKeyboardButton(text="👥 All Users", callback_data="admin_list_users", style="primary")],
        [InlineKeyboardButton(text=fancy("Back to Admin"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text(
        "💻 <b>User Control Terminal</b>\n\n"
        "✏️ Enter <b>User ID</b> or <b>@Username</b> to manage:\n\n"
        "👇 OR download full list:",
        reply_markup=kb, parse_mode='HTML',
    )
    await state.set_state(AdminStates.manage_target_user)


@dp.callback_query(F.data == "admin_list_users")
async def admin_list_users(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    users = db_query(
        "SELECT user_id, first_name, username, balance, is_reseller, is_vip FROM users ORDER BY user_id DESC LIMIT 30",
        fetchall=True,
    )
    if not users:
        return await call.answer("No users yet.", show_alert=True)
    body = "👥 <b>✦ USERS (latest 30) ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
    for u in users:
        body += f"🆔 <code>{u[0]}</code> │ {(u[1] or 'Unknown')[:20]}\n💰 {fmt_curr(u[3])} │ {'👑' if u[4] else ''}{'🌟' if u[5] else ''}\n\n"
    await call.message.edit_text(body[:4000], reply_markup=admin_back_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "admin_download_userlist")
async def admin_download_userlist(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    users = db_query(
        "SELECT username, user_id, phone, balance, orders_count, is_vip, is_reseller FROM users",
        fetchall=True,
    )
    if not users:
        return await call.answer("No users.", show_alert=True)
    content = "USER DATABASE DUMP\n" + "=" * 100 + "\n"
    for u in users:
        content += (
            f"UID: {u[1]} | UNAME: {u[0] or 'N/A'} | PHONE: {u[2] or 'N/A'} | "
            f"BAL: ₹{u[3]:.2f} | ORDERS: {u[4]} | VIP: {'Y' if u[5] else 'N'} | "
            f"RES: {'Y' if u[6] else 'N'}\n"
        )
    doc = BufferedInputFile(content.encode(), filename=f"users_{datetime.now().strftime('%Y%m%d')}.txt")
    await call.message.answer_document(doc, caption="📋 <b>User DB Export</b>", parse_mode='HTML')
    await call.answer()


@dp.message(AdminStates.manage_target_user)
async def process_user_lookup(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    target = m.text.strip()
    if target.startswith('@'):
        target = target[1:]
    user_q = db_query(
        "SELECT user_id, first_name, username, balance, is_reseller, orders_count, spent, joined_date, is_banned, warnings, is_vip FROM users WHERE user_id=? OR username=? COLLATE NOCASE",
        (target, target), fetchone=True,
    )
    if not user_q:
        return await m.answer("❌ Target not found.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name, u_user, bal, is_res, orders, spent, joined, is_banned, warnings, is_vip = user_q
    await state.update_data(target_u_id=u_id)
    status_emoji = "🔴 BANNED" if is_banned else "🟢 ACTIVE"
    tags = []
    if is_res:
        tags.append("👑 Reseller")
    if is_vip:
        tags.append("🌟 VIP")
    type_str = " | ".join(tags) if tags else "👤 Regular"
    text = (
        f"🛡 <b><u>USER CONTROL</u></b> 🛡\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📛 <b>Name:</b> {u_name} (@{u_user or 'N/A'})\n"
        f"🆔 <b>ID:</b> <code>{u_id}</code>\n"
        f"📊 <b>Status:</b> {status_emoji}\n"
        f"🔰 <b>Type:</b> {type_str}\n"
        f"⚠️ <b>Warnings:</b> {warnings}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Wallet:</b> {fmt_curr(bal)}\n"
        f"📦 <b>Orders:</b> {orders} | 💸 <b>Spent:</b> {fmt_curr(spent)}\n"
        f"📅 <b>Joined:</b> {joined}"
    )
    ban_btn_text = "Unban ✅" if is_banned else "Ban 🚫"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Add Funds ➕", callback_data=f"usrctrl_add_{u_id}", style="success"),
         InlineKeyboardButton(text="Minus Funds ➖", callback_data=f"usrctrl_min_{u_id}", style="danger")],
        [InlineKeyboardButton(text=ban_btn_text, callback_data=f"usrctrl_ban_{u_id}", style="danger"),
         InlineKeyboardButton(text="Warn ⚠️", callback_data=f"usrctrl_warn_{u_id}", style="danger")],
        [InlineKeyboardButton(text="Give VIP 🌟" if not is_vip else "Remove VIP 🚫",
                              callback_data=f"usrctrl_vip_{u_id}", style="success")],
        [InlineKeyboardButton(text=fancy("Back to Admin"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await m.answer(text, reply_markup=kb, parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data.startswith("usrctrl_"))
async def handle_user_actions(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    action = parts[1]
    u_id = int(parts[2])
    await state.update_data(target_u_id=u_id)
    if action == "ban":
        current_status = db_query("SELECT is_banned FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if current_status == 0:
            db_query("UPDATE users SET is_banned=1 WHERE user_id=?", (u_id,))
            await call.answer("🔴 User banned!", show_alert=True)
        else:
            db_query("UPDATE users SET is_banned=0 WHERE user_id=?", (u_id,))
            await call.answer("✅ User unbanned!", show_alert=True)
    elif action == "vip":
        current_status = db_query("SELECT is_vip FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if current_status == 1:
            db_query("UPDATE users SET is_vip=0 WHERE user_id=?", (u_id,))
            await call.answer("✅ VIP Removed!", show_alert=True)
        else:
            db_query("UPDATE users SET is_vip=1, vip_since=? WHERE user_id=?",
                     (datetime.now().strftime("%Y-%m-%d"), u_id))
            await call.answer("✅ VIP Granted!", show_alert=True)
    elif action == "add":
        await call.message.edit_text("💰 Enter amount to ADD:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_money)
        return
    elif action == "min":
        await call.message.edit_text("💸 Enter amount to DEDUCT:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_minus_money)
        return
    elif action == "warn":
        await call.message.edit_text("⚠️ Type the warning message:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_warning)
        return
    m = call.message
    m.text = str(u_id)
    m.from_user = call.from_user
    await process_user_lookup(m, state)


@dp.message(AdminStates.wait_for_add_money)
async def exec_add_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        data = await state.get_data()
        u_id = data['target_u_id']
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, u_id))
        db_query("INSERT INTO wallet_transactions (user_id, amount_delta, note) VALUES (?, ?, ?)",
                 (u_id, amt, "Admin credit"))
        await m.answer(f"✅ Added {fmt_curr(amt)} to <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
        try:
            await bot.send_message(u_id, f"💰 <b>Wallet Top-up!</b>\nAdmin added {fmt_curr(amt)}.", parse_mode='HTML')
        except Exception:
            pass
        await state.clear()
    except ValueError:
        await m.answer("❌ Invalid number.")


@dp.message(AdminStates.wait_for_minus_money)
async def exec_minus_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        data = await state.get_data()
        u_id = data['target_u_id']
        db_query("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id=?", (amt, u_id))
        db_query("INSERT INTO wallet_transactions (user_id, amount_delta, note) VALUES (?, ?, ?)",
                 (u_id, -amt, "Admin debit"))
        await m.answer(f"✅ Deducted {fmt_curr(amt)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError:
        await m.answer("❌ Invalid number.")


@dp.message(AdminStates.wait_for_warning)
async def exec_warn_user(m: Message, state: FSMContext):
    data = await state.get_data()
    u_id = data['target_u_id']
    db_query("UPDATE users SET warnings = warnings + 1 WHERE user_id=?", (u_id,))
    await m.answer(f"✅ Warning dispatched to <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
    try:
        await bot.send_message(u_id, f"⚠️ <b>OFFICIAL WARNING:</b>\n\n{m.text}", parse_mode='HTML')
    except Exception:
        pass
    await state.clear()


# -------------------- BALANCE MANAGER --------------------
@dp.callback_query(F.data == "admin_bal_menu")
async def admin_bal_menu(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Balance", callback_data="adm_bal_add", style="success"),
         InlineKeyboardButton(text="➖ Remove Balance", callback_data="adm_bal_remove", style="danger")],
        [InlineKeyboardButton(text="🔍 Check Balance", callback_data="adm_bal_check", style="primary"),
         InlineKeyboardButton(text="👥 Add to All Users", callback_data="adm_bal_addall", style="primary")],
        [InlineKeyboardButton(text="🧾 Balance Requests", callback_data="admin_bal_requests", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("💰 <b>✦ BALANCE MANAGER ✦</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "adm_bal_add")
async def adm_bal_add(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("➕ User ID bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.bal_add_uid)


@dp.message(AdminStates.bal_add_uid)
async def adm_bal_add_uid(m: Message, state: FSMContext):
    if not m.text.strip().isdigit():
        return await m.answer("❌ Numeric ID bhejein.")
    await state.update_data(bal_target_uid=int(m.text.strip()))
    await m.answer("Amount ₹ bhejein:")
    await state.set_state(AdminStates.bal_add_amt)


@dp.message(AdminStates.bal_add_amt)
async def adm_bal_add_amt(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
    except ValueError:
        return await m.answer("❌ Number bhejein.")
    data = await state.get_data()
    uid = data.get("bal_target_uid", 0)
    if not db_query("SELECT 1 FROM users WHERE user_id=?", (uid,), fetchone=True):
        await state.clear()
        return await m.answer("❌ User not found.", reply_markup=admin_kb(), parse_mode='HTML')
    db_query("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
    db_query("INSERT INTO wallet_transactions (user_id, amount_delta, note) VALUES (?, ?, ?)",
             (uid, amt, "Admin credit"))
    await state.clear()
    await m.answer(f"✅ Added {fmt_curr(amt)} to <code>{uid}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
    try:
        await bot.send_message(uid, f"💰 Admin added {fmt_curr(amt)}!", parse_mode='HTML')
    except Exception:
        pass


@dp.callback_query(F.data == "adm_bal_remove")
async def adm_bal_remove(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("➖ User ID bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.bal_remove_uid)


@dp.message(AdminStates.bal_remove_uid)
async def adm_bal_remove_uid(m: Message, state: FSMContext):
    if not m.text.strip().isdigit():
        return await m.answer("❌ Numeric ID bhejein.")
    await state.update_data(bal_target_uid=int(m.text.strip()))
    await m.answer("Amount ₹ bhejein:")
    await state.set_state(AdminStates.bal_remove_amt)


@dp.message(AdminStates.bal_remove_amt)
async def adm_bal_remove_amt(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
    except ValueError:
        return await m.answer("❌ Number bhejein.")
    data = await state.get_data()
    uid = data.get("bal_target_uid", 0)
    db_query("UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=?", (amt, uid))
    db_query("INSERT INTO wallet_transactions (user_id, amount_delta, note) VALUES (?, ?, ?)",
             (uid, -amt, "Admin debit"))
    await state.clear()
    await m.answer(f"✅ Removed {fmt_curr(amt)}.", reply_markup=admin_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "adm_bal_check")
async def adm_bal_check(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("🔍 User ID bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.bal_check_uid)


@dp.message(AdminStates.bal_check_uid)
async def adm_bal_check_uid(m: Message, state: FSMContext):
    if not m.text.strip().isdigit():
        return await m.answer("❌ Numeric ID bhejein.")
    uid = int(m.text.strip())
    u = db_query("SELECT balance, first_name FROM users WHERE user_id=?", (uid,), fetchone=True)
    await state.clear()
    if u:
        await m.answer(f"👤 {u[1]}\n💰 Balance: {fmt_curr(u[0])}", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        await m.answer("❌ User not found.", reply_markup=admin_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "adm_bal_addall")
async def adm_bal_addall(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("👥 Amount ₹ bhejein (sab users ko add hoga):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.bal_addall_amt)


@dp.message(AdminStates.bal_addall_amt)
async def adm_bal_addall_amt(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
    except ValueError:
        return await m.answer("❌ Number bhejein.")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET balance=balance+?", (amt,))
    conn.commit()
    conn.close()
    await state.clear()
    await m.answer(f"✅ Added {fmt_curr(amt)} to ALL users.", reply_markup=admin_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "admin_bal_requests")
async def admin_bal_requests(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    rows = db_query(
        "SELECT id, user_id, username, amount, method, status, created_at FROM balance_requests WHERE status='pending' ORDER BY id DESC LIMIT 20",
        fetchall=True,
    )
    if not rows:
        return await call.answer("✅ No pending balance requests.", show_alert=True)
    body = "🧾 <b>✦ PENDING BALANCE REQUESTS ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
    kb_rows = []
    for r in rows:
        body += f"#{r[0]} • <code>{r[1]}</code> • {fmt_curr(r[3])}\n@{r[2] or 'N/A'} • {r[5]} • {r[6]}\n\n"
        kb_rows.append([
            InlineKeyboardButton(text=f"✅ #{r[0]}", callback_data=f"bappr_{r[0]}", style="success"),
            InlineKeyboardButton(text=f"❌ #{r[0]}", callback_data=f"brej_{r[0]}", style="danger"),
        ])
    kb_rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                                          icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(body[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode='HTML')


# -------------------- PRODUCT MANAGEMENT --------------------
@dp.callback_query(F.data == "admin_manage_prods")
async def admin_manage_prods(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    prods = db_query(
        "SELECT id, name, category, panel_name, stock, is_active FROM products ORDER BY category, panel_name",
        fetchall=True,
    )
    if not prods:
        return await call.message.edit_text("📦 Store Database empty.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in prods:
        status_dot = "🟢" if p[5] else "🔴"
        panel_name = p[3] if p[3] is not None else ""
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{status_dot} [{p[2]}] {panel_name} - {p[1]} (Stock: {p[4]})",
            callback_data=f"admin_view_p_{p[0]}", style="primary",
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back to Admin"), callback_data="admin_panel_back",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("📦 <b>Select a node to modify</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("admin_view_p_"))
async def admin_view_product(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    try:
        p_id = int(call.data.split("_")[3])
        prod = db_query("SELECT * FROM products WHERE id=?", (p_id,), fetchone=True)
        if not prod:
            return await call.answer("❌ Not found!", show_alert=True)
        panel_name = prod[2] if prod[2] is not None else ""
        price_inr = safe_float(prod[4])
        reseller_price = safe_float(prod[5])
        text = (
            f"📦 <b><u>NODE #{prod[0]}</u></b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Panel Group:</b> {prod[1]}\n"
            f"<b>Panel Name:</b> {panel_name}\n"
            f"<b>Package:</b> {prod[3]}\n"
            f"<b>Standard Price:</b> {fmt_curr(price_inr)}\n"
            f"👑 <b>Wholesale:</b> {fmt_curr(reseller_price)}\n"
            f"<b>Stock:</b> {prod[6]}\n"
            f"<b>APK:</b> {prod[7] if prod[7] else 'None'}\n"
            f"<b>Validity:</b> {prod[8]}\n"
            f"<b>Device:</b> {prod[9]}\n"
            f"<b>Visibility:</b> {'Active' if prod[10] else 'Hidden'}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        toggle_btn_text = "Hide 👁‍🗨" if prod[10] else "Unhide 👁"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Edit Panel 🏷️", callback_data=f"edit_p_{p_id}_cat", style="primary"),
             InlineKeyboardButton(text="Edit Panel Name 🏷️", callback_data=f"edit_p_{p_id}_panel_name", style="primary")],
            [InlineKeyboardButton(text="Edit Name ✏️", callback_data=f"edit_p_{p_id}_name", style="primary")],
            [InlineKeyboardButton(text="Edit Price 💰", callback_data=f"edit_p_{p_id}_price", style="primary"),
             InlineKeyboardButton(text="Edit R-Price 👑", callback_data=f"edit_p_{p_id}_rprice", style="primary")],
            [InlineKeyboardButton(text="Edit Validity ⏳", callback_data=f"edit_p_{p_id}_validity", style="primary"),
             InlineKeyboardButton(text="Edit Device 📱", callback_data=f"edit_p_{p_id}_device", style="primary")],
            [InlineKeyboardButton(text="Edit APK 🔗", callback_data=f"edit_p_{p_id}_apk", style="primary"),
             InlineKeyboardButton(text="Add Keys ➕", callback_data=f"edit_p_{p_id}_keys", style="success")],
            [InlineKeyboardButton(text="Delete Key 🗑", callback_data=f"delkey_p_{p_id}", style="danger"),
             InlineKeyboardButton(text=toggle_btn_text, callback_data=f"toggle_p_{p_id}", style="danger")],
            [InlineKeyboardButton(text="Nuke Node 🗑", callback_data=f"delete_p_{p_id}", style="danger"),
             InlineKeyboardButton(text=fancy("BACK"), callback_data="admin_manage_prods",
                                  icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
        ])
        await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error in admin_view_product: {e}")
        await call.message.edit_text(f"❌ Error: {e}", reply_markup=admin_back_kb(), parse_mode='HTML')


@dp.callback_query(F.data.startswith("toggle_p_"))
async def admin_toggle_product(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    p_id = int(call.data.split("_")[2])
    current = db_query("SELECT is_active FROM products WHERE id=?", (p_id,), fetchone=True)[0]
    new_val = 0 if current == 1 else 1
    db_query("UPDATE products SET is_active=? WHERE id=?", (new_val, p_id))
    await call.answer("Visibility updated!", show_alert=True)
    await admin_view_product(call)


@dp.callback_query(F.data.startswith("edit_p_"))
async def start_edit_product(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    parts = call.data.split("_", 3)
    if len(parts) < 4:
        return await call.answer("Invalid data.", show_alert=True)
    p_id = int(parts[2])
    field = parts[3]
    await state.update_data(edit_p_id=p_id, edit_field=field)
    if field == 'keys':
        await call.message.edit_text("📥 Paste NEW KEYS (1 per line):", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_keys)
    else:
        field_map = {
            'cat': 'New Panel Group',
            'panel_name': 'New Panel Name',
            'name': 'New Package Name',
            'price': 'New Standard Price in ₹',
            'rprice': 'New Reseller Price in ₹',
            'validity': 'New Validity String',
            'device': 'New Device Limit',
            'apk': 'New APK Link (or "none")',
        }
        await call.message.edit_text(f"✏️ Input for: <b>{field_map.get(field, field)}</b>",
                                      reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_new_value)


@dp.message(AdminStates.wait_for_new_value)
async def process_edit_value(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    data = await state.get_data()
    p_id = data['edit_p_id']
    field = data['edit_field']
    new_val = m.text.strip()
    if field in ['price', 'rprice']:
        try:
            new_val = float(new_val)
        except ValueError:
            return await m.answer("❌ Invalid number.")
    elif field == 'apk':
        new_val = "" if new_val.lower() == 'none' else new_val
    db_col_map = {
        'cat': 'category', 'panel_name': 'panel_name', 'name': 'name',
        'price': 'price_inr', 'rprice': 'reseller_price', 'validity': 'validity',
        'device': 'device_limit', 'apk': 'apk_link',
    }
    db_query(f"UPDATE products SET {db_col_map[field]}=? WHERE id=?", (new_val, p_id))
    await m.answer("✅ Node updated!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.message(AdminStates.wait_for_add_keys)
async def process_add_keys(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    data = await state.get_data()
    p_id = data['edit_p_id']
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    if not keys:
        return await m.answer("❌ No keys.", reply_markup=admin_kb(), parse_mode='HTML')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for k in keys:
        c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (p_id, k))
    c.execute("UPDATE products SET stock = stock + ? WHERE id=?", (len(keys), p_id))
    conn.commit()
    conn.close()
    await m.answer(f"✅ {len(keys)} keys added!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data.startswith("delete_p_"))
async def admin_delete_product(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    p_id = int(call.data.split("_")[2])
    db_query("DELETE FROM products WHERE id=?", (p_id,))
    db_query("DELETE FROM product_keys WHERE product_id=?", (p_id,))
    await call.answer("☢️ Deleted!", show_alert=True)
    await admin_manage_prods(call)


@dp.callback_query(F.data.startswith("delkey_p_"))
async def admin_delete_key_start(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    p_id = int(call.data.split("_")[2])
    await state.update_data(del_p_id=p_id)
    await call.message.edit_text("🗑 Send exact key to delete:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_delete_key)


@dp.message(AdminStates.wait_for_delete_key)
async def process_delete_key(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    data = await state.get_data()
    p_id = data['del_p_id']
    key_to_delete = m.text.strip()
    key_data = db_query("SELECT id, is_used FROM product_keys WHERE product_id=? AND key_text=?",
                        (p_id, key_to_delete), fetchone=True)
    if not key_data:
        return await m.answer("❌ Key not found.", reply_markup=admin_back_kb(), parse_mode='HTML')
    if key_data[1] == 1:
        return await m.answer("⚠️ Key already dispatched!", reply_markup=admin_back_kb(), parse_mode='HTML')
    db_query("DELETE FROM product_keys WHERE id=?", (key_data[0],))
    db_query("UPDATE products SET stock = stock - 1 WHERE id=?", (p_id,))
    await m.answer("✅ Key purged.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_add_prod")
async def add_prod_start(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in FIXED_CATEGORIES:
        emoji_id = get_category_emoji(cat)
        kb.inline_keyboard.append([InlineKeyboardButton(text=cat, callback_data=f"addprod_cat_{cat}",
                                                         icon_custom_emoji_id=emoji_id, style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Cancel"), callback_data="admin_panel_back",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("<b>Step 1:</b> Choose Category:", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("addprod_cat_"))
async def add_prod_category_selected(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    category = call.data.split("addprod_cat_", 1)[1]
    await state.update_data(cat=category)
    await call.message.edit_text("<b>Step 2:</b> Enter PANEL NAME:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_panel_name)


@dp.message(AdminStates.add_prod_panel_name)
async def add_prod_panel_name(m: Message, state: FSMContext):
    await state.update_data(panel_name=m.text)
    await m.answer("<b>Step 3:</b> Enter Package Duration/Name:", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_name)


@dp.message(AdminStates.add_prod_name)
async def add_prod_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("⏳ Enter Validity (e.g., '30 Days'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_validity)


@dp.message(AdminStates.add_prod_validity)
async def add_prod_validity(m: Message, state: FSMContext):
    await state.update_data(validity=m.text)
    await m.answer("📱 Enter Device Limit (e.g., '1 Device'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_device_limit)


@dp.message(AdminStates.add_prod_device_limit)
async def add_prod_device_limit(m: Message, state: FSMContext):
    await state.update_data(device_limit=m.text)
    await m.answer("💰 Enter Standard Price ₹:", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_price)


@dp.message(AdminStates.add_prod_price)
async def add_prod_price(m: Message, state: FSMContext):
    try:
        await state.update_data(price=float(m.text))
        await m.answer("👑 Enter Reseller Price ₹:", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_reseller_price)
    except ValueError:
        await m.answer("❌ Invalid number.")


@dp.message(AdminStates.add_prod_reseller_price)
async def add_prod_reseller_price(m: Message, state: FSMContext):
    try:
        await state.update_data(reseller_price=float(m.text))
        await m.answer("🔗 Enter APK Link (or 'none'):", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_apk)
    except ValueError:
        await m.answer("❌ Invalid number.")


@dp.message(AdminStates.add_prod_apk)
async def add_prod_apk(m: Message, state: FSMContext):
    await state.update_data(apk="" if m.text.lower() == 'none' else m.text)
    await m.answer("📥 Paste Keys (1 per line):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_keys)


@dp.message(AdminStates.add_prod_keys)
async def add_prod_keys(m: Message, state: FSMContext):
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    data = await state.get_data()
    stock = len(keys)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO products (category, panel_name, name, price_inr, reseller_price, stock, apk_link, validity, device_limit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data['cat'], data['panel_name'], data['name'], data['price'],
         data['reseller_price'], stock, data['apk'], data['validity'], data['device_limit']),
    )
    prod_id = c.lastrowid
    for k in keys:
        c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (prod_id, k))
    conn.commit()
    conn.close()
    await m.answer(
        f"✅ <b>Deployed!</b>\n📦 {data['cat']} → {data['panel_name']} → {data['name']}\n🔒 {stock} keys injected.",
        reply_markup=admin_kb(), parse_mode='HTML',
    )
    await state.clear()


# -------------------- CATEGORY MANAGER --------------------
@dp.callback_query(F.data == "admin_cat_menu")
async def admin_cat_menu(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Category", callback_data="adm_cat_add", style="success"),
         InlineKeyboardButton(text="📋 List Categories", callback_data="adm_cat_list", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("📂 <b>✦ CATEGORY MANAGER ✦</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "adm_cat_add")
async def adm_cat_add(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Category ka naam bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_cat_name)


@dp.message(AdminStates.add_cat_name)
async def adm_cat_add_name(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    db_query("INSERT INTO categories (name) VALUES (?)", (m.text[:100],))
    await m.answer("✅ Category added.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "adm_cat_list")
async def adm_cat_list(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    cats = db_query("SELECT id, name, emoji, visible FROM categories ORDER BY id", fetchall=True)
    if not cats:
        return await call.message.edit_text("No custom categories.", reply_markup=admin_back_kb(), parse_mode='HTML')
    body = "📂 <b>✦ CATEGORIES ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
    for c in cats:
        body += f"{'✅' if c[3] else '❌'} {c[2]} {c[1]} (ID {c[0]})\n"
    await call.message.edit_text(body, reply_markup=admin_back_kb(), parse_mode='HTML')


# -------------------- KEY MANAGER --------------------
@dp.callback_query(F.data == "admin_key_menu")
async def admin_key_menu(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Key", callback_data="adm_key_add", style="success"),
         InlineKeyboardButton(text="🔍 Check Stock", callback_data="adm_key_check", style="primary")],
        [InlineKeyboardButton(text="🧹 Clear All Unused", callback_data="adm_key_clear", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("🔑 <b>✦ KEY MANAGER ✦</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "adm_key_add")
async def adm_key_add(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    prods = db_query("SELECT id, name FROM products ORDER BY id", fetchall=True)
    if not prods:
        return await call.answer("Add a product first.", show_alert=True)
    kb_rows = [[InlineKeyboardButton(text=p[1], callback_data=f"keyadd_p_{p[0]}", style="primary")] for p in prods]
    kb_rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_key_menu",
                                          icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("Kis product ke liye keys add karni hain?",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode='HTML')


@dp.callback_query(F.data.startswith("keyadd_p_"))
async def adm_key_add_pid(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    p_id = int(call.data.split("_")[2])
    await state.update_data(key_pid=p_id)
    await call.message.edit_text("Keys paste karein (1 per line):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_key_text)


@dp.message(AdminStates.wait_for_key_text)
async def adm_key_text(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    data = await state.get_data()
    p_id = data.get("key_pid")
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for k in keys:
        c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (p_id, k))
    c.execute("UPDATE products SET stock = stock + ? WHERE id=?", (len(keys), p_id))
    conn.commit()
    conn.close()
    await m.answer(f"✅ {len(keys)} keys added.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "adm_key_check")
async def adm_key_check(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    prods = db_query(
        "SELECT p.id, p.name, SUM(CASE WHEN k.is_used=0 THEN 1 ELSE 0 END) AS avail, "
        "SUM(CASE WHEN k.is_used=1 THEN 1 ELSE 0 END) AS sold FROM products p "
        "LEFT JOIN product_keys k ON k.product_id=p.id GROUP BY p.id ORDER BY p.id",
        fetchall=True,
    )
    body = "🔑 <b>✦ KEY STOCK ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
    for p in prods:
        body += f"#{p[0]} {p[1]}: 🟢 {p[2] or 0} | 🔴 {p[3] or 0}\n"
    await call.message.edit_text(body, reply_markup=admin_back_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "adm_key_clear")
async def adm_key_clear(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    db_query("DELETE FROM product_keys WHERE is_used=0")
    await call.answer("🧹 All unused keys cleared!", show_alert=True)


# -------------------- RESELLER / COUPONS / BROADCAST / TICKETS --------------------
@dp.callback_query(F.data == "admin_reseller_menu")
async def admin_reseller_menu(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    sys_status_row = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    sys_status = sys_status_row[0] if sys_status_row else "ON"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Grant Reseller", callback_data="reseller_make", style="success"),
         InlineKeyboardButton(text="➖ Revoke Reseller", callback_data="reseller_remove", style="danger")],
        [InlineKeyboardButton(text="📋 View Active Resellers", callback_data="reseller_view", style="primary")],
        [InlineKeyboardButton(text=f"{'🟢' if sys_status == 'ON' else '🔴'} System: {sys_status}",
                              callback_data="admin_toggle_reseller_sys",
                              style="success" if sys_status == 'ON' else "danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("👑 <b>✦ RESELLER PROTOCOLS ✦</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "admin_toggle_reseller_sys")
async def toggle_reseller_sys(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    res = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('reseller_system_status', ?)", (new_status,))
    await admin_reseller_menu(call)


@dp.callback_query(F.data.in_(["reseller_make", "reseller_remove"]))
async def reseller_prompt_id(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await state.update_data(reseller_action=call.data)
    await call.message.edit_text("User ID or @username bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.reseller_manage_id)


@dp.message(AdminStates.reseller_manage_id)
async def process_reseller_manage(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    data = await state.get_data()
    target = m.text.strip().lstrip('@')
    user_q = db_query("SELECT user_id, first_name FROM users WHERE user_id=? OR username=? COLLATE NOCASE",
                      (target, target), fetchone=True)
    if not user_q:
        return await m.answer("❌ User not found.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name = user_q
    if data['reseller_action'] == "reseller_make":
        db_query("UPDATE users SET is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?",
                 (datetime.now().strftime("%Y-%m-%d"), u_id))
        await m.answer(f"✅ {u_name} is now a reseller.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        db_query("UPDATE users SET is_reseller=0, account_type='Regular' WHERE user_id=?", (u_id,))
        await m.answer(f"✅ {u_name} is back to regular.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "reseller_view")
async def reseller_view(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    resellers = db_query("SELECT user_id, first_name, username FROM users WHERE is_reseller=1", fetchall=True)
    if not resellers:
        return await call.message.edit_text("📋 No active resellers.", reply_markup=admin_back_kb(), parse_mode='HTML')
    body = "👑 <b>ACTIVE RESELLERS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for r in resellers:
        body += f"👤 {r[1]} (@{r[2] or 'N/A'})\n🆔 <code>{r[0]}</code>\n\n"
    await call.message.edit_text(body, reply_markup=admin_back_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "admin_create_coupon")
async def admin_create_coupon_start(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("🎟 Promo Code bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_code)


@dp.message(AdminStates.add_coupon_code)
async def admin_coupon_code(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    await state.update_data(code=m.text.strip().upper())
    await m.answer("💰 Reward ₹ bhejein:", parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_amount)


@dp.message(AdminStates.add_coupon_amount)
async def admin_coupon_amount(m: Message, state: FSMContext):
    try:
        await state.update_data(amount=float(m.text))
        await m.answer("👥 Max uses bhejein:", parse_mode='HTML')
        await state.set_state(AdminStates.add_coupon_uses)
    except ValueError:
        await m.answer("❌ Invalid number.")


@dp.message(AdminStates.add_coupon_uses)
async def admin_coupon_uses(m: Message, state: FSMContext):
    try:
        uses = int(m.text)
        data = await state.get_data()
        db_query("INSERT OR REPLACE INTO coupons (code, amount, uses_left) VALUES (?, ?, ?)",
                 (data['code'], data['amount'], uses))
        await m.answer(f"✅ Coupon {data['code']} created!\nReward: {fmt_curr(data['amount'])}\nUses: {uses}",
                       reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError:
        await m.answer("❌ Invalid number.")


@dp.callback_query(F.data == "admin_broadcast_btn")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("📢 Broadcast message bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.broadcast_msg)


@dp.message(AdminStates.broadcast_msg)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if not is_co_admin(message.from_user.id):
        return
    users = db_query("SELECT user_id FROM users", fetchall=True)
    sent, failed = 0, 0
    m = await message.answer("⏳ Broadcasting...", parse_mode='HTML')
    for u in users:
        try:
            if message.photo:
                await bot.send_photo(u[0], message.photo[-1].file_id,
                                     caption=(message.caption or "")[:1024], parse_mode='HTML')
            elif message.video:
                await bot.send_video(u[0], message.video.file_id,
                                     caption=(message.caption or "")[:1024], parse_mode='HTML')
            elif message.document:
                await bot.send_document(u[0], message.document.file_id,
                                        caption=(message.caption or "")[:1024], parse_mode='HTML')
            else:
                await message.send_copy(chat_id=u[0])
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    db_query("INSERT INTO broadcasts (message, sent_to, failed) VALUES (?, ?, ?)",
             ((message.text or message.caption or "[media]")[:500], sent, failed))
    await m.edit_text(f"✅ <b>Broadcast done!</b>\n🟢 Sent: {sent}\n🔴 Failed: {failed}",
                      reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_view_tickets")
async def admin_view_tickets(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    tickets = db_query("SELECT id, user_id, message, created_at FROM tickets WHERE status='Open' LIMIT 1", fetchall=True)
    if not tickets:
        return await call.answer("✅ No pending tickets.", show_alert=True)
    t = tickets[0]
    text = (
        f"🎫 <b>TICKET #{t[0]}</b>\n"
        f"👤 User: <code>{t[1]}</code>\n"
        f"📅 {t[3]}\n\n📝 {t[2]}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Reply", callback_data=f"reply_ticket_{t[0]}_{t[1]}", style="primary")],
        [InlineKeyboardButton(text="❌ Close", callback_data=f"close_ticket_{t[0]}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("close_ticket_"))
async def close_ticket(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    ticket_id = call.data.split("_")[2]
    db_query("UPDATE tickets SET status='Closed' WHERE id=?", (ticket_id,))
    await call.answer("✅ Closed.", show_alert=True)
    await admin_view_tickets(call)


@dp.callback_query(F.data.startswith("reply_ticket_"))
async def reply_ticket_start(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    await state.update_data(ticket_id=parts[2], user_id=parts[3])
    await call.message.edit_text(f"Reply to <code>{parts[3]}</code>:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.ticket_reply_msg)


@dp.message(AdminStates.ticket_reply_msg)
async def send_ticket_reply(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    data = await state.get_data()
    try:
        await bot.send_message(data['user_id'],
                               f"📞 <b>Admin Reply (Ticket #{data['ticket_id']}):</b>\n\n{m.text}",
                               parse_mode='HTML')
        db_query("UPDATE tickets SET status='Closed' WHERE id=?", (data['ticket_id'],))
        await m.answer("✅ Reply sent.", reply_markup=admin_kb(), parse_mode='HTML')
    except Exception as e:
        await m.answer(f"❌ Failed: {e}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


# -------------------- Emoji / UI / Reseller settings --------------------
@dp.callback_query(F.data == "admin_edit_emojis")
async def admin_edit_emojis(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    rows = db_query("SELECT key, value FROM settings WHERE key LIKE 'emoji_%' ORDER BY key", fetchall=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row in rows:
        slot = row[0].replace("emoji_", "")
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{slot} (ID: {row[1] or 'N/A'})", callback_data=f"edit_emoji_{slot}", style="primary",
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎨 <b>Edit All Emojis</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("edit_emoji_"))
async def admin_edit_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    slot = call.data.split("edit_emoji_", 1)[1]
    await state.update_data(emoji_slot=slot)
    current = get_setting(f"emoji_{slot}", "Not set")
    await call.message.edit_text(
        f"✏️ Enter new emoji ID for <b>{slot}</b>:\nCurrent: {current}\n(Empty to reset)",
        reply_markup=admin_back_kb(), parse_mode='HTML',
    )
    await state.set_state(AdminStates.wait_for_emoji_slot)


@dp.message(AdminStates.wait_for_emoji_slot)
async def save_emoji_slot(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    data = await state.get_data()
    slot = data['emoji_slot']
    new_id = m.text.strip()
    if new_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"emoji_{slot}",))
        await m.answer(f"✅ Reset.", reply_markup=admin_kb(), parse_mode='HTML')
    elif not new_id.isdigit():
        await m.answer("❌ Numeric ID only.")
        return
    else:
        set_setting(f"emoji_{slot}", new_id)
        await m.answer(f"✅ Updated.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_edit_ui_menu")
async def admin_edit_ui_menu(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Edit Start Menu", callback_data="edit_ui_start", style="primary")],
        [InlineKeyboardButton(text="Edit VIP Menu", callback_data="edit_ui_vip", style="primary")],
        [InlineKeyboardButton(text="Edit Add Balance", callback_data="edit_ui_add_balance", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("✏️ <b>Edit UI Texts</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("edit_ui_"))
async def admin_edit_ui_prompt(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    ui_key = call.data.split("_")[2]
    await state.update_data(ui_key=ui_key)
    current_text = get_ui_text(ui_key)
    await call.message.edit_text(
        f"📝 New text for <b>{ui_key.upper()}</b>:\n\nCurrent:\n{current_text[:600]}",
        reply_markup=admin_back_kb(), parse_mode='HTML',
    )
    await state.set_state(AdminStates.edit_ui_text)


@dp.message(AdminStates.edit_ui_text)
async def admin_save_ui_text(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    data = await state.get_data()
    ui_key = data['ui_key']
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"ui_{ui_key}", m.text))
    await m.answer(f"✅ UI text <b>{ui_key}</b> updated!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_edit_reseller_price")
async def admin_edit_reseller_price_start(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    prods = db_query("SELECT id, name, category, panel_name, reseller_price FROM products ORDER BY category", fetchall=True)
    if not prods:
        return await call.message.edit_text("No products.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in prods:
        r_price = safe_float(p[4])
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{p[2]} - {p[3] or ''} - {p[1]} (₹{r_price:.2f})",
            callback_data=f"edit_reseller_{p[0]}", style="primary",
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("👑 <b>Edit Reseller Price</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("edit_reseller_"))
async def admin_edit_reseller_price_prompt(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    prod_id = int(call.data.split("_")[2])
    await state.update_data(edit_reseller_prod_id=prod_id)
    await call.message.edit_text("💰 New Reseller Price ₹:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_reseller_price)


@dp.message(AdminStates.edit_reseller_price)
async def admin_save_reseller_price(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    try:
        new_price = float(m.text)
        data = await state.get_data()
        db_query("UPDATE products SET reseller_price=? WHERE id=?", (new_price, data['edit_reseller_prod_id']))
        await m.answer(f"✅ R-Price set to {fmt_curr(new_price)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError:
        await m.answer("❌ Invalid number.")


@dp.callback_query(F.data == "admin_set_reseller_fee")
async def admin_set_reseller_fee(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text(
        f"💰 Reseller Setup Fee (current: {get_setting('reseller_setup_fee', '200.0')}):",
        reply_markup=admin_back_kb(), parse_mode='HTML',
    )
    await state.set_state(AdminStates.wait_for_reseller_setup_fee)


@dp.message(AdminStates.wait_for_reseller_setup_fee)
async def admin_save_reseller_fee(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    try:
        fee = float(m.text)
        set_setting("reseller_setup_fee", str(fee))
        await m.answer(f"✅ Fee set to {fmt_curr(fee)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError:
        await m.answer("❌ Invalid number.")


@dp.callback_query(F.data == "admin_set_reseller_min")
async def admin_set_reseller_min(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text(
        f"💳 Minimum Balance (current: {get_setting('reseller_min_balance', '500.0')}):",
        reply_markup=admin_back_kb(), parse_mode='HTML',
    )
    await state.set_state(AdminStates.wait_for_reseller_min_balance)


@dp.message(AdminStates.wait_for_reseller_min_balance)
async def admin_save_reseller_min(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    try:
        min_bal = float(m.text)
        set_setting("reseller_min_balance", str(min_bal))
        await m.answer(f"✅ Min set to {fmt_curr(min_bal)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError:
        await m.answer("❌ Invalid number.")


@dp.callback_query(F.data == "admin_set_support_links")
async def admin_set_support_links(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Telegram", callback_data="admin_set_telegram", style="primary")],
        [InlineKeyboardButton(text="📱 WhatsApp", callback_data="admin_set_whatsapp", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("📌 <b>Support Links</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "admin_set_telegram")
async def admin_set_telegram(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Telegram URL:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_telegram)


@dp.message(AdminStates.wait_for_support_telegram)
async def save_telegram_link(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("support_telegram", m.text.strip())
    await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_set_whatsapp")
async def admin_set_whatsapp(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("WhatsApp URL:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_whatsapp)


@dp.message(AdminStates.wait_for_support_whatsapp)
async def save_whatsapp_link(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("support_whatsapp", m.text.strip())
    await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_set_category_emojis")
async def admin_set_category_emojis(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in FIXED_CATEGORIES:
        slot = CATEGORY_SLOT_MAP.get(cat, "")
        current = get_setting(f"emoji_{slot}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{cat} (ID: {current})", callback_data=f"set_cat_emoji_{cat}", style="primary",
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎨 <b>Set Category Emojis</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("set_cat_emoji_"))
async def admin_set_category_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    category = call.data.split("set_cat_emoji_", 1)[1]
    await state.update_data(cat_emoji_category=category)
    await call.message.edit_text(f"Emoji ID for <b>{category}</b>:\n(Empty to reset)",
                                  reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_category_emoji)


@dp.message(AdminStates.wait_for_category_emoji)
async def save_category_emoji(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    data = await state.get_data()
    category = data['cat_emoji_category']
    slot = CATEGORY_SLOT_MAP.get(category)
    if not slot:
        return await m.answer("❌ Unknown category.", reply_markup=admin_kb(), parse_mode='HTML')
    emoji_id = m.text.strip()
    if emoji_id == "":
        set_setting(f"emoji_{slot}", DEFAULT_EMOJIS.get(slot, ""))
        await m.answer("✅ Reset.", reply_markup=admin_kb(), parse_mode='HTML')
    elif not emoji_id.isdigit():
        await m.answer("❌ Numeric only.")
        return
    else:
        set_setting(f"emoji_{slot}", emoji_id)
        await m.answer("✅ Set.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_set_panel_emojis")
async def admin_set_panel_emojis(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    panels = db_query("SELECT DISTINCT panel_name FROM products WHERE panel_name != '' ORDER BY panel_name", fetchall=True)
    if not panels:
        return await call.message.edit_text("No panels.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in panels:
        panel = p[0]
        current = get_setting(f"panel_emoji_{panel}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{panel} (ID: {current})", callback_data=f"set_panel_emoji_{panel}", style="primary",
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                                                     icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🖼 <b>Set Panel Emojis</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("set_panel_emoji_"))
async def admin_set_panel_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    panel_name = call.data.split("set_panel_emoji_", 1)[1]
    await state.update_data(panel_emoji_name=panel_name)
    await call.message.edit_text(f"Emoji ID for <b>{panel_name}</b>:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_panel_emoji_id)


@dp.message(AdminStates.wait_for_panel_emoji_id)
async def save_panel_emoji(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    data = await state.get_data()
    panel_name = data['panel_emoji_name']
    emoji_id = m.text.strip()
    if emoji_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"panel_emoji_{panel_name}",))
        await m.answer("✅ Reset.", reply_markup=admin_kb(), parse_mode='HTML')
    elif not emoji_id.isdigit():
        await m.answer("❌ Numeric only.")
        return
    else:
        set_setting(f"panel_emoji_{panel_name}", emoji_id)
        await m.answer("✅ Set.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_set_logo")
async def admin_set_logo(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("🖼️ Admin logo PHOTO bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_logo)


@dp.message(AdminStates.wait_for_logo, F.photo)
async def save_admin_logo(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("admin_logo_file_id", m.photo[-1].file_id)
    await m.answer("✅ Logo saved!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


# -------------------- FAMPAY SETUP --------------------
@dp.callback_query(F.data == "admin_setup_fampay")
async def setup_fampay_start(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    current_api = get_setting("fampay_api_key", "Not set")
    current_upi = get_setting("fampay_upi_id", "Not set")
    await call.message.edit_text(
        f"⚙️ <b>FAMPAY SETUP</b>\n\n"
        f"🔑 API: {current_api[:8] if current_api != 'Not set' else 'Not set'}...\n"
        f"🏦 UPI: {current_upi}\n\n"
        f"Send new API Key:",
        reply_markup=admin_back_kb(), parse_mode='HTML',
    )
    await state.set_state(AdminStates.wait_for_fampay_api)


@dp.message(AdminStates.wait_for_fampay_api)
async def setup_fampay_api(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    if m.text == '/cancel':
        await state.clear()
        return await m.answer("Cancelled.", reply_markup=admin_kb(), parse_mode='HTML')
    set_setting("fampay_api_key", m.text.strip())
    await m.answer("🔑 API saved!\nNow UPI ID:")
    await state.set_state(AdminStates.wait_for_fampay_upi)


@dp.message(AdminStates.wait_for_fampay_upi)
async def setup_fampay_upi(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    upi = m.text.strip()
    if '@' not in upi:
        return await m.answer("❌ Invalid UPI (must contain @).")
    set_setting("fampay_upi_id", upi)
    set_setting("upi_id", upi)
    await m.answer(f"✅ FamPay configured!\nUPI: {upi}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_setup_binance")
async def setup_binance_start(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("🪙 Binance API Key:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_api)


@dp.message(AdminStates.wait_for_binance_api)
async def setup_binance_api(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("binance_api", m.text.strip())
    await m.answer("Secret Key:")
    await state.set_state(AdminStates.wait_for_binance_secret)


@dp.message(AdminStates.wait_for_binance_secret)
async def setup_binance_secret(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("binance_secret", m.text.strip())
    await m.answer("USDT Deposit Address:")
    await state.set_state(AdminStates.wait_for_binance_address)


@dp.message(AdminStates.wait_for_binance_address)
async def setup_binance_address(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("binance_address", m.text.strip())
    await m.answer("✅ Binance ready.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


# -------------------- PAYMENT SETTINGS (combined) --------------------
@dp.callback_query(F.data == "admin_payment_menu")
async def admin_payment_menu(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Set UPI ID", callback_data="admin_set_upi", style="primary"),
         InlineKeyboardButton(text="🏷️ Set Payee Name", callback_data="admin_set_payee", style="primary")],
        [InlineKeyboardButton(text="🖼️ Static QR", callback_data="admin_set_qr", style="primary"),
         InlineKeyboardButton(text="⚡ ZapUPI Key", callback_data="admin_set_zapupi", style="primary")],
        [InlineKeyboardButton(text="🪙 Binance Pay ID", callback_data="admin_set_binance_pay", style="primary")],
        [InlineKeyboardButton(text="⚙️ Payment Instructions", callback_data="admin_set_instructions", style="primary")],
        [InlineKeyboardButton(text="🪙 Binance Full Setup", callback_data="admin_setup_binance", style="success")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("💳 <b>✦ PAYMENT SETTINGS ✦</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "admin_set_upi")
async def admin_set_upi(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("UPI ID bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_upi)


@dp.message(AdminStates.wait_for_upi)
async def save_upi(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("upi_id", m.text.strip())
    set_setting("fampay_upi_id", m.text.strip())
    await m.answer("✅ UPI saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_set_payee")
async def admin_set_payee(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Payee name bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_payee)


@dp.message(AdminStates.wait_for_payee)
async def save_payee(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("payee_name", m.text.strip())
    await m.answer("✅ Payee saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_set_qr")
async def admin_set_qr(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Static QR PHOTO bhejein:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_static_qr)


@dp.message(AdminStates.wait_for_static_qr, F.photo)
async def save_static_qr(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("payment_qr_file_id", m.photo[-1].file_id)
    await m.answer("✅ Static QR saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_set_zapupi")
async def admin_set_zapupi(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("ZapUPI Key:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_zapupi)


@dp.message(AdminStates.wait_for_zapupi)
async def save_zapupi(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("zapupi_key", m.text.strip())
    await m.answer("✅ ZapUPI saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_set_binance_pay")
async def admin_set_binance_pay(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Binance Pay ID:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_pay)


@dp.message(AdminStates.wait_for_binance_pay)
async def save_binance_pay(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("binance_pay_id", m.text.strip())
    await m.answer("✅ Binance Pay ID saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_set_instructions")
async def admin_set_instructions(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Payment instructions:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_instructions)


@dp.message(AdminStates.wait_for_instructions)
async def save_instructions(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("payment_instructions", m.text)
    await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


# -------------------- MESSAGE EDITOR --------------------
@dp.callback_query(F.data == "admin_msg_editor")
async def admin_msg_editor(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Welcome", callback_data="adm_msg_welcome", style="primary"),
         InlineKeyboardButton(text="✏️ Category", callback_data="adm_msg_category", style="primary")],
        [InlineKeyboardButton(text="✏️ Product", callback_data="adm_msg_product", style="primary"),
         InlineKeyboardButton(text="✏️ Key", callback_data="adm_msg_key", style="primary")],
        [InlineKeyboardButton(text="✏️ Profile", callback_data="adm_msg_profile", style="primary"),
         InlineKeyboardButton(text="✏️ Orders", callback_data="adm_msg_orders", style="primary")],
        [InlineKeyboardButton(text="✏️ Support", callback_data="adm_msg_support", style="primary"),
         InlineKeyboardButton(text="✏️ Balance", callback_data="adm_msg_balance", style="primary")],
        [InlineKeyboardButton(text="♻️ Reset All", callback_data="adm_msg_reset", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("✏️ <b>Message Editor</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("adm_msg_"))
async def adm_msg_edit(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    key = call.data.split("adm_msg_", 1)[1]
    if key == "reset":
        set_setting("ui_welcome", UI_TEXTS['welcome_default'])
        set_setting("ui_category_message", UI_TEXTS['category_default'])
        set_setting("ui_product_message", UI_TEXTS['product_default'])
        set_setting("ui_key_message", UI_TEXTS['key_default'])
        set_setting("ui_profile_message", UI_TEXTS['profile_default'])
        set_setting("ui_orders_message", UI_TEXTS['orders_default'])
        set_setting("ui_support_message", UI_TEXTS['support_default'])
        set_setting("ui_balance_message", UI_TEXTS['balance_default'])
        return await call.answer("✅ All reset to default.", show_alert=True)
    mapping = {
        "welcome": ("ui_welcome", AdminStates.wait_for_msg_welcome, UI_TEXTS['welcome_default']),
        "category": ("ui_category_message", AdminStates.wait_for_msg_category, UI_TEXTS['category_default']),
        "product": ("ui_product_message", AdminStates.wait_for_msg_product, UI_TEXTS['product_default']),
        "key": ("ui_key_message", AdminStates.wait_for_msg_key, UI_TEXTS['key_default']),
        "profile": ("ui_profile_message", AdminStates.wait_for_msg_profile, UI_TEXTS['profile_default']),
        "orders": ("ui_orders_message", AdminStates.wait_for_msg_orders, UI_TEXTS['orders_default']),
        "support": ("ui_support_message", AdminStates.wait_for_msg_support, UI_TEXTS['support_default']),
        "balance": ("ui_balance_message", AdminStates.wait_for_msg_balance, UI_TEXTS['balance_default']),
    }
    if key not in mapping:
        return
    setting_key, st, default = mapping[key]
    await state.update_data(msg_setting_key=setting_key, msg_default=default)
    await call.message.edit_text(
        f"✏️ Send new <b>{key.upper()}</b> text:\n\nCurrent:\n{get_setting(setting_key, default)[:600]}",
        reply_markup=admin_back_kb(), parse_mode='HTML',
    )
    await state.set_state(st)


async def _save_msg(m: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get('msg_setting_key')
    if key:
        set_setting(key, m.text)
        await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.message(AdminStates.wait_for_msg_welcome)
async def save_msg_welcome(m: Message, state: FSMContext):
    await _save_msg(m, state)


@dp.message(AdminStates.wait_for_msg_category)
async def save_msg_category(m: Message, state: FSMContext):
    await _save_msg(m, state)


@dp.message(AdminStates.wait_for_msg_product)
async def save_msg_product(m: Message, state: FSMContext):
    await _save_msg(m, state)


@dp.message(AdminStates.wait_for_msg_key)
async def save_msg_key(m: Message, state: FSMContext):
    await _save_msg(m, state)


@dp.message(AdminStates.wait_for_msg_profile)
async def save_msg_profile(m: Message, state: FSMContext):
    await _save_msg(m, state)


@dp.message(AdminStates.wait_for_msg_orders)
async def save_msg_orders(m: Message, state: FSMContext):
    await _save_msg(m, state)


@dp.message(AdminStates.wait_for_msg_support)
async def save_msg_support(m: Message, state: FSMContext):
    await _save_msg(m, state)


@dp.message(AdminStates.wait_for_msg_balance)
async def save_msg_balance(m: Message, state: FSMContext):
    await _save_msg(m, state)


# -------------------- API MANAGER --------------------
@dp.callback_query(F.data == "admin_api_menu")
async def admin_api_menu(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add API", callback_data="adm_api_add", style="success"),
         InlineKeyboardButton(text="📋 View APIs", callback_data="adm_api_view", style="primary")],
        [InlineKeyboardButton(text="🗑 Delete API", callback_data="adm_api_del", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("🌐 <b>API Manager</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "adm_api_add")
async def adm_api_add(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("API name:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_api_name)


@dp.message(AdminStates.wait_for_api_name)
async def adm_api_name(m: Message, state: FSMContext):
    await state.update_data(api_name=m.text.strip())
    await m.answer("URL:")
    await state.set_state(AdminStates.wait_for_api_url)


@dp.message(AdminStates.wait_for_api_url)
async def adm_api_url(m: Message, state: FSMContext):
    await state.update_data(api_url=m.text.strip())
    await m.answer("API Key:")
    await state.set_state(AdminStates.wait_for_api_key)


@dp.message(AdminStates.wait_for_api_key)
async def adm_api_key(m: Message, state: FSMContext):
    data = await state.get_data()
    db_query("INSERT INTO apis (name, url, api_key) VALUES (?, ?, ?)",
             (data['api_name'], data['api_url'], m.text.strip()))
    await m.answer("✅ API added.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "adm_api_view")
async def adm_api_view(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    rows = db_query("SELECT id, name, url FROM apis ORDER BY id", fetchall=True)
    body = "🌐 <b>APIs</b>\n"
    for r in rows:
        body += f"#{r[0]} {r[1]} ({r[2]})\n"
    await call.message.edit_text(body or "No APIs.", reply_markup=admin_back_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "adm_api_del")
async def adm_api_del(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("API ID to delete:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_api_del)


@dp.message(AdminStates.wait_for_api_del)
async def adm_api_del_do(m: Message, state: FSMContext):
    if not m.text.strip().isdigit():
        return await m.answer("Numeric ID.")
    db_query("DELETE FROM apis WHERE id=?", (int(m.text.strip()),))
    await m.answer("✅ Deleted.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


# -------------------- CO-ADMIN / OWNER / LINKS / GIFT --------------------
@dp.callback_query(F.data == "admin_coadmin_menu")
async def admin_coadmin_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Only primary owner.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add", callback_data="adm_coadmin_add", style="success"),
         InlineKeyboardButton(text="➖ Remove", callback_data="adm_coadmin_remove", style="danger")],
        [InlineKeyboardButton(text="📋 View", callback_data="adm_coadmin_view", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("🤝 <b>Co-Admin Manager</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "adm_coadmin_add")
async def adm_coadmin_add(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.edit_text("User ID:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_coadmin_add)


@dp.message(AdminStates.wait_for_coadmin_add)
async def save_coadmin_add(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    if not m.text.strip().isdigit():
        return await m.answer("Numeric ID.")
    uid = int(m.text.strip())
    u = db_query("SELECT first_name FROM users WHERE user_id=?", (uid,), fetchone=True)
    name = u[0] if u else "Unknown"
    db_query("INSERT OR IGNORE INTO co_admins (user_id, name) VALUES (?, ?)", (uid, name))
    await m.answer("✅ Co-admin added.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "adm_coadmin_remove")
async def adm_coadmin_remove(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.edit_text("User ID:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_coadmin_remove)


@dp.message(AdminStates.wait_for_coadmin_remove)
async def save_coadmin_remove(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    if not m.text.strip().isdigit():
        return await m.answer("Numeric ID.")
    db_query("DELETE FROM co_admins WHERE user_id=?", (int(m.text.strip()),))
    await m.answer("✅ Removed.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "adm_coadmin_view")
async def adm_coadmin_view(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    rows = db_query("SELECT user_id, name FROM co_admins ORDER BY user_id", fetchall=True)
    body = "🤝 <b>Co-Admins</b>\n"
    for r in rows:
        body += f"🆔 <code>{r[0]}</code> — {r[1]}\n"
    await call.message.edit_text(body or "None.", reply_markup=admin_back_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "admin_transfer_owner")
async def admin_transfer_owner(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Only primary owner.", show_alert=True)
    await call.message.edit_text("New owner User ID:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_new_owner)


@dp.message(AdminStates.wait_for_new_owner)
async def save_new_owner(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    if not m.text.strip().isdigit():
        return await m.answer("Numeric ID.")
    set_setting("owner_id", m.text.strip())
    await m.answer(f"✅ Ownership set to {m.text.strip()}.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_link_menu")
async def admin_link_menu(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Support URL", callback_data="adm_link_support", style="primary"),
         InlineKeyboardButton(text="📖 How-To URL", callback_data="adm_link_howto", style="primary")],
        [InlineKeyboardButton(text="📸 Proof URL", callback_data="adm_link_proof", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("🔗 <b>Link Manager</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "adm_link_support")
async def adm_link_support(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Support URL:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_url)


@dp.message(AdminStates.wait_for_support_url)
async def save_support_url(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("support_url", m.text.strip())
    await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "adm_link_howto")
async def adm_link_howto(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("How-To URL:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_howto_url)


@dp.message(AdminStates.wait_for_howto_url)
async def save_howto_url(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("how_to_use_url", m.text.strip())
    await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "adm_link_proof")
async def adm_link_proof(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Proof URL:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_proof_url)


@dp.message(AdminStates.wait_for_proof_url)
async def save_proof_url(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("payment_proof_url", m.text.strip())
    await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_gift_menu")
async def admin_gift_menu(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Set Daily Gift", callback_data="adm_gift_set", style="primary"),
         InlineKeyboardButton(text="🤝 Set Refer & Earn", callback_data="adm_gift_refer", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("🎁 <b>Gift & Refer</b>", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "adm_gift_set")
async def adm_gift_set(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Daily gift ₹:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_gift_amount)


@dp.message(AdminStates.wait_for_gift_amount)
async def save_gift_amount(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    try:
        set_setting("daily_gift_price", str(float(m.text)))
        await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError:
        await m.answer("❌ Number.")


@dp.callback_query(F.data == "adm_gift_refer")
async def adm_gift_refer(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Refer & Earn ₹:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_refer_amount)


@dp.message(AdminStates.wait_for_refer_amount)
async def save_refer_amount(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    try:
        set_setting("refer_earn_amount", str(float(m.text)))
        await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError:
        await m.answer("❌ Number.")


@dp.callback_query(F.data == "admin_set_video")
async def admin_set_video_start(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Tutorial video URL (or 'None'):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_howto_video)


@dp.message(AdminStates.wait_for_howto_video)
async def exec_set_video(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    set_setting("how_to_video", m.text.strip())
    await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


# -------------------- MAINTENANCE --------------------
@dp.callback_query(F.data == "admin_maintenance_menu")
async def admin_maintenance_menu(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    mt = db_query("SELECT enabled FROM maintenance WHERE id=1", fetchone=True)
    st = "🔴 ON" if mt and mt[0] else "🟢 OFF"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔛 Toggle", callback_data="adm_mt_toggle", style="primary")],
        [InlineKeyboardButton(text="✏️ Edit Msg", callback_data="adm_mt_edit", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back",
                              icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text(f"🔧 <b>Maintenance Mode</b>\nStatus: {st}", reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "adm_mt_toggle")
async def adm_mt_toggle(call: CallbackQuery):
    if not is_co_admin(call.from_user.id):
        return
    mt = db_query("SELECT enabled FROM maintenance WHERE id=1", fetchone=True)
    new = 0 if (mt and mt[0]) else 1
    db_query("UPDATE maintenance SET enabled=? WHERE id=1", (new,))
    await admin_maintenance_menu(call)


@dp.callback_query(F.data == "adm_mt_edit")
async def adm_mt_edit(call: CallbackQuery, state: FSMContext):
    if not is_co_admin(call.from_user.id):
        return
    await call.message.edit_text("Maintenance message:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_maintenance_msg)


@dp.message(AdminStates.wait_for_maintenance_msg)
async def adm_mt_edit_save(m: Message, state: FSMContext):
    if not is_co_admin(m.from_user.id):
        return
    db_query("UPDATE maintenance SET message=? WHERE id=1", (m.text,))
    await m.answer("✅ Saved.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


# ==============================================================================
# 18. MAIN
# ==============================================================================
async def main() -> None:
    init_db()
    logger.info("Initializing DB structure...")
    migrate_categories()
    asyncio.create_task(auto_verify_task())
    logger.info("FamPay Auto-Verifier Daemon started.")
    logger.info("🚀 CORE SYSTEM OPERATIONAL...")
    try:
        await dp.start_polling(bot)
    except Exception as err:
        logger.error(f"Critical failure: {err}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown.")