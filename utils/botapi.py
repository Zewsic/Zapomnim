from typing import Final

import aiofiles
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import File, User

from config import TELEGRAM_SERVER, TELEGRAM_SERVER_DATA, WEBHOOK_HOST

WEBHOOK_URL: Final[str] = f"http://{WEBHOOK_HOST}/webhook/%s"


class TelegramMirrorUtils:
    CONNECTED_BOTS: dict[int, Bot] = {}

    @staticmethod
    async def check_token(token: str) -> tuple[Bot, User]:
        mirror_bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                         session=AiohttpSession(api=TELEGRAM_SERVER))

        try:
            bot_info = await mirror_bot.get_me()
        except:  # noqa: E722
            raise KeyError

        return mirror_bot, bot_info

    @staticmethod
    async def check_and_connect(token: str) -> User:
        mirror_bot, bot_info = await TelegramMirrorUtils.check_token(token)

        if not bot_info.can_connect_to_business:
            raise ConnectionError

        await mirror_bot.delete_webhook()
        await mirror_bot.set_webhook(WEBHOOK_URL % bot_info.id)
        TelegramMirrorUtils.CONNECTED_BOTS[bot_info.id] = mirror_bot

        return bot_info

    @staticmethod
    async def disconnect(bot_id):
        bot = TelegramMirrorUtils.CONNECTED_BOTS.get(bot_id)
        if not bot:
            return

        await bot.delete_webhook()
        await bot.close()

        del TelegramMirrorUtils.CONNECTED_BOTS[bot_id]


class TelegramDataUtils:
    BASE_TG_DATA = "/var/lib/telegram-bot-api/"

    @staticmethod
    def get_normal_file_path(file: File) -> str:
        path = file.file_path.replace(TelegramDataUtils.BASE_TG_DATA, TELEGRAM_SERVER_DATA)
        return path

    @staticmethod
    async def get_file(file: File) -> bytes:
        async with aiofiles.open(TelegramDataUtils.get_normal_file_path(file), "rb") as f:
            return await f.read()
