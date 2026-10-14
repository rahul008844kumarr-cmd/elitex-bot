#!/usr/bin/env python3
"""ELITE X CONFIG - Elite Telegram Store Bot with FULL Admin Control"""
from __future__ import annotations

import io
import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import random
import string

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters,
)

try:
    import qrcode
except ImportError:
    qrcode = None

# ==================== CONFIG ====================
BOT_TOKEN = "8851779409:AAE9cUrtDX4LWwRD5FDY_R6FQDhLMiKmLsk"
ADMIN_IDS = {8467166339}
DB_PATH = "elite_x_config.sqlite3"
SUPPORT_URL = "https://t.me/elitexconfig"
BRAND_NAME = "ELITE X CONFIG"

logging.basicConfig(level="INFO", format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("elite_x_config")

# ==================== DEFAULT MESSAGES ====================
WELCOME_DEFAULT = (
    "⚡ <b>ELITE X CONFIG</b> ⚡\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🎉 Welcome to the <b>ELITE X CONFIG Store</b>!\n\n"
    "🛍️ Browse categories and products\n"
    "💰 Add balance using QR payment\n"
    "🔑 Keys delivered after admin approval\n"
    "🎧 Need help? Open Support\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "👇 <i>Choose an option below to continue</i>"
)

CATEGORY_DEFAULT = "📂 <b>Select a Category</b>\n\n👇 Choose from below:"
PRODUCT_DEFAULT = "📦 <b>Select a Product</b>\n\n👇 Choose from below:"
KEY_DEFAULT = "🎉 Thank you for your purchase!"
PROFILE_DEFAULT = "👤 <b>My Profile</b>"
ORDERS_DEFAULT = "📦 <b>My Orders</b>"
SUPPORT_DEFAULT = "🎧 <b>Support Center</b>\n\nClick below to contact support:"
BALANCE_DEFAULT = "💰 <b>Add Balance</b>\n\n👇 Select amount to add:"
MAINTENANCE_DEFAULT = "🛠️ <b>Bot Under Maintenance</b>\n\nWe'll be back soon. Please try again later."

# ==================== HELPERS ====================
def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    return con

def query(sql, args=()):
    with closing(db()) as con:
        return con.execute(sql, args).fetchall()

def one(sql, args=()):
    rows = query(sql, args)
    return rows[0] if rows else None

def execute(sql, args=()):
    with closing(db()) as con:
        cur = con.execute(sql, args)
        con.commit()
        return int(cur.lastrowid or 0)

def money(v):
    return "₹{:,.2f}".format(float(v))

def is_admin(update):
    uid = update.effective_user.id if update.effective_user else None
    return bool(uid and uid in ADMIN_IDS)

def is_co_admin(update):
    uid = update.effective_user.id if update.effective_user else None
    if not uid:
        return False
    if uid in ADMIN_IDS:
        return True
    return bool(one("SELECT 1 FROM co_admins WHERE user_id=?", (uid,)))

def is_owner(update):
    uid = update.effective_user.id if update.effective_user else None
    if not uid:
        return False
    owner = int(get_setting("owner_id", "0") or 0)
    return uid == owner or uid in ADMIN_IDS

def b(label, data):
    return InlineKeyboardButton(label, callback_data=data[:64])

def kb(rows):
    return InlineKeyboardMarkup(rows)

def rand_code(n=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

# ==================== DATABASE ====================
def init_db():
    Path(DB_PATH).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    with closing(db()) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, name TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '', balance REAL NOT NULL DEFAULT 0, is_reseller INTEGER NOT NULL DEFAULT 0, referred_by INTEGER NOT NULL DEFAULT 0, last_gift TEXT NOT NULL DEFAULT '', joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, emoji TEXT NOT NULL DEFAULT '📂', visible INTEGER NOT NULL DEFAULT 1, message TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', price REAL NOT NULL DEFAULT 0, reseller_price REAL NOT NULL DEFAULT 0, discount INTEGER NOT NULL DEFAULT 0, visible INTEGER NOT NULL DEFAULT 1, message TEXT NOT NULL DEFAULT '', download_link TEXT NOT NULL DEFAULT '', api_id INTEGER NOT NULL DEFAULT 0, variant TEXT NOT NULL DEFAULT '', FOREIGN KEY(category_id) REFERENCES categories(id));
        CREATE TABLE IF NOT EXISTS key_stock(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, key_text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'available', added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, sold_to INTEGER, sold_at TEXT NOT NULL DEFAULT '', FOREIGN KEY(product_id) REFERENCES products(id));
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS balance_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, username TEXT NOT NULL DEFAULT '', amount REAL NOT NULL, proof_file_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reviewed_at TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, username TEXT NOT NULL DEFAULT '', product_id INTEGER NOT NULL, product_name TEXT NOT NULL, price REAL NOT NULL, payment_method TEXT NOT NULL DEFAULT 'qr', proof_file_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', key_stock_id INTEGER, delivered_key TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reviewed_at TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS wallet_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, amount_delta REAL NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS coupons(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, discount REAL NOT NULL DEFAULT 0, max_uses INTEGER NOT NULL DEFAULT 1, used INTEGER NOT NULL DEFAULT 0, expires_at TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS co_admins(user_id INTEGER PRIMARY KEY, name TEXT NOT NULL DEFAULT '', added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS apis(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', api_key TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS broadcasts(id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, sent_to INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS maintenance(id INTEGER PRIMARY KEY CHECK (id = 1), enabled INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '');
        """)
        defaults = {
            "welcome": WELCOME_DEFAULT,
            "category_message": CATEGORY_DEFAULT,
            "product_message": PRODUCT_DEFAULT,
            "key_message": KEY_DEFAULT,
            "profile_message": PROFILE_DEFAULT,
            "orders_message": ORDERS_DEFAULT,
            "support_message": SUPPORT_DEFAULT,
            "balance_message": BALANCE_DEFAULT,
            "payment_instructions": "📸 Scan the QR, pay the EXACT amount, then send a screenshot here.\n⏳ Admin approval is required.",
            "upi_id": "",
            "payee_name": BRAND_NAME,
            "support_url": SUPPORT_URL,
            "how_to_use_url": "",
            "payment_proof_url": "",
            "payment_qr_file_id": "",
            "binance_pay_id": "",
            "zapupi_key": "",
            "balance_amounts": "100,200,500,1000",
            "daily_gift_price": "0",
            "refer_earn_amount": "0",
            "reseller_system": "0",
            "owner_id": str(list(ADMIN_IDS)[0]) if ADMIN_IDS else "0",
            "admin_logo_file_id": "",
            "store_name": BRAND_NAME,
        }
        con.executemany("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", defaults.items())
        con.execute("INSERT OR IGNORE INTO maintenance(id,enabled,message) VALUES(1,0,?)", (MAINTENANCE_DEFAULT,))
        con.commit()

def get_setting(key, default=""):
    row = one("SELECT value FROM settings WHERE key=?", (key,))
    return str(row["value"]) if row else default

def set_setting(key, value):
    execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

def is_maintenance():
    row = one("SELECT enabled FROM maintenance WHERE id=1")
    return bool(row and row["enabled"])

def get_maintenance_msg():
    row = one("SELECT message FROM maintenance WHERE id=1")
    return row["message"] if row else MAINTENANCE_DEFAULT

# ==================== KEYBOARDS ====================
def main_kb():
    return kb([
        [b("🛍️ Shop Now", "shop"), b("👤 My Profile", "profile")],
        [b("💰 Add Balance", "addbalance"), b("📦 My Orders", "myorders")],
        [b("🎟️ Redeem Coupon", "redeem_coupon"), b("🎁 Daily Gift", "daily_gift")],
        [b("🎧 Support", "support")],
    ])

def admin_kb():
    return kb([
        [b("📊 Dashboard", "adm:dash"), b("🖼️ Admin Logo", "adm:logo")],
        [b("📂 Category Manager", "adm:cats"), b("📦 Product Manager", "adm:prods")],
        [b("🔑 Key Manager", "adm:keys"), b("💰 Balance Manager", "adm:bal")],
        [b("👥 User Manager", "adm:users"), b("🎟️ Coupon System", "adm:coupons")],
        [b("🤝 Co-Admin Manager", "adm:coadmins"), b("👑 Transfer Ownership", "adm:transfer")],
        [b("🏪 Reseller System", "adm:reseller"), b("💳 Payment Settings", "adm:payment")],
        [b("🎁 Gift & Refer", "adm:gift"), b("🔗 Link Manager", "adm:links")],
        [b("🌐 API Manager", "adm:api"), b("✏️ Message Editor", "adm:messages")],
        [b("📢 Broadcast", "adm:broadcast"), b("🔧 Maintenance", "adm:maintenance")],
        [b("🏠 User Menu", "home")],
    ])

def category_admin_kb():
    return kb([
        [b("➕ Add Category", "adm:cat_add"), b("📋 List All", "adm:cat_list")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def product_admin_kb():
    return kb([
        [b("➕ Add Product", "adm:prod_add"), b("📋 List All", "adm:prod_list")],
        [b("🔗 Set Download Link", "adm:prod_link"), b("🎯 Set Plan API", "adm:prod_api")],
        [b("💸 Set Discount", "adm:prod_disc")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def key_admin_kb():
    return kb([
        [b("➕ Add Key", "adm:key_add"), b("🗑️ Remove Key", "adm:key_remove")],
        [b("📋 Check ID Stock", "adm:key_check"), b("🧹 Clear All Stock", "adm:key_clear")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def balance_admin_kb():
    return kb([
        [b("➕ Add Balance", "adm:bal_add"), b("➖ Remove Balance", "adm:bal_remove")],
        [b("🔍 Check Balance", "adm:bal_check"), b("👥 Add to All Users", "adm:bal_addall")],
        [b("🧾 Balance Requests", "adm:bal_requests")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def user_admin_kb():
    return kb([
        [b("👥 All Users", "adm:user_all"), b("🔢 Total Users", "adm:user_total")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def coupon_admin_kb():
    return kb([
        [b("🎟️ Generate Coupon", "adm:coupon_gen"), b("📋 View Coupons", "adm:coupon_view")],
        [b("🗑️ Delete Coupon", "adm:coupon_del")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def coadmin_kb():
    return kb([
        [b("➕ Add Co-Admin", "adm:coadmin_add"), b("➖ Remove Co-Admin", "adm:coadmin_remove")],
        [b("📋 View Co-Admins", "adm:coadmin_view")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def reseller_kb():
    return kb([
        [b("🔛 Toggle Reseller System", "adm:res_toggle")],
        [b("💰 Set Reseller Price (Product)", "adm:res_setprice")],
        [b("🎯 Direct Reseller (by User ID)", "adm:res_direct")],
        [b("👤 Set Reseller Role", "adm:res_setuser")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def payment_kb():
    return kb([
        [b("💳 Set UPI ID", "adm:set_upi"), b("🏷️ Set Payee Name", "adm:set_payee")],
        [b("🖼️ Set Static QR", "adm:set_qr"), b("⚡ Set ZapUPI Key", "adm:set_zapupi")],
        [b("🪙 Set Binance Pay ID", "adm:set_binance")],
        [b("⚙️ Payment Instructions", "adm:set_instructions")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def gift_kb():
    return kb([
        [b("🎁 Set Daily Gift Price", "adm:set_gift"), b("🤝 Set Refer & Earn", "adm:set_refer")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def link_kb():
    return kb([
        [b("🎧 Set Support Link", "adm:set_support"), b("📖 Set How-To-Use Link", "adm:set_howto")],
        [b("📸 Set Payment Proof Link", "adm:set_prooflink")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def api_kb():
    return kb([
        [b("➕ Add API", "adm:api_add"), b("📋 View APIs", "adm:api_view")],
        [b("🗑️ Delete API", "adm:api_del")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def messages_kb():
    return kb([
        [b("✏️ Edit Welcome", "adm:msg_welcome"), b("✏️ Edit Category", "adm:msg_category")],
        [b("✏️ Edit Product", "adm:msg_product"), b("✏️ Edit Key", "adm:msg_key")],
        [b("✏️ Edit Profile", "adm:msg_profile"), b("✏️ Edit Orders", "adm:msg_orders")],
        [b("✏️ Edit Support", "adm:msg_support"), b("✏️ Edit Balance", "adm:msg_balance")],
        [b("♻️ Reset to Default", "adm:msg_reset")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def broadcast_kb():
    return kb([
        [b("📢 Send Broadcast", "adm:bc_send")],
        [b("📊 Broadcast History", "adm:bc_history")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def maintenance_kb():
    return kb([
        [b("🔛 Toggle Maintenance", "adm:mt_toggle")],
        [b("✏️ Edit Maintenance Msg", "adm:mt_edit")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

# ==================== UPI / QR ====================
def build_upi_link(upi_id, payee_name, amount, note=""):
    base = "upi://pay?pa=" + quote(upi_id) + "&pn=" + quote(payee_name)
    base += "&am={:.2f}&cu=INR".format(amount)
    if note:
        base += "&tn=" + quote(note)
    return base

def generate_qr_bytes(data):
    if qrcode is None:
        return None
    img = qrcode.make(data)
    buf = io.BytesIO()
    buf.name = "qr.png"
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

async def notify_admins(context, text, reply_markup=None, photo_id=""):
    all_admins = set(ADMIN_IDS)
    for r in query("SELECT user_id FROM co_admins"):
        all_admins.add(r["user_id"])
    for admin_id in all_admins:
        try:
            if photo_id:
                await context.bot.send_photo(admin_id, photo_id, caption=text[:1024], reply_markup=reply_markup, parse_mode="HTML")
            else:
                await context.bot.send_message(admin_id, text[:4000], reply_markup=reply_markup, parse_mode="HTML")
        except TelegramError:
            log.exception("Could not notify admin %s", admin_id)

# ==================== USER VIEWS ====================
async def show_home(update, context):
    user = update.effective_user
    if user:
        execute("INSERT INTO users(user_id,name,username) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET name=excluded.name,username=excluded.username",
                (user.id, user.full_name, user.username or ""))
    text = get_setting("welcome", WELCOME_DEFAULT)
    logo = get_setting("admin_logo_file_id")
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=main_kb(), parse_mode="HTML")
        except BadRequest:
            if logo:
                try:
                    await update.effective_chat.send_photo(logo, caption=text[:1024], reply_markup=main_kb(), parse_mode="HTML")
                    return
                except TelegramError:
                    pass
            await update.effective_chat.send_message(text, reply_markup=main_kb(), parse_mode="HTML")
    else:
        if logo:
            try:
                await update.effective_message.reply_photo(logo, caption=text[:1024], reply_markup=main_kb(), parse_mode="HTML")
                return
            except TelegramError:
                pass
        await update.effective_message.reply_text(text, reply_markup=main_kb(), parse_mode="HTML")

async def start(update, context):
    if is_maintenance() and not is_co_admin(update):
        await update.effective_message.reply_text(get_maintenance_msg(), parse_mode="HTML")
        return
    context.user_data.clear()
    await show_home(update, context)

async def admin_command(update, context):
    if not is_co_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    upi = get_setting("upi_id") or "(not set)"
    payee = get_setting("payee_name") or BRAND_NAME
    qr_mode = "Static image" if get_setting("payment_qr_file_id") else ("Auto UPI QR" if upi != "(not set)" else "None")
    total_users = one("SELECT COUNT(*) n FROM users")["n"]
    msg = (
        "⚙️ <b>ELITE X CONFIG — Admin Panel</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users: <b>{total_users}</b>\n"
        f"💳 UPI ID: <code>{upi}</code>\n"
        f"🏷️ Payee: <b>{payee}</b>\n"
        f"🔧 QR Mode: <b>{qr_mode}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 <i>Select an operational control module:</i>"
    )
    logo = get_setting("admin_logo_file_id")
    if logo:
        try:
            await update.effective_message.reply_photo(logo, caption=msg, reply_markup=admin_kb(), parse_mode="HTML")
            return
        except TelegramError:
            pass
    await update.effective_message.reply_text(msg, reply_markup=admin_kb(), parse_mode="HTML")

async def send_qr_and_prompt(chat_id, context, caption, amount, note=""):
    instructions = get_setting("payment_instructions")
    upi_id = get_setting("upi_id").strip()
    payee_name = get_setting("payee_name").strip() or BRAND_NAME
    sent = False
    if upi_id and qrcode is not None:
        link = build_upi_link(upi_id, payee_name, amount, note)
        buf = generate_qr_bytes(link)
        if buf:
            try:
                cap = caption + "\n\n💳 UPI: <code>" + upi_id + "</code>\n\n" + instructions
                await context.bot.send_photo(chat_id, buf, caption=cap[:1024], parse_mode="HTML")
                sent = True
            except TelegramError:
                log.exception("Auto QR send failed")
        try:
            await context.bot.send_message(chat_id, "📲 <a href='" + link + "'>Tap to Pay " + money(amount) + "</a>", disable_web_page_preview=True, parse_mode="HTML")
        except TelegramError:
            pass
    if not sent:
        qr_file_id = get_setting("payment_qr_file_id")
        if qr_file_id:
            try:
                cap = caption + "\n\n" + instructions
                await context.bot.send_photo(chat_id, qr_file_id, caption=cap[:1024], parse_mode="HTML")
                sent = True
            except TelegramError:
                pass
    if not sent:
        await context.bot.send_message(chat_id, caption + "\n\n⚠️ Admin ne payment set nahi kiya hai. Please support se contact karein.\n" + instructions, parse_mode="HTML")
    await context.bot.send_message(chat_id, "📸 Payment karne ke baad screenshot isi chat mein bhejein.")

async def show_categories(update, context):
    cats = query("SELECT id,name,emoji FROM categories WHERE visible=1 ORDER BY id")
    rows = [[b(r["emoji"] + " " + r["name"], "cat:" + str(r["id"]))] for r in cats]
    rows.append([b("🏠 Main Menu", "home")])
    text = get_setting("category_message", CATEGORY_DEFAULT)
    if not cats:
        text = "📂 Abhi koi category available nahi hai."
    await update.callback_query.edit_message_text(text, reply_markup=kb(rows), parse_mode="HTML")

async def show_products(update, category_id):
    cat = one("SELECT name,emoji FROM categories WHERE id=? AND visible=1", (category_id,))
    if not cat:
        await update.callback_query.edit_message_text("❌ Category nahi mili.", reply_markup=main_kb())
        return
    products = query("SELECT id,name,price FROM products WHERE category_id=? AND visible=1 ORDER BY id", (category_id,))
    rows = []
    for p in products:
        stock = one("SELECT COUNT(*) AS n FROM key_stock WHERE product_id=? AND status='available'", (p["id"],))
        rows.append([b("🛒 " + p["name"] + " — " + money(p["price"]) + " | 🔑 " + str(stock["n"]), "prod:" + str(p["id"]))])
    rows.append([b("⬅️ Categories", "shop")])
    await update.callback_query.edit_message_text("📂 " + cat["emoji"] + " <b>" + cat["name"] + "</b>\n\nSelect a product:", reply_markup=kb(rows), parse_mode="HTML")

async def show_product(update, context, product_id):
    p = one("SELECT p.*, c.name AS category_name, c.emoji AS cat_emoji FROM products p JOIN categories c ON c.id=p.category_id WHERE p.id=? AND p.visible=1 AND c.visible=1", (product_id,))
    if not p:
        await update.callback_query.edit_message_text("❌ Product nahi mila.", reply_markup=main_kb())
        return
    stock = one("SELECT COUNT(*) AS n FROM key_stock WHERE product_id=? AND status='available'", (product_id,))
    user = update.effective_user
    u = one("SELECT is_reseller FROM users WHERE user_id=?", (user.id,))
    is_res = bool(u and u["is_reseller"]) and get_setting("reseller_system", "0") == "1"
    price = float(p["reseller_price"]) if (is_res and float(p["reseller_price"]) > 0) else float(p["price"])
    if p["discount"]:
        price = price - (price * float(p["discount"]) / 100)
    text = (
        "📦 <b>" + p["name"] + "</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📂 Category: " + p["cat_emoji"] + " " + p["category_name"] + "\n"
        "💰 Price: <b>" + money(price) + "</b>" + (f" <s>{money(p['price'])}</s> -{p['discount']}%" if p["discount"] else "") + "\n"
        "🔑 Available Keys: <b>" + str(stock["n"]) + "</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        + (p["description"] or "")
    )
    rows = [
        [b("💳 Buy with QR Payment", "buy:" + str(product_id))],
        [b("💰 Buy with Wallet", "walletbuy:" + str(product_id))],
    ]
    if p["download_link"]:
        rows.append([InlineKeyboardButton("📥 Download", url=p["download_link"])])
    rows.append([b("⬅️ Back to Products", "cat:" + str(p["category_id"]))])
    await update.callback_query.edit_message_text(text, reply_markup=kb(rows), parse_mode="HTML")

async def begin_balance(update, context):
    context.user_data.clear()
    amounts = [x.strip() for x in get_setting("balance_amounts", "100,200,500,1000").split(",") if x.strip()]
    rows = [[b("₹" + a, "balamt:" + a)] for a in amounts if a.replace(".", "", 1).isdigit()]
    rows.append([b("✍️ Enter Custom Amount", "balcustom")])
    rows.append([b("🏠 Main Menu", "home")])
    text = get_setting("balance_message", BALANCE_DEFAULT)
    await update.callback_query.edit_message_text(text, reply_markup=kb(rows), parse_mode="HTML")

async def create_balance_request(update, context, amount):
    if amount <= 0 or amount > 1000000:
        await update.effective_message.reply_text("❌ Valid amount bhejein (1 - 10,00,000).")
        return
    context.user_data.clear()
    context.user_data["pending_balance_amount"] = amount
    cap = "💰 <b>Balance Top-Up Request</b>\nAmount: <b>" + money(amount) + "</b>"
    await send_qr_and_prompt(update.effective_chat.id, context, cap, amount=amount, note="Balance top-up")
    context.user_data["awaiting_balance_proof"] = True

async def begin_buy(update, context, product_id):
    p = one("SELECT * FROM products WHERE id=? AND visible=1", (product_id,))
    if not p:
        await update.callback_query.edit_message_text("❌ Product nahi mila.")
        return
    stock = one("SELECT id FROM key_stock WHERE product_id=? AND status='available' ORDER BY id LIMIT 1", (product_id,))
    if not stock:
        await update.callback_query.edit_message_text("❌ Is product ka stock khatam hai.", reply_markup=main_kb())
        return
    context.user_data.clear()
    context.user_data["pending_order_product"] = product_id
    context.user_data["pending_order_price"] = float(p["price"])
    cap = "🛍️ <b>Product Purchase Request</b>\nProduct: <b>" + p["name"] + "</b>\nAmount: <b>" + money(p["price"]) + "</b>"
    await send_qr_and_prompt(update.effective_chat.id, context, cap, amount=float(p["price"]), note=p["name"][:50])
    context.user_data["awaiting_order_proof"] = True

async def wallet_buy(update, context, product_id):
    user = update.effective_user
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        p = con.execute("SELECT * FROM products WHERE id=? AND visible=1", (product_id,)).fetchone()
        u = con.execute("SELECT balance FROM users WHERE user_id=?", (user.id,)).fetchone()
        key = con.execute("SELECT * FROM key_stock WHERE product_id=? AND status='available' ORDER BY id LIMIT 1", (product_id,)).fetchone()
        if not p or not u:
            con.rollback()
            await update.callback_query.edit_message_text("❌ Product/User nahi mila.")
            return
        if not key:
            con.rollback()
            await update.callback_query.edit_message_text("❌ Key stock khatam hai.")
            return
        if float(u["balance"]) < float(p["price"]):
            con.rollback()
            await update.callback_query.edit_message_text("❌ Wallet balance kam hai.\nBalance: " + money(u["balance"]), reply_markup=main_kb())
            return
        con.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (p["price"], user.id))
        con.execute("UPDATE key_stock SET status='sold',sold_to=?,sold_at=? WHERE id=? AND status='available'", (user.id, utc_now(), key["id"]))
        con.execute("INSERT INTO wallet_transactions(user_id,amount_delta,note) VALUES(?,?,?)", (user.id, -float(p["price"]), "Purchase product #" + str(product_id)))
        con.execute("INSERT INTO orders(user_id,username,product_id,product_name,price,payment_method,status,key_stock_id,delivered_key,reviewed_at) VALUES(?,?,?,?,?,'wallet','approved',?,?,?)",
                    (user.id, user.username or "", product_id, p["name"], p["price"], key["id"], key["key_text"], utc_now()))
        con.commit()
    key_msg = get_setting("key_message", KEY_DEFAULT)
    success = (
        "🎉 <b>PURCHASE SUCCESSFUL!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📦 Product: <b>" + p["name"] + "</b>\n"
        "💰 Paid: <b>" + money(p["price"]) + "</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🔑 <b>YOUR KEY:</b>\n"
        "<code>" + key["key_text"] + "</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        + key_msg
    )
    await update.callback_query.edit_message_text(success, reply_markup=main_kb(), parse_mode="HTML")

# ==================== PROOF HANDLER ====================
async def handle_proof(update, context):
    user = update.effective_user
    photo = update.effective_message.photo
    if not photo:
        await update.effective_message.reply_text("📸 Screenshot ko photo ke roop mein bhejein.")
        return
    file_id = photo[-1].file_id
    if context.user_data.get("awaiting_balance_proof"):
        amount = float(context.user_data.get("pending_balance_amount", 0))
        req_id = execute("INSERT INTO balance_requests(user_id,username,amount,proof_file_id) VALUES(?,?,?,?)",
                         (user.id, user.username or "", amount, file_id))
        context.user_data.clear()
        await update.effective_message.reply_text("✅ Screenshot mil gaya.\n💰 Balance request <b>#" + str(req_id) + "</b> admin approval ke liye bhej di gayi hai.", parse_mode="HTML")
        admin_msg = (
            "💰 <b>BALANCE REQUEST #" + str(req_id) + "</b>\n"
            "👤 User: " + user.full_name + " (@" + (user.username or "no_username") + ")\n"
            "🆔 User ID: <code>" + str(user.id) + "</code>\n"
            "💵 Amount: <b>" + money(amount) + "</b>\n\n"
            "✅ Screenshot verify karke approve/reject karein."
        )
        await notify_admins(context, admin_msg, kb([[b("✅ Approve Balance", "ba:" + str(req_id)), b("❌ Reject", "bj:" + str(req_id))]]), photo_id=file_id)
        return
    if context.user_data.get("awaiting_order_proof"):
        product_id = int(context.user_data.get("pending_order_product", 0))
        p = one("SELECT * FROM products WHERE id=?", (product_id,))
        if not p:
            context.user_data.clear()
            await update.effective_message.reply_text("❌ Product request expire ho gayi. Dobara try karein.")
            return
        order_id = execute("INSERT INTO orders(user_id,username,product_id,product_name,price,payment_method,proof_file_id,status) VALUES(?,?,?,?,?,'qr',?,'pending')",
                           (user.id, user.username or "", product_id, p["name"], float(p["price"]), file_id))
        context.user_data.clear()
        await update.effective_message.reply_text("✅ Payment screenshot mil gaya.\n🧾 Order <b>#" + str(order_id) + "</b> admin approval mein hai.", parse_mode="HTML")
        admin_msg = (
            "🧾 <b>PRODUCT PAYMENT #" + str(order_id) + "</b>\n"
            "👤 User: " + user.full_name + " (@" + (user.username or "no_username") + ")\n"
            "🆔 User ID: <code>" + str(user.id) + "</code>\n"
            "📦 Product: <b>" + p["name"] + "</b>\n"
            "💵 Amount: <b>" + money(p["price"]) + "</b>\n\n"
            "✅ Verify karke approve/reject karein."
        )
        await notify_admins(context, admin_msg, kb([[b("✅ Approve & Deliver Key", "oa:" + str(order_id)), b("❌ Reject", "or:" + str(order_id))]]), photo_id=file_id)
        return
    await update.effective_message.reply_text("Pehle Add Balance ya product purchase shuru karein, phir screenshot bhejein.")

# ==================== ADMIN APPROVAL ====================
async def admin_approve_balance(update, context, req_id, approve):
    q = update.callback_query
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        req = con.execute("SELECT * FROM balance_requests WHERE id=?", (req_id,)).fetchone()
        if not req or req["status"] != "pending":
            con.rollback()
            await q.answer("Already processed.", show_alert=True)
            return
        status = "approved" if approve else "rejected"
        con.execute("UPDATE balance_requests SET status=?,reviewed_at=? WHERE id=?", (status, utc_now(), req_id))
        if approve:
            con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (req["amount"], req["user_id"]))
            con.execute("INSERT INTO wallet_transactions(user_id,amount_delta,note) VALUES(?,?,?)", (req["user_id"], req["amount"], "Balance request #" + str(req_id)))
        con.commit()
    await q.answer("Done")
    cap = "💰 Balance request #" + str(req_id) + " — " + status.upper()
    try:
        await q.edit_message_caption(caption=cap)
    except (BadRequest, AttributeError):
        try:
            await q.edit_message_text(cap)
        except TelegramError:
            pass
    try:
        msg = ("✅ Approved" if approve else "❌ Rejected") + ": Balance request #" + str(req_id) + ".\n"
        msg += ("Added: " + money(req["amount"])) if approve else "Balance add nahi hua."
        await context.bot.send_message(req["user_id"], msg)
    except TelegramError:
        pass

async def admin_approve_order(update, context, order_id, approve):
    q = update.callback_query
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order or order["status"] != "pending":
            con.rollback()
            await q.answer("Already processed.", show_alert=True)
            return
        if not approve:
            con.execute("UPDATE orders SET status='rejected',reviewed_at=? WHERE id=?", (utc_now(), order_id))
            con.commit()
            await q.answer("Rejected")
            try:
                await q.edit_message_caption(caption="❌ Order #" + str(order_id) + " rejected.")
            except (BadRequest, AttributeError):
                try:
                    await q.edit_message_text("❌ Order #" + str(order_id) + " rejected.")
                except TelegramError:
                    pass
            try:
                await context.bot.send_message(order["user_id"], "❌ Payment for order #" + str(order_id) + " was rejected.")
            except TelegramError:
                pass
            return
        key = con.execute("SELECT * FROM key_stock WHERE product_id=? AND status='available' ORDER BY id LIMIT 1", (order["product_id"],)).fetchone()
        if not key:
            con.rollback()
            await q.answer("No key in stock.", show_alert=True)
            return
        con.execute("UPDATE key_stock SET status='sold',sold_to=?,sold_at=? WHERE id=? AND status='available'", (order["user_id"], utc_now(), key["id"]))
        con.execute("UPDATE orders SET status='approved',key_stock_id=?,delivered_key=?,reviewed_at=? WHERE id=?", (key["id"], key["key_text"], utc_now(), order_id))
        con.commit()
    await q.answer("Approved")
    cap = "✅ Order #" + str(order_id) + " approved."
    try:
        await q.edit_message_caption(caption=cap)
    except (BadRequest, AttributeError):
        try:
            await q.edit_message_text(cap)
        except TelegramError:
            pass
    key_msg = get_setting("key_message", KEY_DEFAULT)
    try:
        deliver = (
            "🎉 <b>PAYMENT APPROVED!</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📦 Product: <b>" + order["product_name"] + "</b>\n"
            "💰 Paid: <b>" + money(order["price"]) + "</b>\n"
            "🧾 Order ID: <b>#" + str(order_id) + "</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🔑 <b>YOUR KEY:</b>\n"
            "<code>" + key["key_text"] + "</code>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            + key_msg
        )
        await context.bot.send_message(order["user_id"], deliver, parse_mode="HTML")
    except TelegramError:
        pass

# ==================== ADMIN PANEL CALLBACKS ====================
async def admin_list_categories(update, context):
    q = update.callback_query
    cats = query("SELECT id,name,emoji,visible FROM categories ORDER BY id")
    if not cats:
        await q.edit_message_text("📂 Koi category nahi hai. Pehle add karein.", reply_markup=category_admin_kb())
        return
    rows = []
    for c in cats:
        status = "✅" if c["visible"] else "❌"
        rows.append([b(status + " " + c["emoji"] + " " + c["name"], "adm:cat_view:" + str(c["id"]))])
    rows.append([b("⬅️ Back", "adm:cats")])
    await q.edit_message_text("📋 <b>CATEGORIES</b>\n\nClick to edit/delete:", reply_markup=kb(rows), parse_mode="HTML")

async def admin_view_category(update, context, cat_id):
    q = update.callback_query
    c = one("SELECT * FROM categories WHERE id=?", (cat_id,))
    if not c:
        await q.edit_message_text("❌ Category nahi mili.", reply_markup=category_admin_kb())
        return
    prods = one("SELECT COUNT(*) n FROM products WHERE category_id=?", (cat_id,))["n"]
    text = (
        "📂 <b>CATEGORY #" + str(c["id"]) + "</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "😀 Emoji: " + c["emoji"] + "\n"
        "📝 Name: " + c["name"] + "\n"
        "👁️ Visible: " + ("✅ Yes" if c["visible"] else "❌ No") + "\n"
        "📦 Products: " + str(prods)
    )
    await q.edit_message_text(text, reply_markup=kb([
        [b("✏️ Edit Name", "adm:cat_editname:" + str(cat_id)), b("😀 Edit Emoji", "adm:cat_editemoji:" + str(cat_id))],
        [b("👁️ Toggle Visible", "adm:cat_toggle:" + str(cat_id))],
        [b("🗑️ Delete", "adm:cat_del:" + str(cat_id))],
        [b("⬅️ Back", "adm:cat_list")],
    ]), parse_mode="HTML")

async def admin_list_products(update, context):
    q = update.callback_query
    prods = query("SELECT p.id,p.name,p.price,p.visible,c.name AS cat FROM products p JOIN categories c ON c.id=p.category_id ORDER BY p.id")
    if not prods:
        await q.edit_message_text("📦 Koi product nahi hai. Pehle add karein.", reply_markup=product_admin_kb())
        return
    rows = []
    for p in prods:
        status = "✅" if p["visible"] else "❌"
        rows.append([b(status + " #" + str(p["id"]) + " " + p["name"] + " — " + money(p["price"]), "adm:prod_view:" + str(p["id"]))])
    rows.append([b("⬅️ Back", "adm:prods")])
    await q.edit_message_text("📋 <b>PRODUCTS</b>\n\nClick to edit/delete:", reply_markup=kb(rows), parse_mode="HTML")

async def admin_view_product(update, context, prod_id):
    q = update.callback_query
    p = one("SELECT p.*,c.name AS cat FROM products p JOIN categories c ON c.id=p.category_id WHERE p.id=?", (prod_id,))
    if not p:
        await q.edit_message_text("❌ Product nahi mila.", reply_markup=product_admin_kb())
        return
    stock = one("SELECT COUNT(*) n FROM key_stock WHERE product_id=? AND status='available'", (prod_id,))["n"]
    text = (
        "📦 <b>PRODUCT #" + str(p["id"]) + "</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📝 Name: " + p["name"] + "\n"
        "📂 Category: " + p["cat"] + "\n"
        "💰 Price: " + money(p["price"]) + "\n"
        "🏪 Reseller Price: " + money(p["reseller_price"]) + "\n"
        "💸 Discount: " + str(p["discount"]) + "%\n"
        "👁️ Visible: " + ("Yes" if p["visible"] else "No") + "\n"
        "🔑 Keys: " + str(stock) + "\n"
        "🔗 Download: " + (p["download_link"] or "(not set)") + "\n"
        "📝 Description: " + (p["description"] or "(empty)")
    )
    await q.edit_message_text(text, reply_markup=kb([
        [b("✏️ Edit Name", "adm:prod_editname:" + str(prod_id)), b("💰 Edit Price", "adm:prod_editprice:" + str(prod_id))],
        [b("📝 Edit Desc", "adm:prod_editdesc:" + str(prod_id)), b("🏪 Reseller Price", "adm:prod_editres:" + str(prod_id))],
        [b("💸 Discount %", "adm:prod_editdisc:" + str(prod_id)), b("🔗 Download Link", "adm:prod_editlink:" + str(prod_id))],
        [b("📂 Change Category", "adm:prod_movecat:" + str(prod_id)), b("🎯 Set API", "adm:prod_setapi:" + str(prod_id))],
        [b("👁️ Toggle Visible", "adm:prod_toggle:" + str(prod_id)), b("🗑️ Delete", "adm:prod_del:" + str(prod_id))],
        [b("⬅️ Back", "adm:prod_list")],
    ]), parse_mode="HTML")

async def admin_list_users(update, context):
    q = update.callback_query
    users = query("SELECT user_id,name,username,balance,is_reseller FROM users ORDER BY user_id DESC LIMIT 30")
    if not users:
        await q.edit_message_text("👥 Koi user nahi.", reply_markup=user_admin_kb())
        return
    body = "👥 <b>USERS (latest 30)</b>\n━━━━━━━━━━━━━━━━━━\n"
    for u in users:
        body += f"🆔 <code>{u['user_id']}</code> | {u['name'][:20]} | 💰 {money(u['balance'])}\n"
    await q.edit_message_text(body, reply_markup=kb([[b("⬅️ Back", "adm:users")]]), parse_mode="HTML")

async def admin_list_coadmins(update, context):
    q = update.callback_query
    rows_db = query("SELECT user_id,name FROM co_admins ORDER BY user_id")
    if not rows_db:
        await q.edit_message_text("🤝 Koi co-admin nahi hai.", reply_markup=coadmin_kb())
        return
    body = "🤝 <b>CO-ADMINS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for u in rows_db:
        body += f"🆔 <code>{u['user_id']}</code> — {u['name']}\n"
    await q.edit_message_text(body, reply_markup=kb([[b("⬅️ Back", "adm:coadmins")]]), parse_mode="HTML")

async def admin_list_coupons(update, context):
    q = update.callback_query
    rows_db = query("SELECT * FROM coupons ORDER BY id DESC LIMIT 30")
    if not rows_db:
        await q.edit_message_text("🎟️ Koi coupon nahi hai.", reply_markup=coupon_admin_kb())
        return
    body = "🎟️ <b>COUPONS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for c in rows_db:
        body += f"<code>{c['code']}</code> | {c['discount']}% | {c['used']}/{c['max_uses']}\n"
    await q.edit_message_text(body, reply_markup=kb([[b("⬅️ Back", "adm:coupons")]]), parse_mode="HTML")

async def admin_list_apis(update, context):
    q = update.callback_query
    rows_db = query("SELECT * FROM apis ORDER BY id")
    if not rows_db:
        await q.edit_message_text("🌐 Koi API nahi hai.", reply_markup=api_kb())
        return
    body = "🌐 <b>APIs</b>\n━━━━━━━━━━━━━━━━━━\n"
    for a in rows_db:
        body += f"#{a['id']} {a['name']}\n"
    await q.edit_message_text(body, reply_markup=kb([[b("⬅️ Back", "adm:api")]]), parse_mode="HTML")

# ==================== CALLBACK ROUTER ====================
async def on_callback(update, context):
    q = update.callback_query
    data = q.data or ""

    # Admin-only guard
    if data.startswith(("adm:", "ba:", "bj:", "oa:", "or:")) and not is_co_admin(update):
        await q.answer("⛔ Admin only.", show_alert=True)
        return

    await q.answer()

    # ===== USER MENU =====
    if data == "home":
        await show_home(update, context)
    elif data == "shop":
        await show_categories(update, context)
    elif data == "profile":
        u = one("SELECT * FROM users WHERE user_id=?", (update.effective_user.id,))
        text = (
            get_setting("profile_message", PROFILE_DEFAULT) + "\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🆔 ID: <code>" + str(update.effective_user.id) + "</code>\n"
            "👤 Name: " + update.effective_user.full_name + "\n"
            "💰 Balance: <b>" + money(u["balance"] if u else 0) + "</b>\n"
            "🏪 Reseller: " + ("✅ Yes" if (u and u["is_reseller"]) else "❌ No")
        )
        await q.edit_message_text(text, reply_markup=kb([[b("🏠 Main Menu", "home")]]), parse_mode="HTML")
    elif data == "addbalance":
        await begin_balance(update, context)
    elif data.startswith("balamt:"):
        try:
            await create_balance_request(update, context, float(data.split(":", 1)[1]))
        except ValueError:
            await q.edit_message_text("Invalid amount.")
    elif data == "balcustom":
        context.user_data.clear()
        context.user_data["awaiting_custom_balance_amount"] = True
        await q.edit_message_text("💰 Kitna balance add karna hai? Amount number mein bhejein (₹).")
    elif data == "myorders":
        orders = query("SELECT id,product_name,price,status,created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (update.effective_user.id,))
        body = get_setting("orders_message", ORDERS_DEFAULT) + "\n━━━━━━━━━━━━━━━━━━\n"
        if orders:
            for r in orders:
                body += f"#{r['id']} • {r['product_name']} • {money(r['price'])} • {r['status']}\n"
        else:
            body += "📭 Abhi koi order nahi hai."
        await q.edit_message_text(body, reply_markup=kb([[b("🏠 Main Menu", "home")]]), parse_mode="HTML")
    elif data == "support":
        text = get_setting("support_message", SUPPORT_DEFAULT) + "\n\n🔗 " + get_setting("support_url", SUPPORT_URL)
        await q.edit_message_text(text, reply_markup=kb([[b("🎧 Contact Support", url=get_setting("support_url", SUPPORT_URL))], [b("🏠 Main Menu", "home")]]), parse_mode="HTML")
    elif data == "redeem_coupon":
        context.user_data.clear()
        context.user_data["awaiting_coupon"] = True
        await q.edit_message_text("🎟️ Coupon code bhejein:")
    elif data == "daily_gift":
        gift = float(get_setting("daily_gift_price", "0"))
        if gift <= 0:
            await q.edit_message_text("🎁 Daily gift abhi available nahi hai.", reply_markup=kb([[b("🏠 Main Menu", "home")]]))
            return
        user = update.effective_user
        u = one("SELECT last_gift FROM users WHERE user_id=?", (user.id,))
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if u and u["last_gift"] == today:
            await q.edit_message_text("🎁 Aaj ka gift already claim kar liya. Kal wapas aayein!", reply_markup=kb([[b("🏠 Main Menu", "home")]]))
            return
        execute("UPDATE users SET balance=balance+?,last_gift=? WHERE user_id=?", (gift, today, user.id))
        execute("INSERT INTO wallet_transactions(user_id,amount_delta,note) VALUES(?,?,?)", (user.id, gift, "Daily gift"))
        await q.edit_message_text("🎁 <b>Daily Gift Claimed!</b>\n💰 +" + money(gift) + " added to wallet.", reply_markup=kb([[b("🏠 Main Menu", "home")]]), parse_mode="HTML")
    elif data.startswith("cat:"):
        await show_products(update, int(data.split(":")[1]))
    elif data.startswith("prod:"):
        await show_product(update, context, int(data.split(":")[1]))
    elif data.startswith("buy:"):
        await begin_buy(update, context, int(data.split(":")[1]))
    elif data.startswith("walletbuy:"):
        await wallet_buy(update, context, int(data.split(":")[1]))

    # ===== ADMIN PANEL =====
    elif data == "adm:home":
        upi = get_setting("upi_id") or "(not set)"
        payee = get_setting("payee_name") or BRAND_NAME
        total_users = one("SELECT COUNT(*) n FROM users")["n"]
        msg = (
            "⚙️ <b>ELITE X CONFIG — Admin Panel</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👥 Total Users: <b>{total_users}</b>\n"
            f"💳 UPI: <code>{upi}</code>\n"
            f"🏷️ Payee: <b>{payee}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "👇 Select a control module:"
        )
        try:
            await q.edit_message_text(msg, reply_markup=admin_kb(), parse_mode="HTML")
        except BadRequest:
            await q.edit_message_caption(caption=msg, reply_markup=admin_kb(), parse_mode="HTML")
    elif data == "adm:dash":
        users = one("SELECT COUNT(*) n FROM users")["n"]
        cats = one("SELECT COUNT(*) n FROM categories")["n"]
        prods = one("SELECT COUNT(*) n FROM products")["n"]
        po = one("SELECT COUNT(*) n FROM orders WHERE status='pending'")["n"]
        pb = one("SELECT COUNT(*) n FROM balance_requests WHERE status='pending'")["n"]
        keys = one("SELECT COUNT(*) n FROM key_stock WHERE status='available'")["n"]
        coa = one("SELECT COUNT(*) n FROM co_admins")["n"]
        coup = one("SELECT COUNT(*) n FROM coupons")["n"]
        text = (
            "📊 <b>DASHBOARD</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👥 Users: <b>{users}</b>\n"
            f"📂 Categories: <b>{cats}</b>\n"
            f"📦 Products: <b>{prods}</b>\n"
            f"🔑 Available Keys: <b>{keys}</b>\n"
            f"🧾 Pending Orders: <b>{po}</b>\n"
            f"💰 Pending Bal Req: <b>{pb}</b>\n"
            f"🤝 Co-Admins: <b>{coa}</b>\n"
            f"🎟️ Coupons: <b>{coup}</b>"
        )
        await q.edit_message_text(text, reply_markup=admin_kb(), parse_mode="HTML")
    elif data == "adm:logo":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_logo"
        await q.edit_message_text("🖼️ Admin logo/banner ke liye PHOTO bhejein.\n\nYe har /admin command aur welcome pe dikhega.")
    elif data == "adm:cats":
        await q.edit_message_text("📂 <b>CATEGORY MANAGER</b>", reply_markup=category_admin_kb(), parse_mode="HTML")
    elif data == "adm:prods":
        await q.edit_message_text("📦 <b>PRODUCT MANAGER</b>", reply_markup=product_admin_kb(), parse_mode="HTML")
    elif data == "adm:keys":
        await q.edit_message_text("🔑 <b>KEY MANAGER</b>", reply_markup=key_admin_kb(), parse_mode="HTML")
    elif data == "adm:bal":
        await q.edit_message_text("💰 <b>BALANCE MANAGER</b>", reply_markup=balance_admin_kb(), parse_mode="HTML")
    elif data == "adm:users":
        await q.edit_message_text("👥 <b>USER MANAGER</b>", reply_markup=user_admin_kb(), parse_mode="HTML")
    elif data == "adm:coupons":
        await q.edit_message_text("🎟️ <b>COUPON SYSTEM</b>", reply_markup=coupon_admin_kb(), parse_mode="HTML")
    elif data == "adm:coadmins":
        await q.edit_message_text("🤝 <b>CO-ADMIN MANAGER</b>", reply_markup=coadmin_kb(), parse_mode="HTML")
    elif data == "adm:reseller":
        st = "✅ ON" if get_setting("reseller_system", "0") == "1" else "❌ OFF"
        await q.edit_message_text("🏪 <b>RESELLER SYSTEM</b>\n\nStatus: " + st, reply_markup=reseller_kb(), parse_mode="HTML")
    elif data == "adm:payment":
        await q.edit_message_text("💳 <b>PAYMENT SETTINGS</b>", reply_markup=payment_kb(), parse_mode="HTML")
    elif data == "adm:gift":
        await q.edit_message_text("🎁 <b>GIFT & REFER</b>", reply_markup=gift_kb(), parse_mode="HTML")
    elif data == "adm:links":
        await q.edit_message_text("🔗 <b>LINK MANAGER</b>", reply_markup=link_kb(), parse_mode="HTML")
    elif data == "adm:api":
        await q.edit_message_text("🌐 <b>API MANAGER</b>", reply_markup=api_kb(), parse_mode="HTML")
    elif data == "adm:messages":
        await q.edit_message_text("✏️ <b>MESSAGE EDITOR</b>\n\nJo message edit karna hai select karein:", reply_markup=messages_kb(), parse_mode="HTML")
    elif data == "adm:broadcast":
        await q.edit_message_text("📢 <b>BROADCAST SYSTEM</b>", reply_markup=broadcast_kb(), parse_mode="HTML")
    elif data == "adm:maintenance":
        st = "🔴 ON" if is_maintenance() else "🟢 OFF"
        await q.edit_message_text("🔧 <b>MAINTENANCE MODE</b>\n\nStatus: " + st, reply_markup=maintenance_kb(), parse_mode="HTML")
    elif data == "adm:transfer":
        context.user_data.clear()
        context.user_data["admin_state"] = "transfer_owner"
        await q.edit_message_text("👑 <b>TRANSFER OWNERSHIP</b>\n\nNaye owner ka User ID bhejein (numeric).\n\n⚠️ Ye irreversible hai!")
    elif data == "adm:mt_toggle":
        new = 0 if is_maintenance() else 1
        execute("UPDATE maintenance SET enabled=? WHERE id=1", (new,))
        st = "🔴 ON" if new else "🟢 OFF"
        await q.edit_message_text("🔧 <b>MAINTENANCE MODE</b>\n\nStatus: " + st, reply_markup=maintenance_kb(), parse_mode="HTML")
    elif data == "adm:mt_edit":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_maintenance_msg"
        await q.edit_message_text("✏️ Naya maintenance message bhejein:")

    # ===== CATEGORY ACTIONS =====
    elif data == "adm:cat_add":
        context.user_data.clear()
        context.user_data["admin_state"] = "addcat_name"
        await q.edit_message_text("📂 Category ka naam bhejein:")
    elif data == "adm:cat_list":
        await admin_list_categories(update, context)
    elif data.startswith("adm:cat_view:"):
        await admin_view_category(update, context, int(data.rsplit(":", 1)[1]))
    elif data.startswith("adm:cat_editname:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_cat_name"
        context.user_data["admin_edit_cat_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("✏️ Naya category name bhejein:")
    elif data.startswith("adm:cat_editemoji:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_cat_emoji"
        context.user_data["admin_edit_cat_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("😀 Naya emoji bhejein (single emoji):")
    elif data.startswith("adm:cat_toggle:"):
        cat_id = int(data.rsplit(":", 1)[1])
        c = one("SELECT visible FROM categories WHERE id=?", (cat_id,))
        if c:
            execute("UPDATE categories SET visible=? WHERE id=?", (0 if c["visible"] else 1, cat_id))
        await admin_view_category(update, context, cat_id)
    elif data.startswith("adm:cat_del:"):
        cat_id = int(data.rsplit(":", 1)[1])
        prods = one("SELECT COUNT(*) n FROM products WHERE category_id=?", (cat_id,))["n"]
        if prods:
            await q.answer(f"Pehle {prods} products delete karein.", show_alert=True)
            return
        execute("DELETE FROM categories WHERE id=?", (cat_id,))
        await q.answer("Deleted")
        await admin_list_categories(update, context)

    # ===== PRODUCT ACTIONS =====
    elif data == "adm:prod_add":
        cats = query("SELECT id,name FROM categories ORDER BY id")
        if not cats:
            await q.edit_message_text("Pehle category add karein.", reply_markup=product_admin_kb())
            return
        rows = [[b(c["name"], "adm:prod_cat:" + str(c["id"]))] for c in cats]
        rows.append([b("⬅️ Back", "adm:prods")])
        await q.edit_message_text("📂 Product kis category mein add karna hai?", reply_markup=kb(rows))
    elif data.startswith("adm:prod_cat:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "addprod_name"
        context.user_data["admin_category_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("📝 Product name bhejein:")
    elif data == "adm:prod_list":
        await admin_list_products(update, context)
    elif data.startswith("adm:prod_view:"):
        await admin_view_product(update, context, int(data.rsplit(":", 1)[1]))
    elif data.startswith("adm:prod_editname:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_prod_name"
        context.user_data["admin_edit_prod_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("✏️ Naya product name bhejein:")
    elif data.startswith("adm:prod_editprice:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_prod_price"
        context.user_data["admin_edit_prod_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("💰 Nayi price ₹ mein bhejein:")
    elif data.startswith("adm:prod_editdesc:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_prod_desc"
        context.user_data["admin_edit_prod_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("📝 Naya description bhejein (ya '-' clear karne ke liye):")
    elif data.startswith("adm:prod_editres:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_prod_res"
        context.user_data["admin_edit_prod_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("🏪 Reseller price bhejein:")
    elif data.startswith("adm:prod_editdisc:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_prod_disc"
        context.user_data["admin_edit_prod_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("💸 Discount % bhejein (0-100):")
    elif data.startswith("adm:prod_editlink:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_prod_link"
        context.user_data["admin_edit_prod_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("🔗 Download link bhejein (ya '-' clear karne ke liye):")
    elif data.startswith("adm:prod_movecat:"):
        prod_id = int(data.rsplit(":", 1)[1])
        cats = query("SELECT id,name FROM categories ORDER BY id")
        rows = [[b(c["name"], "adm:prod_setcat:" + str(prod_id) + ":" + str(c["id"]))] for c in cats]
        rows.append([b("⬅️ Back", "adm:prod_view:" + str(prod_id))])
        await q.edit_message_text("📂 Nayi category select karein:", reply_markup=kb(rows))
    elif data.startswith("adm:prod_setcat:"):
        parts = data.split(":")
        pid, cid = int(parts[2]), int(parts[3])
        execute("UPDATE products SET category_id=? WHERE id=?", (cid, pid))
        await admin_view_product(update, context, pid)
    elif data.startswith("adm:prod_setapi:"):
        prod_id = int(data.rsplit(":", 1)[1])
        apis = query("SELECT id,name FROM apis ORDER BY id")
        if not apis:
            await q.edit_message_text("Koi API nahi. Pehle API add karein.", reply_markup=product_admin_kb())
            return
        rows = [[b(a["name"], "adm:prod_api_set:" + str(prod_id) + ":" + str(a["id"]))] for a in apis]
        rows.append([b("⬅️ Back", "adm:prod_view:" + str(prod_id))])
        await q.edit_message_text("🌐 API select karein:", reply_markup=kb(rows))
    elif data.startswith("adm:prod_api_set:"):
        parts = data.split(":")
        pid, aid = int(parts[2]), int(parts[3])
        execute("UPDATE products SET api_id=? WHERE id=?", (aid, pid))
        await admin_view_product(update, context, pid)
    elif data.startswith("adm:prod_toggle:"):
        pid = int(data.rsplit(":", 1)[1])
        p = one("SELECT visible FROM products WHERE id=?", (pid,))
        if p:
            execute("UPDATE products SET visible=? WHERE id=?", (0 if p["visible"] else 1, pid))
        await admin_view_product(update, context, pid)
    elif data.startswith("adm:prod_del:"):
        pid = int(data.rsplit(":", 1)[1])
        with closing(db()) as con:
            con.execute("DELETE FROM key_stock WHERE product_id=?", (pid,))
            con.execute("DELETE FROM products WHERE id=?", (pid,))
            con.commit()
        await q.answer("Deleted")
        await admin_list_products(update, context)
    elif data == "adm:prod_link":
        context.user_data.clear()
        context.user_data["admin_state"] = "pick_prod_link"
        prods = query("SELECT id,name FROM products ORDER BY id")
        if not prods:
            await q.edit_message_text("Koi product nahi.", reply_markup=product_admin_kb())
            return
        rows = [[b(p["name"], "adm:prod_editlink:" + str(p["id"]))] for p in prods]
        rows.append([b("⬅️ Back", "adm:prods")])
        await q.edit_message_text("🔗 Kis product ka download link set karna hai?", reply_markup=kb(rows))
    elif data == "adm:prod_api":
        context.user_data.clear()
        prods = query("SELECT id,name FROM products ORDER BY id")
        if not prods:
            await q.edit_message_text("Koi product nahi.", reply_markup=product_admin_kb())
            return
        rows = [[b(p["name"], "adm:prod_setapi:" + str(p["id"]))] for p in prods]
        rows.append([b("⬅️ Back", "adm:prods")])
        await q.edit_message_text("🎯 Kis product ka API set karna hai?", reply_markup=kb(rows))
    elif data == "adm:prod_disc":
        prods = query("SELECT id,name FROM products ORDER BY id")
        if not prods:
            await q.edit_message_text("Koi product nahi.", reply_markup=product_admin_kb())
            return
        rows = [[b(p["name"], "adm:prod_editdisc:" + str(p["id"]))] for p in prods]
        rows.append([b("⬅️ Back", "adm:prods")])
        await q.edit_message_text("💸 Kis product ka discount set karna hai?", reply_markup=kb(rows))

    # ===== KEY ACTIONS =====
    elif data == "adm:key_add":
        prods = query("SELECT id,name FROM products ORDER BY id")
        if not prods:
            await q.edit_message_text("Pehle product add karein.", reply_markup=admin_kb())
            return
        rows = [[b(p["name"], "adm:key_prod:" + str(p["id"]))] for p in prods]
        rows.append([b("⬅️ Back", "adm:keys")])
        await q.edit_message_text("🔑 Kis product ke liye key add karni hai?", reply_markup=kb(rows))
    elif data.startswith("adm:key_prod:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "addkey_text"
        context.user_data["admin_product_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("🔑 Ab key paste karein. Ek message = ek key.")
    elif data == "adm:key_remove":
        prods = query("SELECT id,name FROM products ORDER BY id")
        rows = [[b(p["name"], "adm:key_remove_prod:" + str(p["id"]))] for p in prods]
        rows.append([b("⬅️ Back", "adm:keys")])
        await q.edit_message_text("🗑️ Kis product se key remove karni hai?", reply_markup=kb(rows))
    elif data.startswith("adm:key_remove_prod:"):
        pid = int(data.rsplit(":", 1)[1])
        keys = query("SELECT id,key_text FROM key_stock WHERE product_id=? AND status='available' ORDER BY id LIMIT 20", (pid,))
        if not keys:
            await q.edit_message_text("Is product ki koi available key nahi hai.", reply_markup=key_admin_kb())
            return
        rows = [[b("🗑️ " + k["key_text"][:30], "adm:key_del:" + str(k["id"]))] for k in keys]
        rows.append([b("⬅️ Back", "adm:keys")])
        await q.edit_message_text("Select key to delete:", reply_markup=kb(rows))
    elif data.startswith("adm:key_del:"):
        kid = int(data.rsplit(":", 1)[1])
        execute("DELETE FROM key_stock WHERE id=?", (kid,))
        await q.answer("Key deleted")
        await q.edit_message_text("✅ Key delete ho gayi.", reply_markup=key_admin_kb())
    elif data == "adm:key_check":
        prods = query("SELECT id,name FROM products ORDER BY id")
        rows = [[b(p["name"], "adm:key_check_prod:" + str(p["id"]))] for p in prods]
        rows.append([b("⬅️ Back", "adm:keys")])
        await q.edit_message_text("📋 Kis product ka stock check karna hai?", reply_markup=kb(rows))
    elif data.startswith("adm:key_check_prod:"):
        pid = int(data.rsplit(":", 1)[1])
        p = one("SELECT name FROM products WHERE id=?", (pid,))
        avail = one("SELECT COUNT(*) n FROM key_stock WHERE product_id=? AND status='available'", (pid,))["n"]
        sold = one("SELECT COUNT(*) n FROM key_stock WHERE product_id=? AND status='sold'", (pid,))["n"]
        await q.edit_message_text(f"📊 <b>{p['name']}</b>\n\n✅ Available: {avail}\n❌ Sold: {sold}", reply_markup=key_admin_kb(), parse_mode="HTML")
    elif data == "adm:key_clear":
        execute("DELETE FROM key_stock WHERE status='available'")
        await q.edit_message_text("🧹 <b>All available stock cleared!</b>", reply_markup=key_admin_kb(), parse_mode="HTML")

    # ===== BALANCE ACTIONS =====
    elif data == "adm:bal_add":
        context.user_data.clear()
        context.user_data["admin_state"] = "bal_add_uid"
        await q.edit_message_text("➕ <b>Add Balance</b>\n\nUser ID bhejein:")
    elif data == "adm:bal_remove":
        context.user_data.clear()
        context.user_data["admin_state"] = "bal_remove_uid"
        await q.edit_message_text("➖ <b>Remove Balance</b>\n\nUser ID bhejein:")
    elif data == "adm:bal_check":
        context.user_data.clear()
        context.user_data["admin_state"] = "bal_check_uid"
        await q.edit_message_text("🔍 <b>Check Balance</b>\n\nUser ID bhejein:")
    elif data == "adm:bal_addall":
        context.user_data.clear()
        context.user_data["admin_state"] = "bal_addall_amt"
        await q.edit_message_text("👥 <b>Add Balance to All Users</b>\n\nAmount bhejein (₹):")
    elif data == "adm:bal_requests":
        rows_db = query("SELECT id,user_id,amount,status FROM balance_requests ORDER BY id DESC LIMIT 15")
        if not rows_db:
            await q.edit_message_text("Koi request nahi.", reply_markup=balance_admin_kb())
            return
        body = "🧾 <b>BALANCE REQUESTS</b>\n━━━━━━━━━━━━━━━━━━\n"
        for r in rows_db:
            body += f"#{r['id']} user <code>{r['user_id']}</code> • {money(r['amount'])} • {r['status']}\n"
        await q.edit_message_text(body, reply_markup=balance_admin_kb(), parse_mode="HTML")

    # ===== USER MANAGER =====
    elif data == "adm:user_all":
        await admin_list_users(update, context)
    elif data == "adm:user_total":
        n = one("SELECT COUNT(*) n FROM users")["n"]
        await q.edit_message_text(f"👥 Total Users: <b>{n}</b>", reply_markup=user_admin_kb(), parse_mode="HTML")

    # ===== COUPON =====
    elif data == "adm:coupon_gen":
        context.user_data.clear()
        context.user_data["admin_state"] = "coupon_discount"
        await q.edit_message_text("🎟️ Coupon discount % bhejein (0-100):")
    elif data == "adm:coupon_view":
        await admin_list_coupons(update, context)
    elif data == "adm:coupon_del":
        context.user_data.clear()
        context.user_data["admin_state"] = "coupon_del"
        await q.edit_message_text("🗑️ Delete karne ke liye coupon code bhejein:")

    # ===== CO-ADMIN =====
    elif data == "adm:coadmin_add":
        context.user_data.clear()
        context.user_data["admin_state"] = "coadmin_add"
        await q.edit_message_text("🤝 Co-admin ka User ID bhejein:")
    elif data == "adm:coadmin_remove":
        context.user_data.clear()
        context.user_data["admin_state"] = "coadmin_remove"
        await q.edit_message_text("🤝 Remove karne ke liye User ID bhejein:")
    elif data == "adm:coadmin_view":
        await admin_list_coadmins(update, context)

    # ===== RESELLER =====
    elif data == "adm:res_toggle":
        new = "0" if get_setting("reseller_system", "0") == "1" else "1"
        set_setting("reseller_system", new)
        st = "✅ ON" if new == "1" else "❌ OFF"
        await q.edit_message_text("🏪 <b>RESELLER SYSTEM</b>\n\nStatus: " + st, reply_markup=reseller_kb(), parse_mode="HTML")
    elif data == "adm:res_setprice":
        prods = query("SELECT id,name FROM products ORDER BY id")
        rows = [[b(p["name"], "adm:prod_editres:" + str(p["id"]))] for p in prods]
        rows.append([b("⬅️ Back", "adm:reseller")])
        await q.edit_message_text("💰 Kis product ka reseller price set karna hai?", reply_markup=kb(rows))
    elif data == "adm:res_direct":
        context.user_data.clear()
        context.user_data["admin_state"] = "res_direct_uid"
        await q.edit_message_text("🎯 User ID bhejein jise reseller banana hai:")
    elif data == "adm:res_setuser":
        context.user_data.clear()
        context.user_data["admin_state"] = "res_setuser_uid"
        await q.edit_message_text("👤 User ID bhejein (reseller banane ke liye):")

    # ===== PAYMENT SETTINGS =====
    elif data == "adm:set_upi":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_upi"
        await q.edit_message_text("💳 UPI ID bhejein (jaise: yourname@upi):")
    elif data == "adm:set_payee":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_payee"
        await q.edit_message_text("🏷️ Payee name bhejein:")
    elif data == "adm:set_qr":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_qr"
        await q.edit_message_text("🖼️ Static QR image PHOTO bhejein:")
    elif data == "adm:set_zapupi":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_zapupi"
        await q.edit_message_text("⚡ ZapUPI key bhejein:")
    elif data == "adm:set_binance":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_binance"
        await q.edit_message_text("🪙 Binance Pay ID bhejein:")
    elif data == "adm:set_instructions":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_instructions"
        await q.edit_message_text("⚙️ Payment instructions bhejein:")

    # ===== GIFT/REFER =====
    elif data == "adm:set_gift":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_gift"
        await q.edit_message_text("🎁 Daily gift amount bhejein (0 = disable):")
    elif data == "adm:set_refer":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_refer"
        await q.edit_message_text("🤝 Refer & earn amount bhejein (0 = disable):")

    # ===== LINKS =====
    elif data == "adm:set_support":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_support"
        await q.edit_message_text("🎧 Support URL bhejein:")
    elif data == "adm:set_howto":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_howto"
        await q.edit_message_text("📖 How-to-use URL bhejein:")
    elif data == "adm:set_prooflink":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_prooflink"
        await q.edit_message_text("📸 Payment proof URL bhejein:")

    # ===== API =====
    elif data == "adm:api_add":
        context.user_data.clear()
        context.user_data["admin_state"] = "api_name"
        await q.edit_message_text("🌐 API ka naam bhejein:")
    elif data == "adm:api_view":
        await admin_list_apis(update, context)
    elif data == "adm:api_del":
        context.user_data.clear()
        context.user_data["admin_state"] = "api_del"
        await q.edit_message_text("🗑️ Delete karne ke liye API ID bhejein:")

    # ===== MESSAGES =====
    elif data == "adm:msg_welcome":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_welcome"
        await q.edit_message_text("✏️ Naya WELCOME message bhejein:\n\n<b>Current:</b>\n" + get_setting("welcome", WELCOME_DEFAULT)[:400], parse_mode="HTML")
    elif data == "adm:msg_category":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_category_msg"
        await q.edit_message_text("✏️ Naya CATEGORY message bhejein:")
    elif data == "adm:msg_product":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_product_msg"
        await q.edit_message_text("✏️ Naya PRODUCT message bhejein:")
    elif data == "adm:msg_key":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_key_msg"
        await q.edit_message_text("✏️ Naya KEY message bhejein:")
    elif data == "adm:msg_profile":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_profile_msg"
        await q.edit_message_text("✏️ Naya PROFILE message bhejein:")
    elif data == "adm:msg_orders":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_orders_msg"
        await q.edit_message_text("✏️ Naya ORDERS message bhejein:")
    elif data == "adm:msg_support":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_support_msg"
        await q.edit_message_text("✏️ Naya SUPPORT message bhejein:")
    elif data == "adm:msg_balance":
        context.user_data.clear()
        context.user_data["admin_state"] = "set_balance_msg"
        await q.edit_message_text("✏️ Naya BALANCE message bhejein:")
    elif data == "adm:msg_reset":
        set_setting("welcome", WELCOME_DEFAULT)
        set_setting("category_message", CATEGORY_DEFAULT)
        set_setting("product_message", PRODUCT_DEFAULT)
        set_setting("key_message", KEY_DEFAULT)
        set_setting("profile_message", PROFILE_DEFAULT)
        set_setting("orders_message", ORDERS_DEFAULT)
        set_setting("support_message", SUPPORT_DEFAULT)
        set_setting("balance_message", BALANCE_DEFAULT)
        await q.edit_message_text("♻️ <b>All messages reset to default!</b>", reply_markup=messages_kb(), parse_mode="HTML")

    # ===== BROADCAST =====
    elif data == "adm:bc_send":
        context.user_data.clear()
        context.user_data["admin_state"] = "broadcast"
        await q.edit_message_text("📢 <b>Broadcast Message</b>\n\nJo message sabhi users ko bhejna hai wo bhejein.\n\n<i>Text, photo, video, ya document bhej sakte hain.</i>", parse_mode="HTML")
    elif data == "adm:bc_history":
        rows_db = query("SELECT * FROM broadcasts ORDER BY id DESC LIMIT 10")
        if not rows_db:
            await q.edit_message_text("Koi broadcast nahi.", reply_markup=broadcast_kb())
            return
        body = "📊 <b>BROADCAST HISTORY</b>\n━━━━━━━━━━━━━━━━━━\n"
        for r in rows_db:
            body += f"#{r['id']} • Sent: {r['sent_to']} • Failed: {r['failed']}\n"
        await q.edit_message_text(body, reply_markup=broadcast_kb(), parse_mode="HTML")

    # ===== APPROVALS =====
    elif data.startswith("ba:"):
        await admin_approve_balance(update, context, int(data.split(":")[1]), True)
    elif data.startswith("bj:"):
        await admin_approve_balance(update, context, int(data.split(":")[1]), False)
    elif data.startswith("oa:"):
        await admin_approve_order(update, context, int(data.split(":")[1]), True)
    elif data.startswith("or:"):
        await admin_approve_order(update, context, int(data.split(":")[1]), False)

# ==================== MESSAGE HANDLER ====================
async def on_message(update, context):
    msg = update.effective_message
    if not msg:
        return
    text = (msg.text or "").strip()
    state = context.user_data.get("admin_state")
    user = update.effective_user
    is_admin_user = is_co_admin(update)

    # ===== ADMIN STATES =====
    if state and is_admin_user:
        # LOGO
        if state == "set_logo" and msg.photo:
            set_setting("admin_logo_file_id", msg.photo[-1].file_id)
            context.user_data.clear()
            await msg.reply_text("✅ Admin logo saved!", reply_markup=admin_kb())
            return
        # SETTINGS (simple text)
        simple_settings = {
            "set_upi": ("upi_id", "✅ UPI ID"),
            "set_payee": ("payee_name", "✅ Payee name"),
            "set_zapupi": ("zapupi_key", "✅ ZapUPI key"),
            "set_binance": ("binance_pay_id", "✅ Binance Pay ID"),
            "set_instructions": ("payment_instructions", "✅ Payment instructions"),
            "set_gift": ("daily_gift_price", "✅ Daily gift"),
            "set_refer": ("refer_earn_amount", "✅ Refer & earn"),
            "set_support": ("support_url", "✅ Support URL"),
            "set_howto": ("how_to_use_url", "✅ How-to-use URL"),
            "set_prooflink": ("payment_proof_url", "✅ Payment proof URL"),
            "set_maintenance_msg": ("", "✅ Maintenance message"),
            "set_welcome": ("welcome", "✅ Welcome message"),
            "set_category_msg": ("category_message", "✅ Category message"),
            "set_product_msg": ("product_message", "✅ Product message"),
            "set_key_msg": ("key_message", "✅ Key message"),
            "set_profile_msg": ("profile_message", "✅ Profile message"),
            "set_orders_msg": ("orders_message", "✅ Orders message"),
            "set_support_msg": ("support_message", "✅ Support message"),
            "set_balance_msg": ("balance_message", "✅ Balance message"),
        }
        if state in simple_settings and text:
            key, ok = simple_settings[state]
            if state == "set_maintenance_msg":
                execute("UPDATE maintenance SET message=? WHERE id=1", (text,))
            else:
                set_setting(key, text)
            context.user_data.clear()
            await msg.reply_text(ok + " saved.", reply_markup=admin_kb())
            return
        # QR
        if state == "set_qr" and msg.photo:
            set_setting("payment_qr_file_id", msg.photo[-1].file_id)
            context.user_data.clear()
            await msg.reply_text("✅ Static QR saved.", reply_markup=payment_kb())
            return
        # CATEGORY
        if state == "addcat_name" and text:
            execute("INSERT INTO categories(name) VALUES(?)", (text[:100],))
            context.user_data.clear()
            await msg.reply_text("✅ Category added.", reply_markup=category_admin_kb())
            return
        if state == "edit_cat_name" and text:
            cid = int(context.user_data.get("admin_edit_cat_id", 0))
            execute("UPDATE categories SET name=? WHERE id=?", (text[:100], cid))
            context.user_data.clear()
            await msg.reply_text("✅ Updated.", reply_markup=category_admin_kb())
            return
        if state == "edit_cat_emoji" and text:
            cid = int(context.user_data.get("admin_edit_cat_id", 0))
            execute("UPDATE categories SET emoji=? WHERE id=?", (text[:10], cid))
            context.user_data.clear()
            await msg.reply_text("✅ Updated.", reply_markup=category_admin_kb())
            return
        # PRODUCT flow
        if state == "addprod_name" and text:
            context.user_data["new_product_name"] = text[:100]
            context.user_data["admin_state"] = "addprod_price"
            await msg.reply_text("💰 Price ₹ mein bhejein:")
            return
        if state == "addprod_price" and text:
            try:
                price = float(text.replace(",", ""))
            except ValueError:
                await msg.reply_text("Number bhejein, jaise 199.")
                return
            name = context.user_data.get("new_product_name", "Product")
            cid = int(context.user_data.get("admin_category_id", 0))
            execute("INSERT INTO products(category_id,name,price) VALUES(?,?,?)", (cid, name, price))
            context.user_data.clear()
            await msg.reply_text("✅ Product added: " + name, reply_markup=product_admin_kb())
            return
        if state in ("edit_prod_name", "edit_prod_desc", "edit_prod_res", "edit_prod_disc", "edit_prod_link"):
            pid = int(context.user_data.get("admin_edit_prod_id", 0))
            field_map = {
                "edit_prod_name": ("name", text[:100]),
                "edit_prod_desc": ("description", "" if text == "-" else text[:1000]),
                "edit_prod_link": ("download_link", "" if text == "-" else text[:500]),
            }
            if state in field_map:
                col, val = field_map[state]
                execute(f"UPDATE products SET {col}=? WHERE id=?", (val, pid))
            elif state == "edit_prod_res":
                try:
                    val = float(text.replace(",", ""))
                except ValueError:
                    await msg.reply_text("Number bhejein.")
                    return
                execute("UPDATE products SET reseller_price=? WHERE id=?", (val, pid))
            elif state == "edit_prod_disc":
                try:
                    val = int(text)
                except ValueError:
                    await msg.reply_text("Integer bhejein.")
                    return
                execute("UPDATE products SET discount=? WHERE id=?", (val, pid))
            context.user_data.clear()
            await msg.reply_text("✅ Updated.", reply_markup=product_admin_kb())
            return
        # KEY add
        if state == "addkey_text" and text:
            pid = int(context.user_data.get("admin_product_id", 0))
            execute("INSERT INTO key_stock(product_id,key_text) VALUES(?,?)", (pid, text))
            context.user_data.clear()
            await msg.reply_text("✅ Key added.", reply_markup=key_admin_kb())
            return
        # BALANCE add/remove/check/addall
        if state == "bal_add_uid" and text:
            try:
                uid = int(text)
            except ValueError:
                await msg.reply_text("Numeric user ID bhejein.")
                return
            context.user_data["bal_target_uid"] = uid
            context.user_data["admin_state"] = "bal_add_amt"
            await msg.reply_text("Amount ₹ bhejein:")
            return
        if state == "bal_add_amt" and text:
            try:
                amt = float(text)
            except ValueError:
                await msg.reply_text("Number bhejein.")
                return
            uid = int(context.user_data.get("bal_target_uid", 0))
            if not one("SELECT 1 FROM users WHERE user_id=?", (uid,)):
                context.user_data.clear()
                await msg.reply_text("❌ User nahi mila.", reply_markup=balance_admin_kb())
                return
            execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
            execute("INSERT INTO wallet_transactions(user_id,amount_delta,note) VALUES(?,?,?)", (uid, amt, "Admin credit"))
            context.user_data.clear()
            await msg.reply_text("✅ Balance added.", reply_markup=balance_admin_kb())
            try:
                await context.bot.send_message(uid, f"💰 Admin ne aapko {money(amt)} balance add kiya!")
            except TelegramError:
                pass
            return
        if state == "bal_remove_uid" and text:
            try:
                uid = int(text)
            except ValueError:
                await msg.reply_text("Numeric ID bhejein.")
                return
            context.user_data["bal_target_uid"] = uid
            context.user_data["admin_state"] = "bal_remove_amt"
            await msg.reply_text("Amount ₹ bhejein:")
            return
        if state == "bal_remove_amt" and text:
            try:
                amt = float(text)
            except ValueError:
                await msg.reply_text("Number bhejein.")
                return
            uid = int(context.user_data.get("bal_target_uid", 0))
            execute("UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=?", (amt, uid))
            execute("INSERT INTO wallet_transactions(user_id,amount_delta,note) VALUES(?,?,?)", (uid, -amt, "Admin debit"))
            context.user_data.clear()
            await msg.reply_text("✅ Balance removed.", reply_markup=balance_admin_kb())
            return
        if state == "bal_check_uid" and text:
            try:
                uid = int(text)
            except ValueError:
                await msg.reply_text("Numeric ID bhejein.")
                return
            u = one("SELECT balance,name FROM users WHERE user_id=?", (uid,))
            context.user_data.clear()
            if u:
                await msg.reply_text(f"👤 {u['name']}\n💰 Balance: {money(u['balance'])}", reply_markup=balance_admin_kb())
            else:
                await msg.reply_text("❌ User nahi mila.", reply_markup=balance_admin_kb())
            return
        if state == "bal_addall_amt" and text:
            try:
                amt = float(text)
            except ValueError:
                await msg.reply_text("Number bhejein.")
                return
            with closing(db()) as con:
                con.execute("UPDATE users SET balance=balance+?", (amt,))
                con.commit()
            context.user_data.clear()
            await msg.reply_text(f"✅ Added {money(amt)} to ALL users.", reply_markup=balance_admin_kb())
            return
        # COUPON
        if state == "coupon_discount" and text:
            try:
                d = float(text)
            except ValueError:
                await msg.reply_text("Number bhejein.")
                return
            context.user_data["coupon_discount"] = d
            context.user_data["admin_state"] = "coupon_maxuses"
            await msg.reply_text("Max uses bhejein:")
            return
        if state == "coupon_maxuses" and text:
            try:
                mu = int(text)
            except ValueError:
                await msg.reply_text("Integer bhejein.")
                return
            code = rand_code(8)
            d = float(context.user_data.get("coupon_discount", 0))
            execute("INSERT INTO coupons(code,discount,max_uses) VALUES(?,?,?)", (code, d, mu))
            context.user_data.clear()
            await msg.reply_text(f"🎟️ Coupon: <code>{code}</code>\n💸 {d}% off | Uses: {mu}", reply_markup=coupon_admin_kb(), parse_mode="HTML")
            return
        if state == "coupon_del" and text:
            execute("DELETE FROM coupons WHERE code=?", (text.upper(),))
            context.user_data.clear()
            await msg.reply_text("✅ Coupon deleted.", reply_markup=coupon_admin_kb())
            return
        # CO-ADMIN
        if state == "coadmin_add" and text:
            try:
                uid = int(text)
            except ValueError:
                await msg.reply_text("Numeric ID bhejein.")
                return
            u = one("SELECT name FROM users WHERE user_id=?", (uid,))
            name = u["name"] if u else "Unknown"
            execute("INSERT OR IGNORE INTO co_admins(user_id,name) VALUES(?,?)", (uid, name))
            context.user_data.clear()
            await msg.reply_text("✅ Co-admin added.", reply_markup=coadmin_kb())
            try:
                await context.bot.send_message(uid, "🤝 Aapko co-admin banaya gaya hai!")
            except TelegramError:
                pass
            return
        if state == "coadmin_remove" and text:
            try:
                uid = int(text)
            except ValueError:
                await msg.reply_text("Numeric ID bhejein.")
                return
            execute("DELETE FROM co_admins WHERE user_id=?", (uid,))
            context.user_data.clear()
            await msg.reply_text("✅ Co-admin removed.", reply_markup=coadmin_kb())
            return
        # RESELLER
        if state == "res_direct_uid" and text:
            try:
                uid = int(text)
            except ValueError:
                await msg.reply_text("Numeric ID bhejein.")
                return
            execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT(user_id) DO NOTHING", (uid,))
            execute("UPDATE users SET is_reseller=1 WHERE user_id=?", (uid,))
            context.user_data.clear()
            await msg.reply_text("✅ Reseller banaya gaya.", reply_markup=reseller_kb())
            return
        if state == "res_setuser_uid" and text:
            try:
                uid = int(text)
            except ValueError:
                await msg.reply_text("Numeric ID bhejein.")
                return
            execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT(user_id) DO NOTHING", (uid,))
            execute("UPDATE users SET is_reseller=1 WHERE user_id=?", (uid,))
            context.user_data.clear()
            await msg.reply_text("✅ Reseller role set.", reply_markup=reseller_kb())
            return
        # API flow
        if state == "api_name" and text:
            context.user_data["api_name"] = text[:100]
            context.user_data["admin_state"] = "api_url"
            await msg.reply_text("URL bhejein:")
            return
        if state == "api_url" and text:
            context.user_data["api_url"] = text[:500]
            context.user_data["admin_state"] = "api_key"
            await msg.reply_text("API key bhejein:")
            return
        if state == "api_key" and text:
            name = context.user_data.get("api_name", "")
            url = context.user_data.get("api_url", "")
            execute("INSERT INTO apis(name,url,api_key) VALUES(?,?,?)", (name, url, text[:500]))
            context.user_data.clear()
            await msg.reply_text("✅ API added.", reply_markup=api_kb())
            return
        if state == "api_del" and text:
            try:
                aid = int(text)
            except ValueError:
                await msg.reply_text("Numeric ID bhejein.")
                return
            execute("DELETE FROM apis WHERE id=?", (aid,))
            context.user_data.clear()
            await msg.reply_text("✅ API deleted.", reply_markup=api_kb())
            return
        # TRANSFER OWNER
        if state == "transfer_owner" and text:
            try:
                uid = int(text)
            except ValueError:
                await msg.reply_text("Numeric ID bhejein.")
                return
            set_setting("owner_id", str(uid))
            context.user_data.clear()
            await msg.reply_text(f"👑 Ownership transferred to {uid}.", reply_markup=admin_kb())
            return
        # BROADCAST
        if state == "broadcast":
            users = query("SELECT user_id FROM users")
            sent = 0
            failed = 0
            for r in users:
                try:
                    if msg.photo:
                        await context.bot.send_photo(r["user_id"], msg.photo[-1].file_id, caption=(msg.caption or "")[:1024], parse_mode="HTML")
                    elif msg.video:
                        await context.bot.send_video(r["user_id"], msg.video.file_id, caption=(msg.caption or "")[:1024], parse_mode="HTML")
                    elif msg.document:
                        await context.bot.send_document(r["user_id"], msg.document.file_id, caption=(msg.caption or "")[:1024], parse_mode="HTML")
                    else:
                        await context.bot.send_message(r["user_id"], text[:4000], parse_mode="HTML")
                    sent += 1
                except TelegramError:
                    failed += 1
            execute("INSERT INTO broadcasts(message,sent_to,failed) VALUES(?,?,?)", ((text or msg.caption or "[media]")[:500], sent, failed))
            context.user_data.clear()
            await msg.reply_text(f"📢 <b>Broadcast complete!</b>\n✅ Sent: {sent}\n❌ Failed: {failed}", reply_markup=broadcast_kb(), parse_mode="HTML")
            return

    # ===== USER STATE HANDLERS =====
    if context.user_data.get("awaiting_custom_balance_amount") and text:
        try:
            amount = float(text.replace(",", "").replace("₹", "").strip())
        except ValueError:
            await msg.reply_text("Amount number mein bhejein.")
            return
        await create_balance_request(update, context, amount)
        return

    if context.user_data.get("awaiting_coupon") and text:
        code = text.upper().strip()
        c = one("SELECT * FROM coupons WHERE code=? AND used<max_uses", (code,))
        context.user_data.clear()
        if not c:
            await msg.reply_text("❌ Invalid ya expired coupon.", reply_markup=main_kb())
            return
        # Add as balance bonus
        execute("UPDATE coupons SET used=used+1 WHERE id=?", (c["id"],))
        execute("UPDATE users SET balance=balance+? WHERE user_id=?", (c["discount"], user.id))
        execute("INSERT INTO wallet_transactions(user_id,amount_delta,note) VALUES(?,?,?)", (user.id, c["discount"], "Coupon " + code))
        await msg.reply_text(f"🎟️ Coupon redeemed!\n💰 +{money(c['discount'])} added.", reply_markup=main_kb())
        return

    # PHOTO proof
    if msg.photo:
        await handle_proof(update, context)
        return

    # Commands / fallback
    if text == "/admin":
        await admin_command(update, context)
        return
    if text == "/cancel":
        context.user_data.clear()
        await msg.reply_text("Cancelled.", reply_markup=main_kb())
        return
    if text == "/start":
        await start(update, context)
        return
    if text and not state:
        await msg.reply_text("Menu use karein ya /start bhejein.", reply_markup=main_kb())

# ==================== MAIN ====================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.TEXT, on_message))
    log.info("ELITE X CONFIG bot starting; db=%s", DB_PATH)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()