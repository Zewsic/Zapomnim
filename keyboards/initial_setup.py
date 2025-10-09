from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.i18n import gettext as _


def language_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [
            KeyboardButton(text="🇷🇺"),
            KeyboardButton(text="🇬🇧"),
        ],
    ], resize_keyboard=True, one_time_keyboard=True)

def start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("START_BUTTON"), callback_data="start")],
        [InlineKeyboardButton(text=_("BOT_FUNCTIONS_BUTTON"), url="https://example.com")],
    ])

def continue_keyboard(callback_data):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("CONTINUE_BUTTON"), callback_data=callback_data),
        ],
    ])

def bot_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("BOT_MODE_STANDARD"), callback_data="initial_setup_select_mode:standard"),
        ],
        [
            InlineKeyboardButton(text=_("BOT_MODE_PRIVACY"), callback_data="initial_setup_select_mode:privacy"),
        ],
    ])

def privacy_policy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("AGREE"), callback_data="start:agree_privacy")],
    ])

def channel_subscription_keyboard(channel_id: str) -> InlineKeyboardMarkup:
    # Определяем URL канала в зависимости от формата ID
    if channel_id.startswith("-100"):
        # Приватный канал - используем формат t.me/c/ без префикса -100
        clean_id = channel_id.lstrip("-100")
        channel_url = f"https://t.me/c/{clean_id}"
    elif channel_id.startswith("@"):
        # Публичный канал с username
        channel_url = f"https://t.me/{channel_id.lstrip('@')}"
    else:
        # Публичный канал без @
        channel_url = f"https://t.me/{channel_id}"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("SUBSCRIBE_TO_CHANNEL_BUTTON"), url=channel_url)],
        [InlineKeyboardButton(text=_("CHECK_SUBSCRIPTION_BUTTON"), callback_data="check_channel_subscription")],
    ])
