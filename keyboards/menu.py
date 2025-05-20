from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from aiogram.utils.i18n import gettext as _, lazy_gettext as __

from database.models import User


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("SETTINGS_BUTTON"), callback_data='settings')],
        [InlineKeyboardButton(text=_("STATISTICS_BUTTON"), callback_data='statistics')],
        [
            InlineKeyboardButton(text=_("PROFILE_BUTTON"), callback_data='profile'),
            InlineKeyboardButton(text=_("SUPPORT_BUTTON"), url=_("SUPPORT_LINK")),
        ]
    ])


async def profile_keyboard(bot: Bot, user: User) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("DATA_SETTINGS_BUTTON"), callback_data='data_settings')
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data='menu')
        ]
    ])

    if not user.has_subscription:
        invoice_link = await bot.create_invoice_link(
            title=_('SUBSCRIPTION_TITLE').format(days=30),
            description=_('SUBSCRIPTION_DESC').format(days=30),
            payload=f"sub_{user.id}_30",
            currency="XTR",
            prices=[LabeledPrice(label=_('SUBSCRIPTION_LABEL'), amount=150)],
            subscription_period=2592000
        )

        kb.inline_keyboard.insert(0, [
            InlineKeyboardButton(text=_("BUY_SUBSCRIPTION_BUTTON"), url=invoice_link, pay=True)
        ])

    return kb
