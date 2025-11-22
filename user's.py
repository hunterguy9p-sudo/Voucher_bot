# user_panel.py

import logging
import uuid
import requests
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import ContextTypes, filters, MessageHandler, CallbackQueryHandler, CommandHandler

from config import ADMIN_ID, PAY0_API_KEY, PAY0_REDIRECT_URL
from data_store import (
    add_user,
    vouchers_for,
    pop_voucher,
    stock_text,
    get_price,
    add_order,
    update_order,
)

logger = logging.getLogger(__name__)


# ---------- UI HELPERS ----------

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


def tnc_text() -> str:
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


def generate_order_id() -> str:
    return "ORD-" + uuid.uuid4().hex[:10].upper()


# ---------- PAY0 API HELPERS ----------

def create_pay0_order(amount: float, order_id: str, customer_mobile: str, customer_name: str) -> str:
    try:
        url = "https://pay0.shop/api/create-order"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "customer_mobile": customer_mobile,
            "customer_name": customer_name or "Telegram User",
            "user_token": PAY0_API_KEY,
            "amount": str(amount),
            "order_id": order_id,
            "redirect_url": PAY0_REDIRECT_URL,
            "remark1": "telegram_bot",
            "remark2": "shein_voucher",
        }

        resp = requests.post(url, data=payload, headers=headers, timeout=15)
        data = resp.json()
        logger.info(f"Pay0 create-order response: {data}")

        if data.get("status") is True and "result" in data:
            return data["result"].get("payment_url", "")

        return ""
    except Exception as e:
        logger.error(f"Error in create_pay0_order: {e}")
        return ""


def check_payment_status(order_id: str) -> str:
    try:
        url = "https://pay0.shop/api/check-order-status"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "user_token": PAY0_API_KEY,
            "order_id": order_id,
        }

        resp = requests.post(url, data=payload, headers=headers, timeout=15)
        data = resp.json()
        logger.info(f"Pay0 check-status response: {data}")

        if data.get("status") is True and "result" in data:
            txn_status = data["result"].get("txnStatus", "").upper()
            if txn_status == "SUCCESS":
                return "success"
            if txn_status == "PENDING":
                return "pending"
            if txn_status == "FAILED":
                return "failed"
        return "unknown"

    except Exception as e:
        logger.error(f"Error in check_payment_status: {e}")
        return "error"


# ---------- HANDLERS (USER SIDE) ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id)

    text = (
        "🎁 *Welcome to Shein Verse Voucher Bot!*\n\n"
        f"Pricing:\n"
        f"• ₹1000 → ₹{get_price(1000):.2f}\n"
        f"• ₹2000 → ₹{get_price(2000):.2f}\n"
        f"• ₹4000 → ₹{get_price(4000):.2f}\n\n"
        "Use the buttons below to get started! 🚀"
    )
    if update.message:
        await update.message.reply_text(
            text, reply_markup=main_menu_kb(), parse_mode="Markdown"
        )
    context.user_data.clear()


async def available_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(stock_text(), parse_mode="Markdown")


async def raise_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *Raise Ticket*\n"
        "Please describe your issue clearly (e.g., 'Voucher not working', "
        "'Payment error', 'UTR 1234').",
        parse_mode="Markdown",
    )
    context.user_data["state"] = "ticket"


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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

    # ticket message
    if state == "ticket":
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

    # quantity after denomination selected
    if state == "wait_quantity":
        if not text.isdigit():
            await update.message.reply_text("Please enter a valid number (1–20).")
            return

        qty = int(text)
        if qty < 1 or qty > 20:
            await update.message.reply_text("Quantity must be between 1 and 20.")
            return

        denom = context.user_data.get("denom")
        price_each = get_price(denom)
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

    await update.message.reply_text(
        "I didn't understand that. Use the buttons below.",
        reply_markup=main_menu_kb(),
    )


async def callback_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Operation cancelled. Back to main menu.")
        await query.message.reply_text("Choose an option:", reply_markup=main_menu_kb())
        return

    if data.startswith("denom_"):
        denom = int(data.split("_")[1])
        context.user_data["denom"] = denom
        context.user_data["state"] = "wait_quantity"

        available = len(vouchers_for(denom))
        price_each = get_price(denom)

        msg = (
            f"💸 *₹{denom} Voucher*\n"
            f"You selected ₹{denom} vouchers.\n"
            f"Available vouchers: {available}\n\n"
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

        order_id = generate_order_id()
        context.user_data["order_id"] = order_id
        context.user_data["user_id"] = user.id

        # order history me add
        add_order(
            {
                "order_id": order_id,
                "user_id": user.id,
                "username": user.username,
                "denom": denom,
                "qty": qty,
                "total": total,
                "status": "created",
                "created_at": datetime.utcnow().isoformat(),
                "voucher_code": None,
            }
        )

        payment_url = create_pay0_order(
            amount=total,
            order_id=order_id,
            customer_mobile="9999999999",
            customer_name=user.first_name or "Telegram User",
        )

        if not payment_url:
            await query.edit_message_text(
                "⚠ Unable to generate payment link. Please try again later."
            )
            context.user_data.clear()
            update_order(order_id, status="paylink_error")
            return

        summary = (
            f"🧾 *Order Summary (₹{denom})*\n"
            f"Order ID: `{order_id}`\n"
            f"Quantity: {qty}\n"
            f"Price each: ₹{get_price(denom):.2f}\n"
            f"*TOTAL: ₹{total:.2f}*\n\n"
            "💳 Please complete the payment using the link below:\n\n"
            f"[Click here to Pay ₹{total:.2f}]({payment_url})\n\n"
            "After completing payment, click *'I Have Paid'* to verify."
        )

        await query.edit_message_text(
            summary,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✔ I Have Paid", callback_data="paid")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
                ]
            ),
            disable_web_page_preview=True,
        )
        context.user_data["state"] = "payment"
        update_order(order_id, status="await_payment")
        return

    if data == "paid":
        denom = context.user_data.get("denom")
        qty = context.user_data.get("qty")
        total = context.user_data.get("total")
        order_id = context.user_data.get("order_id")
        user_id = context.user_data.get("user_id")

        if not order_id:
            await query.edit_message_text("Order expired. Please start again.")
            context.user_data.clear()
            return

        status = check_payment_status(order_id)

        if status == "success":
            code = pop_voucher(denom)
            if not code:
                await query.edit_message_text(
                    "✅ Payment verified, but vouchers out of stock.\n"
                    "Admin will contact you shortly."
                )
                update_order(order_id, status="paid_no_stock")
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠ Payment success but NO voucher left for ₹{denom}. Order ID: {order_id}",
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "🎉 *Payment Verified!*\n\n"
                        f"Order ID: `{order_id}`\n"
                        f"Voucher (₹{denom}): `{code}`\n\n"
                        "Please keep this code safe and do not share it with anyone."
                    ),
                    parse_mode="Markdown",
                )
                update_order(order_id, status="completed", voucher_code=code)
                admin_msg = (
                    f"✅ *New Order Completed*\n\n"
                    f"User: {user.first_name} (@{user.username})\n"
                    f"ID: {user.id}\n"
                    f"Order ID: {order_id}\n"
                    f"Voucher: ₹{denom}\n"
                    f"Qty: {qty}\n"
                    f"Total: ₹{total:.2f}\n"
                    f"Code: {code}"
                )
                await context.bot.send_message(
                    chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown"
                )

            await query.edit_message_text(
                "✅ Payment successful & voucher delivered to your chat. Check your messages. 💌"
            )
            context.user_data.clear()
            return

        elif status in ("pending", "processing"):
            await query.edit_message_text(
                "⏳ Payment is still pending / processing.\n"
                "Please wait 30–60 seconds and press *'I Have Paid'* again.\n"
                "If amount is deducted and still pending, contact support.",
                parse_mode="Markdown",
            )
            return

        elif status in ("failed", "cancelled"):
            await query.edit_message_text(
                "❌ Payment failed or cancelled.\n"
                "If money is deducted, please contact support with your Order ID."
            )
            update_order(order_id, status="failed")
            context.user_data.clear()
            return

        else:
            await query.edit_message_text(
                "⚠ Unable to verify payment right now.\n"
                "Please contact support or try again later."
            )
            update_order(order_id, status="unknown")
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠ Pay0 status unknown/error for Order ID: {order_id}",
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


# helper to register in main.py
def get_user_handlers():
    return [
        CommandHandler("start", start),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        CallbackQueryHandler(callback_buttons, pattern="^(?!admin_).*"),
      ]
