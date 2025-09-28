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
from user_store import upsert_user
from team_store import create_team, request_join, approve, deny, get_team, my_team

OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ====== عناوين الأزرار (Reply Keyboard) ======
BTN_SHOW_ID      = "📋 عرض الـID"
BTN_SET_TEAM     = "🛠️ تعيين/إنشاء فريق"
BTN_JOIN_TEAM    = "➕ طلب الانضمام"
BTN_MY_TEAM      = "👥 فريقي"
BTN_HELP         = "ℹ️ مساعدة"
BTN_MENU         = "📎 القائمة"

def build_reply_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(BTN_SHOW_ID),   KeyboardButton(BTN_MY_TEAM)],
        [KeyboardButton(BTN_SET_TEAM),  KeyboardButton(BTN_JOIN_TEAM)],
        [KeyboardButton(BTN_HELP)]
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False, selective=False)

# ===== Utilities =====
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii")
def _unb64(s: str) -> str:
    return base64.urlsafe_b64decode(s.encode("ascii")).decode("utf-8")

async def _track_user(update: Update):
    tg_user = update.effective_user or (update.message and update.message.from_user)
    if tg_user:
        upsert_user(tg_user)

async def _send_with_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE, text: str):
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_reply_kb())

# ===== Basic =====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text("أهلاً 👋", reply_markup=build_reply_kb())
    await _send_with_menu(update.effective_chat.id, context, "اختَر من الأزرار بالأسفل:")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await _send_with_menu(update.effective_chat.id, context,
        "القائمة:\n"
        f"• {BTN_SHOW_ID} — يظهر معرفك لنسخه.\n"
        f"• {BTN_SET_TEAM} — (للمالك) تعيين/إنشاء فريق.\n"
        f"• {BTN_JOIN_TEAM} — إرسال طلب انضمام للمالك.\n"
        f"• {BTN_MY_TEAM} — عرض فريقك الحالي.\n"
        "تقدر تكتب /start أو تضغط «القائمة» في أي وقت.")

async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await _send_with_menu(update.effective_chat.id, context, "بوت فريق تيليجرام — منيو سفلية (Reply Keyboard) + إدارة فريق ✅")

# ===== Actions (من الأزرار) =====
async def act_show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    uid = update.effective_user.id
    t = my_team(uid)
    msg = f"🆔 الـID بتاعك:\n{uid}"
    if t:
        msg += f"\n👥 فريقك: {t['name']}"
    await _send_with_menu(update.effective_chat.id, context, msg)

async def act_set_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    if OWNER_ID == 0:
        await _send_with_menu(update.effective_chat.id, context, "⚠️ ضيف OWNER_ID في متغيرات البيئة أولًا.")
        return
    if update.effective_user.id != OWNER_ID:
        await _send_with_menu(update.effective_chat.id, context, "هذه العملية للمالك فقط.")
        return
    context.user_data["awaiting"] = "SETTEAM"
    await _send_with_menu(update.effective_chat.id, context, "أرسل اسم الفريق الآن (رسالة واحدة).")

async def act_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    context.user_data["awaiting"] = "JOIN"
    await _send_with_menu(update.effective_chat.id, context, "أرسل اسم الفريق الذي تريد الانضمام له (رسالة واحدة).")

async def act_my_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    t = my_team(update.effective_user.id)
    if not t:
        await _send_with_menu(update.effective_chat.id, context, "🚫 لست عضوًا بأي فريق حاليًا.")
    else:
        members_count = len(t.get("members", []))
        pending_count = len(t.get("pending", []))
        txt = (
            f"👥 فريقك: {t['name']}\n"
            f"المالك: {t['owner_id']}\n"
            f"عدد الأعضاء: {members_count}\n"
            f"طلبات مُعلّقة: {pending_count}"
        )
        await _send_with_menu(update.effective_chat.id, context, txt)

# ===== Owner decision buttons (Inline) =====
async def on_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    q = update.callback_query
    await q.answer()
    try:
        action, payload = q.data.split(":", 1)
        team_name, uid_str = _unb64(payload).split("|", 1)
        uid = int(uid_str)
    except Exception:
        await q.edit_message_text("بيانات غير صالحة.")
        return
    if update.effective_user.id != OWNER_ID:
        await q.edit_message_text("هذه الأزرار للمالك فقط.")
        return
    if action == "APPROVE":
        approve(team_name, uid)
        await q.edit_message_text(f"✅ تم قبول {uid} في فريق {team_name}.")
        try:
            await context.bot.send_message(chat_id=uid, text=f"🎉 تم قبولك في فريق {team_name}!")
        except Exception:
            pass
    elif action == "DENY":
        deny(team_name, uid)
        await q.edit_message_text(f"✖️ تم رفض طلب {uid} للانضمام إلى {team_name}.")
        try:
            await context.bot.send_message(chat_id=uid, text=f"عذرًا، تم رفض طلب الانضمام إلى فريق {team_name}.")
        except Exception:
            pass

# ===== Text handler (ينفّذ حسب حالة الانتظار أو حسب الأزرار) =====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    text = (update.message.text or "").strip()

    # 1) لو مستنيين إدخال اسم
    waiting = context.user_data.get("awaiting")
    if waiting == "SETTEAM":
        if update.effective_user.id != OWNER_ID:
            await _send_with_menu(update.effective_chat.id, context, "هذه العملية للمالك فقط.")
            context.user_data.pop("awaiting", None)
            return
        if not text:
            await _send_with_menu(update.effective_chat.id, context, "أرسل اسمًا صالحًا.")
            return
        create_team(text, OWNER_ID)
        context.user_data.pop("awaiting", None)
        await _send_with_menu(update.effective_chat.id, context, f"✅ تم تعيين/إنشاء الفريق: {text}")
        return

    if waiting == "JOIN":
        if not text:
            await _send_with_menu(update.effective_chat.id, context, "أرسل اسمًا صالحًا.")
            return
        try:
            request_join(text, update.effective_user.id)
        except ValueError as e:
            code = str(e)
            if code == "TEAM_NOT_FOUND":
                await _send_with_menu(update.effective_chat.id, context, "❌ الفريق غير موجود. اطلب من المالك إنشاؤه أولًا.")
            elif code == "ALREADY_MEMBER":
                await _send_with_menu(update.effective_chat.id, context, "✅ أنت بالفعل عضو في هذا الفريق.")
            else:
                await _send_with_menu(update.effective_chat.id, context, "حدث خطأ. حاول لاحقًا.")
            context.user_data.pop("awaiting", None)
            return

        context.user_data.pop("awaiting", None)
        await _send_with_menu(update.effective_chat.id, context, "📨 تم إرسال طلب الانضمام للمالك.")
        # إرسال إشعار للمالك
        if OWNER_ID:
            uid = update.effective_user.id
            uname = update.effective_user.username or update.effective_user.full_name
            payload = _b64(f"{text}|{uid}")
            kb = [[
                InlineKeyboardButton("✅ موافقة", callback_data=f"APPROVE:{payload}"),
                InlineKeyboardButton("✖️ رفض", callback_data=f"DENY:{payload}")
            ]]
            notify = f"طلب انضمام جديد:\nفريق: {text}\nالمستخدم: {uname} (ID: {uid})"
            try:
                await context.bot.send_message(chat_id=OWNER_ID, text=notify, reply_markup=InlineKeyboardMarkup(kb))
            except Exception:
                pass
        return

    # 2) لو مش مستنيين حاجة — نفّذ حسب نص الزر
    if text == BTN_SHOW_ID:
        await act_show_id(update, context)
    elif text == BTN_SET_TEAM:
        await act_set_team(update, context)
    elif text == BTN_JOIN_TEAM:
        await act_join(update, context)
    elif text == BTN_MY_TEAM:
        await act_my_team(update, context)
    elif text in (BTN_HELP, BTN_MENU, "/menu", "/help"):
        await cmd_help(update, context)
    else:
        # أي نص عادي
        await _send_with_menu(update.effective_chat.id, context, f"إنت كتبت: {text}\nاستخدم الأزرار بالأسفل.")

def register_handlers(app: Application) -> None:
    # أوامر
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("about", cmd_about))
    # قرارات المالك (Inline)
    app.add_handler(CallbackQueryHandler(on_decision, pattern="^(APPROVE|DENY):"))
    # كل النصوص (تفعّل الأزرار الكبيرة + إدخال الأسماء)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))