# bot_handlers.py
import base64
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

from team_store import (
    new_team, set_team_name, get_team_by_id,
    request_join, approve, deny, my_team
)

# أزرار الكيبورد الجديدة
BTN_CREATE = "🆕 إنشاء حساب/مجموعة"
BTN_JOIN   = "👥 الانضمام إلى مجموعة"
BTN_MYID   = "🆔 حسابي"
BTN_MYTEAM = "👥 مجموعتي"
BTN_HELP   = "ℹ️ مساعدة"

def reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_CREATE), KeyboardButton(BTN_JOIN)],
            [KeyboardButton(BTN_MYID),   KeyboardButton(BTN_MYTEAM)],
            [KeyboardButton(BTN_HELP)]
        ],
        resize_keyboard=True, one_time_keyboard=False
    )

async def _send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    await update.message.reply_text(text, reply_markup=reply_kb())

# أوامر
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send(update, context, "أهلاً 👋\nاختَر من الأزرار بالأسفل.")

async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send(update, context, "✅ version: teams-by-ID v1.0")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send(update, context,
        f"• {BTN_CREATE}: يولّد Team ID ويطلب اسم المجموعة.\n"
        f"• {BTN_JOIN}: يطلب Team ID للانضمام (يذهب للمالك للموافقة).\n"
        f"• {BTN_MYID}: يعرض رقم حسابك.\n"
        f"• {BTN_MYTEAM}: تفاصيل مجموعتك إن وُجدت."
    )

# حالات الإدخال
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    state = context.user_data.get("state")
    if state == "AWAIT_NAME":
        team_id = context.user_data.get("team_id")
        if not team_id:
            context.user_data.clear()
            return await _send(update, context, "حصل خطأ، جرّب إنشاء الحساب مرة أخرى.")
        set_team_name(team_id, text)
        context.user_data.clear()
        return await _send(update, context, f"✅ تم تعيين الاسم: {text}\n🆔 Team ID: {team_id}")

    if state == "AWAIT_JOIN_ID":
        team_id = text.upper().replace(" ", "")
        try:
            t = request_join(team_id, update.effective_user.id)
        except ValueError as e:
            code = str(e)
            if code == "TEAM_NOT_FOUND":
                return await _send(update, context, "❌ Team ID غير صحيح.")
            if code == "ALREADY_MEMBER":
                context.user_data.clear()
                return await _send(update, context, "✅ أنت بالفعل عضو.")
            return await _send(update, context, "حدث خطأ. حاول لاحقًا.")
        context.user_data.clear()
        owner_id = t["owner_id"]
        uid = update.effective_user.id
        uname = update.effective_user.username or update.effective_user.full_name
        payload = base64.urlsafe_b64encode(f"{team_id}|{uid}".encode()).decode()
        kb = [[
            InlineKeyboardButton("✅ موافقة", callback_data=f"APPROVE:{payload}"),
            InlineKeyboardButton("✖️ رفض",    callback_data=f"DENY:{payload}")
        ]]
        try:
            await context.bot.send_message(
                owner_id,
                f"📨 طلب انضمام:\nTeam ID: {team_id}\nالمستخدم: {uname} (ID: {uid})",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except Exception:
            pass
        return await _send(update, context, "تم إرسال الطلب للمالك ✔️")

    # أزرار
    if text == BTN_CREATE:
        team_id = new_team(update.effective_user.id)
        context.user_data["state"] = "AWAIT_NAME"
        context.user_data["team_id"] = team_id
        return await _send(update, context,
            f"🎉 تم إنشاء الحساب!\n🆔 Team ID: {team_id}\n"
            "اكتب اسم المجموعة الآن ليتم تعيينه."
        )

    if text == BTN_JOIN:
        context.user_data["state"] = "AWAIT_JOIN_ID"
        return await _send(update, context, "اكتب Team ID للمجموعة التي تريد الانضمام لها.")

    if text == BTN_MYID:
        return await _send(update, context, f"🆔 ID الخاص بك:\n{update.effective_user.id}")

    if text == BTN_MYTEAM:
        t = my_team(update.effective_user.id)
        if not t:
            return await _send(update, context, "🚫 لست عضوًا بأي مجموعة.")
        name = t['name'] or "— لم يُعيَّن —"
        return await _send(update, context,
            f"👥 مجموعتك:\n• Team ID: {t['id']}\n• الاسم: {name}\n"
            f"• المالك: {t['owner_id']}\n• الأعضاء: {len(t.get('members', []))}\n"
            f"• طلبات معلّقة: {len(t.get('pending', []))}"
        )

    if text == BTN_HELP or text in ("/help", "/menu"):
        return await cmd_help(update, context)

    return await _send(update, context, f"استخدم الأزرار بالأسفل.\n(كتبت: {text})")

# موافقة/رفض
async def on_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        action, payload = q.data.split(":", 1)
        team_id, uid_str = base64.urlsafe_b64decode(payload.encode()).decode().split("|", 1)
        uid = int(uid_str)
    except Exception:
        return await q.edit_message_text("بيانات غير صالحة.")
    t = get_team_by_id(team_id)
    if not t:
        return await q.edit_message_text("المجموعة غير موجودة.")
    if update.effective_user.id != t["owner_id"]:
        return await q.edit_message_text("للّمالك فقط.")
    if action == "APPROVE":
        approve(team_id, uid)
        await q.edit_message_text(f"✅ تم قبول {uid} في {team_id}.")
        try: await context.bot.send_message(uid, f"🎉 تم قبولك في المجموعة (ID: {team_id})")
        except Exception: pass
    else:
        deny(team_id, uid)
        await q.edit_message_text(f"✖️ تم رفض {uid}.")
        try: await context.bot.send_message(uid, f"عذرًا، تم رفض طلبك (ID: {team_id}).")
        except Exception: pass

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(CallbackQueryHandler(on_decision, pattern="^(APPROVE|DENY):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))