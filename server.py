# server.py
import os, asyncio
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import uvicorn

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set TELEGRAM_TOKEN env var")

# Telegram app (python-telegram-bot v20+)
tg_app = Application.builder().token(TOKEN).build()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت شغال ✅")

tg_app.add_handler(CommandHandler("start", start_cmd))

# FastAPI web server (for webhook & health)
app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    # schedule processing (non-blocking)
    asyncio.create_task(tg_app.process_update(update))
    return PlainTextResponse("OK", status_code=200)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port)