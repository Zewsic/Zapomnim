from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.i18n import gettext as _, lazy_gettext as __

def security_select_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("SECURITY_MODE_STANDARD"), callback_data='select_security:standard'),
        ],
        [
            InlineKeyboardButton(text=_("SECURITY_MODE_SECURITY"), callback_data='select_security:security'),
        ],

    ])