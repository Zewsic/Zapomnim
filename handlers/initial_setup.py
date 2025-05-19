import asyncio

from aiogram import Router, F
from aiogram.filters import CommandStart, StateFilter, and_f, or_f
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, CallbackQuery, MenuButtonCommands, BusinessConnection
from aiogram.utils.i18n import gettext as _

from config import StartState
from database import create_session
from keyboards import start_keyboard, continue_keyboard, language_keyboard
from utils import update_user, get_user, _UNSET, PatchedI18nMiddleware

router = Router()

@router.message(
    or_f(
        and_f(
            F.text.in_(('🇷🇺', '🇬🇧')),
            StateFilter(StartState.setup_language)
        ),
        CommandStart()
    )
)
async def start_command(
    message: Message,
    state: FSMContext,
    i18n_middleware: PatchedI18nMiddleware
):
    await state.set_state(StartState.start)
    data = await state.get_data()

    selected_language = _UNSET
    if message.text == '🇷🇺':
        selected_language = 'ru'
    elif message.text == '🇬🇧':
        selected_language = 'en'

    if selected_language is not _UNSET:
        i18n_middleware.i18n.current_locale = selected_language
        await message.delete()
        if 'lang_message' in data:
            await data['lang_message'].delete()

    async with create_session() as session:
        user = await update_user(
            id=message.from_user.id, session=session,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            is_enabled=True,
            language=selected_language
        )
        await session.commit()

    emoji = await message.answer('👋')
    await asyncio.sleep(0.7)

    if not user.language_code:
        lang_message = await message.answer(
            "<b>Choose a language.</b>",
            reply_markup=language_keyboard()
        )
        await emoji.delete()
        await state.update_data({'lang_message': lang_message})
        await state.set_state(StartState.setup_language)
        return

    await message.answer_photo(
        photo=FSInputFile(_("START_IMAGE")),
        caption=_("START_TEXT"),
        reply_markup=start_keyboard()
    )
    await emoji.delete()


@router.callback_query(F.data.startswith('start'))
async def start_callback(query: CallbackQuery, state: FSMContext):
    if not query.from_user.is_premium:
        await query.answer(_("ONLY_FOR_TELEGRAM_PREMIUM"), show_alert=True)
        return

    await state.set_state(StartState.connect_business_bot)
    await query.message.edit_reply_markup(reply_markup=None)
    emoji = await query.message.answer('🚀')

    await asyncio.sleep(1)
    await query.message.delete()
    await emoji.delete()

    instruction_message = await query.message.answer_photo(
        photo=FSInputFile(_("CONNECT_BUSINESS_BOT_IMAGE")),
        caption=_("CONNECT_BUSINESS_BOT_TEXT")
    )
    await state.update_data({
        'instruction_message': instruction_message,
    })


@router.business_connection()
async def on_new_connection(event: BusinessConnection, state: FSMContext):
    await state.set_state(StartState.business_connection_done)
    data = await state.get_data()
    instruction_message: Message = data.get('instruction_message')

    async with create_session() as session:
        user = await get_user(session, id=event.user.id)
        if not user:
            return

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

        await event.bot.send_message(
            chat_id=user.id,
            text=_("CONNECT_BUSINESS_BOT_SUCCESS_TEXT"),
            reply_markup=continue_keyboard("settings")
        )