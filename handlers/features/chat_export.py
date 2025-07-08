import logging
from typing import List

from aiogram import Bot, F, Router
from aiogram.filters import and_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.utils.i18n import gettext as _

from config import Export_State
from database import create_session
from database.models import SavedMessage
from database.models import User
from handlers.menu import send_main_menu
from keyboards import continue_keyboard
from keyboards.chat_export import export_chat_share_keyboard
from utils import get_user
from utils.messages import load_chat_with_user, RestoredMessage
from utils.userdata import get_persona

logger = logging.getLogger('Zapomnim/ChatExport')
router = Router()


async def perform_export(messages: List['RestoredMessage']):
    lines = []
    for message in messages:
        if message.content_type != 'text':
            lines.append(f"> {message.persona.full_name}: [{message.content_type}]")
        else:
            lines.append(f"> {message.persona.full_name}:")

        if message.text is not None:
            lines.append(f"{message.text}")

        lines.append('')
        lines.append('')
    return '\n'.join(lines)


async def send_export_menu(bot: Bot, chat_id: int, user: User, state: FSMContext):
    if not user.is_working:
        await bot.send_message(
            chat_id,
            text=_("SUBSCRIPTION_REQUIRED_ERROR"),
            reply_markup=continue_keyboard('profile'),
        )
        return
    if user.privacy_mode:
        await bot.send_message(
            chat_id,
            text=_("UNAVAILABLE_IN_PRIVACY_MODE"),
            reply_markup=continue_keyboard('menu'),
        )
        return

    await state.set_state(Export_State.select_user)

    m = await bot.send_message(
        chat_id,
        text=_("STA_START_TEXT"),
        reply_markup=export_chat_share_keyboard(),
    )

    await state.update_data({'message_id': m.message_id})


@router.callback_query(F.data == 'export')
async def sta_callback(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
        if user.privacy_mode:
            await callback_query.answer(_("UNAVAILABLE_IN_PRIVACY_MODE"), show_alert=True)
            return
    await send_export_menu(callback_query.bot, callback_query.message.chat.id, user, state=state)
    await callback_query.message.delete()


@router.message(and_f(F.user_shared, StateFilter(Export_State.select_user)))
async def on_chat_shared(message: Message, state: FSMContext):
    data = await state.get_data()
    m: int = data.get('message_id')
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=m)
    except:
        ...

    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)

        persona = await get_persona(session, message.user_shared.user_id)
        if persona is None:
            msg = await message.answer(
                text=_("STA_INVALID_CHAT_ERROR"),
                reply_markup=export_chat_share_keyboard(),
            )

            await state.update_data({'message_id': msg.message_id})
            return

        messages = await load_chat_with_user(user.id, persona.id, session)
        result = await perform_export(messages)

        print(result)

        await message.bot.send_document(
            chat_id=message.chat.id,
            document=BufferedInputFile(result.encode('utf-8'), filename=f'{persona.id}_exported.txt'),
        )


@router.message(and_f(
    StateFilter(Export_State.select_user),
    F.text.startswith('👈')
))
async def on_back(message: Message, state: FSMContext):
    data = await state.get_data()
    m = data.get('message_id')
    await message.bot.delete_message(chat_id=message.chat.id, message_id=m)

    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)

    await send_main_menu(message.bot, message.chat.id, user)
    await message.delete()
