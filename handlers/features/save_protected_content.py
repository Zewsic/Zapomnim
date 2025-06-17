from datetime import datetime
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, LinkPreviewOptions, Message
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Persona, User, Metric
from keyboards import continue_keyboard
from utils.botapi import TelegramDataUtils
from utils.messages import ContentType, save_message
from utils.userdata import get_persona

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
        await bot.send_video(
            chat_id,
            video=content,
            caption=caption,
        )
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
            "text": f'\n<blockquote expandable>{caption}</blockquote>\n' if caption else "",
        }
    )

    await send_media(
        bot=bot,
        chat_id=user_id,
        content_type=content_type,
        content=content,
        caption=base_msg
    )


async def process_protected_message(
        user: User,
        message: Message,
        session: AsyncSession,
) -> None:
    if not await user.get_bool('settings.protected_messages.enabled', session, default=True):
        return

    try:
        content_type, content, text = await save_message(user, message, session)
    except TypeError:
        return
    if message.has_protected_content:
        file_data = TelegramDataUtils.get_file(await message.bot.get_file(content))

        if not user.is_working:
            await message.bot.send_message(
                user.id,
                text=_("SUBSCRIPTION_REQUIRED_ERROR"),
                reply_markup=continue_keyboard('profile'),
            )
            return

        chat = await get_persona(session, message.chat.id)
        persona = await get_persona(session, message.from_user.id)
        try:
            await send_protected_message(message.bot, chat, user.id, persona, content_type, file_data, text)
        except TelegramBadRequest as e:
            if 'VOICE_MESSAGES_FORBIDDEN' in e.message:
                await message.bot.send_message(user.id, _("VOICE_MESSAGES_FORBIDDEN"))
            else:
                raise e

        metric = Metric(
            connected_user_id=user.id if not user.privacy_mode else None,
            chat_id=chat.id if not user.privacy_mode else None,
            message_id=message.message_id if not user.privacy_mode else None,
            name='metrics.save_protected_content',
        )
        session.add(metric)
        await session.commit()