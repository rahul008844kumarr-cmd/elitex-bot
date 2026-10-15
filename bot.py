#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║           ELITE X CONFIG — COMPLETE TELEGRAM BOT             ║
║              Version 5.0 — Rebuild (All-in-One)              ║
║                                                              ║
║  PART 1/7: Config, Logging, Helpers, Database Schema         ║
║                                                              ║
║  Features covered in full build:                             ║
║  • Category → Product → Plan → Key store flow                 ║
║  • Wallet + UPI QR + Binance USDT + UTR manual                ║
║  • Auto API payment verification (ZapUPI/Binance)             ║
║  • Manual approval flow (admin sees request, approves)        ║
║  • Stock ID system (category-wise ID inventory)               ║
║  • Per-user normal / reseller pricing                         ║
║  • Set All Products Normal / Reseller bulk op                 ║
║  • Coupons, Daily Gift, Refer & Earn                          ║
║  • Support tickets + admin reply                              ║
║  • Broadcast (text/photo/video/doc)                           ║
║  • Complete admin panel matching provided screenshots         ║
║  • Menu Designer, Message Editor, Profile Field Manager       ║
║  • Global + Category + Product maintenance modes              ║
║  • Co-admins + Ownership transfer + Direct reseller by ID     ║
║  • API Manager (multiple endpoints + plan variants)           ║
║  • Link manager (Download / How-To-Use / Payment Proof /      ║
║    Support)                                                   ║
║  • Full logging + health web server                           ║
╚══════════════════════════════════════════════════════════════╝
"""
import asyncio
import sqlite3
import logging
import time
import os
import io
import json
import aiohttp
from aiohttp import web
from datetime import datetime, timedelta
from urllib.parse import quote
from typing import Optional, List, Tuple, Dict, Any

# .env loader (agar python-dotenv installed ho)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Telegram + aiogram imports
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    CallbackQuery,
    Message,
    BufferedInputFile,
)

# QR ke liye optional
try:
    import qrcode
except ImportError:
    qrcode = None

# ══════════════════════════════════════════════════════════════
#                        CONFIGURATION
# ══════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN missing. Set it in environment variables.\n"
        "Render/Railway: Dashboard → Environment → Add BOT_TOKEN"
    )

_ADMIN_IDS_TEXT = os.getenv("ADMIN_IDS", "").strip()
_CONFIGURED_ADMIN_ID_LIST = [
    int(x.strip()) for x in _ADMIN_IDS_TEXT.split(",") if x.strip().isdigit()
]
_CONFIGURED_ADMIN_IDS = set(_CONFIGURED_ADMIN_ID_LIST)

ADMIN_ID = int(
    os.getenv(
        "ADMIN_ID",
        str(_CONFIGURED_ADMIN_ID_LIST[0] if _CONFIGURED_ADMIN_ID_LIST else 8467166339),
    )
)

STATIC_ADMIN_IDS = set(_CONFIGURED_ADMIN_IDS) | {ADMIN_ID}

BOT_USERNAME = os.getenv("BOT_USERNAME", "elitexbot")
BRAND_NAME = os.getenv("BRAND_NAME", "ELITE X CONFIG")
DB_PATH = os.getenv("DB_PATH", "elitex_bot.db")
VIP_DISCOUNT = float(os.getenv("VIP_DISCOUNT", "10.0"))
VIP_PRICE = float(os.getenv("VIP_PRICE", "1000.0"))
WEB_PORT = int(os.getenv("PORT", "8080"))

# Welcome banner path (screenshots jaisa text, HTML allowed)
DEFAULT_WELCOME = (
    "🛒 <b>—— ASIM IS LIVE ——</b> 🛒\n\n"
    "👑 <i>Welcome, {name}</i>\n\n"
    "⭐ <b>—— STORE HIGHLIGHTS ——</b> ⭐\n\n"
    "🎮 Premium Game Keys\n"
    "🟢 Instant Delivery 24/7\n"
    "💯 100% Secure Payment\n"
    "🔥 Best Prices Guaranteed\n"
    "🇮🇳 Safe And Trusted\n"
    "✅ Professional Support\n\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "💰 <b>Wallet Balance:</b> {balance}\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "🔥 <i>Tap Shop Now to Start!</i>"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler("bot_activity.log"), logging.StreamHandler()],
)
logger = logging.getLogger("EliteXBot")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ══════════════════════════════════════════════════════════════
#                        HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════

def fmt(a) -> str:
    """Amount ko ₹X,XXX.XX format me convert karo."""
    try:
        return f"₹{float(a):,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"


def fancy(text) -> str:
    """Unicode small-caps styling (existing feature)."""
    bc = {chr(ord("A") + i): chr(0x1D400 + i) for i in range(26)}
    sc = {
        "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ",
        "g": "ɢ", "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ",
        "m": "ᴍ", "n": "ɴ", "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ",
        "s": "s", "t": "ᴛ", "u": "ᴜ", "v": "ᴠ", "w": "ᴡ", "x": "x",
        "y": "ʏ", "z": "ᴢ",
    }
    out, at = [], True
    for ch in str(text):
        if ch.isascii() and ch.isalpha():
            out.append(bc.get(ch.upper(), ch) if at else sc.get(ch.lower(), ch))
            at = False
        else:
            out.append(ch)
            if ch.isspace() or ch in "/\\|•":
                at = True
    return "".join(out)


def sfloat(v, d=0.0) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return d


def sint(v, d=0) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return d


def upi_link(upi: str, name: str, amt: float, note: str = "") -> str:
    """UPI deep link generate."""
    s = f"upi://pay?pa={quote(str(upi))}&pn={quote(str(name))}&am={float(amt):.2f}&cu=INR"
    if note:
        s += f"&tn={quote(str(note))}"
    return s


def make_qr(data: str):
    """QR code image banao."""
    if qrcode is None:
        return None
    try:
        img = qrcode.make(data)
        buf = io.BytesIO()
        buf.name = "qr.png"
        img.save(buf, format="PNG")
        buf.seek(0)
        return BufferedInputFile(buf.getvalue(), filename="qr.png")
    except Exception as e:
        logger.error(f"QR generation failed: {e}")
        return None


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_progress_bar(pct: int, width: int = 10) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled) + f" {pct}%"


def truncate(text: str, length: int = 100) -> str:
    if not text:
        return ""
    return text[:length] + "..." if len(text) > length else text


def tier_of(user_row) -> str:
    """User tier string nikalo screenshots style me."""
    if not user_row:
        return "USER"
    is_res = bool(user_row[4]) if len(user_row) > 4 else False
    is_vip = bool(user_row[5]) if len(user_row) > 5 else False
    if is_res and is_vip:
        return "VIP RESELLER"
    if is_res:
        return "RESELLER"
    if is_vip:
        return "VIP"
    return "USER"


def tier_emoji(user_row) -> str:
    t = tier_of(user_row)
    return {
        "VIP RESELLER": "💎", "RESELLER": "👑", "VIP": "🌟", "USER": "🥈"
    }.get(t, "👤")


# ══════════════════════════════════════════════════════════════
#                         DATABASE LAYER
# ══════════════════════════════════════════════════════════════

def db(q, p=(), one=False, all=False, commit=True):
    """Thread-safe SQLite helper."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    c = conn.cursor()
    try:
        c.execute(q, p)
        statement = q.lstrip().split(None, 1)[0].upper() if q.strip() else ""
        if one:
            r = c.fetchone()
        elif all:
            r = c.fetchall()
        elif statement in {"INSERT", "REPLACE"}:
            r = c.lastrowid
        else:
            r = None
        if commit:
            conn.commit()
        return r
    except Exception as e:
        logger.error(f"DB error: {e} | Query: {q} | Params: {p}")
        return None
    finally:
        conn.close()


def move_position(table, parent_column, parent_value, item_id, direction):
    """Item ko up/down reorder karo (transaction-safe)."""
    allowed = {
        "categories": ("id", "position", None),
        "products": ("id", "position", "category_id"),
        "plans": ("id", "position", "product_id"),
    }
    if table not in allowed or direction not in ("up", "down"):
        return False
    _, position_column, expected_parent = allowed[table]
    if expected_parent != parent_column:
        return False
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if parent_column:
            rows = conn.execute(
                f"SELECT id FROM {table} WHERE {parent_column}=? ORDER BY {position_column}, id",
                (parent_value,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT id FROM {table} ORDER BY {position_column}, id"
            ).fetchall()
        ids = [row[0] for row in rows]
        if item_id not in ids:
            conn.rollback()
            return False
        index = ids.index(item_id)
        other = index - 1 if direction == "up" else index + 1
        if other < 0 or other >= len(ids):
            conn.rollback()
            return False
        ids[index], ids[other] = ids[other], ids[index]
        for position, row_id in enumerate(ids, start=1):
            conn.execute(
                f"UPDATE {table} SET {position_column}=? WHERE id=?", (position, row_id)
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Failed to reorder %s item %s", table, item_id)
        return False
    finally:
        conn.close()


def gs(k: str, d: str = "") -> str:
    """Get setting."""
    v = db("SELECT value FROM settings WHERE key=?", (k,), one=True)
    return v[0] if v and v[0] else d


def ss(k: str, v):
    """Set setting."""
    db(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (k, str(v)),
    )


def log_activity(user_id: int, action: str, details: str = ""):
    try:
        db(
            "INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, now_str()),
        )
    except Exception as e:
        logger.error(f"Activity log failed: {e}")


def get_user(uid):
    """Full user row nikalo."""
    return db(
        "SELECT user_id, first_name, username, balance, is_reseller, is_vip, "
        "is_banned, joined_date, last_gift, total_spent, total_orders, "
        "refer_by, refer_count FROM users WHERE user_id=?",
        (uid,),
        one=True,
    )


def is_admin(uid: int) -> bool:
    """Owner / configured admin / co-admin check."""
    if uid in STATIC_ADMIN_IDS:
        return True
    r = db("SELECT user_id FROM co_admins WHERE user_id=?", (uid,), one=True)
    return bool(r)


def is_owner(uid: int) -> bool:
    return uid == ADMIN_ID


def ensure_user(m: Message):
    """User ko DB me insert/update karo."""
    uid = m.from_user.id
    row = db("SELECT user_id FROM users WHERE user_id=?", (uid,), one=True)
    if not row:
        db(
            "INSERT INTO users (user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)",
            (uid, m.from_user.first_name or "", m.from_user.username or "", now_str()),
        )
    else:
        db(
            "UPDATE users SET first_name=?, username=? WHERE user_id=?",
            (m.from_user.first_name or "", m.from_user.username or "", uid),
        )


# ══════════════════════════════════════════════════════════════
#                       DATABASE SCHEMA
# ══════════════════════════════════════════════════════════════

def init_db():
    """Saari tables create karo + migrate karo."""
    db_parent = os.path.dirname(os.path.abspath(DB_PATH))
    if db_parent:
        os.makedirs(db_parent, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    c = conn.cursor()

    # ── USERS ──
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT DEFAULT '',
        username TEXT DEFAULT '',
        balance REAL DEFAULT 0,
        is_reseller INTEGER DEFAULT 0,
        is_vip INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        joined_date TEXT,
        last_gift TEXT DEFAULT '',
        total_spent REAL DEFAULT 0,
        total_orders INTEGER DEFAULT 0,
        refer_by INTEGER DEFAULT 0,
        refer_count INTEGER DEFAULT 0
    )""")

    # ── CATEGORIES ──
    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '📂',
        description TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        is_maintenance INTEGER DEFAULT 0,
        position INTEGER DEFAULT 0
    )""")

    # ── PRODUCTS ──
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        emoji TEXT DEFAULT '📦',
        badge_text TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        is_maintenance INTEGER DEFAULT 0,
        position INTEGER DEFAULT 0
    )""")

    # ── PLANS ──
    c.execute("""CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        price REAL DEFAULT 0,
        reseller_price REAL DEFAULT 0,
        discount INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        position INTEGER DEFAULT 0
    )""")

    # ── PRODUCT KEYS ──
    c.execute("""CREATE TABLE IF NOT EXISTS product_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        key_text TEXT NOT NULL,
        is_used INTEGER DEFAULT 0,
        used_by INTEGER DEFAULT 0,
        used_at TEXT DEFAULT '',
        added_at TEXT DEFAULT ''
    )""")

    # ── ORDERS ──
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan_id INTEGER,
        plan_name TEXT,
        product_name TEXT,
        category_name TEXT,
        price_paid REAL,
        delivered_key TEXT,
        purchase_date TEXT,
        status TEXT DEFAULT 'delivered',
        order_ref TEXT DEFAULT ''
    )""")

    # ── BALANCE REQUESTS (manual/auto proof queue) ──
    c.execute("""CREATE TABLE IF NOT EXISTS balance_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT DEFAULT '',
        amount REAL NOT NULL,
        method TEXT DEFAULT 'manual',
        proof_file_id TEXT DEFAULT '',
        reference TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        reviewed_at TEXT DEFAULT ''
    )""")

    # ── SUPPORT TICKETS ──
    c.execute("""CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT,
        status TEXT DEFAULT 'Open',
        reply TEXT DEFAULT '',
        created_at TEXT,
        replied_at TEXT DEFAULT ''
    )""")

    # ── COUPONS ──
    c.execute("""CREATE TABLE IF NOT EXISTS coupons (
        code TEXT PRIMARY KEY,
        discount REAL DEFAULT 0,
        max_uses INTEGER DEFAULT 1,
        used INTEGER DEFAULT 0,
        created_at TEXT
    )""")

    # ── CO-ADMINS ──
    c.execute("""CREATE TABLE IF NOT EXISTS co_admins (
        user_id INTEGER PRIMARY KEY,
        name TEXT DEFAULT '',
        added_at TEXT
    )""")

    # ── SETTINGS ──
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    # ── TRANSACTIONS ──
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        order_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        status TEXT DEFAULT 'pending',
        created_at INTEGER,
        expires_at INTEGER,
        qr_data TEXT DEFAULT '',
        purpose TEXT DEFAULT 'balance',
        plan_id INTEGER,
        method TEXT DEFAULT 'upi'
    )""")

    # ── MENU BUTTONS (Menu Designer) ──
    c.execute("""CREATE TABLE IF NOT EXISTS menu_buttons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        emoji TEXT DEFAULT '',
        action TEXT,
        position INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        row_group INTEGER DEFAULT 0,
        style TEXT DEFAULT 'primary'
    )""")

    # ── PROFILE FIELDS ──
    c.execute("""CREATE TABLE IF NOT EXISTS profile_fields (
        field_key TEXT PRIMARY KEY,
        label TEXT,
        is_visible INTEGER DEFAULT 1
    )""")

    # ── BROADCASTS ──
    c.execute("""CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT,
        sent INTEGER DEFAULT 0,
        failed INTEGER DEFAULT 0,
        created_at TEXT
    )""")

    # ── ACTIVITY LOGS ──
    c.execute("""CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        timestamp TEXT
    )""")

    # ── 🆕 STOCK IDs (admin: Add Stock ID / Check ID Stock) ──
    c.execute("""CREATE TABLE IF NOT EXISTS stock_ids (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER DEFAULT 0,
        product_id INTEGER DEFAULT 0,
        plan_id INTEGER DEFAULT 0,
        id_text TEXT NOT NULL,
        note TEXT DEFAULT '',
        is_used INTEGER DEFAULT 0,
        used_by INTEGER DEFAULT 0,
        used_at TEXT DEFAULT '',
        added_at TEXT
    )""")

    # ── 🆕 CATEGORY ↔ ID MAPPING (Add Cat for ID) ──
    c.execute("""CREATE TABLE IF NOT EXISTS category_id_map (
        category_id INTEGER PRIMARY KEY,
        id_prefix TEXT DEFAULT '',
        note TEXT DEFAULT '',
        created_at TEXT
    )""")

    # ── 🆕 PER-USER PRICE OVERRIDES (Set Normal/Reseller Price ID) ──
    c.execute("""CREATE TABLE IF NOT EXISTS user_price_overrides (
        user_id INTEGER NOT NULL,
        plan_id INTEGER NOT NULL,
        normal_price REAL DEFAULT 0,
        reseller_price REAL DEFAULT 0,
        updated_at TEXT,
        PRIMARY KEY (user_id, plan_id)
    )""")

    # ── 🆕 LINK MANAGER (Download / How-To-Use / Payment Proof / Support) ──
    c.execute("""CREATE TABLE IF NOT EXISTS bot_links (
        key TEXT PRIMARY KEY,
        value TEXT DEFAULT '',
        updated_at TEXT
    )""")

    # ── 🆕 API MANAGER (multiple endpoints + plan variants) ──
    c.execute("""CREATE TABLE IF NOT EXISTS api_endpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        api_key TEXT DEFAULT '',
        provider TEXT DEFAULT 'custom',
        is_active INTEGER DEFAULT 1,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS plan_api_variant (
        plan_id INTEGER PRIMARY KEY,
        api_id INTEGER DEFAULT 0,
        variant TEXT DEFAULT '',
        updated_at TEXT
    )""")

    # ── 🆕 RESELLER REQUESTS (Direct reseller by user ID) ──
    c.execute("""CREATE TABLE IF NOT EXISTS reseller_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        reviewed_at TEXT DEFAULT ''
    )""")

    # ══════════════════════════════════════════════════════════
    # MIGRATIONS (purane DB ke liye safe additions)
    # ══════════════════════════════════════════════════════════

    def _cols(table):
        return {row[1] for row in c.execute(f"PRAGMA table_info({table})").fetchall()}

    # transactions: plan_id, method
    cols = _cols("transactions")
    if "plan_id" not in cols:
        c.execute("ALTER TABLE transactions ADD COLUMN plan_id INTEGER")
    if "method" not in cols:
        c.execute("ALTER TABLE transactions ADD COLUMN method TEXT DEFAULT 'upi'")

    # products: badge_text
    cols = _cols("products")
    if "badge_text" not in cols:
        c.execute("ALTER TABLE products ADD COLUMN badge_text TEXT DEFAULT ''")

    # orders: order_ref, category_name
    cols = _cols("orders")
    if "order_ref" not in cols:
        c.execute("ALTER TABLE orders ADD COLUMN order_ref TEXT DEFAULT ''")
    if "category_name" not in cols:
        c.execute("ALTER TABLE orders ADD COLUMN category_name TEXT DEFAULT ''")

    # menu_buttons: style
    cols = _cols("menu_buttons")
    if "style" not in cols:
        c.execute("ALTER TABLE menu_buttons ADD COLUMN style TEXT DEFAULT 'primary'")

    # ══════════════════════════════════════════════════════════
    # DEFAULT SETTINGS
    # ══════════════════════════════════════════════════════════

    defaults = {
        # UI texts
        "welcome_text": DEFAULT_WELCOME,
        "ui_category_msg": "🛒 <b>PRODUCT STORE — SHOP</b> 🛒\n\n🔥 Choose a product:",
        "ui_product_msg": "📦 <b>Choose a product:</b>",
        "ui_plan_msg": "🛒 <b>Choose your access plan:</b>",
        "ui_key_msg": "✅ <b>Thank you for your purchase!</b>",
        "ui_shop_header": "🛒 <b>PRODUCT STORE — SHOP</b> 🛒",
        "ui_highlights": (
            "🎮 Premium Game Keys\n"
            "🟢 Instant Delivery 24/7\n"
            "💯 100% Secure Payment\n"
            "🔥 Best Prices Guaranteed\n"
            "🇮🇳 Safe And Trusted\n"
            "✅ Professional Support"
        ),

        # Payments
        "upi_id": "",
        "payee_name": BRAND_NAME,
        "static_qr_file_id": "",
        "payment_mode": "manual",  # manual / auto
        "auto_api_key": "",
        "auto_api_url": "",
        "auto_api_enabled": "0",
        # 🆕 Binance
        "binance_pay_id": "",
        "binance_pay_name": "",
        "binance_qr_file_id": "",
        "binance_enabled": "1",
        "zapupi_enabled": "0",
        "zapupi_key": "",
        "zapupi_merchant": "",
        # Payment options on order page
        "pay_upi_enabled": "1",
        "pay_binance_enabled": "1",
        "coupon_on_order": "1",

        # Wallet quick amounts
        "quick_amounts": "100,500,1000,2000",
        "min_add_amount": "1",
        "max_add_amount": "99999",

        # Maintenance
        "global_maintenance": "0",
        "maintenance_msg": "🛠️ Bot is under maintenance. Please try again later.",

        # Marketing
        "daily_gift_price": "0",
        "refer_earn_amount": "0",
        "reseller_setup_fee": "500",
        "reseller_min_balance": "1000",
        "reseller_system_status": "ON",
        "vip_system_status": "ON",
        "reseller_global_discount": "0",  # set all products reseller %
        "normal_global_discount": "0",    # set all products normal %

        # Support links
        "support_telegram": "https://t.me/YourSupport",
        "support_whatsapp": "",

        # 🆕 Link manager
        "link_download": "",
        "link_howtouse": "",
        "link_payment_proof": "",
        "link_share": "",
        "link_support": "",

        # Media
        "admin_logo_file_id": "",
        "admin_logo_media_type": "photo",
        "welcome_media_type": "none",

        # Custom buttons (legacy)
        "custom_buttons": "[]",
    }

    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))

    # ══════════════════════════════════════════════════════════
    # DEFAULT MENU BUTTONS (screenshots ke mutabik)
    # ══════════════════════════════════════════════════════════
    if c.execute("SELECT COUNT(*) FROM menu_buttons").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO menu_buttons (label, emoji, action, position, is_active, row_group, style) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            [
                ("Shop / Store Product", "🛒", "shop", 1, 0, "danger"),
                ("Add Balance", "💰", "addbalance", 2, 1, "success"),
                ("My Profile", "👑", "profile", 3, 1, "primary"),
                ("How To Use", "📚", "howtouse", 4, 2, "primary"),
                ("Lucky", "🎁", "daily_gift", 5, 2, "success"),
                ("Share", "🔗", "share", 6, 3, "primary"),
                ("Support", "🔔", "support", 7, 3, "primary"),
            ],
        )

    # ══════════════════════════════════════════════════════════
    # DEFAULT PROFILE FIELDS
    # ══════════════════════════════════════════════════════════
    if c.execute("SELECT COUNT(*) FROM profile_fields").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO profile_fields (field_key, label, is_visible) VALUES (?, ?, 1)",
            [
                ("user_id", "🆔 ID"),
                ("type", "👤 Type"),
                ("tier", "🏅 Tier"),
                ("joined_date", "📅 Member Since"),
                ("balance", "💰 Balance"),
                ("total_orders", "🛍 Total Orders"),
                ("total_spent", "💵 Total Spent"),
                ("referrals", "⭐ Referrals"),
            ],
        )

    conn.commit()
    conn.close()
    logger.info("✅ Database schema initialized (v5.0)")


# ══════════════════════════════════════════════════════════════
#                       MIDDLEWARE
# ══════════════════════════════════════════════════════════════

class AntiSpam(BaseMiddleware):
    """Simple anti-spam (0.3s throttle)."""

    def __init__(self):
        super().__init__()
        self.last = {}

    async def __call__(self, handler, event, data):
        try:
            uid = event.from_user.id
        except Exception:
            return await handler(event, data)
        now = time.time()
        if uid in self.last and now - self.last[uid] < 0.3:
            return
        self.last[uid] = now
        return await handler(event, data)


class AccessControl(BaseMiddleware):
    """Ban + global maintenance check."""

    async def __call__(self, handler, event, data):
        try:
            uid = event.from_user.id
        except Exception:
            return await handler(event, data)

        if uid != ADMIN_ID and not is_admin(uid):
            u = db("SELECT is_banned FROM users WHERE user_id=?", (uid,), one=True)
            if u and u[0] == 1:
                if isinstance(event, Message):
                    await event.answer("🚫 You are banned from using this bot.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Banned", show_alert=True)
                return

            if gs("global_maintenance") == "1":
                msg = gs("maintenance_msg", "🛠️ Maintenance.")
                if isinstance(event, Message):
                    await event.answer(msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Maintenance ON", show_alert=True)
                return

        return await handler(event, data)


dp.message.middleware(AntiSpam())
dp.callback_query.middleware(AntiSpam())
dp.message.middleware(AccessControl())
dp.callback_query.middleware(AccessControl())


# ══════════════════════════════════════════════════════════════
#                       FSM STATES
# ══════════════════════════════════════════════════════════════

class U(StatesGroup):
    """User FSM states."""
    ticket = State()
    coupon = State()
    custom_amt = State()
    proof = State()
    buy_proof = State()
    ticket_reply = State()
    binance_proof = State()
    # 🆕
    share_target = State()
    redeem_coupon_code = State()


class A(StatesGroup):
    """Admin FSM states — extended."""
    # Category
    cat_name = State()
    cat_desc = State()
    cat_emoji = State()
    cat_edit = State()
    cat_id_prefix = State()

    # Panel
    panel_cat = State()
    panel_name = State()
    panel_desc = State()
    panel_emoji = State()
    panel_edit = State()
    panel_badge = State()

    # Plan
    plan_panel = State()
    plan_name = State()
    plan_price = State()
    plan_rprice = State()
    plan_disc = State()
    plan_edit = State()

    # Keys
    key_plan = State()
    key_text = State()
    key_del = State()

    # Stock IDs (new)
    stock_cat = State()
    stock_product = State()
    stock_plan = State()
    stock_text = State()
    stock_note = State()

    # Users
    user_search = State()
    user_addbal = State()
    user_rembal = State()
    user_price_normal = State()
    user_price_reseller = State()
    user_id_input = State()

    # Broadcast
    bc_msg = State()

    # Coupon
    cp_code = State()
    cp_disc = State()
    cp_max = State()
    cp_del = State()

    # Settings
    set_logo = State()
    set_qr = State()
    set_upi = State()
    set_payee = State()
    set_tg = State()
    set_wa = State()
    set_gift = State()
    set_refer = State()
    set_maint = State()
    set_api_key = State()
    set_api_url = State()

    # 🆕 Binance
    set_binance_id = State()
    set_binance_name = State()
    set_binance_qr = State()

    # 🆕 Links
    set_link_download = State()
    set_link_howtouse = State()
    set_link_proof = State()
    set_link_support = State()
    set_link_share = State()

    # 🆕 API Manager
    api_add_name = State()
    api_add_url = State()
    api_add_key = State()
    api_add_provider = State()
    api_edit_value = State()
    plan_api_variant = State()

    # Message Editor
    msg_welcome = State()
    msg_cat = State()
    msg_prod = State()
    msg_plan = State()
    msg_key = State()

    # Menu Designer
    menu_add_label = State()
    menu_add_emoji = State()
    menu_add_action = State()
    menu_add_row = State()
    menu_edit = State()

    # Co-Admin
    coadmin_add = State()
    coadmin_remove = State()

    # Reseller
    res_fee = State()
    res_min = State()
    res_direct_id = State()

    # 🆕 Ownership
    transfer_confirm = State()

    # 🆕 Bulk operations
    bulk_discount_value = State()
    bulk_balance_value = State()

    # 🆕 Per-user pricing
    price_override_value = State()


logger.info("✅ PART 1 loaded — Config + DB + Helpers + Middleware + FSM ready")
# ══════════════════════════════════════════════════════════════
#                   END OF PART 1 (Continues in Part 2)
# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
#             PART 2 — USER PANEL (Start + Shop + Order)
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
#                       KEYBOARD BUILDERS
# ══════════════════════════════════════════════════════════════

def _btn_style_to_color(action: str) -> str:
    """Screenshot-style hint; Telegram doesn't support color, but we
    keep this function for future Bot API additions."""
    return action


def main_menu_kb(uid=None):
    """Main menu — inline buttons (existing feature preserved)."""
    rows = []
    btns = db(
        "SELECT id, label, emoji, action, row_group FROM menu_buttons "
        "WHERE is_active=1 ORDER BY position, id",
        all=True,
    )
    grouped = {}
    for b in btns or []:
        grouped.setdefault(b[4] or 0, []).append(b)

    for rg in sorted(grouped.keys()):
        row = []
        for b in grouped[rg]:
            t = f"{b[2]} {fancy(b[1])}" if b[2] else fancy(b[1])
            action = str(b[3] or "")
            if action.startswith("url:"):
                url = action[4:].strip()
                if url.startswith(("https://", "http://", "tg://")):
                    row.append(InlineKeyboardButton(text=t, url=url[:500]))
            else:
                row.append(InlineKeyboardButton(text=t, callback_data=f"act_{action}"))
        if row:
            rows.append(row)

    # Legacy custom URL buttons
    try:
        custom_buttons = json.loads(gs("custom_buttons", "[]"))
        if isinstance(custom_buttons, list):
            for item in custom_buttons[:8]:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label", "")).strip()[:50]
                url = str(item.get("url", "")).strip()[:500]
                if label and url.startswith(("https://", "http://", "tg://")):
                    rows.append([InlineKeyboardButton(text=label, url=url)])
    except (ValueError, TypeError):
        logger.warning("Invalid custom_buttons setting; ignoring it")

    # Reseller / VIP quick access
    if uid:
        u = db("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (uid,), one=True)
        ex = []
        if u and u[0]:
            ex.append(InlineKeyboardButton(text="👑 " + fancy("Reseller"), callback_data="act_reseller"))
        if u and u[1]:
            ex.append(InlineKeyboardButton(text="🌟 " + fancy("VIP"), callback_data="act_vip"))
        if ex:
            rows.append(ex)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def bk(cb="adm_back", label="⬅️ Back"):
    """Simple back button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{label} {fancy('Back')}" if label == "⬅️ Back" else label, callback_data=cb)]
    ])


def user_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👆 Back", callback_data="back_main")]
    ])


# ══════════════════════════════════════════════════════════════
#                       START & HOME
# ══════════════════════════════════════════════════════════════

def _build_welcome_text(uid: int) -> str:
    """Welcome text with dynamic name + balance."""
    u = get_user(uid)
    name = "DON"
    balance = "₹0.00"
    if u:
        name = u[1] or "DON"
        balance = fmt(u[3])
    raw = gs("welcome_text", DEFAULT_WELCOME)
    try:
        return raw.format(name=name, balance=balance)
    except (KeyError, IndexError):
        return raw


@dp.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    ensure_user(m)
    log_activity(m.from_user.id, "START")

    # Referral handling
    try:
        args = (m.text or "").split()
        if len(args) > 1 and args[1].startswith("ref_"):
            ref_by = sint(args[1][4:])
            if ref_by and ref_by != m.from_user.id:
                referred = db(
                    "SELECT refer_by FROM users WHERE user_id=?",
                    (m.from_user.id,),
                    one=True,
                )
                referrer = db("SELECT user_id FROM users WHERE user_id=?", (ref_by,), one=True)
                if referred and (referred[0] in (0, None)) and referrer:
                    db("UPDATE users SET refer_by=? WHERE user_id=?", (ref_by, m.from_user.id))
                    db(
                        "UPDATE users SET refer_count=refer_count+1 WHERE user_id=?",
                        (ref_by,),
                    )
                    reward = sfloat(gs("refer_earn_amount"))
                    if reward > 0:
                        db(
                            "UPDATE users SET balance=balance+? WHERE user_id=?",
                            (reward, ref_by),
                        )
    except Exception as e:
        logger.error(f"Referral error: {e}")

    text = _build_welcome_text(m.from_user.id)
    logo = gs("admin_logo_file_id")
    kb = main_menu_kb(m.from_user.id)

    if logo:
        try:
            media_type = gs("admin_logo_media_type", "photo")
            if media_type == "animation":
                await m.answer_animation(logo, caption=text, reply_markup=kb)
            elif media_type == "video":
                await m.answer_video(logo, caption=text, reply_markup=kb)
            else:
                await m.answer_photo(logo, caption=text, reply_markup=kb)
            return
        except Exception:
            logger.exception("Could not send configured welcome media")

    await m.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = _build_welcome_text(call.from_user.id)
    kb = main_menu_kb(call.from_user.id)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await call.message.delete()
        except Exception:
            pass
        await bot.send_message(call.from_user.id, text, reply_markup=kb)


@dp.message(Command("cancel"))
async def cmd_cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("✅ Cancelled.", reply_markup=main_menu_kb(m.from_user.id))


@dp.message(Command("help"))
async def cmd_help(m: Message):
    text = (
        "📖 <b>HELP</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🛍️ /start — Main menu\n"
        "👤 /profile — Your profile\n"
        "💳 /balance — Wallet balance\n"
        "🧾 /orders — Order history\n"
        "🔑 /mykey — Your purchased keys\n"
        "🎧 /support — Contact support\n"
        "❌ /cancel — Cancel current action\n"
    )
    if is_admin(m.from_user.id):
        text += (
            "\n👑 <b>ADMIN COMMANDS</b>\n"
            "/admin — Admin panel\n"
            "/addbal USER_ID AMOUNT\n"
            "/removebal USER_ID AMOUNT\n"
            "/deliver ORDER_ID TEXT\n"
            "/addbutton LABEL | URL\n"
            "/clearbuttons"
        )
    await m.answer(text, reply_markup=main_menu_kb(m.from_user.id))


@dp.message(Command("profile"))
async def cmd_profile(m: Message):
    u = get_user(m.from_user.id)
    if not u:
        return await m.answer("User not found. Send /start first.")
    text = build_profile_text(m.from_user.id)
    await m.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 My Key", callback_data="act_my_key")],
            [InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
        ]),
    )


@dp.message(Command("balance"))
async def cmd_balance(m: Message):
    u = get_user(m.from_user.id)
    if not u:
        return await m.answer("User not found. Send /start first.")
    await m.answer(
        f"💰 <b>Your Balance:</b> {fmt(u[3])}",
        reply_markup=main_menu_kb(m.from_user.id),
    )


@dp.message(Command("orders"))
async def cmd_orders(m: Message):
    await show_user_orders(m.from_user.id, m)


@dp.message(Command("support"))
async def cmd_support(m: Message):
    text = "🎧 <b>Support</b>\n\nContact us:\n"
    tg = gs("support_telegram")
    wa = gs("support_whatsapp")
    if tg:
        text += f"\n✈️ Telegram: {tg}"
    if wa:
        text += f"\n📱 WhatsApp: {wa}"
    await m.answer(text, reply_markup=main_menu_kb(m.from_user.id))


@dp.message(Command("mykey"))
async def cmd_mykey(m: Message):
    await show_my_key(m.from_user.id, m)


# ══════════════════════════════════════════════════════════════
#                       MENU ACTIONS
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("act_"))
async def menu_act(call: CallbackQuery, state: FSMContext):
    action = call.data[4:]
    await state.clear()

    if action == "shop":
        await show_categories(call)

    elif action == "profile":
        text = build_profile_text(call.from_user.id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 My Key", callback_data="act_my_key")],
            [InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton(text="🎟️ Redeem Coupon", callback_data="act_redeem_coupon")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
        ])
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            await call.message.answer(text, reply_markup=kb)

    elif action == "my_key":
        await show_my_key(call.from_user.id, call)

    elif action == "addbalance":
        await show_add_balance(call)

    elif action == "support":
        await show_support_menu(call)

    elif action == "daily_gift":
        await claim_daily_gift(call)

    elif action == "howtouse":
        link = gs("link_howtouse")
        if link:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📚 Open Tutorial", url=link)],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
            ])
        else:
            kb = user_back_kb()
        try:
            await call.message.edit_text(
                "📚 <b>How To Use</b>\n\nStep-by-step guide for buying and using products.",
                reply_markup=kb,
            )
        except Exception:
            await call.message.answer("📚 How To Use", reply_markup=kb)

    elif action == "share":
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{call.from_user.id}"
        txt = (
            "🔗 <b>Share & Earn</b>\n\n"
            f"Invite friends using your link:\n<code>{link}</code>\n\n"
            f"💰 Refer Reward: {fmt(gs('refer_earn_amount', '0'))} per referral"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Share on Telegram",
                    url=f"https://t.me/share/url?url={quote(link)}&text=Join%20Now",
                )
            ],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
        ])
        try:
            await call.message.edit_text(txt, reply_markup=kb)
        except Exception:
            await call.message.answer(txt, reply_markup=kb)

    elif action == "redeem_coupon":
        await state.set_state(U.coupon)
        try:
            await call.message.edit_text(
                "🎟️ <b>Redeem Coupon</b>\n\nSend your coupon code:",
                reply_markup=bk("back_main"),
            )
        except Exception:
            await call.message.answer("🎟️ Send your coupon code:")

    elif action == "reseller":
        await show_reseller_panel(call)

    elif action == "vip":
        await show_vip_panel(call)

    else:
        await call.answer("Coming soon!", show_alert=True)


# ══════════════════════════════════════════════════════════════
#                       PROFILE
# ══════════════════════════════════════════════════════════════

def build_profile_text(uid: int) -> str:
    u = get_user(uid)
    if not u:
        return "User not found."

    oc = db("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,), one=True)
    oc = oc[0] if oc else 0
    sp = db(
        "SELECT COALESCE(SUM(price_paid),0) FROM orders WHERE user_id=?",
        (uid,),
        one=True,
    )
    sp = sp[0] if sp else 0
    fields = db(
        "SELECT field_key, label FROM profile_fields WHERE is_visible=1", all=True
    )

    t = tier_of(u)
    t_emoji = tier_emoji(u)
    acc_type = "VIP Reseller" if (u[4] and u[5]) else (
        "Reseller" if u[4] else ("VIP" if u[5] else "User")
    )

    text = "👑 <b>Your Profile</b>\n━━━━━━━━━━━━━━━━━━\n"
    for f in fields or []:
        k = f[0]
        label = f[1] or k
        if k == "user_id":
            text += f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        elif k == "type":
            text += f"👤 <b>Type:</b> {acc_type}\n"
        elif k == "tier":
            text += f"{t_emoji} <b>Tier:</b> {t}\n"
        elif k == "joined_date":
            text += f"📅 <b>Member Since:</b> {u[7] or 'N/A'}\n"
        elif k == "balance":
            text += f"💰 <b>Balance:</b> {fmt(u[3])}\n"
        elif k == "total_orders":
            text += f"🛍 <b>Total Orders:</b> {oc}\n"
        elif k == "total_spent":
            text += f"💵 <b>Total Spent:</b> {fmt(sp)}\n"
        elif k == "referrals":
            text += f"⭐ <b>Referrals:</b> {u[12] or 0}\n"

    text += "\n🔑 <i>Want to see your purchased keys? Tap \"My Key\" below.</i>"
    return text


@dp.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):
    await show_user_orders(call.from_user.id, call)


async def show_user_orders(uid, target):
    o = db(
        """SELECT id, product_name, plan_name, price_paid, delivered_key,
                  purchase_date, status
           FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 15""",
        (uid,),
        all=True,
    )
    if not o:
        msg = "📭 <b>No orders yet.</b>\n\nStart shopping from the main menu!"
        kb = bk("back_main")
        if isinstance(target, CallbackQuery):
            try:
                await target.message.edit_text(msg, reply_markup=kb)
            except Exception:
                await target.message.answer(msg, reply_markup=kb)
        else:
            await target.answer(msg, reply_markup=kb)
        return

    text = "🧾 <b>MY ORDERS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for r in o:
        text += (
            f"\n🆔 <b>Order #{r[0]}</b>\n"
            f"📦 {r[1]} - {r[2]}\n"
            f"💰 {fmt(r[3])}\n"
            f"🔑 <code>{truncate(r[4], 40)}</code>\n"
            f"📅 {r[5]}\n"
        )
    text = text[:4000]
    kb = bk("back_main")
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb)
        except Exception:
            await target.message.answer(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


# ══════════════════════════════════════════════════════════════
#                  MY KEY (New — product-wise view)
# ══════════════════════════════════════════════════════════════

async def show_my_key(uid: int, target):
    """Show products user has purchased keys for (screenshot style)."""
    rows_data = db(
        """SELECT product_name, COUNT(*) FROM orders
           WHERE user_id=? AND delivered_key IS NOT NULL AND delivered_key != ''
           GROUP BY product_name ORDER BY MAX(id) DESC""",
        (uid,),
        all=True,
    )
    if not rows_data:
        msg = "📭 <b>No keys yet.</b>\n\nPurchase a product first!"
        kb = bk("back_main")
        if isinstance(target, CallbackQuery):
            try:
                await target.message.edit_text(msg, reply_markup=kb)
            except Exception:
                await target.message.answer(msg, reply_markup=kb)
        else:
            await target.answer(msg, reply_markup=kb)
        return

    rows = []
    for r in rows_data:
        pname = r[0] or "Product"
        cnt = r[1]
        rows.append([
            InlineKeyboardButton(
                text=f"🔑 {pname} ({cnt})",
                callback_data=f"myk_{quote(pname)[:40]}",
            )
        ])
    rows.append([InlineKeyboardButton(text="👆 Back", callback_data="back_main")])

    text = "🔑 <b>My Key</b>\n\nSelect a product to view your keys:"
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb)
        except Exception:
            await target.message.answer(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@dp.callback_query(F.data.startswith("myk_"))
async def my_key_view(call: CallbackQuery):
    from urllib.parse import unquote
    pname = unquote(call.data[4:])
    keys = db(
        """SELECT id, plan_name, delivered_key, purchase_date
           FROM orders WHERE user_id=? AND product_name=?
           ORDER BY id DESC""",
        (call.from_user.id, pname),
        all=True,
    )
    if not keys:
        return await call.answer("No keys found.", show_alert=True)

    text = f"🔑 <b>{pname}</b>\n━━━━━━━━━━━━━━━━━━\n"
    for k in keys:
        text += (
            f"\n⏱ <b>{k[1]}</b>\n"
            f"🔑 <code>{k[2]}</code>\n"
            f"📅 {k[3]}\n"
        )
    text = text[:4000]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="act_my_key")]
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)


# ══════════════════════════════════════════════════════════════
#                  SUPPORT MENU
# ══════════════════════════════════════════════════════════════

async def show_support_menu(call: CallbackQuery):
    rows = []
    tg = gs("support_telegram")
    wa = gs("support_whatsapp")
    if tg:
        rows.append([InlineKeyboardButton(text="✈️ Telegram Support", url=tg)])
    if wa:
        rows.append([InlineKeyboardButton(text="📱 WhatsApp Support", url=wa)])
    rows.append([InlineKeyboardButton(text="🎫 New Ticket", callback_data="new_ticket")])
    rows.append([InlineKeyboardButton(text="📋 My Tickets", callback_data="my_tickets")])
    rows.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await call.message.edit_text(
            "🎧 <b>SUPPORT CENTER</b>\n\nChoose an option:", reply_markup=kb
        )
    except Exception:
        await call.message.answer("🎧 <b>SUPPORT CENTER</b>", reply_markup=kb)


# ══════════════════════════════════════════════════════════════
#                  DAILY GIFT / VIP / RESELLER
# ══════════════════════════════════════════════════════════════

async def claim_daily_gift(call: CallbackQuery):
    gift = sfloat(gs("daily_gift_price"))
    if gift <= 0:
        return await call.answer("🎁 Daily gift is disabled.", show_alert=True)

    today = today_str()
    u = get_user(call.from_user.id)
    if not u:
        return await call.answer("Please /start first.", show_alert=True)

    if u[8] == today:
        return await call.answer(
            "🎁 Already claimed today! Come back tomorrow.", show_alert=True
        )

    db(
        "UPDATE users SET balance=balance+?, last_gift=? WHERE user_id=?",
        (gift, today, call.from_user.id),
    )
    log_activity(call.from_user.id, "DAILY_GIFT", str(gift))
    await call.answer(f"🎁 +{fmt(gift)} claimed successfully!", show_alert=True)

    try:
        await call.message.edit_text(
            f"🎁 <b>Daily Gift Claimed!</b
# ══════════════════════════════════════════════════════════════
#             PART 3 — ADMIN PANEL (Core + Store Manager)
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
#                  ADMIN KEYBOARDS
# ══════════════════════════════════════════════════════════════

def admin_kb():
    """Main admin panel keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ " + fancy("Store Manager"), callback_data="adm_store")],
        [InlineKeyboardButton(text="👥 " + fancy("User Manager"), callback_data="adm_users")],
        [InlineKeyboardButton(text="💰 " + fancy("Balance Manager"), callback_data="adm_bal")],
        [InlineKeyboardButton(text="👑 " + fancy("Reseller System"), callback_data="adm_reseller")],
        [InlineKeyboardButton(text="💳 " + fancy("Payment Settings"), callback_data="adm_pay")],
        [InlineKeyboardButton(text="📢 " + fancy("Broadcast"), callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="🎟️ " + fancy("Marketing"), callback_data="adm_mkt")],
        [InlineKeyboardButton(text="🎨 " + fancy("Menu Designer"), callback_data="adm_menu")],
        [InlineKeyboardButton(text="📝 " + fancy("Message Editor"), callback_data="adm_msg")],
        [InlineKeyboardButton(text="🔗 " + fancy("Link Manager"), callback_data="adm_links")],
        [InlineKeyboardButton(text="🧩 " + fancy("API Manager"), callback_data="adm_api_mgr")],
        [InlineKeyboardButton(text="🤝 " + fancy("Co-Admins"), callback_data="adm_coadmin")],
        [InlineKeyboardButton(text="⚙️ " + fancy("Settings"), callback_data="adm_settings")],
        [InlineKeyboardButton(text="🛠️ " + fancy("Maintenance"), callback_data="adm_maint")],
        [InlineKeyboardButton(text="📊 " + fancy("Statistics"), callback_data="adm_stats")],
        [InlineKeyboardButton(text="🏠 " + fancy("User View"), callback_data="back_main")],
    ])


# ══════════════════════════════════════════════════════════════
#                  ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════

async def _admin_balance_command(m: Message, mode: str):
    """Handle /addbal and /removebal."""
    if not is_admin(m.from_user.id):
        return await m.answer("⛔ Admin access only.")
    parts = (m.text or "").split()
    if len(parts) != 3:
        return await m.answer(f"Usage: /{mode} USER_ID AMOUNT")
    try:
        uid = int(parts[1])
        amount = float(parts[2])
        if uid <= 0 or amount <= 0 or amount > 100000000:
            raise ValueError
    except ValueError:
        return await m.answer("USER_ID must be positive integer and AMOUNT 0-100000000.")
    db("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)", (uid, now_str()))
    current = db("SELECT balance FROM users WHERE user_id=?", (uid,), one=True)
    balance = float(current[0]) if current else 0.0
    if mode == "removebal" and balance < amount:
        return await m.answer(f"❌ User has only {fmt(balance)}.")
    if mode == "addbal":
        db("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
        action = "ADMIN_BALANCE_ADD"
        message = f"✅ Added {fmt(amount)} to <code>{uid}</code>. New: {fmt(balance + amount)}"
        user_message = f"💰 Admin added {fmt(amount)}.\nBalance: {fmt(balance + amount)}"
    else:
        db("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))
        action = "ADMIN_BALANCE_REMOVE"
        message = f"✅ Removed {fmt(amount)} from <code>{uid}</code>. New: {fmt(balance - amount)}"
        user_message = f"💰 Admin adjusted: -{fmt(amount)}.\nBalance: {fmt(balance - amount)}"
    log_activity(m.from_user.id, action, f"target={uid}; amount={amount}")
    try:
        await bot.send_message(uid, user_message, reply_markup=main_menu_kb(uid))
    except Exception:
        pass
    await m.answer(message)


@dp.message(Command("addbal"))
async def cmd_addbal(m: Message):
    await _admin_balance_command(m, "addbal")


@dp.message(Command("removebal"))
async def cmd_removebal(m: Message):
    await _admin_balance_command(m, "removebal")


@dp.message(Command("addbutton"))
async def cmd_addbutton(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("⛔ Admin access only.")
    raw = (m.text or "").partition(" ")[2].strip()
    if "|" not in raw:
        return await m.answer("Usage: /addbutton Label | https://example.com")
    label, url = [x.strip() for x in raw.split("|", 1)]
    if not label or not url.startswith(("https://", "http://", "tg://")):
        return await m.answer("Provide label and valid URL.")
    try:
        items = json.loads(gs("custom_buttons", "[]"))
        if not isinstance(items, list):
            items = []
    except (ValueError, TypeError):
        items = []
    if len(items) >= 8:
        return await m.answer("Maximum 8 custom buttons.")
    items.append({"label": label[:50], "url": url[:500]})
    ss("custom_buttons", json.dumps(items, ensure_ascii=False))
    await m.answer("✅ Custom button added. Send /start.")


@dp.message(Command("clearbuttons"))
async def cmd_clearbuttons(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("⛔ Admin access only.")
    ss("custom_buttons", "[]")
    await m.answer("✅ Custom buttons removed.")


@dp.message(Command("deliver"))
async def cmd_deliver(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("⛔ Admin access only.")
    parts = (m.text or "").split(maxsplit=2)
    if len(parts) < 3 or not parts[1].strip() or not parts[2].strip():
        return await m.answer("Usage: /deliver ORDER_ID delivery-text")
    order_token = parts[1].strip()
    content = parts[2].strip()
    product_name = "Product"
    plan_name = "Plan"
    previous_status = "unknown"
    if order_token.isdigit():
        order = db(
            "SELECT user_id, status, product_name, plan_name FROM orders WHERE id=?",
            (int(order_token),),
            one=True,
        )
        if not order:
            return await m.answer("❌ Order ID not found.")
        uid, previous_status, product_name, plan_name = order
    else:
        txn = db(
            "SELECT user_id, status, purpose, plan_id FROM transactions WHERE order_id=?",
            (order_token,),
            one=True,
        )
        if not txn or txn[2] != "order":
            return await m.answer("❌ Order ID not found.")
        uid, previous_status = txn[0], txn[1]
        if previous_status != "paid":
            return await m.answer("⚠️ Manual delivery only after payment approved.")
        product = db(
            "SELECT p.name, pl.name FROM plans pl JOIN products p ON p.id=pl.product_id WHERE pl.id=?",
            (txn[3],),
            one=True,
        )
        if product:
            product_name, plan_name = product
    try:
        await bot.send_message(
            uid,
            f"🎁 <b>MANUAL DELIVERY / ORDER #{order_token}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n📦 {product_name or 'Product'} — {plan_name or 'Plan'}\n\n"
            f"{content}\n━━━━━━━━━━━━━━━━━━\nELITE X CONFIG",
            reply_markup=main_menu_kb(uid),
        )
    except Exception as exc:
        logger.exception("Manual delivery failed for %s", order_token)
        return await m.answer(f"❌ Could not send: {str(exc)[:150]}")
    log_activity(m.from_user.id, "MANUAL_DELIVERY", f"order={order_token}; user={uid}")
    await m.answer(f"✅ Delivered to <code>{uid}</code> for #{order_token}.")


@dp.message(Command("admin"))
async def admin_cmd(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return await m.answer("⛔ Access denied.")
    await state.clear()
    text = (
        "⚙️ <b>ADMIN CONTROL PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👑 Welcome Admin!\n"
        "Select an option below:"
    )
    await m.answer(text, reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_back")
async def adm_back(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Access denied.", show_alert=True)
    await state.clear()
    try:
        await call.message.edit_text(
            "⚙️ <b>ADMIN CONTROL PANEL</b>\n━━━━━━━━━━━━━━━━━━\n👑 Select an option:",
            reply_markup=admin_kb(),
        )
    except Exception:
        await call.message.answer("⚙️ Admin Panel", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                  STATISTICS
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    total_users = db("SELECT COUNT(*) FROM users", one=True)[0]
    total_orders = db("SELECT COUNT(*) FROM orders", one=True)[0]
    total_products = db("SELECT COUNT(*) FROM products", one=True)[0]
    total_plans = db("SELECT COUNT(*) FROM plans", one=True)[0]
    total_keys = db("SELECT COUNT(*) FROM product_keys WHERE is_used=0", one=True)[0]
    used_keys = db("SELECT COUNT(*) FROM product_keys WHERE is_used=1", one=True)[0]
    total_revenue = db("SELECT COALESCE(SUM(price_paid),0) FROM orders", one=True)[0]
    total_balance = db("SELECT COALESCE(SUM(balance),0) FROM users", one=True)[0]
    resellers = db("SELECT COUNT(*) FROM users WHERE is_reseller=1", one=True)[0]
    vip_users = db("SELECT COUNT(*) FROM users WHERE is_vip=1", one=True)[0]
    pending_reqs = db("SELECT COUNT(*) FROM balance_requests WHERE status='pending'", one=True)[0]
    open_tickets = db("SELECT COUNT(*) FROM tickets WHERE status='Open'", one=True)[0]
    banned = db("SELECT COUNT(*) FROM users WHERE is_banned=1", one=True)[0]
    total_stock_ids = db("SELECT COUNT(*) FROM stock_ids WHERE is_used=0", one=True)[0]

    text = (
        f"📊 <b>BOT STATISTICS</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>USERS</b>\n"
        f"• Total Users: <b>{total_users}</b>\n"
        f"• Resellers: <b>{resellers}</b>\n"
        f"• VIP Members: <b>{vip_users}</b>\n"
        f"• Banned: <b>{banned}</b>\n\n"
        f"🛍️ <b>STORE</b>\n"
        f"• Products: <b>{total_products}</b>\n"
        f"• Plans: <b>{total_plans}</b>\n"
        f"• Available Keys: <b>{total_keys}</b>\n"
        f"• Used Keys: <b>{used_keys}</b>\n"
        f"• Stock IDs: <b>{total_stock_ids}</b>\n\n"
        f"💰 <b>FINANCE</b>\n"
        f"• Total Revenue: <b>{fmt(total_revenue)}</b>\n"
        f"• Total Balance: <b>{fmt(total_balance)}</b>\n"
        f"• Total Orders: <b>{total_orders}</b>\n\n"
        f"📋 <b>PENDING</b>\n"
        f"• Balance Requests: <b>{pending_reqs}</b>\n"
        f"• Open Tickets: <b>{open_tickets}</b>\n"
    )
    try:
        await call.message.edit_text(text, reply_markup=bk("adm_back"))
    except Exception:
        await call.message.answer(text, reply_markup=bk("adm_back"))


# ══════════════════════════════════════════════════════════════
#                  STORE MANAGER
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_store")
async def adm_store(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Categories", callback_data="adm_cats"),
         InlineKeyboardButton(text="📦 Panels", callback_data="adm_panels")],
        [InlineKeyboardButton(text="⏱ Plans", callback_data="adm_plans"),
         InlineKeyboardButton(text="🔑 Keys", callback_data="adm_keys")],
        [InlineKeyboardButton(text="🧩 Stock ID Manager", callback_data="adm_stockid")],
        [InlineKeyboardButton(text="🔀 Reorder Store", callback_data="adm_reorder")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("🛍️ <b>STORE MANAGER</b>\n\nChoose section:", reply_markup=kb)
    except Exception:
        await call.message.answer("🛍️ Store Manager", reply_markup=kb)


# ══════════════════════════════════════════════════════════════
#                  CATEGORY MANAGER
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_cats")
async def adm_cats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Category", callback_data="adm_cat_add")],
        [InlineKeyboardButton(text="📋 List Categories", callback_data="adm_cat_list")],
        [InlineKeyboardButton(text="✏️ Edit Category", callback_data="adm_cat_edit_list")],
        [InlineKeyboardButton(text="🗑️ Delete Category", callback_data="adm_cat_del_list")],
        [InlineKeyboardButton(text="🔀 Reorder Categories", callback_data="adm_cat_move_list")],
        [InlineKeyboardButton(text="🔧 Maintenance Toggle", callback_data="adm_cat_mt_list")],
        [InlineKeyboardButton(text="🆔 Category ID Prefix", callback_data="adm_cat_id_list")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_store")],
    ])
    try:
        await call.message.edit_text("📂 <b>CATEGORY MANAGER</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("📂 Category Manager", reply_markup=kb)


@dp.callback_query(F.data == "adm_cat_add")
async def cat_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.cat_name)
    await call.message.edit_text(
        "📝 <b>Add Category</b>\n\nStep 1/3: Enter category name:",
        reply_markup=bk("adm_cats"),
    )


@dp.message(A.cat_name)
async def cat_name_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    await state.update_data(cat_name=m.text.strip())
    await state.set_state(A.cat_desc)
    await m.answer("📝 Step 2/3: Enter description (or 'none'):")


@dp.message(A.cat_desc)
async def cat_desc_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    desc = "" if m.text.lower() == "none" else m.text.strip()
    await state.update_data(cat_desc=desc)
    await state.set_state(A.cat_emoji)
    await m.answer("😀 Step 3/3: Send emoji (e.g. 📱):")


@dp.message(A.cat_emoji)
async def cat_emoji_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    d = await state.get_data()
    pos_row = db("SELECT COALESCE(MAX(position),0)+1 FROM categories", one=True)
    pos = pos_row[0] if pos_row else 1
    cid = db(
        "INSERT INTO categories (name, emoji, description, position) VALUES (?, ?, ?, ?)",
        (d.get("cat_name", ""), m.text.strip()[:10], d.get("cat_desc", ""), pos),
    )
    await state.clear()
    await m.answer(f"✅ Category added! ID: <code>{cid}</code>", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_cat_list")
async def cat_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cats = db(
        "SELECT id, name, emoji, is_active, is_maintenance FROM categories ORDER BY position, id",
        all=True,
    )
    if not cats:
        return await call.message.edit_text("📭 No categories.", reply_markup=bk("adm_cats"))
    text = "📋 <b>CATEGORIES</b>\n━━━━━━━━━━━━━━━━━━\n"
    for c in cats:
        st = "🟢" if c[3] else "🔴"
        mt = " 🔧" if c[4] else ""
        text += f"\n<b>ID {c[0]}</b> {st}{mt}\n{c[2]} {c[1]}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_cats"))


@dp.callback_query(F.data == "adm_cat_edit_list")
async def cat_edit_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cats = db("SELECT id, name FROM categories ORDER BY position, id", all=True)
    if not cats:
        return await call.answer("No categories!", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"✏️ {c[1]}", callback_data=f"cat_edit_{c[0]}")] for c in cats]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_cats")])
    await call.message.edit_text("✏️ Select category to edit:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("cat_edit_"))
async def cat_edit_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[9:])
    c = db("SELECT id, name, emoji, description FROM categories WHERE id=?", (cid,), one=True)
    if not c:
        return await call.answer("Not found!", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Name", callback_data=f"cat_ed_name_{cid}")],
        [InlineKeyboardButton(text="😀 Emoji", callback_data=f"cat_ed_emoji_{cid}")],
        [InlineKeyboardButton(text="📝 Description", callback_data=f"cat_ed_desc_{cid}")],
        [InlineKeyboardButton(text="👁️ Toggle Active", callback_data=f"cat_ed_tog_{cid}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_cat_edit_list")],
    ])
    await call.message.edit_text(
        f"📂 <b>{c[1]}</b>\n\nID: {cid}\nEmoji: {c[2]}\nDesc: {c[3] or 'None'}",
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith("cat_ed_"))
async def cat_edit_field(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    field = parts[2]
    cid = sint(parts[3])
    if field == "tog":
        cur = db("SELECT is_active FROM categories WHERE id=?", (cid,), one=True)[0]
        db("UPDATE categories SET is_active=? WHERE id=?", (0 if cur else 1, cid))
        await call.answer("✅ Toggled!", show_alert=True)
        return await cat_edit_menu(call)
    await state.update_data(edit_cat_id=cid, edit_cat_field=field)
    await state.set_state(A.cat_edit)
    await call.message.edit_text(f"📝 Send new value for <b>{field}</b>:", reply_markup=bk("adm_cats"))


@dp.message(A.cat_edit)
async def cat_edit_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    d = await state.get_data()
    col_map = {"name": "name", "emoji": "emoji", "desc": "description"}
    col = col_map.get(d.get("edit_cat_field"), "name")
    val = m.text.strip()
    if col == "emoji":
        val = val[:10]
    db(f"UPDATE categories SET {col}=? WHERE id=?", (val, d.get("edit_cat_id")))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_cat_del_list")
async def cat_del_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cats = db("SELECT id, name FROM categories ORDER BY position, id", all=True)
    if not cats:
        return await call.answer("No categories!", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"🗑️ {c[1]}", callback_data=f"cat_del_{c[0]}")] for c in cats]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_cats")])
    await call.message.edit_text(
        "⚠️ Select category to DELETE (cascades to panels/plans/keys):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@dp.callback_query(F.data.regexp(r"^cat_del_\d+$"))
async def cat_del_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[8:])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"cat_del_yes_{cid}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_cats")],
    ])
    await call.message.edit_text(
        f"⚠️ Delete category <code>{cid}</code> and all its panels/plans/keys?",
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith("cat_del_yes_"))
async def cat_del_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[12:])
    category = db("SELECT id, name FROM categories WHERE id=?", (cid,), one=True)
    if not category:
        return await call.answer("Category not found.", show_alert=True)

    historical = db(
        "SELECT COUNT(*) FROM orders o JOIN plans pl ON pl.id=o.plan_id "
        "JOIN products p ON p.id=pl.product_id WHERE p.category_id=?",
        (cid,),
        one=True,
    )
    if historical and historical[0] > 0:
        return await call.answer(
            "Cannot delete: category contains products with historical orders.",
            show_alert=True,
        )
    pending = db(
        "SELECT COUNT(*) FROM balance_requests br JOIN plans pl "
        "ON br.reference LIKE ('%|PLAN:' || pl.id || '|%') "
        "JOIN products p ON p.id=pl.product_id WHERE p.category_id=? AND br.status='pending'",
        (cid,),
        one=True,
    )
    if pending and pending[0] > 0:
        return await call.answer(
            "Resolve pending payments first.", show_alert=True
        )
    prods = db("SELECT id FROM products WHERE category_id=?", (cid,), all=True)
    for product in prods or []:
        plans = db("SELECT id FROM plans WHERE product_id=?", (product[0],), all=True)
        for plan in plans or []:
            db("DELETE FROM product_keys WHERE plan_id=?", (plan[0],))
        db("DELETE FROM plans WHERE product_id=?", (product[0],))
    db("DELETE FROM products WHERE category_id=?", (cid,))
    db("DELETE FROM categories WHERE id=?", (cid,))
    db("DELETE FROM stock_ids WHERE category_id=?", (cid,))
    db("DELETE FROM category_id_map WHERE category_id=?", (cid,))
    await call.answer("🗑️ Category deleted.", show_alert=True)
    await adm_cats(call)


@dp.callback_query(F.data == "adm_cat_move_list")
async def cat_move_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cats = db("SELECT id, name, emoji FROM categories ORDER BY position, id", all=True)
    if not cats:
        return await call.answer("No categories to reorder.", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"{c[2]} {c[1]}", callback_data=f"ac_move_{c[0]}")] for c in cats]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_cats")])
    await call.message.edit_text("🔀 Select a category to reorder:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("ac_move_"))
async def cat_move_pick(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[8:])
    cat = db("SELECT name, emoji FROM categories WHERE id=?", (cid,), one=True)
    if not cat:
        return await call.answer("Category not found.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬆️ Move Up", callback_data=f"acm_{cid}_up"),
         InlineKeyboardButton(text="⬇️ Move Down", callback_data=f"acm_{cid}_down")],
        [InlineKeyboardButton(text="⬅️ Category List", callback_data="adm_cat_move_list")],
    ])
    await call.message.edit_text(f"🔀 Reorder: {cat[1]} {cat[0]}", reply_markup=kb)


@dp.callback_query(F.data.startswith("acm_"))
async def cat_move_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    if len(parts) != 3:
        return await call.answer("Invalid reorder action.", show_alert=True)
    cid, direction = sint(parts[1]), parts[2]
    moved = move_position("categories", None, None, cid, direction)
    if not moved:
        return await call.answer("Already at end or not found.", show_alert=True)
    await call.answer("✅ Order updated.")
    await cat_move_list(call)


@dp.callback_query(F.data == "adm_cat_mt_list")
async def cat_mt_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cats = db("SELECT id, name, is_maintenance FROM categories", all=True)
    if not cats:
        return await call.answer("No categories!", show_alert=True)
    rows = []
    for c in cats:
        st = "🔧 ON" if c[2] else "✅ OFF"
        rows.append([InlineKeyboardButton(text=f"{st} — {c[1]}", callback_data=f"cat_mt_{c[0]}")])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_cats")])
    await call.message.edit_text("🔧 Toggle maintenance per category:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("cat_mt_"))
async def cat_mt_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[7:])
    cur = db("SELECT is_maintenance FROM categories WHERE id=?", (cid,), one=True)[0]
    db("UPDATE categories SET is_maintenance=? WHERE id=?", (0 if cur else 1, cid))
    await call.answer(f"🔧 Maintenance {'OFF' if cur else 'ON'}!", show_alert=True)
    await cat_mt_list(call)


# ══════════════════════════════════════════════════════════════
#                  CATEGORY ID PREFIX (Add Cat for ID)
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_cat_id_list")
async def cat_id_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cats = db("SELECT id, name FROM categories ORDER BY position, id", all=True)
    if not cats:
        return await call.answer("No categories!", show_alert=True)
    rows = []
    for c in cats:
        m = db(
            "SELECT id_prefix FROM category_id_map WHERE category_id=?",
            (c[0],),
            one=True,
        )
        prefix = m[0] if m and m[0] else "—"
        rows.append([InlineKeyboardButton(
            text=f"{c[1]} [{prefix}]", callback_data=f"cat_id_{c[0]}"
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_cats")])
    await call.message.edit_text(
        "🆔 <b>Category ID Prefix</b>\n\nSelect category to set ID prefix:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@dp.callback_query(F.data.startswith("cat_id_"))
async def cat_id_pick(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[7:])
    cat = db("SELECT name FROM categories WHERE id=?", (cid,), one=True)
    if not cat:
        return await call.answer("Category not found.", show_alert=True)
    await state.update_data(cat_id_target=cid)
    await state.set_state(A.cat_id_prefix)
    await call.message.edit_text(
        f"🆔 Set ID prefix for <b>{cat[0]}</b>:\n\n"
        f"<i>Example: BLA, AIM, XRG</i>",
        reply_markup=bk("adm_cat_id_list"),
    )


@dp.message(A.cat_id_prefix)
async def cat_id_prefix_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    d = await state.get_data()
    cid = d.get("cat_id_target")
    prefix = m.text.strip().upper()[:20]
    db(
        "INSERT OR REPLACE INTO category_id_map (category_id, id_prefix, created_at) VALUES (?, ?, ?)",
        (cid, prefix, now_str()),
    )
    await state.clear()
    await m.answer(f"✅ ID prefix set: <b>{prefix}</b>", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                  PANEL MANAGER
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_panels")
async def adm_panels(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Panel", callback_data="adm_panel_add")],
        [InlineKeyboardButton(text="📋 List Panels", callback_data="adm_panel_list")],
        [InlineKeyboardButton(text="✏️ Edit Panel", callback_data="adm_panel_edit_list")],
        [InlineKeyboardButton(text="🏷️ Set Badge Text", callback_data="adm_panel_badge_list")],
        [InlineKeyboardButton(text="👁️ Show / Hide", callback_data="adm_panel_toggle_list")],
        [InlineKeyboardButton(text="🔧 Maintenance", callback_data="adm_panel_maint_list")],
        [InlineKeyboardButton(text="🔀 Reorder", callback_data="adm_panel_move_list")],
        [InlineKeyboardButton(text="📂 Move to Category", callback_data="adm_panel_transfer_list")],
        [InlineKeyboardButton(text="🗑️ Delete Panel", callback_data="adm_panel_delete_list")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_store")],
    ])
    try:
        await call.message.edit_text("📦 <b>PANEL MANAGER</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("📦 Panel Manager", reply_markup=kb)


@dp.callback_query(F.data == "adm_panel_add")
async def panel_add(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cats = db("SELECT id, name, emoji FROM categories ORDER BY position, id", all=True)
    if not cats:
        return await call.answer("Add category first!", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"{c[2]} {c[1]}", callback_data=f"panel_add_cat_{c[0]}"
    )] for c in cats]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panels")])
    await call.message.edit_text(
        "Select category for this panel:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@dp.callback_query(F.data.startswith("panel_add_cat_"))
async def panel_add_cat(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[14:])
    await state.update_data(panel_cat_id=cid)
    await state.set_state(A.panel_name)
    await call.message.edit_text("📝 Step 1/3: Enter panel name:", reply_markup=bk("adm_panels"))


@dp.message(A.panel_name)
async def panel_name_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    await state.update_data(panel_name=m.text.strip())
    await state.set_state(A.panel_desc)
    await m.answer("📝 Step 2/3: Enter description (or 'none'):")


@dp.message(A.panel_desc)
async def panel_desc_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    desc = "" if m.text.lower() == "none" else m.text.strip()
    await state.update_data(panel_desc=desc)
    await state.set_state(A.panel_emoji)
    await m.answer("😀 Step 3/3: Send emoji for this panel:")


@dp.message(A.panel_emoji)
async def panel_emoji_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    d = await state.get_data()
    cid = d.get("panel_cat_id")
    pos_row = db(
        "SELECT COALESCE(MAX(position),0)+1 FROM products WHERE category_id=?",
        (cid,),
        one=True,
    )
    pos = pos_row[0] if pos_row else 1
    pid = db(
        "INSERT INTO products (category_id, name, description, emoji, position) "
        "VALUES (?, ?, ?, ?, ?)",
        (cid, d.get("panel_name", ""), d.get("panel_desc", ""), m.text.strip()[:10], pos),
    )
    await state.clear()
    await m.answer(f"✅ Panel added! ID: <code>{pid}</code>", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_panel_list")
async def panel_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    panels = db(
        """SELECT p.id, p.name, p.emoji, p.is_active, p.is_maintenance, c.name, p.badge_text
           FROM products p LEFT JOIN categories c ON c.id=p.category_id
           ORDER BY p.category_id, p.position, p.id""",
        all=True,
    )
    if not panels:
        return await call.message.edit_text("📭 No panels.", reply_markup=bk("adm_panels"))
    text = "📦 <b>PANELS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for p in panels:
        st = "🟢" if p[3] else "🔴"
        mt = " 🔧" if p[4] else ""
        bt = f" [{p[6]}]" if p[6] else ""
        text += f"\n<b>ID {p[0]}</b> {st}{mt}{bt}\n{p[2]} {p[1]}\n📂 {p[5] or 'N/A'}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_panels"))


@dp.callback_query(F.data == "adm_panel_edit_list")
async def panel_edit_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    panels = db(
        "SELECT p.id, p.name, c.name FROM products p LEFT JOIN categories c ON c.id=p.category_id "
        "ORDER BY p.category_id, p.position, p.id",
        all=True,
    )
    if not panels:
        return await call.answer("No panels to edit.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"✏️ {p[1]} ({p[2] or 'N/A'})", callback_data=f"ap_edit_{p[0]}"
    )] for p in panels]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panels")])
    await call.message.edit_text("Select a panel to edit:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("ap_edit_"))
async def panel_edit_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    pid = sint(call.data[8:])
    panel = db(
        "SELECT name, emoji, description, category_id, badge_text FROM products WHERE id=?",
        (pid,),
        one=True,
    )
    if not panel:
        return await call.answer("Panel not found.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Name", callback_data=f"ape_{pid}_name"),
         InlineKeyboardButton(text="😀 Emoji", callback_data=f"ape_{pid}_emoji")],
        [InlineKeyboardButton(text="📝 Description", callback_data=f"ape_{pid}_desc")],
        [InlineKeyboardButton(text="🏷️ Badge Text", callback_data=f"ape_{pid}_badge")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panel_edit_list")],
    ])
    await call.message.edit_text(
        f"📦 <b>{panel[0]}</b>\nID: {pid}\nEmoji: {panel[1]}\n"
        f"Desc: {panel[2] or 'None'}\nBadge: {panel[4] or 'None'}\n\nChoose field:",
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith("ape_"))
async def panel_edit_field(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    if len(parts) != 3:
        return await call.answer("Invalid edit action.", show_alert=True)
    pid, field = sint(parts[1]), parts[2]
    if field not in {"name", "emoji", "desc", "badge"}:
        return await call.answer("Invalid field.", show_alert=True)
    await state.update_data(edit_panel_id=pid, edit_panel_field=field)
    await state.set_state(A.panel_edit)
    await call.message.edit_text(f"Send new panel {field}:", reply_markup=bk("adm_panel_edit_list"))


@dp.message(A.panel_edit)
async def panel_edit_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    data = await state.get_data()
    field = data.get("edit_panel_field")
    column = {
        "name": "name", "emoji": "emoji", "desc": "description", "badge": "badge_text"
    }.get(field)
    if not column:
        await state.clear()
        return await m.answer("Invalid session.", reply_markup=admin_kb())
    value = m.text.strip()
    if not value:
        return await m.answer("Value cannot be empty.")
    if field == "emoji":
        value = value[:10]
    elif field == "badge":
        value = value[:100]
    elif field == "name":
        value = value[:100]
    else:
        value = "" if value.lower() == "none" else value[:1000]
    db(f"UPDATE products SET {column}=? WHERE id=?", (value, data.get("edit_panel_id")))
    await state.clear()
    await m.answer("✅ Panel updated.", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_panel_badge_list")
async def panel_badge_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    panels = db(
        "SELECT p.id, p.name, p.badge_text FROM products p ORDER BY p.category_id, p.position",
        all=True,
    )
    if not panels:
        return await call.answer("No panels.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"🏷️ {p[1]} [{p[2] or '—'}]", callback_data=f"apbadge_{p[0]}"
    )] for p in panels]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panels")])
    await call.message.edit_text(
        "🏷️ Send badge text per panel:\n<i>Example: (Main id safe) 🔥100</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@dp.callback_query(F.data.startswith("apbadge_"))
async def panel_badge_pick(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    pid = sint(call.data[8:])
    panel = db("SELECT name FROM products WHERE id=?", (pid,), one=True)
    if not panel:
        return await call.answer("Panel not found.", show_alert=True)
    await state.update_data(badge_pid=pid)
    await state.set_state(A.panel_badge)
    await call.message.edit_text(
        f"🏷️ Send new badge for <b>{panel[0]}</b>:\n<i>Example: (Main id safe) 🔥100</i>\n"
        f"<i>'none' for empty.</i>",
        reply_markup=bk("adm_panel_badge_list"),
    )


@dp.message(A.panel_badge)
async def panel_badge_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    d = await state.get_data()
    pid = d.get("badge_pid")
    val = "" if m.text.lower() == "none" else m.text.strip()[:100]
    db("UPDATE products SET badge_text=? WHERE id=?", (val, pid))
    await state.clear()
    await m.answer("✅ Badge saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_panel_toggle_list")
async def panel_toggle_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    panels = db("SELECT id, name, is_active FROM products ORDER BY category_id, position", all=True)
    if not panels:
        return await call.answer("No panels found.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"{'🟢' if p[2] else '🔴'} {p[1]}", callback_data=f"apt_{p[0]}"
    )] for p in panels]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panels")])
    await call.message.edit_text("Toggle panel visibility:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("apt_"))
async def panel_toggle_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    pid = sint(call.data[4:])
    row = db("SELECT is_active FROM products WHERE id=?", (pid,), one=True)
    if not row:
        return await call.answer("Panel not found.", show_alert=True)
    db("UPDATE products SET is_active=? WHERE id=?", (0 if row[0] else 1, pid))
    await call.answer("✅ Updated.")
    await panel_toggle_list(call)


@dp.callback_query(F.data == "adm_panel_maint_list")
async def panel_maint_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    panels = db("SELECT id, name, is_maintenance FROM products ORDER BY category_id, position", all=True)
    if not panels:
        return await call.answer("No panels found.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"{'🔧 ON' if p[2] else '✅ OFF'} — {p[1]}", callback_data=f"apmaint_{p[0]}"
    )] for p in panels]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panels")])
    await call.message.edit_text("Toggle per-panel maintenance:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("apmaint_"))
async def panel_maint_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    pid = sint(call.data[8:])
    row = db("SELECT is_maintenance FROM products WHERE id=?", (pid,), one=True)
    if not row:
        return await call.answer("Panel not found.", show_alert=True)
    db("UPDATE products SET is_maintenance=? WHERE id=?", (0 if row[0] else 1, pid))
    await call.answer("✅ Updated.")
    await panel_maint_list(call)


@dp.callback_query(F.data == "adm_panel_move_list")
async def panel_move_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    panels = db(
        "SELECT p.id, p.name, c.name FROM products p LEFT JOIN categories c ON c.id=p.category_id "
        "ORDER BY p.category_id, p.position",
        all=True,
    )
    if not panels:
        return await call.answer("No panels found.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"🔀 {p[1]} ({p[2] or 'N/A'})", callback_data=f"ap_move_{p[0]}"
    )] for p in panels]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panels")])
    await call.message.edit_text("Select a panel to reorder:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("ap_move_"))
async def panel_move_pick(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    pid = sint(call.data[8:])
    panel = db("SELECT name FROM products WHERE id=?", (pid,), one=True)
    if not panel:
        return await call.answer("Panel not found.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬆️ Move Up", callback_data=f"apm_{pid}_up"),
         InlineKeyboardButton(text="⬇️ Move Down", callback_data=f"apm_{pid}_down")],
        [InlineKeyboardButton(text="⬅️ Panel List", callback_data="adm_panel_move_list")],
    ])
    await call.message.edit_text(f"🔀 Reorder panel: {panel[0]}", reply_markup=kb)


@dp.callback_query(F.data.startswith("apm_"))
async def panel_move_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    if len(parts) != 3:
        return await call.answer("Invalid action.", show_alert=True)
    pid, direction = sint(parts[1]), parts[2]
    panel = db("SELECT category_id FROM products WHERE id=?", (pid,), one=True)
    if not panel or not move_position("products", "category_id", panel[0], pid, direction):
        return await call.answer("Already at end or not found.", show_alert=True)
    await call.answer("✅ Updated.")
    await panel_move_list(call)


@dp.callback_query(F.data == "adm_panel_transfer_list")
async def panel_transfer_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    panels = db(
        "SELECT p.id, p.name, c.name FROM products p LEFT JOIN categories c ON c.id=p.category_id "
        "ORDER BY p.category_id, p.position",
        all=True,
    )
    if not panels:
        return await call.answer("No panels found.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"📂 {p[1]} ({p[2] or 'N/A'})", callback_data=f"ap_transfer_{p[0]}"
    )] for p in panels]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panels")])
    await call.message.edit_text("Select a panel to move:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("ap_transfer_"))
async def panel_transfer_pick(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    pid = sint(call.data[12:])
    panel = db("SELECT name, category_id FROM products WHERE id=?", (pid,), one=True)
    if not panel:
        return await call.answer("Panel not found.", show_alert=True)
    cats = db("SELECT id, name, emoji FROM categories ORDER BY position", all=True)
    if not cats:
        return await call.answer("Create a category first.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"{c[2]} {c[1]}{' ✓' if c[0] == panel[1] else ''}",
        callback_data=f"apdest_{pid}_{c[0]}",
    )] for c in cats]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panel_transfer_list")])
    await call.message.edit_text(
        f"📂 Move <b>{panel[0]}</b> to which category?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@dp.callback_query(F.data.startswith("apdest_"))
async def panel_transfer_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    if len(parts) != 3:
        return await call.answer("Invalid action.", show_alert=True)
    pid, cid = sint(parts[1]), sint(parts[2])
    panel = db("SELECT name FROM products WHERE id=?", (pid,), one=True)
    cat = db("SELECT name FROM categories WHERE id=?", (cid,), one=True)
    if not panel or not cat:
        return await call.answer("Not found.", show_alert=True)
    pos = db(
        "SELECT COALESCE(MAX(position),0)+1 FROM products WHERE category_id=?",
        (cid,),
        one=True,
    )
    db(
        "UPDATE products SET category_id=?, position=? WHERE id=?",
        (cid, pos[0] if pos else 1, pid),
    )
    log_activity(call.from_user.id, "PANEL_MOVED", f"panel={pid}; category={cid}")
    await call.answer("✅ Moved.")
    await panel_transfer_list(call)


@dp.callback_query(F.data == "adm_panel_delete_list")
async def panel_delete_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    panels = db("SELECT p.id, p.name FROM products p ORDER BY p.category_id, p.position", all=True)
    if not panels:
        return await call.answer("No panels found.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"🗑️ {p[1]}", callback_data=f"ap_delete_{p[0]}"
    )] for p in panels]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panels")])
    await call.message.edit_text("Select a panel to delete:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("ap_delete_"))
async def panel_delete_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    pid = sint(call.data[10:])
    panel = db("SELECT name FROM products WHERE id=?", (pid,), one=True)
    if not panel:
        return await call.answer("Panel not found.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Yes, Delete", callback_data=f"apdel_yes_{pid}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_panels")],
    ])
    await call.message.edit_text(
        f"Delete panel <b>{panel[0]}</b> and its plans/keys?", reply_markup=kb
    )


@dp.callback_query(F.data.startswith("apdel_yes_"))
async def panel_delete_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    pid = sint(call.data[10:])
    panel = db("SELECT name FROM products WHERE id=?", (pid,), one=True)
    if not panel:
        return await call.answer("Panel not found.", show_alert=True)
    usage = db(
        "SELECT COUNT(*) FROM orders o JOIN plans pl ON pl.id=o.plan_id WHERE pl.product_id=?",
        (pid,),
        one=True,
    )
    if usage and usage[0] > 0:
        return await call.answer("Cannot delete: historical orders exist.", show_alert=True)
    plans = db("SELECT id FROM plans WHERE product_id=?", (pid,), all=True)
    for plan in plans or []:
        pending = db(
            "SELECT COUNT(*) FROM balance_requests WHERE status='pending' AND reference LIKE ?",
            (f"%|PLAN:{plan[0]}|%",),
            one=True,
        )
        if pending and pending[0] > 0:
            return await call.answer("Resolve pending payments first.", show_alert=True)
    for plan in plans or []:
        db("DELETE FROM product_keys WHERE plan_id=?", (plan[0],))
    db("DELETE FROM plans WHERE product_id=?", (pid,))
    db("DELETE FROM products WHERE id=?", (pid,))
    db("DELETE FROM stock_ids WHERE product_id=?", (pid,))
    await call.answer("🗑️ Deleted.")
    await adm_panels(call)


# ══════════════════════════════════════════════════════════════
#                  PLAN MANAGER
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_plans")
async def adm_plans(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Plan", callback_data="adm_plan_add")],
        [InlineKeyboardButton(text="📋 List Plans", callback_data="adm_plan_list")],
        [InlineKeyboardButton(text="✏️ Edit Plan", callback_data="adm_plan_edit_list")],
        [InlineKeyboardButton(text="👁️ Show / Hide", callback_data="adm_plan_toggle_list")],
        [InlineKeyboardButton(text="🔀 Move Plan", callback_data="adm_plan_move_list")],
        [InlineKeyboardButton(text="🗑️ Delete Plan", callback_data="adm_plan_delete_list")],
        [InlineKeyboardButton(text="🧩 Set Plan API/Variant", callback_data="adm_plan_api_list")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_store")],
    ])
    try:
        await call.message.edit_text("⏱ <b>PLAN MANAGER</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("⏱ Plan Manager", reply_markup=kb)


@dp.callback_query(F.data == "adm_plan_add")
async def plan_add(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    panels = db(
        """SELECT p.id, p.name, c.name FROM products p
           LEFT JOIN categories c ON c.id=p.category_id
           ORDER BY p.category_id, p.position""",
        all=True,
    )
    if not panels:
        return await call.answer("Add panel first!", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"📦 {p[1]} ({p[2] or 'N/A'})", callback_data=f"plan_add_panel_{p[0]}"
    )] for p in panels]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_plans")])
    await call.message.edit_text("Select panel for this plan:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("plan_add_panel_"))
async def plan_add_panel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    pid = sint(call.data[15:])
    await state.update_data(plan_panel_id=pid)
    await state.set_state(A.plan_name)
    await call.message.edit_text("📝 Step 1/5: Enter plan name (e.g. 1 HOUR):", reply_markup=bk("adm_plans"))


@dp.message(A.plan_name)
async def plan_name_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    await state.update_data(plan_name=m.text.strip())
    await state.set_state(A.plan_price)
    await m.answer("💰 Step 2/5: Enter regular price (₹):")


@dp.message(A.plan_price)
async def plan_price_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        p = float(m.text.strip())
    except Exception:
        return await m.answer("❌ Invalid number. Try again:")
    await state.update_data(plan_price=p)
    await state.set_state(A.plan_rprice)
    await m.answer("👑 Step 3/5: Reseller price (₹), 0 for same:")


@dp.message(A.plan_rprice)
async def plan_rprice_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        rp = float(m.text.strip())
    except Exception:
        return await m.answer("❌ Invalid number.")
    await state.update_data(plan_rprice=rp)
    await state.set_state(A.plan_disc)
    await m.answer("💸 Step 4/5: Discount % (0-100), 0 for none:")


@dp.message(A.plan_disc)
async def plan_disc_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        d = int(m.text.strip())
        if d < 0 or d > 100:
            raise ValueError
    except Exception:
        return await m.answer("❌ Enter 0-100:")
    d_data = await state.get_data()
    pid = d_data.get("plan_panel_id")
    pos_row = db(
        "SELECT COALESCE(MAX(position),0)+1 FROM plans WHERE product_id=?", (pid,), one=True
    )
    pos = pos_row[0] if pos_row else 1
    plid = db(
        """INSERT INTO plans (product_id, name, price, reseller_price, discount, position)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            pid,
            d_data.get("plan_name", ""),
            d_data.get("plan_price", 0),
            d_data.get("plan_rprice", 0),
            d,
            pos,
        ),
    )
    await state.clear()
    await m.answer(
        f"✅ Plan added! ID: <code>{plid}</code>\n\n📝 Add keys via Key Manager.",
        reply_markup=admin_kb(),
    )


@dp.callback_query(F.data == "adm_plan_list")
async def plan_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db(
        """SELECT pl.id, pl.name, pl.price, pl.reseller_price, pl.discount,
                  p.name, c.name
           FROM plans pl
           LEFT JOIN products p ON p.id=pl.product_id
           LEFT JOIN categories c ON c.id=p.category_id
           ORDER BY pl.product_id, pl.id DESC""",
        all=True,
    )
    if not plans:
        return await call.message.edit_text("📭 No plans.", reply_markup=bk("adm_plans"))
    text = "⏱ <b>PLANS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for p in plans:
        keys = db(
            "SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0",
            (p[0],),
            one=True,
        )[0]
        text += (
            f"\n<b>ID {p[0]}</b> — {p[1]}\n"
            f"📂 {p[6] or ''} / {p[5] or ''}\n"
            f"💰 {fmt(p[2])} | 👑 {fmt(p[3])} | 💸 {p[4]}%\n"
            f"🔑 Stock: {keys}\n"
        )
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_plans"))


@dp.callback_query(F.data == "adm_plan_edit_list")
async def plan_edit_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db(
        "SELECT pl.id, pl.name, p.name FROM plans pl LEFT JOIN products p ON p.id=pl.product_id "
        "ORDER BY pl.product_id, pl.position, pl.id",
        all=True,
    )
    if not plans:
        return await call.answer("No plans to edit.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"✏️ {pl[1]} ({pl[2] or 'N/A'})", callback_data=f"adpl_edit_{pl[0]}"
    )] for pl in plans]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_plans")])
    await call.message.edit_text("Select a plan to edit:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("adpl_edit_"))
async def plan_edit_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plid = sint(call.data[10:])
    pl = db(
        "SELECT name, price, reseller_price, discount FROM plans WHERE id=?",
        (plid,),
        one=True,
    )
    if not pl:
        return await call.answer("Plan not found.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Name", callback_data=f"adple_{plid}_name")],
        [InlineKeyboardButton(text="💰 Regular Price", callback_data=f"adple_{plid}_price"),
         InlineKeyboardButton(text="👑 Reseller Price", callback_data=f"adple_{plid}_reseller_price")],
        [InlineKeyboardButton(text="💸 Discount %", callback_data=f"adple_{plid}_discount")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_plan_edit_list")],
    ])
    await call.message.edit_text(
        f"⏱ <b>{pl[0]}</b>\nID: {plid}\nRegular: {fmt(pl[1])}\n"
        f"Reseller: {fmt(pl[2])}\nDiscount: {pl[3]}%\n\nChoose field:",
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith("adple_"))
async def plan_edit_field(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    if len(parts) < 3:
        return await call.answer("Invalid edit action.", show_alert=True)
    plid = sint(parts[1])
    field = "_".join(parts[2:])
    if field not in {"name", "price", "reseller_price", "discount"}:
        return await call.answer("Invalid field.", show_alert=True)
    await state.update_data(edit_plan_id=plid, edit_plan_field=field)
    await state.set_state(A.plan_edit)
    await call.message.edit_text(
        f"Send new plan {field.replace('_', ' ')}:",
        reply_markup=bk("adm_plan_edit_list"),
    )


@dp.message(A.plan_edit)
async def plan_edit_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    data = await state.get_data()
    field = data.get("edit_plan_field")
    column = {
        "name": "name",
        "price": "price",
        "reseller_price": "reseller_price",
        "discount": "discount",
    }.get(field)
    if not column:
        await state.clear()
        return await m.answer("Invalid session.", reply_markup=admin_kb())
    value_text = m.text.strip()
    if field == "name":
        if not value_text:
            return await m.answer("Name cannot be empty.")
        value = value_text[:100]
    elif field in {"price", "reseller_price"}:
        try:
            value = float(value_text)
            if value < 0 or value > 100000000:
                raise ValueError
        except ValueError:
            return await m.answer("Enter valid price 0-100000000:")
    else:
        try:
            value = int(value_text)
            if value < 0 or value > 100:
                raise ValueError
        except ValueError:
            return await m.answer("Discount 0-100:")
    db(f"UPDATE plans SET {column}=? WHERE id=?", (value, data.get("edit_plan_id")))
    await state.clear()
    await m.answer("✅ Plan updated.", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_plan_toggle_list")
async def plan_toggle_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db("SELECT id, name, is_active FROM plans ORDER BY product_id, position", all=True)
    if not plans:
        return await call.answer("No plans found.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"{'🟢' if pl[2] else '🔴'} {pl[1]}", callback_data=f"adplt_{pl[0]}"
    )] for pl in plans]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_plans")])
    await call.message.edit_text("Toggle plan visibility:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("adplt_"))
async def plan_toggle_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plid = sint(call.data[6:])
    row = db("SELECT is_active FROM plans WHERE id=?", (plid,), one=True)
    if not row:
        return await call.answer("Plan not found.", show_alert=True)
    db("UPDATE plans SET is_active=? WHERE id=?", (0 if row[0] else 1, plid))
    await call.answer("✅ Updated.")
    await plan_toggle_list(call)


@dp.callback_query(F.data == "adm_plan_move_list")
async def plan_move_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db(
        "SELECT pl.id, pl.name, p.name FROM plans pl LEFT JOIN products p ON p.id=pl.product_id "
        "ORDER BY pl.product_id, pl.position",
        all=True,
    )
    if not plans:
        return await call.answer("No plans found.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"🔀 {pl[1]} ({pl[2] or 'N/A'})", callback_data=f"adpl_move_{pl[0]}"
    )] for pl in plans]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_plans")])
    await call.message.edit_text("Select a plan to reorder:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("adpl_move_"))
async def plan_move_pick(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plid = sint(call.data[10:])
    pl = db("SELECT name FROM plans WHERE id=?", (plid,), one=True)
    if not pl:
        return await call.answer("Plan not found.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬆️ Move Up", callback_data=f"adplm_{plid}_up"),
         InlineKeyboardButton(text="⬇️ Move Down", callback_data=f"adplm_{plid}_down")],
        [InlineKeyboardButton(text="⬅️ Plan List", callback_data="adm_plan_move_list")],
    ])
    await call.message.edit_text(f"🔀 Reorder plan: {pl[0]}", reply_markup=kb)


@dp.callback_query(F.data.startswith("adplm_"))
async def plan_move_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    if len(parts) != 3:
        return await call.answer("Invalid action.", show_alert=True)
    plid, direction = sint(parts[1]), parts[2]
    pl = db("SELECT product_id FROM plans WHERE id=?", (plid,), one=True)
    if not pl or not move_position("plans", "product_id", pl[0], plid, direction):
        return await call.answer("Already at end or not found.", show_alert=True)
    await call.answer("✅ Updated.")
    await plan_move_list(call)


@dp.callback_query(F.data == "adm_plan_delete_list")
async def plan_delete_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db("SELECT id, name FROM plans ORDER BY product_id, position", all=True)
    if not plans:
        return await call.answer("No plans found.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"🗑️ {pl[1]}", callback_data=f"adpl_delete_{pl[0]}"
    )] for pl in plans]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_plans")])
    await call.message.edit_text("Select a plan to delete:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("adpl_delete_"))
async def plan_delete_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plid = sint(call.data[12:])
    pl = db("SELECT name FROM plans WHERE id=?", (plid,), one=True)
    if not pl:
        return await call.answer("Plan not found.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Yes, Delete", callback_data=f"adpldel_yes_{plid}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_plans")],
    ])
    await call.message.edit_text(
        f"Delete plan <b>{pl[0]}</b> and its keys?", reply_markup=kb
    )


@dp.callback_query(F.data.startswith("adpldel_yes_"))
async def plan_delete_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plid = sint(call.data[12:])
    pl = db("SELECT name FROM plans WHERE id=?", (plid,), one=True)
    if not pl:
        return await call.answer("Plan not found.", show_alert=True)
    usage = db("SELECT COUNT(*) FROM orders WHERE plan_id=?", (plid,), one=True)
    if usage and usage[0] > 0:
        return await call.answer("Cannot delete: historical orders exist.", show_alert=True)
    pending = db(
        "SELECT COUNT(*) FROM balance_requests WHERE status='pending' AND reference LIKE ?",
        (f"%|PLAN:{plid}|%",),
        one=True,
    )
    if pending and pending[0] > 0:
        return await call.answer("Pending payments exist.", show_alert=True)
    db("DELETE FROM product_keys WHERE plan_id=?", (plid,))
    db("DELETE FROM plans WHERE id=?", (plid,))
    db("DELETE FROM stock_ids WHERE plan_id=?", (plid,))
    db("DELETE FROM plan_api_variant WHERE plan_id=?", (plid,))
    await call.answer("🗑️ Deleted.")
    await adm_plans(call)


# ══════════════════════════════════════════════════════════════
#                  KEY MANAGER
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_keys")
async def adm_keys(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Keys", callback_data="adm_keys_add")],
        [InlineKeyboardButton(text="📊 View Stock", callback_data="adm_keys_stock")],
        [InlineKeyboardButton(text="📋 View Keys", callback_data="adm_keys_view")],
        [InlineKeyboardButton(text="🗑️ Delete Key", callback_data="adm_keys_del")],
        [InlineKeyboardButton(text="🧹 Clear Unused", callback_data="adm_keys_clear")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_store")],
    ])
    try:
        await call.message.edit_text("🔑 <b>KEY MANAGER</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("🔑 Key Manager", reply_markup=kb)


@dp.callback_query(F.data == "adm_keys_add")
async def keys_add_start(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db(
        """SELECT pl.id, pl.name, p.name FROM plans pl
           LEFT JOIN products p ON p.id=pl.product_id
           ORDER BY pl.id""",
        all=True,
    )
    if not plans:
        return await call.answer("Add plan first!", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"⏱ {pl[1]} ({pl[2] or 'N/A'})", callback_data=f"keys_add_{pl[0]}"
    )] for pl in plans]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_keys")])
    await call.message.edit_text("Select plan to add keys:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("keys_add_"))
async def keys_add_plan(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    plid = sint(call.data[9:])
    await state.update_data(key_plan_id=plid)
    await state.set_state(A.key_text)
    await call.message.edit_text(
        "📥 <b>Add Keys</b>\n\nSend keys (1 per line).\n"
        "Example:\n<code>KEY-ABC-123\nKEY-DEF-456</code>",
        reply_markup=bk("adm_keys"),
    )


@dp.message(A.key_text)
async def keys_text_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    d = await state.get_data()
    plid = d.get("key_plan_id")
    keys = [k.strip() for k in m.text.split("\n") if k.strip()]
    if not keys:
        return await m.answer("❌ No valid keys found.")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for k in keys:
        c.execute(
            "INSERT INTO product_keys (plan_id, key_text, added_at) VALUES (?, ?, ?)",
            (plid, k, now_str()),
        )
    conn.commit()
    conn.close()
    await state.clear()
    await m.answer(f"✅ <b>{len(keys)} keys added!</b>", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_keys_stock")
async def keys_stock(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db(
        """SELECT pl.id, pl.name, p.name, c.name FROM plans pl
           LEFT JOIN products p ON p.id=pl.product_id
           LEFT JOIN categories c ON c.id=p.category_id
           ORDER BY pl.id""",
        all=True,
    )
    if not plans:
        return await call.message.edit_text("📭 No plans.", reply_markup=bk("adm_keys"))
    text = "📊 <b>KEY STOCK</b>\n━━━━━━━━━━━━━━━━━━\n"
    for pl in plans:
        avail = db(
            "SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0",
            (pl[0],),
            one=True,
        )[0]
        used = db(
            "SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=1",
            (pl[0],),
            one=True,
        )[0]
        emoji = "🟢" if avail > 0 else "🔴"
        text += f"\n{emoji} <b>{pl[1]}</b>\n📂 {pl[3] or ''} / {pl[2] or ''}\n🟢 Free: {avail} | ❌ Used: {used}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_keys"))


@dp.callback_query(F.data == "adm_keys_view")
async def keys_view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db("SELECT id, name FROM plans ORDER BY id", all=True)
    if not plans:
        return await call.answer("No plans!", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"⏱ {pl[1]}", callback_data=f"keys_view_{pl[0]}"
    )] for pl in plans]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_keys")])
    await call.message.edit_text("Select plan to view keys:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("keys_view_"))
async def keys_view_plan(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plid = sint(call.data[10:])
    keys = db(
        """SELECT id, key_text, is_used FROM product_keys
           WHERE plan_id=? ORDER BY id DESC LIMIT 30""",
        (plid,),
        all=True,
    )
    if not keys:
        return await call.message.edit_text("📭 No keys for this plan.", reply_markup=bk("adm_keys"))
    text = f"🔑 <b>KEYS — Plan {plid}</b>\n━━━━━━━━━━━━━━━━━━\n"
    for k in keys:
        st = "✅ Used" if k[2] else "🟢 Free"
        text += f"\n<b>#{k[0]}</b> [{st}]\n<code>{truncate(k[1], 80)}</code>\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_keys"))


@dp.callback_query(F.data == "adm_keys_del")
async def keys_del_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.key_del)
    await call.message.edit_text(
        "🗑️ Send exact key text to delete:", reply_markup=bk("adm_keys")
    )


@dp.message(A.key_del)
async def keys_del_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    key = m.text.strip()
    row = db("SELECT id, is_used FROM product_keys WHERE key_text=?", (key,), one=True)
    if not row:
        return await m.answer("❌ Key not found!")
    if row[1] == 1:
        return await m.answer("⚠️ Key already used. Cannot delete.")
    db("DELETE FROM product_keys WHERE id=?", (row[0],))
    await state.clear()
    await m.answer("🗑️ Key deleted!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_keys_clear")
async def keys_clear(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Yes, Clear All Unused", callback_data="adm_keys_clear_yes")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_keys")],
    ])
    await call.message.edit_text("⚠️ Delete ALL unused keys?", reply_markup=kb)


@dp.callback_query(F.data == "adm_keys_clear_yes")
async def keys_clear_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    db("DELETE FROM product_keys WHERE is_used=0")
    await call.answer("🧹 Cleared!", show_alert=True)
    await adm_keys(call)


# ══════════════════════════════════════════════════════════════
#                  STOCK ID MANAGER (New Feature)
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_stockid")
async def adm_stockid(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    total = db("SELECT COUNT(*) FROM stock_ids WHERE is_used=0", one=True)[0]
    used = db("SELECT COUNT(*) FROM stock_ids WHERE is_used=1", one=True)[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Stock ID", callback_data="adm_sid_add")],
        [InlineKeyboardButton(text="📊 Check ID Stock", callback_data="adm_sid_check")],
        [InlineKeyboardButton(text="📋 View IDs", callback_data="adm_sid_view")],
        [InlineKeyboardButton(text="🗑️ Remove Stock ID", callback_data="adm_sid_remove")],
        [InlineKeyboardButton(text="🧹 Clear All ID Stock", callback_data="adm_sid_clear")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_store")],
    ])
    text = (
        f"🧩 <b>STOCK ID MANAGER</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🟢 Available: <b>{total}</b>\n"
        f"❌ Used: <b>{used}</b>\n\nChoose an option:"
    )
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "adm_sid_add")
async def sid_add(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cats = db("SELECT id, name, emoji FROM categories ORDER BY position", all=True)
    if not cats:
        return await call.answer("Add category first!", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"{c[2]} {c[1]}", callback_data=f"sid_cat_{c[0]}"
    )] for c in cats]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_stockid")])
    await call.message.edit_text("Select category for stock IDs:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("sid_cat_"))
async def sid_cat_pick(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[8:])
    panels = db(
        "SELECT id, name, emoji FROM products WHERE category_id=? ORDER BY position", (cid,), all=True
    )
    if not panels:
        return await call.answer("No panels in this category.", show_alert=True)
    rows = [[InlineKeyboardButton(
        text=f"{p[2]} {p[1]}", callback_data=f"sid_prod_{cid}_{p[0]}"
    )] for p in panels]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_sid_add")])
    await call.message.edit_text("Select product:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("sid_prod_"))
async def sid_prod_pick(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    cid, pid = sint(parts[2]), sint(parts[3])
    await state.update_data(sid_cat=cid, sid_prod=pid)
    await state.set_state(A.stock_text)
    await call.message.edit_text(
        "🆔 Send stock IDs (1 per line):\n\n<code>ID-001\nID-002\nID-003</code>",
        reply_markup=bk("adm_stockid"),
    )


@dp.message(A.stock_text)
async def sid_text_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    d = await state.get_data()
    cid, pid = d.get("sid_cat", 0), d.get("sid_prod", 0)
    ids = [x.strip() for x in m.text.split("\n") if x.strip()]
    if not ids:
        return await m.answer("❌ No valid IDs found.")
    for i in ids:
        db(
            """INSERT INTO stock_ids (category_id, product_id, id_text, added_at)
               VALUES (?, ?, ?, ?)""",
            (cid, pid, i, now_str()),
        )
    await state.clear()
    await m.answer(
        f"✅ <b>{len(ids)} Stock IDs added!</b>", reply_markup=admin_kb()
    )


@dp.callback_query(F.data == "adm_sid_check")
async def sid_check(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cats = db("SELECT id, name FROM categories ORDER BY position", all=True)
    if not cats:
        return await call.answer("No categories!", show_alert=True)
    text = "📊 <b>ID STOCK BY CATEGORY</b>\n━━━━━━━━━━━━━━━━━━\n"
    for c in cats:
        free = db(
            "SELECT COUNT(*) FROM stock_ids WHERE category_id=? AND is_used=0",
            (c[0],),
            one=True,
        )[0]
        used = db(
            "SELECT COUNT(*) FROM stock_ids WHERE category_id=? AND is_used=1",
            (c[0],),
            one=True,
        )[0]
        text += f"\n📂 <b>{c[1]}</b>\n🟢 Free: {free} | ❌ Used: {used}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_stockid"))


@dp.callback_query(F.data == "adm_sid_view")
async def sid_view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    ids = db(
        """SELECT id, category_id, product_id, id_text, is_used
           FROM stock_ids ORDER BY id DESC LIMIT 50""",
        all=True,
    )
    if not ids:
        return await call.message.edit_text("📭 No stock IDs.", reply_markup=bk("adm_stockid"))
    text = "🆔 <b>STOCK IDS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for i in ids:
        st = "✅" if i[4] else "🟢"
        text += f"\n{st} #{i[0]} [cat:{i[1]} prod:{i[2]}]\n<code>{truncate(i[3], 60)}</code>"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_stockid"))


@dp.callback_query(F.data == "adm_sid_remove")
async def sid_remove_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.stock_note)
    await call.message.edit_text(
        "🗑️ Send exact ID text to remove:", reply_markup=bk("adm_stockid")
    )


@dp.message(A.stock_note)
async def sid_remove_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    val = m.text.strip()
    row = db("SELECT id, is_used FROM stock_ids WHERE id_text=?", (val,), one=True)
    if not row:
        return await m.answer("❌ Stock ID not found!")
    if row[1] == 1:
        return await m.answer("⚠️ ID already used. Cannot delete.")
    db("DELETE FROM stock_ids WHERE id=?", (row[0],))
    await state.clear()
    await m.answer("🗑️ Stock ID deleted!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_sid_clear")
async def sid_clear(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Yes, Clear All", callback_data="adm_sid_clear_yes")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_stockid")],
    ])
    await call.message.edit_text(
        "⚠️ Delete ALL unused stock IDs?", reply_markup=kb
    )


@dp.callback_query(F.data == "adm_sid_clear_yes")
async def sid_clear_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    db("DELETE FROM stock_ids WHERE is_used=0")
    await call.answer("🧹 Cleared!", show_alert=True)
    await adm_stockid(call)


# ══════════════════════════════════════════════════════════════
#                  REORDER STORE (Overall)
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_reorder")
async def adm_reorder(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔀 Categories", callback_data="adm_cat_move_list")],
        [InlineKeyboardButton(text="🔀 Panels", callback_data="adm_panel_move_list")],
        [InlineKeyboardButton(text="🔀 Plans", callback_data="adm_plan_move_list")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_store")],
    ])
    await call.message.edit_text("🔀 <b>REORDER STORE</b>\n\nChoose level:", reply_markup=kb)


logger.info("✅ PART 3 loaded — Admin Core + Store Manager + Stock ID ready")
# ══════════════════════════════════════════════════════════════
#                   END OF PART 3 (Continues in Part 4)
# ══════════════════════════════════════════════════════════════>
# ══════════════════════════════════════════════════════════════
#             PART 4 — ADMIN PANEL (Users + Payments + Approval)
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
#                  USER MANAGER
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_users")
async def adm_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Search User", callback_data="adm_u_search")],
        [InlineKeyboardButton(text="📋 Recent Users", callback_data="adm_u_recent")],
        [InlineKeyboardButton(text="💰 Balance Requests", callback_data="adm_u_balreq")],
        [InlineKeyboardButton(text="🧾 Recent Orders", callback_data="adm_u_orders")],
        [InlineKeyboardButton(text="🎫 Open Tickets", callback_data="adm_u_tickets")],
        [InlineKeyboardButton(text="🎯 User Price Override", callback_data="adm_u_price")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("👥 <b>USER MANAGER</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("👥 User Manager", reply_markup=kb)


@dp.callback_query(F.data == "adm_u_search")
async def u_search_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.user_search)
    await call.message.edit_text("🔍 Send user ID or @username:", reply_markup=bk("adm_users"))


@dp.message(A.user_search)
async def u_search_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    t = m.text.strip().lstrip("@")
    u = db(
        """SELECT user_id, first_name, username, balance, is_reseller, is_vip,
                  is_banned, joined_date, last_gift, total_spent, total_orders,
                  refer_by, refer_count
           FROM users WHERE user_id=? OR username=?""",
        (t, t),
        one=True,
    )
    if not u:
        return await m.answer("❌ User not found!", reply_markup=bk("adm_users"))
    await state.clear()
    await send_user_panel(m, u)


async def send_user_panel(msg_target, u):
    """Show user detail panel with admin action buttons."""
    tags = []
    if u[4]:
        tags.append("👑 Reseller")
    if u[5]:
        tags.append("🌟 VIP")
    type_str = " | ".join(tags) if tags else "Regular"
    banned = "🔴 BANNED" if u[6] else "🟢 Active"
    t_emoji = tier_emoji(u)
    tier = tier_of(u)

    text = (
        f"👤 <b>USER DETAILS</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{u[0]}</code>\n"
        f"📛 Name: {u[1] or 'N/A'}\n"
        f"🔗 Username: @{u[2] or 'N/A'}\n"
        f"💰 Balance: <b>{fmt(u[3])}</b>\n"
        f"🔰 Type: {type_str}\n"
        f"{t_emoji} Tier: {tier}\n"
        f"📊 Status: {banned}\n"
        f"📅 Joined: {u[7]}\n"
        f"💵 Total Spent: {fmt(u[9])}\n"
        f"🛍 Orders: {u[10]}\n"
        f"⭐ Referrals: {u[12] or 0}\n"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Add Balance", callback_data=f"u_add_{u[0]}"),
         InlineKeyboardButton(text="💸 Remove Balance", callback_data=f"u_rem_{u[0]}")],
        [InlineKeyboardButton(text="🌟 Toggle VIP", callback_data=f"u_vip_{u[0]}"),
         InlineKeyboardButton(text="👑 Toggle Reseller", callback_data=f"u_res_{u[0]}")],
        [InlineKeyboardButton(text="🚫 Ban/Unban", callback_data=f"u_ban_{u[0]}")],
        [InlineKeyboardButton(text="📦 User Orders", callback_data=f"u_ord_{u[0]}")],
        [InlineKeyboardButton(text="🎯 Set Price Override", callback_data=f"u_price_{u[0]}")],
        [InlineKeyboardButton(text="🗑️ Delete User", callback_data=f"u_del_{u[0]}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_users")],
    ])

    if hasattr(msg_target, "answer"):
        try:
            await msg_target.edit_text(text, reply_markup=kb)
        except Exception:
            await msg_target.answer(text, reply_markup=kb)
    else:
        await msg_target.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "adm_u_recent")
async def u_recent(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    users = db(
        "SELECT user_id, first_name, balance FROM users ORDER BY joined_date DESC LIMIT 50",
        all=True,
    )
    if not users:
        return await call.message.edit_text("📭 No users.", reply_markup=bk("adm_users"))
    text = "📋 <b>RECENT USERS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for u in users:
        text += f"\n<code>{u[0]}</code> — {u[1] or 'N/A'} — {fmt(u[2])}"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))


@dp.callback_query(F.data.startswith("u_add_"))
async def u_add_bal(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    await state.update_data(target_uid=uid, action="add")
    await state.set_state(A.user_addbal)
    await call.message.edit_text(
        f"💰 Send amount to ADD to <code>{uid}</code>:", reply_markup=bk("adm_users")
    )


@dp.message(A.user_addbal)
async def u_add_bal_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        amt = float(m.text.strip())
        if amt <= 0:
            raise ValueError
    except Exception:
        return await m.answer("❌ Invalid amount.")
    d = await state.get_data()
    uid = d.get("target_uid")
    db("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
    log_activity(m.from_user.id, "ADMIN_BAL_ADD", f"user={uid}; amt={amt}")
    await state.clear()
    await m.answer(f"✅ Added {fmt(amt)} to <code>{uid}</code>", reply_markup=admin_kb())
    try:
        await bot.send_message(
            uid,
            f"💰 <b>Balance Added!</b>\n\n+{fmt(amt)} credited by admin.",
            reply_markup=main_menu_kb(uid),
        )
    except Exception:
        pass


@dp.callback_query(F.data.startswith("u_rem_"))
async def u_rem_bal(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    await state.update_data(target_uid=uid, action="rem")
    await state.set_state(A.user_rembal)
    await call.message.edit_text(
        f"💸 Send amount to REMOVE from <code>{uid}</code>:", reply_markup=bk("adm_users")
    )


@dp.message(A.user_rembal)
async def u_rem_bal_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        amt = float(m.text.strip())
        if amt <= 0:
            raise ValueError
    except Exception:
        return await m.answer("❌ Invalid amount.")
    d = await state.get_data()
    uid = d.get("target_uid")
    db("UPDATE users SET balance=MAX(0, balance-?) WHERE user_id=?", (amt, uid))
    log_activity(m.from_user.id, "ADMIN_BAL_REM", f"user={uid}; amt={amt}")
    await state.clear()
    await m.answer(f"✅ Removed {fmt(amt)} from <code>{uid}</code>", reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("u_vip_"))
async def u_vip_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    row = db("SELECT is_vip FROM users WHERE user_id=?", (uid,), one=True)
    if not row:
        return await call.answer("User not found.", show_alert=True)
    db("UPDATE users SET is_vip=? WHERE user_id=?", (0 if row[0] else 1, uid))
    await call.answer("✅ Toggled!")
    log_activity(call.from_user.id, "ADMIN_VIP_TOGGLE", f"user={uid}")


@dp.callback_query(F.data.startswith("u_res_"))
async def u_res_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    row = db("SELECT is_reseller FROM users WHERE user_id=?", (uid,), one=True)
    if not row:
        return await call.answer("User not found.", show_alert=True)
    db("UPDATE users SET is_reseller=? WHERE user_id=?", (0 if row[0] else 1, uid))
    await call.answer("✅ Toggled!")
    log_activity(call.from_user.id, "ADMIN_RESELLER_TOGGLE", f"user={uid}")


@dp.callback_query(F.data.startswith("u_ban_"))
async def u_ban_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    row = db("SELECT is_banned FROM users WHERE user_id=?", (uid,), one=True)
    if not row:
        return await call.answer("User not found.", show_alert=True)
    db("UPDATE users SET is_banned=? WHERE user_id=?", (0 if row[0] else 1, uid))
    await call.answer("✅ Toggled!")
    log_activity(call.from_user.id, "ADMIN_BAN_TOGGLE", f"user={uid}")


@dp.callback_query(F.data.startswith("u_ord_"))
async def u_ord_show(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    o = db(
        """SELECT id, product_name, plan_name, price_paid, delivered_key, purchase_date
           FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20""",
        (uid,),
        all=True,
    )
    if not o:
        return await call.answer("No orders!", show_alert=True)
    text = f"📦 <b>Orders for {uid}</b>\n"
    for r in o:
        text += (
            f"\n<b>#{r[0]}</b> {r[1]} - {r[2]}\n💰 {fmt(r[3])}\n"
            f"🔑 <code>{truncate(r[4], 40)}</code>\n📅 {r[5]}\n"
        )
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))


# ══════════════════════════════════════════════════════════════
#                  USER PRICE OVERRIDE (New — Set Normal/Reseller Price ID)
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("u_price_"))
async def u_price_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[8:])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Set Normal Price", callback_data=f"upn_{uid}")],
        [InlineKeyboardButton(text="🧪 Set Reseller Price", callback_data=f"upr_{uid}")],
        [InlineKeyboardButton(text="🗑️ Clear Overrides", callback_data=f"upc_{uid}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_users")],
    ])
    await call.message.edit_text(
        f"🎯 <b>Price Override for {uid}</b>\n\n"
        f"Custom price per plan overrides global pricing.",
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith("upn_"))
async def u_price_normal_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[4:])
    await state.update_data(po_uid=uid, po_type="normal")
    await state.set_state(A.price_override_value)
    await call.message.edit_text(
        "👤 Send: <code>PLAN_ID PRICE</code>\n\nExample: <code>5 99</code>",
        reply_markup=bk("adm_users"),
    )


@dp.callback_query(F.data.startswith("upr_"))
async def u_price_reseller_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[4:])
    await state.update_data(po_uid=uid, po_type="reseller")
    await state.set_state(A.price_override_value)
    await call.message.edit_text(
        "🧪 Send: <code>PLAN_ID PRICE</code>\n\nExample: <code>5 79</code>",
        reply_markup=bk("adm_users"),
    )


@dp.message(A.price_override_value)
async def u_price_override_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    parts = m.text.strip().split()
    if len(parts) != 2:
        return await m.answer("Format: PLAN_ID PRICE")
    try:
        plid = int(parts[0])
        price = float(parts[1])
    except ValueError:
        return await m.answer("❌ Invalid numbers.")
    plan = db("SELECT id FROM plans WHERE id=?", (plid,), one=True)
    if not plan:
        return await m.answer("❌ Plan not found.")
    d = await state.get_data()
    uid, typ = d.get("po_uid"), d.get("po_type")
    existing = db(
        "SELECT normal_price, reseller_price FROM user_price_overrides WHERE user_id=? AND plan_id=?",
        (uid, plid),
        one=True,
    )
    n = existing[0] if existing else 0
    r = existing[1] if existing else 0
    if typ == "normal":
        n = price
    else:
        r = price
    db(
        "INSERT OR REPLACE INTO user_price_overrides (user_id, plan_id, normal_price, reseller_price, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, plid, n, r, now_str()),
    )
    await state.clear()
    await m.answer(f"✅ Override set for user {uid}, plan {plid}.", reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("upc_"))
async def u_price_clear(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[4:])
    db("DELETE FROM user_price_overrides WHERE user_id=?", (uid,))
    await call.answer("🗑️ Overrides cleared.")
    await adm_users(call)


@dp.callback_query(F.data.regexp(r"^u_del_\d+$"))
async def u_del_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"u_del_yes_{uid}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_users")],
    ])
    await call.message.edit_text(
        f"⚠️ Delete user <code>{uid}</code> and all their data?", reply_markup=kb
    )


@dp.callback_query(F.data.startswith("u_del_yes_"))
async def u_del_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[10:])
    db("DELETE FROM users WHERE user_id=?", (uid,))
    db("DELETE FROM orders WHERE user_id=?", (uid,))
    db("DELETE FROM balance_requests WHERE user_id=?", (uid,))
    db("DELETE FROM user_price_overrides WHERE user_id=?", (uid,))
    await call.answer("🗑️ Deleted.", show_alert=True)
    await adm_users(call)


@dp.callback_query(F.data == "adm_u_balreq")
async def u_balreq(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    reqs = db(
        """SELECT id, user_id, amount, status, method, created_at
           FROM balance_requests ORDER BY id DESC LIMIT 25""",
        all=True,
    )
    if not reqs:
        return await call.message.edit_text("📭 No balance requests.", reply_markup=bk("adm_users"))
    text = "💰 <b>BALANCE REQUESTS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for r in reqs:
        icon = "🟢" if r[3] == "approved" else ("🔴" if r[3] == "rejected" else "🟡")
        text += (
            f"\n{icon} <b>#{r[0]}</b>\n👤 <code>{r[1]}</code>\n"
            f"💵 {fmt(r[2])}\n🔧 {r[4]} | {r[3]}\n📅 {r[5]}\n"
        )
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))


@dp.callback_query(F.data == "adm_u_orders")
async def u_orders(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    o = db(
        """SELECT id, user_id, product_name, plan_name, price_paid, purchase_date
           FROM orders ORDER BY id DESC LIMIT 25""",
        all=True,
    )
    if not o:
        return await call.message.edit_text("📭 No orders.", reply_markup=bk("adm_users"))
    text = "🧾 <b>RECENT ORDERS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for r in o:
        text += (
            f"\n<b>#{r[0]}</b> — {r[2]} - {r[3]}\n"
            f"👤 <code>{r[1]}</code>\n💰 {fmt(r[4])}\n📅 {r[5]}\n"
        )
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))


@dp.callback_query(F.data == "adm_u_tickets")
async def u_tickets(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    ts = db(
        """SELECT id, user_id, message, created_at FROM tickets
           WHERE status='Open' ORDER BY id DESC LIMIT 15""",
        all=True,
    )
    if not ts:
        return await call.message.edit_text("✅ No open tickets.", reply_markup=bk("adm_users"))
    rows = []
    text = "🎫 <b>OPEN TICKETS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for t in ts:
        text += f"\n<b>#{t[0]}</b> 👤 <code>{t[1]}</code>\n📝 {t[2][:200]}\n📅 {t[3]}\n"
        rows.append([
            InlineKeyboardButton(text=f"💬 Reply #{t[0]}", callback_data=f"ticket_reply_{t[0]}"),
            InlineKeyboardButton(text=f"❌ Close #{t[0]}", callback_data=f"ticket_close_{t[0]}"),
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_users")])
    await call.message.edit_text(text[:4000], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data == "adm_u_price")
async def u_price_entry(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.user_id_input)
    await state.update_data(po_entry="price_override")
    await call.message.edit_text(
        "🎯 Send user ID to set price override:", reply_markup=bk("adm_users")
    )


@dp.message(A.user_id_input)
async def u_id_input_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        uid = int(m.text.strip())
    except ValueError:
        return await m.answer("❌ Invalid ID.")
    d = await state.get_data()
    entry = d.get("po_entry")
    await state.clear()
    if entry == "price_override":
        # Reuse the same menu
        fake_call = type("CB", (), {
            "from_user": m.from_user,
            "data": f"u_price_{uid}",
            "message": m,
            "answer": lambda *a, **k: asyncio.sleep(0),
        })()
        await u_price_menu(fake_call)
    else:
        # Direct reseller
        await _direct_reseller_apply(m, uid)


# ══════════════════════════════════════════════════════════════
#                  BALANCE MANAGER (New menu)
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_bal")
async def adm_bal(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Add Bal", callback_data="adm_bal_add")],
        [InlineKeyboardButton(text="🗑️ Remove Bal", callback_data="adm_bal_rem")],
        [InlineKeyboardButton(text="📞 Check Bal", callback_data="adm_bal_check")],
        [InlineKeyboardButton(text="👥 Add Bal To All Users", callback_data="adm_bal_all")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("💰 <b>BALANCE MANAGER</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("💰 Balance Manager", reply_markup=kb)


@dp.callback_query(F.data == "adm_bal_add")
async def bal_add_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.user_addbal)
    await call.message.edit_text(
        "👤 Send: <code>USER_ID AMOUNT</code>\n\nExample: <code>123456 500</code>",
        reply_markup=bk("adm_bal"),
    )


@dp.message(A.user_addbal)
async def bal_add_any(m: Message, state: FSMContext):
    """Handle both flow paths: direct user panel + balance manager."""
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    parts = m.text.strip().split()
    if len(parts) == 2:
        # Balance manager format
        try:
            uid = int(parts[0])
            amt = float(parts[1])
            if amt <= 0:
                raise ValueError
        except ValueError:
            return await m.answer("❌ Invalid input.")
        db("INSERT OR IGN
        # ══════════════════════════════════════════════════════════════
#             PART 5 — DESIGNERS + MANAGERS + SETTINGS
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
#                  MENU DESIGNER
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_menu")
async def adm_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Manage Buttons", callback_data="adm_menu_list")],
        [InlineKeyboardButton(text="➕ Add Button", callback_data="adm_menu_add")],
        [InlineKeyboardButton(text="👤 Profile Fields", callback_data="adm_pf")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("🎨 <b>MENU DESIGNER</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("🎨 Menu Designer", reply_markup=kb)


@dp.callback_query(F.data == "adm_menu_list")
async def menu_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    btns = db(
        "SELECT id, label, emoji, action, is_active FROM menu_buttons ORDER BY position",
        all=True,
    )
    if not btns:
        return await call.message.edit_text("📭 No buttons.", reply_markup=bk("adm_menu"))
    rows = []
    for b in btns:
        st = "🟢" if b[4] else "🔴"
        rows.append([InlineKeyboardButton(text=f"{st} {b[2]} {b[1]}", callback_data=f"mb_{b[0]}")])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_menu")])
    await call.message.edit_text("Select button:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("mb_"))
async def menu_btn_view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    bid = sint(call.data[3:])
    b = db(
        "SELECT label, emoji, action, is_active FROM menu_buttons WHERE id=?",
        (bid,),
        one=True,
    )
    if not b:
        return await call.answer("Not found!", show_alert=True)
    st = "🟢 Active" if b[3] else "🔴 Inactive"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Label", callback_data=f"mbe_{bid}_label"),
         InlineKeyboardButton(text="😀 Emoji", callback_data=f"mbe_{bid}_emoji")],
        [InlineKeyboardButton(text="⚙️ Action", callback_data=f"mbe_{bid}_action")],
        [InlineKeyboardButton(text="👁️ Toggle", callback_data=f"mbt_{bid}")],
        [InlineKeyboardButton(text="🗑️ Delete", callback_data=f"mbd_{bid}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_menu_list")],
    ])
    await call.message.edit_text(
        f"🎨 <b>Button</b>\n\nLabel: {b[0]} {b[1]}\nAction: {b[2]}\nStatus: {st}",
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith("mbe_"))
async def menu_btn_edit(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_", 2)
    bid = sint(parts[1])
    field = parts[2]
    await state.update_data(mbe_id=bid, mbe_field=field)
    await state.set_state(A.menu_edit)
    await call.message.edit_text(f"📝 Send new {field}:", reply_markup=bk("adm_menu_list"))


@dp.message(A.menu_edit)
async def menu_edit_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    d = await state.get_data()
    field = d.get("mbe_field")
    if field not in ("label", "emoji", "action"):
        field = "label"
    db(f"UPDATE menu_buttons SET {field}=? WHERE id=?", (m.text.strip(), d.get("mbe_id")))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("mbt_"))
async def menu_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    bid = sint(call.data[4:])
    row = db("SELECT is_active FROM menu_buttons WHERE id=?", (bid,), one=True)
    if not row:
        return await call.answer("Not found.", show_alert=True)
    db("UPDATE menu_buttons SET is_active=? WHERE id=?", (0 if row[0] else 1, bid))
    await call.answer("✅ Toggled!")
    await menu_list(call)


@dp.callback_query(F.data.startswith("mbd_"))
async def menu_del(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    bid = sint(call.data[4:])
    db("DELETE FROM menu_buttons WHERE id=?", (bid,))
    await call.answer("🗑️ Deleted!")
    await menu_list(call)


@dp.callback_query(F.data == "adm_menu_add")
async def menu_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.menu_add_label)
    await call.message.edit_text("🎨 Step 1/4: Send button label:", reply_markup=bk("adm_menu"))


@dp.message(A.menu_add_label)
async def menu_add_label(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    await state.update_data(menu_label=m.text.strip()[:40])
    await state.set_state(A.menu_add_emoji)
    await m.answer("😀 Step 2/4: Send emoji (or 'none'):")


@dp.message(A.menu_add_emoji)
async def menu_add_emoji(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    e = "" if m.text.lower() == "none" else m.text.strip()[:10]
    await state.update_data(menu_emoji=e)
    await state.set_state(A.menu_add_action)
    await m.answer(
        "⚙️ Step 3/4: Send action:\n"
        "shop / profile / addbalance / support / daily_gift / redeem_coupon / "
        "reseller / vip / howtouse / share"
    )


@dp.message(A.menu_add_action)
async def menu_add_action(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    action = m.text.strip().lower()
    valid = {
        "shop", "profile", "addbalance", "support", "daily_gift",
        "redeem_coupon", "reseller", "vip", "howtouse", "share",
    }
    if action not in valid and not action.startswith("url:"):
        return await m.answer("❌ Invalid action. Try again:")
    await state.update_data(menu_action=action)
    await state.set_state(A.menu_add_row)
    await m.answer("🔢 Step 4/4: Send row group number (0-10):")


@dp.message(A.menu_add_row)
async def menu_add_row(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        rg = int(m.text.strip())
        if rg < 0 or rg > 10:
            raise ValueError
    except ValueError:
        return await m.answer("❌ Enter 0-10.")
    d = await state.get_data()
    pos_row = db("SELECT COALESCE(MAX(position),0)+1 FROM menu_buttons", one=True)
    pos = pos_row[0] if pos_row else 1
    db(
        """INSERT INTO menu_buttons (label, emoji, action, position, is_active, row_group)
           VALUES (?, ?, ?, ?, 1, ?)""",
        (d.get("menu_label"), d.get("menu_emoji", ""), d.get("menu_action"), pos, rg),
    )
    await state.clear()
    await m.answer("✅ Button added!", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                  PROFILE FIELDS
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_pf")
async def adm_pf(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    fields = db("SELECT field_key, label, is_visible FROM profile_fields", all=True)
    rows = []
    for f in fields or []:
        st = "🟢" if f[2] else "🔴"
        rows.append([InlineKeyboardButton(text=f"{st} {f[1]}", callback_data=f"pft_{f[0]}")])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_menu")])
    await call.message.edit_text(
        "👤 <b>PROFILE FIELDS</b>\n\nToggle visibility:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@dp.callback_query(F.data.startswith("pft_"))
async def pf_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    key = call.data[4:]
    row = db("SELECT is_visible FROM profile_fields WHERE field_key=?", (key,), one=True)
    if not row:
        return await call.answer("Not found.", show_alert=True)
    db("UPDATE profile_fields SET is_visible=? WHERE field_key=?", (0 if row[0] else 1, key))
    await call.answer("✅ Toggled!")
    await adm_pf(call)


# ══════════════════════════════════════════════════════════════
#                  MESSAGE EDITOR
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_msg")
async def adm_msg(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Welcome Text", callback_data="am_w")],
        [InlineKeyboardButton(text="📂 Category Msg", callback_data="am_c")],
        [InlineKeyboardButton(text="📦 Panel Msg", callback_data="am_p")],
        [InlineKeyboardButton(text="⏱ Plan Msg", callback_data="am_pl")],
        [InlineKeyboardButton(text="🔑 Key Msg", callback_data="am_k")],
        [InlineKeyboardButton(text="🛒 Shop Header", callback_data="am_shop")],
        [InlineKeyboardButton(text="⭐ Highlights", callback_data="am_hl")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("📝 <b>MESSAGE EDITOR</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("📝 Message Editor", reply_markup=kb)


@dp.callback_query(F.data == "am_w")
async def am_w(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(msg_key="welcome_text")
    await state.set_state(A.msg_welcome)
    await call.message.edit_text(
        "📝 Send new welcome message.\n"
        "Variables: <code>{name}</code>, <code>{balance}</code>",
        reply_markup=bk("adm_msg"),
    )


@dp.message(A.msg_welcome)
async def am_w_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("welcome_text", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "am_c")
async def am_c(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(msg_key="ui_category_msg")
    await state.set_state(A.msg_cat)
    await call.message.edit_text("📝 Send new category page message:", reply_markup=bk("adm_msg"))


@dp.message(A.msg_cat)
async def am_c_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("ui_category_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "am_p")
async def am_p(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(msg_key="ui_product_msg")
    await state.set_state(A.msg_prod)
    await call.message.edit_text("📝 Send new panel page message:", reply_markup=bk("adm_msg"))


@dp.message(A.msg_prod)
async def am_p_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("ui_product_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "am_pl")
async def am_pl(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(msg_key="ui_plan_msg")
    await state.set_state(A.msg_plan)
    await call.message.edit_text("📝 Send new plan page message:", reply_markup=bk("adm_msg"))


@dp.message(A.msg_plan)
async def am_pl_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("ui_plan_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "am_k")
async def am_k(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(msg_key="ui_key_msg")
    await state.set_state(A.msg_key)
    await call.message.edit_text("📝 Send new key delivery message:", reply_markup=bk("adm_msg"))


@dp.message(A.msg_key)
async def am_k_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("ui_key_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "am_shop")
async def am_shop(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(msg_key="ui_shop_header")
    await state.set_state(A.msg_cat)
    await call.message.edit_text("📝 Send new shop header:", reply_markup=bk("adm_msg"))


@dp.callback_query(F.data == "am_hl")
async def am_hl(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(msg_key="ui_highlights")
    await state.set_state(A.msg_prod)
    await call.message.edit_text(
        "⭐ Send new highlights (one per line):", reply_markup=bk("adm_msg")
    )


# ══════════════════════════════════════════════════════════════
#                  LINK MANAGER
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_links")
async def adm_links(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🍎 Download: {truncate(gs('link_download') or '❌', 20)}", callback_data="adm_lk_dl")],
        [InlineKeyboardButton(text=f"📹 How-To-Use: {truncate(gs('link_howtouse') or '❌', 20)}", callback_data="adm_lk_htu")],
        [InlineKeyboardButton(text=f"📤 Payment Proof: {truncate(gs('link_payment_proof') or '❌', 20)}", callback_data="adm_lk_pp")],
        [InlineKeyboardButton(text=f"🟡 Support: {truncate(gs('link_support') or '❌', 20)}", callback_data="adm_lk_sup")],
        [InlineKeyboardButton(text=f"🔗 Share: {truncate(gs('link_share') or '❌', 20)}", callback_data="adm_lk_sh")],
        [InlineKeyboardButton(text="✈️ Telegram Support", callback_data="adm_set_tg")],
        [InlineKeyboardButton(text="📱 WhatsApp Support", callback_data="adm_set_wa")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("🔗 <b>LINK MANAGER</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("🔗 Link Manager", reply_markup=kb)


@dp.callback_query(F.data == "adm_lk_dl")
async def lk_dl(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(link_key="link_download")
    await state.set_state(A.set_link_download)
    await call.message.edit_text("🍎 Send Download Link URL:", reply_markup=bk("adm_links"))


@dp.message(A.set_link_download)
async def lk_dl_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    val = m.text.strip()
    if val.lower() == "none":
        val = ""
    ss("link_download", val)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_lk_htu")
async def lk_htu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(link_key="link_howtouse")
    await state.set_state(A.set_link_howtouse)
    await call.message.edit_text("📹 Send How-To-Use Link:", reply_markup=bk("adm_links"))


@dp.message(A.set_link_howtouse)
async def lk_htu_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    val = m.text.strip()
    if val.lower() == "none":
        val = ""
    ss("link_howtouse", val)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_lk_pp")
async def lk_pp(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(link_key="link_payment_proof")
    await state.set_state(A.set_link_proof)
    await call.message.edit_text("📤 Send Payment Proof Link:", reply_markup=bk("adm_links"))


@dp.message(A.set_link_proof)
async def lk_pp_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    val = m.text.strip()
    if val.lower() == "none":
        val = ""
    ss("link_payment_proof", val)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_lk_sup")
async def lk_sup(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(link_key="link_support")
    await state.set_state(A.set_link_support)
    await call.message.edit_text("🟡 Send Support Link:", reply_markup=bk("adm_links"))


@dp.message(A.set_link_support)
async def lk_sup_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    val = m.text.strip()
    if val.lower() == "none":
        val = ""
    ss("link_support", val)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_lk_sh")
async def lk_sh(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(link_key="link_share")
    await state.set_state(A.set_link_share)
    await call.message.edit_text("🔗 Send Share Link (optional):", reply_markup=bk("adm_links"))


@dp.message(A.set_link_share)
async def lk_sh_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    val = m.text.strip()
    if val.lower() == "none":
        val = ""
    ss("link_share", val)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_set_tg")
async def set_tg_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_tg)
    cur = gs("support_telegram") or "Not set"
    await call.message.edit_text(
        f"✈️ Current: {cur}\n\nSend Telegram support URL:",
        reply_markup=bk("adm_links"),
    )


@dp.message(A.set_tg)
async def set_tg_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("support_telegram", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_set_wa")
async def set_wa_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_wa)
    cur = gs("support_whatsapp") or "Not set"
    await call.message.edit_text(
        f"📱 Current: 
        # ══════════════════════════════════════════════════════════════
#             PART 6 — WEB SERVER + ERROR HANDLER + MAIN
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
#                  WEB SERVER (Health Check)
# ══════════════════════════════════════════════════════════════

async def web_handle(request):
    """Root + health endpoint."""
    return web.Response(
        text="✅ ELITE X CONFIG Bot is running!",
        content_type="text/plain",
    )


async def web_status(request):
    """JSON status endpoint for monitoring."""
    try:
        users = db("SELECT COUNT(*) FROM users", one=True)[0]
        orders = db("SELECT COUNT(*) FROM orders", one=True)[0]
        pending = db("SELECT COUNT(*) FROM balance_requests WHERE status='pending'", one=True)[0]
        return web.json_response({
            "status": "ok",
            "bot": BRAND_NAME,
            "users": users,
            "orders": orders,
            "pending_requests": pending,
            "time": now_str(),
        })
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def start_web():
    """Start aiohttp web server (used by Render/Railway for health checks)."""
    app = web.Application()
    app.router.add_get("/", web_handle)
    app.router.add_get("/health", web_handle)
    app.router.add_get("/status", web_status)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    logger.info(f"✅ Web server running on port {WEB_PORT}")


# ══════════════════════════════════════════════════════════════
#                  GLOBAL ERROR HANDLER
# ══════════════════════════════════════════════════════════════

@dp.errors()
async def error_handler(event):
    """Log unhandled update errors + safe retry message."""
    exc = event.exception
    update = getattr(event, "update", None)
    logger.error(
        "Unhandled update error (update_id=%s): %r",
        getattr(update, "update_id", "unknown"),
        exc,
        exc_info=(type(exc), exc, getattr(exc, "__traceback__", None)),
    )

    # Notify user politely
    try:
        if update and getattr(update, "callback_query", None):
            try:
                await update.callback_query.answer(
                    "⚠️ This action failed. Please try again.", show_alert=True
                )
            except Exception:
                pass
        elif update and getattr(update, "message", None):
            try:
                await update.message.answer(
                    "⚠️ Something went wrong while processing your request. Please try again."
                )
            except Exception:
                pass
    except Exception:
        logger.debug("Could not send error notification", exc_info=True)

    # Try to alert admin on critical errors
    try:
        if isinstance(exc, (sqlite3.Error, asyncio.TimeoutError)):
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ <b>BOT ERROR</b>\n\n"
                f"<code>{type(exc).__name__}: {str(exc)[:300]}</code>",
            )
    except Exception:
        pass
    return True


# ══════════════════════════════════════════════════════════════
#                  STARTUP HOOKS
# ══════════════════════════════════════════════════════════════

async def on_startup(bot: Bot):
    """Called when bot starts."""
    logger.info("🚀 Bot starting...")

    # Set bot commands
    try:
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="start", description="🏠 Main Menu"),
            BotCommand(command="profile", description="👤 My Profile"),
            BotCommand(command="balance", description="💰 Wallet Balance"),
            BotCommand(command="orders", description="🧾 My Orders"),
            BotCommand(command="mykey", description="🔑 My Keys"),
            BotCommand(command="support", description="🎧 Support"),
            BotCommand(command="help", description="📖 Help"),
            BotCommand(command="cancel", description="❌ Cancel Action"),
        ])
        logger.info("✅ Bot commands registered")
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")

    # Notify owner
    try:
        await bot.send_message(
            ADMIN_ID,
            f"✅ <b>{BRAND_NAME} Bot started!</b>\n\n"
            f"🕐 {now_str()}\n"
            f"🌐 Port: {WEB_PORT}\n"
            f"💾 DB: <code>{DB_PATH}</code>",
        )
    except Exception:
        pass


async def on_shutdown(bot: Bot):
    """Called when bot stops."""
    logger.info("🛑 Bot shutting down...")
    try:
        await bot.send_message(ADMIN_ID, "🛑 Bot shutting down...")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#                  PERIODIC TASKS
# ══════════════════════════════════════════════════════════════

async def cleanup_expired_transactions():
    """Delete old pending transactions older than 1 hour."""
    while True:
        try:
            cutoff = int(time.time()) - 3600
            db(
                "DELETE FROM transactions WHERE status='pending' AND expires_at < ?",
                (cutoff,),
            )
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")
        await asyncio.sleep(600)  # every 10 minutes


async def periodic_reminder():
    """Notify admin about pending balance requests."""
    last_count = 0
    while True:
        try:
            await asyncio.sleep(1800)  # every 30 minutes
            pending = db(
                "SELECT COUNT(*) FROM balance_requests WHERE status='pending'",
                one=True,
            )[0]
            if pending > 0 and pending != last_count:
                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"📋 <b>PENDING PAYMENTS</b>\n\n"
                        f"There are <b>{pending}</b> pending balance/order requests.\n"
                        f"Open Admin Panel to review.",
                    )
                    last_count = pending
                except Exception:
                    pass
            elif pending == 0:
                last_count = 0
        except Exception as e:
            logger.error(f"Reminder task error: {e}")
            await asyncio.sleep(60)


# ══════════════════════════════════════════════════════════════
#                  MAIN FUNCTION
# ══════════════════════════════════════════════════════════════

async def main():
    # 1. Init database
    init_db()
    logger.info("✅ Database initialized")

    # 2. Start health web server
    await start_web()

    # 3. Register startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # 4. Start background tasks
    asyncio.create_task(cleanup_expired_transactions())
    asyncio.create_task(periodic_reminder())

    logger.info(f"🚀 Starting {BRAND_NAME} bot polling...")

    # 5. Start polling
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
    except Exception as e:
        logger.error(f"❌ Polling error: {e}")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Bot stopped by user.")
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)