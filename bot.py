#!/usr/bin/env python3
"""ELITE X CONFIG Telegram Store Bot
Python 3.10+ | python-telegram-bot 21.x / 22.x

Features:
- Category -> Product/Plan -> QR payment -> screenshot proof -> admin approval -> one-time key delivery
- Add Balance shows one manual QR-credit request flow; admin approves/rejects
- Admin can add/edit/delete categories, products/plans, keys, configure payment QR and inspect requests
- Admin can edit welcome message
- SQLite storage

Set BOT_TOKEN and ADMIN_IDS environment variables.
Example:
  export BOT_TOKEN="123:token"
  export ADMIN_IDS="123456789,987654321"
  python bot.py

IMPORTANT:
- A QR image cannot verify a payment by itself. Admin must manually verify the proof.
- Back up the SQLite database before updating an existing production bot.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS_TEXT = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = {int(x.strip()) for x in ADMIN_IDS_TEXT.split(",") if x.strip().isdigit()}
DB_PATH = os.getenv("DB_PATH", "elite_x_config.sqlite3").strip() or "elite_x_config.sqlite3"
LOGO_PATH = os.getenv("LOGO_PATH", "welcome_logo.png").strip()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("elite_x_config")

WELCOME_DEFAULT = (
    "⚡ ELITE X CONFIG ⚡\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Welcome to the ELITE X CONFIG Store.\n\n"
    "🛍️ Browse categories and products.\n"
    "💰 Add balance using QR payment.\n"
    "🔑 Keys are delivered after admin approval.\n"
    "🎧 Need help? Open Support.\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Choose an option below to continue."
)

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    return con

def query(sql: str, args: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with closing(db()) as con:
        return con.execute(sql, args).fetchall()

def one(sql: str, args: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    rows = query(sql, args)
    return rows[0] if rows else None

def execute(sql: str, args: tuple[Any, ...] = ()) -> int:
    with closing(db()) as con:
        cur = con.execute(sql, args)
        con.commit()
        return int(cur.lastrowid or 0)

def money(value: float | int) -> str:
    return f"₹{float(value):,.2f}"

def is_admin_user(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id in ADMIN_IDS:
        return True
    return bool(one("SELECT user_id FROM admins WHERE user_id=?", (user_id,)))

def is_admin(update: Update) -> bool:
    return is_admin_user(update.effective_user.id if update.effective_user else None)

def b(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data[:64])

def kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(rows)

def init_db() -> None:
    Path(DB_PATH).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    with closing(db()) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          user_id INTEGER PRIMARY KEY, name TEXT NOT NULL DEFAULT '',
          username TEXT NOT NULL DEFAULT '', balance REAL NOT NULL DEFAULT 0,
          joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS categories(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          emoji TEXT NOT NULL DEFAULT '📂', visible INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS products(
          id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER NOT NULL,
          name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          price REAL NOT NULL DEFAULT 0, visible INTEGER NOT NULL DEFAULT 1,
          FOREIGN KEY(category_id) REFERENCES categories(id)
        );
        CREATE TABLE IF NOT EXISTS key_stock(
          id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
          key_text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'available',
          added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          sold_to INTEGER, sold_at TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS balance_requests(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          username TEXT NOT NULL DEFAULT '', amount REAL NOT NULL,
          proof_file_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reviewed_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS orders(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          username TEXT NOT NULL DEFAULT '', product_id INTEGER NOT NULL,
          product_name TEXT NOT NULL, price REAL NOT NULL,
          payment_method TEXT NOT NULL DEFAULT 'qr',
          proof_file_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
          key_stock_id INTEGER, delivered_key TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reviewed_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS wallet_transactions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          amount_delta REAL NOT NULL, note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        defaults = {
            "welcome": WELCOME_DEFAULT,
            "payment_instructions": "Scan the QR code, pay the exact amount, then send a screenshot here. Admin approval is required.",
            "upi_id": "",
            "support_url": "https://t.me/elitexconfig",
            "payment_qr_file_id": "",
        }
        con.executemany("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", defaults.items())
        con.commit()

def get_setting(key: str, default: str = "") -> str:
    row = one("SELECT value FROM settings WHERE key=?", (key,))
    return str(row["value"]) if row else default

def set_setting(key: str, value: str) -> None:
    execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

def main_kb() -> InlineKeyboardMarkup:
    return kb([
        [b("🛍️ Shop Now", "shop"), b("👤 My Profile", "profile")],
        [b("💰 Add Balance", "addbalance"), b("📦 My Orders", "myorders")],
        [b("🎧 Support", "support")],
    ])

def admin_kb() -> InlineKeyboardMarkup:
    return kb([
        [b("📊 Dashboard", "adm:dash")],
        [b("📂 Categories", "adm:cats"), b("📦 Products", "adm:prods")],
        [b("🔑 Add Key Stock", "adm:addkey"), b("📋 Key Stock", "adm:stock")],
        [b("🧾 Product Payment Requests", "adm:orders"), b("💰 Balance Requests", "adm:balances")],
        [b("🖼️ Set Payment QR", "adm:setqr"), b("⚙️ Payment Instructions", "adm:instructions")],
        [b("✏️ Edit Welcome Message", "adm:welcome")],
        [b("🏠 User Menu", "home")],
    ])

def categories_admin_kb() -> InlineKeyboardMarkup:
    return kb([
        [b("➕ Add Category", "adm:addcat")],
        [b("📋 List / Edit / Delete Categories", "adm:listcats")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

def products_admin_kb() -> InlineKeyboardMarkup:
    return kb([
        [b("➕ Add Product", "adm:addprod")],
        [b("📋 List / Edit / Delete Products", "adm:listprods")],
        [b("⬅️ Admin Panel", "adm:home")],
    ])

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, photo_id: str = "") -> None:
    for admin_id in ADMIN_IDS:
        try:
            if photo_id:
                await context.bot.send_photo(admin_id, photo_id, caption=text[:1024], reply_markup=reply_markup)
            else:
                await context.bot.send_message(admin_id, text[:4000], reply_markup=reply_markup)
        except TelegramError:
            log.exception("Could not notify admin %s", admin_id)

async def show_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        execute(
            "INSERT INTO users(user_id,name,username) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET name=excluded.name,username=excluded.username",
            (user.id, user.full_name, user.username or ""),
        )
    text = get_setting("welcome", WELCOME_DEFAULT)
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=main_kb())
        except BadRequest:
            await update.effective_chat.send_message(text, reply_markup=main_kb())
    else:
        await update.effective_message.reply_text(text, reply_markup=main_kb())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await show_home(update, context)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    await update.effective_message.reply_text("⚙️ ELITE X CONFIG — Admin Panel", reply_markup=admin_kb())

async def send_qr_and_prompt(chat_id: int, context: ContextTypes.DEFAULT_TYPE, caption: str) -> None:
    qr_id = get_setting("payment_qr_file_id")
    instructions = get_setting("payment_instructions")
    if qr_id:
        await context.bot.send_photo(chat_id, qr_id, caption=(caption + "\n\n" + instructions)[:1024])
    else:
        await context.bot.send_message(chat_id, caption + "\n\n⚠️ Admin has not configured a QR image yet.\n" + instructions)
    await context.bot.send_message(chat_id, "📸 Payment karne ke baad screenshot isi chat mein bhejein. Request admin approval ke liye jayegi.")

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cats = query("SELECT id,name,emoji FROM categories WHERE visible=1 ORDER BY id")
    rows = [[b(f"{r['emoji']} {r['name']}", f"cat:{r['id']}")] for r in cats]
    rows.append([b("⬅️ Main Menu", "home")])
    text = "📂 Select a category:" if cats else "Abhi koi category available nahi hai."
    await update.callback_query.edit_message_text(text, reply_markup=kb(rows))

async def show_products(update: Update, category_id: int) -> None:
    cat = one("SELECT name FROM categories WHERE id=? AND visible=1", (category_id,))
    if not cat:
        await update.callback_query.edit_message_text("Category nahi mili.", reply_markup=main_kb())
        return
    products = query("SELECT id,name,description,price FROM products WHERE category_id=? AND visible=1 ORDER BY id", (category_id,))
    rows = []
    for p in products:
        stock = one("SELECT COUNT(*) AS n FROM key_stock WHERE product_id=? AND status='available'", (p["id"],))
        rows.append([b(f"🛒 {p['name']} — {money(p['price'])} | 🔑 {stock['n']}", f"prod:{p['id']}")])
    rows.append([b("⬅️ Categories", "shop")])
    await update.callback_query.edit_message_text(f"📂 {cat['name']}\nSelect a product:", reply_markup=kb(rows))

async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    p = one("""SELECT p.*, c.name AS category_name FROM products p
               JOIN categories c ON c.id=p.category_id WHERE p.id=? AND p.visible=1 AND c.visible=1""", (product_id,))
    if not p:
        await update.callback_query.edit_message_text("Product nahi mila.", reply_markup=main_kb())
        return
    stock = one("SELECT COUNT(*) AS n FROM key_stock WHERE product_id=? AND status='available'", (product_id,))
    text = f"📦 {p['name']}\n📂 Category: {p['category_name']}\n💰 Price: {money(p['price'])}\n🔑 Available keys: {stock['n']}\n\n{p['description']}"
    await update.callback_query.edit_message_text(text, reply_markup=kb([
        [b("💳 Buy with QR Payment", f"buy:{product_id}")],
        [b("💰 Buy with Wallet", f"walletbuy:{product_id}")],
        [b("⬅️ Back to Products", f"cat:{p['category_id']}")],
    ]))

async def begin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    context.user_data["awaiting_balance_amount"] = True
    amounts = [x.strip() for x in get_setting("balance_amounts", "100,200,500,1000").split(",") if x.strip()]
    rows = [[b(f"₹{a}", f"balamt:{a}")] for a in amounts if a.replace(".", "", 1).isdigit()]
    rows.append([b("✍️ Enter another amount", "balcustom")])
    rows.append([b("⬅️ Main Menu", "home")])
    await update.callback_query.edit_message_text(
        "💰 ADD BALANCE\n\nAmount select karein. Iske baad QR milega, phir screenshot bhejna hoga. Admin approve karega tabhi balance add hoga.",
        reply_markup=kb(rows))

async def create_balance_request(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float) -> None:
    user = update.effective_user
    if amount <= 0 or amount > 1000000:
        await update.effective_message.reply_text("Valid amount bhejein.")
        return
    context.user_data.clear()
    context.user_data["pending_balance_amount"] = amount
    await send_qr_and_prompt(update.effective_chat.id, context, f"💰 Balance top-up request\nAmount: {money(amount)}")
    context.user_data["awaiting_balance_proof"] = True

async def begin_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    p = one("SELECT * FROM products WHERE id=? AND visible=1", (product_id,))
    if not p:
        await update.callback_query.edit_message_text("Product nahi mila.")
        return
    stock = one("SELECT id FROM key_stock WHERE product_id=? AND status='available' ORDER BY id LIMIT 1", (product_id,))
    if not stock:
        await update.callback_query.edit_message_text("❌ Is product ka stock khatam hai.", reply_markup=main_kb())
        return
    context.user_data.clear()
    context.user_data["pending_order_product"] = product_id
    context.user_data["pending_order_price"] = float(p["price"])
    await send_qr_and_prompt(update.effective_chat.id, context, f"🛍️ Product purchase request\nProduct: {p['name']}\nAmount: {money(p['price'])}")
    context.user_data["awaiting_order_proof"] = True

async def wallet_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    user = update.effective_user
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        p = con.execute("SELECT * FROM products WHERE id=? AND visible=1", (product_id,)).fetchone()
        u = con.execute("SELECT balance FROM users WHERE user_id=?", (user.id,)).fetchone()
        key = con.execute("SELECT * FROM key_stock WHERE product_id=? AND status='available' ORDER BY id LIMIT 1", (product_id,)).fetchone()
        if not p or not u:
            con.rollback()
            await update.callback_query.edit_message_text("Product/user nahi mila.")
            return
        if not key:
            con.rollback()
            await update.callback_query.edit_message_text("❌ Key stock khatam hai.")
            return
        if float(u["balance"]) < float(p["price"]):
            con.rollback()
            await update.callback_query.edit_message_text(f"Wallet balance kam hai.\nBalance: {money(u['balance'])}", reply_markup=main_kb())
            return
        con.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (p["price"], user.id))
        con.execute("UPDATE key_stock SET status='sold',sold_to=?,sold_at=? WHERE id=? AND status='available'", (user.id, utc_now(), key["id"]))
        con.execute("INSERT INTO wallet_transactions(user_id,amount_delta,note) VALUES(?,?,?)", (user.id, -float(p["price"]), f"Purchase product #{product_id}"))
        con.execute("""INSERT INTO orders(user_id,username,product_id,product_name,price,payment_method,status,key_stock_id,delivered_key,reviewed_at)
                       VALUES(?,?,?,?,?,'wallet','approved',?,?,?)""",
                    (user.id, user.username or "", product_id, p["name"], p["price"], key["id"], key["key_text"], utc_now()))
        con.commit()
    await update.callback_query.edit_message_text(
        f"🎉 PURCHASE SUCCESSFUL!\n📦 Product: {p['name']}\n💰 Paid: {money(p['price'])}\n\n🔑 YOUR KEY:\n`{key['key_text']}`",
        parse_mode="Markdown", reply_markup=main_kb())

async def handle_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    photo = update.effective_message.photo
    if not photo:
        await update.effective_message.reply_text("Screenshot ko photo ke roop mein bhejein.")
        return
    file_id = photo[-1].file_id
    if context.user_data.get("awaiting_balance_proof"):
        amount = float(context.user_data.get("pending_balance_amount", 0))
        req_id = execute("INSERT INTO balance_requests(user_id,username,amount,proof_file_id) VALUES(?,?,?,?)",
                         (user.id, user.username or "", amount, file_id))
        context.user_data.clear()
        await update.effective_message.reply_text(f"✅ Screenshot mil gaya. Balance request #{req_id} admin approval ke liye bhej di gayi hai.")
        await notify_admins(context, f"💰 BALANCE REQUEST #{req_id}\nUser: {user.full_name} (@{user.username or 'no_username'})\nUser ID: {user.id}\nAmount: {money(amount)}\n\nScreenshot verify karke approve/reject karein.",
                            kb([[b("✅ Approve Balance", f"ba:{req_id}"), b("❌ Reject", f"bj:{req_id}")]]), photo_id=file_id)
        return
    if context.user_data.get("awaiting_order_proof"):
        product_id = int(context.user_data.get("pending_order_product", 0))
        p = one("SELECT * FROM products WHERE id=?", (product_id,))
        if not p:
            context.user_data.clear()
            await update.effective_message.reply_text("Product request expire ho gayi. Dobara try karein.")
            return
        order_id = execute("""INSERT INTO orders(user_id,username,product_id,product_name,price,payment_method,proof_file_id,status)
                              VALUES(?,?,?,?,?,'qr',?,'pending')""",
                           (user.id, user.username or "", product_id, p["name"], float(p["price"]), file_id))
        context.user_data.clear()
        await update.effective_message.reply_text(f"✅ Payment screenshot mil gaya. Order #{order_id} admin approval mein hai. Approval ke baad key milegi.")
        await notify_admins(context, f"🧾 PRODUCT PAYMENT #{order_id}\nUser: {user.full_name} (@{user.username or 'no_username'})\nUser ID: {user.id}\nProduct: {p['name']}\nAmount: {money(p['price'])}\n\nPayment verify karke approve/reject karein.",
                            kb([[b("✅ Approve & Deliver Key", f"oa:{order_id}"), b("❌ Reject", f"or:{order_id}")]]), photo_id=file_id)
        return
    await update.effective_message.reply_text("Pehle Add Balance ya product purchase shuru karein, phir payment screenshot bhejein.")

async def admin_approve_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, req_id: int, approve: bool) -> None:
    q = update.callback_query
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        req = con.execute("SELECT * FROM balance_requests WHERE id=?", (req_id,)).fetchone()
        if not req or req["status"] != "pending":
            con.rollback()
            await q.answer("Request already processed/not found.", show_alert=True)
            return
        status = "approved" if approve else "rejected"
        con.execute("UPDATE balance_requests SET status=?,reviewed_at=? WHERE id=?", (status, utc_now(), req_id))
        if approve:
            con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (req["amount"], req["user_id"]))
            con.execute("INSERT INTO wallet_transactions(user_id,amount_delta,note) VALUES(?,?,?)", (req["user_id"], req["amount"], f"Approved balance request #{req_id}"))
        con.commit()
    await q.answer("Done")
    try:
        await q.edit_message_caption(caption=f"💰 Balance request #{req_id} — {status.upper()}")
    except (BadRequest, AttributeError):
        try: await q.edit_message_text(f"💰 Balance request #{req_id} — {status.upper()}")
        except TelegramError: pass
    try:
        await context.bot.send_message(req["user_id"], f"{'✅ Approved' if approve else '❌ Rejected'}: Balance request #{req_id}.\n" + (f"Added: {money(req['amount'])}" if approve else "Balance add nahi hua."))
    except TelegramError:
        log.exception("Could not message user")

async def admin_approve_order(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int, approve: bool) -> None:
    q = update.callback_query
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order or order["status"] != "pending":
            con.rollback()
            await q.answer("Order already processed/not found.", show_alert=True)
            return
        if not approve:
            con.execute("UPDATE orders SET status='rejected',reviewed_at=? WHERE id=?", (utc_now(), order_id))
            con.commit()
            await q.answer("Payment rejected")
            try: await q.edit_message_caption(caption=f"❌ Order #{order_id} rejected.")
            except (BadRequest, AttributeError):
                try: await q.edit_message_text(f"❌ Order #{order_id} rejected.")
                except TelegramError: pass
            try: await context.bot.send_message(order["user_id"], f"❌ Payment for order #{order_id} was rejected. Please contact support if needed.")
            except TelegramError: pass
            return
        key = con.execute("SELECT * FROM key_stock WHERE product_id=? AND status='available' ORDER BY id LIMIT 1", (order["product_id"],)).fetchone()
        if not key:
            con.rollback()
            await q.answer("No key in stock. Add a key before approving.", show_alert=True)
            return
        con.execute("UPDATE key_stock SET status='sold',sold_to=?,sold_at=? WHERE id=? AND status='available'", (order["user_id"], utc_now(), key["id"]))
        con.execute("UPDATE orders SET status='approved',key_stock_id=?,delivered_key=?,reviewed_at=? WHERE id=?",
                    (key["id"], key["key_text"], utc_now(), order_id))
        con.commit()
    await q.answer("Approved; key delivered")
    try: await q.edit_message_caption(caption=f"✅ Order #{order_id} approved. Key delivered to user.")
    except (BadRequest, AttributeError):
        try: await q.edit_message_text(f"✅ Order #{order_id} approved. Key delivered to user.")
        except TelegramError: pass
    try:
        await context.bot.send_message(order["user_id"],
            f"🎉 PAYMENT APPROVED!\n📦 Product: {order['product_name']}\n💰 Paid: {money(order['price'])}\n🧾 Order ID: {order_id}\n\n🔑 YOUR PRODUCT KEY:\n{key['key_text']}\n\n⚡ Thank you for choosing ELITE X CONFIG!")
    except TelegramError:
        log.exception("Could not deliver key to user")

# ---------- CATEGORY MANAGEMENT ----------
async def admin_list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    cats = query("SELECT id,name,emoji,visible FROM categories ORDER BY id")
    if not cats:
        await q.edit_message_text("Koi category nahi hai. Pehle add karein.", reply_markup=categories_admin_kb())
        return
    rows = []
    for c in cats:
        status = "✅" if c["visible"] else "❌"
        rows.append([b(f"{status} {c['emoji']} {c['name']}", f"adm:catview:{c['id']}")])
    rows.append([b("⬅️ Categories Menu", "adm:cats")])
    await q.edit_message_text("📋 CATEGORIES (click to edit/delete):", reply_markup=kb(rows))

async def admin_view_category(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: int) -> None:
    q = update.callback_query
    c = one("SELECT * FROM categories WHERE id=?", (cat_id,))
    if not c:
        await q.edit_message_text("Category nahi mili.", reply_markup=categories_admin_kb())
        return
    prods = one("SELECT COUNT(*) n FROM products WHERE category_id=?", (cat_id,))["n"]
    text = f"📂 CATEGORY #{c['id']}\nEmoji: {c['emoji']}\nName: {c['name']}\nVisible: {'Yes' if c['visible'] else 'No'}\nProducts: {prods}"
    await q.edit_message_text(text, reply_markup=kb([
        [b("✏️ Edit Name", f"adm:cateditname:{cat_id}"), b("😀 Edit Emoji", f"adm:cateditemoji:{cat_id}")],
        [b("👁️ Toggle Visible", f"adm:cattoggle:{cat_id}")],
        [b("🗑️ Delete Category", f"adm:catdel:{cat_id}")],
        [b("⬅️ Categories", "adm:listcats")],
    ]))

async def admin_delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: int) -> None:
    q = update.callback_query
    prods = one("SELECT COUNT(*) n FROM products WHERE category_id=?", (cat_id,))["n"]
    if prods:
        await q.answer(f"Pehle is category ke {prods} products delete karein.", show_alert=True)
        return
    execute("DELETE FROM categories WHERE id=?", (cat_id,))
    await q.answer("Category deleted")
    await admin_list_categories(update, context)

# ---------- PRODUCT MANAGEMENT ----------
async def admin_list_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    prods = query("""SELECT p.id,p.name,p.price,p.visible,c.name AS cat FROM products p
                     JOIN categories c ON c.id=p.category_id ORDER BY p.id""")
    if not prods:
        await q.edit_message_text("Koi product nahi hai. Pehle add karein.", reply_markup=products_admin_kb())
        return
    rows = []
    for p in prods:
        status = "✅" if p["visible"] else "❌"
        rows.append([b(f"{status} #{p['id']} {p['name']} — {money(p['price'])} ({p['cat']})", f"adm:prodview:{p['id']}")])
    rows.append([b("⬅️ Products Menu", "adm:prods")])
    await q.edit_message_text("📋 PRODUCTS (click to edit/delete):", reply_markup=kb(rows))

async def admin_view_product(update: Update, context: ContextTypes.DEFAULT_TYPE, prod_id: int) -> None:
    q = update.callback_query
    p = one("""SELECT p.*,c.name AS cat FROM products p JOIN categories c ON c.id=p.category_id WHERE p.id=?""", (prod_id,))
    if not p:
        await q.edit_message_text("Product nahi mila.", reply_markup=products_admin_kb())
        return
    stock = one("SELECT COUNT(*) n FROM key_stock WHERE product_id=? AND status='available'", (prod_id,))["n"]
    text = (f"📦 PRODUCT #{p['id']}\nName: {p['name']}\nCategory: {p['cat']}\nPrice: {money(p['price'])}\n"
            f"Visible: {'Yes' if p['visible'] else 'No'}\nAvailable keys: {stock}\nDescription: {p['description'] or '(empty)'}")
    await q.edit_message_text(text, reply_markup=kb([
        [b("✏️ Edit Name", f"adm:prodeditname:{prod_id}"), b("💰 Edit Price", f"adm:prodeditprice:{prod_id}")],
        [b("📝 Edit Description", f"adm:prodeditdesc:{prod_id}")],
        [b("📂 Change Category", f"adm:prodmovecat:{prod_id}")],
        [b("👁️ Toggle Visible", f"adm:prodtoggle:{prod_id}")],
        [b("🗑️ Delete Product", f"adm:proddelete:{prod_id}")],
        [b("⬅️ Products", "adm:listprods")],
    ]))

async def admin_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE, prod_id: int) -> None:
    q = update.callback_query
    with closing(db()) as con:
        con.execute("DELETE FROM key_stock WHERE product_id=?", (prod_id,))
        con.execute("DELETE FROM products WHERE id=?", (prod_id,))
        con.commit()
    await q.answer("Product deleted")
    await admin_list_products(update, context)

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    data = q.data or ""
    if data.startswith(("adm:", "ba:", "bj:", "oa:", "or:")) and not is_admin(update):
        await q.answer("Admin only.", show_alert=True)
        return
    await q.answer()
    if data == "home":
        await show_home(update, context)
    elif data == "shop":
        await show_categories(update, context)
    elif data == "profile":
        u = one("SELECT * FROM users WHERE user_id=?", (update.effective_user.id,))
        await q.edit_message_text(f"👤 My Profile\nID: {update.effective_user.id}\nName: {update.effective_user.full_name}\n💰 Balance: {money(u['balance'] if u else 0)}", reply_markup=kb([[b("🏠 Main Menu", "home")]]))
    elif data == "addbalance":
        await begin_balance(update, context)
    elif data.startswith("balamt:"):
        try: await create_balance_request(update, context, float(data.split(":", 1)[1]))
        except ValueError: await q.edit_message_text("Invalid amount.")
    elif data == "balcustom":
        context.user_data.clear()
        context.user_data["awaiting_custom_balance_amount"] = True
        await q.edit_message_text("Kitna balance add karna hai? Amount number mein bhejein (₹).")
    elif data == "myorders":
        orders = query("SELECT id,product_name,price,status,created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (update.effective_user.id,))
        text = "📦 MY ORDERS\n\n" + ("\n".join(f"#{r['id']} • {r['product_name']} • {money(r['price'])} • {r['status']}" for r in orders) if orders else "Abhi koi order nahi hai.")
        await q.edit_message_text(text, reply_markup=kb([[b("🏠 Main Menu", "home")]]))
    elif data == "support":
        await q.edit_message_text(f"🎧 Support: {get_setting('support_url', 'https://t.me/elitexconfig')}", reply_markup=kb([[b("🏠 Main Menu", "home")]]))
    elif data.startswith("cat:"):
        await show_products(update, int(data.split(":")[1]))
    elif data.startswith("prod:"):
        await show_product(update, context, int(data.split(":")[1]))
    elif data.startswith("buy:"):
        await begin_buy(update, context, int(data.split(":")[1]))
    elif data.startswith("walletbuy:"):
        await wallet_buy(update, context, int(data.split(":")[1]))
    elif data == "adm:home":
        await q.edit_message_text("⚙️ Admin Panel", reply_markup=admin_kb())
    elif data == "adm:dash":
        users = one("SELECT COUNT(*) n FROM users")["n"]
        cats = one("SELECT COUNT(*) n FROM categories")["n"]
        prods = one("SELECT COUNT(*) n FROM products")["n"]
        pending_o = one("SELECT COUNT(*) n FROM orders WHERE status='pending'")["n"]
        pending_b = one("SELECT COUNT(*) n FROM balance_requests WHERE status='pending'")["n"]
        keys = one("SELECT COUNT(*) n FROM key_stock WHERE status='available'")["n"]
        await q.edit_message_text(f"📊 DASHBOARD\nUsers: {users}\nCategories: {cats}\nProducts: {prods}\nAvailable keys: {keys}\nPending product payments: {pending_o}\nPending balance requests: {pending_b}", reply_markup=admin_kb())
    elif data == "adm:cats":
        await q.edit_message_text("📂 CATEGORY MANAGEMENT", reply_markup=categories_admin_kb())
    elif data == "adm:prods":
        await q.edit_message_text("📦 PRODUCT MANAGEMENT", reply_markup=products_admin_kb())
    elif data == "adm:addcat":
        context.user_data.clear(); context.user_data["admin_state"] = "addcat_name"
        await q.edit_message_text("Category ka naam bhejein.")
    elif data == "adm:listcats":
        await admin_list_categories(update, context)
    elif data.startswith("adm:catview:"):
        await admin_view_category(update, context, int(data.rsplit(":", 1)[1]))
    elif data.startswith("adm:cateditname:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_cat_name"
        context.user_data["admin_edit_cat_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("Naya category name bhejein.")
    elif data.startswith("adm:cateditemoji:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_cat_emoji"
        context.user_data["admin_edit_cat_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("Naya emoji bhejein (single emoji).")
    elif data.startswith("adm:cattoggle:"):
        cat_id = int(data.rsplit(":", 1)[1])
        c = one("SELECT visible FROM categories WHERE id=?", (cat_id,))
        if c:
            execute("UPDATE categories SET visible=? WHERE id=?", (0 if c["visible"] else 1, cat_id))
        await admin_view_category(update, context, cat_id)
    elif data.startswith("adm:catdel:"):
        await admin_delete_category(update, context, int(data.rsplit(":", 1)[1]))
    elif data == "adm:addprod":
        cats = query("SELECT id,name FROM categories ORDER BY id")
        if not cats:
            await q.edit_message_text("Pehle category add karein.", reply_markup=products_admin_kb()); return
        await q.edit_message_text("Product kis category mein add karna hai?", reply_markup=kb([[b(c["name"], f"adm:prodcat:{c['id']}")] for c in cats] + [[b("⬅️ Products Menu", "adm:prods")]]))
    elif data.startswith("adm:prodcat:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "addprod_name"
        context.user_data["admin_category_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("Product name bhejein.")
    elif data == "adm:listprods":
        await admin_list_products(update, context)
    elif data.startswith("adm:prodview:"):
        await admin_view_product(update, context, int(data.rsplit(":", 1)[1]))
    elif data.startswith("adm:prodeditname:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_prod_name"
        context.user_data["admin_edit_prod_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("Naya product name bhejein.")
    elif data.startswith("adm:prodeditprice:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_prod_price"
        context.user_data["admin_edit_prod_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("Nayi price ₹ mein bhejein (number).")
    elif data.startswith("adm:prodeditdesc:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "edit_prod_desc"
        context.user_data["admin_edit_prod_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("Naya description bhejein (ya '-' bhejein clear karne ke liye).")
    elif data.startswith("adm:prodmovecat:"):
        prod_id = int(data.rsplit(":", 1)[1])
        cats = query("SELECT id,name FROM categories ORDER BY id")
        await q.edit_message_text("Nayi category select karein:", reply_markup=kb([[b(c["name"], f"adm:prodsetcat:{prod_id}:{c['id']}")] for c in cats] + [[b("⬅️ Back", f"adm:prodview:{prod_id}")]]))
    elif data.startswith("adm:prodsetcat:"):
        parts = data.split(":")
        prod_id, cat_id = int(parts[2]), int(parts[3])
        execute("UPDATE products SET category_id=? WHERE id=?", (cat_id, prod_id))
        await admin_view_product(update, context, prod_id)
    elif data.startswith("adm:prodtoggle:"):
        prod_id = int(data.rsplit(":", 1)[1])
        p = one("SELECT visible FROM products WHERE id=?", (prod_id,))
        if p:
            execute("UPDATE products SET visible=? WHERE id=?", (0 if p["visible"] else 1, prod_id))
        await admin_view_product(update, context, prod_id)
    elif data.startswith("adm:proddelete:"):
        await admin_delete_product(update, context, int(data.rsplit(":", 1)[1]))
    elif data == "adm:addkey":
        prods = query("SELECT id,name FROM products ORDER BY id")
        if not prods:
            await q.edit_message_text("Pehle product add karein.", reply_markup=admin_kb()); return
        await q.edit_message_text("Kis product ke liye key add karni hai?", reply_markup=kb([[b(p["name"], f"adm:keyprod:{p['id']}")] for p in prods] + [[b("⬅️ Admin Panel", "adm:home")]]))
    elif data.startswith("adm:keyprod:"):
        context.user_data.clear()
        context.user_data["admin_state"] = "addkey_text"
        context.user_data["admin_product_id"] = int(data.rsplit(":", 1)[1])
        await q.edit_message_text("Ab key paste karein. Har message mein ek key add hogi.")
    elif data == "adm:stock":
        rows = query("""SELECT p.id,p.name,
             SUM(CASE WHEN k.status='available' THEN 1 ELSE 0 END) AS available,
             SUM(CASE WHEN k.status='sold' THEN 1 ELSE 0 END) AS sold
             FROM products p LEFT JOIN key_stock k ON k.product_id=p.id GROUP BY p.id ORDER BY p.id""")
        text = "🔑 KEY STOCK\n\n" + ("\n".join(f"#{r['id']} {r['name']}: available {r['available'] or 0}, sold {r['sold'] or 0}" for r in rows) if rows else "No products.")
        await q.edit_message_text(text, reply_markup=admin_kb())
    elif data == "adm:orders":
        rows = query("SELECT id,user_id,product_name,price,status FROM orders ORDER BY id DESC LIMIT 15")
        text = "🧾 RECENT PRODUCT ORDERS\n\n" + ("\n".join(f"#{r['id']} user {r['user_id']} • {r['product_name']} • {money(r['price'])} • {r['status']}" for r in rows) if rows else "No orders.")
        await q.edit_message_text(text, reply_markup=admin_kb())
    elif data == "adm:balances":
        rows = query("SELECT id,user_id,amount,status FROM balance_requests ORDER BY id DESC LIMIT 15")
        text = "💰 BALANCE REQUESTS\n\n" + ("\n".join(f"#{r['id']} user {r['user_id']} • {money(r['amount'])} • {r['status']}" for r in rows) if rows else "No requests.")
        await q.edit_message_text(text, reply_markup=admin_kb())
    elif data == "adm:setqr":
        context.user_data.clear(); context.user_data["admin_state"] = "set_qr"
        await q.edit_message_text("Payment QR ki image/photo bhejein. Ye existing QR ko replace karegi.")
    elif data == "adm:instructions":
        context.user_data.clear(); context.user_data["admin_state"] = "set_instructions"
        await q.edit_message_text("Payment instructions ka text bhejein.")
    elif data == "adm:welcome":
        context.user_data.clear(); context.user_data["admin_state"] = "set_welcome"
        current = get_setting("welcome", WELCOME_DEFAULT)
        await q.edit_message_text(f"✏️ WELCOME MESSAGE EDIT\n\nCurrent:\n{current[:500]}\n\nNaya welcome message bhejein (HTML/plain text). Ye turant apply ho jayega.")
    elif data.startswith("ba:"):
        await admin_approve_balance(update, context, int(data.split(":")[1]), True)
    elif data.startswith("bj:"):
        await admin_approve_balance(update, context, int(data.split(":")[1]), False)
    elif data.startswith("oa:"):
        await admin_approve_order(update, context, int(data.split(":")[1]), True)
    elif data.startswith("or:"):
        await admin_approve_order(update, context, int(data.split(":")[1]), False)

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (update.effective_message.text or "").strip() if update.effective_message else ""
    state = context.user_data.get("admin_state")
    if state and is_admin(update):
        if state == "set_qr" and update.effective_message.photo:
            set_setting("payment_qr_file_id", update.effective_message.photo[-1].file_id)
            context.user_data.clear()
            await update.effective_message.reply_text("✅ Payment QR saved.", reply_markup=admin_kb())
            return
        if state == "set_instructions" and text:
            set_setting("payment_instructions", text)
            context.user_data.clear()
            await update.effective_message.reply_text("✅ Payment instructions saved.", reply_markup=admin_kb())
            return
        if state == "set_welcome" and text:
            set_setting("welcome", text)
            context.user_data.clear()
            await update.effective_message.reply_text("✅ Welcome message updated.", reply_markup=admin_kb())
            return
        if state == "addcat_name" and text:
            execute("INSERT INTO categories(name) VALUES(?)", (text[:100],))
            context.user_data.clear()
            await update.effective_message.reply_text("✅ Category added.", reply_markup=categories_admin_kb())
            return
        if state == "edit_cat_name" and text:
            cat_id = int(context.user_data.get("admin_edit_cat_id", 0))
            execute("UPDATE categories SET name=? WHERE id=?", (text[:100], cat_id))
            context.user_data.clear()
            await update.effective_message.reply_text("✅ Category name updated.", reply_markup=categories_admin_kb())
            return
        if state == "edit_cat_emoji" and text:
            cat_id = int(context.user_data.get("admin_edit_cat_id", 0))
            execute("UPDATE categories SET emoji=? WHERE id=?", (text[:10], cat_id))
            context.user_data.clear()
            await update.effective_message.reply_text("✅ Category emoji updated.", reply_markup=categories_admin_kb())
            return
        if state == "addprod_name" and text:
            context.user_data["new_product_name"] = text[:100]
            context.user_data["admin_state"] = "addprod_price"
            await update.effective_message.reply_text("Product ki price ₹ mein bhejein (number).")
            return
        if state == "addprod_price" and text:
            try: price = float(text.replace(",", ""))
            except ValueError:
                await update.effective_message.reply_text("Price number mein bhejein, jaise 199.")
                return
            if price < 0 or price > 10000000:
                await update.effective_message.reply_text("Valid price bhejein.")
                return
            name = context.user_data.get("new_product_name", "Product")
            cat_id = int(context.user_data.get("admin_category_id", 0))
            execute("INSERT INTO products(category_id,name,price) VALUES(?,?,?)", (cat_id, name, price))
            context.user_data.clear()
            await update.effective_message.reply_text(f"✅ Product added: {name} — {money(price)}", reply_markup=products_admin_kb())
            return
        if state == "edit_prod_name" and text:
            prod_id = int(context.user_data.get("admin_edit_prod_id", 0))
            execute("UPDATE products SET name=? WHERE id=?", (text[:100], prod_id))
            context.user_data.clear()
            await update.effective_message.reply_text("✅ Product name updated.", reply_markup=products_admin_kb())
            return
        if state == "edit_prod_price" and text:
            try: price = float(text.replace(",", "").replace("₹", "").strip())
            except ValueError:
                await update.effective_message.reply_text("Price number mein bhejein, jaise 199.")
                return
            prod_id = int(context.user_data.get("admin_edit_prod_id", 0))
            execute("UPDATE products SET price=? WHERE id=?", (price, prod_id))
            context.user_data.clear()
            await update.effective_message.reply_text(f"✅ Product price updated: {money(price)}", reply_markup=products_admin_kb())
            return
        if state == "edit_prod_desc" and text:
            prod_id = int(context.user_data.get("admin_edit_prod_id", 0))
            desc = "" if text == "-" else text
            execute("UPDATE products SET description=? WHERE id=?", (desc[:1000], prod_id))
            context.user_data.clear()
            await update.effective_message.reply_text("✅ Product description updated.", reply_markup=products_admin_kb())
            return
        if state == "addkey_text" and text:
            product_id = int(context.user_data.get("admin_product_id", 0))
            execute("INSERT INTO key_stock(product_id,key_text) VALUES(?,?)", (product_id, text))
            context.user_data.clear()
            await update.effective_message.reply_text("✅ Key stock mein add ho gayi.", reply_markup=admin_kb())
            return
    if context.user_data.get("awaiting_custom_balance_amount") and text:
        try: amount = float(text.replace(",", "").replace("₹", "").strip())
        except ValueError:
            await update.effective_message.reply_text("Amount number mein bhejein, jaise 500.")
            return
        await create_balance_request(update, context, amount)
        return
    if update.effective_message and update.effective_message.photo:
        await handle_proof(update, context)
        return
    if text == "/cancel":
        context.user_data.clear()
        await update.effective_message.reply_text("Cancelled.", reply_markup=main_kb())
    elif text:
        await update.effective_message.reply_text("Menu use karein ya /start bhejein.", reply_markup=main_kb())

def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("ERROR: BOT_TOKEN environment variable is required.")
    if not ADMIN_IDS:
        raise SystemExit("ERROR: ADMIN_IDS environment variable is required (comma-separated Telegram user IDs).")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.TEXT, on_message))
    log.info("ELITE X CONFIG bot starting; database=%s", DB_PATH)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()