# 🤖 ELITE X CONFIG — Telegram Bot

Complete Telegram shop bot with wallet, payment verification, reseller system, and full admin panel.

---

## 📋 Features

### 👤 User Panel
- Welcome screen with wallet balance
- Product store (Category → Panel → Plan)
- **Multi-payment:** UPI QR / Binance USDT / Wallet / Coupon
- Order summary + Payment proof submission
- **Manual payment approval** (admin approves)
- Auto API verification (optional)
- My Profile with tier system
- My Keys (product-wise keys viewing)
- Add Balance (quick amounts + custom)
- Daily Gift / Lucky
- Refer & Earn
- Support tickets
- Share button

### 👑 Admin Panel
- **Store Manager:** Categories, Panels, Plans, Keys (full CRUD)
- **Stock ID Manager:** Category-wise ID inventory
- **User Manager:** Search, ban, VIP/Reseller toggle, orders, price override
- **Balance Manager:** Add/Remove/Check/Add-to-All
- **Reseller System:** Add/Remove/View/Direct activation by ID
- **Payment Settings:** UPI + Binance + ZapUPI + Auto API + Options
- **Order Approval:** Manual credit/reject with proof
- **Broadcast:** Text/Photo/Video/Doc to all users
- **Marketing:** Coupons, Daily Gift, Refer, Bulk Discounts
- **Menu Designer:** Custom buttons
- **Message Editor:** All UI texts editable
- **Link Manager:** Download/How-To-Use/Payment Proof/Support
- **API Manager:** Multiple endpoints + Plan variants
- **Co-Admins + Ownership Transfer**
- **Maintenance:** Global + Category + Panel
- **Statistics Dashboard**

---

## 🚀 Deployment on Render (Free Tier)

### Step 1: Fork/Clone this repo

### Step 2: Get your Bot Token
1. Open Telegram → search `@BotFather`
2. Send `/newbot`
3. Follow instructions
4. Copy the token (format: `1234:ABC-xyz`)

### Step 3: Get your Telegram User ID
1. Open Telegram → search `@userinfobot`
2. Send `/start`
3. Copy your ID (e.g., `8467166339`)

### Step 4: Deploy on Render
1. Go to [render.com](https://render.com) → **New Web Service**
2. Connect your GitHub repo
3. Settings:
   - **Name:** `elitex-config-bot`
   - **Region:** Singapore (closest to India)
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** Free

4. **Environment Variables** (add these):

5. Click **Create Web Service**

### Step 5: Persistent Storage (IMPORTANT!)
Render Free tier **does NOT persist files** across restarts.
For persistent DB, add a **Disk**:
1. Render Dashboard → Your Service → **Disks** → **Add Disk**
2. Name: `data`
3. Mount Path: `/opt/render/project/src/data`
4. Size: 1 GB (minimum)
5. Update `DB_PATH` env var to `/opt/render/project/src/data/elitex_bot.db`

⚠️ **Note:** Free tier doesn't support Disks. Upgrade to Starter ($7/mo) or use **Railway.app** / **Fly.io** for free persistent storage.

---

## 🖥️ Local Testing

```bash
# 1. Clone repo
git clone https://github.com/yourname/elitex-config-bot.git
cd elitex-config-bot

# 2. Create virtual env
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install deps
pip install -r requirements.txt

# 4. Create .env
cp .env.example .env
# Edit .env with your BOT_TOKEN and ADMIN_ID

# 5. Run
python bot.py