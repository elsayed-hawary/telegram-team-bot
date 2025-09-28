# bot_handlers.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from user_store import upsert_user

async def _track_user(update: Update):
    tg_user = None
    if update.message and update.message.from_user:
        tg_user = update.message.from_user
    elif update.callback_query and update.callback_query.from_user:
        tg_user = update.callback_query.from_user
    elif update.effective_user:
        tg_user = update.effective_user
    if tg_user:
        upsert_user(tg_user)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text("أهلاً! البوت شغال ✅\nجرّب /help.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text(
        "الأوامر:\n/start — بدء\n/help — مساعدة\n/about — عن البوت\n/menu — أزرار مثال\nأكتب أي رسالة وهرد عليك."
    )

async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text("بوت تيليجرام مع تخزين المستخدمين تلقائيًا 💾")

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    kb = [[InlineKeyboardButton("زر 1", callback_data="btn_1")],
          [InlineKeyboardButton("زر 2", callback_data="btn_2")]]
    await update.message.reply_text("اختار زر:", reply_markup=InlineKeyboardMarkup(kb))

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    q = update.callback_query
    await q.answer()
    if q.data == "btn_1":
        await q.edit_message_text("تم الضغط على زر 1 ✅")
    elif q.data == "btn_2":
        await q.edit_message_text("تم الضغط على زر 2 ✅")

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text(f"إنت كتبت: {update.message.text or ''}")

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("about", cmd_about))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
