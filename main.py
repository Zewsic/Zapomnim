import asyncio
import logging
import traceback
from contextlib import asynccontextmanager
from typing import Final

import uvicorn
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.utils.i18n import I18n
from aiogram.types import MenuButtonCommands

from config import WEBHOOK_HOST, BOT_TOKEN, TELEGRAM_SERVER
from database import RedisSession, create_tables
from handlers import (
    initial_setup_router, settings_router, process_message_router,
    delete_messages_router, edit_messages_router, data_management_router, subscription_router,
    menu_router, statistics_router, STA_router, chat_export_router, voice_transcribe_router
)
from utils import PatchedI18nMiddleware, set_bot_commands, admin_api_router
from utils.anti_ddos import DistributedThrottleMiddleware, ThrottleConfig

BOT_TOKEN: Final[str] = BOT_TOKEN
WEBHOOK_URL: Final[str] = f"http://{WEBHOOK_HOST}/webhook/main"


main_bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=AiohttpSession(api=TELEGRAM_SERVER)
)

i18n = I18n(
    path="locales",
    default_locale="en",
    domain="zapomnim"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await main_bot.set_webhook(
        WEBHOOK_URL,
        allowed_updates=[
            "message", "callback_query", "business_connection", "business_message",
            "deleted_business_messages", "edited_business_message", "pre_checkout_query"
        ]
    )
    await set_bot_commands(main_bot)
    await main_bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("Bot webhook and commands set.")
    yield
    await main_bot.delete_webhook()
    logger.info("Webhook deleted on shutdown.")


app = FastAPI(lifespan=lifespan)

dp = Dispatcher(storage=RedisStorage(redis=RedisSession))

dp.include_routers(
    initial_setup_router,
    process_message_router,
    settings_router,
    delete_messages_router,
    edit_messages_router,
    data_management_router,
    subscription_router,
    statistics_router,
    menu_router,
    STA_router,
    chat_export_router,
    voice_transcribe_router
)

dp.message.middleware(
    DistributedThrottleMiddleware(
        RedisSession,
        ThrottleConfig(capacity=2, window_seconds=3),
        ban_message="Не спамь!",
    )
)

PatchedI18nMiddleware(i18n).setup(dp)
app.include_router(admin_api_router)


@app.post('/webhook/{bot_id}')
async def telegram_main_webhook(bot_id: str, req: Request):
    if bot_id != 'main':
        raise HTTPException(status_code=404, detail="Unknown bot id")
    try:
        payload = await req.json()

        # if '5183374599' in str(payload):
        #     return

        update = types.Update(**payload)
        logger.info("Update received: %s", payload)
        try:
            await dp.feed_update(main_bot, update)
        except TelegramBadRequest as e:
            logger.error(e)
            logger.exception(traceback.format_exc())
        return {"ok": True}
    except Exception:
        logger.exception("Error in webhook handler:")
        logger.exception(traceback.format_exc())
        return {"ok": True}


if __name__ == "__main__":
    # print(asyncio.run(test_static_chat()))
    uvicorn.run(app, host="0.0.0.0", port=88)
