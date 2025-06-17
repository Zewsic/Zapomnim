import json
from typing import Optional

from aiogram import Router, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BufferedInputFile,
    LinkPreviewOptions,
    Message, InlineKeyboardMarkup
)
from aiogram.utils.i18n import gettext as _

from database import create_session
from database.models import Persona, Metric
from utils import get_user
from utils.messages import restore_last_messages, save_message, ContentType, RestoredMessage
from utils.userdata import update_persona

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
        user_id: int,
        content_type: ContentType,
        content: Optional[str],
        caption: str,
        keyboard: InlineKeyboardMarkup,
        silent_mode: bool = True,
):
    """
    Универсальная отправка медиа по content_type.
    """
    if content_type in MEDIA_TYPES and content:
        send_method_name = MEDIA_TYPES[content_type]
        send_method = getattr(bot, send_method_name)
        await send_method(chat_id=user_id, **{content_type.value: content}, caption=caption, reply_markup=keyboard, disable_notification=silent_mode)
        return

    if content_type == ContentType.STICKER and content:
        sent_msg = await bot.send_message(
            user_id,
            text=caption,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            disable_notification=silent_mode
        )
        await bot.send_sticker(user_id, sticker=content, reply_to_message_id=sent_msg.message_id, disable_notification=silent_mode)
        return

    if content_type == ContentType.VIDEO_NOTE and content:
        sent_msg = await bot.send_message(
            user_id,
            text=caption,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            disable_notification=silent_mode
        )
        await bot.send_video_note(user_id, video_note=content, reply_to_message_id=sent_msg.message_id, disable_notification=silent_mode)
        return

    if content_type in DUMPABLE_TYPES and content:
        try:
            parsed_content = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            parsed_content = {"error": "invalid json data"}
        dump_bytes = json.dumps(parsed_content, ensure_ascii=True, indent=2).encode("utf-8")
        await bot.send_document(
            chat_id=user_id,
            document=BufferedInputFile(dump_bytes, filename="dump.json"),
            caption=caption,
            reply_markup=keyboard,
            disable_notification=silent_mode,
        )
        return

    await bot.send_message(
        user_id,
        text=caption,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
        reply_markup=keyboard,
        disable_notification=silent_mode
    )


async def send_edited_info(
        bot: Bot,
        user_id: int,
        chat: Persona,
        old_msg: RestoredMessage,
        new_msg: RestoredMessage,
        message_id: int,
        silent_mode: bool,
) -> None:
    """
    Отправляем в личку пользователю сообщение о том,
    что он отредактировал в бизнес-чате.
    """
    content_type_str = _(f"EDITED_CONTENT_TYPE_{old_msg.content_type.value.upper()}")
    _date = old_msg.created_at.strftime("%d.%m.%Y %H:%M")

    base_msg = _(
        "EDITED_MESSAGE_TEMPLATE"
    ).format(
        content_type=content_type_str,
        **{
            "from": old_msg.persona.hname if old_msg.persona else "Unknown",
            "chat": chat.hname,
            "id": message_id,
            "content": (
                    (_("EDITED_MESSAGE_TEMPLATE_OLD_TEXT").format(
                        text=old_msg.text, date=_date) if old_msg.text else "") +
                    (_("EDITED_MESSAGE_TEMPLATE_NEW_TEXT").format(text=new_msg.text) if new_msg.text else "")
            )
        }
    )

    await send_media(
        bot=bot,
        user_id=user_id,
        content_type=old_msg.content_type,
        content=old_msg.content or "",
        caption=base_msg,
        keyboard=InlineKeyboardMarkup(inline_keyboard=[]),
        silent_mode=silent_mode
    )


@router.edited_business_message()
async def on_edit_messages(event: Message):
    """
    Хэндлер, который ловит отредактированные сообщения.
    """
    bot: Bot = event.bot

    async with create_session() as session:
        user = await get_user(business_connection_id=event.business_connection_id, session=session)
        if not user or not user.is_enabled or user.is_banned:
            return

        restored = await restore_last_messages(user.id, event.chat.id, [event.message_id], session)
        if not restored:
            return

        old_msg: RestoredMessage = restored[0]

        new_result = await save_message(user, event, session)
        if not new_result:
            return

        if not user.is_working:
            return

        new_msg = RestoredMessage(
            content_type=new_result[0],
            content=new_result[1],
            text=new_result[2],
            persona=old_msg.persona,
            created_at=old_msg.created_at
        )

        chat = await update_persona(
            id=event.chat.id,
            session=session,
            first_name=event.chat.first_name,
            last_name=event.chat.last_name,
            username=event.chat.username
        )

        if user.id != new_msg.persona.id:
            if not await user.get_bool('settings.edited_messages.enabled', session, default=True):
                return
        else:
            if not await user.get_bool('settings.edited_messages.enabled_for_outgoing', session, default=True):
                return

        if new_msg.content_type == ContentType.TEXT:
            if not await user.get_bool('settings.edited_messages.save_text', session, default=True):
                return
        elif new_msg.content_type in list(MEDIA_TYPES.keys()) + [ContentType.VIDEO_NOTE, ContentType.STICKER]:
            if not await user.get_bool('settings.edited_messages.save_media', session, default=True):
                return
        else:
            if not await user.get_bool('settings.edited_messages.save_other', session, default=False):
                return

        silent_mode = await user.get_bool('settings.edited_messages.silent_mode', session, default=True)

        try:
            await send_edited_info(
                bot=bot,
                user_id=user.id,
                chat=chat,
                old_msg=old_msg,
                new_msg=new_msg,
                message_id=event.message_id,
                silent_mode=silent_mode
            )
        except TelegramBadRequest as e:
            if 'VOICE_MESSAGES_FORBIDDEN' in e.message:
                await event.bot.send_message(user.id, _("VOICE_MESSAGES_FORBIDDEN"))
            else:
                raise e

        metric = Metric(
            connected_user_id=user.id if not user.privacy_mode else None,
            chat_id=chat.id if not user.privacy_mode else None,
            message_id=event.message_id if not user.privacy_mode else None,
            name='metrics.save_edited_messages',
        )
        session.add(metric)
        await session.commit()
