# bot_handlers.py
import os, base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from user_store import upsert_user
from team_store import create_team, request_join, approve, deny, get_team, my_team

OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # لازم تضيفها في Render

# ===== Utilities =====
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii")

def _unb64(s: str) -> str:
    return base64.urlsafe_b64decode(s.encode("ascii")).decode("utf-8")

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

# ===== Basic =====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text(
        "أهلاً! ⚡️\n"
        "• ID بتاعك: {}\n"
        "جرّب:\n"
        "  /myid — عرض ID قابل للنسخ\n"
        "  /setteam اسم_الفريق — إنشاء/تحديد فريق (للمالك)\n"
        "  /join اسم_الفريق — طلب انضمام للفريق\n"
        "  /help — المساعدة"
        .format(update.effective_user.id)
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text(
        "الأوامر:\n"
        "/myid — يعرض ID بشكل واضح للنسخ\n"
        "/setteam <اسم_الفريق> — المالك يحدد/ينشئ فريق\n"
        "/join <اسم_الفريق> — ترسل طلب انضمام للمالك\n"
        "/about — عن البوت\n"
        "أي رسالة نصية هاردّ عليها عادي."
    )

async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text("بوت فريق تيليجرام — ID قابل للنسخ + فرق وطلبات انضمام ✅")

# ===== New: /myid =====
async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    uid = update.effective_user.id
    # نص واضح وقابل للنسخ (ايفون ينسخ بسهولة بالضغط المطوّل)
    text = f"🆔 الـ ID بتاعك:\n{uid}\n\n"
    t = my_team(uid)
    if t:
        text += f"👥 فريقك الحالي: {t['name']}"
    kb = [
        [InlineKeyboardButton("اختيار اسم فريق", callback_data="SHOW_SETTEAM")],
        [InlineKeyboardButton("طلب الانضمام لفريق", callback_data="SHOW_JOIN")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

# أزرار مساعدة لعرض تلميحات الكتابة
async def on_show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    q = update.callback_query
    await q.answer()
    if q.data == "SHOW_SETTEAM":
        await q.message.reply_text("اكتب الأمر بالشكل:\n/setteam اسم_الفريق")
    elif q.data == "SHOW_JOIN":
        await q.message.reply_text("اكتب الأمر بالشكل:\n/join اسم_الفريق")

# ===== New: /setteam =====
async def cmd_setteam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    if OWNER_ID == 0:
        await update.message.reply_text("⚠️ لازم تضيف OWNER_ID في متغيرات البيئة أولاً.")
        return
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("هذه العملية للمالك فقط.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("اكتب بالشكل: /setteam اسم_الفريق")
        return
    name = " ".join(args).strip()
    create_team(name, OWNER_ID)
    await update.message.reply_text(f"✅ تم تعيين/إنشاء الفريق: {name}")

# ===== New: /join =====
async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    args = context.args
    if not args:
        await update.message.reply_text("اكتب بالشكل: /join اسم_الفريق")
        return
    team_name = " ".join(args).strip()
    try:
        request_join(team_name, update.effective_user.id)
    except ValueError as e:
        code = str(e)
        if code == "TEAM_NOT_FOUND":
            await update.message.reply_text("❌ الفريق غير موجود. اطلب من المالك إنشاؤه بـ /setteam")
        elif code == "ALREADY_MEMBER":
            await update.message.reply_text("✅ أنت بالفعل عضو في هذا الفريق.")
        else:
            await update.message.reply_text("حدث خطأ. حاول لاحقًا.")
        return

    await update.message.reply_text("📨 تم إرسال طلب الانضمام للمالك. سنبلغك بعد الموافقة.")

    # ارسال إشعار للمالك مع أزرار موافقة/رفض
    if OWNER_ID:
        uid = update.effective_user.id
        uname = update.effective_user.username or update.effective_user.full_name
        payload = _b64(f"{team_name}|{uid}")
        kb = [[
            InlineKeyboardButton("✅ موافقة", callback_data=f"APPROVE:{payload}"),
            InlineKeyboardButton("✖️ رفض", callback_data=f"DENY:{payload}")
        ]]
        text = f"طلب انضمام جديد:\nفريق: {team_name}\nالمستخدم: {uname} (ID: {uid})"
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=text, reply_markup=InlineKeyboardMarkup(kb))
        except Exception:
            # لو المالك لسه ما بدأش محادثة مع البوت
            await update.message.reply_text("⚠️ تأكد أن المالك بدأ محادثة مع البوت ليستقبل الإشعارات.")

# ===== Callbacks (approve/deny) =====
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
        await q.edit_message_text(f"✅ تم قبول العضو {uid} في فريق {team_name}.")
        try:
            await context.bot.send_message(chat_id=uid, text=f"🎉 تم قبولك في فريق {team_name}. أهلاً بك!")
        except Exception:
            pass
    elif action == "DENY":
        deny(team_name, uid)
        await q.edit_message_text(f"تم رفض طلب {uid} للانضمام إلى {team_name}.")
        try:
            await context.bot.send_message(chat_id=uid, text=f"عذرًا، تم رفض طلب الانضمام إلى فريق {team_name}.")
        except Exception:
            pass

# ===== Fallback echo =====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text(f"إنت كتبت: {update.message.text or ''}")

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("about", cmd_about))
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("setteam", cmd_setteam))
    app.add_handler(CommandHandler("join", cmd_join))

    app.add_handler(CallbackQueryHandler(on_show_menu, pattern="^SHOW_(SETTEAM|JOIN)$"))
    app.add_handler(CallbackQueryHandler(on_decision, pattern="^(APPROVE|DENY):"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))