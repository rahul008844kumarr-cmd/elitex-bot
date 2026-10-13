#!/usr/bin/env python3
"""
ELITE X CONFIG BOT — starter bot.py
-----------------------------------
Features:
- Telegram shop menu
- Admin-only category and product management
- Add, edit, delete, show/hide, and reorder categories
- Add, edit, delete, show/hide products and move products between categories
- Editable welcome text, category subtitles, product descriptions, prices, plans and stock
- SQLite storage

Requirements:
    pip install "python-telegram-bot>=21,<23"

Run:
    1. Set BOT_TOKEN and ADMIN_IDS below (or as environment variables).
    2. python bot.py

Important:
- This is a starter shop/catalog bot. Real payment verification and automatic digital-key
  delivery are intentionally not faked. Add a trusted payment provider before selling.
- Only upload/distribute files and digital products you have permission to sell.
"""

import logging
import os
import sqlite3
from contextlib import closing
from html import escape
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
ADMIN_IDS_TEXT = os.getenv("ADMIN_IDS", "123456789")
DB_PATH = os.getenv("DB_PATH", "elite_x_bot.sqlite3")

# Conversation states
(
    ADD_CAT_NAME, ADD_CAT_SUBTITLE,
    EDIT_CAT_ID, EDIT_CAT_FIELD, EDIT_CAT_VALUE,
    DELETE_CAT_ID, TOGGLE_CAT_ID, MOVE_CAT_ID, MOVE_CAT_POS,
    ADD_PROD_CAT, ADD_PROD_NAME, ADD_PROD_DESC, ADD_PROD_PLAN,
    ADD_PROD_PRICE, ADD_PROD_STOCK,
    EDIT_PROD_ID, EDIT_PROD_FIELD, EDIT_PROD_VALUE,
    DELETE_PROD_ID, TOGGLE_PROD_ID, MOVE_PROD_ID, MOVE_PROD_CAT,
    MOVE_PROD_POS, SET_WELCOME,
) = range(24)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("elite_x_bot")


def parse_admin_ids() -> set[int]:
    result = set()
    for item in ADMIN_IDS_TEXT.split(","):
        item = item.strip()
        if item.isdigit():
            result.add(int(item))
    return result


ADMIN_IDS = parse_admin_ids()


def db():
    return sqlite3.connect(DB_PATH)


def init_db():
    with closing(db()) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subtitle TEXT NOT NULL DEFAULT '',
                emoji TEXT NOT NULL DEFAULT '📂',
                visible INTEGER NOT NULL DEFAULT 1,
                position INTEGER NOT NULL DEFAULT 0
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                emoji TEXT NOT NULL DEFAULT '🛒',
                visible INTEGER NOT NULL DEFAULT 1,
                position INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(category_id) REFERENCES categories(id)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('welcome',?)",
                    ("👑 Welcome to ELITE X CONFIG BOT!\nChoose an option below.",))
        con.commit()


def fetchall(query, args=()):
    with closing(db()) as con:
        return con.execute(query, args).fetchall()


def execute(query, args=()):
    with closing(db()) as con:
        con.execute("PRAGMA foreign_keys=ON")
        cur = con.execute(query, args)
        con.commit()
        return cur.lastrowid


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in ADMIN_IDS)


async def deny(update: Update):
    if update.callback_query:
        await update.callback_query.answer("Admin only.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("⛔ This command is for admins only.")


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Shop / Store", callback_data="shop")],
        [InlineKeyboardButton("👤 My Profile", callback_data="profile"),
         InlineKeyboardButton("🆘 Support", callback_data="support")],
    ])


def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Dashboard", callback_data="adm_dash")],
        [InlineKeyboardButton("📂 Categories", callback_data="adm_categories"),
         InlineKeyboardButton("📦 Products", callback_data="adm_products")],
        [InlineKeyboardButton("📝 Welcome Message", callback_data="adm_welcome")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
    ])


def category_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add category", callback_data="adm_cat_add")],
        [InlineKeyboardButton("✏️ Edit category", callback_data="adm_cat_edit"),
         InlineKeyboardButton("🗑️ Delete category", callback_data="adm_cat_delete")],
        [InlineKeyboardButton("👁️ Show/Hide", callback_data="adm_cat_toggle"),
         InlineKeyboardButton("🔀 Reorder", callback_data="adm_cat_move")],
        [InlineKeyboardButton("📋 List categories", callback_data="adm_cat_list")],
        [InlineKeyboardButton("⬅️ Admin panel", callback_data="admin")],
    ])


def product_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add product", callback_data="adm_prod_add")],
        [InlineKeyboardButton("✏️ Edit product", callback_data="adm_prod_edit"),
         InlineKeyboardButton("🗑️ Delete product", callback_data="adm_prod_delete")],
        [InlineKeyboardButton("👁️ Show/Hide", callback_data="adm_prod_toggle"),
         InlineKeyboardButton("🔀 Move product", callback_data="adm_prod_move")],
        [InlineKeyboardButton("📋 List products", callback_data="adm_prod_list")],
        [InlineKeyboardButton("⬅️ Admin panel", callback_data="admin")],
    ])


def categories_keyboard():
    rows = []
    cats = fetchall(
        "SELECT id,name,emoji FROM categories WHERE visible=1 ORDER BY position,id"
    )
    for cid, name, emoji in cats:
        rows.append([InlineKeyboardButton(f"{emoji} {name}"[:60], callback_data=f"cat:{cid}")])
    rows.append([InlineKeyboardButton("⬅️ Main menu", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def products_keyboard(category_id: int):
    rows = []
    products = fetchall(
        "SELECT id,name,emoji FROM products WHERE category_id=? AND visible=1 ORDER BY position,id",
        (category_id,),
    )
    for pid, name, emoji in products:
        rows.append([InlineKeyboardButton(f"{emoji} {name}"[:60], callback_data=f"prod:{pid}")])
    rows.append([InlineKeyboardButton("⬅️ Categories", callback_data="shop")])
    return InlineKeyboardMarkup(rows)


def plans_keyboard(product_id: int):
    rows = []
    plans = fetchall(
        "SELECT id,name,price,stock FROM plans WHERE product_id=? ORDER BY id",
        (product_id,),
    )
    for plan_id, name, price, stock in plans:
        stock_text = "✅ In stock" if stock > 0 else "❌ Out of stock"
        rows.append([InlineKeyboardButton(
            f"{name} — ₹{price:.2f} | {stock_text}"[:60],
            callback_data=f"plan:{plan_id}",
        )])
    rows.append([InlineKeyboardButton("⬅️ Back to products", callback_data=f"catback:{product_id}")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = fetchall("SELECT value FROM settings WHERE key='welcome'")
    message = welcome[0][0] if welcome else "Welcome to ELITE X CONFIG BOT!"
    await update.effective_message.reply_text(message, reply_markup=main_menu())


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)
    await update.effective_message.reply_text("👑 ELITE X ADMIN PANEL", reply_markup=admin_menu())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Use /start to open the shop.\nAdmins: /admin opens management.\n"
        "Set BOT_TOKEN and ADMIN_IDS before running."
    )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    if data.startswith("adm_") or data == "admin":
        if not is_admin(update):
            return await deny(update)

    if data == "home":
        await q.edit_message_text("👑 ELITE X CONFIG BOT\nChoose an option:", reply_markup=main_menu())
    elif data == "shop":
        cats = fetchall("SELECT id FROM categories WHERE visible=1")
        if not cats:
            await q.edit_message_text("Abhi koi category available nahi hai.", reply_markup=main_menu())
        else:
            await q.edit_message_text("🛒 SHOP\nCategory choose karein:", reply_markup=categories_keyboard())
    elif data.startswith("cat:"):
        cid = int(data.split(":")[1])
        cat = fetchall("SELECT name,subtitle FROM categories WHERE id=? AND visible=1", (cid,))
        if not cat:
            await q.edit_message_text("Category nahi mili.", reply_markup=categories_keyboard())
            return
        name, subtitle = cat[0]
        products = fetchall("SELECT id FROM products WHERE category_id=? AND visible=1", (cid,))
        body = f"📂 {name}"
        if subtitle:
            body += f"\n\n{subtitle}"
        body += "\n\nProduct choose karein:" if products else "\n\nIs category mein abhi products nahi hain."
        await q.edit_message_text(body, reply_markup=products_keyboard(cid))
    elif data.startswith("prod:"):
        pid = int(data.split(":")[1])
        product = fetchall(
            "SELECT name,description,category_id FROM products WHERE id=? AND visible=1", (pid,)
        )
        if not product:
            await q.edit_message_text("Product nahi mila.", reply_markup=categories_keyboard())
            return
        name, desc, cid = product[0]
        plans = fetchall("SELECT id FROM plans WHERE product_id=?", (pid,))
        body = f"🛒 {name}"
        if desc:
            body += f"\n\n{desc}"
        body += "\n\nPlan choose karein:" if plans else "\n\nAbhi koi plan add nahi hai."
        await q.edit_message_text(body, reply_markup=plans_keyboard(pid))
    elif data.startswith("plan:"):
        plan_id = int(data.split(":")[1])
        plan = fetchall("SELECT product_id,name,price,stock FROM plans WHERE id=?", (plan_id,))
        if not plan:
            await q.edit_message_text("Plan nahi mila.", reply_markup=main_menu())
            return
        pid, name, price, stock = plan[0]
        if stock <= 0:
            await q.answer("Out of stock", show_alert=True)
            return
        await q.edit_message_text(
            f"🧾 Order preview\nPlan: {name}\nPrice: ₹{price:.2f}\nStock: {stock}\n\n"
            "⚠️ Payment/delivery abhi configure nahi hai. Admin se contact karein.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🆘 Contact admin", callback_data="support")],
                [InlineKeyboardButton("⬅️ Back", callback_data=f"prod:{pid}")],
            ]),
        )
    elif data == "profile":
        user = update.effective_user
        await q.edit_message_text(
            f"👤 Your Profile\nName: {user.full_name}\nTelegram ID: {user.id}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="home")]]),
        )
    elif data == "support":
        await q.edit_message_text(
            "🆘 Support ke liye bot admin se contact karein.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="home")]]),
        )
    elif data == "admin":
        await q.edit_message_text("👑 ELITE X ADMIN PANEL", reply_markup=admin_menu())
    elif data == "adm_dash":
        c = fetchall("SELECT COUNT(*) FROM categories")[0][0]
        p = fetchall("SELECT COUNT(*) FROM products")[0][0]
        await q.edit_message_text(
            f"📊 Dashboard\nCategories: {c}\nProducts: {p}",
            reply_markup=admin_menu(),
        )
    elif data == "adm_categories":
        await q.edit_message_text("📂 Category Management", reply_markup=category_admin_menu())
    elif data == "adm_products":
        await q.edit_message_text("📦 Product Management", reply_markup=product_admin_menu())
    elif data == "adm_cat_list":
        rows = fetchall("SELECT id,name,subtitle,visible,position FROM categories ORDER BY position,id")
        body = "📂 Categories\n\n" + ("\n".join(
            f"ID {r[0]} | {r[1]} | {'Visible' if r[3] else 'Hidden'} | pos {r[4]}\nSubtitle: {r[2] or '-'}"
            for r in rows
        ) if rows else "No categories yet.")
        await q.edit_message_text(body[:4000], reply_markup=category_admin_menu())
    elif data == "adm_prod_list":
        rows = fetchall(
            "SELECT p.id,p.name,c.name,p.visible,p.position FROM products p "
            "LEFT JOIN categories c ON c.id=p.category_id ORDER BY c.position,p.position,p.id"
        )
        body = "📦 Products\n\n" + ("\n".join(
            f"ID {r[0]} | {r[1]} | Category: {r[2]} | {'Visible' if r[3] else 'Hidden'} | pos {r[4]}"
            for r in rows
        ) if rows else "No products yet.")
        await q.edit_message_text(body[:4000], reply_markup=product_admin_menu())
    elif data == "adm_cat_add":
        context.user_data["flow"] = "add_cat"
        await q.edit_message_text("Category ka naam bhejein:")
    elif data == "adm_cat_edit":
        context.user_data["flow"] = "edit_cat_id"
        await q.edit_message_text("Edit karne ke liye Category ID bhejein. List: /admin phir Categories → List.")
    elif data == "adm_cat_delete":
        context.user_data["flow"] = "delete_cat_id"
        await q.edit_message_text("Delete karne ke liye Category ID bhejein. Iske products bhi delete honge.")
    elif data == "adm_cat_toggle":
        context.user_data["flow"] = "toggle_cat_id"
        await q.edit_message_text("Show/Hide karne ke liye Category ID bhejein.")
    elif data == "adm_cat_move":
        context.user_data["flow"] = "move_cat_id"
        await q.edit_message_text("Reorder ke liye Category ID bhejein, phir position number.")
    elif data == "adm_prod_add":
        cats = fetchall("SELECT id,name FROM categories ORDER BY position,id")
        if not cats:
            await q.edit_message_text("Pehle ek category add karein.", reply_markup=product_admin_menu())
            return
        context.user_data["flow"] = "add_prod_cat"
        await q.edit_message_text("Category ID bhejein:\n" + "\n".join(f"{r[0]} — {r[1]}" for r in cats))
    elif data == "adm_prod_edit":
        context.user_data["flow"] = "edit_prod_id"
        await q.edit_message_text("Edit karne ke liye Product ID bhejein. List: Products → List.")
    elif data == "adm_prod_delete":
        context.user_data["flow"] = "delete_prod_id"
        await q.edit_message_text("Delete karne ke liye Product ID bhejein.")
    elif data == "adm_prod_toggle":
        context.user_data["flow"] = "toggle_prod_id"
        await q.edit_message_text("Show/Hide karne ke liye Product ID bhejein.")
    elif data == "adm_prod_move":
        context.user_data["flow"] = "move_prod_id"
        await q.edit_message_text("Move karne ke liye Product ID bhejein.")
    elif data == "adm_welcome":
        context.user_data["flow"] = "welcome"
        await q.edit_message_text("Naya welcome message bhejein:")
    elif data.startswith("catback:"):
        pid = int(data.split(":")[1])
        row = fetchall("SELECT category_id FROM products WHERE id=?", (pid,))
        if row:
            cid = row[0][0]
            await q.edit_message_text("Products:", reply_markup=products_keyboard(cid))
        else:
            await q.edit_message_text("Category choose karein:", reply_markup=categories_keyboard())
    else:
        await q.edit_message_text("Unknown option.", reply_markup=main_menu())


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    flow = context.user_data.get("flow")
    if not flow:
        return
    text_in = (update.effective_message.text or "").strip()
    msg = update.effective_message

    def done(message="✅ Done."):
        context.user_data.pop("flow", None)
        return msg.reply_text(message, reply_markup=admin_menu())

    def ask(message):
        return msg.reply_text(message)

    if flow == "add_cat":
        context.user_data["new_cat_name"] = text_in
        context.user_data["flow"] = "add_cat_subtitle"
        await ask("Category subtitle bhejein (nahi chahiye to - bhejein):")
    elif flow == "add_cat_subtitle":
        name = context.user_data.pop("new_cat_name", "New Category")
        subtitle = "" if text_in == "-" else text_in
        execute("INSERT INTO categories(name,subtitle,position) VALUES(?,?,?)",
                (name, subtitle, fetchall("SELECT COALESCE(MAX(position),0)+1 FROM categories")[0][0]))
        await done(f"✅ Category '{name}' add ho gayi.")
    elif flow == "edit_cat_id":
        if not text_in.isdigit() or not fetchall("SELECT id FROM categories WHERE id=?", (int(text_in),)):
            await ask("Valid Category ID bhejein.")
            return
        context.user_data["edit_cat_id"] = int(text_in)
        context.user_data["flow"] = "edit_cat_field"
        await ask("Kya edit karna hai? 'name' ya 'subtitle' likhein.")
    elif flow == "edit_cat_field":
        if text_in.lower() not in ("name", "subtitle"):
            await ask("Sirf name ya subtitle likhein.")
            return
        context.user_data["edit_cat_field"] = text_in.lower()
        context.user_data["flow"] = "edit_cat_value"
        await ask("Nayi value bhejein:")
    elif flow == "edit_cat_value":
        cid = context.user_data.pop("edit_cat_id")
        field = context.user_data.pop("edit_cat_field")
        execute(f"UPDATE categories SET {field}=? WHERE id=?", (text_in, cid))
        await done("✅ Category update ho gayi.")
    elif flow == "delete_cat_id":
        if not text_in.isdigit():
            await ask("Category ID number bhejein.")
            return
        cid = int(text_in)
        if not fetchall("SELECT id FROM categories WHERE id=?", (cid,)):
            await ask("Category nahi mili.")
            return
        # Remove associated plans and products first.
        product_ids = [r[0] for r in fetchall("SELECT id FROM products WHERE category_id=?", (cid,))]
        for pid in product_ids:
            execute("DELETE FROM plans WHERE product_id=?", (pid,))
        execute("DELETE FROM products WHERE category_id=?", (cid,))
        execute("DELETE FROM categories WHERE id=?", (cid,))
        await done("🗑️ Category aur uske products/plans delete ho gaye.")
    elif flow == "toggle_cat_id":
        if not text_in.isdigit():
            await ask("Category ID number bhejein.")
            return
        row = fetchall("SELECT visible FROM categories WHERE id=?", (int(text_in),))
        if not row:
            await ask("Category nahi mili.")
            return
        execute("UPDATE categories SET visible=? WHERE id=?", (0 if row[0][0] else 1, int(text_in)))
        await done("✅ Category visibility badal di gayi.")
    elif flow == "move_cat_id":
        if not text_in.isdigit() or not fetchall("SELECT id FROM categories WHERE id=?", (int(text_in),)):
            await ask("Valid Category ID bhejein.")
            return
        context.user_data["move_cat_id"] = int(text_in)
        context.user_data["flow"] = "move_cat_pos"
        await ask("Nayi position number bhejein (1, 2, 3...).")
    elif flow == "move_cat_pos":
        if not text_in.isdigit() or int(text_in) < 1:
            await ask("Position 1 ya usse bada number hona chahiye.")
            return
        execute("UPDATE categories SET position=? WHERE id=?", (int(text_in), context.user_data.pop("move_cat_id")))
        await done("🔀 Category position update ho gayi.")
    elif flow == "add_prod_cat":
        if not text_in.isdigit() or not fetchall("SELECT id FROM categories WHERE id=?", (int(text_in),)):
            await ask("Valid Category ID bhejein.")
            return
        context.user_data["new_prod_cat"] = int(text_in)
        context.user_data["flow"] = "add_prod_name"
        await ask("Product ka naam bhejein:")
    elif flow == "add_prod_name":
        context.user_data["new_prod_name"] = text_in
        context.user_data["flow"] = "add_prod_desc"
        await ask("Product description bhejein (nahi chahiye to -):")
    elif flow == "add_prod_desc":
        context.user_data["new_prod_desc"] = "" if text_in == "-" else text_in
        context.user_data["flow"] = "add_prod_plan"
        await ask("Pehle plan ka naam bhejein, jaise 1 Hour (skip ke liye -):")
    elif flow == "add_prod_plan":
        context.user_data["new_prod_plan"] = text_in
        if text_in == "-":
            pid = execute(
                "INSERT INTO products(category_id,name,description,position) VALUES(?,?,?,?)",
                (context.user_data.pop("new_prod_cat"), context.user_data.pop("new_prod_name"),
                 context.user_data.pop("new_prod_desc"), 9999),
            )
            await done(f"✅ Product add ho gaya. Product ID: {pid} (abhi plan nahi hai).")
        else:
            context.user_data["flow"] = "add_prod_price"
            await ask("Plan ki price ₹ mein bhejein (example: 15 or 25.50):")
    elif flow == "add_prod_price":
        try:
            price = float(text_in)
            if price < 0:
                raise ValueError
        except ValueError:
            await ask("Valid non-negative price bhejein.")
            return
        context.user_data["new_prod_price"] = price
        context.user_data["flow"] = "add_prod_stock"
        await ask("Stock quantity number bhejein:")
    elif flow == "add_prod_stock":
        if not text_in.isdigit():
            await ask("Stock quantity 0 ya usse bada whole number hona chahiye.")
            return
        pid = execute(
            "INSERT INTO products(category_id,name,description,position) VALUES(?,?,?,?)",
            (context.user_data.pop("new_prod_cat"), context.user_data.pop("new_prod_name"),
             context.user_data.pop("new_prod_desc"), 9999),
        )
        execute("INSERT INTO plans(product_id,name,price,stock) VALUES(?,?,?,?)",
                (pid, context.user_data.pop("new_prod_plan"),
                 context.user_data.pop("new_prod_price"), int(text_in)))
        await done(f"✅ Product aur plan add ho gaye. Product ID: {pid}")
    elif flow == "edit_prod_id":
        if not text_in.isdigit() or not fetchall("SELECT id FROM products WHERE id=?", (int(text_in),)):
            await ask("Valid Product ID bhejein.")
            return
        context.user_data["edit_prod_id"] = int(text_in)
        context.user_data["flow"] = "edit_prod_field"
        await ask("Field likhein: name, description, category_id")
    elif flow == "edit_prod_field":
        field = text_in.lower()
        if field not in ("name", "description", "category_id"):
            await ask("Sirf name, description, category_id valid hain.")
            return
        context.user_data["edit_prod_field"] = field
        context.user_data["flow"] = "edit_prod_value"
        await ask("Nayi value bhejein:")
    elif flow == "edit_prod_value":
        pid = context.user_data.pop("edit_prod_id")
        field = context.user_data.pop("edit_prod_field")
        if field == "category_id" and (not text_in.isdigit() or not fetchall("SELECT id FROM categories WHERE id=?", (int(text_in),))):
            await ask("Valid Category ID bhejein.")
            context.user_data["edit_prod_id"] = pid
            context.user_data["edit_prod_field"] = field
            context.user_data["flow"] = "edit_prod_value"
            return
        execute(f"UPDATE products SET {field}=? WHERE id=?", (int(text_in) if field == "category_id" else text_in, pid))
        await done("✅ Product update ho gaya.")
    elif flow == "delete_prod_id":
        if not text_in.isdigit() or not fetchall("SELECT id FROM products WHERE id=?", (int(text_in),)):
            await ask("Valid Product ID bhejein.")
            return
        pid = int(text_in)
        execute("DELETE FROM plans WHERE product_id=?", (pid,))
        execute("DELETE FROM products WHERE id=?", (pid,))
        await done("🗑️ Product aur uske plans delete ho gaye.")
    elif flow == "toggle_prod_id":
        if not text_in.isdigit():
            await ask("Product ID number bhejein.")
            return
        row = fetchall("SELECT visible FROM products WHERE id=?", (int(text_in),))
        if not row:
            await ask("Product nahi mila.")
            return
        execute("UPDATE products SET visible=? WHERE id=?", (0 if row[0][0] else 1, int(text_in)))
        await done("✅ Product visibility badal di gayi.")
    elif flow == "move_prod_id":
        if not text_in.isdigit() or not fetchall("SELECT id FROM products WHERE id=?", (int(text_in),)):
            await ask("Valid Product ID bhejein.")
            return
        context.user_data["move_prod_id"] = int(text_in)
        context.user_data["flow"] = "move_prod_cat"
        cats = fetchall("SELECT id,name FROM categories ORDER BY position,id")
        await ask("Nayi Category ID bhejein:\n" + "\n".join(f"{r[0]} — {r[1]}" for r in cats))
    elif flow == "move_prod_cat":
        if not text_in.isdigit() or not fetchall("SELECT id FROM categories WHERE id=?", (int(text_in),)):
            await ask("Valid Category ID bhejein.")
            return
        context.user_data["move_prod_cat"] = int(text_in)
        context.user_data["flow"] = "move_prod_pos"
        await ask("Nayi position number bhejein:")
    elif flow == "move_prod_pos":
        if not text_in.isdigit() or int(text_in) < 1:
            await ask("Position 1 ya usse bada number bhejein.")
            return
        execute("UPDATE products SET category_id=?,position=? WHERE id=?",
                (context.user_data.pop("move_prod_cat"), int(text_in), context.user_data.pop("move_prod_id")))
        await done("🔀 Product move/reorder ho gaya.")
    elif flow == "welcome":
        execute("INSERT INTO settings(key,value) VALUES('welcome',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (text_in,))
        await done("✅ Welcome message update ho gaya.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("flow", None)
    await update.effective_message.reply_text("Cancelled. /admin se dobara shuru karein.")
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled error: %s", context.error)


def main():
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            "BOT_TOKEN set nahi hai. Environment variable BOT_TOKEN set karein, "
            "ya file mein PASTE_YOUR_BOT_TOKEN_HERE replace karein."
        )
    if not ADMIN_IDS:
        raise SystemExit("ADMIN_IDS set karein, jaise 123456789.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    app.add_error_handler(error_handler)
    log.info("ELITE X CONFIG BOT started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
