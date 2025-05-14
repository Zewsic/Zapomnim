from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _, lazy_gettext as __

def start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("START_BUTTON"), callback_data="start")
        ]
    ])

def setup_business_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("CHECK_BUSINESS_BUTTON"), callback_data="check_business")
        ]
    ])

def bot_link_keyboard(bot_username: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("GO_TO_BOT_BUTTON"), url=f'https://t.me/{bot_username}')
        ]
    ])