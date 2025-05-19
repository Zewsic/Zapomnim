import asyncio
import time
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart, StateFilter, and_f, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, CallbackQuery, MenuButtonCommands, \
    BusinessConnection, Chat
from aiogram.utils.i18n import gettext as _, lazy_gettext as __

from config import StartState, SettingsState
from database import create_session
from database.models import User
from keyboards import security_select_keyboard, main_menu_keyboard
from keyboards.menu import profile_keyboard
from utils import TelegramMirrorUtils, update_user, get_user, _UNSET, PatchedI18nMiddleware

router = Router()

async def send_main_menu(bot: Bot, chat_id: int, user: User):
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
        reply_markup=profile_keyboard(user)
    )


@router.callback_query(F.data == 'profile')
async def profile(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
    await send_profile(callback_query.bot, callback_query.message.chat.id, user)
    await callback_query.message.delete()

@router.callback_query(F.data == 'menu')
async def menu(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
    await send_main_menu(callback_query.bot, callback_query.message.chat.id, user)
    await callback_query.message.delete()
