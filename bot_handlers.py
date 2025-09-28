# bot_handlers.py
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

from account_store import create_or_update_account, get_account_by_user
from group_store import create_group, get_group, add_member, my_groups

# ==== نصوص الأزرار ====
BTN_CREATE_ACC   = "🆕 إنشاء حساب"
BTN_CREATE_GROUP = "➕ إنشاء مجموعة"
BTN_JOIN_GROUP   = "👥 الانضمام إلى مجموعة"
BTN_MY_ACC       = "🆔 حسابي"
BTN_HELP         = "ℹ️ مساعدة"

def build_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(BTN_CREATE_ACC),   KeyboardButton(BTN_CREATE_GROUP)],
        [KeyboardButton(BTN_JOIN_GROUP),   KeyboardButton(BTN_MY_ACC)],
        [KeyboardButton(BTN_HELP)],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

async def send_kb(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if update.message:
        await update.message.reply_text(text, reply_markup=build_kb())
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=build_kb())

# ==== أوامر أساسية ====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_kb(update, context, "أهلاً 👋\nاختَر من الأزرار بالأسفل.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"• {BTN_CREATE_ACC} — يطلب اسمك ويُنشئ لك Account ID (يبدأ بـ U).\n"
        f"• {BTN_CREATE_GROUP} — (تحتاج حساب أولًا) يطلب اسم المجموعة ويعطيك Group ID (يبدأ بـ G).\n"
        f"• {BTN_JOIN_GROUP} — انضمام لمجموعة عبر Group ID (مثال: GABC123).\n"
        f"• {BTN_MY_ACC} — يعرض حسابك ومجموعاتك.\n"
        "ملاحظة: لا ينفع تستخدم Account ID للانضمام — لازم Group ID."
    )
    await send_kb(update, context, msg)

async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_kb(update, context, "✅ version: accounts+groups v1.1")

# ==== منطق الأزرار والنص ====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # حالات انتظار الإدخال
    waiting = context.user_data.get("awaiting")

    # إنشاء حساب — إدخال الاسم
    if waiting == "CREATE_NAME":
        name = text
        if not name:
            return await send_kb(update, context, "❌ اسم غير صالح. أعد المحاولة.")
        acc = create_or_update_account(update.effective_user.id, name)
        context.user_data.pop("awaiting", None)
        return await send_kb(update, context,
            f"🎉 تم إنشاء حسابك.\nالاسم: {acc['name']}\n🆔 Account ID: {acc['account_id']}")

    # إنشاء مجموعة — إدخال الاسم
    if waiting == "CREATE_GROUP_NAME":
        name = text
        if not name:
            return await send_kb(update, context, "❌ اسم مجموعة غير صالح. أعد المحاولة.")
        # لازم حساب أولًا
        acc = get_account_by_user(update.effective_user.id)
        if not acc:
            context.user_data.pop("awaiting", None)
            return await send_kb(update, context, "⚠️ أنشئ حسابًا أولًا من الزر 🆕 إنشاء حساب.")
        g = create_group(name, update.effective_user.id)
        context.user_data.pop("awaiting", None)
        return await send_kb(update, context,
            f"✅ تم إنشاء المجموعة: {g['name']}\n🆔 Group ID: {g['group_id']}\n"
            "شارِك الـ Group ID مع أصحابك ليقدروا ينضموا.")

    # الانضمام — إدخال الـ Group ID
    if waiting == "JOIN_GROUP":
        group_id = text.upper().replace(" ", "")
        # حماية من استخدام Account ID بالخطأ
        if group_id.startswith("U"):
            context.user_data.pop("awaiting", None)
            return await send_kb(update, context,
                "❌ ده Account ID (يبدأ بـ U). المطلوب **Group ID** (يبدأ بـ G).")
        g = get_group(group_id)
        if not g:
            context.user_data.pop("awaiting", None)
            return await send_kb(update, context, "❌ لم أجد مجموعة بهذا الـID. تأكد منه وحاول مرة أخرى.")
        # لازم حساب
        acc = get_account_by_user(update.effective_user.id)
        if not acc:
            context.user_data.pop("awaiting", None)
            return await send_kb(update, context, "⚠️ أنشئ حسابًا أولًا من الزر 🆕 إنشاء حساب.")
        add_member(group_id, update.effective_user.id)
        context.user_data.pop("awaiting", None)
        return await send_kb(update, context, f"✅ تم انضمامك إلى المجموعة: {g['name']} ({g['group_id']})")

    # ===== أزرار الكيبورد =====
    if text == BTN_CREATE_ACC:
        acc = get_account_by_user(update.effective_user.id)
        if acc:
            return await send_kb(update, context, f"لديك حساب بالفعل:\nالاسم: {acc['name']}\n🆔 Account ID: {acc['account_id']}")
        context.user_data["awaiting"] = "CREATE_NAME"
        return await send_kb(update, context, "✍️ اكتب اسمك الآن (رسالة واحدة).")

    if text == BTN_CREATE_GROUP:
        # لازم حساب أولًا
        if not get_account_by_user(update.effective_user.id):
            return await send_kb(update, context, "⚠️ أنشئ حسابًا أولًا من الزر 🆕 إنشاء حساب.")
        context.user_data["awaiting"] = "CREATE_GROUP_NAME"
        return await send_kb(update, context, "✍️ اكتب اسم المجموعة الآن (رسالة واحدة).")

    if text == BTN_JOIN_GROUP:
        context.user_data["awaiting"] = "JOIN_GROUP"
        return await send_kb(update, context, "✍️ اكتب **ID المجموعة** الآن (مثال: GABC123).")

    if text == BTN_MY_ACC:
        acc = get_account_by_user(update.effective_user.id)
        if not acc:
            return await send_kb(update, context, "لا يوجد حساب بعد. استخدم زر 🆕 إنشاء حساب.")
        groups = my_groups(update.effective_user.id)
        extra = ""
        if groups:
            extra = "\n\nمجموعاتك:\n" + "\n".join([f"- {g['name']} ({g['group_id']})" for g in groups])
        return await send_kb(update, context, f"الاسم: {acc['name']}\n🆔 Account ID: {acc['account_id']}{extra}")

    if text == BTN_HELP or text == "/help":
        return await cmd_help(update, context)

    # أي نص آخر
    return await send_kb(update, context, f"إنت كتبت: {text}\nاستخدم الأزرار بالأسفل.")

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))