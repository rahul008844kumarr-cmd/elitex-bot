#!/usr/bin/env python3
"""ELITE X CONFIG — FINAL COMBINED BOT (aiogram)"""
import asyncio, sqlite3, logging, time, os, io, aiohttp
from aiohttp import web
from datetime import datetime
from urllib.parse import quote

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton,
                           CallbackQuery, Message, BufferedInputFile)

try:
    import qrcode
except ImportError:
    qrcode = None

# ============ CONFIG ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "8606369071:AAEqBcCFHPz8syTBP40cvnOHQHojn0R-WoI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8467166339"))
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
    sc = {"a":"ᴀ","b":"ʙ","c":"ᴄ","d":"ᴅ","e":"ᴇ","f":"ꜰ","g":"ɢ","h":"ʜ","i":"ɪ","j":"ᴊ",
          "k":"ᴋ","l":"ʟ","m":"ᴍ","n":"ɴ","o":"ᴏ","p":"ᴘ","q":"ǫ","r":"ʀ","s":"s","t":"ᴛ",
          "u":"ᴜ","v":"ᴠ","w":"ᴡ","x":"x","y":"ʏ","z":"ᴢ"}
    out, at = [], True
    for ch in str(text):
        if ch.isascii() and ch.isalpha():
            out.append(bc.get(ch.upper(), ch) if at else sc.get(ch.lower(), ch)); at = False
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
    return BufferedInputFile(buf.getvalue(), filename="qr.png")

# ============ DB ============
def db(q, p=(), one=False, all=False, commit=True):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    try:
        c.execute(q, p)
        r = c.fetchone() if one else (c.fetchall() if all else None)
        if commit: conn.commit()
        return r
    except Exception as e:
        logger.error(f"DB error: {e} | {q}")
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
        category_id INTEGER, name TEXT, description TEXT DEFAULT '', emoji TEXT DEFAULT '📦',
        is_active INTEGER DEFAULT 1, is_maintenance INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS plans (id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER, name TEXT, price REAL DEFAULT 0, reseller_price REAL DEFAULT 0,
        is_active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS product_keys (id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER, key_text TEXT, is_used INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, plan_id INTEGER, plan_name TEXT, product_name TEXT, price_paid REAL,
        delivered_key TEXT, purchase_date TEXT, status TEXT DEFAULT 'delivered')""")
    c.execute("""CREATE TABLE IF NOT EXISTS balance_requests (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, username TEXT, amount REAL, method TEXT, proof_file_id TEXT,
        reference TEXT, status TEXT DEFAULT 'pending', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, message TEXT, status TEXT DEFAULT 'Open', created_at TEXT, reply TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS coupons (code TEXT PRIMARY KEY, discount REAL,
        max_uses INTEGER, used INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS co_admins (user_id INTEGER PRIMARY KEY, name TEXT, added_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (order_id TEXT PRIMARY KEY, user_id INTEGER,
        amount REAL, status TEXT DEFAULT 'pending', created_at INTEGER, expires_at INTEGER, qr_data TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS menu_buttons (id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT, emoji TEXT DEFAULT '', action TEXT, position INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1, row_group INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS profile_fields (field_key TEXT PRIMARY KEY,
        label TEXT, is_visible INTEGER DEFAULT 1)""")

    defaults = {
        'welcome_text': '⚡ <b>Welcome to ELITE X CONFIG</b> ⚡\n\n🛍️ Premium Digital Store',
        'upi_id': '', 'payee_name': BRAND_NAME,
        'support_telegram': 'https://t.me/YourSupport',
        'support_whatsapp': 'https://wa.me/YourNumber',
        'global_maintenance': '0', 'maintenance_msg': '🛠 Bot under maintenance.',
        'daily_gift_price': '0', 'refer_earn_amount': '0',
        'admin_logo_file_id': '', 'static_qr_file_id': '',
        'ui_category_msg': '📂 <b>Select a Category</b>',
        'ui_product_msg': '📦 <b>Select a Panel</b>',
        'ui_plan_msg': '⏱ <b>Select a Plan</b>',
        'ui_key_msg': '🎉 Thank you for your purchase!',
        'payment_mode': 'manual',
        'auto_api_key': '', 'auto_api_url': '', 'auto_api_enabled': '0',
        'reseller_setup_fee': '500', 'reseller_min_balance': '1000',
        'reseller_system_status': 'ON', 'vip_system_status': 'ON',
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
    ticket = State(); coupon = State(); custom_amt = State()
    proof = State(); buy_proof = State()

class A(StatesGroup):
    cat_name = State(); cat_emoji = State(); cat_edit = State()
    panel_cat = State(); panel_name = State(); panel_desc = State(); panel_edit = State()
    plan_panel = State(); plan_name = State(); plan_price = State(); plan_rprice = State(); plan_edit = State()
    key_plan = State(); key_text = State()
    user_search = State(); user_addbal = State(); user_rembal = State()
    bc_msg = State(); cp_code = State(); cp_disc = State(); cp_max = State()
    set_logo = State(); set_qr = State(); set_upi = State(); set_payee = State()
    set_tg = State(); set_wa = State(); set_gift = State(); set_refer = State()
    set_maint = State(); set_api_key = State(); set_api_url = State()
    msg_welcome = State(); msg_cat = State(); msg_prod = State(); msg_plan = State(); msg_key = State()
    menu_add_label = State(); menu_add_emoji = State(); menu_add_action = State(); menu_edit = State()
    coadmin_add = State(); coadmin_remove = State()
    res_fee = State(); res_min = State()

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
        if u and u[0]: ex.append(InlineKeyboardButton(text="👑 " + fancy("Reseller"), callback_data="act_reseller", style="success"))
        if u and u[1]: ex.append(InlineKeyboardButton(text="🌟 " + fancy("VIP"), callback_data="act_vip", style="danger"))
        if ex: rows.append(ex)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ " + fancy("Store Manager"), callback_data="adm_store", style="primary")],
        [InlineKeyboardButton(text="👥 " + fancy("User Manager"), callback_data="adm_users", style="success")],
        [InlineKeyboardButton(text="💳 " + fancy("Payment Settings"), callback_data="adm_pay", style="success")],
        [InlineKeyboardButton(text="📢 " + fancy("Broadcast"), callback_data="adm_broadcast", style="danger")],
        [InlineKeyboardButton(text="🎟️ " + fancy("Marketing"), callback_data="adm_mkt", style="primary")],
        [InlineKeyboardButton(text="🎨 " + fancy("Menu Designer"), callback_data="adm_menu", style="success")],
        [InlineKeyboardButton(text="📝 " + fancy("Message Editor"), callback_data="adm_msg", style="primary")],
        [InlineKeyboardButton(text="🤝 " + fancy("Co-Admins"), callback_data="adm_coadmin", style="primary")],
        [InlineKeyboardButton(text="⚙️ " + fancy("Settings"), callback_data="adm_settings", style="primary")],
        [InlineKeyboardButton(text="🏠 " + fancy("User View"), callback_data="back_main", style="danger")]
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
           (uid, m.from_user.first_name, m.from_user.username or "",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    text = gs("welcome_text")
    logo = gs("admin_logo_file_id")
    kb = main_menu_kb(uid)
    if logo:
        try:
            await m.answer_photo(logo, caption=text, reply_markup=kb)
            return
        except Exception: pass
    await m.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.edit_text(gs("welcome_text"), reply_markup=main_menu_kb(call.from_user.id))
    except Exception:
        await bot.send_message(call.from_user.id, gs("welcome_text"), reply_markup=main_menu_kb(call.from_user.id))

# ============ MENU ACTIONS ============
@dp.callback_query(F.data.startswith("act_"))
async def menu_act(call: CallbackQuery, state: FSMContext):
    action = call.data[4:]
    await state.clear()
    if action == "shop":
        cats = db("SELECT id,name,emoji FROM categories WHERE is_active=1 AND is_maintenance=0", all=True)
        if not cats: return await call.answer("No categories yet!", show_alert=True)
        rows = [[InlineKeyboardButton(text=f"{c[2]} {c[1]}", callback_data=f"cat_{c[0]}", style="primary")] for c in cats]
        rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")])
        await call.message.edit_text(gs("ui_category_msg"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    elif action == "profile":
        await show_profile(call)
    elif action == "addbalance":
        await show_add_balance(call)
    elif action == "support":
        rows = []
        tg = gs("support_telegram"); wa = gs("support_whatsapp")
        if tg: rows.append([InlineKeyboardButton(text="✈️ Telegram Support", url=tg, style="primary")])
        if wa: rows.append([InlineKeyboardButton(text="📱 WhatsApp Support", url=wa, style="primary")])
        rows.append([InlineKeyboardButton(text="🎫 New Ticket", callback_data="new_ticket", style="success")])
        rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")])
        await call.message.edit_text("🎧 <b>SUPPORT CENTER</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    elif action == "daily_gift":
        gift = sfloat(gs("daily_gift_price"))
        if gift <= 0: return await call.answer("Gift disabled!", show_alert=True)
        today = datetime.now().strftime("%Y-%m-%d")
        u = db("SELECT last_gift FROM users WHERE user_id=?", (call.from_user.id,), one=True)
        if u and u[0] == today: return await call.answer("🎁 Already claimed today!", show_alert=True)
        db("UPDATE users SET balance=balance+?,last_gift=? WHERE user_id=?", (gift, today, call.from_user.id))
        await call.answer(f"🎁 +{fmt(gift)} claimed!", show_alert=True)
    elif action == "redeem_coupon":
        await state.set_state(U.coupon)
        await call.message.edit_text("🎟️ Send coupon code:", reply_markup=bk("back_main"))
    elif action == "reseller":
        u = db("SELECT is_reseller,balance FROM users WHERE user_id=?", (call.from_user.id,), one=True)
        if u[0]: return await call.message.edit_text("👑 You are a Reseller!", reply_markup=bk("back_main"))
        if gs("reseller_system_status") == "OFF":
            return await call.message.edit_text("⚠️ Reseller system closed.", reply_markup=bk("back_main"))
        fee = sfloat(gs("reseller_setup_fee", "500"))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Become Reseller {fmt(fee)}", callback_data="buy_reseller", style="success")],
            [InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")]])
        await call.message.edit_text(f"👑 <b>RESELLER PANEL</b>\n\nFee: {fmt(fee)}\nBalance: {fmt(u[1])}", reply_markup=kb)
    elif action == "vip":
        u = db("SELECT balance,is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)
        if u[1]: return await call.message.edit_text("🌟 Already VIP!", reply_markup=bk("back_main"))
        if u[0] < VIP_PRICE: return await call.message.edit_text(f"❌ Need {fmt(VIP_PRICE)}", reply_markup=bk("back_main"))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Buy VIP {fmt(VIP_PRICE)}", callback_data="buy_vip", style="success")],
            [InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")]])
        await call.message.edit_text(f"🌟 <b>VIP MEMBERSHIP</b>\n\nPrice: {fmt(VIP_PRICE)}\nDiscount: {VIP_DISCOUNT}%", reply_markup=kb)
    else:
        await call.answer("Coming soon!", show_alert=True)

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
    o = db("SELECT product_name,plan_name,price_paid,delivered_key,purchase_date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,), all=True)
    if not o: return await call.message.edit_text("📭 No orders yet.", reply_markup=bk("back_main"))
    text = "🧾 <b>MY ORDERS</b>\n"
    for r in o:
        text += f"\n📦 {r[0]} - {r[1]}\n💰 {fmt(r[2])}\n🔑 <code>{r[3]}</code>\n📅 {r[4]}"
    await call.message.edit_text(text[:4000], reply_markup=bk("back_main"))

# ============ BALANCE ============
async def show_add_balance(call: CallbackQuery):
    mode = "Auto ✅" if gs("payment_mode") == "auto" else "Manual ⏳"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₹50", callback_data="amt_50", style="primary"),
         InlineKeyboardButton(text="₹100", callback_data="amt_100", style="primary")],
        [InlineKeyboardButton(text="₹200", callback_data="amt_200", style="primary"),
         InlineKeyboardButton(text="₹500", callback_data="amt_500", style="primary")],
        [InlineKeyboardButton(text="₹1000", callback_data="amt_1000", style="primary"),
         InlineKeyboardButton(text="₹2000", callback_data="amt_2000", style="primary")],
        [InlineKeyboardButton(text="✏️ Custom Amount", callback_data="amt_custom", style="success")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="back_main", style="danger")]])
    await call.message.edit_text(f"💰 <b>ADD BALANCE</b>\n━━━━━━━━━━━━━━━━━━\n🔧 Mode: {mode}\n\nSelect amount:", reply_markup=kb)

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
    except Exception:
        return await m.answer("❌ Invalid")
    await state.clear()
    await make_payment(m.from_user.id, a, m)

async def make_payment(uid, amount, target):
    upi = gs("upi_id"); static_qr = gs("static_qr_file_id")
    if not upi and not static_qr:
        msg = "⚠️ Admin ne payment setup nahi kiya."
        if isinstance(target, CallbackQuery): await target.message.edit_text(msg, reply_markup=bk("back_main"))
        else: await target.answer(msg, reply_markup=bk("back_main"))
        return
    oid = f"PAY{uid}{int(time.time())}"
    expires = int(time.time()) + 300
    qr_file = None
    if upi:
        payee = gs("payee_name", BRAND_NAME)
        link = upi_link(upi, payee, amount, f"Pay {oid}")
        db("INSERT OR REPLACE INTO transactions (order_id,user_id,amount,status,created_at,expires_at,qr_data) VALUES (?,?,?,'pending',?,?,?)",
           (oid, uid, amount, int(time.time()), expires, link))
        qr_file = make_qr(link)
    else:
        db("INSERT OR REPLACE INTO transactions (order_id,user_id,amount,status,created_at,expires_at,qr_data) VALUES (?,?,?,'pending',?,?,'')",
           (oid, uid, amount, int(time.time()), expires))
    text = (f"🧾 <b>PAYMENT REQUEST</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"💵 Amount: <b>{fmt(amount)}</b>\n"
            f"🆔 Order: <code>{oid}</code>\n")
    if upi: text += f"🏦 UPI: <code>{upi}</code>\n"
    text += ("⏳ Valid 5 min\n━━━━━━━━━━━━━━━━━━\n📱 Scan QR & pay\n✅ Then tap 'I Have Paid'")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I Have Paid", callback_data=f"paid_{oid}", style="success")],
        [InlineKeyboardButton(text="🔄 Check Auto", callback_data=f"autocheck_{oid}", style="primary")],
        [InlineKeyboardButton(text=fancy("Cancel"), callback_data="back_main", style="danger")]])
    try:
        if isinstance(target, CallbackQuery): await target.message.delete()
    except Exception: pass
    if qr_file: await bot.send_photo(uid, qr_file, caption=text, reply_markup=kb)
    elif static_qr: await bot.send_photo(uid, static_qr, caption=text, reply_markup=kb)
    else: await bot.send_message(uid, text, reply_markup=kb)

@dp.callback_query(F.data.startswith("paid_"))
async def paid(call: CallbackQuery, state: FSMContext):
    oid = call.data[5:]
    t = db("SELECT amount,status FROM transactions WHERE order_id=?", (oid,), one=True)
    if not t: return await call.answer("❌ Not found!", show_alert=True)
    if t[1] == "paid": return await call.answer("✅ Already credited!", show_alert=True)
    await state.update_data(po=oid, pa=t[0])
    await state.set_state(U.proof)
    await call.message.edit_text(f"📸 Send Screenshot or UTR\nAmount: {fmt(t[0])}", reply_markup=bk("back_main"))

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
            caption=f"💰 <b>BALANCE PROOF</b>\n👤 <code>{m.from_user.id}</code>\n💵 {fmt(amt)}\n🆔 {oid}",
            reply_markup=kb)
    except Exception: pass

@dp.message(U.proof)
async def proof_text(m: Message, state: FSMContext):
    d = await state.get_data()
    oid, amt = d.get("po"), d.get("pa", 0)
    db("INSERT INTO balance_requests (user_id,username,amount,method,reference,status,created_at) VALUES (?,?,?,'manual',?,'pending',?)",
       (m.from_user.id, m.from_user.username or "", amt, f"{oid}|UTR:{m.text[:80]}",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await state.clear()
    await m.answer("✅ UTR sent! Admin will verify.", reply_markup=main_menu_kb(m.from_user.id))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Credit", callback_data=f"credit_{oid}", style="success"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{oid}", style="danger")]])
    try:
        await bot.send_message(ADMIN_ID,
            f"💰 <b>UTR</b>\n👤 <code>{m.from_user.id}</code>\n💵 {fmt(amt)}\n🆔 {oid}\n📝 {m.text[:200]}",
            reply_markup=kb)
    except Exception: pass

@dp.callback_query(F.data.startswith("autocheck_"))
async def auto_check(call: CallbackQuery):
    oid = call.data[10:]
    if gs("payment_mode") != "auto":
        return await call.answer("⏳ Auto OFF. Send screenshot.", show_alert=True)
    if gs("auto_api_enabled", "0") != "1" or not gs("auto_api_url"):
        return await call.answer("⚠️ API not configured.", show_alert=True)
    await call.answer("🔄 Checking...", show_alert=False)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{gs('auto_api_url')}?order_id={oid}&api_key={gs('auto_api_key')}", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if data.get("status") == "success" or data.get("paid") is True:
                        t = db("SELECT user_id,amount,status FROM transactions WHERE order_id=?", (oid,), one=True)
                        if t and t[2] != "paid":
                            db("UPDATE transactions SET status='paid' WHERE order_id=?", (oid,))
                            db("UPDATE users SET balance=balance+? WHERE user_id=?", (t[1], t[0]))
                            await call.message.edit_text(f"✅ Payment verified!\n+{fmt(t[1])} added.", reply_markup=bk("back_main"))
                            return
                    await call.answer("⏳ Not received yet.", show_alert=True)
    except Exception as e:
        await call.answer(f"⚠️ Error: {str(e)[:50]}", show_alert=True)

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
    try: await bot.send_message(t[0], f"✅ <b>Payment Verified!</b>\n+{fmt(t[1])} added.")
    except Exception: pass
    try: await call.message.edit_reply_markup(reply_markup=None)
    except Exception: pass

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
    except Exception: pass
    try: await call.message.edit_reply_markup(reply_markup=None)
    except Exception: pass

# ============ SHOP FLOW ============
@dp.callback_query(F.data.startswith("cat_"))
async def show_panels(call: CallbackQuery):
    cid = int(call.data[4:])
    panels = db("SELECT id,name FROM products WHERE category_id=? AND is_active=1 AND is_maintenance=0", (cid,), all=True)
    if not panels: return await call.answer("No panels!", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"📦 {p[1]}", callback_data=f"panel_{p[0]}", style="primary")] for p in panels]
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="act_shop", style="danger")])
    await call.message.edit_text(gs("ui_product_msg"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("panel_"))
async def show_plans(call: CallbackQuery):
    pid = int(call.data[6:])
    p = db("SELECT name FROM products WHERE id=?", (pid,), one=True)
    if not p: return await call.answer("Panel not found!", show_alert=True)
    plans = db("SELECT id,name,price,reseller_price FROM plans WHERE product_id=? AND is_active=1", (pid,), all=True)
    if not plans: return await call.answer("No plans!", show_alert=True)
    u = db("SELECT is_reseller,is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)
    rows = []
    for pl in plans:
        base = pl[3] if (u and u[0] and pl[3] > 0) else pl[2]
        final = base - (base * VIP_DISCOUNT / 100) if (u and u[1]) else base
        avail = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (pl[0],), one=True)[0]
        stock = "🟢" if avail > 0 else "🔴"
        rows.append([InlineKeyboardButton(text=f"⏱ {pl[1]} - {fmt(final)} {stock}", callback_data=f"plan_{pl[0]}", style="success")])
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="act_shop", style="danger")])
    await call.message.edit_text(f"📦 <b>{p[0]}</b>\n\n{gs('ui_plan_msg')}", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("plan_"))
async def buy_plan(call: CallbackQuery):
    plid = int(call.data[5:])
    pl = db("SELECT id,product_id,name,price,reseller_price FROM plans WHERE id=?", (plid,), one=True)
    if not pl: return await call.answer("Plan not found!", show_alert=True)
    prod = db("SELECT name FROM products WHERE id=?", (pl[1],), one=True)
    u = db("SELECT balance,is_reseller,is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)
    base = pl[4] if (u[1] and pl[4] > 0) else pl[3]
    final = base - (base * VIP_DISCOUNT / 100) if u[2] else base
    avail = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (plid,), one=True)[0]
    if avail <= 0: return await call.answer("❌ Out of stock!", show_alert=True)
    text = (f"🛒 <b>ORDER SUMMARY</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"📦 Panel: <b>{prod[0]}</b>\n⏱ Plan: <b>{pl[2]}</b>\n"
            f"💰 Price: <b>{fmt(final)}</b>\n💵 Balance: <b>{fmt(u[0])}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\nChoose payment:")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Pay with Wallet", callback_data=f"walletbuy_{plid}", style="success")],
        [InlineKeyboardButton(text="💳 Pay via QR", callback_data=f"qrpay_{plid}", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data=f"panel_{pl[1]}", style="danger")]])
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("walletbuy_"))
async def wallet_buy(call: CallbackQuery):
    plid = int(call.data[10:])
    pl = db("SELECT id,product_id,name,price,reseller_price FROM plans WHERE id=?", (plid,), one=True)
    if not pl: return await call.answer("Plan not found!", show_alert=True)
    prod = db("SELECT name FROM products WHERE id=?", (pl[1],), one=True)
    u = db("SELECT balance,is_reseller,is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)
    base = pl[4] if (u[1] and pl[4] > 0) else pl[3]
    final = base - (base * VIP_DISCOUNT / 100) if u[2] else base
    if u[0] < final: return await call.answer(f"❌ Need {fmt(final)}. Add balance.", show_alert=True)
    key = db("SELECT id,key_text FROM product_keys WHERE plan_id=? AND is_used=0 LIMIT 1", (plid,), one=True)
    if not key: return await call.answer("❌ Out of stock!", show_alert=True)
    db("UPDATE users SET balance=balance-? WHERE user_id=?", (final, call.from_user.id))
    db("UPDATE product_keys SET is_used=1 WHERE id=?", (key[0],))
    db("INSERT INTO orders (user_id,plan_id,plan_name,product_name,price_paid,delivered_key,purchase_date) VALUES (?,?,?,?,?,?,?)",
       (call.from_user.id, plid, pl[2], prod[0], final, key[1], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    text = (f"🎉 <b>PURCHASE SUCCESSFUL!</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"📦 {prod[0]}\n⏱ {pl[2]}\n💰 {fmt(final)}\n"
            f"🔑 <b>Your Key:</b>\n<code>{key[1]}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n{gs('ui_key_msg')}")
    await call.message.edit_text(text, reply_markup=main_menu_kb(call.from_user.id))
    try: await bot.send_message(ADMIN_ID, f"🛒 <b>NEW ORDER</b>\n👤 <code>{call.from_user.id}</code>\n📦 {prod[0]} - {pl[2]}\n💰 {fmt(final)}")
    except Exception: pass

@dp.callback_query(F.data.startswith("qrpay_"))
async def qr_buy(call: CallbackQuery, state: FSMContext):
    plid = int(call.data[6:])
    pl = db("SELECT id,product_id,name,price,reseller_price FROM plans WHERE id=?", (plid,), one=True)
    if not pl: return await call.answer("Plan not found!", show_alert=True)
    prod = db("SELECT name FROM products WHERE id=?", (pl[1],), one=True)
    u = db("SELECT is_reseller,is_vip FROM users WHERE user_id=?", (call.from_user.id,), one=True)
    base = pl[4] if (u[0] and pl[4] > 0) else pl[3]
    final = base - (base * VIP_DISCOUNT / 100) if u[1] else base
    upi = gs("upi_id"); static_qr = gs("static_qr_file_id")
    if not upi and not static_qr:
        return await call.answer("⚠️ Payment not setup!", show_alert=True)
    oid = f"ORD{call.from_user.id}{int(time.time())}"
    expires = int(time.time()) + 300
    qr_file = None
    if upi:
        payee = gs("payee_name", BRAND_NAME)
        link = upi_link(upi, payee, final, f"Order {oid}")
        db("INSERT OR REPLACE INTO transactions (order_id,user_id,amount,status,created_at,expires_at,qr_data) VALUES (?,?,?,'pending',?,?,?)",
           (oid, call.from_user.id, final, int(time.time()), expires, link))
        qr_file = make_qr(link)
    else:
        db("INSERT OR REPLACE INTO transactions (order_id,user_id,amount,status,created_at,expires_at,qr_data) VALUES (?,?,?,'pending',?,?,'')",
           (oid, call.from_user.id, final, int(time.time()), expires))
    await state.update_data(buy_oid=oid, buy_amount=final, buy_plan_id=plid,
                            buy_plan_name=pl[2], buy_product_name=prod[0])
    text = (f"💳 <b>QR PAYMENT</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"📦 {prod[0]} - {pl[2]}\n💵 <b>{fmt(final)}</b>\n"
            f"🆔 <code>{oid}</code>\n")
    if upi: text += f"🏦 UPI: <code>{upi}</code>\n"
    text += "⏳ Valid 5 min\n━━━━━━━━━━━━━━━━━━\n📱 Scan & pay\n✅ Then tap 'I Have Paid'"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I Have Paid", callback_data=f"bpaid_{oid}", style="success")],
        [InlineKeyboardButton(text="🔄 Check Auto", callback_data=f"bautocheck_{oid}", style="primary")],
        [InlineKeyboardButton(text=fancy("Cancel"), callback_data="back_main", style="danger")]])
    try: await call.message.delete()
    except Exception: pass
    if qr_file: await bot.send_photo(call.from_user.id, qr_file, caption=text, reply_markup=kb)
    elif static_qr: await bot.send_photo(call.from_user.id, static_qr, caption=text, reply_markup=kb)
    else: await bot.send_message(call.from_user.id, text, reply_markup=kb)

@dp.callback_query(F.data.startswith("bpaid_"))
async def buy_paid(call: CallbackQuery, state: FSMContext):
    oid = call.data[6:]
    t = db("SELECT amount,status FROM transactions WHERE order_id=?", (oid,), one=True)
    if not t: return await call.answer("Not found!", show_alert=True)
    if t[1] == "paid": return await call.answer("✅ Already processed!", show_alert=True)
    await state.update_data(buy_proof_oid=oid, po=oid, pa=t[0])
    await state.set_state(U.buy_proof)
    await call.message.edit_text(f"📸 Send payment screenshot OR UTR\nAmount: {fmt(t[0])}", reply_markup=bk("back_main"))

@dp.message(U.buy_proof)
async def buy_proof_handler(m: Message, state: FSMContext):
    d = await state.get_data()
    oid = d.get("buy_proof_oid") or d.get("buy_oid")
    plid = d.get("buy_plan_id"); final = d.get("buy_amount", 0)
    pl_name = d.get("buy_plan_name", ""); prod_name = d.get("buy_product_name", "")
    if not oid: return await m.answer("❌ Session expired.", reply_markup=main_menu_kb(m.from_user.id))
    proof_id = m.photo[-1].file_id if m.photo else ""
    utr = m.text or ""
    db("INSERT INTO balance_requests (user_id,username,amount,method,proof_file_id,reference,status,created_at) VALUES (?,?,?,'order',?,?,'pending',?)",
       (m.from_user.id, m.from_user.username or "", final, proof_id,
        f"{oid}|PLAN:{plid}|UTR:{utr[:80]}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await state.clear()
    await m.answer("✅ Proof sent! Admin will deliver key.", reply_markup=main_menu_kb(m.from_user.id))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve & Deliver", callback_data=f"order_approve_{oid}", style="success"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"order_reject_{oid}", style="danger")]])
    caption = (f"🛒 <b>ORDER PAYMENT</b>\n👤 <code>{m.from_user.id}</code>\n"
               f"📦 {prod_name} - {pl_name}\n💵 {fmt(final)}\n🆔 {oid}")
    try:
        if proof_id: await bot.send_photo(ADMIN_ID, proof_id, caption=caption, reply_markup=kb)
        else: await bot.send_message(ADMIN_ID, caption + f"\n📝 UTR: {utr[:200]}", reply_markup=kb)
    except Exception: pass

@dp.callback_query(F.data.startswith("order_approve_"))
async def order_approve(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    oid = call.data[14:]
    req = db("SELECT id,user_id,amount,reference FROM balance_requests WHERE reference LIKE ? ORDER BY id DESC LIMIT 1", (f"{oid}|PLAN:%",), one=True)
    if not req: return await call.answer("Order not found!", show_alert=True)
    try:
        parts = req[3].split("|")
        plan_part = [p for p in parts if p.startswith("PLAN:")]
        plid = int(plan_part[0].split(":")[1]) if plan_part else None
    except Exception: plid = None
    if not plid: return await call.answer("Invalid order data!", show_alert=True)
    pl = db("SELECT id,name,product_id FROM plans WHERE id=?", (plid,), one=True)
    if not pl: return await call.answer("Plan gone!", show_alert=True)
    prod = db("SELECT name FROM products WHERE id=?", (pl[2],), one=True)
    key = db("SELECT id,key_text FROM product_keys WHERE plan_id=? AND is_used=0 LIMIT 1", (plid,), one=True)
    if not key: return await call.answer("❌ No key in stock!", show_alert=True)
    db("UPDATE product_keys SET is_used=1 WHERE id=?", (key[0],))
    db("UPDATE transactions SET status='paid' WHERE order_id=?", (oid,))
    db("UPDATE balance_requests SET status='approved' WHERE id=?", (req[0],))
    db("INSERT INTO orders (user_id,plan_id,plan_name,product_name,price_paid,delivered_key,purchase_date) VALUES (?,?,?,?,?,?,?)",
       (req[1], plid, pl[0], prod[0], req[2], key[1], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await call.answer("✅ Delivered!", show_alert=True)
    try: await call.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    text = (f"🎉 <b>ORDER DELIVERED!</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"📦 {prod[0]}\n⏱ {pl[0]}\n💰 {fmt(req[2])}\n"
            f"🔑 <b>Your Key:</b>\n<code>{key[1]}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n{gs('ui_key_msg')}")
    try: await bot.send_message(req[1], text, reply_markup=main_menu_kb(req[1]))
    except Exception: pass

@dp.callback_query(F.data.startswith("order_reject_"))
async def order_reject(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    oid = call.data[13:]
    req = db("SELECT id,user_id FROM balance_requests WHERE reference LIKE ? ORDER BY id DESC LIMIT 1", (f"{oid}|PLAN:%",), one=True)
    if req:
        db("UPDATE balance_requests SET status='rejected' WHERE id=?", (req[0],))
        try: await bot.send_message(req[1], "❌ Payment rejected.", reply_markup=main_menu_kb(req[1]))
        except Exception: pass
    db("UPDATE transactions SET status='rejected' WHERE order_id=?", (oid,))
    await call.answer("❌ Rejected!", show_alert=True)
    try: await call.message.edit_reply_markup(reply_markup=None)
    except Exception: pass

@dp.callback_query(F.data.startswith("bautocheck_"))
async def buy_auto_check(call: CallbackQuery):
    oid = call.data[11:]
    if gs("payment_mode") != "auto":
        return await call.answer("⏳ Auto OFF. Send screenshot.", show_alert=True)
    if gs("auto_api_enabled", "0") != "1" or not gs("auto_api_url"):
        return await call.answer("⚠️ API not configured.", show_alert=True)
    await call.answer("🔄 Checking...", show_alert=False)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{gs('auto_api_url')}?order_id={oid}&api_key={gs('auto_api_key')}", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if data.get("status") == "success" or data.get("paid") is True:
                        fake = type('obj', (), {'from_user': call.from_user, 'data': f'order_approve_{oid}',
                                                 'answer': call.answer, 'message': call.message})()
                        await order_approve(fake)
                        return
                    await call.answer("⏳ Not received.", show_alert=True)
    except Exception as e:
        await call.answer(f"⚠️ Error: {str(e)[:50]}", show_alert=True)

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
    try: await bot.send_message(ADMIN_ID, f"🚨 <b>TICKET</b>\nFrom: <code>{m.from_user.id}</code>\n\n{m.text}")
    except Exception: pass

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
    await m.answer("⚙️ <b>ADMIN CONTROL PANEL</b>", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_back")
async def adm_back(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.clear()
    await call.message.edit_text("⚙️ <b>ADMIN CONTROL PANEL</b>", reply_markup=admin_kb())

# ============ BROADCAST ============
@dp.callback_query(F.data == "adm_broadcast")
async def broadcast_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Send Broadcast", callback_data="adm_bc_send", style="success")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text(
        "📢 <b>BROADCAST SYSTEM</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        "Send a message and it will be delivered to ALL users.\n\n"
        "✅ Text, Photo, Video, Document - all supported", reply_markup=kb)

@dp.callback_query(F.data == "adm_bc_send")
async def bc_send_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.bc_msg)
    await call.message.edit_text(
        "📢 <b>Send your broadcast message now</b>\n\n"
        "Send /cancel to cancel.", reply_markup=bk("adm_broadcast"))

@dp.message(A.bc_msg)
async def bc_send(m: Message, state: FSMContext):
    users = db("SELECT user_id FROM users", all=True)
    sent, failed = 0, 0
    st = await m.answer(f"⏳ Broadcasting to {len(users or [])} users...")
    for u in users or []:
        try:
            await m.send_copy(chat_id=u[0]); sent += 1
        except Exception: failed += 1
        await asyncio.sleep(0.05)
    await st.edit_text(f"✅ <b>Broadcast Complete!</b>\n\n🟢 Sent: {sent}\n🔴 Failed: {failed}",
                       reply_markup=admin_kb())
    await state.clear()

# ============ STORE MANAGER ============
@dp.callback_query(F.data == "adm_store")
async def adm_store(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Categories", callback_data="adm_cats", style="success"),
         InlineKeyboardButton(text="📦 Panels", callback_data="adm_panels", style="success")],
        [InlineKeyboardButton(text="⏱ Plans", callback_data="adm_plans", style="primary"),
         InlineKeyboardButton(text="🔑 Keys", callback_data="adm_keys", style="primary")],
        [InlineKeyboardButton(text="🛠️ Maintenance", callback_data="adm_maint", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("🛍️ <b>STORE MANAGER</b>", reply_markup=kb)

# ---------- CATEGORIES ----------
@dp.callback_query(F.data == "adm_cats")
async def adm_cats(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Category", callback_data="adm_cat_add", style="success")],
        [InlineKeyboardButton(text="📋 List Categories", callback_data="adm_cat_list", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]])
    await call.message.edit_text("📂 <b>CATEGORY MANAGER</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_cat_add")
async def cat_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.cat_name)
    await call.message.edit_text("Enter Category Name:", reply_markup=bk("adm_cats"))

@dp.message(A.cat_name)
async def cat_name_save(m: Message, state: FSMContext):
    await state.update_data(cn=m.text)
    await state.set_state(A.cat_emoji)
    await m.answer("Enter Emoji (e.g., 📱):")

@dp.message(A.cat_emoji)
async def cat_emoji_save(m: Message, state: FSMContext):
    d = await state.get_data()
    db("INSERT INTO categories (name,emoji) VALUES (?,?)", (d['cn'], m.text))
    await state.clear()
    await m.answer("✅ Category added!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_cat_list")
async def cat_list(call: CallbackQuery):
    cats = db("SELECT id,name,emoji FROM categories", all=True)
    if not cats: return await call.message.edit_text("No categories yet.", reply_markup=bk("adm_cats"))
    rows = [[InlineKeyboardButton(text=f"{c[2]} {c[1]}", callback_data=f"catv_{c[0]}", style="primary")] for c in cats]
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_cats", style="danger")])
    await call.message.edit_text("Select Category to Edit:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("catv_"))
async def cat_view(call: CallbackQuery):
    cid = int(call.data[5:])
    c = db("SELECT name,emoji,is_active FROM categories WHERE id=?", (cid,), one=True)
    if not c: return await call.answer("Not found!", show_alert=True)
    st = "🟢 Active" if c[2] else "🔴 Inactive"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Name", callback_data=f"cate_{cid}_name", style="primary"),
         InlineKeyboardButton(text="😀 Emoji", callback_data=f"cate_{cid}_emoji", style="primary")],
        [InlineKeyboardButton(text="👁️ Toggle", callback_data=f"cattog_{cid}", style="success"),
         InlineKeyboardButton(text="🗑️ Delete", callback_data=f"catd_{cid}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_cat_list", style="danger")]])
    await call.message.edit_text(f"{c[1]} <b>{c[0]}</b>\n\nID: {cid}\n{st}", reply_markup=kb)

@dp.callback_query(F.data.startswith("cate_"))
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

@dp.callback_query(F.data.startswith("cattog_"))
async def cat_toggle(call: CallbackQuery):
    cid = int(call.data[7:])
    cur = db("SELECT is_active FROM categories WHERE id=?", (cid,), one=True)[0]
    db("UPDATE categories SET is_active=? WHERE id=?", (0 if cur else 1, cid))
    await call.answer("✅ Toggled!", show_alert=True)

@dp.callback_query(F.data.startswith("catd_"))
async def cat_del(call: CallbackQuery):
    cid = int(call.data[5:])
    prods = db("SELECT id FROM products WHERE category_id=?", (cid,), all=True)
    for p in prods or []:
        plans = db("SELECT id FROM plans WHERE product_id=?", (p[0],), all=True)
        for pl in plans or []:
            db("DELETE FROM product_keys WHERE plan_id=?", (pl[0],))
        db("DELETE FROM plans WHERE product_id=?", (p[0],))
    db("DELETE FROM products WHERE category_id=?", (cid,))
    db("DELETE FROM categories WHERE id=?", (cid,))
    await call.answer("✅ Deleted!", show_alert=True)
    await cat_list(call)

# ---------- PANELS ----------
@dp.callback_query(F.data == "adm_panels")
async def adm_panels(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Panel", callback_data="adm_panel_add", style="success")],
        [InlineKeyboardButton(text="📋 List Panels", callback_data="adm_panel_list", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]])
    await call.message.edit_text("📦 <b>PANEL MANAGER</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_panel_add")
async def panel_add(call: CallbackQuery):
    cats = db("SELECT id,name,emoji FROM categories", all=True)
    if not cats: return await call.answer("Add category first!", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"{c[2]} {c[1]}", callback_data=f"panelc_{c[0]}", style="primary")] for c in cats]
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_panels", style="danger")])
    await call.message.edit_text("Select Category:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("panelc_"))
async def panel_cat(call: CallbackQuery, state: FSMContext):
    cid = int(call.data[7:])
    await state.update_data(pc=cid)
    await state.set_state(A.panel_name)
    await call.message.edit_text("Enter Panel Name:", reply_markup=bk("adm_panels"))

@dp.message(A.panel_name)
async def panel_name_save(m: Message, state: FSMContext):
    await state.update_data(pn=m.text)
    await state.set_state(A.panel_desc)
    await m.answer("Enter Description (or 'none'):")

@dp.message(A.panel_desc)
async def panel_desc_save(m: Message, state: FSMContext):
    d = await state.get_data()
    desc = "" if m.text.lower() == 'none' else m.text
    db("INSERT INTO products (category_id,name,description) VALUES (?,?,?)", (d['pc'], d['pn'], desc))
    await state.clear()
    await m.answer("✅ Panel added!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_panel_list")
async def panel_list(call: CallbackQuery):
    panels = db("SELECT p.id,p.name,c.name FROM products p LEFT JOIN categories c ON c.id=p.category_id", all=True)
    if not panels: return await call.message.edit_text("No panels yet.", reply_markup=bk("adm_panels"))
    rows = [[InlineKeyboardButton(text=f"📦 {p[1]} ({p[2] or 'N/A'})", callback_data=f"panelv_{p[0]}", style="primary")] for p in panels]
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_panels", style="danger")])
    await call.message.edit_text("Select Panel:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("panelv_"))
async def panel_view(call: CallbackQuery):
    pid = int(call.data[7:])
    p = db("SELECT name,description,is_active FROM products WHERE id=?", (pid,), one=True)
    if not p: return await call.answer("Not found!", show_alert=True)
    plans = db("SELECT COUNT(*) FROM plans WHERE product_id=?", (pid,), one=True)[0]
    st = "🟢 Active" if p[2] else "🔴 Inactive"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Name", callback_data=f"panele_{pid}_name", style="primary"),
         InlineKeyboardButton(text="📝 Desc", callback_data=f"panele_{pid}_description", style="primary")],
        [InlineKeyboardButton(text="👁️ Toggle", callback_data=f"paneltog_{pid}", style="success"),
         InlineKeyboardButton(text="🗑️ Delete", callback_data=f"paneld_{pid}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_panel_list", style="danger")]])
    await call.message.edit_text(f"📦 <b>{p[0]}</b>\n\nDesc: {p[1] or 'None'}\nPlans: {plans}\n{st}", reply_markup=kb)

@dp.callback_query(F.data.startswith("panele_"))
async def panel_edit(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_", 2)
    pid, field = int(parts[1]), parts[2]
    await state.update_data(pe_id=pid, pe_field=field)
    await state.set_state(A.panel_edit)
    await call.message.edit_text(f"New {field}:", reply_markup=bk("adm_panel_list"))

@dp.message(A.panel_edit)
async def panel_edit_save(m: Message, state: FSMContext):
    d = await state.get_data()
    val = "" if m.text.lower() == 'none' else m.text
    db(f"UPDATE products SET {d['pe_field']}=? WHERE id=?", (val, d['pe_id']))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("paneltog_"))
async def panel_toggle(call: CallbackQuery):
    pid = int(call.data[9:])
    cur = db("SELECT is_active FROM products WHERE id=?", (pid,), one=True)[0]
    db("UPDATE products SET is_active=? WHERE id=?", (0 if cur else 1, pid))
    await call.answer("✅ Toggled!", show_alert=True)

@dp.callback_query(F.data.startswith("paneld_"))
async def panel_del(call: CallbackQuery):
    pid = int(call.data[7:])
    plans = db("SELECT id FROM plans WHERE product_id=?", (pid,), all=True)
    for pl in plans or []:
        db("DELETE FROM product_keys WHERE plan_id=?", (pl[0],))
    db("DELETE FROM plans WHERE product_id=?", (pid,))
    db("DELETE FROM products WHERE id=?", (pid,))
    await call.answer("✅ Deleted!", show_alert=True)
    await panel_list(call)

# ---------- PLANS ----------
@dp.callback_query(F.data == "adm_plans")
async def adm_plans(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Plan", callback_data="adm_plan_add", style="success")],
        [InlineKeyboardButton(text="📋 List Plans", callback_data="adm_plan_list", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]])
    await call.message.edit_text("⏱ <b>PLAN MANAGER</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_plan_add")
async def plan_add(call: CallbackQuery):
    panels = db("SELECT p.id,p.name,c.name FROM products p LEFT JOIN categories c ON c.id=p.category_id", all=True)
    if not panels: return await call.answer("Add panel first!", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"📦 {p[1]} ({p[2] or 'N/A'})", callback_data=f"planp_{p[0]}", style="primary")] for p in panels]
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_plans", style="danger")])
    await call.message.edit_text("Select Panel:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("planp_"))
async def plan_panel(call: CallbackQuery, state: FSMContext):
    pid = int(call.data[6:])
    await state.update_data(pl_pid=pid)
    await state.set_state(A.plan_name)
    await call.message.edit_text("Enter Plan Name (1 Hour, 1 Day, 1 Month):", reply_markup=bk("adm_plans"))

@dp.message(A.plan_name)
async def plan_name_save(m: Message, state: FSMContext):
    await state.update_data(pl_n=m.text)
    await state.set_state(A.plan_price)
    await m.answer("Enter Price (₹):")

@dp.message(A.plan_price)
async def plan_price_save(m: Message, state: FSMContext):
    try: p = float(m.text)
    except Exception: return await m.answer("❌ Number!")
    await state.update_data(pl_p=p)
    await state.set_state(A.plan_rprice)
    await m.answer("Enter Reseller Price (₹, 0 = same):")

@dp.message(A.plan_rprice)
async def plan_rprice_save(m: Message, state: FSMContext):
    try: rp = float(m.text)
    except Exception: return await m.answer("❌ Number!")
    d = await state.get_data()
    db("INSERT INTO plans (product_id,name,price,reseller_price) VALUES (?,?,?,?)",
       (d['pl_pid'], d['pl_n'], d['pl_p'], rp))
    await state.clear()
    await m.answer("✅ Plan added!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_plan_list")
async def plan_list(call: CallbackQuery):
    plans = db("""SELECT pl.id,pl.name,pl.price,p.name FROM plans pl
                  LEFT JOIN products p ON p.id=pl.product_id ORDER BY pl.id DESC""", all=True)
    if not plans: return await call.message.edit_text("No plans yet.", reply_markup=bk("adm_plans"))
    rows = [[InlineKeyboardButton(text=f"⏱ {pl[1]} - {fmt(pl[2])} ({pl[3] or 'N/A'})", callback_data=f"planv_{pl[0]}", style="primary")] for pl in plans]
    rows.append([InlineKeyboardButton(text=fancy("Back"), callback_data="adm_plans", style="danger")])
    await call.message.edit_text("Select Plan:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("planv_"))
async def plan_view(call: CallbackQuery):
    plid = int(call.data[6:])
    pl = db("SELECT name,price,reseller_price,is_active FROM plans WHERE id=?", (plid,), one=True)
    if not pl: return await call.answer("Not found!", show_alert=True)
    avail = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (plid,), one=True)[0]
    st = "🟢 Active" if pl[3] else "🔴 Inactive"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Name", callback_data=f"plane_{plid}_name", style="primary"),
         InlineKeyboardButton(text="💰 Price", callback_data=f"plane_{plid}_price", style="primary")],
        [InlineKeyboardButton(text="👑 Reseller Price", callback_data=f"plane_{plid}_reseller_price", style="primary")],
        [InlineKeyboardButton(text="➕ Add Keys", callback_data=f"planaddk_{plid}", style="success")],
        [InlineKeyboardButton(text="👁️ Toggle", callback_data=f"plantog_{plid}", style="success"),
         InlineKeyboardButton(text="🗑️ Delete", callback_data=f"pland_{plid}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_plan_list", style="danger")]])
    await call.message.edit_text(f"⏱ <b>{pl[0]}</b>\n💰 {fmt(pl[1])}\n👑 {fmt(pl[2])}\n🔑 Available: {avail}\n{st}", reply_markup=kb)

@dp.callback_query(F.data.startswith("plane_"))
async def plan_edit(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_", 2)
    plid, field = int(parts[1]), parts[2]
    await state.update_data(ple_id=plid, ple_field=field)
    await state.set_state(A.plan_edit)
    await call.message.edit_text(f"New {field}:", reply_markup=bk("adm_plan_list"))

@dp.message(A.plan_edit)
async def plan_edit_save(m: Message, state: FSMContext):
    d = await state.get_data()
    field = d['ple_field']; val = m.text
    if field in ('price', 'reseller_price'):
        try: val = float(val)
        except Exception: return await m.answer("❌ Number!")
    db(f"UPDATE plans SET {field}=? WHERE id=?", (val, d['ple_id']))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("plantog_"))
async def plan_toggle(call: CallbackQuery):
    plid = int(call.data[8:])
    cur = db("SELECT is_active FROM plans WHERE id=?", (plid,), one=True)[0]
    db("UPDATE plans SET is_active=? WHERE id=?", (0 if cur else 1, plid))
    await call.answer("✅ Toggled!", show_alert=True)

@dp.callback_query(F.data.startswith("planaddk_"))
async def plan_add_keys(call: CallbackQuery, state: FSMContext):
    plid = int(call.data[9:])
    await state.update_data(key_plid=plid)
    await state.set_state(A.key_text)
    await call.message.edit_text("Paste Keys (1 per line):", reply_markup=bk("adm_plan_list"))

@dp.message(A.key_text)
async def plan_keys_save(m: Message, state: FSMContext):
    d = await state.get_data()
    plid = d['key_plid']
    keys = [k.strip() for k in m.text.split('\n') if k.strip()]
    if not keys: return await m.answer("❌ No keys!")
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    for k in keys:
        c.execute("INSERT INTO product_keys (plan_id,key_text) VALUES (?,?)", (plid, k))
    conn.commit(); conn.close()
    await state.clear()
    await m.answer(f"✅ {len(keys)} keys added!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("pland_"))
async def plan_del(call: CallbackQuery):
    plid = int(call.data[6:])
    db("DELETE FROM plans WHERE id=?", (plid,))
    db("DELETE FROM product_keys WHERE plan_id=?", (plid,))
    await call.answer("✅ Deleted!", show_alert=True)
    await plan_list(call)

# ---------- KEYS ----------
@dp.callback_query(F.data == "adm_keys")
async def adm_keys(call: CallbackQuery):
    plans = db("""SELECT pl.id,pl.name,p.name FROM plans pl
                  LEFT JOIN products p ON p.id=pl.product_id""", all=True)
    text = "🔑 <b>KEY STOCK</b>\n━━━━━━━━━━━━━━━━━━\n"
    for pl in plans or []:
        av = db("SELECT COUNT(*) FROM product_keys WHERE plan_id=? AND is_used=0", (pl[0],), one=True)[0]
        text += f"\n⏱ {pl[2] or ''} - {pl[1]}: 🟢 {av}"
    if not plans: text += "\nNo plans yet."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Clear Unused Keys", callback_data="adm_key_clear", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_store", style="danger")]])
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "adm_key_clear")
async def key_clear(call: CallbackQuery):
    db("DELETE FROM product_keys WHERE is_used=0")
    await call.answer("🧹 Cleared!", show_alert=True)

# ---------- MAINTENANCE ----------
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

# ============ USER MANAGER ============
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
         InlineKeyboardButton(text="🌟 VIP Toggle", callback_data=f"uv_{u[0]}", style="success")],
        [InlineKeyboardButton(text="👑 Reseller Toggle", callback_data=f"ures_{u[0]}", style="primary")],
        [InlineKeyboardButton(text="➕ Add ₹", callback_data=f"ua_{u[0]}", style="success"),
         InlineKeyboardButton(text="➖ Remove ₹", callback_data=f"ur_{u[0]}", style="danger")],
        [InlineKeyboardButton(text="🗑️ DELETE USER", callback_data=f"udel_{u[0]}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_users", style="danger")]])
    await m.answer(f"👤 <b>USER</b>\n🆔 <code>{u[0]}</code>\n📛 {u[1]}\n💰 {fmt(u[2])}\n📊 {st}\n🏷 {' | '.join(tags) if tags else 'Regular'}", reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data == "adm_u_all")
async def u_all(call: CallbackQuery):
    users = db("SELECT user_id,first_name,balance FROM users ORDER BY user_id DESC LIMIT 30", all=True)
    text = "👥 <b>USERS (Latest 30)</b>\n━━━━━━━━━━━━━━━━━━\n"
    for u in users or []: text += f"\n<code>{u[0]}</code> | {u[1] or 'N/A'} | {fmt(u[2])}"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))

@dp.callback_query(F.data.startswith("udel_"))
async def u_del(call: CallbackQuery):
    uid = int(call.data[5:])
    db("DELETE FROM users WHERE user_id=?", (uid,))
    db("DELETE FROM orders WHERE user_id=?", (uid,))
    db("DELETE FROM balance_requests WHERE user_id=?", (uid,))
    await call.answer("🗑️ User deleted!", show_alert=True)

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
    except Exception: return await m.answer("❌ Number!")
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
    except Exception: return await m.answer("❌ Number!")
    d = await state.get_data()
    db("UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=?", (a, d['ub']))
    await state.clear()
    await m.answer(f"✅ -{fmt(a)} removed!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_u_balreq")
async def u_balreq(call: CallbackQuery):
    reqs = db("SELECT id,user_id,amount,status,reference FROM balance_requests ORDER BY id DESC LIMIT 15", all=True)
    if not reqs: return await call.message.edit_text("No requests.", reply_markup=bk("adm_users"))
    text = "💰 <b>BALANCE REQUESTS</b>\n"
    for r in reqs:
        text += f"\n#{r[0]} | <code>{r[1]}</code> | {fmt(r[2])} | {r[3]}"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))

@dp.callback_query(F.data == "adm_u_orders")
async def u_orders(call: CallbackQuery):
    o = db("SELECT id,user_id,product_name,plan_name,price_paid FROM orders ORDER BY id DESC LIMIT 15", all=True)
    if not o: return await call.message.edit_text("No orders.", reply_markup=bk("adm_users"))
    text = "🧾 <b>RECENT ORDERS</b>\n"
    for r in o: text += f"\n#{r[0]} | <code>{r[1]}</code> | {r[2]} - {r[3]} | {fmt(r[4])}"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))

@dp.callback_query(F.data == "adm_u_tickets")
async def u_tickets(call: CallbackQuery):
    t = db("SELECT id,user_id,message,created_at FROM tickets WHERE status='Open' ORDER BY id DESC LIMIT 10", all=True)
    if not t: return await call.message.edit_text("✅ No open tickets.", reply_markup=bk("adm_users"))
    text = "🎫 <b>OPEN TICKETS</b>\n"
    for r in t: text += f"\n#{r[0]} | <code>{r[1]}</code>\n{r[2][:150]}\n"
    await call.message.edit_text(text[:4000], reply_markup=bk("adm_users"))

# ============ PAYMENT SETTINGS ============
@dp.callback_query(F.data == "adm_pay")
async def adm_pay(call: CallbackQuery):
    mode = gs("payment_mode", "manual")
    m = "🤖 AUTO" if mode == "auto" else "✋ MANUAL"
    api_enabled = gs("auto_api_enabled", "0")
    api_st = "✅ ON" if api_enabled == "1" else "❌ OFF"
    upi = gs("upi_id") or "❌ Not set"
    qr = "✅ Set" if gs("static_qr_file_id") else "❌ Not set"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⚙️ Mode: {m}", callback_data="adm_pay_mode", style="primary")],
        [InlineKeyboardButton(text=f"🏦 UPI: {upi[:20]}", callback_data="adm_set_upi", style="success")],
        [InlineKeyboardButton(text="🏷️ Set Payee Name", callback_data="adm_set_payee", style="success")],
        [InlineKeyboardButton(text=f"🖼️ Static QR: {qr}", callback_data="adm_set_qr", style="success")],
        [InlineKeyboardButton(text=f"🔌 Auto API: {api_st}", callback_data="adm_api_menu", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("💳 <b>PAYMENT SETTINGS</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_pay_mode")
async def pay_mode(call: CallbackQuery):
    cur = gs("payment_mode", "manual")
    new = "auto" if cur == "manual" else "manual"
    ss("payment_mode", new)
    await call.answer(f"✅ {new.upper()}", show_alert=True)
    await adm_pay(call)

@dp.callback_query(F.data == "adm_set_upi")
async def set_upi(call: CallbackQuery, state: FSMContext):
    cur = gs("upi_id") or "Not set"
    await state.set_state(A.set_upi)
    await call.message.edit_text(f"Current: <code>{cur}</code>\n\nEnter UPI ID:", reply_markup=bk("adm_pay"))

@dp.message(A.set_upi)
async def set_upi_save(m: Message, state: FSMContext):
    ss("upi_id", m.text.strip())
    await state.clear()
    await m.answer("✅ UPI saved! Auto QR active now.", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_set_payee")
async def set_payee(call: CallbackQuery, state: FSMContext):
    cur = gs("payee_name", BRAND_NAME)
    await state.set_state(A.set_payee)
    await call.message.edit_text(f"Current: <b>{cur}</b>\n\nEnter Payee Name:", reply_markup=bk("adm_pay"))

@dp.message(A.set_payee)
async def set_payee_save(m: Message, state: FSMContext):
    ss("payee_name", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_set_qr")
async def set_qr(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_qr)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Remove QR", callback_data="adm_qr_remove", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_pay", style="danger")]])
    await call.message.edit_text("Send QR image as photo:", reply_markup=kb)

@dp.message(A.set_qr, F.photo)
async def set_qr_save(m: Message, state: FSMContext):
    ss("static_qr_file_id", m.photo[-1].file_id)
    await state.clear()
    await m.answer("✅ Static QR saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_qr_remove")
async def qr_remove(call: CallbackQuery):
    ss("static_qr_file_id", "")
    await call.answer("✅ Removed!", show_alert=True)
    await adm_pay(call)

@dp.callback_query(F.data == "adm_api_menu")
async def adm_api_menu(call: CallbackQuery):
    enabled = gs("auto_api_enabled", "0")
    st = "✅ ON" if enabled == "1" else "❌ OFF"
    url = gs("auto_api_url", "") or "(not set)"
    key = gs("auto_api_key", "") or "(not set)"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔛 Toggle: {st}", callback_data="adm_api_toggle", style="success" if enabled == "1" else "danger")],
        [InlineKeyboardButton(text="🔑 Set API Key", callback_data="adm_api_setkey", style="primary")],
        [InlineKeyboardButton(text="🌐 Set API URL", callback_data="adm_api_seturl", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_pay", style="danger")]])
    await call.message.edit_text(
        f"🔌 <b>AUTO PAYMENT API</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"Status: {st}\n🌐 <code>{url[:60]}</code>\n🔑 <code>{key[:40]}</code>\n\n"
        f"API should return JSON: {{\"status\":\"success\"}}", reply_markup=kb)

@dp.callback_query(F.data == "adm_api_toggle")
async def api_toggle(call: CallbackQuery):
    cur = gs("auto_api_enabled", "0")
    ss("auto_api_enabled", "0" if cur == "1" else "1")
    await call.answer("✅ Toggled!", show_alert=True)
    await adm_api_menu(call)

@dp.callback_query(F.data == "adm_api_setkey")
async def api_setkey(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_api_key)
    await call.message.edit_text("Enter API Key:", reply_markup=bk("adm_api_menu"))

@dp.message(A.set_api_key)
async def api_setkey_save(m: Message, state: FSMContext):
    ss("auto_api_key", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_api_seturl")
async def api_seturl(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.set_api_url)
    await call.message.edit_text("Enter API URL:", reply_markup=bk("adm_api_menu"))

@dp.message(A.set_api_url)
async def api_seturl_save(m: Message, state: FSMContext):
    ss("auto_api_url", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

# ============ MARKETING ============
@dp.callback_query(F.data == "adm_mkt")
async def adm_mkt(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ Coupons", callback_data="adm_cp", style="success")],
        [InlineKeyboardButton(text="🎁 Daily Gift", callback_data="adm_gift", style="success")],
        [InlineKeyboardButton(text="🤝 Refer Reward", callback_data="adm_ref", style="success")],
        [InlineKeyboardButton(text="👑 Reseller Settings", callback_data="adm_res", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("🎟️ <b>MARKETING</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_cp")
async def adm_cp(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create", callback_data="adm_cp_add", style="success")],
        [InlineKeyboardButton(text="📋 View", callback_data="adm_cp_view", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_mkt", style="danger")]])
    await call.message.edit_text("🎟️ <b>COUPONS</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_cp_add")
async def cp_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.cp_code)
    await call.message.edit_text("Enter Coupon Code:", reply_markup=bk("adm_cp"))

@dp.message(A.cp_code)
async def cp_code_save(m: Message, state: FSMContext):
    await state.update_data(cc=m.text.strip().upper())
    await state.set_state(A.cp_disc)
    await m.answer("Discount (₹):")

@dp.message(A.cp_disc)
async def cp_disc_save(m: Message, state: FSMContext):
    try: d = float(m.text)
    except Exception: return await m.answer("❌ Number!")
    await state.update_data(cd=d)
    await state.set_state(A.cp_max)
    await m.answer("Max Uses:")

@dp.message(A.cp_max)
async def cp_max_save(m: Message, state: FSMContext):
    try: mx = int(m.text)
    except Exception: return await m.answer("❌ Integer!")
    d = await state.get_data()
    db("INSERT OR REPLACE INTO coupons (code,discount,max_uses) VALUES (?,?,?)", (d['cc'], d['cd'], mx))
    await state.clear()
    await m.answer(f"✅ Coupon {d['cc']} created!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_cp_view")
async def cp_view(call: CallbackQuery):
    cps = db("SELECT code,discount,max_uses,used FROM coupons", all=True)
    text = "🎟️ <b>COUPONS</b>\n"
    for c in cps or []: text += f"\n<code>{c[0]}</code> | {fmt(c[1])} | {c[3]}/{c[2]}"
    if not cps: text += "\nNo coupons."
    await call.message.edit_text(text, reply_markup=bk("adm_cp"))

@dp.callback_query(F.data == "adm_gift")
async def gift_set(call: CallbackQuery, state: FSMContext):
    cur = gs("daily_gift_price", "0")
    await state.set_state(A.set_gift)
    await call.message.edit_text(f"Current: {fmt(cur)}\n\nDaily Gift (₹, 0 = disable):", reply_markup=bk("adm_mkt"))

@dp.message(A.set_gift)
async def gift_save(m: Message, state: FSMContext):
    ss("daily_gift_price", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_ref")
async def ref_set(call: CallbackQuery, state: FSMContext):
    cur = gs("refer_earn_amount", "0")
    await state.set_state(A.set_refer)
    await call.message.edit_text(f"Current: {fmt(cur)}\n\nRefer Reward (₹):", reply_markup=bk("adm_mkt"))

@dp.message(A.set_refer)
async def ref_save(m: Message, state: FSMContext):
    ss("refer_earn_amount", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_res")
async def adm_res(call: CallbackQuery):
    st = "✅ ON" if gs("reseller_system_status", "ON") == "ON" else "❌ OFF"
    fee = gs("reseller_setup_fee", "500")
    mn = gs("reseller_min_balance", "1000")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔛 System: {st}", callback_data="adm_res_tog", style="success" if "ON" in st else "danger")],
        [InlineKeyboardButton(text=f"💰 Fee: {fmt(fee)}", callback_data="adm_res_fee", style="primary")],
        [InlineKeyboardButton(text=f"💳 Min Bal: {fmt(mn)}", callback_data="adm_res_min", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_mkt", style="danger")]])
    await call.message.edit_text("👑 <b>RESELLER SETTINGS</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_res_tog")
async def res_tog(call: CallbackQuery):
    cur = gs("reseller_system_status", "ON")
    ss("reseller_system_status", "OFF" if cur == "ON" else "ON")
    await adm_res(call)

@dp.callback_query(F.data == "adm_res_fee")
async def res_fee(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.res_fee)
    await call.message.edit_text("Fee (₹):", reply_markup=bk("adm_res"))

@dp.message(A.res_fee)
async def res_fee_save(m: Message, state: FSMContext):
    ss("reseller_setup_fee", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_res_min")
async def res_min(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.res_min)
    await call.message.edit_text("Min Balance (₹):", reply_markup=bk("adm_res"))

@dp.message(A.res_min)
async def res_min_save(m: Message, state: FSMContext):
    ss("reseller_min_balance", m.text)
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

# ============ MENU DESIGNER ============
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
    if not b: return await call.answer("Not found!", show_alert=True)
    st = "🟢 Active" if b[3] else "🔴 Inactive"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Label", callback_data=f"mbe_{bid}_label", style="primary"),
         InlineKeyboardButton(text="😀 Emoji", callback_data=f"mbe_{bid}_emoji", style="primary")],
        [InlineKeyboardButton(text="⚙️ Action", callback_data=f"mbe_{bid}_action", style="primary")],
        [InlineKeyboardButton(text="👁️ Toggle", callback_data=f"mbt_{bid}", style="success")],
        [InlineKeyboardButton(text="🗑️ Delete", callback_data=f"mbd_{bid}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_menu_list", style="danger")]])
    await call.message.edit_text(f"Button: {b[2]} {b[1]}\nAction: {b[2]}\nStatus: {st}", reply_markup=kb)

@dp.callback_query(F.data.startswith("mbe_"))
async def menu_btn_edit(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_", 2)
    bid, field = int(parts[1]), parts[2]
    await state.update_data(mbe_id=bid, mbe_field=field)
    await state.set_state(A.menu_edit)
    await call.message.edit_text(f"New {field}:", reply_markup=bk("adm_menu_list"))

@dp.message(A.menu_edit)
async def menu_edit_save(m: Message, state: FSMContext):
    d = await state.get_data()
    db(f"UPDATE menu_buttons SET {d['mbe_field']}=? WHERE id=?", (m.text, d['mbe_id']))
    await state.clear()
    await m.answer("✅ Updated!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("mbt_"))
async def menu_toggle(call: CallbackQuery):
    bid = int(call.data[4:])
    c = db("SELECT is_active FROM menu_buttons WHERE id=?", (bid,), one=True)[0]
    db("UPDATE menu_buttons SET is_active=? WHERE id=?", (0 if c else 1, bid))
    await call.answer("✅ Toggled!", show_alert=True)
    await menu_list(call)

@dp.callback_query(F.data.startswith("mbd_"))
async def menu_del(call: CallbackQuery):
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
    await call.message.edit_text("👤 <b>PROFILE FIELDS</b>\nToggle visibility:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("pft_"))
async def pf_toggle(call: CallbackQuery):
    key = call.data[4:]
    c = db("SELECT is_visible FROM profile_fields WHERE field_key=?", (key,), one=True)[0]
    db("UPDATE profile_fields SET is_visible=? WHERE field_key=?", (0 if c else 1, key))
    await call.answer("✅ Toggled!", show_alert=True)
    await adm_pf(call)

# ============ CO-ADMINS ============
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
    except Exception: return await m.answer("❌ Numeric!")
    u = db("SELECT first_name FROM users WHERE user_id=?", (uid,), one=True)
    name = u[0] if u else "Unknown"
    db("INSERT OR IGNORE INTO co_admins (user_id,name) VALUES (?,?)", (uid, name))
    await state.clear()
    await m.answer("✅ Added!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_ca_rem")
async def ca_rem(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.coadmin_remove)
    await call.message.edit_text("User ID to remove:", reply_markup=bk("adm_coadmin"))

@dp.message(A.coadmin_remove)
async def ca_rem_save(m: Message, state: FSMContext):
    try: uid = int(m.text.strip())
    except Exception: return await m.answer("❌ Numeric!")
    db("DELETE FROM co_admins WHERE user_id=?", (uid,))
    await state.clear()
    await m.answer("✅ Removed!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_ca_list")
async def ca_list(call: CallbackQuery):
    cas = db("SELECT user_id,name FROM co_admins", all=True)
    text = "🤝 <b>CO-ADMINS</b>\n"
    for c in cas or []: text += f"\n<code>{c[0]}</code> | {c[1]}"
    if not cas: text += "\nNone."
    await call.message.edit_text(text, reply_markup=bk("adm_coadmin"))

# ============ SETTINGS ============
@dp.callback_query(F.data == "adm_settings")
async def adm_settings(call: CallbackQuery):
    logo = "✅ Set" if gs("admin_logo_file_id") else "❌ Not set"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🖼️ Logo: {logo}", callback_data="adm_set_logo", style="success")],
        [InlineKeyboardButton(text="📞 Set TG Support", callback_data="adm_set_tg", style="primary")],
        [InlineKeyboardButton(text="📱 Set WA Support", callback_data="adm_set_wa", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("⚙️ <b>SETTINGS</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_set_logo")
async def set_logo(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Remove Logo", callback_data="adm_logo_remove", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_settings", style="danger")]])
    await state.set_state(A.set_logo)
    await call.message.edit_text("Send Logo photo:", reply_markup=kb)

@dp.message(A.set_logo, F.photo)
async def set_logo_save(m: Message, state: FSMContext):
    ss("admin_logo_file_id", m.photo[-1].file_id)
    await state.clear()
    await m.answer("✅ Logo saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "adm_logo_remove")
async def logo_remove(call: CallbackQuery):
    ss("admin_logo_file_id", "")
    await call.answer("✅ Removed!", show_alert=True)
    await adm_settings(call)

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
    await call.message.edit_text("WhatsApp Support URL:", reply_markup=bk("adm_settings"))

@dp.message(A.set_wa)
async def set_wa_save(m: Message, state: FSMContext):
    ss("support_whatsapp", m.text.strip())
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

# ============ MESSAGE EDITOR ============
@dp.callback_query(F.data == "adm_msg")
async def adm_msg(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Welcome Message", callback_data="am_w", style="primary")],
        [InlineKeyboardButton(text="📂 Category Page", callback_data="am_c", style="primary")],
        [InlineKeyboardButton(text="📦 Panel Page", callback_data="am_p", style="primary")],
        [InlineKeyboardButton(text="⏱ Plan Page", callback_data="am_pl", style="primary")],
        [InlineKeyboardButton(text="🔑 Key Delivery", callback_data="am_k", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="adm_back", style="danger")]])
    await call.message.edit_text("📝 <b>MESSAGE EDITOR</b>", reply_markup=kb)

@dp.callback_query(F.data == "am_w")
async def am_w(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.msg_welcome)
    await call.message.edit_text("New Welcome Message:", reply_markup=bk("adm_msg"))

@dp.message(A.msg_welcome)
async def am_w_save(m: Message, state: FSMContext):
    ss("welcome_text", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "am_c")
async def am_c(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.msg_cat)
    await call.message.edit_text("New Category Page Message:", reply_markup=bk("adm_msg"))

@dp.message(A.msg_cat)
async def am_c_save(m: Message, state: FSMContext):
    ss("ui_category_msg", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "am_p")
async def am_p(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.msg_prod)
    await call.message.edit_text("New Panel Page Message:", reply_markup=bk("adm_msg"))

@dp.message(A.msg_prod)
async def am_p_save(m: Message, state: FSMContext):
    ss("ui_product_msg", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "am_pl")
async def am_pl(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.msg_plan)
    await call.message.edit_text("New Plan Page Message:", reply_markup=bk("adm_msg"))

@dp.message(A.msg_plan)
async def am_pl_save(m: Message, state: FSMContext):
    ss("ui_plan_msg", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

@dp.callback_query(F.data == "am_k")
async def am_k(call: CallbackQuery, state: FSMContext):
    await state.set_state(A.msg_key)
    await call.message.edit_text("New Key Delivery Message:", reply_markup=bk("adm_msg"))

@dp.message(A.msg_key)
async def am_k_save(m: Message, state: FSMContext):
    ss("ui_key_msg", m.text); await state.clear()
    await m.answer("✅ Saved!", reply_markup=admin_kb())

# ============ WEB SERVER ============
async def handle(request):
    return web.Response(text="Bot running")

async def start_web():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server on port {port}")

async def main():
    init_db()
    logger.info("DB initialized.")
    await start_web()
    logger.info("Bot starting...")
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