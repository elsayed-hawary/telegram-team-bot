# bot_handlers.py
import base64
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

from account_store import create_or_update_account, get_account_by_user
from group_store   import (
    create_group, get_group, request_join, approve_join, deny_join,
    my_groups, list_members
)

# ===== نصوص الأزرار =====
BTN_CREATE_ACC   = "🆕 إنشاء حساب"
BTN_CREATE_GROUP = "➕ إنشاء مجموعة"
BTN_JOIN_GROUP   = "👥 الانضمام إلى مجموعة"
BTN_MY_ACC       = "🆔 حسابي"
BTN_MEMBERS      = "👥 أعضاء مجموعتي"
BTN_HELP         = "ℹ️ مساعدة"

def build_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(BTN_CREATE_ACC),   KeyboardButton(BTN_CREATE_GROUP)],
        [KeyboardButton(BTN_JOIN_GROUP),   KeyboardButton(BTN_MY_ACC)],
        [KeyboardButton(BTN_MEMBERS)],
        [KeyboardButton(BTN_HELP)],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

async def send_kb(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if update.message:
        await update.message.reply_text(text, reply_markup=build_kb())
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=build_kb())

# ===== أوامر =====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_kb(update, context, "أهلاً 👋\nاختَر من الأزرار بالأسفل.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"• {BTN_CREATE_ACC}: ينشئ حساب (Uxxxxxx) ولا يحتاج مجموعة.\n"
        f"• {BTN_CREATE_GROUP}: يتطلب حسابًا، ينشئ مجموعة (Gxxxxxx) ويجعلُك مالكها.\n"
        f"• {BTN_JOIN_GROUP}: يطلب Group ID ويرسل طلبًا للمالك للموافقة.\n"
        f"• {BTN_MY_ACC}: يعرض حسابك ومجموعاتك.\n"
        f"• {BTN_MEMBERS}: يعرض أعضاء مجموعتك/مجموعاتك.\n"
        "ملاحظة: لا يمكن الانضمام إلا بعد موافقة المالك."
    )
    await send_kb(update, context, msg)

async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_kb(update, context, "✅ version: approvals+members v1.0")

# ===== المنطق النصي والأزرار =====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    waiting = context.user_data.get("awaiting")

    # 1) إنشاء حساب — إدخال الاسم
    if waiting == "CREATE_NAME":
        name = text
        if not name:
            return await send_kb(update, context, "❌ اسم غير صالح. أعد المحاولة.")
        acc = create_or_update_account(update.effective_user.id, name)
        context.user_data.pop("awaiting", None)
        return await send_kb(update, context, f"🎉 تم إنشاء حسابك.\nالاسم: {acc['name']}\n🆔 Account ID: {acc['account_id']}")

    # 2) إنشاء مجموعة — إدخال الاسم (يتطلب حساب)
    if waiting == "CREATE_GROUP_NAME":
        name = text
        if not name:
            return await send_kb(update, context, "❌ اسم مجموعة غير صالح. أعد المحاولة.")
        if not get_account_by_user(update.effective_user.id):
            context.user_data.pop("awaiting", None)
            return await send_kb(update, context, "⚠️ يجب إنشاء حساب أولًا من زر 🆕 إنشاء حساب.")
        g = create_group(name, update.effective_user.id)
        context.user_data.pop("awaiting", None)
        return await send_kb(update, context, f"✅ تم إنشاء المجموعة: {g['name']}\n🆔 Group ID: {g['group_id']}")

    # 3) الانضمام — إدخال Group ID → إرسال للمالك للموافقة
    if waiting == "JOIN_GROUP":
        gid = text.upper().replace(" ", "")
        if gid.startswith("U"):
            context.user_data.pop("awaiting", None)
            return await send_kb(update, context, "❌ هذا Account ID (يبدأ بـ U). المطلوب Group ID (يبدأ بـ G).")
        g = get_group(gid)
        if not g:
            context.user_data.pop("awaiting", None)
            return await send_kb(update, context, "❌ لم أجد مجموعة بهذا الـID.")
        if not get_account_by_user(update.effective_user.id):
            context.user_data.pop("awaiting", None)
            return await send_kb(update, context, "⚠️ أنشئ حسابًا أولًا من زر 🆕 إنشاء حساب.")

        # حفظ الطلب كمعلّق وإرسال زر للمالك
        try:
            request_join(gid, update.effective_user.id)
        except ValueError as e:
            context.user_data.pop("awaiting", None)
            if str(e) == "ALREADY_MEMBER":
                return await send_kb(update, context, "✅ أنت بالفعل عضو في هذه المجموعة.")
            return await send_kb(update, context, "حدث خطأ، حاول لاحقًا.")

        payload = base64.urlsafe_b64encode(f"{gid}|{update.effective_user.id}".encode()).decode()
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ موافقة", callback_data=f"APPROVE_G:{payload}"),
            InlineKeyboardButton("✖️ رفض",    callback_data=f"DENY_G:{payload}")
        ]])
        uname = update.effective_user.username or update.effective_user.full_name
        try:
            await context.bot.send_message(
                g["owner_user_id"],
                f"📨 طلب انضمام جديد للمجموعة {g['name']} ({g['group_id']}):\n"
                f"المستخدم: {uname} (ID: {update.effective_user.id})",
                reply_markup=kb
            )
        except Exception:
            pass

        context.user_data.pop("awaiting", None)
        return await send_kb(update, context, "تم إرسال طلبك للمالك. انتظر الموافقة ✅")

    # ===== الأزرار =====
    if text == BTN_CREATE_ACC:
        acc = get_account_by_user(update.effective_user.id)
        if acc:
            return await send_kb(update, context, f"لديك حساب بالفعل:\nالاسم: {acc['name']}\n🆔 Account ID: {acc['account_id']}")
        context.user_data["awaiting"] = "CREATE_NAME"
        return await send_kb(update, context, "✍️ اكتب اسمك الآن (رسالة واحدة).")

    if text == BTN_CREATE_GROUP:
        if not get_account_by_user(update.effective_user.id):
            return await send_kb(update, context, "⚠️ يجب إنشاء حساب أولًا من زر 🆕 إنشاء حساب.")
        context.user_data["awaiting"] = "CREATE_GROUP_NAME"
        return await send_kb(update, context, "✍️ اكتب اسم المجموعة الآن (رسالة واحدة).")

    if text == BTN_JOIN_GROUP:
        context.user_data["awaiting"] = "JOIN_GROUP"
        return await send_kb(update, context, "✍️ اكتب **ID المجموعة** الآن (مثل: GABC123).")

    if text == BTN_MY_ACC:
        acc = get_account_by_user(update.effective_user.id)
        if not acc:
            return await send_kb(update, context, "لا يوجد حساب بعد. استخدم زر 🆕 إنشاء حساب.")
        groups = my_groups(update.effective_user.id)
        extra = ""
        if groups:
            extra = "\n\nمجموعاتك:\n" + "\n".join([f"- {g['name']} ({g['group_id']})" for g in groups])
        return await send_kb(update, context, f"الاسم: {acc['name']}\n🆔 Account ID: {acc['account_id']}{extra}")

    if text == BTN_MEMBERS:
        groups = my_groups(update.effective_user.id)
        if not groups:
            return await send_kb(update, context, "🚫 لست عضوًا بأي مجموعة.")
        # اعرض أعضاء كل مجموعة أنت فيها
        lines = []
        for g in groups:
            uids = list_members(g["group_id"])
            if not uids:
                lines.append(f"• {g['name']} ({g['group_id']}): لا يوجد أعضاء.")
                continue
            # جِب أسماء لو عندهم حسابات
            from account_store import get_account_by_user as _get_acc
            names = []
            for uid in uids:
                acc = _get_acc(uid)
                names.append(acc["name"] if acc else str(uid))
            lines.append(f"• {g['name']} ({g['group_id']}):\n  - " + "\n  - ".join(names))
        return await send_kb(update, context, "👥 أعضاء مجموعتك/مجموعاتك:\n" + "\n".join(lines))

    if text == BTN_HELP or text == "/help":
        return await cmd_help(update, context)

    return await send_kb(update, context, f"إنت كتبت: {text}\nاستخدم الأزرار بالأسفل.")

# ===== ردود المالك على أزرار الموافقة/الرفض =====
async def on_owner_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        action, payload = q.data.split(":", 1)
        gid, uid_str = base64.urlsafe_b64decode(payload.encode()).decode().split("|", 1)
        uid = int(uid_str)
    except Exception:
        return await q.edit_message_text("بيانات غير صالحة.")
    g = get_group(gid)
    if not g:
        return await q.edit_message_text("المجموعة غير موجودة.")
    if update.effective_user.id != g["owner_user_id"]:
        return await q.edit_message_text("هذه الأزرار للمالك فقط.")

    if action == "APPROVE_G":
        approve_join(gid, uid)
        await q.edit_message_text(f"✅ تمت الموافقة على انضمام {uid} إلى {g['name']} ({g['group_id']}).")
        try: await context.bot.send_message(uid, f"🎉 تم قبولك في المجموعة {g['name']} (ID: {g['group_id']})")
        except Exception: pass
    else:
        deny_join(gid, uid)
        await q.edit_message_text(f"✖️ تم رفض طلب {uid}.")
        try: await context.bot.send_message(uid, f"عذرًا، تم رفض طلبك للانضمام إلى {g['name']}.")
        except Exception: pass

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(CallbackQueryHandler(on_owner_decision, pattern="^(APPROVE_G|DENY_G):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))