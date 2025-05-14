from os import environ

from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.state import StatesGroup, State

BOT_TOKEN = environ.get("BOT_TOKEN")
WEBHOOK_HOST = environ.get('WEBHOOK_HOST')

TELEGRAM_SERVER = TelegramAPIServer.from_base(environ.get('TELEGRAM_SERVER'), is_local=True)

class StartState(StatesGroup):
    start = State()
    enter_token = State()
    enable_business_mode = State()