from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _


def go_to_history(privacy_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("OPEN_HISTORY_BUTTON"), callback_data=f"open_history:{privacy_id}"),
        ],
    ])
