from aiogram import Bot
from aiogram.types import BotCommand


async def set_bot_commands(bot: Bot):
    await bot.set_my_commands(commands=[
        BotCommand(command='start', description='Open bot main menu'),
        BotCommand(command='analyze', description='Analyze chat with AI'),
        BotCommand(command='profile', description='Open user profile'),
        BotCommand(command='settings', description='Open bot settings'),
        # BotCommand(command='privacy', description='Show Privacy Policy'),
    ], language_code='en')

    await bot.set_my_commands(commands=[
        BotCommand(command='start', description='Открыть главное меню'),
        BotCommand(command='analyze', description='Проанализировать чат'),
        BotCommand(command='profile', description='Открыть профиль пользователя'),
        BotCommand(command='settings', description='Открыть настройки'),
        # BotCommand(command='privacy', description='Политика обработки персональных данных'),
    ], language_code='ru')