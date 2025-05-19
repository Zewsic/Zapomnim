import asyncio
import time
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart, StateFilter, and_f, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, CallbackQuery, MenuButtonCommands, \
    BusinessConnection
from aiogram.utils.i18n import gettext as _, lazy_gettext as __
from sqlalchemy.ext.asyncio import AsyncSession

from config import StartState, SettingsState
from database import create_session
from database.models import User
from keyboards import security_select_keyboard
from keyboards.settings import settings_keyboard, messages_settings_keyboard
from utils import TelegramMirrorUtils, update_user, get_user, _UNSET, PatchedI18nMiddleware
from utils.widgets import settings_widget, SettingsOption

router = Router()


async def send_settings(bot: Bot, chat_id: int, user: User):
    await bot.send_message(
        chat_id,
        text=_("SETTINGS_TEXT"),
        reply_markup=settings_keyboard()
    )


@router.callback_query(F.data == 'settings')
async def settings(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
    await send_settings(callback_query.bot, callback_query.message.chat.id, user)
    await callback_query.message.delete()


# Messages Settings

@router.callback_query(F.data == 'messages_settings')
async def messages_settings(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        text=_("MESSAGES_SETTINGS_TEXT"),
        reply_markup=messages_settings_keyboard())


@router.callback_query(lambda c: c.data.startswith("deleted_messages_settings"))
async def deleted_messages_settings(callback: CallbackQuery):
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)

        parts = callback.data.split(":")
        toggle_id = parts[2] if len(parts) > 2 and parts[1] == "toggle" else None

        options = [
            SettingsOption(
                option_id="enabled",
                name=_("ENABLE_BUTTON"),
                description=_("DELETED_MESSAGES_SETTINGS_ENABLE_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="enabled_for_outgoing",
                name=_("ENABLE_FOR_OUTGOING"),
                description=_("DELETED_MESSAGES_SETTINGS_ENABLE_FOR_OUTGOING_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="save_text",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_TEXT"),
                description=_("DELETED_MESSAGES_SETTINGS_SAVE_TEXT_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="save_media",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_MEDIA"),
                description=_("DELETED_MESSAGES_SETTINGS_SAVE_MEDIA_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="save_other",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_OTHER"),
                description=_("DELETED_MESSAGES_SETTINGS_SAVE_OTHER_DESCRIPTION"),
                default=False
            ),
        ]

        title = _("DELETED_MESSAGES_SETTINGS_BUTTON")
        description = _("DELETED_MESSAGES_SETTINGS_DESCRIPTION")

        text, reply_markup = await settings_widget(
            user=user,
            session=session,
            options=options,
            message_callback="deleted_messages_settings",
            settings_id="deleted_messages",
            back_id="messages_settings",
            title=title,
            description=description,
            toggle=toggle_id
        )

        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edited_messages_settings"))
async def edited_messages_settings(callback: CallbackQuery):
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)

        parts = callback.data.split(":")
        toggle_id = parts[2] if len(parts) > 2 and parts[1] == "toggle" else None

        options = [
            SettingsOption(
                option_id="enabled",
                name=_("ENABLE_BUTTON"),
                description=_("EDITED_MESSAGES_SETTINGS_ENABLE_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="enabled_for_outgoing",
                name=_("ENABLE_FOR_OUTGOING"),
                description=_("EDITED_MESSAGES_SETTINGS_ENABLE_FOR_OUTGOING_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="save_text",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_TEXT"),
                description=_("EDITED_MESSAGES_SETTINGS_SAVE_TEXT_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="save_media",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_MEDIA"),
                description=_("DELETED_MESSAGES_SETTINGS_SAVE_MEDIA_DESCRIPTION"),
                default=True
            ),
            SettingsOption(
                option_id="save_other",
                name=_("DELETED_MESSAGES_SETTINGS_SAVE_OTHER"),
                description=_("DELETED_MESSAGES_SETTINGS_SAVE_OTHER_DESCRIPTION"),
                default=False
            ),
        ]

        title = _("EDITED_MESSAGES_SETTINGS_BUTTON")
        description = _("EDITED_MESSAGES_SETTINGS_DESCRIPTION")

        text, reply_markup = await settings_widget(
            user=user,
            session=session,
            options=options,
            message_callback="edited_messages_settings",
            settings_id="edited_messages",
            back_id="messages_settings",
            title=title,
            description=description,
            toggle=toggle_id
        )

        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("protected_messages_settings"))
async def protected_messages_settings(callback: CallbackQuery):
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)

        parts = callback.data.split(":")
        toggle_id = parts[2] if len(parts) > 2 and parts[1] == "toggle" else None

        options = [
            SettingsOption(
                option_id="enabled",
                name=_("ENABLE_BUTTON"),
                description=_("EDITED_MESSAGES_SETTINGS_ENABLE_DESCRIPTION"),
                default=True
            ),
        ]

        title = _("PROTECTED_MESSAGES_SETTINGS_BUTTON")
        description = _("EDITED_MESSAGES_SETTINGS_DESCRIPTION")

        text, reply_markup = await settings_widget(
            user=user,
            session=session,
            options=options,
            message_callback="protected_messages_settings",
            settings_id="protected_messages",
            back_id="messages_settings",
            title=title,
            description=description,
            toggle=toggle_id
        )

        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer()
