from aiogram import Bot
from aiogram.types import BotCommand


async def set_bot_commands(bot: Bot):
    await bot.set_my_commands(commands=[
        BotCommand(command='start', description='Open bot main menu'),
    ], language_code='en')

    await bot.set_my_commands(commands=[
        BotCommand(command='start', description='Открыть главное меню'),
    ], language_code='ru')