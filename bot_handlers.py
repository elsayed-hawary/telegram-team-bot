# bot_handlers.py
import os, base64
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from user_store import upsert_user
from team_store import create_team, request_join, approve, deny, get_team, my_team

OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ==== Utilities ====
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii")
def _unb64(s: str) -> str:
    return base64.urlsafe_b64decode(s.encode("ascii")).decode("utf-8")

def _menu_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("📋 عرض الـID", callback_data="SHOW_ID")],
        [InlineKeyboardButton("🛠️ تعيين/إنشاء فريق", callback_data="ASK_SETTEAM")],
        [InlineKeyboardButton("➕ طلب الانضمام", callback_data="ASK_JOIN")],
        [InlineKeyboardButton("👥 فريقي", callback_data="SHOW_TEAM")],
        [InlineKeyboardButton("ℹ️ مساعدة", callback_data="SHOW_HELP")],
    ]
    return InlineKeyboardMarkup(kb)

async def _track_user(update: Update):
    tg_user = update.effective_user or (update.message and update.message.from_user)
    if tg_user:
        upsert_user(tg_user)

# ==== Menu ====
async def send_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE, text: str = "اختَر من القائمة:"):
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=_menu_kb())

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await send_menu(update.effective_chat.id, context, text="أهلاً 👋 — دي قائمة الاختيارات:")

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await send_menu(update.effective_chat.id, context)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text(
        "القائمة فيها:\n"
        "• 📋 عرض الـID — يظهر معرفك لنسخه.\n"
        "• 🛠️ تعيين/إنشاء فريق — (للمالك) يحدد اسم الفريق.\n"
        "• ➕ طلب الانضمام — يرسل طلب للمالك مع أزرار موافقة/رفض.\n"
        "• 👥 فريقي — يعرض فريقك الحالي.\n"
        "اكتب /menu لفتح الأزرار في أي وقت."
    )

async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    await update.message.reply_text("بوت فريق تيليجرام — منيو أزرار + إدارة فريق وطلبات انضمام ✅")

# ==== Callbacks from menu ====
async def on_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    q = update.callback_query
    await q.answer()

    data = q.data

    # عرض الـID
    if data == "SHOW_ID":
        uid = update.effective_user.id
        t = my_team(uid)
        txt = f"🆔 الـID بتاعك:\n{uid}"
        if t:
            txt += f"\n👥 فريقك: {t['name']}"
        await q.message.reply_text(txt)

    # طلب اسم لتعيين/إنشاء فريق (للـ OWNER)
    elif data == "ASK_SETTEAM":
        if OWNER_ID == 0:
            await q.message.reply_text("⚠️ لازم تضيف OWNER_ID في متغيرات البيئة أولًا.")
            return
        if update.effective_user.id != OWNER_ID:
            await q.message.reply_text("هذه العملية للمالك فقط.")
            return
        context.user_data["awaiting"] = "SETTEAM"
        await q.message.reply_text("أرسل اسم الفريق الآن (رسالة واحدة).")

    # طلب اسم للانضمام
    elif data == "ASK_JOIN":
        context.user_data["awaiting"] = "JOIN"
        await q.message.reply_text("أرسل اسم الفريق الذي تريد الانضمام له (رسالة واحدة).")

    # عرض فريقي
    elif data == "SHOW_TEAM":
        t = my_team(update.effective_user.id)
        if not t:
            await q.message.reply_text("🚫 لست عضوًا بأي فريق حاليًا.")
        else:
            members_count = len(t.get("members", []))
            pending_count = len(t.get("pending", []))
            is_owner = (t.get("owner_id") == update.effective_user.id)
            txt = (
                f"👥 فريقك: {t['name']}\n"
                f"المالك: {t['owner_id']}\n"
                f"عدد الأعضاء: {members_count}\n"
                f"طلبات مُعلّقة: {pending_count}\n"
            )
            if is_owner and pending_count:
                txt += "ملاحظـة: هتجيلك رسائل بالموافقـة/الرفض لكل طلب.\n"
            await q.message.reply_text(txt)

    elif data == "SHOW_HELP":
        await q.message.reply_text(
            "• استخدم الأزرار فوق للتحكم.\n"
            "• لو طلبنا اسم فريق: أرسله في رسالة واحدة.\n"
            "• تقدر تكتب /menu في أي وقت لفتح الأزرار."
        )

# ==== Approve / Deny join requests (same as before) ====
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

    from team_store import approve, deny
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

# ==== Handle text when waiting for name ====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _track_user(update)
    waiting = context.user_data.get("awaiting")

    # مالك يرسل اسم لتعيين/إنشاء فريق
    if waiting == "SETTEAM":
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("هذه العملية للمالك فقط.")
            context.user_data.pop("awaiting", None)
            return
        name = (update.message.text or "").strip()
        if not name:
            await update.message.reply_text("أرسل اسمًا صالحًا.")
            return
        create_team(name, OWNER_ID)
        context.user_data.pop("awaiting", None)
        await update.message.reply_text(f"✅ تم تعيين/إنشاء الفريق: {name}")
        await send_menu(update.effective_chat.id, context, "اختَر من القائمة:")

    # أي مستخدم يرسل اسم للانضمام
    elif waiting == "JOIN":
        team_name = (update.message.text or "").strip()
        if not team_name:
            await update.message.reply_text("أرسل اسمًا صالحًا.")
            return
        try:
            request_join(team_name, update.effective_user.id)
        except ValueError as e:
            code = str(e)
            if code == "TEAM_NOT_FOUND":
                await update.message.reply_text("❌ الفريق غير موجود. اطلب من المالك إنشاؤه أولًا.")
            elif code == "ALREADY_MEMBER":
                await update.message.reply_text("✅ أنت بالفعل عضو في هذا الفريق.")
            else:
                await update.message.reply_text("حدث خطأ. حاول لاحقًا.")
            context.user_data.pop("awaiting", None)
            return

        context.user_data.pop("awaiting", None)
        await update.message.reply_text("📨 تم إرسال طلب الانضمام للمالك. سنبلغك بعد الموافقة.")
        # إرسال إشعار للمالك
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
                pass

    else:
        # Echo عادي عندما لا ننتظر شيء
        await update.message.reply_text(f"إنت كتبت: {update.message.text or ''}\nاكتب /menu لفتح الأزرار.")

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("about", cmd_about))

    app.add_handler(CallbackQueryHandler(on_menu_cb, pattern="^(SHOW_ID|ASK_SETTEAM|ASK_JOIN|SHOW_TEAM|SHOW_HELP)$"))
    app.add_handler(CallbackQueryHandler(on_decision, pattern="^(APPROVE|DENY):"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))