from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, Message
from aiogram.utils.i18n import gettext as _

from database.models import User


async def make_payment_url(bot: Bot, user_id, selected_period: int, selected_payment_method: str):
    if selected_payment_method == 'youkassa':
        if selected_period == 30:
            price = 199
        elif selected_period == 90:
            price = 569
        elif selected_period == 180:
            price = 1079
        elif selected_period == 360:
            price = 2029
        else:
            price = 9999

        return await bot.create_invoice_link(
            title=_('SUBSCRIPTION_TITLE').format(days=selected_period),
            description=_('SUBSCRIPTION_DESC').format(days=selected_period),
            payload=f"sub_{user_id}_{selected_period}",
            currency="RUB",
            prices=[LabeledPrice(label=_('SUBSCRIPTION_LABEL'), amount=price)],
            provider_token="390540012:LIVE:72415",
        )

    elif selected_payment_method == 'stars':
        if selected_period == 30:
            price = 400
        elif selected_period == 90:
            price = 1100
        elif selected_period == 180:
            price = 2100
        elif selected_period == 360:
            price = 4000
        else:
            price = 9999

        return await bot.create_invoice_link(
            title=_('SUBSCRIPTION_TITLE').format(days=selected_period),
            description=_('SUBSCRIPTION_DESC').format(days=selected_period),
            payload=f"sub_{user_id}_{selected_period}",
            currency="XTR",
            prices=[LabeledPrice(label=_('SUBSCRIPTION_LABEL'), amount=price)],
        )
    return 'https://google.com'


async def subscription_keyboard(bot: Bot, user: User, selected_period: int,
                                selected_payment_method: str, selected_type: str = None) -> InlineKeyboardMarkup:
    def make_selected(text: str, value: Any, required: Any) -> str:
        return f'⭐️ {text} ⭐️' if value == required else text

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("SUBSCRIPTION_PAYMENT_METHOD"), callback_data='nothing')
        ],
        [
            InlineKeyboardButton(text=make_selected(_("SUBSCRIPTION_PAYMENT_METHOD_YOUKASSA"), selected_payment_method, 'youkassa'),
                                 callback_data='subscription_add:method:youkassa'),
            InlineKeyboardButton(text=make_selected(_("SUBSCRIPTION_PAYMENT_METHOD_STARS"), selected_payment_method, 'stars'),
                                 callback_data='subscription_add:method:stars')
        ],
        # [
        #     InlineKeyboardButton(text=_("Подписка"), callback_data='nothing')
        # ],
        # [
        #     InlineKeyboardButton(text=make_selected(_('Обычная'), selected_type, 'normal'),
        #                          callback_data='subscription_add:type:normal'),
        #     InlineKeyboardButton(text=make_selected(_('Расширенная'), selected_type, 'plus'),
        #                          callback_data='subscription_add:type:plus')
        # ],
        [
            InlineKeyboardButton(text=_("SUBSCRIPTION_DURATION"), callback_data='nothing')
        ],
        [
            InlineKeyboardButton(text=make_selected(_('SUBSCRIPTION_DURATION_30'), selected_period, 30),
                                 callback_data='subscription_add:duration:30'),
            InlineKeyboardButton(text=make_selected(_('SUBSCRIPTION_DURATION_90'), selected_period, 90),
                                 callback_data='subscription_add:duration:90')
        ],
        [
            InlineKeyboardButton(text=make_selected(_('SUBSCRIPTION_DURATION_180'), selected_period, 180),
                                 callback_data='subscription_add:duration:180'),
            InlineKeyboardButton(text=make_selected(_('SUBSCRIPTION_DURATION_360'), selected_period, 360),
                                 callback_data='subscription_add:duration:360')
        ],
        [
            InlineKeyboardButton(text=_("SUBSCRIPTION_GO_PAY"), pay=True,
                                 url=await make_payment_url(bot, user.id, selected_period, selected_payment_method)),
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data='profile')
        ]
    ])
