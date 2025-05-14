import json
import traceback
from contextlib import asynccontextmanager
from typing import Final

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.utils.i18n import I18n, gettext as _, ngettext, lazy_gettext as __

from config import WEBHOOK_HOST, BOT_TOKEN, TELEGRAM_SERVER
from handlers import main_menu_router
from handlers.business import business_test_router
from utils import TelegramMirrorUtils, PatchedI18nMiddleware

BOT_TOKEN: Final[str] = BOT_TOKEN
WEBHOOK_URL: Final[str] = f"http://{WEBHOOK_HOST}/main"

main_bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML),
               session=AiohttpSession(api=TELEGRAM_SERVER))

i18n = I18n(
    path="locales",
    default_locale="en",
    domain="zapomnim"
)

@asynccontextmanager
async def lifespan(*args):
    await main_bot.set_webhook(WEBHOOK_URL)
    yield
    await main_bot.delete_webhook()


app = FastAPI(lifespan=lifespan)

main_dp = Dispatcher()
main_dp.include_routers(main_menu_router)
PatchedI18nMiddleware(i18n).setup(main_dp)

@app.post('/main')
async def telegram_main_webhook(req: Request):
    print('Main webhook received\n', json.dumps(await req.json(), indent=2), '\n\n-----------------\n')

    try:
        update = types.Update(**await req.json())
        await main_dp.feed_update(main_bot, update)
    except:
        traceback.print_exc()
    return {"ok": True}


mirror_dp = Dispatcher()
mirror_dp.include_routers(business_test_router)
PatchedI18nMiddleware(i18n).setup(mirror_dp)


@app.post('/mirror/{bot_id}')
async def telegram_mirror_webhook(req: Request, bot_id: int):
    if (mirror_bot := TelegramMirrorUtils.CONNECTED_BOTS.get(bot_id)) is None:
        raise HTTPException(status_code=415, detail="Unconnected Bot")

    print('Mirror webhook received\n', json.dumps(await req.json(), indent=2), '\n\n-----------------\n')

    try:
        update = types.Update(**await req.json())
        await mirror_dp.feed_update(mirror_bot, update)
    except:
        traceback.print_exc()
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=88)
