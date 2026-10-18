# Singapore Pools TOTO Jackpot Auto-Buyer Bot

An automated assistant that periodically monitors the Singapore Pools TOTO estimated jackpot and lets you purchase QuickPick or System 7 tickets directly via Telegram with human-in-the-loop SMS OTP confirmation.

---

## 🎯 How It Works

```mermaid
sequenceDiagram
    autonumber
    participant Cron as Scheduler (Every 2h)
    participant Scraper as scraper.py
    participant Bot as bot.py (Telegram)
    participant Buyer as buyer.py (Playwright)
    participant User as You (Mobile)

    Cron->>Scraper: Check live TOTO prize quantum
    alt Jackpot >= $2,000,000
        Scraper->>Bot: Jackpot meets threshold!
        Bot->>User: 🎰 TOTO Alert! ($2.5M est). Buy? [QP $1] [QP $2] [Sys 7 $7] [Pass]
        User->>Bot: Taps "QuickPick $1"
        Bot->>Buyer: Launch Playwright & submit username/password
        Buyer-->>User: 📲 Singapore Pools sends SMS OTP to your phone
        Bot->>User: "SMS OTP sent! Please reply with 6-digit code:"
        User->>Bot: Replies "123456"
        Bot->>Buyer: Injects OTP digits into #0_input_login_otp .. #5_input_login_otp
        Buyer->>Buyer: Navigates to TOTO -> Adds to Bet Slip -> Places Bet
        Buyer-->>Bot: Confirmed! Takes screenshot of receipt
        Bot->>User: 🎉 Ticket Confirmed! (Receipt image attached)
    end
```

---

## 📁 Project Structure

* **scraper.py**: Lightweight scraper that queries Singapore Pools' official static pregenerated file (`toto_next_draw_estimate_en.html`) with zero dependencies and no bot blocking.
* **buyer.py**: Playwright automation engine that handles login, OTP box injection, navigating to TOTO QuickPick, placing bets, and taking receipt screenshots.
* **bot.py**: The Telegram bot engine running `python-telegram-bot` with background scheduler (`JobQueue`) and interactive conversation state machine.
* **history.py**: Purchase tracker and duplicate bet prevention store.
* **settings.py**: Dynamic threshold management.
* **.env.example**: Safe template for your private environment variables.

---

## ⚙️ Configuration (`.env`)

```ini
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_telegram_chat_id
JACKPOT_THRESHOLD=2000000
CHECK_INTERVAL_HOURS=24

SGPOOLS_USERNAME=your_username
SGPOOLS_PASSWORD=your_password

# Set to true for silent background, false for visible window
HEADLESS_MODE=true
```

---

## 🚀 Telegram Commands

* `/check` - Check the current live jackpot immediately.
* `/threshold` - Change target jackpot cutoff (e.g. `/threshold 3m`).
* `/status` - Bot health, schedule & draw status.
* `/history` - View past purchases.
* `/test`  - Trigger an instant test alert with QuickPick / System 7 buttons.
* `/cancel`- Cancel any pending login / OTP purchase session.

---

## ☁️ Google Cloud Free Tier Deployment (e2-micro)

1. **Create Free VM** in GCP Console (`Compute Engine` -> `VM instances`):
   * **Name**: `totobot`
   * **Region**: `us-central1` (Iowa), `us-east1`, or `us-west1` (Always Free eligible)
   * **Machine type**: `e2-micro` (2 vCPU, 1 GB memory)
   * **Boot disk**: Ubuntu 24.04 LTS, 20 GB Standard persistent disk

2. **SSH into the VM** and run:
   ```bash
   git clone https://github.com/kevinseow/lottery_buyer.git
   cd lottery_buyer
   chmod +x setup_gcp_vm.sh
   ./setup_gcp_vm.sh
   ```

3. **Configure your credentials**:
   ```bash
   nano .env
   ```
   Paste your `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SGPOOLS_USERNAME`, and `SGPOOLS_PASSWORD`.

4. **Start the 24/7 background service**:
   ```bash
   sudo systemctl start totobot
   sudo journalctl -u totobot -f
   ```
