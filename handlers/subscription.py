from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, LabeledPrice
from aiogram.utils.i18n import gettext as _

from config import SUBSCRIPTION_PLANS
from database import create_session
from utils import get_user, update_user

router = Router()

@router.message(F.successful_payment)
async def payment_success(message: Message):
    payload = message.successful_payment.invoice_payload
    if not payload.startswith('sub_'):
        return
    ____, user_id, days = payload.split('_')
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

