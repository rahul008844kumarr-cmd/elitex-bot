import asyncio
import sqlite3
import random
import logging
import time
import os
import aiohttp
import hmac
import hashlib
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, Dice, BufferedInputFile
)

# ==============================================================================
# 1. BOT CONFIGURATION & CONSTANTS
# ==============================================================================
BOT_TOKEN = "8851779409:AAHQxEuu8pDJTnr_5yBwQf3rUGVnKrhZKU8"
BOT_USERNAME = "elitexconfig_bot"
ADMIN_ID = 8467166339
ADMIN_CONTACT = "@elitexconfig"

FAMPAY_API_KEY = "YOUR_FAMPAY_API_KEY"  # Replace with your actual API key
FAMPAY_QR_URL = "https://fampay.api/qr.php"
FAMPAY_VERIFY_URL = "https://fampay.api/verify.php"

USDT_TO_INR = 90.0
VIP_DISCOUNT_PERCENTAGE = 10.0
VIP_PRICE_INR = 1000.0

WELCOME_STICKER_ID = "CAACAgIAAxkBAAEU-WZmH_..."  # Replace with your sticker ID

FIXED_CATEGORIES = [
    "ANDROID NON ROOT PANEL",
    "ANDROID ROOT PANEL",
    "PC PANEL"
]

# ==============================================================================
# PERSISTENT STORAGE PATH (Render Disk Mount)
# ==============================================================================
DATA_DIR = "/data" if os.path.exists("/data") else "."
DB_PATH = os.path.join(DATA_DIR, "Sandii.dp")
LOG_PATH = os.path.join(DATA_DIR, "bot_activity.log")

# ==============================================================================
# YOUR PREMIUM EMOJIS – all required emoji IDs
# ==============================================================================
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
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


def fmt_curr(amount: float) -> str:
    return f"₹{amount:,.2f}"


def fancy(text: str) -> str:
    """Premium mixed typography for UI/button labels."""
    bold_caps = {chr(ord("A") + i): chr(0x1D400 + i) for i in range(26)}
    small_caps = {
        "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ",
        "f": "ꜰ", "g": "ɢ", "h": "ʜ", "i": "ɪ", "j": "ᴊ",
        "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ", "o": "ᴏ",
        "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "s", "t": "ᴛ",
        "u": "ᴜ", "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ",
        "z": "ᴢ",
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
    """Safely convert a value to float, return default if fails."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ==============================================================================
# 2. DATABASE FUNCTIONS
# ==============================================================================
def get_db():
    """Get a connection to the persistent SQLite database."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    return conn


def db_query(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = True) -> Any:
    conn = get_db()
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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_query(
            "INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, timestamp)
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
    emoji_id = stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))
    return emoji_id


# ==============================================================================
# 3. STRING RESOURCES – using placeholders for premium emojis
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
    )
}


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
# 4. DATABASE INITIALISATION & MIGRATION
# ==============================================================================
def init_db() -> None:
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            phone TEXT,
            first_name TEXT,
            username TEXT,
            balance REAL DEFAULT 0.0,
            account_type TEXT DEFAULT 'Regular',
            orders_count INTEGER DEFAULT 0,
            spent REAL DEFAULT 0.0,
            last_spin TEXT,
            joined_date TEXT,
            is_reseller INTEGER DEFAULT 0,
            reseller_since TEXT,
            total_saved REAL DEFAULT 0.0,
            is_banned INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            vip_since TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            panel_name TEXT DEFAULT '',
            name TEXT,
            price_inr REAL,
            reseller_price REAL DEFAULT 0.0,
            stock INTEGER,
            apk_link TEXT,
            validity TEXT DEFAULT 'Lifetime',
            device_limit TEXT DEFAULT '1 Device',
            is_active INTEGER DEFAULT 1
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS product_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            key_text TEXT,
            is_used INTEGER DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_name TEXT,
            price_paid REAL,
            delivered_key TEXT,
            purchase_date TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            status TEXT DEFAULT 'Open',
            created_at TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY,
            amount REAL,
            uses_left INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS redeemed (
            user_id INTEGER,
            code TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            amount_inr REAL,
            status TEXT,
            timestamp INTEGER,
            qr_url TEXT,
            upi_id TEXT,
            expires_at INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS crypto_txns (
            txid TEXT PRIMARY KEY,
            user_id INTEGER,
            amount_usdt REAL,
            timestamp INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS spin_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TEXT
        )
    ''')

    migrations = [
        "ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN vip_since TEXT",
        "ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE tickets ADD COLUMN created_at TEXT",
        "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN warnings INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN panel_name TEXT DEFAULT ''",
        "ALTER TABLE transactions ADD COLUMN qr_url TEXT",
        "ALTER TABLE transactions ADD COLUMN upi_id TEXT",
        "ALTER TABLE transactions ADD COLUMN expires_at INTEGER"
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
    ]
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        default_settings.append((f"emoji_{slot}", emoji_id))

    for key, val in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    conn.commit()
    conn.close()

    # Removed feature settings are intentionally ignored by the UI.
    # Their old database values may remain, but no button or handler exposes them.


def migrate_categories() -> None:
    done = get_setting("migration_done", "0")

    # ALWAYS force update emojis and UI texts regardless of migration status
    logger.info("Forcing emoji and UI text updates...")

    # Remove legacy Ludo Spin / Download Files settings from existing databases
    db_query(
        "DELETE FROM settings WHERE key IN "
        "('emoji_ludo_spin', 'emoji_download', 'ui_download_files', "
        "'ui_lucky_dice_result', 'all_files_link', 'spin_status', "
        "'daily_spin_limit', 'emoji_referral')"
    )

    # Update all emoji settings
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        set_setting(f"emoji_{slot}", emoji_id)

    # Force update UI texts
    set_setting("ui_start_menu", UI_TEXTS['start_menu'])
    set_setting("ui_add_balance_menu", UI_TEXTS['add_balance_menu'])
    set_setting("ui_vip_menu", UI_TEXTS['vip_menu'])
    logger.info("UI texts and emojis updated with new placeholders and IDs.")

    # Fix any corrupted price columns (one-time cleanup)
    conn = get_db()
    c = conn.cursor()
    products = c.execute("SELECT id, price_inr, reseller_price FROM products").fetchall()
    for prod in products:
        pid = prod[0]
        for col in ['price_inr', 'reseller_price']:
            val = prod[1] if col == 'price_inr' else prod[2]
            if val is None or val == "":
                new_val = 0.0
            else:
                try:
                    new_val = float(val)
                except (ValueError, TypeError):
                    new_val = 0.0
            c.execute(f"UPDATE products SET {col}=? WHERE id=?", (new_val, pid))
    conn.commit()
    conn.close()
    logger.info("Fixed any non-numeric price columns.")

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
        "UPDATE products SET category = 'ANDROID NON ROOT PANEL' "
        "WHERE LOWER(category) NOT IN (?, ?, ?)",
        ("android non root panel", "android root panel", "pc panel")
    )

    set_setting("migration_done", "1")
    logger.info("Category migration complete.")


# ==============================================================================
# 5. MIDDLEWARES & SECURITY
# ==============================================================================
async def hacker_loading(message: Message, text: str = "Decrypting Data") -> Message:
    msg = await message.answer(f"✦ <b>{text}</b>\n▱▱▱▱▱ 𝟬%")
    await asyncio.sleep(0.3)
    await msg.edit_text(f"✦ <b>{text}</b>\n▰▰▱▱▱ 𝟯𝟯%", parse_mode='HTML')
    await asyncio.sleep(0.3)
    await msg.edit_text(f"✦ <b>{text}</b>\n▰▰▰▰▱ 𝟲𝟲%", parse_mode='HTML')
    await asyncio.sleep(0.3)
    await msg.edit_text(f"✦ <b>{text}</b>\n▰▰▰▰▰ 𝟭𝟬𝟬%", parse_mode='HTML')
    return msg


class GlobalSecurityMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.last_action_times = {}

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = time.time()
        if user_id in self.last_action_times:
            if now - self.last_action_times[user_id] < 0.3:
                return
        self.last_action_times[user_id] = now

        if user_id != ADMIN_ID:
            user_info = db_query("SELECT is_banned FROM users WHERE user_id=?", (user_id,), fetchone=True)
            if user_info and user_info[0] == 1:
                msg = (
                    "🚫 <b>✦ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 ✦</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "You have been banned from using this bot.\n"
                    f"<i>Contact {ADMIN_CONTACT} if you think this is a mistake.</i>"
                )
                if isinstance(event, Message):
                    await event.answer(msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 You are banned.", show_alert=True)
                return

        return await handler(event, data)


dp.message.middleware(GlobalSecurityMiddleware())
dp.callback_query.middleware(GlobalSecurityMiddleware())


# ==============================================================================
# 6. STARTUP
# ==============================================================================
async def on_startup():
    logger.info(f"Using database at: {DB_PATH}")
    init_db()
    migrate_categories()
    logger.info("Bot starting up...")


async def main():
    await on_startup()

    # Register handlers here:
    # dp.include_router(...)

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")