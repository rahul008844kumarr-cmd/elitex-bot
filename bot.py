#!/usr/bin/env python3
"""
ELITE X CONFIG - ULTIMATE EDITION
Auto + Manual Payment | Menu Manager | Profile Toggle | User Delete | Full CRUD
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
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, BufferedInputFile
)

try:
    import qrcode
except ImportError:
    qrcode = None

# ==============================================================================
# CONFIG
# ==============================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "elitexbot")
BRAND_NAME = os.getenv("BRAND_NAME", "ELITE X CONFIG")
DB_PATH = os.getenv("DB_PATH", "elitex_bot.db")

VIP_DISCOUNT = 10.0
VIP_PRICE = 1000.0

DEFAULT_EMOJIS = {
    'product_store': '6163205892834598715', 'profile': '5258011929993026890',
    'add_balance': '5985630530111020079', 'support': '5967280668885913944',
    'back': '5877536313623711363', 'reseller': '5886505193180239900',
    'vip': '5206607081334906820'
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ==============================================================================
# HELPERS
# ==============================================================================
def fmt_curr(a):
    return f"₹{a:,.2f}"

def fancy(text):
    bold_caps = {chr(ord("A") + i): chr(0x1D400 + i) for i in range(26)}
    small_caps = {"a":"ᴀ","b":"ʙ","c":"ᴄ","d":"ᴅ","e":"ᴇ","f":"ꜰ","g":"ɢ","h":"ʜ","i":"ɪ","j":"ᴊ","k":"ᴋ","l":"ʟ","m":"ᴍ","n":"ɴ","o":"ᴏ","p":"ᴘ","q":"ǫ","r":"ʀ","s":"s","t":"ᴛ","u":"ᴜ","v":"ᴠ","w":"ᴡ","x":"x","y":"ʏ","z":"ᴢ"}
    out, at_start = [], True
    for ch in str(text):
        if ch.isascii() and ch.isalpha():
            out.append(bold_caps.get(ch.upper(), ch) if at_start else small_caps.get(ch.lower(), ch))
            at_start = False
        else:
            out.append(ch)
            if ch.isspace() or ch in "/\\|•": at_start = True
    return "".join(out)

def safe_float(v, d=0.0):
    if v is None or v == "": return d
    try: return float(v)
    except: return d

def build_upi_link(upi, name, amt, note=""):
    s = f"upi://pay?pa={quote(upi)}&pn={quote(name)}&am={amt:.2f}&cu=INR"
    if note: s += f"&tn={quote(note)}"
    return s

def gen_qr(data):
    if qrcode is None: return None
    img = qrcode.make(data)
    buf = io.BytesIO(); buf.name = "qr.png"
    img.save(buf, format="PNG"); buf.seek(0)
    return buf

# ==============================================================================
# DATABASE
# ==============================================================================
def db(query, params=(), fetchone=False, fetchall=False, commit=True):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    try:
        c.execute(query, params)
        if fetchone: r = c.fetchone()
        elif fetchall: r = c.fetchall()
        else: r = None
        if commit: conn.commit()
        return r
    except Exception as e:
        logger.error(f"DB: {e} | {query}")
        return None
    finally: conn.close()

def get_setting(k, d=""):
    v = db("SELECT value FROM settings WHERE key=?", (k,), fetchone=True)
    return v[0] if v and v[0] else d

def set_setting(k, v):
    db("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, balance REAL DEFAULT 0.0,
        is_reseller INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0,
        joined_date TEXT, last_gift TEXT DEFAULT '')''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, emoji TEXT DEFAULT '📂',
        is_active INTEGER DEFAULT 1, is_maintenance INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT,
        price REAL DEFAULT 0.0, reseller_price REAL DEFAULT 0.0, stock INTEGER DEFAULT 0,
        apk_link TEXT, validity TEXT, device_limit TEXT,
        is_active INTEGER DEFAULT 1, is_maintenance INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS product_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, key_text TEXT, is_used INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_name TEXT,
        price_paid REAL, delivered_key TEXT, purchase_date TEXT, status TEXT DEFAULT 'delivered')''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS balance_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        amount REAL, method TEXT, proof_file_id TEXT, reference TEXT,
        status TEXT DEFAULT 'pending', created_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT,
        status TEXT DEFAULT 'Open', created_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS coupons (
        code TEXT PRIMARY KEY, discount REAL, max_uses INTEGER, used INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS co_admins (
        user_id INTEGER PRIMARY KEY, name TEXT, added_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        order_id TEXT PRIMARY KEY, user_id INTEGER, amount REAL, status TEXT DEFAULT 'pending',
        created_at INTEGER, expires_at INTEGER, qr_data TEXT, api_order_id TEXT)''')
    
    # NEW: Menu buttons (for dynamic main menu)
    c.execute('''CREATE TABLE IF NOT EXISTS menu_buttons (
        id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, emoji TEXT DEFAULT '',
        action TEXT, position INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
        row_group INTEGER DEFAULT 0)''')
    
    # NEW: Profile fields visibility
    c.execute('''CREATE TABLE IF NOT EXISTS profile_fields (
        field_key TEXT PRIMARY KEY, label TEXT, is_visible INTEGER DEFAULT 1)''')
    
    # Default settings
    defaults = [
        ('bot_status', 'ON'), ('global_maintenance', '0'),
        ('maintenance_msg', '🛠 Bot under maintenance.'),
        ('welcome_text', '⚡ Welcome to ELITE X CONFIG ⚡'),
        ('upi_id', ''), ('payee_name', BRAND_NAME),
        ('support_telegram', 'https://t.me/YourSupport'),
        ('support_whatsapp', 'https://wa.me/YourNumber'),
        ('daily_gift_price', '0'), ('refer_earn_amount', '0'),
        ('admin_logo_file_id', ''),
        ('ui_category_msg', '📂 Select a Category:'),
        ('ui_product_msg', '📦 Select a Product:'),
        ('ui_key_msg', '🎉 Thank you for your purchase!'),
        ('ui_balance_msg', '💰 Add Balance'),
        ('payment_mode', 'manual'),  # manual OR auto
        ('auto_api_key', ''), ('auto_api_url', ''),
        ('auto_api_enabled', '0'),
        ('referral_enabled', '0')
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    
    # Default menu buttons
    menu_count = c.execute("SELECT COUNT(*) FROM menu_buttons").fetchone()[0]
    if menu_count == 0:
        default_menus = [
            ("Product Store", "🛍️", "shop", 1, 1, 0),
            ("My Profile", "👤", "profile", 2, 1, 1),
            ("Add Balance", "💰", "addbalance", 3, 1, 1),
            ("Support", "🎧", "support", 4, 1, 2),
            ("Daily Gift", "🎁", "daily_gift", 5, 1, 2),
            ("Redeem Coupon", "🎟️", "redeem_coupon", 6, 1, 3)
        ]
        for m in default_menus:
            c.execute("INSERT INTO menu_buttons (label, emoji, action, position, is_active, row_group) VALUES (?, ?, ?, ?, ?, ?)", m)
    
    # Default profile fields
    pf_count = c.execute("SELECT COUNT(*) FROM profile_fields").fetchone()[0]
    if pf_count == 0:
        fields = [
            ("user_id", "User ID", 1), ("name", "Name", 1),
            ("balance", "Balance", 1), ("account_type", "Account Type", 1),
            ("joined_date", "Join Date", 1), ("total_spent", "Total Spent", 1),
            ("total_orders", "Total Orders", 1)
        ]
        for f in fields:
            c.execute("INSERT INTO profile_fields (field_key, label, is_visible) VALUES (?, ?, ?)", f)
    
    conn.commit(); conn.close()

# ==============================================================================
# MIDDLEWARE
# ==============================================================================
class SecurityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        uid = event.from_user.id
        if uid != ADMIN_ID:
            u = db("SELECT is_banned FROM users WHERE user_id=?", (uid,), fetchone=True)
            if u and u[0] == 1:
                msg = "🚫 Banned."
                if isinstance(event, Message): await event.answer(msg)
                else: await event.answer(msg, show_alert=True)
                return
            if get_setting("global_maintenance") == "1":
                msg = get_setting("maintenance_msg", "🛠 Maintenance.")
                if isinstance(event, Message): await event.answer(msg)
                else: await event.answer("⚠️ Maintenance.", show_alert=True)
                return
        return await handler(event, data)

dp.message.middleware(SecurityMiddleware())
dp.callback_query.middleware(SecurityMiddleware())

# ==============================================================================
# FSM STATES
# ==============================================================================
class UserStates(StatesGroup):
    wait_for_ticket = State()
    wait_for_coupon = State()
    wait_for_custom_amt = State()
    wait_for_proof = State()

class AdminStates(StatesGroup):
    # Category
    cat_add_name = State(); cat_add_emoji = State()
    cat_edit_field = State(); cat_edit_value = State()
    # Product
    prod_add_cat = State(); prod_add_name = State(); prod_add_price = State()
    prod_add_rprice = State(); prod_add_validity = State(); prod_add_device = State()
    prod_add_apk = State(); prod_add_keys = State()
    prod_edit_field = State(); prod_edit_value = State()
    prod_add_keys2 = State()
    # User
    user_search = State(); user_addbal = State(); user_rembal = State()
    # Marketing
    bc_msg = State(); cp_code = State(); cp_disc = State(); cp_max = State()
    # Settings
    set_logo = State(); set_upi = State(); set_payee = State()
    set_tg = State(); set_wa = State(); set_gift = State(); set_refer = State()
    set_maint_msg = State()
    # Messages
    msg_welcome = State(); msg_cat = State(); msg_prod = State(); msg_key = State()
    msg_balance = State()
    # Menu Manager
    menu_add_label = State(); menu_add_emoji = State(); menu_add_action = State()
    menu_edit_field = State(); menu_edit_value = State()
    # Auto API
    set_auto_key = State(); set_auto_url = State()
    # Co-admin
    coadmin_add = State(); coadmin_remove = State()
    # Tickets
    ticket_reply = State()

# ==============================================================================
# KEYBOARDS
# ==============================================================================
def get_emoji_icon(slot):
    return get_setting(f"emoji_{slot}", DEFAULT_EMOJIS.get(slot, ""))

def main_menu_kb(uid=None):
    rows = []
    buttons = db("SELECT id, label, emoji, action, row_group FROM menu_buttons WHERE is_active=1 ORDER BY position", fetchall=True)
    
    # Group by row_group
    grouped = {}
    for b in buttons:
        rg = b[4] or 0
        grouped.setdefault(rg, []).append(b)
    
    for rg in sorted(grouped.keys()):
        row = []
        for b in grouped[rg]:
            text = f"{b[2]} {fancy(b[1])}" if b[2] else fancy(b[1])
            row.append(InlineKeyboardButton(text=text, callback_data=f"act_{b[3]}", style="primary"))
        rows.append(row)
    
    # Auto VIP/Reseller buttons
    if uid:
        u = db("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (uid,), fetchone=True)
        extra = []
        if u and u[0]: extra.append(InlineKeyboardButton(text=fancy("Reseller"), callback_data="act_reseller", style="success"))
        if u and u[1]: extra.append(InlineKeyboardButton(text=fancy("VIP Club"), callback_data="act_vip", style="danger"))
        if extra: rows.append(extra)
    
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ " + fancy("Store Manager"), callback_data="adm_store", style="primary")],
        [InlineKeyboardButton(text="👥 " + fancy("User Manager"), callback_data="adm_users", style="success")],
        [InlineKeyboardButton(text="🎟️ " + fancy("Marketing"), callback_data="adm_marketing", style="primary")],
        [InlineKeyboardButton(text="🎨 " + fancy("Menu Designer"), callback_data="adm_menu", style="success")],
        [InlineKeyboardButton(text="⚙️ " + fancy("Settings"), callback_data="adm_settings", style="primary")],
        [InlineKeyboardButton(text="🏠 " + fancy("User View"), callback_data="back_main", style="danger")]
    ])

def back_kb(cb="adm_panel_back"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=fancy("Back"), callback_data=cb, style="danger")]])

# ==============================================================================
# START
# ==============================================================================
@dp.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    if not db("SELECT user_id FROM users WHERE user_id=?", (uid,), fetchone=True):
        db("INSERT INTO users (user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)",
           (uid, m.from_user.first_name, m.from_user.username or "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    text = get_setting("welcome_text", "⚡ Welcome!")
    logo = get_setting("admin_logo_file_id")
    if logo:
        try:
            await m.answer_photo(logo, caption=text, reply_markup=main_menu_kb(uid), parse_mode='HTML')
            return
        except: pass
    await m.answer(text, reply_markup=main_menu_kb(uid), parse_mode='HTML')

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(get_setting("welcome_text", "⚡ Welcome!"), reply_markup=main_menu_kb(call.from_user.id), parse_mode='HTML')

# ==============================================================================
# DYNAMIC MENU ACTIONS
# ==============================================================================
@dp.callback_query(F.data.startswith("act_"))
async def menu_action(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_", 1)[1]
    await state.clear()
    
    if action == "shop":
        cats = db("SELECT id, name, emoji FROM categories WHERE is_active=1 AND is_maintenance=0", fetchall=True)
        if not cats: return await call.answer("No categories!", show_alert=True)
        kb_rows = []
        for c in cats:
            kb_rows.append([InlineKeyboardButton(text=f"{c[2]} {c[1]}", callback_data=f"cat_{c[0]}", style="primary")])
        kb_rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")])
        await call.message.edit_text(get_setting("ui_category_msg", "📂 Select:"), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode='HTML')
    
    elif action == "profile":
        await show_profile(call)
    
    elif action == "addbalance":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="₹50", callback_data="amt_50", style="primary"),
             InlineKeyboardButton(text="₹100", callback_data="amt_100", style="primary")],
            [InlineKeyboardButton(text="₹200", callback_data="amt_200", style="primary"),
             InlineKeyboardButton(text="₹500", callback_data="amt_500", style="primary")],
            [InlineKeyboardButton(text="₹1000", callback_data="amt_1000", style="primary"),
             InlineKeyboardButton(text="✏️ " + fancy("Custom"), callback_data="amt_custom", style="success")],
            [InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")]
        ])
        mode = "Auto Verify ✅" if get_setting("payment_mode") == "auto" else "Manual Approval ⏳"
        await call.message.edit_text(
            f"💰 <b>ADD BALANCE</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"🔧 Mode: {mode}\n\nSelect amount:",
            reply_markup=kb, parse_mode='HTML')
    
    elif action == "support":
        tg = get_setting("support_telegram", "")
        wa = get_setting("support_whatsapp", "")
        rows = []
        if tg: rows.append([InlineKeyboardButton(text="✈️ " + fancy("Telegram"), url=tg, style="primary")])
        if wa: rows.append([InlineKeyboardButton(text="📱 " + fancy("WhatsApp"), url=wa, style="primary")])
        rows.append([InlineKeyboardButton(text="🎫 " + fancy("New Ticket"), callback_data="new_ticket", style="success")])
        rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")])
        await call.message.edit_text("🎧 <b>SUPPORT</b>\n━━━━━━━━━━━━━━━━━━\nContact us:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode='HTML')
    
    elif action == "daily_gift":
        gift = safe_float(get_setting("daily_gift_price", "0"))
        if gift <= 0: return await call.answer("Gift disabled!", show_alert=True)
        today = datetime.now().strftime("%Y-%m-%d")
        u = db("SELECT last_gift FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
        if u and u[0] == today: return await call.answer("🎁 Already claimed today!", show_alert=True)
        db("UPDATE users SET balance=balance+?, last_gift=? WHERE user_id=?", (gift, today, call.from_user.id))
        await call.answer(f"🎁 +{fmt_curr(gift)} claimed!", show_alert=True)
    
    elif action == "redeem_coupon":
        await state.set_state(UserStates.wait_for_coupon)
        await call.message.edit_text("🎟️ Send coupon code:", reply_markup=back_kb("back_main"), parse_mode='HTML')
    
    elif action == "reseller":
        await call.message.edit_text("👑 Reseller Panel\nContact admin for wholesale.", reply_markup=back_kb("back_main"), parse_mode='HTML')
    
    elif action == "vip":
        u = db("SELECT balance, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
        if u[1]: return await call.message.edit_text("🌟 Already VIP!", reply_markup=back_kb("back_main"), parse_mode='HTML')
        if u[0] < VIP_PRICE:
            return await call.message.edit_text(f"❌ Need {fmt_curr(VIP_PRICE)}", reply_markup=back_kb("back_main"), parse_mode='HTML')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Buy VIP {fmt_curr(VIP_PRICE)}", callback_data="buy_vip", style="success")],
            [InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")]
        ])
        await call.message.edit_text(f"🌟 <b>VIP</b>\n{fmt_curr(VIP_PRICE)}\n{VIP_DISCOUNT}% off", reply_markup=kb, parse_mode='HTML')
    
    else:
        await call.answer(f"Action '{action}' coming soon!", show_alert=True)

@dp.callback_query(F.data == "buy_vip")
async def buy_vip(call: CallbackQuery):
    u = db("SELECT balance FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[0] < VIP_PRICE: return await call.answer("❌ Not enough!", show_alert=True)
    db("UPDATE users SET balance=balance-?, is_vip=1 WHERE user_id=?", (VIP_PRICE, call.from_user.id))
    await call.answer("🎉 VIP activated!", show_alert=True)
    await back_main(call, None)

# ==============================================================================
# PROFILE (with dynamic fields)
# ==============================================================================
async def show_profile(call: CallbackQuery):
    uid = call.from_user.id
    u = db("SELECT first_name, balance, is_reseller, is_vip, joined_date, total_spent FROM users WHERE user_id=?", (uid,), fetchone=True)
    if not u: return await call.answer("User not found!", show_alert=True)
    
    orders = db("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,), fetchone=True)[0]
    fields = db("SELECT field_key, label, is_visible FROM profile_fields WHERE is_visible=1", fetchall=True)
    
    text = "👤 <b>MY PROFILE</b>\n━━━━━━━━━━━━━━━━━━\n"
    for f in fields:
        key, label = f[0], f[1]
        if key == "user_id": text += f"🆔 {label}: <code>{uid}</code>\n"
        elif key == "name": text += f"📛 {label}: {u[0]}\n"
        elif key == "balance": text += f"💰 {label}: <b>{fmt_curr(u[1])}</b>\n"
        elif key == "account_type":
            tags = []
            if u[2]: tags.append("👑 Reseller")
            if u[3]: tags.append("🌟 VIP")
            text += f"🔰 {label}: {' | '.join(tags) if tags else 'Regular'}\n"
        elif key == "joined_date": text += f"📅 {label}: {u[4]}\n"
        elif key == "total_spent": text += f"💸 {label}: {fmt_curr(u[5] or 0)}\n"
        elif key == "total_orders": text += f"📦 {label}: {orders}\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 " + fancy("My Orders"), callback_data="my_orders", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):
    orders = db("SELECT product_name, price_paid, delivered_key, purchase_date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,), fetchall=True)
    if not orders:
        return await call.message.edit_text("📭 No orders.", reply_markup=back_kb("back_main"), parse_mode='HTML')
    text = "🧾 <b>MY ORDERS</b>\n"
    for o in orders:
        text += f"\n📦 {o[0]} • {fmt_curr(o[1])}\n🔑 <code>{o[2]}</code>\n📅 {o[3]}\n"
    await call.message.edit_text(text, reply_markup=back_kb("back_main"), parse_mode='HTML')

# ==============================================================================
# ADD BALANCE (Auto + Manual)
# ==============================================================================
@dp.callback_query(F.data.startswith("amt_"))
async def amount_selected(call: CallbackQuery, state: FSMContext):
    val = call.data.split("_")[1]
    if val == "custom":
        await state.set_state(UserStates.wait_for_custom_amt)
        await call.message.edit_text("Enter amount (₹):", reply_markup=back_kb("back_main"), parse_mode='HTML')
        return
    amount = float(val)
    await create_payment(call.from_user.id, amount, call)

@dp.message(UserStates.wait_for_custom_amt)
async def custom_amt(m: Message, state: FSMContext):
    try:
        amount = float(m.text.strip())
        if amount < 10: return await m.answer("❌ Min ₹10")
        if amount > 100000: return await m.answer("❌ Max ₹1,00,000")
    except: return await m.answer("❌ Invalid")
    await state.clear()
    await create_payment(m.from_user.id, amount, m)

async def create_payment(uid, amount, target):
    mode = get_setting("payment_mode", "manual")
    order_id = f"PAY{uid}{int(time.time())}"
    
    if mode == "auto":
        # AUTO MODE: Try API, else fallback to manual
        api_url = get_setting("auto_api_url", "")
        api_key = get_setting("auto_api_key", "")
        
        if api_url and api_key:
            # TODO: Call your payment API here to create order
            # For now, fallback to manual + notify that auto is being set up
            pass
    
    # MANUAL/QR MODE (works always)
    upi = get_setting("upi_id", "")
    if not upi:
        return await send_msg(target, "⚠️ Admin ne UPI set nahi ki. Support contact karein.", "back_main")
    
    payee = get_setting("payee_name", BRAND_NAME)
    upi_link = build_upi_link(upi, payee, amount, f"Pay {order_id}")
    expires = int(time.time()) + 300
    
    db("INSERT OR REPLACE INTO transactions (order_id, user_id, amount, status, created_at, expires_at, qr_data) VALUES (?, ?, ?, 'pending', ?, ?, ?)",
       (order_id, uid, amount, int(time.time()), expires, upi_link))
    
    qr_buf = gen_qr(upi_link)
    text = (
        f"🧾 <b>PAYMENT QR</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"💵 Amount: <b>{fmt_curr(amount)}</b>\n"
        f"🆔 Order: <code>{order_id}</code>\n"
        f"🏦 UPI: <code>{upi}</code>\n"
        f"⏳ Valid 5 mins\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📱 Scan QR with any UPI app\n"
        f"💸 Pay: <b>{fmt_curr(amount)}</b>\n"
        f"✅ Then tap 'I Have Paid'"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ " + fancy("I Have Paid"), callback_data=f"paid_{order_id}", style="success")],
        [InlineKeyboardButton(text="🔄 " + fancy("Auto Check"), callback_data=f"autocheck_{order_id}", style="primary")],
        [InlineKeyboardButton(text=fancy("Cancel"), callback_data="back_main", style="danger")]
    ])
    
    if isinstance(target, CallbackQuery):
        try: await target.message.delete()
        except: pass
        if qr_buf:
            await bot.send_photo(uid, qr_buf, caption=text, reply_markup=kb, parse_mode='HTML')
        else:
            await bot.send_message(uid, text, reply_markup=kb, parse_mode='HTML')
    else:
        if qr_buf:
            await target.answer_photo(qr_buf, caption=text, reply_markup=kb, parse_mode='HTML')
        else:
            await target.answer(text, reply_markup=kb, parse_mode='HTML')

async def send_msg(target, text, back_cb="back_main"):
    kb = back_kb(back_cb)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    else:
        await target.answer(text, reply_markup=kb, parse_mode='HTML')

# USER CLICKED "I HAVE PAID" -> Ask for proof
@dp.callback_query(F.data.startswith("paid_"))
async def user_paid(call: CallbackQuery, state: FSMContext):
    order_id = call.data.split("_", 1)[1]
    t = db("SELECT amount, status FROM transactions WHERE order_id=?", (order_id,), fetchone=True)
    if not t: return await call.answer("❌ Not found!", show_alert=True)
    if t[1] == "paid": return await call.answer("✅ Already credited!", show_alert=True)
    await state.update_data(proof_order=order_id, proof_amount=t[0])
    await state.set_state(UserStates.wait_for_proof)
    await call.message.edit_text(
        f"📸 <b>Send Screenshot / UTR</b>\n\nAmount: {fmt_curr(t[0])}\nSend screenshot OR UTR number.",
        reply_markup=back_kb("back_main"), parse_mode='HTML')

@dp.message(UserStates.wait_for_proof, F.photo)
async def proof_photo(m: Message, state: FSMContext):
    d = await state.get_data()
    order_id = d.get("proof_order"); amount = d.get("proof_amount", 0)
    db("INSERT INTO balance_requests (user_id, username, amount, method, proof_file_id, reference, status, created_at) VALUES (?, ?, ?, 'manual', ?, ?, 'pending', ?)",
       (m.from_user.id, m.from_user.username or "", amount, m.photo[-1].file_id, order_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    req = db("SELECT id FROM balance_requests WHERE user_id=? ORDER BY id DESC LIMIT 1", (m.from_user.id,), fetchone=True)
    await state.clear()
    await m.answer("✅ Proof received! Admin will verify.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Credit", callback_data=f"credit_{order_id}", style="success"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{order_id}", style="danger")
    ]])
    try:
        await bot.send_photo(ADMIN_ID, m.photo[-1].file_id,
            caption=f"💰 <b>Proof</b>\n👤 <code>{m.from_user.id}</code>\n💵 {fmt_curr(amount)}\n🆔 {order_id}",
            reply_markup=kb, parse_mode='HTML')
    except: pass

@dp.message(UserStates.wait_for_proof)
async def proof_text(m: Message, state: FSMContext):
    # Accept UTR number as text
    d = await state.get_data()
    order_id = d.get("proof_order"); amount = d.get("proof_amount", 0)
    db("INSERT INTO balance_requests (user_id, username, amount, method, reference, status, created_at) VALUES (?, ?, ?, 'manual', ?, 'pending', ?)",
       (m.from_user.id, m.from_user.username or "", amount, f"{order_id} UTR:{m.text[:50]}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await state.clear()
    await m.answer("✅ UTR received! Admin will verify.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Credit", callback_data=f"credit_{order_id}", style="success"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{order_id}", style="danger")
    ]])
    try:
        await bot.send_message(ADMIN_ID,
            f"💰 <b>UTR Received</b>\n👤 <code>{m.from_user.id}</code>\n💵 {fmt_curr(amount)}\n🆔 {order_id}\n📝 {m.text[:200]}",
            reply_markup=kb, parse_mode='HTML')
    except: pass

# AUTO CHECK button
@dp.callback_query(F.data.startswith("autocheck_"))
async def auto_check(call: CallbackQuery):
    order_id = call.data.split("_", 1)[1]
    mode = get_setting("payment_mode", "manual")
    if mode != "auto":
        return await call.answer("⏳ Auto mode off. Please send screenshot.", show_alert=True)
    api_url = get_setting("auto_api_url", "")
    if not api_url:
        return await call.answer("⚠️ API not configured. Send screenshot.", show_alert=True)
    await call.answer("🔄 Checking...", show_alert=False)
    # TODO: Call API here to check payment status
    await call.message.answer("⚠️ Auto check not configured yet. Please send screenshot.")

# ADMIN CREDIT/REJECT
@dp.callback_query(F.data.startswith("credit_"))
async def admin_credit(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    order_id = call.data.split("_", 1)[1]
    t = db("SELECT user_id, amount, status FROM transactions WHERE order_id=?", (order_id,), fetchone=True)
    if not t: return await call.answer("Not found!", show_alert=True)
    if t[2] == "paid": return await call.answer("Already credited!", show_alert=True)
    db("UPDATE transactions SET status='paid' WHERE order_id=?", (order_id,))
    db("UPDATE users SET balance=balance+? WHERE user_id=?", (t[1], t[0]))
    db("UPDATE balance_requests SET status='approved' WHERE reference=?", (order_id,))
    await call.answer("✅ Credited!", show_alert=True)
    try: await bot.send_message(t[0], f"✅ <b>Payment Verified!</b>\n💰 +{fmt_curr(t[1])}", parse_mode='HTML')
    except: pass
    try: await call.message.edit_reply_markup(reply_markup=None)
    except: pass

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    order_id = call.data.split("_", 1)[1]
    t = db("SELECT user_id FROM transactions WHERE order_id=?", (order_id,), fetchone=True)
    if not t: return
    db("UPDATE transactions SET status='rejected' WHERE order_id=?", (order_id,))
    db("UPDATE balance_requests SET status='rejected' WHERE reference=?", (order_id,))
    await call.answer("❌ Rejected!", show_alert=True)
    try: await bot.send_message(t[0], "❌ Payment rejected.", parse_mode='HTML')
    except: pass
    try: await call.message.edit_reply_markup(reply_markup=None)
    except: pass

# ==============================================================================
# SHOP
# ==============================================================================
@dp.callback_query(F.data.startswith("cat_"))
async def cat_products(call: CallbackQuery):
    cid = int(call.data.split("_")[1])
    prods = db("SELECT id, name, price, stock FROM products WHERE category_id=? AND is_active=1 AND is_maintenance=0", (cid,), fetchall=True)
    if not prods: return await call.answer("No products!", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in prods:
        st = "🟢" if p[3] > 0 else "🔴"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{p[1]} - ₹{p[2]} {st}", callback_data=f"buy_{p[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="act_shop", style="danger")])
    await call.message.edit_text(get_setting("ui_product_msg", "📦 Select:"), reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("buy_"))
async def buy_product(call: CallbackQuery):
    pid = int(call.data.split("_")[1])
    p = db("SELECT name, price, stock FROM products WHERE id=?", (pid,), fetchone=True)
    if not p or p[2] <= 0: return await call.answer("❌ Out of stock!", show_alert=True)
    u = db("SELECT balance FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[0] < p[1]: return await call.answer(f"❌ Need ₹{p[1]}. Add balance first.", show_alert=True)
    k = db("SELECT id, key_text FROM product_keys WHERE product_id=? AND is_used=0 LIMIT 1", (pid,), fetchone=True)
    if not k: return await call.answer("❌ No keys!", show_alert=True)
    db("UPDATE users SET balance=balance-? WHERE user_id=?", (p[1], call.from_user.id))
    db("UPDATE product_keys SET is_used=1 WHERE id=?", (k[0],))
    db("UPDATE products SET stock=stock-1 WHERE id=?", (pid,))
    db("INSERT INTO orders (user_id, product_name, price_paid, delivered_key, purchase_date) VALUES (?, ?, ?, ?, ?)",
       (call.from_user.id, p[0], p[1], k[1], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await call.message.edit_text(
        f"🎉 <b>PURCHASE SUCCESS!</b>\n📦 {p[0]}\n💰 {fmt_curr(p[1])}\n🔑 <code>{k[1]}</code>\n\n{get_setting('ui_key_msg', '🎉 Thanks!')}",
        reply_markup=main_menu_kb(call.from_user.id), parse_mode='HTML')

# ==============================================================================
# SUPPORT / COUPON / TICKET
# ==============================================================================
@dp.callback_query(F.data == "new_ticket")
async def new_ticket(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.wait_for_ticket)
    await call.message.edit_text("📝 Describe issue:", reply_markup=back_kb("back_main"), parse_mode='HTML')

@dp.message(UserStates.wait_for_ticket)
async def ticket_save(m: Message, state: FSMContext):
    db("INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)",
       (m.from_user.id, m.text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await state.clear()
    await m.answer("✅ Ticket submitted!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    try: await bot.send_message(ADMIN_ID, f"🚨 Ticket\nFrom: <code>{m.from_user.id}</code>\n\n{m.text}", parse_mode='HTML')
    except: pass

@dp.message(UserStates.wait_for_coupon)
async def coupon_save(m: Message, state: FSMContext):
    code = m.text.strip().upper()
    c = db("SELECT discount, max_uses, used FROM coupons WHERE code=?", (code,), fetchone=True)
    if not c: await m.answer("❌ Invalid!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    elif c[2] >= c[1]: await m.answer("❌ Expired!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    else:
        db("UPDATE users SET balance=balance+? WHERE user_id=?", (c[0], m.from_user.id))
        db("UPDATE coupons SET used=used+1 WHERE code=?", (code,))
        await m.answer(f"✅ +{fmt_curr(c[0])}", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    await state.clear()

# ==============================================================================
# ADMIN PANEL
# ==============================================================================
@dp.message(Command("admin"))
async def admin_cmd(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    await state.clear()
    await m.answer("⚙️ <b>ADMIN PANEL</b>", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_panel_back")
async def adm_back(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.clear()
    await call.message.edit_text("⚙️ <b>ADMIN PANEL</b>", reply_markup=admin_main_kb(), parse_mode='HTML')

# --- STORE MANAGER ---
@dp.callback_query(F.data == "adm_store")
async def adm_store(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 " + fancy("Categories"), callback_data="adm_cats", style="success"),
         InlineKeyboardButton(text="📦 " + fancy("Products"), callback_data="adm_prods", style="success")],
        [InlineKeyboardButton(text="🔑 " + fancy("Key Manager"), callback_data="adm_keys", style="primary")],
        [InlineKeyboardButton(text="🛠️ " + fancy("Maintenance"), callback_data="adm_maint", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_panel_back", style="danger")]
    ])
    await call.message.edit_text("🛍️ <b>STORE</b>", reply_markup=kb, parse_mode='HTML')

# --- CATEGORY ---
@dp.callback_query(F.data == "adm_cats")
async def adm_cats(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ " + fancy("Add"), callback_data="adm_cat_add", style="success"),
         InlineKeyboardButton(text="📋 " + fancy("List"), callback_data="adm_cat_list", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]
    ])
    await call.message.edit_text("📂 <b>CATEGORIES</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_cat_add")
async def cat_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.cat_add_name)
    await call.message.edit_text("Enter Name:", reply_markup=back_kb("adm_cats"), parse_mode='HTML')

@dp.message(AdminStates.cat_add_name)
async def cat_add_name(m: Message, state: FSMContext):
    await state.update_data(cn=m.text); await state.set_state(AdminStates.cat_add_emoji)
    await m.answer("Emoji:")

@dp.message(AdminStates.cat_add_emoji)
async def cat_add_emoji(m: Message, state: FSMContext):
    d = await state.get_data()
    db("INSERT INTO categories (name, emoji) VALUES (?, ?)", (d['cn'], m.text))
    await state.clear()
    await m.answer("✅ Added!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_cat_list")
async def cat_list(call: CallbackQuery):
    cats = db("SELECT id, name, emoji FROM categories", fetchall=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for c in cats:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{c[2]} {c[1]}", callback_data=f"cv_{c[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_cats", style="danger")])
    await call.message.edit_text("Select:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("cv_"))
async def cat_view(call: CallbackQuery):
    cid = int(call.data.split("_")[1])
    c = db("SELECT name, emoji FROM categories WHERE id=?", (cid,), fetchone=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Name", callback_data=f"ce_{cid}_name", style="primary"),
         InlineKeyboardButton(text="😀 Emoji", callback_data=f"ce_{cid}_emoji", style="primary")],
        [InlineKeyboardButton(text="🗑️ Delete", callback_data=f"cd_{cid}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_cat_list", style="danger")]
    ])
    await call.message.edit_text(f"{c[1]} <b>{c[0]}</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("ce_"))
async def cat_edit(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    cid = int(parts[1]); field = parts[2]
    await state.update_data(ce_id=cid, ce_field=field)
    await state.set_state(AdminStates.cat_edit_value)
    await call.message.edit_text(f"New {field}:", reply_markup=back_kb("adm_cat_list"), parse_mode='HTML')

@dp.message(AdminStates.cat_edit_value)
async def cat_edit_val(m: Message, state: FSMContext):
    d = await state.get_data()
    col = "name" if d['ce_field'] == 'name' else "emoji"
    db(f"UPDATE categories SET {col}=? WHERE id=?", (m.text, d['ce_id']))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data.startswith("cd_"))
async def cat_del(call: CallbackQuery):
    cid = int(call.data.split("_")[1])
    db("DELETE FROM categories WHERE id=?", (cid,))
    await call.answer("Deleted!", show_alert=True)
    await cat_list(call)

# --- PRODUCT ---
@dp.callback_query(F.data == "adm_prods")
async def adm_prods(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ " + fancy("Add"), callback_data="adm_prod_add", style="success"),
         InlineKeyboardButton(text="📋 " + fancy("List"), callback_data="adm_prod_list", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]
    ])
    await call.message.edit_text("📦 <b>PRODUCTS</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_prod_add")
async def prod_add(call: CallbackQuery):
    cats = db("SELECT id, name FROM categories", fetchall=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for c in cats: kb.inline_keyboard.append([InlineKeyboardButton(text=c[1], callback_data=f"pa_{c[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_prods", style="danger")])
    await call.message.edit_text("Select Category:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("pa_"))
async def prod_add_cat(call: CallbackQuery, state: FSMContext):
    cid = int(call.data.split("_")[1]); await state.update_data(pc=cid)
    await state.set_state(AdminStates.prod_add_name)
    await call.message.edit_text("Product Name:", reply_markup=back_kb("adm_prods"), parse_mode='HTML')

@dp.message(AdminStates.prod_add_name)
async def prod_add_name(m: Message, state: FSMContext):
    await state.update_data(pn=m.text); await state.set_state(AdminStates.prod_add_price)
    await m.answer("Price (₹):")

@dp.message(AdminStates.prod_add_price)
async def prod_add_price(m: Message, state: FSMContext):
    await state.update_data(pp=float(m.text)); await state.set_state(AdminStates.prod_add_rprice)
    await m.answer("Reseller Price (₹):")

@dp.message(AdminStates.prod_add_rprice)
async def prod_add_rprice(m: Message, state: FSMContext):
    await state.update_data(prp=float(m.text)); await state.set_state(AdminStates.prod_add_validity)
    await m.answer("Validity (e.g., 30 Days):")

@dp.message(AdminStates.prod_add_validity)
async def prod_add_validity(m: Message, state: FSMContext):
    await state.update_data(pv=m.text); await state.set_state(AdminStates.prod_add_device)
    await m.answer("Device Limit:")

@dp.message(AdminStates.prod_add_device)
async def prod_add_device(m: Message, state: FSMContext):
    await state.update_data(pd=m.text); await state.set_state(AdminStates.prod_add_apk)
    await m.answer("APK Link (or 'none'):")

@dp.message(AdminStates.prod_add_apk)
async def prod_add_apk(m: Message, state: FSMContext):
    await state.update_data(pap=m.text if m.text.lower() != 'none' else ""); await state.set_state(AdminStates.prod_add_keys)
    await m.answer("Paste keys (1 per line):")

@dp.message(AdminStates.prod_add_keys)
async def prod_add_keys(m: Message, state: FSMContext):
    d = await state.get_data()
    keys = [k.strip() for k in m.text.split('\n') if k.strip()]
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO products (category_id, name, price, reseller_price, validity, device_limit, apk_link, stock) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (d['pc'], d['pn'], d['pp'], d['prp'], d['pv'], d['pd'], d['pap'], len(keys)))
    pid = c.lastrowid
    for k in keys: c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (pid, k))
    conn.commit(); conn.close(); await state.clear()
    await m.answer(f"✅ Product added with {len(keys)} keys!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_prod_list")
async def prod_list(call: CallbackQuery):
    prods = db("SELECT id, name, price FROM products", fetchall=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in prods:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{p[1]} - ₹{p[2]}", callback_data=f"pv_{p[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_prods", style="danger")])
    await call.message.edit_text("Select Product:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("pv_"))
async def prod_view(call: CallbackQuery):
    pid = int(call.data.split("_")[1])
    p = db("SELECT name, price, reseller_price, stock FROM products WHERE id=?", (pid,), fetchone=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Name", callback_data=f"pe_{pid}_name", style="primary"),
         InlineKeyboardButton(text="💰 Price", callback_data=f"pe_{pid}_price", style="primary")],
        [InlineKeyboardButton(text="👑 R-Price", callback_data=f"pe_{pid}_reseller_price", style="primary"),
         InlineKeyboardButton(text="⏱ Validity", callback_data=f"pe_{pid}_validity", style="primary")],
        [InlineKeyboardButton(text="📱 Device", callback_data=f"pe_{pid}_device_limit", style="primary"),
         InlineKeyboardButton(text="🔗 APK", callback_data=f"pe_{pid}_apk_link", style="primary")],
        [InlineKeyboardButton(text="➕ Add Keys", callback_data=f"pk_{pid}", style="success"),
         InlineKeyboardButton(text="🗑️ Delete", callback_data=f"pdl_{pid}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_prod_list", style="danger")]
    ])
    await call.message.edit_text(f"📦 <b>{p[0]}</b>\n💰 ₹{p[1]} | 👑 ₹{p[2]} | 🔑 {p[3]}", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("pe_"))
async def prod_edit(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_", 2)
    pid = int(parts[1]); field = parts[2]
    await state.update_data(pe_id=pid, pe_field=field)
    await state.set_state(AdminStates.prod_edit_value)
    await call.message.edit_text(f"New {field}:", reply_markup=back_kb("adm_prod_list"), parse_mode='HTML')

@dp.message(AdminStates.prod_edit_value)
async def prod_edit_val(m: Message, state: FSMContext):
    d = await state.get_data()
    field = d['pe_field']
    val = m.text
    if field in ('price', 'reseller_price'):
        try: val = float(val)
        except: return await m.answer("❌ Number!")
    if field == 'apk_link' and val.lower() == 'none': val = ""
    db(f"UPDATE products SET {field}=? WHERE id=?", (val, d['pe_id']))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data.startswith("pk_"))
async def prod_addkeys(call: CallbackQuery, state: FSMContext):
    pid = int(call.data.split("_")[1])
    await state.update_data(pk_id=pid)
    await state.set_state(AdminStates.prod_add_keys2)
    await call.message.edit_text("Paste keys (1 per line):", reply_markup=back_kb("adm_prod_list"), parse_mode='HTML')

@dp.message(AdminStates.prod_add_keys2)
async def prod_addkeys2(m: Message, state: FSMContext):
    d = await state.get_data()
    pid = d['pk_id']
    keys = [k.strip() for k in m.text.split('\n') if k.strip()]
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    for k in keys: c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (pid, k))
    c.execute("UPDATE products SET stock=stock+? WHERE id=?", (len(keys), pid))
    conn.commit(); conn.close(); await state.clear()
    await m.answer(f"✅ {len(keys)} keys added!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data.startswith("pdl_"))
async def prod_del(call: CallbackQuery):
    pid = int(call.data.split("_")[1])
    db("DELETE FROM products WHERE id=?", (pid,))
    db("DELETE FROM product_keys WHERE product_id=?", (pid,))
    await call.answer("Deleted!", show_alert=True)
    await prod_list(call)

# --- KEYS ---
@dp.callback_query(F.data == "adm_keys")
async def adm_keys(call: CallbackQuery):
    prods = db("SELECT id, name, stock FROM products", fetchall=True)
    text = "🔑 <b>KEY STOCK</b>\n━━━━━━━━━━━━━━━━━━\n"
    for p in prods:
        avail = db("SELECT COUNT(*) FROM product_keys WHERE product_id=? AND is_used=0", (p[0],), fetchone=True)[0]
        text += f"\n📦 {p[1]}: 🟢 {avail} keys"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 " + fancy("Clear Unused"), callback_data="adm_key_clear", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_key_clear")
async def key_clear(call: CallbackQuery):
    db("DELETE FROM product_keys WHERE is_used=0")
    await call.answer("🧹 Cleared!", show_alert=True)

# --- MAINTENANCE ---
@dp.callback_query(F.data == "adm_maint")
async def adm_maint(call: CallbackQuery):
    st = "🔴 ON" if get_setting("global_maintenance") == "1" else "🟢 OFF"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Global: {st}", callback_data="adm_mt_tog", style="danger" if st == "🔴 ON" else "success")],
        [InlineKeyboardButton(text="✏️ " + fancy("Edit Msg"), callback_data="adm_mt_edit", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]
    ])
    await call.message.edit_text("🛠️ <b>MAINTENANCE</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_mt_tog")
async def mt_tog(call: CallbackQuery):
    cur = get_setting("global_maintenance")
    set_setting("global_maintenance", "0" if cur == "1" else "1")
    await adm_maint(call)

@dp.callback_query(F.data == "adm_mt_edit")
async def mt_edit(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.set_maint_msg)
    await call.message.edit_text("New Message:", reply_markup=back_kb("adm_maint"), parse_mode='HTML')

@dp.message(AdminStates.set_maint_msg)
async def mt_edit_save(m: Message, state: FSMContext):
    set_setting("maintenance_msg", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

# --- USER MANAGER (with DELETE) ---
@dp.callback_query(F.data == "adm_users")
async def adm_users(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 " + fancy("Search"), callback_data="adm_u_search", style="primary")],
        [InlineKeyboardButton(text="📋 " + fancy("All Users"), callback_data="adm_u_all", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_panel_back", style="danger")]
    ])
    await call.message.edit_text("👥 <b>USERS</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_u_search")
async def u_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.user_search)
    await call.message.edit_text("Send User ID or @username:", reply_markup=back_kb("adm_users"), parse_mode='HTML')

@dp.message(AdminStates.user_search)
async def u_search_save(m: Message, state: FSMContext):
    t = m.text.strip().lstrip('@')
    u = db("SELECT user_id, first_name, balance, is_banned, is_vip, is_reseller FROM users WHERE user_id=? OR username=?", (t, t), fetchone=True)
    if not u: return await m.answer("❌ Not found!", reply_markup=back_kb("adm_users"), parse_mode='HTML')
    await show_admin_user(m, u)
    await state.clear()

async def show_admin_user(m, u):
    st = "🔴" if u[3] else "🟢"
    tags = []
    if u[5]: tags.append("👑")
    if u[4]: tags.append("🌟")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ban/Unban", callback_data=f"ub_{u[0]}", style="danger"),
         InlineKeyboardButton(text="VIP Toggle", callback_data=f"uv_{u[0]}", style="success")],
        [InlineKeyboardButton(text="Add ₹", callback_data=f"ua_{u[0]}", style="success"),
         InlineKeyboardButton(text="Remove ₹", callback_data=f"ur_{u[0]}", style="danger")],
        [InlineKeyboardButton(text="🗑️ DELETE USER", callback_data=f"udel_{u[0]}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_users", style="danger")]
    ])
    await m.answer(
        f"👤 <b>USER</b>\n🆔 <code>{u[0]}</code>\n📛 {u[1]}\n💰 {fmt_curr(u[2])}\n📊 {st} {' '.join(tags)}",
        reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_u_all")
async def u_all(call: CallbackQuery):
    users = db("SELECT user_id, first_name, balance FROM users ORDER BY user_id DESC LIMIT 30", fetchall=True)
    text = "👥 <b>USERS</b>\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for u in users:
        text += f"\n<code>{u[0]}</code> - {u[1] or 'N/A'} - {fmt_curr(u[2])}"
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_users", style="danger")])
    await call.message.edit_text(text[:4000], reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("udel_"))
async def u_del(call: CallbackQuery):
    uid = int(call.data.split("_")[1])
    db("DELETE FROM users WHERE user_id=?", (uid,))
    db("DELETE FROM orders WHERE user_id=?", (uid,))
    db("DELETE FROM balance_requests WHERE user_id=?", (uid,))
    await call.answer("🗑️ User deleted!", show_alert=True)
    try: await call.message.edit_reply_markup(reply_markup=back_kb("adm_users"))
    except: pass

@dp.callback_query(F.data.startswith("ub_"))
async def u_ban(call: CallbackQuery):
    uid = int(call.data.split("_")[1])
    c = db("SELECT is_banned FROM users WHERE user_id=?", (uid,), fetchone=True)[0]
    db("UPDATE users SET is_banned=? WHERE user_id=?", (0 if c else 1, uid))
    await call.answer("✅ Toggled!", show_alert=True)

@dp.callback_query(F.data.startswith("uv_"))
async def u_vip(call: CallbackQuery):
    uid = int(call.data.split("_")[1])
    c = db("SELECT is_vip FROM users WHERE user_id=?", (uid,), fetchone=True)[0]
    db("UPDATE users SET is_vip=? WHERE user_id=?", (0 if c else 1, uid))
    await call.answer("✅ Toggled!", show_alert=True)

@dp.callback_query(F.data.startswith("ua_"))
async def u_bal_add(call: CallbackQuery, state: FSMContext):
    uid = int(call.data.split("_")[1])
    await state.update_data(ub=uid)
    await state.set_state(AdminStates.user_addbal)
    await call.message.edit_text("Amount:", reply_markup=back_kb("adm_users"), parse_mode='HTML')

@dp.message(AdminStates.user_addbal)
async def u_bal_add_save(m: Message, state: FSMContext):
    d = await state.get_data()
    db("UPDATE users SET balance=balance+? WHERE user_id=?", (float(m.text), d['ub']))
    await state.clear(); await m.answer("✅ Added!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data.startswith("ur_"))
async def u_bal_rem(call: CallbackQuery, state: FSMContext):
    uid = int(call.data.split("_")[1])
    await state.update_data(ub=uid)
    await state.set_state(AdminStates.user_rembal)
    await call.message.edit_text("Amount:", reply_markup=back_kb("adm_users"), parse_mode='HTML')

@dp.message(AdminStates.user_rembal)
async def u_bal_rem_save(m: Message, state: FSMContext):
    d = await state.get_data()
    db("UPDATE users SET balance=MAX(0, balance-?) WHERE user_id=?", (float(m.text), d['ub']))
    await state.clear(); await m.answer("✅ Removed!", reply_markup=admin_main_kb(), parse_mode='HTML')

# --- MARKETING ---
@dp.callback_query(F.data == "adm_marketing")
async def adm_marketing(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ " + fancy("Coupons"), callback_data="adm_cp", style="success"),
         InlineKeyboardButton(text="📢 " + fancy("Broadcast"), callback_data="adm_bc", style="danger")],
        [InlineKeyboardButton(text="🎁 " + fancy("Gift"), callback_data="adm_gift", style="success"),
         InlineKeyboardButton(text="🤝 " + fancy("Refer"), callback_data="adm_ref", style="success")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_panel_back", style="danger")]
    ])
    await call.message.edit_text("🎟️ <b>MARKETING</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_cp")
async def adm_cp(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ " + fancy("Create"), callback_data="adm_cp_add", style="success"),
         InlineKeyboardButton(text="📋 " + fancy("View"), callback_data="adm_cp_view", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_marketing", style="danger")]
    ])
    await call.message.edit_text("🎟️ <b>COUPONS</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_cp_add")
async def cp_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.cp_code)
    await call.message.edit_text("Code:", reply_markup=back_kb("adm_cp"), parse_mode='HTML')

@dp.message(AdminStates.cp_code)
async def cp_code_save(m: Message, state: FSMContext):
    await state.update_data(cc=m.text.strip().upper()); await state.set_state(AdminStates.cp_disc)
    await m.answer("Discount (₹):")

@dp.message(AdminStates.cp_disc)
async def cp_disc_save(m: Message, state: FSMContext):
    await state.update_data(cd=float(m.text)); await state.set_state(AdminStates.cp_max)
    await m.answer("Max Uses:")

@dp.message(AdminStates.cp_max)
async def cp_max_save(m: Message, state: FSMContext):
    d = await state.get_data()
    db("INSERT OR REPLACE INTO coupons (code, discount, max_uses) VALUES (?, ?, ?)", (d['cc'], d['cd'], int(m.text)))
    await state.clear(); await m.answer("✅ Created!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_cp_view")
async def cp_view(call: CallbackQuery):
    cps = db("SELECT code, discount, max_uses, used FROM coupons", fetchall=True)
    text = "🎟️ <b>COUPONS</b>\n"
    for c in cps: text += f"\n<code>{c[0]}</code> - ₹{c[1]} ({c[3]}/{c[2]})"
    if not cps: text += "\nNo coupons."
    await call.message.edit_text(text, reply_markup=back_kb("adm_cp"), parse_mode='HTML')

@dp.callback_query(F.data == "adm_bc")
async def bc_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.bc_msg)
    await call.message.edit_text("Send broadcast message:", reply_markup=back_kb("adm_marketing"), parse_mode='HTML')

@dp.message(AdminStates.bc_msg)
async def bc_send(m: Message, state: FSMContext):
    users = db("SELECT user_id FROM users", fetchall=True)
    sent, failed = 0, 0
    st = await m.answer("⏳ Sending...")
    for u in users:
        try:
            await m.send_copy(chat_id=u[0]); sent += 1
        except: failed += 1
        await asyncio.sleep(0.05)
    await st.edit_text(f"✅ Sent: {sent}\n❌ Failed: {failed}", reply_markup=admin_main_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "adm_gift")
async def gift_set(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.set_gift)
    await call.message.edit_text("Daily Gift (₹):", reply_markup=back_kb("adm_marketing"), parse_mode='HTML')

@dp.message(AdminStates.set_gift)
async def gift_save(m: Message, state: FSMContext):
    set_setting("daily_gift_price", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_ref")
async def ref_set(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.set_refer)
    await call.message.edit_text("Refer Reward (₹):", reply_markup=back_kb("adm_marketing"), parse_mode='HTML')

@dp.message(AdminStates.set_refer)
async def ref_save(m: Message, state: FSMContext):
    set_setting("refer_earn_amount", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

# --- MENU DESIGNER (Add/Edit/Delete menu buttons + Profile fields) ---
@dp.callback_query(F.data == "adm_menu")
async def adm_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 " + fancy("Manage Buttons"), callback_data="adm_menu_list", style="primary")],
        [InlineKeyboardButton(text="➕ " + fancy("Add Button"), callback_data="adm_menu_add", style="success")],
        [InlineKeyboardButton(text="👤 " + fancy("Profile Fields"), callback_data="adm_pf", style="success")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_panel_back", style="danger")]
    ])
    await call.message.edit_text("🎨 <b>MENU DESIGNER</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_menu_list")
async def menu_list(call: CallbackQuery):
    btns = db("SELECT id, label, emoji, action, is_active FROM menu_buttons ORDER BY position", fetchall=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for b in btns:
        st = "🟢" if b[4] else "🔴"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{st} {b[2]} {b[1]}", callback_data=f"mb_{b[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_menu", style="danger")])
    await call.message.edit_text("Select button to edit:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("mb_"))
async def menu_btn_view(call: CallbackQuery):
    bid = int(call.data.split("_")[1])
    b = db("SELECT label, emoji, action, is_active FROM menu_buttons WHERE id=?", (bid,), fetchone=True)
    st = "🟢 Active" if b[3] else "🔴 Inactive"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Label", callback_data=f"mbe_{bid}_label", style="primary"),
         InlineKeyboardButton(text="😀 Emoji", callback_data=f"mbe_{bid}_emoji", style="primary")],
        [InlineKeyboardButton(text="⚙️ Action", callback_data=f"mbe_{bid}_action", style="primary")],
        [InlineKeyboardButton(text="👁️ Toggle", callback_data=f"mbt_{bid}", style="success")],
        [InlineKeyboardButton(text="🗑️ Delete", callback_data=f"mbd_{bid}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_menu_list", style="danger")]
    ])
    await call.message.edit_text(f"Button: {b[2]} {b[1]}\nAction: {b[2]}\nStatus: {st}", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("mbe_"))
async def menu_btn_edit(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_", 2)
    bid = int(parts[1]); field = parts[2]
    await state.update_data(mbe_id=bid, mbe_field=field)
    await state.set_state(AdminStates.menu_edit_value)
    await call.message.edit_text(f"New {field}:", reply_markup=back_kb("adm_menu_list"), parse_mode='HTML')

@dp.message(AdminStates.menu_edit_value)
async def menu_btn_edit_save(m: Message, state: FSMContext):
    d = await state.get_data()
    db(f"UPDATE menu_buttons SET {d['mbe_field']}=? WHERE id=?", (m.text, d['mbe_id']))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data.startswith("mbt_"))
async def menu_btn_toggle(call: CallbackQuery):
    bid = int(call.data.split("_")[1])
    c = db("SELECT is_active FROM menu_buttons WHERE id=?", (bid,), fetchone=True)[0]
    db("UPDATE menu_buttons SET is_active=? WHERE id=?", (0 if c else 1, bid))
    await call.answer("✅ Toggled!", show_alert=True)
    await menu_list(call)

@dp.callback_query(F.data.startswith("mbd_"))
async def menu_btn_del(call: CallbackQuery):
    bid = int(call.data.split("_")[1])
    db("DELETE FROM menu_buttons WHERE id=?", (bid,))
    await call.answer("🗑️ Deleted!", show_alert=True)
    await menu_list(call)

@dp.callback_query(F.data == "adm_menu_add")
async def menu_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.menu_add_label)
    await call.message.edit_text("Button Label:", reply_markup=back_kb("adm_menu"), parse_mode='HTML')

@dp.message(AdminStates.menu_add_label)
async def menu_add_label(m: Message, state: FSMContext):
    await state.update_data(ml=m.text); await state.set_state(AdminStates.menu_add_emoji)
    await m.answer("Emoji (or 'none'):")

@dp.message(AdminStates.menu_add_emoji)
async def menu_add_emoji(m: Message, state: FSMContext):
    e = "" if m.text.lower() == 'none' else m.text
    await state.update_data(me=e); await state.set_state(AdminStates.menu_add_action)
    await m.answer("Action (shop/profile/addbalance/support/daily_gift/redeem_coupon/reseller/vip):")

@dp.message(AdminStates.menu_add_action)
async def menu_add_action(m: Message, state: FSMContext):
    d = await state.get_data()
    pos = db("SELECT MAX(position) FROM menu_buttons", fetchone=True)[0] or 0
    db("INSERT INTO menu_buttons (label, emoji, action, position, is_active, row_group) VALUES (?, ?, ?, ?, 1, ?)",
       (d['ml'], d['me'], m.text.lower(), pos + 1, pos // 2))
    await state.clear()
    await m.answer("✅ Button added!", reply_markup=admin_main_kb(), parse_mode='HTML')

# --- PROFILE FIELDS ---
@dp.callback_query(F.data == "adm_pf")
async def adm_pf(call: CallbackQuery):
    fields = db("SELECT field_key, label, is_visible FROM profile_fields", fetchall=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for f in fields:
        st = "🟢" if f[2] else "🔴"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{st} {f[1]}", callback_data=f"pft_{f[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_menu", style="danger")])
    await call.message.edit_text("👤 <b>PROFILE FIELDS</b>\nToggle what shows in profile:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("pft_"))
async def pf_toggle(call: CallbackQuery):
    key = call.data.split("_", 1)[1]
    c = db("SELECT is_visible FROM profile_fields WHERE field_key=?", (key,), fetchone=True)[0]
    db("UPDATE profile_fields SET is_visible=? WHERE field_key=?", (0 if c else 1, key))
    await call.answer("✅ Toggled!", show_alert=True)
    await adm_pf(call)

# --- SETTINGS ---
@dp.callback_query(F.data == "adm_settings")
async def adm_settings(call: CallbackQuery):
    mode = get_setting("payment_mode", "manual")
    mode_txt = "🤖 AUTO" if mode == "auto" else "✋ MANUAL"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼️ " + fancy("Set Logo"), callback_data="adm_set_logo", style="success")],
        [InlineKeyboardButton(text="📝 " + fancy("Message Editor"), callback_data="adm_msg", style="success")],
        [InlineKeyboardButton(text=f"💳 Payment: {mode_txt}", callback_data="adm_pay_mode", style="danger" if mode == "auto" else "primary")],
        [InlineKeyboardButton(text="🏦 " + fancy("Set UPI ID"), callback_data="adm_set_upi", style="primary")],
        [InlineKeyboardButton(text="🏷️ " + fancy("Set Payee"), callback_data="adm_set_payee", style="primary")],
        [InlineKeyboardButton(text="📞 " + fancy("TG Support"), callback_data="adm_set_tg", style="primary"),
         InlineKeyboardButton(text="📱 " + fancy("WA Support"), callback_data="adm_set_wa", style="primary")],
        [InlineKeyboardButton(text="🔌 " + fancy("Auto API Setup"), callback_data="adm_auto_api", style="success")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_panel_back", style="danger")]
    ])
    await call.message.edit_text("⚙️ <b>SETTINGS</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_pay_mode")
async def pay_mode(call: CallbackQuery):
    mode = get_setting("payment_mode", "manual")
    new = "auto" if mode == "manual" else "manual"
    set_setting("payment_mode", new)
    await call.answer(f"✅ Switched to {new.upper()}", show_alert=True)
    await adm_settings(call)

@dp.callback_query(F.data == "adm_auto_api")
async def adm_auto_api(call: CallbackQuery):
    url = get_setting("auto_api_url", "") or "(not set)"
    key = get_setting("auto_api_key", "") or "(not set)"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 " + fancy("Set API Key"), callback_data="adm_api_setkey", style="primary")],
        [InlineKeyboardButton(text="🌐 " + fancy("Set API URL"), callback_data="adm_api_seturl", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_settings", style="danger")]
    ])
    await call.message.edit_text(
        f"🔌 <b>AUTO API SETUP</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"🌐 URL: <code>{url[:60]}</code>\n"
        f"🔑 Key: <code>{key[:20]}...</code>\n\n"
        f"Add your payment gateway API credentials here.\n"
        f"Supported: FamPay, Razorpay, Cashfree, PhonePe, etc.",
        reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "adm_api_setkey")
async def api_setkey(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.set_auto_key)
    await call.message.edit_text("Enter API Key:", reply_markup=back_kb("adm_auto_api"), parse_mode='HTML')

@dp.message(AdminStates.set_auto_key)
async def api_setkey_save(m: Message, state: FSMContext):
    set_setting("auto_api_key", m.text.strip()); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_api_seturl")
async def api_seturl(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.set_auto_url)
    await call.message.edit_text("Enter API URL:", reply_markup=back_kb("adm_auto_api"), parse_mode='HTML')

@dp.message(AdminStates.set_auto_url)
async def api_seturl_save(m: Message, state: FSMContext):
    set_setting("auto_api_url", m.text.strip()); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_set_logo")
async def set_logo(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.set_logo)
    await call.message.edit_text("Send photo:", reply_markup=back_kb("adm_settings"), parse_mode='HTML')

@dp.message(AdminStates.set_logo, F.photo)
async def set_logo_save(m: Message, state: FSMContext):
    set_setting("admin_logo_file_id", m.photo[-1].file_id); await state.clear()
    await m.answer("✅ Logo saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_set_upi")
async def set_upi(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.set_upi)
    await call.message.edit_text("UPI ID:", reply_markup=back_kb("adm_settings"), parse_mode='HTML')

@dp.message(AdminStates.set_upi)
async def set_upi_save(m: Message, state: FSMContext):
    set_setting("upi_id", m.text.strip()); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_set_payee")
async def set_payee(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.set_payee)
    await call.message.edit_text("Payee Name:", reply_markup=back_kb("adm_settings"), parse_mode='HTML')

@dp.message(AdminStates.set_payee)
async def set_payee_save(m: Message, state: FSMContext):
    set_setting("payee_name", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_set_tg")
async def set_tg(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.set_tg)
    await call.message.edit_text("Telegram URL:", reply_markup=back_kb("adm_settings"), parse_mode='HTML')

@dp.message(AdminStates.set_tg)
async def set_tg_save(m: Message, state: FSMContext):
    set_setting("support_telegram", m.text.strip()); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "adm_set_wa")
async def set_wa(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.set_wa)
    await call.message.edit_text("WhatsApp URL:", reply_markup=back_kb("adm_settings"), parse_mode='HTML')

@dp.message(AdminStates.set_wa)
async def set_wa_save(m: Message, state: FSMContext):
    set_setting("support_whatsapp", m.text.strip()); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

# --- MESSAGE EDITOR ---
@dp.callback_query(F.data == "adm_msg")
async def adm_msg(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 " + fancy("Welcome"), callback_data="am_w", style="primary")],
        [InlineKeyboardButton(text="📂 " + fancy("Category Page"), callback_data="am_c", style="primary")],
        [InlineKeyboardButton(text="📦 " + fancy("Product Page"), callback_data="am_p", style="primary")],
        [InlineKeyboardButton(text="🔑 " + fancy("Key Delivery"), callback_data="am_k", style="primary")],
        [InlineKeyboardButton(text="💰 " + fancy("Balance Page"), callback_data="am_b", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_settings", style="danger")]
    ])
    await call.message.edit_text("📝 <b>MESSAGE EDITOR</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "am_w")
async def am_w(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.msg_welcome)
    await call.message.edit_text("New Welcome:", reply_markup=back_kb("adm_msg"), parse_mode='HTML')

@dp.message(AdminStates.msg_welcome)
async def am_w_save(m: Message, state: FSMContext):
    set_setting("welcome_text", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "am_c")
async def am_c(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.msg_cat)
    await call.message.edit_text("New Category Message:", reply_markup=back_kb("adm_msg"), parse_mode='HTML')

@dp.message(AdminStates.msg_cat)
async def am_c_save(m: Message, state: FSMContext):
    set_setting("ui_category_msg", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "am_p")
async def am_p(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.msg_prod)
    await call.message.edit_text("New Product Message:", reply_markup=back_kb("adm_msg"), parse_mode='HTML')

@dp.message(AdminStates.msg_prod)
async def am_p_save(m: Message, state: FSMContext):
    set_setting("ui_product_msg", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "am_k")
async def am_k(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.msg_key)
    await call.message.edit_text("New Key Delivery Msg:", reply_markup=back_kb("adm_msg"), parse_mode='HTML')

@dp.message(AdminStates.msg_key)
async def am_k_save(m: Message, state: FSMContext):
    set_setting("ui_key_msg", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "am_b")
async def am_b(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.msg_balance)
    await call.message.edit_text("New Balance Msg:", reply_markup=back_kb("adm_msg"), parse_mode='HTML')

@dp.message(AdminStates.msg_balance)
async def am_b_save(m: Message, state: FSMContext):
    set_setting("ui_balance_msg", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_main_kb(), parse_mode='HTML')

# ==============================================================================
# RENDER WEB SERVER + MAIN
# ==============================================================================
async def handle(request): return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server on port {port}")

async def main():
    init_db()
    logger.info("DB ready.")
    await start_web_server()
    logger.info("Bot starting...")
    try: await dp.start_polling(bot)
    except Exception as e: logger.error(f"Error: {e}")
    finally: await bot.session.close()

if __name__ == "__main__":
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): logger.info("Stopped.")