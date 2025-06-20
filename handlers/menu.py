from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy import select

from config import EmptyState
from database import create_session
from database.models import User
from keyboards import main_menu_keyboard
from keyboards.menu import profile_keyboard, referrals_keyboard
from utils import get_user, update_user

router = Router()


async def send_main_menu(bot: Bot, chat_id: int, user: User, state: FSMContext = None):
    if state:
        data = await state.get_data()

        if promo := data.get('activate_promo'):
            async with create_session() as session:
                new_until = max(user.subscriber_until, datetime.now()) + timedelta(days=promo[1])
                user = await update_user(id=user.id, session=session, subscription_until=new_until)
                await session.commit()
            await state.update_data({'activate_promo': None})
            await bot.send_message(chat_id=chat_id, text=_("PROMO_ACTIVATED").format(days=promo[1]))
        elif promo_error := data.get('activate_promo_error'):
            await bot.send_message(chat_id=chat_id, text=_("PROMO_ERROR_" + promo_error))
            await state.update_data({'activate_promo_error': None})


    await bot.send_photo(
        chat_id,
        photo=FSInputFile(_("MAIN_MENU_IMAGE")),
        caption=_("MAIN_MENU_TEXT").format(
            name=user.first_name,
            subscription_date=user.subscriber_until.strftime("%d.%m.%Y"),
            days=max((user.subscriber_until - datetime.now()).days, 0),
            bot_mode=_("BOT_MODE_PRIVACY" if user.privacy_mode else "BOT_MODE_STANDARD"),
        ),
        reply_markup=main_menu_keyboard()
    )


async def send_profile(bot: Bot, chat_id: int, user: User):
    await bot.send_message(
        chat_id,
        text=_("PROFILE_TEXT").format(
            name=user.first_name,
            user_id=user.id,
            subscription_date=user.subscriber_until.strftime("%d.%m.%Y"),
            subscription_days=max((user.subscriber_until - datetime.now()).days, 0),
            reg_date=user.created_at.strftime("%d.%m.%Y"),
            reg_days=max((datetime.now() - user.created_at).days, 0),
        ),
        reply_markup=await profile_keyboard(bot, user)
    )


async def send_referrals(bot: Bot, chat_id: int, user: User):
    async with create_session() as session:
        count = len((await session.execute(
            select(User)
            .where(User.referral_id == user.id)
        )).scalars().all())

    await bot.send_message(
        chat_id,
        text=_("REFERRALS_TEXT").format(
            user_id=user.id,
            days=user.referrals_income,
            count=count,
        ),
        reply_markup=await referrals_keyboard(bot, user),
        disable_web_page_preview=True
    )


@router.callback_query(F.data == 'profile')
async def profile(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(EmptyState.state)
    await state.set_data({})
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
    await send_profile(callback_query.bot, callback_query.message.chat.id, user)
    await callback_query.message.delete()


@router.callback_query(F.data == 'referrals')
async def referrals(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
    await send_referrals(callback_query.bot, callback_query.message.chat.id, user)
    await callback_query.message.delete()


@router.callback_query(F.data == 'menu')
async def menu(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
    await send_main_menu(callback_query.bot, callback_query.message.chat.id, user)
    await callback_query.message.delete()
