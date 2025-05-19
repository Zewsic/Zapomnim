from datetime import datetime
from typing import Optional

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, LinkPreviewOptions, BufferedInputFile

from database import create_session
from database.models import Persona
from handlers.features.save_protected_content import process_protected_message
from utils import get_user
from utils.botapi import TelegramDataUtils
from utils.messages import save_message, ContentType
from utils.userdata import update_persona, get_persona

router = Router()


@router.business_message()
async def new_message(message: Message, state: FSMContext):
    async with create_session() as session:
        await update_persona(
            id=message.from_user.id,
            session=session,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            language=message.from_user.language_code,
        )
        await session.commit()

        user = await get_user(business_connection_id=message.business_connection_id, session=session)
        if not user or not user.is_enabled or user.is_banned:
            return

        # Save Message
        await save_message(user, message, session)

        # Check Protected Content
        if message.reply_to_message:
            await process_protected_message(user, message.reply_to_message, session)
