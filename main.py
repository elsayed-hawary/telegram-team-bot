import os
import sqlite3
import string
import random
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from dotenv import load_dotenv

# ===== إعدادات =====
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "8331353191:AAGnY-ZfvDZZBjBN3qkkmnwCIrporljxEDg")
DB_PATH = os.getenv("DB_PATH", "bot.db")

CHOOSING, WAIT_JOIN_ID = range(2)

# ===== الداتابيز =====
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id TEXT PRIMARY KEY,
            owner_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            team_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner','member')),
            joined_at TEXT NOT NULL,
            PRIMARY KEY (team_id, user_id),
            FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

def gen_team_id(length=6):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(random.choice(alphabet) for _ in range(length))

def user_in_any_team(user_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT team_id, role FROM team_members WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def create_team_for_user(user_id: int):
    conn = db()
    cur = conn.cursor()
    while True:
        tid = gen_team_id()
        cur.execute("SELECT 1 FROM teams WHERE team_id = ?", (tid,))
        if not cur.fetchone():
            break
    now = datetime.now(timezone.utc).isoformat()
    cur.execute("INSERT INTO teams(team_id, owner_user_id, created_at) VALUES (?,?,?)",
                (tid, user_id, now))
    cur.execute("INSERT INTO team_members(team_id, user_id, role, joined_at) VALUES (?,?,?,?)",
                (tid, user_id, 'owner', now))
    conn.commit()
    conn.close()
    return tid

def add_member_to_team(team_id: str, user_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT team_id FROM teams WHERE team_id = ?", (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return False, "لا يوجد فريق بهذا الـ ID."
    cur.execute("SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?", (team_id, user_id))
    if cur.fetchone():
        conn.close()
        return True, "أنت بالفعل عضو في هذا الفريق."
    now = datetime.now(timezone.utc).isoformat()
    cur.execute("INSERT INTO team_members(team_id, user_id, role, joined_at) VALUES (?,?,?,?)",
                (team_id, user_id, 'member', now))
    conn.commit()
    conn.close()
    return True, "تم انضمامك للفريق بنجاح ✅"

def get_team_members(team_id: str):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT tm.user_id, tm.role, t.owner_user_id
        FROM team_members tm
        JOIN teams t ON t.team_id = tm.team_id
        WHERE tm.team_id = ?
        ORDER BY CASE WHEN tm.role='owner' THEN 0 ELSE 1 END, tm.user_id
    """, (team_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_user_team(user_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.team_id, t.owner_user_id
        FROM team_members tm
        JOIN teams t ON t.team_id = tm.team_id
        WHERE tm.user_id = ?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def leave_team(user_id: int):
    ut = get_user_team(user_id)
    if not ut:
        return False, "أنت غير منضم لأي فريق."
    team_id, owner_id = ut
    if owner_id == user_id:
        return False, "أنت مالك الفريق، لا يمكنك المغادرة قبل نقل الملكية (غير مدعوم حالياً)."
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM team_members WHERE team_id = ? AND user_id = ?", (team_id, user_id))
    conn.commit()
    conn.close()
    return True, f"تم خروجك من الفريق {team_id}."

# ===== واجهة البوت =====
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("إنشاء حساب رئيسي 🧭", callback_data="create_main")],
        [InlineKeyboardButton("الانضمام إلى حساب 👥", callback_data="join_team")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "أهلاً بيك! 👋\n"
        "عايز تعمل حساب رئيسي جديد وتاخد Team ID خاص بيك؟ ولا عايز تنضم لحساب موجود؟\n\n"
        "اختار من تحت:"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu_keyboard())
    return CHOOSING

async def handle_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    user_id = query.from_user.id

    if choice == "create_main":
        exists = user_in_any_team(user_id)
        if exists:
            team_id, role = exists
            msg = (
                f"إنت بالفعل منضم لفريق: {team_id}\n"
                f"دورك الحالي: {('مالك' if role=='owner' else 'عضو')}.\n"
                "لو محتاج Team ID بتاعك: استخدم /myteam\n"
                "ولو عايز تشوف الأعضاء: استخدم /members"
            )
            await query.edit_message_text(msg, reply_markup=main_menu_keyboard())
            return CHOOSING

        new_tid = create_team_for_user(user_id)
        msg = (
            "تم إنشاء الحساب الرئيسي بنجاح! ✅\n"
            f"ده **Team ID** الخاص بيك: `{new_tid}`\n\n"
            "إبعته للي عايزهم ينضموا معاك.\n"
            "الأوامر المفيدة:\n"
            "- /myteam لعرض فريقك\n"
            "- /members لعرض الأعضاء"
        )
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        return CHOOSING

    elif choice == "join_team":
        await query.edit_message_text(
            "من فضلك ابعتلي دلوقتي **Team ID** علشان أضمّك للفريق.",
            parse_mode="Markdown"
        )
        return WAIT_JOIN_ID

async def receive_join_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = (update.message.text or "").strip().upper()

    if user_in_any_team(user_id):
        await update.message.reply_text("إنت بالفعل منضم لفريق. استخدم /myteam لمعرفة التفاصيل.")
        return ConversationHandler.END

    if not text or len(text) < 4 or len(text) > 12:
        await update.message.reply_text("صيغة Team ID غير صحيحة. ابعت الكود اللي شكله زي: ABC123")
        return WAIT_JOIN_ID

    ok, msg = add_member_to_team(text, user_id)
    await update.message.reply_text(msg)
    return ConversationHandler.END

async def cmd_myteam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ut = get_user_team(user_id)
    if not ut:
        await update.message.reply_text("أنت غير منضم لأي فريق. استخدم /start واختر إنشاء أو انضمام.")
        return
    team_id, owner_id = ut
    role = "مالك" if owner_id == user_id else "عضو"
    await update.message.reply_text(f"Team ID: {team_id}\nدورك: {role}")

async def cmd_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ut = get_user_team(user_id)
    if not ut:
        await update.message.reply_text("أنت غير منضم لأي فريق.")
        return
    team_id, owner_id = ut
    rows = get_team_members(team_id)
    if not rows:
        await update.message.reply_text("لا يوجد أعضاء (غريب!)")
        return
    lines = [f"أعضاء الفريق {team_id}:"]
    for uid, role, owner_uid in rows:
        tag = "👑 مالك" if role == "owner" else "عضو"
        you = " (أنت)" if uid == user_id else ""
        lines.append(f"- {uid}: {tag}{you}")
    await update.message.reply_text("\n".join(lines))

async def cmd_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ok, msg = leave_team(user_id)
    await update.message.reply_text(msg)

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء. استخدم /start للعودة للقائمة.")
    return ConversationHandler.END

def build_application():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(handle_menu_choice, pattern="^(create_main|join_team)$")],
            WAIT_JOIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_join_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("myteam", cmd_myteam))
    app.add_handler(CommandHandler("members", cmd_members))
    app.add_handler(CommandHandler("leave", cmd_leave))

    return app

if __name__ == "__main__":
    application = build_application()
    print("Bot is running... Press Ctrl+C to stop.")
    application.run_polling(close_loop=False)
