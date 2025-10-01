import asyncio

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import create_session
from handlers.features.message_enhancer import enhance_message
from handlers.features.save_protected_content import process_protected_message
from handlers.features.voice_messages_transcriber import transcribe_voice_messages
from utils import get_user
from utils.messages import save_message
from utils.userdata import update_persona

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
        _saved_data = await save_message(user, message, session)
        if not _saved_data:
            return
        content_type, content, text = _saved_data

        # Check Protected Content
        if message.reply_to_message:
            await process_protected_message(user, message.reply_to_message, session)

        if not user.privacy_mode and not message.forward_from and message.from_user.id == user.id:
            if content_type in ("voice", "video_note"):
                asyncio.create_task(transcribe_voice_messages(user, message, session, content_type == "video_note"))
            else:
                asyncio.create_task(enhance_message(user, message, session))

