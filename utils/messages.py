from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from typing import Iterable, Optional, List

from aiogram.types import Message
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, SavedMessage, Persona, Metric
from utils.security import (
    generate_privacy_key, generate_encryption_data,
    encrypt_message, decrypt_message
)
from utils.userdata import get_persona


class ContentType(str, Enum):
    TEXT = "text"
    PHOTO = "photo"
    DOCUMENT = "document"
    VIDEO = "video"
    STICKER = "sticker"
    AUDIO = "audio"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    ANIMATION = "animation"
    CONTACT = "contact"
    LOCATION = "location"
    VENUE = "venue"
    POLL = "poll"
    PAID_MEDIA = "paid_media"
    STORY = "story"
    GIFT = "gift"
    UNIQUE_GIFT = "unique_gift"
    DICE = "dice"
    GAME = "game"


FILE_EXTRACTORS = (
    ContentType.DOCUMENT,
    ContentType.VIDEO,
    ContentType.STICKER,
    ContentType.AUDIO,
    ContentType.VOICE,
    ContentType.VIDEO_NOTE,
    ContentType.ANIMATION,
)

MODEL_DUMP_ATTRS = (
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
)


@dataclass
class RestoredMessage:
    content_type: ContentType
    content: Optional[str]
    text: Optional[str]
    persona: Optional[Persona]
    created_at: datetime
    privacy_key: str = None


async def save_message(
        connected_user: User,
        message: Message,
        session: AsyncSession
) -> Optional[tuple[ContentType, Optional[str], Optional[str]]]:
    """Сохраняет сообщение пользователя с учетом типа контента и приватности."""
    chat_id = message.chat.id
    user_id = message.from_user.id

    text = message.text or message.caption
    content = None
    content_type: Optional[ContentType] = ContentType.TEXT if message.text else None

    if not content_type and message.photo:
        content_type = ContentType.PHOTO
        content = message.photo[-1].file_id

    if not content_type:
        for attr in FILE_EXTRACTORS:
            val = getattr(message, attr.value, None)
            if val:
                content_type = attr
                content = val.file_id
                break

    if not content_type:
        for attr in MODEL_DUMP_ATTRS:
            val = getattr(message, attr.value, None)
            if val:
                content_type = attr
                # Важно: предполагается, что model_dump_json() возвращает строку!
                content = val.model_dump_json()
                break

    if not content_type:
        return None

    await _save_message(
        connected_user_id=connected_user.id,
        chat_id=chat_id,
        message_id=message.message_id,
        from_id=user_id,
        text=text,
        content_type=content_type,
        content=content,
        is_privacy_mode=connected_user.privacy_mode,
        session=session
    )
    return content_type, content, text


async def _save_message(
        connected_user_id: int,
        chat_id: int,
        message_id: int,
        from_id: int,
        text: Optional[str],
        content_type: ContentType,
        content: Optional[str],
        is_privacy_mode: bool,
        session: AsyncSession
) -> None:
    """Внутренняя функция для сохранения сообщения в базу."""
    privacy_key = generate_privacy_key(connected_user_id, chat_id, message_id)
    encryption_data = generate_encryption_data(connected_user_id, chat_id, message_id)

    _text = encrypt_message(encryption_data, text) if text else None
    _content = encrypt_message(encryption_data, content) if content else None

    msg = SavedMessage(
        privacy_key=privacy_key,
        text=_text,
        content_type=content_type.value,
        content=_content,
        outgoing=from_id == connected_user_id,
    )

    if not is_privacy_mode:
        msg.connected_user_id = connected_user_id
        msg.chat_id = chat_id
        msg.message_id = message_id

    session.add(msg)
    await session.commit()


async def load_message_history(
        connected_user_id: int,
        chat_id: int,
        message_ids: Iterable[int],
        session: AsyncSession,
) -> List[RestoredMessage]:
    """Восстанавливает последние версии сообщений по id."""
    result: List[RestoredMessage] = []
    for message_id in sorted(message_ids):
        messages = await _load_messages(connected_user_id, chat_id, message_id, session)
        if messages:
            result.append(messages[-1])
    return result


async def restore_last_messages(
        connected_user_id: int,
        chat_id: int,
        message_ids: Iterable[int],
        session: AsyncSession,
) -> List[RestoredMessage]:
    """Восстанавливает последние версии сообщений по id."""
    result: List[RestoredMessage] = []
    for message_id in sorted(message_ids):
        messages = await _load_messages(connected_user_id, chat_id, message_id, session)
        if messages:
            result.append(messages[-1])
    return result


async def _load_messages(
        connected_user_id: int,
        chat_id: int,
        message_id: int,
        session: AsyncSession,
) -> List[RestoredMessage]:
    """Загружает и расшифровывает сообщения с привязкой к ключу приватности."""
    privacy_key = generate_privacy_key(connected_user_id, chat_id, message_id)
    encryption_data = generate_encryption_data(connected_user_id, chat_id, message_id)

    result: List[RestoredMessage] = []
    r = await session.execute(
        select(SavedMessage)
        .where(SavedMessage.privacy_key == privacy_key)
        .order_by(SavedMessage.created_at)
    )
    _messages: List[SavedMessage] = r.scalars()
    for _message in _messages:
        if not _message:
            continue
        text = decrypt_message(encryption_data, _message.text) if _message.text else None
        content = decrypt_message(encryption_data, _message.content) if _message.content else None
        persona_id = connected_user_id if _message.outgoing else chat_id
        persona = await get_persona(session, persona_id)
        result.append(
            RestoredMessage(
                content_type=ContentType(_message.content_type),
                content=content,
                text=text,
                persona=persona,
                created_at=_message.created_at,
                privacy_key=privacy_key,
            )
        )
    return result


async def make_all_messages_private(
        connected_user_id: int,
        session: AsyncSession,
):
    await session.execute(
        update(SavedMessage)
        .where(SavedMessage.connected_user_id == connected_user_id)
        .values(connected_user_id=None, chat_id=None, message_id=None)
    )

    await session.commit()

async def anonymize_metrics(user_id: int, session: AsyncSession):
    await session.execute(
        update(Metric)
        .where(
            Metric.connected_user_id == user_id,
            Metric.name.in_([
                'metrics.save_deleted_messages',
                'metrics.save_edited_messages',
                'metrics.save_protected_messages',
                'metrics.transcribe_voice_message'
            ]),
        )
        .values(connected_user_id=None, chat_id=None, message_id=None)
    )


async def load_chat_with_user(
        connected_user_id: int,
        chat_id: int,
        session: AsyncSession,
        *,
        count: int = 1000
) -> List[RestoredMessage]:
    """Восстанавливает последние версии сообщений по id."""
    result: List[RestoredMessage] = []

    r = await session.execute(
        select(SavedMessage.message_id)
        .where(
            SavedMessage.connected_user_id == connected_user_id,
            SavedMessage.chat_id == chat_id,
        )
        .order_by(SavedMessage.created_at.desc())
        .limit(count)
    )

    raw_message_ids = r.scalars().all()

    for raw_message_id in reversed(raw_message_ids):
        messages = await _load_messages(connected_user_id, chat_id, raw_message_id, session)
        print(messages)
        if messages:
            result.append(messages[-1])

    return result


async def load_encrypted_user_messages(
        connected_user_id: int,
        session: AsyncSession,
        *,
        chat_id: Optional[int] = None,
        cutoff: Optional[datetime] = None,
) -> List[SavedMessage]:
    filters = [
        SavedMessage.connected_user_id == connected_user_id
    ]

    if chat_id:
        filters.append(SavedMessage.chat_id == chat_id)

    if cutoff:
        filters.append(SavedMessage.created_at >= cutoff)

    r = (await session.execute(
        select(SavedMessage)
        .where(
            *filters
        )
        .order_by(SavedMessage.created_at.desc())
    )).scalars().all()

    return list(r)