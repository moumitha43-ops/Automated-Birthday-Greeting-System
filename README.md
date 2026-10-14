# 🎂 BIT Birthday Wishes
**Bannari Amman Institute of Technology**
Automated birthday email system — Flask + SQLite + Playwright + Render.com

---

## 📁 Project Files

```
bit_birthday/
├── app.py            ← Flask routes (all API endpoints)
├── helpers.py        ← SQLite DB, auth, CSV parser, config
├── send.py           ← Playwright screenshot + Gmail SMTP sender
├── scheduler.py      ← APScheduler daily auto-send job
├── pdf_report.py     ← ReportLab PDF birthday report generator
├── requirements.txt
├── render.yaml       ← Render.com one-click deploy config
├── sample_data.csv   ← Example CSV to test with
├── templates/
│   └── index.html    ← Full single-page app UI
└── static/           ← (place any static assets here)
```

---

## 🚀 Deploy to Render.com — Step by Step

### Step 1 — Push to GitHub

```bash
# In the bit_birthday/ folder:
git init
git add .
git commit -m "BIT Birthday Wishes — initial deploy"
git remote add origin https://github.com/YOUR_USERNAME/bit-birthday.git
git push -u origin main
```

### Step 2 — Create Web Service on Render

1. Go to [https://render.com](https://render.com) → sign up / log in
2. Click **New +** → **Web Service**
3. Connect your GitHub account → select the repo
4. Render will detect `render.yaml` automatically → click **Apply**

   If it doesn't auto-detect, set manually:
   | Field | Value |
   |---|---|
   | Runtime | Python 3 |
   | Build Command | `pip install -r requirements.txt && playwright install chromium && playwright install-deps chromium` |
   | Start Command | `python app.py` |
   | Plan | Free |

### Step 3 — Add Persistent Disk ⚠️ CRITICAL

Without this your database resets every redeploy.

Render service → **Disks** tab → **Add Disk**:
- **Name:** `data`
- **Mount Path:** `/data`
- **Size:** 1 GB

### Step 4 — Environment Variables

Render service → **Environment** tab → add:

| Key | Value |
|---|---|
| `DATA_DIR` | `/data` |
| `PORT` | `10000` |
| `SECRET_KEY` | any long random string (`openssl rand -hex 32`) |

> `render.yaml` sets these automatically if Render reads it.

### Step 5 — Deploy

Click **Manual Deploy** → **Deploy latest commit**

Build takes ~5–10 min on first run (Playwright + Chromium install).

Your app URL: `https://bit-birthday-wishes.onrender.com`

---

## 🔧 First-Time Setup

1. Open your app URL in the browser
2. The **Setup screen** appears — fill in:
   - Admin username + password (min 6 chars)
   - Gmail sender address
   - Gmail App Password (16 chars)
   - SMTP settings (defaults are correct for Gmail)
3. Click **Complete Setup** — you'll never see this screen again

### Getting a Gmail App Password

1. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. **Enable 2-Factor Authentication first** (required)
3. App → **Other** → name it `BIT Birthday`
4. Copy the 16-character password
5. Paste it in the setup form

---

## 📋 CSV Format

```csv
name,dob,email
Aarav Kumar,15-08-2003,aarav@example.com
Priya Sharma,03-12-2002,priya@example.com
```

- **name** — full student name
- **dob** — `DD-MM-YYYY` or `DD/MM/YYYY`
- **email** — student email address
- Uploading a new CSV **replaces** all existing records

---

## 🎨 Card Template

1. Go to **Card Template** in the sidebar
2. Click **Upload Template File** → select your HTML file
3. The template must contain `{{name}}` where the student's name appears
4. The card is rendered at **677×452 px** via Playwright and attached as a PNG

---

## ⏰ Auto Scheduler

1. Go to **Scheduler**
2. Set time (e.g. `08:00`) and timezone (`Asia/Kolkata`)
3. Toggle **Auto-send → Enabled**
4. Click **Save Schedule**

The system now runs every day at the set time, finds that day's birthday students, and sends them wishes automatically — no manual action needed.

---

## 📅 Calendar

- Click **Calendar** in the sidebar
- Navigate months with Prev / Next
- 🎂 highlighted dates have birthday students
- Click any highlighted date to see student details
- Click **⬇ PDF Report** to download a professional A4 PDF

---

## 🔄 Keeping the Free Tier Always-On

Render free tier sleeps after 15 min of inactivity.

**Fix with UptimeRobot (free):**
1. [https://uptimerobot.com](https://uptimerobot.com) → New Monitor
2. Type: **HTTP(s)**
3. URL: your Render app URL
4. Interval: **5 minutes**

This keeps the app awake 24×7.

---

## 🛠 Local Development

```bash
cd bit_birthday
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python app.py
# Open http://localhost:5000
```

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| Playwright fails to build | Make sure build command includes `playwright install-deps chromium` |
| Emails not sending | Check App Password is correct; Gmail 2FA must be enabled |
| Database resets on redeploy | Confirm persistent disk is mounted at `/data` and `DATA_DIR=/data` |
| App sleeps / cold starts slow | Set up UptimeRobot pings every 5 min |
| Card preview is blank | Template must include `{{name}}` and images must be base64 embedded |
| First deploy takes too long | Normal — Playwright + Chromium takes ~8 min on free tier |
