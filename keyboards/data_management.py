from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _


def data_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("CLEAR_DATA_BUTTON"), callback_data="clear_data")],
        [InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="profile")]
    ])


def confirm_clear_keyboard(step: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("CONTINUE_BUTTON"), callback_data=f"clear_data_confirm:{step}")],
        [InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="data_settings")]
    ])

def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="profile")]
    ])

