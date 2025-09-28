# bot_handlers.py
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

from account_store import create_or_update_account, get_account_by_user
from group_store import create_group, get_group, add_member, my_groups

# ==== نصوص الأزرار ====
BTN_CREATE_ACC = "🆕 إنشاء حساب"
BTN_JOIN_GROUP = "👥 الانضمام إلى مجموعة"
BTN_MY_ACC     = "🆔 حسابي"
BTN_HELP       = "ℹ️ مساعدة"

def build_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(BTN_CREATE_ACC), KeyboardButton(BTN_JOIN_GROUP)],
        [KeyboardButton(BTN_MY_ACC),     KeyboardButton(BTN_HELP)],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

async def send_kb(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    # يدعم الرد سواء كانت الرسالة أمرًا أو نصًا
    if update.message:
        await update.message.reply_text(text, reply_markup=build_kb())
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=build_kb())

# ==== أوامر أساسية ====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_kb(update, context, "أهلاً 👋\nاختَر من الأزرار بالأسفل.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"القائمة:\n"
        f"• {BTN_CREATE_ACC} — يطلب اسمك ويُنشئ لك ID حساب.\n"
        f"• {BTN_JOIN_GROUP} — يطلب ID المجموعة للانضمام.\n"
        f"• {BTN_MY_ACC} — يعرض حسابك الحالي.\n"
        f"• /mkgroup اسم_المجموعة — (للتجربة) إنشاء مجموعة وإرجاع Group ID.\n"
        "ملاحظـة: شكل IDs مثل: حساب `UABC123` — مجموعة `GABC123`."
    )
    await send_kb(update, context, msg)

async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_kb(update, context, "✅ version: accounts+groups v1.0")

# ==== إنشاء مجموعة (اختياري للتجربة) ====
async def cmd_mkgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args).strip()
    if not name:
        return await send_kb(update, context, "استخدم: /mkgroup اسم_المجموعة")
    acc = get_account_by_user(update.effective_user.id)
    if not acc:
        return await send_kb(update, context, "أولاً أنشئ حساب من الزر: 🆕 إنشاء حساب")
    g = create_group(name, update.effective_user.id)
    await send_kb(update, context, f"✅ تم إنشاء المجموعة: {g['name']}\n🆔 Group ID: {g['group_id']}")

# ==== التعامل مع الأزرار كنصوص ====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # حالات انتظار إدخال
    waiting = context.user_data.get("awaiting")
    if waiting == "CREATE_NAME":
        name = text
        if not name:
            return await send_kb(update, context, "❌ اسم غير صالح. أعد المحاولة.")
        acc = create_or_update_account(update.effective_user.id, name)
        return await finish_wait(update, context,
            f"🎉 تم إنشاء حسابك.\n"
            f"الاسم: {acc['name']}\n"
            f"🆔 Account ID: {acc['account_id']}")

    if waiting == "JOIN_GROUP":
        group_id = text.upper().replace(" ", "")
        g = get_group(group_id)
        if not g:
            return await finish_wait(update, context, "❌ لم أجد مجموعة بهذا الـID. تأكد منه وحاول مرة أخرى.")
        # لازم يكون عندك حساب أولًا
        acc = get_account_by_user(update.effective_user.id)
        if not acc:
            return await finish_wait(update, context, "⚠️ لست تمتلك حسابًا بعد. أنشئ حسابًا أولًا من الزر 🆕.")
        add_member(group_id, update.effective_user.id)
        return await finish_wait(update, context, f"✅ تم انضمامك إلى المجموعة: {g['name']} ({g['group_id']})")

    # تنفيذ الأزرار
    if text == BTN_CREATE_ACC:
        acc = get_account_by_user(update.effective_user.id)
        if acc:
            return await send_kb(update, context, f"لديك حساب بالفعل:\nالاسم: {acc['name']}\n🆔 Account ID: {acc['account_id']}")
        context.user_data["awaiting"] = "CREATE_NAME"
        return await send_kb(update, context, "✍️ اكتب اسمك الآن (رسالة واحدة).")

    if text == BTN_JOIN_GROUP:
        context.user_data["awaiting"] = "JOIN_GROUP"
        return await send_kb(update, context, "✍️ اكتب **ID المجموعة** الآن (مثل: GABC123).")

    if text == BTN_MY_ACC:
        acc = get_account_by_user(update.effective_user.id)
        if not acc:
            return await send_kb(update, context, "لا يوجد حساب بعد. استخدم زر 🆕 إنشاء حساب.")
        # اعرض حسابي + المجموعات اللي أنا عضو فيها
        groups = my_groups(update.effective_user.id)
        extra = ""
        if groups:
            extra = "\n\nمجموعاتك:\n" + "\n".join([f"- {g['name']} ({g['group_id']})" for g in groups])
        return await send_kb(update, context, f"الاسم: {acc['name']}\n🆔 Account ID: {acc['account_id']}{extra}")

    if text == BTN_HELP or text == "/help":
        return await cmd_help(update, context)

    # أي نص آخر
    return await send_kb(update, context, f"إنت كتبت: {text}\nاستخدم الأزرار بالأسفل.")

async def finish_wait(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: str):
    context.user_data.pop("awaiting", None)
    await send_kb(update, context, msg)

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(CommandHandler("mkgroup", cmd_mkgroup))  # اختياري للتجربة
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))