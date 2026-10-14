#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║           ELITE X CONFIG — COMPLETE TELEGRAM BOT             ║
║                  Version 4.0 — Final Build                   ║
║                                                              ║
║  Features:                                                   ║
║  • Full Store System (Category→Panel→Plan→Key)              ║
║  • Wallet + QR + UTR Payment                                ║
║  • Auto API Payment Verification                            ║
║  • VIP / Reseller System                                    ║
║  • Coupons / Daily Gift / Refer Reward                      ║
║  • Support Tickets with Admin Reply                         ║
║  • Broadcast (Text/Photo/Video/Document)                    ║
║  • Complete Admin Panel                                     ║
║  • Menu Designer (Custom Buttons)                           ║
║  • Message Editor (All UI texts)                            ║
║  • Maintenance (Global + Category + Product)                ║
║  • Co-Admin System                                          ║
║  • Profile Field Customization                              ║
║  • Full Logging + Web Server                                ║
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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
    BufferedInputFile,
)

try:
    import qrcode
except ImportError:
    qrcode = None

# ══════════════════════════════════════════════════════════════
#                        CONFIGURATION
# ══════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "8606369071:AAEqBcCFHPz8syTBP40cvnOHQHojn0R-WoI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8467166339"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "elitexbot")
BRAND_NAME = os.getenv("BRAND_NAME", "ELITE X CONFIG")
DB_PATH = os.getenv("DB_PATH", "elitex_bot.db")
VIP_DISCOUNT = float(os.getenv("VIP_DISCOUNT", "10.0"))
VIP_PRICE = float(os.getenv("VIP_PRICE", "1000.0"))
WEB_PORT = int(os.getenv("PORT", "8080"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EliteXBot")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ══════════════════════════════════════════════════════════════
#                        HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════

def fmt(a):
    """Format amount as currency"""
    try:
        return f"₹{float(a):,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"

def fancy(text):
    """Convert text to fancy small-caps Unicode"""
    bc = {chr(ord("A") + i): chr(0x1D400 + i) for i in range(26)}
    sc = {
        "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ",
        "g": "ɢ", "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ",
        "m": "ᴍ", "n": "ɴ", "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ",
        "s": "s", "t": "ᴛ", "u": "ᴜ", "v": "ᴠ", "w": "ᴡ", "x": "x",
        "y": "ʏ", "z": "ᴢ"
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

def sfloat(v, d=0.0):
    """Safe float conversion"""
    try:
        return float(v)
    except (ValueError, TypeError):
        return d

def sint(v, d=0):
    """Safe int conversion"""
    try:
        return int(v)
    except (ValueError, TypeError):
        return d

def upi_link(upi, name, amt, note=""):
    """Generate UPI payment deep link"""
    s = f"upi://pay?pa={quote(str(upi))}&pn={quote(str(name))}&am={float(amt):.2f}&cu=INR"
    if note:
        s += f"&tn={quote(str(note))}"
    return s

def make_qr(data):
    """Generate QR code as BufferedInputFile"""
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

def now_str():
    """Get current timestamp string"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_progress_bar(pct: int, width: int = 10) -> str:
    """Generate a progress bar"""
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled) + f" {pct}%"

def truncate(text: str, length: int = 100) -> str:
    """Truncate text with ellipsis"""
    if not text:
        return ""
    return text[:length] + "..." if len(text) > length else text

# ══════════════════════════════════════════════════════════════
#                         DATABASE LAYER
# ══════════════════════════════════════════════════════════════

def db(q, p=(), one=False, all=False, commit=True):
    """Execute DB query"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    try:
        c.execute(q, p)
        r = c.fetchone() if one else (c.fetchall() if all else None)
        if commit:
            conn.commit()
        return r
    except Exception as e:
        logger.error(f"DB error: {e} | Query: {q} | Params: {p}")
        return None
    finally:
        conn.close()

def gs(k, d=""):
    """Get setting"""
    v = db("SELECT value FROM settings WHERE key=?", (k,), one=True)
    return v[0] if v and v[0] else d

def ss(k, v):
    """Set setting"""
    db("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))

def log_activity(user_id: int, action: str, details: str = ""):
    """Log user activity"""
    try:
        db("INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
           (user_id, action, details, now_str()))
    except Exception as e:
        logger.error(f"Activity log failed: {e}")

def get_user(uid):
    """Get user row"""
    return db("SELECT user_id, first_name, username, balance, is_reseller, is_vip, is_banned, joined_date, last_gift FROM users WHERE user_id=?",
              (uid,), one=True)

def is_admin(uid):
    """Check if user is admin"""
    if uid == ADMIN_ID:
        return True
    r = db("SELECT user_id FROM co_admins WHERE user_id=?", (uid,), one=True)
    return bool(r)

def ensure_user(m: Message):
    """Ensure user exists in DB"""
    uid = m.from_user.id
    if not db("SELECT user_id FROM users WHERE user_id=?", (uid,), one=True):
        db("INSERT INTO users (user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)",
           (uid, m.from_user.first_name or "", m.from_user.username or "", now_str()))
    else:
        db("UPDATE users SET first_name=?, username=? WHERE user_id=?",
           (m.from_user.first_name or "", m.from_user.username or "", uid))

# ══════════════════════════════════════════════════════════════
#                       DATABASE SCHEMA
# ══════════════════════════════════════════════════════════════

def init_db():
    """Initialize database with all tables"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()

    # Users
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

    # Categories
    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '📂',
        description TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        is_maintenance INTEGER DEFAULT 0,
        position INTEGER DEFAULT 0
    )""")

    # Products (Panels)
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        emoji TEXT DEFAULT '📦',
        is_active INTEGER DEFAULT 1,
        is_maintenance INTEGER DEFAULT 0,
        position INTEGER DEFAULT 0
    )""")

    # Plans
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

    # Product Keys
    c.execute("""CREATE TABLE IF NOT EXISTS product_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        key_text TEXT NOT NULL,
        is_used INTEGER DEFAULT 0,
        used_by INTEGER DEFAULT 0,
        used_at TEXT DEFAULT '',
        added_at TEXT DEFAULT ''
    )""")

    # Orders
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
        status TEXT DEFAULT 'delivered'
    )""")

    # Balance Requests
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

    # Support Tickets
    c.execute("""CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT,
        status TEXT DEFAULT 'Open',
        reply TEXT DEFAULT '',
        created_at TEXT,
        replied_at TEXT DEFAULT ''
    )""")

    # Coupons
    c.execute("""CREATE TABLE IF NOT EXISTS coupons (
        code TEXT PRIMARY KEY,
        discount REAL DEFAULT 0,
        max_uses INTEGER DEFAULT 1,
        used INTEGER DEFAULT 0,
        created_at TEXT
    )""")

    # Co-Admins
    c.execute("""CREATE TABLE IF NOT EXISTS co_admins (
        user_id INTEGER PRIMARY KEY,
        name TEXT DEFAULT '',
        added_at TEXT
    )""")

    # Settings
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    # Transactions (payments)
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        order_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        status TEXT DEFAULT 'pending',
        created_at INTEGER,
        expires_at INTEGER,
        qr_data TEXT DEFAULT '',
        purpose TEXT DEFAULT 'balance'
    )""")

    # Menu Buttons
    c.execute("""CREATE TABLE IF NOT EXISTS menu_buttons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        emoji TEXT DEFAULT '',
        action TEXT,
        position INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        row_group INTEGER DEFAULT 0
    )""")

    # Profile Fields
    c.execute("""CREATE TABLE IF NOT EXISTS profile_fields (
        field_key TEXT PRIMARY KEY,
        label TEXT,
        is_visible INTEGER DEFAULT 1
    )""")

    # Broadcast History
    c.execute("""CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT,
        sent INTEGER DEFAULT 0,
        failed INTEGER DEFAULT 0,
        created_at TEXT
    )""")

    # Activity Logs
    c.execute("""CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        timestamp TEXT
    )""")

    # Settings defaults
    defaults = {
        'welcome_text': '⚡ <b>Welcome to ELITE X CONFIG</b> ⚡\n\n🛍️ Premium Digital Store\n\n🎯 Buy panels, get instant keys!',
        'upi_id': '',
        'payee_name': BRAND_NAME,
        'support_telegram': 'https://t.me/YourSupport',
        'support_whatsapp': 'https://wa.me/YourNumber',
        'global_maintenance': '0',
        'maintenance_msg': '🛠️ Bot is under maintenance. Please try again later.',
        'daily_gift_price': '0',
        'refer_earn_amount': '0',
        'admin_logo_file_id': '',
        'static_qr_file_id': '',
        'ui_category_msg': '📂 <b>Select a Category</b>',
        'ui_product_msg': '📦 <b>Select a Panel</b>',
        'ui_plan_msg': '⏱ <b>Select a Plan</b>',
        'ui_key_msg': '🎉 <b>Thank you for your purchase!</b>',
        'payment_mode': 'manual',
        'auto_api_key': '',
        'auto_api_url': '',
        'auto_api_enabled': '0',
        'reseller_setup_fee': '500',
        'reseller_min_balance': '1000',
        'reseller_system_status': 'ON',
        'vip_system_status': 'ON',
        'force_join_channel': '',
        'welcome_media_type': 'none',
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))

    # Default menu buttons
    if c.execute("SELECT COUNT(*) FROM menu_buttons").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO menu_buttons (label, emoji, action, position, is_active, row_group) VALUES (?, ?, ?, ?, 1, ?)",
            [
                ("Product Store", "🛍️", "shop", 1, 0),
                ("My Profile", "👤", "profile", 2, 1),
                ("Add Balance", "💰", "addbalance", 3, 1),
                ("Support", "🎧", "support", 4, 2),
                ("Daily Gift", "🎁", "daily_gift", 5, 2),
                ("Redeem Coupon", "🎟️", "redeem_coupon", 6, 3),
            ]
        )

    # Default profile fields
    if c.execute("SELECT COUNT(*) FROM profile_fields").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO profile_fields (field_key, label, is_visible) VALUES (?, ?, 1)",
            [
                ("user_id", "User ID"),
                ("name", "Name"),
                ("balance", "Balance"),
                ("account_type", "Account Type"),
                ("joined_date", "Join Date"),
                ("total_spent", "Total Spent"),
                ("total_orders", "Total Orders"),
            ]
        )

    conn.commit()
    conn.close()

# ══════════════════════════════════════════════════════════════
#                       MIDDLEWARE
# ══════════════════════════════════════════════════════════════

class AntiSpam(BaseMiddleware):
    """Simple anti-spam middleware"""
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
    """Ban + maintenance check"""
    async def __call__(self, handler, event, data):
        try:
            uid = event.from_user.id
        except Exception:
            return await handler(event, data)

        if uid != ADMIN_ID:
            u = db("SELECT is_banned FROM users WHERE user_id=?", (uid,), one=True)
            if u and u[0] == 1:
                if isinstance(event, Message):
                    await event.answer("🚫 You are banned from using this bot.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Banned", show_alert=True)
                return

            if gs("global_maintenance") == "1" and not is_admin(uid):
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
    """User states"""
    ticket = State()
    coupon = State()
    custom_amt = State()
    proof = State()
    buy_proof = State()
    ticket_reply = State()


class A(StatesGroup):
    """Admin states"""
    # Category
    cat_name = State()
    cat_desc = State()
    cat_emoji = State()
    cat_edit = State()

    # Panel
    panel_cat = State()
    panel_name = State()
    panel_desc = State()
    panel_emoji = State()
    panel_edit = State()

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

    # Users
    user_search = State()
    user_addbal = State()
    user_rembal = State()

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
    menu_edit = State()

    # Co-Admin
    coadmin_add = State()
    coadmin_remove = State()

    # Reseller
    res_fee = State()
    res_min = State()

# ══════════════════════════════════════════════════════════════
#                       KEYBOARDS
# ══════════════════════════════════════════════════════════════

def main_menu_kb(uid=None):
    """Main menu keyboard"""
    rows = []
    btns = db("SELECT id, label, emoji, action, row_group FROM menu_buttons WHERE is_active=1 ORDER BY position", all=True)
    grouped = {}
    for b in btns or []:
        grouped.setdefault(b[4] or 0, []).append(b)
    for rg in sorted(grouped.keys()):
        row = []
        for b in grouped[rg]:
            t = f"{b[2]} {fancy(b[1])}" if b[2] else fancy(b[1])
            row.append(InlineKeyboardButton(text=t, callback_data=f"act_{b[3]}"))
        rows.append(row)
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


def admin_kb():
    """Admin panel main keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ " + fancy("Store Manager"), callback_data="adm_store")],
        [InlineKeyboardButton(text="👥 " + fancy("User Manager"), callback_data="adm_users")],
        [InlineKeyboardButton(text="💳 " + fancy("Payment Settings"), callback_data="adm_pay")],
        [InlineKeyboardButton(text="📢 " + fancy("Broadcast"), callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="🎟️ " + fancy("Marketing"), callback_data="adm_mkt")],
        [InlineKeyboardButton(text="🎨 " + fancy("Menu Designer"), callback_data="adm_menu")],
        [InlineKeyboardButton(text="📝 " + fancy("Message Editor"), callback_data="adm_msg")],
        [InlineKeyboardButton(text="🤝 " + fancy("Co-Admins"), callback_data="adm_coadmin")],
        [InlineKeyboardButton(text="⚙️ " + fancy("Settings"), callback_data="adm_settings")],
        [InlineKeyboardButton(text="🛠️ " + fancy("Maintenance"), callback_data="adm_maint")],
        [InlineKeyboardButton(text="📊 " + fancy("Statistics"), callback_data="adm_stats")],
        [InlineKeyboardButton(text="🏠 " + fancy("User View"), callback_data="back_main")],
    ])


def bk(cb="adm_back"):
    """Simple back button"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ " + fancy("Back"), callback_data=cb)]
    ])

# ══════════════════════════════════════════════════════════════
#                       START & HOME
# ══════════════════════════════════════════════════════════════

@dp.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    ensure_user(m)
    log_activity(m.from_user.id, "START")

    # Referral handling
    try:
        args = m.text.split()
        if len(args) > 1 and args[1].startswith("ref_"):
            ref_by = sint(args[1][4:])
            if ref_by and ref_by != m.from_user.id:
                u = get_user(m.from_user.id)
                if u and u[9 if len(u) > 9 else 8] in (0, None):  # refer_by check
                    db("UPDATE users SET refer_by=? WHERE user_id=?", (ref_by, m.from_user.id))
                    db("UPDATE users SET refer_count=refer_count+1 WHERE user_id=?", (ref_by,))
                    reward = sfloat(gs("refer_earn_amount"))
                    if reward > 0:
                        db("UPDATE users SET balance=balance+? WHERE user_id=?", (reward, ref_by))
    except Exception as e:
        logger.error(f"Referral error: {e}")

    text = gs("welcome_text")
    logo = gs("admin_logo_file_id")
    kb = main_menu_kb(m.from_user.id)

    if logo:
        try:
            await m.answer_photo(logo, caption=text, reply_markup=kb)
            return
        except Exception:
            pass
    await m.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.edit_text(gs("welcome_text"), reply_markup=main_menu_kb(call.from_user.id))
    except Exception:
        try:
            await call.message.delete()
        except Exception:
            pass
        await bot.send_message(call.from_user.id, gs("welcome_text"), reply_markup=main_menu_kb(call.from_user.id))


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
        "📦 /orders — Your orders\n"
        "💰 /balance — Your balance\n"
        "🎧 /support — Contact support\n"
        "❌ /cancel — Cancel current action\n"
    )
    if is_admin(m.from_user.id):
        text += "\n👑 /admin — Admin panel"
    await m.answer(text, reply_markup=main_menu_kb(m.from_user.id))


@dp.message(Command("profile"))
async def cmd_profile(m: Message):
    u = get_user(m.from_user.id)
    if not u:
        return await m.answer("User not found. Send /start first.")
    text = build_profile_text(m.from_user.id)
    await m.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders")],
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
    ]))


@dp.message(Command("balance"))
async def cmd_balance(m: Message):
    u = get_user(m.from_user.id)
    if not u:
        return await m.answer("User not found. Send /start first.")
    await m.answer(f"💰 <b>Your Balance:</b> {fmt(u[3])}", reply_markup=main_menu_kb(m.from_user.id))


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
            [InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton(text="🎟️ Redeem Coupon", callback_data="act_redeem_coupon")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
        ])
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            await call.message.answer(text, reply_markup=kb)

    elif action == "addbalance":
        await show_add_balance(call)

    elif action == "support":
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
        try:
            await call.message.edit_text("🎧 <b>SUPPORT CENTER</b>\n\nChoose an option:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        except Exception:
            await call.message.answer("🎧 <b>SUPPORT CENTER</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    elif action == "daily_gift":
        await claim_daily_gift(call)

    elif action == "redeem_coupon":
        await state.set_state(U.coupon)
        try:
            await call.message.edit_text("🎟️ <b>Redeem Coupon</b>\n\nSend your coupon code:", reply_markup=bk("back_main"))
        except Exception:
            await call.message.answer("🎟️ Send your coupon code:")

    elif action == "reseller":
        await show_reseller_panel(call)

    elif action == "vip":
        await show_vip_panel(call)

    else:
        await call.answer("Coming soon!", show_alert=True)


def build_profile_text(uid):
    u = get_user(uid)
    if not u:
        return "User not found."
    oc = db("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,), one=True)
    oc = oc[0] if oc else 0
    sp = db("SELECT COALESCE(SUM(price_paid),0) FROM orders WHERE user_id=?", (uid,), one=True)
    sp = sp[0] if sp else 0
    fields = db("SELECT field_key, label FROM profile_fields WHERE is_visible=1", all=True)

    text = "👤 <b>MY PROFILE</b>\n━━━━━━━━━━━━━━━━━━\n"
    for f in fields or []:
        k = f[0]
        if k == "user_id":
            text += f"🆔 ID: <code>{uid}</code>\n"
        elif k == "name":
            text += f"📛 Name: {u[1] or 'N/A'}\n"
        elif k == "balance":
            text += f"💰 Balance: <b>{fmt(u[3])}</b>\n"
        elif k == "account_type":
            t = []
            if u[4]:
                t.append("👑 Reseller")
            if u[5]:
                t.append("🌟 VIP")
            text += f"🔰 Type: {' | '.join(t) if t else 'Regular'}\n"
        elif k == "joined_date":
            text += f"📅 Joined: {u[7]}\n"
        elif k == "total_spent":
            text += f"💸 Spent: {fmt(sp)}\n"
        elif k == "total_orders":
            text += f"📦 Orders: {oc}\n"
    return text


@dp.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):
    await show_user_orders(call.from_user.id, call)


async def show_user_orders(uid, target):
    o = db("""SELECT id, product_name, plan_name, price_paid, delivered_key, purchase_date, status
              FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 15""", (uid,), all=True)
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
        text += f"\n🆔 <b>Order #{r[0]}</b>\n📦 {r[1]} - {r[2]}\n💰 {fmt(r[3])}\n🔑 <code>{truncate(r[4], 40)}</code>\n📅 {r[5]}\n"
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
#                       DAILY GIFT
# ══════════════════════════════════════════════════════════════

async def claim_daily_gift(call: CallbackQuery):
    gift = sfloat(gs("daily_gift_price"))
    if gift <= 0:
        return await call.answer("🎁 Daily gift is disabled.", show_alert=True)

    today = datetime.now().strftime("%Y-%m-%d")
    u = get_user(call.from_user.id)
    if not u:
        return await call.answer("Please /start first.", show_alert=True)

    if u[8] == today:
        return await call.answer("🎁 Already claimed today! Come back tomorrow.", show_alert=True)

    db("UPDATE users SET balance=balance+?, last_gift=? WHERE user_id=?", (gift, today, call.from_user.id))
    log_activity(call.from_user.id, "DAILY_GIFT", str(gift))
    await call.answer(f"🎁 +{fmt(gift)} claimed successfully!", show_alert=True)

    try:
        await call.message.edit_text(
            f"🎁 <b>Daily Gift Claimed!</b>\n\n💰 You received: <b>{fmt(gift)}</b>\n\nCome back tomorrow for more!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")]
            ])
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════
#                       VIP SYSTEM
# ══════════════════════════════════════════════════════════════

async def show_vip_panel(call: CallbackQuery):
    u = get_user(call.from_user.id)
    if not u:
        return await call.answer("User not found!", show_alert=True)

    is_vip = bool(u[5])
    if is_vip:
        text = (
            f"🌟 <b>VIP MEMBERSHIP</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ Status: <b>ACTIVE</b>\n"
            f"💰 You get <b>{VIP_DISCOUNT}% off</b> on every purchase!\n\n"
            f"Thank you for being a VIP member!"
        )
        kb = bk("back_main")
    else:
        if gs("vip_system_status") == "OFF":
            return await call.answer("VIP system is currently disabled.", show_alert=True)
        balance = u[3]
        text = (
            f"🌟 <b>VIP MEMBERSHIP</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💎 <b>Benefits:</b>\n"
            f"• {VIP_DISCOUNT}% discount on all products\n"
            f"• Priority support\n"
            f"• Exclusive deals\n\n"
            f"💳 <b>Price:</b> {fmt(VIP_PRICE)} (Lifetime)\n"
            f"💰 <b>Your Balance:</b> {fmt(balance)}\n"
        )
        rows = []
        if balance >= VIP_PRICE:
            rows.append([InlineKeyboardButton(text=f"✅ Buy VIP {fmt(VIP_PRICE)}", callback_data="buy_vip")])
        else:
            need = VIP_PRICE - balance
            rows.append([InlineKeyboardButton(text=f"❌ Need {fmt(need)} more", callback_data="noop")])
            rows.append([InlineKeyboardButton(text="💰 Add Balance", callback_data="act_addbalance")])
        rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "buy_vip")
async def buy_vip(call: CallbackQuery):
    u = get_user(call.from_user.id)
    if not u:
        return await call.answer("User not found!", show_alert=True)
    if u[5]:
        return await call.answer("You are already VIP!", show_alert=True)
    if u[3] < VIP_PRICE:
        return await call.answer(f"❌ Need {fmt(VIP_PRICE)}. Add balance first.", show_alert=True)

    db("UPDATE users SET balance=balance-?, is_vip=1 WHERE user_id=?", (VIP_PRICE, call.from_user.id))
    log_activity(call.from_user.id, "VIP_PURCHASE", str(VIP_PRICE))

    try:
        await bot.send_message(
            ADMIN_ID,
            f"🌟 <b>NEW VIP PURCHASE</b>\n"
            f"👤 User: <code>{call.from_user.id}</code>\n"
            f"💰 Amount: {fmt(VIP_PRICE)}"
        )
    except Exception:
        pass

    await call.answer("🎉 VIP activated successfully!", show_alert=True)
    await show_vip_panel(call)

# ══════════════════════════════════════════════════════════════
#                       RESELLER SYSTEM
# ══════════════════════════════════════════════════════════════

async def show_reseller_panel(call: CallbackQuery):
    u = get_user(call.from_user.id)
    if not u:
        return await call.answer("User not found!", show_alert=True)

    is_res = bool(u[4])
    if is_res:
        text = (
            f"👑 <b>RESELLER DASHBOARD</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ Status: <b>ACTIVE</b>\n"
            f"💰 You get special wholesale prices!\n\n"
            f"Browse products to see your reseller rates."
        )
        kb = bk("back_main")
    else:
        if gs("reseller_system_status") == "OFF":
            return await call.answer("Reseller system is currently disabled.", show_alert=True)
        fee = sfloat(gs("reseller_setup_fee", "500"))
        min_bal = sfloat(gs("reseller_min_balance", "1000"))
        balance = u[3]
        text = (
            f"👑 <b>BECOME A RESELLER</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💎 <b>Benefits:</b>\n"
            f"• Wholesale prices on all products\n"
            f"• Higher profit margins\n"
            f"• Priority support\n\n"
            f"📋 <b>Requirements:</b>\n"
            f"• Minimum balance: {fmt(min_bal)}\n"
            f"• Setup fee: {fmt(fee)}\n\n"
            f"💰 <b>Your Balance:</b> {fmt(balance)}\n"
        )
        rows = []
        if balance >= min_bal:
            rows.append([InlineKeyboardButton(text=f"✅ Become Reseller {fmt(fee)}", callback_data="buy_reseller")])
        else:
            need = min_bal - balance
            rows.append([InlineKeyboardButton(text=f"❌ Need {fmt(need)} more", callback_data="noop")])
            rows.append([InlineKeyboardButton(text="💰 Add Balance", callback_data="act_addbalance")])
        rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "buy_reseller")
async def buy_reseller(call: CallbackQuery):
    u = get_user(call.from_user.id)
    if not u:
        return await call.answer("User not found!", show_alert=True)
    if u[4]:
        return await call.answer("You are already a reseller!", show_alert=True)

    fee = sfloat(gs("reseller_setup_fee", "500"))
    min_bal = sfloat(gs("reseller_min_balance", "1000"))

    if u[3] < min_bal:
        return await call.answer(f"❌ Need minimum {fmt(min_bal)} to become reseller.", show_alert=True)
    if u[3] < fee:
        return await call.answer(f"❌ Need {fmt(fee)} setup fee.", show_alert=True)

    db("UPDATE users SET balance=balance-?, is_reseller=1 WHERE user_id=?", (fee, call.from_user.id))
    log_activity(call.from_user.id, "RESELLER_PURCHASE", str(fee))

    try:
        await bot.send_message(
            ADMIN_ID,
            f"👑 <b>NEW RESELLER</b>\n"
            f"👤 User: <code>{call.from_user.id}</code>\n"
            f"💰 Paid: {fmt(fee)}"
        )
    except Exception:
        pass

    await call.answer("🎉 Welcome to Reseller tier!", show_alert=True)
    await show_reseller_panel(call)


@dp.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()

# ══════════════════════════════════════════════════════════════
#                       SHOP: CATEGORIES
# ══════════════════════════════════════════════════════════════

async def show_categories(call: CallbackQuery):
    cats = db("""SELECT id, name, emoji, is_maintenance
                 FROM categories WHERE is_active=1 ORDER BY position, id""", all=True)
    if not cats:
        return await call.answer("❌ No categories available!", show_alert=True)

    rows = []
    for c in cats:
        badge = " 🔧" if c[3] else ""
        rows.append([InlineKeyboardButton(text=f"{c[2]} {c[1]}{badge}", callback_data=f"cat_{c[0]}")])
    rows.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")])

    try:
        await call.message.edit_text(gs("ui_category_msg"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await call.message.answer(gs("ui_category_msg"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("cat_"))
async def show_panels(call: CallbackQuery):
    cid = sint(call.data[4:])
    cat = db("SELECT name, emoji, is_maintenance, description FROM categories WHERE id=?", (cid,), one=True)
    if not cat:
        return await call.answer("Category not found!", show_alert=True)
    if cat[2]:
        return await call.answer("🔧 This category is under maintenance.", show_alert=True)

    panels = db("""SELECT id, name, emoji, is_maintenance, description
                   FROM products WHERE category_id=? AND is_active=1
                   ORDER BY position, id""", (cid,), all=True)

    if not panels:
        return await call.answer("📭 No products in this category yet.", show_alert=True)

    rows = []
    for p in panels:
        badge = " 🔧" if p[3] else ""
        emoji = p[2] or "📦"
        rows.append([InlineKeyboardButton(text=f"{emoji} {p[1]}{badge}", callback_data=f"panel_{p[0]}")])
    rows.append([InlineKeyboardButton(text="⬅️ Categories", callback_data="act_shop")])

    header = f"{cat[1]} <b>{cat[0]}</b>\n"
    if cat[3]:
        header += f"\n<i>{cat[3]}</i>\n"
    header += f"\n{gs('ui_product_msg')}"

    try:
        await call.message.edit_text(header, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await call.message.answer(header, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("panel_"))
async def show_plans(call: CallbackQuery):
    pid = sint(call.data[6:])
    p = db("SELECT name, emoji, is_maintenance, description, category_id FROM products WHERE id=?", (pid,), one=True)
    if not p:
        return await call.answer("Panel not found!", show_alert=True)
    if p[2]:
        return await call.answer("🔧 This panel is under maintenance.", show_alert=True)

    plans = db("""SELECT id, name, price, reseller_price, discount
                  FROM plans WHERE product_id=? AND is_active=1
                  ORDER BY position, id""", (pid,), all=True)

    if not plans:
        return await call.answer("📭 No plans for this product yet.", show_alert=True)

    u = db("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)
    is_res, is_vip = bool(u[0]), bool(u[1])

    rows = []
    for pl in plans:
        base = pl[3] if (is_res and pl[3] > 0) else pl[2]
        if is_vip:
            base = base - (base * VIP_DISCOUNT / 100)
        if pl[4]:
            base = base - (base * pl[4] / 100)
        avail = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (pl[0],), one=True)
        avail = avail[0] if avail else 0
        stock = "🟢" if avail > 0 else "🔴"
        rows.append([InlineKeyboardButton(text=f"⏱ {pl[1]} - {fmt(base)} {stock}", callback_data=f"plan_{pl[0]}")])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data=f"cat_{p[4]}")])

    header = f"{p[1] or '📦'} <b>{p[0]}</b>\n"
    if p[3]:
        header += f"\n<i>{p[3]}</i>\n"
    header += f"\n{gs('ui_plan_msg')}"

    try:
        await call.message.edit_text(header, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await call.message.answer(header, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("plan_"))
async def buy_plan(call: CallbackQuery):
    plid = sint(call.data[5:])
    pl = db("""SELECT id, product_id, name, price, reseller_price, discount
               FROM plans WHERE id=?""", (plid,), one=True)
    if not pl:
        return await call.answer("Plan not found!", show_alert=True)

    prod = db("SELECT name, category_id FROM products WHERE id=?", (pl[1],), one=True)
    cat = db("SELECT name FROM categories WHERE id=?", (prod[1],), one=True) if prod else None

    u = db("SELECT balance, is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)
    base = pl[4] if (u[1] and pl[4] > 0) else pl[3]
    if u[2]:
        base = base - (base * VIP_DISCOUNT / 100)
    if pl[5]:
        base = base - (base * pl[5] / 100)
    final = base

    avail = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (plid,), one=True)
    avail = avail[0] if avail else 0
    if avail <= 0:
        return await call.answer("❌ This plan is out of stock!", show_alert=True)

    text = (
        f"🛒 <b>ORDER SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📂 Category: <b>{cat[0] if cat else 'N/A'}</b>\n"
        f"📦 Panel: <b>{prod[0] if prod else 'N/A'}</b>\n"
        f"⏱ Plan: <b>{pl[2]}</b>\n"
        f"💰 Price: <b>{fmt(final)}</b>\n"
        f"💵 Your Balance: <b>{fmt(u[0])}</b>\n"
        f"🔑 Stock: <b>{avail}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Choose payment method:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Pay with Wallet", callback_data=f"walletbuy_{plid}")],
        [InlineKeyboardButton(text="💳 Pay via QR/UPI", callback_data=f"qrpay_{plid}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data=f"panel_{pl[1]}")],
    ])

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)


# ══════════════════════════════════════════════════════════════
#                       WALLET PURCHASE
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("walletbuy_"))
async def wallet_buy(call: CallbackQuery):
    plid = sint(call.data[10:])
    pl = db("""SELECT id, product_id, name, price, reseller_price, discount
               FROM plans WHERE id=?""", (plid,), one=True)
    if not pl:
        return await call.answer("Plan not found!", show_alert=True)

    prod = db("SELECT name FROM products WHERE id=?", (pl[1],), one=True)
    u = db("SELECT balance, is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)

    base = pl[4] if (u[1] and pl[4] > 0) else pl[3]
    if u[2]:
        base = base - (base * VIP_DISCOUNT / 100)
    if pl[5]:
        base = base - (base * pl[5] / 100)
    final = base

    if u[0] < final:
        return await call.answer(f"❌ Insufficient balance! Need {fmt(final)}.", show_alert=True)

    key = db("SELECT id, key_text FROM product_keys WHERE plan_id=? AND is_used=0 LIMIT 1", (plid,), one=True)
    if not key:
        return await call.answer("❌ Out of stock!", show_alert=True)

    # Atomic delivery
    db("UPDATE users SET balance=balance-?, total_spent=total_spent+?, total_orders=total_orders+1 WHERE user_id=?",
       (final, final, call.from_user.id))
    db("UPDATE product_keys SET is_used=1, used_by=?, used_at=? WHERE id=?",
       (call.from_user.id, now_str(), key[0]))
    db("""INSERT INTO orders (user_id, plan_id, plan_name, product_name, price_paid, delivered_key, purchase_date, status)
          VALUES (?, ?, ?, ?, ?, ?, ?, 'delivered')""",
       (call.from_user.id, plid, pl[2], prod[0] if prod else "", final, key[1], now_str()))

    log_activity(call.from_user.id, "PURCHASE", f"{prod[0] if prod else ''} - {pl[2]} - {final}")

    text = (
        f"🎉 <b>PURCHASE SUCCESSFUL!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Product: <b>{prod[0] if prod else 'N/A'}</b>\n"
        f"⏱ Plan: <b>{pl[2]}</b>\n"
        f"💰 Paid: <b>{fmt(final)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>YOUR KEY:</b>\n"
        f"<code>{key[1]}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{gs('ui_key_msg')}"
    )
    try:
        await call.message.edit_text(text, reply_markup=main_menu_kb(call.from_user.id))
    except Exception:
        await call.message.answer(text, reply_markup=main_menu_kb(call.from_user.id))

    try:
        await bot.send_message(
            ADMIN_ID,
            f"🛒 <b>NEW ORDER</b>\n"
            f"👤 <code>{call.from_user.id}</code>\n"
            f"📦 {prod[0] if prod else 'N/A'} - {pl[2]}\n"
            f"💰 {fmt(final)}"
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#                       QR PURCHASE
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("qrpay_"))
async def qr_buy(call: CallbackQuery, state: FSMContext):
    plid = sint(call.data[6:])
    pl = db("""SELECT id, product_id, name, price, reseller_price, discount
               FROM plans WHERE id=?""", (plid,), one=True)
    if not pl:
        return await call.answer("Plan not found!", show_alert=True)

    prod = db("SELECT name FROM products WHERE id=?", (pl[1],), one=True)
    u = db("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)

    base = pl[4] if (u[0] and pl[4] > 0) else pl[3]
    if u[1]:
        base = base - (base * VIP_DISCOUNT / 100)
    if pl[5]:
        base = base - (base * pl[5] / 100)
    final = base

    upi = gs("upi_id")
    static_qr = gs("static_qr_file_id")
    if not upi and not static_qr:
        return await call.answer("⚠️ Payment not configured yet. Contact admin.", show_alert=True)

    oid = f"ORD{call.from_user.id}{int(time.time())}"
    expires = int(time.time()) + 300
    qr_file = None

    if upi:
        payee = gs("payee_name", BRAND_NAME)
        link = upi_link(upi, payee, final, f"Order {oid}")
        db("""INSERT OR REPLACE INTO transactions
              (order_id, user_id, amount, status, created_at, expires_at, qr_data, purpose)
              VALUES (?, ?, ?, 'pending', ?, ?, ?, 'order')""",
           (oid, call.from_user.id, final, int(time.time()), expires, link))
        qr_file = make_qr(link)
    else:
        db("""INSERT OR REPLACE INTO transactions
              (order_id, user_id, amount, status, created_at, expires_at, qr_data, purpose)
              VALUES (?, ?, ?, 'pending', ?, ?, '', 'order')""",
           (oid, call.from_user.id, final, int(time.time()), expires))

    await state.update_data(
        buy_oid=oid,
        buy_amount=final,
        buy_plan_id=plid,
        buy_plan_name=pl[2],
        buy_product_name=prod[0] if prod else "",
    )

    text = (
        f"💳 <b>QR PAYMENT</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 {prod[0] if prod else 'N/A'} - {pl[2]}\n"
        f"💵 Amount: <b>{fmt(final)}</b>\n"
        f"🆔 Order: <code>{oid}</code>\n"
    )
    if upi:
        text += f"🏦 UPI: <code>{upi}</code>\n"
    text += (
        f"⏳ Valid for 5 minutes\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📱 Scan QR and pay exact amount\n"
        f"✅ Then tap 'I Have Paid'"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I Have Paid", callback_data=f"bpaid_{oid}")],
        [InlineKeyboardButton(text="🔄 Check Auto", callback_data=f"bautocheck_{oid}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="back_main")],
    ])

    try:
        await call.message.delete()
    except Exception:
        pass

    if qr_file:
        await bot.send_photo(call.from_user.id, qr_file, caption=text, reply_markup=kb)
    elif static_qr:
        await bot.send_photo(call.from_user.id, static_qr, caption=text, reply_markup=kb)
    else:
        await bot.send_message(call.from_user.id, text, reply_markup=kb)


@dp.callback_query(F.data.startswith("bpaid_"))
async def buy_paid(call: CallbackQuery, state: FSMContext):
    oid = call.data[6:]
    t = db("SELECT amount, status FROM transactions WHERE order_id=?", (oid,), one=True)
    if not t:
        return await call.answer("❌ Transaction not found!", show_alert=True)
    if t[1] == "paid":
        return await call.answer("✅ Already processed!", show_alert=True)

    await state.update_data(buy_proof_oid=oid, po=oid, pa=t[0])
    await state.set_state(U.buy_proof)
    try:
        await call.message.edit_text(
            f"📸 <b>Send Payment Proof</b>\n\n"
            f"💰 Amount: {fmt(t[0])}\n"
            f"🆔 Order: <code>{oid}</code>\n\n"
            f"Send screenshot OR UTR number:",
            reply_markup=bk("back_main")
        )
    except Exception:
        await call.message.answer(f"📸 Send proof for {oid}:")


@dp.message(U.buy_proof)
async def buy_proof_handler(m: Message, state: FSMContext):
    d = await state.get_data()
    oid = d.get("buy_proof_oid") or d.get("buy_oid")
    plid = d.get("buy_plan_id")
    final = d.get("buy_amount", 0)
    pl_name = d.get("buy_plan_name", "")
    prod_name = d.get("buy_product_name", "")

    if not oid:
        await state.clear()
        return await m.answer("❌ Session expired. Please try again.", reply_markup=main_menu_kb(m.from_user.id))

    proof_id = m.photo[-1].file_id if m.photo else ""
    utr = m.text or ""

    db("""INSERT INTO balance_requests
          (user_id, username, amount, method, proof_file_id, reference, status, created_at)
          VALUES (?, ?, ?, 'order', ?, ?, 'pending', ?)""",
       (m.from_user.id, m.from_user.username or "", final, proof_id,
        f"{oid}|PLAN:{plid}|UTR:{utr[:80]}", now_str()))

    await state.clear()
    await m.answer("✅ Proof submitted! Admin will verify and deliver your key.", reply_markup=main_menu_kb(m.from_user.id))

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve & Deliver", callback_data=f"order_approve_{oid}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"order_reject_{oid}"),
    ]])

    caption = (
        f"🛒 <b>ORDER PAYMENT</b>\n"
        f"👤 User: <code>{m.from_user.id}</code>\n"
        f"📦 {prod_name} - {pl_name}\n"
        f"💵 {fmt(final)}\n"
        f"🆔 {oid}"
    )

    try:
        if proof_id:
            await bot.send_photo(ADMIN_ID, proof_id, caption=caption, reply_markup=kb)
        else:
            await bot.send_message(ADMIN_ID, caption + f"\n📝 UTR: {utr[:200]}", reply_markup=kb)
    except Exception:
        pass


@dp.callback_query(F.data.startswith("bautocheck_"))
async def buy_auto_check(call: CallbackQuery):
    oid = call.data[11:]
    if gs("payment_mode") != "auto":
        return await call.answer("⏳ Auto verification is OFF. Send screenshot.", show_alert=True)
    if gs("auto_api_enabled", "0") != "1" or not gs("auto_api_url"):
        return await call.answer("⚠️ Auto API not configured.", show_alert=True)

    await call.answer("🔄 Checking payment...", show_alert=False)

    try:
        async with aiohttp.ClientSession() as session:
            url = f"{gs('auto_api_url')}?order_id={oid}&api_key={gs('auto_api_key')}"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if data.get("status") == "success" or data.get("paid") is True:
                        # Auto approve
                        t = db("SELECT user_id, amount, status FROM transactions WHERE order_id=?", (oid,), one=True)
                        if t and t[2] != "paid":
                            db("UPDATE transactions SET status='paid' WHERE order_id=?", (oid,))
                            fake = type('obj', (), {
                                'from_user': call.from_user,
                                'data': f'order_approve_{oid}',
                                'answer': call.answer,
                                'message': call.message,
                            })()
                            await order_approve(fake)
                            return
                    await call.answer("⏳ Payment not received yet.", show_alert=True)
    except Exception as e:
        await call.answer(f"⚠️ Error: {str(e)[:80]}", show_alert=True)


# ══════════════════════════════════════════════════════════════
#                       ORDER APPROVE / REJECT
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data.startswith("order_approve_"))
async def order_approve(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    oid = call.data[14:]

    req = db("""SELECT id, user_id, amount, reference FROM balance_requests
                WHERE reference LIKE ? ORDER BY id DESC LIMIT 1""",
             (f"{oid}|PLAN:%",), one=True)
    if not req:
        return await call.answer("Order request not found!", show_alert=True)

    try:
        parts = req[3].split("|")
        plan_part = [p for p in parts if p.startswith("PLAN:")]
        plid = sint(plan_part[0].split(":")[1]) if plan_part else None
    except Exception:
        plid = None

    if not plid:
        return await call.answer("Invalid order data!", show_alert=True)

    pl = db("SELECT id, name, product_id FROM plans WHERE id=?", (plid,), one=True)
    if not pl:
        return await call.answer("Plan not found!", show_alert=True)

    prod = db("SELECT name FROM products WHERE id=?", (pl[2],), one=True)
    key = db("SELECT id, key_text FROM product_keys WHERE plan_id=? AND is_used=0 LIMIT 1", (plid,), one=True)
    if not key:
        return await call.answer("❌ No key in stock!", show_alert=True)

    db("UPDATE product_keys SET is_used=1, used_by=?, used_at=? WHERE id=?",
       (req[1], now_str(), key[0]))
    db("UPDATE transactions SET status='paid' WHERE order_id=?", (oid,))
    db("UPDATE balance_requests SET status='approved', reviewed_at=? WHERE id=?", (now_str(), req[0]))
    db("""INSERT INTO orders (user_id, plan_id, plan_name, product_name, price_paid, delivered_key, purchase_date, status)
          VALUES (?, ?, ?, ?, ?, ?, ?, 'delivered')""",
       (req[1], plid, pl[0], prod[0] if prod else "", req[2], key[1], now_str()))
    db("UPDATE users SET total_spent=total_spent+?, total_orders=total_orders+1 WHERE user_id=?",
       (req[2], req[1]))

    await call.answer("✅ Approved and delivered!", show_alert=True)

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    text = (
        f"🎉 <b>ORDER DELIVERED!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 {prod[0] if prod else 'N/A'}\n"
        f"⏱ {pl[0]}\n"
        f"💰 {fmt(req[2])}\n"
        f"🔑 <b>Your Key:</b>\n"
        f"<code>{key[1]}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{gs('ui_key_msg')}"
    )
    try:
        await bot.send_message(req[1], text, reply_markup=main_menu_kb(req[1]))
    except Exception:
        pass


@dp.callback_query(F.data.startswith("order_reject_"))
async def order_reject(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    oid = call.data[13:]

    req = db("""SELECT id, user_id FROM balance_requests
                WHERE reference LIKE ? ORDER BY id DESC LIMIT 1""",
             (f"{oid}|PLAN:%",), one=True)
    if req:
        db("UPDATE balance_requests SET status='rejected', reviewed_at=? WHERE id=?", (now_str(), req[0]))
        try:
            await bot.send_message(req[1], "❌ Payment rejected. Please contact support.", reply_markup=main_menu_kb(req[1]))
        except Exception:
            pass

    db("UPDATE transactions SET status='rejected' WHERE order_id=?", (oid,))
    await call.answer("❌ Rejected!", show_alert=True)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════
#                       ADD BALANCE FLOW
# ══════════════════════════════════════════════════════════════

async def show_add_balance(call: CallbackQuery):
    mode = "Auto ✅" if gs("payment_mode") == "auto" else "Manual ⏳"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₹50", callback_data="amt_50"),
         InlineKeyboardButton(text="₹100", callback_data="amt_100")],
        [InlineKeyboardButton(text="₹200", callback_data="amt_200"),
         InlineKeyboardButton(text="₹500", callback_data="amt_500")],
        [InlineKeyboardButton(text="₹1000", callback_data="amt_1000"),
         InlineKeyboardButton(text="₹2000", callback_data="amt_2000")],
        [InlineKeyboardButton(text="✏️ Custom Amount", callback_data="amt_custom")],
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_main")],
    ])
    text = f"💰 <b>ADD BALANCE</b>\n━━━━━━━━━━━━━━━━━━\n🔧 Mode: {mode}\n\nSelect amount:"
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)


@dp.callback_query(F.data.startswith("amt_"))
async def amt_pick(call: CallbackQuery, state: FSMContext):
    v = call.data[4:]
    if v == "custom":
        await state.set_state(U.custom_amt)
        try:
            await call.message.edit_text("✏️ <b>Custom Amount</b>\n\nEnter amount (₹10 - ₹100000):", reply_markup=bk("back_main"))
        except Exception:
            await call.message.answer("Enter amount:")
        return
    await make_payment(call.from_user.id, sfloat(v), call)


@dp.message(U.custom_amt)
async def cust_amt(m: Message, state: FSMContext):
    try:
        a = float(m.text.strip())
        if a < 10:
            return await m.answer("❌ Minimum ₹10")
        if a > 100000:
            return await m.answer("❌ Maximum ₹1,00,000")
    except Exception:
        return await m.answer("❌ Invalid amount")
    await state.clear()
    await make_payment(m.from_user.id, a, m)


async def make_payment(uid, amount, target):
    upi = gs("upi_id")
    static_qr = gs("static_qr_file_id")
    if not upi and not static_qr:
        msg = "⚠️ Payment not configured. Contact admin."
        if isinstance(target, CallbackQuery):
            try:
                await target.message.edit_text(msg, reply_markup=bk("back_main"))
            except Exception:
                await target.message.answer(msg)
        else:
            await target.answer(msg)
        return

    oid = f"PAY{uid}{int(time.time())}"
    expires = int(time.time()) + 300
    qr_file = None

    if upi:
        payee = gs("payee_name", BRAND_NAME)
        link = upi_link(upi, payee, amount, f"Pay {oid}")
        db("""INSERT OR REPLACE INTO transactions
              (order_id, user_id, amount, status, created_at, expires_at, qr_data, purpose)
              VALUES (?, ?, ?, 'pending', ?, ?, ?, 'balance')""",
           (oid, uid, amount, int(time.time()), expires, link))
        qr_file = make_qr(link)
    else:
        db("""INSERT OR REPLACE INTO transactions
              (order_id, user_id, amount, status, created_at, expires_at, qr_data, purpose)
              VALUES (?, ?, ?, 'pending', ?, ?, '', 'balance')""",
           (oid, uid, amount, int(time.time()), expires))

    text = (
        f"🧾 <b>PAYMENT REQUEST</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💵 Amount: <b>{fmt(amount)}</b>\n"
        f"🆔 Order: <code>{oid}</code>\n"
    )
    if upi:
        text += f"🏦 UPI: <code>{upi}</code>\n"
    text += (
        "⏳ Valid for 5 minutes\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📱 Scan QR and pay\n"
        "✅ Then tap 'I Have Paid'"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I Have Paid", callback_data=f"paid_{oid}")],
        [InlineKeyboardButton(text="🔄 Check Auto", callback_data=f"autocheck_{oid}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="back_main")],
    ])

    try:
        if isinstance(target, CallbackQuery):
            await target.message.delete()
    except Exception:
        pass

    if qr_file:
        await bot.send_photo(uid, qr_file, caption=text, reply_markup=kb)
    elif static_qr:
        await bot.send_photo(uid, static_qr, caption=text, reply_markup=kb)
    else:
        await bot.send_message(uid, text, reply_markup=kb)


@dp.callback_query(F.data.startswith("paid_"))
async def paid(call: CallbackQuery, state: FSMContext):
    oid = call.data[5:]
    t = db("SELECT amount, status FROM transactions WHERE order_id=?", (oid,), one=True)
    if not t:
        return await call.answer("❌ Not found!", show_alert=True)
    if t[1] == "paid":
        return await call.answer("✅ Already credited!", show_alert=True)

    await state.update_data(po=oid, pa=t[0])
    await state.set_state(U.proof)
    try:
        await call.message.edit_text(
            f"📸 <b>Send Proof</b>\n\nAmount: {fmt(t[0])}\n\nSend screenshot OR UTR:",
            reply_markup=bk("back_main")
        )
    except Exception:
        await call.message.answer("Send screenshot:")


@dp.message(U.proof, F.photo)
async def proof_photo(m: Message, state: FSMContext):
    d = await state.get_data()
    oid, amt = d.get("po"), d.get("pa", 0)

    db("""INSERT INTO balance_requests
          (user_id, username, amount, method, proof_file_id, reference, status, created_at)
          VALUES (?, ?, ?, 'manual', ?, ?, 'pending', ?)""",
       (m.from_user.id, m.from_user.username or "", amt, m.photo[-1].file_id, oid, now_str()))

    await state.clear()
    await m.answer("✅ Proof sent! Admin will verify shortly.", reply_markup=main_menu_kb(m.from_user.id))

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Credit", callback_data=f"credit_{oid}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{oid}"),
    ]])

    try:
        await bot.send_photo(
            ADMIN_ID, m.photo[-1].file_id,
            caption=f"💰 <b>BALANCE PROOF</b>\n👤 <code>{m.from_user.id}</code>\n💵 {fmt(amt)}\n🆔 {oid}",
            reply_markup=kb
        )
    except Exception:
        pass


@dp.message(U.proof)
async def proof_text(m: Message, state: FSMContext):
    d = await state.get_data()
    oid, amt = d.get("po"), d.get("pa", 0)

    db("""INSERT INTO balance_requests
          (user_id, username, amount, method, reference, status, created_at)
          VALUES (?, ?, ?, 'manual', ?, 'pending', ?)""",
       (m.from_user.id, m.from_user.username or "", amt, f"{oid}|UTR:{m.text[:80]}", now_str()))

    await state.clear()
    await m.answer("✅ UTR sent! Admin will verify shortly.", reply_markup=main_menu_kb(m.from_user.id))

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Credit", callback_data=f"credit_{oid}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{oid}"),
    ]])

    try:
        await bot.send_message(
            ADMIN_ID,
            f"💰 <b>UTR RECEIVED</b>\n👤 <code>{m.from_user.id}</code>\n💵 {fmt(amt)}\n🆔 {oid}\n📝 {m.text[:200]}",
            reply_markup=kb
        )
    except Exception:
        pass


@dp.callback_query(F.data.startswith("autocheck_"))
async def auto_check(call: CallbackQuery):
    oid = call.data[10:]
    if gs("payment_mode") != "auto":
        return await call.answer("⏳ Auto OFF. Send screenshot.", show_alert=True)
    if gs("auto_api_enabled", "0") != "1" or not gs("auto_api_url"):
        return await call.answer("⚠️ API not configured.", show_alert=True)

    await call.answer("🔄 Checking...", show_alert=False)

    try:
        async with aiohttp.ClientSession() as session:
            url = f"{gs('auto_api_url')}?order_id={oid}&api_key={gs('auto_api_key')}"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if data.get("status") == "success" or data.get("paid") is True:
                        t = db("SELECT user_id, amount, status FROM transactions WHERE order_id=?", (oid,), one=True)
                        if t and t[2] != "paid":
                            db("UPDATE transactions SET status='paid' WHERE order_id=?", (oid,))
                            db("UPDATE users SET balance=balance+? WHERE user_id=?", (t[1], t[0]))
                            db("UPDATE balance_requests SET status='approved' WHERE reference=?", (oid,))
                            try:
                                await call.message.edit_text(
                                    f"✅ <b>Payment Verified!</b>\n\n+{fmt(t[1])} added to your wallet.",
                                    reply_markup=bk("back_main")
                                )
                            except Exception:
                                pass
                            return
                    await call.answer("⏳ Not received yet.", show_alert=True)
    except Exception as e:
        await call.answer(f"⚠️ Error: {str(e)[:80]}", show_alert=True)


@dp.callback_query(F.data.startswith("credit_"))
async def admin_credit(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    oid = call.data[7:]
    t = db("SELECT user_id, amount, status FROM transactions WHERE order_id=?", (oid,), one=True)
    if not t:
        return await call.answer("Not found!", show_alert=True)
    if t[2] == "paid":
        return await call.answer("Already credited!", show_alert=True)

    db("UPDATE transactions SET status='paid' WHERE order_id=?", (oid,))
    db("UPDATE users SET balance=balance+? WHERE user_id=?", (t[1], t[0]))
    db("UPDATE balance_requests SET status='approved', reviewed_at=? WHERE reference=?", (now_str(), oid))

    await call.answer("✅ Credited!", show_alert=True)
    try:
        await bot.send_message(t[0], f"✅ <b>Payment Verified!</b>\n\n+{fmt(t[1])} added to wallet.")
    except Exception:
        pass
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    oid = call.data[7:]
    t = db("SELECT user_id FROM transactions WHERE order_id=?", (oid,), one=True)
    if not t:
        return
    db("UPDATE transactions SET status='rejected' WHERE order_id=?", (oid,))
    db("UPDATE balance_requests SET status='rejected', reviewed_at=? WHERE reference=?", (now_str(), oid))
    await call.answer("❌ Rejected!", show_alert=True)
    try:
        await bot.send_message(t[0], "❌ Payment rejected. Contact support.")
    except Exception:
        pass
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#                       TICKETS
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "new_ticket")
async def new_ticket(call: CallbackQuery, state: FSMContext):
    await state.set_state(U.ticket)
    try:
        await call.message.edit_text(
            "📝 <b>New Ticket</b>\n\nDescribe your issue in detail:",
            reply_markup=bk("back_main")
        )
    except Exception:
        await call.message.answer("📝 Describe your issue:")


@dp.message(U.ticket)
async def ticket_save(m: Message, state: FSMContext):
    tid = db("INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)",
             (m.from_user.id, m.text, now_str()))
    await state.clear()
    await m.answer(f"✅ Ticket #{tid} submitted! Admin will reply soon.", reply_markup=main_menu_kb(m.from_user.id))

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Reply", callback_data=f"ticket_reply_{tid}"),
        InlineKeyboardButton(text="❌ Close", callback_data=f"ticket_close_{tid}"),
    ]])

    try:
        await bot.send_message(
            ADMIN_ID,
            f"🚨 <b>TICKET #{tid}</b>\n"
            f"👤 From: <code>{m.from_user.id}</code>\n"
            f"📅 {now_str()}\n\n"
            f"📝 {m.text}",
            reply_markup=kb
        )
    except Exception:
        pass


@dp.callback_query(F.data == "my_tickets")
async def my_tickets(call: CallbackQuery):
    ts = db("""SELECT id, message, status, reply, created_at
              FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 10""",
            (call.from_user.id,), all=True)
    if not ts:
        try:
            await call.message.edit_text("📭 No tickets found.", reply_markup=bk("back_main"))
        except Exception:
            await call.message.answer("📭 No tickets.")
        return

    text = "🎫 <b>MY TICKETS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for t in ts:
        icon = "🟢" if t[2] == "Open" else "🔴"
        text += f"\n#{t[0]} {icon} <b>{t[2]}</b>\n📝 {t[1][:100]}\n"
        if t[3]:
            text += f"💬 <b>Reply:</b> {t[3][:200]}\n"
        text += f"📅 {t[4]}\n"

    try:
        await call.message.edit_text(text[:4000], reply_markup=bk("back_main"))
    except Exception:
        await call.message.answer(text[:4000])


@dp.callback_query(F.data.startswith("ticket_reply_"))
async def ticket_reply_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    tid = sint(call.data[13:])
    await state.update_data(tid=tid)
    await state.set_state(U.ticket_reply)
    await call.message.edit_text(f"💬 Send reply for ticket #{tid}:")


@dp.message(U.ticket_reply)
async def ticket_reply_save(m: Message, state: FSMContext):
    d = await state.get_data()
    tid = d.get("tid")
    t = db("SELECT user_id FROM tickets WHERE id=?", (tid,), one=True)
    if not t:
        await state.clear()
        return await m.answer("Ticket not found!")

    db("UPDATE tickets SET reply=?, status='Closed', replied_at=? WHERE id=?", (m.text, now_str(), tid))
    await m.answer("✅ Reply sent!", reply_markup=admin_kb())

    try:
        await bot.send_message(t[0], f"📬 <b>Ticket #{tid} Reply</b>\n\n{m.text}", reply_markup=main_menu_kb(t[0]))
    except Exception:
        pass
    await state.clear()


@dp.callback_query(F.data.startswith("ticket_close_"))
async def ticket_close(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = sint(call.data[13:])
    db("UPDATE tickets SET status='Closed' WHERE id=?", (tid,))
    await call.answer("✅ Ticket closed!", show_alert=True)


# ══════════════════════════════════════════════════════════════
#                       COUPON REDEEM
# ══════════════════════════════════════════════════════════════

@dp.message(U.coupon)
async def coupon_save(m: Message, state: FSMContext):
    code = m.text.strip().upper()
    c = db("SELECT discount, max_uses, used FROM coupons WHERE code=?", (code,), one=True)
    if not c:
        await m.answer("❌ Invalid coupon code!", reply_markup=main_menu_kb(m.from_user.id))
    elif c[2] >= c[1]:
        await m.answer("❌ Coupon expired!", reply_markup=main_menu_kb(m.from_user.id))
    else:
        db("UPDATE users SET balance=balance+? WHERE user_id=?", (c[0], m.from_user.id))
        db("UPDATE coupons SET used=used+1 WHERE code=?", (code,))
        log_activity(m.from_user.id, "COUPON_REDEEM", f"{code} - {c[0]}")
        await m.answer(f"✅ +{fmt(c[0])} added to your wallet!", reply_markup=main_menu_kb(m.from_user.id))
    await state.clear()


# ══════════════════════════════════════════════════════════════
#                       NO-OP HANDLER
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "noop")
async def noop_cb(call: CallbackQuery):
    await call.answer()


# ══════════════════════════════════════════════════════════════
#                       WEB SERVER
# ══════════════════════════════════════════════════════════════

async def web_handle(request):
    return web.Response(text="✅ Elite X Bot is running!")


async def start_web():
    app = web.Application()
    app.router.add_get('/', web_handle)
    app.router.add_get('/health', web_handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEB_PORT)
    await site.start()
    logger.info(f"Web server running on port {WEB_PORT}")


# ══════════════════════════════════════════════════════════════
#                       PART 1 ENDS HERE
# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
#                       PART 2 STARTS HERE
#                       ADMIN PANEL
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
#                       ADMIN COMMAND
# ══════════════════════════════════════════════════════════════

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
            reply_markup=admin_kb()
        )
    except Exception:
        await call.message.answer("⚙️ Admin Panel", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                       STATISTICS
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
        f"• Used Keys: <b>{used_keys}</b>\n\n"
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
#                       STORE MANAGER
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
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("🛍️ <b>STORE MANAGER</b>\n\nChoose section:", reply_markup=kb)
    except Exception:
        await call.message.answer("🛍️ Store Manager", reply_markup=kb)


# ---------- CATEGORIES ----------

@dp.callback_query(F.data == "adm_cats")
async def adm_cats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Category", callback_data="adm_cat_add")],
        [InlineKeyboardButton(text="📋 List Categories", callback_data="adm_cat_list")],
        [InlineKeyboardButton(text="✏️ Edit Category", callback_data="adm_cat_edit_list")],
        [InlineKeyboardButton(text="🗑️ Delete Category", callback_data="adm_cat_del_list")],
        [InlineKeyboardButton(text="🔧 Maintenance Toggle", callback_data="adm_cat_mt_list")],
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
        reply_markup=bk("adm_cats")
    )


@dp.message(A.cat_name)
async def cat_name_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    await state.update_data(cat_name=m.text.strip())
    await state.set_state(A.cat_desc)
    await m.answer("📝 Step 2/3: Enter description (or type 'none'):")


@dp.message(A.cat_desc)
async def cat_desc_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    desc = "" if m.text.lower() == "none" else m.text.strip()
    await state.update_data(cat_desc=desc)
    await state.set_state(A.cat_emoji)
    await m.answer("😀 Step 3/3: Send an emoji (e.g., 📱):")


@dp.message(A.cat_emoji)
async def cat_emoji_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    d = await state.get_data()
    pos_row = db("SELECT COALESCE(MAX(position),0)+1 FROM categories", one=True)
    pos = pos_row[0] if pos_row else 1
    cid = db("INSERT INTO categories (name, emoji, description, position) VALUES (?, ?, ?, ?)",
             (d.get("cat_name", ""), m.text.strip()[:10], d.get("cat_desc", ""), pos))
    await state.clear()
    await m.answer(f"✅ Category added! ID: <code>{cid}</code>", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_cat_list")
async def cat_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cats = db("SELECT id, name, emoji, is_active, is_maintenance FROM categories ORDER BY position, id", all=True)
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
        reply_markup=kb
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
    await call.message.edit_text("⚠️ Select category to DELETE (this also deletes its panels, plans, and keys):", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("cat_del_"))
async def cat_del_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[8:])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"cat_del_yes_{cid}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_cats")],
    ])
    await call.message.edit_text(f"⚠️ Are you sure you want to delete category <code>{cid}</code>?\n\nThis will delete all panels, plans, and keys inside!", reply_markup=kb)


@dp.callback_query(F.data.startswith("cat_del_yes_"))
async def cat_del_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[12:])
    prods = db("SELECT id FROM products WHERE category_id=?", (cid,), all=True)
    for p in prods or []:
        plans = db("SELECT id FROM plans WHERE product_id=?", (p[0],), all=True)
        for pl in plans or []:
            db("DELETE FROM product_keys WHERE plan_id=?", (pl[0],))
        db("DELETE FROM plans WHERE product_id=?", (p[0],))
    db("DELETE FROM products WHERE category_id=?", (cid,))
    db("DELETE FROM categories WHERE id=?", (cid,))
    await call.answer("🗑️ Category deleted!", show_alert=True)
    await adm_cats(call)


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


# ---------- PANELS ----------

@dp.callback_query(F.data == "adm_panels")
async def adm_panels(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Panel", callback_data="adm_panel_add")],
        [InlineKeyboardButton(text="📋 List Panels", callback_data="adm_panel_list")],
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
    rows = [[InlineKeyboardButton(text=f"{c[2]} {c[1]}", callback_data=f"panel_add_cat_{c[0]}")] for c in cats]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_panels")])
    await call.message.edit_text("Select category for this panel:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("panel_add_cat_"))
async def panel_add_cat(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    cid = sint(call.data[14:])
    await state.update_data(panel_cat_id=cid)
    await state.set_state(A.panel_name)
    await call.message.edit_text("📝 Step 1/3: Enter panel name (e.g., MHA, DRIP):", reply_markup=bk("adm_panels"))


@dp.message(A.panel_name)
async def panel_name_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    await state.update_data(panel_name=m.text.strip())
    await state.set_state(A.panel_desc)
    await m.answer("📝 Step 2/3: Enter description (or 'none'):")


@dp.message(A.panel_desc)
async def panel_desc_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    desc = "" if m.text.lower() == "none" else m.text.strip()
    await state.update_data(panel_desc=desc)
    await state.set_state(A.panel_emoji)
    await m.answer("😀 Step 3/3: Send an emoji for this panel:")


@dp.message(A.panel_emoji)
async def panel_emoji_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    d = await state.get_data()
    cid = d.get("panel_cat_id")
    pos_row = db("SELECT COALESCE(MAX(position),0)+1 FROM products WHERE category_id=?", (cid,), one=True)
    pos = pos_row[0] if pos_row else 1
    pid = db("INSERT INTO products (category_id, name, description, emoji, position) VALUES (?, ?, ?, ?, ?)",
             (cid, d.get("panel_name", ""), d.get("panel_desc", ""), m.text.strip()[:10], pos))
    await state.clear()
    await m.answer(f"✅ Panel added! ID: <code>{pid}</code>", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_panel_list")
async def panel_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    panels = db("""SELECT p.id, p.name, p.emoji, p.is_active, p.is_maintenance, c.name
                   FROM products p LEFT JOIN categories c ON c.id=p.category_id
                   ORDER BY p.category_id, p.position, p.id""", all=True)
    if not panels:
        return await call.message.edit_text("📭 No panels.", reply_markup=bk("adm_panels"))

    text = "📦 <b>PANELS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for p in panels:
        st = "🟢" if p[3] else "🔴"
        mt = " 🔧" if p[4] else ""
        text += f"\n<b>ID {p[0]}</b> {st}{mt}\n{p[2]} {p[1]}\n📂 {p[5] or 'N/A'}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_panels"))


# ---------- PLANS ----------

@dp.callback_query(F.data == "adm_plans")
async def adm_plans(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Plan", callback_data="adm_plan_add")],
        [InlineKeyboardButton(text="📋 List Plans", callback_data="adm_plan_list")],
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
    panels = db("""SELECT p.id, p.name, c.name FROM products p
                   LEFT JOIN categories c ON c.id=p.category_id
                   ORDER BY p.category_id, p.position""", all=True)
    if not panels:
        return await call.answer("Add panel first!", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"📦 {p[1]} ({p[2] or 'N/A'})", callback_data=f"plan_add_panel_{p[0]}")] for p in panels]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_plans")])
    await call.message.edit_text("Select panel for this plan:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("plan_add_panel_"))
async def plan_add_panel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    pid = sint(call.data[15:])
    await state.update_data(plan_panel_id=pid)
    await state.set_state(A.plan_name)
    await call.message.edit_text("📝 Step 1/5: Enter plan name (e.g., 1 Day, 1 Month):", reply_markup=bk("adm_plans"))


@dp.message(A.plan_name)
async def plan_name_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    await state.update_data(plan_name=m.text.strip())
    await state.set_state(A.plan_price)
    await m.answer("💰 Step 2/5: Enter regular price (₹):")


@dp.message(A.plan_price)
async def plan_price_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    try:
        p = float(m.text.strip())
    except Exception:
        return await m.answer("❌ Invalid number. Try again:")
    await state.update_data(plan_price=p)
    await state.set_state(A.plan_rprice)
    await m.answer("👑 Step 3/5: Enter reseller price (₹), or 0 for same as regular:")


@dp.message(A.plan_rprice)
async def plan_rprice_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    try:
        rp = float(m.text.strip())
    except Exception:
        return await m.answer("❌ Invalid number. Try again:")
    await state.update_data(plan_rprice=rp)
    await state.set_state(A.plan_disc)
    await m.answer("💸 Step 4/5: Enter discount % (0-100), or 0 for none:")


@dp.message(A.plan_disc)
async def plan_disc_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    try:
        d = int(m.text.strip())
        if d < 0 or d > 100:
            raise ValueError
    except Exception:
        return await m.answer("❌ Enter a number between 0-100:")
    d_data = await state.get_data()
    pid = d_data.get("plan_panel_id")
    pos_row = db("SELECT COALESCE(MAX(position),0)+1 FROM plans WHERE product_id=?", (pid,), one=True)
    pos = pos_row[0] if pos_row else 1
    plid = db("""INSERT INTO plans (product_id, name, price, reseller_price, discount, position)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (pid, d_data.get("plan_name", ""), d_data.get("plan_price", 0),
               d_data.get("plan_rprice", 0), d, pos))
    await state.clear()
    await m.answer(
        f"✅ Plan added! ID: <code>{plid}</code>\n\n"
        f"📝 Now add keys using Key Manager.",
        reply_markup=admin_kb()
    )


@dp.callback_query(F.data == "adm_plan_list")
async def plan_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db("""SELECT pl.id, pl.name, pl.price, pl.reseller_price, pl.discount,
                         p.name, c.name
                  FROM plans pl
                  LEFT JOIN products p ON p.id=pl.product_id
                  LEFT JOIN categories c ON c.id=p.category_id
                  ORDER BY pl.product_id, pl.id DESC""", all=True)
    if not plans:
        return await call.message.edit_text("📭 No plans.", reply_markup=bk("adm_plans"))

    text = "⏱ <b>PLANS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for p in plans:
        keys = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (p[0],), one=True)[0]
        text += (
            f"\n<b>ID {p[0]}</b> — {p[1]}\n"
            f"📂 {p[6] or ''} / {p[5] or ''}\n"
            f"💰 {fmt(p[2])} | 👑 {fmt(p[3])} | 💸 {p[4]}%\n"
            f"🔑 Stock: {keys}\n"
        )
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_plans"))


# ---------- KEYS ----------

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
    plans = db("""SELECT pl.id, pl.name, p.name FROM plans pl
                  LEFT JOIN products p ON p.id=pl.product_id
                  ORDER BY pl.id""", all=True)
    if not plans:
        return await call.answer("Add plan first!", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"⏱ {pl[1]} ({pl[2] or 'N/A'})", callback_data=f"keys_add_{pl[0]}")] for pl in plans]
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
        "📥 <b>Add Keys</b>\n\n"
        "Send keys (1 per line).\n"
        "Example:\n<code>KEY-ABC-123\nKEY-DEF-456\nKEY-GHI-789</code>",
        reply_markup=bk("adm_keys")
    )


@dp.message(A.key_text)
async def keys_text_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    d = await state.get_data()
    plid = d.get("key_plan_id")
    keys = [k.strip() for k in m.text.split("\n") if k.strip()]
    if not keys:
        return await m.answer("❌ No valid keys found. Try again:")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for k in keys:
        c.execute("INSERT INTO product_keys (plan_id, key_text, added_at) VALUES (?, ?, ?)",
                  (plid, k, now_str()))
    conn.commit()
    conn.close()
    await state.clear()
    await m.answer(f"✅ <b>{len(keys)} keys added!</b>", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_keys_stock")
async def keys_stock(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db("""SELECT pl.id, pl.name, p.name, c.name FROM plans pl
                  LEFT JOIN products p ON p.id=pl.product_id
                  LEFT JOIN categories c ON c.id=p.category_id
                  ORDER BY pl.id""", all=True)
    if not plans:
        return await call.message.edit_text("📭 No plans.", reply_markup=bk("adm_keys"))
    text = "📊 <b>KEY STOCK</b>\n━━━━━━━━━━━━━━━━━━\n"
    for pl in plans:
        avail = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (pl[0],), one=True)[0]
        used = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=1", (pl[0],), one=True)[0]
        emoji = "🟢" if avail > 0 else "🔴"
        text += f"\n{emoji} <b>{pl[1]}</b>\n📂 {pl[3] or ''} / {pl[2] or ''}\n🟢 Free: {avail} | ❌ Used: {used}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_keys"))


@dp.callback_query(F.data == "adm_keys_view")
async def keys_view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plans = db("""SELECT pl.id, pl.name FROM plans pl ORDER BY pl.id""", all=True)
    if not plans:
        return await call.answer("No plans!", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"⏱ {pl[1]}", callback_data=f"keys_view_{pl[0]}")] for pl in plans]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="adm_keys")])
    await call.message.edit_text("Select plan to view keys:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("keys_view_"))
async def keys_view_plan(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    plid = sint(call.data[10:])
    keys = db("""SELECT id, key_text, is_used FROM product_keys
                 WHERE plan_id=? ORDER BY id DESC LIMIT 30""", (plid,), all=True)
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
        "🗑️ <b>Delete Key</b>\n\nSend the exact key text to delete:",
        reply_markup=bk("adm_keys")
    )


@dp.message(A.key_del)
async def keys_del_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
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
    await call.message.edit_text("⚠️ Delete ALL unused keys from every plan?", reply_markup=kb)


@dp.callback_query(F.data == "adm_keys_clear_yes")
async def keys_clear_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    db("DELETE FROM product_keys WHERE is_used=0")
    await call.answer("🧹 Cleared!", show_alert=True)
    await adm_keys(call)


# ══════════════════════════════════════════════════════════════
#                       USER MANAGER
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
    t = m.text.strip().lstrip("@")
    u = db("""SELECT user_id, first_name, username, balance, is_reseller, is_vip,
                     is_banned, joined_date
              FROM users WHERE user_id=? OR username=?""", (t, t), one=True)
    if not u:
        return await m.answer("❌ User not found!", reply_markup=bk("adm_users"))

    await state.clear()
    await send_user_panel(m, u)


async def send_user_panel(msg_target, u):
    tags = []
    if u[4]:
        tags.append("👑 Reseller")
    if u[5]:
        tags.append("🌟 VIP")
    type_str = " | ".join(tags) if tags else "Regular"
    banned = "🔴 BANNED" if u[6] else "🟢 Active"

    text = (
        f"👤 <b>USER DETAILS</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{u[0]}</code>\n"
        f"📛 Name: {u[1] or 'N/A'}\n"
        f"🔗 Username: @{u[2] or 'N/A'}\n"
        f"💰 Balance: <b>{fmt(u[3])}</b>\n"
        f"🔰 Type: {type_str}\n"
        f"📊 Status: {banned}\n"
        f"📅 Joined: {u[7]}\n"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Add Balance", callback_data=f"u_add_{u[0]}"),
         InlineKeyboardButton(text="💸 Remove Balance", callback_data=f"u_rem_{u[0]}")],
        [InlineKeyboardButton(text="🌟 Toggle VIP", callback_data=f"u_vip_{u[0]}"),
         InlineKeyboardButton(text="👑 Toggle Reseller", callback_data=f"u_res_{u[0]}")],
        [InlineKeyboardButton(text="🚫 Ban/Unban", callback_data=f"u_ban_{u[0]}")],
        [InlineKeyboardButton(text="📦 User Orders", callback_data=f"u_ord_{u[0]}")],
        [InlineKeyboardButton(text="🗑️ Delete User", callback_data=f"u_del_{u[0]}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_users")],
    ])

    if hasattr(msg_target, "answer"):
        await msg_target.answer(text, reply_markup=kb)
    else:
        await msg_target.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data == "adm_u_recent")
async def u_recent(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    users = db("""SELECT user_id, first_name, balance FROM users
                  ORDER BY joined_date DESC LIMIT 50""", all=True)
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
    await call.message.edit_text(f"💰 Send amount to ADD to user <code>{uid}</code>:", reply_markup=bk("adm_users"))


@dp.message(A.user_addbal)
async def u_add_bal_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    try:
        amt = float(m.text.strip())
        if amt <= 0:
            raise ValueError
    except Exception:
        return await m.answer("❌ Invalid amount. Try again:")
    d = await state.get_data()
    uid = d.get("target_uid")
    db("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
    await state.clear()
    await m.answer(f"✅ Added {fmt(amt)} to <code>{uid}</code>", reply_markup=admin_kb())
    try:
        await bot.send_message(uid, f"💰 <b>Balance Added!</b>\n\n+{fmt(amt)} credited by admin.", reply_markup=main_menu_kb(uid))
    except Exception:
        pass


@dp.callback_query(F.data.startswith("u_rem_"))
async def u_rem_bal(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    await state.update_data(target_uid=uid, action="rem")
    await state.set_state(A.user_rembal)
    await call.message.edit_text(f"💸 Send amount to REMOVE from user <code>{uid}</code>:", reply_markup=bk("adm_users"))


@dp.message(A.user_rembal)
async def u_rem_bal_do(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    try:
        amt = float(m.text.strip())
        if amt <= 0:
            raise ValueError
    except Exception:
        return await m.answer("❌ Invalid amount. Try again:")
    d = await state.get_data()
    uid = d.get("target_uid")
    db("UPDATE users SET balance=MAX(0, balance-?) WHERE user_id=?", (amt, uid))
    await state.clear()
    await m.answer(f"✅ Removed {fmt(amt)} from <code>{uid}</code>", reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("u_vip_"))
async def u_vip_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    cur = db("SELECT is_vip FROM users WHERE user_id=?", (uid,), one=True)[0]
    db("UPDATE users SET is_vip=? WHERE user_id=?", (0 if cur else 1, uid))
    await call.answer("✅ Toggled!", show_alert=True)


@dp.callback_query(F.data.startswith("u_res_"))
async def u_res_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    cur = db("SELECT is_reseller FROM users WHERE user_id=?", (uid,), one=True)[0]
    db("UPDATE users SET is_reseller=? WHERE user_id=?", (0 if cur else 1, uid))
    await call.answer("✅ Toggled!", show_alert=True)


@dp.callback_query(F.data.startswith("u_ban_"))
async def u_ban_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    cur = db("SELECT is_banned FROM users WHERE user_id=?", (uid,), one=True)[0]
    db("UPDATE users SET is_banned=? WHERE user_id=?", (0 if cur else 1, uid))
    await call.answer("✅ Toggled!", show_alert=True)


@dp.callback_query(F.data.startswith("u_ord_"))
async def u_ord_show(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    o = db("""SELECT id, product_name, plan_name, price_paid, delivered_key, purchase_date
              FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20""", (uid,), all=True)
    if not o:
        return await call.answer("No orders!", show_alert=True)
    text = f"📦 <b>Orders for {uid}</b>\n"
    for r in o:
        text += f"\n<b>#{r[0]}</b> {r[1]} - {r[2]}\n💰 {fmt(r[3])}\n🔑 <code>{truncate(r[4], 40)}</code>\n📅 {r[5]}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))


@dp.callback_query(F.data.startswith("u_del_"))
async def u_del_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[6:])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"u_del_yes_{uid}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_users")],
    ])
    await call.message.edit_text(f"⚠️ Delete user <code>{uid}</code> and all their data?", reply_markup=kb)


@dp.callback_query(F.data.startswith("u_del_yes_"))
async def u_del_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = sint(call.data[10:])
    db("DELETE FROM users WHERE user_id=?", (uid,))
    db("DELETE FROM orders WHERE user_id=?", (uid,))
    db("DELETE FROM balance_requests WHERE user_id=?", (uid,))
    await call.answer("🗑️ User deleted!", show_alert=True)
    await adm_users(call)


@dp.callback_query(F.data == "adm_u_balreq")
async def u_balreq(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    reqs = db("""SELECT id, user_id, amount, status, method, created_at
                 FROM balance_requests ORDER BY id DESC LIMIT 25""", all=True)
    if not reqs:
        return await call.message.edit_text("📭 No balance requests.", reply_markup=bk("adm_users"))
    text = "💰 <b>BALANCE REQUESTS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for r in reqs:
        icon = "🟢" if r[3] == "approved" else ("🔴" if r[3] == "rejected" else "🟡")
        text += f"\n{icon} <b>#{r[0]}</b>\n👤 <code>{r[1]}</code>\n💵 {fmt(r[2])}\n🔧 {r[4]} | {r[3]}\n📅 {r[5]}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))


@dp.callback_query(F.data == "adm_u_orders")
async def u_orders(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    o = db("""SELECT id, user_id, product_name, plan_name, price_paid, purchase_date
              FROM orders ORDER BY id DESC LIMIT 25""", all=True)
    if not o:
        return await call.message.edit_text("📭 No orders.", reply_markup=bk("adm_users"))
    text = "🧾 <b>RECENT ORDERS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for r in o:
        text += f"\n<b>#{r[0]}</b> — {r[2]} - {r[3]}\n👤 <code>{r[1]}</code>\n💰 {fmt(r[4])}\n📅 {r[5]}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))


@dp.callback_query(F.data == "adm_u_tickets")
async def u_tickets(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    ts = db("""SELECT id, user_id, message, created_at FROM tickets
               WHERE status='Open' ORDER BY id DESC LIMIT 15""", all=True)
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


# ══════════════════════════════════════════════════════════════
#                       PAYMENT SETTINGS
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_pay")
async def adm_pay(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    mode = gs("payment_mode", "manual")
    m = "🤖 AUTO" if mode == "auto" else "✋ MANUAL"
    api_on = gs("auto_api_enabled", "0") == "1"
    api_st = "✅ ON" if api_on else "❌ OFF"
    upi = gs("upi_id") or "❌ Not set"
    qr = "✅ Set" if gs("static_qr_file_id") else "❌ Not set"
    payee = gs("payee_name") or "Not set"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⚙️ Mode: {m}", callback_data="adm_pay_mode")],
        [InlineKeyboardButton(text=f"🏦 UPI: {truncate(upi, 20)}", callback_data="adm_set_upi")],
        [InlineKeyboardButton(text=f"🏷️ Payee: {truncate(payee, 20)}", callback_data="adm_set_payee")],
        [InlineKeyboardButton(text=f"🖼️ Static QR: {qr}", callback_data="adm_set_qr")],
        [InlineKeyboardButton(text=f"🔌 Auto API: {api_st}", callback_data="adm_api_menu")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("💳 <b>PAYMENT SETTINGS</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("💳 Payment Settings", reply_markup=kb)


@dp.callback_query(F.data == "adm_pay_mode")
async def pay_mode_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("payment_mode", "manual")
    new = "auto" if cur == "manual" else "manual"
    ss("payment_mode", new)
    await call.answer(f"✅ Mode: {new.upper()}", show_alert=True)
    await adm_pay(call)


@dp.callback_query(F.data == "adm_set_upi")
async def set_upi_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_upi)
    cur = gs("upi_id") or "Not set"
    await call.message.edit_text(f"🏦 Current UPI: <code>{cur}</code>\n\nSend new UPI ID:", reply_markup=bk("adm_pay"))


@dp.message(A.set_upi)
async def set_upi_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("upi_id", m.text.strip())
    await state.clear()
    await m.answer("✅ UPI saved! Auto QR will now generate.", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_set_payee")
async def set_payee_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_payee)
    cur = gs("payee_name") or BRAND_NAME
    await call.message.edit_text(f"🏷️ Current Payee: <b>{cur}</b>\n\nSend new payee name:", reply_markup=bk("adm_pay"))


@dp.message(A.set_payee)
async def set_payee_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("payee_name", m.text.strip())
    await state.clear()
    await m.answer("✅ Payee saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_set_qr")
async def set_qr_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_qr)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Remove QR", callback_data="adm_qr_remove")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_pay")],
    ])
    await call.message.edit_text("🖼️ Send QR image as photo:", reply_markup=kb)


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
    await call.answer("✅ Removed!", show_alert=True)
    await adm_pay(call)


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
        reply_markup=kb
    )


@dp.callback_query(F.data == "adm_api_toggle")
async def api_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("auto_api_enabled", "0")
    ss("auto_api_enabled", "0" if cur == "1" else "1")
    await call.answer("✅ Toggled!", show_alert=True)
    await adm_api_menu(call)


@dp.callback_query(F.data == "adm_api_setkey")
async def api_setkey_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_api_key)
    await call.message.edit_text("🔑 Send API key:", reply_markup=bk("adm_api_menu"))


@dp.message(A.set_api_key)
async def api_setkey_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("auto_api_key", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_api_seturl")
async def api_seturl_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_api_url)
    await call.message.edit_text("🌐 Send API URL:", reply_markup=bk("adm_api_menu"))


@dp.message(A.set_api_url)
async def api_seturl_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("auto_api_url", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                       BROADCAST
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
        await call.message.edit_text("📢 <b>BROADCAST</b>\n\nSend text/photo/video/doc to all users.", reply_markup=kb)
    except Exception:
        await call.message.answer("📢 Broadcast", reply_markup=kb)


@dp.callback_query(F.data == "adm_bc_send")
async def bc_send_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.bc_msg)
    await call.message.edit_text("📢 Send message (text/photo/video/doc):", reply_markup=bk("adm_broadcast"))


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
    db("INSERT INTO broadcasts (content, sent, failed, created_at) VALUES (?, ?, ?, ?)",
       (content, sent, failed, now_str()))

    try:
        await status_msg.edit_text(
            f"✅ <b>Broadcast Complete!</b>\n\n🟢 Sent: {sent}\n🔴 Failed: {failed}\n📊 Total: {total}",
            reply_markup=admin_kb()
        )
    except Exception:
        pass
    await state.clear()


@dp.callback_query(F.data == "adm_bc_history")
async def bc_history(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    hs = db("SELECT id, content, sent, failed, created_at FROM broadcasts ORDER BY id DESC LIMIT 10", all=True)
    if not hs:
        return await call.message.edit_text("📭 No broadcast history.", reply_markup=bk("adm_broadcast"))
    text = "📜 <b>BROADCAST HISTORY</b>\n━━━━━━━━━━━━━━━━━━\n"
    for h in hs:
        text += f"\n<b>#{h[0]}</b> — 📅 {h[4]}\n🟢 {h[2]} | 🔴 {h[3]}\n📝 {truncate(h[1], 100)}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_broadcast"))


# ══════════════════════════════════════════════════════════════
#                       MARKETING
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_mkt")
async def adm_mkt(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ Coupons", callback_data="adm_cp")],
        [InlineKeyboardButton(text="🎁 Daily Gift", callback_data="adm_gift")],
        [InlineKeyboardButton(text="🤝 Refer Reward", callback_data="adm_ref")],
        [InlineKeyboardButton(text="👑 Reseller Settings", callback_data="adm_res")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("🎯 <b>MARKETING</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("🎯 Marketing", reply_markup=kb)


# ---------- COUPONS ----------

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
    await state.update_data(cp_code=m.text.strip().upper())
    await state.set_state(A.cp_disc)
    await m.answer("💰 Step 2/3: Send discount amount (₹):")


@dp.message(A.cp_disc)
async def cp_disc_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    try:
        d = float(m.text.strip())
    except Exception:
        return await m.answer("❌ Invalid number:")
    await state.update_data(cp_disc=d)
    await state.set_state(A.cp_max)
    await m.answer("🔢 Step 3/3: Send max uses:")


@dp.message(A.cp_max)
async def cp_max_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    try:
        mx = int(m.text.strip())
    except Exception:
        return await m.answer("❌ Invalid number:")
    d = await state.get_data()
    db("""INSERT OR REPLACE INTO coupons (code, discount, max_uses, created_at)
          VALUES (?, ?, ?, ?)""",
       (d.get("cp_code"), d.get("cp_disc", 0), mx, now_str()))
    await state.clear()
    await m.answer(f"✅ Coupon <b>{d.get('cp_code')}</b> created!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_cp_view")
async def cp_view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cps = db("SELECT code, discount, max_uses, used, created_at FROM coupons ORDER BY created_at DESC", all=True)
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
    code = m.text.strip().upper()
    db("DELETE FROM coupons WHERE code=?", (code,))
    await state.clear()
    await m.answer(f"🗑️ Coupon <b>{code}</b> deleted!", reply_markup=admin_kb())


# ---------- GIFT ----------

@dp.callback_query(F.data == "adm_gift")
async def adm_gift(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    cur = gs("daily_gift_price", "0")
    await state.set_state(A.set_gift)
    await call.message.edit_text(
        f"🎁 <b>Daily Gift</b>\n\nCurrent: {fmt(cur)}\n\nSend new amount (0 to disable):",
        reply_markup=bk("adm_mkt")
    )


@dp.message(A.set_gift)
async def gift_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("daily_gift_price", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


# ---------- REFER ----------

@dp.callback_query(F.data == "adm_ref")
async def adm_ref(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    cur = gs("refer_earn_amount", "0")
    await state.set_state(A.set_refer)
    await call.message.edit_text(
        f"🤝 <b>Refer Reward</b>\n\nCurrent: {fmt(cur)}\n\nSend reward amount (0 to disable):",
        reply_markup=bk("adm_mkt")
    )


@dp.message(A.set_refer)
async def refer_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("refer_earn_amount", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


# ---------- RESELLER ----------

@dp.callback_query(F.data == "adm_res")
async def adm_res(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    st = gs("reseller_system_status", "ON")
    fee = gs("reseller_setup_fee", "500")
    mn = gs("reseller_min_balance", "1000")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔛 System: {st}", callback_data="adm_res_tog")],
        [InlineKeyboardButton(text=f"💰 Setup Fee: {fmt(fee)}", callback_data="adm_res_fee")],
        [InlineKeyboardButton(text=f"💳 Min Balance: {fmt(mn)}", callback_data="adm_res_min")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_mkt")],
    ])
    await call.message.edit_text("👑 <b>RESELLER SETTINGS</b>", reply_markup=kb)


@dp.callback_query(F.data == "adm_res_tog")
async def res_tog(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("reseller_system_status", "ON")
    ss("reseller_system_status", "OFF" if cur == "ON" else "ON")
    await adm_res(call)


@dp.callback_query(F.data == "adm_res_fee")
async def res_fee(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.res_fee)
    await call.message.edit_text("💰 Send new setup fee (₹):", reply_markup=bk("adm_res"))


@dp.message(A.res_fee)
async def res_fee_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("reseller_setup_fee", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_res_min")
async def res_min(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.res_min)
    await call.message.edit_text("💳 Send new minimum balance (₹):", reply_markup=bk("adm_res"))


@dp.message(A.res_min)
async def res_min_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("reseller_min_balance", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                       MENU DESIGNER
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
    btns = db("SELECT id, label, emoji, action, is_active FROM menu_buttons ORDER BY position", all=True)
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
    b = db("SELECT label, emoji, action, is_active FROM menu_buttons WHERE id=?", (bid,), one=True)
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
        f"🎨 <b>Button</b>\n\nLabel: {b[2]} {b[1]}\nAction: {b[2]}\nStatus: {st}",
        reply_markup=kb
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
    c = db("SELECT is_active FROM menu_buttons WHERE id=?", (bid,), one=True)[0]
    db("UPDATE menu_buttons SET is_active=? WHERE id=?", (0 if c else 1, bid))
    await call.answer("✅ Toggled!", show_alert=True)
    await menu_list(call)


@dp.callback_query(F.data.startswith("mbd_"))
async def menu_del(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    bid = sint(call.data[4:])
    db("DELETE FROM menu_buttons WHERE id=?", (bid,))
    await call.answer("🗑️ Deleted!", show_alert=True)
    await menu_list(call)


@dp.callback_query(F.data == "adm_menu_add")
async def menu_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.menu_add_label)
    await call.message.edit_text("🎨 Step 1/3: Send button label:", reply_markup=bk("adm_menu"))


@dp.message(A.menu_add_label)
async def menu_add_label(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    await state.update_data(menu_label=m.text.strip()[:40])
    await state.set_state(A.menu_add_emoji)
    await m.answer("😀 Step 2/3: Send emoji (or 'none'):")


@dp.message(A.menu_add_emoji)
async def menu_add_emoji(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    e = "" if m.text.lower() == "none" else m.text.strip()[:10]
    await state.update_data(menu_emoji=e)
    await state.set_state(A.menu_add_action)
    await m.answer(
        "⚙️ Step 3/3: Send action:\n"
        "shop / profile / addbalance / support / daily_gift / redeem_coupon / reseller / vip"
    )


@dp.message(A.menu_add_action)
async def menu_add_action(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    action = m.text.strip().lower()
    valid = {"shop", "profile", "addbalance", "support", "daily_gift", "redeem_coupon", "reseller", "vip"}
    if action not in valid:
        return await m.answer("❌ Invalid action. Try again:")
    d = await state.get_data()
    pos_row = db("SELECT COALESCE(MAX(position),0)+1 FROM menu_buttons", one=True)
    pos = pos_row[0] if pos_row else 1
    db("""INSERT INTO menu_buttons (label, emoji, action, position, is_active, row_group)
          VALUES (?, ?, ?, ?, 1, ?)""",
       (d.get("menu_label"), d.get("menu_emoji", ""), action, pos, pos // 2))
    await state.clear()
    await m.answer("✅ Button added!", reply_markup=admin_kb())


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
    await call.message.edit_text("👤 <b>PROFILE FIELDS</b>\n\nToggle visibility:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("pft_"))
async def pf_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    key = call.data[4:]
    c = db("SELECT is_visible FROM profile_fields WHERE field_key=?", (key,), one=True)[0]
    db("UPDATE profile_fields SET is_visible=? WHERE field_key=?", (0 if c else 1, key))
    await call.answer("✅ Toggled!", show_alert=True)
    await adm_pf(call)


# ══════════════════════════════════════════════════════════════
#                       MESSAGE EDITOR
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
    await state.set_state(A.msg_welcome)
    await call.message.edit_text("📝 Send new welcome message:", reply_markup=bk("adm_msg"))


@dp.message(A.msg_welcome)
async def am_w_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("welcome_text", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "am_c")
async def am_c(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.msg_cat)
    await call.message.edit_text("📝 Send new category page message:", reply_markup=bk("adm_msg"))


@dp.message(A.msg_cat)
async def am_c_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("ui_category_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "am_p")
async def am_p(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.msg_prod)
    await call.message.edit_text("📝 Send new panel page message:", reply_markup=bk("adm_msg"))


@dp.message(A.msg_prod)
async def am_p_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("ui_product_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "am_pl")
async def am_pl(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.msg_plan)
    await call.message.edit_text("📝 Send new plan page message:", reply_markup=bk("adm_msg"))


@dp.message(A.msg_plan)
async def am_pl_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("ui_plan_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "am_k")
async def am_k(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.msg_key)
    await call.message.edit_text("📝 Send new key delivery message:", reply_markup=bk("adm_msg"))


@dp.message(A.msg_key)
async def am_k_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("ui_key_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                       CO-ADMINS
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_coadmin")
async def adm_coadmin(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Only owner can manage co-admins.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add", callback_data="adm_ca_add"),
         InlineKeyboardButton(text="➖ Remove", callback_data="adm_ca_rem")],
        [InlineKeyboardButton(text="📋 List", callback_data="adm_ca_list")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("🤝 <b>CO-ADMINS</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("🤝 Co-Admins", reply_markup=kb)


@dp.callback_query(F.data == "adm_ca_add")
async def ca_add(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(A.coadmin_add)
    await call.message.edit_text("🤝 Send user ID to add as co-admin:", reply_markup=bk("adm_coadmin"))


@dp.message(A.coadmin_add)
async def ca_add_save(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    try:
        uid = int(m.text.strip())
    except Exception:
        return await m.answer("❌ Invalid ID:")
    u = db("SELECT first_name FROM users WHERE user_id=?", (uid,), one=True)
    name = u[0] if u else "Unknown"
    db("INSERT OR IGNORE INTO co_admins (user_id, name, added_at) VALUES (?, ?, ?)", (uid, name, now_str()))
    await state.clear()
    await m.answer(f"✅ Added <code>{uid}</code> as co-admin!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_ca_rem")
async def ca_rem(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(A.coadmin_remove)
    await call.message.edit_text("🤝 Send user ID to remove:", reply_markup=bk("adm_coadmin"))


@dp.message(A.coadmin_remove)
async def ca_rem_save(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    try:
        uid = int(m.text.strip())
    except Exception:
        return await m.answer("❌ Invalid ID:")
    db("DELETE FROM co_admins WHERE user_id=?", (uid,))
    await state.clear()
    await m.answer("✅ Removed!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_ca_list")
async def ca_list(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    cas = db("SELECT user_id, name FROM co_admins", all=True)
    text = "🤝 <b>CO-ADMINS</b>\n"
    for c in cas or []:
        text += f"\n<code>{c[0]}</code> — {c[1]}"
    if not cas:
        text += "\nNone."
    await call.message.edit_text(text, reply_markup=bk("adm_coadmin"))


# ══════════════════════════════════════════════════════════════
#                       SETTINGS
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_settings")
async def adm_settings(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    logo = "✅ Set" if gs("admin_logo_file_id") else "❌ Not set"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🖼️ Logo: {logo}", callback_data="adm_set_logo")],
        [InlineKeyboardButton(text="✈️ Set Telegram Support", callback_data="adm_set_tg")],
        [InlineKeyboardButton(text="📱 Set WhatsApp Support", callback_data="adm_set_wa")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text("⚙️ <b>SETTINGS</b>", reply_markup=kb)
    except Exception:
        await call.message.answer("⚙️ Settings", reply_markup=kb)


@dp.callback_query(F.data == "adm_set_logo")
async def set_logo_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_logo)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Remove Logo", callback_data="adm_logo_remove")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_settings")],
    ])
    await call.message.edit_text("🖼️ Send logo photo:", reply_markup=kb)


@dp.message(A.set_logo, F.photo)
async def set_logo_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("admin_logo_file_id", m.photo[-1].file_id)
    await state.clear()
    await m.answer("✅ Logo saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_logo_remove")
async def logo_remove(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    ss("admin_logo_file_id", "")
    await call.answer("✅ Removed!", show_alert=True)
    await adm_settings(call)


@dp.callback_query(F.data == "adm_set_tg")
async def set_tg_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_tg)
    cur = gs("support_telegram") or "Not set"
    await call.message.edit_text(f"✈️ Current: {cur}\n\nSend Telegram support URL:", reply_markup=bk("adm_settings"))


@dp.message(A.set_tg)
async def set_tg_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("support_telegram", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


@dp.callback_query(F.data == "adm_set_wa")
async def set_wa_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_wa)
    cur = gs("support_whatsapp") or "Not set"
    await call.message.edit_text(f"📱 Current: {cur}\n\nSend WhatsApp support URL:", reply_markup=bk("adm_settings"))


@dp.message(A.set_wa)
async def set_wa_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("support_whatsapp", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                       MAINTENANCE
# ══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "adm_maint")
async def adm_maint(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    st = "🔴 ON" if gs("global_maintenance") == "1" else "🟢 OFF"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🌐 Global: {st}", callback_data="adm_mt_tog")],
        [InlineKeyboardButton(text="✏️ Edit Message", callback_data="adm_mt_edit")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="adm_back")],
    ])
    try:
        await call.message.edit_text(
            "🛠️ <b>MAINTENANCE MODE</b>\n\n"
            "🔧 Per-category & per-product maintenance available in their sections.",
            reply_markup=kb
        )
    except Exception:
        await call.message.answer("🛠️ Maintenance", reply_markup=kb)


@dp.callback_query(F.data == "adm_mt_tog")
async def mt_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cur = gs("global_maintenance")
    ss("global_maintenance", "0" if cur == "1" else "1")
    await adm_maint(call)


@dp.callback_query(F.data == "adm_mt_edit")
async def mt_edit(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(A.set_maint)
    await call.message.edit_text("✏️ Send new maintenance message:", reply_markup=bk("adm_maint"))


@dp.message(A.set_maint)
async def mt_edit_save(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    ss("maintenance_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())


# ══════════════════════════════════════════════════════════════
#                       FALLBACK HANDLER
# ══════════════════════════════════════════════════════════════

@dp.message()
async def fallback(m: Message, state: FSMContext):
    if not m.text:
        return
    if m.text.startswith("/"):
        return
    cur = await state.get_state()
    if cur:
        return
    await m.answer("Use /start to open the menu.", reply_markup=main_menu_kb(m.from_user.id))


@dp.callback_query()
async def fallback_cb(call: CallbackQuery):
    await call.answer("⚠️ Unknown option.")


# ══════════════════════════════════════════════════════════════
#                       MAIN FUNCTION
# ══════════════════════════════════════════════════════════════

async def main():
    init_db()
    logger.info("✅ Database initialized")
    await start_web()
    logger.info("✅ Web server started")
    logger.info("🚀 Bot is starting...")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Polling error: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Bot stopped.")