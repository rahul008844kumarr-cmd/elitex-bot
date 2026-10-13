import telebot
import sqlite3
import logging
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

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


def db_query(q, p=(), f1=False, fa=False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(q, p)
        if f1:
            r = c.fetchone()
        elif fa:
            r = c.fetchall()
        else:
            r = None
        conn.commit()
        return r
    except Exception as e:
        logger.error("DB Error: " + str(e))
        conn.rollback()
        return None
    finally:
        conn.close()


def get_setting(k, d=""):
    v = db_query("SELECT value FROM settings WHERE key=?", (k,), f1=True)
    return v[0] if v and v[0] else d


def set_setting(k, v):
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, balance REAL DEFAULT 0.0, orders_count INTEGER DEFAULT 0, spent REAL DEFAULT 0.0, joined_date TEXT, is_banned INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, is_active INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER DEFAULT 0, category_id INTEGER, name TEXT, price_inr REAL DEFAULT 0.0, stock INTEGER DEFAULT 0, apk_link TEXT, is_active INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS product_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, key_text TEXT, is_used INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_name TEXT, price_paid REAL, delivered_key TEXT, purchase_date TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('bot_status', 'ON'))
    conn.commit()
    conn.close()


init_db()


def main_menu_kb(is_admin=False):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🛒 Product Store", callback_data="store"))
    kb.add(InlineKeyboardButton("👤 My Profile", callback_data="profile"))
    kb.add(InlineKeyboardButton("💰 Add Balance", callback_data="add_balance"))
    kb.add(InlineKeyboardButton("📞 Support", callback_data="support"))
    if is_admin:
        kb.add(InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
    return kb


def back_kb(t="main"):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back", callback_data=t))
    return kb


def categories_kb():
    cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fa=True)
    kb = InlineKeyboardMarkup(row_width=1)
    if not cats:
        kb.add(InlineKeyboardButton("❌ No categories", callback_data="noop"))
    else:
        for c in cats:
            kb.add(InlineKeyboardButton("📁 " + c[1], callback_data="cat_" + str(c[0])))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="main"))
    return kb


def admin_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ Add Category", callback_data="a_add_cat"))
    kb.add(InlineKeyboardButton("✏️ Edit/Del Cat", callback_data="a_edit_cat"))
    kb.add(InlineKeyboardButton("➕ Add Product", callback_data="a_add_prod"))
    kb.add(InlineKeyboardButton("✏️ Edit/Del Prod", callback_data="a_edit_prod"))
    kb.add(InlineKeyboardButton("🔑 Add Keys", callback_data="a_add_keys"))
    kb.add(InlineKeyboardButton("📊 Stats", callback_data="a_stats"))
    kb.add(InlineKeyboardButton("💰 Add Balance", callback_data="a_add_bal"))
    kb.add(InlineKeyboardButton("📢 Broadcast", callback_data="a_broadcast"))
    kb.add(InlineKeyboardButton("🚫 Ban/Unban", callback_data="a_ban"))
    kb.add(InlineKeyboardButton("🔛 Bot ON/OFF", callback_data="a_toggle_bot"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="main"))
    return kb


@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.from_user.id
    u = db_query("SELECT user_id FROM users WHERE user_id=?", (uid,), f1=True)
    if not u:
        db_query("INSERT INTO users (user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)",
                 (uid, message.from_user.first_name, message.from_user.username or "", datetime.now().strftime("%Y-%m-%d")))
    is_admin = (uid == ADMIN_ID)
    text = "✦ <b>" + BOT_NAME + "</b> ✦\n<i>Premium Digital Marketplace</i>\n━━━━━━━━━━━━━━━━━━\n\nWelcome, <b>" + message.from_user.first_name + "</b>! 👋\n\n🛒 <b>Product Store</b>\n👤 <b>My Profile</b>\n💰 <b>Add Balance</b>\n📞 <b>Support</b>\n\n👇 <i>Select an option</i>"
    bot.send_message(uid, text, reply_markup=main_menu_kb(is_admin))


@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Admin only!")
        return
    bot.send_message(message.chat.id, "⚙️ <b>Admin Panel</b>\n\nSelect action 👇", reply_markup=admin_kb())


@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    uid = call.from_user.id
    data = call.data

    if uid != ADMIN_ID:
        u = db_query("SELECT is_banned FROM users WHERE user_id=?", (uid,), f1=True)
        if u and u[0] == 1:
            bot.answer_callback_query(call.id, "⛔ You are banned!", show_alert=True)
            return

    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    if data == "main":
        is_admin = (uid == ADMIN_ID)
        text = "✦ <b>" + BOT_NAME + "</b> ✦\n\nWelcome back!"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu_kb(is_admin))
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=main_menu_kb(is_admin))
        bot.answer_callback_query(call.id)
        return

    if data == "profile":
        u = db_query("SELECT balance, orders_count, spent, is_vip FROM users WHERE user_id=?", (uid,), f1=True)
        if not u:
            bot.answer_callback_query(call.id, "Please /start first", show_alert=True)
            return
        vip = "💎 VIP" if u[3] else "Regular"
        text = "👤 <b>Your Profile</b>\n━━━━━━━━━━━━━━━━━━\n\n🆔 ID: <code>" + str(uid) + "</code>\n📛 Name: " + call.from_user.first_name + "\n💠 Account: " + vip + "\n\n💰 Balance: " + fmt_curr(safe_float(u[0])) + "\n📦 Orders: " + str(u[1] or 0) + "\n💸 Spent: " + fmt_curr(safe_float(u[2]))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id)
        return

    if data == "store":
        text = "🛒 <b>Product Store</b>\n━━━━━━━━━━━━━━━━━━\n\n📁 <i>Select category:</i>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=categories_kb())
        bot.answer_callback_query(call.id)
        return

    if data == "add_balance":
        text = "💰 <b>Add Balance</b>\n━━━━━━━━━━━━━━━━━━\n\nContact: " + ADMIN_CONTACT + "\n\n<i>Send payment screenshot to admin.</i>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id)
        return

    if data == "support":
        text = "📞 <b>Support</b>\n\n👤 " + ADMIN_CONTACT + "\n\n<i>We reply within 24 hours.</i>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id)
        return

    if data.startswith("cat_"):
        cid = int(data[4:])
        c = db_query("SELECT name FROM categories WHERE id=?", (cid,), f1=True)
        cname = c[0] if c else "Category"
        prods = db_query("SELECT id, name, price_inr, stock FROM products WHERE category_id=? AND parent_id=0 AND is_active=1", (cid,), fa=True)
        if not prods:
            bot.answer_callback_query(call.id, "No products yet.", show_alert=True)
            return
        text = "📁 <b>" + cname + "</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        kb = InlineKeyboardMarkup(row_width=1)
        for p in prods:
            pid = p[0]
            subs = db_query("SELECT COUNT(*) FROM products WHERE parent_id=?", (pid,), f1=True)[0]
            if subs > 0:
                text = text + "📦 <b>" + p[1] + "</b> — " + str(subs) + " plans\n"
            else:
                text = text + "• <b>" + p[1] + "</b> — " + fmt_curr(safe_float(p[2])) + " (Stock: " + str(p[3] or 0) + ")\n"
            kb.add(InlineKeyboardButton("📦 " + p[1][:30], callback_data="prod_" + str(pid)))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="store"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("prod_"):
        pid = int(data[5:])
        subs = db_query("SELECT id, name, price_inr, stock FROM products WHERE parent_id=? AND is_active=1", (pid,), fa=True)
        if subs:
            p = db_query("SELECT name, parent_id, category_id FROM products WHERE id=?", (pid,), f1=True)
            text = "📦 <b>" + p[0] + "</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            kb = InlineKeyboardMarkup(row_width=1)
            for s in subs:
                subsub = db_query("SELECT COUNT(*) FROM products WHERE parent_id=?", (s[0],), f1=True)[0]
                if subsub > 0:
                    text = text + "📁 <b>" + s[1] + "</b> — " + str(subsub) + " items\n"
                else:
                    st = "✅ In Stock" if (s[3] or 0) > 0 else "❌ Out of Stock"
                    text = text + "✅ <b>" + s[1] + "</b>\n💰 " + fmt_curr(safe_float(s[2])) + "\n📦 " + st + "\n\n"
                kb.add(InlineKeyboardButton("🛍️ " + s[1][:30], callback_data="prod_" + str(s[0])))
            if p and p[1] != 0:
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="prod_" + str(p[1])))
            else:
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="cat_" + str(p[2])))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        else:
            p = db_query("SELECT name, price_inr, stock FROM products WHERE id=?", (pid,), f1=True)
            if not p:
                bot.answer_callback_query(call.id, "Not found.", show_alert=True)
                return
            if (p[2] or 0) <= 0:
                bot.answer_callback_query(call.id, "Out of stock!", show_alert=True)
                return
            u2 = db_query("SELECT balance FROM users WHERE user_id=?", (uid,), f1=True)
            bal = safe_float(u2[0]) if u2 else 0.0
            text = "🛍️ <b>" + p[0] + "</b>\n━━━━━━━━━━━━━━━━━━\n\n💰 Price: " + fmt_curr(safe_float(p[1])) + "\n📦 Stock: " + str(p[2]) + "\n\nYour Balance: " + fmt_curr(bal)
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(InlineKeyboardButton("✅ Buy Now", callback_data="buy_" + str(pid)))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="store"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("buy_"):
        pid = int(data[4:])
        p = db_query("SELECT name, price_inr, stock FROM products WHERE id=?", (pid,), f1=True)
        if not p:
            bot.answer_callback_query(call.id, "Not found.", show_alert=True)
            return
        price = safe_float(p[1])
        if (p[2] or 0) <= 0:
            bot.answer_callback_query(call.id, "Out of stock!", show_alert=True)
            return
        u = db_query("SELECT balance FROM users WHERE user_id=?", (uid,), f1=True)
        bal = safe_float(u[0]) if u else 0.0
        if bal < price:
            bot.answer_callback_query(call.id, "Insufficient! Need " + fmt_curr(price - bal), show_alert=True)
            return
        kr = db_query("SELECT id, key_text FROM product_keys WHERE product_id=? AND is_used=0 LIMIT 1", (pid,), f1=True)
        if not kr:
            bot.answer_callback_query(call.id, "No keys in stock.", show_alert=True)
            return
        db_query("UPDATE product_keys SET is_used=1 WHERE id=?", (kr[0],))
        db_query("UPDATE products SET stock = stock - 1 WHERE id=?", (pid,))
        db_query("UPDATE users SET balance = balance - ?, orders_count = orders_count + 1, spent = spent + ? WHERE user_id=?", (price, price, uid))
        db_query("INSERT INTO orders (user_id, product_name, price_paid, delivered_key, purchase_date) VALUES (?, ?, ?, ?, ?)",
                 (uid, p[0], price, kr[1], datetime.now().strftime("%Y-%m-%d %H:%M")))
        text = "✅ <b>Purchase Successful</b>\n━━━━━━━━━━━━━━━━━━\n\n📦 " + p[0] + "\n💵 Paid: " + fmt_curr(price) + "\n\n🔑 <b>Your Key:</b>\n<code>" + kr[1] + "</code>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("main"))
        bot.answer_callback_query(call.id, "Done!")
        return

    if not data.startswith("a_"):
        bot.answer_callback_query(call.id)
        return

    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
        return

    if data == "admin_panel":
        bot.edit_message_text("⚙️ <b>Admin Panel</b>\n\nSelect action 👇", call.message.chat.id, call.message.message_id, reply_markup=admin_kb())
        bot.answer_callback_query(call.id)
        return

    if data == "a_stats":
        tu = db_query("SELECT COUNT(*) FROM users", f1=True)[0]
        to = db_query("SELECT COUNT(*) FROM orders", f1=True)[0]
        tp = db_query("SELECT COUNT(*) FROM products", f1=True)[0]
        tc = db_query("SELECT COUNT(*) FROM categories", f1=True)[0]
        text = "📊 <b>Bot Stats</b>\n━━━━━━━━━━━━━━━━━━\n\n👥 Users: <b>" + str(tu) + "</b>\n📦 Orders: <b>" + str(to) + "</b>\n🛒 Products: <b>" + str(tp) + "</b>\n📁 Categories: <b>" + str(tc) + "</b>\n🔛 Bot: <b>" + get_setting('bot_status', 'ON') + "</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_kb("admin_panel"))
        bot.answer_callback_query(call.id)
        return

    if data == "a_toggle_bot":
        cur = get_setting("bot_status", "ON")
        new = "OFF" if cur == "ON" else "ON"
        set_setting("bot_status", new)
        bot.answer_callback_query(call.id, "Bot is now " + new, show_alert=True)
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

    if data == "a_add_cat":
        m = bot.send_message(call.message.chat.id, "📁 <b>Send new category name:</b>")
        bot.register_next_step_handler(m, process_add_cat)
        bot.answer_callback_query(call.id)
        return

    if data == "a_edit_cat":
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fa=True)
        if not cats:
            bot.answer_callback_query(call.id, "No categories yet.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for c in cats:
            kb.add(InlineKeyboardButton("📁 " + c[1], callback_data="mcat_" + str(c[0])))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        bot.edit_message_text("📁 <b>Select category:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("mcat_"):
        cid = int(data[5:])
        c = db_query("SELECT name FROM categories WHERE id=?", (cid,), f1=True)
        if not c:
            bot.answer_callback_query(call.id, "Not found.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("✏️ Edit Name", callback_data="ecat_" + str(cid)))
        kb.add(InlineKeyboardButton("🗑️ Delete", callback_data="dcat_" + str(cid)))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="a_edit_cat"))
        bot.edit_message_text("📁 <b>" + c[0] + "</b>\n\n<b>What to do?</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("ecat_"):
        cid = int(data[5:])
        c = db_query("SELECT name FROM categories WHERE id=?", (cid,), f1=True)
        if not c:
            bot.answer_callback_query(call.id, "Not found.", show_alert=True)
            return
        m = bot.send_message(call.message.chat.id, "✏️ <b>Current:</b> " + c[0] + "\n\n<b>Send new name:</b>")
        bot.register_next_step_handler(m, process_edit_cat, cid)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("dcat_"):
        cid = int(data[5:])
        db_query("DELETE FROM products WHERE category_id=?", (cid,))
        db_query("DELETE FROM categories WHERE id=?", (cid,))
        bot.answer_callback_query(call.id, "✅ Deleted!", show_alert=True)
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fa=True)
        kb = InlineKeyboardMarkup(row_width=1)
        if cats:
            for c in cats:
                kb.add(InlineKeyboardButton("📁 " + c[1], callback_data="mcat_" + str(c[0])))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        try:
            bot.edit_message_text("📁 <b>Select category:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            pass
        return

    if data == "a_add_prod":
        cats = db_query("SELECT id, name FROM categories WHERE is_active=1", fa=True)
        if not cats:
            bot.answer_callback_query(call.id, "Pehle category add karein!", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for c in cats:
            kb.add(InlineKeyboardButton("📁 " + c[1], callback_data="ncat_" + str(c[0])))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        bot.edit_message_text("📁 <b>Select category:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("ncat_"):
        cid = int(data[5:])
        existing = db_query("SELECT id, name FROM products WHERE category_id=? AND parent_id=0", (cid,), fa=True)
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("📁 Top Level", callback_data="npar_" + str(cid) + "_0"))
        if existing:
            for e in existing:
                kb.add(InlineKeyboardButton(