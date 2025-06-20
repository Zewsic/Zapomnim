import asyncio
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.client import bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery
from aiogram.utils.i18n import gettext as _

from config import PaymentState
from database import create_session
from database.models import User
from keyboards import continue_keyboard
from keyboards.subscription import subscription_keyboard
from utils import get_user, update_user

router = Router()


async def send_subscription_add(bot: Bot, chat_id: int, user: User, state: FSMContext):
    msg = await bot.send_message(
        chat_id,
        text=_("SUBSCRIPTION_ADD_TEXT").format(
            subscription_date=user.subscriber_until.strftime("%d.%m.%Y"),
            subscription_days=max((user.subscriber_until - datetime.now()).days, 0),
        ),
        reply_markup=await subscription_keyboard(bot, user)
    )

    await state.set_state(PaymentState.pay_with_stars)
    await state.update_data({'message_id': msg.message_id})


@router.callback_query(F.data == 'subscription_add')
async def profile(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
    await send_subscription_add(callback_query.bot, callback_query.message.chat.id, user, state=state)
    await callback_query.message.delete()


@router.pre_checkout_query()
async def pre_checkout_query_handler(query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(
        pre_checkout_query_id=query.id,
        ok=True
    )


@router.message(F.successful_payment)
async def payment_success(message: Message, state: FSMContext):
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

        if user.referral_id is not None:
            referral = await get_user(session, id=user.referral_id)
            referral_days = days // 30 * 5

            new_referral_until = max(referral.subscriber_until, datetime.now()) + timedelta(days=referral_days)
            await update_user(
                id=int(referral.id),
                session=session,
                subscription_until=new_referral_until,
                referrals_income=referral.referrals_income + referral_days
            )

            await message.bot.send_message(referral.id,
                                           _("SUBSCRIPTION_REFERRAL_SUCCESS").format(days=referral_days),
                                           reply_markup=continue_keyboard('profile')
                                           )

        await session.commit()

    try:
        emoji = await message.answer('💸')
        await asyncio.sleep(0.7)

        if (msg_id := (await state.get_data()).get('message_id')) is not None:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)

        await message.answer(
            _("SUBSCRIPTION_SUCCESS").format(date=new_until.strftime('%d.%m.%Y')),
            reply_markup=continue_keyboard('profile')
        )

        await emoji.delete()
    except:
        ...
