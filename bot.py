"""ELITE X CONFIG bot - repaired implementation.

Requires aiogram >= 3.25.0 (Telegram Bot API 9.4 button styles).
Set BOT_TOKEN and optionally ADMIN_ID in the environment before running.
"""

import asyncio
import html
import logging
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

# ================= CONFIGURATION =================
# Never put a live token in source code. Export BOT_TOKEN in your shell.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "8467166339"))
DB_PATH = os.getenv("ELITE_X_DB", "elite_x.db")

bot: Bot | None = None
dp = Dispatcher(storage=MemoryStorage())

# Visible menu labels. These are used as message text by reply-keyboard buttons.
SHOP = "Shop / Store Product"
ADD_BALANCE = "Add Balance"
MY_PROFILE = "My Profile"
HOW_TO_USE = "How To Use"
LUCKY = "Lucky"
SHARE = "Share"
SUPPORT = "Support"
DOWNLOAD = "Download File"
NON_ROOT = "NON ROOT"
ANDROID_ROOT = "ANDROID ROOT"
IPHONE = "OIS/IPHONE"
BACK_MENU = "Back to Menu"
CANCEL = "❌ Cancel"

CATEGORY_CHOICES = (NON_ROOT, ANDROID_ROOT, IPHONE)


# ================= DATABASE =================
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 20000")
    return conn


@contextmanager
def db_connection():
    """Connection context that always closes SQLite handles."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def db_one(query: str, params: tuple = ()) -> sqlite3.Row | None:
    with db_connection() as conn:
        return conn.execute(query, params).fetchone()


def db_all(query: str, params: tuple = ()) -> list[sqlite3.Row]:
    with db_connection() as conn:
        return conn.execute(query, params).fetchall()


def db_execute(query: str, params: tuple = ()) -> int:
    with db_connection() as conn:
        cur = conn.execute(query, params)
        return cur.rowcount


def db_setting(key: str, default: str = "") -> str:
    row = db_one("SELECT value FROM settings WHERE key = ?", (key,))
    return str(row["value"]) if row and row["value"] is not None else default


def set_setting(key: str, value: str) -> None:
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    """Create tables and safely add columns when upgrading an older elite_x.db."""
    with db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                balance REAL NOT NULL DEFAULT 0,
                is_reseller INTEGER NOT NULL DEFAULT 0,
                reseller_parent_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS product_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                key_text TEXT NOT NULL,
                is_used INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS member_prices (
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                price REAL NOT NULL,
                PRIMARY KEY(user_id, product_id)
            );
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                duration_days INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS payment_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'awaiting_proof',
                proof TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                processed_at TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS coupons (
                code TEXT PRIMARY KEY,
                amount REAL NOT NULL,
                max_uses INTEGER NOT NULL,
                used_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS coupon_redemptions (
                code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                redeemed_at TEXT NOT NULL,
                PRIMARY KEY(code, user_id)
            );
            """
        )

        # Migrate existing databases created by the originally uploaded bot.py.
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "reseller_parent_id" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN reseller_parent_id INTEGER")

        defaults = {
            "maintenance_mode": "OFF",
            "panel_maintenance": "OFF",
            "payment_gateways_enabled": "ON",
            "welcome_gif": "",  # legacy key; new uploads also store media type
            "welcome_media_file_id": "",
            "welcome_media_type": "animation",
            "category_gif": "",  # legacy key
            "category_media_file_id": "",
            "category_media_type": "animation",
            "panel_demo_file_id": "",
            "panel_demo_media_type": "animation",
            "support_link": "",
            "howto_link": "",
            "download_link": "",
            "files_link": "",
            "paytm_payment": "",
            "fampay_payment": "",
            "welcome_text": (
                "🛒 <b>ELITE X CONFIG STORE</b> 🛒\n\n"
                "👑 <b>Welcome, {name}!</b>\n\n"
                "⬆️ <b>STORE HIGHLIGHTS</b> ⬆️\n"
                "🎮 Premium Game Keys\n🐼 Instant Delivery 24/7\n"
                "💯 100% Secure Payment\n🛍 Best Prices Guaranteed\n"
                "🇮🇳 Safe And Trusted\n✅ Professional Support\n\n"
                "💰 <b>Wallet Balance:</b> ₹{balance}\n\n"
                "🔥 <b>Tap Shop Now to Start!</b>"
            ),
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                (key, value),
            )
        # Clear only known dummy links from the original sample source; preserve real configured links.
        fake_links = {
            "support_link": "https://t.me/YourSupport",
            "howto_link": "https://t.me/YourChannel",
            "download_link": "https://t.me/YourFiles",
        }
        for key, placeholder in fake_links.items():
            conn.execute("UPDATE settings SET value = '' WHERE key = ? AND value = ?", (key, placeholder))

        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_keys_product_used ON product_keys(product_id, is_used)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deposits_user ON payment_requests(user_id)")


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def active_bot() -> Bot:
    if bot is None:
        raise RuntimeError("Bot has not been initialized. Set BOT_TOKEN and start the bot.")
    return bot


# ================= FSM STATES =================
class AdminStates(StatesGroup):
    wait_welcome_media = State()
    wait_category_media = State()
    wait_panel_demo_media = State()
    wait_welcome_text = State()
    wait_support_link = State()
    wait_howto_link = State()
    wait_files_link = State()
    wait_paytm_payment = State()
    wait_fampay_payment = State()

    wait_direct_reseller_id = State()
    wait_custom_user_id = State()
    wait_custom_product_id = State()
    wait_custom_price = State()
    wait_remove_custom_user_id = State()
    wait_remove_custom_product_id = State()

    wait_add_balance_user_id = State()
    wait_add_balance_amount = State()
    wait_remove_balance_user_id = State()
    wait_remove_balance_amount = State()
    wait_check_balance_user_id = State()
    wait_bulk_balance_amount = State()

    wait_product_category = State()
    wait_product_name = State()
    wait_product_price = State()
    wait_product_keys = State()
    wait_remove_product_id = State()
    wait_add_keys_product_id = State()
    wait_add_keys_lines = State()
    wait_pid_old = State()
    wait_pid_new = State()
    wait_plan_name = State()
    wait_plan_price = State()
    wait_plan_days = State()
    wait_remove_plan_id = State()
    wait_remove_key_id = State()

    wait_reseller_add_id = State()
    wait_reseller_remove_id = State()
    wait_reseller_view_id = State()
    wait_reseller_up_user_id = State()
    wait_reseller_up_parent_id = State()

    wait_broadcast = State()
    wait_coupon_amount = State()
    wait_coupon_uses = State()


class UserStates(StatesGroup):
    wait_deposit_amount = State()
    wait_deposit_proof = State()


MEDIA_STATES = {
    AdminStates.wait_welcome_media.state,
    AdminStates.wait_category_media.state,
    AdminStates.wait_panel_demo_media.state,
}


# ================= REPLY KEYBOARDS (SCREENSHOT-STYLE) =================
def button(label: str, style: str = "primary") -> KeyboardButton:
    return KeyboardButton(text=label, style=style)


def keyboard(rows: list[list[KeyboardButton]], *, persistent: bool = True) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=persistent,
        input_field_placeholder="Choose an option…",
    )


def main_keyboard() -> ReplyKeyboardMarkup:
    return keyboard([
        [button(SHOP, "danger")],
        [button(ADD_BALANCE, "success"), button(MY_PROFILE, "primary")],
        [button(HOW_TO_USE, "primary"), button(LUCKY, "success")],
        [button(SHARE, "primary"), button(SUPPORT, "primary")],
        [button(DOWNLOAD, "success")],
    ])


def category_keyboard() -> ReplyKeyboardMarkup:
    return keyboard([
        [button(NON_ROOT, "primary")],
        [button(ANDROID_ROOT, "primary")],
        [button(IPHONE, "primary")],
        [button(BACK_MENU, "danger")],
    ])


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return keyboard([[button(CANCEL, "danger")]], persistent=False)


def admin_keyboard(page: int = 1) -> ReplyKeyboardMarkup:
    if page == 1:
        rows = [
            [button("Maintenance Mode", "danger")],
            [button("Panel Maintenance", "danger")],
            [button("Direct Reseller (by User ID)", "success")],
            [button("Member Custom Price", "success"), button("Remove Member Price", "danger")],
            [button("📁 Set Files Channel Link", "primary")],
            [button("Set Payment (Paytm Bus)", "primary"), button("Set Payment (FamPay)", "primary")],
            [button("💳 Payment Gateways ON/OFF", "success")],
            [button("API Record / Connection Check", "success")],
            [button("Set How-To-Use Link", "primary")],
            [button("Set Support Link", "danger")],
            [button("🎬 Shop Welcome GIF / Video", "primary")],
            [button("📸 Category GIF / Video", "primary")],
            [button("Panel Video Demo", "success")],
            [button("✏️ Edit Welcome Text", "primary")],
            [button("🤖 AI Support Manager", "success")],
            [button("➡️ Next Page (Products & Users)", "primary")],
        ]
    else:
        rows = [
            [button("Add Product", "success"), button("Remove Product", "danger")],
            [button("📦 Manage Products", "primary")],
            [button("⚡ Quick Add API Key", "success")],
            [button("🔑 External Key", "primary")],
            [button("🌐 Multi Website (API)", "primary"), button("🆔 PID Badlo", "primary")],
            [button("Add Plan", "primary"), button("Remove Plan", "danger")],
            [button("Add Key", "success"), button("Remove Key", "danger")],
            [button("Add Bal", "success"), button("Remove Bal", "danger"), button("Check Bal", "primary")],
            [button("👥 All Users Balance", "primary")],
            [button("Add Bal To All Users", "success")],
            [button("💰 All Deposit History", "primary")],
            [button("Add Reseller", "success"), button("Remove Reseller", "danger"), button("View Role", "primary")],
            [button("Set Reseller Up", "primary"), button("All Keys", "success"), button("Total Users", "primary")],
            [button("Broadcast System Terminal", "primary")],
            [button("Generate Coupon", "success"), button("View Coupons", "primary")],
            [button("User ID / Bot & Admin Username", "primary")],
            [button("⬅️ Back", "danger")],
        ]
    return keyboard(rows)


def product_inline_keyboard(products: list[sqlite3.Row]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for product in products:
        pid = int(product["id"])
        name = str(product["name"])
        price = float(product["price"])
        stock = int(product["stock"] or 0)
        label = f"{name[:28]} — ₹{price:g} | Stock {stock}"
        rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"buy_{pid}",
            style="success" if stock > 0 else "danger",
        )])
    rows.append([InlineKeyboardButton(text="Back to Categories", callback_data="show_categories")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def deposit_action_keyboard(deposit_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Approve Deposit", callback_data=f"dep_approve_{deposit_id}", style="success"),
        InlineKeyboardButton(text="Reject Deposit", callback_data=f"dep_reject_{deposit_id}", style="danger"),
    ]])


# ================= MESSAGE / MENU HELPERS =================
async def safe_send_media(
    message: Message,
    file_id: str,
    media_type: str,
    caption: str,
    reply_markup: ReplyKeyboardMarkup | InlineKeyboardMarkup | None = None,
) -> bool:
    try:
        if media_type == "video":
            await message.answer_video(file_id, caption=caption, reply_markup=reply_markup)
        else:
            await message.answer_animation(file_id, caption=caption, reply_markup=reply_markup)
        return True
    except Exception:
        logging.exception("Could not send saved %s media", media_type)
        return False


def get_welcome_text(user_id: int) -> str:
    user = db_one("SELECT first_name, balance FROM users WHERE user_id = ?", (user_id,))
    name = html.escape(str(user["first_name"] or "User")) if user else "User"
    balance = float(user["balance"] or 0) if user else 0.0
    template = db_setting("welcome_text") or "Welcome, {name}! Wallet Balance: ₹{balance}"
    # replace() avoids errors if a custom template contains unrelated braces.
    return template.replace("{name}", name).replace("{balance}", f"{balance:.2f}")


async def show_main_menu(message: Message) -> None:
    text = get_welcome_text(message.from_user.id)
    media_id = db_setting("welcome_media_file_id") or db_setting("welcome_gif")
    media_type = db_setting("welcome_media_type", "animation")
    sent = False
    if media_id:
        sent = await safe_send_media(message, media_id, media_type, text, main_keyboard())
    if not sent:
        try:
            await message.answer(text, reply_markup=main_keyboard())
        except TelegramBadRequest:
            # A malformed admin-edited HTML template should not break /start.
            await message.answer(html.escape(text), reply_markup=main_keyboard(), parse_mode=None)


async def show_categories(message: Message) -> None:
    text = "🛒 <b>PRODUCT STORE — SHOP</b>\n\n📱 <b>Select your device type:</b>"
    media_id = db_setting("category_media_file_id") or db_setting("category_gif")
    media_type = db_setting("category_media_type", "animation")
    sent = False
    if media_id:
        sent = await safe_send_media(message, media_id, media_type, text, category_keyboard())
    if not sent:
        await message.answer(text, reply_markup=category_keyboard())


async def show_admin_panel(message: Message, page: int = 1) -> None:
    heading = (
        "📙 <b>Select an operational control terminal module:</b>"
        if page == 1 else
        "📙 <b>Select an operational control terminal module (Page 2):</b>"
    )
    await message.answer(heading, reply_markup=admin_keyboard(page))


async def admin_prompt(message: Message, state: FSMContext, state_to_set: State, prompt: str, page: int = 1) -> None:
    await state.clear()
    await state.update_data(return_page=page)
    await state.set_state(state_to_set)
    await message.answer(prompt, reply_markup=cancel_keyboard())


async def finish_admin(message: Message, state: FSMContext, note: str) -> None:
    data = await state.get_data()
    page = int(data.get("return_page", 1))
    await state.clear()
    await message.answer(note)
    await show_admin_panel(message, page)


async def ensure_user(message: Message) -> None:
    if not message.from_user:
        return
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO users(user_id, first_name, username) VALUES(?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET first_name=excluded.first_name, username=excluded.username",
            (message.from_user.id, message.from_user.first_name, message.from_user.username),
        )


def valid_url(value: str) -> bool:
    value = value.strip()
    return value.startswith("https://") or value.startswith("http://")


def number_from_text(value: str, *, allow_zero: bool = False) -> float | None:
    try:
        num = float(value.strip().replace(",", ""))
        if num < 0 or (not allow_zero and num <= 0):
            return None
        return num
    except (ValueError, AttributeError):
        return None


def category_name(value: str) -> bool:
    return value in CATEGORY_CHOICES


# ================= START / COMMANDS =================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await ensure_user(message)
    if not is_admin(message.from_user.id) and (
        db_setting("maintenance_mode") == "ON" or db_setting("panel_maintenance") == "ON"
    ):
        await message.answer("🛠 <b>Store is under maintenance. Please try again later.</b>")
        return
    await show_main_menu(message)


@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await show_admin_panel(message, 1)


@dp.message(Command("redeem"))
async def redeem_coupon_command(message: Message) -> None:
    await ensure_user(message)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Use: <code>/redeem COUPONCODE</code>")
        return
    code = parts[1].strip().upper()
    user_id = message.from_user.id
    try:
        with db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            coupon = conn.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone()
            if not coupon:
                conn.rollback()
                await message.answer("❌ Coupon not found.")
                return
            if int(coupon["used_count"]) >= int(coupon["max_uses"]):
                conn.rollback()
                await message.answer("❌ This coupon has reached its use limit.")
                return
            already = conn.execute(
                "SELECT 1 FROM coupon_redemptions WHERE code = ? AND user_id = ?", (code, user_id)
            ).fetchone()
            if already:
                conn.rollback()
                await message.answer("❌ You have already used this coupon.")
                return
            conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (coupon["amount"], user_id))
            conn.execute("UPDATE coupons SET used_count = used_count + 1 WHERE code = ?", (code,))
            conn.execute(
                "INSERT INTO coupon_redemptions(code, user_id, redeemed_at) VALUES(?, ?, ?)",
                (code, user_id, now_iso()),
            )
            conn.commit()
        await message.answer(f"✅ Coupon redeemed. ₹{float(coupon['amount']):.2f} added to your wallet.")
    except sqlite3.Error:
        logging.exception("Coupon redemption failed")
        await message.answer("❌ Coupon could not be redeemed right now. Please try again.")


# ================= PRODUCT PURCHASE CALLBACKS =================
@dp.callback_query(F.data == "show_categories")
async def callback_show_categories(call: CallbackQuery) -> None:
    await call.answer()
    if not call.message:
        return
    await show_categories(call.message)


@dp.callback_query(F.data.startswith("buy_"))
async def callback_buy_product(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer("Unable to open this product.", show_alert=True)
        return
    try:
        product_id = int((call.data or "").split("_", 1)[1])
    except (ValueError, IndexError):
        await call.answer("Invalid product ID.", show_alert=True)
        return

    result, details = purchase_product(call.from_user.id, product_id)
    if not result:
        await call.answer(details, show_alert=True)
        return
    await call.answer("Purchase successful")
    await call.message.answer(details, reply_markup=main_keyboard())


def purchase_product(user_id: int, product_id: int) -> tuple[bool, str]:
    """Atomically charge wallet, consume one unused key, and update stock."""
    try:
        with db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
            product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if not user or not product:
                conn.rollback()
                return False, "❌ User or product not found."
            key_row = conn.execute(
                "SELECT id, key_text FROM product_keys WHERE product_id = ? AND is_used = 0 ORDER BY id LIMIT 1",
                (product_id,),
            ).fetchone()
            if not key_row:
                conn.execute("UPDATE products SET stock = 0 WHERE id = ?", (product_id,))
                conn.commit()
                return False, "❌ This product is out of stock."
            custom = conn.execute(
                "SELECT price FROM member_prices WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            ).fetchone()
            price = float(custom["price"] if custom else product["price"])
            if float(user["balance"] or 0) < price:
                conn.rollback()
                return False, "❌ Insufficient balance. Use Add Balance first."
            bal_update = conn.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
                (price, user_id, price),
            )
            key_update = conn.execute(
                "UPDATE product_keys SET is_used = 1 WHERE id = ? AND is_used = 0",
                (key_row["id"],),
            )
            if bal_update.rowcount != 1 or key_update.rowcount != 1:
                conn.rollback()
                return False, "❌ Stock or balance changed. Please try again."
            conn.execute("UPDATE products SET stock = MAX(stock - 1, 0) WHERE id = ?", (product_id,))
            conn.commit()
        return True, (
            "✅ <b>PURCHASE SUCCESSFUL</b>\n\n"
            f"📦 Product: {html.escape(str(product['name']))}\n"
            f"💰 Paid: ₹{price:.2f}\n"
            f"🔑 Key: <code>{html.escape(str(key_row['key_text']))}</code>\n\n"
            "<i>Thank you for your purchase!</i>"
        )
    except sqlite3.Error:
        logging.exception("Purchase failed")
        return False, "❌ Purchase failed due to a database error. Please contact support."


# ================= DEPOSIT APPROVAL CALLBACKS =================
@dp.callback_query(F.data.startswith("dep_approve_"))
async def approve_deposit(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Admin only.", show_alert=True)
        return
    try:
        deposit_id = int((call.data or "").rsplit("_", 1)[1])
        with db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            dep = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (deposit_id,)).fetchone()
            if not dep or dep["status"] != "pending":
                conn.rollback()
                await call.answer("Request not found or already handled.", show_alert=True)
                return
            conn.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (float(dep["amount"]), int(dep["user_id"])),
            )
            conn.execute(
                "UPDATE payment_requests SET status = 'approved', processed_at = ? WHERE id = ?",
                (now_iso(), deposit_id),
            )
            conn.commit()
        await call.answer("Deposit approved.", show_alert=True)
        try:
            await active_bot().send_message(
                int(dep["user_id"]),
                f"✅ Your deposit request #{deposit_id} was approved. ₹{float(dep['amount']):.2f} added to your wallet.",
            )
        except Exception:
            logging.exception("Could not notify user about approved deposit")
        if call.message:
            await call.message.edit_reply_markup(reply_markup=None)
    except (ValueError, sqlite3.Error):
        logging.exception("Deposit approval failed")
        await call.answer("Could not approve this deposit.", show_alert=True)


@dp.callback_query(F.data.startswith("dep_reject_"))
async def reject_deposit(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Admin only.", show_alert=True)
        return
    try:
        deposit_id = int((call.data or "").rsplit("_", 1)[1])
        with db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            dep = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (deposit_id,)).fetchone()
            if not dep or dep["status"] != "pending":
                conn.rollback()
                await call.answer("Request not found or already handled.", show_alert=True)
                return
            conn.execute(
                "UPDATE payment_requests SET status = 'rejected', processed_at = ? WHERE id = ?",
                (now_iso(), deposit_id),
            )
            conn.commit()
        await call.answer("Deposit rejected.", show_alert=True)
        try:
            await active_bot().send_message(
                int(dep["user_id"]),
                f"❌ Your deposit request #{deposit_id} was rejected. Please contact support if this is incorrect.",
            )
        except Exception:
            logging.exception("Could not notify user about rejected deposit")
        if call.message:
            await call.message.edit_reply_markup(reply_markup=None)
    except (ValueError, sqlite3.Error):
        logging.exception("Deposit rejection failed")
        await call.answer("Could not reject this deposit.", show_alert=True)


# ================= CENTRAL MESSAGE ROUTER =================
# All text/reply-keyboard clicks are routed here AFTER FSM state handling, so a
# product/category label cannot accidentally interrupt an active admin form.
@dp.message()
async def route_message(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return
    await ensure_user(message)
    current = await state.get_state()

    if current:
        if message.text and message.text.strip() in {CANCEL, "/cancel", "cancel", "Cancel"}:
            data = await state.get_data()
            page = int(data.get("return_page", 1))
            if current == UserStates.wait_deposit_proof.state and data.get("deposit_id"):
                db_execute(
                    "UPDATE payment_requests SET status = 'cancelled' WHERE id = ? AND user_id = ? AND status = 'awaiting_proof'",
                    (int(data["deposit_id"]), message.from_user.id),
                )
            await state.clear()
            if is_admin(message.from_user.id):
                await message.answer("Cancelled.")
                await show_admin_panel(message, page)
            else:
                await show_main_menu(message)
            return
        await process_state_message(message, state, current)
        return

    if not message.text:
        return
    text = message.text.strip()

    # Respect maintenance for user-facing store functions.
    if not is_admin(message.from_user.id) and (
        db_setting("maintenance_mode") == "ON" or db_setting("panel_maintenance") == "ON"
    ):
        if text not in {"/start", "/cancel"}:
            await message.answer("🛠 <b>Store is under maintenance. Please try again later.</b>")
        return

    # ----- Customer main menu -----
    if text == SHOP:
        await show_categories(message)
    elif text in CATEGORY_CHOICES:
        await show_category_products(message, text)
    elif text == BACK_MENU:
        await state.clear()
        await show_main_menu(message)
    elif text == MY_PROFILE:
        user = db_one("SELECT user_id, first_name, username, balance, is_reseller FROM users WHERE user_id = ?", (message.from_user.id,))
        if not user:
            await ensure_user(message)
            user = db_one("SELECT user_id, first_name, username, balance, is_reseller FROM users WHERE user_id = ?", (message.from_user.id,))
        role = "Reseller" if int(user["is_reseller"] or 0) else "Member"
        await message.answer(
            "👤 <b>MY PROFILE</b>\n\n"
            f"🆔 ID: <code>{int(user['user_id'])}</code>\n"
            f"👑 Name: {html.escape(str(user['first_name'] or 'User'))}\n"
            f"🔖 Role: {role}\n"
            f"💰 Balance: ₹{float(user['balance'] or 0):.2f}",
            reply_markup=main_keyboard(),
        )
    elif text == ADD_BALANCE:
        if db_setting("payment_gateways_enabled", "ON") != "ON":
            await message.answer("💳 Deposits are currently disabled. Please contact Support.", reply_markup=main_keyboard())
            return
        payment_info = []
        paytm = db_setting("paytm_payment")
        fampay = db_setting("fampay_payment")
        if paytm:
            payment_info.append("<b>Paytm:</b>\n" + html.escape(paytm))
        if fampay:
            payment_info.append("<b>FamPay:</b>\n" + html.escape(fampay))
        if not payment_info:
            await message.answer("❌ Payment instructions have not been configured by the admin yet. Please contact Support.", reply_markup=main_keyboard())
            return
        info = "\n\n".join(payment_info)
        await state.set_state(UserStates.wait_deposit_amount)
        await message.answer(
            "💰 <b>ADD BALANCE</b>\n\n" + info + "\n\nEnter the amount you want to deposit (₹):",
            reply_markup=cancel_keyboard(),
        )
    elif text == HOW_TO_USE:
        link = db_setting("howto_link")
        if valid_url(link):
            await message.answer(
                "📖 <b>HOW TO USE</b>\nTap the button to open the tutorial.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Watch Tutorial", url=link, style="primary")
                ]]),
            )
        else:
            await message.answer("📖 How-to link is not configured yet. Please contact Support.", reply_markup=main_keyboard())
    elif text == SUPPORT:
        link = db_setting("support_link")
        if valid_url(link):
            await message.answer(
                "📞 <b>SUPPORT CENTER</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Contact Support", url=link, style="primary")
                ]]),
            )
        else:
            await message.answer("📞 Support link is not configured yet. Please contact the admin.", reply_markup=main_keyboard())
    elif text == DOWNLOAD:
        link = db_setting("files_link") or db_setting("download_link")
        if valid_url(link):
            await message.answer(
                "📥 <b>DOWNLOAD FILES</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Download Files", url=link, style="success")
                ]]),
            )
        else:
            await message.answer("📥 Download link is not configured yet.", reply_markup=main_keyboard())
    elif text == SHARE:
        try:
            me = await active_bot().get_me()
            if me.username:
                link = f"https://t.me/{me.username}?start=share"
                await message.answer(f"🔗 Share this bot with friends:\n{link}", reply_markup=main_keyboard())
            else:
                await message.answer("Could not create a share link for this bot.", reply_markup=main_keyboard())
        except Exception:
            logging.exception("Share link lookup failed")
            await message.answer("Could not create a share link right now.", reply_markup=main_keyboard())
    elif text == LUCKY:
        await message.answer(
            "🎁 <b>Lucky</b>\nThis project does not contain a configured lucky-draw/reward engine yet. No wallet amount was changed.",
            reply_markup=main_keyboard(),
        )

    # ----- Admin page navigation and toggles -----
    elif text == "➡️ Next Page (Products & Users)" and is_admin(message.from_user.id):
        await show_admin_panel(message, 2)
    elif text == "⬅️ Back" and is_admin(message.from_user.id):
        await show_admin_panel(message, 1)
    elif text == "Maintenance Mode" and is_admin(message.from_user.id):
        new = "OFF" if db_setting("maintenance_mode") == "ON" else "ON"
        set_setting("maintenance_mode", new)
        await message.answer(f"✅ Maintenance Mode is now <b>{new}</b>.", reply_markup=admin_keyboard(1))
    elif text == "Panel Maintenance" and is_admin(message.from_user.id):
        new = "OFF" if db_setting("panel_maintenance") == "ON" else "ON"
        set_setting("panel_maintenance", new)
        await message.answer(f"✅ Panel Maintenance is now <b>{new}</b>.", reply_markup=admin_keyboard(1))
    elif text == "💳 Payment Gateways ON/OFF" and is_admin(message.from_user.id):
        new = "OFF" if db_setting("payment_gateways_enabled", "ON") == "ON" else "ON"
        set_setting("payment_gateways_enabled", new)
        await message.answer(f"✅ Payment Gateways are now <b>{new}</b>.", reply_markup=admin_keyboard(1))
    elif text == "Direct Reseller (by User ID)" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_direct_reseller_id, "Enter the existing user's Telegram ID to make them a reseller:", 1)
    elif text == "Member Custom Price" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_custom_user_id, "Enter the member's Telegram ID:", 1)
    elif text == "Remove Member Price" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_remove_custom_user_id, "Enter the member's Telegram ID:", 1)
    elif text == "📁 Set Files Channel Link" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_files_link, "Send the Files Channel URL (https://…). Type clear to remove it:", 1)
    elif text == "Set Payment (Paytm Bus)" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_paytm_payment, "Send Paytm payment instructions (UPI ID/link/details), or type clear:", 1)
    elif text == "Set Payment (FamPay)" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_fampay_payment, "Send FamPay payment instructions (UPI ID/link/details), or type clear:", 1)
    elif text == "API Record / Connection Check" and is_admin(message.from_user.id):
        try:
            me = await active_bot().get_me()
            db_one("SELECT 1 AS ok")
            await message.answer(
                "✅ <b>Connection Check</b>\nDatabase: OK\nTelegram API: OK\n"
                f"Bot username: @{html.escape(me.username or 'unknown')}\nAdmin ID: <code>{ADMIN_ID}</code>",
                reply_markup=admin_keyboard(1),
            )
        except Exception as exc:
            logging.exception("Connection check failed")
            await message.answer(f"❌ Connection check failed: {html.escape(str(exc)[:250])}", reply_markup=admin_keyboard(1))
    elif text == "Set How-To-Use Link" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_howto_link, "Send the How-To-Use URL (https://…):", 1)
    elif text == "Set Support Link" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_support_link, "Send the Support URL (https://…):", 1)
    elif text == "🎬 Shop Welcome GIF / Video" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_welcome_media, "Send a GIF or video for the main welcome screen. Type clear to remove the media:", 1)
    elif text == "📸 Category GIF / Video" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_category_media, "Send a GIF or video for the category screen. Type clear to remove the media:", 1)
    elif text == "Panel Video Demo" and is_admin(message.from_user.id):
        existing_id = db_setting("panel_demo_file_id")
        if existing_id:
            await safe_send_media(message, existing_id, db_setting("panel_demo_media_type", "animation"), "🎬 <b>Current Panel Demo</b>")
        await admin_prompt(message, state, AdminStates.wait_panel_demo_media, "Send a new GIF/video to set or replace the panel demo, or type clear:", 1)
    elif text == "✏️ Edit Welcome Text" and is_admin(message.from_user.id):
        current_text = db_setting("welcome_text")
        await admin_prompt(
            message, state, AdminStates.wait_welcome_text,
            "✏️ <b>Current Welcome Text:</b>\n\n" + current_text +
            "\n\nSend the new text (placeholders: {name}, {balance}). HTML formatting is allowed:", 1,
        )
    elif text == "🤖 AI Support Manager" and is_admin(message.from_user.id):
        await message.answer(
            "⚠️ <b>AI Support Manager is not integrated in this source file.</b>\n"
            "There is no AI provider, API endpoint, model, or credentials configured here, so the bot will not claim that AI is active.",
            reply_markup=admin_keyboard(1),
        )

    # ----- Admin page 2: products and keys -----
    elif text == "Add Product" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_product_category, "Choose a category for the new product:", 2)
        await message.answer("Categories:", reply_markup=keyboard([
            [button(NON_ROOT, "primary")], [button(ANDROID_ROOT, "primary")], [button(IPHONE, "primary")], [button(CANCEL, "danger")]
        ], persistent=False))
    elif text == "Remove Product" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_remove_product_id, "Enter the product ID to remove. Its key inventory and member-price overrides will also be deleted:", 2)
    elif text == "📦 Manage Products" and is_admin(message.from_user.id):
        await send_products_report(message, page=2)
    elif text in {"⚡ Quick Add API Key", "🔑 External Key", "Add Key"} and is_admin(message.from_user.id):
        mode = {"⚡ Quick Add API Key": "Quick Add API Key", "🔑 External Key": "External Key (local inventory)", "Add Key": "Add Key"}[text]
        await state.clear()
        await state.update_data(return_page=2, key_mode=mode)
        await state.set_state(AdminStates.wait_add_keys_product_id)
        await message.answer(f"{mode}: enter the existing product ID. This adds local inventory keys; it does not call a third-party API.", reply_markup=cancel_keyboard())
    elif text == "🌐 Multi Website (API)" and is_admin(message.from_user.id):
        await message.answer(
            "⚠️ <b>Multi Website (API) cannot be connected from the current source alone.</b>\n"
            "The file contains no provider URL, authentication scheme, response format, or API documentation. This button now explains the blocker instead of falsely reporting success.",
            reply_markup=admin_keyboard(2),
        )
    elif text == "🆔 PID Badlo" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_pid_old, "Enter the current product ID:", 2)
    elif text == "Add Plan" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_plan_name, "Enter the plan name:", 2)
    elif text == "Remove Plan" and is_admin(message.from_user.id):
        plans = db_all("SELECT id, name, price, duration_days FROM plans ORDER BY id DESC LIMIT 30")
        report = "📋 <b>Plans</b>\n\n" + ("\n".join(
            f"ID <code>{r['id']}</code> — {html.escape(str(r['name']))} — ₹{float(r['price']):.2f} / {int(r['duration_days'])} days"
            for r in plans
        ) or "No plans created yet.")
        await message.answer(report[:3900], reply_markup=admin_keyboard(2))
        await admin_prompt(message, state, AdminStates.wait_remove_plan_id, "Enter the plan ID to remove:", 2)
    elif text == "Remove Key" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_remove_key_id, "Enter the key record ID to delete. Only unused keys can be removed:", 2)
    elif text == "Add Bal" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_add_balance_user_id, "Enter the existing user's Telegram ID:", 2)
    elif text == "Remove Bal" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_remove_balance_user_id, "Enter the existing user's Telegram ID:", 2)
    elif text == "Check Bal" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_check_balance_user_id, "Enter the user's Telegram ID:", 2)
    elif text == "👥 All Users Balance" and is_admin(message.from_user.id):
        rows = db_all("SELECT user_id, first_name, balance FROM users ORDER BY user_id DESC LIMIT 35")
        report = "👥 <b>Users Balance (latest 35)</b>\n\n" + ("\n".join(
            f"<code>{r['user_id']}</code> — {html.escape(str(r['first_name'] or 'User'))}: ₹{float(r['balance'] or 0):.2f}"
            for r in rows
        ) or "No users found.")
        await message.answer(report[:3900], reply_markup=admin_keyboard(2))
    elif text == "Add Bal To All Users" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_bulk_balance_amount, "Enter the amount (₹) to add to every registered user:", 2)
    elif text == "💰 All Deposit History" and is_admin(message.from_user.id):
        rows = db_all("SELECT id, user_id, amount, status, created_at FROM payment_requests ORDER BY id DESC LIMIT 25")
        report = "💰 <b>Deposit History (latest 25)</b>\n\n" + ("\n".join(
            f"#{r['id']} | User <code>{r['user_id']}</code> | ₹{float(r['amount']):.2f} | {html.escape(str(r['status']))} | {html.escape(str(r['created_at']))}"
            for r in rows
        ) or "No deposit requests yet.")
        await message.answer(report[:3900], reply_markup=admin_keyboard(2))
    elif text == "Add Reseller" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_reseller_add_id, "Enter the existing user's Telegram ID to grant reseller role:", 2)
    elif text == "Remove Reseller" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_reseller_remove_id, "Enter the user's Telegram ID to remove reseller role:", 2)
    elif text == "View Role" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_reseller_view_id, "Enter the user's Telegram ID:", 2)
    elif text == "Set Reseller Up" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_reseller_up_user_id, "Enter the user's Telegram ID:", 2)
    elif text == "All Keys" and is_admin(message.from_user.id):
        rows = db_all(
            "SELECT k.id AS key_id, k.product_id, k.is_used, k.key_text, p.name "
            "FROM product_keys k LEFT JOIN products p ON p.id = k.product_id ORDER BY k.id DESC LIMIT 25"
        )
        report = "🔑 <b>Key Inventory (latest 25)</b>\n\n" + ("\n".join(
            f"Key ID <code>{r['key_id']}</code> | Product <code>{r['product_id']}</code> "
            f"({html.escape(str(r['name'] or 'deleted product'))}) | {'USED' if r['is_used'] else 'AVAILABLE'}\n"
            f"<code>{html.escape(str(r['key_text'])[:90])}</code>"
            for r in rows
        ) or "No keys found.")
        await message.answer(report[:3900], reply_markup=admin_keyboard(2))
    elif text == "Total Users" and is_admin(message.from_user.id):
        count = db_one("SELECT COUNT(*) AS n FROM users")["n"]
        await message.answer(f"👥 Total registered users: <b>{int(count)}</b>", reply_markup=admin_keyboard(2))
    elif text == "Broadcast System Terminal" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_broadcast, "Send the text, photo, GIF, video or document to copy to all registered users:", 2)
    elif text == "Generate Coupon" and is_admin(message.from_user.id):
        await admin_prompt(message, state, AdminStates.wait_coupon_amount, "Enter the wallet amount this coupon should add (₹):", 2)
    elif text == "View Coupons" and is_admin(message.from_user.id):
        rows = db_all("SELECT code, amount, max_uses, used_count, created_at FROM coupons ORDER BY created_at DESC LIMIT 30")
        report = "🎟 <b>Coupons (latest 30)</b>\n\n" + ("\n".join(
            f"<code>{html.escape(str(r['code']))}</code> — ₹{float(r['amount']):.2f} — {int(r['used_count'])}/{int(r['max_uses'])} uses"
            for r in rows
        ) or "No coupons created yet.")
        await message.answer(report[:3900], reply_markup=admin_keyboard(2))
    elif text == "User ID / Bot & Admin Username" and is_admin(message.from_user.id):
        try:
            me = await active_bot().get_me()
            await message.answer(
                "ℹ️ <b>Bot Information</b>\n"
                f"Bot name: {html.escape(me.full_name)}\n"
                f"Bot username: @{html.escape(me.username or 'unknown')}\n"
                f"Admin ID: <code>{ADMIN_ID}</code>\n"
                f"Your ID: <code>{message.from_user.id}</code>",
                reply_markup=admin_keyboard(2),
            )
        except Exception:
            logging.exception("Could not get bot info")
            await message.answer("Could not retrieve bot information right now.", reply_markup=admin_keyboard(2))


async def show_category_products(message: Message, category: str) -> None:
    rows = db_all(
        "SELECT p.id, p.name, p.price, "
        "(SELECT COUNT(*) FROM product_keys k WHERE k.product_id = p.id AND k.is_used = 0) AS live_stock "
        "FROM products p WHERE p.category = ? ORDER BY p.id",
        (category,),
    )
    if not rows:
        await message.answer(
            f"📦 <b>{html.escape(category)}</b>\n\n❌ No products found in this category.",
            reply_markup=category_keyboard(),
        )
        return
    # Show actual unused keys, rather than trusting a stale stock number.
    display_rows = []
    for row in rows:
        # The callback keyboard expects a 'stock' field. Use tiny dict-backed rows here.
        display_rows.append({"id": row["id"], "name": row["name"], "price": row["price"], "stock": row["live_stock"]})
    await message.answer(
        f"📦 <b>{html.escape(category)} PRODUCTS</b>\n\nSelect a package to buy:",
        reply_markup=product_inline_keyboard(display_rows),
    )


async def send_products_report(message: Message, page: int = 2) -> None:
    rows = db_all(
        "SELECT p.id, p.category, p.name, p.price, "
        "(SELECT COUNT(*) FROM product_keys k WHERE k.product_id = p.id AND k.is_used = 0) AS live_stock "
        "FROM products p ORDER BY p.id DESC LIMIT 35"
    )
    report = "📦 <b>MANAGE PRODUCTS (latest 35)</b>\n\n" + ("\n".join(
        f"ID <code>{r['id']}</code> | {html.escape(str(r['category']))} | {html.escape(str(r['name']))}\n"
        f"Price ₹{float(r['price']):.2f} | Available keys: {int(r['live_stock'])}"
        for r in rows
    ) or "No products found.")
    await message.answer(report[:3900], reply_markup=admin_keyboard(page))


# ================= FSM STATE PROCESSOR =================
async def process_state_message(message: Message, state: FSMContext, current: str) -> None:
    user_id = message.from_user.id
    data = await state.get_data()
    text = (message.text or "").strip()
    admin = is_admin(user_id)

    # Media upload flow: distinguish animation GIFs from video file IDs.
    if current in MEDIA_STATES:
        if not admin:
            await state.clear()
            await message.answer("This action is available to admins only.")
            return
        if text.lower() == "clear":
            if current == AdminStates.wait_welcome_media.state:
                set_setting("welcome_media_file_id", "")
                set_setting("welcome_gif", "")
                set_setting("welcome_media_type", "animation")
                note = "✅ Welcome media removed."
            elif current == AdminStates.wait_category_media.state:
                set_setting("category_media_file_id", "")
                set_setting("category_gif", "")
                set_setting("category_media_type", "animation")
                note = "✅ Category media removed."
            else:
                set_setting("panel_demo_file_id", "")
                set_setting("panel_demo_media_type", "animation")
                note = "✅ Panel demo removed."
            await finish_admin(message, state, note)
            return
        if message.animation:
            file_id, media_type = message.animation.file_id, "animation"
        elif message.video:
            file_id, media_type = message.video.file_id, "video"
        else:
            await message.answer("❌ Please send a real Telegram GIF/animation or video, or type clear.", reply_markup=cancel_keyboard())
            return
        if current == AdminStates.wait_welcome_media.state:
            set_setting("welcome_media_file_id", file_id)
            set_setting("welcome_media_type", media_type)
            set_setting("welcome_gif", file_id)  # legacy compatibility
            note = f"✅ Welcome {('video' if media_type == 'video' else 'GIF')} saved."
        elif current == AdminStates.wait_category_media.state:
            set_setting("category_media_file_id", file_id)
            set_setting("category_media_type", media_type)
            set_setting("category_gif", file_id)
            note = f"✅ Category {('video' if media_type == 'video' else 'GIF')} saved."
        else:
            set_setting("panel_demo_file_id", file_id)
            set_setting("panel_demo_media_type", media_type)
            note = f"✅ Panel demo {('video' if media_type == 'video' else 'GIF')} saved."
        await finish_admin(message, state, note)
        return

    # Broadcast must accept non-text messages too.
    if current == AdminStates.wait_broadcast.state:
        if not admin:
            await state.clear()
            return
        users = db_all("SELECT user_id FROM users")
        sent = 0
        failed = 0
        for row in users:
            try:
                await message.send_copy(chat_id=int(row["user_id"]))
                sent += 1
                await asyncio.sleep(0.04)
            except Exception:
                failed += 1
        await finish_admin(message, state, f"✅ Broadcast finished. Sent: {sent}; failed: {failed}.")
        return

    # From here onward this form expects text input.
    if message.text is None and current != UserStates.wait_deposit_proof.state:
        await message.answer("Please send text for this step, or use Cancel.", reply_markup=cancel_keyboard())
        return
    if admin is False and current not in {UserStates.wait_deposit_amount.state, UserStates.wait_deposit_proof.state}:
        await state.clear()
        await message.answer("This admin operation is not available to users.")
        return

    # ----- User deposit flow (manual verification; no fake gateway integration) -----
    if current == UserStates.wait_deposit_amount.state:
        amount = number_from_text(text)
        if amount is None or amount > 1_000_000:
            await message.answer("❌ Enter a valid amount greater than ₹0 and no more than ₹10,00,000:", reply_markup=cancel_keyboard())
            return
        configured = bool(db_setting("paytm_payment") or db_setting("fampay_payment"))
        if not configured:
            await state.clear()
            await message.answer("❌ Payment instructions are not configured yet. Please contact Support.", reply_markup=main_keyboard())
            return
        with db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO payment_requests(user_id, amount, status, created_at) VALUES(?, ?, 'awaiting_proof', ?)",
                (user_id, amount, now_iso()),
            )
            deposit_id = int(cur.lastrowid)
        await state.update_data(deposit_id=deposit_id, deposit_amount=amount)
        await state.set_state(UserStates.wait_deposit_proof)
        await message.answer(
            f"✅ Deposit request <b>#{deposit_id}</b> created for ₹{amount:.2f}.\n\n"
            "Make the payment using the instructions above, then send the transaction/reference ID or a payment screenshot here. "
            "The admin will verify it manually before adding funds.",
            reply_markup=cancel_keyboard(),
        )
        return

    if current == UserStates.wait_deposit_proof.state:
        dep_id = int(data.get("deposit_id", 0))
        if not dep_id:
            await state.clear()
            await message.answer("Deposit session expired. Tap Add Balance to start again.", reply_markup=main_keyboard())
            return
        proof = text[:800] if message.text else ""
        if message.photo:
            proof = "photo file_id=" + message.photo[-1].file_id
        elif message.video:
            proof = "video file_id=" + message.video.file_id
        elif message.document:
            proof = "document file_id=" + message.document.file_id
        elif message.animation:
            proof = "animation file_id=" + message.animation.file_id
        if not proof:
            await message.answer("Send a transaction/reference ID or a payment screenshot/file.", reply_markup=cancel_keyboard())
            return
        with db_connection() as conn:
            cur = conn.execute(
                "UPDATE payment_requests SET proof = ?, status = 'pending' WHERE id = ? AND user_id = ? AND status = 'awaiting_proof'",
                (proof, dep_id, user_id),
            )
            if cur.rowcount != 1:
                await state.clear()
                await message.answer("This deposit request has expired or was already handled. Tap Add Balance to start again.", reply_markup=main_keyboard())
                return
        try:
            await message.send_copy(chat_id=ADMIN_ID)
        except Exception:
            logging.exception("Could not forward deposit proof to admin")
        dep = db_one("SELECT amount FROM payment_requests WHERE id = ?", (dep_id,))
        try:
            await active_bot().send_message(
                ADMIN_ID,
                "💳 <b>Deposit Verification</b>\n"
                f"Request: <code>#{dep_id}</code>\n"
                f"User: <code>{user_id}</code>\n"
                f"Amount: ₹{float(dep['amount']):.2f}\n\nReview the forwarded payment proof before approving.",
                reply_markup=deposit_action_keyboard(dep_id),
            )
        except Exception:
            logging.exception("Could not notify admin about deposit")
        await state.clear()
        await message.answer(f"✅ Proof submitted for request #{dep_id}. Funds will be added after admin verification.", reply_markup=main_keyboard())
        return

    # ----- Shared/admin form helpers -----
    if current == AdminStates.wait_welcome_text.state:
        if not text or len(text) > 3500:
            await message.answer("Send welcome text under 3500 characters.", reply_markup=cancel_keyboard())
            return
        set_setting("welcome_text", text)
        await finish_admin(message, state, "✅ Welcome text updated. Use /start to preview it.")

    elif current in {AdminStates.wait_support_link.state, AdminStates.wait_howto_link.state, AdminStates.wait_files_link.state}:
        setting_key = {
            AdminStates.wait_support_link.state: "support_link",
            AdminStates.wait_howto_link.state: "howto_link",
            AdminStates.wait_files_link.state: "files_link",
        }[current]
        if text.lower() == "clear" and current == AdminStates.wait_files_link.state:
            set_setting(setting_key, "")
            await finish_admin(message, state, "✅ Files Channel Link cleared.")
            return
        if not valid_url(text):
            await message.answer("❌ Please send a valid http:// or https:// URL.", reply_markup=cancel_keyboard())
            return
        set_setting(setting_key, text)
        await finish_admin(message, state, f"✅ {setting_key.replace('_', ' ').title()} saved.")

    elif current in {AdminStates.wait_paytm_payment.state, AdminStates.wait_fampay_payment.state}:
        key = "paytm_payment" if current == AdminStates.wait_paytm_payment.state else "fampay_payment"
        set_setting(key, "" if text.lower() == "clear" else text[:1000])
        await finish_admin(message, state, "✅ Payment instructions saved. Payments are still manually verified; no real payment gateway is connected.")

    elif current == AdminStates.wait_direct_reseller_id.state:
        target = parse_user_id(text)
        if target is None or not user_exists(target):
            await message.answer("❌ User ID is invalid or not registered. Ask that user to open the bot first.", reply_markup=cancel_keyboard())
            return
        db_execute("UPDATE users SET is_reseller = 1 WHERE user_id = ?", (target,))
        await finish_admin(message, state, f"✅ User {target} is now a reseller.")

    elif current == AdminStates.wait_custom_user_id.state:
        target = parse_user_id(text)
        if target is None or not user_exists(target):
            await message.answer("❌ User ID is invalid or not registered.", reply_markup=cancel_keyboard())
            return
        await state.update_data(target_user_id=target)
        await state.set_state(AdminStates.wait_custom_product_id)
        await message.answer("Enter the product ID for this member-specific price:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_custom_product_id.state:
        product_id = parse_positive_int(text)
        if product_id is None or not db_one("SELECT id FROM products WHERE id = ?", (product_id,)):
            await message.answer("❌ Product ID not found.", reply_markup=cancel_keyboard())
            return
        await state.update_data(target_product_id=product_id)
        await state.set_state(AdminStates.wait_custom_price)
        await message.answer("Enter the custom price in ₹:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_custom_price.state:
        price = number_from_text(text, allow_zero=True)
        if price is None or price > 1_000_000:
            await message.answer("❌ Enter a valid price between ₹0 and ₹10,00,000.", reply_markup=cancel_keyboard())
            return
        target = int(data["target_user_id"])
        pid = int(data["target_product_id"])
        with db_connection() as conn:
            conn.execute(
                "INSERT INTO member_prices(user_id, product_id, price) VALUES(?, ?, ?) "
                "ON CONFLICT(user_id, product_id) DO UPDATE SET price = excluded.price",
                (target, pid, price),
            )
        await finish_admin(message, state, f"✅ Custom price ₹{price:.2f} set for user {target}, product {pid}.")

    elif current == AdminStates.wait_remove_custom_user_id.state:
        target = parse_user_id(text)
        if target is None or not user_exists(target):
            await message.answer("❌ User ID is invalid or not registered.", reply_markup=cancel_keyboard())
            return
        await state.update_data(target_user_id=target)
        await state.set_state(AdminStates.wait_remove_custom_product_id)
        await message.answer("Enter the product ID whose custom price should be removed:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_remove_custom_product_id.state:
        pid = parse_positive_int(text)
        if pid is None:
            await message.answer("❌ Enter a valid product ID.", reply_markup=cancel_keyboard())
            return
        target = int(data["target_user_id"])
        deleted = db_execute("DELETE FROM member_prices WHERE user_id = ? AND product_id = ?", (target, pid))
        await finish_admin(message, state, "✅ Custom price removed." if deleted else "No custom price existed for that user/product.")

    elif current == AdminStates.wait_add_balance_user_id.state:
        target = parse_user_id(text)
        if target is None or not user_exists(target):
            await message.answer("❌ User ID is invalid or not registered.", reply_markup=cancel_keyboard())
            return
        await state.update_data(target_user_id=target)
        await state.set_state(AdminStates.wait_add_balance_amount)
        await message.answer("Enter the amount (₹) to add:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_add_balance_amount.state:
        amount = number_from_text(text)
        if amount is None or amount > 1_000_000:
            await message.answer("❌ Enter a valid positive amount up to ₹10,00,000.", reply_markup=cancel_keyboard())
            return
        target = int(data["target_user_id"])
        db_execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target))
        await finish_admin(message, state, f"✅ Added ₹{amount:.2f} to user {target}.")

    elif current == AdminStates.wait_remove_balance_user_id.state:
        target = parse_user_id(text)
        if target is None or not user_exists(target):
            await message.answer("❌ User ID is invalid or not registered.", reply_markup=cancel_keyboard())
            return
        await state.update_data(target_user_id=target)
        await state.set_state(AdminStates.wait_remove_balance_amount)
        await message.answer("Enter the amount (₹) to remove:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_remove_balance_amount.state:
        amount = number_from_text(text)
        if amount is None:
            await message.answer("❌ Enter a valid positive amount.", reply_markup=cancel_keyboard())
            return
        target = int(data["target_user_id"])
        with db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (target,)).fetchone()
            if not row or float(row["balance"]) < amount:
                conn.rollback()
                await message.answer("❌ User not found or balance is lower than that amount.", reply_markup=cancel_keyboard())
                return
            conn.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, target))
            conn.commit()
        await finish_admin(message, state, f"✅ Removed ₹{amount:.2f} from user {target}.")

    elif current == AdminStates.wait_check_balance_user_id.state:
        target = parse_user_id(text)
        row = db_one("SELECT balance, first_name, is_reseller FROM users WHERE user_id = ?", (target,)) if target else None
        if not row:
            await message.answer("❌ User ID is invalid or not registered.", reply_markup=cancel_keyboard())
            return
        await finish_admin(message, state, f"💰 User {target} ({html.escape(str(row['first_name'] or 'User'))}) balance: ₹{float(row['balance']):.2f}; role: {'Reseller' if row['is_reseller'] else 'Member'}.")

    elif current == AdminStates.wait_bulk_balance_amount.state:
        amount = number_from_text(text, allow_zero=False)
        if amount is None or amount > 100_000:
            await message.answer("❌ Enter a valid amount up to ₹1,00,000.", reply_markup=cancel_keyboard())
            return
        with db_connection() as conn:
            cur = conn.execute("UPDATE users SET balance = balance + ?", (amount,))
            count = cur.rowcount
        await finish_admin(message, state, f"✅ Added ₹{amount:.2f} to {count} registered users.")

    elif current == AdminStates.wait_product_category.state:
        if not category_name(text):
            await message.answer("Choose one of the category buttons above.", reply_markup=keyboard([
                [button(NON_ROOT, "primary")], [button(ANDROID_ROOT, "primary")], [button(IPHONE, "primary")], [button(CANCEL, "danger")]
            ], persistent=False))
            return
        await state.update_data(product_category=text)
        await state.set_state(AdminStates.wait_product_name)
        await message.answer("Enter product name:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_product_name.state:
        if not text or len(text) > 100:
            await message.answer("Product name must be 1–100 characters.", reply_markup=cancel_keyboard())
            return
        await state.update_data(product_name=text)
        await state.set_state(AdminStates.wait_product_price)
        await message.answer("Enter the product price in ₹:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_product_price.state:
        price = number_from_text(text, allow_zero=True)
        if price is None or price > 1_000_000:
            await message.answer("❌ Enter a valid price from ₹0 to ₹10,00,000.", reply_markup=cancel_keyboard())
            return
        await state.update_data(product_price=price)
        await state.set_state(AdminStates.wait_product_keys)
        await message.answer("Send product keys/codes, one per line. Available stock will be calculated from the keys sent:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_product_keys.state:
        keys = unique_nonempty_lines(text)
        if not keys:
            await message.answer("❌ At least one non-empty key is required. Send one key per line:", reply_markup=cancel_keyboard())
            return
        with db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO products(category, name, price, stock) VALUES(?, ?, ?, ?)",
                (data["product_category"], data["product_name"], float(data["product_price"]), len(keys)),
            )
            pid = int(cur.lastrowid)
            conn.executemany("INSERT INTO product_keys(product_id, key_text, is_used) VALUES(?, ?, 0)", [(pid, key) for key in keys])
        await finish_admin(message, state, f"✅ Product added. ID: {pid}; name: {html.escape(data['product_name'])}; price: ₹{float(data['product_price']):.2f}; keys added: {len(keys)}.")

    elif current == AdminStates.wait_remove_product_id.state:
        pid = parse_positive_int(text)
        if pid is None or not db_one("SELECT id FROM products WHERE id = ?", (pid,)):
            await message.answer("❌ Product ID not found.", reply_markup=cancel_keyboard())
            return
        with db_connection() as conn:
            conn.execute("DELETE FROM product_keys WHERE product_id = ?", (pid,))
            conn.execute("DELETE FROM member_prices WHERE product_id = ?", (pid,))
            conn.execute("DELETE FROM products WHERE id = ?", (pid,))
        await finish_admin(message, state, f"✅ Product {pid} and its stored keys/member prices were removed.")

    elif current == AdminStates.wait_add_keys_product_id.state:
        pid = parse_positive_int(text)
        if pid is None or not db_one("SELECT id, name FROM products WHERE id = ?", (pid,)):
            await message.answer("❌ Product ID not found.", reply_markup=cancel_keyboard())
            return
        await state.update_data(target_product_id=pid)
        await state.set_state(AdminStates.wait_add_keys_lines)
        await message.answer("Send the new keys/codes, one per line:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_add_keys_lines.state:
        keys = unique_nonempty_lines(text)
        if not keys:
            await message.answer("❌ Send at least one key, one per line:", reply_markup=cancel_keyboard())
            return
        pid = int(data["target_product_id"])
        with db_connection() as conn:
            product = conn.execute("SELECT id FROM products WHERE id = ?", (pid,)).fetchone()
            if not product:
                await message.answer("❌ That product no longer exists. Start again.", reply_markup=admin_keyboard(2))
                await state.clear()
                return
            conn.executemany("INSERT INTO product_keys(product_id, key_text, is_used) VALUES(?, ?, 0)", [(pid, key) for key in keys])
            count = conn.execute("SELECT COUNT(*) AS n FROM product_keys WHERE product_id = ? AND is_used = 0", (pid,)).fetchone()["n"]
            conn.execute("UPDATE products SET stock = ? WHERE id = ?", (int(count), pid))
        await finish_admin(message, state, f"✅ Added {len(keys)} key(s) to product {pid}. Available keys: {int(count)}.")

    elif current == AdminStates.wait_pid_old.state:
        old_id = parse_positive_int(text)
        if old_id is None or not db_one("SELECT id FROM products WHERE id = ?", (old_id,)):
            await message.answer("❌ Current product ID not found.", reply_markup=cancel_keyboard())
            return
        await state.update_data(old_product_id=old_id)
        await state.set_state(AdminStates.wait_pid_new)
        await message.answer("Enter a new positive product ID that is not already used:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_pid_new.state:
        new_id = parse_positive_int(text)
        old_id = int(data["old_product_id"])
        if new_id is None or db_one("SELECT id FROM products WHERE id = ?", (new_id,)):
            await message.answer("❌ New product ID is invalid or already used.", reply_markup=cancel_keyboard())
            return
        with db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE product_keys SET product_id = ? WHERE product_id = ?", (new_id, old_id))
            conn.execute("UPDATE member_prices SET product_id = ? WHERE product_id = ?", (new_id, old_id))
            conn.execute("UPDATE products SET id = ? WHERE id = ?", (new_id, old_id))
            conn.commit()
        await finish_admin(message, state, f"✅ Product ID changed from {old_id} to {new_id}; linked keys and member prices were updated.")

    elif current == AdminStates.wait_plan_name.state:
        if not text or len(text) > 100:
            await message.answer("Plan name must be 1–100 characters.", reply_markup=cancel_keyboard())
            return
        await state.update_data(plan_name=text)
        await state.set_state(AdminStates.wait_plan_price)
        await message.answer("Enter plan price in ₹:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_plan_price.state:
        price = number_from_text(text, allow_zero=True)
        if price is None:
            await message.answer("Enter a valid plan price:", reply_markup=cancel_keyboard())
            return
        await state.update_data(plan_price=price)
        await state.set_state(AdminStates.wait_plan_days)
        await message.answer("Enter plan duration in whole days:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_plan_days.state:
        days = parse_positive_int(text)
        if days is None or days > 36500:
            await message.answer("Enter a positive number of days (max 36500):", reply_markup=cancel_keyboard())
            return
        with db_connection() as conn:
            cur = conn.execute("INSERT INTO plans(name, price, duration_days) VALUES(?, ?, ?)", (data["plan_name"], data["plan_price"], days))
            plan_id = int(cur.lastrowid)
        await finish_admin(message, state, f"✅ Plan created. ID: {plan_id}; {html.escape(data['plan_name'])}; ₹{float(data['plan_price']):.2f}; {days} days.")

    elif current == AdminStates.wait_remove_plan_id.state:
        plan_id = parse_positive_int(text)
        removed = db_execute("DELETE FROM plans WHERE id = ?", (plan_id,)) if plan_id else 0
        await finish_admin(message, state, f"✅ Plan {plan_id} removed." if removed else "Plan ID not found.")

    elif current == AdminStates.wait_remove_key_id.state:
        key_id = parse_positive_int(text)
        if key_id is None:
            await message.answer("Enter a valid key record ID:", reply_markup=cancel_keyboard())
            return
        with db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            key_row = conn.execute("SELECT product_id, is_used FROM product_keys WHERE id = ?", (key_id,)).fetchone()
            if not key_row or int(key_row["is_used"]):
                conn.rollback()
                await message.answer("❌ Key not found or already used; only unused keys can be removed.", reply_markup=cancel_keyboard())
                return
            conn.execute("DELETE FROM product_keys WHERE id = ?", (key_id,))
            conn.execute("UPDATE products SET stock = MAX(stock - 1, 0) WHERE id = ?", (key_row["product_id"],))
            conn.commit()
        await finish_admin(message, state, f"✅ Unused key record {key_id} removed.")

    elif current == AdminStates.wait_reseller_add_id.state:
        target = parse_user_id(text)
        if target is None or not user_exists(target):
            await message.answer("❌ User ID is invalid or not registered.", reply_markup=cancel_keyboard())
            return
        db_execute("UPDATE users SET is_reseller = 1 WHERE user_id = ?", (target,))
        await finish_admin(message, state, f"✅ Reseller role granted to user {target}.")

    elif current == AdminStates.wait_reseller_remove_id.state:
        target = parse_user_id(text)
        if target is None or not user_exists(target):
            await message.answer("❌ User ID is invalid or not registered.", reply_markup=cancel_keyboard())
            return
        db_execute("UPDATE users SET is_reseller = 0, reseller_parent_id = NULL WHERE user_id = ?", (target,))
        await finish_admin(message, state, f"✅ Reseller role removed from user {target}.")

    elif current == AdminStates.wait_reseller_view_id.state:
        target = parse_user_id(text)
        row = db_one("SELECT is_reseller, reseller_parent_id FROM users WHERE user_id = ?", (target,)) if target else None
        if not row:
            await message.answer("❌ User ID not found.", reply_markup=cancel_keyboard())
            return
        role = "Reseller" if int(row["is_reseller"] or 0) else "Member"
        parent = row["reseller_parent_id"] or "not set"
        await finish_admin(message, state, f"👤 User {target}: role = {role}; reseller parent = {parent}.")

    elif current == AdminStates.wait_reseller_up_user_id.state:
        target = parse_user_id(text)
        if target is None or not user_exists(target):
            await message.answer("❌ User ID not found.", reply_markup=cancel_keyboard())
            return
        await state.update_data(reseller_target_id=target)
        await state.set_state(AdminStates.wait_reseller_up_parent_id)
        await message.answer("Enter the parent/reseller Telegram ID (or 0 to clear it):", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_reseller_up_parent_id.state:
        target = int(data["reseller_target_id"])
        parent = parse_user_id(text, allow_zero=True)
        if parent is None or (parent != 0 and not user_exists(parent)) or parent == target:
            await message.answer("❌ Enter an existing parent ID, or 0 to clear. A user cannot be their own parent.", reply_markup=cancel_keyboard())
            return
        db_execute("UPDATE users SET reseller_parent_id = ? WHERE user_id = ?", (None if parent == 0 else parent, target))
        await finish_admin(message, state, f"✅ Reseller parent updated for user {target}.")

    elif current == AdminStates.wait_coupon_amount.state:
        amount = number_from_text(text)
        if amount is None or amount > 1_000_000:
            await message.answer("Enter a valid coupon amount from ₹0.01 to ₹10,00,000:", reply_markup=cancel_keyboard())
            return
        await state.update_data(coupon_amount=amount)
        await state.set_state(AdminStates.wait_coupon_uses)
        await message.answer("Enter maximum number of redemptions for this coupon:", reply_markup=cancel_keyboard())

    elif current == AdminStates.wait_coupon_uses.state:
        uses = parse_positive_int(text)
        if uses is None or uses > 1_000_000:
            await message.answer("Enter a positive whole number of uses:", reply_markup=cancel_keyboard())
            return
        code = secrets.token_hex(4).upper()
        with db_connection() as conn:
            conn.execute(
                "INSERT INTO coupons(code, amount, max_uses, used_count, created_at) VALUES(?, ?, ?, 0, ?)",
                (code, float(data["coupon_amount"]), uses, now_iso()),
            )
        await finish_admin(message, state, f"✅ Coupon created: <code>{code}</code>\nAmount: ₹{float(data['coupon_amount']):.2f}\nMax uses: {uses}\nUsers can redeem it with <code>/redeem {code}</code>.")

    else:
        await state.clear()
        await message.answer("This form is no longer active. Please choose a menu button again.", reply_markup=admin_keyboard(1) if admin else main_keyboard())


def parse_positive_int(value: str) -> int | None:
    try:
        number = int(value.strip())
        return number if number > 0 else None
    except (ValueError, AttributeError):
        return None


def parse_user_id(value: str, *, allow_zero: bool = False) -> int | None:
    try:
        number = int(value.strip())
        return number if (number > 0 or (allow_zero and number == 0)) else None
    except (ValueError, AttributeError):
        return None


def user_exists(user_id: int) -> bool:
    return db_one("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) is not None


def unique_nonempty_lines(value: str) -> list[str]:
    seen: set[str] = set()
    keys: list[str] = []
    for line in value.splitlines():
        candidate = line.strip()
        if candidate and candidate not in seen and len(candidate) <= 1000:
            keys.append(candidate)
            seen.add(candidate)
    return keys


# ================= CALLBACK FALLBACK =================
@dp.callback_query()
async def unknown_callback(call: CallbackQuery) -> None:
    # Every active callback has a dedicated handler above. Never claim a missing
    # feature is active merely to make the button look responsive.
    await call.answer("This action is expired or not implemented. Reopen the menu with /start.", show_alert=False)


# ================= START BOT =================
async def main() -> None:
    global bot
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Revoke any token previously posted in source/chat, "
            "create a new token in @BotFather, and set it as the BOT_TOKEN environment variable."
        )
    init_db()
    logging.info("ELITE X CONFIG bot is starting")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    asyncio.run(main())
