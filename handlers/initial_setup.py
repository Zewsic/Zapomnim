import asyncio
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter, and_f, or_f
from aiogram.fsm.context import FSMContext
from aiogram.types import BusinessConnection, CallbackQuery, FSInputFile, Message
from aiogram.utils.i18n import gettext as _
from sqlalchemy import select

from config import StartState
from database import create_session
from database.models import Metric
from handlers.features.chat_export import send_export_menu
from handlers.menu import send_main_menu, send_profile
from handlers.settings import send_settings
from keyboards import continue_keyboard, language_keyboard, start_keyboard
from keyboards.initial_setup import bot_mode_keyboard, privacy_policy_keyboard
from utils import _UNSET, PatchedI18nMiddleware, get_user, update_user
from utils.security import check_promocode

router = Router()


@router.message(Command("export"))
async def profile(message: Message, state: FSMContext, i18n_middleware: PatchedI18nMiddleware):
    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)
        if not user or not user.is_enabled:
            return await start_command(message, state, i18n_middleware)

        await send_export_menu(message.bot, message.chat.id, user, state)

@router.message(Command("profile"))
async def profile(message: Message, state: FSMContext, i18n_middleware: PatchedI18nMiddleware):
    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)
        if not user or not user.is_enabled:
            return await start_command(message, state, i18n_middleware)

        await send_profile(message.bot, message.chat.id, user)


@router.message(Command("settings"))
async def settings(message: Message, state: FSMContext, i18n_middleware: PatchedI18nMiddleware):
    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)
        if not user or not user.is_enabled:
            return await start_command(message, state, i18n_middleware)

        await send_settings(message.bot, message.chat.id, user)


@router.message(
    or_f(
        and_f(
            F.text.in_(("🇷🇺", "🇬🇧")),
            StateFilter(StartState.setup_language),
        ),
        CommandStart(),
    ),
)
async def start_command(
        message: Message,
        state: FSMContext,
        i18n_middleware: PatchedI18nMiddleware,
        command: CommandObject = None,
):
    await state.set_state(StartState.start)
    data = await state.get_data()

    referral_id = None
    promo = None
    if command is not None and command.args:
        if command.args.startswith("ref"):
            referral_id = int(command.args[3:])
        if command.args.startswith("promo"):
            _promo = check_promocode(command.args[5:])
            if _promo:
                promo = (command.args[5:], _promo)
            else:
                await state.update_data({"activate_promo_error": "INVALID_PROMO"})

    selected_language = _UNSET
    if message.text == "🇷🇺":
        selected_language = "ru"
    elif message.text == "🇬🇧":
        selected_language = "en"

    if selected_language is not _UNSET:
        i18n_middleware.i18n.current_locale = selected_language
        await message.delete()
        if "lang_message_id" in data:
            await message.bot.delete_message(message.chat.id, data["lang_message_id"])

    async with create_session() as session:
        if promo:
            is_promo_activated = (await session.execute(
                select(Metric)
                .where(
                    Metric.name == "system.promocode.activated",
                    Metric.value.contains(promo[0]),
                ),
            )).scalar_one_or_none()

            if not is_promo_activated:
                await state.update_data({"activate_promo": promo})

                metric = Metric(
                    connected_user_id=message.from_user.id,
                    name="system.promocode.activated",
                    value=promo[0],
                )
                session.add(metric)
                await session.commit()
            else:
                await state.update_data({"activate_promo_error": "ALREADY_ACTIVATED"})

        user = await update_user(
            id=message.from_user.id, session=session,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            language=selected_language,
            referral_id=referral_id,
        )
        await session.commit()

    emoji = await message.answer("👋")
    await asyncio.sleep(0.7)

    if not user.language_code:
        lang_message = await message.answer(
            "<b>Choose a language / Выберите язык.</b>",
            reply_markup=language_keyboard(),
        )
        await emoji.delete()
        await state.update_data({"lang_message_id": lang_message.message_id})
        await state.set_state(StartState.setup_language)
        return

    if not user.is_enabled:
        await message.answer_photo(
            photo=FSInputFile(_("START_IMAGE")),
            caption=_("START_TEXT"),
            reply_markup=start_keyboard(),
        )
    else:
        await send_main_menu(message.bot, message.chat.id, user, state)
    await emoji.delete()


@router.callback_query(F.data.startswith("start"))
async def start_callback(query: CallbackQuery, state: FSMContext):
    if not query.from_user.is_premium:
        await query.answer(_("ONLY_FOR_TELEGRAM_PREMIUM"), show_alert=True)
        return

    async with create_session() as session:
        user = await get_user(session, id=query.from_user.id)
        if user.privacy_agreed is None:
            if "agree_privacy" in query.data:
                await update_user(id=query.from_user.id, session=session, privacy_agreed=datetime.now())
            else:
                await query.message.delete()
                await query.message.answer(_("PRIVACY_TEXT").format(link=_("PRIVACY_URL")), reply_markup=privacy_policy_keyboard())
                return
        else:
            await state.set_state(StartState.connect_business_bot)
            await query.message.edit_reply_markup(reply_markup=None)
            emoji = await query.message.answer("🚀")

            await asyncio.sleep(1)
            await emoji.delete()
    await query.message.delete()

    instruction_message = await query.message.answer_photo(
        photo=FSInputFile(_("CONNECT_BUSINESS_BOT_IMAGE")),
        caption=_("CONNECT_BUSINESS_BOT_TEXT"),
    )
    await state.update_data({
        "instruction_message": instruction_message,
    })


@router.business_connection()
async def on_new_connection(event: BusinessConnection, state: FSMContext):
    await state.set_state(StartState.business_connection_done)
    data = await state.get_data()
    instruction_message: Message = data.get("instruction_message")

    async with create_session() as session:
        user = await get_user(session, id=event.user.id)
        if not user:
            return

        _had_been_enabled = user.is_enabled

        user = await update_user(
            id=user.id, session=session,
            first_name=event.user.first_name,
            last_name=event.user.last_name,
            username=event.user.username,
            is_enabled=event.is_enabled,
            business_connection_id=event.id,
        )
        await session.commit()

    if event.is_enabled:
        if instruction_message:
            await instruction_message.delete()

        if not _had_been_enabled:

            if user.subscriber_until is None:
                await update_user(
                    id=user.id,
                    session=session,
                    subscription_until=datetime.now() + timedelta(days=30),
                )
                await session.commit()

                await event.bot.send_message(
                    chat_id=user.id,
                    text=_("FREE_SUBSCRIPTION_ENABLED_TEXT"),
                    reply_markup=continue_keyboard("initial_setup_select_mode"),
                )
                return

            await event.bot.send_message(
                chat_id=user.id,
                text=_("CONNECT_BUSINESS_BOT_SUCCESS_TEXT"),
                reply_markup=continue_keyboard("menu"),
            )
        return
    await event.bot.send_message(
        chat_id=user.id,
        text=_("BUSINESS_BOT_DISCONNECTED_TEXT"),
        reply_markup=continue_keyboard("start"),
    )


@router.callback_query(F.data.startswith("initial_setup_select_mode"))
async def initial_setup_select_mode_callback(query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=query.from_user.id)
        if not user:
            return

        parts = query.data.split(":")
        action = parts[1] if len(parts) > 1 else None

        if action == "standard":
            await update_user(id=user.id, session=session, privacy_mode=False)
            await send_main_menu(query.bot, query.message.chat.id, user, state)
            await query.message.delete()
        elif action == "privacy":
            await update_user(id=user.id, session=session, privacy_mode=True)
            await send_main_menu(query.bot, query.message.chat.id, user, state)
            await query.message.delete()
        else:
            await query.message.edit_text(
                text=_("SELECT_BOT_TYPE").format(
                    selected_mode=_("BOT_MODE_PRIVACY" if user.privacy_mode else "BOT_MODE_STANDARD"),
                ),
                reply_markup=bot_mode_keyboard())

        await session.commit()


@router.callback_query(F.data.startswith("nothing"))
async def nothing(query: CallbackQuery, state: FSMContext):
    await query.answer()
