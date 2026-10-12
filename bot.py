import telebot
import sqlite3
import logging
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================================================
# BOT CONFIG
# ==============================================================
BOT_TOKEN = "8851779409:AAHQxEuu8pDJTnr_5yBwQf3rUGVnKrhZKU8"
ADMIN_ID = 8467166339
ADMIN_CONTACT = "@elitexconfig"
BOT_NAME = "ELITE X CONFIG"

DB_PATH = "EliteX.dp"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


def fmt_curr(amount: float) -> str:
    return f"₹{amount:,.2f}"


def safe_float(val, default=0.0):
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ==============================================================
# DATABASE
# ==============================================================
def db_query(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetchone:
            res = c.fetchone()
        elif fetchall:
            res = c.fetchall()
        else:
            res = None
        conn.commit()
        return res
    except Exception as e:
        logger.error(f"DB Error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def get_setting(key: str, default: str = "") -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return val[0] if val and val[0] else default


def set_setting(key: str, value: str):
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        balance REAL DEFAULT 0.0,
        orders_count INTEGER DEFAULT 0,
        spent REAL DEFAULT 0.0,
        joined_date TEXT,
        is_banned INTEGER DEFAULT 0,
        is_vip INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        is_active INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER DEFAULT 0,
        category_id INTEGER,
        name TEXT,
        price_inr REAL DEFAULT 0.0,
        stock INTEGER DEFAULT 0,
        apk_link TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS product_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        key_text TEXT,
        is_used INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_name TEXT,
        price_paid REAL,
        delivered_key TEXT,
        purchase_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS coupons (
        code TEXT PRIMARY KEY,
        amount REAL,
        uses_left INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('bot_status', 'ON'))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('reseller_status', 'ON'))
    conn.commit()
    conn.close()


init_db()
logger.info("Database ready")


# ==============================================================
# KEYBOARDS
# ==============================================================
def main_menu_kb(is_admin=False):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🛒 Product Store", callback_data="store"),
        InlineKeyboardButton("👤 My Profile", callback_data="profile"),
        InlineKeyboardButton("💰 Add Balance", callback_data="add_balance"),
        InlineKeyboardButton("📞 Support", callback_data="support"),
    )
    if is_admin:
        kb.add(InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
    return kb


def back_kb(target="main"):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back", callback_data=target))
    return kb


def categories_kb():
    cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fetchall=True)
    kb = InlineKeyboardMarkup(row_width=1)
    if not cats:
        kb.add(InlineKeyboardButton("❌ No categories yet", callback_data="noop"))
    else:
        for c in cats:
            kb.add(InlineKeyboardButton(f"📁 {c[1]}", callback_data=f"cat_{c[0]}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="main"))
    return kb


def admin_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Add Category", callback_data="admin_add_cat"),
        InlineKeyboardButton("✏️ Edit Category", callback_data="admin_edit_cat_list"),
    )
    kb.add(
        InlineKeyboardButton("🗑️ Delete Category", callback_data="admin_del_cat_list"),
        InlineKeyboardButton("📁 View All Categories", callback_data="admin_view_cat"),
    )
    kb.add(
        InlineKeyboardButton("➕ Add Product/Plan", callback_data="admin_add_prod"),
        InlineKeyboardButton("✏️ Edit Product", callback_data="admin_edit_prod_list"),
    )
    kb.add(
        InlineKeyboardButton("🗑️ Delete Product", callback_data="admin_del_prod_list"),
        InlineKeyboardButton("📦 View All Products", callback_data="admin_view_prod"),
    )
    kb.add(
        InlineKeyboardButton("🔑 Add Keys", callback_data="admin_add_keys_list"),
        InlineKeyboardButton("🗑️ Remove Keys", callback_data="admin_rem_keys_list"),
    )
    kb.add(
        InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
    )
    kb.add(
        InlineKeyboardButton("💰 Add Balance", callback_data="admin_add_balance"),
        InlineKeyboardButton("💸 Remove Balance", callback_data="admin_rem_balance"),
    )
    kb.add(
        InlineKeyboardButton("🚫 Ban/Unban", callback_data="admin_ban"),
        InlineKeyboardButton("🎟️ Coupons", callback_data="admin_coupons"),
    )
    kb.add(
        InlineKeyboardButton("🔛 Bot ON/OFF", callback_data="admin_toggle_bot"),
        InlineKeyboardButton("🔄 Reseller ON/OFF", callback_data="admin_toggle_reseller"),
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="main"))
    return kb


# ==============================================================
# COMMANDS
# ==============================================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.from_user.id
    u = db_query("SELECT user_id FROM users WHERE user_id=?", (uid,), fetchone=True)
    if not u:
        db_query(
            "INSERT INTO users (user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)",
            (uid, message.from_user.first_name, message.from_user.username or "", datetime.now().strftime("%Y-%m-%d"))
        )
    is_admin = (uid == ADMIN_ID)
    text = (
        f"✦ <b>{BOT_NAME}</b> ✦\n"
        f"<i>Premium Digital Marketplace</i>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Welcome, <b>{message.from_user.first_name}</b>! 👋\n\n"
        f"🛒 <b>Product Store</b>\n"
        f"👤 <b>My Profile</b>\n"
        f"💰 <b>Add Balance</b>\n"
        f"📞 <b>Support</b>\n\n"
        f"👇 <i>Select an option below</i>"
    )
    bot.send_message(uid, text, reply_markup=main_menu_kb(is_admin))


@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Admin only!")
        return
    bot.send_message(message.chat.id, "⚙️ <b>Admin Panel</b>\n\nSelect action 👇", reply_markup=admin_kb())


# ==============================================================
# CALLBACK HANDLERS
# ==============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    data = call.data

    u = db_query("SELECT is_banned FROM users WHERE user_id=?", (uid,), fetchone=True)
    if u and u[0] == 1 and uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ You are banned!", show_alert=True)
        return

    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    # ---------- MAIN MENU ----------
    if data == "main":
        is_admin = (uid == ADMIN_ID)
        text = f"✦ <b>{BOT_NAME}</b> ✦\n\nWelcome back, <b>{call.from_user.first_name}</b>!"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu_kb(is_admin))
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=main_menu_kb(is_admin))
        bot.answer_callback_query(call.id)
        return

    if data == "profile":
        u = db_query("SELECT balance, orders_count, spent, is_vip FROM users WHERE user_id=?", (uid,), fetchone=True)
        if not u:
            bot.answer_callback_query(call.id, "Please /start first", show_alert=True)
            return
        text = (
            f"👤 <b>Your Profile</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"📛 Name: {call.from_user.first_name}\n"
            f"💠 Account: {'💎 VIP' if u[3] else 'Regular'}\n\n"
            f"💰 Balance: {fmt_curr(safe_float(u[0]))}\n"
            f"📦 Orders: {u[1] or 0}\n"
            f"💸 Spent: {fmt_curr(safe_float(u[2]))}"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id)
        return

    if data == "store":
        text = "🛒 <b>Product Store</b>\n━━━━━━━━━━━━━━━━━━\n\n📁 <i>Select category:</i>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=categories_kb())
        bot.answer_callback_query(call.id)
        return

    if data == "add_balance":
        text = (
            f"💰 <b>Add Balance</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"Contact: {ADMIN_CONTACT}\n\n"
            f"<i>Send payment screenshot to admin for top-up.</i>"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id)
        return

    if data == "support":
        text = f"📞 <b>Support</b>\n\n👤 {ADMIN_CONTACT}\n\n<i>We reply within 24 hours.</i>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id)
        return

    # ---------- CATEGORY VIEW ----------
    if data.startswith("cat_"):
        cat_id = int(data[4:])
        cat = db_query("SELECT name FROM categories WHERE id=?", (cat_id,), fetchone=True)
        cat_name = cat[0] if cat else "Category"
        products = db_query(
            "SELECT id, name, price_inr, stock FROM products WHERE category_id=? AND parent_id=0 AND is_active=1",
            (cat_id,), fetchall=True
        )
        if not products:
            bot.answer_callback_query(call.id, "No products yet.", show_alert=True)
            return
        text = f"📁 <b>{cat_name}</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        kb = InlineKeyboardMarkup(row_width=1)
        for p in products:
            pid, name, price, stock = p
            subs = db_query("SELECT COUNT(*) FROM products WHERE parent_id=?", (pid,), fetchone=True)[0]
            if subs > 0:
                text += f"📦 <b>{name}</b> — {subs} plans\n"
            else:
                text += f"• <b>{name}</b> — {fmt_curr(safe_float(price))} (Stock: {stock or 0})\n"
            kb.add(InlineKeyboardButton(f"📦 {name[:30]}", callback_data=f"prod_{pid}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="store"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # ---------- PRODUCT VIEW ----------
    if data.startswith("prod_"):
        pid = int(data[5:])
        subs = db_query(
            "SELECT id, name, price_inr, stock FROM products WHERE parent_id=? AND is_active=1",
            (pid,), fetchall=True
        )
        if subs:
            p = db_query("SELECT name, parent_id, category_id FROM products WHERE id=?", (pid,), fetchone=True)
            pname = p[0] if p else "Product"
            text = f"📦 <b>{pname}</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            kb = InlineKeyboardMarkup(row_width=1)
            for s in subs:
                sid, sname, sprice, sstock = s
                subsub = db_query("SELECT COUNT(*) FROM products WHERE parent_id=?", (sid,), fetchone=True)[0]
                if subsub > 0:
                    text += f"📁 <b>{sname}</b> — {subsub} items\n"
                else:
                    stock_status = "✅ In Stock" if (sstock or 0) > 0 else "❌ Out of Stock"
                    text += f"✅ <b>{sname}</b>\n"
                    text += f"   💰 Price: {fmt_curr(safe_float(sprice))}\n"
                    text += f"   📦 {stock_status}\n\n"
                kb.add(InlineKeyboardButton(f"🛍️ {sname[:30]}", callback_data=f"prod_{sid}"))
            if p and p[1] != 0:
                kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"prod_{p[1]}"))
            else:
                kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"cat_{p[2]}"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        else:
            p = db_query("SELECT name, price_inr, stock FROM products WHERE id=?", (pid,), fetchone=True)
            if not p:
                bot.answer_callback_query(call.id, "Not found.", show_alert=True)
                return
            name, price, stock = p
            if (stock or 0) <= 0:
                bot.answer_callback_query(call.id, "Out of stock!", show_alert=True)
                return
            u2 = db_query("SELECT balance FROM users WHERE user_id=?", (uid,), fetchone=True)
            balance = safe_float(u2[0]) if u2 else 0.0
            price = safe_float(price)
            text = (
                f"🛍️ <b>{name}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 Price: {fmt_curr(price)}\n"
                f"📦 Stock: {stock}\n\n"
                f"Your Balance: {fmt_curr(balance)}"
            )
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(InlineKeyboardButton("✅ Buy Now", callback_data=f"buy_{pid}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="store"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # ---------- BUY ----------
    if data.startswith("buy_"):
        pid = int(data[4:])
        p = db_query("SELECT name, price_inr, stock FROM products WHERE id=?", (pid,), fetchone=True)
        if not p:
            bot.answer_callback_query(call.id, "Product not found.", show_alert=True)
            return
        name, price, stock = p
        price = safe_float(price)
        if (stock or 0) <= 0:
            bot.answer_callback_query(call.id, "Out of stock!", show_alert=True)
            return
        u = db_query("SELECT balance FROM users WHERE user_id=?", (uid,), fetchone=True)
        balance = safe_float(u[0]) if u else 0.0
        if balance < price:
            bot.answer_callback_query(call.id, f"Insufficient! Need {fmt_curr(price - balance)} more.", show_alert=True)
            return
        key_row = db_query(
            "SELECT id, key_text FROM product_keys WHERE product_id=? AND is_used=0 LIMIT 1",
            (pid,), fetchone=True
        )
        if not key_row:
            bot.answer_callback_query(call.id, "No keys in stock.", show_alert=True)
            return
        key_id, key_text = key_row
        db_query("UPDATE product_keys SET is_used=1 WHERE id=?", (key_id,))
        db_query("UPDATE products SET stock = stock - 1 WHERE id=?", (pid,))
        db_query(
            "UPDATE users SET balance = balance - ?, orders_count = orders_count + 1, spent = spent + ? WHERE user_id=?",
            (price, price, uid)
        )
        db_query(
            "INSERT INTO orders (user_id, product_name, price_paid, delivered_key, purchase_date) VALUES (?, ?, ?, ?, ?)",
            (uid, name, price, key_text, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        text = (
            f"✅ <b>Purchase Successful</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 {name}\n"
            f"💵 Paid: {fmt_curr(price)}\n\n"
            f"🔑 <b>Your Key:</b>\n<code>{key_text}</code>"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id, "Done!")
        return

    # ---------- ADMIN PANEL ----------
    if data == "admin_panel":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        bot.edit_message_text(
            "⚙️ <b>Admin Panel</b>\n\nSelect action 👇",
            call.message.chat.id, call.message.message_id, reply_markup=admin_kb()
        )
        bot.answer_callback_query(call.id)
        return

    # ---------- STATS ----------
    if data == "admin_stats":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        tu = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
        to = db_query("SELECT COUNT(*) FROM orders", fetchone=True)[0]
        tp = db_query("SELECT COUNT(*) FROM products", fetchone=True)[0]
        tc = db_query("SELECT COUNT(*) FROM categories", fetchone=True)[0]
        text = (
            f"📊 <b>Bot Stats</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 Users: <b>{tu}</b>\n"
            f"📦 Orders: <b>{to}</b>\n"
            f"🛒 Products: <b>{tp}</b>\n"
            f"📁 Categories: <b>{tc}</b>\n"
            f"🔛 Bot: <b>{get_setting('bot_status','ON')}</b>\n"
            f"🔄 Reseller: <b>{get_setting('reseller_status','ON')}</b>"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("admin_panel"))
        bot.answer_callback_query(call.id)
        return

    # ---------- TOGGLE ----------
    if data == "admin_toggle_bot":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        cur = get_setting("bot_status", "ON")
        new = "OFF" if cur == "ON" else "ON"
        set_setting("bot_status", new)
        bot.answer_callback_query(call.id, f"Bot is now {new}", show_alert=True)
        return

    if data == "admin_toggle_reseller":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        cur = get_setting("reseller_status", "ON")
        new = "OFF" if cur == "ON" else "ON"
        set_setting("reseller_status", new)
        bot.answer_callback_query(call.id, f"Reseller is now {new}", show_alert=True)
        return

    # ---------- BROADCAST ----------
    if data == "admin_broadcast":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "📢 <b>Send message to broadcast:</b>")
        bot.register_next_step_handler(msg, process_broadcast)
        bot.answer_callback_query(call.id)
        return

    # ---------- BALANCE ----------
    if data == "admin_add_balance":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "💰 <b>Send user ID to ADD balance:</b>")
        bot.register_next_step_handler(msg, process_bal_user_add)
        bot.answer_callback_query(call.id)
        return

    if data == "admin_rem_balance":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "💸 <b>Send user ID to REMOVE balance:</b>")
        bot.register_next_step_handler(msg, process_bal_user_rem)
        bot.answer_callback_query(call.id)
        return

    # ---------- BAN ----------
    if data == "admin_ban":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "🚫 <b>Send user ID to ban/unban:</b>")
        bot.register_next_step_handler(msg, process_ban)
        bot.answer_callback_query(call.id)
        return

    # ---------- CATEGORY ADD ----------
    if data == "admin_add_cat":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "📁 <b>Send new category name:</b>")
        bot.register_next_step_handler(msg, process_add_cat)
        bot.answer_callback_query(call.id)
        return

    # ---------- CATEGORY EDIT LIST ----------
    if data == "admin_edit_cat_list":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fetchall=True)
        if not cats:
            bot.answer_callback_query(call.id, "No categories yet.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for c in cats:
            kb.add(InlineKeyboardButton(f"✏️ {c[1]}", callback_data=f"editcat_{c[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        bot.edit_message_text("✏️ <b>Select category to edit:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("editcat_"):
        if uid != ADMIN_ID:
            return
        cid = int(data[8:])
        cat = db_query("SELECT name FROM categories WHERE id=?", (cid,), fetchone=True)
        if not cat:
            bot.answer_callback_query(call.id, "Not found.", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, f"✏️ <b>Current name:</b> {cat[0]}\n\n<b>Send new name:</b>")
        bot.register_next_step_handler(msg, process_edit_cat, cid)
        bot.answer_callback_query(call.id)
        return

    # ---------- CATEGORY DELETE LIST ----------
    if data == "admin_del_cat_list":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fetchall=True)
        if not cats:
            bot.answer_callback_query(call.id, "No categories yet.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for c in cats:
            kb.add(InlineKeyboardButton(f"🗑️ {c[1]}", callback_data=f"delcat_{c[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        bot.edit_message_text("🗑️ <b>Select category to delete:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("delcat_"):
        if uid != ADMIN_ID:
            return
        cid = int(data[7:])
        db_query("DELETE FROM products WHERE category_id=?", (cid,))
        db_query("DELETE FROM categories WHERE id=?", (cid,))
        bot.answer_callback_query(call.id, "✅ Category deleted!", show_alert=True)
        # Refresh list
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fetchall=True)
        kb = InlineKeyboardMarkup(row_width=1)
        if cats:
            for c in cats:
                kb.add(InlineKeyboardButton(f"🗑️ {c[1]}", callback_data=f"delcat_{c[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        try:
            bot.edit_message_text("🗑️ <b>Select category to delete:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            pass
        return

    # ---------- VIEW CATEGORIES ----------
    if data == "admin_view_cat":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fetchall=True)
        if not cats:
            bot.answer_callback_query(call.id, "No categories yet.", show_alert=True)
            return
        text = "📁 <b>All Categories:</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for c in cats:
            text += f"• <b>{c[1]}</b> (ID: {c[0]})\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("admin_panel"))
        bot.answer_callback_query(call.id)
        return

    # ---------- ADD PRODUCT ----------
    if data == "admin_add_prod":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fetchall=True)
        if not cats:
            bot.answer_callback_query(call.id, "Pehle category add karein!", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for c in cats:
            kb.add(InlineKeyboardButton(f"📁 {c[1]}", callback_data=f"newcat_{c[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        bot.edit_message_text("📁 <b>Select category:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("newcat_"):
        if uid != ADMIN_ID:
            return
        cat_id = int(data[7:])
        existing = db_query(
            "SELECT id, name FROM products WHERE category_id=? AND parent_id=0",
            (cat_id,), fetchall=True
        )
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("📁 Top Level (Main Category)", callback_data=f"newparent_{cat_id}_0"))
        if existing:
            for e in existing:
                kb.add(InlineKeyboardButton(f"└ 📦 {e[1]}", callback_data=f"newparent_{cat_id}_{e[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_add_prod"))
        bot.edit_message_text(
            "❓ <b>Kis ke andar daalna hai?</b>\n<i>(Top Level = main product, ya kisi product ke andar plan)</i>",
            call.message.chat.id, call.message.message_id, reply_markup=kb
        )
        bot.answer_callback_query(call.id)
        return

    if data.startswith("newparent_"):
        if uid != ADMIN_ID:
            return
        parts = data.split("_")
        cat_id = int(parts[1])
        parent_id = int(parts[2])
        msg = bot.send_message(call.message.chat.id, "✏️ <b>Send product/plan name:</b>")
        bot.register_next_step_handler(msg, process_prod_name, cat_id, parent_id)
        bot.answer_callback_query(call.id)
        return

    # ---------- EDIT PRODUCT LIST ----------
    if data == "admin_edit_prod_list":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
            return
        prods = db_query("SELECT id, name FROM products WHERE is_active=1 ORDER BY id DESC LIMIT 30", fetchall=True)
        if not prods:
            bot.answer_callback_query(call.id, "No products yet.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for p in prods:
            kb.add(InlineKeyboardButton(f"✏️ {p[1][:30]}", callback_data=f"editprod_{p[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        bot.edit_message_text("✏️ <b>Select product to edit:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("editprod_"):
        if uid != ADMIN_ID:
            return
        pid = int(data[9:])
        p = db_query("SELECT name, price_inr, stock FROM products WHERE id=?", (pid,), fetchone=True)
        if not p:
            bot.answer_callback_query(call.id, "Not found.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton(f"📝 Edit Name ({p[0]})", callback_data=f"editpname_{pid}"))
        kb.add(InlineKeyboardButton(f"💰 Edit Price ({fmt_curr(safe_float(p[1]))})", callback_data=f"editpprice_{pid}"))
        kb.add(InlineKeyboardButton(f"📦 Edit Stock ({p[2]})", callback_data=f"editpstock_{pid}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="