from urllib.parse import quote

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.utils.i18n import gettext as _

from database.models import User


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("STATISTICS_BUTTON"), callback_data='statistics')],
        [InlineKeyboardButton(text=_("STA_BUTTON"), callback_data='analyze')],
        [
            InlineKeyboardButton(text=_("SETTINGS_BUTTON"), callback_data='settings'),
            InlineKeyboardButton(text=_("PROFILE_BUTTON"), callback_data='profile'),
        ],
        [
            InlineKeyboardButton(text=_("SUPPORT_BUTTON"), url=_("SUPPORT_LINK")),
            InlineKeyboardButton(text=_("CHANNEL_BUTTON"), url=_("CHANNEL_LINK")),
        ]
    ])


async def profile_keyboard(bot: Bot, user: User) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("SUBSCRIPTION_ADD_BUTTON"), callback_data='subscription_add'),
        ],
        [
            InlineKeyboardButton(text=_("REFERRALS_BUTTON"), callback_data='referrals'),
        ],
        [
            InlineKeyboardButton(text=_("DATA_SETTINGS_BUTTON"), callback_data='data_settings')
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data='menu')
        ]
    ])

    return kb


async def referrals_keyboard(bot: Bot, user: User) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("REFERRALS_SHARE_BUTTON"), url='https://t.me/share/url?url=&text=' + quote(
                _("REFERRALS_SHARE_TEXT").format(user_id=user.id))),
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data='profile')
        ]
    ])

    return kb
