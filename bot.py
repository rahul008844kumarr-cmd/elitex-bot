#!/usr/bin/env python3
"""ELITE X CONFIG Telegram Store Bot.

Python: 3.10+
Library: python-telegram-bot 21.x / 22.x

Configure BOT_TOKEN and ADMIN_IDS as environment variables. Never put a live bot
 token, payment password, OTP, or PIN into this source file or send it to anyone.

Payment note: QR / UPI payments are reviewed by an admin after the user submits
proof. A QR image alone cannot verify payment automatically; automatic crediting
requires an authenticated payment-provider API/webhook integration.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

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
    "🛍️ Browse products and plans.\n"
    "💰 Add balance to your wallet.\n"
    "👤 Check your profile and orders.\n"
    "🎧 Need help? Open Support.\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Choose an option below to continue."
)
DEFAULT_MENU_BUTTONS = [
    ("🛍️ Shop Now", "shop", ""),
    ("👤 My Profile", "profile", ""),
    ("💰 Add Balance", "addbalance", ""),
    ("🎧 Support", "support", ""),
    ("📦 My Orders", "myorders", ""),
]
KNOWN_ACTIONS = {"shop", "profile", "addbalance", "support", "myorders", "howto", "channel", "url"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    return con


def table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_column(con: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    if column not in table_columns(con, table):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def init_db() -> None:
    Path(DB_PATH).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    with closing(db()) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            username TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'User',
            account_status TEXT NOT NULL DEFAULT 'Active',
            balance REAL NOT NULL DEFAULT 0,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_active_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            referrals INTEGER NOT NULL DEFAULT 0,
            referred_by INTEGER
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subtitle TEXT NOT NULL DEFAULT '',
            emoji TEXT NOT NULL DEFAULT '📂',
            visible INTEGER NOT NULL DEFAULT 1,
            position INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            emoji TEXT NOT NULL DEFAULT '🛒',
            visible INTEGER NOT NULL DEFAULT 1,
            position INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT -1,
            visible INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            plan_id INTEGER NOT NULL DEFAULT 0,
            product_name TEXT NOT NULL,
            plan_name TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'awaiting_payment',
            proof_file_id TEXT NOT NULL DEFAULT '',
            proof_reference TEXT NOT NULL DEFAULT '',
            payment_method TEXT NOT NULL DEFAULT 'qr',
            delivery_text TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS balance_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            amount REAL NOT NULL,
            method TEXT NOT NULL DEFAULT 'qr',
            reference TEXT NOT NULL DEFAULT '',
            proof_file_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount_delta REAL NOT NULL,
            transaction_type TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            related_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS menu_buttons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            action TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            visible INTEGER NOT NULL DEFAULT 1,
            position INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS support_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            url TEXT NOT NULL,
            visible INTEGER NOT NULL DEFAULT 1,
            position INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL DEFAULT 'Admin',
            added_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, id DESC);
        CREATE INDEX IF NOT EXISTS idx_balance_requests_user ON balance_requests(user_id, id DESC);
        CREATE INDEX IF NOT EXISTS idx_wallet_user ON wallet_transactions(user_id, id DESC);
        """)
        # Migrate older databases produced by earlier ELITE X CONFIG versions.
        migrations = {
            "users": {
                "role": "TEXT NOT NULL DEFAULT 'User'",
                "account_status": "TEXT NOT NULL DEFAULT 'Active'",
                "last_active_at": "TEXT NOT NULL DEFAULT ''",
                "referred_by": "INTEGER",
            },
            "categories": {
                "subtitle": "TEXT NOT NULL DEFAULT ''",
                "emoji": "TEXT NOT NULL DEFAULT '📂'",
                "visible": "INTEGER NOT NULL DEFAULT 1",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "products": {
                "description": "TEXT NOT NULL DEFAULT ''",
                "emoji": "TEXT NOT NULL DEFAULT '🛒'",
                "visible": "INTEGER NOT NULL DEFAULT 1",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "plans": {
                "stock": "INTEGER NOT NULL DEFAULT -1",
                "visible": "INTEGER NOT NULL DEFAULT 1",
            },
            "orders": {
                "username": "TEXT NOT NULL DEFAULT ''",
                "proof_file_id": "TEXT NOT NULL DEFAULT ''",
                "proof_reference": "TEXT NOT NULL DEFAULT ''",
                "payment_method": "TEXT NOT NULL DEFAULT 'qr'",
                "delivery_text": "TEXT NOT NULL DEFAULT ''",
                "reviewed_at": "TEXT NOT NULL DEFAULT ''",
            },
        }
        for table, fields in migrations.items():
            for col, decl in fields.items():
                ensure_column(con, table, col, decl)
        con.execute("UPDATE users SET last_active_at=? WHERE last_active_at IS NULL OR last_active_at=''", (utc_now(),))
        defaults = {
            "welcome": WELCOME_DEFAULT,
            "support_username": "@elitexconfig",
            "support_url": "https://t.me/elitexconfig",
            "channel_url": "",
            "tutorial_text": "Tutorial details will be added soon. Contact support if you need help.",
            "tutorial_url": "",
            "payment_instructions": "Add your UPI ID and payment steps in Admin Panel → Store Settings.",
            "upi_id": "",
            "balance_amounts": "100,200,500,1000,2000",
            "referral_reward": "0",
            "welcome_media_disabled": "0",
            "welcome_logo_file_id": "",
            "welcome_animation_file_id": "",
            "payment_qr_file_id": "",
        }
        con.executemany("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", defaults.items())
        con.execute("INSERT OR IGNORE INTO users(user_id,name,username) VALUES(0,'System','')")
        # Seed the four requested starting categories only on a new/empty store.
        cat_count = con.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"]
        if cat_count == 0:
            for pos, (name, emoji) in enumerate([
                ("Android Non-Root", "📱"), ("Android Root", "🔓"),
                ("iOS / iPhone", "🍎"), ("PC", "💻")
            ], 1):
                con.execute("INSERT INTO categories(name,emoji,position) VALUES(?,?,?)", (name, emoji, pos))
        menu_count = con.execute("SELECT COUNT(*) AS n FROM menu_buttons").fetchone()["n"]
        if menu_count == 0:
            for pos, (label, action, url) in enumerate(DEFAULT_MENU_BUTTONS, 1):
                con.execute("INSERT INTO menu_buttons(label,action,url,position) VALUES(?,?,?,?)", (label, action, url, pos))
        con.commit()


def query(sql: str, args: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with closing(db()) as con:
        return con.execute(sql, args).fetchall()


def one(sql: str, args: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    found = query(sql, args)
    return found[0] if found else None


def execute(sql: str, args: tuple[Any, ...] = ()) -> int:
    with closing(db()) as con:
        cur = con.execute(sql, args)
        con.commit()
        return int(cur.lastrowid or 0)


def get_setting(key: str, default: str = "") -> str:
    row = one("SELECT value FROM settings WHERE key=?", (key,))
    return str(row["value"]) if row else default


def set_setting(key: str, value: str) -> None:
    execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def money(value: float | int) -> str:
    return f"₹{float(value):,.2f}"


def valid_url(value: str, allow_blank: bool = False) -> bool:
    value = value.strip()
    return (allow_blank and not value) or value.startswith(("https://", "http://", "tg://"))


def is_owner(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)


def is_admin(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    if user.id in ADMIN_IDS:
        return True
    return bool(one("SELECT user_id FROM admins WHERE user_id=?", (user.id,)))


def button(label: str, data: str | None = None, url: str | None = None) -> InlineKeyboardButton:
    if url:
        return InlineKeyboardButton(label[:60], url=url)
    return InlineKeyboardButton(label[:60], callback_data=(data or "home")[:64])


def markup(rows_: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(rows_)


def pair_rows(buttons: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


def main_menu() -> InlineKeyboardMarkup:
    items = query("SELECT id,label,action,url FROM menu_buttons WHERE visible=1 ORDER BY position,id")
    buttons: list[InlineKeyboardButton] = []
    for item in items:
        action = str(item["action"])
        url = str(item["url"] or "")
        if action == "url" or url:
            if valid_url(url):
                buttons.append(button(item["label"], url=url))
        elif action in KNOWN_ACTIONS:
            buttons.append(button(item["label"], data=f"go:{action}"))
    return markup(pair_rows(buttons))


def admin_menu() -> InlineKeyboardMarkup:
    items = [
        [button("📊 Dashboard", "adm:dash")],
        [button("📂 Categories", "adm:categories"), button("📦 Products / Plans", "adm:products")],
        [button("🧾 Orders / Payments", "adm:orders"), button("💳 Balance Requests", "adm:balances")],
        [button("👥 Users", "adm:users"), button("🧩 Main Menu Buttons", "adm:menubtns")],
        [button("⚙️ Store Settings", "adm:settings"), button("🎧 Support Links", "adm:supportlinks")],
        [button("🖼️ Payment QR", "adm:qr"), button("🛡️ Admin Accounts", "adm:admins")],
        [button("🏠 User Main Menu", "home")],
    ]
    return markup(items)


def categories_menu() -> InlineKeyboardMarkup:
    return markup([
        [button("➕ Add Category", "ca:add")],
        [button("✏️ Edit Category", "ca:edit"), button("🗑️ Delete Category", "ca:delete")],
        [button("👁️ Show / Hide", "ca:toggle"), button("📋 List Categories", "ca:list")],
        [button("⬅️ Admin Panel", "adm:home")],
    ])


def products_menu() -> InlineKeyboardMarkup:
    return markup([
        [button("➕ Add Product + Plan", "pr:add")],
        [button("➕ Add Plan", "pl:add")],
        [button("✏️ Edit Product", "pr:edit"), button("🗑️ Delete Product", "pr:delete")],
        [button("✏️ Edit Plan", "pl:edit"), button("🗑️ Delete Plan", "pl:delete")],
        [button("👁️ Product Show / Hide", "pr:toggle"), button("📋 List Products", "pr:list")],
        [button("⬅️ Admin Panel", "adm:home")],
    ])


def settings_menu() -> InlineKeyboardMarkup:
    return markup([
        [button("✏️ Welcome Text", "cfg:welcome"), button("💳 Payment Instructions", "cfg:payment")],
        [button("🆔 UPI ID", "cfg:upi"), button("💰 Balance Amount Buttons", "cfg:amounts")],
        [button("🎧 Support Username", "cfg:support_user"), button("🔗 Support URL", "cfg:support_url")],
        [button("📢 Channel URL", "cfg:channel"), button("📖 Tutorial Text", "cfg:tutorial_text")],
        [button("🔗 Tutorial URL", "cfg:tutorial_url"), button("👥 Referral Reward", "cfg:reward")],
        [button("🖼️ Welcome Image / GIF", "cfg:welcome_media"), button("🧹 Remove Welcome Media", "cfg:welcome_clear")],
        [button("⬅️ Admin Panel", "adm:home")],
    ])


def menu_buttons_menu() -> InlineKeyboardMarkup:
    return markup([
        [button("📋 List Buttons", "mb:list")],
        [button("➕ Add Button", "mb:add"), button("✏️ Edit Button", "mb:edit")],
        [button("🗑️ Delete Button", "mb:delete"), button("👁️ Show / Hide", "mb:toggle")],
        [button("⬅️ Admin Panel", "adm:home")],
    ])


def support_links_menu() -> InlineKeyboardMarkup:
    return markup([
        [button("📋 List Support Links", "sl:list")],
        [button("➕ Add Link", "sl:add"), button("✏️ Edit Link", "sl:edit")],
        [button("🗑️ Delete Link", "sl:delete"), button("👁️ Show / Hide", "sl:toggle")],
        [button("⬅️ Admin Panel", "adm:home")],
    ])


def order_review_markup(order_id: int) -> InlineKeyboardMarkup:
    return markup([[button("✅ Approve Payment", f"oa:{order_id}"), button("❌ Reject Payment", f"or:{order_id}")]])


def balance_review_markup(request_id: int) -> InlineKeyboardMarkup:
    return markup([[button("✅ Approve Balance", f"ba:{request_id}"), button("❌ Reject Request", f"bj:{request_id}")]])


async def safe_edit(query_obj, text: str, reply_markup=None) -> None:
    try:
        await query_obj.edit_message_text(text[:4000], reply_markup=reply_markup)
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return
        try:
            await query_obj.message.reply_text(text[:4000], reply_markup=reply_markup)
        except TelegramError:
            log.exception("Could not edit or reply to callback message")


async def maybe_update_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = get_setting("welcome", WELCOME_DEFAULT)
    animation_id = get_setting("welcome_animation_file_id")
    logo_id = get_setting("welcome_logo_file_id")
    media_disabled = get_setting("welcome_media_disabled", "0") == "1"
    try:
        if not media_disabled and animation_id:
            await context.bot.send_animation(chat_id, animation_id, caption=text[:1024], reply_markup=main_menu())
        elif not media_disabled and logo_id:
            await context.bot.send_photo(chat_id, logo_id, caption=text[:1024], reply_markup=main_menu())
        elif not media_disabled and Path(LOGO_PATH).exists():
            with open(LOGO_PATH, "rb") as photo:
                await context.bot.send_photo(chat_id, photo, caption=text[:1024], reply_markup=main_menu())
        else:
            await context.bot.send_message(chat_id, text[:4000], reply_markup=main_menu())
    except TelegramError:
        log.exception("Welcome media failed; sending text fallback")
        await context.bot.send_message(chat_id, text[:4000], reply_markup=main_menu())


def ensure_user(tg_user, referrer_id: int | None = None) -> tuple[bool, bool]:
    """Return (new_user, blocked); referral bonus is credited once if configured."""
    now = utc_now()
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        old = con.execute("SELECT user_id,account_status,referred_by FROM users WHERE user_id=?", (tg_user.id,)).fetchone()
        if old:
            con.execute("UPDATE users SET name=?,username=?,last_active_at=? WHERE user_id=?",
                         (tg_user.full_name, tg_user.username or "", now, tg_user.id))
            con.commit()
            return False, old["account_status"] == "Blocked"
        valid_referrer = None
        if referrer_id and referrer_id != tg_user.id:
            ref = con.execute("SELECT user_id FROM users WHERE user_id=? AND account_status='Active'", (referrer_id,)).fetchone()
            if ref:
                valid_referrer = referrer_id
        con.execute("INSERT INTO users(user_id,name,username,joined_at,last_active_at,referred_by) VALUES(?,?,?,?,?,?)",
                    (tg_user.id, tg_user.full_name, tg_user.username or "", now, now, valid_referrer))
        con.commit()
    if valid_referrer:
        reward = 0.0
        try:
            reward = max(0.0, float(get_setting("referral_reward", "0")))
        except ValueError:
            reward = 0.0
        with closing(db()) as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE users SET referrals=referrals+1 WHERE user_id=?", (valid_referrer,))
            if reward > 0:
                con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (reward, valid_referrer))
                con.execute("INSERT INTO wallet_transactions(user_id,amount_delta,transaction_type,note,created_at) VALUES(?,?,?,?,?)",
                            (valid_referrer, reward, "referral_reward", f"Referral reward for user {tg_user.id}", now))
            con.commit()
    return True, False


def has_user_access(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    row = one("SELECT account_status FROM users WHERE user_id=?", (user.id,))
    return not row or row["account_status"] != "Blocked"


async def deny_admin(update: Update) -> None:
    if update.callback_query:
        await update.callback_query.answer("Admin access only.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("⛔ Admin access only.")


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None,
                        photo_id: str = "", document_id: str = "") -> None:
    ids = set(ADMIN_IDS)
    ids.update(int(r["user_id"]) for r in query("SELECT user_id FROM admins"))
    for admin_id in ids:
        try:
            if photo_id:
                await context.bot.send_photo(admin_id, photo_id, caption=text[:1024], reply_markup=reply_markup)
            elif document_id:
                await context.bot.send_document(admin_id, document_id, caption=text[:1024], reply_markup=reply_markup)
            else:
                await context.bot.send_message(admin_id, text[:4000], reply_markup=reply_markup)
        except TelegramError:
            log.warning("Unable to notify admin %s", admin_id, exc_info=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    ref_id = None
    if context.args:
        token = context.args[0]
        if token.startswith("ref_") and token[4:].isdigit():
            ref_id = int(token[4:])
    is_new, blocked = ensure_user(user, ref_id)
    if blocked:
        return await update.effective_message.reply_text("⛔ Your account is currently restricted. Please contact Support.")
    if is_new and ref_id and ref_id != user.id:
        reward = 0.0
        try:
            reward = max(0.0, float(get_setting("referral_reward", "0")))
        except ValueError:
            pass
        try:
            note = f"A new user joined with your referral link. Reward: {money(reward)}." if reward else "A new user joined with your referral link."
            await context.bot.send_message(ref_id, f"👥 Referral update\n{note}")
        except TelegramError:
            pass
    await maybe_update_home(update, context)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny_admin(update)
    msg = update.effective_message
    await msg.reply_text("👑 ELITE X CONFIG · ADMIN CONTROL CENTER\nManage every category, product, plan, payment, user and public link below.", reply_markup=admin_menu())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Use /start to open the store.\n"
        "Support: " + get_setting("support_username", "@elitexconfig") + "\n"
        "Admin panel: /admin\n"
        "Deliver approved order: /deliver ORDER_ID delivery-text\n"
        "Admin wallet adjustment: /addbal USER_ID AMOUNT or /removebal USER_ID AMOUNT\n"
        "Cancel an input flow: /cancel"
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("flow", None)
    context.user_data.pop("awaiting_order_proof", None)
    context.user_data.pop("awaiting_balance_proof", None)
    await update.effective_message.reply_text("✅ Cancelled. Use /start or /admin to continue.")


async def addbal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await admin_balance_command(update, context, add=True)


async def removebal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await admin_balance_command(update, context, add=False)


async def admin_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE, add: bool) -> None:
    if not is_admin(update):
        return await deny_admin(update)
    if len(context.args) != 2:
        command = "/addbal" if add else "/removebal"
        return await update.effective_message.reply_text(f"Usage: {command} USER_ID AMOUNT")
    try:
        uid = int(context.args[0])
        amount = round(float(context.args[1]), 2)
        if uid <= 0 or amount <= 0:
            raise ValueError
    except ValueError:
        return await update.effective_message.reply_text("USER_ID must be a positive integer and amount must be greater than zero.")
    delta = amount if add else -amount
    try:
        ok, bal = change_wallet(uid, delta, "admin_credit" if add else "admin_debit", f"Admin adjustment by {update.effective_user.id}")
    except ValueError as exc:
        return await update.effective_message.reply_text(str(exc))
    await update.effective_message.reply_text(f"✅ Wallet updated for user {uid}. Current balance: {money(bal)}")
    try:
        await context.bot.send_message(uid, f"💰 Wallet update\nAmount: {'+' if add else '-'}{money(amount)}\nCurrent balance: {money(bal)}")
    except TelegramError:
        pass


def change_wallet(user_id: int, delta: float, tx_type: str, note: str, related_id: int | None = None) -> tuple[bool, float]:
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute("INSERT OR IGNORE INTO users(user_id,name,username) VALUES(?,?,?)", (user_id, f"User {user_id}", ""))
        row = con.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        current = float(row["balance"])
        updated = round(current + delta, 2)
        if updated < -0.00001:
            con.rollback()
            raise ValueError("The wallet does not have enough balance for that debit.")
        con.execute("UPDATE users SET balance=? WHERE user_id=?", (updated, user_id))
        con.execute("INSERT INTO wallet_transactions(user_id,amount_delta,transaction_type,note,related_id,created_at) VALUES(?,?,?,?,?,?)",
                    (user_id, delta, tx_type, note, related_id, utc_now()))
        con.commit()
    return True, updated


def user_is_blocked(user_id: int) -> bool:
    row = one("SELECT account_status FROM users WHERE user_id=?", (user_id,))
    return bool(row and row["account_status"] == "Blocked")


def categories_kb() -> InlineKeyboardMarkup:
    items = query("SELECT id,name,emoji FROM categories WHERE visible=1 ORDER BY position,id")
    buttons = [button(f"{r['emoji']} {r['name']}", f"cat:{r['id']}") for r in items]
    buttons.append(button("⬅️ Main Menu", "home"))
    return markup(pair_rows(buttons))


def products_kb(category_id: int) -> InlineKeyboardMarkup:
    items = query("SELECT id,name,emoji FROM products WHERE category_id=? AND visible=1 ORDER BY position,id", (category_id,))
    buttons = [button(f"{r['emoji']} {r['name']}", f"prod:{r['id']}") for r in items]
    buttons.append(button("⬅️ Categories", "go:shop"))
    buttons.append(button("🏠 Main Menu", "home"))
    return markup(pair_rows(buttons))


def plans_kb(product_id: int) -> InlineKeyboardMarkup:
    items = query("SELECT id,name,price,stock FROM plans WHERE product_id=? AND visible=1 ORDER BY id", (product_id,))
    out: list[list[InlineKeyboardButton]] = []
    for r in items:
        stock_text = "Unlimited" if int(r["stock"]) < 0 else ("In stock" if int(r["stock"]) > 0 else "Out of stock")
        out.append([button(f"{r['name']} · {money(r['price'])} · {stock_text}", f"plan:{r['id']}")])
    out.extend([[button("⬅️ Back to Products", f"catback:{product_id}")], [button("🏠 Main Menu", "home")]])
    return markup(out)


def amount_choices() -> list[float]:
    try:
        raw = get_setting("balance_amounts", "100,200,500,1000,2000")
        vals = []
        for p in raw.split(","):
            val = round(float(p.strip()), 2)
            if val > 0 and val not in vals:
                vals.append(val)
        return vals[:8]
    except ValueError:
        return [100.0, 200.0, 500.0, 1000.0, 2000.0]


def add_balance_menu() -> InlineKeyboardMarkup:
    out: list[list[InlineKeyboardButton]] = []
    for amount in amount_choices():
        out.append([button(money(amount), f"bamt:{amount:g}")])
    out.append([button("✍️ Custom Amount", "bcustom")])
    out.append([button("🧑‍💼 Request Manual Credit", "bmanual")])
    out.append([button("📋 My Top-up Requests", "brequests")])
    out.append([button("⬅️ Main Menu", "home")])
    return markup(out)


def user_profile_text(user_id: int) -> str:
    u = one("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not u:
        return "User profile not found. Send /start first."
    stats = one("SELECT COUNT(*) AS n,COALESCE(SUM(price),0) AS total FROM orders WHERE user_id=? AND status='delivered'", (user_id,))
    delivered_count, spent = int(stats["n"]), float(stats["total"])
    total_orders = one("SELECT COUNT(*) AS n FROM orders WHERE user_id=?", (user_id,))["n"]
    total_added = one("SELECT COALESCE(SUM(amount_delta),0) AS n FROM wallet_transactions WHERE user_id=? AND amount_delta>0", (user_id,))["n"]
    product_rows = query("SELECT product_name,plan_name,status,created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,))
    products = "\n".join(f"• {r['product_name']} — {r['plan_name']} ({r['status']})" for r in product_rows) or "• No purchases yet"
    username_line = f"🔗 Username: @{u['username']}\n" if u['username'] else "🔗 Username: Not set\n"
    return (
        "👤 ELITE X CONFIG · MY PROFILE\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🆔 Telegram ID: {u['user_id']}\n"
        f"👤 Name: {u['name'] or '-'}\n"
        + username_line
    ) + (
        f"🏷️ User Type: {u['role']}\n"
        f"📌 Status: {u['account_status']}\n"
        f"📅 Member Since: {u['joined_at']}\n"
        f"🕒 Last Active: {u['last_active_at']}\n\n"
        f"💰 Current Balance: {money(u['balance'])}\n"
        f"➕ Total Added: {money(total_added)}\n"
        f"💸 Total Spent: {money(spent)}\n"
        f"📦 Total Orders: {total_orders} (delivered: {delivered_count})\n"
        f"👥 Referrals: {u['referrals']}\n\n"
        f"🛍️ Recent Products:\n{products}"
    )


def profile_menu() -> InlineKeyboardMarkup:
    return markup([
        [button("🛍️ My Products", "myproducts"), button("📦 My Orders", "go:myorders")],
        [button("🔑 My Keys / Licenses", "mykeys"), button("💳 Transaction History", "transactions")],
        [button("👥 My Referrals", "referrals")],
        [button("⬅️ Main Menu", "home")],
    ])


def support_markup() -> InlineKeyboardMarkup:
    out: list[list[InlineKeyboardButton]] = []
    url = get_setting("support_url", "https://t.me/elitexconfig").strip()
    username = get_setting("support_username", "@elitexconfig").strip()
    if url and valid_url(url):
        out.append([button(f"💬 Contact {username or 'Support'}", url=url)])
    for r in query("SELECT id,label,url FROM support_links WHERE visible=1 ORDER BY position,id"):
        if valid_url(r["url"]):
            out.append([button(r["label"], url=r["url"])])
    channel = get_setting("channel_url", "").strip()
    if channel and valid_url(channel):
        out.append([button("📢 Telegram Channel", url=channel)])
    out.append([button("⬅️ Main Menu", "home")])
    return markup(out)


async def add_balance_request(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float, method: str) -> int:
    user = update.effective_user
    rid = execute(
        "INSERT INTO balance_requests(user_id,username,amount,method,status,created_at) VALUES(?,?,?,?,?,?)",
        (user.id, user.username or user.full_name, round(amount, 2), method, "awaiting_proof" if method == "qr" else "pending", utc_now()),
    )
    if method == "manual":
        text = (f"💳 MANUAL BALANCE REQUEST #{rid}\nUser ID: {user.id}\nUsername: @{user.username or 'not set'}\n"
                f"Name: {user.full_name}\nRequested amount: {money(amount)}\nUser asks the admin to verify the payment and credit this wallet.")
        await notify_admins(context, text, balance_review_markup(rid))
        await update.effective_message.reply_text(
            f"✅ Manual credit request #{rid} sent to the admin. The balance will be added only after admin approval.",
            reply_markup=add_balance_menu())
        return rid
    context.user_data["awaiting_balance_proof"] = rid
    text = (
        f"💰 ADD BALANCE · REQUEST #{rid}\n━━━━━━━━━━━━━━━━━━\n"
        f"Amount: {money(amount)}\n"
        f"UPI ID: {get_setting('upi_id', '').strip() or 'Admin has not set a UPI ID yet.'}\n\n"
        f"{get_setting('payment_instructions', '').strip()}\n\n"
        "After paying, send a screenshot or transaction reference in this chat. Admin will review it before adding wallet balance.\n"
        "Never share your UPI PIN, OTP or bank password."
    )
    await update.effective_message.reply_text(text[:4000], reply_markup=markup([[button("⬅️ Cancel / Main Menu", "home")]]))
    qr_id = get_setting("payment_qr_file_id", "").strip()
    if qr_id:
        try:
            await context.bot.send_photo(update.effective_chat.id, qr_id, caption=f"Payment QR for top-up request #{rid} · {money(amount)}")
        except TelegramError:
            log.warning("Could not send stored payment QR", exc_info=True)
    return rid


async def go_howto(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = get_setting("tutorial_text", "Tutorial details will be added soon.").strip()
    url = get_setting("tutorial_url", "").strip()
    reply_markup = markup([[button("▶️ Open Tutorial", url=url)], [button("⬅️ Main Menu", "home")]]) if url and valid_url(url) else markup([[button("⬅️ Main Menu", "home")]])
    await context.bot.send_message(chat_id, "📖 HOW TO USE\n━━━━━━━━━━━━━━━━━━\n" + text[:3500], reply_markup=reply_markup)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    user = update.effective_user
    if data.startswith("adm:") or data.startswith(("ca:", "pr:", "pl:", "cfg:", "mb:", "sl:", "oa:", "or:", "ba:", "bj:", "usr:", "admn:")):
        if not is_admin(update):
            return await deny_admin(update)
    if user_is_blocked(user.id) and not is_admin(update):
        return await safe_edit(q, "⛔ Your account is restricted. Please contact Support.", markup([[button("🎧 Support", "go:support")]]))

    # User navigation
    if data == "home":
        await safe_edit(q, get_setting("welcome", WELCOME_DEFAULT), main_menu())
    elif data == "go:shop":
        cats = query("SELECT id FROM categories WHERE visible=1")
        msg = "🛍️ ELITE X CONFIG · SHOP NOW\n━━━━━━━━━━━━━━━━━━\nChoose a category:" if cats else "🛍️ The shop is being prepared. Please check again later."
        await safe_edit(q, msg, categories_kb())
    elif data.startswith("cat:"):
        try: cid = int(data.split(":", 1)[1])
        except ValueError: return await safe_edit(q, "Invalid category.", categories_kb())
        cat = one("SELECT * FROM categories WHERE id=? AND visible=1", (cid,))
        if not cat: return await safe_edit(q, "Category not found or unavailable.", categories_kb())
        products_count = one("SELECT COUNT(*) AS n FROM products WHERE category_id=? AND visible=1", (cid,))["n"]
        body = f"{cat['emoji']} {cat['name']}\n━━━━━━━━━━━━━━━━━━"
        if cat["subtitle"]: body += f"\n{cat['subtitle']}"
        body += "\n\nChoose a product below:" if products_count else "\n\nNo products are available in this category yet."
        await safe_edit(q, body, products_kb(cid))
    elif data.startswith("catback:"):
        try: pid = int(data.split(":", 1)[1])
        except ValueError: return await safe_edit(q, "Invalid product.", categories_kb())
        p = one("SELECT category_id FROM products WHERE id=?", (pid,))
        await safe_edit(q, "Choose a product:", products_kb(int(p["category_id"])) if p else categories_kb())
    elif data.startswith("prod:"):
        try: pid = int(data.split(":", 1)[1])
        except ValueError: return await safe_edit(q, "Invalid product.", categories_kb())
        prod = one("SELECT * FROM products WHERE id=? AND visible=1", (pid,))
        if not prod: return await safe_edit(q, "Product not found or unavailable.", categories_kb())
        body = f"{prod['emoji']} {prod['name']}\n━━━━━━━━━━━━━━━━━━"
        if prod["description"]: body += f"\n{prod['description']}"
        if query("SELECT id FROM plans WHERE product_id=? AND visible=1", (pid,)):
            body += "\n\n📦 Select a validity / plan and price:"
        else:
            body += "\n\nPlans will be added soon."
        await safe_edit(q, body, plans_kb(pid))
    elif data.startswith("plan:"):
        try: plan_id = int(data.split(":", 1)[1])
        except ValueError: return await safe_edit(q, "Invalid plan.", main_menu())
        r = one("SELECT pl.*,pr.name AS product_name,pr.description,pr.visible AS product_visible FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=? AND pl.visible=1", (plan_id,))
        if not r or not r["product_visible"]:
            return await safe_edit(q, "This plan is no longer available.", categories_kb())
        if int(r["stock"]) == 0:
            return await q.answer("This plan is out of stock.", show_alert=True)
        context.user_data["chosen_plan"] = plan_id
        body = (f"🛒 PRODUCT CHECKOUT\n━━━━━━━━━━━━━━━━━━\nProduct: {r['product_name']}\n"
                f"Validity: {r['name']}\nPrice: {money(r['price'])}\n"
                f"Wallet balance: {money(one('SELECT balance FROM users WHERE user_id=?', (user.id,))['balance'])}\n\n"
                "Choose how you want to pay:")
        await safe_edit(q, body, markup([
            [button(f"💰 Pay from Wallet · {money(r['price'])}", f"buyw:{plan_id}")],
            [button("💳 Pay by UPI / QR", f"buyq:{plan_id}")],
            [button("💰 Add Balance", "go:addbalance")],
            [button("⬅️ Back", f"prod:{r['product_id']}")],
        ]))
    elif data.startswith("buyw:"):
        try: plan_id = int(data.split(":", 1)[1])
        except ValueError: return await safe_edit(q, "Invalid plan.", main_menu())
        try:
            order_id = wallet_purchase(user, plan_id)
        except ValueError as exc:
            return await q.answer(str(exc), show_alert=True)
        order = one("SELECT product_name,plan_name,price FROM orders WHERE id=?", (order_id,))
        await safe_edit(q, f"✅ WALLET PAYMENT SUCCESSFUL\nOrder: #{order_id}\nProduct: {order['product_name']}\nValidity: {order['plan_name']}\nPaid: {money(order['price'])}\n\nYour order is awaiting delivery. The admin will send your product/key when ready.", markup([[button("📦 My Orders", "go:myorders")], [button("🏠 Main Menu", "home")]]))
        await notify_admins(context, f"🛍️ WALLET ORDER #{order_id}\nUser ID: {user.id}\nProduct: {order['product_name']}\nPlan: {order['plan_name']}\nPrice: {money(order['price'])}\nStatus: awaiting delivery. Use /deliver {order_id} delivery-text")
    elif data.startswith("buyq:"):
        try: plan_id = int(data.split(":", 1)[1])
        except ValueError: return await safe_edit(q, "Invalid plan.", main_menu())
        r = one("SELECT pl.*,pr.name AS product_name,pr.visible AS product_visible FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=? AND pl.visible=1", (plan_id,))
        if not r or not r["product_visible"] or (int(r["stock"]) == 0):
            return await q.answer("This plan is no longer available.", show_alert=True)
        order_id = execute("INSERT INTO orders(user_id,username,plan_id,product_name,plan_name,price,status,payment_method,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                           (user.id, user.username or user.full_name, plan_id, r["product_name"], r["name"], r["price"], "awaiting_payment", "qr", utc_now()))
        context.user_data["awaiting_order_proof"] = order_id
        instructions = get_setting("payment_instructions", "").strip()
        upi_id = get_setting("upi_id", "").strip() or "Not configured yet"
        body = (f"🧾 ORDER #{order_id}\n━━━━━━━━━━━━━━━━━━\nProduct: {r['product_name']}\nValidity: {r['name']}\nTotal: {money(r['price'])}\n"
                f"UPI ID: {upi_id}\n\n{instructions}\n\nAfter payment, send a screenshot or transaction reference in this chat. Admin reviews it before approving delivery.\n"
                "Never share your UPI PIN, OTP or bank password.")
        await safe_edit(q, body, markup([[button("❌ Cancel Order", f"cancelord:{order_id}")], [button("🏠 Main Menu", "home")]]))
        qr_id = get_setting("payment_qr_file_id", "").strip()
        if qr_id:
            try: await context.bot.send_photo(user.id, qr_id, caption=f"Payment QR for order #{order_id} · {money(r['price'])}")
            except TelegramError: log.warning("Failed to send checkout QR", exc_info=True)
    elif data.startswith("proof:"):
        try: oid = int(data.split(":", 1)[1])
        except ValueError: return await q.answer("Invalid order.", show_alert=True)
        order = one("SELECT user_id,status FROM orders WHERE id=?", (oid,))
        if not order or order["user_id"] != user.id or order["status"] != "awaiting_payment":
            return await q.answer("This order is not waiting for proof.", show_alert=True)
        context.user_data["awaiting_order_proof"] = oid
        await safe_edit(q, f"📤 Send a payment screenshot or transaction reference for order #{oid} now. Do not send any PIN or OTP.", markup([[button("🏠 Main Menu", "home")]]))
    elif data.startswith("cancelord:"):
        try: oid = int(data.split(":", 1)[1])
        except ValueError: return await q.answer("Invalid order.", show_alert=True)
        order = one("SELECT user_id,status FROM orders WHERE id=?", (oid,))
        if order and order["user_id"] == user.id and order["status"] == "awaiting_payment":
            execute("UPDATE orders SET status='cancelled' WHERE id=? AND status='awaiting_payment'", (oid,))
            context.user_data.pop("awaiting_order_proof", None)
            await safe_edit(q, f"Order #{oid} has been cancelled.", main_menu())
        else:
            await q.answer("This order cannot be cancelled now.", show_alert=True)
    elif data == "go:profile":
        await safe_edit(q, user_profile_text(user.id), profile_menu())
    elif data == "go:myorders":
        items = query("SELECT id,product_name,plan_name,price,status,created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 12", (user.id,))
        body = "📦 MY ORDERS\n━━━━━━━━━━━━━━━━━━\n" + ("\n\n".join(
            f"Order #{r['id']} · {r['product_name']} / {r['plan_name']}\n{money(r['price'])} · {r['status']}\n{r['created_at']}" for r in items
        ) if items else "You have not placed any orders yet.")
        await safe_edit(q, body[:3900], markup([[button("👤 My Profile", "go:profile")], [button("🏠 Main Menu", "home")]]))
    elif data == "myproducts":
        items = query("SELECT product_name,plan_name,status,created_at,price FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 25", (user.id,))
        body = "🛍️ MY PRODUCTS\n━━━━━━━━━━━━━━━━━━\n" + ("\n\n".join(
            f"{r['product_name']}\nPlan: {r['plan_name']} · {money(r['price'])}\nStatus: {r['status']} · {r['created_at']}" for r in items
        ) if items else "No products purchased yet.")
        await safe_edit(q, body[:3900], markup([[button("🔑 My Keys / Licenses", "mykeys")], [button("⬅️ My Profile", "go:profile")]]))
    elif data == "mykeys":
        items = query("SELECT id,product_name,plan_name,status,delivery_text,created_at FROM orders WHERE user_id=? AND delivery_text<>'' ORDER BY id DESC LIMIT 15", (user.id,))
        body = "🔑 MY KEYS / LICENSES\n━━━━━━━━━━━━━━━━━━\n" + ("\n\n".join(
            f"Order #{r['id']} · {r['product_name']} / {r['plan_name']}\n{r['delivery_text']}\nDelivered: {r['created_at']}" for r in items
        ) if items else "No keys or licenses have been delivered to your account yet.")
        await safe_edit(q, body[:3900], markup([[button("⬅️ My Profile", "go:profile")], [button("🏠 Main Menu", "home")]]))
    elif data == "transactions":
        items = query("SELECT amount_delta,transaction_type,note,created_at FROM wallet_transactions WHERE user_id=? ORDER BY id DESC LIMIT 20", (user.id,))
        body = "💳 WALLET TRANSACTION HISTORY\n━━━━━━━━━━━━━━━━━━\n" + ("\n".join(
            f"{r['created_at']} · {'+' if r['amount_delta']>=0 else ''}{money(r['amount_delta'])}\n{r['transaction_type']} · {r['note']}" for r in items
        ) if items else "No wallet transactions yet.")
        await safe_edit(q, body[:3900], markup([[button("⬅️ My Profile", "go:profile")], [button("🏠 Main Menu", "home")]]))
    elif data == "referrals":
        bot_username = (await context.bot.get_me()).username or "your_bot"
        u = one("SELECT referrals FROM users WHERE user_id=?", (user.id,))
        reward = get_setting("referral_reward", "0")
        link = f"https://t.me/{bot_username}?start=ref_{user.id}"
        await safe_edit(q, f"👥 MY REFERRALS\n━━━━━━━━━━━━━━━━━━\nTotal referrals: {u['referrals'] if u else 0}\nReward per eligible new user: {money(float(reward or 0))}\n\nYour link:\n{link}", markup([[button("⬅️ My Profile", "go:profile")], [button("🏠 Main Menu", "home")]]))
    elif data == "go:addbalance":
        await safe_edit(q, "💰 ADD BALANCE\n━━━━━━━━━━━━━━━━━━\nChoose an amount. You can pay by QR/UPI and submit proof, or request manual admin credit if you have arranged payment with the admin.", add_balance_menu())
    elif data.startswith("bamt:"):
        try: amount = round(float(data.split(":", 1)[1]), 2)
        except ValueError: return await q.answer("Invalid amount.", show_alert=True)
        if amount <= 0 or amount > 10000000: return await q.answer("Invalid amount.", show_alert=True)
        # callbacks cannot call add_balance_request because that function expects an effective_message reply.
        rid = execute("INSERT INTO balance_requests(user_id,username,amount,method,status,created_at) VALUES(?,?,?,?,?,?)",
                      (user.id, user.username or user.full_name, amount, "qr", "awaiting_proof", utc_now()))
        context.user_data["awaiting_balance_proof"] = rid
        text = (f"💰 ADD BALANCE · REQUEST #{rid}\n━━━━━━━━━━━━━━━━━━\nAmount: {money(amount)}\n"
                f"UPI ID: {get_setting('upi_id', '').strip() or 'Not configured yet'}\n\n{get_setting('payment_instructions', '').strip()}\n\n"
                "Send a payment screenshot or transaction reference in this chat. An admin will review it before crediting your wallet. Never share PIN/OTP.")
        await safe_edit(q, text[:3900], markup([[button("🏠 Main Menu", "home")]]))
        qr_id = get_setting("payment_qr_file_id", "").strip()
        if qr_id:
            try: await context.bot.send_photo(user.id, qr_id, caption=f"Payment QR for balance request #{rid} · {money(amount)}")
            except TelegramError: log.warning("Failed to send balance QR", exc_info=True)
    elif data == "bcustom":
        context.user_data["flow"] = "user_custom_balance"
        await safe_edit(q, "✍️ Send the amount you want to add (numbers only, for example 350). Send /cancel to stop.", markup([[button("🏠 Main Menu", "home")]]))
    elif data == "bmanual":
        context.user_data["flow"] = "user_manual_balance"
        await safe_edit(q, "🧑‍💼 Send the amount you arranged with the admin. This creates a manual credit request; the wallet changes only after an admin approves it.", markup([[button("🏠 Main Menu", "home")]]))
    elif data == "brequests":
        items = query("SELECT id,amount,method,status,created_at FROM balance_requests WHERE user_id=? ORDER BY id DESC LIMIT 15", (user.id,))
        body = "📋 MY TOP-UP REQUESTS\n━━━━━━━━━━━━━━━━━━\n" + ("\n\n".join(f"Request #{r['id']} · {money(r['amount'])}\nMethod: {r['method']} · Status: {r['status']}\n{r['created_at']}" for r in items) if items else "No top-up requests yet.")
        await safe_edit(q, body[:3900], markup([[button("⬅️ Add Balance", "go:addbalance")], [button("🏠 Main Menu", "home")]]))
    elif data == "go:support":
        username = get_setting("support_username", "@elitexconfig").strip() or "@elitexconfig"
        await safe_edit(q, f"🎧 ELITE X CONFIG · SUPPORT\n━━━━━━━━━━━━━━━━━━\nContact: {username}\n\nUse the buttons below to open support or configured help links.", support_markup())
    elif data == "go:howto":
        await safe_edit(q, "📖 HOW TO USE\n━━━━━━━━━━━━━━━━━━\n" + get_setting("tutorial_text", "Tutorial details will be added soon.")[:3000], markup(
            ([[button("▶️ Open Tutorial", url=get_setting("tutorial_url"))]] if valid_url(get_setting("tutorial_url")) else []) + [[button("⬅️ Main Menu", "home")]]
        ))
    elif data == "go:channel":
        url = get_setting("channel_url", "").strip()
        if url and valid_url(url):
            await safe_edit(q, "📢 ELITE X CONFIG · CHANNEL\nOpen the configured Telegram channel below.", markup([[button("📢 Open Channel", url=url)], [button("🏠 Main Menu", "home")]]))
        else:
            await safe_edit(q, "The channel link has not been configured yet.", markup([[button("🎧 Support", "go:support")], [button("🏠 Main Menu", "home")]]))

    # Admin navigation / actions
    elif data == "adm:home":
        await safe_edit(q, "👑 ELITE X CONFIG · ADMIN CONTROL CENTER", admin_menu())
    elif data == "adm:dash":
        c = one("SELECT COUNT(*) AS n FROM categories")["n"]
        p = one("SELECT COUNT(*) AS n FROM products")["n"]
        users_count = one("SELECT COUNT(*) AS n FROM users WHERE user_id<>0")["n"]
        pending_orders = one("SELECT COUNT(*) AS n FROM orders WHERE status IN ('awaiting_payment','proof_submitted','approved_awaiting_delivery')")["n"]
        pending_bal = one("SELECT COUNT(*) AS n FROM balance_requests WHERE status IN ('pending','proof_submitted')")["n"]
        balance_sum = one("SELECT COALESCE(SUM(balance),0) AS n FROM users WHERE user_id<>0")["n"]
        await safe_edit(q, f"📊 ADMIN DASHBOARD\n━━━━━━━━━━━━━━━━━━\nCategories: {c}\nProducts: {p}\nUsers: {users_count}\nOrders requiring action: {pending_orders}\nBalance requests requiring action: {pending_bal}\nWallet balance total: {money(balance_sum)}", admin_menu())
    elif data == "adm:categories":
        await safe_edit(q, "📂 CATEGORY MANAGEMENT\nAdd/edit/delete/show/hide every category. Deleting a category also removes its products and plans; historical order names are preserved.", categories_menu())
    elif data == "adm:products":
        await safe_edit(q, "📦 PRODUCT / PLAN MANAGEMENT\nAdd products under categories. Each product can have several plans, each with its own duration, price and stock.", products_menu())
    elif data == "adm:settings":
        await safe_edit(q, "⚙️ STORE SETTINGS\nAll public text, payment instructions, usernames and links below are editable. Clear a text/link by sending a single dash (-).", settings_menu())
    elif data == "adm:menubtns":
        await safe_edit(q, "🧩 MAIN MENU BUTTONS\nAdd, edit, hide or delete the buttons shown after /start. Use actions: shop, profile, addbalance, support, myorders, howto, channel, url.", menu_buttons_menu())
    elif data == "adm:supportlinks":
        await safe_edit(q, "🎧 SUPPORT LINKS\nThese optional URL buttons are shown inside the Support page. Main support username and URL are configured in Store Settings.", support_links_menu())
    elif data == "adm:qr":
        qr_present = bool(get_setting("payment_qr_file_id", "").strip())
        await safe_edit(q, f"🖼️ PAYMENT QR\nCurrently configured: {'Yes' if qr_present else 'No'}\nSend a photo to upload/replace your payment QR. Use Remove QR to clear it.", markup([[button("📤 Upload / Replace QR", "qr:set")], [button("🗑️ Remove QR", "qr:clear")], [button("⬅️ Admin Panel", "adm:home")]]))
    elif data == "qr:set":
        context.user_data["flow"] = "upload_payment_qr"
        await safe_edit(q, "📤 Send the QR image as a photo now. Send /cancel to stop.")
    elif data == "qr:clear":
        set_setting("payment_qr_file_id", "")
        await safe_edit(q, "✅ Payment QR removed.", admin_menu())
    elif data == "cfg:welcome":
        return await start_admin_input(q, context, "cfg_welcome", "Send the new welcome message. Emojis and line breaks are supported; send - to clear it.")
    elif data == "cfg:payment":
        return await start_admin_input(q, context, "cfg_payment", "Send payment instructions (UPI steps, payment notes, etc.). Send - to clear.")
    elif data == "cfg:upi":
        return await start_admin_input(q, context, "cfg_upi", "Send the UPI ID shown to customers, or - to remove it.")
    elif data == "cfg:amounts":
        return await start_admin_input(q, context, "cfg_amounts", "Send comma-separated top-up amounts, e.g. 100,200,500,1000. Up to 8 values; send - for no presets.")
    elif data == "cfg:support_user":
        return await start_admin_input(q, context, "cfg_support_user", "Send support username, e.g. @elitexconfig. Send - to remove the displayed username.")
    elif data == "cfg:support_url":
        return await start_admin_input(q, context, "cfg_support_url", "Send support URL, e.g. https://t.me/elitexconfig, or - to remove the button.")
    elif data == "cfg:channel":
        return await start_admin_input(q, context, "cfg_channel", "Send the Telegram channel URL, or - to remove it.")
    elif data == "cfg:tutorial_text":
        return await start_admin_input(q, context, "cfg_tutorial_text", "Send the How to Use instructions, or - to clear them.")
    elif data == "cfg:tutorial_url":
        return await start_admin_input(q, context, "cfg_tutorial_url", "Send a tutorial/video/Telegram URL, or - to remove the button.")
    elif data == "cfg:reward":
        return await start_admin_input(q, context, "cfg_reward", "Send referral reward per eligible new user (e.g. 5 or 0 to disable).")
    elif data == "cfg:welcome_media":
        context.user_data["flow"] = "upload_welcome_media"
        await safe_edit(q, "📤 Send a photo, GIF or video to set the /start welcome media. Send /cancel to stop.")
    elif data == "cfg:welcome_clear":
        set_setting("welcome_logo_file_id", "")
        set_setting("welcome_animation_file_id", "")
        set_setting("welcome_media_disabled", "1")
        await safe_edit(q, "✅ Welcome media removed. The bot now sends text only.", settings_menu())

    # Category management
    elif data == "ca:list":
        rows_ = query("SELECT id,name,subtitle,emoji,visible,position FROM categories ORDER BY position,id")
        text = "📂 CATEGORIES\n\n" + ("\n\n".join(f"ID {r['id']} · {r['emoji']} {r['name']}\nStatus: {'Visible' if r['visible'] else 'Hidden'} · Position: {r['position']}\nDescription: {r['subtitle'] or '-'}" for r in rows_) if rows_ else "No categories." )
        await safe_edit(q, text[:3900], categories_menu())
    elif data in {"ca:add", "ca:edit", "ca:delete", "ca:toggle"}:
        flow = {"ca:add": "cat_add_name", "ca:edit": "cat_edit_id", "ca:delete": "cat_delete_id", "ca:toggle": "cat_toggle_id"}[data]
        prompts = {"cat_add_name": "Send the new category name.", "cat_edit_id": "Send the category ID to edit.", "cat_delete_id": "Send category ID to delete. Its products and plans will also be removed.", "cat_toggle_id": "Send category ID to toggle visible/hidden."}
        return await start_admin_input(q, context, flow, prompts[flow])
    elif data == "pr:list":
        rows_ = query("SELECT p.id,p.name,c.name AS category,p.visible,pl.id AS plan_id,pl.name AS plan,pl.price,pl.stock,pl.visible AS plan_visible FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN plans pl ON pl.product_id=p.id ORDER BY c.position,p.position,p.id,pl.id")
        text = "📦 PRODUCTS / PLANS\n\n" + ("\n".join(f"Product #{r['id']} · {r['name']} | {r['category']} | {'Visible' if r['visible'] else 'Hidden'}\n  Plan #{r['plan_id'] or '-'} · {r['plan'] or '-'} · {money(r['price'] or 0)} · Stock {r['stock'] if r['stock'] is not None else '-'} · {'Visible' if r['plan_visible'] else 'Hidden'}" for r in rows_) if rows_ else "No products yet.")
        await safe_edit(q, text[:3900], products_menu())
    elif data in {"pr:add", "pr:edit", "pr:delete", "pr:toggle", "pl:add", "pl:edit", "pl:delete"}:
        mapping = {"pr:add": ("prod_add_cat", "Send the category ID for the new product."), "pr:edit": ("prod_edit_id", "Send the product ID to edit."), "pr:delete": ("prod_delete_id", "Send the product ID to delete."), "pr:toggle": ("prod_toggle_id", "Send the product ID to show/hide."), "pl:add": ("plan_add_product", "Send the product ID that should receive a new plan."), "pl:edit": ("plan_edit_id", "Send the plan ID to edit."), "pl:delete": ("plan_delete_id", "Send the plan ID to delete.")}
        flow, prompt = mapping[data]
        if flow == "prod_add_cat":
            cats = query("SELECT id,name FROM categories ORDER BY position,id")
            prompt += "\n\n" + ("\n".join(f"{r['id']} — {r['name']}" for r in cats) if cats else "No categories exist; add one first.")
        return await start_admin_input(q, context, flow, prompt)

    # Orders and balance review
    elif data == "adm:orders":
        rows_ = query("SELECT id,user_id,product_name,plan_name,price,status,created_at FROM orders WHERE status IN ('awaiting_payment','proof_submitted','approved_awaiting_delivery') ORDER BY id DESC LIMIT 20")
        text = "🧾 ORDERS NEEDING ACTION\n\n" + ("\n\n".join(f"Order #{r['id']} · User {r['user_id']}\n{r['product_name']} / {r['plan_name']} · {money(r['price'])}\nStatus: {r['status']} · {r['created_at']}" for r in rows_) if rows_ else "No pending orders.")
        await safe_edit(q, text[:3900], admin_menu())
    elif data == "adm:balances":
        rows_ = query("SELECT id,user_id,username,amount,method,status,created_at FROM balance_requests WHERE status IN ('pending','proof_submitted') ORDER BY id DESC LIMIT 20")
        text = "💳 BALANCE REQUESTS NEEDING ACTION\n\n" + ("\n\n".join(f"Request #{r['id']} · User {r['user_id']} (@{r['username'] or 'none'})\nAmount: {money(r['amount'])} · {r['method']} · {r['status']}\n{r['created_at']}" for r in rows_) if rows_ else "No pending balance requests.")
        await safe_edit(q, text[:3900], admin_menu())
    elif data.startswith("oa:"):
        oid = int(data.split(":", 1)[1])
        msg = await review_order_payment(oid, approve=True, context=context, query_obj=q)
        return msg
    elif data.startswith("or:"):
        oid = int(data.split(":", 1)[1])
        return await review_order_payment(oid, approve=False, context=context, query_obj=q)
    elif data.startswith("ba:"):
        rid = int(data.split(":", 1)[1])
        return await review_balance_request(rid, approve=True, context=context, query_obj=q)
    elif data.startswith("bj:"):
        rid = int(data.split(":", 1)[1])
        return await review_balance_request(rid, approve=False, context=context, query_obj=q)

    # User administration
    elif data == "adm:users":
        await safe_edit(q, "👥 USER MANAGEMENT\nSearch users by Telegram ID, view user information, set balance, change user type or block/unblock a user.", markup([
            [button("🔎 Find User", "usr:find")],
            [button("📋 Recent Users", "usr:list")],
            [button("💰 Adjust Balance", "usr:balance")],
            [button("🏷️ Change User Type", "usr:type"), button("🚦 Block / Unblock", "usr:status")],
            [button("⬅️ Admin Panel", "adm:home")],
        ]))
    elif data.startswith("usr:"):
        flow_map = {
            "usr:find": ("user_find", "Send the user's numeric Telegram ID."),
            "usr:balance": ("user_balance_id", "Send the user's numeric Telegram ID."),
            "usr:type": ("user_type_id", "Send the user's numeric Telegram ID."),
            "usr:status": ("user_status_id", "Send the user's numeric Telegram ID."),
        }
        if data == "usr:list":
            people = query("SELECT user_id,name,username,role,account_status,balance FROM users WHERE user_id<>0 ORDER BY joined_at DESC LIMIT 20")
            text = "👥 RECENT USERS\n\n" + ("\n\n".join(f"{r['user_id']} · {r['name']} (@{r['username'] or 'none'})\nType: {r['role']} · Status: {r['account_status']} · Balance: {money(r['balance'])}" for r in people) if people else "No users yet.")
            return await safe_edit(q, text[:3900], markup([[button("⬅️ User Management", "adm:users")]]))
        flow, prompt = flow_map[data]
        return await start_admin_input(q, context, flow, prompt)

    # Main menu button editor
    elif data == "mb:list":
        items = query("SELECT id,label,action,url,visible,position FROM menu_buttons ORDER BY position,id")
        text = "🧩 MAIN MENU BUTTONS\n\n" + ("\n\n".join(f"ID {r['id']} · {r['label']}\nAction: {r['action']} · {'Visible' if r['visible'] else 'Hidden'} · Position: {r['position']}\nURL: {r['url'] or '-'}" for r in items) if items else "No menu buttons.")
        await safe_edit(q, text[:3900], menu_buttons_menu())
    elif data in {"mb:add", "mb:edit", "mb:delete", "mb:toggle"}:
        flow_map = {"mb:add": ("menu_add_label", "Send the new button label."), "mb:edit": ("menu_edit_id", "Send the menu button ID to edit."), "mb:delete": ("menu_delete_id", "Send the menu button ID to delete."), "mb:toggle": ("menu_toggle_id", "Send the menu button ID to show/hide.")}
        flow, prompt = flow_map[data]
        return await start_admin_input(q, context, flow, prompt)

    # Support URL link manager
    elif data == "sl:list":
        items = query("SELECT id,label,url,visible FROM support_links ORDER BY position,id")
        text = "🎧 SUPPORT LINKS\n\n" + ("\n\n".join(f"ID {r['id']} · {r['label']}\n{r['url']} · {'Visible' if r['visible'] else 'Hidden'}" for r in items) if items else "No extra support links.")
        await safe_edit(q, text[:3900], support_links_menu())
    elif data in {"sl:add", "sl:edit", "sl:delete", "sl:toggle"}:
        flow_map = {"sl:add": ("support_add_label", "Send the label for the new support URL button."), "sl:edit": ("support_edit_id", "Send support link ID to edit."), "sl:delete": ("support_delete_id", "Send support link ID to delete."), "sl:toggle": ("support_toggle_id", "Send support link ID to show/hide.")}
        flow, prompt = flow_map[data]
        return await start_admin_input(q, context, flow, prompt)

    elif data == "adm:admins":
        if not is_owner(update):
            return await q.answer("Only the configured owner can manage admin accounts.", show_alert=True)
        items = query("SELECT user_id,role,created_at FROM admins ORDER BY user_id")
        text = "🛡️ ADMIN ACCOUNTS\n\nConfigured owner IDs in ADMIN_IDS cannot be removed from this panel.\n\n" + ("\n".join(f"{r['user_id']} · {r['role']} · {r['created_at']}" for r in items) if items else "No additional admins.")
        await safe_edit(q, text[:3800], markup([[button("➕ Add Admin ID", "admn:add")], [button("🗑️ Remove Admin ID", "admn:delete")], [button("⬅️ Admin Panel", "adm:home")]]))
    elif data in {"admn:add", "admn:delete"}:
        if not is_owner(update): return await q.answer("Only the owner can manage admins.", show_alert=True)
        flow = "coadmin_add_id" if data == "admn:add" else "coadmin_delete_id"
        prompt = "Send the numeric Telegram ID to grant admin access." if data == "admn:add" else "Send the additional admin ID to remove. Configured owner IDs cannot be removed here."
        return await start_admin_input(q, context, flow, prompt)


async def start_admin_input(q, context: ContextTypes.DEFAULT_TYPE, flow: str, prompt: str):
    context.user_data["flow"] = flow
    await safe_edit(q, prompt)


def wallet_purchase(tg_user, plan_id: int) -> int:
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        user = con.execute("SELECT balance,account_status FROM users WHERE user_id=?", (tg_user.id,)).fetchone()
        if not user or user["account_status"] == "Blocked":
            con.rollback(); raise ValueError("Your account is restricted or not registered. Send /start and contact Support.")
        r = con.execute("SELECT pl.*,pr.name AS product_name,pr.visible AS product_visible FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=? AND pl.visible=1", (plan_id,)).fetchone()
        if not r or not r["product_visible"]:
            con.rollback(); raise ValueError("This plan is no longer available.")
        stock = int(r["stock"])
        if stock == 0:
            con.rollback(); raise ValueError("This plan is out of stock.")
        price = round(float(r["price"]), 2)
        balance = round(float(user["balance"]), 2)
        if balance < price:
            con.rollback(); raise ValueError(f"Insufficient wallet balance. You have {money(balance)} but need {money(price)}.")
        if stock > 0:
            cur = con.execute("UPDATE plans SET stock=stock-1 WHERE id=? AND stock>0", (plan_id,))
            if cur.rowcount != 1:
                con.rollback(); raise ValueError("This plan just went out of stock. Please try another plan.")
        con.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (price, tg_user.id))
        cur = con.execute("INSERT INTO orders(user_id,username,plan_id,product_name,plan_name,price,status,payment_method,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                          (tg_user.id, tg_user.username or tg_user.full_name, plan_id, r["product_name"], r["name"], price, "approved_awaiting_delivery", "wallet", utc_now()))
        oid = int(cur.lastrowid)
        con.execute("INSERT INTO wallet_transactions(user_id,amount_delta,transaction_type,note,related_id,created_at) VALUES(?,?,?,?,?,?)",
                    (tg_user.id, -price, "purchase", f"Purchase order #{oid}: {r['product_name']} / {r['name']}", oid, utc_now()))
        con.commit()
    return oid


async def review_order_payment(order_id: int, approve: bool, context: ContextTypes.DEFAULT_TYPE, query_obj) -> None:
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            con.rollback(); return await query_obj.answer("Order not found.", show_alert=True)
        if order["status"] != "proof_submitted":
            con.rollback(); return await query_obj.answer("This order is not waiting for payment review.", show_alert=True)
        if approve:
            plan = con.execute("SELECT stock FROM plans WHERE id=?", (order["plan_id"],)).fetchone()
            if not plan:
                con.rollback(); return await query_obj.answer("Plan no longer exists. Review manually.", show_alert=True)
            stock = int(plan["stock"])
            if stock == 0:
                con.rollback(); return await query_obj.answer("Plan is now out of stock. Do not approve; update stock first.", show_alert=True)
            if stock > 0:
                cur = con.execute("UPDATE plans SET stock=stock-1 WHERE id=? AND stock>0", (order["plan_id"],))
                if cur.rowcount != 1:
                    con.rollback(); return await query_obj.answer("Stock has changed. Recheck the plan.", show_alert=True)
            status = "approved_awaiting_delivery"
        else:
            status = "payment_rejected"
        con.execute("UPDATE orders SET status=?,reviewed_at=? WHERE id=? AND status='proof_submitted'", (status, utc_now(), order_id))
        con.commit()
    if approve:
        notify_text = f"✅ Payment for order #{order_id} approved. Your order is queued for delivery."
    else:
        notify_text = f"❌ Payment for order #{order_id} was rejected. Contact Support if you believe this is a mistake."
    try: await context.bot.send_message(order["user_id"], notify_text)
    except TelegramError: pass
    caption = (query_obj.message.caption or "") if query_obj.message else ""
    append = "\n\n✅ APPROVED. Deliver with /deliver {} delivery-text".format(order_id) if approve else "\n\n❌ PAYMENT REJECTED."
    try:
        if query_obj.message and (query_obj.message.photo or query_obj.message.document or query_obj.message.video or query_obj.message.animation):
            await query_obj.edit_message_caption(caption=(caption + append)[:1024], reply_markup=None)
        else:
            old_text = query_obj.message.text if query_obj.message else ""
            await query_obj.edit_message_text((old_text or caption) + append, reply_markup=None)
    except TelegramError:
        await query_obj.message.reply_text(append)


async def review_balance_request(request_id: int, approve: bool, context: ContextTypes.DEFAULT_TYPE, query_obj) -> None:
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        req = con.execute("SELECT * FROM balance_requests WHERE id=?", (request_id,)).fetchone()
        if not req:
            con.rollback(); return await query_obj.answer("Request not found.", show_alert=True)
        if req["status"] not in ("pending", "proof_submitted"):
            con.rollback(); return await query_obj.answer("This request was already reviewed or is still awaiting proof.", show_alert=True)
        if approve:
            con.execute("INSERT OR IGNORE INTO users(user_id,name,username) VALUES(?,?,?)", (req["user_id"], f"User {req['user_id']}", req["username"]))
            con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (req["amount"], req["user_id"]))
            con.execute("INSERT INTO wallet_transactions(user_id,amount_delta,transaction_type,note,related_id,created_at) VALUES(?,?,?,?,?,?)",
                        (req["user_id"], req["amount"], "topup", f"Balance request #{request_id} approved", request_id, utc_now()))
            status = "approved"
        else:
            status = "rejected"
        con.execute("UPDATE balance_requests SET status=?,reviewed_at=? WHERE id=?", (status, utc_now(), request_id))
        con.commit()
    text = f"✅ Your balance request #{request_id} for {money(req['amount'])} was approved. New balance: {money(one('SELECT balance FROM users WHERE user_id=?', (req['user_id'],))['balance'])}." if approve else f"❌ Your balance request #{request_id} was rejected. Contact Support if you need help."
    try: await context.bot.send_message(req["user_id"], text)
    except TelegramError: pass
    caption = (query_obj.message.caption or "") if query_obj.message else ""
    append = "\n\n✅ BALANCE CREDITED." if approve else "\n\n❌ REQUEST REJECTED."
    try:
        if query_obj.message and (query_obj.message.photo or query_obj.message.document or query_obj.message.video or query_obj.message.animation):
            await query_obj.edit_message_caption(caption=(caption + append)[:1024], reply_markup=None)
        else:
            await query_obj.edit_message_text(((query_obj.message.text or caption) if query_obj.message else "") + append, reply_markup=None)
    except TelegramError:
        if query_obj.message: await query_obj.message.reply_text(append)


async def handle_user_balance_input(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float, manual: bool) -> None:
    user = update.effective_user
    if amount <= 0 or amount > 10000000:
        await update.effective_message.reply_text("Please enter an amount greater than 0 and no more than 10,000,000.")
        return
    rid = execute("INSERT INTO balance_requests(user_id,username,amount,method,status,created_at) VALUES(?,?,?,?,?,?)",
                  (user.id, user.username or user.full_name, round(amount, 2), "manual" if manual else "qr", "pending" if manual else "awaiting_proof", utc_now()))
    if manual:
        await notify_admins(context,
            f"💳 MANUAL BALANCE REQUEST #{rid}\nUser ID: {user.id}\nUsername: @{user.username or 'not set'}\nAmount: {money(amount)}\nAdmin: verify payment/arrangement before approval.", balance_review_markup(rid))
        await update.effective_message.reply_text(f"✅ Manual balance request #{rid} sent. Admin will credit the wallet after verification.", reply_markup=add_balance_menu())
    else:
        context.user_data["awaiting_balance_proof"] = rid
        await update.effective_message.reply_text(f"💰 Balance request #{rid}\nAmount: {money(amount)}\nUPI ID: {get_setting('upi_id', '').strip() or 'Not configured'}\n\n{get_setting('payment_instructions', '').strip()}\n\nSend payment screenshot or transaction reference. Balance is added only after admin approval.", reply_markup=markup([[button("🏠 Main Menu", "home")]]))
        qr_id = get_setting("payment_qr_file_id", "").strip()
        if qr_id:
            try: await context.bot.send_photo(user.id, qr_id, caption=f"Payment QR for request #{rid} · {money(amount)}")
            except TelegramError: log.exception("QR send failed")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or not msg.text:
        return
    text = msg.text.strip()

    # Customer may send a transaction reference instead of a screenshot.
    balance_req_id = context.user_data.get("awaiting_balance_proof")
    if balance_req_id and not is_admin(update):
        req = one("SELECT user_id,status,amount FROM balance_requests WHERE id=?", (balance_req_id,))
        if req and req["user_id"] == user.id and req["status"] == "awaiting_proof":
            execute("UPDATE balance_requests SET reference=?,status='proof_submitted' WHERE id=?", (text[:200], balance_req_id))
            context.user_data.pop("awaiting_balance_proof", None)
            await msg.reply_text(f"📨 Transaction reference received for balance request #{balance_req_id}. Admin will review it.")
            await notify_admins(context, f"💰 BALANCE PAYMENT REVIEW #{balance_req_id}\nUser ID: {user.id}\nUsername: @{user.username or 'not set'}\nAmount: {money(req['amount'])}\nTransaction reference: {text[:200]}", balance_review_markup(balance_req_id))
            return
    order_id = context.user_data.get("awaiting_order_proof")
    if order_id and not is_admin(update):
        order = one("SELECT user_id,status,price,product_name,plan_name FROM orders WHERE id=?", (order_id,))
        if order and order["user_id"] == user.id and order["status"] == "awaiting_payment":
            execute("UPDATE orders SET proof_reference=?,status='proof_submitted' WHERE id=? AND status='awaiting_payment'", (text[:200], order_id))
            context.user_data.pop("awaiting_order_proof", None)
            await msg.reply_text(f"📨 Transaction reference received for order #{order_id}. Admin will review it.")
            await notify_admins(context, f"🧾 PAYMENT REVIEW · ORDER #{order_id}\nUser ID: {user.id}\nProduct: {order['product_name']}\nPlan: {order['plan_name']}\nAmount: {money(order['price'])}\nReference: {text[:200]}", order_review_markup(order_id))
            return

    flow = context.user_data.get("flow")
    if not flow:
        return
    if not is_admin(update) and flow not in ("user_custom_balance", "user_manual_balance"):
        context.user_data.pop("flow", None)
        return await msg.reply_text("This input session has expired. Use /start again.")
    async def ask(prompt: str):
        await msg.reply_text(prompt)

    async def done(prompt: str, reply_markup=None):
        context.user_data.pop("flow", None)
        await msg.reply_text(prompt, reply_markup=reply_markup or (admin_menu() if is_admin(update) else add_balance_menu()))

    # User self-service flows
    if flow in ("user_custom_balance", "user_manual_balance"):
        try: amount = round(float(text.replace(",", "")), 2)
        except ValueError: return await ask("Enter a valid numeric amount, e.g. 350.")
        context.user_data.pop("flow", None)
        return await handle_user_balance_input(update, context, amount, manual=(flow == "user_manual_balance"))

    # Category CRUD
    if flow == "cat_add_name":
        if not text or len(text) > 80: return await ask("Category name must be 1-80 characters. Send it again.")
        context.user_data["new_cat_name"] = text; context.user_data["flow"] = "cat_add_subtitle"
        return await ask("Send the category description/subtitle, or - for none.")
    if flow == "cat_add_subtitle":
        context.user_data["new_cat_subtitle"] = "" if text == "-" else text[:300]
        context.user_data["flow"] = "cat_add_emoji"; return await ask("Send one emoji for the category, or - to use 📂.")
    if flow == "cat_add_emoji":
        name = context.user_data.pop("new_cat_name"); subtitle = context.user_data.pop("new_cat_subtitle")
        emoji = "📂" if text == "-" else text[:8]
        pos = one("SELECT COALESCE(MAX(position),0)+1 AS n FROM categories")["n"]
        cid = execute("INSERT INTO categories(name,subtitle,emoji,position) VALUES(?,?,?,?)", (name, subtitle, emoji, pos))
        return await done(f"✅ Category added. Category ID: {cid}")
    if flow in ("cat_edit_id", "cat_delete_id", "cat_toggle_id"):
        if not text.isdigit(): return await ask("Send a numeric category ID.")
        cid = int(text); cat = one("SELECT * FROM categories WHERE id=?", (cid,))
        if not cat: return await ask("Category ID not found. Check Categories → List Categories.")
        context.user_data.pop("flow", None)
        if flow == "cat_delete_id":
            # The catalogue is removed; order snapshots remain in the orders table.
            pids = [int(r["id"]) for r in query("SELECT id FROM products WHERE category_id=?", (cid,))]
            for pid in pids: execute("DELETE FROM plans WHERE product_id=?", (pid,))
            execute("DELETE FROM products WHERE category_id=?", (cid,)); execute("DELETE FROM categories WHERE id=?", (cid,))
            return await done(f"🗑️ Category #{cid} and its products/plans deleted. Historical orders remain.")
        if flow == "cat_toggle_id":
            execute("UPDATE categories SET visible=? WHERE id=?", (0 if cat["visible"] else 1, cid))
            return await done(f"✅ Category #{cid} is now {'hidden' if cat['visible'] else 'visible'}.")
        context.user_data["edit_cat_id"] = cid; context.user_data["flow"] = "cat_edit_field"
        return await ask("Which field do you want to edit? Send: name, subtitle, emoji")
    if flow == "cat_edit_field":
        if text.lower() not in ("name", "subtitle", "emoji"): return await ask("Choose exactly: name, subtitle, emoji")
        context.user_data["edit_cat_field"] = text.lower(); context.user_data["flow"] = "cat_edit_value"
        return await ask("Send the new value (send - to clear subtitle).")
    if flow == "cat_edit_value":
        field = context.user_data.pop("edit_cat_field"); cid = context.user_data.pop("edit_cat_id")
        value = "" if text == "-" and field == "subtitle" else text[:300]
        if field == "name" and not value: context.user_data["edit_cat_id"] = cid; context.user_data["edit_cat_field"] = field; context.user_data["flow"] = flow; return await ask("Name cannot be blank.")
        if field == "emoji" and text == "-": value = "📂"
        execute(f"UPDATE categories SET {field}=? WHERE id=?", (value, cid))
        return await done(f"✅ Category #{cid} updated.")

    # Product creation and edit/delete
    if flow == "prod_add_cat":
        if not text.isdigit() or not one("SELECT id FROM categories WHERE id=?", (int(text),)): return await ask("Invalid Category ID. See Categories → List Categories.")
        context.user_data["new_prod_cat"] = int(text); context.user_data["flow"] = "prod_add_name"; return await ask("Send product name.")
    if flow == "prod_add_name":
        if not text or len(text) > 100: return await ask("Product name must be 1-100 characters.")
        context.user_data["new_prod_name"] = text; context.user_data["flow"] = "prod_add_desc"; return await ask("Send product description, or - for none.")
    if flow == "prod_add_desc":
        context.user_data["new_prod_desc"] = "" if text == "-" else text[:1000]; context.user_data["flow"] = "prod_add_emoji"; return await ask("Send product emoji, or - to use 🛒.")
    if flow == "prod_add_emoji":
        context.user_data["new_prod_emoji"] = "🛒" if text == "-" else text[:8]; context.user_data["flow"] = "prod_add_plan_name"; return await ask("Send the first plan's validity/name (e.g. 7 Days, 30 Days, Lifetime).")
    if flow == "prod_add_plan_name":
        context.user_data["new_plan_name"] = text[:80]; context.user_data["flow"] = "prod_add_price"; return await ask("Send the plan price in INR, e.g. 99 or 249.50.")
    if flow == "prod_add_price":
        try: price = round(float(text), 2)
        except ValueError: return await ask("Enter a valid numeric price.")
        if price < 0: return await ask("Price cannot be negative.")
        context.user_data["new_plan_price"] = price; context.user_data["flow"] = "prod_add_stock"; return await ask("Send stock quantity: -1 means unlimited, 0 means out of stock, 1+ means limited stock.")
    if flow == "prod_add_stock":
        try: stock = int(text)
        except ValueError: return await ask("Stock must be an integer. Use -1 for unlimited.")
        if stock < -1: return await ask("Stock must be -1 or greater.")
        cid = context.user_data.pop("new_prod_cat"); name = context.user_data.pop("new_prod_name")
        desc = context.user_data.pop("new_prod_desc"); emoji = context.user_data.pop("new_prod_emoji")
        plan_name = context.user_data.pop("new_plan_name"); price = context.user_data.pop("new_plan_price")
        pos = one("SELECT COALESCE(MAX(position),0)+1 AS n FROM products WHERE category_id=?", (cid,))["n"]
        pid = execute("INSERT INTO products(category_id,name,description,emoji,position) VALUES(?,?,?,?,?)", (cid, name, desc, emoji, pos))
        plan_id = execute("INSERT INTO plans(product_id,name,price,stock) VALUES(?,?,?,?)", (pid, plan_name, price, stock))
        return await done(f"✅ Product and first plan created.\nProduct ID: {pid}\nPlan ID: {plan_id}")
    if flow == "plan_add_product":
        if not text.isdigit() or not one("SELECT id FROM products WHERE id=?", (int(text),)): return await ask("Invalid Product ID. Check Products → List Products.")
        context.user_data["new_plan_product"] = int(text); context.user_data["flow"] = "plan_add_name"; return await ask("Send validity / plan name, e.g. 30 Days.")
    if flow == "plan_add_name":
        context.user_data["new_plan_name"] = text[:80]; context.user_data["flow"] = "plan_add_price"; return await ask("Send the plan price in INR.")
    if flow == "plan_add_price":
        try: price = round(float(text), 2)
        except ValueError: return await ask("Enter a valid price.")
        if price < 0: return await ask("Price cannot be negative.")
        context.user_data["new_plan_price"] = price; context.user_data["flow"] = "plan_add_stock"; return await ask("Send stock quantity (-1 unlimited, 0 out, positive limited).")
    if flow == "plan_add_stock":
        try: stock = int(text)
        except ValueError: return await ask("Stock must be an integer.")
        if stock < -1: return await ask("Stock must be -1 or greater.")
        pid = context.user_data.pop("new_plan_product"); name = context.user_data.pop("new_plan_name"); price = context.user_data.pop("new_plan_price")
        plan_id = execute("INSERT INTO plans(product_id,name,price,stock) VALUES(?,?,?,?)", (pid, name, price, stock))
        return await done(f"✅ Plan added. Plan ID: {plan_id}")
    if flow in ("prod_edit_id", "prod_delete_id", "prod_toggle_id", "plan_edit_id", "plan_delete_id"):
        if not text.isdigit(): return await ask("Send a numeric ID.")
        obj_id = int(text)
        if flow.startswith("prod_"):
            obj = one("SELECT * FROM products WHERE id=?", (obj_id,))
            if not obj: return await ask("Product ID not found.")
            context.user_data.pop("flow", None)
            if flow == "prod_delete_id":
                execute("DELETE FROM plans WHERE product_id=?", (obj_id,)); execute("DELETE FROM products WHERE id=?", (obj_id,))
                return await done(f"🗑️ Product #{obj_id} and its plans deleted. Historical orders remain.")
            if flow == "prod_toggle_id":
                execute("UPDATE products SET visible=? WHERE id=?", (0 if obj["visible"] else 1, obj_id))
                return await done(f"✅ Product #{obj_id} visibility changed.")
            context.user_data["edit_prod_id"] = obj_id; context.user_data["flow"] = "prod_edit_field"
            return await ask("Which field? Send: name, description, emoji, category_id")
        obj = one("SELECT * FROM plans WHERE id=?", (obj_id,))
        if not obj: return await ask("Plan ID not found.")
        context.user_data.pop("flow", None)
        if flow == "plan_delete_id":
            execute("DELETE FROM plans WHERE id=?", (obj_id,)); return await done(f"🗑️ Plan #{obj_id} deleted. Historical orders remain.")
        context.user_data["edit_plan_id"] = obj_id; context.user_data["flow"] = "plan_edit_field"
        return await ask("Which field? Send: name, price, stock, visible")
    if flow == "prod_edit_field":
        if text.lower() not in ("name", "description", "emoji", "category_id"): return await ask("Choose: name, description, emoji, category_id")
        context.user_data["edit_prod_field"] = text.lower(); context.user_data["flow"] = "prod_edit_value"; return await ask("Send the new value. For category_id, send an existing category ID; send - to clear description.")
    if flow == "prod_edit_value":
        field = context.user_data.pop("edit_prod_field"); pid = context.user_data.pop("edit_prod_id")
        if field == "category_id":
            if not text.isdigit() or not one("SELECT id FROM categories WHERE id=?", (int(text),)):
                context.user_data["edit_prod_field"] = field; context.user_data["edit_prod_id"] = pid; context.user_data["flow"] = flow
                return await ask("Invalid category ID. Send an existing category ID.")
            value: Any = int(text)
        elif field == "description" and text == "-": value = ""
        else: value = text[:1000]
        if field == "name" and not str(value).strip():
            context.user_data["edit_prod_field"] = field; context.user_data["edit_prod_id"] = pid; context.user_data["flow"] = flow
            return await ask("Product name cannot be blank.")
        execute(f"UPDATE products SET {field}=? WHERE id=?", (value, pid)); return await done(f"✅ Product #{pid} updated.")
    if flow == "plan_edit_field":
        if text.lower() not in ("name", "price", "stock", "visible"): return await ask("Choose: name, price, stock, visible")
        context.user_data["edit_plan_field"] = text.lower(); context.user_data["flow"] = "plan_edit_value"; return await ask("Send the new value. visible must be 0 or 1; stock: -1 unlimited.")
    if flow == "plan_edit_value":
        field = context.user_data.pop("edit_plan_field"); pid = context.user_data.pop("edit_plan_id")
        try:
            if field == "price":
                value = round(float(text), 2)
                if value < 0: raise ValueError
            elif field == "stock":
                value = int(text)
                if value < -1: raise ValueError
            elif field == "visible":
                value = int(text)
                if value not in (0, 1): raise ValueError
            else:
                value = text[:80]
                if not value.strip(): raise ValueError
        except ValueError:
            context.user_data["edit_plan_field"] = field; context.user_data["edit_plan_id"] = pid; context.user_data["flow"] = flow
            return await ask("Invalid value. Try again with the correct data type.")
        execute(f"UPDATE plans SET {field}=? WHERE id=?", (value, pid)); return await done(f"✅ Plan #{pid} updated.")

    # Settings input
    setting_flows = {
        "cfg_welcome": "welcome", "cfg_payment": "payment_instructions", "cfg_upi": "upi_id",
        "cfg_support_user": "support_username", "cfg_support_url": "support_url", "cfg_channel": "channel_url",
        "cfg_tutorial_text": "tutorial_text", "cfg_tutorial_url": "tutorial_url",
    }
    if flow in setting_flows:
        key = setting_flows[flow]
        value = "" if text == "-" else text
        if flow in ("cfg_support_url", "cfg_channel", "cfg_tutorial_url") and not valid_url(value, allow_blank=True):
            return await ask("Please send a valid URL beginning with https://, http:// or tg://, or - to clear it.")
        if flow == "cfg_support_user" and value and not value.startswith("@"):
            value = "@" + value
        set_setting(key, value)
        return await done(f"✅ Setting saved: {key}.")
    if flow == "cfg_amounts":
        if text == "-":
            values = []
        else:
            try:
                values = [round(float(s.strip()), 2) for s in text.split(",") if s.strip()]
                if not values or len(values) > 8 or any(v <= 0 for v in values) or len(set(values)) != len(values): raise ValueError
            except ValueError:
                return await ask("Send up to 8 unique positive amounts separated by commas, e.g. 100,200,500,1000; or -.")
        set_setting("balance_amounts", ",".join(str(v) for v in values))
        return await done("✅ Add Balance amount buttons updated.")
    if flow == "cfg_reward":
        try: value = round(float(text), 2)
        except ValueError: return await ask("Enter a number such as 5 or 0.")
        if value < 0: return await ask("Referral reward cannot be negative.")
        set_setting("referral_reward", str(value)); return await done(f"✅ Referral reward set to {money(value)} per eligible new user.")

    # Main menu button manager
    if flow == "menu_add_label":
        if not text or len(text) > 60: return await ask("Button label must be 1-60 characters.")
        context.user_data["menu_new_label"] = text; context.user_data["flow"] = "menu_add_action"
        return await ask("Send action: shop, profile, addbalance, support, myorders, howto, channel, or url.")
    if flow == "menu_add_action":
        action = text.lower()
        if action not in KNOWN_ACTIONS: return await ask("Use one of: shop, profile, addbalance, support, myorders, howto, channel, url.")
        context.user_data["menu_new_action"] = action
        if action == "url": context.user_data["flow"] = "menu_add_url"; return await ask("Send the button URL starting with https://, http:// or tg://.")
        label = context.user_data.pop("menu_new_label"); pos = one("SELECT COALESCE(MAX(position),0)+1 AS n FROM menu_buttons")["n"]
        bid = execute("INSERT INTO menu_buttons(label,action,position) VALUES(?,?,?)", (label, action, pos))
        context.user_data.pop("menu_new_action", None); return await done(f"✅ Menu button added. ID: {bid}")
    if flow == "menu_add_url":
        if not valid_url(text): return await ask("Invalid URL. Use https://, http:// or tg://.")
        label = context.user_data.pop("menu_new_label"); pos = one("SELECT COALESCE(MAX(position),0)+1 AS n FROM menu_buttons")["n"]
        bid = execute("INSERT INTO menu_buttons(label,action,url,position) VALUES(?,?,?,?)", (label, "url", text[:500], pos))
        context.user_data.pop("menu_new_action", None); return await done(f"✅ URL menu button added. ID: {bid}")
    if flow in ("menu_edit_id", "menu_delete_id", "menu_toggle_id"):
        if not text.isdigit(): return await ask("Send a numeric menu button ID.")
        bid = int(text); obj = one("SELECT * FROM menu_buttons WHERE id=?", (bid,))
        if not obj: return await ask("Menu button ID not found.")
        context.user_data.pop("flow", None)
        if flow == "menu_delete_id": execute("DELETE FROM menu_buttons WHERE id=?", (bid,)); return await done(f"🗑️ Menu button #{bid} deleted.")
        if flow == "menu_toggle_id": execute("UPDATE menu_buttons SET visible=? WHERE id=?", (0 if obj["visible"] else 1, bid)); return await done(f"✅ Menu button #{bid} visibility updated.")
        context.user_data["menu_edit_id"] = bid; context.user_data["flow"] = "menu_edit_field"; return await ask("Which field? Send: label, action, url, position")
    if flow == "menu_edit_field":
        if text.lower() not in ("label", "action", "url", "position"): return await ask("Choose: label, action, url, position")
        context.user_data["menu_edit_field"] = text.lower(); context.user_data["flow"] = "menu_edit_value"; return await ask("Send the new value. action must be a supported action; url can be - to clear.")
    if flow == "menu_edit_value":
        field = context.user_data.pop("menu_edit_field"); bid = context.user_data.pop("menu_edit_id")
        if field == "action":
            value = text.lower()
            if value not in KNOWN_ACTIONS: context.user_data["menu_edit_field"] = field; context.user_data["menu_edit_id"] = bid; context.user_data["flow"] = flow; return await ask("Invalid action. Use shop, profile, addbalance, support, myorders, howto, channel, url.")
        elif field == "url":
            value = "" if text == "-" else text
            if value and not valid_url(value): context.user_data["menu_edit_field"] = field; context.user_data["menu_edit_id"] = bid; context.user_data["flow"] = flow; return await ask("Send a valid URL, or - to clear it.")
        elif field == "position":
            if not text.isdigit() or int(text) < 1: context.user_data["menu_edit_field"] = field; context.user_data["menu_edit_id"] = bid; context.user_data["flow"] = flow; return await ask("Position must be a positive integer.")
            value = int(text)
        else:
            value = text[:60]
            if not value.strip(): context.user_data["menu_edit_field"] = field; context.user_data["menu_edit_id"] = bid; context.user_data["flow"] = flow; return await ask("Label cannot be blank.")
        execute(f"UPDATE menu_buttons SET {field}=? WHERE id=?", (value, bid)); return await done(f"✅ Menu button #{bid} updated.")

    # Support links CRUD
    if flow == "support_add_label":
        if not text or len(text) > 60: return await ask("Support link label must be 1-60 characters.")
        context.user_data["support_new_label"] = text; context.user_data["flow"] = "support_add_url"; return await ask("Send the link URL starting with https://, http:// or tg://.")
    if flow == "support_add_url":
        if not valid_url(text): return await ask("Invalid URL. Try again.")
        label = context.user_data.pop("support_new_label"); pos = one("SELECT COALESCE(MAX(position),0)+1 AS n FROM support_links")["n"]
        lid = execute("INSERT INTO support_links(label,url,position) VALUES(?,?,?)", (label, text[:500], pos)); return await done(f"✅ Support link added. ID: {lid}")
    if flow in ("support_edit_id", "support_delete_id", "support_toggle_id"):
        if not text.isdigit(): return await ask("Send a numeric support link ID.")
        lid = int(text); obj = one("SELECT * FROM support_links WHERE id=?", (lid,))
        if not obj: return await ask("Support link ID not found.")
        context.user_data.pop("flow", None)
        if flow == "support_delete_id": execute("DELETE FROM support_links WHERE id=?", (lid,)); return await done(f"🗑️ Support link #{lid} deleted.")
        if flow == "support_toggle_id": execute("UPDATE support_links SET visible=? WHERE id=?", (0 if obj["visible"] else 1, lid)); return await done(f"✅ Support link #{lid} visibility updated.")
        context.user_data["support_edit_id"] = lid; context.user_data["flow"] = "support_edit_field"; return await ask("Which field? Send: label, url, position")
    if flow == "support_edit_field":
        if text.lower() not in ("label", "url", "position"): return await ask("Choose: label, url, position")
        context.user_data["support_edit_field"] = text.lower(); context.user_data["flow"] = "support_edit_value"; return await ask("Send the new value. URL can be - to clear.")
    if flow == "support_edit_value":
        field = context.user_data.pop("support_edit_field"); lid = context.user_data.pop("support_edit_id")
        if field == "url":
            value = "" if text == "-" else text
            if value and not valid_url(value): context.user_data["support_edit_field"] = field; context.user_data["support_edit_id"] = lid; context.user_data["flow"] = flow; return await ask("Send a valid URL or - to clear.")
        elif field == "position":
            if not text.isdigit() or int(text)<1: context.user_data["support_edit_field"] = field; context.user_data["support_edit_id"] = lid; context.user_data["flow"] = flow; return await ask("Position must be a positive integer.")
            value = int(text)
        else:
            value = text[:60]
            if not value.strip(): context.user_data["support_edit_field"] = field; context.user_data["support_edit_id"] = lid; context.user_data["flow"] = flow; return await ask("Label cannot be blank.")
        execute(f"UPDATE support_links SET {field}=? WHERE id=?", (value, lid)); return await done(f"✅ Support link #{lid} updated.")

    # User management
    if flow == "user_find":
        if not text.isdigit(): return await ask("Send numeric Telegram ID.")
        uid = int(text); row = one("SELECT user_id FROM users WHERE user_id=?", (uid,))
        context.user_data.pop("flow", None)
        if not row: return await done("User not found in this bot's database.")
        return await done(user_profile_text(uid))
    if flow == "user_balance_id":
        if not text.isdigit(): return await ask("Send numeric Telegram ID.")
        uid = int(text)
        if not one("SELECT user_id FROM users WHERE user_id=?", (uid,)): return await ask("User not found. Ask the user to start the bot first.")
        context.user_data["user_balance_target"] = uid; context.user_data["flow"] = "user_balance_amount"; return await ask("Send a signed balance change: positive to add (250), negative to remove (-50). It cannot reduce balance below zero.")
    if flow == "user_balance_amount":
        try: delta = round(float(text), 2)
        except ValueError: return await ask("Send a numeric signed amount, e.g. 250 or -50.")
        if not delta: return await ask("Amount must not be zero.")
        uid = context.user_data.pop("user_balance_target")
        try: _, bal = change_wallet(uid, delta, "admin_adjustment", f"Admin {user.id} adjusted balance")
        except ValueError as exc: context.user_data["user_balance_target"] = uid; return await ask(str(exc))
        return await done(f"✅ User {uid} wallet adjusted by {money(delta)}. New balance: {money(bal)}")
    if flow == "user_type_id":
        if not text.isdigit(): return await ask("Send numeric Telegram ID.")
        uid = int(text)
        if not one("SELECT user_id FROM users WHERE user_id=?", (uid,)): return await ask("User not found. Ask them to start the bot first.")
        context.user_data["user_type_target"] = uid; context.user_data["flow"] = "user_type_value"; return await ask("Send the new user type, e.g. User, VIP, Reseller. Max 30 characters.")
    if flow == "user_type_value":
        if not text or len(text)>30: return await ask("Type must be 1-30 characters.")
        uid = context.user_data.pop("user_type_target"); execute("UPDATE users SET role=? WHERE user_id=?", (text, uid)); return await done(f"✅ User {uid} type changed to {text}.")
    if flow == "user_status_id":
        if not text.isdigit(): return await ask("Send numeric Telegram ID.")
        uid = int(text); row = one("SELECT account_status FROM users WHERE user_id=?", (uid,))
        if not row: return await ask("User not found. Ask the user to start the bot first.")
        new = "Active" if row["account_status"] == "Blocked" else "Blocked"
        execute("UPDATE users SET account_status=? WHERE user_id=?", (new, uid))
        return await done(f"✅ User {uid} status changed to {new}.")

    # Co-admin accounts; configured owners from ADMIN_IDS cannot be removed here.
    if flow == "coadmin_add_id":
        if not is_owner(update): return await done("Only owner can manage admin accounts.")
        if not text.isdigit() or int(text) <= 0: return await ask("Send a valid positive Telegram ID.")
        aid = int(text)
        if aid in ADMIN_IDS: return await done("That ID is already a configured owner.")
        execute("INSERT OR REPLACE INTO admins(user_id,role,added_by,created_at) VALUES(?,?,?,?)", (aid, "Admin", user.id, utc_now()))
        return await done(f"✅ Admin access granted to Telegram ID {aid}. They need to open the bot once before you can message them.")
    if flow == "coadmin_delete_id":
        if not is_owner(update): return await done("Only owner can manage admin accounts.")
        if not text.isdigit(): return await ask("Send a valid numeric ID.")
        aid = int(text)
        if aid in ADMIN_IDS: return await done("Configured owner IDs cannot be removed here. Change ADMIN_IDS in hosting environment.")
        execute("DELETE FROM admins WHERE user_id=?", (aid,)); return await done(f"✅ Additional admin {aid} removed, if present.")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return
    flow = context.user_data.get("flow")
    if is_admin(update) and flow == "upload_payment_qr":
        if not msg.photo:
            return await msg.reply_text("Please send the QR as a photo. Send /cancel to stop.")
        set_setting("payment_qr_file_id", msg.photo[-1].file_id)
        context.user_data.pop("flow", None)
        return await msg.reply_text("✅ Payment QR saved/replaced. Buyers will see it during checkout and Add Balance.", reply_markup=admin_menu())
    if is_admin(update) and flow == "upload_welcome_media":
        if msg.photo:
            set_setting("welcome_logo_file_id", msg.photo[-1].file_id)
            set_setting("welcome_animation_file_id", "")
            set_setting("welcome_media_disabled", "0")
            context.user_data.pop("flow", None)
            return await msg.reply_text("✅ Welcome photo saved. Use /start to preview.", reply_markup=admin_menu())
        if msg.animation or msg.video:
            media = msg.animation or msg.video
            set_setting("welcome_animation_file_id", media.file_id)
            set_setting("welcome_logo_file_id", "")
            set_setting("welcome_media_disabled", "0")
            context.user_data.pop("flow", None)
            return await msg.reply_text("✅ Welcome GIF/video saved. Use /start to preview.", reply_markup=admin_menu())
        return await msg.reply_text("Please send a photo, GIF or video. Send /cancel to stop.")

    # Balance payment proof can be a photo or a document.
    balance_req_id = context.user_data.get("awaiting_balance_proof")
    if balance_req_id and (msg.photo or msg.document):
        req = one("SELECT * FROM balance_requests WHERE id=?", (balance_req_id,))
        if not req or req["user_id"] != user.id or req["status"] != "awaiting_proof":
            context.user_data.pop("awaiting_balance_proof", None)
            return await msg.reply_text("That balance request is no longer waiting for proof.")
        file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
        execute("UPDATE balance_requests SET proof_file_id=?,status='proof_submitted' WHERE id=?", (file_id, balance_req_id))
        context.user_data.pop("awaiting_balance_proof", None)
        await msg.reply_text(f"📨 Proof received for balance request #{balance_req_id}. Admin will review it.")
        await notify_admins(context, f"💰 BALANCE PAYMENT REVIEW #{balance_req_id}\nUser ID: {user.id}\nUsername: @{user.username or 'not set'}\nAmount: {money(req['amount'])}\nPlease review payment proof.", balance_review_markup(balance_req_id), photo_id=file_id if msg.photo else "", document_id=file_id if msg.document else "")
        return

    order_id = context.user_data.get("awaiting_order_proof")
    if order_id and (msg.photo or msg.document):
        order = one("SELECT * FROM orders WHERE id=?", (order_id,))
        if not order or order["user_id"] != user.id or order["status"] != "awaiting_payment":
            context.user_data.pop("awaiting_order_proof", None)
            return await msg.reply_text("That order is no longer waiting for payment proof.")
        file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
        execute("UPDATE orders SET proof_file_id=?,status='proof_submitted' WHERE id=?", (file_id, order_id))
        context.user_data.pop("awaiting_order_proof", None)
        await msg.reply_text(f"📨 Payment proof received for order #{order_id}. Admin will review it before delivery.")
        await notify_admins(context, f"🧾 PAYMENT REVIEW · ORDER #{order_id}\nUser ID: {user.id}\nProduct: {order['product_name']}\nPlan: {order['plan_name']}\nAmount: {money(order['price'])}\nReview the proof before approving.", order_review_markup(order_id), photo_id=file_id if msg.photo else "", document_id=file_id if msg.document else "")
        return


async def deliver_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny_admin(update)
    msg = update.effective_message
    if len(context.args) < 2 or not context.args[0].isdigit():
        return await msg.reply_text("Usage: /deliver ORDER_ID delivery-text\nExample: /deliver 12 Your key is ABC123")
    oid = int(context.args[0])
    delivery = " ".join(context.args[1:]).strip()
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        order = con.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not order:
            con.rollback(); return await msg.reply_text("Order ID not found.")
        if order["status"] != "approved_awaiting_delivery":
            con.rollback(); return await msg.reply_text("Order is not awaiting delivery. Check payment status and try again.")
        cur = con.execute("UPDATE orders SET status='delivery_in_progress' WHERE id=? AND status='approved_awaiting_delivery'", (oid,))
        if cur.rowcount != 1:
            con.rollback(); return await msg.reply_text("Another admin process is already handling this order.")
        con.commit()
    try:
        await context.bot.send_message(order["user_id"], f"🎉 ELITE X CONFIG · ORDER DELIVERY\n━━━━━━━━━━━━━━━━━━\nOrder: #{oid}\nProduct: {order['product_name']}\nValidity: {order['plan_name']}\n\nDelivery details:\n{delivery}\n\nThank you for your order.")
    except TelegramError:
        execute("UPDATE orders SET status='approved_awaiting_delivery' WHERE id=? AND status='delivery_in_progress'", (oid,))
        return await msg.reply_text("❌ Delivery message could not be sent. Order returned to the delivery queue; verify user can open the bot.")
    execute("UPDATE orders SET status='delivered',delivery_text=?,reviewed_at=? WHERE id=? AND status='delivery_in_progress'", (delivery, utc_now(), oid))
    await msg.reply_text(f"✅ Order #{oid} delivered successfully to user {order['user_id']}.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled bot error: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("⚠️ Something went wrong. Please try again or contact Support.")
        except TelegramError:
            pass


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("Missing BOT_TOKEN environment variable. Set it in your hosting dashboard.")
    if not ADMIN_IDS:
        raise SystemExit("Missing ADMIN_IDS environment variable (your numeric Telegram ID).")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("deliver", deliver_command))
    app.add_handler(CommandHandler("addbal", addbal_command))
    app.add_handler(CommandHandler("removebal", removebal_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.ANIMATION | filters.VIDEO, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)
    log.info("ELITE X CONFIG bot started; owner IDs=%s; database=%s", sorted(ADMIN_IDS), DB_PATH)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
