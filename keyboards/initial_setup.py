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
