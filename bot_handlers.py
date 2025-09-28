# bot_handlers.py
import os, base64, logging
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from user_store import upsert_user
from team_store import create_team, request_join, approve, deny, my_team

log = logging.getLogger("replykb")

OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# عناوين الأزرار (Reply Keyboard الكبيرة تحت)
BTN_SHOW_ID   = "📋 عرض الـID"
BTN_SET_TEAM  = "🛠️ تعيين/إنشاء فريق"
BTN_JOIN_TEAM = "➕ طلب الانضمام"
BTN_MY_TEAM   = "👥 فريقي"
BTN_HELP      = "ℹ️ مساعدة"

def build_reply_kb() -> ReplyKeyboardMarkup:
    """كيبوردة كبيرة تحت، 3 صفوف."""
    rows = [
        [KeyboardButton(BTN_SHOW_ID),  KeyboardButton(BTN_MY_TEAM)],
        [KeyboardButton(BTN_SET_TEAM), KeyboardButton(BTN_JOIN_TEAM)],
        [KeyboardButton(BTN_HELP)]
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

# أدوات صغيرة
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii")
def _unb64(s: str) -> str:
    return base64.urlsafe_b64decode(s.encode("ascii")).decode("utf-8")

async def _track_user(update: Update):
    u = update.effective_user or (update.message and update.message.from_user)
    if u:
        upsert_user(u)

async def _send(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, text: str):
    """أي رسالة من البوت لازم ترجع ومعاها الكيبورد الكبيرة."""
    await ctx.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_reply_kb())

# ===== أوامر أساسية =====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await _send(update.effective_chat.id, context, "أهلاً 👋 اختَر من الأزرار بالأسفل:")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await _send(update.effective_chat.id, context,
        f"• {BTN_SHOW_ID} — يظهر معرفك.\n"
        f"• {BTN_SET_TEAM} — (للمالك) تعيين/إنشاء فريق.\n"
        f"• {BTN_JOIN_TEAM} — إرسال طلب انضمام.\n"
        f"• {BTN_MY_TEAM} — عرض فريقك.\n"
        "لوحة الأزرار ثابتة تحت. لو ما ظهرتش، ابعت /start.")

async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await _send(update.effective_chat.id, context, "Reply Keyboard مفعلة + إدارة فرق وطلبات الانضمام ✅")

# للتأكد إن النسخة الجديدة شغالة
async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await _send(update.effective_chat.id, context, "✅ version: reply-kb v1.0")

# ===== أفعال الأزرار =====
async def act_show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    uid = update.effective_user.id
    t = my_team(uid)
    msg = f"🆔 الـID:\n{uid}"
    if t:
        msg += f"\n👥 فريقك: {t['name']}"
    await _send(update.effective_chat.id, context, msg)

async def act_set_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    if OWNER_ID == 0:
        return await _send(update.effective_chat.id, context, "⚠️ ضيف OWNER_ID في Environment أولًا.")
    if update.effective_user.id != OWNER_ID:
        return await _send(update.effective_chat.id, context, "هذه العملية للمالك فقط.")
    context.user_data["awaiting"] = "SETTEAM"
    await _send(update.effective_chat.id, context, "اكتب اسم الفريق الآن (رسالة واحدة).")

async def act_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    context.user_data["awaiting"] = "JOIN"
    await _send(update.effective_chat.id, context, "اكتب اسم الفريق الذي تريد الانضمام له (رسالة واحدة).")

async def act_my_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    t = my_team(update.effective_user.id)
    if not t:
        return await _send(update.effective_chat.id, context, "🚫 لست عضوًا بأي فريق.")
    txt = (f"👥 فريقك: {t['name']}\n"
           f"المالك: {t['owner_id']}\n"
           f"عدد الأعضاء: {len(t.get('members', []))}\n"
           f"طلبات مُعلّقة: {len(t.get('pending', []))}")
    await _send(update.effective_chat.id, context, txt)

# ===== قرارات المالك (Inline في إشعار خاص بالمالك) =====
async def on_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    q = update.callback_query
    await q.answer()
    try:
        action, payload = q.data.split(":", 1)
        team_name, uid_str = _unb64(payload).split("|", 1)
        uid = int(uid_str)
    except Exception:
        return await q.edit_message_text("بيانات غير صالحة.")

    if update.effective_user.id != OWNER_ID:
        return await q.edit_message_text("للـمالك فقط.")

    if action == "APPROVE":
        approve(team_name, uid)
        await q.edit_message_text(f"✅ تم قبول {uid} في {team_name}.")
        try: await context.bot.send_message(uid, f"🎉 تم قبولك في {team_name}!")
        except Exception: pass
    else:
        deny(team_name, uid)
        await q.edit_message_text(f"✖️ تم رفض طلب {uid} لـ {team_name}.")
        try: await context.bot.send_message(uid, f"عذرًا، تم رفض طلبك للانضمام إلى {team_name}.")
        except Exception: pass

# ===== استقبال النصوص (الأزرار + إدخالات الأسماء) =====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    text = (update.message.text or "").strip()

    # إدخال اسم الفريق (انتظار)
    waiting = context.user_data.get("awaiting")
    if waiting == "SETTEAM":
        if update.effective_user.id != OWNER_ID:
            context.user_data.pop("awaiting", None)
            return await _send(update.effective_chat.id, context, "هذه العملية للمالك فقط.")
        if not text:
            return await _send(update.effective_chat.id, context, "أرسل اسمًا صالحًا.")
        create_team(text, OWNER_ID)
        context.user_data.pop("awaiting", None)
        return await _send(update.effective_chat.id, context, f"✅ تم تعيين/إنشاء الفريق: {text}")

    if waiting == "JOIN":
        if not text:
            return await _send(update.effective_chat.id, context, "أرسل اسمًا صالحًا.")
        try:
            request_join(text, update.effective_user.id)
        except ValueError as e:
            code = str(e)
            msg = "حدث خطأ. حاول لاحقًا."
            if code == "TEAM_NOT_FOUND": msg = "❌ الفريق غير موجود."
            elif code == "ALREADY_MEMBER": msg = "✅ أنت بالفعل عضو في هذا الفريق."
            context.user_data.pop("awaiting", None)
            return await _send(update.effective_chat.id, context, msg)

        context.user_data.pop("awaiting", None)
        await _send(update.effective_chat.id, context, "📨 تم إرسال الطلب للمالك.")
        # إشعار للمالك
        if OWNER_ID:
            uid = update.effective_user.id
            uname = update.effective_user.username or update.effective_user.full_name
            payload = _b64(f"{text}|{uid}")
            kb = [[
                InlineKeyboardButton("✅ موافقة", callback_data=f"APPROVE:{payload}"),
                InlineKeyboardButton("✖️ رفض",    callback_data=f"DENY:{payload}")
            ]]
            try:
                await context.bot.send_message(OWNER_ID,
                    f"طلب انضمام جديد:\nفريق: {text}\nالمستخدم: {uname} (ID: {uid})",
                    reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                pass
        return

    # تنفيذ حسب نص الزر
    if text == BTN_SHOW_ID:   return await act_show_id(update, context)
    if text == BTN_SET_TEAM:  return await act_set_team(update, context)
    if text == BTN_JOIN_TEAM: return await act_join(update, context)
    if text == BTN_MY_TEAM:   return await act_my_team(update, context)
    if text == BTN_HELP:      return await cmd_help(update, context)

    # أي نص عادي
    await _send(update.effective_chat.id, context, f"إنت كتبت: {text}\nاستخدم الأزرار بالأسفل.")

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("about",   cmd_about))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(CallbackQueryHandler(on_decision, pattern="^(APPROVE|DENY):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))