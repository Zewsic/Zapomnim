from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, LabeledPrice
from aiogram.utils.i18n import gettext as _

from config import SUBSCRIPTION_PLANS
from keyboards.subscription import subscription_keyboard
from database import create_session
from utils import get_user, update_user

router = Router()


@router.callback_query(F.data == 'buy_subscription')
async def choose_plan(callback: CallbackQuery):
    await callback.message.edit_text(
        _("SUBSCRIPTION_TEXT"),
        reply_markup=subscription_keyboard()
    )


@router.callback_query(lambda c: c.data.startswith('sub_plan:'))
async def send_invoice(callback: CallbackQuery):
    days = int(callback.data.split(':')[1])
    plan = next((p for p in SUBSCRIPTION_PLANS if p['days'] == days), None)
    if not plan:
        await callback.answer('Unknown plan')
        return
    invoice_link = await callback.bot.create_invoice_link(
        title=_('SUBSCRIPTION_TITLE').format(days=days),
        description=_('SUBSCRIPTION_DESC').format(days=days),
        payload=f"sub_{callback.from_user.id}_{days}",
        currency="XTR",
        prices=[LabeledPrice(label=_('SUBSCRIPTION_LABEL'), amount=int(plan['price'] * 100))],
        start_parameter=f"sub_{days}"
    )
    await callback.message.answer(invoice_link)
    await callback.answer()


@router.message(F.successful_payment)
async def payment_success(message: Message):
    payload = message.successful_payment.invoice_payload
    if not payload.startswith('sub_'):
        return
    _, user_id, days = payload.split('_')
    days = int(days)
    async with create_session() as session:
        user = await get_user(session, id=int(user_id))
        if not user:
            return
        new_until = max(user.subscriber_until, datetime.now()) + timedelta(days=days)
        await update_user(id=user.id, session=session, subscription_until=new_until)
        await session.commit()
    await message.answer(
        _("SUBSCRIPTION_SUCCESS").format(date=new_until.strftime('%d.%m.%Y'))
    )

