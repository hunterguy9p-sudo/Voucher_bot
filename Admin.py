# admin_panel.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import ADMIN_ID
from data_store import (
    stock_text,
    add_vouchers,
    list_orders,
    set_price,
    get_price,
    get_users,
)

logger = logging.getLogger(__name__)


def admin_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Add ₹1000", callback_data="admin_add_1000"),
                InlineKeyboardButton("➕ Add ₹2000", callback_data="admin_add_2000"),
            ],
            [
                InlineKeyboardButton("➕ Add ₹4000", callback_data="admin_add_4000"),
            ],
            [
                InlineKeyboardButton("📦 Stock", callback_data="admin_stock"),
                InlineKeyboardButton("🧾 Orders", callback_data="admin_orders"),
            ],
        ]
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized.")
        return

    msg = (
        "🛠 *Admin Panel*\n\n"
        "Buttons se:\n"
        "• Vouchers add karo\n"
        "• Stock dekho\n"
        "• Recent orders dekho\n\n"
        "Commands:\n"
        "`/setprice 2000 80`  → ₹2000 ka price 80 set\n"
        "`/broadcast msg`     → sab users ko alert\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=admin_kb())
    context.user_data["state"] = None


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    if user.id != ADMIN_ID:
        await query.answer("Not admin", show_alert=True)
        return

    data = query.data

    if data == "admin_stock":
        await query.edit_message_text(stock_text(), parse_mode="Markdown", reply_markup=admin_kb())
        return

    if data == "admin_orders":
        orders = list_orders(10)
        if not orders:
            text = "No orders yet."
        else:
            lines = []
            for o in orders:
                lines.append(
                    f"• `{o['order_id']}` ₹{o['denom']} x{o['qty']} = ₹{o['total']} "
                    f"- *{o['status']}*"
                )
            text = "🧾 *Last Orders*\n\n" + "\n".join(lines)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_kb())
        return

    if data.startswith("admin_add_"):
        denom = int(data.split("_")[-1])
        context.user_data["state"] = f"admin_add_{denom}"
        await query.edit_message_text(
            f"Send voucher code(s) for ₹{denom}.\n"
            "• One code per line OR\n"
            "• Comma separated codes\n\n"
            "Example:\n`CODE1`\n`CODE2`\n`CODE3`",
            parse_mode="Markdown",
        )
        return


async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    state = context.user_data.get("state")
    text = (update.message.text or "").strip()

    # add vouchers flow
    if state and state.startswith("admin_add_"):
        denom = int(state.split("_")[-1])
        raw = text.replace("\n", ",")
        codes = [c.strip() for c in raw.split(",") if c.strip()]
        if not codes:
            await update.message.reply_text("No codes found. Please send again.")
            return

        add_vouchers(denom, codes)
        await update.message.reply_text(
            f"✅ Added {len(codes)} voucher(s) for ₹{denom}.\n\n" + stock_text(),
            parse_mode="Markdown",
            reply_markup=admin_kb(),
        )
        context.user_data["state"] = None
        return


async def setprice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    if len(context.args) != 2:
        await update.message.reply_text("Usage: /setprice 2000 80")
        return

    try:
        denom = int(context.args[0])
        price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid format. Example: /setprice 2000 80")
        return

    set_price(denom, price)
    await update.message.reply_text(
        f"✅ Price for ₹{denom} set to ₹{price:.2f}\n"
        f"Current:\n"
        f"• ₹1000 → ₹{get_price(1000):.2f}\n"
        f"• ₹2000 → ₹{get_price(2000):.2f}\n"
        f"• ₹4000 → ₹{get_price(4000):.2f}"
    )


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast message text...")
        return

    msg = "💥 *Shopping Alert*\n\n" + " ".join(context.args)
    users = get_users()
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
            count += 1
        except Exception as e:
            logger.error(f"Broadcast error for {uid}: {e}")

    await update.message.reply_text(f"Broadcast sent to {count} users.")


def get_admin_handlers():
    return [
        CommandHandler("admin", admin_command),
        CommandHandler("setprice", setprice_cmd),
        CommandHandler("broadcast", broadcast_cmd),
        CallbackQueryHandler(admin_callback, pattern="^admin_"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text),
    ]
