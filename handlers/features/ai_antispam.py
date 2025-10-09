import asyncio
import json
import logging
import time
from typing import List

from aiogram.types import Message
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from database import RedisSession, create_session
from database.models import Metric, User
from handlers.features.delete_messages_handler import send_deleted_info
from utils import get_user
from utils.messages import RestoredMessage, restore_last_messages
from utils.userdata import get_persona

logger = logging.getLogger("Zapomnim/AIAntiSpam")
client = AsyncOpenAI()

SPAM_DETECTION_PROMPT = """Ты анализируешь сообщения в чате на предмет спама. 

Определи, являются ли последние сообщения спамом. Спам - это:
- Повторяющиеся одинаковые или очень похожие сообщения
- Бессмысленные наборы символов или букв
- Массовая рассылка рекламы или ссылок
- Флуд (много коротких бессмысленных сообщений подряд)
- Попытки обойти фильтры спама

НЕ считай спамом:
- Обычные разговоры, даже если они быстрые
- Эмоциональные реакции (смех, восклицания)
- Исправления или дополнения к предыдущим сообщениям
- Короткие ответы в активном диалоге

Отвечай только "SPAM" если это явный спам, или "NOT_SPAM" если это обычное общение."""


async def check_spam_with_ai(messages: List[str]) -> tuple[bool, dict[str, int]]:
    """Отправляет сообщения в OpenAI для проверки на спам."""
    
    messages_text = "\n".join([f"Сообщение {i+1}: {msg}" for i, msg in enumerate(messages)])
    
    ai_chat = [
        {"role": "system", "content": SPAM_DETECTION_PROMPT},
        {"role": "user", "content": f"Проанализируй эти сообщения:\n\n{messages_text}"}
    ]
    
    resp = await client.chat.completions.create(
        model="gpt-5-nano",
        messages=ai_chat,
        reasoning_effort="medium",
        max_tokens=10,
        temperature=0.1
    )
    
    result = resp.choices[0].message.content.strip()
    is_spam = "SPAM" in result.upper()
    
    return is_spam, {
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
        "model": "gpt-5-nano",
        "result": result
    }


async def track_user_messages(user_id: int, chat_id: int) -> bool:
    """
    Отслеживает количество сообщений пользователя за последние 10 секунд.
    Возвращает True если превышен лимит (4+ сообщений за 10 секунд).
    """
    now = int(time.time())
    window_start = now - 10  # 10 секунд назад
    
    # Ключ для отслеживания сообщений пользователя в конкретном чате
    key = f"antispam:{user_id}:{chat_id}"
    
    # Удаляем старые записи и добавляем новую
    async with RedisSession.pipeline(transaction=True) as pipe:
        await pipe.zremrangebyscore(key, 0, window_start)
        await pipe.zadd(key, {f"{now}-{asyncio.get_event_loop().time()}": now})
        await pipe.zcard(key)
        await pipe.expire(key, 15)  # TTL 15 секунд
        _, _, count, _ = await pipe.execute()
    
    return count > 4


async def get_last_messages_for_spam_check(user_id: int, chat_id: int, session: AsyncSession) -> tuple[List[str], List[int]]:
    """Получает последние 10 сообщений пользователя из базы для анализа спама."""
    from sqlalchemy import select, desc
    from database.models import SavedMessage
    
    # Получаем последние 10 сообщений пользователя в этом чате
    stmt = (
        select(SavedMessage.text, SavedMessage.message_id)
        .where(
            SavedMessage.connected_user_id == user_id,
            SavedMessage.chat_id == chat_id,
            SavedMessage.text.isnot(None),
            SavedMessage.text != "",
            SavedMessage.message_id.isnot(None)
        )
        .order_by(desc(SavedMessage.created_at))
        .limit(10)
    )
    
    result = await session.execute(stmt)
    rows = result.fetchall()
    
    if not rows:
        return [], []
    
    # Возвращаем в хронологическом порядке (сначала старые)
    messages = [row[0] for row in reversed(rows) if row[0]]
    message_ids = [row[1] for row in reversed(rows) if row[1]]
    
    return messages, message_ids


async def delete_spam_messages(bot, user: User, chat_id: int, message_ids: List[int], session: AsyncSession) -> None:
    """Удаляет спам сообщения и отправляет их в ЛС пользователю."""
    
    try:
        # Удаляем сообщения через Business API
        await bot.delete_messages(
            chat_id=chat_id,
            message_ids=message_ids,
            business_connection_id=user.business_connection_id
        )
        
        # Получаем информацию об удаляемых сообщениях для отправки в ЛС
        restored = await restore_last_messages(user.id, chat_id, message_ids, session)
        if restored:
            chat = await get_persona(session, chat_id)
            
            # Отправляем удаленные сообщения в ЛС как обычно
            await send_deleted_info(
                bot=bot,
                user=user,
                chat=chat,
                restored_messages=restored,
                session=session,
                message_ids=message_ids,
            )
        
        logger.info(f"Удалено {len(message_ids)} спам сообщений от пользователя {user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении спам сообщений: {e}")


async def send_antispam_warning(message: Message) -> None:
    """Отправляет предупреждение о спаме."""
    try:
        await message.answer(
            "🚫 Обнаружен спам! Пожалуйста, не отправляйте повторяющиеся или бессмысленные сообщения.",
            disable_notification=True
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке предупреждения о спаме: {e}")


async def process_antispam_check(user: User, message: Message, session: AsyncSession) -> None:
    """
    Основная функция проверки антиспама.
    Вызывается для каждого нового сообщения.
    """
    
    # Проверяем включена ли функция антиспама
    antispam_enabled = await user.get_bool("settings.enhance_messages.ai_antispam", session, default=False)
    if not antispam_enabled:
        return
    
    # Проверяем превышение лимита сообщений
    is_flooding = await track_user_messages(message.from_user.id, message.chat.id)
    if not is_flooding:
        return
    
    logger.info(f"Пользователь {message.from_user.id} превысил лимит сообщений, проверяем на спам")
    
    # Получаем последние сообщения для анализа
    messages, message_ids = await get_last_messages_for_spam_check(message.from_user.id, message.chat.id, session)
    if len(messages) < 3:  # Мало данных для анализа
        return
    
    try:
        # Проверяем с помощью ИИ
        is_spam, usage = await check_spam_with_ai(messages)
        
        # Записываем метрику
        metric = Metric(
            connected_user_id=user.id if not user.privacy_mode else None,
            chat_id=message.chat.id if not user.privacy_mode else None,
            message_id=message.message_id if not user.privacy_mode else None,
            name="metrics.ai_antispam_check",
            value=json.dumps({**usage, "is_spam": is_spam})
        )
        session.add(metric)
        await session.commit()
        
        if is_spam:
            logger.info(f"ИИ определил спам от пользователя {message.from_user.id}")
            
            # Отправляем предупреждение
            await send_antispam_warning(message)
            
            # Удаляем спам сообщения (последние 5 сообщений, включая текущее)
            spam_message_ids = message_ids[-5:] + [message.message_id]
            await delete_spam_messages(message.bot, user, message.chat.id, spam_message_ids, session)
            
    except Exception as e:
        logger.error(f"Ошибка при проверке спама: {e}")