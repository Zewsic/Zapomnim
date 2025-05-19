from datetime import datetime
from typing import Optional

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, LinkPreviewOptions, BufferedInputFile
from aiogram.utils.i18n import gettext as _

from database import create_session
from database.models import Persona
from utils import get_user
from utils.botapi import TelegramDataUtils
from utils.messages import save_message, ContentType
from utils.userdata import update_persona, get_persona

router = Router()

MEDIA_TYPES = {
    ContentType.PHOTO: "send_photo",
    ContentType.VIDEO: "send_video",
    ContentType.AUDIO: "send_audio",
    ContentType.VOICE: "send_voice",
}


async def send_media(
        bot: Bot,
        chat_id: int,
        content_type: ContentType,
        content: bytes,
        caption: str
):
    """
    Универсальная функция отправки контента по content_type (Enum).
    """

    content = BufferedInputFile(content, filename='saved')

    if content_type in MEDIA_TYPES:
        method_name = MEDIA_TYPES[content_type]
        send_method = getattr(bot, method_name)
        await send_method(**{content_type.value: content}, chat_id=chat_id, caption=caption)
        return

    if content_type == ContentType.VIDEO_NOTE:
        sent_msg = await bot.send_message(
            chat_id,
            text=caption,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        await bot.send_video_note(chat_id, video_note=content, reply_to_message_id=sent_msg.message_id)
        return

    await bot.send_message(
        chat_id,
        text=caption,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

async def send_protected_message(
        bot: Bot,
        chat: Persona,
        user_id: int,
        from_user: Persona,
        content_type: ContentType,
        content: bytes,
        caption: Optional[str]
) -> None:
    """
    Отправляем в личку пользователю сообщение о том,
    что было получено защищенное сообщение.
    """

    base_msg = _(
        "PROTECTED_MESSAGE_SAVED_TEMPLATE"
    ).format(
        **{
            "from": from_user.hname if from_user else "Unknown",
            "chat": chat.hname,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "text": caption or _("NONE")
        }
    )

    await send_media(
        bot=bot,
        chat_id=user_id,
        content_type=content_type,
        content=content,
        caption=base_msg
    )


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

        await save_message(user, message, session)

        if message.reply_to_message:
            content_type, content, text = await save_message(user, message.reply_to_message, session)
            if message.reply_to_message.has_protected_content:
                file_data = TelegramDataUtils.get_file(await message.bot.get_file(content))

                chat = await get_persona(session, message.chat.id)
                persona = await get_persona(session, message.reply_to_message.from_user.id)
                await send_protected_message(message.bot, chat, user.id, persona, content_type, file_data, text)
