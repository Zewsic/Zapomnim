from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.utils.i18n import gettext as _

from database.models import User


async def subscription_keyboard(bot: Bot, user: User) -> InlineKeyboardMarkup:
    # invoice_7_link = await bot.create_invoice_link(
    #     title=_('SUBSCRIPTION_TITLE').format(days=7),
    #     description=_('SUBSCRIPTION_DESC').format(days=7),
    #     payload=f"sub_{user.id}_7",
    #     currency="XTR",
    #     prices=[LabeledPrice(label=_('SUBSCRIPTION_LABEL'), amount=1)],
    # )

    invoice_30_link = await bot.create_invoice_link(
        title=_('SUBSCRIPTION_TITLE').format(days=30),
        description=_('SUBSCRIPTION_DESC').format(days=30),
        payload=f"sub_{user.id}_30",
        currency="XTR",
        prices=[LabeledPrice(label=_('SUBSCRIPTION_LABEL'), amount=180)], # 250
        subscription_period=2592000
    )

    invoice_180_link = await bot.create_invoice_link(
        title=_('SUBSCRIPTION_TITLE').format(days=180),
        description=_('SUBSCRIPTION_DESC').format(days=180),
        payload=f"sub_{user.id}_180",
        currency="XTR",
        prices=[LabeledPrice(label=_('SUBSCRIPTION_LABEL'), amount=1000)],
    )

    invoice_360_link = await bot.create_invoice_link(
        title=_('SUBSCRIPTION_TITLE').format(days=360),
        description=_('SUBSCRIPTION_DESC').format(days=360),
        payload=f"sub_{user.id}_360",
        currency="XTR",
        prices=[LabeledPrice(label=_('SUBSCRIPTION_LABEL'), amount=1900)],
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        # [
        #     InlineKeyboardButton(text=_('SUBSCRIPTION_TITLE').format(days=7), url=invoice_7_link, pay=True)
        # ],
        [
            InlineKeyboardButton(text=_('SUBSCRIPTION_TITLE').format(days=30), url=invoice_30_link, pay=True)
        ],
        [
            InlineKeyboardButton(text=_('SUBSCRIPTION_TITLE').format(days=180), url=invoice_180_link, pay=True)
        ],
        [
            InlineKeyboardButton(text=_('SUBSCRIPTION_TITLE').format(days=360), url=invoice_360_link, pay=True)
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data='profile')
        ]
    ])

    return kb
