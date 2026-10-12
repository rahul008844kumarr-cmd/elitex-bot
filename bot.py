import telebot
import sqlite3
import logging
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================================================
# CONFIG
# ==============================================================
BOT_TOKEN = "8851779409:AAHQxEuu8pDJTnr_5yBwQf3rUGVnKrhZKU8"
ADMIN_ID = 8467166339
ADMIN_CONTACT = "@elitexconfig"
BOT_NAME = "ELITE X CONFIG"
DB_PATH = "EliteX.dp"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


def fmt_curr(a):
    return f"₹{a:,.2f}"


def safe_float(v, d=0.0):
    if v is None or v == "":
        return d
    try:
        return float(v)
    except (ValueError, TypeError):
        return d


# ==============================================================
# DATABASE
# ==============================================================
def db_query(query, params=(), fetchone=False, fetchall=False):
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


def get_setting(key, default=""):
    v = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return v[0] if v and v[0] else default


def set_setting(key, value):
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT,
        balance REAL DEFAULT 0.0, orders_count INTEGER DEFAULT 0,
        spent REAL DEFAULT 0.0, joined_date TEXT,
        is_banned INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE,
        is_active INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER DEFAULT 0,
        category_id INTEGER, name TEXT, price_inr REAL DEFAULT 0.0,
        stock INTEGER DEFAULT 0, apk_link TEXT, is_active INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS product_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER,
        key_text TEXT, is_used INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        product_name TEXT, price_paid REAL, delivered_key TEXT,
        purchase_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('bot_status', 'ON'))
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
        InlineKeyboardButton("➕ Add Category", callback_data="a_add_cat"),
        InlineKeyboardButton("✏️ Edit/Delete Cat", callback_data="a_edit_cat"),
    )
    kb.add(
        InlineKeyboardButton("➕ Add Product", callback_data="a_add_prod"),
        InlineKeyboardButton("✏️ Edit/Delete Prod", callback_data="a_edit_prod"),
    )
    kb.add(
        InlineKeyboardButton("🔑 Add Keys", callback_data="a_add_keys"),
        InlineKeyboardButton("📊 Stats", callback_data="a_stats"),
    )
    kb.add(
        InlineKeyboardButton("💰 Add Balance", callback_data="a_add_bal"),
        InlineKeyboardButton("📢 Broadcast", callback_data="a_broadcast"),
    )
    kb.add(
        InlineKeyboardButton("🚫 Ban/Unban", callback_data="a_ban"),
        InlineKeyboardButton("🔛 Bot ON/OFF", callback_data="a_toggle_bot"),
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
# CALLBACK HANDLER
# ==============================================================
@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    uid = call.from_user.id
    data = call.data

    # Banned check
    if uid != ADMIN_ID:
        u = db_query("SELECT is_banned FROM users WHERE user_id=?", (uid,), fetchone=True)
        if u and u[0] == 1:
            bot.answer_callback_query(call.id, "⛔ You are banned!", show_alert=True)
            return

    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    # ---------- MAIN ----------
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
            f"👤 <b>Your Profile</b>\n━━━━━━━━━━━━━━━━━━\n\n"
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
        text = f"💰 <b>Add Balance</b>\n━━━━━━━━━━━━━━━━━━\n\nContact: {ADMIN_CONTACT}\n\n<i>Send payment screenshot to admin.</i>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id)
        return

    if data == "support":
        text = f"📞 <b>Support</b>\n\n👤 {ADMIN_CONTACT}\n\n<i>We reply within 24 hours.</i>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id)
        return

    # ---------- CATEGORY VIEW (user) ----------
    if data.startswith("cat_"):
        cat_id = int(data[4:])
        cat = db_query("SELECT name FROM categories WHERE id=?", (cat_id,), fetchone=True)
        cat_name = cat[0] if cat else "Category"
        prods = db_query(
            "SELECT id, name, price_inr, stock FROM products WHERE category_id=? AND parent_id=0 AND is_active=1",
            (cat_id,), fetchall=True
        )
        if not prods:
            bot.answer_callback_query(call.id, "No products yet.", show_alert=True)
            return
        text = f"📁 <b>{cat_name}</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        kb = InlineKeyboardMarkup(row_width=1)
        for p in prods:
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

    # ---------- PRODUCT VIEW (user) ----------
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
                    st = "✅ In Stock" if (sstock or 0) > 0 else "❌ Out of Stock"
                    text += f"✅ <b>{sname}</b>\n   💰 {fmt_curr(safe_float(sprice))}\n   📦 {st}\n\n"
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
                f"🛍️ <b>{name}</b>\n━━━━━━━━━━━━━━━━━━\n\n"
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
            bot.answer_callback_query(call.id, "Not found.", show_alert=True)
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
        kr = db_query("SELECT id, key_text FROM product_keys WHERE product_id=? AND is_used=0 LIMIT 1", (pid,), fetchone=True)
        if not kr:
            bot.answer_callback_query(call.id, "No keys in stock.", show_alert=True)
            return
        kid, ktext = kr
        db_query("UPDATE product_keys SET is_used=1 WHERE id=?", (kid,))
        db_query("UPDATE products SET stock = stock - 1 WHERE id=?", (pid,))
        db_query("UPDATE users SET balance = balance - ?, orders_count = orders_count + 1, spent = spent + ? WHERE user_id=?",
                 (price, price, uid))
        db_query("INSERT INTO orders (user_id, product_name, price_paid, delivered_key, purchase_date) VALUES (?, ?, ?, ?, ?)",
                 (uid, name, price, ktext, datetime.now().strftime("%Y-%m-%d %H:%M")))
        text = (
            f"✅ <b>Purchase Successful</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 {name}\n💵 Paid: {fmt_curr(price)}\n\n"
            f"🔑 <b>Your Key:</b>\n<code>{ktext}</code>"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id, "Done!")
        return

    # =========================================================
    # ADMIN HANDLERS (only admin)
    # =========================================================
    if not data.startswith("a_"):
        bot.answer_callback_query(call.id)
        return

    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
        return

    if data == "admin_panel":
        bot.edit_message_text("⚙️ <b>Admin Panel</b>\n\nSelect action 👇",
                              call.message.chat.id, call.message.message_id, reply_markup=admin_kb())
        bot.answer_callback_query(call.id)
        return

    # ---------- STATS ----------
    if data == "a_stats":
        tu = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
        to = db_query("SELECT COUNT(*) FROM orders", fetchone=True)[0]
        tp = db_query("SELECT COUNT(*) FROM products", fetchone=True)[0]
        tc = db_query("SELECT COUNT(*) FROM categories", fetchone=True)[0]
        text = (
            f"📊 <b>Bot Stats</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 Users: <b>{tu}</b>\n📦 Orders: <b>{to}</b>\n"
            f"🛒 Products: <b>{tp}</b>\n📁 Categories: <b>{tc}</b>\n"
            f"🔛 Bot: <b>{get_setting('bot_status','ON')}</b>"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("admin_panel"))
        bot.answer_callback_query(call.id)
        return

    if data == "a_toggle_bot":
        cur = get_setting("bot_status", "ON")
        new = "OFF" if cur == "ON" else "ON"
        set_setting("bot_status", new)
        bot.answer_callback_query(call.id, f"Bot is now {new}", show_alert=True)
        return

    if data == "a_broadcast":
        m = bot.send_message(call.message.chat.id, "📢 <b>Send message to broadcast:</b>")
        bot.register_next_step_handler(m, process_broadcast)
        bot.answer_callback_query(call.id)
        return

    if data == "a_add_bal":
        m = bot.send_message(call.message.chat.id, "💰 <b>Send user ID:</b>")
        bot.register_next_step_handler(m, process_bal_user)
        bot.answer_callback_query(call.id)
        return

    if data == "a_ban":
        m = bot.send_message(call.message.chat.id, "🚫 <b>Send user ID to ban/unban:</b>")
        bot.register_next_step_handler(m, process_ban)
        bot.answer_callback_query(call.id)
        return

    # ---------- ADD CATEGORY ----------
    if data == "a_add_cat":
        m = bot.send_message(call.message.chat.id, "📁 <b>Send new category name:</b>")
        bot.register_next_step_handler(m, process_add_cat)
        bot.answer_callback_query(call.id)
        return

    # ---------- EDIT / DELETE CATEGORY LIST ----------
    if data == "a_edit_cat":
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fetchall=True)
        if not cats:
            bot.answer_callback_query(call.id, "No categories yet.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for c in cats:
            kb.add(InlineKeyboardButton(f"📁 {c[1]}", callback_data=f"mcat_{c[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        bot.edit_message_text("📁 <b>Select category:</b>",
                              call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("mcat_"):
        cid = int(data[5:])
        c = db_query("SELECT name FROM categories WHERE id=?", (cid,), fetchone=True)
        if not c:
            bot.answer_callback_query(call.id, "Not found.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("✏️ Edit Name", callback_data=f"ecat_{cid}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"dcat_{cid}"),
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="a_edit_cat"))
        bot.edit_message_text(
            f"📁 <b>{c[0]}</b>\n\n<b>What to do?</b>",
            call.message.chat.id, call.message.message_id, reply_markup=kb
        )
        bot.answer_callback_query(call.id)
        return

    if data.startswith("ecat_"):
        cid = int(data[5:])
        c = db_query("SELECT name FROM categories WHERE id=?", (cid,), fetchone=True)
        if not c:
            bot.answer_callback_query(call.id, "Not found.", show_alert=True)
            return
        m = bot.send_message(call.message.chat.id, f"✏️ <b>Current:</b> {c[0]}\n\n<b>Send new name:</b>")
        bot.register_next_step_handler(m, process_edit_cat, cid)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("dcat_"):
        cid = int(data[5:])
        db_query("DELETE FROM products WHERE category_id=?", (cid,))
        db_query("DELETE FROM categories WHERE id=?", (cid,))
        bot.answer_callback_query(call.id, "✅ Deleted!", show_alert=True)
        # Refresh
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fetchall=True)
        kb = InlineKeyboardMarkup(row_width=1)
        if cats:
            for c in cats:
                kb.add(InlineKeyboardButton(f"📁 {c[1]}", callback_data=f"mcat_{c[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        try:
            bot.edit_message_text("📁 <b>Select category:</b>",
                                  call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            pass
        return

    # ---------- ADD PRODUCT ----------
    if data == "a_add_prod":
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fetchall=True)
        if not cats:
            bot.answer_callback_query(call.id, "Pehle category add karein!", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for c in cats:
            kb.add(InlineKeyboardButton(f"📁 {c[1]}", callback_data=f"ncat_{c[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        bot.edit_message_text("📁 <b>Select category:</b>",
                              call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("ncat_"):
        cid = int(data[5:])
        existing = db_query("SELECT id, name FROM products WHERE category_id=? AND parent_id=0", (cid,), fetchall=True)
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("📁 Top Level (Main Category)", callback_data=f"npar_{cid}_0"))
        if existing:
            for e in existing:
                kb.add(InlineKeyboardButton(f"└ 📦 {e[1]}", callback_data=f"npar_{cid}_{e[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="a_add_prod"))
        bot.edit_message_text("❓ <b>Kis ke andar daalna hai?</b>",
                              call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("npar_"):
        parts = data.split("_")
        cid = int(parts[1])
        par = int(parts[2])
        m = bot.send_message(call.message.chat.id, "✏️ <b>Send product/plan name:</b>")
        bot.register_next_step_handler(m, process_prod_name, cid, par)
        bot.answer_callback_query(call.id)
        return

    # ---------- EDIT / DELETE PRODUCT LIST ----------
    if data == "a_edit_prod":
        prods = db_query("SELECT id, name FROM products WHERE is_active=1 ORDER BY id DESC LIMIT 30", fetchall=True)
        if not prods:
            bot.answer_callback_query(call.id, "No products yet.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for p in prods:
            kb.add(InlineKeyboardButton(f"📦 {p[1][:30]}", callback_data=f"mprod_{p[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        bot.edit_message_text("📦 <b>Select product:</b>",
                              call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("mprod_"):
        pid = int(data[6:])
        p = db_query("SELECT name, price_inr, stock FROM products WHERE id=?", (pid,), fetchone=True)
        if not p:
            bot.answer_callback_query(call.id, "Not found.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton(f"✏️ Edit Name: {p[0][:20]}", callback_data=f"epn_{pid}"))
        kb.add(InlineKeyboardButton(f"💰 Edit Price: {fmt_curr(safe_float(p[1]))}", callback_data=f"epp_{pid}"))
        kb.add(InlineKeyboardButton(f"📦 Edit Stock: {p[2]}", callback_data=f"eps_{pid}"))
        kb.add(InlineKeyboardButton("🗑️ Delete", callback_data=f"dprod_{pid}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="a_edit_prod"))
        bot.edit_message_text(
            f"📦 <b>{p[0]}</b>\n\n<b>What to do?</b>",
            call.message.chat.id, call.message.message_id, reply_markup=kb
        )
        bot.answer_callback_query(call.id)
        return

    if data.startswith("epn_"):
        pid = int(data[4:])
        m = bot.send_message(call.message.chat.id, "✏️ <b>Send new name:</b>")
        bot.register_next_step_handler(m, process_edit_prod_name, pid)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("epp_"):
        pid = int(data[4:])
        m = bot.send_message(call.message.chat.id, "💰 <b>Send new price (₹):</b>")
        bot.register_next_step_handler(m, process_edit_prod_price, pid)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("eps_"):
        pid = int(data[4:])
        m = bot.send_message(call.message.chat.id, "📦 <b>Send new stock:</b>")
        bot.register_next_step_handler(m, process_edit_prod_stock, pid)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("dprod_"):
        pid = int(data[6:])
        db_query("DELETE FROM product_keys WHERE product_id=?", (pid,))
        db_query("DELETE FROM products WHERE id=?", (pid,))
        bot.answer_callback_query(call.id, "✅ Deleted!", show_alert=True)
        prods = db_query("SELECT id, name FROM products WHERE is_active=1 ORDER BY id DESC LIMIT 30", fetchall=True)
        kb = InlineKeyboardMarkup(row_width=1)
        if prods:
            for p in prods:
                kb.add(InlineKeyboardButton(f"📦 {p[1][:30]}", callback_data=f"mprod_{p[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        try:
            bot.edit_message_text("📦 <b>Select product:</b>",
                                  call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            pass
        return

    # ---------- ADD KEYS ----------
    if data == "a_add_keys":
        prods = db_query("SELECT id, name FROM products WHERE is_active=1 ORDER BY id DESC LIMIT 30", fetchall=True)
        if not prods:
            bot.answer_callback_query(call.id, "No products yet.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for p in prods:
            kb.add(InlineKeyboardButton(f"🔑 {p[1][:30]}", callback_data=f"akey_{p[0]}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        bot.edit_message_text("🔑 <b>Select product to add keys:</b>",
                              call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("akey_"):
        pid = int(data[5:])
        m = bot.send_message(call.message.chat.id, "🔑 <b>Send keys (one per line):</b>")
        bot.register_next_step_handler(m, process_add_keys, pid)
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id)


# ==============================================================
# NEXT STEP HANDLERS
# ==============================================================
def process_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    users = db_query("SELECT user_id FROM users", fetchall=True)
    sent, failed = 0, 0
    if users:
        for u in users:
            try:
                bot.send_message(u[0], message.text)
                sent += 1
            except Exception:
                failed += 1
    bot.send_message(message.chat.id, f"✅ Sent: {sent}, Failed: {failed}")


def process_bal_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        uid = int(message.text.strip())
        m = bot.send_message(message.chat.id, "💰 <b>Send amount (₹):</b>")
        bot.register_next_step_handler(m, process_bal_amount, uid)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid ID.")


def process_bal_amount(message, uid):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        amt = float(message.text.strip())
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, uid))
        bot.send_message(message.chat.id, f"✅ Added {fmt_curr(amt)}")
        try:
            bot.send_message(uid, f"💰 <b>Balance Added:</b> {fmt_curr(amt)}")
        except Exception:
            pass
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid amount.")


def process_ban(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        uid = int(message.text.strip())
        u = db_query("SELECT is_banned FROM users WHERE user_id=?", (uid,), fetchone=True)
        if not u:
            bot.send_message(message.chat.id, "❌ User not found.")
            return
        new = 0 if u[0] == 1 else 1
        db_query("UPDATE users SET is_banned=? WHERE user_id=?", (new, uid))
        bot.send_message(message.chat.id, f"✅ User {uid} now {'BANNED' if new else 'UNBANNED'}")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid ID.")


def