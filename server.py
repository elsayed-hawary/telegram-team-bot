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

TOKEN = (os.getenv("TELEGRAM_TOKEN") or "8331353191:AAGnY-ZfvDZZBjBN3qkkmnwCIrporljxEDg").strip()

app = FastAPI()
tg_app: Application | None = None

@app.on_event("startup")
async def on_startup():
    global tg_app
    tg_app = Application.builder().token(TOKEN).build()
    register_handlers(tg_app)
    # أهم سطر ↓
    await tg_app.initialize()
    logger.info("✅ Telegram bot initialized")

@app.get("/")
async def root():
    return JSONResponse({"msg": "Bot server running"})

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})

@app.post("/webhook")
async def webhook(request: Request):
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