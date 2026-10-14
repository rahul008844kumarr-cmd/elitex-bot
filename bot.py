#!/usr/bin/env python3
"""
ELITE X CONFIG - FINAL COMPLETE BOT
Flow: Category -> Product -> Payment -> Auto Key Delivery
Admin: Full CRUD for everything
"""
import asyncio
import sqlite3
import logging
import time
import os
import io
import aiohttp
from aiohttp import web
from datetime import datetime
from urllib.parse import quote
from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

try:
    import qrcode
except ImportError:
    qrcode = None

# ============ CONFIG ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "elitexbot")
BRAND_NAME = os.getenv("BRAND_NAME", "ELITE X CONFIG")
DB_PATH = os.getenv("DB_PATH", "elitex_bot.db")
VIP_DISCOUNT = 10.0
VIP_PRICE = 1000.0

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ============ HELPERS ============
def fmt(a):
    try: return f"₹{float(a):,.2f}"
    except: return "₹0.00"

def fancy(text):
    bc = {chr(ord("A")+i): chr(0x1D400+i) for i in range(26)}
    sc = {"a":"ᴀ","b":"ʙ","c":"ᴄ","d":"ᴅ","e":"ᴇ","f":"ꜰ","g":"ɢ","h":"ʜ","i":"ɪ","j":"ᴊ","k":"ᴋ","l":"ʟ","m":"ᴍ","n":"ɴ","o":"ᴏ","p":"ᴘ","q":"ǫ","r":"ʀ","s":"s","t":"ᴛ","u":"ᴜ","v":"ᴠ","w":"ᴡ","x":"x","y":"ʏ","z":"ᴢ"}
    out, at = [], True
    for ch in str(text):
        if ch.isascii() and ch.isalpha():
            out.append(bc.get(ch.upper(), ch) if at else sc.get(ch.lower(), ch))
            at = False
        else:
            out.append(ch)
            if ch.isspace() or ch in "/\\|•": at = True
    return "".join(out)

def sfloat(v, d=0.0):
    try: return float(v)
    except: return d

def upi_link(upi, name, amt, note=""):
    s = f"upi://pay?pa={quote(str(upi))}&pn={quote(str(name))}&am={amt:.2f}&cu=INR"
    if note: s += f"&tn={quote(str(note))}"
    return s

def make_qr(data):
    if qrcode is None: return None
    img = qrcode.make(data)
    buf = io.BytesIO(); buf.name = "qr.png"
    img.save(buf, format="PNG"); buf.seek(0)
    return buf

# ============ DB ============
def db(q, p=(), one=False, all=False, commit=True):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    try:
        c.execute(q, p)
        r = c.fetchone() if one else (c.fetchall() if all else None)
        if commit: conn.commit()
        return r
    except Exception as e:
        logger.error(f"DB error: {e} | Query: {q}")
        return None
    finally: conn.close()

def gs(k, d=""):
    v = db("SELECT value FROM settings WHERE key=?", (k,), one=True)
    return v[0] if v and v[0] else d

def ss(k, v):
    db("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (k, str(v)))

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT,
        username TEXT, balance REAL DEFAULT 0, is_reseller INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0, joined_date TEXT, last_gift TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, emoji TEXT DEFAULT '📂', is_active INTEGER DEFAULT 1, is_maintenance INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER, name TEXT, price REAL DEFAULT 0, reseller_price REAL DEFAULT 0,
        stock INTEGER DEFAULT 0, apk_link TEXT, validity TEXT, device_limit TEXT,
        is_active INTEGER DEFAULT 1, is_maintenance INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS product_keys (id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER, key_text TEXT, is_used INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, product_name TEXT, price_paid REAL, delivered_key TEXT,
        purchase_date TEXT, status TEXT DEFAULT 'delivered')""")
    c.execute("""CREATE TABLE IF NOT EXISTS balance_requests (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, username TEXT, amount REAL, method TEXT, proof_file_id TEXT,
        reference TEXT, status TEXT DEFAULT 'pending', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, message TEXT, status TEXT DEFAULT 'Open', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS coupons (code TEXT PRIMARY KEY, discount REAL,
        max_uses INTEGER, used INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS co_admins (user_id INTEGER PRIMARY KEY,
        name TEXT, added_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (order_id TEXT PRIMARY KEY,
        user_id INTEGER, amount REAL, status TEXT DEFAULT 'pending', created_at INTEGER,
        expires_at INTEGER, qr_data TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS menu_buttons (id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT, emoji TEXT DEFAULT '', action TEXT, position INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1, row_group INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS profile_fields (field_key TEXT PRIMARY KEY,
        label TEXT, is_visible INTEGER DEFAULT 1)""")
    defaults = {
        'welcome_text': '⚡ Welcome to ELITE X CONFIG ⚡',
        'upi_id': '', 'payee_name': BRAND_NAME,
        'support_telegram': 'https://t.me/YourSupport',
        'support_whatsapp': 'https://wa.me/YourNumber',
        'global_maintenance': '0', 'maintenance_msg': '🛠 Bot under maintenance.',
        'daily_gift_price': '0', 'refer_earn_amount': '0',
        'admin_logo_file_id': '',
        'ui_category_msg': '📂 Select a Category:',
        'ui_product_msg': '📦 Select a Product:',
        'ui_key_msg': '🎉 Thank you for your purchase!',
        'payment_mode': 'manual', 'auto_api_key': '', 'auto_api_url': '',
        'reseller_setup_fee': '500', 'reseller_min_balance': '1000',
        'reseller_system_status': 'ON', 'vip_system_status': 'ON'
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)", (k, v))
    if c.execute("SELECT COUNT(*) FROM menu_buttons").fetchone()[0] == 0:
        c.executemany("INSERT INTO menu_buttons (label,emoji,action,position,is_active,row_group) VALUES (?,?,?,?,1,?)",
                      [("Product Store","🛍️","shop",1,0), ("My Profile","👤","profile",2,1),
                       ("Add Balance","💰","addbalance",3,1), ("Support","🎧","support",4,2),
                       ("Daily Gift","🎁","daily_gift",5,2), ("Redeem Coupon","🎟️","redeem_coupon",6,3)])
    if c.execute("SELECT COUNT(*) FROM profile_fields").fetchone()[0] == 0:
        c.executemany("INSERT INTO profile_fields (field_key,label,is_visible) VALUES (?,?,1)",
                      [("user_id","User ID"),("name","Name"),("balance","Balance"),
                       ("account_type","Account Type"),("joined_date","Join Date"),
                       ("total_spent","Total Spent"),("total_orders","Total Orders")])
    conn.commit(); conn.close()

# ============ MIDDLEWARE ============
class MW(BaseMiddleware):
    async def __call__(self, handler, event, data):
        uid = event.from_user.id
        if uid != ADMIN_ID:
            u = db("SELECT is_banned FROM users WHERE user_id=?", (uid,), one=True)
            if u and u[0] == 1:
                if isinstance(event, Message): await event.answer("🚫 You are banned.")
                else: await event.answer("🚫 Banned", show_alert=True)
                return
            if gs("global_maintenance") == "1":
                msg = gs("maintenance_msg", "🛠 Maintenance.")
                if isinstance(event, Message): await event.answer(msg)
                else: await event.answer("⚠️ Maintenance", show_alert=True)
                return
        return await handler(event, data)

dp.message.middleware(MW())
dp.callback_query.middleware(MW())

# ============ FSM ============
class U(StatesGroup):
    ticket = State(); coupon = State(); custom_amt = State(); proof = State()

class A(StatesGroup):
    cat_name = State(); cat_emoji = State(); cat_edit = State()
    prod_cat = State(); prod_name = State(); prod_price = State(); prod_rprice = State()
    prod_validity = State(); prod_device = State(); prod_apk = State(); prod_keys = State()
    prod_edit = State(); prod_addkeys = State()
    user_search = State(); user_addbal = State(); user_rembal = State()
    bc_msg = State(); cp_code = State(); cp_disc = State(); cp_max = State()
    set_logo = State(); set_upi = State(); set_payee = State()
    set_tg = State(); set_wa = State(); set_gift = State(); set_refer = State()
    set_maint = State()
    msg_welcome = State(); msg_cat = State(); msg_prod = State(); msg_key = State()
    menu_add_label = State(); menu_add_emoji = State(); menu_add_action = State()
    menu_edit = State()
    set_auto_key = State(); set_auto_url = State()
    coadmin_add = State(); coadmin_remove = State(); ticket_reply = State()
    reseller_fee = State(); reseller_min = State()

# ============ KEYBOARDS ============
def main_menu_kb(uid=None):
    rows = []
    btns = db("SELECT id,label,emoji,action,row_group FROM menu_buttons WHERE is_active=1 ORDER BY position", all=True)
    grouped = {}
    for b in btns or []:
        grouped.setdefault(b[4] or 0, []).append(b)
    for rg in sorted(grouped.keys()):
        row = []
        for b in grouped[rg]:
            t = f"{b[2]} {fancy(b[1])}" if b[2] else fancy(b[1])
            row.append(InlineKeyboardButton(text=t, callback_data=f"act_{b[3]}", style="primary"))
        rows.append(row)
    if uid:
        u = db("SELECT is_reseller,is_vip FROM users WHERE user_id=?", (uid,), one=True)
        ex = []
        if u and u[0]: ex.append(InlineKeyboardButton(text=fancy("Reseller"), callback_data="act_reseller", style="success"))
        if u and u[1]: ex.append(InlineKeyboardButton(text=fancy("VIP Club"), callback_data="act_vip", style="danger"))
        if ex: rows.append(ex)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ "+fancy("Store Manager"), callback_data="adm_store", style="primary")],
        [InlineKeyboardButton(text="👥 "+fancy("User Manager"), callback_data="adm_users", style="success")],
        [InlineKeyboardButton(text="🎟️ "+fancy("Marketing"), callback_data="adm_mkt", style="primary")],
        [InlineKeyboardButton(text="🎨 "+fancy("Menu Designer"), callback_data="adm_menu", style="success")],
        [InlineKeyboardButton(text="🤝 "+fancy("Co-Admins"), callback_data="adm_coadmin", style="primary")],
        [InlineKeyboardButton(text="⚙️ "+fancy("Settings"), callback_data="adm_settings", style="primary")],
        [InlineKeyboardButton(text="🏠 "+fancy("User View"), callback_data="back_main", style="danger")]
    ])

def bk(cb="adm_back"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=fancy("Back"), callback_data=cb, style="danger")]])

# ============ START ============
@dp.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    if not db("SELECT user_id FROM users WHERE user_id=?", (uid,), one=True):
        db("INSERT INTO users (user_id,first_name,username,joined_date) VALUES (?,?,?,?)",
           (uid, m.from_user.first_name, m.from_user.username or "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    text = gs("welcome_text", "⚡ Welcome!")
    logo = gs("admin_logo_file_id")
    kb = main_menu_kb(uid)
    if logo:
        try:
            await m.answer_photo(logo, caption=text, reply_markup=kb)
            return
        except: pass
    await m.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.edit_text(gs("welcome_text", "⚡ Welcome!"), reply_markup=main_menu_kb(call.from_user.id))
    except:
        await bot.send_message(call.from_user.id, gs("welcome_text", "⚡ Welcome!"), reply_markup=main_menu_kb(call.from_user.id))

# ============ MENU ACTIONS ============
@dp.callback_query(F.data.startswith("act_"))
async def menu_act(call: CallbackQuery, state: FSMContext):
    action = call.data[4:]
    await state.clear()
    if action == "shop":
        cats = db("SELECT id,name,emoji FROM categories WHERE is_active=1 AND is_maintenance=0", all=True)
        if not cats: return await call.answer("No categories!", show_alert=True)
        rows = [[InlineKeyboardButton(text=f"{c[2]} {c[1]}", callback_data=f"cat_{c[0]}", style="primary")] for c in cats]
        rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")])
        await call.message.edit_text(gs("ui_category_msg"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    elif action == "profile":
        await show_profile(call)
    elif action == "addbalance":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="₹50", callback_data="amt_50", style="primary"),
             InlineKeyboardButton(text="₹100", callback_data="amt_100", style="primary")],
            [InlineKeyboardButton(text="₹200", callback_data="amt_200", style="primary"),
             InlineKeyboardButton(text="₹500", callback_data="amt_500", style="primary")],
            [InlineKeyboardButton(text="₹1000", callback_data="amt_1000", style="primary"),
             InlineKeyboardButton(text="✏️ Custom", callback_data="amt_custom", style="success")],
            [InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")]])
        mode = "Auto ✅" if gs("payment_mode") == "auto" else "Manual ⏳"
        await call.message.edit_text(f"💰 <b>ADD BALANCE</b>\nMode: {mode}\n\nSelect amount:", reply_markup=kb)
    elif action == "support":
        rows = []
        tg = gs("support_telegram"); wa = gs("support_whatsapp")
        if tg: rows.append([InlineKeyboardButton(text="✈️ Telegram", url=tg, style="primary")])
        if wa: rows.append([InlineKeyboardButton(text="📱 WhatsApp", url=wa, style="primary")])
        rows.append([InlineKeyboardButton(text="🎫 New Ticket", callback_data="new_ticket", style="success")])
        rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")])
        await call.message.edit_text("🎧 <b>SUPPORT</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    elif action == "daily_gift":
        gift = sfloat(gs("daily_gift_price"))
        if gift <= 0: return await call.answer("Gift disabled!", show_alert=True)
        today = datetime.now().strftime("%Y-%m-%d")
        u = db("SELECT last_gift FROM users WHERE user_id=?", (call.from_user.id,), one=True)
        if u and u[0] == today: return await call.answer("🎁 Already claimed!", show_alert=True)
        db("UPDATE users SET balance=balance+?,last_gift=? WHERE user_id=?", (gift, today, call.from_user.id))
        await call.answer(f"🎁 +{fmt(gift)}!", show_alert=True)
    elif action == "redeem_coupon":
        await state.set_state(U.coupon)
        await call.message.edit_text("🎟️ Send coupon code:", reply_markup=bk("back_main"))
    elif action == "reseller":
        u = db("SELECT is_reseller,balance FROM users WHERE user_id=?", (call.from_user.id,), one=True)
        if u[0]: return await call.message.edit_text("👑 You are a Reseller!", reply_markup=bk("back_main"))
        fee = sfloat(gs("reseller_setup_fee", "500"))
        if gs("reseller_system_status") == "OFF":
            return await call.message.edit_text("⚠️ Reseller closed.", reply_markup=bk("back_main"))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Become {fmt(fee)}", callback_data="buy_reseller", style="success")],
            [InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")]])
        await call.message.edit_text(f"👑 <b>RESELLER</b>\nFee: {fmt(fee)}\nBalance: {fmt(u[1])}", reply_markup=kb)
    elif action == "vip":
        u = db("SELECT balance,is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)
        if u[1]: return await call.message.edit_text("🌟 Already VIP!", reply_markup=bk("back_main"))
        if u[0] < VIP_PRICE: return await call.message.edit_text(f"❌ Need {fmt(VIP_PRICE)}", reply_markup=bk("back_main"))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Buy VIP {fmt(VIP_PRICE)}", callback_data="buy_vip", style="success")],
            [InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")]])
        await call.message.edit_text(f"🌟 <b>VIP</b>\n{fmt(VIP_PRICE)}\n{VIP_DISCOUNT}% off", reply_markup=kb)
    else: await call.answer(f"'{action}' soon!", show_alert=True)

@dp.callback_query(F.data == "buy_vip")
async def buy_vip(call: CallbackQuery):
    u = db("SELECT balance FROM users WHERE user_id=?", (call.from_user.id,), one=True)
    if u[0] < VIP_PRICE: return await call.answer("❌ Not enough!", show_alert=True)
    db("UPDATE users SET balance=balance-?,is_vip=1 WHERE user_id=?", (VIP_PRICE, call.from_user.id))
    await call.answer("🎉 VIP activated!", show_alert=True)

@dp.callback_query(F.data == "buy_reseller")
async def buy_reseller(call: CallbackQuery):
    fee = sfloat(gs("reseller_setup_fee", "500"))
    u = db("SELECT balance,is_reseller FROM users WHERE user_id=?", (call.from_user.id,), one=True)
    if u[1]: return await call.answer("Already reseller!", show_alert=True)
    if u[0] < fee: return await call.answer(f"❌ Need {fmt(fee)}", show_alert=True)
    db("UPDATE users SET balance=balance-?,is_reseller=1 WHERE user_id=?", (fee, call.from_user.id))
    await call.answer("👑 Reseller activated!", show_alert=True)

# ============ PROFILE ============
async def show_profile(call: CallbackQuery):
    uid = call.from_user.id
    u = db("SELECT first_name,balance,is_reseller,is_vip,joined_date FROM users WHERE user_id=?", (uid,), one=True)
    if not u: return await call.answer("User not found!", show_alert=True)
    oc = db("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,), one=True)[0]
    sp = db("SELECT COALESCE(SUM(price_paid),0) FROM orders WHERE user_id=?", (uid,), one=True)[0]
    fields = db("SELECT field_key,label FROM profile_fields WHERE is_visible=1", all=True)
    text = "👤 <b>MY PROFILE</b>\n━━━━━━━━━━━━━━━━━━\n"
    for f in fields or []:
        k = f[0]
        if k == "user_id": text += f"🆔 ID: <code>{uid}</code>\n"
        elif k == "name": text += f"📛 Name: {u[0]}\n"
        elif k == "balance": text += f"💰 Balance: <b>{fmt(u[1])}</b>\n"
        elif k == "account_type":
            t = []
            if u[2]: t.append("👑 Reseller")
            if u[3]: t.append("🌟 VIP")
            text += f"🔰 Type: {' | '.join(t) if t else 'Regular'}\n"
        elif k == "joined_date": text += f"📅 Joined: {u[4]}\n"
        elif k == "total_spent": text += f"💸 Spent: {fmt(sp)}\n"
        elif k == "total_orders": text += f"📦 Orders: {oc}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")]])
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):
    o = db("SELECT product_name,price_paid,delivered_key,purchase_date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,), all=True)
    if not o: return await call.message.edit_text("📭 No orders.", reply_markup=bk("back_main"))
    text = "🧾 <b>MY ORDERS</b>\n"
    for r in o: text += f"\n📦 {r[0]} - {fmt(r[1])}\n🔑 <code>{r[2]}</code>\n📅 {r[3]}"
    await call.message.edit_text(text, reply_markup=bk("back_main"))

# ============ BALANCE ============
@dp.callback_query(F.data.startswith("amt_"))
async def amt_pick(call: CallbackQuery, state: FSMContext):
    v = call.data[4:]
    if v == "custom":
        await state.set_state(U.custom_amt)
        await call.message.edit_text("Enter amount (₹):", reply_markup=bk("back_main"))
        return
    await make_payment(call.from_user.id, float(v), call)

@dp.message(U.custom_amt)
async def cust_amt(m: Message, state: FSMContext):
    try:
        a = float(m.text.strip())
        if a < 10: return await m.answer("❌ Min ₹10")
        if a > 100000: return await m.answer("❌ Max ₹1,00,000")
    except: return await m.answer("❌ Invalid")
    await state.clear()
    await make_payment(m.from_user.id, a, m)

async def make_payment(uid, amount, target):
    oid = f"PAY{uid}{int(time.time())}"
    upi = gs("upi_id")
    if not upi:
        msg = "⚠️ Admin ne UPI set nahi ki."
        if isinstance(target, CallbackQuery): await target.message.edit_text(msg, reply_markup=bk("back_main"))
        else: await target.answer(msg, reply_markup=bk("back_main"))
        return
    payee = gs("payee_name", BRAND_NAME)
    link = upi_link(upi, payee, amount, f"Pay {oid}")
    expires = int(time.time()) + 300
    db("INSERT OR REPLACE INTO transactions (order_id,user_id,amount,status,created_at,expires_at,qr_data) VALUES (?,?,?,'pending',?,?,?)",
       (oid, uid, amount, int(time.time()), expires, link))
    qr = make_qr(link)
    text = (f"🧾 <b>PAYMENT QR</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"💵 Amount: <b>{fmt(amount)}</b>\n"
            f"🆔 Order: <code>{oid}</code>\n"
            f"🏦 UPI: <code>{upi}</code>\n"
            f"⏳ Valid 5 mins\n\n"
            f"📱 Scan with any UPI app\n"
            f"✅ Then tap 'I Have Paid'")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I Have Paid", callback_data=f"paid_{oid}", style="success")],
        [InlineKeyboardButton(text=fancy("Cancel"), callback_data="back_main", style="danger")]])
    if isinstance(target, CallbackQuery):
        try: await target.message.delete()
        except: pass
        if qr: await bot.send_photo(uid, qr, caption=text, reply_markup=kb)
        else: await bot.send_message(uid, text, reply_markup=kb)
    else:
        if qr: await target.answer_photo(qr, caption=text, reply_markup=kb)
        else: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("paid_"))
async def paid(call: CallbackQuery, state: FSMContext):
    oid = call.data[5:]
    t = db("SELECT amount,status FROM transactions WHERE order_id=?", (oid,), one=True)
    if not t: return await call.answer("❌ Not found!", show_alert=True)
    if t[1] == "paid": return await call.answer("✅ Already credited!", show_alert=True)
    await state.update_data(po=oid, pa=t[0])
    await state.set_state(U.proof)
    await call.message.edit_text(f"📸 Send Screenshot or UTR\n\nAmount: {fmt(t[0])}", reply_markup=bk("back_main"))

@dp.message(U.proof, F.photo)
async def proof_photo(m: Message, state: FSMContext):
    d = await state.get_data()
    oid, amt = d.get("po"), d.get("pa", 0)
    db("INSERT INTO balance_requests (user_id,username,amount,method,proof_file_id,reference,status,created_at) VALUES (?,?,?,'manual',?,?,'pending',?)",
       (m.from_user.id, m.from_user.username or "", amt, m.photo[-1].file_id, oid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await state.clear()
    await m.answer("✅ Proof sent! Admin will verify.", reply_markup=main_menu_kb(m.from_user.id))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Credit", callback_data=f"credit_{oid}", style="success"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{oid}", style="danger")]])
    try:
        await bot.send_photo(ADMIN_ID, m.photo[-1].file_id,
            caption=f"💰 <b>Proof</b>\nUser: <code>{m.from_user.id}</code>\nAmount: {fmt(amt)}\nOrder: {oid}",
            reply_markup=kb)
    except: pass

@dp.message(U.proof)
async def proof_text(m: Message, state: FSMContext):
    d = await state.get_data()
    oid, amt = d.get("po"), d.get("pa", 0)
    db("INSERT INTO balance_requests (user_id,username,amount,method,reference,status,created_at) VALUES (?,?,?,'manual',?,'pending',?)",
       (m.from_user.id, m.from_user.username or "", amt, f"{oid} UTR:{m.text[:50]}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await state.clear()
    await m.answer("✅ UTR sent! Admin will verify.", reply_markup=main_menu_kb(m.from_user.id))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Credit", callback_data=f"credit_{oid}", style="success"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{oid}", style="danger")]])
    try:
        await bot.send_message(ADMIN_ID,
            f"💰 <b>UTR Received</b>\nUser: <code>{m.from_user.id}</code>\nAmount: {fmt(amt)}\nOrder: {oid}\nUTR: {m.text[:200]}",
            reply_markup=kb)
    except: pass

@dp.callback_query(F.data.startswith("credit_"))
async def admin_credit(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    oid = call.data[7:]
    t = db("SELECT user_id,amount,status FROM transactions WHERE order_id=?", (oid,), one=True)
    if not t: return await call.answer("Not found!", show_alert=True)
    if t[2] == "paid": return await call.answer("Already credited!", show_alert=True)
    db("UPDATE transactions SET status='paid' WHERE order_id=?", (oid,))
    db("UPDATE users SET balance=balance+? WHERE user_id=?", (t[1], t[0]))
    db("UPDATE balance_requests SET status='approved' WHERE reference=?", (oid,))
    await call.answer("✅ Credited!", show_alert=True)
    try: await bot.send_message(t[0], f"✅ <b>Payment Verified!</b>\n+{fmt(t[1])}")
    except: pass
    try: await call.message.edit_reply_markup(reply_markup=None)
    except: pass

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    oid = call.data[7:]
    t = db("SELECT user_id FROM transactions WHERE order_id=?", (oid,), one=True)
    if not t: return
    db("UPDATE transactions SET status='rejected' WHERE order_id=?", (oid,))
    db("UPDATE balance_requests SET status='rejected' WHERE reference=?", (oid,))
    await call.answer("❌ Rejected!", show_alert=True)
    try: await bot.send_message(t[0], "❌ Payment rejected.")
    except: pass
    try: await call.message.edit_reply_markup(reply_markup=None)
    except: pass

# ============ SHOP: Category -> Product -> BUY ============
@dp.callback_query(F.data.startswith("cat_"))
async def show_products(call: CallbackQuery):
    cid = int(call.data[4:])
    prods = db("SELECT id,name,price,stock FROM products WHERE category_id=? AND is_active=1 AND is_maintenance=0", (cid,), all=True)
    if not prods: return await call.answer("No products!", show_alert=True)
    rows = []
    for p in prods:
        st = "🟢" if p[3] > 0 else "🔴"
        rows.append([InlineKeyboardButton(text=f"{p[1]} - {fmt(p[2])} {st}", callback_data=f"vp_{p[0]}", style="primary")])
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="act_shop", style="danger")])
    await call.message.edit_text(gs("ui_product_msg"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("vp_"))
async def view_product(call: CallbackQuery):
    pid = int(call.data[3:])
    p = db("SELECT name,price,reseller_price,stock,validity,device_limit FROM products WHERE id=?", (pid,), one=True)
    if not p: return await call.answer("❌ Not found!", show_alert=True)
    u = db("SELECT is_reseller,is_vip,balance FROM users WHERE user_id=?", (call.from_user.id,), one=True)
    base = p[2] if (u and u[0] and p[2] > 0) else p[1]
    final = base - (base * VIP_DISCOUNT / 100) if (u and u[1]) else base
    text = (f"📦 <b>{p[0]}</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: <b>{fmt(final)}</b>\n"
            f"⏱ Validity: {p[4] or 'N/A'}\n"
            f"📱 Device: {p[5] or 'N/A'}\n"
            f"🔑 Stock: {'🟢 '+str(p[3]) if p[3] > 0 else '🔴 Out'}\n"
            f"💰 Your Balance: {fmt(u[2] if u else 0)}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Buy Now", callback_data=f"buy_{pid}", style="success")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="act_shop", style="danger")]])
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_"))
async def buy_product(call: CallbackQuery):
    pid = int(call.data[4:])
    p = db("SELECT name,price,reseller_price,stock FROM products WHERE id=?", (pid,), one=True)
    if not p or p[3] <= 0: return await call.answer("❌ Out of stock!", show_alert=True)
    u = db("SELECT balance,is_reseller,is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)
    base = p[2] if (u[1] and p[2] > 0) else p[1]
    final = base - (base * VIP_DISCOUNT / 100) if u[2] else base
    if u[0] < final:
        return await call.answer(f"❌ Insufficient! Need {fmt(final)}. Add balance first.", show_alert=True)
    k = db("SELECT id,key_text FROM product_keys WHERE product_id=? AND is_used=0 LIMIT 1", (pid,), one=True)
    if not k: return await call.answer("❌ No keys in stock!", show_alert=True)
    db("UPDATE users SET balance=balance-? WHERE user_id=?", (final, call.from_user.id))
    db("UPDATE product_keys SET is_used=1 WHERE id=?", (k[0],))
    db("UPDATE products SET stock=stock-1 WHERE id=?", (pid,))
    db("INSERT INTO orders (user_id,product_name,price_paid,delivered_key,purchase_date) VALUES (?,?,?,?,?)",
       (call.from_user.id, p[0], final, k[1], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await call.message.edit_text(
        f"🎉 <b>PURCHASE SUCCESSFUL!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 {p[0]}\n"
        f"💰 Paid: {fmt(final)}\n"
        f"🔑 <code>{k[1]}</code>\n\n"
        f"{gs('ui_key_msg')}",
        reply_markup=main_menu_kb(call.from_user.id))

# ============ SUPPORT / COUPON ============
@dp.callback_query(F.data == "new_ticket")
async def new_ticket(call: CallbackQuery, state: FSMContext):
    await state.set_state(U.ticket)
    await call.message.edit_text("📝 Describe issue:", reply_markup=bk("back_main"))

@dp.message(U.ticket)
async def ticket_save(m: Message, state: FSMContext):
    db("INSERT INTO tickets (user_id,message,created_at) VALUES (?,?,?)",
       (m.from_user.id, m.text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await state.clear()
    await m.answer("✅ Ticket submitted!", reply_markup=main_menu_kb(m.from_user.id))
    try: await bot.send_message(ADMIN_ID, f"🚨 <b>Ticket</b>\nFrom: <code>{m.from_user.id}</code>\n\n{m.text}")
    except: pass

@dp.message(U.coupon)
async def coupon_save(m: Message, state: FSMContext):
    code = m.text.strip().upper()
    c = db("SELECT discount,max_uses,used FROM coupons WHERE code=?", (code,), one=True)
    if not c: await m.answer("❌ Invalid!", reply_markup=main_menu_kb(m.from_user.id))
    elif c[2] >= c[1]: await m.answer("❌ Expired!", reply_markup=main_menu_kb(m.from_user.id))
    else:
        db("UPDATE users SET balance=balance+? WHERE user_id=?", (c[0], m.from_user.id))
        db("UPDATE coupons SET used=used+1 WHERE code=?", (code,))
        await m.answer(f"✅ +{fmt(c[0])} added!", reply_markup=main_menu_kb(m.from_user.id))
    await state.clear()

# ============ ADMIN PANEL ============
@dp.message(Command("admin"))
async def admin_cmd(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    await state.clear()
    await m.answer("⚙️ <b>ADMIN PANEL</b>", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_back")
async def adm_back(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.clear()
    await call.message.edit_text("⚙️ <b>ADMIN PANEL</b>", reply_markup=admin_kb())

# ---- STORE MANAGER ----
@dp.callback_query(F.data == "adm_store")
async def adm_store(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Categories", callback_data="adm_cats", style="success"),
         InlineKeyboardButton(text="📦 Products", callback_data="adm_prods", style="success")],
        [InlineKeyboardButton(text="🔑 Key Manager", callback_data="adm_keys", style="primary")],
        [InlineKeyboardButton(text="🛠️ Maintenance", callback_data="adm_maint", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("🛍️ <b>STORE MANAGER</b>", reply_markup=kb)

# ---- CATEGORY ----
@dp.callback_query(F.data == "adm_cats")
async def adm_cats(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add", callback_data="adm_cat_add", style="success"),
         InlineKeyboardButton(text="📋 List", callback_data="adm_cat_list", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]])
    await call.message.edit_text("📂 <b>CATEGORIES</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_cat_add")
async def cat_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.cat_name)
    await call.message.edit_text("Enter Category Name:", reply_markup=bk("adm_cats"))

@dp.message(A.cat_name)
async def cat_name_save(m: Message, state: FSMContext):
    await state.update_data(cn=m.text)
    await state.set_state(A.cat_emoji)
    await m.answer("Enter Emoji (📱):")

@dp.message(A.cat_emoji)
async def cat_emoji_save(m: Message, state: FSMContext):
    d = await state.get_data()
    db("INSERT INTO categories (name,emoji) VALUES (?,?)", (d['cn'], m.text))
    await state.clear()
    await m.answer("✅ Category added!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_cat_list")
async def cat_list(call: CallbackQuery):
    cats = db("SELECT id,name,emoji FROM categories", all=True)
    rows = []
    for c in cats or []:
        rows.append([InlineKeyboardButton(text=f"{c[2]} {c[1]}", callback_data=f"cv_{c[0]}", style="primary")])
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_cats", style="danger")])
    await call.message.edit_text("Select Category:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("cv_"))
async def cat_view(call: CallbackQuery):
    cid = int(call.data[3:])
    c = db("SELECT name,emoji FROM categories WHERE id=?", (cid,), one=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Name", callback_data=f"ce_{cid}_name", style="primary"),
         InlineKeyboardButton(text="😀 Emoji", callback_data=f"ce_{cid}_emoji", style="primary")],
        [InlineKeyboardButton(text="🗑️ Delete", callback_data=f"cd_{cid}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_cat_list", style="danger")]])
    await call.message.edit_text(f"{c[1]} <b>{c[0]}</b>", reply_markup=kb)

@dp.callback_query(F.data.startswith("ce_"))
async def cat_edit(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    cid, field = int(parts[1]), parts[2]
    await state.update_data(ce_id=cid, ce_field=field)
    await state.set_state(A.cat_edit)
    await call.message.edit_text(f"New {field}:", reply_markup=bk("adm_cat_list"))

@dp.message(A.cat_edit)
async def cat_edit_save(m: Message, state: FSMContext):
    d = await state.get_data()
    col = "name" if d['ce_field'] == 'name' else "emoji"
    db(f"UPDATE categories SET {col}=? WHERE id=?", (m.text, d['ce_id']))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("cd_"))
async def cat_del(call: CallbackQuery):
    cid = int(call.data[3:])
    db("DELETE FROM categories WHERE id=?", (cid,))
    await call.answer("Deleted!", show_alert=True)
    await cat_list(call)

# ---- PRODUCTS ----
@dp.callback_query(F.data == "adm_prods")
async def adm_prods(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add", callback_data="adm_prod_add", style="success"),
         InlineKeyboardButton(text="📋 List", callback_data="adm_prod_list", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]])
    await call.message.edit_text("📦 <b>PRODUCTS</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_prod_add")
async def prod_add(call: CallbackQuery):
    cats = db("SELECT id,name FROM categories", all=True)
    if not cats: return await call.answer("Add category first!", show_alert=True)
    rows = [[InlineKeyboardButton(text=c[1], callback_data=f"pa_{c[0]}", style="primary")] for c in cats]
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_prods", style="danger")])
    await call.message.edit_text("Select Category:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("pa_"))
async def prod_cat(call: CallbackQuery, state: FSMContext):
    cid = int(call.data[3:])
    await state.update_data(pc=cid)
    await state.set_state(A.prod_name)
    await call.message.edit_text("Product Name:", reply_markup=bk("adm_prods"))

@dp.message(A.prod_name)
async def prod_name_save(m: Message, state: FSMContext):
    await state.update_data(pn=m.text)
    await state.set_state(A.prod_price)
    await m.answer("Price (₹):")

@dp.message(A.prod_price)
async def prod_price_save(m: Message, state: FSMContext):
    try: p = float(m.text)
    except: return await m.answer("❌ Number!")
    await state.update_data(pp=p)
    await state.set_state(A.prod_rprice)
    await m.answer("Reseller Price (₹):")

@dp.message(A.prod_rprice)
async def prod_rprice_save(m: Message, state: FSMContext):
    try: p = float(m.text)
    except: return await m.answer("❌ Number!")
    await state.update_data(prp=p)
    await state.set_state(A.prod_validity)
    await m.answer("Validity (e.g., 30 Days):")

@dp.message(A.prod_validity)
async def prod_validity_save(m: Message, state: FSMContext):
    await state.update_data(pv=m.text)
    await state.set_state(A.prod_device)
    await m.answer("Device Limit:")

@dp.message(A.prod_device)
async def prod_device_save(m: Message, state: FSMContext):
    await state.update_data(pd=m.text)
    await state.set_state(A.prod_apk)
    await m.answer("APK Link (or 'none'):")

@dp.message(A.prod_apk)
async def prod_apk_save(m: Message, state: FSMContext):
    await state.update_data(pap=m.text if m.text.lower() != 'none' else "")
    await state.set_state(A.prod_keys)
    await m.answer("Paste Keys (1 per line):")

@dp.message(A.prod_keys)
async def prod_keys_save(m: Message, state: FSMContext):
    d = await state.get_data()
    keys = [k.strip() for k in m.text.split('\n') if k.strip()]
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO products (category_id,name,price,reseller_price,validity,device_limit,apk_link,stock) VALUES (?,?,?,?,?,?,?,?)",
              (d['pc'], d['pn'], d['pp'], d['prp'], d['pv'], d['pd'], d['pap'], len(keys)))
    pid = c.lastrowid
    for k in keys: c.execute("INSERT INTO product_keys (product_id,key_text) VALUES (?,?)", (pid, k))
    conn.commit(); conn.close()
    await state.clear()
    await m.answer(f"✅ Product added with {len(keys)} keys!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_prod_list")
async def prod_list(call: CallbackQuery):
    prods = db("SELECT id,name,price FROM products", all=True)
    rows = []
    for p in prods or []:
        rows.append([InlineKeyboardButton(text=f"{p[1]} - {fmt(p[2])}", callback_data=f"pv_{p[0]}", style="primary")])
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_prods", style="danger")])
    await call.message.edit_text("Select Product:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("pv_"))
async def prod_view(call: CallbackQuery):
    pid = int(call.data[3:])
    p = db("SELECT name,price,reseller_price,stock FROM products WHERE id=?", (pid,), one=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Name", callback_data=f"pe_{pid}_name", style="primary"),
         InlineKeyboardButton(text="💰 Price", callback_data=f"pe_{pid}_price", style="primary")],
        [InlineKeyboardButton(text="👑 R-Price", callback_data=f"pe_{pid}_reseller_price", style="primary"),
         InlineKeyboardButton(text="⏱ Validity", callback_data=f"pe_{pid}_validity", style="primary")],
        [InlineKeyboardButton(text="📱 Device", callback_data=f"pe_{pid}_device_limit", style="primary"),
         InlineKeyboardButton(text="🔗 APK", callback_data=f"pe_{pid}_apk_link", style="primary")],
        [InlineKeyboardButton(text="➕ Add Keys", callback_data=f"pk_{pid}", style="success"),
         InlineKeyboardButton(text="🗑️ Delete", callback_data=f"pdl_{pid}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_prod_list", style="danger")]])
    await call.message.edit_text(f"📦 <b>{p[0]}</b>\n💰 {fmt(p[1])} | 👑 {fmt(p[2])} | 🔑 {p[3]}", reply_markup=kb)

@dp.callback_query(F.data.startswith("pe_"))
async def prod_edit(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_", 2)
    pid, field = int(parts[1]), parts[2]
    await state.update_data(pe_id=pid, pe_field=field)
    await state.set_state(A.prod_edit)
    await call.message.edit_text(f"New {field}:", reply_markup=bk("adm_prod_list"))

@dp.message(A.prod_edit)
async def prod_edit_save(m: Message, state: FSMContext):
    d = await state.get_data()
    field = d['pe_field']
    val = m.text
    if field in ('price', 'reseller_price'):
        try: val = float(val)
        except: return await m.answer("❌ Number!")
    if field == 'apk_link' and val.lower() == 'none': val = ""
    db(f"UPDATE products SET {field}=? WHERE id=?", (val, d['pe_id']))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("pk_"))
async def prod_addkeys(call: CallbackQuery, state: FSMContext):
    pid = int(call.data[3:])
    await state.update_data(pk_id=pid)
    await state.set_state(A.prod_addkeys)
    await call.message.edit_text("Paste Keys (1 per line):", reply_markup=bk("adm_prod_list"))

@dp.message(A.prod_addkeys)
async def prod_addkeys_save(m: Message, state: FSMContext):
    d = await state.get_data()
    pid = d['pk_id']
    keys = [k.strip() for k in m.text.split('\n') if k.strip()]
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    for k in keys: c.execute("INSERT INTO product_keys (product_id,key_text) VALUES (?,?)", (pid, k))
    c.execute("UPDATE products SET stock=stock+? WHERE id=?", (len(keys), pid))
    conn.commit(); conn.close()
    await state.clear()
    await m.answer(f"✅ {len(keys)} keys added!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("pdl_"))
async def prod_del(call: CallbackQuery):
    pid = int(call.data[4:])
    db("DELETE FROM products WHERE id=?", (pid,))
    db("DELETE FROM product_keys WHERE product_id=?", (pid,))
    await call.answer("Deleted!", show_alert=True)
    await prod_list(call)

# ---- KEY MANAGER ----
@dp.callback_query(F.data == "adm_keys")
async def adm_keys(call: CallbackQuery):
    prods = db("SELECT id,name FROM products", all=True)
    text = "🔑 <b>KEY STOCK</b>\n━━━━━━━━━━━━━━━━━━\n"
    for p in prods or []:
        av = db("SELECT COUNT(*) FROM product_keys WHERE product_id=? AND is_used=0", (p[0],), one=True)[0]
        text += f"\n📦 {p[1]}: 🟢 {av} keys"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Clear Unused", callback_data="adm_key_clear", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]])
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "adm_key_clear")
async def key_clear(call: CallbackQuery):
    db("DELETE FROM product_keys WHERE is_used=0")
    await call.answer("🧹 Cleared!", show_alert=True)

# ---- MAINTENANCE ----
@dp.callback_query(F.data == "adm_maint")
async def adm_maint(call: CallbackQuery):
    st = "🔴 ON" if gs("global_maintenance") == "1" else "🟢 OFF"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Global: {st}", callback_data="adm_mt_tog", style="danger" if st == "🔴 ON" else "success")],
        [InlineKeyboardButton(text="✏️ Edit Msg", callback_data="adm_mt_edit", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]])
    await call.message.edit_text("🛠️ <b>MAINTENANCE</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_mt_tog")
async def mt_tog(call: CallbackQuery):
    cur = gs("global_maintenance")
    ss("global_maintenance", "0" if cur == "1" else "1")
    await adm_maint(call)

@dp.callback_query(F.data == "adm_mt_edit")
async def mt_edit(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_maint)
    await call.message.edit_text("New Message:", reply_markup=bk("adm_maint"))

@dp.message(A.set_maint)
async def mt_edit_save(m: Message, state: FSMContext):
    ss("maintenance_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

# ---- USER MANAGER ----
@dp.callback_query(F.data == "adm_users")
async def adm_users(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Search User", callback_data="adm_u_search", style="primary")],
        [InlineKeyboardButton(text="📋 All Users", callback_data="adm_u_all", style="primary")],
        [InlineKeyboardButton(text="💰 Balance Requests", callback_data="adm_u_balreq", style="success")],
        [InlineKeyboardButton(text="🧾 Orders", callback_data="adm_u_orders", style="primary")],
        [InlineKeyboardButton(text="🎫 Tickets", callback_data="adm_u_tickets", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("👥 <b>USER MANAGER</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_u_search")
async def u_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.user_search)
    await call.message.edit_text("Send User ID or @username:", reply_markup=bk("adm_users"))

@dp.message(A.user_search)
async def u_search_save(m: Message, state: FSMContext):
    t = m.text.strip().lstrip('@')
    u = db("SELECT user_id,first_name,balance,is_banned,is_vip,is_reseller FROM users WHERE user_id=? OR username=?", (t, t), one=True)
    if not u: return await m.answer("❌ Not found!", reply_markup=bk("adm_users"))
    st = "🔴 Banned" if u[3] else "🟢 Active"
    tags = []
    if u[5]: tags.append("👑 Reseller")
    if u[4]: tags.append("🌟 VIP")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Ban/Unban", callback_data=f"ub_{u[0]}", style="danger"),
         InlineKeyboardButton(text="🌟 VIP", callback_data=f"uv_{u[0]}", style="success")],
        [InlineKeyboardButton(text="👑 Reseller", callback_data=f"ures_{u[0]}", style="primary")],
        [InlineKeyboardButton(text="➕ Add ₹", callback_data=f"ua_{u[0]}", style="success"),
         InlineKeyboardButton(text="➖ Remove ₹", callback_data=f"ur_{u[0]}", style="danger")],
        [InlineKeyboardButton(text="🗑️ DELETE USER", callback_data=f"udel_{u[0]}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_users", style="danger")]])
    await m.answer(f"👤 <b>USER</b>\n🆔 <code>{u[0]}</code>\n📛 {u[1]}\n💰 {fmt(u[2])}\n📊 {st}\n🏷 {' | '.join(tags) if tags else 'Regular'}",
                   reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data == "adm_u_all")
async def u_all(call: CallbackQuery):
    users = db("SELECT user_id,first_name,balance FROM users ORDER BY user_id DESC LIMIT 30", all=True)
    text = "👥 <b>USERS (Latest 30)</b>\n"
    for u in users or []: text += f"\n<code>{u[0]}</code> | {u[1] or 'N/A'} | {fmt(u[2])}"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))

@dp.callback_query(F.data.startswith("udel_"))
async def u_del(call: CallbackQuery):
    uid = int(call.data[5:])
    db("DELETE FROM users WHERE user_id=?", (uid,))
    db("DELETE FROM orders WHERE user_id=?", (uid,))
    db("DELETE FROM balance_requests WHERE user_id=?", (uid,))
    await call.answer("🗑️ Deleted!", show_alert=True)

@dp.callback_query(F.data.startswith("ub_"))
async def u_ban(call: CallbackQuery):
    uid = int(call.data[3:])
    c = db("SELECT is_banned FROM users WHERE user_id=?", (uid,), one=True)[0]
    db("UPDATE users SET is_banned=? WHERE user_id=?", (0 if c else 1, uid))
    await call.answer("✅ Toggled!", show_alert=True)

@dp.callback_query(F.data.startswith("uv_"))
async def u_vip(call: CallbackQuery):
    uid = int(call.data[3:])
    c = db("SELECT is_vip FROM users WHERE user_id=?", (uid,), one=True)[0]
    db("UPDATE users SET is_vip=? WHERE user_id=?", (0 if c else 1, uid))
    await call.answer("✅ Toggled!", show_alert=True)

@dp.callback_query(F.data.startswith("ures_"))
async def u_res(call: CallbackQuery):
    uid = int(call.data[5:])
    c = db("SELECT is_reseller FROM users WHERE user_id=?", (uid,), one=True)[0]
    db("UPDATE users SET is_reseller=? WHERE user_id=?", (0 if c else 1, uid))
    await call.answer("✅ Toggled!", show_alert=True)

@dp.callback_query(F.data.startswith("ua_"))
async def u_addbal(call: CallbackQuery, state: FSMContext):
    uid = int(call.data[3:])
    await state.update_data(ub=uid)
    await state.set_state(A.user_addbal)
    await call.message.edit_text("Amount to Add:", reply_markup=bk("adm_users"))

@dp.message(A.user_addbal)
async def u_addbal_save(m: Message, state: FSMContext):
    try: a = float(m.text)
    except: return await m.answer("❌ Number!")
    d = await state.get_data()
    db("UPDATE users SET balance=balance+? WHERE user_id=?", (a, d['ub']))
    await state.clear()
    await m.answer(f"✅ +{fmt(a)} added!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("ur_"))
async def u_rembal(call: CallbackQuery, state: FSMContext):
    uid = int(call.data[3:])
    await state.update_data(ub=uid)
    await state.set_state(A.user_rembal)
    await call.message.edit_text("Amount to Remove:", reply_markup=bk("adm_users"))

@dp.message(A.user_rembal)
async def u_rembal_save(m: Message, state: FSMContext):
    try: a = float(m.text)
    except: return await m.answer("❌ Number!")
    d = await state.get_data()
    db("UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=?", (a, d['ub']))
    await state.clear()
    await m.answer(f"✅ -{fmt(a)} removed!", reply_markup=admin_kb())

# ---- BALANCE REQUESTS / ORDERS / TICKETS (admin view) ----
@dp.callback_query(F.data == "adm_u_balreq")
async def u_balreq(call: CallbackQuery):
    reqs = db("SELECT id,user_id,amount,status,created_at FROM balance_requests ORDER BY id DESC LIMIT 15", all=True)
    if not reqs: return await call.message.edit_text("No requests.", reply_markup=bk("adm_users"))
    text = "💰 <b>BALANCE REQUESTS</b>\n"
    for r in reqs: text += f"\n#{r[0]} | <code>{r[1]}</code> | {fmt(r[2])} | {r[3]}"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))

@dp.callback_query(F.data == "adm_u_orders")
async def u_orders(call: CallbackQuery):
    o = db("SELECT id,user_id,product_name,price_paid,purchase_date FROM orders ORDER BY id DESC LIMIT 15", all=True)
    if not o: return await call.message.edit_text("No orders.", reply_markup=bk("adm_users"))
    text = "🧾 <b>ORDERS</b>\n"
    for r in o: text += f"\n#{r[0]} | <code>{r[1]}</code> | {r[2]} | {fmt(r[3])}"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))

@dp.callback_query(F.data == "adm_u_tickets")
async def u_tickets(call: CallbackQuery):
    t = db("SELECT id,user_id,message,status,created_at FROM tickets WHERE status='Open' ORDER BY id DESC LIMIT 10", all=True)
    if not t: return await call.message.edit_text("✅ No open tickets.", reply_markup=bk("adm_users"))
    text = "🎫 <b>OPEN TICKETS</b>\n"
    for r in t: text += f"\n#{r[0]} | <code>{r[1]}</code>\n{r[2][:100]}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))

# ---- MARKETING ----
@dp.callback_query(F.data == "adm_mkt")
async def adm_mkt(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ Coupons", callback_data="adm_cp", style="success"),
         InlineKeyboardButton(text="📢 Broadcast", callback_data="adm_bc", style="danger")],
        [InlineKeyboardButton(text="🎁 Gift", callback_data="adm_gift", style="success"),
         InlineKeyboardButton(text="🤝 Refer", callback_data="adm_ref", style="success")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("🎟️ <b>MARKETING</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_cp")
async def adm_cp(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create", callback_data="adm_cp_add", style="success"),
         InlineKeyboardButton(text="📋 View", callback_data="adm_cp_view", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_mkt", style="danger")]])
    await call.message.edit_text("🎟️ <b>COUPONS</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_cp_add")
async def cp_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.cp_code)
    await call.message.edit_text("Coupon Code:", reply_markup=bk("adm_cp"))

@dp.message(A.cp_code)
async def cp_code_save(m: Message, state: FSMContext):
    await state.update_data(cc=m.text.strip().upper())
    await state.set_state(A.cp_disc)
    await m.answer("Discount (₹):")

@dp.message(A.cp_disc)
async def cp_disc_save(m: Message, state: FSMContext):
    try: d = float(m.text)
    except: return await m.answer("❌ Number!")
    await state.update_data(cd=d)
    await state.set_state(A.cp_max)
    await m.answer("Max Uses:")

@dp.message(A.cp_max)
async def cp_max_save(m: Message, state: FSMContext):
    try: mx = int(m.text)
    except: return await m.answer("❌ Integer!")
    d = await state.get_data()
    db("INSERT OR REPLACE INTO coupons (code,discount,max_uses) VALUES (?,?,?)", (d['cc'], d['cd'], mx))
    await state.clear()
    await m.answer("✅ Coupon created!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_cp_view")
async def cp_view(call: CallbackQuery):
    cps = db("SELECT code,discount,max_uses,used FROM coupons", all=True)
    text = "🎟️ <b>COUPONS</b>\n"
    for c in cps or []: text += f"\n<code>{c[0]}</code> | {fmt(c[1])} | {c[3]}/{c[2]}"
    if not cps: text += "\nNo coupons."
    await call.message.edit_text(text, reply_markup=bk("adm_cp"))

@dp.callback_query(F.data == "adm_bc")
async def bc_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.bc_msg)
    await call.message.edit_text("Send broadcast message:", reply_markup=bk("adm_mkt"))

@dp.message(A.bc_msg)
async def bc_send(m: Message, state: FSMContext):
    users = db("SELECT user_id FROM users", all=True)
    sent, failed = 0, 0
    st = await m.answer("⏳ Broadcasting...")
    for u in users or []:
        try:
            await m.send_copy(chat_id=u[0]); sent += 1
        except: failed += 1
        await asyncio.sleep(0.05)
    await st.edit_text(f"✅ Sent: {sent}\n❌ Failed: {failed}", reply_markup=admin_kb())
    await state.clear()

@dp.callback_query(F.data == "adm_gift")
async def gift_set(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_gift)
    await call.message.edit_text("Daily Gift (₹):", reply_markup=bk("adm_mkt"))

@dp.message(A.set_gift)
async def gift_save(m: Message, state: FSMContext):
    ss("daily_gift_price", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_ref")
async def ref_set(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_refer)
    await call.message.edit_text("Refer Reward (₹):", reply_markup=bk("adm_mkt"))

@dp.message(A.set_refer)
async def ref_save(m: Message, state: FSMContext):
    ss("refer_earn_amount", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

# ---- MENU DESIGNER ----
@dp.callback_query(F.data == "adm_menu")
async def adm_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Manage Buttons", callback_data="adm_menu_list", style="primary")],
        [InlineKeyboardButton(text="➕ Add Button", callback_data="adm_menu_add", style="success")],
        [InlineKeyboardButton(text="👤 Profile Fields", callback_data="adm_pf", style="success")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("🎨 <b>MENU DESIGNER</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_menu_list")
async def menu_list(call: CallbackQuery):
    btns = db("SELECT id,label,emoji,action,is_active FROM menu_buttons ORDER BY position", all=True)
    rows = []
    for b in btns or []:
        st = "🟢" if b[4] else "🔴"
        rows.append([InlineKeyboardButton(text=f"{st} {b[2]} {b[1]}", callback_data=f"mb_{b[0]}", style="primary")])
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_menu", style="danger")])
    await call.message.edit_text("Select Button:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("mb_"))
async def menu_btn_view(call: CallbackQuery):
    bid = int(call.data[3:])
    b = db("SELECT label,emoji,action,is_active FROM menu_buttons WHERE id=?", (bid,), one=True)
    st = "🟢 Active" if b[3] else "🔴 Inactive"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Label", callback_data=f"mbe_{bid}_label", style="primary"),
         InlineKeyboardButton(text="😀 Emoji", callback_data=f"mbe_{bid}_emoji", style="primary")],
        [InlineKeyboardButton(text="⚙️ Action", callback_data=f"mbe_{bid}_action", style="primary")],
        [InlineKeyboardButton(text="👁️ Toggle", callback_data=f"mbt_{bid}", style="success")],
        [InlineKeyboardButton(text="🗑️ Delete", callback_data=f"mbd_{bid}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_menu_list", style="danger")]])
    await call.message.edit_text(f"Button: {b[2]} {b[1]}\nStatus: {st}", reply_markup=kb)

@dp.callback_query(F.data.startswith("mbe_"))
async def menu_btn_edit(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_", 2)
    bid, field = int(parts[1]), parts[2]
    await state.update_data(mbe_id=bid, mbe_field=field)
    await state.set_state(A.menu_edit)
    await call.message.edit_text(f"New {field}:", reply_markup=bk("adm_menu_list"))

@dp.message(A.menu_edit)
async def menu_btn_edit_save(m: Message, state: FSMContext):
    d = await state.get_data()
    db(f"UPDATE menu_buttons SET {d['mbe_field']}=? WHERE id=?", (m.text, d['mbe_id']))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("mbt_"))
async def menu_btn_toggle(call: CallbackQuery):
    bid = int(call.data[4:])
    c = db("SELECT is_active FROM menu_buttons WHERE id=?", (bid,), one=True)[0]
    db("UPDATE menu_buttons SET is_active=? WHERE id=?", (0 if c else 1, bid))
    await call.answer("✅ Toggled!", show_alert=True)
    await menu_list(call)

@dp.callback_query(F.data.startswith("mbd_"))
async def menu_btn_del(call: CallbackQuery):
    bid = int(call.data[4:])
    db("DELETE FROM menu_buttons WHERE id=?", (bid,))
    await call.answer("🗑️ Deleted!", show_alert=True)
    await menu_list(call)

@dp.callback_query(F.data == "adm_menu_add")
async def menu_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.menu_add_label)
    await call.message.edit_text("Button Label:", reply_markup=bk("adm_menu"))

@dp.message(A.menu_add_label)
async def menu_add_label(m: Message, state: FSMContext):
    await state.update_data(ml=m.text)
    await state.set_state(A.menu_add_emoji)
    await m.answer("Emoji (or 'none'):")

@dp.message(A.menu_add_emoji)
async def menu_add_emoji(m: Message, state: FSMContext):
    e = "" if m.text.lower() == 'none' else m.text
    await state.update_data(me=e)
    await state.set_state(A.menu_add_action)
    await m.answer("Action (shop/profile/addbalance/support/daily_gift/redeem_coupon/reseller/vip):")

@dp.message(A.menu_add_action)
async def menu_add_action(m: Message, state: FSMContext):
    d = await state.get_data()
    pos = db("SELECT MAX(position) FROM menu_buttons", one=True)[0] or 0
    db("INSERT INTO menu_buttons (label,emoji,action,position,is_active,row_group) VALUES (?,?,?,?,1,?)",
       (d['ml'], d['me'], m.text.lower(), pos + 1, pos // 2))
    await state.clear()
    await m.answer("✅ Button added!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_pf")
async def adm_pf(call: CallbackQuery):
    fields = db("SELECT field_key,label,is_visible FROM profile_fields", all=True)
    rows = []
    for f in fields or []:
        st = "🟢" if f[2] else "🔴"
        rows.append([InlineKeyboardButton(text=f"{st} {f[1]}", callback_data=f"pft_{f[0]}", style="primary")])
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_menu", style="danger")])
    await call.message.edit_text("👤 <b>PROFILE FIELDS</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("pft_"))
async def pf_toggle(call: CallbackQuery):
    key = call.data[4:]
    c = db("SELECT is_visible FROM profile_fields WHERE field_key=?", (key,), one=True)[0]
    db("UPDATE profile_fields SET is_visible=? WHERE field_key=?", (0 if c else 1, key))
    await call.answer("✅ Toggled!", show_alert=True)
    await adm_pf(call)

# ---- CO-ADMIN ----
@dp.callback_query(F.data == "adm_coadmin")
async def adm_coadmin(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add", callback_data="adm_ca_add", style="success"),
         InlineKeyboardButton(text="➖ Remove", callback_data="adm_ca_rem", style="danger")],
        [InlineKeyboardButton(text="📋 List", callback_data="adm_ca_list", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("🤝 <b>CO-ADMINS</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_ca_add")
async def ca_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.coadmin_add)
    await call.message.edit_text("User ID:", reply_markup=bk("adm_coadmin"))

@dp.message(A.coadmin_add)
async def ca_add_save(m: Message, state: FSMContext):
    try: uid = int(m.text.strip())
    except: return await m.answer("❌ Numeric ID!")
    u = db("SELECT first_name FROM users WHERE user_id=?", (uid,), one=True)
    name = u[0] if u else "Unknown"
    db("INSERT OR IGNORE INTO co_admins (user_id,name) VALUES (?,?)", (uid, name))
    await state.clear()
    await m.answer("✅ Co-admin added!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_ca_rem")
async def ca_rem(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.coadmin_remove)
    await call.message.edit_text("User ID to remove:", reply_markup=bk("adm_coadmin"))

@dp.message(A.coadmin_remove)
async def ca_rem_save(m: Message, state: FSMContext):
    try: uid = int(m.text.strip())
    except: return await m.answer("❌ Numeric!")
    db("DELETE FROM co_admins WHERE user_id=?", (uid,))
    await state.clear()
    await m.answer("✅ Removed!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_ca_list")
async def ca_list(call: CallbackQuery):
    cas = db("SELECT user_id,name FROM co_admins", all=True)
    text = "🤝 <b>CO-ADMINS</b>\n"
    for c in cas or []: text += f"\n<code>{c[0]}</code> | {c[1]}"
    if not cas: text += "\nNo co-admins."
    await call.message.edit_text(text, reply_markup=bk("adm_coadmin"))

# ---- SETTINGS ----
@dp.callback_query(F.data == "adm_settings")
async def adm_settings(call: CallbackQuery):
    mode = gs("payment_mode", "manual")
    m = "🤖 AUTO" if mode == "auto" else "✋ MANUAL"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼️ Set Logo", callback_data="adm_set_logo", style="success")],
        [InlineKeyboardButton(text="📝 Message Editor", callback_data="adm_msg", style="success")],
        [InlineKeyboardButton(text=f"💳 Payment: {m}", callback_data="adm_pay_mode", style="primary")],
        [InlineKeyboardButton(text="🏦 Set UPI ID", callback_data="adm_set_upi", style="primary")],
        [InlineKeyboardButton(text="🏷️ Set Payee", callback_data="adm_set_payee", style="primary")],
        [InlineKeyboardButton(text="📞 TG Support", callback_data="adm_set_tg", style="primary")],
        [InlineKeyboardButton(text="📱 WA Support", callback_data="adm_set_wa", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("⚙️ <b>SETTINGS</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_pay_mode")
async def pay_mode(call: CallbackQuery):
    cur = gs("payment_mode", "manual")
    new = "auto" if cur == "manual" else "manual"
    ss("payment_mode", new)
    await call.answer(f"✅ {new.upper()}", show_alert=True)
    await adm_settings(call)

@dp.callback_query(F.data == "adm_set_logo")
async def set_logo(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_logo)
    await call.message.edit_text("Send photo for Logo:", reply_markup=bk("adm_settings"))

@dp.message(A.set_logo, F.photo)
async def set_logo_save(m: Message, state: FSMContext):
    ss("admin_logo_file_id", m.photo[-1].file_id)
    await state.clear()
    await m.answer("✅ Logo saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_set_upi")
async def set_upi(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_upi)
    await call.message.edit_text("UPI ID (e.g., name@paytm):", reply_markup=bk("adm_settings"))

@dp.message(A.set_upi)
async def set_upi_save(m: Message, state: FSMContext):
    ss("upi_id", m.text.strip())
    await state.clear()
    await m.answer("✅ UPI saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_set_payee")
async def set_payee(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_payee)
    await call.message.edit_text("Payee Name:", reply_markup=bk("adm_settings"))

@dp.message(A.set_payee)
async def set_payee_save(m: Message, state: FSMContext):
    ss("payee_name", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_set_tg")
async def set_tg(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_tg)
    await call.message.edit_text("Telegram Support URL:", reply_markup=bk("adm_settings"))

@dp.message(A.set_tg)
async def set_tg_save(m: Message, state: FSMContext):
    ss("support_telegram", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_set_wa")
async def set_wa(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_wa)
    await call.message.edit_text("WhatsApp URL:", reply_markup=bk("adm_settings"))

@dp.message(A.set_wa)
async def set_wa_save(m: Message, state: FSMContext):
    ss("support_whatsapp", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

# ---- MESSAGE EDITOR ----
@dp.callback_query(F.data == "adm_msg")
async def adm_msg(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Welcome", callback_data="am_w", style="primary")],
        [InlineKeyboardButton(text="📂 Category Page", callback_data="am_c", style="primary")],
        [InlineKeyboardButton(text="📦 Product Page", callback_data="am_p", style="primary")],
        [InlineKeyboardButton(text="🔑 Key Delivery", callback_data="am_k", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_settings", style="danger")]])
    await call.message.edit_text("📝 <b>MESSAGE EDITOR</b>", reply_markup=kb)

@dp.callback_query(F.data == "am_w")
async def am_w(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.msg_welcome)
    await call.message.edit_text("New Welcome Message:", reply_markup=bk("adm_msg"))

@dp.message(A.msg_welcome)
async def am_w_save(m: Message, state: FSMContext):
    ss("welcome_text", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "am_c")
async def am_c(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.msg_cat)
    await call.message.edit_text("New Category Page Message:", reply_markup=bk("adm_msg"))

@dp.message(A.msg_cat)
async def am_c_save(m: Message, state: FSMContext):
    ss("ui_category_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "am_p")
async def am_p(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.msg_prod)
    await call.message.edit_text("New Product Page Message:", reply_markup=bk("adm_msg"))

@dp.message(A.msg_prod)
async def am_p_save(m: Message, state: FSMContext):
    ss("ui_product_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "am_k")
async def am_k(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.msg_key)
    await call.message.edit_text("New Key Delivery Message:", reply_markup=bk("adm_msg"))

@dp.message(A.msg_key)
async def am_k_save(m: Message, state: FSMContext):
    ss("ui_key_msg", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

# ============ RENDER WEB SERVER + MAIN ============
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server started on port {port}")

async def main():
    init_db()
    logger.info("DB initialized.")
    await start_web()
    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")