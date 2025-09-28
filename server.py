# server.py
import os, asyncio, logging
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
import uvicorn

from telegram import Update
from telegram.ext import Application

from bot_handlers import register_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram-bot")

# === التوكن: من ENV ولو مش موجود هنستخدم احتياطي (غير آمن لكن يمنع سقوط السيرفر) ===
TOKEN = (os.getenv("TELEGRAM_TOKEN") or "8331353191:AAGnY-ZfvDZZBjBN3qkkmnwCIrporljxEDg").strip()
if not TOKEN or ":" not in TOKEN:
    # لو حتى الاحتياطي مش صالح، شغّل السيرفر بدون بوت لتعمل /health
    logger.error("No valid TELEGRAM_TOKEN found. Bot will not start, but health is up.")
    BOT_ENABLED = False
    tg_app = None
else:
    BOT_ENABLED = True
    tg_app = Application.builder().token(TOKEN).build()
    register_handlers(tg_app)
    logger.info("Bot app built. Token hash: %s", hash(TOKEN))

app = FastAPI()

@app.get("/")
async def root():
    return JSONResponse({"msg": "Bot server running", "bot_enabled": BOT_ENABLED})

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "bot_enabled": BOT_ENABLED})

@app.post("/webhook")
async def webhook(request: Request):
    if not BOT_ENABLED or tg_app is None:
        # لو البوت متعطّل، رجّع 503 عشان تعرف من اللوجز
        return PlainTextResponse("BOT_DISABLED", status_code=503)
    try:
        data = await request.json()
        logger.info("📩 Update from Telegram: %s", data)
        update = Update.de_json(data, tg_app.bot)
        asyncio.create_task(tg_app.process_update(update))
        return PlainTextResponse("OK", status_code=200)
    except Exception as e:
        logger.exception("Webhook error: %s", e)
        return PlainTextResponse("ERROR", status_code=500)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port)