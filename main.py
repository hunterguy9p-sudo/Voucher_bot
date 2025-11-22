import os
import logging
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable not set")

ADMIN_ID = 7757877833  # tumhara Telegram user id

PRICES = {
    1000: 40.0,
    2000: 70.0,
    4000: 140.0,
}

# demo stock
STOCK = {
    1000: {"available": 0, "reserved": 0},
    2000: {"available": 129, "reserved": 0},
    4000: {"available": 0, "reserved": 0},
}

# logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------- KEYBOARDS ----------
def main_menu_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🛒 Buy Vouchers"), KeyboardButton("📦 Available Stock")],
            [KeyboardButton("❓ Raise Ticket")],
        ],
        resize_keyboard=True,
    )


def voucher_denom_kb():
    buttons = [
        [InlineKeyboardButton("💸 1000 Voucher", callback_data="denom_1000")],
        [InlineKeyboardButton("💸 2000 Voucher", callback_data="denom_2000")],
        [InlineKeyboardButton("💸 4000 Voucher", callback_data="denom_4000")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(buttons)


def tnc_text():
    return (
        "📜 TERMS AND CONDITIONS\n\n"
        "1. This service is provided for educational purposes only.\n"
        "2. We are not liable for any issues that may arise from using these vouchers.\n"
        "3. We are not responsible for any problems with vouchers or their usage.\n"
        "4. No refunds or replacements will be provided under any circumstances.\n"
        "5. We operate as a marketplace, simply sourcing and selling vouchers.\n"
        "6. By proceeding with this purchase, you acknowledge that you understand and "
        "agree to these terms."
    )


# ---------- HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎁 *Welcome to Shein Verse Voucher Bot!*\n\n"
        "Pricing for ₹1000 Vouchers:\n• All quantities: ₹40.0 each\n\n"
        "Pricing for ₹2000 Vouchers:\n• All quantities: ₹70.0 each\n\n"
        "Pricing for ₹4000 Vouchers:\n• All quantities: ₹140.0 each\n\n"
        "Use the buttons below to get started! 🚀\n\n"
        "🧾 *DISCLAIMER*: Vouchers are only applicable on allowed products."
    )
    if update.message:
        await update.message.reply_text(
            text, reply_markup=main_menu_kb(), parse_mode="Markdown"
        )
    context.user_data.clear()


async def available_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📦 *Current Stock*\n"
        f"• ₹1000: {STOCK[1000]['available']} available, {STOCK[1000]['reserved']} reserved\n"
        f"• ₹2000: {STOCK[2000]['available']} available, {STOCK[2000]['reserved']} reserved\n"
        f"• ₹4000: {STOCK[4000]['available']} available, {STOCK[4000]['reserved']} reserved"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def raise_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *Raise Ticket*\n"
        "Please describe your issue clearly (e.g., 'Voucher not working', "
        "'Payment error', 'UTR 1234').",
        parse_mode="Markdown",
    )
    context.user_data["state"] = "ticket"


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple admin command: shows stock."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized.")
        return

    msg = (
        "🛠 *Admin Panel (Simple)*\n\n"
        "📦 Stock:\n"
        f"• ₹1000 → {STOCK[1000]['available']}\n"
        f"• ₹2000 → {STOCK[2000]['available']}\n"
        f"• ₹4000 → {STOCK[4000]['available']}\n\n"
        "Future: add more admin features here."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    state = context.user_data.get("state")

    if text == "🛒 Buy Vouchers":
        await update.message.reply_text(
            "🛒 *Buy Vouchers*\nPlease select the voucher denomination you wish to buy:",
            reply_markup=voucher_denom_kb(),
            parse_mode="Markdown",
        )
        return

    if text == "📦 Available Stock":
        await available_stock(update, context)
        return

    if text == "❓ Raise Ticket":
        await raise_ticket(update, context)
        return

    # ticket text
    if state == "ticket":
        user = update.effective_user
        admin_msg = (
            f"🆕 New Ticket\n"
            f"From: {user.first_name} (id: {user.id}, username: @{user.username})\n\n"
            f"Message:\n{text}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        await update.message.reply_text(
            "✅ Your ticket has been recorded. Admin will reply soon.",
            reply_markup=main_menu_kb(),
        )
        context.user_data["state"] = None
        return

    # quantity after denomination
    if state == "wait_quantity":
        if not text.isdigit():
            await update.message.reply_text("Please enter a valid number (1–20).")
            return

        qty = int(text)
        if qty < 1 or qty > 20:
            await update.message.reply_text("Quantity must be between 1 and 20.")
            return

        denom = context.user_data.get("denom")
        price_each = PRICES[denom]
        total = qty * price_each

        context.user_data["qty"] = qty
        context.user_data["total"] = total
        context.user_data["state"] = "tnc"

        order_summary = (
            f"🧾 *Order Summary (₹{denom})*\n"
            f"Quantity: {qty}\n"
            f"Price each: ₹{price_each:.2f}\n"
            f"*TOTAL: ₹{total:.2f}*\n\n"
            "⏰ Voucher(s) will be reserved for you for 5 minutes after you agree to the terms.\n"
            "⚠️ If payment is not completed within this time, the reservation will be released.\n\n"
        )

        await update.message.reply_text(
            order_summary + tnc_text(),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ I Agree", callback_data="agree"),
                        InlineKeyboardButton("❌ I Disagree", callback_data="disagree"),
                    ]
                ]
            ),
        )
        return

    # anything else
    await update.message.reply_text(
        "I didn't understand that. Use the buttons below.",
        reply_markup=main_menu_kb(),
    )


async def callback_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Operation cancelled. Back to main menu.")
        await query.message.reply_text(
            "Choose an option:", reply_markup=main_menu_kb()
        )
        return

    if data.startswith("denom_"):
        denom = int(data.split("_")[1])
        context.user_data["denom"] = denom
        context.user_data["state"] = "wait_quantity"

        stock_avail = STOCK[denom]["available"]
        price_each = PRICES[denom]

        msg = (
            f"💸 *₹{denom} Voucher*\n"
            f"You selected ₹{denom} vouchers. Available: {stock_avail}\n\n"
            f"Pricing for ₹{denom} vouchers:\n"
            f"• All quantities: ₹{price_each:.1f} each\n\n"
            "🔢 Enter quantity (min 1, max 20):"
        )
        await query.edit_message_text(msg, parse_mode="Markdown")
        return

    if data == "agree":
        denom = context.user_data.get("denom")
        qty = context.user_data.get("qty")
        total = context.user_data.get("total")

        if not denom or not qty:
            await query.edit_message_text("Order expired. Please start again.")
            context.user_data.clear()
            return

        summary = (
            f"✅ *Order Summary (₹{denom})*\n"
            f"Quantity: {qty}\n"
            f"Price each: ₹{PRICES[denom]:.2f}\n"
            f"*TOTAL: ₹{total:.2f}*\n\n"
            "🔐 Vouchers are now reserved for you for 5 minutes.\n"
            "⏰ If payment is not completed within this time, the reservation will be released.\n\n"
            "💳 Click the link to complete payment:\n"
            f"[Click here to Pay ₹{total:.2f}](https://example.com/payment)"
        )

        context.user_data["state"] = None

        await query.edit_message_text(
            summary, parse_mode="Markdown", disable_web_page_preview=True
        )
        return

    if data == "disagree":
        context.user_data.clear()
        await query.edit_message_text(
            "You disagreed with the terms. Order cancelled."
        )
        await query.message.reply_text(
            "Back to main menu.", reply_markup=main_menu_kb()
        )
        return


# ---------- MAIN ----------
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CallbackQueryHandler(callback_buttons))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()


if __name__ == "__main__":
    main()
