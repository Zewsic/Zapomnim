from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.i18n import gettext as _, lazy_gettext as __

from database.models import User


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("STATISTICS_BUTTON"), callback_data='statistics')],
        [InlineKeyboardButton(text=_("SETTINGS_BUTTON"), callback_data='settings')],
        [
            InlineKeyboardButton(text=_("PROFILE_BUTTON"), callback_data='profile'),
            InlineKeyboardButton(text=_("SUPPORT_BUTTON"), url=_("SUPPORT_LINK")),
        ]
    ])


def profile_keyboard(user: User) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("DATA_SETTINGS_BUTTON"), callback_data='data_settings')
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data='menu')
        ]
    ])

    if not user.has_subscription:
        kb.inline_keyboard.insert(0, [
            InlineKeyboardButton(text=_("BUY_SUBSCRIPTION_BUTTON"), callback_data='buy_subscription')
        ])

    return kb
