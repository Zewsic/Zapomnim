from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _

from config import SUBSCRIPTION_PLANS


def subscription_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for plan in SUBSCRIPTION_PLANS:
        text = _("SUBSCRIPTION_PLAN_BUTTON").format(days=plan["days"], price=plan["price"])
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"sub_plan:{plan['days']}")])
    buttons.append([InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="profile")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
