# bot_handlers.py
import os, base64
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from team_store import create_team, request_join, approve, deny, my_team

OWNER_ID = int(os.getenv("OWNER_ID", "0"))

BTN_SHOW_ID   = "📋 عرض الـID"
BTN_SET_TEAM  = "🛠️ تعيين/إنشاء فريق"
BTN_JOIN_TEAM = "➕ طلب الانضمام"
BTN_MY_TEAM   = "👥 فريقي"
BTN_HELP      = "ℹ️ مساعدة"

def build_reply_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(BTN_SHOW_ID),  KeyboardButton(BTN_MY_TEAM)],
        [KeyboardButton(BTN_SET_TEAM), KeyboardButton(BTN_JOIN_TEAM)],
        [KeyboardButton(BTN_HELP)]
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii")
def _unb64(s: str) -> str:
    return base64.urlsafe_b64decode(s.encode("ascii")).decode("utf-8")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً 👋 اختَر من الأزرار:", reply_markup=build_reply_kb())

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (f"• {BTN_SHOW_ID} — معرفك.\n"
           f"• {BTN_SET_TEAM} — (للمالك) تعيين/إنشاء فريق.\n"
           f"• {BTN_JOIN_TEAM} — طلب انضمام.\n"
           f"• {BTN_MY_TEAM} — فريقك الحالي.\n"
           "لوحة الأزرار ثابتة تحت.")
    await update.message.reply_text(txt, reply_markup=build_reply_kb())

async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ version: reply-kb v1.0", reply_markup=build_reply_kb())

# === Actions ===
async def act_show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    t = my_team(uid)
    msg = f"🆔 الـID:\n{uid}"
    if t: msg += f"\n👥 فريقك: {t['name']}"
    await update.message.reply_text(msg, reply_markup=build_reply_kb())

async def act_set_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if OWNER_ID == 0 or update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ هذه العملية للمالك فقط.", reply_markup=build_reply_kb())
    context.user_data["awaiting"] = "SETTEAM"
    await update.message.reply_text("✍️ اكتب اسم الفريق الآن:", reply_markup=build_reply_kb())

async def act_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting"] = "JOIN"
    await update.message.reply_text("✍️ اكتب اسم الفريق للانضمام:", reply_markup=build_reply_kb())

async def act_my_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = my_team(update.effective_user.id)
    if not t:
        return await update.message.reply_text("🚫 لست عضوًا بأي فريق.", reply_markup=build_reply_kb())
    txt = (f"👥 فريقك: {t['name']}\n"
           f"المالك: {t['owner_id']}\n"
           f"الأعضاء: {len(t.get('members', []))}\n"
           f"طلبات: {len(t.get('pending', []))}")
    await update.message.reply_text(txt, reply_markup=build_reply_kb())

async def on_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    action, payload = q.data.split(":", 1)
    team_name, uid_str = _unb64(payload).split("|", 1); uid = int(uid_str)
    if update.effective_user.id != OWNER_ID:
        return await q.edit_message_text("للّمالك فقط.")
    if action == "APPROVE":
        approve(team_name, uid); await q.edit_message_text(f"✅ تم قبول {uid} في {team_name}.")
        try: await context.bot.send_message(uid, f"🎉 تم قبولك في {team_name}!")
        except: pass
    else:
        deny(team_name, uid); await q.edit_message_text(f"✖️ تم رفض {uid} لـ {team_name}.")
        try: await context.bot.send_message(uid, f"❌ تم رفض طلبك للانضمام إلى {team_name}.")
        except: pass

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    waiting = context.user_data.get("awaiting")

    if waiting == "SETTEAM":
        create_team(text, OWNER_ID)
        context.user_data.pop("awaiting", None)
        return await update.message.reply_text(f"✅ تم إنشاء الفريق: {text}", reply_markup=build_reply_kb())

    if waiting == "JOIN":
        try:
            request_join(text, update.effective_user.id)
        except ValueError as e:
            code = str(e); msg = "❌ خطأ."
            if code == "TEAM_NOT_FOUND": msg = "❌ الفريق غير موجود."
            elif code == "ALREADY_MEMBER": msg = "✅ أنت بالفعل عضو."
            context.user_data.pop("awaiting", None)
            return await update.message.reply_text(msg, reply_markup=build_reply_kb())

        context.user_data.pop("awaiting", None)
        await update.message.reply_text("📨 تم إرسال الطلب للمالك.", reply_markup=build_reply_kb())
        if OWNER_ID:
            uid = update.effective_user.id
            uname = update.effective_user.username or update.effective_user.full_name
            payload = _b64(f"{text}|{uid}")
            kb = [[
                InlineKeyboardButton("✅ موافقة", callback_data=f"APPROVE:{payload}"),
                InlineKeyboardButton("✖️ رفض",    callback_data=f"DENY:{payload}")
            ]]
            await context.bot.send_message(OWNER_ID,
                f"طلب انضمام:\nفريق: {text}\nالمستخدم: {uname} (ID: {uid})",
                reply_markup=InlineKeyboardMarkup(kb))
        return

    if text == BTN_SHOW_ID:   return await act_show_id(update, context)
    if text == BTN_SET_TEAM:  return await act_set_team(update, context)
    if text == BTN_JOIN_TEAM: return await act_join(update, context)
    if text == BTN_MY_TEAM:   return await act_my_team(update, context)
    if text == BTN_HELP:      return await cmd_help(update, context)

    await update.message.reply_text(f"إنت كتبت: {text}", reply_markup=build_reply_kb())

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(CallbackQueryHandler(on_decision, pattern="^(APPROVE|DENY):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))