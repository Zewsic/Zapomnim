from os import environ

from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.state import State, StatesGroup

BOT_TOKEN = environ.get("BOT_TOKEN")
WEBHOOK_HOST = environ.get("WEBHOOK_HOST")

TELEGRAM_SERVER = TelegramAPIServer.from_base(environ.get("TELEGRAM_SERVER"), is_local=True)
TELEGRAM_SERVER_DATA = environ.get("TELEGRAM_SERVER_DATA")

# Channel that the user must be subscribed to in order to receive a free month
# Accepts values like "@channel_username" or "-1001234567890". If not set, code will
# try to infer from the localized CHANNEL_LINK string.
SUBSCRIPTION_REQUIRED_CHANNEL = environ.get("SUBSCRIPTION_REQUIRED_CHANNEL")

SUBSCRIPTION_PLANS = [
    {"days": 7, "price": 100},
    {"days": 30, "price": 150},
    {"days": 60, "price": 250},
    {"days": 90, "price": 350},
]

class EmptyState(StatesGroup):
    state = State()


class StartState(StatesGroup):
    setup_language = State()
    start = State()
    connect_business_bot = State()
    business_connection_done = State()


class SettingsState(StatesGroup):
    setup_language = State()

class PaymentState(StatesGroup):
    select_params = State()
    pay_with_stars = State()

class STA_State(StatesGroup):
    select_user = State()

class Export_State(StatesGroup):
    select_user = State()

class StatisticsState(StatesGroup):
    main = State()  # главное меню статистики
    wait_for_dialog = State()  # когда нажали "Выбрать человека" и ждём ChatShared
