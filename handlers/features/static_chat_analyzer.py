import asyncio
import json
import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import and_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from openai import AsyncOpenAI
from openai.types.responses import ResponseUsage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import STA_State
from database import create_session
from aiogram.utils.i18n import gettext as _
from database.models import SavedMessage, User, Metric, Persona
from handlers.menu import send_main_menu
from keyboards.static_chat_analyzer import STA_keyboard
from utils.messages import RestoredMessage, load_chat_with_user
from utils.userdata import get_persona, get_user

client = AsyncOpenAI()

logger = logging.getLogger('Zapomnim/StaticChatAnalyzer')
router = Router()


class Participant(BaseModel):
    name: str
    character: str
    psychological_profile: str
    mood: str
    manipulative_tendencies: str
    frequent_words: list[str]


class DialogueTopic(BaseModel):
    title: str
    description: str
    outcome: str | None


class DialogueData(BaseModel):
    participants: list[Participant]
    dialogue_topics: list[DialogueTopic]


async def send_request(messages: str, language: str = '', high_mode: bool = False) -> tuple[DialogueData, ResponseUsage]:
    response = await client.responses.create(
        model="o4-mini" if high_mode else "gpt-4.1-nano",
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"You are an expert static dialogue analyzer.\nYour task is to analyze a dialogue between users and provide the following data for each participant (ONLY 2 OBJECTS):\n\n* Character (briefly describe the personality traits of the participant)\n* Psychological profile (identify the personality type, internal motivations, stress resilience, etc.)\n* Mood (determine the participant’s emotional state during the dialogue)\n* Manipulative tendencies (determine and describe if the participant shows manipulative behavior and how it manifests)\n* Frequently used words and phrases (provide a list of 5–10 words or phrases most often used by this participant)\n\nAdditionally, analyze the entire dialogue and identify the main topics of discussion (for each topic, provide):\n\n* Title (short summary of the topic)\n* Description (detailed explanation of the discussed issue)\n* Outcome (state the result or conclusion reached by the participants on each topic; if no outcome is clear, indicate this)\n\nResponse Language: {language}"
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": messages
                    }
                ]
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "dialogue_schema",
                "schema": {
                    "type": "object",
                    "required": [
                        "participants",
                        "dialogue_topics"
                    ],
                    "properties": {
                        "participants": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": [
                                    "name",
                                    "character",
                                    "psychological_profile",
                                    "mood",
                                    "manipulative_tendencies",
                                    "frequent_words"
                                ],
                                "properties": {
                                    "mood": {
                                        "type": "string",
                                        "description": "Current mood of the participant."
                                    },
                                    "name": {
                                        "type": "string",
                                        "description": "Name of the participant."
                                    },
                                    "character": {
                                        "type": "string",
                                        "description": "Traits or characteristics of the participant."
                                    },
                                    "frequent_words": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "description": "Words frequently used by the participant."
                                    },
                                    "psychological_profile": {
                                        "type": "string",
                                        "description": "Psychological profile of the participant."
                                    },
                                    "manipulative_tendencies": {
                                        "type": "string",
                                        "description": "Tendency of the participant to manipulate."
                                    }
                                },
                                "additionalProperties": False
                            },
                            "description": "List of participants in the dialogue. (2 OBJECTS)"
                        },
                        "dialogue_topics": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": [
                                    "title",
                                    "description",
                                    "outcome"
                                ],
                                "properties": {
                                    "title": {
                                        "type": "string",
                                        "description": "Title of the topic."
                                    },
                                    "outcome": {
                                        "type": "string",
                                        "description": "Expected outcome of the topic."
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "Description of the topic."
                                    }
                                },
                                "additionalProperties": False
                            },
                            "description": "Topics of the dialogue."
                        }
                    },
                    "additionalProperties": False
                },
                "strict": True
            }
        },
        reasoning={
            "effort": "low",
        } if high_mode else {},
        tools=[],
        store=True
    )

    raw = response.output[int(high_mode)].content[0].text
    return DialogueData.model_validate_json(raw), response.usage


async def make_request(messages: list[RestoredMessage], user: User, high_mode: bool):
    lines = []

    for message in messages:
        if message.content_type != 'text':
            lines.append(f"> {message.persona.full_name}: [{message.content_type}]")
        else:
            lines.append(f"> {message.persona.full_name}:")

        if message.text is not None:
            lines.append(f"{message.text}")

        lines.append('')
        lines.append('')

    logger.info(lines)

    resp = await send_request('\n'.join(lines), _("LANG_NAME"), high_mode=high_mode)
    return resp


async def process_analysis(persona: Persona, user: User, session: AsyncSession):
    if not user.has_subscription:
        return None

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    high_usage = (await session.execute(
        select(Metric)
        .where(
            Metric.connected_user_id == user.id,
            Metric.name == 'metrics.static_chat_analyzer.high',
            Metric.created_at >= thirty_days_ago
        )
    )).scalars().all()

    low_usage = (await session.execute(
        select(Metric)
        .where(
            Metric.connected_user_id == user.id,
            Metric.name == 'metrics.static_chat_analyzer.low',
            Metric.created_at >= thirty_days_ago
        )
    )).scalars().all()


    logger.info(f'Found {len(high_usage)} high and {len(low_usage)} low usages for 30 days')

    if len(high_usage) < 5:
        high_mode = True
    elif len(low_usage) < 15:
        high_mode = False
    else:
        return None

    messages = await load_chat_with_user(user.id, persona.id, session, count=700 if high_mode else 300)
    logger.info(f'Found {len(messages)} messages')
    if len(messages) < 10:
        return -1

    data, usage = await make_request(messages, user, high_mode)

    response = _("STA_RESPONSE_TEMPLATE").format(
        receiver_first_name=persona.first_name,
        remaining_count=19-len(high_usage)-len(low_usage),
        participants='\n'.join(
            [_("STA_RESPONSE_PARTICIPANT_TEMPLATE").format(
                full_name=part.name,
                character=part.character,
                psychological_profile=part.psychological_profile,
                mood=part.mood,
                manipulative_tendencies=part.manipulative_tendencies,
                frequent_words=', '.join(part.frequent_words),
            ) for part in data.participants]
        ),
        topics='\n'.join([
            _("STA_RESPONSE_TOPIC_TEMPLATE").format(
                num=str(num + 1),
                title=topic.title,
                description=topic.description,
                result=topic.outcome,
            ) for num, topic in enumerate(data.dialogue_topics)]
        )
    )

    metric = Metric(
        connected_user_id=user.id,
        chat_id=persona.id if not user.privacy_mode else None,
        name='metrics.static_chat_analyzer.' + ('high' if high_mode else 'low'),
        value=usage.model_dump_json()
    )
    session.add(metric)
    await session.commit()

    return response


async def send_STA(bot: Bot, chat_id: int, user: User, state: FSMContext):
    await state.set_state(STA_State.select_user)

    m = await bot.send_message(
        chat_id,
        text=_("STA_START_TEXT"),
        reply_markup=STA_keyboard(),
    )

    await state.update_data({'message_id': m.message_id})


@router.callback_query(F.data == 'analyze')
async def sta_callback(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
    await send_STA(callback_query.bot, callback_query.message.chat.id, user, state=state)
    await callback_query.message.delete()


@router.message(and_f(F.user_shared, StateFilter(STA_State.select_user)))
async def on_chat_shared(message: Message, state: FSMContext):
    data = await state.get_data()
    m = data.get('message_id')
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=m)
    except:
        ...

    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)

        persona = await get_persona(session, message.user_shared.user_id)
        if persona is None:
            m = await message.answer(
                text=_("STA_INVALID_CHAT_ERROR"),
                reply_markup=STA_keyboard(),
            )

            await state.update_data({'message_id': m.message_id})
            return

        task = asyncio.create_task(process_analysis(persona, user, session))

        m: Message = await message.answer('⭐️ ' + _('STA_ANALYZING_CHAT'))

        c = False
        leaders = r'/-\|'
        while not task.done():
            await asyncio.sleep(1.5)
            c = not c

            await m.edit_text(('🌟 ' if c else '⭐️ ') + _('STA_ANALYZING_CHAT'))

        await m.delete()

        result = task.result()
        if result == -1:
            m = await message.answer(
                text=_("STA_INVALID_CHAT_ERROR"),
                reply_markup=STA_keyboard(),
            )

            await state.update_data({'message_id': m.message_id})
            return
        elif result is None:
            m = await message.answer(
                text=_("STA_NO_MORE_REQUESTS_ERROR"),
                reply_markup=STA_keyboard(),
            )

            await state.update_data({'message_id': m.message_id})
            return

        await message.answer(result)


@router.message(and_f(
    StateFilter(STA_State.select_user),
    F.text.startswith('👈')
))
async def on_back(message: Message, state: FSMContext):
    data = await state.get_data()
    m = data.get('message_id')
    await message.bot.delete_message(chat_id=message.chat.id, message_id=m)

    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)

    await send_main_menu(message.bot, message.chat.id, user)
    await message.delete()
