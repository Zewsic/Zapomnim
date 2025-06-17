import json

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, BusinessMessagesDeleted, LinkPreviewOptions
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from database import create_session
from database.models import Persona, User, Metric
from utils import get_user
from utils.messages import ContentType, RestoredMessage, restore_last_messages
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
        content: str | None,
        caption: str,
):
    """Универсальная функция отправки контента по content_type (Enum)."""
    if not content:
        await bot.send_message(
            chat_id,
            text=caption,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
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
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        await bot.send_sticker(chat_id, sticker=content, reply_to_message_id=sent_msg.message_id)
        return

    if content_type == ContentType.VIDEO_NOTE:
        sent_msg = await bot.send_message(
            chat_id,
            text=caption,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
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
            caption=caption,
        )
        return

    await bot.send_message(
        chat_id,
        text=caption,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def send_deleted_info(
        bot: Bot,
        user: User,
        chat: Persona,
        restored_messages: list[RestoredMessage],
        session: AsyncSession,
        message_ids: list[int],
) -> None:
    """Рассылает в личку пользователю (user_id) информацию об удалённых сообщениях."""
    for msg_data, msg_id in zip(restored_messages, message_ids):
        if user.id != msg_data.persona.id:
            if not await user.get_bool("settings.deleted_messages.enabled", session, default=True):
                continue
        elif not await user.get_bool("settings.deleted_messages.enabled_for_outgoing", session, default=True):
            continue

        if msg_data.content_type == ContentType.TEXT:
            if not await user.get_bool("settings.deleted_messages.save_text", session, default=True):
                continue
        elif msg_data.content_type in [*list(MEDIA_TYPES.keys()), ContentType.VIDEO_NOTE, ContentType.STICKER]:
            if not await user.get_bool("settings.deleted_messages.save_media", session, default=True):
                continue
        elif not await user.get_bool("settings.deleted_messages.save_other", session, default=False):
            continue

        content_type_str = _("REMOVED_CONTENT_TYPE_%s" % msg_data.content_type.value.upper())  # noqa: INT003, UP031
        persona_name = msg_data.persona.hname if msg_data.persona else "Unknown"
        date_str = msg_data.created_at.strftime("%d.%m.%Y %H:%M:%S")

        base_text = _(
            "DELETED_MESSAGE_TEMPLATE",
        ).format(
            content_type=content_type_str,
            **{
                "from": persona_name,
                "chat": chat.hname,
                "date": date_str,
                "text": f"\n<blockquote expandable>{msg_data.text}</blockquote>\n" if msg_data.text else "",
            },
        )

        await send_media(
            bot=bot,
            chat_id=user.id,
            content_type=msg_data.content_type,
            content=msg_data.content,
            caption=base_text,
        )

        metric = Metric(
            connected_user_id=user.id if not user.privacy_mode else None,
            chat_id=chat.id if not user.privacy_mode else None,
            message_id=msg_id if not user.privacy_mode else None,
            name='metrics.save_deleted_messages',
        )
        session.add(metric)
    await session.commit()


@router.deleted_business_messages()
async def on_delete_messages(event: BusinessMessagesDeleted):
    """Хэндлер, который ловит событие удаления сообщений в бизнес-чате.
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

        try:
            await send_deleted_info(
                bot=bot,
                user=user,
                chat=chat,
                restored_messages=restored,
                session=session,
                message_ids=event.message_ids
            )
        except TelegramBadRequest as e:
            if "VOICE_MESSAGES_FORBIDDEN" in e.message:
                await event.bot.send_message(user.id, _("VOICE_MESSAGES_FORBIDDEN"))
            else:
                raise e
