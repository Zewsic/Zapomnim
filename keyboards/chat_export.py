from aiogram.types import KeyboardButton, KeyboardButtonRequestUser, ReplyKeyboardMarkup
from aiogram.utils.i18n import gettext as _


def export_chat_share_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(
            text=_("EXPORT_SELECT_CHAT_BUTTON"),
            request_user=KeyboardButtonRequestUser(request_id=123, user_is_bot=False),
        )],
        [KeyboardButton(
            text=_("BACK_BUTTON"),
        )],
    ], resize_keyboard=True, one_time_keyboard=True)
