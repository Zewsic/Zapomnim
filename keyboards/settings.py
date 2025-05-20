from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.i18n import gettext as _, lazy_gettext as __
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User


def messages_settings_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("DELETED_MESSAGES_SETTINGS_BUTTON"), callback_data="deleted_messages_settings"),
        ],
        [
            InlineKeyboardButton(text=_("EDITED_MESSAGES_SETTINGS_BUTTON"), callback_data="edited_messages_settings"),
        ],
        [
            InlineKeyboardButton(text=_("PROTECTED_MESSAGES_SETTINGS_BUTTON"), callback_data="protected_messages_settings"),
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="settings"),
        ]
    ])


def settings_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("BOT_MODE_SETTINGS_BUTTON"), callback_data="bot_mode_settings"),
        ],
        [
            InlineKeyboardButton(text=_("MESSAGES_SETTINGS_BUTTON"), callback_data="messages_settings"),
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="menu"),
        ]
    ])


def bot_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("BOT_MODE_STANDARD"), callback_data='bot_mode_settings:standard'),
        ],
        [
            InlineKeyboardButton(text=_("BOT_MODE_PRIVACY"), callback_data='bot_mode_settings:privacy'),
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="settings"),
        ]
    ])

def confirm_mode_keyboard(mode: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("CONTINUE_BUTTON"), callback_data=f'bot_mode_settings:{mode}-confirm'),
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data='bot_mode_settings'),
        ],
    ])