# bot_handlers.py
import base64, re
from typing import Optional
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

from account_store import create_or_update_account, get_account_by_user, set_username, get_display
from group_store   import (
    create_group, get_group, request_join, approve_join, deny_join,
    my_groups, list_members, is_owner, add_member, remove_member, owner_group
)
from user_index    import upsert as idx_upsert, find_by_username, find_by_phone

# ===== الكيبورد =====
BTN_ADMIN = "🛠️ الإدارة"

# داخل الإدارة (تُعرض ديناميكيًا حسب الحالة)
BTN_CREATE_ACC   = "🆕 إنشاء حساب"
BTN_CREATE_GROUP = "➕ إنشاء مجموعة"
BTN_JOIN_GROUP   = "👥 طلب انضمام"
BTN_MY_ACC       = "🆔 حسابي"
BTN_MY_GROUPS    = "📂 مجموعاتي"
BTN_MEMBERS      = "👥 أعضاء مجموعتي"
BTN_ADD_MEMBER   = "➕ إضافة عضو"
BTN_REM_MEMBER   = "➖ إزالة عضو"
BTN_INVITE       = "📨 دعوة لشخص"
BTN_BACK         = "↩︎ رجوع"
BTN_HELP         = "ℹ️ مساعدة"

def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(BTN_ADMIN)]], resize_keyboard=True)

def admin_kb(user_id: int) -> ReplyKeyboardMarkup:
    rows = []
    acc = get_account_by_user(user_id)
    groups = my_groups(user_id)
    own = owner_group(user_id)

    # صف 1: حساب + إنشاء مجموعة (لو عنده حساب ولم يملك مجموعة بعد)
    rows.append([KeyboardButton(BTN_CREATE_ACC), KeyboardButton(BTN_MY_ACC)])
    if acc and not own:
        rows[0].append(KeyboardButton(BTN_CREATE_GROUP))

    # صف 2: الانضمام + مجموعاتي
    rows.append([KeyboardButton(BTN_JOIN_GROUP), KeyboardButton(BTN_MY_GROUPS)])

    # صف 3: أدوات الأعضاء (تظهر لو عضو بأي مجموعة)
    if groups:
        rows.append([KeyboardButton(BTN_MEMBERS)])

    # صف 4: أدوات المالك فقط
    if own:
        rows.append([KeyboardButton(BTN_ADD_MEMBER), KeyboardButton(BTN_REM_MEMBER)])
        rows.append([KeyboardButton(BTN_INVITE)])

    # صف 5: مساعدة + رجوع
    rows.append([KeyboardButton(BTN_HELP), KeyboardButton(BTN_BACK)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

async def show_main(update: Update, context: ContextTypes.DEFAULT_TYPE, text="اختر من القائمة:"):
    await send_text(update, context, text, main_kb())

async def show_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, text="قائمة الإدارة:"):
    await send_text(update, context, text, admin_kb(update.effective_user.id))

async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, kb: ReplyKeyboardMarkup):
    if update.message:
        await update.message.reply_text(text, reply_markup=kb)
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=kb)

# ===== أوامر =====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    idx_upsert(user.id, username=user.username)
    set_username(user.id, user.username)
    await show_main(update, context, "أهلًا 👋")

async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main(update, context, "✅ version: admin-dynamic v1.0")

# ===== حالات الويزارد =====
def reset_state(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("state", None)
def state(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.user_data.setdefault("state", {})

# ===== منطق النص =====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = (msg.text or "").strip()
    user = update.effective_user

    idx_upsert(user.id, username=user.username)  # تحديث فهرس المستخدم

    st = state(context)
    if st.get("action"):
        return await handle_wizard(update, context, text, st)

    if text == BTN_ADMIN:
        return await show_admin(update, context)

    if text == BTN_BACK:
        reset_state(context)
        return await show_main(update, context, "رجعت للقائمة الرئيسية.")

    # === أزرار الإدارة (تعرض حسب الحالة تلقائيًا) ===
    if text == BTN_CREATE_ACC:
        acc = get_account_by_user(user.id)
        if acc:
            return await show_admin(update, context, f"لديك حساب بالفعل: {get_display(user.id)}\n🆔 {acc['account_id']}")
        st.update({"action": "CREATE_ACC", "step": "ASK_NAME"})
        return await send_text(update, context, "✍️ اكتب اسمك الآن (رسالة واحدة).", admin_kb(user.id))

    if text == BTN_CREATE_GROUP:
        if not get_account_by_user(user.id):
            return await show_admin(update, context, "⚠️ أنشئ حسابًا أولًا.")
        if owner_group(user.id):
            return await show_admin(update, context, "🚫 مسموح بمجموعة واحدة فقط لكل مالك.")
        st.update({"action": "CREATE_GROUP", "step": "ASK_NAME"})
        return await send_text(update, context, "✍️ اكتب اسم المجموعة الآن.", admin_kb(user.id))

    if text == BTN_JOIN_GROUP:
        if not get_account_by_user(user.id):
            return await show_admin(update, context, "⚠️ أنشئ حسابًا أولًا.")
        st.update({"action": "JOIN_GROUP", "step": "ASK_GID"})
        return await send_text(update, context, "✍️ اكتب **رقم مجموعة** مكوّن من أرقام فقط (مثال: 825104).", admin_kb(user.id))

    if text == BTN_MY_ACC:
        acc = get_account_by_user(user.id)
        if not acc:
            return await show_admin(update, context, "لا يوجد حساب بعد.")
        groups = my_groups(user.id)
        extra = ""
        if groups:
            extra = "\n\nمجموعاتك:\n" + "\n".join([f"- {g['name']} ({g['group_id']})" for g in groups])
        return await show_admin(update, context, f"{get_display(user.id)}\n🆔 {acc['account_id']}{extra}")

    if text == BTN_MY_GROUPS:
        groups = my_groups(user.id)
        if not groups:
            return await show_admin(update, context, "🚫 لست عضوًا بأي مجموعة.")
        return await show_admin(update, context, "مجموعاتك:\n" + "\n".join([f"- {g['name']} ({g['group_id']})" for g in groups]))

    if text == BTN_MEMBERS:
        groups = my_groups(user.id)
        if not groups:
            return await show_admin(update, context, "🚫 لست عضوًا بأي مجموعة.")
        if len(groups) == 1:
            return await show_members(update, context, groups[0]["group_id"])
        st.update({"action": "LIST_MEMBERS", "step": "ASK_GID"})
        return await send_text(update, context, "اكتب رقم المجموعة لعرض الأعضاء.", admin_kb(user.id))

    if text == BTN_ADD_MEMBER:
        own = owner_group(user.id)
        if not own:
            return await show_admin(update, context, "🚫 هذه الخاصية للمالك فقط.")
        st.update({"action": "ADD_MEMBER", "step": "ASK_USER", "gid": own["group_id"]})
        return await send_text(update, context, "ارسل @username أو ID المستخدم لإضافته.", admin_kb(user.id))

    if text == BTN_REM_MEMBER:
        own = owner_group(user.id)
        if not own:
            return await show_admin(update, context, "🚫 هذه الخاصية للمالك فقط.")
        st.update({"action": "REM_MEMBER", "step": "ASK_USER", "gid": own["group_id"]})
        return await send_text(update, context, "ارسل @username أو ID المستخدم لإزالته.", admin_kb(user.id))

    if text == BTN_INVITE:
        own = owner_group(user.id)
        if not own:
            return await show_admin(update, context, "🚫 هذه الخاصية للمالك فقط.")
        st.update({"action": "INVITE", "step": "ASK_TARGET", "gid": own["group_id"]})
        return await send_text(update, context, "أرسل @username أو رقم الهاتف الدولي (+201234567890).", admin_kb(user.id))

    if text == BTN_HELP or text == "/help":
        return await show_admin(update, context,
            "الإدارة ديناميكية حسب دورك: المالك يرى أدوات الإضافة/الإزالة/الدعوة؛ العضو يرى الأعضاء فقط.")

    return await show_main(update, context, f"استخدم زر {BTN_ADMIN} لإظهار الإدارة.")

# ===== الويزارد =====
async def handle_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, st: dict):
    user = update.effective_user
    action, step = st.get("action"), st.get("step")

    # إنشاء حساب
    if action == "CREATE_ACC" and step == "ASK_NAME":
        acc = create_or_update_account(user.id, text, username=user.username)
        reset_state(context)
        return await show_admin(update, context, f"🎉 تم إنشاء حسابك.\n{get_display(user.id)}\n🆔 {acc['account_id']}")

    # إنشاء مجموعة
    if action == "CREATE_GROUP" and step == "ASK_NAME":
        try:
            g = create_group(text, user.id)
        except ValueError as e:
            reset_state(context)
            if str(e) == "ALREADY_OWNER":
                return await show_admin(update, context, "🚫 لديك مجموعة بالفعل. مسموح بواحدة فقط.")
            return await show_admin(update, context, "حدث خطأ أثناء إنشاء المجموعة.")
        reset_state(context)
        return await show_admin(update, context, f"✅ تم إنشاء المجموعة: {g['name']}\n🆔 Group ID: {g['group_id']}")

    # طلب انضمام
    if action == "JOIN_GROUP" and step == "ASK_GID":
        if not re.fullmatch(r"\d{4,10}", text):
            reset_state(context)
            return await show_admin(update, context, "❌ رقم مجموعة غير صالح. أرقام فقط.")
        gid = text
        g = get_group(gid)
        if not g:
            reset_state(context)
            return await show_admin(update, context, "❌ لم أجد مجموعة بهذا الرقم.")
        try:
            request_join(gid, user.id)
        except ValueError as e:
            reset_state(context)
            if str(e) == "ALREADY_MEMBER":
                return await show_admin(update, context, "✅ أنت بالفعل عضو.")
            return await show_admin(update, context, "حدث خطأ، حاول لاحقًا.")
        payload = base64.urlsafe_b64encode(f"{gid}|{user.id}".encode()).decode()
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ موافقة", callback_data=f"APPROVE_G:{payload}"),
            InlineKeyboardButton("✖️ رفض",    callback_data=f"DENY_G:{payload}")
        ]])
        uname = user.username or user.full_name
        try:
            await context.bot.send_message(
                g["owner_user_id"],
                f"📨 طلب انضمام جديد إلى {g['name']} ({g['group_id']}):\n"
                f"المستخدم: {uname} (ID: {user.id})",
                reply_markup=kb
            )
        except Exception:
            pass
        reset_state(context)
        return await show_admin(update, context, "تم إرسال طلبك للمالك. انتظر الموافقة ✅")

    # عرض الأعضاء لمجموعة يحددها المستخدم
    if action == "LIST_MEMBERS" and step == "ASK_GID":
        gid = text.strip()
        reset_state(context)
        return await show_members(update, context, gid)

    # إضافة عضو (المالك فقط)
    if action == "ADD_MEMBER" and step == "ASK_USER":
        gid = st.get("gid")
        uid = await resolve_user_id(text)
        if not uid:
            reset_state(context)
            return await show_admin(update, context, "لم أجد هذا المستخدم.")
        add_member(gid, uid)
        reset_state(context)
        return await show_admin(update, context, f"✅ تمت إضافة {await display_user(uid)} إلى المجموعة {gid}.")

    # إزالة عضو (المالك فقط)
    if action == "REM_MEMBER" and step == "ASK_USER":
        gid = st.get("gid")
        uid = await resolve_user_id(text)
        if not uid:
            reset_state(context)
            return await show_admin(update, context, "لم أجد هذا المستخدم.")
        remove_member(gid, uid)
        reset_state(context)
        return await show_admin(update, context, f"✅ تمت إزالة {await display_user(uid)} من المجموعة {gid}.")

    # دعوة شخص
    if action == "INVITE" and step == "ASK_TARGET":
        gid = st.get("gid")
        uname, phone = parse_target(text)
        me = await context.bot.get_me()
        invite_link = f"https://t.me/{me.username}?start=join_{gid}"
        ok = False
        target_id: Optional[int] = None
        if uname:
            target_id = find_by_username(uname)
        elif phone:
            target_id = find_by_phone(phone)
        if target_id:
            try:
                await context.bot.send_message(
                    target_id,
                    f"📨 دعوة للانضمام إلى مجموعة رقم: {gid}\nاضغط: {invite_link}"
                )
                ok = True
            except Exception:
                ok = False
        reset_state(context)
        if ok:
            return await show_admin(update, context, "✅ تم إرسال الدعوة مباشرة.")
        else:
            return await show_admin(update, context, f"شارك هذا الرابط مع الشخص:\n{invite_link}")

    # fallback
    reset_state(context)
    return await show_admin(update, context, "تم إلغاء العملية.")

# ===== دعم =====
async def resolve_user_id(text: str) -> Optional[int]:
    text = text.strip()
    if re.fullmatch(r"\d{5,12}", text):
        return int(text)
    if text.startswith("@"):
        return find_by_username(text[1:])
    return None

async def display_user(user_id: int) -> str:
    return get_display(user_id)

async def show_members(update: Update, context: ContextTypes.DEFAULT_TYPE, gid: str):
    g = get_group(gid)
    if not g:
        return await show_admin(update, context, "❌ لم أجد هذه المجموعة.")
    uids = list_members(gid)
    if not uids:
        return await show_admin(update, context, f"المجموعة {g['name']} ({gid}) بلا أعضاء.")
    lines = []
    for uid in uids:
        lines.append(f"- {await display_user(uid)} (ID: {uid})")
    return await show_admin(update, context, f"👥 أعضاء {g['name']} ({gid}):\n" + "\n".join(lines))

def parse_target(text: str) -> tuple[Optional[str], Optional[str]]:
    t = text.strip()
    if t.startswith("@"): return (t[1:], None)
    if t.startswith("+") and re.fullmatch(r"\+\d{7,15}", t): return (None, t)
    return (None, None)

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
        await q.edit_message_text(f"✅ تمت الموافقة على {await display_user(uid)}.")
        try: await context.bot.send_message(uid, f"🎉 تم قبولك في {g['name']} (ID: {g['group_id']})")
        except Exception: pass
    else:
        deny_join(gid, uid)
        await q.edit_message_text(f"✖️ تم رفض {await display_user(uid)}.")
        try: await context.bot.send_message(uid, f"عذرًا، تم رفض طلبك للانضمام إلى {g['name']}.")
        except Exception: pass

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(CallbackQueryHandler(on_owner_decision, pattern="^(APPROVE_G|DENY_G):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))