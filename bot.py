import asyncio, sqlite3, random, logging, time, aiohttp, hmac, hashlib, urllib.parse
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, Dice, BufferedInputFile)

# ═══════════════════════════════════════════════════════════════════
# 1. CONFIG
# ═══════════════════════════════════════════════════════════════════
BOT_TOKEN = "8754317781:AAF3LIu4C4UB059lSuTWUOopQJLXyY0TTQU"
BOT_USERNAME = "elitexconfig_bot"
ADMIN_ID = 8467166339
ADMIN_CONTACT = "@elitexconfig"
FAMPAY_API_KEY = "YOUR_FAMPAY_API_KEY"
FAMPAY_QR_URL = "https://fampay.api/qr.php"
FAMPAY_VERIFY_URL = "https://fampay.api/verify.php"
USDT_TO_INR = 90.0
VIP_DISCOUNT_PERCENTAGE = 10.0
VIP_PRICE_INR = 1000.0
WELCOME_STICKER_ID = "CAACAgIAAxkBAAEU-WZmH_..."
FIXED_CATEGORIES = ["ANDROID NON ROOT PANEL", "ANDROID ROOT PANEL", "PC PANEL"]

DEFAULT_EMOJIS = {
    'product_store': '6163205892834598715', 'profile': '5258011929993026890',
    'add_balance': '5985630530111020079', 'history': '6032594876506312598',
    'support': '5967280668885913944', 'back': '5877536313623711363',
    'upi': '5807750375033278838', 'reseller': '5886505193180239900',
    'tutorial': '6005986106703613755', 'telegram': '5875465628285931233',
    'whatsapp': '5954224165874569584', 'welcome': '5994502837327892086',
    'vip': '5206607081334906820',
    'category_android_non_root': '6161172706856282588',
    'category_android_root': '6161449831031118974',
    'category_pc': '5350554349074391003',
    'grid_id': '5474625972751837256', 'name': '5215399540814781035',
    'account_level': '6129584162992034014', 'regular_user': '5904630315946611415',
    'wallet': '6210859306602995217', 'current_balance': '5316711376876485361',
    'global_stats': '6161437856662298090', 'total_orders': '6160968017304888311',
    'total_spent': '5197503331215361533', 'joined_grid': '5433614043006903194',
    'info_icon': '6037421444789440735', 'check_icon': '6161241250239356403',
    'checkbox_icon': '6161437856662298090', 'shield_icon': '6086672466132865380',
    'money_icon': '5890848474563352982', 'redeem_icon': '5377624166436445368',
    'wallet_left': '6210859306602995217', 'wallet_right': '5305699699204837855',
    'point_down': '6161302621027049305',
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot_activity.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

def fmt_curr(amount: float) -> str: return f"₹{amount:,.2f}"

def fancy(text: str) -> str:
    bold_caps = {chr(ord("A") + i): chr(0x1D400 + i) for i in range(26)}
    small_caps = {"a":"ᴀ","b":"ʙ","c":"ᴄ","d":"ᴅ","e":"ᴇ","f":"ꜰ","g":"ɢ","h":"ʜ","i":"ɪ","j":"ᴊ",
        "k":"ᴋ","l":"ʟ","m":"ᴍ","n":"ɴ","o":"ᴏ","p":"ᴘ","q":"ǫ","r":"ʀ","s":"s","t":"ᴛ",
        "u":"ᴜ","v":"ᴠ","w":"ᴡ","x":"x","y":"ʏ","z":"ᴢ"}
    out, at_word_start = [], True
    for ch in str(text):
        if ch.isascii() and ch.isalpha():
            if at_word_start: out.append(bold_caps.get(ch.upper(), ch)); at_word_start = False
            else: out.append(small_caps.get(ch.lower(), ch))
        else:
            out.append(ch)
            if ch.isspace() or ch in "/\\|•": at_word_start = True
    return "".join(out)

def safe_float(val, default=0.0):
    if val is None or val == "": return default
    try: return float(val)
    except (ValueError, TypeError): return default

# ═══════════════════════════════════════════════════════════════════
# 2. DATABASE
# ═══════════════════════════════════════════════════════════════════
def db_query(query: str, params: tuple = (), fetchone=False, fetchall=False, commit=True) -> Any:
    conn = sqlite3.connect('Sandii.dp'); c = conn.cursor()
    try:
        c.execute(query, params)
        res = c.fetchone() if fetchone else (c.fetchall() if fetchall else None)
        if commit: conn.commit()
        return res
    except Exception as e:
        logger.error(f"DB Error: {e} | Query: {query}")
        if commit: conn.rollback()
        return None
    finally: conn.close()

def get_setting(key: str, default: str = "") -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return val[0] if val and val[0] else default

def set_setting(key: str, value: str) -> None:
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

def log_activity(user_id: int, action: str, details: str = "") -> None:
    try:
        db_query("INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    except Exception as e: logger.error(f"Failed to log activity: {e}")

def get_emoji(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    eid = stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))
    return f'<tg-emoji emoji-id="{eid}">✨</tg-emoji>' if eid else "✨"

def get_emoji_icon(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    return stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))

# ═══════════════════════════════════════════════════════════════════
# 3. UI TEXTS
# ═══════════════════════════════════════════════════════════════════
UI_TEXTS = {
    "start_menu": ("{welcome} <b>✦ 𝗦𝗔𝗡𝗗𝗜𝗜 𝗦𝗧𝗢𝗥𝗘 ✦</b>\n<i>Premium Digital Marketplace</i>\n━━━━━━━━━━━━━━━━━━\n\n"
        "{product_store} <b>𝗣𝗿𝗼𝗱𝘂𝗰𝘁 𝗦𝘁𝗼𝗿𝗲</b>\n╰ <i>Instant key delivery, 24/7</i>\n\n"
        "{profile} <b>𝗠𝘆 𝗣𝗿𝗼𝗳𝗶𝗹𝗲</b>\n╰ <i>Account, wallet and purchase history</i>\n\n"
        "{add_balance} <b>𝗔𝗱𝗱 𝗕𝗮𝗹𝗮𝗻𝗰𝗲</b>\n╰ <i>Secure and instant UPI deposits</i>\n\n"
        "{tutorial} <b>𝗧𝘂𝘁𝗼𝗿𝗶𝗮𝗹</b>\n╰ <i>Learn how to use this bot</i>\n\n"
        "{support} <b>𝗦𝘂𝗽𝗽𝗼𝗿𝘁</b>\n╰ <i>Fast help from our team</i>\n\n"
        "━━━━━━━━━━━━━━━━━━\n{point_down} <i>Select an option below</i>"),
    "vip_menu": ("{vip} <b>✦ 𝗩𝗜𝗣 𝗠𝗘𝗠𝗕𝗘𝗥𝗦𝗛𝗜𝗣 𝗖𝗟𝗨𝗕 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
        "<i>Unlock permanent discounts and exclusive perks.</i>\n\n💎 <b>𝗩𝗜𝗣 𝗕𝗲𝗻𝗲𝗳𝗶𝘁𝘀</b>\n"
        f"╰ Flat {VIP_DISCOUNT_PERCENTAGE:g}% off on ALL products <i>(stacks with Reseller)</i>\n"
        "╰ Priority support\n╰ Exclusive VIP-only giveaways\n\n"
        f"💳 <b>𝗩𝗜𝗣 𝗣𝗿𝗶𝗰𝗲</b> ┃ {fmt_curr(VIP_PRICE_INR)} <i>(Lifetime)</i>\n"
        "👤 <b>𝗬𝗼𝘂𝗿 𝗦𝘁𝗮𝘁𝘂𝘀</b> ┃ {vip_status}"),
    "add_balance_menu": ("{add_balance} <b>✦ 𝗔𝗗𝗗 𝗕𝗔𝗟𝗔𝗡𝗖𝗘 ✦</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        "{info_icon} <i>Choose your preferred payment method</i>\n\n"
        "{upi} <b>𝗨𝗣𝗜</b> ┃ <i>Fast Indian payments</i> {check_icon}\n\n"
        "━━━━━━━━━━━━━━━━━━\n{shield_icon} <i>All payments are verified securely</i>")
}

def get_ui_text(key: str, **kwargs) -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (f"ui_{key}",), fetchone=True)
    template = val[0] if val and val[0] else UI_TEXTS.get(key, "")
    emoji_map = {f'{{{s}}}': get_emoji(s) for s in DEFAULT_EMOJIS.keys()}
    for ph, tag in emoji_map.items(): template = template.replace(ph, tag)
    if kwargs:
        try: return template.format(**kwargs)
        except KeyError: pass
    return template

# ═══════════════════════════════════════════════════════════════════
# 4. DB INIT
# ═══════════════════════════════════════════════════════════════════
def init_db() -> None:
    conn = sqlite3.connect('Sandii.dp'); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, phone TEXT,
        first_name TEXT, username TEXT, balance REAL DEFAULT 0.0, account_type TEXT DEFAULT 'Regular',
        orders_count INTEGER DEFAULT 0, spent REAL DEFAULT 0.0, last_spin TEXT, joined_date TEXT,
        is_reseller INTEGER DEFAULT 0, reseller_since TEXT, total_saved REAL DEFAULT 0.0,
        is_banned INTEGER DEFAULT 0, warnings INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0, vip_since TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT, panel_name TEXT DEFAULT '', name TEXT, price_inr REAL,
        reseller_price REAL DEFAULT 0.0, stock INTEGER, apk_link TEXT,
        validity TEXT DEFAULT 'Lifetime', device_limit TEXT DEFAULT '1 Device',
        is_active INTEGER DEFAULT 1, video_file_id TEXT DEFAULT '', image_file_id TEXT DEFAULT '')''')
    c.execute('''CREATE TABLE IF NOT EXISTS product_keys (id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER, key_text TEXT, is_used INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, product_name TEXT, price_paid REAL, delivered_key TEXT, purchase_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, message TEXT, status TEXT DEFAULT 'Open', created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS coupons (code TEXT PRIMARY KEY, amount REAL, uses_left INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS redeemed (user_id INTEGER, code TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (order_id TEXT PRIMARY KEY, user_id INTEGER,
        amount_inr REAL, status TEXT, timestamp INTEGER, qr_url TEXT, upi_id TEXT, expires_at INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS crypto_txns (txid TEXT PRIMARY KEY, user_id INTEGER,
        amount_usdt REAL, timestamp INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS spin_rewards (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, action TEXT, details TEXT, timestamp TEXT)''')
    for mig in [
        "ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0", "ALTER TABLE users ADD COLUMN vip_since TEXT",
        "ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1", "ALTER TABLE tickets ADD COLUMN created_at TEXT",
        "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0", "ALTER TABLE users ADD COLUMN warnings INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN panel_name TEXT DEFAULT ''", "ALTER TABLE transactions ADD COLUMN qr_url TEXT",
        "ALTER TABLE transactions ADD COLUMN upi_id TEXT", "ALTER TABLE transactions ADD COLUMN expires_at INTEGER",
        "ALTER TABLE products ADD COLUMN video_file_id TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN image_file_id TEXT DEFAULT ''",
    ]:
        try: c.execute(mig)
        except sqlite3.OperationalError: pass
    defaults = [('reseller_system_status','ON'),('bot_status','ON'),('how_to_video','None'),
        ('fampay_api_key',FAMPAY_API_KEY),('fampay_upi_id',''),('binance_api',''),('binance_secret',''),
        ('binance_address',''),('vip_status','OFF'),('reseller_setup_fee','200.0'),
        ('reseller_min_balance','500.0'),('migration_done','0'),
        ('support_telegram','https://t.me/YourSupport'),('support_whatsapp','https://wa.me/YourNumber'),
        ('ui_start_menu',UI_TEXTS['start_menu']),('ui_vip_menu',UI_TEXTS['vip_menu']),
        ('ui_add_balance_menu',UI_TEXTS['add_balance_menu']),
        ('welcome_media_type','sticker'),('welcome_media_id',WELCOME_STICKER_ID)]
    for i, cat in enumerate(FIXED_CATEGORIES):
        defaults.append((f'category_media_type_{i}', 'video'))
        defaults.append((f'category_media_id_{i}', ''))
    for slot, eid in DEFAULT_EMOJIS.items(): defaults.append((f"emoji_{slot}", eid))
    for k, v in defaults: c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit(); conn.close()

def migrate_categories() -> None:
    # NOTE: Do NOT reset emojis/UI on every start — only INSERT OR IGNORE in init_db
    done = get_setting("migration_done", "0")
    if done == "1":
        # Still cleanup legacy keys (safe, idempotent)
        db_query("DELETE FROM settings WHERE key IN ('emoji_ludo_spin','emoji_download','ui_download_files','ui_lucky_dice_result','all_files_link','spin_status','daily_spin_limit','emoji_referral')")
        return
    logger.info("Running category migration...")
    mapping = {"android non root panel":"ANDROID NON ROOT PANEL",
               "android root panel":"ANDROID ROOT PANEL","pc panel":"PC PANEL"}
    for old, new in mapping.items():
        db_query("UPDATE products SET category = ? WHERE LOWER(category) = ?", (new, old))
    db_query("UPDATE products SET category = 'ANDROID NON ROOT PANEL' WHERE LOWER(category) NOT IN (?, ?, ?)",
             ("android non root panel", "android root panel", "pc panel"))
    set_setting("migration_done", "1")

# ═══════════════════════════════════════════════════════════════════
# 5. MEDIA HELPERS (NEW — welcome gif / category video / product media)
# ═══════════════════════════════════════════════════════════════════
async def send_media(chat_id: int, media_type: str, media_id: str, caption: str = "", reply_markup=None):
    if not media_id: return None
    try:
        if media_type == "sticker": return await bot.send_sticker(chat_id, media_id, reply_markup=reply_markup)
        if media_type == "video": return await bot.send_video(chat_id, media_id, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
        if media_type == "animation": return await bot.send_animation(chat_id, media_id, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
        if media_type == "photo": return await bot.send_photo(chat_id, media_id, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
    except Exception as e: logger.error(f"send_media error: {e}")
    return None

def media_from_message(m: Message) -> Tuple[str, str]:
    if m.sticker: return "sticker", m.sticker.file_id
    if m.animation: return "animation", m.animation.file_id
    if m.video: return "video", m.video.file_id
    if m.photo: return "photo", m.photo[-1].file_id
    if m.document and m.document.mime_type and m.document.mime_type.startswith("video/"):
        return "video", m.document.file_id
    if m.document and m.document.mime_type and m.document.mime_type.startswith("image/"):
        return "photo", m.document.file_id
    return "", ""

# ═══════════════════════════════════════════════════════════════════
# 6. MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════
async def hacker_loading(message: Message, text: str = "Decrypting Data") -> Message:
    msg = await message.answer(f"✦ <b>{text}</b>\n▱▱▱▱▱ 𝟬%")
    await asyncio.sleep(0.3); await msg.edit_text(f"✦ <b>{text}</b>\n▰▰▱▱▱ 𝟯𝟯%", parse_mode='HTML')
    await asyncio.sleep(0.3); await msg.edit_text(f"✦ <b>{text}</b>\n▰▰▰▰▱ 𝟲𝟲%", parse_mode='HTML')
    await asyncio.sleep(0.3); await msg.edit_text(f"✦ <b>{text}</b>\n▰▰▰▰▰ 𝟭𝟬𝟬%", parse_mode='HTML')
    return msg

class GlobalSecurityMiddleware(BaseMiddleware):
    def __init__(self): super().__init__(); self.last_action_times = {}
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id; now = time.time()
        if user_id in self.last_action_times and now - self.last_action_times[user_id] < 0.3: return
        self.last_action_times[user_id] = now
        if user_id != ADMIN_ID:
            info = db_query("SELECT is_banned FROM users WHERE user_id=?", (user_id,), fetchone=True)
            if info and info[0] == 1:
                msg = "🚫 <b>✦ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 ✦</b>\n━━━━━━━━━━━━━━━━━━\nYou have been banned."
                if isinstance(event, Message): await event.answer(msg)
                elif isinstance(event, CallbackQuery): await event.answer(msg, show_alert=True)
                return
            status = (db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True) or ['ON'])[0]
            if status == 'OFF':
                msg = "🛠 <b>✦ 𝗠𝗔𝗜𝗡𝗧𝗘𝗡𝗔𝗡𝗖𝗘 ✦</b>\nThe store is offline."
                if isinstance(event, Message): await event.answer(msg)
                elif isinstance(event, CallbackQuery): await event.answer("⚠️ Bot is OFF for Maintenance.", show_alert=True)
                return
        return await handler(event, data)

dp.message.middleware(GlobalSecurityMiddleware())
dp.callback_query.middleware(GlobalSecurityMiddleware())

# ═══════════════════════════════════════════════════════════════════
# 7. FSM
# ═══════════════════════════════════════════════════════════════════
class UserStates(StatesGroup):
    wait_for_ticket = State(); wait_for_redeem = State()
    wait_for_crypto_txid = State(); custom_amount_input = State()

class AdminStates(StatesGroup):
    add_prod_category = State(); add_prod_panel_name = State(); add_prod_name = State()
    add_prod_validity = State(); add_prod_device_limit = State(); add_prod_price = State()
    add_prod_reseller_price = State(); add_prod_apk = State(); add_prod_keys = State()
    edit_prod_field = State(); wait_for_new_value = State()
    wait_for_add_keys = State(); wait_for_delete_key = State()
    broadcast_msg = State(); add_coupon_code = State(); add_coupon_amount = State(); add_coupon_uses = State()
    wait_for_fampay_api = State(); wait_for_fampay_upi = State()
    wait_for_binance_api = State(); wait_for_binance_secret = State(); wait_for_binance_address = State()
    ticket_reply_msg = State(); reseller_manage_id = State(); manage_target_user = State()
    wait_for_add_money = State(); wait_for_minus_money = State(); wait_for_warning = State()
    wait_for_howto_video = State(); edit_ui_text = State(); edit_reseller_price = State()
    wait_for_reseller_setup_fee = State(); wait_for_reseller_min_balance = State(); confirm_ban = State()
    wait_for_support_telegram = State(); wait_for_support_whatsapp = State()
    wait_for_category_emoji = State(); wait_for_panel_emoji_id = State(); wait_for_emoji_slot = State()
    wait_for_welcome_media = State(); wait_for_category_media = State(); wait_for_product_media = State()

# ═══════════════════════════════════════════════════════════════════
# 8. KEYBOARDS
# ═══════════════════════════════════════════════════════════════════
def get_category_emoji(category: str) -> str:
    slot_map = {"ANDROID NON ROOT PANEL":"category_android_non_root",
        "ANDROID ROOT PANEL":"category_android_root","PC PANEL":"category_pc"}
    slot = slot_map.get(category)
    return get_emoji_icon(slot, DEFAULT_EMOJIS.get(slot, "")) if slot else ""

def get_panel_emoji(panel_name: str) -> str:
    stored = get_setting(f"panel_emoji_{panel_name}", "")
    return stored if stored and stored.isdigit() else get_emoji_icon("product_store")

def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 " + fancy("Verify Contact"), request_contact=True)]],
                               resize_keyboard=True, one_time_keyboard=True)

def main_menu_kb(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    sys_status = (db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True) or ['ON'])[0]
    vip_system = (db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True) or ['OFF'])[0]
    is_reseller = False
    if user_id:
        chk = db_query("SELECT is_reseller FROM users WHERE user_id=?", (user_id,), fetchone=True)
        if chk: is_reseller = bool(chk[0])
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Product Store"), callback_data="menu_shop",
        icon_custom_emoji_id=get_emoji_icon("product_store"), style="danger")])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text=fancy("My Profile"), callback_data="menu_profile",
            icon_custom_emoji_id=get_emoji_icon("profile"), style="primary"),
        InlineKeyboardButton(text=fancy("Add Balance"), callback_data="menu_add_balance",
            icon_custom_emoji_id=get_emoji_icon("add_balance"), style="primary")])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text=fancy("Tutorials"), callback_data="menu_how_to",
            icon_custom_emoji_id=get_emoji_icon("tutorial"), style="success"),
        InlineKeyboardButton(text=fancy("Support"), callback_data="menu_support",
            icon_custom_emoji_id=get_emoji_icon("support"), style="danger")])
    extras = []
    if sys_status == 'ON' or is_reseller:
        extras.append(InlineKeyboardButton(text=fancy("Reseller Panel"), callback_data="menu_reseller_dash",
            icon_custom_emoji_id=get_emoji_icon("reseller"), style="primary"))
    if vip_system == 'ON':
        extras.append(InlineKeyboardButton(text=fancy("VIP Club"), callback_data="menu_vip_dash",
            icon_custom_emoji_id=get_emoji_icon("vip"), style="danger"))
    if extras: kb.inline_keyboard.append(extras)
    return kb

def back_kb(callback: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=fancy("BACK"), callback_data=callback, icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])

def admin_kb() -> InlineKeyboardMarkup:
    status_val = (db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True) or ['ON'])[0]
    vip_val = (db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True) or ['OFF'])[0]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 " + fancy("Bot Statistics"), callback_data="admin_view_stats", style="primary")],
        [InlineKeyboardButton(text="👥 " + fancy("User Control Panel"), callback_data="admin_user_control_start", style="primary")],
        [InlineKeyboardButton(text="➕ " + fancy("Add Product"), callback_data="admin_add_prod", style="primary"),
         InlineKeyboardButton(text="📦 " + fancy("Manage Products"), callback_data="admin_manage_prods", style="primary")],
        [InlineKeyboardButton(text="👑 " + fancy("Reseller Mgmt"), callback_data="admin_reseller_menu", style="primary")],
        [InlineKeyboardButton(text="🎟 " + fancy("Create Coupon"), callback_data="admin_create_coupon", style="primary"),
         InlineKeyboardButton(text="📢 " + fancy("Broadcast"), callback_data="admin_broadcast_btn", style="primary")],
        [InlineKeyboardButton(text="🎫 " + fancy("View Tickets"), callback_data="admin_view_tickets", style="primary"),
         InlineKeyboardButton(text="📹 " + fancy("Tutorial Video"), callback_data="admin_set_video", style="primary")],
        [InlineKeyboardButton(text="🖼 " + fancy("Welcome Media"), callback_data="admin_set_welcome_media", style="success"),
         InlineKeyboardButton(text="🎬 " + fancy("Category Videos"), callback_data="admin_set_category_media", style="success")],
        [InlineKeyboardButton(text="🎨 " + fancy("Edit All Emojis"), callback_data="admin_edit_emojis", style="primary")],
        [InlineKeyboardButton(text="⚙️ " + fancy("FamPay Setup"), callback_data="admin_setup_fampay", style="primary"),
         InlineKeyboardButton(text="🪙 " + fancy("Binance Setup"), callback_data="admin_setup_binance", style="primary")],
        [InlineKeyboardButton(text="✏️ " + fancy("Edit UI Texts"), callback_data="admin_edit_ui_menu", style="primary"),
         InlineKeyboardButton(text="📝 " + fancy("Edit Reseller Price"), callback_data="admin_edit_reseller_price", style="primary")],
        [InlineKeyboardButton(text="💰 " + fancy("Reseller Fee"), callback_data="admin_set_reseller_fee", style="primary"),
         InlineKeyboardButton(text="💳 " + fancy("Min Balance"), callback_data="admin_set_reseller_min", style="primary")],
        [InlineKeyboardButton(text="📞 " + fancy("Set Support Links"), callback_data="admin_set_support_links", style="primary"),
         InlineKeyboardButton(text="🎨 " + fancy("Set Category Emojis"), callback_data="admin_set_category_emojis", style="primary")],
        [InlineKeyboardButton(text="🖼 " + fancy("Set Panel Emojis"), callback_data="admin_set_panel_emojis", style="primary")],
        [InlineKeyboardButton(text=f"{fancy('Bot Status')}: {status_val} {'🟢' if status_val=='ON' else '🔴'}",
            callback_data="admin_toggle_bot", style="success" if status_val=='ON' else "danger")],
        [InlineKeyboardButton(text=f"{fancy('VIP System')}: {vip_val} {'🟢' if vip_val=='ON' else '🔴'}",
            callback_data="admin_toggle_vip_sys", style="success" if vip_val=='ON' else "danger")]])

def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=fancy("Back to Admin"), callback_data="admin_panel_back",
        icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])

# ═══════════════════════════════════════════════════════════════════
# 9. NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════
async def send_advanced_notification(user_id, notif_type, amount, product=None, key=None, gateway="FamPay"):
    ui = db_query("SELECT first_name, phone, username, is_reseller, is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)
    if not ui: return
    name, phone = ui[0] or "Unknown", (ui[1] or "Not Provided")
    username = f"@{ui[2]}" if ui[2] else "None"
    tags = []
    if ui[3]: tags.append("👑 𝗥𝗲𝘀𝗲𝗹𝗹𝗲𝗿")
    if ui[4]: tags.append("🌟 𝗩𝗜𝗣")
    tag_str = " | ".join(tags) if tags else "👤 𝗥𝗲𝗴𝘂𝗹𝗮𝗿"
    time_now = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    if notif_type == "ORDER":
        title = "🛒 <b>✦ 𝗡𝗘𝗪 𝗢𝗥𝗗𝗘𝗥 ✦</b>"
        details = f"📦 <b>𝗣𝗿𝗼𝗱𝘂𝗰𝘁</b> ┃ {product}\n🔑 <b>𝗞𝗲𝘆</b> ┃ <code>{key}</code>\n💰 <b>𝗣𝗮𝗶𝗱</b> ┃ ₹{amount:.2f}\n📅 <b>𝗧𝗶𝗺𝗲</b> ┃ {time_now}"
    else:
        title = "💎 <b>✦ 𝗡𝗘𝗪 𝗗𝗘𝗣𝗢𝗦𝗜𝗧 ✦</b>"
        details = f"💵 <b>𝗔𝗺𝗼𝘂𝗻𝘁</b> ┃ ₹{amount:.2f}\n🧾 <b>𝗚𝗮𝘁𝗲𝘄𝗮𝘆</b> ┃ {gateway}\n🆔 <b>𝗥𝗲𝗳𝗲𝗿𝗲𝗻𝗰𝗲</b> ┃ <code>{product}</code>\n📅 <b>𝗧𝗶𝗺𝗲</b> ┃ {time_now}"
    msg = (f"{title}\n━━━━━━━━━━━━━━━━━━\n👤 <b>𝗡𝗮𝗺𝗲</b> ┃ {name}\n🆔 <b>𝗨𝘀𝗲𝗿 𝗜𝗗</b> ┃ <code>{user_id}</code>\n"
        f"📱 <b>𝗣𝗵𝗼𝗻𝗲</b> ┃ {phone}\n🔗 <b>𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲</b> ┃ {username}\n"
        f"🏷 <b>𝗦𝘁𝗮𝘁𝘂𝘀</b> ┃ {tag_str}\n━━━━━━━━━━━━━━━━━━\n{details}")
    try: await bot.send_message(ADMIN_ID, msg, parse_mode='HTML')
    except Exception as e: logger.error(f"admin notify failed: {e}")

# ═══════════════════════════════════════════════════════════════════
# 10. FAMPAY
# ═══════════════════════════════════════════════════════════════════
async def generate_fampay_qr(user_id: int, amount: float, upi_id: str = None) -> Dict[str, Any]:
    api_key = get_setting("fampay_api_key", FAMPAY_API_KEY)
    if not api_key or api_key == "YOUR_FAMPAY_API_KEY": return {"status":"error","message":"API key not configured"}
    if not upi_id:
        upi_id = get_setting("fampay_upi_id", "")
        if not upi_id: return {"status":"error","message":"UPI ID not configured"}
    url = f"{FAMPAY_QR_URL}?upi={upi_id}&amount={amount}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200: return await resp.json(content_type=None)
                return {"status":"error","message":f"HTTP {resp.status}"}
        except Exception as e: return {"status":"error","message":str(e)}

async def verify_fampay_payment(order_id: str) -> Dict[str, Any]:
    api_key = get_setting("fampay_api_key", FAMPAY_API_KEY)
    if not api_key or api_key == "YOUR_FAMPAY_API_KEY": return {"status":"error","message":"API key not configured"}
    url = f"{FAMPAY_VERIFY_URL}?order_id={order_id}&api_key={api_key}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200: return await resp.json(content_type=None)
                return {"status":"error","message":f"HTTP {resp.status}"}
        except Exception as e: return {"status":"error","message":str(e)}

async def run_payment_verification(user_id: int, order_id: str, reply_target: Any) -> None:
    txn = db_query("SELECT amount_inr, status, timestamp, qr_url, upi_id, expires_at FROM transactions WHERE order_id=?", (order_id,), fetchone=True)
    if not txn:
        err = "❌ Invalid Order ID!"
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(err, show_alert=True)
        else: await reply_target.answer(err)
        return
    if txn[5] and time.time() > txn[5]:
        db_query("UPDATE transactions SET status='expired' WHERE order_id=?", (order_id,))
        em = "⏳ <b>✦ 𝗤𝗥 𝗘𝗫𝗣𝗜𝗥𝗘𝗗 ✦</b>\n<i>Please generate a new QR.</i>"
        if isinstance(reply_target, CallbackQuery): await reply_target.message.edit_text(em, reply_markup=back_kb(), parse_mode='HTML')
        else: await reply_target.answer(em, reply_markup=back_kb())
        return
    if txn[1] == 'paid':
        msg = "✅ Already credited."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg); return
    elif txn[1] == 'expired':
        msg = "❌ Order expired."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg); return
    result = await verify_fampay_payment(order_id)
    if result.get("status") == "success":
        d = result.get("data", {}); amt = d.get("amount", txn[0]); utr = d.get("utr"); sname = d.get("sender_name")
        db_query("UPDATE transactions SET status='paid' WHERE order_id=?", (order_id,))
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, user_id))
        sm = (f"✅ <b>✦ 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗩𝗘𝗥𝗜𝗙𝗜𝗘𝗗 ✦</b>\n━━━━━━━━━━━━━━━━━━\n💎 <b>𝗖𝗿𝗲𝗱𝗶𝘁𝗲𝗱</b> ┃ {fmt_curr(amt)}\n"
              f"🧾 <b>𝗨𝗧𝗥</b> ┃ <code>{utr}</code>\n👤 <b>𝗦𝗲𝗻𝗱𝗲𝗿</b> ┃ {sname}")
        if isinstance(reply_target, CallbackQuery): await reply_target.message.edit_text(sm, reply_markup=back_kb(), parse_mode='HTML')
        else: await reply_target.answer(sm, reply_markup=back_kb())
        await send_advanced_notification(user_id, "DEPOSIT", amt, product=d.get("transaction_id"), gateway="FamPay")
        log_activity(user_id, "DEPOSIT_SUCCESS", f"Amt:{amt} Order:{order_id}")
    else:
        em = result.get("message", "Pending")
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(f"⏳ {em}", show_alert=True)
        else: await reply_target.answer(f"⏳ {em}")

async def auto_verify_task() -> None:
    while True:
        await asyncio.sleep(30)
        api_key = get_setting("fampay_api_key", "")
        if not api_key or api_key == "YOUR_FAMPAY_API_KEY": continue
        pend = db_query("SELECT order_id, user_id, amount_inr, timestamp, expires_at FROM transactions WHERE status='pending'", fetchall=True)
        if not pend: continue
        for txn in pend:
            oid, uid, amt, ts, exp = txn
            if exp and time.time() > exp:
                db_query("UPDATE transactions SET status='expired' WHERE order_id=?", (oid,))
                try: await bot.send_message(uid, f"⏳ <b>✦ 𝗤𝗥 𝗘𝗫𝗣𝗜𝗥𝗘𝗗 ✦</b>\nOrder <code>{oid}</code> timed out.", parse_mode='HTML')
                except: pass
                continue
            r = await verify_fampay_payment(oid)
            if r.get("status") == "success":
                d = r.get("data", {}); ar = d.get("amount", amt); utr = d.get("utr")
                db_query("UPDATE transactions SET status='paid' WHERE order_id=?", (oid,))
                db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (ar, uid))
                try: await bot.send_message(uid, f"✨ <b>✦ 𝗔𝗨𝗧𝗢-𝗩𝗘𝗥𝗜𝗙𝗜𝗘𝗗 ✦</b>\n💎 {fmt_curr(ar)}\nUTP: <code>{utr}</code>", parse_mode='HTML')
                except: pass
                await send_advanced_notification(uid, "DEPOSIT", ar, product=oid, gateway="FamPay Auto")
                log_activity(uid, "DEPOSIT_AUTO", f"Amt:{ar} Order:{oid}")

# ═══════════════════════════════════════════════════════════════════
# 11. START
# ═══════════════════════════════════════════════════════════════════
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    # Welcome media (gif/photo/video/sticker)
    w_type = get_setting("welcome_media_type", "sticker")
    w_id = get_setting("welcome_media_id", WELCOME_STICKER_ID)
    await send_media(message.chat.id, w_type, w_id)
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("v_"):
        oid = args[1].split("v_")[1]
        m = await message.answer("🔄 <b>✦ 𝗩𝗘𝗥𝗜𝗙𝗬𝗜𝗡𝗚 ✦</b>", parse_mode='HTML')
        await run_payment_verification(message.from_user.id, oid, m); return
    cur_uname = message.from_user.username or ""
    user = db_query("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    db_query("UPDATE users SET username=? WHERE user_id=?", (cur_uname, message.from_user.id))
    if not user or not user[0]:
        db_query("INSERT OR IGNORE INTO users (user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)",
            (message.from_user.id, message.from_user.first_name, cur_uname, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        log_activity(message.from_user.id, "ACCOUNT_CREATED")
    log_activity(message.from_user.id, "CMD_START")
    await send_main_menu(message)

async def send_main_menu(ctx: Any):
    text = get_ui_text("start_menu"); kb = main_menu_kb(ctx.from_user.id)
    if isinstance(ctx, Message): await ctx.answer(text, reply_markup=kb, parse_mode='HTML')
    else: await ctx.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear(); log_activity(call.from_user.id, "RETURN_MAIN_MENU"); await send_main_menu(call)

# ═══════════════════════════════════════════════════════════════════
# 12. ADD BALANCE (FIXED — includes Binance option)
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "menu_add_balance")
async def select_gateway_menu(call: CallbackQuery):
    log_activity(call.from_user.id, "VIEW_ADD_BALANCE")
    text = get_ui_text("add_balance_menu")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fancy("UPI PAY"), callback_data="gateway_inr",
            icon_custom_emoji_id=get_emoji_icon("upi"), style="primary"),
         InlineKeyboardButton(text=fancy("CRYPTO USDT"), callback_data="gateway_crypto",
            icon_custom_emoji_id=get_emoji_icon("money_icon"), style="success")],
        [InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
            icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "gateway_inr")
async def add_balance_inr(call: CallbackQuery):
    text = "💵 <b>✦ 𝗨𝗣𝗜 𝗗𝗘𝗣𝗢𝗦𝗜𝗧 ✦</b>\n<i>Select amount</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₹50", callback_data="pay_50", style="primary"), InlineKeyboardButton(text="₹100", callback_data="pay_100", style="primary")],
        [InlineKeyboardButton(text="₹200", callback_data="pay_200", style="primary"), InlineKeyboardButton(text="₹500", callback_data="pay_500", style="primary")],
        [InlineKeyboardButton(text="₹1000", callback_data="pay_1000", style="primary"), InlineKeyboardButton(text="₹2000", callback_data="pay_2000", style="primary")],
        [InlineKeyboardButton(text="✏️ " + fancy("Custom Amount"), callback_data="custom_deposit_keypad", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "custom_deposit_keypad")
async def show_custom_keypad(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.custom_amount_input); await state.update_data(amount_str="0")
    await show_keypad(call.message)

async def show_keypad(message: Message, amount_str: str = "0"):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="  1  ", callback_data="kp_1", style="primary"), InlineKeyboardButton(text="  2  ", callback_data="kp_2", style="primary"), InlineKeyboardButton(text="  3  ", callback_data="kp_3", style="primary")],
        [InlineKeyboardButton(text="  4  ", callback_data="kp_4", style="primary"), InlineKeyboardButton(text="  5  ", callback_data="kp_5", style="primary"), InlineKeyboardButton(text="  6  ", callback_data="kp_6", style="primary")],
        [InlineKeyboardButton(text="  7  ", callback_data="kp_7", style="primary"), InlineKeyboardButton(text="  8  ", callback_data="kp_8", style="primary"), InlineKeyboardButton(text="  9  ", callback_data="kp_9", style="primary")],
        [InlineKeyboardButton(text="⌫", callback_data="kp_backspace", style="danger"), InlineKeyboardButton(text="  0  ", callback_data="kp_0", style="primary"), InlineKeyboardButton(text="C", callback_data="kp_clear", style="danger")],
        [InlineKeyboardButton(text=f"✅ {fancy('Confirm')} • ₹{amount_str}", callback_data="kp_confirm", style="success")],
        [InlineKeyboardButton(text=fancy("Cancel"), callback_data="gateway_inr", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    text = f"💵 <b>✦ 𝗘𝗡𝗧𝗘𝗥 𝗔𝗠𝗢𝗨𝗡𝗧 ✦</b>\n💎 <b>Current</b> ┃ ₹{amount_str}"
    await message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("kp_"), UserStates.custom_amount_input)
async def keypad_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data(); amount_str = data.get("amount_str", "0"); action = call.data.split("_")[1]
    if action == "confirm":
        if amount_str == "0": return await call.answer("Amount cannot be zero.", show_alert=True)
        try:
            amount = float(amount_str)
            if amount < 10: return await call.answer("Min ₹10.", show_alert=True)
            await state.clear(); await call.message.edit_text("⏳ <b>✦ 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗜𝗡𝗚 𝗤𝗥 ✦</b>", parse_mode='HTML')
            await generate_fampay_order(call.from_user.id, amount, call.message)
        except ValueError: await call.answer("Invalid.", show_alert=True)
        return
    if action == "backspace": amount_str = amount_str[:-1] if len(amount_str) > 1 else "0"
    elif action == "clear": amount_str = "0"
    else:
        amount_str = action if amount_str == "0" else (amount_str + action)[:6]
    await state.update_data(amount_str=amount_str); await show_keypad(call.message, amount_str); await call.answer()

@dp.callback_query(F.data.startswith("pay_"))
async def process_fampay_payment_callback(call: CallbackQuery):
    inr = float(call.data.split("_")[1])
    await call.message.edit_text("⏳ <b>✦ 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗜𝗡𝗚 𝗤𝗥 ✦</b>", parse_mode='HTML')
    await generate_fampay_order(call.from_user.id, inr, call.message)

async def generate_fampay_order(user_id: int, inr_amount: float, message_obj: Message) -> None:
    api_key = get_setting("fampay_api_key", "")
    if not api_key or api_key == "YOUR_FAMPAY_API_KEY":
        return await message_obj.edit_text("⚠️ <b>Gateway Offline</b>\n<i>Contact support.</i>", reply_markup=back_kb("gateway_inr"), parse_mode='HTML')
    upi_id = get_setting("fampay_upi_id", "")
    if not upi_id:
        return await message_obj.edit_text("⚠️ <b>UPI not configured</b>", reply_markup=back_kb("gateway_inr"), parse_mode='HTML')
    current_time = int(time.time()); order_id = f"FAMPAY{user_id}{current_time}"
    result = await generate_fampay_qr(user_id, inr_amount, upi_id)
    if result.get("status") != "success":
        return await message_obj.edit_text(f"❌ Gateway Error: {result.get('message','Unknown')}", reply_markup=back_kb("gateway_inr"), parse_mode='HTML')
    d = result.get("data", {}); qr_url = d.get("qr_url"); order_id = d.get("order_id", order_id)
    upi_id = d.get("upi_id", upi_id); exp_str = d.get("expires_at_ist"); created = d.get("created_at_ist")
    try:
        exp_ts = int(datetime.strptime(exp_str, "%d-%m-%Y %H:%M:%S").timestamp()) if exp_str else int(time.time() + 300)
    except: exp_ts = int(time.time() + 300)
    db_query("INSERT INTO transactions (order_id, user_id, amount_inr, status, timestamp, qr_url, upi_id, expires_at) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)",
        (order_id, user_id, inr_amount, current_time, qr_url, upi_id, exp_ts))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 " + fancy("Verify Payment"), callback_data=f"verify_{order_id}", style="primary")],
        [InlineKeyboardButton(text="🖼 " + fancy("View QR"), url=qr_url, style="success")],
        [InlineKeyboardButton(text=fancy("Cancel"), callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    text = (f"🧾 <b>✦ 𝗦𝗘𝗖𝗨𝗥𝗘 𝗤𝗥 𝗥𝗘𝗔𝗗𝗬 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"💵 <b>Amount</b> ┃ {fmt_curr(inr_amount)}\n🆔 <b>Order</b> ┃ <code>{order_id}</code>\n"
        f"🏦 <b>UPI</b> ┃ <code>{upi_id}</code>\n⏳ <b>Expires</b> ┃ {exp_str}\n📅 <b>Created</b> ┃ {created}\n"
        f"━━━━━━━━━━━━━━━━━━\n📱 Send exact {fmt_curr(inr_amount)} & tap Verify.")
    log_activity(user_id, "GENERATE_INVOICE", f"Amt:{inr_amount} Order:{order_id}")
    await message_obj.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("verify_"))
async def manual_verify_callback(call: CallbackQuery):
    await run_payment_verification(call.from_user.id, call.data.split("_", 1)[1], call)

# ═══════════════════════════════════════════════════════════════════
# 13. BINANCE (FIXED — reachable now)
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "gateway_crypto")
async def add_balance_crypto(call: CallbackQuery, state: FSMContext):
    addr = db_query("SELECT value FROM settings WHERE key='binance_address'", fetchone=True)
    if not addr or not addr[0]:
        return await call.message.edit_text("⚠️ Crypto gateway offline.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    msg = (f"🪙 <b>— BINANCE USDT —</b>\n\n💵 1 USDT = ₹{USDT_TO_INR}\n⚠️ Network: <b>TRC20 / BEP20</b>\n\n"
        f"👇 Send to:\n<code>{addr[0]}</code>\n\n✅ Reply with TxID to claim.")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=fancy("Cancel"), callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode='HTML')
    await state.set_state(UserStates.wait_for_crypto_txid)

@dp.message(UserStates.wait_for_crypto_txid)
async def process_crypto_txid(m: Message, state: FSMContext):
    txid = m.text.strip(); user_id = m.from_user.id
    if len(txid) < 10: return await m.answer("❌ Invalid TxID.")
    if db_query("SELECT txid FROM crypto_txns WHERE txid=?", (txid,), fetchone=True):
        return await m.answer("⚠️ Already claimed!", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    api = db_query("SELECT value FROM settings WHERE key='binance_api'", fetchone=True)
    sec = db_query("SELECT value FROM settings WHERE key='binance_secret'", fetchone=True)
    if not api or not sec: return await m.answer("⚠️ Binance API missing.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    await m.answer("🔄 Verifying with Binance...", parse_mode='HTML')
    ts = int(time.time() * 1000); qs = f"timestamp={ts}"
    sig = hmac.new(sec[0].encode(), qs.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.binance.com/sapi/v1/capital/deposit/hisrec?{qs}&signature={sig}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers={'X-MBX-APIKEY': api[0]}) as resp:
                if resp.status == 200:
                    hist = await resp.json(content_type=None); found = False
                    for dep in hist:
                        if dep.get("txId") == txid and dep.get("status") == 1:
                            found = True; usdt = float(dep.get("amount")); inr = usdt * USDT_TO_INR
                            db_query("INSERT INTO crypto_txns (txid, user_id, amount_usdt, timestamp) VALUES (?, ?, ?, ?)", (txid, user_id, usdt, int(time.time())))
                            db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (inr, user_id))
                            await m.answer(f"🎉 SUCCESS!\n✅ {usdt} USDT\n💰 {fmt_curr(inr)} added.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
                            await send_advanced_notification(user_id, "DEPOSIT", inr, product=txid, gateway="Binance")
                            log_activity(user_id, "CRYPTO_DEPOSIT", f"TxID:{txid} Amt:{inr}")
                            await state.clear(); break
                    if not found: await m.answer("❌ TxID not found/pending.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
                else: await m.answer(f"⚠️ Binance HTTP {resp.status}.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
        except Exception as e: await m.answer(f"⚠️ Error: {e}", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')

# ═══════════════════════════════════════════════════════════════════
# 14. SHOP (FIXED — uses index-based callbacks, category video shown)
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "menu_shop")
async def view_shop_panels(call: CallbackQuery):
    log_activity(call.from_user.id, "VIEW_SHOP")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b>✦ 𝗦𝗘𝗟𝗘𝗖𝗧 𝗣𝗔𝗡𝗘𝗟 ✦</b>\n━━━━━━━━━━━━━━━━━━\n\n{get_emoji('point_down')} <b>Choose a panel</b>"
    for i, cat in enumerate(FIXED_CATEGORIES):
        emoji_id = get_category_emoji(cat)
        kb.inline_keyboard.append([InlineKeyboardButton(text=fancy(cat), callback_data=f"cat_{i}",
            icon_custom_emoji_id=emoji_id, style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
        icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("cat_"))
async def view_panel_names(call: CallbackQuery):
    try:
        idx = int(call.data.split("_", 1)[1]); category = FIXED_CATEGORIES[idx]
    except (ValueError, IndexError): return await call.answer("Invalid.", show_alert=True)
    # Show category video (above products)
    cmedia = get_setting(f"category_media_id_{idx}", "")
    if cmedia:
        mtype = get_setting(f"category_media_type_{idx}", "video")
        await send_media(call.message.chat.id, mtype, cmedia, caption=f"📺 {category}")
    panel_names = db_query("SELECT DISTINCT panel_name FROM products WHERE category=? AND is_active=1 AND panel_name != ''", (category,), fetchall=True)
    if not panel_names:
        prods = db_query("SELECT id, name, price_inr, stock, reseller_price, validity, device_limit FROM products WHERE category=? AND is_active=1", (category,), fetchall=True)
        if not prods: return await call.answer("❌ No products in this category.", show_alert=True)
        await show_products_for_panel(call, prods, category); return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b>✦ {fancy(category + ' PANELS')} ✦</b>\n━━━━━━━━━━━━━━━━━━\n\n{get_emoji('point_down')} <b>Choose a panel</b>"
    for p_i, pn in enumerate(panel_names):
        panel = pn[0]; emoji_id = get_panel_emoji(panel) or get_emoji_icon("product_store")
        kb.inline_keyboard.append([InlineKeyboardButton(text=fancy(panel), callback_data=f"pnl_{idx}_{p_i}",
            icon_custom_emoji_id=emoji_id, style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK"), callback_data="menu_shop",
        icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("pnl_"))
async def view_products_for_panel(call: CallbackQuery):
    try:
        parts = call.data.split("_")
        if len(parts) != 3: return await call.answer("Invalid.", show_alert=True)
        cat_idx, p_idx = int(parts[1]), int(parts[2]); category = FIXED_CATEGORIES[cat_idx]
    except (ValueError, IndexError): return await call.answer("Invalid.", show_alert=True)
    panel_names = db_query("SELECT DISTINCT panel_name FROM products WHERE category=? AND is_active=1 AND panel_name != ''", (category,), fetchall=True)
    if not panel_names or p_idx >= len(panel_names): return await call.answer("Panel not found.", show_alert=True)
    panel_name = panel_names[p_idx][0]
    prods = db_query("SELECT id, name, price_inr, stock, reseller_price, validity, device_limit FROM products WHERE category=? AND panel_name=? AND is_active=1", (category, panel_name), fetchall=True)
    if not prods: return await call.answer("No products.", show_alert=True)
    # Show category video above products too
    cmedia = get_setting(f"category_media_id_{cat_idx}", "")
    if cmedia:
        mtype = get_setting(f"category_media_type_{cat_idx}", "video")
        await send_media(call.message.chat.id, mtype, cmedia, caption=f"📺 {category} — {panel_name}")
    await show_products_for_panel(call, prods, f"{category} - {panel_name}")

async def show_products_for_panel(call: CallbackQuery, prods: List[Tuple], header: str):
    u = db_query("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_reseller = bool(u[0]) if u else False; is_vip = bool(u[1]) if u else False
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b>✦ {fancy(header + ' PACKAGES')} ✦</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for p in prods:
        pid, pname, npr, stock, rpr, val, dev = p
        npr = safe_float(npr); rpr = safe_float(rpr)
        base = rpr if is_reseller else npr
        disp = base - (base * (VIP_DISCOUNT_PERCENTAGE / 100)) if is_vip else base
        stock_s = "🟢 In Stock" if stock > 0 else "🔴 Out of Stock"
        text += f"{get_emoji('product_store')} <b>{fancy(str(pname))}</b>\n"
        if is_reseller or is_vip:
            text += f"💰 <b>Regular</b> ┃ <s>{fmt_curr(npr)}</s>\n👑 <b>Your Price</b> ┃ <b>{fmt_curr(disp)}</b>\n"
        else: text += f"💰 <b>Price</b> ┃ <b>{fmt_curr(npr)}</b>\n"
        text += f"📱 <b>Limit</b> ┃ {dev}\n📦 <b>Stock</b> ┃ {stock_s}\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        if stock > 0:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"{fancy('Buy')} {fancy(str(pname))} • {fmt_curr(disp)}",
                callback_data=f"buy_{pid}", icon_custom_emoji_id=get_emoji_icon("product_store"), style="success")])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ {fancy(str(pname))} • Sold Out",
                callback_data="ignore_stock_click", style="danger")])
    text += f"{get_emoji('point_down')} <b>Select a package</b>"
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK"), callback_data="menu_shop",
        icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "ignore_stock_click")
async def ignore_stock_click(call: CallbackQuery):
    await call.answer("⚠️ Out of Stock!", show_alert=True)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(call: CallbackQuery):
    pid = int(call.data.split("_")[1])
    prod = db_query("SELECT name, price_inr, stock, apk_link, validity, device_limit, category, reseller_price, panel_name, video_file_id, image_file_id FROM products WHERE id=?", (pid,), fetchone=True)
    u = db_query("SELECT balance, is_reseller, total_saved, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if not prod: return await call.answer("❌ Item not found.", show_alert=True)
    npr = safe_float(prod[1]); rpr = safe_float(prod[7])
    is_reseller = bool(u[1]); is_vip = bool(u[3])
    base = rpr if is_reseller else npr
    final = base - (base * (VIP_DISCOUNT_PERCENTAGE / 100)) if is_vip else base
    savings = npr - final
    if u[0] < final: return await call.answer(f"❌ Insufficient! Need {fmt_curr(final)}.", show_alert=True)
    # FIX: Removed broken reseller commission code that credited user_id=1
    db_query("UPDATE users SET balance=?, spent=spent+?, orders_count=orders_count+1, total_saved=total_saved+? WHERE user_id=?",
        (u[0] - final, final, savings, call.from_user.id))
    delivered_key = ""
    if prod[2] > 0:
        kd = db_query("SELECT id, key_text FROM product_keys WHERE product_id=? AND is_used=0 LIMIT 1", (pid,), fetchone=True)
        if kd:
            delivered_key = kd[1]; db_query("UPDATE product_keys SET is_used=1 WHERE id=?", (kd[0],))
            db_query("UPDATE products SET stock=stock-1 WHERE id=?", (pid,))
        else: delivered_key = "OUT_OF_STOCK_CONTACT_ADMIN_CODE_01"
    else: delivered_key = "OUT_OF_STOCK_CONTACT_ADMIN_CODE_02"
    full_name = f"{prod[6]} - {prod[8]} ({prod[0]})"
    db_query("INSERT INTO orders (user_id, product_name, price_paid, delivered_key, purchase_date) VALUES (?, ?, ?, ?, ?)",
        (call.from_user.id, full_name, final, delivered_key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_activity(call.from_user.id, "PURCHASE", f"Prod:{full_name} Paid:{final}")
    await send_advanced_notification(call.from_user.id, "ORDER", final, product=full_name, key=delivered_key)
    # Product media (video/image below purchase message)
    if prod[9]:  # video_file_id
        try: await bot.send_video(call.message.chat.id, prod[9], caption=f"📹 Tutorial for {prod[0]}")
        except Exception as e: logger.error(f"send video failed: {e}")
    elif prod[10]:  # image_file_id
        try: await bot.send_photo(call.message.chat.id, prod[10], caption=f"🖼 {prod[0]}")
        except Exception as e: logger.error(f"send photo failed: {e}")
    msg = (f"{get_emoji('check_icon')} <b>✦ 𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘 𝗦𝗨𝗖𝗖𝗘𝗦𝗦 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Panel</b> ┃ {prod[6]}\n📁 <b>Name</b> ┃ {prod[8]}\n⏱ <b>Package</b> ┃ {prod[0]}\n"
        f"💰 <b>Paid</b> ┃ {fmt_curr(final)}\n📱 <b>Device</b> ┃ {prod[5]}\n━━━━━━━━━━━━━━━━━━\n")
    if prod[3] and prod[3].startswith("http"): msg += f"📥 <b>APK</b> ┃ <a href='{prod[3]}'>Download</a>\n\n"
    if "OUT_OF_STOCK" in delivered_key:
        msg += f"⚠️ <b>INVENTORY ALERT</b>\nBalance deducted but vault empty. Contact: <code>{ADMIN_CONTACT}</code>"
    else:
        msg += f"🔑 <b>Your Key</b>\n<code>{delivered_key}</code>\n\n<i>Need help? Contact</i> <code>{ADMIN_CONTACT}</code>"
    await call.message.edit_text(msg, reply_markup=back_kb("menu_shop"), disable_web_page_preview=True, parse_mode='HTML')

# [Continue with sections 15-25 as in original — VIP, Reseller, Orders, Profile, Support, Admin Panel, Media handlers]

# ═══════════════════════════════════════════════════════════════════
# 15. VIP / RESELLER / ORDERS / PROFILE
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "menu_vip_dash")
async def vip_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip, vip_since FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_vip = bool(u[1])
    status_str = "🟢 𝗔𝗰𝘁𝗶𝘃𝗲" if is_vip else "🔴 𝗡𝗼𝘁 𝗦𝘂𝗯𝘀𝗰𝗿𝗶𝗯𝗲𝗱"
    text = get_ui_text("vip_menu", vip_status=status_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if is_vip: text += f"\n📅 <b>Since</b> ┃ {u[2]}"
    else:
        text += f"\n💳 <b>Balance</b> ┃ {fmt_curr(u[0])}\n"
        if u[0] >= VIP_PRICE_INR:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"✅ {fancy('Purchase VIP')} • {fmt_curr(VIP_PRICE_INR)}", callback_data="execute_vip_upgrade", style="success")])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ Need {fmt_curr(VIP_PRICE_INR)}", callback_data="ignore_stock_click", style="danger")])
            kb.inline_keyboard.append([InlineKeyboardButton(text="💳 " + fancy("Add Balance"), callback_data="menu_add_balance", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "execute_vip_upgrade")
async def execute_vip_upgrade(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]: return await call.answer("⚠️ Already VIP!", show_alert=True)
    if u[0] < VIP_PRICE_INR: return await call.answer("❌ Insufficient balance.", show_alert=True)
    db_query("UPDATE users SET balance=?, is_vip=1, vip_since=? WHERE user_id=?",
        (u[0] - VIP_PRICE_INR, datetime.now().strftime("%Y-%m-%d"), call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_VIP")
    try: await bot.send_message(ADMIN_ID, f"🌟 NEW VIP: <code>{call.from_user.id}</code>", parse_mode='HTML')
    except: pass
    await call.answer("🎉 VIP activated!", show_alert=True); await vip_dashboard(call)

@dp.callback_query(F.data == "menu_reseller_dash")
async def reseller_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_reseller, reseller_since, total_saved FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    sys = (db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True) or ['ON'])[0]
    fee = safe_float(get_setting("reseller_setup_fee", "200.0"))
    min_b = safe_float(get_setting("reseller_min_balance", "500.0"))
    if u[1]:
        text = f"{get_emoji('shield_icon')} <b>✦ 𝗥𝗘𝗦𝗘𝗟𝗟𝗘𝗥 𝗗𝗔𝗦𝗛 ✦</b>\n━━━━━━━━━━━━━━━━━━\n🟢 Active\n📅 Since: {u[2]}\n💰 Saved: {fmt_curr(u[3])}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
        await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML'); return
    if sys == "OFF": return await call.answer("⚠️ Registrations closed.", show_alert=True)
    text = f"👑 <b>✦ 𝗕𝗘𝗖𝗢𝗠𝗘 𝗥𝗘𝗦𝗘𝗟𝗟𝗘𝗥 ✦</b>\n━━━━━━━━━━━━━━━━━━\n📋 Min: <b>{fmt_curr(min_b)}</b>\nSetup Fee: <b>{fmt_curr(fee)}</b>\n💳 Balance: {fmt_curr(u[0])}"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if u[0] >= min_b:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"✅ {fancy('Pay')} {fmt_curr(fee)} {fancy('Now')}", callback_data="execute_reseller_upgrade", style="success")])
    else:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ Need {fmt_curr(min_b)}", callback_data="ignore_stock_click", style="danger")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="💳 " + fancy("Add Balance"), callback_data="menu_add_balance", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "execute_reseller_upgrade")
async def execute_reseller_upgrade(call: CallbackQuery):
    fee = safe_float(get_setting("reseller_setup_fee", "200.0"))
    min_b = safe_float(get_setting("reseller_min_balance", "500.0"))
    u = db_query("SELECT balance, is_reseller FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]: return await call.answer("⚠️ Already Reseller!", show_alert=True)
    if u[0] < min_b: return await call.answer(f"❌ Need {fmt_curr(min_b)}.", show_alert=True)
    db_query("UPDATE users SET balance=?, is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?",
        (u[0] - fee, datetime.now().strftime("%Y-%m-%d"), call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_RESELLER")
    try: await bot.send_message(ADMIN_ID, f"👑 NEW RESELLER: <code>{call.from_user.id}</code>", parse_mode='HTML')
    except: pass
    await call.answer("🎉 Welcome to Reseller tier!", show_alert=True); await reseller_dashboard(call)

@dp.callback_query(F.data == "menu_orders")
async def my_orders(call: CallbackQuery):
    orders = db_query("SELECT product_name, delivered_key, purchase_date, price_paid FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,), fetchall=True)
    if not orders: return await call.message.edit_text("📭 No purchases.", reply_markup=back_kb(), parse_mode='HTML')
    text = "🧾 <b>✦ 𝗥𝗘𝗖𝗘𝗡𝗧 𝗢𝗥𝗗𝗘𝗥𝗦 ✦</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for o in orders: text += f"📦 <b>{o[0]}</b> • {fmt_curr(o[3])}\n╰ 🔑 <code>{o[1]}</code>\n╰ 📅 <i>{o[2]}</i>\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "menu_profile")
async def show_profile(call: CallbackQuery):
    u = db_query("SELECT user_id, first_name, account_type, balance, orders_count, spent, joined_date, is_reseller, reseller_since, total_saved, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    tags = []
    if u[7]: tags.append(f"{get_emoji('reseller')} 𝗥𝗲𝘀𝗲𝗹𝗹𝗲𝗿")
    if u[10]: tags.append(f"{get_emoji('vip')} 𝗩𝗜𝗣")
    type_str = " | ".join(tags) if tags else f"{get_emoji('regular_user')} 𝗥𝗲𝗴𝘂𝗹𝗮𝗿"
    text = (f"{get_emoji('grid_id')} <b>✦ 𝗬𝗢𝗨𝗥 𝗣𝗥𝗢𝗙𝗜𝗟𝗘 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji('grid_id')} <b>ID</b> ┃ <code>{u[0]}</code>\n{get_emoji('name')} <b>Name</b> ┃ {u[1]}\n"
        f"{get_emoji('account_level')} <b>Type</b> ┃ {type_str}\n\n"
        f"{get_emoji('wallet_left')} <b>✦ 𝗪𝗔𝗟𝗟𝗘𝗧 ✦</b>\n{get_emoji('wallet_left')} <b>Balance</b> ┃ {fmt_curr(u[3])}\n\n"
        f"{get_emoji('global_stats')} <b>✦ 𝗦𝗧𝗔𝗧𝗦 ✦</b>\n{get_emoji('total_orders')} <b>Orders</b> ┃ {u[4]}\n"
        f"{get_emoji('total_spent')} <b>Spent</b> ┃ {fmt_curr(u[5])}\n")
    if u[7]: text += f"{get_emoji('shield_icon')} <b>Reseller Saved</b> ┃ {fmt_curr(u[9])}\n"
    text += f"\n{get_emoji('joined_grid')} <b>Joined</b> ┃ {u[6]}\n"
    orders = db_query("SELECT delivered_key FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,), fetchall=True)
    text += "━━━━━━━━━━━━━━━━━━\n🧾 <b>✦ 𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘 𝗛𝗜𝗦𝗧𝗢𝗥𝗬 ✦</b>\n\n"
    if orders:
        for o in orders: text += f"🔑 <code>{o[0]}</code>\n"
    else: text += "📭 No purchases yet.\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fancy("Redeem Promo Code"), callback_data="redeem_coupon",
            icon_custom_emoji_id=get_emoji_icon('redeem_icon'), style="success")],
        [InlineKeyboardButton(text=fancy("My Orders"), callback_data="menu_orders",
            icon_custom_emoji_id=get_emoji_icon('history'), style="primary")],
        [InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main",
            icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "redeem_coupon")
async def redeem_coupon_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🎟 <b>✦ 𝗥𝗘𝗗𝗘𝗘𝗠 𝗖𝗢𝗗𝗘 ✦</b>\n<i>Send code below</i>", reply_markup=back_kb("menu_profile"), parse_mode='HTML')
    await state.set_state(UserStates.wait_for_redeem)

@dp.message(UserStates.wait_for_redeem)
async def process_redeem(m: Message, state: FSMContext):
    code = m.text.strip().upper(); user_id = m.from_user.id
    if db_query("SELECT * FROM redeemed WHERE user_id=? AND code=?", (user_id, code), fetchone=True):
        await m.answer("❌ Already redeemed.", reply_markup=main_menu_kb(user_id), parse_mode='HTML'); await state.clear(); return
    coupon = db_query("SELECT amount, uses_left FROM coupons WHERE code=?", (code,), fetchone=True)
    if not coupon: await m.answer("❌ Invalid code.", reply_markup=main_menu_kb(user_id), parse_mode='HTML')
    elif coupon[1] <= 0: await m.answer("❌ Code fully claimed.", reply_markup=main_menu_kb(user_id), parse_mode='HTML')
    else:
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (coupon[0], user_id))
        db_query("UPDATE coupons SET uses_left = uses_left - 1 WHERE code=?", (code,))
        db_query("INSERT INTO redeemed (user_id, code) VALUES (?, ?)", (user_id, code))
        log_activity(user_id, "PROMO_REDEEMED", f"Code:{code} Amt:{coupon[0]}")
        await m.answer(f"🎉 <b>REDEEMED</b>\n💎 +{fmt_curr(coupon[0])}", reply_markup=main_menu_kb(user_id), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "menu_how_to")
async def tutorial_system(call: CallbackQuery):
    vl = db_query("SELECT value FROM settings WHERE key='how_to_video'", fetchone=True)
    video = vl[0] if vl and vl[0] != 'None' else None
    text = (f"{get_emoji('tutorial')} <b>✦ 𝗧𝗨𝗧𝗢𝗥𝗜𝗔𝗟𝗦 ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ Add funds via Add Balance\n2️⃣ Open Product Store\n3️⃣ Pick Panel & Package\n4️⃣ Receive key + APK instantly")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if video: kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Watch Video"), url=video, icon_custom_emoji_id=get_emoji_icon("tutorial"), style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "menu_support")
async def support_center(call: CallbackQuery):
    tg = get_setting("support_telegram", "https://t.me/YourSupport")
    wa = get_setting("support_whatsapp", "https://wa.me/YourNumber")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fancy("Telegram"), url=tg, icon_custom_emoji_id=get_emoji_icon("telegram"), style="primary")],
        [InlineKeyboardButton(text=fancy("WhatsApp"), url=wa, icon_custom_emoji_id=get_emoji_icon("whatsapp"), style="primary")],
        [InlineKeyboardButton(text="🎫 " + fancy("New Ticket"), callback_data="open_ticket", style="primary"),
         InlineKeyboardButton(text="📋 " + fancy("My Tickets"), callback_data="my_tickets", style="primary")],
        [InlineKeyboardButton(text=fancy("BACK"), callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(f"{get_emoji('telegram')}{get_emoji('whatsapp')} <b>✦ 𝗦𝗨𝗣𝗣𝗢𝗥𝗧 ✦</b>\n<i>Reach us via Telegram, WhatsApp or open a ticket.</i>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "my_tickets")
async def view_my_tickets(call: CallbackQuery):
    tickets = db_query("SELECT id, message, status, created_at FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 5", (call.from_user.id,), fetchall=True)
    if not tickets: return await call.message.edit_text("📋 No tickets.", reply_markup=back_kb("menu_support"), parse_mode='HTML')
    text = "📋 <b>✦ 𝗬𝗢𝗨𝗥 𝗧𝗜𝗖𝗞𝗘𝗧𝗦 ✦</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for t in tickets:
        icon = "🟢" if t[2] == 'Open' else "🔴"
        text += f"🎫 <b>#{t[0]}</b> ┃ {icon} {t[2]}\n╰ 📅 {t[3]}\n╰ 📝 {t[1][:80]}...\n\n"
    await call.message.edit_text(text, reply_markup=back_kb("menu_support"), parse_mode='HTML')

@dp.callback_query(F.data == "open_ticket")
async def open_ticket_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📝 <b>✦ 𝗡𝗘𝗪 𝗧𝗜𝗖𝗞𝗘𝗧 ✦</b>\n<i>Describe issue below</i>", reply_markup=back_kb("menu_support"), parse_mode='HTML')
    await state.set_state(UserStates.wait_for_ticket)

@dp.message(UserStates.wait_for_ticket)
async def process_ticket(m: Message, state: FSMContext):
    db_query("INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)",
        (m.from_user.id, m.text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await m.answer("✅ Ticket submitted.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    try: await bot.send_message(ADMIN_ID, f"🚨 <b>NEW TICKET</b>\nFrom: <code>{m.from_user.id}</code>\n{m.text}", parse_mode='HTML')
    except: pass
    log_activity(m.from_user.id, "OPENED_TICKET"); await state.clear()

# ═══════════════════════════════════════════════════════════════════
# 16. ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════
@dp.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("⚙️ <b>✦ 𝗔𝗗𝗠𝗜𝗡 𝗧𝗘𝗥𝗠𝗜𝗡𝗔𝗟 ✦</b>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_panel_back")
async def back_to_admin(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("⚙️ <b>✦ 𝗔𝗗𝗠𝗜𝗡 𝗧𝗘𝗥𝗠𝗜𝗡𝗔𝗟 ✦</b>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_vip_sys")
async def toggle_vip_sys(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    cur = (db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True) or ['OFF'])[0]
    set_setting("vip_status", 'ON' if cur == 'OFF' else 'OFF')
    await call.message.edit_reply_markup(reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_toggle_bot")
async def toggle_bot(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    cur = (db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True) or ['ON'])[0]
    set_setting("bot_status", 'OFF' if cur == 'ON' else 'ON')
    await call.message.edit_reply_markup(reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_view_stats")
async def admin_dashboard_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    tu = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    tr = db_query("SELECT COUNT(*) FROM users WHERE is_reseller=1", fetchone=True)[0]
    tv = db_query("SELECT COUNT(*) FROM users WHERE is_vip=1", fetchone=True)[0]
    tp = db_query("SELECT COUNT(*) FROM products", fetchone=True)[0]
    tk = db_query("SELECT COUNT(*) FROM product_keys WHERE is_used=0", fetchone=True)[0]
    rev = db_query("SELECT SUM(spent) FROM users", fetchone=True)[0] or 0.0
    msg = f"📊 <b>✦ 𝗔𝗡𝗔𝗟𝗬𝗧𝗜𝗖𝗦 ✦</b>\n━━━━━━━━━━━━━━━━━━\n👥 Users: {tu}\n👑 Resellers: {tr}\n🌟 VIP: {tv}\n📦 Products: {tp}\n🔑 Unused Keys: {tk}\n💰 Revenue: {fmt_curr(rev)}"
    await call.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode='HTML')

# ═══════════════════════════════════════════════════════════════════
# 17. USER CONTROL
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "admin_user_control_start")
async def admin_user_control_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Download User List", callback_data="admin_download_userlist", style="success")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text("💻 Enter User ID or @Username to manage:", reply_markup=kb, parse_mode='HTML')
    await state.set_state(AdminStates.manage_target_user)

@dp.callback_query(F.data == "admin_download_userlist")
async def admin_download_userlist(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    users = db_query("SELECT username, user_id, phone, balance, orders_count, is_vip, is_reseller FROM users", fetchall=True)
    if not users: return await call.answer("❌ No users.", show_alert=True)
    content = "FULL DATABASE DUMP\n" + "="*100 + "\n"
    for u in users:
        content += f"UID: {u[1]} | UNAME: {u[0] or 'N/A'} | PHONE: {u[2] or 'N/A'} | BAL: ₹{u[3]:.2f} | BUY: {u[4]} | VIP: {'Y' if u[5] else 'N'} | RES: {'Y' if u[6] else 'N'}\n"
    doc = BufferedInputFile(content.encode('utf-8'), filename=f"DB_{datetime.now().strftime('%Y%m%d')}.txt")
    await call.message.answer_document(document=doc, caption="📋 Database export", parse_mode='HTML'); await call.answer()

@dp.message(AdminStates.manage_target_user)
async def process_user_lookup(m: Message, state: FSMContext):
    target = m.text.strip()
    if target.startswith('@'): target = target[1:]
    lm = await hacker_loading(m, "Querying DB")
    u = db_query("SELECT user_id, first_name, username, balance, is_reseller, orders_count, spent, joined_date, is_banned, warnings, is_vip FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if not u: return await lm.edit_text("❌ Not found.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name, u_user, bal, is_res, orders, spent, joined, banned, warns, is_vip = u
    await state.update_data(target_u_id=u_id)
    status = "🔴 BANNED" if banned else "🟢 ACTIVE"
    tags = []
    if is_res: tags.append("👑 Reseller")
    if is_vip: tags.append("🌟 VIP")
    ts = " | ".join(tags) if tags else "👤 Regular"
    text = (f"🛡 <b>USER CONTROL</b>\n━━━━━━━━━━━━━━━━━━\n📛 {u_name} (@{u_user})\n🆔 <code>{u_id}</code>\n"
        f"📊 {status}\n🔰 {ts}\n⚠️ Warnings: {warns}\n━━━━━━━━━━━━━━━━━━\n💰 {fmt_curr(bal)}\n📦 Orders: {orders} | 💸 {fmt_curr(spent)}\n📅 {joined}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add", callback_data=f"usrctrl_add_{u_id}", style="success"),
         InlineKeyboardButton(text="➖ Minus", callback_data=f"usrctrl_min_{u_id}", style="danger")],
        [InlineKeyboardButton(text="Unban ✅" if banned else "Ban 🚫", callback_data=f"usrctrl_ban_{u_id}", style="danger"),
         InlineKeyboardButton(text="Warn ⚠️", callback_data=f"usrctrl_warn_{u_id}", style="danger")],
        [InlineKeyboardButton(text="Remove VIP 🚫" if is_vip else "Give VIP 🌟", callback_data=f"usrctrl_vip_{u_id}", style="success")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await lm.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("usrctrl_"))
async def handle_user_actions(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split("_")
    action = parts[1]; u_id = int(parts[2])
    await state.update_data(target_u_id=u_id)
    if action == "ban":
        cur = db_query("SELECT is_banned FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if cur == 0:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Yes, Ban", callback_data=f"confirm_ban_{u_id}", style="danger"),
                 InlineKeyboardButton(text="❌ Cancel", callback_data="admin_user_control_start", style="danger")]])
            await call.message.edit_text(f"⚠️ Ban user <code>{u_id}</code>?", reply_markup=kb, parse_mode='HTML')
            await state.set_state(AdminStates.confirm_ban)
        else:
            db_query("UPDATE users SET is_banned=0 WHERE user_id=?", (u_id,))
            await call.answer("✅ Unbanned!", show_alert=True)
            m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
    elif action == "vip":
        cur = db_query("SELECT is_vip FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if cur == 1: db_query("UPDATE users SET is_vip=0 WHERE user_id=?", (u_id,)); await call.answer("✅ VIP removed!", show_alert=True)
        else: db_query("UPDATE users SET is_vip=1, vip_since=? WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d"), u_id)); await call.answer("✅ VIP granted!", show_alert=True)
        m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
    elif action == "add":
        await call.message.edit_text("💰 Amount to ADD:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_money)
    elif action == "min":
        await call.message.edit_text("💸 Amount to DEDUCT:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_minus_money)
    elif action == "warn":
        await call.message.edit_text("⚠️ Warning message:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_warning)

@dp.callback_query(F.data.startswith("confirm_ban_"))
async def confirm_ban(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    u_id = int(call.data.split("_")[2])
    db_query("UPDATE users SET is_banned=1 WHERE user_id=?", (u_id,))
    await call.answer("🔴 Banned!", show_alert=True); await state.clear()
    m = call.message; m.text = str(u_id); await process_user_lookup(m, state)

@dp.message(AdminStates.wait_for_add_money)
async def exec_add_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text); data = await state.get_data(); u_id = data['target_u_id']
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, u_id))
        await m.answer(f"✅ Added {fmt_curr(amt)}", reply_markup=admin_kb(), parse_mode='HTML')
        try: await bot.send_message(u_id, f"💰 Admin added {fmt_curr(amt)} to your wallet.", parse_mode='HTML')
        except: pass
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number.")

@dp.message(AdminStates.wait_for_minus_money)
async def exec_minus_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text); data = await state.get_data(); u_id = data['target_u_id']
        db_query("UPDATE users SET balance = balance - ? WHERE user_id=?", (amt, u_id))
        await m.answer(f"✅ Deducted {fmt_curr(amt)}", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()
    except ValueError: await m.answer("❌ Invalid number.")

@dp.message(AdminStates.wait_for_warning)
async def exec_warn_user(m: Message, state: FSMContext):
    data = await state.get_data(); u_id = data['target_u_id']
    db_query("UPDATE users SET warnings = warnings + 1 WHERE user_id=?", (u_id,))
    await m.answer(f"✅ Warning sent to {u_id}", reply_markup=admin_kb(), parse_mode='HTML')
    try: await bot.send_message(u_id, f"⚠️ <b>WARNING:</b>\n\n{m.text}", parse_mode='HTML')
    except: pass
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# 18. ADMIN: WELCOME MEDIA (NEW)
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "admin_set_welcome_media")
async def admin_set_welcome_media(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    ct = get_setting("welcome_media_type", "sticker")
    ci = get_setting("welcome_media_id", "Not set")
    await call.message.edit_text(
        f"🖼 <b>Welcome Media Setup</b>\n\nCurrent: <b>{ct}</b>\nID: <code>{ci[:25]}...</code>\n\n"
        f"Send a <b>GIF / Sticker / Photo / Video</b> — will be used on /start.\nType /skip to keep current.",
        reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_welcome_media)

@dp.message(AdminStates.wait_for_welcome_media)
async def save_welcome_media(m: Message, state: FSMContext):
    if m.text and m.text.strip() == '/skip':
        await state.clear(); return await m.answer("✅ Unchanged.", reply_markup=admin_kb(), parse_mode='HTML')
    mt, fid = media_from_message(m)
    if not fid: return await m.answer("❌ Unsupported. Send GIF/sticker/photo/video.", reply_markup=admin_back_kb(), parse_mode='HTML')
    set_setting("welcome_media_type", mt); set_setting("welcome_media_id", fid)
    await m.answer(f"✅ Welcome media saved as <b>{mt}</b>!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# 19. ADMIN: CATEGORY VIDEO (NEW)
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "admin_set_category_media")
async def admin_set_category_media(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i, cat in enumerate(FIXED_CATEGORIES):
        cur = get_setting(f"category_media_id_{i}", "")
        status = "✅" if cur else "⬜"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{status} {cat}", callback_data=f"set_cat_media_{i}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎬 <b>Category Videos</b>\nShown above products in each category:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("set_cat_media_"))
async def admin_set_category_media_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    idx = int(call.data.split("_")[3])
    await state.update_data(cat_media_idx=idx)
    cat = FIXED_CATEGORIES[idx]
    cur = get_setting(f"category_media_id_{idx}", "Not set")
    await call.message.edit_text(
        f"🎬 <b>{cat}</b>\nCurrent ID: <code>{cur[:25]}</code>\n\n"
        f"Send a <b>Video / GIF / Photo</b> for this category.\nType <code>clear</code> to remove.",
        reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_category_media)

@dp.message(AdminStates.wait_for_category_media)
async def save_category_media(m: Message, state: FSMContext):
    data = await state.get_data(); idx = data['cat_media_idx']
    if m.text and m.text.strip().lower() == 'clear':
        set_setting(f"category_media_id_{idx}", "")
        await state.clear()
        return await m.answer("✅ Removed.", reply_markup=admin_kb(), parse_mode='HTML')
    mt, fid = media_from_message(m)
    if not fid: return await m.answer("❌ Unsupported. Send video/GIF/photo.", reply_markup=admin_back_kb(), parse_mode='HTML')
    set_setting(f"category_media_type_{idx}", mt)
    set_setting(f"category_media_id_{idx}", fid)
    await m.answer(f"✅ Category media saved as <b>{mt}</b>!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# 20. ADMIN: PRODUCT MEDIA (NEW)
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("set_prod_media_"))
async def admin_set_product_media(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    pid = int(call.data.split("_")[3])
    await state.update_data(prod_media_id=pid)
    prod = db_query("SELECT name, video_file_id, image_file_id FROM products WHERE id=?", (pid,), fetchone=True)
    if not prod: return await call.answer("❌ Product not found.", show_alert=True)
    await call.message.edit_text(
        f"🎬 <b>{prod[0]}</b>\n\nCurrent video: {'✅' if prod[1] else '❌'}\nCurrent image: {'✅' if prod[2] else '❌'}\n\n"
        f"Send a <b>Video</b> or <b>Photo</b> for this product.\nType <code>clear</code> to remove.",
        reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_product_media)

@dp.message(AdminStates.wait_for_product_media)
async def save_product_media(m: Message, state: FSMContext):
    data = await state.get_data(); pid = data['prod_media_id']
    if m.text and m.text.strip().lower() == 'clear':
        db_query("UPDATE products SET video_file_id='', image_file_id='' WHERE id=?", (pid,))
        await state.clear()
        return await m.answer("✅ Removed.", reply_markup=admin_kb(), parse_mode='HTML')
    mt, fid = media_from_message(m)
    if not fid: return await m.answer("❌ Unsupported.", reply_markup=admin_back_kb(), parse_mode='HTML')
    if mt == "video": db_query("UPDATE products SET video_file_id=? WHERE id=?", (fid, pid))
    elif mt in ("photo", "animation"): db_query("UPDATE products SET image_file_id=? WHERE id=?", (fid, pid))
    else: return await m.answer("❌ Send video or photo only.", reply_markup=admin_back_kb(), parse_mode='HTML')
    await m.answer(f"✅ Product media saved as <b>{mt}</b>!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ═══════════════════════════════════════════════════════════════════
# 21. ADMIN: PRODUCT CRUD (FIXED toggle_p_ bug)
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "admin_add_prod")
async def add_prod_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in FIXED_CATEGORIES:
        kb.inline_keyboard.append([InlineKeyboardButton(text=cat, callback_data=f"addprod_cat_{cat}", icon_custom_emoji_id=get_category_emoji(cat), style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Cancel"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("<b>Step 1:</b> Choose Category:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("addprod_cat_"))
async def add_prod_category_selected(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.update_data(cat=call.data.split("addprod_cat_", 1)[1])
    await call.message.edit_text("<b>Step 2:</b> Enter PANEL NAME:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_panel_name)

@dp.message(AdminStates.add_prod_panel_name)
async def add_prod_panel_name(m: Message, state: FSMContext):
    await state.update_data(panel_name=m.text)
    await m.answer("<b>Step 3:</b> Enter PACKAGE DURATION NAME:", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_name)

@dp.message(AdminStates.add_prod_name)
async def add_prod_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("⏳ Enter validity:", parse_mode='HTML'); await state.set_state(AdminStates.add_prod_validity)

@dp.message(AdminStates.add_prod_validity)
async def add_prod_validity(m: Message, state: FSMContext):
    await state.update_data(validity=m.text)
    await m.answer("📱 Enter device limit:", parse_mode='HTML'); await state.set_state(AdminStates.add_prod_device_limit)

@dp.message(AdminStates.add_prod_device_limit)
async def add_prod_device_limit(m: Message, state: FSMContext):
    await state.update_data(device_limit=m.text)
    await m.answer("💰 Enter USER Price (₹):", parse_mode='HTML'); await state.set_state(AdminStates.add_prod_price)

@dp.message(AdminStates.add_prod_price)
async def add_prod_price(m: Message, state: FSMContext):
    try:
        await state.update_data(price=float(m.text))
        await m.answer("👑 Enter RESELLER Price (₹):", parse_mode='HTML'); await state.set_state(AdminStates.add_prod_reseller_price)
    except ValueError: await m.answer("❌ Invalid number.")

@dp.message(AdminStates.add_prod_reseller_price)
async def add_prod_reseller_price(m: Message, state: FSMContext):
    try:
        await state.update_data(reseller_price=float(m.text))
        await m.answer("🔗 APK/Payload Link (or 'none'):", parse_mode='HTML'); await state.set_state(AdminStates.add_prod_apk)
    except ValueError: await m.answer("❌ Invalid number.")

@dp.message(AdminStates.add_prod_apk)
async def add_prod_apk(m: Message, state: FSMContext):
    await state.update_data(apk="" if m.text.lower() == 'none' else m.text)
    await m.answer("📥 <b>Vault Phase</b>\nPaste keys (1 per line):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_keys)

@dp.message(AdminStates.add_prod_keys)
async def add_prod_keys(m: Message, state: FSMContext):
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    data = await state.get_data()
    conn = sqlite3.connect('Sandii.dp'); c = conn.cursor()
    c.execute("INSERT INTO products (category, panel_name, name, price_inr, reseller_price, stock, apk_link, validity, device_limit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data['cat'], data['panel_name'], data['name'], data['price'], data['reseller_price'], len(keys), data['apk'], data['validity'], data['device_limit']))
    pid = c.lastrowid
    for k in keys: c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (pid, k))
    conn.commit(); conn.close()
    await m.answer(f"✅ Deployed!\n📦 {data['cat']} → {data['panel_name']} → {data['name']}\n🔑 {len(keys)} keys | 💰 {fmt_curr(data['price'])}",
        reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_manage_prods")
async def admin_manage_prods(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    prods = db_query("SELECT id, name, category, panel_name, stock, is_active FROM products ORDER BY category, panel_name", fetchall=True)
    if not prods: return await call.message.edit_text("📦 Empty.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in prods:
        dot = "🟢" if p[5] else "🔴"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{dot} [{p[2]}] {p[3] or ''} - {p[1]} (Stock: {p[4]})", callback_data=f"admin_view_p_{p[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("📦 Select node:", reply_markup=kb, parse_mode='HTML')

async def _render_product_detail(call: CallbackQuery, p_id: int):
    prod = db_query("SELECT * FROM products WHERE id=?", (p_id,), fetchone=True)
    if not prod: return await call.answer("❌ Not found.", show_alert=True)
    pn = prod[2] or ""; pr = safe_float(prod[4]); rpr = safe_float(prod[5])
    text = (f"📦 <b>NODE DETAILS</b>\n━━━━━━━━━━━━━━━━━━\nID: <code>{prod[0]}</code>\n"
        f"Group: {prod[1]}\nName: {pn}\nPackage: {prod[3]}\nPrice: {fmt_curr(pr)}\n"
        f"R-Price: {fmt_curr(rpr)}\nStock: {prod[6]}\nAPK: {prod[7] or 'None'}\n"
        f"Validity: {prod[8]}\nDevice: {prod[9]}\nVisible: {'✅' if prod[10] else '❌'}\n"
        f"Video: {'✅' if prod[11] else '❌'} | Image: {'✅' if prod[12] else '❌'}")
    toggle_txt = "Hide 👁‍🗨" if prod[10] else "Show 👁"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Edit Group", callback_data=f"edit_p_{p_id}_cat", style="primary"),
         InlineKeyboardButton(text="Edit Panel", callback_data=f"edit_p_{p_id}_panel_name", style="primary")],
        [InlineKeyboardButton(text="Edit Name", callback_data=f"edit_p_{p_id}_name", style="primary")],
        [InlineKeyboardButton(text="Edit Price", callback_data=f"edit_p_{p_id}_price", style="primary"),
         InlineKeyboardButton(text="Edit R-Price", callback_data=f"edit_p_{p_id}_rprice", style="primary")],
        [InlineKeyboardButton(text="Edit Validity", callback_data=f"edit_p_{p_id}_validity", style="primary"),
         InlineKeyboardButton(text="Edit Device", callback_data=f"edit_p_{p_id}_device", style="primary")],
        [InlineKeyboardButton(text="Edit APK", callback_data=f"edit_p_{p_id}_apk", style="primary"),
         InlineKeyboardButton(text="Add Keys ➕", callback_data=f"edit_p_{p_id}_keys", style="success")],
        [InlineKeyboardButton(text="🎬 Set Media", callback_data=f"set_prod_media_{p_id}", style="success")],
        [InlineKeyboardButton(text="Delete Key 🗑", callback_data=f"delkey_p_{p_id}", style="danger"),
         InlineKeyboardButton(text=toggle_txt, callback_data=f"toggle_p_{p_id}", style="danger")],
        [InlineKeyboardButton(text="Nuke Node 🗑", callback_data=f"delete_p_{p_id}", style="danger"),
         InlineKeyboardButton(text=fancy("Back"), callback_data="admin_manage_prods", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True, parse_mode='HTML')

@dp.callback_query(F.data.startswith("admin_view_p_"))
async def admin_view_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    try: p_id = int(call.data.split("_")[3])
    except: return
    await _render_product_detail(call, p_id)

@dp.callback_query(F.data.startswith("toggle_p_"))
async def admin_toggle_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    cur = db_query("SELECT is_active FROM products WHERE id=?", (p_id,), fetchone=True)[0]
    db_query("UPDATE products SET is_active=? WHERE id=?", (0 if cur == 1 else 1, p_id))
    await call.answer("✅ Updated!", show_alert=True)
    await _render_product_detail(call, p_id)

@dp.callback_query(F.data.startswith("edit_p_"))
async def start_edit_product(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split("_", 3)
    if len(parts) < 4: return await call.answer("Invalid.", show_alert=True)
    p_id = int(parts[2]); field = parts[3]
    await state.update_data(edit_p_id=p_id, edit_field=field)
    if field == 'keys':
        await call.message.edit_text("📥 Paste NEW KEYS (1 per line):", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_keys)
    else:
        fm = {'cat':'Category','panel_name':'Panel Name','name':'Package Name','price':'Price ₹','rprice':'R-Price ₹',
            'validity':'Validity','device':'Device Limit','apk':'APK Link'}
        await call.message.edit_text(f"✏️ New value for <b>{fm.get(field, field)}</b>:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_new_value)

@dp.message(AdminStates.wait_for_new_value)
async def process_edit_value(m: Message, state: FSMContext):
    data = await state.get_data(); p_id = data['edit_p_id']; field = data['edit_field']; nv = m.text.strip()
    if field in ['price', 'rprice']:
        try: nv = float(nv)
        except ValueError: return await m.answer("❌ Invalid number.")
    elif field == 'apk': nv = "" if nv.lower() == 'none' else nv
    col = {'cat':'category','panel_name':'panel_name','name':'name','price':'price_inr','rprice':'reseller_price',
        'validity':'validity','device':'device_limit','apk':'apk_link'}
    db_query(f"UPDATE products SET {col[field]}=? WHERE id=?", (nv, p_id))
    await m.answer("✅ Updated!", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

@dp.message(AdminStates.wait_for_add_keys)
async def process_add_keys(m: Message, state: FSMContext):
    data = await state.get_data(); p_id = data['edit_p_id']
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    if not keys: return await m.answer("❌ Zero keys.", reply_markup=admin_kb(), parse_mode='HTML')
    conn = sqlite3.connect('Sandii.dp'); c = conn.cursor()
    for k in keys: c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (p_id, k))
    c.execute("UPDATE products SET stock = stock + ? WHERE id=?", (len(keys), p_id))
    conn.commit(); conn.close()
    await m.answer(f"✅ {len(keys)} keys added!", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

@dp.callback_query(F.data.startswith("delete_p_"))
async def admin_delete_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    db_query("DELETE FROM products WHERE id=?", (p_id,)); db_query("DELETE FROM product_keys WHERE product_id=?", (p_id,))
    await call.answer("☢️ Deleted!", show_alert=True); await admin_manage_prods(call)

@dp.callback_query(F.data.startswith("delkey_p_"))
async def admin_delete_key_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2]); await state.update_data(del_p_id=p_id)
    await call.message.edit_text("🗑 Send exact key string to delete:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_delete_key)

@dp.message(AdminStates.wait_for_delete_key)
async def process_delete_key(m: Message, state: FSMContext):
    data = await state.get_data(); p_id = data['del_p_id']; k = m.text.strip()
    kd = db_query("SELECT id, is_used FROM product_keys WHERE product_id=? AND key_text=?", (p_id, k), fetchone=True)
    if not kd: return await m.answer("❌ Key not found.", reply_markup=admin_back_kb(), parse_mode='HTML')
    if kd[1] == 1: return await m.answer("⚠️ Key already used.", reply_markup=admin_back_kb(), parse_mode='HTML')
    db_query("DELETE FROM product_keys WHERE id=?", (kd[0],)); db_query("UPDATE products SET stock = stock - 1 WHERE id=?", (p_id,))
    await m.answer(f"✅ Key purged.", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

# ═══════════════════════════════════════════════════════════════════
# 22. ADMIN: TICKETS / BROADCAST / COUPONS
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "admin_view_tickets")
async def admin_view_tickets(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    tickets = db_query("SELECT id, user_id, message, created_at FROM tickets WHERE status='Open' LIMIT 1", fetchall=True)
    if not tickets: return await call.answer("✅ No pending tickets!", show_alert=True)
    t = tickets[0]
    text = f"🎫 <b>ACTIVE TICKET #{t[0]}</b>\n👤 <code>{t[1]}</code>\n📅 {t[3]}\n\n📝 {t[2]}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Reply", callback_data=f"reply_ticket_{t[0]}_{t[1]}", style="primary")],
        [InlineKeyboardButton(text="❌ Close", callback_data=f"close_ticket_{t[0]}", style="danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("close_ticket_"))
async def close_ticket(call: CallbackQuery):
    db_query("UPDATE tickets SET status='Closed' WHERE id=?", (call.data.split("_")[2],))
    await call.answer("✅ Closed.", show_alert=True); await admin_view_tickets(call)

@dp.callback_query(F.data.startswith("reply_ticket_"))
async def reply_ticket_start(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    await state.update_data(ticket_id=parts[2], user_id=parts[3])
    await call.message.edit_text("💬 Type reply message:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.ticket_reply_msg)

@dp.message(AdminStates.ticket_reply_msg)
async def send_ticket_reply(m: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await bot.send_message(data['user_id'], f"📞 <b>Admin Reply (Ref #{data['ticket_id']}):</b>\n\n{m.text}", parse_mode='HTML')
        db_query("UPDATE tickets SET status='Closed' WHERE id=?", (data['ticket_id'],))
        await m.answer("✅ Reply delivered.", reply_markup=admin_kb(), parse_mode='HTML')
    except Exception as e: await m.answer(f"❌ Error: {e}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_broadcast_btn")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📢 Send broadcast message:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.broadcast_msg)

@dp.message(AdminStates.broadcast_msg)
async def admin_broadcast_send(message: Message, state: FSMContext):
    users = db_query("SELECT user_id FROM users", fetchall=True)
    sent, failed = 0, 0
    m = await message.answer("⏳ Broadcasting...", parse_mode='HTML')
    for u in users:
        try: await message.send_copy(chat_id=u[0]); sent += 1
        except: failed += 1
        await asyncio.sleep(0.06)
    await m.edit_text(f"✅ Done!\n🟢 Sent: {sent}\n🔴 Failed: {failed}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_create_coupon")
async def admin_create_coupon_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🎟 Enter promo code:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_code)

@dp.message(AdminStates.add_coupon_code)
async def admin_coupon_code(m: Message, state: FSMContext):
    await state.update_data(code=m.text.strip().upper())
    await m.answer("💰 Reward amount (₹):", parse_mode='HTML'); await state.set_state(AdminStates.add_coupon_amount)

@dp.message(AdminStates.add_coupon_amount)
async def admin_coupon_amount(m: Message, state: FSMContext):
    try:
        await state.update_data(amount=float(m.text))
        await m.answer("👥 Max uses:", parse_mode='HTML'); await state.set_state(AdminStates.add_coupon_uses)
    except ValueError: await m.answer("❌ Invalid.")

@dp.message(AdminStates.add_coupon_uses)
async def admin_coupon_uses(m: Message, state: FSMContext):
    try:
        uses = int(m.text); data = await state.get_data()
        db_query("INSERT OR REPLACE INTO coupons (code, amount, uses_left) VALUES (?, ?, ?)", (data['code'], data['amount'], uses))
        await m.answer(f"✅ Code <b>{data['code']}</b> created!\n₹{data['amount']} × {uses} uses", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid.")

# ═══════════════════════════════════════════════════════════════════
# 23. ADMIN: RESELLER MGMT
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "admin_reseller_menu")
async def admin_reseller_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    sys = (db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True) or ['ON'])[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Grant", callback_data="reseller_make", style="success"),
         InlineKeyboardButton(text="➖ Revoke", callback_data="reseller_remove", style="danger")],
        [InlineKeyboardButton(text="📋 View Resellers", callback_data="reseller_view", style="primary")],
        [InlineKeyboardButton(text=f"{'🟢' if sys == 'ON' else '🔴'} Auto System: {sys}", callback_data="admin_toggle_reseller_sys", style="success" if sys == 'ON' else "danger")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text("👑 Reseller Management:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_reseller_sys")
async def toggle_reseller_sys(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    cur = (db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True) or ['ON'])[0]
    set_setting("reseller_system_status", 'OFF' if cur == 'ON' else 'ON')
    await admin_reseller_menu(call)

@dp.callback_query(F.data.in_(["reseller_make", "reseller_remove"]))
async def reseller_prompt_id(call: CallbackQuery, state: FSMContext):
    await state.update_data(reseller_action=call.data)
    await call.message.edit_text("👤 Enter User ID or @username:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.reseller_manage_id)

@dp.message(AdminStates.reseller_manage_id)
async def process_reseller_manage(m: Message, state: FSMContext):
    data = await state.get_data(); target = m.text.strip()
    if target.startswith('@'): target = target[1:]
    u = db_query("SELECT user_id, first_name FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if not u: return await m.answer("❌ Not found.", reply_markup=admin_back_kb(), parse_mode='HTML')
    if data['reseller_action'] == "reseller_make":
        db_query("UPDATE users SET is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?",
            (datetime.now().strftime("%Y-%m-%d"), u[0]))
        await m.answer(f"✅ <b>{u[1]}</b> is Reseller.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        db_query("UPDATE users SET is_reseller=0, account_type='Regular' WHERE user_id=?", (u[0],))
        await m.answer(f"✅ <b>{u[1]}</b> is Regular.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "reseller_view")
async def reseller_view(call: CallbackQuery):
    rs = db_query("SELECT user_id, first_name, username FROM users WHERE is_reseller=1", fetchall=True)
    if not rs: return await call.message.edit_text("📋 No resellers.", reply_markup=admin_back_kb(), parse_mode='HTML')
    text = "👑 <b>ACTIVE RESELLERS</b>\n━━━━━━━━━━━━━━━━━━\n"
    for r in rs:
        text += f"👤 {r[1]} (@{r[2] if r[2] else 'N/A'})\n🆔 <code>{r[0]}</code>\n\n"
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode='HTML')

# ═══════════════════════════════════════════════════════════════════
# 24. ADMIN: UI / EMOJI / MISC
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "admin_set_video")
async def admin_set_video_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📹 YouTube/video link (or 'None'):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_howto_video)

@dp.message(AdminStates.wait_for_howto_video)
async def exec_set_video(m: Message, state: FSMContext):
    set_setting("how_to_video", m.text.strip())
    await m.answer("✅ Video linked.", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

@dp.callback_query(F.data == "admin_edit_emojis")
async def admin_edit_emojis(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    rows = db_query("SELECT key, value FROM settings WHERE key LIKE 'emoji_%' ORDER BY key", fetchall=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row in rows:
        slot = row[0].replace("emoji_", "")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{slot} ({row[1]})", callback_data=f"edit_emoji_{slot}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎨 Choose emoji slot:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_emoji_"))
async def admin_edit_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    slot = call.data.split("edit_emoji_", 1)[1]
    await state.update_data(emoji_slot=slot)
    cur = get_setting(f"emoji_{slot}", "Not set")
    await call.message.edit_text(f"✏️ New emoji ID for <b>{slot}</b>:\nCurrent: {cur}\n(empty = reset)",
        reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_emoji_slot)

@dp.message(AdminStates.wait_for_emoji_slot)
async def save_emoji_slot(m: Message, state: FSMContext):
    data = await state.get_data(); slot = data['emoji_slot']; nid = m.text.strip()
    if nid == "":
        db_query("DELETE FROM settings WHERE key=?", (f"emoji_{slot}",))
        await m.answer(f"✅ Reset '{slot}' to default.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not nid.isdigit(): return await m.answer("❌ Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
        set_setting(f"emoji_{slot}", nid)
        await m.answer(f"✅ Emoji for '{slot}' updated.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_edit_ui_menu")
async def admin_edit_ui_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Start Menu", callback_data="edit_ui_start", style="primary")],
        [InlineKeyboardButton(text="VIP Menu", callback_data="edit_ui_vip", style="primary")],
        [InlineKeyboardButton(text="Add Balance", callback_data="edit_ui_add_balance", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text("✏️ Select text:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_ui_"))
async def admin_edit_ui_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    key = call.data.split("_")[2]; await state.update_data(ui_key=key)
    cur = get_ui_text(key)
    await call.message.edit_text(f"📝 New text for <b>{key.upper()}</b>:\n\nCurrent:\n{cur}", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_ui_text)

@dp.message(AdminStates.edit_ui_text)
async def admin_save_ui_text(m: Message, state: FSMContext):
    data = await state.get_data()
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"ui_{data['ui_key']}", m.text))
    await m.answer("✅ Updated!", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

@dp.callback_query(F.data == "admin_edit_reseller_price")
async def admin_edit_reseller_price_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    prods = db_query("SELECT id, name, category, panel_name, reseller_price FROM products ORDER BY category, panel_name", fetchall=True)
    if not prods: return await call.message.edit_text("No products.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in prods:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{p[2]} - {p[3] or ''} - {p[1]} (₹{safe_float(p[4]):.2f})",
            callback_data=f"edit_reseller_{p[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("👑 Select product:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_reseller_"))
async def admin_edit_reseller_price_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    pid = int(call.data.split("_")[2]); await state.update_data(edit_reseller_prod_id=pid)
    await call.message.edit_text("💰 New Reseller Price (₹):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_reseller_price)

@dp.message(AdminStates.edit_reseller_price)
async def admin_save_reseller_price(m: Message, state: FSMContext):
    try:
        np = float(m.text); data = await state.get_data()
        db_query("UPDATE products SET reseller_price=? WHERE id=?", (np, data['edit_reseller_prod_id']))
        await m.answer(f"✅ Updated to {fmt_curr(np)}.", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()
    except ValueError: await m.answer("❌ Invalid.")

@dp.callback_query(F.data == "admin_set_reseller_fee")
async def admin_set_reseller_fee(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text(f"💰 New Reseller Fee (₹):\nCurrent: {get_setting('reseller_setup_fee', '200.0')}",
        reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_setup_fee)

@dp.message(AdminStates.wait_for_reseller_setup_fee)
async def admin_save_reseller_fee(m: Message, state: FSMContext):
    try:
        set_setting("reseller_setup_fee", str(float(m.text)))
        await m.answer("✅ Updated.", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()
    except ValueError: await m.answer("❌ Invalid.")

@dp.callback_query(F.data == "admin_set_reseller_min")
async def admin_set_reseller_min(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text(f"💳 New Min Balance (₹):\nCurrent: {get_setting('reseller_min_balance', '500.0')}",
        reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_min_balance)

@dp.message(AdminStates.wait_for_reseller_min_balance)
async def admin_save_reseller_min(m: Message, state: FSMContext):
    try:
        set_setting("reseller_min_balance", str(float(m.text)))
        await m.answer("✅ Updated.", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()
    except ValueError: await m.answer("❌ Invalid.")

@dp.callback_query(F.data == "admin_set_support_links")
async def admin_set_support_links(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Telegram", callback_data="admin_set_telegram", style="primary")],
        [InlineKeyboardButton(text="📱 WhatsApp", callback_data="admin_set_whatsapp", style="primary")],
        [InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text("📌 Support links:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_set_telegram")
async def admin_set_telegram(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("✈️ Telegram URL:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_telegram)

@dp.message(AdminStates.wait_for_support_telegram)
async def save_telegram_link(m: Message, state: FSMContext):
    set_setting("support_telegram", m.text.strip())
    await m.answer("✅ Updated.", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

@dp.callback_query(F.data == "admin_set_whatsapp")
async def admin_set_whatsapp(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📱 WhatsApp URL:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_whatsapp)

@dp.message(AdminStates.wait_for_support_whatsapp)
async def save_whatsapp_link(m: Message, state: FSMContext):
    set_setting("support_whatsapp", m.text.strip())
    await m.answer("✅ Updated.", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

@dp.callback_query(F.data == "admin_set_category_emojis")
async def admin_set_category_emojis(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in FIXED_CATEGORIES:
        cur = get_setting(f"cat_emoji_{cat}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{cat} ({cur})", callback_data=f"set_cat_emoji_{cat}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎨 Choose category:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("set_cat_emoji_"))
async def admin_set_category_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    cat = call.data.split("set_cat_emoji_", 1)[1]; await state.update_data(cat_emoji_category=cat)
    await call.message.edit_text(f"🎨 Emoji ID for <b>{cat}</b>:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_category_emoji)

@dp.message(AdminStates.wait_for_category_emoji)
async def save_category_emoji(m: Message, state: FSMContext):
    data = await state.get_data(); cat = data['cat_emoji_category']; eid = m.text.strip()
    if eid == "": db_query("DELETE FROM settings WHERE key=?", (f"cat_emoji_{cat}",))
    elif not eid.isdigit(): return await m.answer("❌ Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
    else: set_setting(f"cat_emoji_{cat}", eid)
    await m.answer("✅ Done.", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

@dp.callback_query(F.data == "admin_set_panel_emojis")
async def admin_set_panel_emojis(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    panels = db_query("SELECT DISTINCT panel_name FROM products WHERE panel_name != '' ORDER BY panel_name", fetchall=True)
    if not panels: return await call.message.edit_text("No panels.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in panels:
        cur = get_setting(f"panel_emoji_{p[0]}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{p[0]} ({cur})", callback_data=f"set_panel_emoji_{p[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=fancy("Back"), callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🖼 Choose panel:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("set_panel_emoji_"))
async def admin_set_panel_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    pn = call.data.split("set_panel_emoji_", 1)[1]; await state.update_data(panel_emoji_name=pn)
    await call.message.edit_text(f"🎨 Emoji ID for <b>{pn}</b>:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_panel_emoji_id)

@dp.message(AdminStates.wait_for_panel_emoji_id)
async def save_panel_emoji(m: Message, state: FSMContext):
    data = await state.get_data(); pn = data['panel_emoji_name']; eid = m.text.strip()
    if eid == "": db_query("DELETE FROM settings WHERE key=?", (f"panel_emoji_{pn}",))
    elif not eid.isdigit(): return await m.answer("❌ Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
    else: set_setting(f"panel_emoji_{pn}", eid)
    await m.answer("✅ Done.", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

# ═══════════════════════════════════════════════════════════════════
# 25. ADMIN: FAMPAY / BINANCE SETUP (FIXED — Binance button now reachable)
# ═══════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "admin_setup_fampay")
async def setup_fampay_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    cur_api = get_setting("fampay_api_key", "Not set")
    cur_upi = get_setting("fampay_upi_id", "Not set")
    await call.message.edit_text(f"⚙️ <b>FAMPAY SETUP</b>\n\nAPI: {cur_api[:8] if cur_api != 'Not set' else 'Not set'}...\nUPI: {cur_upi}\n\nSend new API Key:\n<i>(/cancel to abort)</i>",
        reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_fampay_api)

@dp.message(AdminStates.wait_for_fampay_api)
async def setup_fampay_api(m: Message, state: FSMContext):
    if m.text == '/cancel': await state.clear(); return await m.answer("Killed.", reply_markup=admin_kb(), parse_mode='HTML')
    set_setting("fampay_api_key", m.text.strip())
    await m.answer("🔑 Saved!\n\nNow enter UPI ID (e.g. example@okhdfcbank):", parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_fampay_upi)

@dp.message(AdminStates.wait_for_fampay_upi)
async def setup_fampay_upi(m: Message, state: FSMContext):
    upi = m.text.strip()
    if '@' not in upi: return await m.answer("❌ Invalid UPI ID.", parse_mode='HTML')
    set_setting("fampay_upi_id", upi)
    await m.answer(f"✅ FamPay configured!\nUPI: {upi}", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

@dp.callback_query(F.data == "admin_setup_binance")
async def setup_binance_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🪙 <b>Binance Setup 1/3</b>\nAPI Key:\n<i>(/cancel to abort)</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_api)

@dp.message(AdminStates.wait_for_binance_api)
async def setup_binance_api(m: Message, state: FSMContext):
    if m.text == '/cancel': await state.clear(); return await m.answer("Aborted.", reply_markup=admin_kb(), parse_mode='HTML')
    set_setting("binance_api", m.text.strip())
    await m.answer("🪙 <b>2/3</b> Secret Key:", parse_mode='HTML'); await state.set_state(AdminStates.wait_for_binance_secret)

@dp.message(AdminStates.wait_for_binance_secret)
async def setup_binance_secret(m: Message, state: FSMContext):
    set_setting("binance_secret", m.text.strip())
    await m.answer("🪙 <b>3/3</b> USDT Deposit Address (TRC20/BEP20):", parse_mode='HTML'); await state.set_state(AdminStates.wait_for_binance_address)

@dp.message(AdminStates.wait_for_binance_address)
async def setup_binance_address(m: Message, state: FSMContext):
    set_setting("binance_address", m.text.strip())
    await m.answer("✅ Binance configured!", reply_markup=admin_kb(), parse_mode='HTML'); await state.clear()

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
async def main() -> None:
    init_db(); logger.info("DB initialized")
    migrate_categories()
    asyncio.create_task(auto_verify_task())
    logger.info("FamPay Auto-Verifier running")
    logger.info("🚀 Bot starting...")
    try: await dp.start_polling(bot)
    except Exception as err: logger.error(f"Polling failed: {err}")
    finally: await bot.session.close()

if __name__ == "__main__":
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): logger.info("Shutdown.")