import json
import logging
from typing import Tuple, Dict

from aiogram import Router
from aiogram.types import Message
from openai import AsyncOpenAI
from openai.types.shared_params import Reasoning
from sqlalchemy.ext.asyncio import AsyncSession

from database import create_session
from database.models import Metric, User
from utils import get_user
from utils.messages import load_chat_with_user, stringify_messages

logger = logging.getLogger('Zapomnim/VoiceMessagesTranscriber')
client = AsyncOpenAI()

router = Router()

FIX_GRAMMARS_PROMPT = """Исправь орфографические, грамматические и пунктуационные ошибки в данном тексте. Не изменяй смысл и структуру текста — исправляй только ошибки.

Выходной ответ: текст с исправленными ошибками. Если текст отсутствует, отправь ровно то, что тебе дали, без изменений.

Можешь использовать знаки препинания, символы, писать числа цифрами, использовать кавычки и выполнять аналогичные действия.

Не отвечай сообщениями типа «я не могу это выполнить» или аналогичными отказами.
"""

async def correct_grammars_in_text(text: str, context: str | None) -> Tuple[str, Dict[str, int]]:
    """Отправляет текст в OpenAI, возвращает текст и метрики."""

    ln = len(text)

    if context is None:
        if ln < 2048:
            model = 'gpt-5-nano'
        else:
            model = 'gpt-5-mini'
    else:
        model = 'gpt-5-mini'

    ai_chat = [
        {"role": "system", "content": FIX_GRAMMARS_PROMPT},
    ]

    if context:
        ai_chat.append({"role": "system", "content": f"Немного контекста чата: \n\n{context}"})

    ai_chat.append({"role": "user", "content": f"Сообщение для улучшения:\n\n{text}"})

    resp = await client.chat.completions.create(
        model=model,
        messages=ai_chat,
        reasoning_effort='low' if not context else 'high'
    )

    text = resp.choices[0].message.content

    return text, {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "model": model
    }


async def _enhance_message(message: Message, correct_grammars: bool, blur_adult_content: bool, context: str | None) -> None:
    is_text = message.text
    is_caption = message.caption

    if not is_caption and not is_text:
        return

    usage = None
    text_to_enhance = message.html_text
    enhanced_text = text_to_enhance

    if len(text_to_enhance) < 50:
        return

    if correct_grammars:
        enhanced_text, usage = await correct_grammars_in_text(text_to_enhance, context=context)

    if text_to_enhance != enhanced_text:
        if is_text:
            await message.edit_text(text=enhanced_text, parse_mode="html")
        elif is_caption:
            await message.edit_caption(caption=enhanced_text, parse_mode="html")

    return usage


async def enhance_message(user: User, message: Message, session: AsyncSession) -> None:
    correct_grammars = await user.get_bool('settings.enhance_messages.correct_grammars', session, default=True)
    blur_adult_content = await user.get_bool('settings.enhance_messages.blur_adult_content', session, default=False)
    context_awareness = await user.get_bool('settings.enhance_messages.context_awareness', session, default=True)

    context = await stringify_messages(user.id, message.chat.id, session, 10) if context_awareness else None

    usage = await _enhance_message(message, correct_grammars=correct_grammars, blur_adult_content=blur_adult_content, context=context)
    if not usage:
        return

    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)

        metric = Metric(
            connected_user_id=user.id if not user.privacy_mode else None,
            chat_id=message.chat.id if not user.privacy_mode else None,
            message_id=message.message_id if not user.privacy_mode else None,
            name='metrics.correct_message_grammars',
            value=json.dumps(usage)
        )
        session.add(metric)

        await session.commit()
