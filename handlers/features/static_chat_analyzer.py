"""Handlers and helpers for the static chat analyzer feature."""

import asyncio
import json
import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter, and_f
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import STA_State
from database import create_session
from database.models import Metric, Persona, User
from handlers.menu import send_main_menu
from keyboards import continue_keyboard
from keyboards.static_chat_analyzer import STA_keyboard
from utils.messages import stringify_messages
from utils.userdata import get_persona, get_user

client = AsyncOpenAI()

logger = logging.getLogger("Zapomnim/StaticChatAnalyzer")
router = Router()

CONTEXT_MISSING = -1
ANALYSIS_ERROR = -2
MAX_HIGH_USAGE = 5
MAX_LOW_USAGE = 15
MAX_REMAINING_COUNT = 19
HIGH_MODE_MESSAGES = 700
LOW_MODE_MESSAGES = 300

PROMPT_TEMPLATE = (
    "You are an expert static dialogue analyzer.\n"
    "Your task is to analyze a dialogue between users and provide the following data for each "
    "participant (ONLY 2 OBJECTS):\n\n"
    "* Character (briefly describe the personality traits of the participant)\n"
    "* Psychological profile (identify the personality type, internal motivations, stress resilience, etc.)\n"
    "* Mood (determine the participant's emotional state during the dialogue)\n"
    "* Manipulative tendencies (determine and describe if the participant shows manipulative behavior and how it manifests)\n"
    "* Frequently used words and phrases (provide a list of 5-10 words or phrases most often used by this participant)\n\n"
    "Additionally, analyze the entire dialogue and identify the main topics of discussion (for each topic, provide):\n\n"
    "* Title (short summary of the topic)\n"
    "* Description (detailed explanation of the discussed issue)\n"
    "* Outcome (state the result or conclusion reached by the participants on each topic; if no outcome is clear, indicate this)\n\n"
    "Response Language: {language}"
)


class Participant(BaseModel):
    """Structured description of a dialogue participant."""

    name: str
    character: str
    psychological_profile: str
    mood: str
    manipulative_tendencies: str
    frequent_words: list[str]


class DialogueTopic(BaseModel):
    """Topic discussed in the dialogue."""

    title: str
    description: str
    outcome: str | None


class DialogueData(BaseModel):
    """Result structure returned by the static analyzer."""

    participants: list[Participant]
    dialogue_topics: list[DialogueTopic]


async def send_request(
    messages: str,
    language: str = "",
    high_mode: bool = False,
) -> tuple[
    DialogueData,
    dict[str, int | str],
]:
    """Call the OpenAI Responses API and return structured dialogue data."""
    model = "gpt-5-mini"
    response = await client.responses.create(
        model=model,
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are an expert static dialogue analyzer.\n"
                            "Your task is to analyze a dialogue between users and provide the following data "
                            "for each participant (ONLY 2 OBJECTS):\n\n"
                            "* Character (briefly describe the personality traits of the participant)\n"
                            "* Psychological profile (identify the personality type, internal motivations, stress resilience, etc.)\n"
                            "* Mood (determine the participant’s emotional state during the dialogue)\n"
                            "* Manipulative tendencies (determine and describe if the participant shows manipulative behavior and how it manifests)\n"
                            "* Frequently used words and phrases (provide a list of 5-10 words or phrases most often used by this participant)\n\n"
                            "Additionally, analyze the entire dialogue and identify the main topics of discussion "
                            "(for each topic, provide):\n\n"
                            "* Title (short summary of the topic)\n"
                            "* Description (detailed explanation of the discussed issue)\n"
                            "* Outcome (state the result or conclusion reached by the participants on each topic; if no outcome is clear, indicate this)\n\n"
                            f"Response Language: {language}"
                        ),
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": messages,
                    },
                ],
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
                        "dialogue_topics",
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
                                    "frequent_words",
                                ],
                                "properties": {
                                    "mood": {
                                        "type": "string",
                                        "description": "Current mood of the participant.",
                                    },
                                    "name": {
                                        "type": "string",
                                        "description": "Name of the participant.",
                                    },
                                    "character": {
                                        "type": "string",
                                        "description": "Traits or characteristics of the participant.",
                                    },
                                    "frequent_words": {
                                        "type": "array",
                                        "items": {
                                            "type": "string",
                                        },
                                        "description": "Words frequently used by the participant.",
                                    },
                                    "psychological_profile": {
                                        "type": "string",
                                        "description": "Psychological profile of the participant.",
                                    },
                                    "manipulative_tendencies": {
                                        "type": "string",
                                        "description": "Tendency of the participant to manipulate.",
                                    },
                                },
                                "additionalProperties": False,
                            },
                            "description": "List of participants in the dialogue. (2 OBJECTS)",
                        },
                        "dialogue_topics": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": [
                                    "title",
                                    "description",
                                    "outcome",
                                ],
                                "properties": {
                                    "title": {
                                        "type": "string",
                                        "description": "Title of the topic.",
                                    },
                                    "outcome": {
                                        "type": "string",
                                        "description": "Expected outcome of the topic.",
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "Description of the topic.",
                                    },
                                },
                                "additionalProperties": False,
                            },
                            "description": "Topics of the dialogue.",
                        },
                    },
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
        reasoning={
            "effort": "high" if high_mode else "medium",
        },
        tools=[],
    )

    if not response.output:
        logger.error("Empty response from OpenAI static chat analyzer: %s", response)
        error_message = "Empty response from OpenAI static chat analyzer"
        raise ValueError(error_message)

    output_entry = response.output[0]
    raw_text = None
    for content_item in getattr(output_entry, "content", []):
        text_value = getattr(content_item, "text", None)
        if text_value:
            raw_text = text_value
            break

    if raw_text is None:
        logger.error("No text payload in OpenAI response: %s", response)
        error_message = "OpenAI response does not contain text payload"
        raise ValueError(error_message)

    return DialogueData.model_validate_json(raw_text), {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "model": model,
    }


async def process_analysis(persona: Persona, user: User, session: AsyncSession):
    """Process the static chat analysis for the given persona and user.

    Args:
    - persona (Persona): The persona to analyze.
    - user (User): The user who initiated the analysis.
    - session (AsyncSession): The database session.

    Returns:
    - str: The analysis result or an error message.

    """
    if not user.has_subscription:
        return None

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    high_usage = (
        (
            await session.execute(
                select(Metric).where(
                    Metric.connected_user_id == user.id,
                    Metric.name == "system.static_chat_analyzer.high",
                    Metric.created_at >= thirty_days_ago,
                ),
            )
        )
        .scalars()
        .all()
    )

    low_usage = (
        (
            await session.execute(
                select(Metric).where(
                    Metric.connected_user_id == user.id,
                    Metric.name == "system.static_chat_analyzer.low",
                    Metric.created_at >= thirty_days_ago,
                ),
            )
        )
        .scalars()
        .all()
    )

    logger.info("Found %s high and %s low usages for 30 days", len(high_usage), len(low_usage))

    if len(high_usage) < MAX_HIGH_USAGE:
        high_mode = True
    elif len(low_usage) < MAX_LOW_USAGE:
        high_mode = False
    else:
        return None

    context = await stringify_messages(
        user.id,
        persona.id,
        session,
        count=HIGH_MODE_MESSAGES if high_mode else LOW_MODE_MESSAGES,
        min_messages=-1,
    )
    if not context:
        return CONTEXT_MISSING
    try:
        data, usage = await send_request(context, _("LANG_NAME"), high_mode=high_mode)
    except Exception as exc:
        logger.exception("Static chat analysis request failed", exc_info=exc)
        return ANALYSIS_ERROR

    response = _("STA_RESPONSE_TEMPLATE").format(
        receiver_first_name=persona.first_name,
        remaining_count=MAX_REMAINING_COUNT - len(high_usage) - len(low_usage),
        participants="\n".join(
            [
                _("STA_RESPONSE_PARTICIPANT_TEMPLATE").format(
                    full_name=part.name,
                    character=part.character,
                    psychological_profile=part.psychological_profile,
                    mood=part.mood,
                    manipulative_tendencies=part.manipulative_tendencies,
                    frequent_words=", ".join(part.frequent_words),
                )
                for part in data.participants
            ],
        ),
        topics="\n".join(
            [
                _("STA_RESPONSE_TOPIC_TEMPLATE").format(
                    num=str(num + 1),
                    title=topic.title,
                    description=topic.description,
                    result=topic.outcome,
                )
                for num, topic in enumerate(data.dialogue_topics)
            ],
        ),
    )

    metric = Metric(
        connected_user_id=user.id,
        chat_id=persona.id if not user.privacy_mode else None,
        name="system.static_chat_analyzer." + ("high" if high_mode else "low"),
        value=json.dumps(usage),
    )
    session.add(metric)
    await session.commit()

    return response


async def send_STA(bot: Bot, chat_id: int, user: User, state: FSMContext):
    """Send the static chat analysis to the user.

    Args:
    - bot (Bot): The bot instance.
    - chat_id (int): The chat ID.
    - user (User): The user who initiated the analysis.
    - state (FSMContext): The finite state machine context.

    """
    if not user.is_working:
        await bot.send_message(
            chat_id,
            text=_("SUBSCRIPTION_REQUIRED_ERROR"),
            reply_markup=continue_keyboard("profile"),
        )
        return
    if user.privacy_mode:
        await bot.send_message(
            chat_id,
            text=_("UNAVAILABLE_IN_PRIVACY_MODE"),
            reply_markup=continue_keyboard("menu"),
        )
        return

    await state.set_state(STA_State.select_user)

    m = await bot.send_message(
        chat_id,
        text=_("STA_START_TEXT"),
        reply_markup=STA_keyboard(),
    )

    await state.update_data({"message_id": m.message_id})


@router.callback_query(F.data == "analyze")
async def sta_callback(callback_query: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback_query.from_user.id)
        if user.privacy_mode:
            await callback_query.answer(_("UNAVAILABLE_IN_PRIVACY_MODE"), show_alert=True)
            return
    await send_STA(callback_query.bot, callback_query.message.chat.id, user, state=state)
    await callback_query.message.delete()


@router.message(and_f(F.user_shared, StateFilter(STA_State.select_user)))
async def on_chat_shared(message: Message, state: FSMContext):
    data = await state.get_data()
    m: int = data.get("message_id")
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=m)
    except:
        ...

    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)

        persona = await get_persona(session, message.user_shared.user_id)
        if persona is None:
            msg = await message.answer(
                text=_("STA_INVALID_CHAT_ERROR"),
                reply_markup=STA_keyboard(),
            )

            await state.update_data({"message_id": msg.message_id})
            return

        task = asyncio.create_task(process_analysis(persona, user, session))

        m: Message = await message.answer("⭐️ " + _("STA_ANALYZING_CHAT"))

        c = False
        while not task.done():
            await asyncio.sleep(1.5)
            c = not c

            await m.edit_text(("🌟 " if c else "⭐️ ") + _("STA_ANALYZING_CHAT"))

        await m.delete()

        try:
            result = task.result()
        except Exception as exc:
            logger.exception("Static chat analysis processing error", exc_info=exc)
            msg = await message.answer(
                text=_("STA_PROCESSING_ERROR"),
                reply_markup=STA_keyboard(),
            )
            await state.update_data({"message_id": msg.message_id})
            return

        if result == CONTEXT_MISSING:
            msg = await message.answer(
                text=_("STA_INVALID_CHAT_ERROR"),
                reply_markup=STA_keyboard(),
            )
            await state.update_data({"message_id": msg.message_id})
            return
        if result == ANALYSIS_ERROR:
            msg = await message.answer(
                text=_("STA_PROCESSING_ERROR"),
                reply_markup=STA_keyboard(),
            )
            await state.update_data({"message_id": msg.message_id})
            return

        await message.answer(result)


@router.message(
    and_f(
        StateFilter(STA_State.select_user),
        F.text.startswith("👈"),
    ),
)
async def on_back(message: Message, state: FSMContext):
    data = await state.get_data()
    m = data.get("message_id")
    await message.bot.delete_message(chat_id=message.chat.id, message_id=m)

    async with create_session() as session:
        user = await get_user(session, id=message.from_user.id)

    await send_main_menu(message.bot, message.chat.id, user)
    await message.delete()
