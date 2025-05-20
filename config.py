from os import environ

from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.state import StatesGroup, State

BOT_TOKEN = environ.get("BOT_TOKEN")
WEBHOOK_HOST = environ.get('WEBHOOK_HOST')

TELEGRAM_SERVER = TelegramAPIServer.from_base(environ.get('TELEGRAM_SERVER'), is_local=True)
TELEGRAM_SERVER_DATA = environ.get('TELEGRAM_SERVER_DATA')

# Subscription plans configuration
# Each plan is defined by number of days and price in XTR
SUBSCRIPTION_PLANS = [
    {"days": 7, "price": 1.99},
    {"days": 30, "price": 4.99},
    {"days": 60, "price": 8.99},
    {"days": 90, "price": 12.99},
]

class StartState(StatesGroup):
    setup_language = State()
    start = State()
    connect_business_bot = State()
    business_connection_done = State()

class SettingsState(StatesGroup):
    setup_language = State()