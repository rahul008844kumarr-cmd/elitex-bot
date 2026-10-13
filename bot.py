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
    return "₹" + str(round(a, 2))


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