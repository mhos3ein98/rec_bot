# 🧾 Receipt Management Telegram Bot

Fully modular, production-ready receipt collection bot with:
- 🌐 Persian + English UI
- 🔐 Strict per-user, per-feature access control
- 📁 Folder-based receipt organisation
- 📊 Accounting + Admin analytics
- 💾 Local JSON file storage (SQLite-upgradable)

---

## 📁 File Structure

```
rec_bot/
├── bot.py                 ← Entry point
├── handlers.py            ← All handlers (message + callback)
├── state.py               ← FSM states
├── storage.py             ← File-system persistence
├── keyboards.py           ← All inline keyboards
├── config.py              ← TOKEN + USER_PERMISSIONS (edit this)
├── i18n.py                ← Translation loader
├── requirements.txt
├── Dockerfile
├── translations/
│   ├── en.json
│   └── fa.json
└── data/                  ← Auto-created at runtime
    ├── sessions.json
    └── <user_id>/
        └── <folder>/
            ├── metadata.json
            ├── logs.json
            └── images/
```

---

## ⚙️ Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

---

### 2. Configure `config.py`
```python
TOKEN = "YOUR_BOT_TOKEN"   # from @BotFather

USER_PERMISSIONS = {
    123456789: {           # your Telegram numeric ID
        "name": "Your Name",
        "language": "fa",  # default language before first /start
        "features": {
            "create_folder": True,
            "continue_folder": True,
            "send_receipts": True,
            "accounting": True,
            "admin_panel": True,
        },
    },
}
```

Find your ID: message @userinfobot

---

### 3. Run bot
```bash
python bot.py
```

---

## 🐳 Docker

```bash
docker build -t rec_bot .
docker run -d --name rec_bot --restart unless-stopped \
  -v $(pwd)/data:/app/data rec_bot
```

---

## 🌐 Language Selection

- Shown **once** on first `/start`
- Stored permanently in `data/sessions.json`
- Never asked again

---

## 🔐 Access Control

- Users not in `USER_PERMISSIONS` → immediately blocked
- Each button is hidden if no permission
- Each action is re-checked before execution

---

## 🧾 7-Step Receipt Flow

```
Step 1 — Customer name / @username / ID
Step 2 — Amount (numeric)
Step 3 — Volume in GB (numeric)
Step 4 — Payment time HH:MM (strict validation)
Step 5 — Select admin (buttons only, no free text)
Step 6 — Receipt image or text
Step 7 — Confirm summary → save OR edit fields
         → continue OR finish session
```

---

## 📊 Main Menu Features

| Button | Feature flag | Description |
|--------|--------------|-------------|
| 📁 Create Folder | `create_folder` | New folder + collection mode |
| 📂 Continue Folder | `continue_folder` | Resume existing folder |
| 📤 Send Receipts | `send_receipts` | View receipts sorted by time |
| 📊 Accounting | `accounting` | Total GB or amount per folder |
| 👤 Admins | `admin_panel` | GB sold per admin per folder |
```
