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

logger = logging.getLogger('Zapomnim/VoiceMessagesTranscriber')
client = AsyncOpenAI()

router = Router()

FIX_GRAMMARS_PROMPT = """Исправь орфографические, грамматические и пунктуационные ошибки в данном тексте. Не изменяй смысл и структуру текста — исправляй только ошибки.

Выходной ответ: текст с исправленными ошибками. Если текст отсутствует, отправь ровно то, что тебе дали, без изменений.

Можешь использовать знаки препинания, символы, писать числа цифрами, использовать кавычки и выполнять аналогичные действия.

Не отвечай сообщениями типа «я не могу это выполнить» или аналогичными отказами.
"""

async def correct_grammars_in_text(text: str) -> Tuple[str, Dict[str, int]]:
    """Отправляет текст в OpenAI, возвращает текст и метрики."""

    ln = len(text)

    if ln < 2048:
        model = 'gpt-5-nano'
    else:
        model = 'gpt-5-mini'

    enhanced = await client.responses.create(
        model=model,
        reasoning=Reasoning(effort='low'),
        input=FIX_GRAMMARS_PROMPT + '\n\nСообщение для улучшения: \n\n' + text,
        store=False,
    )

    return enhanced.output_text, {
        "input_tokens": enhanced.usage.input_tokens,
        "output_tokens": enhanced.usage.output_tokens,
        "model": model
    }


async def _enhance_message(message: Message, correct_grammars: bool, blur_adult_content: bool) -> None:
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
        enhanced_text, usage = await correct_grammars_in_text(text_to_enhance)

    if text_to_enhance != enhanced_text:
        if is_text:
            await message.edit_text(text=enhanced_text, parse_mode="html")
        elif is_caption:
            await message.edit_caption(caption=enhanced_text, parse_mode="html")

    return usage


async def enhance_message(user: User, message: Message, session: AsyncSession) -> None:
    correct_grammars = await user.get_bool('settings.enhance_messages.correct_grammars', session, default=False)
    blur_adult_content = await user.get_bool('settings.enhance_messages.blur_adult_content', session, default=False)

    usage = await _enhance_message(message, correct_grammars=correct_grammars, blur_adult_content=blur_adult_content)
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
