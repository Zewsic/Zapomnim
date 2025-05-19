import json
from datetime import datetime
from typing import Optional, List

from aiogram import Router, Bot
from aiogram.types import (
    BusinessMessagesDeleted,
    BufferedInputFile,
    LinkPreviewOptions
)
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from database import create_session
from database.models import Persona, User
from utils import get_user
from utils.messages import restore_last_messages, RestoredMessage, ContentType
from utils.userdata import get_persona

router = Router()

MEDIA_TYPES = {
    ContentType.PHOTO: "send_photo",
    ContentType.DOCUMENT: "send_document",
    ContentType.VIDEO: "send_video",
    ContentType.AUDIO: "send_audio",
    ContentType.VOICE: "send_voice",
    ContentType.ANIMATION: "send_animation",
}

DUMPABLE_TYPES = {
    ContentType.CONTACT,
    ContentType.LOCATION,
    ContentType.VENUE,
    ContentType.POLL,
    ContentType.PAID_MEDIA,
    ContentType.STORY,
    ContentType.GIFT,
    ContentType.UNIQUE_GIFT,
    ContentType.DICE,
    ContentType.GAME,
}


async def send_media(
        bot: Bot,
        chat_id: int,
        content_type: ContentType,
        content: Optional[str],
        caption: str
):
    """
    Универсальная функция отправки контента по content_type (Enum).
    """
    if not content:
        await bot.send_message(
            chat_id,
            text=caption,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        return

    if content_type in MEDIA_TYPES:
        method_name = MEDIA_TYPES[content_type]
        send_method = getattr(bot, method_name)
        await send_method(**{content_type.value: content}, chat_id=chat_id, caption=caption)
        return

    if content_type == ContentType.STICKER:
        sent_msg = await bot.send_message(
            chat_id,
            text=caption,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        await bot.send_sticker(chat_id, sticker=content, reply_to_message_id=sent_msg.message_id)
        return

    if content_type == ContentType.VIDEO_NOTE:
        sent_msg = await bot.send_message(
            chat_id,
            text=caption,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        await bot.send_video_note(chat_id, video_note=content, reply_to_message_id=sent_msg.message_id)
        return

    if content_type in DUMPABLE_TYPES:
        try:
            parsed_json = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            parsed_json = {"error": "invalid json data"}

        dump_bytes = json.dumps(parsed_json, ensure_ascii=True, indent=2).encode("utf-8")
        await bot.send_document(
            chat_id,
            BufferedInputFile(dump_bytes, filename="dump.json"),
            caption=caption
        )
        return

    await bot.send_message(
        chat_id,
        text=caption,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )


async def send_deleted_info(
        bot: Bot,
        user: User,
        chat: Persona,
        restored_messages: List[RestoredMessage],
        session: AsyncSession,
) -> None:
    """
    Рассылает в личку пользователю (user_id) информацию об удалённых сообщениях.
    """
    for msg_data in restored_messages:
        if user.id != msg_data.persona.id:
            if not await user.get_bool('settings.deleted_messages.enabled', session, default=True):
                continue
        else:
            if not await user.get_bool('settings.deleted_messages.enabled_for_outgoing', session, default=True):
                continue

        if msg_data.content_type == ContentType.TEXT:
            if not await user.get_bool('settings.deleted_messages.save_text', session, default=True):
                continue
        elif msg_data.content_type in list(MEDIA_TYPES.keys()) + [ContentType.VIDEO_NOTE, ContentType.STICKER]:
            if not await user.get_bool('settings.deleted_messages.save_media', session, default=True):
                continue
        else:
            if not await user.get_bool('settings.deleted_messages.save_other', session, default=False):
                continue

        content_type_str = _(f"REMOVED_CONTENT_TYPE_{msg_data.content_type.value.upper()}")
        persona_name = msg_data.persona.hname if msg_data.persona else "Unknown"
        date_str = msg_data.created_at.strftime("%d.%m.%Y %H:%M:%S")

        base_text = _(
            "DELETED_MESSAGE_TEMPLATE"
        ).format(
            content_type=content_type_str,
            **{
                "from": persona_name,
                "chat": chat.hname,
                "date": date_str,
                "text": f'<blockquote expandable>{msg_data.text}</blockquote>\n' if msg_data.text else "",
            }
        )

        await send_media(
            bot=bot,
            chat_id=user.id,
            content_type=msg_data.content_type,
            content=msg_data.content,
            caption=base_text
        )


@router.deleted_business_messages()
async def on_delete_messages(event: BusinessMessagesDeleted):
    """
    Хэндлер, который ловит событие удаления сообщений в бизнес-чате.
    """
    bot: Bot = event.bot

    async with create_session() as session:
        user = await get_user(business_connection_id=event.business_connection_id, session=session)
        if not user or not user.is_enabled or user.is_banned:
            return

        # Теперь restore_last_messages возвращает List[RestoredMessage]
        restored = await restore_last_messages(user.id, event.chat.id, event.message_ids, session)
        if not restored:
            return

        if not user.is_working:
            return

        chat = await get_persona(session, event.chat.id)

        await send_deleted_info(
            bot=bot,
            user=user,
            chat=chat,
            restored_messages=restored,
            session=session
        )
