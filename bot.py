"""
Production Telegram Bot Engine for Singapore Pools TOTO Auto-Buyer.
Features:
- Live scheduled TOTO monitoring (daily or custom interval)
- Dynamic threshold adjustment via /threshold command or interactive buttons
- Duplicate alert & purchase prevention via history.py
- Interactive inline buttons (QuickPick $1, $2, System 7 $7)
- 3-minute automatic session cleanup
- Registered Telegram Command Menu (/check, /status, /threshold, /history, /cancel, /help)
- Direct receipt delivery to Telegram
"""

import asyncio
import logging
import os
import re
import sys
from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from buyer import SingaporePoolsBuyer
import history
from scraper import get_current_toto_jackpot
import settings

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Load environment variables
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHECK_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "24"))
USERNAME = os.getenv("SGPOOLS_USERNAME", "").strip()
PASSWORD = os.getenv("SGPOOLS_PASSWORD", "").strip()
HEADLESS = os.getenv("HEADLESS_MODE", "true").lower() in ("true", "1", "yes")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def is_authorized(update: Update) -> bool:
    """Security firewall: only allows interactions from ALLOWED_CHAT_ID."""
    if not ALLOWED_CHAT_ID:
        return False
    chat_id = str(update.effective_chat.id) if update.effective_chat else ""
    if chat_id != str(ALLOWED_CHAT_ID):
        logger.warning(f"Blocked unauthorized access attempt from chat_id: {chat_id}")
        return False
    return True

# Active user sessions
# Format: {chat_id: {"state": "AWAITING_OTP", "buyer": SingaporePoolsBuyer, ...}}
user_sessions = {}


def build_buy_keyboard() -> InlineKeyboardMarkup:
    """Builds inline action buttons for bet options."""
    keyboard = [
        [
            InlineKeyboardButton("🎲 QuickPick $1", callback_data="buy_qp_1"),
            InlineKeyboardButton("🎲 QuickPick $2", callback_data="buy_qp_2"),
        ],
        [
            InlineKeyboardButton("🌟 System 7 ($7)", callback_data="buy_sys7_7"),
        ],
        [
            InlineKeyboardButton("❌ Pass / Dismiss", callback_data="buy_dismiss"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_threshold_keyboard() -> InlineKeyboardMarkup:
    """Builds preset buttons for quick threshold changes."""
    keyboard = [
        [
            InlineKeyboardButton("$1 Million", callback_data="set_thresh_1000000"),
            InlineKeyboardButton("$2 Million", callback_data="set_thresh_2000000"),
            InlineKeyboardButton("$3 Million", callback_data="set_thresh_3000000"),
        ],
        [
            InlineKeyboardButton("$4 Million", callback_data="set_thresh_4000000"),
            InlineKeyboardButton("$5 Million", callback_data="set_thresh_5000000"),
            InlineKeyboardButton("$10 Million", callback_data="set_thresh_10000000"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def send_jackpot_alert(context: ContextTypes.DEFAULT_TYPE, chat_id: str, info):
    """Sends the formatted jackpot alert message with interactive buttons."""
    threshold = settings.get_threshold()
    message = (
        f"🎰 *TOTO JACKPOT ALERT!*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Est. Jackpot:* `{info.formatted_amount}`\n"
        f"📅 *Next Draw:* `{info.draw_date}`\n"
        f"🎯 *Trigger Target:* `${threshold:,}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Jackpot exceeds your target of *${threshold/1_000_000:.1f}M*!\n"
        f"Select a bet option below to proceed:"
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode="Markdown",
        reply_markup=build_buy_keyboard(),
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command."""
    if not is_authorized(update):
        return
    chat_id = str(update.effective_chat.id)
    threshold = settings.get_threshold()
    welcome_text = (
        f"👋 *Welcome to TOTO Alert & Buyer Bot!*\n\n"
        f"🎯 Current Jackpot Cutoff: *${threshold:,}* (${threshold/1_000_000:.1f}M)\n"
        f"⏱️ Schedule: Checking once every *{CHECK_INTERVAL_HOURS} hours* (Daily)\n\n"
        f"📌 *Quick Commands:*\n"
        f"• `/check` - Check live jackpot now\n"
        f"• `/threshold` - Change target cutoff (e.g. `/threshold 3m`)\n"
        f"• `/status` - Bot health & draw info\n"
        f"• `/history` - View past purchases\n"
        f"• `/cancel` - Cancel active session"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /help command."""
    if not is_authorized(update):
        return
    threshold = settings.get_threshold()
    help_text = (
        f"📖 *TOTO BOT GUIDE*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"• `/check`\n"
        f"  Fetches live Singapore Pools jackpot right now.\n\n"
        f"• `/threshold [amount]`\n"
        f"  View or change your jackpot cutoff.\n"
        f"  Examples: `/threshold 3m`, `/threshold 5000000`, `/threshold 2.5m`\n"
        f"  Or just type `/threshold` to pick with buttons!\n\n"
        f"• `/status`\n"
        f"  Shows jackpot amount, draw date, and whether you already hold a ticket.\n\n"
        f"• `/history`\n"
        f"  Shows recent purchase receipts and dates.\n\n"
        f"• `/cancel`\n"
        f"  Cancels any in-progress purchase session."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def threshold_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /threshold [amount] or presents preset buttons."""
    if not is_authorized(update):
        return
    args = context.args
    if args:
        # User typed e.g. /threshold 3m or /threshold 5000000
        raw_input = " ".join(args)
        parsed = settings.parse_amount_str(raw_input)
        if parsed and parsed >= 1_000_000:
            settings.set_threshold(parsed)
            await update.message.reply_text(
                f"✅ *Jackpot cutoff updated!*\n"
                f"New Threshold: *${parsed:,}* (${parsed/1_000_000:.1f} Million)\n\n"
                f"The bot will now alert and buy only when the estimated jackpot reaches or exceeds this amount.",
                parse_mode="Markdown",
            )
            return
        else:
            await update.message.reply_text(
                "⚠️ Invalid amount. Minimum TOTO jackpot is $1,000,000.\n"
                "Examples: `/threshold 3m`, `/threshold 5M`, `/threshold 2500000`",
                parse_mode="Markdown",
            )
            return

    # No arguments provided, show current and preset keyboard
    current = settings.get_threshold()
    msg = (
        f"🎯 *TOTO JACKPOT CUTOFF*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Current Target: *${current:,}* (${current/1_000_000:.1f}M)\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Select a new target cutoff below, or type `/threshold <amount>` (e.g. `/threshold 3.5m`):"
    )
    await update.message.reply_text(
        msg, parse_mode="Markdown", reply_markup=build_threshold_keyboard()
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reports bot status, configuration, and latest draw state."""
    if not is_authorized(update):
        return
    await update.message.reply_text("⏳ Checking system status...")
    threshold = settings.get_threshold()
    try:
        info = get_current_toto_jackpot()
        already_bought = history.has_purchased_for_draw(info.draw_date)
        status_msg = (
            f"📊 *TOTO BOT STATUS REPORT*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Current Jackpot:* `{info.formatted_amount}`\n"
            f"📅 *Next Draw:* `{info.draw_date}`\n"
            f"🎯 *Trigger Target:* `${threshold:,}` (${threshold/1_000_000:.1f}M)\n"
            f"🎫 *Bought for this draw:* `{'YES ✅' if already_bought else 'NO ⏳'}`\n"
            f"🖥️ *Browser Mode:* `{'Headless (Background)' if HEADLESS else 'Visible Window'}`\n"
            f"⏱️ *Schedule Interval:* Daily ({CHECK_INTERVAL_HOURS} hours)\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"System is operational and ready."
        )
        await update.message.reply_text(status_msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error checking status: {e}")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists past recorded purchases."""
    if not is_authorized(update):
        return
    records = history.load_history()
    if not records:
        await update.message.reply_text("ℹ️ No purchases recorded yet.")
        return

    lines = ["📜 *TOTO PURCHASE HISTORY*", "━━━━━━━━━━━━━━━━━━━"]
    for r in records[-5:]:
        lines.append(
            f"• *{r.get('draw_date')}* | `{r.get('bet_name')}` (${r.get('cost')}.00) - {r.get('timestamp')[:10]}"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any ongoing session."""
    if not is_authorized(update):
        return
    chat_id = str(update.effective_chat.id)
    session = user_sessions.pop(chat_id, None)
    if session and "buyer" in session:
        session["buyer"].close()
    await update.message.reply_text("🛑 Active session canceled.")


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually triggers a live TOTO check."""
    if not is_authorized(update):
        return
    chat_id = str(update.effective_chat.id)
    threshold = settings.get_threshold()
    await update.message.reply_text("🔍 Checking Singapore Pools live jackpot...")
    try:
        info = get_current_toto_jackpot()
        if history.has_purchased_for_draw(info.draw_date):
            await update.message.reply_text(
                f"ℹ️ Current jackpot is *{info.formatted_amount}* for *{info.draw_date}*.\n"
                f"✅ You have *already purchased* a ticket for this draw!",
                parse_mode="Markdown",
            )
            return

        if info.meets_threshold(threshold):
            await send_jackpot_alert(context, chat_id, info)
        else:
            await update.message.reply_text(
                f"ℹ️ Current jackpot is *{info.formatted_amount}* for *{info.draw_date}*.\n"
                f"Below your cutoff target of `${threshold:,}` (${threshold/1_000_000:.1f}M).\n"
                f"No purchase needed.",
                parse_mode="Markdown",
            )
    except Exception as e:
        logger.error(f"Error checking jackpot: {e}")
        await update.message.reply_text(f"⚠️ Failed to fetch jackpot: {e}")


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Presents the buy buttons for testing."""
    if not is_authorized(update):
        return
    chat_id = str(update.effective_chat.id)
    mock_msg = (
        f"🧪 *[TEST MODE] TOTO JACKPOT ALERT*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Live Jackpot:* `$2,500,000 est`\n"
        f"📅 *Next Draw:* `Mon, 19 Oct 2026, 6:30pm`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Select an option below to initiate Singapore Pools login and OTP:"
    )
    await update.message.reply_text(
        mock_msg, parse_mode="Markdown", reply_markup=build_buy_keyboard()
    )


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks (QP $1, QP $2, Sys 7, and Threshold presets)."""
    if not is_authorized(update):
        return
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = str(update.effective_chat.id)

    # 1. Handle threshold preset changes
    if data.startswith("set_thresh_"):
        new_amount = int(data.replace("set_thresh_", ""))
        settings.set_threshold(new_amount)
        await query.edit_message_text(
            f"✅ *Jackpot cutoff updated!*\n\n"
            f"New Target: *${new_amount:,}* (${new_amount/1_000_000:.1f} Million)\n"
            f"The bot will now trigger alerts when the estimated jackpot reaches this amount.",
            parse_mode="Markdown",
        )
        return

    # 2. Handle dismiss
    if data == "buy_dismiss":
        await query.edit_message_text("❌ Bet alert dismissed. No action taken.")
        session = user_sessions.pop(chat_id, None)
        if session and "buyer" in session:
            session["buyer"].close()
        return

    # 3. Handle buy options
    bet_mapping = {
        "buy_qp_1": {"name": "QuickPick Ordinary ($1)", "cost": 1, "code": "QP1"},
        "buy_qp_2": {"name": "QuickPick 2 Boards ($2)", "cost": 2, "code": "QP2"},
        "buy_sys7_7": {"name": "System 7 QuickPick ($7)", "cost": 7, "code": "SYS7"},
    }

    bet_info = bet_mapping.get(data)
    if not bet_info:
        await query.edit_message_text("❓ Unknown selection.")
        return

    # Check credentials
    if not USERNAME or not PASSWORD:
        await query.edit_message_text("❌ Error: SGPOOLS_USERNAME or SGPOOLS_PASSWORD missing.")
        return

    # Cancel previous session if any
    old_session = user_sessions.pop(chat_id, None)
    if old_session and "buyer" in old_session:
        old_session["buyer"].close()

    await query.edit_message_text(
        f"🎯 *Selected:* `{bet_info['name']}`\n\n"
        f"🔄 *Connecting to Singapore Pools...*\n"
        f"Submitting credentials to trigger SMS OTP...",
        parse_mode="Markdown",
    )

    buyer = SingaporePoolsBuyer(headless=HEADLESS)

    # Run browser login in background thread
    login_ok, login_msg = await asyncio.to_thread(buyer.start_login, USERNAME, PASSWORD)

    if login_ok:
        try:
            curr_draw = get_current_toto_jackpot().draw_date
        except:
            curr_draw = "Upcoming Draw"

        user_sessions[chat_id] = {
            "state": "AWAITING_OTP",
            "buyer": buyer,
            "bet_code": bet_info["code"],
            "bet_info": bet_info,
            "draw_date": curr_draw,
        }
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"📲 *SMS OTP Dispatched!*\n\n"
                f"Singapore Pools has sent a 6-digit verification code to your phone.\n\n"
                f"👉 *Reply to this bot with the 6-digit code* (e.g. `123456`) to confirm purchase."
            ),
            parse_mode="Markdown",
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ *Login Failed*: {login_msg}",
            parse_mode="Markdown",
        )


async def otp_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listens for user replying with their 6-digit SMS OTP."""
    if not is_authorized(update):
        return
    chat_id = str(update.effective_chat.id)
    text = update.message.text.strip()

    session = user_sessions.get(chat_id)
    if not session or session.get("state") != "AWAITING_OTP":
        return

    # Validate 6 digits
    if not re.fullmatch(r"\d{6}", text):
        await update.message.reply_text(
            "⚠️ Invalid format. Please enter exactly a *6-digit number* (e.g. `839201`).",
            parse_mode="Markdown",
        )
        return

    buyer: SingaporePoolsBuyer = session["buyer"]
    bet_code = session["bet_code"]
    bet_info = session["bet_info"]
    draw_date = session.get("draw_date", "Upcoming Draw")
    otp_code = text

    await update.message.reply_text(
        f"🔑 *Submitting OTP `{otp_code}` to Singapore Pools...*\n"
        f"Please wait a few seconds...",
        parse_mode="Markdown",
    )

    # Submit OTP in background thread
    otp_ok, otp_msg = await asyncio.to_thread(buyer.submit_otp, otp_code)

    if not otp_ok:
        await update.message.reply_text(
            f"❌ *Verification Failed*: {otp_msg}\n"
            f"Please check the code or request a new one.",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(
        f"✅ *Login Verified!*\n"
        f"🎫 Navigating to TOTO and placing order for *{bet_info['name']}*...",
        parse_mode="Markdown",
    )

    # Place bet in background thread
    bet_res = await asyncio.to_thread(buyer.place_bet, bet_code)

    # Clean session
    user_sessions.pop(chat_id, None)

    if bet_res.get("success"):
        receipt_path = bet_res.get("receipt_path")

        # Record in history to prevent duplicate buys
        history.record_purchase(
            draw_date=draw_date,
            bet_code=bet_code,
            bet_name=bet_info["name"],
            cost=bet_info["cost"],
            receipt_path=receipt_path,
        )

        success_msg = (
            f"🎉 *TOTO BET CONFIRMED!*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *Draw:* `{draw_date}`\n"
            f"🎫 *Bet:* `{bet_info['name']}`\n"
            f"💵 *Stake:* `${bet_info['cost']}.00`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Receipt confirmation attached below:"
        )
        if receipt_path and os.path.exists(receipt_path):
            with open(receipt_path, "rb") as photo:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=success_msg,
                    parse_mode="Markdown",
                )
        else:
            await update.message.reply_text(success_msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"⚠️ *Bet Placement Error*: {bet_res.get('error')}",
            parse_mode="Markdown",
        )


async def scheduled_jackpot_job(context: ContextTypes.DEFAULT_TYPE):
    """Background periodic checker run by JobQueue."""
    logger.info("Running scheduled TOTO jackpot check...")
    threshold = settings.get_threshold()
    try:
        info = get_current_toto_jackpot()
        logger.info(f"Checked jackpot: {info.formatted_amount} for {info.draw_date}")

        # Check if already purchased for this draw
        if history.has_purchased_for_draw(info.draw_date):
            logger.info(f"Already purchased for draw {info.draw_date}. Skipping alert.")
            return

        if info.meets_threshold(threshold) and ALLOWED_CHAT_ID:
            await send_jackpot_alert(context, ALLOWED_CHAT_ID, info)
    except Exception as e:
        logger.error(f"Periodic check failed: {e}")


async def post_init_setup(app: Application):
    """Registers bot commands with Telegram so they appear in the native Menu."""
    commands = [
        BotCommand("check", "Check live TOTO jackpot right now"),
        BotCommand("threshold", "Change or view jackpot cutoff target"),
        BotCommand("status", "System health & draw ticket status"),
        BotCommand("history", "View recent purchase history"),
        BotCommand("cancel", "Cancel active purchase session"),
        BotCommand("help", "View bot guide and commands"),
    ]
    try:
        await app.bot.set_my_commands(commands)
        logger.info("Successfully registered Telegram Command Menu.")
    except Exception as e:
        logger.warning(f"Could not register command menu: {e}")


def main():
    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not found in .env or environment.")
        sys.exit(1)

    print("Starting Singapore Pools TOTO Telegram Bot...")
    app = Application.builder().token(TOKEN).post_init(post_init_setup).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("threshold", threshold_command))
    app.add_handler(CommandHandler("cutoff", threshold_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(button_callback_handler))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, otp_message_handler)
    )

    # Schedule recurring job
    if app.job_queue:
        interval_seconds = max(3600, CHECK_INTERVAL_HOURS * 3600)
        app.job_queue.run_repeating(scheduled_jackpot_job, interval=interval_seconds, first=10)
        print(f"✅ Background periodic jackpot checker registered (every {CHECK_INTERVAL_HOURS} hours / daily).")

    print("🤖 Bot is polling for updates... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
