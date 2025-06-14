from urllib.parse import quote

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, ReplyKeyboardMarkup, KeyboardButton, \
    KeyboardButtonRequestUser
from aiogram.utils.i18n import gettext as _

from database.models import User


def STA_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(
            text=_("STA_SELECT_CHAT_BUTTON"),
            request_user=KeyboardButtonRequestUser(request_id=123, user_is_bot=False)
        )],
        [KeyboardButton(
            text=_("BACK_BUTTON")
        )]
    ], resize_keyboard=True, one_time_keyboard=True)
