import asyncio
import time

from aiogram import Router, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.i18n import gettext as _, lazy_gettext as __

from config import StartState
from keyboards.main_menu import start_keyboard, setup_business_keyboard, bot_link_keyboard
from utils import TelegramMirrorUtils

router = Router()


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await state.set_state(StartState.start)

    emoji = await message.answer('👋')
    await asyncio.sleep(0.7)
    await message.answer_photo(
        photo=FSInputFile(_("START_IMAGE")),
        caption=_("START_TEXT"),
        reply_markup=start_keyboard()
    )
    await emoji.delete()


@router.callback_query(F.data == 'start')
async def start_callback(query: CallbackQuery, state: FSMContext):
    if not query.from_user.is_premium:
        await query.answer(_("ONLY_FOR_TELEGRAM_PREMIUM"), show_alert=True)
        return
    await state.set_state(StartState.enter_token)

    emoji = await query.message.answer('🚀')
    await query.message.delete()
    await asyncio.sleep(1)

    instruction_message = await query.message.answer_photo(
        photo=FSInputFile(_("START_IMAGE")),
        caption=_("CONNECT_BOT_INSTRUCTION")
    )
    await state.update_data({'instruction_message': instruction_message})

    await emoji.delete()


@router.message(StateFilter(StartState.enter_token))
async def enter_token(message: Message, state: FSMContext):
    token = message.text
    state_data = await state.get_data()
    instruction_message: Message = state_data['instruction_message']
    instructions_text = _("CONNECT_BOT_INSTRUCTION")

    await message.delete()

    if token.count(':') != 1 or not token.split(':')[0].isnumeric():
        await instruction_message.edit_caption(caption=instructions_text + _("INVALID_TOKEN"))
        return

    await instruction_message.edit_caption(caption=instructions_text + _("CHECKING_BOT") % message.text.split(':')[0])

    try:
        _bot, bot_info = await TelegramMirrorUtils.check_token(token)
    except KeyError:
        await instruction_message.edit_caption(caption=instructions_text + _("INVALID_TOKEN"))
        return

    await instruction_message.edit_caption(caption=instructions_text + (_("CHECKING_BOT") % bot_info.full_name))

    await asyncio.sleep(1)

    await state.update_data({'instruction_message': instruction_message})

    if bot_info.can_connect_to_business:
        emoji = await instruction_message.answer('💥')
        await instruction_message.delete()
        await asyncio.sleep(0.7)
        await instruction_message.answer(
            text=_("BOT_SETUP_COMPLETE") % bot_info.username,
            reply_markup=bot_link_keyboard(bot_info.username)
        )
        await emoji.delete()
        await TelegramMirrorUtils.check_and_connect(token)
    else:
        await state.set_state(StartState.enable_business_mode)
        await state.update_data({'bot_username': bot_info.username, 'token': token})

        emoji = await instruction_message.answer('✅')
        await instruction_message.delete()
        await asyncio.sleep(0.7)
        await instruction_message.answer_photo(
            photo=FSInputFile(_("START_IMAGE")),
            caption=_("BOT_SETUP_BUSINESS_INSTRUCTION"),
            reply_markup=setup_business_keyboard()
        )
        await emoji.delete()

@router.callback_query(F.data == 'check_business')
async def check_business_callback(query: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()

    try:
        await TelegramMirrorUtils.check_and_connect(state_data.get('token'))
    except KeyError:
        await start_callback(query, state)
        return
    except ConnectionError:
        await query.answer(_("BUSINESS_MODE_IS_NOT_ENABLED"), show_alert=True)
        return

    emoji = await query.message.answer('💥')
    await query.message.delete()
    await asyncio.sleep(0.7)
    await query.message.answer(
        text=_("BOT_SETUP_COMPLETE") % state_data.get('bot_username'),
        reply_markup=bot_link_keyboard(state_data.get('bot_username'))
    )
    await emoji.delete()
    await state.clear()