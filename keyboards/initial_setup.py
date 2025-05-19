from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.i18n import gettext as _, lazy_gettext as __

def language_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [
            KeyboardButton(text='🇷🇺'),
            KeyboardButton(text='🇬🇧'),
        ]
    ], resize_keyboard=True, one_time_keyboard=True)

def start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("START_BUTTON"), callback_data="start")
        ]
    ])

def continue_keyboard(callback_data):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("CONTINUE_BUTTON"), callback_data=callback_data)
        ]
    ])
