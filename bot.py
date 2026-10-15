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
import html
import uuid
import aiohttp
from aiohttp import web
from datetime import datetime, timedelta
from urllib.parse import quote, unquote_plus
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
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", os.getenv("RENDER_EXTERNAL_URL", "")).strip().rstrip("/")

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
    """Saari tables create/migrate karein aur persisted owner restore karein."""
    global ADMIN_ID, STATIC_ADMIN_IDS
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

    # Coupon selections are per-user, so one user cannot overwrite another user's code.
    c.execute("""CREATE TABLE IF NOT EXISTS user_coupon_selections (
        user_id INTEGER PRIMARY KEY,
        coupon_code TEXT NOT NULL,
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
        method TEXT DEFAULT 'upi',
        coupon_code TEXT DEFAULT ''
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
    if "coupon_code" not in cols:
        c.execute("ALTER TABLE transactions ADD COLUMN coupon_code TEXT DEFAULT ''")

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
        # Owner identity survives service restarts. Existing values are not overwritten.
        "owner_id": str(ADMIN_ID),

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
        # INR value of one USDT; must be configured by the owner before Binance can be offered.
        "binance_inr_per_usdt": "0",
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

    # Restore owner saved by the ownership-transfer feature after a restart.
    owner_row = c.execute("SELECT value FROM settings WHERE key='owner_id'").fetchone()
    if owner_row and str(owner_row[0] or "").strip().isdigit():
        persisted_owner = int(str(owner_row[0]).strip())
        if persisted_owner > 0:
            ADMIN_ID = persisted_owner
            STATIC_ADMIN_IDS = set(_CONFIGURED_ADMIN_IDS) | {ADMIN_ID}

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
    zap_utr = State()


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
    set_binance_rate = State()

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
            f"🎁 <b>Daily Gift Claimed!</b>\n\n"
            f"💰 You received: <b>{fmt(gift)}</b>\n\nCome back tomorrow for more!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")]
            ]),
        )
    except Exception:
        pass
# ══════════════════════════════════════════════════════════════
#               USER STORE / WALLET / PAYMENT FLOWS
# ══════════════════════════════════════════════════════════════

def _safe_html(value: Any) -> str:
    """Escape dynamic content before inserting it into HTML-mode Telegram messages."""
    return html.escape(str(value or ""), quote=False)


async def _edit_or_send(call: CallbackQuery, text: str, reply_markup=None):
    """Edit a text/caption message when possible; otherwise send a new message."""
    message = getattr(call, "message", None)
    if message is not None:
        try:
            await message.edit_text(text, reply_markup=reply_markup)
            return
        except Exception:
            try:
                if getattr(message, "caption", None) is not None:
                    await message.edit_caption(caption=text, reply_markup=reply_markup)
                    return
            except Exception:
                pass
    await bot.send_message(call.from_user.id, text, reply_markup=reply_markup)


def _conn_setting(conn, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return str(row[0]) if row and row[0] not in (None, "") else default


def _coupon_discount_conn(conn, code: str) -> Optional[float]:
    if not code:
        return None
    row = conn.execute(
        "SELECT discount, max_uses, used FROM coupons WHERE code=? COLLATE NOCASE",
        (code.strip().upper(),),
    ).fetchone()
    if not row:
        return None
    discount, max_uses, used = float(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
    reserved = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE coupon_code=? AND status='pending'",
        (code.strip().upper(),),
    ).fetchone()[0]
    if discount <= 0 or discount > 100 or used + reserved >= max_uses:
        return None
    return discount


def _effective_plan_price_conn(conn, uid: int, plan_id: int):
    """Return current plan/product/category details and effective per-user price."""
    row = conn.execute(
        """SELECT pl.id, pl.name, pl.price, pl.reseller_price, pl.discount, pl.is_active,
                  p.id, p.name, p.emoji, p.description, p.badge_text, p.is_active, p.is_maintenance,
                  c.id, c.name, c.emoji, c.description, c.is_active, c.is_maintenance
           FROM plans pl
           JOIN products p ON p.id=pl.product_id
           JOIN categories c ON c.id=p.category_id
           WHERE pl.id=?""",
        (plan_id,),
    ).fetchone()
    if not row or not row[5] or not row[11] or row[12] or not row[17] or row[18]:
        return None

    user = conn.execute(
        "SELECT balance, is_reseller, is_vip FROM users WHERE user_id=?", (uid,)
    ).fetchone()
    if not user:
        return None
    _, is_reseller, is_vip = user
    override = conn.execute(
        "SELECT normal_price, reseller_price FROM user_price_overrides WHERE user_id=? AND plan_id=?",
        (uid, plan_id),
    ).fetchone()

    if is_reseller:
        candidate = override[1] if override and float(override[1] or 0) > 0 else row[3]
        base_price = float(candidate if candidate is not None and float(candidate) > 0 else row[2] or 0)
        global_discount = sfloat(_conn_setting(conn, "reseller_global_discount", "0"))
    else:
        candidate = override[0] if override and float(override[0] or 0) > 0 else row[2]
        base_price = float(candidate or 0)
        global_discount = sfloat(_conn_setting(conn, "normal_global_discount", "0"))

    plan_discount = max(0.0, min(100.0, float(row[4] or 0)))
    global_discount = max(0.0, min(100.0, global_discount))
    vip_discount = max(0.0, min(100.0, VIP_DISCOUNT if is_vip else 0.0))
    price = base_price * (1 - plan_discount / 100) * (1 - global_discount / 100)
    price *= 1 - vip_discount / 100
    price = round(max(0.0, price), 2)

    return {
        "plan_id": row[0], "plan_name": row[1], "base_price": round(base_price, 2),
        "price": price, "discount": plan_discount, "reseller": bool(is_reseller),
        "vip": bool(is_vip), "product_id": row[6], "product_name": row[7],
        "product_emoji": row[8] or "📦", "product_description": row[9] or "",
        "badge_text": row[10] or "", "category_id": row[13],
        "category_name": row[14], "category_emoji": row[15] or "📂",
        "category_description": row[16] or "",
    }


def _effective_plan_price(uid: int, plan_id: int):
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        return _effective_plan_price_conn(conn, uid, plan_id)
    finally:
        conn.close()


def _user_coupon(uid: int) -> Optional[str]:
    row = db("SELECT coupon_code FROM user_coupon_selections WHERE user_id=?", (uid,), one=True)
    if not row or not row[0]:
        return None
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        if _coupon_discount_conn(conn, row[0]) is None:
            return None
        return str(row[0]).upper()
    finally:
        conn.close()


def _coupon_adjusted_price(uid: int, plan_id: int):
    plan = _effective_plan_price(uid, plan_id)
    if not plan:
        return None
    code = _user_coupon(uid)
    discount = None
    if code:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            discount = _coupon_discount_conn(conn, code)
        finally:
            conn.close()
    plan["coupon_code"] = code if discount is not None else None
    plan["coupon_discount"] = discount or 0
    plan["final_price"] = round(plan["price"] * (1 - (discount or 0) / 100), 2)
    return plan


async def show_categories(call: CallbackQuery):
    """Open the public category list (the missing entry point for Shop/Store)."""
    cats = db(
        "SELECT id, name, emoji, description FROM categories "
        "WHERE is_active=1 AND is_maintenance=0 ORDER BY position, id",
        all=True,
    )
    if not cats:
        return await call.answer("🛍️ The store is empty or under maintenance.", show_alert=True)
    rows = []
    for cid, name, emoji, _desc in cats:
        rows.append([InlineKeyboardButton(
            text=f"{emoji or '📂'} {str(name)[:45]}", callback_data=f"shopcat_{cid}"
        )])
    rows.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")])
    msg = gs("ui_category_msg", "🛒 <b>PRODUCT STORE — SHOP</b> 🛒\n\n🔥 Choose a product:")
    await call.answer()
    await _edit_or_send(call, msg, InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("shopcat_"))
async def shop_category(call: CallbackQuery):
    cid = sint(call.data[8:])
    category = db(
        "SELECT id, name, emoji, description, is_active, is_maintenance FROM categories WHERE id=?",
        (cid,), one=True,
    )
    if not category or not category[4] or category[5]:
        return await call.answer("This category is unavailable.", show_alert=True)
    products = db(
        "SELECT id, name, emoji, description, badge_text, is_maintenance FROM products "
        "WHERE category_id=? AND is_active=1 ORDER BY position, id",
        (cid,), all=True,
    )
    products = [p for p in (products or []) if not p[5]]
    rows = [[InlineKeyboardButton(
        text=f"{p[2] or '📦'} {str(p[1])[:38]}{(' · ' + str(p[4])[:15]) if p[4] else ''}",
        callback_data=f"shopprod_{p[0]}",
    )] for p in products]
    rows.append([InlineKeyboardButton(text="⬅️ Categories", callback_data="act_shop")])
    rows.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")])
    description = f"\n\n{_safe_html(category[3])}" if category[3] else ""
    text = f"{category[2] or '📂'} <b>{_safe_html(category[1])}</b>{description}\n\nChoose a product:"
    if not products:
        text = f"{category[2] or '📂'} <b>{_safe_html(category[1])}</b>\n\nNo available products in this category."
    await call.answer()
    await _edit_or_send(call, text, InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("shopprod_"))
async def shop_product(call: CallbackQuery):
    pid = sint(call.data[9:])
    product = db(
        "SELECT p.id, p.name, p.emoji, p.description, p.badge_text, p.is_active, "
        "p.is_maintenance, c.id, c.is_active, c.is_maintenance "
        "FROM products p JOIN categories c ON c.id=p.category_id WHERE p.id=?",
        (pid,), one=True,
    )
    if not product or not product[5] or product[6] or not product[8] or product[9]:
        return await call.answer("This product is unavailable.", show_alert=True)
    plans = db(
        "SELECT id, name, price, reseller_price, discount FROM plans "
        "WHERE product_id=? AND is_active=1 ORDER BY position, id",
        (pid,), all=True,
    )
    rows = []
    for plid, pname, regular, reseller, discount in plans or []:
        info = _effective_plan_price(call.from_user.id, plid)
        if not info:
            continue
        stock = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (plid,), one=True)
        qty = stock[0] if stock else 0
        price_info = _coupon_adjusted_price(call.from_user.id, plid)
        final_price = price_info["final_price"] if price_info else info["price"]
        rows.append([InlineKeyboardButton(
            text=f"⏱ {str(pname)[:28]} · {fmt(final_price)} · Stock {qty}",
            callback_data=f"shopplan_{plid}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Products", callback_data=f"shopcat_{product[7]}")])
    rows.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")])
    text = f"{product[2] or '📦'} <b>{_safe_html(product[1])}</b>"
    if product[4]:
        text += f"\n🏷️ {_safe_html(product[4])}"
    if product[3]:
        text += f"\n\n{_safe_html(product[3])}"
    text += "\n\nChoose an access plan:"
    await call.answer()
    await _edit_or_send(call, text, InlineKeyboardMarkup(inline_keyboard=rows))


async def _show_plan_detail(target, plan_id: int, uid: int):
    info = _coupon_adjusted_price(uid, plan_id)
    if not info:
        if isinstance(target, CallbackQuery):
            return await target.answer("Plan is unavailable or under maintenance.", show_alert=True)
        return await target.answer("Plan is unavailable or under maintenance.")
    stock = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (plan_id,), one=True)
    qty = stock[0] if stock else 0
    text = (
        f"⏱ <b>{_safe_html(info['plan_name'])}</b>\n"
        f"📦 {_safe_html(info['product_name'])}\n"
        f"📂 {_safe_html(info['category_name'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Price: <b>{fmt(info['price'])}</b>\n"
    )
    if info["coupon_code"]:
        text += f"🎟️ Coupon <code>{_safe_html(info['coupon_code'])}</code>: -{info['coupon_discount']:g}%\n"
    text += f"✅ Payable: <b>{fmt(info['final_price'])}</b>\n🔑 Available stock: <b>{qty}</b>"
    if info["badge_text"]:
        text += f"\n🏷️ {_safe_html(info['badge_text'])}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Checkout", callback_data=f"buyplan_{plan_id}")],
        [InlineKeyboardButton(text="🎟️ Apply Coupon", callback_data=f"couponplan_{plan_id}")],
        [InlineKeyboardButton(text="⬅️ Back to Product", callback_data=f"shopprod_{info['product_id']}")],
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
    ])
    if isinstance(target, CallbackQuery):
        await target.answer()
        await _edit_or_send(target, text, kb)
    else:
        await target.answer(text, reply_markup=kb)


@dp.callback_query(F.data.startswith("shopplan_"))
async def shop_plan(call: CallbackQuery):
    await _show_plan_detail(call, sint(call.data[9:]), call.from_user.id)


@dp.callback_query(F.data.startswith("buyplan_"))
async def checkout_plan(call: CallbackQuery):
    plan_id = sint(call.data[8:])
    info = _coupon_adjusted_price(call.from_user.id, plan_id)
    if not info:
        return await call.answer("Plan unavailable.", show_alert=True)
    stock = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (plan_id,), one=True)
    if not stock or stock[0] < 1:
        return await call.answer("Out of stock. Please contact support or try later.", show_alert=True)
    user = get_user(call.from_user.id)
    balance = float(user[3] or 0) if user else 0
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 Pay from Wallet ({fmt(balance)})", callback_data=f"walletbuy_{plan_id}")],
        [InlineKeyboardButton(text="💳 Pay by UPI / Binance", callback_data=f"externalbuy_{plan_id}")],
        [InlineKeyboardButton(text="🎟️ Apply Coupon", callback_data=f"couponplan_{plan_id}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data=f"shopplan_{plan_id}")],
    ])
    await call.answer()
    await _edit_or_send(
        call,
        f"🧾 <b>CHECKOUT</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"📦 {_safe_html(info['product_name'])}\n⏱ {_safe_html(info['plan_name'])}\n"
        f"💰 Payable: <b>{fmt(info['final_price'])}</b>\n"
        f"👛 Wallet balance: <b>{fmt(balance)}</b>\n\nChoose payment method:",
        kb,
    )


def _purchase_from_wallet(uid: int, plan_id: int) -> dict:
    """Atomically check balance/stock, debit wallet, consume a key, and record the order."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute("BEGIN IMMEDIATE")
        info = _effective_plan_price_conn(conn, uid, plan_id)
        if not info:
            conn.rollback()
            return {"status": "unavailable"}
        user = conn.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
        if not user:
            conn.rollback()
            return {"status": "user_missing"}

        selected = conn.execute(
            "SELECT coupon_code FROM user_coupon_selections WHERE user_id=?", (uid,)
        ).fetchone()
        code = selected[0].upper() if selected and selected[0] else ""
        coupon_discount = _coupon_discount_conn(conn, code) if code else None
        if not coupon_discount:
            code = ""
        amount = round(info["price"] * (1 - (coupon_discount or 0) / 100), 2)
        if float(user[0] or 0) + 0.000001 < amount:
            conn.rollback()
            return {"status": "insufficient", "price": amount, "balance": float(user[0] or 0)}

        key = conn.execute(
            "SELECT id, key_text FROM product_keys WHERE plan_id=? AND is_used=0 ORDER BY id LIMIT 1",
            (plan_id,),
        ).fetchone()
        if not key:
            conn.rollback()
            return {"status": "no_stock", "price": amount}
        cur = conn.execute(
            "UPDATE product_keys SET is_used=1, used_by=?, used_at=? WHERE id=? AND is_used=0",
            (uid, now_str(), key[0]),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return {"status": "retry"}
        cur = conn.execute(
            "UPDATE users SET balance=balance-?, total_spent=total_spent+?, total_orders=total_orders+1 "
            "WHERE user_id=? AND balance>=?",
            (amount, amount, uid, amount),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return {"status": "insufficient", "price": amount}
        conn.execute(
            "INSERT INTO orders (user_id, plan_id, plan_name, product_name, category_name, price_paid, delivered_key, purchase_date, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'delivered')",
            (uid, plan_id, info["plan_name"], info["product_name"], info["category_name"], amount, key[1], now_str()),
        )
        if code and coupon_discount:
            conn.execute("UPDATE coupons SET used=used+1 WHERE code=? COLLATE NOCASE", (code,))
        conn.execute("DELETE FROM user_coupon_selections WHERE user_id=?", (uid,))
        conn.commit()
        return {
            "status": "success", "user_id": uid, "amount": amount,
            "plan_name": info["plan_name"], "product_name": info["product_name"],
            "key": key[1], "code": code,
        }
    except Exception:
        conn.rollback()
        logger.exception("Wallet purchase failed for user %s and plan %s", uid, plan_id)
        return {"status": "error"}
    finally:
        conn.close()


@dp.callback_query(F.data.startswith("walletbuy_"))
async def wallet_buy(call: CallbackQuery):
    plan_id = sint(call.data[10:])
    result = _purchase_from_wallet(call.from_user.id, plan_id)
    if result["status"] == "success":
        await call.answer("✅ Purchase successful!", show_alert=True)
        text = (
            f"🎉 <b>ORDER DELIVERED!</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"📦 {_safe_html(result['product_name'])}\n⏱ {_safe_html(result['plan_name'])}\n"
            f"💰 {fmt(result['amount'])}\n🔑 <b>YOUR KEY:</b>\n<code>{_safe_html(result['key'])}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n{gs('ui_key_msg')}"
        )
        try:
            await call.message.edit_text(text, reply_markup=main_menu_kb(call.from_user.id))
        except Exception:
            await bot.send_message(call.from_user.id, text, reply_markup=main_menu_kb(call.from_user.id))
        log_activity(call.from_user.id, "WALLET_ORDER_DELIVERED", f"plan={plan_id}; amount={result['amount']}")
    elif result["status"] == "insufficient":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Add Balance", callback_data="act_addbalance")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=f"shopplan_{plan_id}")],
        ])
        await call.answer("Insufficient wallet balance.", show_alert=True)
        await _edit_or_send(call, f"❌ Insufficient balance.\nPayable: {fmt(result['price'])}\nWallet: {fmt(result.get('balance', 0))}", kb)
    else:
        messages = {
            "unavailable": "This plan is unavailable.", "user_missing": "Send /start first.",
            "no_stock": "Out of stock. Please contact support.", "retry": "Stock changed; please try again.",
            "error": "Purchase failed. Please contact support.",
        }
        await call.answer(messages.get(result["status"], "Purchase failed."), show_alert=True)


def _create_order_transaction(uid: int, plan_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        info = _effective_plan_price_conn(conn, uid, plan_id)
        if not info:
            conn.rollback()
            return {"status": "unavailable"}
        key_count = conn.execute(
            "SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (plan_id,)
        ).fetchone()[0]
        if key_count < 1:
            conn.rollback()
            return {"status": "no_stock"}
        selected = conn.execute(
            "SELECT coupon_code FROM user_coupon_selections WHERE user_id=?", (uid,)
        ).fetchone()
        code = selected[0].upper() if selected and selected[0] else ""
        discount = _coupon_discount_conn(conn, code) if code else None
        if not discount:
            code = ""
        amount = round(info["price"] * (1 - (discount or 0) / 100), 2)
        if amount <= 0:
            conn.rollback()
            return {"status": "free_plan_use_wallet"}
        oid = "ELX" + uuid.uuid4().hex[:16].upper()
        now = int(time.time())
        conn.execute(
            "INSERT INTO transactions (order_id,user_id,amount,status,created_at,expires_at,purpose,plan_id,method,coupon_code) "
            "VALUES (?,?,?,'pending',?,?, 'order', ?, 'pending', ?)",
            (oid, uid, amount, now, now + 3600, plan_id, code),
        )
        conn.execute("DELETE FROM user_coupon_selections WHERE user_id=?", (uid,))
        conn.commit()
        return {"status": "success", "oid": oid, "amount": amount, "plan": info, "coupon_code": code}
    except Exception:
        conn.rollback()
        logger.exception("Could not create order transaction for uid=%s plan=%s", uid, plan_id)
        return {"status": "error"}
    finally:
        conn.close()


def _create_balance_transaction(uid: int, amount: float) -> dict:
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        return {"status": "invalid_amount"}
    minimum = sfloat(gs("min_add_amount", "1"), 1)
    maximum = sfloat(gs("max_add_amount", "99999"), 99999)
    if amount < minimum or amount > maximum:
        return {"status": "amount_range", "minimum": minimum, "maximum": maximum}
    oid = "ELX" + uuid.uuid4().hex[:16].upper()
    now = int(time.time())
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO transactions (order_id,user_id,amount,status,created_at,expires_at,purpose,method) "
            "VALUES (?,?,?,'pending',?,?, 'balance','pending')",
            (oid, uid, amount, now, now + 3600),
        )
        conn.commit()
        return {"status": "success", "oid": oid, "amount": amount}
    except Exception:
        conn.rollback()
        logger.exception("Could not create balance transaction for uid=%s", uid)
        return {"status": "error"}
    finally:
        conn.close()


async def show_add_balance(call: CallbackQuery):
    user = get_user(call.from_user.id)
    balance = float(user[3] or 0) if user else 0
    quick_raw = gs("quick_amounts", "100,500,1000,2000")
    quick = []
    for raw in quick_raw.split(","):
        try:
            amount = float(raw.strip())
            if amount > 0 and amount not in quick:
                quick.append(amount)
        except ValueError:
            continue
    rows = []
    row = []
    for amount in quick[:8]:
        label = str(int(amount)) if amount.is_integer() else str(amount)
        row.append(InlineKeyboardButton(text=f"➕ ₹{label}", callback_data=f"topup_{label}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✍️ Custom Amount", callback_data="topup_custom")])
    rows.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")])
    text = f"💰 <b>ADD BALANCE</b>\n━━━━━━━━━━━━━━━━━━\nWallet: <b>{fmt(balance)}</b>\n\nChoose an amount to continue."
    await call.answer()
    await _edit_or_send(call, text, InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("topup_"))
async def topup_amount_pick(call: CallbackQuery, state: FSMContext):
    raw = call.data[6:]
    if raw == "custom":
        await state.clear()
        await state.set_state(U.custom_amt)
        await call.answer()
        return await _edit_or_send(call, "✍️ Send the amount to add to your wallet (numbers only).", bk("act_addbalance"))
    try:
        amount = float(raw)
    except ValueError:
        return await call.answer("Invalid amount.", show_alert=True)
    result = _create_balance_transaction(call.from_user.id, amount)
    if result["status"] != "success":
        if result["status"] == "amount_range":
            msg = f"Amount must be between {fmt(result['minimum'])} and {fmt(result['maximum'])}."
        else:
            msg = "Could not create payment request. Try again."
        return await call.answer(msg, show_alert=True)
    await state.clear()
    await call.answer()
    await _show_payment_method_picker(call.from_user.id, result["oid"], "balance", state)


@dp.message(U.custom_amt)
async def custom_topup_amount(m: Message, state: FSMContext):
    if not m.text:
        return await m.answer("Send the amount as text, for example: 500")
    try:
        amount = float(m.text.strip())
    except ValueError:
        return await m.answer("❌ Invalid amount. Send a number, for example: 500")
    result = _create_balance_transaction(m.from_user.id, amount)
    if result["status"] != "success":
        if result["status"] == "amount_range":
            return await m.answer(f"Amount must be between {fmt(result['minimum'])} and {fmt(result['maximum'])}.")
        return await m.answer("❌ Could not create payment request. Please try again.")
    await state.clear()
    await _show_payment_method_picker(m.from_user.id, result["oid"], "balance", state)


def _available_payment_methods() -> list:
    methods = []
    zapupi_ready = (
        gs("payment_mode", "manual") == "auto"
        and gs("zapupi_enabled", "0") == "1"
        and bool(gs("zapupi_key"))
        and PUBLIC_BASE_URL.startswith("https://")
    )
    if gs("pay_upi_enabled", "1") == "1" and (gs("upi_id") or gs("static_qr_file_id") or zapupi_ready):
        methods.append(("upi", "⚡ ZapUPI / UPI" if zapupi_ready else "🏦 UPI / QR"))
    rate = sfloat(gs("binance_inr_per_usdt", "0"))
    if (gs("pay_binance_enabled", "1") == "1" and gs("binance_enabled", "1") == "1"
            and rate > 0 and (gs("binance_pay_id") or gs("binance_qr_file_id"))):
        methods.append(("binance", "🟡 Binance USDT"))
    return methods


async def _show_payment_method_picker(uid: int, oid: str, purpose: str, state: FSMContext):
    tx = db("SELECT amount, purpose, status FROM transactions WHERE order_id=? AND user_id=?", (oid, uid), one=True)
    if not tx or tx[2] != "pending":
        return await bot.send_message(uid, "❌ This payment request is no longer active.", reply_markup=main_menu_kb(uid))
    methods = _available_payment_methods()
    if not methods:
        await bot.send_message(
            uid,
            "⚠️ Payment methods are not configured yet. Please contact support or try later.",
            reply_markup=main_menu_kb(uid),
        )
        return
    rows = []
    for method, label in methods:
        prefix = "bal" if purpose == "balance" else "ord"
        action = "upi" if method == "upi" else "bin"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{prefix}{action}_{oid}")])
    rows.append([InlineKeyboardButton(text="❌ Cancel Payment", callback_data=f"txcancel_{oid}")])
    amount_label = fmt(tx[0])
    text = f"💳 <b>SELECT PAYMENT METHOD</b>\n\nReference: <code>{oid}</code>\nAmount: <b>{amount_label}</b>\n\nChoose how you want to pay:"
    await bot.send_message(uid, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


def _claim_zapupi_creation(oid: str) -> bool:
    """Atomically claim creation to prevent duplicate provider orders on double taps."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status, qr_data, method FROM transactions WHERE order_id=?", (oid,)
        ).fetchone()
        if not row or row[0] != "pending" or row[1] or row[2] == "zapupi_creating":
            conn.rollback()
            return False
        cur = conn.execute(
            "UPDATE transactions SET method='zapupi_creating' WHERE order_id=? AND status='pending' AND COALESCE(qr_data,'')=''",
            (oid,),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return False
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Could not claim ZapUPI creation for %s", oid)
        return False
    finally:
        conn.close()


async def _zapupi_post_status(order_id: str) -> tuple[bool, dict, str]:
    """Use ZapUPI's authenticated order-status API; never trust a frontend preview."""
    key = gs("zapupi_key", "").strip()
    if not key:
        return False, {}, "ZapUPI API key is not configured."
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://pay.zapupi.com/api/order-status",
                json={"zap_key": key, "order_id": order_id},
            ) as resp:
                payload = await resp.json(content_type=None)
                if resp.status != 200:
                    return False, {}, f"ZapUPI returned HTTP {resp.status}."
        if not isinstance(payload, dict) or str(payload.get("status", "")).lower() != "success":
            return False, {}, str(payload.get("message", "ZapUPI could not confirm this order.")) if isinstance(payload, dict) else "Unexpected ZapUPI response."
        details = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        return True, details, ""
    except asyncio.TimeoutError:
        return False, {}, "ZapUPI status request timed out."
    except Exception as exc:
        logger.exception("ZapUPI order-status failed for %s", order_id)
        return False, {}, f"ZapUPI status error: {type(exc).__name__}."


async def _create_zapupi_order(oid: str, uid: int, amount: float, purpose: str, plan_id: int = 0) -> tuple[bool, dict, str]:
    """Create a real ZapUPI order. An externally reachable webhook URL is required."""
    key = gs("zapupi_key", "").strip()
    if not key:
        return False, {}, "ZapUPI API key is not configured in Admin → Payment Settings."
    if not PUBLIC_BASE_URL.startswith("https://"):
        return False, {}, "Set PUBLIC_BASE_URL to your public HTTPS Render/service URL before accepting auto-payments."
    try:
        me = await bot.get_me()
        username = (getattr(me, "username", None) or BOT_USERNAME).lstrip("@")
    except Exception:
        username = BOT_USERNAME.lstrip("@")
    base = f"https://t.me/{username}?start="
    payload = {
        "zap_key": key,
        "order_id": oid,
        "amount": f"{float(amount):.2f}",
        "remark": f"{BRAND_NAME} | USER:{uid} | {purpose} | PLAN:{plan_id}",
        "success_url": base + quote("success_" + oid, safe=""),
        "failed_url": base + quote("failed_" + oid, safe=""),
        "timeout_url": base + quote("timeout_" + oid, safe=""),
        "webhook_url": f"{PUBLIC_BASE_URL}/zapupi/webhook",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post("https://pay.zapupi.com/api/create-order", json=payload) as resp:
                result = await resp.json(content_type=None)
                if resp.status != 200:
                    msg = result.get("message", f"ZapUPI returned HTTP {resp.status}.") if isinstance(result, dict) else f"ZapUPI returned HTTP {resp.status}."
                    return False, {}, str(msg)
        if not isinstance(result, dict) or str(result.get("status", "")).lower() != "success":
            return False, {}, str(result.get("message", "ZapUPI could not create the payment order.")) if isinstance(result, dict) else "Unexpected ZapUPI response."
        data = result.get("data") if isinstance(result.get("data"), dict) else result
        pay_id = str(data.get("pay_id", "") or "").strip()
        payment_url = str(data.get("payment_url", "") or "").strip()
        image_url = str(data.get("payment_image_url", "") or "").strip()
        upi_button = str(data.get("upi_button", "") or "").strip()
        paytm_button = str(data.get("paytm_button", "") or "").strip()
        if pay_id:
            # For custom UI, do not persist or show payment_url: the pay_id flow is used.
            meta = {"zapupi": True, "flow": "custom", "pay_id": pay_id,
                    "payment_image_url": image_url, "upi_button": upi_button,
                    "paytm_button": paytm_button, "provider_order_id": oid}
        elif payment_url.startswith(("https://", "http://")):
            # Default hosted page. Store only flow/order reference, not the external payment URL.
            meta = {"zapupi": True, "flow": "hosted", "provider_order_id": oid}
        else:
            return False, {}, "ZapUPI reported success but returned neither pay_id nor a valid payment_url."
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                "UPDATE transactions SET method='upi', qr_data=? WHERE order_id=? AND user_id=? AND status='pending' AND method='zapupi_creating'",
                (json.dumps(meta, separators=(",", ":")), oid, uid),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return False, {}, "Payment request changed before ZapUPI finished creating it. Please open a new payment request."
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Could not save ZapUPI metadata for %s", oid)
            return False, {}, "Could not save payment session. Contact support before paying again."
        finally:
            conn.close()
        data = dict(data)
        data["pay_id"] = pay_id
        data["payment_url"] = payment_url
        return True, data, ""
    except asyncio.TimeoutError:
        return False, {}, "ZapUPI order creation timed out. Please try again."
    except Exception as exc:
        logger.exception("ZapUPI create-order failed for %s", oid)
        return False, {}, f"ZapUPI error: {type(exc).__name__}."


def _zapupi_custom_button_url(value: str) -> str:
    decoded = unquote_plus(str(value or "").strip())
    if decoded.startswith(("https://", "http://", "upi://", "paytmmp://", "intent:")):
        return decoded[:2000]
    return ""


async def _send_zapupi_payment(uid: int, oid: str, amount: float, purpose: str, plan_id: int, state: FSMContext):
    ok, data, error = await _create_zapupi_order(oid, uid, amount, purpose, plan_id)
    if not ok:
        db("UPDATE transactions SET method='upi' WHERE order_id=? AND status='pending' AND method='zapupi_creating'", (oid,))
        await bot.send_message(uid, f"⚠️ <b>ZapUPI payment could not start.</b>\n{_safe_html(error)}\n\nNo payment was confirmed. You may try again or contact support.", reply_markup=main_menu_kb(uid))
        return
    pay_id = str(data.get("pay_id", "") or "").strip()
    meta_row = db("SELECT qr_data FROM transactions WHERE order_id=? AND user_id=?", (oid, uid), one=True)
    try:
        meta = json.loads(meta_row[0]) if meta_row and meta_row[0] else {}
    except (TypeError, ValueError):
        meta = {}
    keyboard_rows = []
    if pay_id:
        upi_url = _zapupi_custom_button_url(meta.get("upi_button", ""))
        paytm_url = _zapupi_custom_button_url(meta.get("paytm_button", ""))
        if upi_url:
            keyboard_rows.append([InlineKeyboardButton(text="📲 Pay with UPI", url=upi_url)])
        if paytm_url:
            keyboard_rows.append([InlineKeyboardButton(text="🟦 Pay with Paytm", url=paytm_url)])
        keyboard_rows.append([InlineKeyboardButton(text="🔎 Check Payment (Preview)", callback_data=f"zapchk_{oid}")])
        keyboard_rows.append([InlineKeyboardButton(text="🧾 Enter UTR (Preview)", callback_data=f"zaputr_{oid}")])
        keyboard_rows.append([InlineKeyboardButton(text="✖️ Close Payment Screen", callback_data=f"txcancel_{oid}")])
        caption = (f"⚡ <b>ZAPUPI PAYMENT</b>\n━━━━━━━━━━━━━━━━━━\nReference: <code>{oid}</code>\n"
                   f"Amount: <b>{fmt(amount)}</b>\nPay ID: <code>{_safe_html(pay_id)}</code>\n\n"
                   "Complete the payment above. Check Payment and Enter UTR only show a preview; wallet credit/order delivery happens after server verification by webhook.")
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        image_url = str(meta.get("payment_image_url", "") or "")
        sent = False
        if image_url.startswith(("https://", "http://")):
            try:
                await bot.send_photo(uid, image_url, caption=caption[:1000], reply_markup=kb)
                sent = True
            except Exception:
                logger.exception("Could not send ZapUPI image for %s", oid)
        if not sent:
            await bot.send_message(uid, caption, reply_markup=kb, disable_web_page_preview=True)
    else:
        payment_url = str(data.get("payment_url", "") or "")
        keyboard_rows.append([InlineKeyboardButton(text="💳 Open Secure Payment", url=payment_url)])
        keyboard_rows.append([InlineKeyboardButton(text="🔎 Check Payment (Preview)", callback_data=f"zapchk_{oid}")])
        keyboard_rows.append([InlineKeyboardButton(text="✖️ Close Payment Screen", callback_data=f"txcancel_{oid}")])
        await bot.send_message(
            uid,
            f"⚡ <b>ZAPUPI PAYMENT</b>\n━━━━━━━━━━━━━━━━━━\nReference: <code>{oid}</code>\n"
            f"Amount: <b>{fmt(amount)}</b>\n\nComplete payment on the secure page. The webhook and authenticated provider status are the only sources used for automatic credit/delivery.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
            disable_web_page_preview=True,
        )
    log_activity(uid, "ZAPUPI_ORDER_CREATED", f"order={oid}; purpose={purpose}; pay_id={'yes' if pay_id else 'no'}")


async def _zapupi_preview_status(oid: str, uid: int) -> tuple[str, bool]:
    tx = db("SELECT user_id,status,qr_data FROM transactions WHERE order_id=?", (oid,), one=True)
    if not tx or tx[0] != uid:
        return "This is not your payment request.", False
    if tx[1] == "paid":
        return "Provider webhook has already completed this payment.", True
    if tx[1] != "pending":
        return f"Payment is {tx[1]}. Start a new request if needed.", True
    try:
        meta = json.loads(tx[2] or "{}")
    except (TypeError, ValueError):
        meta = {}
    if not meta.get("zapupi"):
        return "This is not a ZapUPI payment session.", False
    pay_id = str(meta.get("pay_id", "") or "").strip()
    if pay_id:
        url = "https://pay.zapupi.com/pay/auto-check-" + quote(pay_id, safe="")
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    body = await resp.text()
            status = "PENDING"
            upper = body.upper()
            for candidate in ("SUCCESS", "FAILED", "TIMEOUT", "PENDING"):
                if candidate in upper:
                    status = candidate
                    break
            return f"Preview status: {status}. This preview does not credit the wallet or deliver a key; the authenticated webhook does that.", True
        except Exception:
            logger.exception("ZapUPI preview request failed for %s", oid)
            return "Could not load provider preview. The bot will still wait for the verified webhook.", True
    ok, details, error = await _zapupi_post_status(oid)
    if not ok:
        return f"Provider status unavailable: {error}", True
    provider_status = str(details.get("status", "Pending")).strip().upper()
    return f"Provider status: {provider_status}. This preview does not credit the wallet or deliver a key; the verified webhook does that.", True


@dp.callback_query(F.data.startswith("zapchk_"))
async def zapupi_check_preview(call: CallbackQuery):
    oid = call.data[7:]
    text, valid = await _zapupi_preview_status(oid, call.from_user.id)
    await call.answer(text[:190], show_alert=True)


@dp.callback_query(F.data.startswith("zaputr_"))
async def zapupi_utr_start(call: CallbackQuery, state: FSMContext):
    oid = call.data[7:]
    tx = db("SELECT user_id,status,qr_data FROM transactions WHERE order_id=?", (oid,), one=True)
    if not tx or tx[0] != call.from_user.id or tx[1] != "pending":
        return await call.answer("Payment request is not active.", show_alert=True)
    try:
        meta = json.loads(tx[2] or "{}")
    except (TypeError, ValueError):
        meta = {}
    if not meta.get("zapupi") or not meta.get("pay_id"):
        return await call.answer("UTR preview is available only for the ZapUPI custom payment screen.", show_alert=True)
    await state.clear()
    await state.update_data(zapupi_oid=oid)
    await state.set_state(U.zap_utr)
    await call.answer()
    await bot.send_message(call.from_user.id, f"Send the UTR for order <code>{oid}</code>. This is a status preview only; payment confirmation comes from ZapUPI's verified webhook.", reply_markup=bk("back_main"))


@dp.message(U.zap_utr)
async def zapupi_utr_preview(m: Message, state: FSMContext):
    if not m.text or not m.text.strip():
        return await m.answer("Send the UTR as text.")
    utr = m.text.strip()
    if len(utr) < 4 or len(utr) > 100 or any(ord(ch) < 32 for ch in utr):
        return await m.answer("UTR must be 4–100 characters. Please send it again.")
    data = await state.get_data()
    oid = str(data.get("zapupi_oid", ""))
    tx = db("SELECT user_id,status,qr_data FROM transactions WHERE order_id=?", (oid,), one=True)
    if not tx or tx[0] != m.from_user.id or tx[1] != "pending":
        await state.clear()
        return await m.answer("This payment session has expired. Please start again.", reply_markup=main_menu_kb(m.from_user.id))
    try:
        meta = json.loads(tx[2] or "{}")
    except (TypeError, ValueError):
        meta = {}
    pay_id = str(meta.get("pay_id", "") or "").strip()
    if not pay_id:
        await state.clear()
        return await m.answer("This payment session does not support UTR preview.", reply_markup=main_menu_kb(m.from_user.id))
    url = "https://pay.zapupi.com/pay/utr-check-" + quote(pay_id, safe="") + "-" + quote(utr, safe="")
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                body = await resp.text()
        upper = body.upper()
        status = next((x for x in ("SUCCESS", "FAILED", "TIMEOUT", "PENDING") if x in upper), "UNKNOWN")
        await state.clear()
        await m.answer(f"UTR preview: {status}. This does not change your order or wallet. Wait for the bot's verified payment confirmation.", reply_markup=main_menu_kb(m.from_user.id))
    except Exception:
        logger.exception("ZapUPI UTR preview failed for %s", oid)
        await state.clear()
        await m.answer("UTR preview is temporarily unavailable. The bot will continue waiting for verified webhook confirmation.", reply_markup=main_menu_kb(m.from_user.id))


async def _finalize_zapupi_balance(oid: str) -> dict:
    """Idempotently credit wallet and retain an audit record after webhook verification."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("BEGIN IMMEDIATE")
        tx = conn.execute("SELECT user_id,amount,status,purpose FROM transactions WHERE order_id=?", (oid,)).fetchone()
        if not tx:
            conn.rollback()
            return {"status": "not_found"}
        uid, amount, status, purpose = tx
        if purpose != "balance":
            conn.rollback()
            return {"status": "wrong_purpose"}
        if status == "paid":
            conn.rollback()
            return {"status": "already_processed", "user_id": uid, "amount": amount}
        if status != "pending":
            conn.rollback()
            return {"status": "not_pending"}
        cur = conn.execute("UPDATE transactions SET status='paid' WHERE order_id=? AND status='pending'", (oid,))
        if cur.rowcount != 1:
            conn.rollback()
            return {"status": "already_processed"}
        cur = conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
        if cur.rowcount != 1:
            conn.rollback()
            return {"status": "user_missing"}
        conn.execute("UPDATE balance_requests SET status='approved', reviewed_at=? WHERE reference LIKE ? AND status='pending'", (now_str(), f"{oid}%"))
        existing = conn.execute("SELECT id FROM balance_requests WHERE reference LIKE ? ORDER BY id DESC LIMIT 1", (f"{oid}%",)).fetchone()
        if not existing:
            user = conn.execute("SELECT username FROM users WHERE user_id=?", (uid,)).fetchone()
            conn.execute(
                "INSERT INTO balance_requests (user_id,username,amount,method,proof_file_id,reference,status,created_at,reviewed_at) VALUES (?,?,?,'zapupi-auto','',?,'approved',?,?)",
                (uid, user[0] if user and user[0] else "", amount, f"{oid}|UTR:AUTO", now_str(), now_str()),
            )
        conn.commit()
        return {"status": "success", "user_id": uid, "amount": amount}
    except Exception:
        conn.rollback()
        logger.exception("ZapUPI balance finalization failed for %s", oid)
        return {"status": "error"}
    finally:
        conn.close()


async def zapupi_webhook(request: web.Request):
    """Authoritative provider webhook; every success is re-checked against authenticated API."""
    try:
        payload = await request.json(loads=json.loads)
    except Exception:
        return web.json_response({"status": "error", "message": "Invalid JSON"}, status=400)
    if not isinstance(payload, dict):
        return web.json_response({"status": "error", "message": "Invalid payload"}, status=400)
    oid = str(payload.get("order_id", "") or "").strip()
    event_status = str(payload.get("status", "") or "").strip().lower()
    if not oid or event_status not in {"success", "failed", "failure", "timeout"}:
        return web.json_response({"status": "error", "message": "Missing or invalid order_id/status"}, status=400)
    tx = db("SELECT user_id,amount,status,purpose,plan_id,method,qr_data FROM transactions WHERE order_id=?", (oid,), one=True)
    if not tx:
        logger.warning("ZapUPI webhook for unknown order %s", oid)
        return web.json_response({"status": "ok"})
    uid, expected_amount, local_status, purpose, plan_id, method, qr_data = tx
    try:
        metadata = json.loads(qr_data or "{}")
    except (TypeError, ValueError):
        metadata = {}
    # A provider webhook can race the create-order response; allow the atomically
    # claimed ZapUPI state without metadata, but still require authenticated status API.
    claimed_before_metadata = method == "zapupi_creating" and not qr_data
    if not (metadata.get("zapupi") or claimed_before_metadata) or method not in {"upi", "zapupi_creating"}:
        return web.json_response({"status": "ignored"})
    if local_status == "paid":
        return web.json_response({"status": "ok", "message": "Already processed"})
    if local_status != "pending":
        return web.json_response({"status": "ok", "message": "Transaction is no longer pending"})
    verified, details, error = await _zapupi_post_status(oid)
    if not verified:
        logger.warning("ZapUPI webhook not yet confirmed for %s: %s", oid, error)
        return web.json_response({"status": "retry", "message": "Provider confirmation pending"}, status=503)
    provider_status = str(details.get("status", "Pending")).strip().lower()
    if provider_status in {"success", "paid", "completed"}:
        provider_amount = details.get("amount", details.get("pay_amount", None))
        try:
            if provider_amount is None:
                provider_amount = details.get("pay_amount")
            if provider_amount is None or abs(float(provider_amount) - float(expected_amount)) > 0.01:
                logger.error("ZapUPI amount mismatch for %s: local=%s provider=%s", oid, expected_amount, provider_amount)
                return web.json_response({"status": "error", "message": "Amount mismatch"}, status=400)
        except (TypeError, ValueError):
            return web.json_response({"status": "retry", "message": "Provider amount unavailable"}, status=503)
        if purpose == "order":
            result = finalize_plan_payment(oid, auto_verified=True)
            if result.get("status") == "success":
                await send_plan_delivery(result, oid)
                return web.json_response({"status": "ok"})
            if result.get("status") == "already_processed":
                return web.json_response({"status": "ok", "message": "Already processed"})
            if result.get("status") == "no_stock":
                try:
                    await bot.send_message(uid, f"✅ Payment received for <code>{oid}</code>, but this plan is temporarily out of stock. Admin has been notified; please do not pay again.")
                    await bot.send_message(ADMIN_ID, f"⚠️ <b>ZAPUPI PAYMENT VERIFIED — NO STOCK</b>\nOrder: <code>{oid}</code>\nUser: <code>{uid}</code>\nAmount: {fmt(expected_amount)}\nPlease restock plan {result.get('plan_id')} and resolve this order.")
                except Exception:
                    logger.exception("Could not notify no-stock ZapUPI payment %s", oid)
                return web.json_response({"status": "ok", "message": "Payment verified; stock handling required"})
            logger.error("ZapUPI paid order couldn't finalize: oid=%s status=%s", oid, result.get("status"))
            return web.json_response({"status": "retry", "message": "Order finalization pending"}, status=503)
        if purpose == "balance":
            result = await _finalize_zapupi_balance(oid)
            if result.get("status") in {"success", "already_processed"}:
                if result.get("status") == "success":
                    try:
                        await bot.send_message(uid, f"✅ <b>Wallet credited!</b>\nReference: <code>{oid}</code>\nAdded: <b>{fmt(expected_amount)}</b>", reply_markup=main_menu_kb(uid))
                    except Exception:
                        logger.exception("Could not notify wallet credit for %s", oid)
                return web.json_response({"status": "ok"})
            return web.json_response({"status": "retry", "message": "Wallet credit pending"}, status=503)
        return web.json_response({"status": "ignored"})
    if provider_status in {"failed", "failure", "timeout", "expired"}:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE transactions SET status='rejected' WHERE order_id=? AND status='pending'", (oid,))
            conn.execute("UPDATE balance_requests SET status='rejected', reviewed_at=? WHERE reference LIKE ? AND status='pending'", (now_str(), f"{oid}%"))
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Could not update failed ZapUPI transaction %s", oid)
            return web.json_response({"status": "retry"}, status=503)
        finally:
            conn.close()
        try:
            await bot.send_message(uid, f"❌ ZapUPI payment {provider_status}. Reference: <code>{oid}</code>. Start a new payment request if you want to try again.", reply_markup=main_menu_kb(uid))
        except Exception:
            logger.exception("Could not notify failed ZapUPI payment %s", oid)
        return web.json_response({"status": "ok"})
    return web.json_response({"status": "retry", "message": "Provider status is still pending"}, status=503)


async def _select_payment_method(call: CallbackQuery, state: FSMContext, oid: str, method: str, expected_purpose: str):
    tx = db(
        "SELECT user_id, amount, status, purpose, plan_id, coupon_code, expires_at FROM transactions WHERE order_id=?",
        (oid,), one=True,
    )
    if not tx or tx[0] != call.from_user.id or tx[3] != expected_purpose:
        return await call.answer("❌ Payment request not found.", show_alert=True)
    if tx[2] != "pending" or int(tx[6] or 0) < int(time.time()):
        db("UPDATE transactions SET status='expired' WHERE order_id=? AND status='pending'", (oid,))
        return await call.answer("⚠️ Payment request expired. Please start again.", show_alert=True)
    if method == "upi" and not any(item[0] == "upi" for item in _available_payment_methods()):
        return await call.answer("UPI is currently unavailable.", show_alert=True)
    if method == "binance" and not any(m[0] == "binance" for m in _available_payment_methods()):
        return await call.answer("Binance is unavailable. Ask admin to configure INR per USDT.", show_alert=True)

    zapupi_active = (
        method == "upi"
        and gs("payment_mode", "manual") == "auto"
        and gs("zapupi_enabled", "0") == "1"
        and bool(gs("zapupi_key"))
    )
    amount = float(tx[1] or 0)
    if zapupi_active:
        if not _claim_zapupi_creation(oid):
            return await call.answer("Payment session is already being prepared or has already been opened.", show_alert=True)
        await state.clear()
        await call.answer("Creating secure ZapUPI payment…")
        await _send_zapupi_payment(call.from_user.id, oid, amount, expected_purpose, sint(tx[4] or 0), state)
        return

    db("UPDATE transactions SET method=? WHERE order_id=? AND status='pending'", (method, oid))
    await state.clear()
    await state.update_data(payment_oid=oid, payment_method=method, payment_purpose=expected_purpose)
    await state.set_state(U.proof if expected_purpose == "balance" else U.buy_proof)

    if method == "binance":
        rate = sfloat(gs("binance_inr_per_usdt", "0"))
        if rate <= 0:
            return await call.answer("Binance rate has not been configured.", show_alert=True)
        usdt = amount / rate
        pay_text = (
            f"🟡 <b>BINANCE PAY (USDT)</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"Reference: <code>{oid}</code>\n"
            f"Amount: <b>{usdt:.4f} USDT</b>\n"
            f"Pay ID: <code>{_safe_html(gs('binance_pay_id'))}</code>\n"
            f"Payee: {_safe_html(gs('binance_pay_name')) or 'N/A'}\n"
            f"Rate used: 1 USDT = {fmt(rate)}\n\n"
            "Send the exact amount, then send the UTR/reference as text or upload a payment screenshot here."
        )
        qr_id = gs("binance_qr_file_id")
        if qr_id:
            await bot.send_photo(call.from_user.id, qr_id, caption=pay_text[:1000], reply_markup=_transaction_keyboard(oid, expected_purpose))
        else:
            await bot.send_message(call.from_user.id, pay_text, reply_markup=_transaction_keyboard(oid, expected_purpose))
    else:
        upi = gs("upi_id")
        payee = gs("payee_name", BRAND_NAME)
        pay_text = (
            f"🏦 <b>UPI PAYMENT</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"Reference: <code>{oid}</code>\nAmount: <b>{fmt(amount)}</b>\n"
            f"UPI ID: <code>{_safe_html(upi) or 'See QR below'}</code>\n"
            f"Payee: {_safe_html(payee)}\n\n"
            "Pay the exact amount, then send the UTR/reference as text or upload a payment screenshot here."
        )
        static_qr = gs("static_qr_file_id")
        qr = make_qr(upi_link(upi, payee, amount, oid)) if upi else None
        if static_qr:
            await bot.send_photo(call.from_user.id, static_qr, caption=pay_text[:1000], reply_markup=_transaction_keyboard(oid, expected_purpose))
        elif qr:
            await bot.send_photo(call.from_user.id, qr, caption=pay_text[:1000], reply_markup=_transaction_keyboard(oid, expected_purpose))
        else:
            if upi:
                pay_text += f"\n\nUPI link: <a href=\"{_safe_html(upi_link(upi, payee, amount, oid))}\">Open payment app</a>"
            await bot.send_message(call.from_user.id, pay_text, reply_markup=_transaction_keyboard(oid, expected_purpose))
    await call.answer("Payment instructions sent.")


def _transaction_keyboard(oid: str, purpose: str):
    rows = []
    if gs("payment_mode", "manual") == "auto":
        tx = db("SELECT plan_id FROM transactions WHERE order_id=?", (oid,), one=True)
        plan_id = tx[0] if tx and purpose == "order" else None
        cfg = _api_config_for_plan(plan_id)
        if cfg and cfg.get("url"):
            prefix = "autocheck_" if purpose == "balance" else "bautocheck_"
            label = "🔎 Check Payment Status"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"{prefix}{oid}")])
    rows.append([InlineKeyboardButton(text="❌ Cancel Payment", callback_data=f"txcancel_{oid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data.startswith("balupi_"))
async def balance_upi_method(call: CallbackQuery, state: FSMContext):
    await _select_payment_method(call, state, call.data[7:], "upi", "balance")


@dp.callback_query(F.data.startswith("balbin_"))
async def balance_binance_method(call: CallbackQuery, state: FSMContext):
    await _select_payment_method(call, state, call.data[7:], "binance", "balance")


@dp.callback_query(F.data.startswith("ordupi_"))
async def order_upi_method(call: CallbackQuery, state: FSMContext):
    await _select_payment_method(call, state, call.data[7:], "upi", "order")


@dp.callback_query(F.data.startswith("ordbin_"))
async def order_binance_method(call: CallbackQuery, state: FSMContext):
    await _select_payment_method(call, state, call.data[7:], "binance", "order")


@dp.callback_query(F.data.startswith("externalbuy_"))
async def external_buy(call: CallbackQuery, state: FSMContext):
    plan_id = sint(call.data[12:])
    result = _create_order_transaction(call.from_user.id, plan_id)
    if result["status"] == "free_plan_use_wallet":
        wallet_result = _purchase_from_wallet(call.from_user.id, plan_id)
        if wallet_result["status"] == "success":
            await call.answer("✅ Delivered.", show_alert=True)
            return await bot.send_message(call.from_user.id, f"🔑 Your key: <code>{_safe_html(wallet_result['key'])}</code>", reply_markup=main_menu_kb(call.from_user.id))
    if result["status"] != "success":
        return await call.answer({"unavailable": "Plan unavailable.", "no_stock": "Out of stock.", "free_plan_use_wallet": "Use wallet checkout for free plan.", "error": "Could not create payment."}.get(result["status"], "Could not create payment."), show_alert=True)
    await call.answer()
    await _show_payment_method_picker(call.from_user.id, result["oid"], "order", state)


@dp.callback_query(F.data.startswith("txcancel_"))
async def cancel_payment_transaction(call: CallbackQuery, state: FSMContext):
    oid = call.data[8:]
    tx = db("SELECT user_id, status, coupon_code, qr_data FROM transactions WHERE order_id=?", (oid,), one=True)
    if not tx or tx[0] != call.from_user.id:
        return await call.answer("Payment request not found.", show_alert=True)
    try:
        tx_meta = json.loads(tx[3] or "{}")
    except (TypeError, ValueError):
        tx_meta = {}
    if tx[1] == "pending" and tx_meta.get("zapupi"):
        # Closing the UI must not cancel a provider payment that may already have been paid.
        await state.clear()
        await call.answer("Payment screen closed; waiting for provider confirmation.")
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return await bot.send_message(call.from_user.id, "Payment screen closed. If you already paid, the verified ZapUPI webhook will still update your order/wallet. Do not pay twice.", reply_markup=main_menu_kb(call.from_user.id))
    if tx[1] == "pending":
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE transactions SET status='cancelled' WHERE order_id=? AND status='pending'", (oid,))
            code = str(tx[2] or "").upper()
            if code:
                conn.execute(
                    "INSERT OR REPLACE INTO user_coupon_selections (user_id,coupon_code,created_at) VALUES (?,?,?)",
                    (call.from_user.id, code, now_str()),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Could not cancel transaction %s", oid)
        finally:
            conn.close()
    await state.clear()
    await call.answer("Payment cancelled.")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await bot.send_message(call.from_user.id, "Payment cancelled. You can return to the store or wallet menu.", reply_markup=main_menu_kb(call.from_user.id))


async def _notify_payment_admins(oid: str, uid: int, amount: float, purpose: str, method: str, proof_file_id: str, reference: str, plan_id: int = 0):
    admins = set(STATIC_ADMIN_IDS) | {ADMIN_ID}
    coadmins = db("SELECT user_id FROM co_admins", all=True) or []
    admins.update(int(row[0]) for row in coadmins if row and row[0])
    if purpose == "order":
        plan = db("SELECT pl.name,p.name FROM plans pl JOIN products p ON p.id=pl.product_id WHERE pl.id=?", (plan_id,), one=True)
        plan_name, product_name = (plan[0], plan[1]) if plan else ("Unknown plan", "Unknown product")
        caption = (
            f"🧾 <b>ORDER PAYMENT PROOF</b>\nReference: <code>{oid}</code>\n"
            f"User: <code>{uid}</code>\nProduct: {_safe_html(product_name)}\n"
            f"Plan: {_safe_html(plan_name)}\nAmount: {fmt(amount)}\nMethod: {_safe_html(method.upper())}\n"
            f"Proof/UTR: <code>{_safe_html(reference[-150:])}</code>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Approve & Deliver", callback_data=f"order_approve_{oid}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"order_reject_{oid}"),
        ]])
    else:
        caption = (
            f"💰 <b>WALLET TOP-UP PROOF</b>\nReference: <code>{oid}</code>\n"
            f"User: <code>{uid}</code>\nAmount: {fmt(amount)}\nMethod: {_safe_html(method.upper())}\n"
            f"Proof/UTR: <code>{_safe_html(reference[-150:])}</code>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Approve & Credit", callback_data=f"credit_{oid}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{oid}"),
        ]])
    for admin_id in admins:
        try:
            if proof_file_id:
                await bot.send_photo(admin_id, proof_file_id, caption=caption[:1000], reply_markup=kb)
            else:
                await bot.send_message(admin_id, caption, reply_markup=kb)
        except Exception:
            logger.info("Could not notify admin %s about payment %s", admin_id, oid)


async def _submit_payment_proof(m: Message, state: FSMContext, purpose: str):
    data = await state.get_data()
    oid = str(data.get("payment_oid") or "")
    if not oid:
        await state.clear()
        return await m.answer("❌ Payment session expired. Open Wallet/Store and start again.")
    tx = db(
        "SELECT user_id, amount, status, purpose, plan_id, method, expires_at FROM transactions WHERE order_id=?",
        (oid,), one=True,
    )
    if not tx or tx[0] != m.from_user.id or tx[3] != purpose:
        await state.clear()
        return await m.answer("❌ Payment request not found. Start again from the menu.")
    if tx[2] != "pending" or int(tx[6] or 0) < int(time.time()):
        db("UPDATE transactions SET status='expired' WHERE order_id=? AND status='pending'", (oid,))
        await state.clear()
        return await m.answer("⚠️ Payment request expired. Please create a new request.")
    photo_id = m.photo[-1].file_id if m.photo else ""
    proof_text = (m.text or m.caption or "").strip()
    if not photo_id and not proof_text:
        return await m.answer("Send the UTR/reference as text or upload a screenshot.")
    utr = proof_text[:100] if proof_text else "PHOTO"
    reference = f"{oid}|PLAN:{tx[4]}|UTR:{utr}" if purpose == "order" else f"{oid}|UTR:{utr}"

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        duplicate = conn.execute(
            "SELECT id FROM balance_requests WHERE reference LIKE ? AND status='pending' LIMIT 1",
            (f"{oid}%",),
        ).fetchone()
        if duplicate:
            conn.rollback()
            return await m.answer("✅ Your proof is already submitted. Please wait for review.")
        conn.execute(
            "INSERT INTO balance_requests (user_id, username, amount, method, proof_file_id, reference, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
            (m.from_user.id, m.from_user.username or "", tx[1], tx[5] or "manual", photo_id, reference, now_str()),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Could not save payment proof for %s", oid)
        return await m.answer("❌ Could not save proof. Please try again or contact support.")
    finally:
        conn.close()

    await state.clear()
    await _notify_payment_admins(oid, m.from_user.id, float(tx[1]), purpose, str(tx[5] or "manual"), photo_id, utr, sint(tx[4] or 0))
    await m.answer(
        f"✅ <b>Payment proof submitted.</b>\nReference: <code>{oid}</code>\n"
        "Your request is pending admin review. Do not pay again for the same reference.",
        reply_markup=main_menu_kb(m.from_user.id),
    )
    log_activity(m.from_user.id, "PAYMENT_PROOF_SUBMITTED", f"order={oid}; purpose={purpose}; method={tx[5]}")


@dp.message(U.proof)
async def topup_payment_proof(m: Message, state: FSMContext):
    await _submit_payment_proof(m, state, "balance")


@dp.message(U.buy_proof)
async def order_payment_proof(m: Message, state: FSMContext):
    await _submit_payment_proof(m, state, "order")


@dp.callback_query(F.data.startswith("couponplan_"))
async def apply_coupon_from_plan(call: CallbackQuery, state: FSMContext):
    plan_id = sint(call.data[11:])
    if not _effective_plan_price(call.from_user.id, plan_id):
        return await call.answer("Plan unavailable.", show_alert=True)
    await state.clear()
    await state.update_data(coupon_plan_id=plan_id)
    await state.set_state(U.coupon)
    await call.answer()
    await _edit_or_send(call, "🎟️ Send your coupon code to apply it to this purchase:", bk(f"shopplan_{plan_id}"))


@dp.message(U.coupon)
async def redeem_user_coupon(m: Message, state: FSMContext):
    if not m.text:
        return await m.answer("Please send your coupon code as text.")
    code = m.text.strip().upper()[:64]
    if not code:
        return await m.answer("Coupon code cannot be empty.")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        discount = _coupon_discount_conn(conn, code)
        if discount is None:
            conn.rollback()
            return await m.answer("❌ Coupon is invalid, expired, or has reached its usage limit. Try another code.")
        conn.execute(
            "INSERT OR REPLACE INTO user_coupon_selections (user_id,coupon_code,created_at) VALUES (?,?,?)",
            (m.from_user.id, code, now_str()),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Coupon selection failed for user %s", m.from_user.id)
        return await m.answer("❌ Could not apply coupon. Please try again.")
    finally:
        conn.close()
    data = await state.get_data()
    plan_id = sint(data.get("coupon_plan_id", 0))
    await state.clear()
    log_activity(m.from_user.id, "COUPON_SELECTED", code)
    if plan_id:
        info = _coupon_adjusted_price(m.from_user.id, plan_id)
        if info:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💰 Wallet · {fmt(info['final_price'])}", callback_data=f"walletbuy_{plan_id}")],
                [InlineKeyboardButton(text="💳 Pay by UPI / Binance", callback_data=f"externalbuy_{plan_id}")],
                [InlineKeyboardButton(text="⬅️ Back to Plan", callback_data=f"shopplan_{plan_id}")],
            ])
            return await m.answer(
                f"✅ Coupon <code>{_safe_html(code)}</code> applied ({discount:g}% off).\n"
                f"Payable amount: <b>{fmt(info['final_price'])}</b>", reply_markup=kb,
            )
    await m.answer(
        f"✅ Coupon <code>{_safe_html(code)}</code> selected for your next purchase. Open a plan and checkout to use it.",
        reply_markup=main_menu_kb(m.from_user.id),
    )


async def show_reseller_panel(call: CallbackQuery):
    user = get_user(call.from_user.id)
    if not user:
        return await call.answer("Send /start first.", show_alert=True)
    if gs("reseller_system_status", "ON").upper() != "ON":
        return await _edit_or_send(call, "👑 <b>RESELLER SYSTEM</b>\n\nApplications are currently paused.", user_back_kb())
    if user[4]:
        text = "👑 <b>RESELLER PANEL</b>\n\n✅ Your reseller access is active. Eligible reseller prices are shown at checkout."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ Open Store", callback_data="act_shop")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
        ])
    else:
        fee = sfloat(gs("reseller_setup_fee", "500"))
        minimum = sfloat(gs("reseller_min_balance", "1000"))
        existing = db("SELECT id,status FROM reseller_requests WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (call.from_user.id,), one=True)
        text = (
            "👑 <b>RESELLER PROGRAM</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"Setup fee: <b>{fmt(fee)}</b>\nMinimum wallet balance: <b>{fmt(minimum)}</b>\n\n"
            "Apply here; an admin will review the request and confirm setup/payment before activation."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Application Pending" if existing else "📨 Apply for Reseller", callback_data="reseller_apply")],
            [InlineKeyboardButton(text="🎧 Support", callback_data="act_support")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
        ])
    await call.answer()
    await _edit_or_send(call, text, kb)


@dp.callback_query(F.data == "reseller_apply")
async def reseller_apply(call: CallbackQuery):
    if gs("reseller_system_status", "ON").upper() != "ON":
        return await call.answer("Reseller applications are paused.", show_alert=True)
    user = get_user(call.from_user.id)
    if user and user[4]:
        return await call.answer("You are already a reseller.", show_alert=True)
    pending = db("SELECT id FROM reseller_requests WHERE user_id=? AND status='pending' LIMIT 1", (call.from_user.id,), one=True)
    if pending:
        return await call.answer("Your application is already pending.", show_alert=True)
    fee = sfloat(gs("reseller_setup_fee", "500"))
    request_id = db(
        "INSERT INTO reseller_requests (user_id, amount, status, created_at) VALUES (?, ?, 'pending', ?)",
        (call.from_user.id, fee, now_str()),
    )
    admins = set(STATIC_ADMIN_IDS) | {ADMIN_ID}
    for aid in db("SELECT user_id FROM co_admins", all=True) or []:
        if aid and aid[0]: admins.add(int(aid[0]))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve Reseller", callback_data=f"resreq_approve_{request_id}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"resreq_reject_{request_id}"),
    ]])
    for aid in admins:
        try:
            await bot.send_message(aid, f"👑 <b>RESELLER APPLICATION</b>\nRequest: <code>{request_id}</code>\nUser: <code>{call.from_user.id}</code>\nFee to verify: {fmt(fee)}", reply_markup=kb)
        except Exception:
            pass
    await call.answer("Application submitted.", show_alert=True)
    await bot.send_message(
        call.from_user.id,
        "✅ Your reseller application has been submitted. An admin will review it.",
        reply_markup=main_menu_kb(call.from_user.id),
    )


@dp.callback_query(F.data.startswith("resreq_approve_"))
async def reseller_request_approve(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    req_id = sint(call.data[len("resreq_approve_"):])
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT user_id,status FROM reseller_requests WHERE id=?", (req_id,)).fetchone()
        if not row or row[1] != "pending":
            conn.rollback()
            return await call.answer("Request already reviewed or not found.", show_alert=True)
        conn.execute("UPDATE reseller_requests SET status='approved', reviewed_at=? WHERE id=?", (now_str(), req_id))
        conn.execute("UPDATE users SET is_reseller=1 WHERE user_id=?", (row[0],))
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Reseller approval failed for request %s", req_id)
        return await call.answer("Database error.", show_alert=True)
    finally:
        conn.close()
    await call.answer("Reseller activated.", show_alert=True)
    try:
        await bot.send_message(row[0], "👑 <b>Your reseller application was approved.</b> Reseller pricing is now active.", reply_markup=main_menu_kb(row[0]))
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@dp.callback_query(F.data.startswith("resreq_reject_"))
async def reseller_request_reject(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    req_id = sint(call.data[len("resreq_reject_"):])
    row = db("SELECT user_id,status FROM reseller_requests WHERE id=?", (req_id,), one=True)
    if not row or row[1] != "pending":
        return await call.answer("Request already reviewed or not found.", show_alert=True)
    db("UPDATE reseller_requests SET status='rejected', reviewed_at=? WHERE id=?", (now_str(), req_id))
    await call.answer("Request rejected.")
    try:
        await bot.send_message(row[0], "Your reseller application was rejected. Contact support if you need details.", reply_markup=main_menu_kb(row[0]))
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


async def show_vip_panel(call: CallbackQuery):
    user = get_user(call.from_user.id)
    if not user:
        return await call.answer("Send /start first.", show_alert=True)
    if user[5]:
        text = (
            "🌟 <b>VIP MEMBER</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"✅ VIP benefits are active. Current configured VIP discount: {VIP_DISCOUNT:g}%.\n"
            "VIP discounts will be applied at checkout."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ Open Store", callback_data="act_shop")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
        ])
    else:
        kb_rows = []
        support = gs("support_telegram")
        if support.startswith(("https://", "http://", "tg://")):
            kb_rows.append([InlineKeyboardButton(text="🎧 Contact Support", url=support)])
        kb_rows.append([InlineKeyboardButton(text="📨 Request VIP", callback_data="vip_request")])
        kb_rows.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")])
        text = (
            "🌟 <b>VIP MEMBERSHIP</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"Configured membership reference price: <b>{fmt(VIP_PRICE)}</b>\n"
            f"Configured VIP price discount: <b>{VIP_DISCOUNT:g}%</b>\n\n"
            "VIP activation is reviewed by the admin. Send a request below or contact support."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await call.answer()
    await _edit_or_send(call, text, kb)


@dp.callback_query(F.data == "vip_request")
async def vip_request(call: CallbackQuery):
    exists = db("SELECT id FROM tickets WHERE user_id=? AND status='Open' AND message LIKE 'VIP activation request%' LIMIT 1", (call.from_user.id,), one=True)
    if exists:
        return await call.answer("Your VIP request is already open.", show_alert=True)
    ticket_id = db(
        "INSERT INTO tickets (user_id,message,status,created_at) VALUES (?,?,'Open',?)",
        (call.from_user.id, "VIP activation request from user", now_str()),
    )
    admins = set(STATIC_ADMIN_IDS) | {ADMIN_ID}
    for row in db("SELECT user_id FROM co_admins", all=True) or []:
        if row and row[0]: admins.add(int(row[0]))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Reply", callback_data=f"ticket_reply_{ticket_id}"),
        InlineKeyboardButton(text="✅ Close", callback_data=f"ticket_close_{ticket_id}"),
    ]])
    for aid in admins:
        try:
            await bot.send_message(aid, f"🌟 <b>VIP ACTIVATION REQUEST</b>\nTicket: <code>#{ticket_id}</code>\nUser: <code>{call.from_user.id}</code>", reply_markup=kb)
        except Exception:
            pass
    await call.answer("VIP request sent to admin.", show_alert=True)


# ══════════════════════════════════════════════════════════════
#                    SUPPORT TICKETS
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "new_ticket")
async def new_ticket_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(U.ticket)
    await call.answer()
    await _edit_or_send(call, "🎫 <b>NEW SUPPORT TICKET</b>\n\nDescribe your issue in one message. Do not send passwords or private payment credentials.", bk("act_support"))


@dp.message(U.ticket)
async def new_ticket_save(m: Message, state: FSMContext):
    if not m.text or not m.text.strip():
        return await m.answer("Please describe the issue in text.")
    body = m.text.strip()[:3500]
    ticket_id = db(
        "INSERT INTO tickets (user_id,message,status,created_at) VALUES (?,?,'Open',?)",
        (m.from_user.id, body, now_str()),
    )
    await state.clear()
    admins = set(STATIC_ADMIN_IDS) | {ADMIN_ID}
    for row in db("SELECT user_id FROM co_admins", all=True) or []:
        if row and row[0]: admins.add(int(row[0]))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Reply", callback_data=f"ticket_reply_{ticket_id}"),
        InlineKeyboardButton(text="✅ Close", callback_data=f"ticket_close_{ticket_id}"),
    ]])
    for aid in admins:
        try:
            await bot.send_message(aid, f"🎫 <b>NEW SUPPORT TICKET #{ticket_id}</b>\nUser: <code>{m.from_user.id}</code>\n\n{_safe_html(body)}", reply_markup=kb)
        except Exception:
            logger.info("Could not notify admin %s about ticket %s", aid, ticket_id)
    await m.answer(f"✅ Ticket <b>#{ticket_id}</b> created. Support will reply here.", reply_markup=main_menu_kb(m.from_user.id))


@dp.callback_query(F.data == "my_tickets")
async def my_tickets(call: CallbackQuery):
    rows = db(
        "SELECT id,message,status,reply,created_at,replied_at FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (call.from_user.id,), all=True,
    )
    if not rows:
        return await call.answer("You have no support tickets.", show_alert=True)
    text = "🎫 <b>YOUR SUPPORT TICKETS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for row in rows:
        text += f"\n<b>#{row[0]}</b> · {_safe_html(row[2])}\n{_safe_html(truncate(row[1], 180))}\n"
        if row[3]:
            text += f"↩️ Reply: {_safe_html(truncate(row[3], 180))}\n"
        text += f"📅 {row[4]}\n"
    await call.answer()
    await _edit_or_send(call, text[:3900], user_back_kb())


@dp.callback_query(F.data.startswith("ticket_reply_"))
async def ticket_reply_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    ticket_id = sint(call.data[len("ticket_reply_"):])
    ticket = db("SELECT user_id,status FROM tickets WHERE id=?", (ticket_id,), one=True)
    if not ticket:
        return await call.answer("Ticket not found.", show_alert=True)
    await state.clear()
    await state.update_data(ticket_reply_id=ticket_id)
    await state.set_state(U.ticket_reply)
    await call.answer()
    await _edit_or_send(call, f"💬 Send reply for ticket <code>#{ticket_id}</code> (user <code>{ticket[0]}</code>):", bk("adm_u_tickets"))


@dp.message(U.ticket_reply)
async def ticket_reply_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text or not m.text.strip():
        return await m.answer("Please send a text reply.")
    data = await state.get_data()
    ticket_id = sint(data.get("ticket_reply_id"))
    ticket = db("SELECT user_id,status FROM tickets WHERE id=?", (ticket_id,), one=True)
    if not ticket:
        await state.clear()
        return await m.answer("Ticket not found.", reply_markup=admin_kb())
    reply_text = m.text.strip()[:3500]
    db("UPDATE tickets SET reply=?, status='Replied', replied_at=? WHERE id=?", (reply_text, now_str(), ticket_id))
    await state.clear()
    try:
        await bot.send_message(ticket[0], f"💬 <b>Support reply — Ticket #{ticket_id}</b>\n\n{_safe_html(reply_text)}", reply_markup=main_menu_kb(ticket[0]))
    except Exception:
        await m.answer("⚠️ Reply saved, but the user could not be messaged. They may not have started the bot.")
    await m.answer(f"✅ Reply saved for ticket #{ticket_id}.", reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("ticket_close_"))
async def ticket_close(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    ticket_id = sint(call.data[len("ticket_close_"):])
    ticket = db("SELECT user_id,status FROM tickets WHERE id=?", (ticket_id,), one=True)
    if not ticket:
        return await call.answer("Ticket not found.", show_alert=True)
    db("UPDATE tickets SET status='Closed' WHERE id=?", (ticket_id,))
    try:
        await bot.send_message(ticket[0], f"✅ Your support ticket #{ticket_id} was closed. You can open a new ticket from Support if you still need help.")
    except Exception:
        pass
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("Ticket closed.")



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
        [InlineKeyboardButton(text="🌐 Payment API Variant", callback_data=f"planapi_{plid}")],
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
    await state.clear()
    await state.update_data(target_uid=uid, action="add")
    await state.set_state(A.user_addbal)
    await call.message.edit_text(
        f"💰 Send amount to ADD to <code>{uid}</code>:", reply_markup=bk("adm_users")
    )


@dp.message(A.user_addbal)
async def u_add_bal_do(m: Message, state: FSMContext):
    """Shared, single handler for user-panel and balance-manager credit flows."""
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    data = await state.get_data()
    parts = m.text.strip().split()
    if data.get("target_uid"):
        if len(parts) != 1:
            return await m.answer("Send only the amount, for example: 500")
        uid = sint(data.get("target_uid"))
        try:
            amount = float(parts[0])
        except ValueError:
            return await m.answer("❌ Invalid amount.")
    else:
        if len(parts) != 2:
            return await m.answer("Send USER_ID AMOUNT, for example: 123456 500")
        uid = sint(parts[0])
        try:
            amount = float(parts[1])
        except ValueError:
            return await m.answer("❌ Invalid amount.")
    if uid <= 0 or amount <= 0 or amount > 100000000:
        return await m.answer("❌ User ID and amount must be positive; amount must not exceed 100000000.")
    exists = db("SELECT user_id FROM users WHERE user_id=?", (uid,), one=True)
    if not exists and data.get("target_uid"):
        return await m.answer("❌ User not found.")
    db("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)", (uid, now_str()))
    db("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
    log_activity(m.from_user.id, "ADMIN_BALANCE_ADD", f"user={uid}; amount={amount}")
    await state.clear()
    current = db("SELECT balance FROM users WHERE user_id=?", (uid,), one=True)
    new_balance = current[0] if current else amount
    await m.answer(f"✅ Added {fmt(amount)} to <code>{uid}</code>. New balance: {fmt(new_balance)}", reply_markup=admin_kb())
    try:
        await bot.send_message(uid, f"💰 <b>Balance Added!</b>\n\n+{fmt(amount)} credited by admin.\nBalance: {fmt(new_balance)}", reply_markup=main_menu_kb(uid))
    except Exception:
        logger.info("Could not notify user %s about admin balance credit", uid)


@dp.callback_query(F.data.startswith("u_rem_"))
async def u_rem_bal(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    await state.clear()
    await state.update_data(target_uid=uid, action="rem")
    await state.set_state(A.user_rembal)
    await call.message.edit_text(
        f"💸 Send amount to REMOVE from <code>{uid}</code>:", reply_markup=bk("adm_users")
    )


@dp.message(A.user_rembal)
async def u_rem_bal_do(m: Message, state: FSMContext):
    """Shared, single handler for user-panel and balance-manager debits."""
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    data = await state.get_data()
    parts = m.text.strip().split()
    if data.get("target_uid"):
        if len(parts) != 1:
            return await m.answer("Send only the amount, for example: 500")
        uid = sint(data.get("target_uid"))
        amount_text = parts[0]
    else:
        if len(parts) != 2:
            return await m.answer("Send USER_ID AMOUNT, for example: 123456 500")
        uid = sint(parts[0])
        amount_text = parts[1]
    try:
        amount = float(amount_text)
    except ValueError:
        return await m.answer("❌ Invalid amount.")
    if uid <= 0 or amount <= 0 or amount > 100000000:
        return await m.answer("❌ User ID and amount must be positive; amount must not exceed 100000000.")
    user_row = db("SELECT balance FROM users WHERE user_id=?", (uid,), one=True)
    if not user_row:
        return await m.answer("❌ User not found.")
    before = float(user_row[0] or 0)
    actual = min(amount, before)
    db("UPDATE users SET balance=MAX(0, balance-?) WHERE user_id=?", (actual, uid))
    log_activity(m.from_user.id, "ADMIN_BALANCE_REMOVE", f"user={uid}; amount={actual}")
    await state.clear()
    await m.answer(f"✅ Removed {fmt(actual)} from <code>{uid}</code>. New balance: {fmt(max(0, before-actual))}", reply_markup=admin_kb())
    try:
        await bot.send_message(uid, f"💸 <b>Balance adjusted by admin</b>\n\n-{fmt(actual)}\nBalance: {fmt(max(0, before-actual))}", reply_markup=main_menu_kb(uid))
    except Exception:
        logger.info("Could not notify user %s about admin balance debit", uid)


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
    await state.clear()
    await state.set_state(A.user_addbal)
    await call.message.edit_text(
        "👤 Send: <code>USER_ID AMOUNT</code>\n\nExample: <code>123456 500</code>",
        reply_markup=bk("adm_bal"),
    )


@dp.callback_query(F.data == "adm_bal_rem")
async def bal_rem_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await state.set_state(A.user_rembal)
    await call.message.edit_text(
        "🗑️ Send: <code>USER_ID AMOUNT</code>", reply_markup=bk("adm_bal")
    )



@dp.callback_query(F.data == "adm_bal_check")
async def bal_check_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.user_search)
    await call.message.edit_text("📞 Send user ID:", reply_markup=bk("adm_bal"))


@dp.callback_query(F.data == "adm_bal_all")
async def bal_all_start(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Yes, Add to All", callback_data="adm_bal_all_yes")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_bal")],
    ])
    await call.message.edit_text(
        "⚠️ Add balance to <b>ALL</b> users? Next you'll send amount.",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "adm_bal_all_yes")
async def bal_all_prompt(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(bulk="bal_all")
    await state.set_state(A.bulk_balance_value)
    await call.message.edit_text("💰 Send amount to add to ALL users:", reply_markup=bk("adm_bal"))


@dp.message(A.bulk_balance_value)
async def bal_all_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        amt = float(m.text.strip())
        if amt <= 0:
            raise ValueError
    except ValueError:
        return await m.answer("❌ Invalid amount.")
    total = db("SELECT COUNT(*) FROM users", one=True)[0]
    db("UPDATE users SET balance=balance+?", (amt,))
    log_activity(m.from_user.id, "ADMIN_BAL_ALL", f"amt={amt}; users={total}")
    await state.clear()
    await m.answer(
        f"✅ Added {fmt(amt)} to {total} users.", reply_markup=admin_kb()
    )


# ══════════════════════════════════════════════════════════════
#                  RESELLER SYSTEM
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_reseller")
async def adm_reseller(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    st = gs("reseller_system_status", "ON")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Add Reseller", callback_data="adm_res_add")],
        [InlineKeyboardButton(text="🗑️ Remove Reseller", callback_data="adm_res_rem")],
        [InlineKeyboardButton(text="🕵️ View Role", callback_data="adm_res_view")],
        [InlineKeyboardButton(text="⚙️ Set Reseller User", callback_data="adm_res_setuser")],
        [InlineKeyboardButton(text="🎯 All Keys", callback_data="adm_res_allkeys")],
        [InlineKeyboardButton(text="📞 Total Users", callback_data="adm_res_total")],
        [InlineKeyboardButton(text=f"🔛 System: {st}", callback_data="adm_res_tog")],
        [InlineKeyboardButton(text="💰 Setup Fee", callback_data="adm_res_fee")],
        [InlineKeyboardButton(text="💳 Min Balance", callback_data="adm_res_min")],
        [InlineKeyboardButton(text="🚨 Direct Reseller (by ID)", callback_data="adm_res_direct")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("👑 <b>RESELLER SYSTEM</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("👑 Reseller System", reply_markup=kb)


@dp.callback_query(F.data == "adm_res_add")
async def res_add_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(res_act="add")
    await state.set_state(A.res_direct_id)
    await call.message.edit_text(
        "🔒 Send user ID to make reseller:", reply_markup=bk("adm_reseller")
    )


@dp.callback_query(F.data == "adm_res_rem")
async def res_rem_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(res_act="remove")
    await state.set_state(A.res_direct_id)
    await call.message.edit_text(
        "🗑️ Send user ID to remove reseller:", reply_markup=bk("adm_reseller")
    )


@dp.callback_query(F.data == "adm_res_setuser")
async def res_setuser(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(res_act="toggle")
    await state.set_state(A.res_direct_id)
    await call.message.edit_text(
        "⚙️ Send user ID to toggle reseller:", reply_markup=bk("adm_reseller")
    )


@dp.callback_query(F.data == "adm_res_direct")
async def res_direct_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(res_act="direct")
    await state.set_state(A.res_direct_id)
    await call.message.edit_text(
        "🚨 <b>Direct Reseller</b>\n\nSend user ID to instantly activate reseller:",
        reply_markup=bk("adm_reseller"),
    )


@dp.message(A.res_direct_id)
async def res_direct_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        uid = int(m.text.strip())
    except ValueError:
        return await m.answer("❌ Invalid ID.")
    d = await state.get_data()
    act = d.get("res_act")
    db("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)", (uid, now_str()))
    if act == "add":
        db("UPDATE users SET is_reseller=1 WHERE user_id=?", (uid,))
        await m.answer(f"✅ <code>{uid}</code> is now a reseller.", reply_markup=admin_kb())
    elif act == "remove":
        db("UPDATE users SET is_reseller=0 WHERE user_id=?", (uid,))
        await m.answer(f"✅ Reseller removed from <code>{uid}</code>.", reply_markup=admin_kb())
    elif act == "toggle":
        row = db("SELECT is_reseller FROM users WHERE user_id=?", (uid,), one=True)
        db("UPDATE users SET is_reseller=? WHERE user_id=?", (0 if (row and row[0]) else 1, uid))
        await m.answer(f"✅ Toggled reseller for <code>{uid}</code>.", reply_markup=admin_kb())
    elif act == "direct":
        db("UPDATE users SET is_reseller=1 WHERE user_id=?", (uid,))
        db(
            "INSERT INTO reseller_requests (user_id, amount, status, created_at, reviewed_at) "
            "VALUES (?, 0, 'approved', ?, ?)",
            (uid, now_str(), now_str()),
        )
        log_activity(m.from_user.id, "DIRECT_RESELLER", f"user={uid}")
        await m.answer(
            f"🚨 <code>{uid}</code> activated as Direct Reseller.", reply_markup=admin_kb()
        )
        try:
            await bot.send_message(
                uid,
                "👑 <b>You are now a Reseller!</b>\n\nWholesale prices unlocked.",
                reply_markup=main_menu_kb(uid),
            )
        except Exception:
            pass
    await state.clear()


@dp.callback_query(F.data == "adm_res_view")
async def res_view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    rs = db(
        "SELECT user_id, first_name, balance FROM users WHERE is_reseller=1 LIMIT 50",
        all=True,
    )
    if not rs:
        return await call.message.edit_text("📭 No resellers.", reply_markup=bk("adm_reseller"))
    text = f"👑 <b>RESELLERS ({len(rs)})</b>\n━━━━━━━━━━━━━━━━━━\n"
    for r in rs:
        text += f"\n<code>{r[0]}</code> — {r[1] or 'N/A'} — {fmt(r[2])}"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_reseller"))


@dp.callback_query(F.data == "adm_res_allkeys")
async def res_allkeys(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    total = db("SELECT COUNT(*) FROM product_keys", one=True)[0]
    used = db("SELECT COUNT(*) FROM product_keys WHERE is_used=1", one=True)[0]
    free = total - used
    text = (
        f"🔑 <b>ALL KEYS OVERVIEW</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Total: <b>{total}</b>\n🟢 Free: <b>{free}</b>\n❌ Used: <b>{used}</b>"
    )
    await call.message.edit_text(text, reply_markup=bk("adm_reseller"))


@dp.callback_query(F.data == "adm_res_total")
async def res_total(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    total = db("SELECT COUNT(*) FROM users", one=True)[0]
    res = db("SELECT COUNT(*) FROM users WHERE is_reseller=1", one=True)[0]
    vip = db("SELECT COUNT(*) FROM users WHERE is_vip=1", one=True)[0]
    text = (
        f"📞 <b>USER STATS</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total: <b>{total}</b>\n"
        f"👑 Resellers: <b>{res}</b>\n"
        f"🌟 VIP: <b>{vip}</b>"
    )
    await call.message.edit_text(text, reply_markup=bk("adm_reseller"))


@dp.callback_query(F.data == "adm_res_tog")
async def res_tog(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("reseller_system_status", "ON")
    ss("reseller_system_status", "OFF" if cur == "ON" else "ON")
    await call.answer("✅ Toggled!")
    await adm_reseller(call)


@dp.callback_query(F.data == "adm_res_fee")
async def res_fee(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.res_fee)
    await call.message.edit_text("💰 Send new setup fee (₹):", reply_markup=bk("adm_reseller"))


@dp.message(A.res_fee)
async def res_fee_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("reseller_setup_fee", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_res_min")
async def res_min(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.res_min)
    await call.message.edit_text("💳 Send new minimum balance (₹):", reply_markup=bk("adm_reseller"))


@dp.message(A.res_min)
async def res_min_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("reseller_min_balance", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


async def _direct_reseller_apply(m: Message, uid: int):
    db("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)", (uid, now_str()))
    db("UPDATE users SET is_reseller=1 WHERE user_id=?", (uid,))
    await m.answer(f"🚨 <code>{uid}</code> activated as Direct Reseller.", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                  BROADCAST
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Send Broadcast", callback_data="adm_bc_send")],
        [InlineKeyboardButton(text="📜 History", callback_data="adm_bc_history")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text(
            "📢 <b>BROADCAST</b>\n\nSend text/photo/video/doc to all users.", reply_markup=kb
        )
    except Exception:
        await call.message.answer("📢 Broadcast", reply_markup=kb)


@dp.callback_query(F.data == "adm_bc_send")
async def bc_send_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.bc_msg)
    await call.message.edit_text(
        "📢 Send message (text/photo/video/doc):", reply_markup=bk("adm_broadcast")
    )


@dp.message(A.bc_msg)
async def bc_send_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    users = db("SELECT user_id FROM users", all=True)
    total = len(users or [])
    sent, failed = 0, 0
    status_msg = await m.answer(f"⏳ Broadcasting to {total} users...")
    for u in users or []:
        try:
            await m.send_copy(chat_id=u[0])
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    content = (m.text or m.caption or "[media]")[:200]
    db(
        "INSERT INTO broadcasts (content, sent, failed, created_at) VALUES (?, ?, ?, ?)",
        (content, sent, failed, now_str()),
    )
    try:
        await status_msg.edit_text(
            f"✅ <b>Broadcast Complete!</b>\n\n"
            f"🟢 Sent: {sent}\n🔴 Failed: {failed}\n📊 Total: {total}",
            reply_markup=admin_kb(),
        )
    except Exception:
        pass
    await state.clear()


@dp.callback_query(F.data == "adm_bc_history")
async def bc_history(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    hs = db(
        "SELECT id, content, sent, failed, created_at FROM broadcasts ORDER BY id DESC LIMIT 10",
        all=True,
    )
    if not hs:
        return await call.message.edit_text("📭 No broadcast history.", reply_markup=bk("adm_broadcast"))
    text = "📜 <b>BROADCAST HISTORY</b>\n━━━━━━━━━━━━━━━━━━\n"
    for h in hs:
        text += f"\n<b>#{h[0]}</b> — 📅 {h[4]}\n🟢 {h[2]} | 🔴 {h[3]}\n📝 {truncate(h[1], 100)}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_broadcast"))


# ══════════════════════════════════════════════════════════════
#                  MARKETING
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_mkt")
async def adm_mkt(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ Coupons", callback_data="adm_cp")],
        [InlineKeyboardButton(text="🎁 Daily Gift", callback_data="adm_gift")],
        [InlineKeyboardButton(text="🤝 Refer & Earn", callback_data="adm_ref")],
        [InlineKeyboardButton(text="📜 Set Product/Plan Discount", callback_data="adm_bulk_disc")],
        [InlineKeyboardButton(text="👤 Set All Products Normal", callback_data="adm_bulk_normal")],
        [InlineKeyboardButton(text="🧪 Set All Products Reseller", callback_data="adm_bulk_reseller")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("🎯 <b>MARKETING</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("🎯 Marketing", reply_markup=kb)


@dp.callback_query(F.data == "adm_cp")
async def adm_cp(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create", callback_data="adm_cp_add")],
        [InlineKeyboardButton(text="📋 View All", callback_data="adm_cp_view")],
        [InlineKeyboardButton(text="🗑️ Delete", callback_data="adm_cp_del_start")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_mkt")],
    ])
    try:
        await call.message.edit_text("🎟️ <b>COUPONS</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("🎟️ Coupons", reply_markup=kb)


@dp.callback_query(F.data == "adm_cp_add")
async def cp_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.cp_code)
    await call.message.edit_text("🎟️ Step 1/3: Send coupon code:", reply_markup=bk("adm_cp"))


@dp.message(A.cp_code)
async def cp_code_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    await state.update_data(cp_code=m.text.strip().upper())
    await state.set_state(A.cp_disc)
    await m.answer("💰 Step 2/3: Discount amount (₹):")


@dp.message(A.cp_disc)
async def cp_disc_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        d = float(m.text.strip())
    except Exception:
        return await m.answer("❌ Invalid number.")
    await state.update_data(cp_disc=d)
    await state.set_state(A.cp_max)
    await m.answer("🔢 Step 3/3: Max uses:")


@dp.message(A.cp_max)
async def cp_max_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        mx = int(m.text.strip())
    except Exception:
        return await m.answer("❌ Invalid number.")
    d = await state.get_data()
    db(
        "INSERT OR REPLACE INTO coupons (code, discount, max_uses, used, created_at) VALUES (?, ?, ?, 0, ?)",
        (d.get("cp_code"), d.get("cp_disc", 0), mx, now_str()),
    )
    await state.clear()
    await m.answer(f"✅ Coupon <b>{d.get('cp_code')}</b> created!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_cp_view")
async def cp_view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cps = db(
        "SELECT code, discount, max_uses, used, created_at FROM coupons ORDER BY created_at DESC",
        all=True,
    )
    if not cps:
        return await call.message.edit_text("📭 No coupons.", reply_markup=bk("adm_cp"))
    text = "🎟️ <b>COUPONS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for c in cps:
        text += f"\n<b>{c[0]}</b>\n💵 {fmt(c[1])} | Used {c[3]}/{c[2]}\n📅 {c[4]}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_cp"))


@dp.callback_query(F.data == "adm_cp_del_start")
async def cp_del_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.cp_del)
    await call.message.edit_text("🗑️ Send coupon code to delete:", reply_markup=bk("adm_cp"))


@dp.message(A.cp_del)
async def cp_del_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    code = m.text.strip().upper()
    db("DELETE FROM coupons WHERE code=?", (code,))
    await state.clear()
    await m.answer(f"🗑️ Coupon <b>{code}</b> deleted!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_gift")
async def adm_gift(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    cur = gs("daily_gift_price", "0")
    await state.set_state(A.set_gift)
    await call.message.edit_text(
        f"🎁 <b>Daily Gift</b>\n\nCurrent: {fmt(cur)}\n\nSend new amount (0 to disable):",
        reply_markup=bk("adm_mkt"),
    )


@dp.message(A.set_gift)
async def gift_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("daily_gift_price", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_ref")
async def adm_ref(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    cur = gs("refer_earn_amount", "0")
    await state.set_state(A.set_refer)
    await call.message.edit_text(
        f"🤝 <b>Refer Reward</b>\n\nCurrent: {fmt(cur)}\n\nSend reward amount (0 to disable):",
        reply_markup=bk("adm_mkt"),
    )


@dp.message(A.set_refer)
async def refer_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("refer_earn_amount", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_bulk_disc")
async def bulk_disc_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(bulk="disc")
    await state.set_state(A.bulk_discount_value)
    await call.message.edit_text(
        "📜 Send discount % (0-100) to apply on ALL plans:", reply_markup=bk("adm_mkt")
    )


@dp.callback_query(F.data == "adm_bulk_normal")
async def bulk_normal_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(bulk="normal")
    await state.set_state(A.bulk_discount_value)
    await call.message.edit_text(
        "👤 Send % to set on ALL plans' normal price (0-100):",
        reply_markup=bk("adm_mkt"),
    )


@dp.callback_query(F.data == "adm_bulk_reseller")
async def bulk_reseller_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(bulk="reseller")
    await state.set_state(A.bulk_discount_value)
    await call.message.edit_text(
        "🧪 Send % to apply on ALL plans for resellers (0-100):",
        reply_markup=bk("adm_mkt"),
    )


@dp.message(A.bulk_discount_value)
async def bulk_disc_all_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    try:
        v = int(m.text.strip())
        if v < 0 or v > 100:
            raise ValueError
    except ValueError:
        return await m.answer("❌ Enter 0-100.")
    d = await state.get_data()
    kind = d.get("bulk", "disc")
    if kind == "disc":
        db("UPDATE plans SET discount=?", (v,))
        await m.answer(f"✅ All plans set to {v}% discount.", reply_markup=admin_kb())
    elif kind == "normal":
        ss("normal_global_discount", str(v))
        await m.answer(f"✅ Normal global discount = {v}%", reply_markup=admin_kb())
    else:
        ss("reseller_global_discount", str(v))
        await m.answer(f"✅ Reseller global discount = {v}%", reply_markup=admin_kb())
    await state.clear()


# ══════════════════════════════════════════════════════════════
#                  PAYMENT SETTINGS
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_pay")
async def adm_pay(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    mode = gs("payment_mode", "manual")
    m = "🤖 AUTO" if mode == "auto" else "✋ MANUAL"
    upi = gs("upi_id") or "❌"
    qr = "✅" if gs("static_qr_file_id") else "❌"
    payee = gs("payee_name") or "—"
    binance = gs("binance_pay_id") or "❌"
    zapupi = "✅" if gs("zapupi_enabled", "0") == "1" else "❌"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⚙️ Mode: {m}", callback_data="adm_pay_mode")],
        [InlineKeyboardButton(text="💳 UPI Settings", callback_data="adm_pay_upi")],
        [InlineKeyboardButton(text="🟡 Binance Settings", callback_data="adm_pay_binance")],
        [InlineKeyboardButton(text="⚡ ZapUPI Settings", callback_data="adm_pay_zapupi")],
        [InlineKeyboardButton(text="🔌 Auto API", callback_data="adm_api_menu")],
        [InlineKeyboardButton(text="🎛️ Payment Options", callback_data="adm_pay_opts")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    text = (
        f"💳 <b>PAYMENT SETTINGS</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ Mode: <b>{m}</b>\n"
        f"🏦 UPI: <code>{truncate(upi, 20)}</code>\n"
        f"🏷️ Payee: {truncate(payee, 20)}\n"
        f"🖼️ Static QR: {qr}\n"
        f"🟡 Binance: <code>{truncate(binance, 20)}</code>\n"
        f"⚡ ZapUPI: {zapupi}"
    )
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "adm_pay_mode")
async def pay_mode_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("payment_mode", "manual")
    new = "auto" if cur == "manual" else "manual"
    ss("payment_mode", new)
    await call.answer(f"✅ Mode: {new.upper()}", show_alert=True)
    await adm_pay(call)


@dp.callback_query(F.data == "adm_pay_upi")
async def pay_upi_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    upi = gs("upi_id") or "❌"
    payee = gs("payee_name") or BRAND_NAME
    qr = "✅ Set" if gs("static_qr_file_id") else "❌"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🏦 UPI: {truncate(upi, 20)}", callback_data="adm_set_upi")],
        [InlineKeyboardButton(text=f"🏷️ Payee: {truncate(payee, 20)}", callback_data="adm_set_payee")],
        [InlineKeyboardButton(text=f"🖼️ Static QR: {qr}", callback_data="adm_set_qr")],
        [InlineKeyboardButton(text="🗑️ Remove QR", callback_data="adm_qr_remove")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_pay")],
    ])
    await call.message.edit_text("💳 <b>UPI SETTINGS</b>", reply_markup=kb)


@dp.callback_query(F.data == "adm_set_upi")
async def set_upi_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_upi)
    cur = gs("upi_id") or "Not set"
    await call.message.edit_text(
        f"🏦 Current UPI: <code>{cur}</code>\n\nSend new UPI ID:",
        reply_markup=bk("adm_pay_upi"),
    )


@dp.message(A.set_upi)
async def set_upi_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("upi_id", m.text.strip())
    await state.clear()
    await m.answer("✅ UPI saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_set_payee")
async def set_payee_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_payee)
    cur = gs("payee_name") or BRAND_NAME
    await call.message.edit_text(
        f"🏷️ Current Payee: <b>{cur}</b>\n\nSend new payee name:",
        reply_markup=bk("adm_pay_upi"),
    )


@dp.message(A.set_payee)
async def set_payee_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("payee_name", m.text.strip())
    await state.clear()
    await m.answer("✅ Payee saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_set_qr")
async def set_qr_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_qr)
    await call.message.edit_text("🖼️ Send QR image as photo:", reply_markup=bk("adm_pay_upi"))


@dp.message(A.set_qr, F.photo)
async def set_qr_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("static_qr_file_id", m.photo[-1].file_id)
    await state.clear()
    await m.answer("✅ Static QR saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_qr_remove")
async def qr_remove(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    ss("static_qr_file_id", "")
    await call.answer("✅ Removed!")
    await pay_upi_menu(call)


@dp.callback_query(F.data == "adm_pay_binance")
async def pay_binance_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    bid = gs("binance_pay_id") or "❌"
    bname = gs("binance_pay_name") or "—"
    enabled = gs("binance_enabled", "1") == "1"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🆔 Binance ID: {truncate(bid, 20)}", callback_data="adm_bin_id")],
        [InlineKeyboardButton(text=f"👤 Payee Name: {truncate(bname, 20)}", callback_data="adm_bin_name")],
        [InlineKeyboardButton(text="🖼️ Set QR", callback_data="adm_bin_qr")],
        [InlineKeyboardButton(text=f"💱 INR per USDT: {gs('binance_inr_per_usdt', '0')}", callback_data="adm_bin_rate")],
        [InlineKeyboardButton(text=f"🔛 Enabled: {'ON' if enabled else 'OFF'}", callback_data="adm_bin_tog")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_pay")],
    ])
    await call.message.edit_text("🟡 <b>BINANCE SETTINGS</b>", reply_markup=kb)


@dp.callback_query(F.data == "adm_bin_id")
async def bin_id_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_binance_id)
    await call.message.edit_text("🆔 Send Binance Pay ID:", reply_markup=bk("adm_pay_binance"))


@dp.message(A.set_binance_id)
async def bin_id_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("binance_pay_id", m.text.strip())
    await state.clear()
    await m.answer("✅ Binance ID saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_bin_name")
async def bin_name_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_binance_name)
    await call.message.edit_text("👤 Send Binance payee name:", reply_markup=bk("adm_pay_binance"))


@dp.message(A.set_binance_name)
async def bin_name_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("binance_pay_name", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_bin_qr")
async def bin_qr_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_binance_qr)
    await call.message.edit_text("🖼️ Send Binance QR as photo:", reply_markup=bk("adm_pay_binance"))


@dp.message(A.set_binance_qr, F.photo)
async def bin_qr_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("binance_qr_file_id", m.photo[-1].file_id)
    await state.clear()
    await m.answer("✅ Binance QR saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_bin_tog")
async def bin_tog(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("binance_enabled", "1")
    ss("binance_enabled", "0" if cur == "1" else "1")
    await call.answer("✅ Toggled!")
    await pay_binance_menu(call)


@dp.callback_query(F.data == "adm_pay_zapupi")
async def pay_zapupi_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    enabled = gs("zapupi_enabled", "0") == "1"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔛 Enabled: {'ON' if enabled else 'OFF'}", callback_data="adm_zap_tog")],
        [InlineKeyboardButton(text="🔑 Set Merchant ID", callback_data="adm_zap_mid")],
        [InlineKeyboardButton(text="🗝️ Set API Key", callback_data="adm_zap_key")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_pay")],
    ])
    webhook_ready = PUBLIC_BASE_URL.startswith("https://")
    key_ready = bool(gs("zapupi_key", "").strip())
    await call.message.edit_text(
        "⚡ <b>ZAPUPI SETTINGS</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"Status: {'✅ ON' if enabled else '❌ OFF'}\n"
        f"API key: {'✅ Saved' if key_ready else '❌ Missing'}\n"
        f"Public HTTPS webhook: {'✅ ' + _safe_html(PUBLIC_BASE_URL) if webhook_ready else '❌ Set PUBLIC_BASE_URL (or use Render external URL)'}\n\n"
        "Automatic credit/delivery is enabled only after the server verifies the provider order-status API. Preview buttons never credit payments.",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "adm_zap_tog")
async def zap_tog(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("zapupi_enabled", "0")
    ss("zapupi_enabled", "0" if cur == "1" else "1")
    await call.answer("✅ Toggled!")
    await pay_zapupi_menu(call)


@dp.callback_query(F.data == "adm_zap_mid")
async def zap_mid_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(zap="merchant")
    await state.set_state(A.set_api_key)
    await call.message.edit_text("🔑 Send ZapUPI Merchant ID:", reply_markup=bk("adm_pay_zapupi"))


@dp.callback_query(F.data == "adm_zap_key")
async def zap_key_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(zap="key")
    await state.set_state(A.set_api_key)
    await call.message.edit_text("🗝️ Send ZapUPI API Key:", reply_markup=bk("adm_pay_zapupi"))


@dp.callback_query(F.data == "adm_pay_opts")
async def pay_opts(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    upi_on = gs("pay_upi_enabled", "1") == "1"
    bin_on = gs("pay_binance_enabled", "1") == "1"
    cpn_on = gs("coupon_on_order", "1") == "1"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 UPI: {'ON' if upi_on else 'OFF'}", callback_data="adm_opt_upi")],
        [InlineKeyboardButton(text=f"🟡 Binance: {'ON' if bin_on else 'OFF'}", callback_data="adm_opt_bin")],
        [InlineKeyboardButton(text=f"🎟️ Coupon on Order: {'ON' if cpn_on else 'OFF'}", callback_data="adm_opt_cpn")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_pay")],
    ])
    await call.message.edit_text("🎛️ <b>PAYMENT OPTIONS</b>", reply_markup=kb)


@dp.callback_query(F.data == "adm_opt_upi")
async def opt_upi(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("pay_upi_enabled", "1")
    ss("pay_upi_enabled", "0" if cur == "1" else "1")
    await call.answer("✅ Toggled!")
    await pay_opts(call)


@dp.callback_query(F.data == "adm_opt_bin")
async def opt_bin(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("pay_binance_enabled", "1")
    ss("pay_binance_enabled", "0" if cur == "1" else "1")
    await call.answer("✅ Toggled!")
    await pay_opts(call)


@dp.callback_query(F.data == "adm_opt_cpn")
async def opt_cpn(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("coupon_on_order", "1")
    ss("coupon_on_order", "0" if cur == "1" else "1")
    await call.answer("✅ Toggled!")
    await pay_opts(call)


@dp.callback_query(F.data == "adm_api_menu")
async def adm_api_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    enabled = gs("auto_api_enabled", "0") == "1"
    url = gs("auto_api_url") or "(not set)"
    key = gs("auto_api_key") or "(not set)"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔛 Toggle: {'ON' if enabled else 'OFF'}", callback_data="adm_api_toggle")],
        [InlineKeyboardButton(text="🔑 Set API Key", callback_data="adm_api_setkey")],
        [InlineKeyboardButton(text="🌐 Set API URL", callback_data="adm_api_seturl")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_pay")],
    ])
    await call.message.edit_text(
        f"🔌 <b>AUTO PAYMENT API</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"Status: {'✅ ON' if enabled else '❌ OFF'}\n"
        f"🌐 URL: <code>{truncate(url, 60)}</code>\n"
        f"🔑 Key: <code>{truncate(key, 40)}</code>",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "adm_api_toggle")
async def api_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("auto_api_enabled", "0")
    ss("auto_api_enabled", "0" if cur == "1" else "1")
    await call.answer("✅ Toggled!")
    await adm_api_menu(call)


@dp.callback_query(F.data == "adm_api_setkey")
async def api_setkey_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(api_field="key")
    await state.set_state(A.set_api_key)
    await call.message.edit_text("🔑 Send API key:", reply_markup=bk("adm_api_menu"))


@dp.message(A.set_api_key)
async def api_setkey_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    d = await state.get_data()
    field = d.get("api_field", "key")
    zap = d.get("zap")
    if zap == "merchant":
        ss("zapupi_merchant", m.text.strip())
    elif zap == "key":
        ss("zapupi_key", m.text.strip())
    elif field == "url":
        ss("auto_api_url", m.text.strip())
    else:
        ss("auto_api_key", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_api_seturl")
async def api_seturl_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.update_data(api_field="url")
    await state.set_state(A.set_api_url)
    await call.message.edit_text("🌐 Send API URL:", reply_markup=bk("adm_api_menu"))


@dp.message(A.set_api_url)
async def api_seturl_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("auto_api_url", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                  ORDER PAYMENT APPROVAL
# ══════════════════════════════════════════════════════════════

def finalize_plan_payment(oid: str, auto_verified: bool = False):
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        tx = conn.execute(
            "SELECT user_id, amount, status, purpose, plan_id, coupon_code FROM transactions WHERE order_id=?",
            (oid,),
        ).fetchone()
        if not tx:
            conn.rollback()
            return {"status": "not_found"}
        uid, amount, tx_status, purpose, plan_id, coupon_code = tx
        if purpose != "order":
            conn.rollback()
            return {"status": "wrong_purpose"}
        if tx_status == "paid":
            conn.rollback()
            return {"status": "already_processed"}
        if tx_status != "pending":
            conn.rollback()
            return {"status": "not_pending"}

        req = conn.execute(
            "SELECT id, user_id, status, reference FROM balance_requests "
            "WHERE reference LIKE ? ORDER BY id DESC LIMIT 1",
            (f"{oid}|PLAN:%",),
        ).fetchone()
        auto_created_request = False
        if not req and auto_verified:
            user = conn.execute("SELECT username FROM users WHERE user_id=?", (uid,)).fetchone()
            cur = conn.execute(
                "INSERT INTO balance_requests "
                "(user_id, username, amount, method, proof_file_id, reference, status, created_at) "
                "VALUES (?, ?, ?, 'auto', '', ?, 'pending', ?)",
                (
                    uid,
                    user[0] if user and user[0] else "",
                    amount,
                    f"{oid}|PLAN:{plan_id}|UTR:AUTO",
                    now_str(),
                ),
            )
            req = (cur.lastrowid, uid, "pending", f"{oid}|PLAN:{plan_id}|UTR:AUTO")
            auto_created_request = True
        if not req:
            conn.rollback()
            return {"status": "no_request"}
        req_id, req_uid, req_status, ref = req
        if req_uid != uid:
            conn.rollback()
            return {"status": "request_user_mismatch"}
        if req_status != "pending":
            conn.rollback()
            return {"status": "request_not_pending"}

        if not plan_id:
            try:
                plan_id = int(
                    next(x.split(":", 1)[1] for x in ref.split("|") if x.startswith("PLAN:"))
                )
            except (StopIteration, ValueError, IndexError):
                conn.rollback()
                return {"status": "invalid_plan"}
        plan = conn.execute(
            "SELECT id, name, product_id FROM plans WHERE id=?", (plan_id,)
        ).fetchone()
        if not plan:
            conn.rollback()
            return {"status": "invalid_plan"}
        product = conn.execute(
            "SELECT p.name, c.name FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.id=?", (plan[2],)
        ).fetchone()
        key = conn.execute(
            "SELECT id, key_text FROM product_keys WHERE plan_id=? AND is_used=0 ORDER BY id LIMIT 1",
            (plan_id,),
        ).fetchone()
        if not key:
            if auto_created_request:
                conn.commit()
            else:
                conn.rollback()
            return {
                "status": "no_stock",
                "user_id": uid,
                "amount": amount,
                "plan_id": plan_id,
                "request_id": req_id,
                "product_name": product[0] if product else "",
                "plan_name": plan[1],
            }

        cur = conn.execute(
            "UPDATE product_keys SET is_used=1, used_by=?, used_at=? WHERE id=? AND is_used=0",
            (uid, now_str(), key[0]),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return {"status": "retry"}
        cur = conn.execute(
            "UPDATE transactions SET status='paid' WHERE order_id=? AND status='pending'", (oid,)
        )
        if cur.rowcount != 1:
            conn.rollback()
            return {"status": "already_processed"}
        if coupon_code:
            # The discounted amount was fixed when the pending transaction was created.
            # Count the coupon only if it still exists and has remaining quota; never block paid delivery.
            conn.execute(
                "UPDATE coupons SET used=used+1 WHERE code=? COLLATE NOCASE AND used < max_uses",
                (coupon_code,),
            )
        conn.execute(
            "UPDATE balance_requests SET status='approved', reviewed_at=? WHERE id=? AND status='pending'",
            (now_str(), req_id),
        )
        conn.execute(
            "INSERT INTO orders (user_id, plan_id, plan_name, product_name, category_name, price_paid, delivered_key, purchase_date, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'delivered')",
            (uid, plan[0], plan[1], product[0] if product else "", product[1] if product else "", amount, key[1], now_str()),
        )
        conn.execute(
            "UPDATE users SET total_spent=total_spent+?, total_orders=total_orders+1 WHERE user_id=?",
            (amount, uid),
        )
        conn.commit()
        return {
            "status": "success",
            "user_id": uid,
            "amount": amount,
            "plan_id": plan[0],
            "plan_name": plan[1],
            "product_name": product[0] if product else "",
            "category_name": product[1] if product else "",
            "key": key[1],
            "request_id": req_id,
        }
    except Exception:
        conn.rollback()
        logger.exception("Could not finalize plan payment %s", oid)
        return {"status": "error"}
    finally:
        conn.close()


async def send_plan_delivery(result: dict, oid: str):
    text = (
        f"🎉 <b>ORDER DELIVERED!</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"📦 {result.get('product_name') or 'N/A'}\n"
        f"⏱ {result.get('plan_name') or 'Plan'}\n"
        f"💰 {fmt(result.get('amount', 0))}\n"
        f"🔑 <b>YOUR KEY:</b>\n<code>{result.get('key', '')}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n{gs('ui_key_msg')}"
    )
    try:
        await bot.send_message(result["user_id"], text, reply_markup=main_menu_kb(result["user_id"]))
    except Exception:
        logger.exception("Could not send delivered key for order %s", oid)
        try:
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ <b>DELIVERY SEND FAILED</b>\nOrder: <code>{oid}</code>\n"
                f"User: <code>{result.get('user_id')}</code>\nKey: <code>{result.get('key', '')}</code>\n"
                "Please contact user and deliver manually.",
            )
        except Exception:
            pass


@dp.callback_query(F.data.startswith("bautocheck_"))
async def buy_auto_check(call: CallbackQuery):
    oid = call.data[11:]
    tx = db(
        "SELECT user_id, amount, status, purpose, method, plan_id FROM transactions WHERE order_id=?",
        (oid,),
        one=True,
    )
    if not tx or tx[0] != call.from_user.id or tx[3] != "order":
        return await call.answer("❌ Not your payment.", show_alert=True)
    if tx[2] == "paid":
        return await call.answer("✅ Already processed.", show_alert=True)
    if tx[2] != "pending":
        return await call.answer("⚠️ Not pending.", show_alert=True)
    if gs("payment_mode") != "auto":
        return await call.answer("⏳ Auto verification is OFF.", show_alert=True)

    try:
        verified, detail = await _verify_payment_with_api(oid, tx, tx[5])
        if not verified:
            return await call.answer(f"⏳ {str(detail)[:180]}", show_alert=True)

        result = finalize_plan_payment(oid, auto_verified=True)
        if result["status"] == "success":
            await call.answer("✅ Verified; key being delivered.", show_alert=True)
            await send_plan_delivery(result, oid)
            return
        if result["status"] == "no_stock":
            await call.answer(
                "✅ Verified but out of stock. Admin notified.", show_alert=True
            )
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>PAYMENT VERIFIED — STOCK EMPTY</b>\n"
                    f"Order: <code>{oid}</code>\nUser: <code>{tx[0]}</code>\n"
                    f"Plan: {result.get('plan_name')}\nAmount: {fmt(tx[1])}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="✅ Approve & Deliver", callback_data=f"order_approve_{oid}")
                    ]]),
                )
            except Exception:
                pass
            return
        messages = {
            "already_processed": "✅ Already processed.",
            "not_pending": "⚠️ Not pending.",
            "request_not_pending": "⚠️ Reviewed.",
            "no_request": "⚠️ No request. Contact support.",
            "invalid_plan": "⚠️ Invalid plan.",
        }
        await call.answer(
            messages.get(result["status"], "⚠️ Could not finalize."), show_alert=True
        )
    except Exception as e:
        logger.exception("Auto-verify failed for %s", oid)
        await call.answer(f"⚠️ Error: {str(e)[:80]}", show_alert=True)


@dp.callback_query(F.data.startswith("order_approve_"))
async def order_approve(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Admin only.", show_alert=True)
    oid = call.data[14:]
    result = finalize_plan_payment(oid, auto_verified=False)
    if result["status"] != "success":
        messages = {
            "not_found": "❌ Order not found.",
            "wrong_purpose": "❌ Not a plan payment.",
            "already_processed": "✅ Already processed.",
            "not_pending": "⚠️ Not pending.",
            "request_not_pending": "⚠️ Reviewed.",
            "request_user_mismatch": "❌ User mismatch.",
            "no_request": "❌ Proof not found.",
            "invalid_plan": "❌ Plan invalid.",
            "no_stock": "❌ No key stock.",
            "retry": "⚠️ Stock changed. Retry.",
        }
        return await call.answer(messages.get(result["status"], "❌ Failed."), show_alert=True)
    await call.answer("✅ Approved and delivered!")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    log_activity(call.from_user.id, "ORDER_APPROVED", f"order={oid}; user={result['user_id']}")
    await send_plan_delivery(result, oid)


@dp.callback_query(F.data.startswith("order_reject_"))
async def order_reject(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Admin only.", show_alert=True)
    oid = call.data[13:]
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        tx = conn.execute(
            "SELECT status, purpose FROM transactions WHERE order_id=?", (oid,)
        ).fetchone()
        if not tx or tx[1] != "order":
            conn.rollback()
            return await call.answer("❌ Not a plan payment.", show_alert=True)
        if tx[0] != "pending":
            conn.rollback()
            return await call.answer("⚠️ Not pending.", show_alert=True)
        req = conn.execute(
            "SELECT id, user_id FROM balance_requests WHERE reference LIKE ? AND status='pending' ORDER BY id DESC LIMIT 1",
            (f"{oid}|PLAN:%",),
        ).fetchone()
        if not req:
            conn.rollback()
            return await call.answer("❌ Pending proof not found.", show_alert=True)
        conn.execute(
            "UPDATE balance_requests SET status='rejected', reviewed_at=? WHERE id=? AND status='pending'",
            (now_str(), req[0]),
        )
        conn.execute(
            "UPDATE transactions SET status='rejected' WHERE order_id=? AND status='pending'", (oid,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Reject failed %s", oid)
        return await call.answer("⚠️ DB error.", show_alert=True)
    finally:
        conn.close()
    await call.answer("❌ Rejected.")
    try:
        await bot.send_message(
            req[1], "❌ Payment rejected. Contact support.", reply_markup=main_menu_kb(req[1])
        )
    except Exception:
        pass
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@dp.callback_query(F.data.startswith("autocheck_"))
async def auto_check(call: CallbackQuery):
    oid = call.data[10:]
    tx = db(
        "SELECT user_id, amount, status, purpose, method, plan_id FROM transactions WHERE order_id=?",
        (oid,),
        one=True,
    )
    if not tx or tx[0] != call.from_user.id or tx[3] != "balance":
        return await call.answer("❌ Not your payment.", show_alert=True)
    if tx[2] == "paid":
        return await call.answer("✅ Already credited.", show_alert=True)
    if tx[2] != "pending":
        return await call.answer("⚠️ Not pending.", show_alert=True)
    if gs("payment_mode") != "auto":
        return await call.answer("⏳ Auto OFF.", show_alert=True)

    try:
        verified, detail = await _verify_payment_with_api(oid, tx, None)
        if not verified:
            return await call.answer(f"⏳ {str(detail)[:180]}", show_alert=True)

        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            conn.execute("BEGIN IMMEDIATE")
            fresh = conn.execute(
                "SELECT user_id, amount, status, purpose FROM transactions WHERE order_id=?",
                (oid,),
            ).fetchone()
            if not fresh or fresh[0] != call.from_user.id or fresh[3] != "balance":
                conn.rollback()
                return await call.answer("❌ Not found.", show_alert=True)
            if fresh[2] == "paid":
                conn.rollback()
                return await call.answer("✅ Credited.", show_alert=True)
            if fresh[2] != "pending":
                conn.rollback()
                return await call.answer("⚠️ Not pending.", show_alert=True)
            conn.execute(
                "UPDATE transactions SET status='paid' WHERE order_id=? AND status='pending'", (oid,)
            )
            conn.execute(
                "UPDATE users SET balance=balance+? WHERE user_id=?", (fresh[1], fresh[0])
            )
            conn.execute(
                "UPDATE balance_requests SET status='approved', reviewed_at=? WHERE reference LIKE ? AND status='pending'",
                (now_str(), f"{oid}%"),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        await call.answer("✅ Verified and credited.")
        text = f"✅ <b>Payment Verified!</b>\n\n+{fmt(tx[1])} added."
        try:
            await call.message.edit_caption(caption=text, reply_markup=main_menu_kb(call.from_user.id))
        except Exception:
            try:
                await call.message.edit_text(text, reply_markup=main_menu_kb(call.from_user.id))
            except Exception:
                await bot.send_message(call.from_user.id, text, reply_markup=main_menu_kb(call.from_user.id))
    except Exception as e:
        logger.exception("Auto balance verify failed %s", oid)
        await call.answer(f"⚠️ Error: {str(e)[:80]}", show_alert=True)


@dp.callback_query(F.data.startswith("credit_"))
async def admin_credit(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Admin only.", show_alert=True)
    oid = call.data[7:]
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        tx = conn.execute(
            "SELECT user_id, amount, status, purpose FROM transactions WHERE order_id=?", (oid,)
        ).fetchone()
        if not tx or tx[3] != "balance":
            conn.rollback()
            return await call.answer("❌ Balance payment not found.", show_alert=True)
        if tx[2] == "paid":
            conn.rollback()
            return await call.answer("✅ Already credited.", show_alert=True)
        if tx[2] != "pending":
            conn.rollback()
            return await call.answer("⚠️ Not pending.", show_alert=True)
        req = conn.execute(
            "SELECT id, user_id FROM balance_requests WHERE reference LIKE ? AND status='pending' ORDER BY id DESC LIMIT 1",
            (f"{oid}%",),
        ).fetchone()
        if not req or req[1] != tx[0]:
            conn.rollback()
            return await call.answer("❌ Proof not found.", show_alert=True)
        conn.execute(
            "UPDATE transactions SET status='paid' WHERE order_id=? AND status='pending'", (oid,)
        )
        conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (tx[1], tx[0]))
        conn.execute(
            "UPDATE balance_requests SET status='approved', reviewed_at=? WHERE id=? AND status='pending'",
            (now_str(), req[0]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Credit failed %s", oid)
        return await call.answer("⚠️ DB error.", show_alert=True)
    finally:
        conn.close()
    await call.answer("✅ Credited!")
    try:
        await bot.send_message(
            tx[0],
            f"✅ <b>Payment Verified!</b>\n\n+{fmt(tx[1])} added.",
            reply_markup=main_menu_kb(tx[0]),
        )
    except Exception:
        pass
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    log_activity(call.from_user.id, "BAL_PAY_APPROVED", f"order={oid}; user={tx[0]}")


@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Admin only.", show_alert=True)
    oid = call.data[7:]
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        tx = conn.execute(
            "SELECT user_id, status, purpose FROM transactions WHERE order_id=?", (oid,)
        ).fetchone()
        if not tx or tx[2] != "balance":
            conn.rollback()
            return await call.answer("❌ Not found.", show_alert=True)
        if tx[1] != "pending":
            conn.rollback()
            return await call.answer("⚠️ Not pending.", show_alert=True)
        req = conn.execute(
            "SELECT id, user_id FROM balance_requests WHERE reference LIKE ? AND status='pending' ORDER BY id DESC LIMIT 1",
            (f"{oid}%",),
        ).fetchone()
        if not req or req[1] != tx[0]:
            conn.rollback()
            return await call.answer("❌ Proof not found.", show_alert=True)
        conn.execute(
            "UPDATE transactions SET status='rejected' WHERE order_id=? AND status='pending'", (oid,)
        )
        conn.execute(
            "UPDATE balance_requests SET status='rejected', reviewed_at=? WHERE id=? AND status='pending'",
            (now_str(), req[0]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Reject failed %s", oid)
        return await call.answer("⚠️ DB error.", show_alert=True)
    finally:
        conn.close()
    await call.answer("❌ Rejected.")
    try:
        await bot.send_message(
            tx[0], "❌ Payment rejected. Contact support.", reply_markup=main_menu_kb(tx[0])
        )
    except Exception:
        pass
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


logger.info("✅ PART 4 loaded — Users + Balance + Reseller + Broadcast + Payment + Approval ready")
# ══════════════════════════════════════════════════════════════
#                   END OF PART 4 (Continues in Part 5)
# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
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
        f"📱 Current: {cur}\n\nSend WhatsApp support URL:",
        reply_markup=bk("adm_links"),
    )


@dp.message(A.set_wa)
async def set_wa_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Please send text.")
    ss("support_whatsapp", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


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
    app.router.add_post("/zapupi/webhook", zapupi_webhook)
    if gs("zapupi_enabled", "0") == "1" and not PUBLIC_BASE_URL.startswith("https://"):
        logger.warning("ZapUPI is enabled but PUBLIC_BASE_URL/RENDER_EXTERNAL_URL is not an HTTPS URL; automatic webhook confirmation will not work.")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    logger.info(f"✅ Web server running on port {WEB_PORT}")


# ══════════════════════════════════════════════════════════════
#               SETTINGS / CO-ADMIN / OWNER TRANSFER
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_settings")
async def adm_settings(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼️ Set Welcome Logo / Media", callback_data="adm_set_logo")],
        [InlineKeyboardButton(text="✈️ Support Telegram", callback_data="adm_set_tg")],
        [InlineKeyboardButton(text="📱 Support WhatsApp", callback_data="adm_set_wa")],
        [InlineKeyboardButton(text="👑 Transfer Ownership", callback_data="adm_transfer_owner")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    await call.answer()
    await _edit_or_send(call, "⚙️ <b>BOT SETTINGS</b>\n\nManage welcome media, support links, and ownership.", kb)


@dp.callback_query(F.data == "adm_set_logo")
async def set_logo_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    await state.clear()
    await state.set_state(A.set_logo)
    await call.answer()
    await _edit_or_send(call, "🖼️ Send a photo, animation/GIF, or video to use as the welcome media. Send `none` to remove the media.", bk("adm_settings"))


@dp.message(A.set_logo)
async def set_logo_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if m.photo:
        ss("admin_logo_file_id", m.photo[-1].file_id)
        ss("admin_logo_media_type", "photo")
    elif m.animation:
        ss("admin_logo_file_id", m.animation.file_id)
        ss("admin_logo_media_type", "animation")
    elif m.video:
        ss("admin_logo_file_id", m.video.file_id)
        ss("admin_logo_media_type", "video")
    elif m.text and m.text.strip().lower() == "none":
        ss("admin_logo_file_id", "")
        ss("admin_logo_media_type", "photo")
    else:
        return await m.answer("Send a photo, animation, video, or `none`.")
    await state.clear()
    await m.answer("✅ Welcome media setting saved.", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_maint")
async def adm_maint(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    current = gs("global_maintenance", "0") == "1"
    new_value = "0" if current else "1"
    ss("global_maintenance", new_value)
    await call.answer(f"Global maintenance {'OFF' if new_value == '0' else 'ON'}", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔧 Global Maintenance: {'ON' if new_value == '1' else 'OFF'} (toggle)", callback_data="adm_maint")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    await _edit_or_send(call, f"🛠️ <b>MAINTENANCE</b>\n\nStatus: <b>{'ON' if new_value == '1' else 'OFF'}</b>\n\nWhen enabled, regular users cannot use the bot; admins remain able to manage it.", kb)


@dp.callback_query(F.data == "adm_coadmin")
async def adm_coadmin(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer("Only the owner can manage co-admins.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Co-Admin", callback_data="adm_coadmin_add")],
        [InlineKeyboardButton(text="➖ Remove Co-Admin", callback_data="adm_coadmin_remove")],
        [InlineKeyboardButton(text="📋 List Co-Admins", callback_data="adm_coadmin_list")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    await call.answer()
    await _edit_or_send(call, "🤝 <b>CO-ADMIN MANAGER</b>\n\nOnly the owner can add or remove co-admin access.", kb)


@dp.callback_query(F.data == "adm_coadmin_add")
async def coadmin_add_start(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return await call.answer("Owner only.", show_alert=True)
    await state.clear()
    await state.set_state(A.coadmin_add)
    await call.answer()
    await _edit_or_send(call, "Send the numeric Telegram user ID to grant co-admin access:", bk("adm_coadmin"))


@dp.message(A.coadmin_add)
async def coadmin_add_save(m: Message, state: FSMContext):
    if not is_owner(m.from_user.id):
        return
    if not m.text or not m.text.strip().isdigit():
        return await m.answer("Send a numeric Telegram user ID.")
    uid = int(m.text.strip())
    if uid <= 0 or uid == ADMIN_ID:
        return await m.answer("That ID cannot be added as a co-admin.")
    db("INSERT OR REPLACE INTO co_admins (user_id,name,added_at) VALUES (?,?,?)", (uid, "", now_str()))
    await state.clear()
    await m.answer(f"✅ <code>{uid}</code> granted co-admin access.", reply_markup=admin_kb())
    try:
        await bot.send_message(uid, "🤝 You have been granted co-admin access to ELITE X CONFIG.")
    except Exception:
        logger.info("Could not notify new co-admin %s", uid)
    log_activity(m.from_user.id, "COADMIN_ADD", str(uid))


@dp.callback_query(F.data == "adm_coadmin_remove")
async def coadmin_remove_start(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return await call.answer("Owner only.", show_alert=True)
    await state.clear()
    await state.set_state(A.coadmin_remove)
    await call.answer()
    await _edit_or_send(call, "Send the Telegram user ID whose co-admin access should be removed:", bk("adm_coadmin"))


@dp.message(A.coadmin_remove)
async def coadmin_remove_save(m: Message, state: FSMContext):
    if not is_owner(m.from_user.id):
        return
    if not m.text or not m.text.strip().isdigit():
        return await m.answer("Send a numeric Telegram user ID.")
    uid = int(m.text.strip())
    cur = db("DELETE FROM co_admins WHERE user_id=?", (uid,))
    await state.clear()
    await m.answer(f"✅ Co-admin removal processed for <code>{uid}</code>.", reply_markup=admin_kb())
    log_activity(m.from_user.id, "COADMIN_REMOVE", str(uid))


@dp.callback_query(F.data == "adm_coadmin_list")
async def coadmin_list(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer("Owner only.", show_alert=True)
    rows = db("SELECT user_id,name,added_at FROM co_admins ORDER BY added_at DESC", all=True) or []
    if not rows:
        return await _edit_or_send(call, "📭 No co-admins configured.", bk("adm_coadmin"))
    text = "🤝 <b>CO-ADMINS</b>\n━━━━━━━━━━━━━━━━━━\n"
    buttons = []
    for row in rows[:40]:
        text += f"\n👤 <code>{row[0]}</code> · { _safe_html(row[1] or 'Co-Admin') } · {row[2] or 'N/A'}"
        buttons.append([InlineKeyboardButton(text=f"➖ Remove {row[0]}", callback_data=f"coadmin_remove_{row[0]}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_coadmin")])
    await call.answer()
    await _edit_or_send(call, text[:3900], InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data.startswith("coadmin_remove_"))
async def coadmin_remove_one(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return await call.answer("Owner only.", show_alert=True)
    uid = sint(call.data[len("coadmin_remove_"):])
    db("DELETE FROM co_admins WHERE user_id=?", (uid,))
    log_activity(call.from_user.id, "COADMIN_REMOVE", str(uid))
    await coadmin_list(call)


@dp.callback_query(F.data == "adm_transfer_owner")
async def transfer_owner_start(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return await call.answer("Only the current owner can transfer ownership.", show_alert=True)
    await state.clear()
    await state.set_state(A.transfer_confirm)
    await state.update_data(transfer_step="enter_id")
    await call.answer()
    await _edit_or_send(call, "👑 <b>TRANSFER OWNERSHIP</b>\n\nSend the Telegram user ID of the new owner. They must have started the bot first.", bk("adm_settings"))


@dp.message(A.transfer_confirm)
async def transfer_owner_id_save(m: Message, state: FSMContext):
    if not is_owner(m.from_user.id):
        return
    data = await state.get_data()
    if data.get("transfer_step") != "enter_id":
        return await m.answer("Use the confirmation buttons to finish the transfer.")
    if not m.text or not m.text.strip().isdigit():
        return await m.answer("Send a numeric Telegram user ID.")
    new_id = int(m.text.strip())
    if new_id <= 0 or new_id == ADMIN_ID:
        return await m.answer("That user ID is invalid or is already the owner.")
    exists = db("SELECT user_id FROM users WHERE user_id=?", (new_id,), one=True)
    if not exists:
        return await m.answer("That user has not started this bot yet. Ask them to send /start, then try again.")
    await state.update_data(transfer_step="confirm", transfer_target_id=new_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Confirm Transfer", callback_data="transfer_owner_yes"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="transfer_owner_no"),
    ]])
    await m.answer(f"⚠️ Transfer bot ownership from <code>{ADMIN_ID}</code> to <code>{new_id}</code>? This changes who is treated as the owner.", reply_markup=kb)


@dp.callback_query(F.data == "transfer_owner_no")
async def transfer_owner_cancel(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return await call.answer("Owner only.", show_alert=True)
    await state.clear()
    await call.answer("Transfer cancelled.")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@dp.callback_query(F.data == "transfer_owner_yes")
async def transfer_owner_confirm(call: CallbackQuery, state: FSMContext):
    global ADMIN_ID, STATIC_ADMIN_IDS
    if not is_owner(call.from_user.id):
        return await call.answer("Only the current owner can confirm.", show_alert=True)
    data = await state.get_data()
    new_id = sint(data.get("transfer_target_id", 0))
    if data.get("transfer_step") != "confirm" or new_id <= 0:
        await state.clear()
        return await call.answer("No pending transfer found.", show_alert=True)
    if not db("SELECT user_id FROM users WHERE user_id=?", (new_id,), one=True):
        await state.clear()
        return await call.answer("New owner account no longer exists in the user database.", show_alert=True)
    old_id = ADMIN_ID
    ADMIN_ID = new_id
    STATIC_ADMIN_IDS = set(_CONFIGURED_ADMIN_IDS) | {new_id}
    ss("owner_id", str(new_id))
    await state.clear()
    await call.answer("Ownership transferred.", show_alert=True)
    try:
        await bot.send_message(new_id, "👑 <b>You are now the bot owner.</b> Use /admin to manage the bot.")
    except Exception:
        pass
    try:
        await call.message.edit_text(f"✅ Ownership transferred from <code>{old_id}</code> to <code>{new_id}</code>.")
    except Exception:
        pass
    log_activity(old_id, "OWNER_TRANSFER", f"new_owner={new_id}")


# ══════════════════════════════════════════════════════════════
#                     BINANCE CONVERSION RATE
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_bin_rate")
async def bin_rate_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    await state.clear()
    await state.set_state(A.set_binance_rate)
    current = gs("binance_inr_per_usdt", "0")
    await call.answer()
    await _edit_or_send(call, f"💱 Current rate: <code>1 USDT = {current} INR</code>\n\nSend the INR value of 1 USDT. Enter 0 to disable Binance checkout. Set this from your trusted exchange quote; the bot does not fetch a live rate.", bk("adm_pay_binance"))


@dp.message(A.set_binance_rate)
async def bin_rate_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    if not m.text:
        return await m.answer("Send a numeric INR-per-USDT rate.")
    try:
        rate = float(m.text.strip())
        if rate < 0 or rate > 10000000:
            raise ValueError
    except ValueError:
        return await m.answer("Enter a number from 0 to 10000000.")
    ss("binance_inr_per_usdt", f"{rate:.6f}".rstrip("0").rstrip("."))
    await state.clear()
    await m.answer("✅ Binance conversion rate saved. Binance will be offered only when the rate is greater than zero.", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                    MULTI-ENDPOINT API MANAGER
# ══════════════════════════════════════════════════════════════

def _api_config_for_plan(plan_id: Optional[int] = None) -> Optional[dict]:
    """Resolve plan-specific endpoint first, then fall back to the configured global API."""
    if plan_id:
        row = db(
            """SELECT e.url,e.api_key,e.provider,e.name,v.variant,e.id
               FROM plan_api_variant v JOIN api_endpoints e ON e.id=v.api_id
               WHERE v.plan_id=? AND e.is_active=1""",
            (plan_id,), one=True,
        )
        if row and row[0]:
            return {"url": row[0], "api_key": row[1] or "", "provider": row[2] or "custom",
                    "name": row[3] or "Endpoint", "variant": row[4] or "", "api_id": row[5]}
    url = gs("auto_api_url")
    if url and gs("auto_api_enabled", "0") == "1":
        return {"url": url, "api_key": gs("auto_api_key"), "provider": "custom",
                "name": "Global Auto API", "variant": "", "api_id": 0}
    return None


async def _verify_payment_with_api(oid: str, tx: tuple, plan_id: Optional[int] = None):
    cfg = _api_config_for_plan(plan_id)
    if not cfg or not cfg.get("url"):
        return False, "Auto verification API is not configured."
    params = {
        "order_id": oid,
        "api_key": cfg.get("api_key", ""),
        "amount": str(tx[1] if len(tx) > 1 else ""),
        "user_id": str(tx[0] if tx else ""),
        "method": str(tx[4] if len(tx) > 4 else ""),
        "plan_id": str(plan_id or ""),
        "variant": cfg.get("variant", ""),
        "provider": cfg.get("provider", "custom"),
    }
    provider = str(cfg.get("provider", "custom")).lower()
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            if provider == "zapupi":
                zap_key = gs("zapupi_key", "").strip() or cfg.get("api_key", "")
                endpoint = "https://pay.zapupi.com/api/order-status"
                async with session.post(endpoint, json={"zap_key": zap_key, "order_id": oid}) as resp:
                    result = await resp.json(content_type=None)
            else:
                if provider == "binance":
                    params["merchant_id"] = gs("binance_pay_id")
                async with session.get(cfg["url"], params=params) as resp:
                    if resp.status != 200:
                        return False, f"Payment provider returned HTTP {resp.status}."
                    result = await resp.json(content_type=None)
        if not isinstance(result, dict):
            return False, "Provider returned an unexpected response."
        if provider == "zapupi":
            if str(result.get("status", "")).lower() != "success":
                return False, str(result.get("message", "ZapUPI has not confirmed payment."))
            details = result.get("data") if isinstance(result.get("data"), dict) else result
            if str(details.get("status", "")).strip().lower() not in {"success", "paid", "completed"}:
                return False, f"ZapUPI status: {details.get('status', 'Pending')}"
            if len(tx) > 1 and details.get("amount") is not None:
                try:
                    if abs(float(details["amount"]) - float(tx[1])) > 0.01:
                        return False, "Amount does not match this payment request."
                except (TypeError, ValueError):
                    return False, "ZapUPI returned an invalid amount."
            return True, details
        status = str(result.get("status", "")).strip().lower()
        verified = (
            result.get("paid") is True or result.get("success") is True
            or status in {"success", "paid", "completed", "approved", "verified"}
        )
        return (True, result) if verified else (False, result.get("message", "Payment is not marked as paid yet."))
    except asyncio.TimeoutError:
        return False, "Payment provider timed out. Try again later."
    except Exception as exc:
        logger.exception("API payment verification failed for transaction %s", oid)
        return False, f"Provider error: {type(exc).__name__}."


@dp.callback_query(F.data == "adm_api_mgr")
async def adm_api_mgr(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    endpoints = db("SELECT COUNT(*) FROM api_endpoints", one=True)
    count = endpoints[0] if endpoints else 0
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Endpoint", callback_data="api_add_start")],
        [InlineKeyboardButton(text=f"📋 Manage Endpoints ({count})", callback_data="api_list")],
        [InlineKeyboardButton(text="🔌 Global Auto API Settings", callback_data="adm_api_menu")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    await call.answer()
    await _edit_or_send(call, "🧩 <b>API MANAGER</b>\n\nManage payment-verification endpoints and map endpoint variants to plans.", kb)


@dp.callback_query(F.data == "api_add_start")
async def api_add_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    await state.clear()
    await state.set_state(A.api_add_name)
    await call.answer()
    await _edit_or_send(call, "Enter a name for the API endpoint:", bk("adm_api_mgr"))


@dp.message(A.api_add_name)
async def api_add_name_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if not m.text or not m.text.strip(): return await m.answer("Endpoint name cannot be empty.")
    await state.update_data(api_add_name=m.text.strip()[:100])
    await state.set_state(A.api_add_url)
    await m.answer("Send endpoint URL (https:// recommended):")


@dp.message(A.api_add_url)
async def api_add_url_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if not m.text or not m.text.strip().startswith(("https://", "http://")):
        return await m.answer("URL must start with https:// or http://")
    await state.update_data(api_add_url=m.text.strip()[:500])
    await state.set_state(A.api_add_key)
    await m.answer("Send endpoint API key, or `none` if no key is required:")


@dp.message(A.api_add_key)
async def api_add_key_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if not m.text: return await m.answer("Send an API key or `none`.")
    await state.update_data(api_add_key="" if m.text.strip().lower() == "none" else m.text.strip()[:500])
    await state.set_state(A.api_add_provider)
    await m.answer("Send provider label: custom, zapupi, binance, or another short provider name:")


@dp.message(A.api_add_provider)
async def api_add_provider_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if not m.text or not m.text.strip(): return await m.answer("Provider name cannot be empty.")
    data = await state.get_data()
    api_id = db(
        "INSERT INTO api_endpoints (name,url,api_key,provider,is_active,created_at) VALUES (?,?,?,?,1,?)",
        (data.get("api_add_name", "Endpoint"), data.get("api_add_url", ""), data.get("api_add_key", ""), m.text.strip().lower()[:50], now_str()),
    )
    await state.clear()
    await m.answer(f"✅ API endpoint added. ID: <code>{api_id}</code>", reply_markup=admin_kb())


@dp.callback_query(F.data == "api_list")
async def api_list(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    endpoints = db("SELECT id,name,provider,is_active,url FROM api_endpoints ORDER BY id DESC", all=True) or []
    if not endpoints:
        return await _edit_or_send(call, "📭 No API endpoints configured yet.", bk("adm_api_mgr"))
    rows = []
    text = "🧩 <b>API ENDPOINTS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for api in endpoints[:50]:
        state_text = "ON" if api[3] else "OFF"
        text += f"\n<b>#{api[0]}</b> · {_safe_html(api[1])} · {_safe_html(api[2])} · {state_text}\n{_safe_html(truncate(api[4], 90))}\n"
        rows.append([InlineKeyboardButton(text=f"#{api[0]} · {str(api[1])[:35]} · {state_text}", callback_data=f"api_ep_{api[0]}")])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_api_mgr")])
    await call.answer()
    await _edit_or_send(call, text[:3900], InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("api_ep_"))
async def api_endpoint_detail(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    api_id = sint(call.data[7:])
    row = db("SELECT id,name,url,api_key,provider,is_active,created_at FROM api_endpoints WHERE id=?", (api_id,), one=True)
    if not row: return await call.answer("Endpoint not found.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Name", callback_data=f"api_edit_{api_id}_name"), InlineKeyboardButton(text="🌐 Edit URL", callback_data=f"api_edit_{api_id}_url")],
        [InlineKeyboardButton(text="🔑 Edit Key", callback_data=f"api_edit_{api_id}_key"), InlineKeyboardButton(text="🏷️ Edit Provider", callback_data=f"api_edit_{api_id}_provider")],
        [InlineKeyboardButton(text=f"🔛 Toggle {'ON' if row[5] else 'OFF'}", callback_data=f"api_toggle_{api_id}")],
        [InlineKeyboardButton(text="🗑️ Delete Endpoint", callback_data=f"api_del_{api_id}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="api_list")],
    ])
    text = f"🧩 <b>{_safe_html(row[1])}</b> · ID {row[0]}\nProvider: {_safe_html(row[4])}\nStatus: {'ON' if row[5] else 'OFF'}\nURL: <code>{_safe_html(row[2])}</code>\nAPI key: {'SET' if row[3] else 'NOT SET'}\nCreated: {row[6]}"
    await call.answer()
    await _edit_or_send(call, text, kb)


@dp.callback_query(F.data.startswith("api_toggle_"))
async def api_endpoint_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    api_id = sint(call.data[len("api_toggle_"):])
    row = db("SELECT is_active FROM api_endpoints WHERE id=?", (api_id,), one=True)
    if not row: return await call.answer("Endpoint not found.", show_alert=True)
    db("UPDATE api_endpoints SET is_active=? WHERE id=?", (0 if row[0] else 1, api_id))
    await call.answer("Endpoint status changed.")
    async def _already_answered(*args, **kwargs):
        return None
    fake = type("CallbackProxy", (), {"from_user": call.from_user, "data": f"api_ep_{api_id}", "message": call.message, "answer": _already_answered})()
    await api_endpoint_detail(fake)


@dp.callback_query(F.data.startswith("api_edit_"))
async def api_endpoint_edit_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    parts = call.data.split("_")
    if len(parts) < 4: return await call.answer("Invalid edit action.", show_alert=True)
    api_id = sint(parts[2]); field = "_".join(parts[3:])
    if field not in {"name", "url", "key", "provider"}: return await call.answer("Invalid field.", show_alert=True)
    await state.clear()
    await state.update_data(api_edit_id=api_id, api_edit_field=field)
    await state.set_state(A.api_edit_value)
    await call.answer()
    await _edit_or_send(call, f"Send new value for API {field}. For key, send `none` to clear it.", bk(f"api_ep_{api_id}"))


@dp.message(A.api_edit_value)
async def api_endpoint_edit_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if not m.text or not m.text.strip(): return await m.answer("Value cannot be empty.")
    data = await state.get_data(); api_id = sint(data.get("api_edit_id")); field = data.get("api_edit_field")
    value = m.text.strip()
    column_map = {"name":"name", "url":"url", "key":"api_key", "provider":"provider"}
    column = column_map.get(field)
    if not column: await state.clear(); return await m.answer("Invalid edit session.")
    if field == "url" and not value.startswith(("https://", "http://")):
        return await m.answer("URL must start with https:// or http://")
    if field == "key" and value.lower() == "none": value = ""
    if field == "provider": value = value.lower()[:50]
    db(f"UPDATE api_endpoints SET {column}=? WHERE id=?", (value[:500], api_id))
    await state.clear()
    await m.answer(f"✅ API endpoint #{api_id} updated.", reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("api_del_"))
async def api_endpoint_delete(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    api_id = sint(call.data[len("api_del_"):])
    row = db("SELECT name FROM api_endpoints WHERE id=?", (api_id,), one=True)
    if not row: return await call.answer("Endpoint not found.", show_alert=True)
    db("DELETE FROM plan_api_variant WHERE api_id=?", (api_id,))
    db("DELETE FROM api_endpoints WHERE id=?", (api_id,))
    await call.answer("Endpoint and plan mappings removed.", show_alert=True)
    async def _already_answered(*args, **kwargs):
        return None
    fake = type("CallbackProxy", (), {"from_user": call.from_user, "data": "api_list", "message": call.message, "answer": _already_answered})()
    await api_list(fake)


@dp.callback_query(F.data == "adm_plan_api_list")
async def plan_api_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    plans = db(
        "SELECT pl.id, pl.name, p.name FROM plans pl LEFT JOIN products p ON p.id=pl.product_id "
        "ORDER BY pl.product_id, pl.position, pl.id",
        all=True,
    ) or []
    if not plans:
        return await _edit_or_send(call, "📭 No plans found. Add a plan first.", bk("adm_plans"))
    rows = []
    for plan_id, plan_name, product_name in plans[:80]:
        rows.append([InlineKeyboardButton(
            text=f"{str(product_name or 'Product')[:24]} · {str(plan_name)[:28]} (#{plan_id})",
            callback_data=f"planapi_{plan_id}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_plans")])
    await call.answer()
    await _edit_or_send(call, "🧩 <b>SELECT PLAN FOR API MAPPING</b>", InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.regexp(r"^planapi_\d+$"))
async def plan_api_pick(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    parts = call.data.split("_")
    if len(parts) != 2: return await call.answer("Invalid plan API action.", show_alert=True)
    plan_id = sint(parts[1])
    apis = db("SELECT id,name,provider FROM api_endpoints WHERE is_active=1 ORDER BY id", all=True) or []
    rows = [[InlineKeyboardButton(text=f"🌐 {str(a[1])[:35]} ({a[2]})", callback_data=f"planapi_ep_{plan_id}_{a[0]}")] for a in apis]
    rows.append([InlineKeyboardButton(text="🗑️ Clear Plan Mapping", callback_data=f"planapi_clear_{plan_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data=f"adpl_edit_{plan_id}")])
    await call.answer()
    await _edit_or_send(call, f"🧩 Choose verification endpoint for plan <code>{plan_id}</code>:", InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("planapi_ep_"))
async def plan_api_endpoint_pick(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    parts = call.data.split("_")
    if len(parts) != 4: return await call.answer("Invalid endpoint selection.", show_alert=True)
    plan_id, api_id = sint(parts[2]), sint(parts[3])
    if not db("SELECT id FROM plans WHERE id=?", (plan_id,), one=True): return await call.answer("Plan not found.", show_alert=True)
    if not db("SELECT id FROM api_endpoints WHERE id=? AND is_active=1", (api_id,), one=True): return await call.answer("Endpoint unavailable.", show_alert=True)
    await state.clear()
    await state.update_data(plan_api_plan_id=plan_id, plan_api_id=api_id)
    await state.set_state(A.plan_api_variant)
    await call.answer()
    await _edit_or_send(call, "Send the plan-specific variant/product code required by this endpoint, or send `none` if not required:", bk(f"adpl_edit_{plan_id}"))


@dp.message(A.plan_api_variant)
async def plan_api_variant_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    if not m.text: return await m.answer("Send a variant code or `none`.")
    data = await state.get_data()
    plan_id = sint(data.get("plan_api_plan_id")); api_id = sint(data.get("plan_api_id"))
    variant = "" if m.text.strip().lower() == "none" else m.text.strip()[:200]
    db("INSERT OR REPLACE INTO plan_api_variant (plan_id,api_id,variant,updated_at) VALUES (?,?,?,?)", (plan_id,api_id,variant,now_str()))
    await state.clear()
    await m.answer(f"✅ Plan #{plan_id} mapped to API endpoint #{api_id}.", reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("planapi_clear_"))
async def plan_api_clear(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    plan_id = sint(call.data[len("planapi_clear_"):])
    db("DELETE FROM plan_api_variant WHERE plan_id=?", (plan_id,))
    await call.answer("Plan API mapping cleared.", show_alert=True)
    fake = type("CallbackProxy", (), {"from_user": call.from_user, "data": f"adpl_edit_{plan_id}", "message": call.message, "answer": call.answer})()
    await plan_edit_menu(fake)



# ══════════════════════════════════════════════════════════════
#                  GLOBAL ERROR HANDLER
# ══════════════════════════════════════════════════════════════

@dp.errors()
async def error_handler(event):
    """Log unhandled update errors + safe retry message."""
    exc = event.exception
    update = getattr(event, "update", None)
    callback = getattr(update, "callback_query", None) if update else None
    callback_data = getattr(callback, "data", None) if callback else None
    message = getattr(update, "message", None) if update else None
    logger.error(
        "Unhandled bot action context: update_id=%s callback_data=%r user_id=%s message=%r",
        getattr(update, "update_id", "unknown"),
        callback_data,
        getattr(getattr(callback, "from_user", None), "id", None) or getattr(getattr(message, "from_user", None), "id", None),
        (getattr(message, "text", None) or "")[:120] if message else None,
    )
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
                    "⚠️ This action failed. Error logged; please try again or contact the admin.",
                    show_alert=True,
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
    """Expire stale payment requests while preserving transaction/audit history."""
    while True:
        try:
            cutoff = int(time.time())
            conn = sqlite3.connect(DB_PATH, timeout=30)
            try:
                conn.execute("PRAGMA busy_timeout=30000")
                conn.execute("BEGIN IMMEDIATE")
                expired_rows = conn.execute(
                    "SELECT order_id, qr_data, method FROM transactions "
                    "WHERE status='pending' AND expires_at > 0 AND expires_at < ?",
                    (cutoff,),
                ).fetchall()
                # Do not auto-expire confirmed ZapUPI sessions: a delayed provider webhook
                # must still be able to credit/deliver a payment that the customer completed.
                ids = []
                for row in expired_rows:
                    order_id, qr_data, method = row
                    try:
                        meta = json.loads(qr_data or "{}")
                    except (TypeError, ValueError):
                        meta = {}
                    if meta.get("zapupi") or method == "zapupi_creating":
                        continue
                    ids.append(order_id)
                if ids:
                    conn.executemany(
                        "UPDATE transactions SET status='expired' WHERE order_id=? AND status='pending'",
                        [(oid,) for oid in ids],
                    )
                    for oid in ids:
                        conn.execute(
                            "UPDATE balance_requests SET status='expired', reviewed_at=? "
                            "WHERE reference LIKE ? AND status='pending'",
                            (now_str(), f"{oid}%"),
                        )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        except Exception as e:
            logger.error("Transaction expiry cleanup failed: %s", e, exc_info=True)
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
