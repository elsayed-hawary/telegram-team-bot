# bot_handlers.py
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# نصوص الأزرار
BTN_SHOW_ID = "📋 عرض الـID"
BTN_HELP    = "ℹ️ مساعدة"
BTN_ABOUT   = "ℹ️ عن البوت"
BTN_MENU    = "📎 القائمة"

def build_reply_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(BTN_SHOW_ID)],
        [KeyboardButton(BTN_HELP), KeyboardButton(BTN_ABOUT)],
        [KeyboardButton(BTN_MENU)]
    ]
    # لوحة أزرار كبيرة وثابتة
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

async def send_with_kb(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    await update.message.reply_text(text, reply_markup=build_reply_kb())

# /start
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_with_kb(update, context, "أهلاً 👋\nاختَر من الأزرار بالأسفل.")

# /help
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"القائمة:\n"
        f"• {BTN_SHOW_ID} — يظهر الـ ID الخاص بك.\n"
        f"• {BTN_HELP} — هذه الرسالة.\n"
        f"• {BTN_ABOUT} — معلومات عن البوت.\n"
        f"• {BTN_MENU} — إظهار الأزرار لو اختفت.\n"
    )
    await send_with_kb(update, context, msg)

# /about
async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_with_kb(update, context, "بوت تجريبي مع أزرار Reply Keyboard ✅")

# /version (للاختبار)
async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_with_kb(update, context, "✅ version: reply-kb v1.0")

# تنفيذ الأزرار كنصوص
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == BTN_SHOW_ID:
        uid = update.effective_user.id
        return await send_with_kb(update, context, f"🆔 الـID الخاص بك:\n{uid}")

    if text == BTN_HELP or text == "/help":
        return await cmd_help(update, context)

    if text == BTN_ABOUT or text == "/about":
        return await cmd_about(update, context)

    if text == BTN_MENU or text == "/menu":
        return await send_with_kb(update, context, "تم عرض القائمة 👇")

    # أي رسالة أخرى
    return await send_with_kb(update, context, f"إنت كتبت: {text}\nاستخدم الأزرار بالأسفل.")

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("about",   cmd_about))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))