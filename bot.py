#!/usr/bin/env python3
"""ELITE X CONFIG BOT — shop, manual payment verification, and admin delivery.

Required environment variables:
  BOT_TOKEN  = token from @BotFather (keep secret)
  ADMIN_IDS  = your numeric Telegram ID, e.g. 8467166339
Optional:
  DB_PATH    = SQLite path; on a Render persistent disk use /var/data/elite_x_bot.sqlite3

Payment flow is MANUAL: buyer chooses a plan, follows your payment instructions,
submits a payment screenshot, admin checks it, then admin sends the product using
/deliver ORDER_ID delivery-text. The bot does not claim to verify payments itself.
"""
import logging
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS_TEXT = os.getenv("ADMIN_IDS", "").strip()
DB_PATH = os.getenv("DB_PATH", "elite_x_bot.sqlite3").strip()
LOGO_PATH = os.getenv("LOGO_PATH", "welcome_logo.png")
ADMIN_IDS = {int(x.strip()) for x in ADMIN_IDS_TEXT.split(",") if x.strip().isdigit()}

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("elite_x_bot")

WELCOME_DEFAULT = (
    "⚡ ELITE X CONFIG ⚡\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "👑 Welcome to the official ELITE X CONFIG Store!\n\n"
    "🛍️ Explore our products and available plans.\n"
    "📋 Check product details before ordering.\n"
    "🔐 Payments are reviewed by an admin before delivery.\n"
    "🎧 Need help? Tap Support and contact our team.\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "✨ Select an option below to get started."
)

# Conversation state is kept in context.user_data for each user/admin.

def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with closing(db()) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            subtitle TEXT NOT NULL DEFAULT '', emoji TEXT NOT NULL DEFAULT '📂',
            visible INTEGER NOT NULL DEFAULT 1, position INTEGER NOT NULL DEFAULT 0)""")
        con.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER NOT NULL,
            name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            emoji TEXT NOT NULL DEFAULT '🛒', visible INTEGER NOT NULL DEFAULT 1,
            position INTEGER NOT NULL DEFAULT 0)""")
        con.execute("""CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
            name TEXT NOT NULL, price REAL NOT NULL DEFAULT 0, stock INTEGER NOT NULL DEFAULT 0)""")
        con.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT '', plan_id INTEGER NOT NULL,
            product_name TEXT NOT NULL, plan_name TEXT NOT NULL, price REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'awaiting_payment', proof_file_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('welcome',?)", (WELCOME_DEFAULT,))
        con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('payment_instructions','')")
        con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('support_text','Please contact the bot administrator for support.')")
        con.commit()


def rows(sql, args=()):
    with closing(db()) as con:
        return con.execute(sql, args).fetchall()


def run(sql, args=()):
    with closing(db()) as con:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid


def setting(key, default=""):
    r = rows("SELECT value FROM settings WHERE key=?", (key,))
    return r[0][0] if r else default


def set_setting(key, value):
    run("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def is_admin(update: Update):
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)


async def deny(update: Update):
    if update.callback_query:
        await update.callback_query.answer("Admin access only.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("⛔ Admin access only. Check ADMIN_IDS in Render Environment.")


def kb(rows_):
    return InlineKeyboardMarkup(rows_)


def main_menu():
    return kb([
        [InlineKeyboardButton("🛍️  EXPLORE STORE", callback_data="shop")],
        [InlineKeyboardButton("👤 My Profile", callback_data="profile"), InlineKeyboardButton("🎧 Support", callback_data="support")],
    ])


def admin_menu():
    return kb([
        [InlineKeyboardButton("📊 Dashboard", callback_data="adm_dash")],
        [InlineKeyboardButton("📂 Categories", callback_data="adm_categories"), InlineKeyboardButton("📦 Products", callback_data="adm_products")],
        [InlineKeyboardButton("🧾 Orders / Payments", callback_data="adm_orders")],
        [InlineKeyboardButton("💳 Payment Instructions", callback_data="adm_payment"), InlineKeyboardButton("🖼️ Welcome Logo", callback_data="adm_logo")],
        [InlineKeyboardButton("✨ Welcome Text", callback_data="adm_welcome")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
    ])


def category_menu():
    return kb([
        [InlineKeyboardButton("➕ Add category", callback_data="adm_cat_add")],
        [InlineKeyboardButton("✏️ Edit category", callback_data="adm_cat_edit"), InlineKeyboardButton("🗑️ Delete category", callback_data="adm_cat_delete")],
        [InlineKeyboardButton("👁️ Show / Hide", callback_data="adm_cat_toggle"), InlineKeyboardButton("🔀 Reorder", callback_data="adm_cat_move")],
        [InlineKeyboardButton("📋 List categories", callback_data="adm_cat_list")],
        [InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin")],
    ])


def product_menu():
    return kb([
        [InlineKeyboardButton("➕ Add product + first plan", callback_data="adm_prod_add")],
        [InlineKeyboardButton("➕ Add another plan", callback_data="adm_plan_add")],
        [InlineKeyboardButton("✏️ Edit product", callback_data="adm_prod_edit"), InlineKeyboardButton("✏️ Edit plan", callback_data="adm_plan_edit")],
        [InlineKeyboardButton("🗑️ Delete product", callback_data="adm_prod_delete")],
        [InlineKeyboardButton("👁️ Show / Hide", callback_data="adm_prod_toggle"), InlineKeyboardButton("🔀 Move product", callback_data="adm_prod_move")],
        [InlineKeyboardButton("📋 List products / plans", callback_data="adm_prod_list")],
        [InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin")],
    ])


def categories_kb():
    items = rows("SELECT id,name,emoji FROM categories WHERE visible=1 ORDER BY position,id")
    out = [[InlineKeyboardButton(f"{emoji} {name}"[:60], callback_data=f"cat:{cid}")] for cid,name,emoji in items]
    out.append([InlineKeyboardButton("⬅️ Main Menu", callback_data="home")])
    return kb(out)


def products_kb(cid):
    items = rows("SELECT id,name,emoji FROM products WHERE category_id=? AND visible=1 ORDER BY position,id", (cid,))
    out = [[InlineKeyboardButton(f"{emoji} {name}"[:60], callback_data=f"prod:{pid}")] for pid,name,emoji in items]
    out.append([InlineKeyboardButton("⬅️ Categories", callback_data="shop")])
    return kb(out)


def plans_kb(pid):
    items = rows("SELECT id,name,price,stock FROM plans WHERE product_id=? ORDER BY id", (pid,))
    out = []
    for plan_id,name,price,stock in items:
        status = "✅ Available" if stock > 0 else "❌ Out of stock"
        out.append([InlineKeyboardButton(f"{name} · ₹{price:.2f} · {status}"[:60], callback_data=f"plan:{plan_id}")])
    out.append([InlineKeyboardButton("⬅️ Back to products", callback_data=f"catback:{pid}")])
    return kb(out)


def order_admin_kb(order_id):
    return kb([[InlineKeyboardButton("✅ Approve payment", callback_data=f"order:approve:{order_id}"),
                InlineKeyboardButton("❌ Reject payment", callback_data=f"order:reject:{order_id}")]])


async def show_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome = setting("welcome", WELCOME_DEFAULT)
    animation_id = setting("welcome_animation", "")
    logo_id = setting("welcome_logo_file_id", "")
    try:
        if animation_id:
            await context.bot.send_animation(chat_id=user.id, animation=animation_id, caption=welcome[:1024], reply_markup=main_menu())
        elif logo_id:
            await context.bot.send_photo(chat_id=user.id, photo=logo_id, caption=welcome[:1024], reply_markup=main_menu())
        elif Path(LOGO_PATH).exists():
            with open(LOGO_PATH, "rb") as photo:
                await context.bot.send_photo(chat_id=user.id, photo=photo, caption=welcome[:1024], reply_markup=main_menu())
        else:
            await context.bot.send_message(chat_id=user.id, text=welcome, reply_markup=main_menu())
    except Exception:
        log.exception("Could not send welcome media; falling back to text")
        await context.bot.send_message(chat_id=user.id, text=welcome, reply_markup=main_menu())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_welcome(update, context)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)
    await update.effective_message.reply_text("👑 ELITE X CONFIG · ADMIN CONTROL CENTER\nManage categories, products, payment instructions and customer orders below.", reply_markup=admin_menu())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Use /start to open the store.\nAdmin: /admin\nAfter approving a payment, deliver the product with:\n/deliver ORDER_ID your-delivery-text")


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if data == "home":
        return await show_welcome(update, context)
    if data == "admin" or data.startswith("adm_") or data.startswith("order:"):
        if not is_admin(update):
            return await deny(update)

    if data == "shop":
        if not rows("SELECT id FROM categories WHERE visible=1"):
            await q.edit_message_text("✨ Our store is being prepared. Please check back soon!", reply_markup=main_menu())
        else:
            await q.edit_message_text("🛍️ ELITE X STORE\n━━━━━━━━━━━━━━━━━━\nChoose a category to explore:", reply_markup=categories_kb())
    elif data.startswith("cat:"):
        cid = int(data.split(":")[1])
        cat = rows("SELECT name,subtitle FROM categories WHERE id=? AND visible=1", (cid,))
        if not cat:
            return await q.edit_message_text("Category not found.", reply_markup=categories_kb())
        name,subtitle = cat[0]
        body = f"📂 {name}\n━━━━━━━━━━━━━━━━━━"
        if subtitle: body += f"\n{subtitle}"
        body += "\n\n👇 Choose a product below:" if rows("SELECT id FROM products WHERE category_id=? AND visible=1", (cid,)) else "\n\nProducts will be added soon."
        await q.edit_message_text(body, reply_markup=products_kb(cid))
    elif data.startswith("prod:"):
        pid = int(data.split(":")[1])
        p = rows("SELECT name,description,category_id FROM products WHERE id=? AND visible=1", (pid,))
        if not p: return await q.edit_message_text("Product not found.", reply_markup=categories_kb())
        name,desc,cid = p[0]
        body = f"💎 {name}\n━━━━━━━━━━━━━━━━━━"
        if desc: body += f"\n{desc}"
        body += "\n\n📦 Select a plan and price:" if rows("SELECT id FROM plans WHERE product_id=?", (pid,)) else "\n\nPlans are being added soon."
        await q.edit_message_text(body, reply_markup=plans_kb(pid))
    elif data.startswith("plan:"):
        plan_id = int(data.split(":")[1])
        p = rows("SELECT pl.product_id,pl.name,pl.price,pl.stock,pr.name FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=?", (plan_id,))
        if not p: return await q.edit_message_text("Plan not found.", reply_markup=main_menu())
        pid,plan_name,price,stock,product_name = p[0]
        if stock <= 0: return await q.answer("This plan is currently out of stock.", show_alert=True)
        instructions = setting("payment_instructions", "").strip()
        if not instructions:
            return await q.edit_message_text("⚠️ Payment is not configured yet. Please contact Support or try again later.", reply_markup=kb([[InlineKeyboardButton("🎧 Support", callback_data="support")],[InlineKeyboardButton("⬅️ Back", callback_data=f"prod:{pid}")]]))
        user = update.effective_user
        oid = run("INSERT INTO orders(user_id,username,plan_id,product_name,plan_name,price,status) VALUES(?,?,?,?,?,?,?)",
                  (user.id, user.username or user.full_name, plan_id, product_name, plan_name, price, "awaiting_payment"))
        context.user_data["payment_order_id"] = oid
        body = (f"🧾 ORDER #{oid}\n━━━━━━━━━━━━━━━━━━\n📦 Product: {product_name}\n🎟️ Plan: {plan_name}\n💰 Total: ₹{price:.2f}\n\n"
                f"💳 PAYMENT INSTRUCTIONS\n{instructions}\n\nAfter paying, tap ‘I’ve Paid’ and send a clear payment screenshot. An admin will review it before delivery.\n\n⚠️ Do not send your UPI PIN, OTP or bank password.")
        await q.edit_message_text(body, reply_markup=kb([[InlineKeyboardButton("📤 I've Paid · Upload Screenshot", callback_data=f"proof:{oid}")],[InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancelorder:{oid}")],[InlineKeyboardButton("🎧 Support", callback_data="support")]]))
    elif data.startswith("proof:"):
        oid = int(data.split(":")[1])
        order = rows("SELECT user_id,status FROM orders WHERE id=?", (oid,))
        if not order or order[0][0] != update.effective_user.id or order[0][1] != "awaiting_payment":
            return await q.answer("This order is not available for payment proof.", show_alert=True)
        context.user_data["awaiting_proof_order"] = oid
        await q.edit_message_text(f"📤 Send the payment screenshot now for order #{oid}.\nPlease make sure the amount and transaction status are visible. Do not send OTPs or PINs.", reply_markup=kb([[InlineKeyboardButton("⬅️ Main Menu", callback_data="home")]]))
    elif data.startswith("cancelorder:"):
        oid = int(data.split(":")[1])
        order = rows("SELECT user_id,status FROM orders WHERE id=?", (oid,))
        if order and order[0][0] == update.effective_user.id and order[0][1] == "awaiting_payment":
            run("UPDATE orders SET status='cancelled' WHERE id=?", (oid,))
            await q.edit_message_text(f"Order #{oid} cancelled.", reply_markup=main_menu())
        else:
            await q.answer("This order cannot be cancelled now.", show_alert=True)
    elif data == "profile":
        u = update.effective_user
        count = rows("SELECT COUNT(*) FROM orders WHERE user_id=?", (u.id,))[0][0]
        await q.edit_message_text(f"👤 YOUR PROFILE\n━━━━━━━━━━━━━━━━━━\nName: {u.full_name}\nTelegram ID: {u.id}\nOrders: {count}\n\nKeep your order ID for support.", reply_markup=kb([[InlineKeyboardButton("⬅️ Main Menu", callback_data="home")]]))
    elif data == "support":
        await q.edit_message_text("🎧 ELITE X SUPPORT\n━━━━━━━━━━━━━━━━━━\n" + setting("support_text", "Please contact the bot administrator for support."), reply_markup=kb([[InlineKeyboardButton("⬅️ Main Menu", callback_data="home")]]))
    elif data == "admin":
        await q.edit_message_text("👑 ELITE X CONFIG · ADMIN CONTROL CENTER", reply_markup=admin_menu())
    elif data == "adm_dash":
        c = rows("SELECT COUNT(*) FROM categories")[0][0]; p = rows("SELECT COUNT(*) FROM products")[0][0]
        pending = rows("SELECT COUNT(*) FROM orders WHERE status IN ('awaiting_payment','proof_submitted','approved_awaiting_delivery')")[0][0]
        await q.edit_message_text(f"📊 DASHBOARD\n━━━━━━━━━━━━━━━━━━\n📂 Categories: {c}\n📦 Products: {p}\n🧾 Active orders: {pending}\n\nUse the controls below to manage your store.", reply_markup=admin_menu())
    elif data == "adm_categories":
        await q.edit_message_text("📂 CATEGORY MANAGEMENT\nAdd, edit, hide, reorder or remove store categories.", reply_markup=category_menu())
    elif data == "adm_products":
        await q.edit_message_text("📦 PRODUCT MANAGEMENT\nProducts belong to categories. Each product can have multiple plans.", reply_markup=product_menu())
    elif data == "adm_cat_list":
        items = rows("SELECT id,name,subtitle,visible,position FROM categories ORDER BY position,id")
        text = "📂 CATEGORIES\n\n" + ("\n\n".join(f"ID {i} · {n}\nStatus: {'Visible' if v else 'Hidden'} · Position: {pos}\nSubtitle: {s or '-'}" for i,n,s,v,pos in items) if items else "No categories yet.")
        await q.edit_message_text(text[:4000], reply_markup=category_menu())
    elif data == "adm_prod_list":
        items = rows("SELECT p.id,p.name,c.name,p.visible,pl.id,pl.name,pl.price,pl.stock FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN plans pl ON pl.product_id=p.id ORDER BY c.position,p.position,p.id,pl.id")
        text = "📦 PRODUCTS & PLANS\n\n" + ("\n".join(f"Product ID {r[0]} · {r[1]} | Category: {r[2]} | {'Visible' if r[3] else 'Hidden'}\n  Plan ID {r[4] or '-'}: {r[5] or '-'} · ₹{r[6] or 0:.2f} · Stock {r[7] if r[7] is not None else '-'}" for r in items) if items else "No products yet.")
        await q.edit_message_text(text[:4000], reply_markup=product_menu())
    elif data == "adm_cat_add":
        context.user_data["flow"] = "add_cat_name"; await q.edit_message_text("Send the new category name:")
    elif data == "adm_cat_edit":
        context.user_data["flow"] = "edit_cat_id"; await q.edit_message_text("Send the Category ID. Open Categories → List categories to see IDs.")
    elif data == "adm_cat_delete":
        context.user_data["flow"] = "delete_cat_id"; await q.edit_message_text("Send the Category ID to delete. Its products and plans will also be deleted.")
    elif data == "adm_cat_toggle":
        context.user_data["flow"] = "toggle_cat_id"; await q.edit_message_text("Send the Category ID to show/hide.")
    elif data == "adm_cat_move":
        context.user_data["flow"] = "move_cat_id"; await q.edit_message_text("Send the Category ID to reorder.")
    elif data == "adm_prod_add":
        cats = rows("SELECT id,name FROM categories ORDER BY position,id")
        if not cats: return await q.edit_message_text("Add a category first.", reply_markup=product_menu())
        context.user_data["flow"] = "add_prod_cat"
        await q.edit_message_text("Choose the category by sending its ID:\n" + "\n".join(f"{i} — {n}" for i,n in cats))
    elif data == "adm_plan_add":
        context.user_data["flow"] = "add_plan_product"; await q.edit_message_text("Send the Product ID that should receive another plan. See Products → List products / plans.")
    elif data == "adm_prod_edit":
        context.user_data["flow"] = "edit_prod_id"; await q.edit_message_text("Send the Product ID to edit.")
    elif data == "adm_plan_edit":
        context.user_data["flow"] = "edit_plan_id"; await q.edit_message_text("Send the Plan ID to edit. See Products → List products / plans.")
    elif data == "adm_prod_delete":
        context.user_data["flow"] = "delete_prod_id"; await q.edit_message_text("Send the Product ID to delete (its plans will also be deleted).")
    elif data == "adm_prod_toggle":
        context.user_data["flow"] = "toggle_prod_id"; await q.edit_message_text("Send the Product ID to show/hide.")
    elif data == "adm_prod_move":
        context.user_data["flow"] = "move_prod_id"; await q.edit_message_text("Send the Product ID to move to another category.")
    elif data == "adm_payment":
        context.user_data["flow"] = "payment_instructions"; await q.edit_message_text("Send your payment instructions as one message (UPI ID, amount/payment steps, and QR instructions). You can include line breaks. Never ask customers for PIN/OTP.")
    elif data == "adm_welcome":
        context.user_data["flow"] = "welcome"; await q.edit_message_text("Send the new welcome message. Emojis and line breaks are supported.")
    elif data == "adm_logo":
        context.user_data["flow"] = "welcome_media_choice"
        await q.edit_message_text("Send a photo to set the welcome logo, or a GIF/video animation to set the welcome animation. Send /cancel to stop.")
    elif data == "adm_orders":
        items = rows("SELECT id,user_id,username,product_name,plan_name,price,status FROM orders WHERE status IN ('proof_submitted','approved_awaiting_delivery') ORDER BY id DESC LIMIT 20")
        text = "🧾 ORDERS NEEDING ACTION\n\n" + ("\n".join(f"#{i} · {n} · {p} · ₹{price:.2f} · {status}\nUser ID: {uid} (@{un})" for i,uid,un,n,p,price,status in items) if items else "No orders currently need action.")
        await q.edit_message_text(text[:4000], reply_markup=admin_menu())
    elif data.startswith("order:approve:"):
        oid = int(data.rsplit(":",1)[1]); order = rows("SELECT user_id,status FROM orders WHERE id=?", (oid,))
        if not order or order[0][1] != "proof_submitted": return await q.answer("Order is not waiting for payment review.", show_alert=True)
        run("UPDATE orders SET status='approved_awaiting_delivery' WHERE id=?", (oid,))
        await context.bot.send_message(order[0][0], f"✅ Payment for order #{oid} has been approved. Your order is awaiting delivery.")
        await q.edit_message_caption(caption=(q.message.caption or "") + "\n\n✅ PAYMENT APPROVED. Now send: /deliver " + str(oid) + " your delivery text") if q.message.photo else await q.edit_message_text((q.message.text or "") + f"\n\n✅ PAYMENT APPROVED. Send: /deliver {oid} your delivery text")
    elif data.startswith("order:reject:"):
        oid = int(data.rsplit(":",1)[1]); order = rows("SELECT user_id,status FROM orders WHERE id=?", (oid,))
        if not order or order[0][1] != "proof_submitted": return await q.answer("Order is not waiting for payment review.", show_alert=True)
        run("UPDATE orders SET status='payment_rejected' WHERE id=?", (oid,))
        await context.bot.send_message(order[0][0], f"❌ Payment proof for order #{oid} was not approved. Please contact Support or submit a clearer valid proof.")
        await q.edit_message_caption(caption=(q.message.caption or "") + "\n\n❌ PAYMENT REJECTED") if q.message.photo else await q.edit_message_text((q.message.text or "") + "\n\n❌ PAYMENT REJECTED")
    elif data.startswith("catback:"):
        pid = int(data.split(":")[1]); r = rows("SELECT category_id FROM products WHERE id=?", (pid,))
        await q.edit_message_text("Products:", reply_markup=products_kb(r[0][0]) if r else categories_kb())
    else:
        await q.edit_message_text("Please choose an option below.", reply_markup=main_menu())


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text or msg.text.startswith("/"):
        return
    flow = context.user_data.get("flow")
    if flow == "awaiting_proof_order":
        return
    if not flow:
        return
    if not is_admin(update):
        return
    t = msg.text.strip()
    async def ask(s): await msg.reply_text(s)
    async def done(s="✅ Saved."):
        context.user_data.pop("flow", None)
        await msg.reply_text(s, reply_markup=admin_menu())
    if flow == "add_cat_name":
        if not t: return await ask("Category name cannot be empty.")
        context.user_data["new_cat_name"] = t; context.user_data["flow"] = "add_cat_subtitle"; return await ask("Send a subtitle, or send - for none:")
    if flow == "add_cat_subtitle":
        name = context.user_data.pop("new_cat_name", "New Category"); sub = "" if t == "-" else t
        pos = rows("SELECT COALESCE(MAX(position),0)+1 FROM categories")[0][0]
        cid = run("INSERT INTO categories(name,subtitle,position) VALUES(?,?,?)", (name,sub,pos))
        return await done(f"✅ Category added. Category ID: {cid}\nUse this ID when adding products.")
    if flow in ("edit_cat_id","delete_cat_id","toggle_cat_id","move_cat_id"):
        if not t.isdigit() or not rows("SELECT id FROM categories WHERE id=?", (int(t),)): return await ask("❌ Invalid Category ID. Open Categories → List categories and send the number shown after ‘ID’.")
        cid = int(t)
        if flow == "edit_cat_id": context.user_data["edit_cat_id"] = cid; context.user_data["flow"] = "edit_cat_field"; return await ask("Type name or subtitle:")
        if flow == "delete_cat_id":
            pids = [r[0] for r in rows("SELECT id FROM products WHERE category_id=?", (cid,))]
            for pid in pids: run("DELETE FROM plans WHERE product_id=?", (pid,))
            run("DELETE FROM products WHERE category_id=?", (cid,)); run("DELETE FROM categories WHERE id=?", (cid,)); return await done("🗑️ Category and its products/plans deleted.")
        if flow == "toggle_cat_id":
            vis = rows("SELECT visible FROM categories WHERE id=?", (cid,))[0][0]; run("UPDATE categories SET visible=? WHERE id=?", (0 if vis else 1,cid)); return await done("✅ Category visibility updated.")
        context.user_data["move_cat_id"] = cid; context.user_data["flow"] = "move_cat_pos"; return await ask("Send the new position (1, 2, 3...).")
    if flow == "edit_cat_field":
        if t.lower() not in ("name","subtitle"): return await ask("Please type exactly: name or subtitle")
        context.user_data["edit_cat_field"] = t.lower(); context.user_data["flow"] = "edit_cat_value"; return await ask("Send the new value:")
    if flow == "edit_cat_value":
        run(f"UPDATE categories SET {context.user_data.pop('edit_cat_field')}=? WHERE id=?", (t,context.user_data.pop("edit_cat_id"))); return await done("✅ Category updated.")
    if flow == "move_cat_pos":
        if not t.isdigit() or int(t)<1: return await ask("Position must be 1 or greater.")
        run("UPDATE categories SET position=? WHERE id=?", (int(t),context.user_data.pop("move_cat_id"))); return await done("🔀 Category order updated.")
    if flow == "add_prod_cat":
        if not t.isdigit() or not rows("SELECT id FROM categories WHERE id=?", (int(t),)): return await ask("❌ Invalid Category ID. Use one of the IDs listed above, e.g. 1 — AIM HACK means send 1.")
        context.user_data["new_prod_cat"] = int(t); context.user_data["flow"] = "add_prod_name"; return await ask("Send product name:")
    if flow == "add_prod_name":
        context.user_data["new_prod_name"] = t; context.user_data["flow"] = "add_prod_desc"; return await ask("Send product description, or - for none:")
    if flow == "add_prod_desc":
        context.user_data["new_prod_desc"] = "" if t == "-" else t; context.user_data["flow"] = "add_prod_plan_name"; return await ask("Send the first plan name (example: 1 Month):")
    if flow == "add_prod_plan_name":
        context.user_data["new_plan_name"] = t; context.user_data["flow"] = "add_prod_price"; return await ask("Send plan price in INR (example: 99 or 99.50):")
    if flow == "add_prod_price":
        try: price = float(t); assert price >= 0
        except Exception: return await ask("Enter a valid price, e.g. 99 or 99.50.")
        context.user_data["new_plan_price"] = price; context.user_data["flow"] = "add_prod_stock"; return await ask("Send stock quantity (0 or higher):")
    if flow == "add_prod_stock":
        if not t.isdigit(): return await ask("Stock must be a whole number, e.g. 10.")
        cid = context.user_data.pop("new_prod_cat"); name = context.user_data.pop("new_prod_name"); desc = context.user_data.pop("new_prod_desc")
        pos = rows("SELECT COALESCE(MAX(position),0)+1 FROM products WHERE category_id=?", (cid,))[0][0]
        pid = run("INSERT INTO products(category_id,name,description,position) VALUES(?,?,?,?)", (cid,name,desc,pos))
        plan_id = run("INSERT INTO plans(product_id,name,price,stock) VALUES(?,?,?,?)", (pid,context.user_data.pop("new_plan_name"),context.user_data.pop("new_plan_price"),int(t)))
        return await done(f"✅ Product and first plan added.\nProduct ID: {pid}\nPlan ID: {plan_id}")
    if flow == "add_plan_product":
        if not t.isdigit() or not rows("SELECT id FROM products WHERE id=?", (int(t),)): return await ask("Invalid Product ID. See Products → List products / plans.")
        context.user_data["new_plan_product"] = int(t); context.user_data["flow"] = "add_plan_name"; return await ask("Send the new plan name:")
    if flow == "add_plan_name":
        context.user_data["new_plan_name"] = t; context.user_data["flow"] = "add_plan_price"; return await ask("Send plan price in INR:")
    if flow == "add_plan_price":
        try: price=float(t); assert price >= 0
        except Exception: return await ask("Enter a valid non-negative price.")
        context.user_data["new_plan_price"] = price; context.user_data["flow"] = "add_plan_stock"; return await ask("Send stock quantity:")
    if flow == "add_plan_stock":
        if not t.isdigit(): return await ask("Stock must be a whole number.")
        plan_id = run("INSERT INTO plans(product_id,name,price,stock) VALUES(?,?,?,?)", (context.user_data.pop("new_plan_product"),context.user_data.pop("new_plan_name"),context.user_data.pop("new_plan_price"),int(t)))
        return await done(f"✅ Additional plan added. Plan ID: {plan_id}")
    if flow == "edit_prod_id":
        if not t.isdigit() or not rows("SELECT id FROM products WHERE id=?", (int(t),)): return await ask("Invalid Product ID. Check Products → List products / plans.")
        context.user_data["edit_prod_id"] = int(t); context.user_data["flow"] = "edit_prod_field"; return await ask("Type name, description, or category_id:")
    if flow == "edit_prod_field":
        if t.lower() not in ("name","description","category_id"): return await ask("Use name, description, or category_id.")
        context.user_data["edit_prod_field"] = t.lower(); context.user_data["flow"] = "edit_prod_value"; return await ask("Send the new value:")
    if flow == "edit_prod_value":
        pid = context.user_data["edit_prod_id"]; field = context.user_data["edit_prod_field"]
        if field == "category_id" and (not t.isdigit() or not rows("SELECT id FROM categories WHERE id=?", (int(t),))): return await ask("Invalid Category ID. Please send a valid category number.")
        run(f"UPDATE products SET {field}=? WHERE id=?", (int(t) if field=="category_id" else t,pid)); context.user_data.pop("edit_prod_id",None); context.user_data.pop("edit_prod_field",None); return await done("✅ Product updated.")
    if flow == "edit_plan_id":
        if not t.isdigit() or not rows("SELECT id FROM plans WHERE id=?", (int(t),)): return await ask("Invalid Plan ID. Check Products → List products / plans.")
        context.user_data["edit_plan_id"] = int(t); context.user_data["flow"] = "edit_plan_field"; return await ask("Type name, price, or stock:")
    if flow == "edit_plan_field":
        if t.lower() not in ("name","price","stock"): return await ask("Use name, price, or stock.")
        context.user_data["edit_plan_field"] = t.lower(); context.user_data["flow"] = "edit_plan_value"; return await ask("Send the new value:")
    if flow == "edit_plan_value":
        field=context.user_data.pop("edit_plan_field"); pid=context.user_data.pop("edit_plan_id")
        if field == "price":
            try: value=float(t); assert value>=0
            except Exception: context.user_data["edit_plan_field"]=field; context.user_data["edit_plan_id"]=pid; context.user_data["flow"]="edit_plan_value"; return await ask("Enter a valid non-negative price.")
        elif field == "stock":
            if not t.isdigit(): context.user_data["edit_plan_field"]=field; context.user_data["edit_plan_id"]=pid; context.user_data["flow"]="edit_plan_value"; return await ask("Stock must be a whole number.")
            value=int(t)
        else: value=t
        run(f"UPDATE plans SET {field}=? WHERE id=?", (value,pid)); return await done("✅ Plan updated.")
    if flow == "delete_prod_id":
        if not t.isdigit() or not rows("SELECT id FROM products WHERE id=?", (int(t),)): return await ask("Invalid Product ID.")
        pid=int(t); run("DELETE FROM plans WHERE product_id=?", (pid,)); run("DELETE FROM products WHERE id=?", (pid,)); return await done("🗑️ Product and its plans deleted.")
    if flow == "toggle_prod_id":
        if not t.isdigit() or not rows("SELECT id FROM products WHERE id=?", (int(t),)): return await ask("Invalid Product ID.")
        pid=int(t); vis=rows("SELECT visible FROM products WHERE id=?",(pid,))[0][0]; run("UPDATE products SET visible=? WHERE id=?",(0 if vis else 1,pid)); return await done("✅ Product visibility updated.")
    if flow == "move_prod_id":
        if not t.isdigit() or not rows("SELECT id FROM products WHERE id=?", (int(t),)): return await ask("Invalid Product ID.")
        context.user_data["move_prod_id"]=int(t); context.user_data["flow"]="move_prod_cat"; cats=rows("SELECT id,name FROM categories ORDER BY position,id"); return await ask("Send destination Category ID:\n"+"\n".join(f"{i} — {n}" for i,n in cats))
    if flow == "move_prod_cat":
        if not t.isdigit() or not rows("SELECT id FROM categories WHERE id=?", (int(t),)): return await ask("Invalid Category ID.")
        context.user_data["move_prod_cat"]=int(t); context.user_data["flow"]="move_prod_pos"; return await ask("Send position number (1, 2, 3...).")
    if flow == "move_prod_pos":
        if not t.isdigit() or int(t)<1: return await ask("Position must be 1 or greater.")
        run("UPDATE products SET category_id=?,position=? WHERE id=?", (context.user_data.pop("move_prod_cat"),int(t),context.user_data.pop("move_prod_id"))); return await done("🔀 Product moved/reordered.")
    if flow == "payment_instructions":
        set_setting("payment_instructions",t); return await done("✅ Payment instructions saved. Buyers will see these after choosing a plan. Please test them with a small test order.")
    if flow == "welcome":
        set_setting("welcome",t); return await done("✨ Welcome text updated.")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    # Admin media setup takes priority.
    if is_admin(update) and context.user_data.get("flow") == "welcome_media_choice":
        if msg.photo:
            set_setting("welcome_logo_file_id", msg.photo[-1].file_id); set_setting("welcome_animation", "")
            context.user_data.pop("flow", None)
            return await msg.reply_text("✅ Welcome logo saved. Send /start to preview.", reply_markup=admin_menu())
        if msg.animation or msg.video:
            media = msg.animation or msg.video
            set_setting("welcome_animation", media.file_id); context.user_data.pop("flow", None)
            return await msg.reply_text("✅ Welcome animation saved. Send /start to preview.", reply_markup=admin_menu())
        return await msg.reply_text("Please send a photo, GIF, or video.")
    # Customer payment proof submission.
    oid = context.user_data.get("awaiting_proof_order")
    if oid and (msg.photo or msg.document):
        order = rows("SELECT user_id,product_name,plan_name,price,status FROM orders WHERE id=?", (oid,))
        if not order or order[0][0] != user.id or order[0][4] != "awaiting_payment":
            context.user_data.pop("awaiting_proof_order", None)
            return await msg.reply_text("This order is no longer waiting for proof. Use /start to return to the store.")
        file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
        run("UPDATE orders SET status='proof_submitted',proof_file_id=? WHERE id=?", (file_id,oid))
        context.user_data.pop("awaiting_proof_order", None)
        await msg.reply_text(f"📨 Payment proof received for order #{oid}. An admin will review it. Delivery is sent only after manual approval.")
        for admin_id in ADMIN_IDS:
            try:
                caption = f"🧾 PAYMENT REVIEW · ORDER #{oid}\nUser ID: {user.id}\nUsername/name: {user.username or user.full_name}\nProduct: {order[0][1]}\nPlan: {order[0][2]}\nAmount: ₹{order[0][3]:.2f}\n\nReview the screenshot before approving."
                if msg.photo:
                    await context.bot.send_photo(admin_id, file_id, caption=caption, reply_markup=order_admin_kb(oid))
                else:
                    await context.bot.send_document(admin_id, file_id, caption=caption, reply_markup=order_admin_kb(oid))
            except Exception:
                log.exception("Could not notify admin %s for order %s", admin_id, oid)
        return
    if is_admin(update) and context.user_data.get("flow") == "welcome_media_choice":
        return await msg.reply_text("Send a photo, GIF, or video.")


async def deliver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return await deny(update)
    msg = update.effective_message
    if len(context.args) < 2:
        return await msg.reply_text("Usage: /deliver ORDER_ID delivery-text\nExample: /deliver 12 Your product code is ABC123")
    if not context.args[0].isdigit(): return await msg.reply_text("Order ID must be a number.")
    oid = int(context.args[0]); content = " ".join(context.args[1:]).strip()
    order = rows("SELECT user_id,status,price,plan_id FROM orders WHERE id=?", (oid,))
    if not order: return await msg.reply_text("Order ID not found.")
    if order[0][1] != "approved_awaiting_delivery": return await msg.reply_text("Payment must be approved first. Use /admin → Orders / Payments.")
    user_id,status,price,plan_id = order[0]
    await context.bot.send_message(user_id, f"🎉 YOUR ELITE X ORDER IS READY!\n━━━━━━━━━━━━━━━━━━\nOrder: #{oid}\nDelivery:\n{content}\n━━━━━━━━━━━━━━━━━━\nThank you for choosing ELITE X CONFIG.")
    run("UPDATE orders SET status='delivered' WHERE id=?", (oid,))
    run("UPDATE plans SET stock=CASE WHEN stock>0 THEN stock-1 ELSE 0 END WHERE id=?", (plan_id,))
    await msg.reply_text(f"✅ Order #{oid} delivered successfully. Stock updated.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("flow", None); context.user_data.pop("awaiting_proof_order", None)
    await update.effective_message.reply_text("Cancelled. Use /admin or /start to continue.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled error: %s", context.error)


def main():
    if not BOT_TOKEN:
        raise SystemExit("Missing BOT_TOKEN. Add it in Render → Environment.")
    if not ADMIN_IDS:
        raise SystemExit("Missing ADMIN_IDS. Add your numeric Telegram ID in Render → Environment.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("deliver", deliver))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler((filters.PHOTO | filters.ANIMATION | filters.VIDEO | filters.Document.ALL), handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    app.add_error_handler(error_handler)
    log.info("ELITE X CONFIG BOT started; admins=%s; db=%s", sorted(ADMIN_IDS), DB_PATH)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
