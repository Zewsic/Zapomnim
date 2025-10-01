from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy import delete, func, select

from database import create_session
from database.models import Metric, SavedMessage
from keyboards import continue_keyboard
from keyboards.data_management import back_keyboard, confirm_clear_keyboard, data_management_keyboard
from utils import get_user
from utils.messages import anonymize_metrics

router = Router()


async def _get_message_count(user_id: int, session):
    count = await session.scalar(
        select(func.count()).select_from(SavedMessage).where(SavedMessage.connected_user_id == user_id),
    )
    return count or 0


async def _get_metric(user_id: int, name: str, session):
    r = (await session.execute(
        select(Metric)
        .where(
            Metric.connected_user_id == user_id,
            Metric.name == name,
        ),
    )).scalars().all()
    return len(r)


async def _get_metrics(user_id: int, session):
    return {
        "deleted_messages_count": await _get_metric(user_id, "metrics.save_deleted_messages", session),
        "edited_messages_count": await _get_metric(user_id, "metrics.save_edited_messages", session),
        "protected_messages_count": await _get_metric(user_id, "metrics.save_protected_messages", session),
        "transcribed_voice_count": await _get_metric(user_id, "metrics.transcribe_voice_message", session),
        "chat_analyzed_count": await _get_metric(user_id, "system.static_chat_analyzer.high", session) + await _get_metric(user_id, "system.static_chat_analyzer.low", session),
    }


@router.callback_query(F.data == "data_settings")
async def data_settings(query: CallbackQuery):
    async with create_session() as session:
        user = await get_user(session, id=query.from_user.id)

        if user.privacy_mode:
            await query.message.edit_text(text=_("DATA_MANAGEMENT_UNAVAILABLE_IN_PRIVACY_MODE"),
                                          reply_markup=back_keyboard())
            return

        saved_messages_count = await _get_message_count(user.id, session)
        metrics = await _get_metrics(user.id, session)

    text = _("DATA_MANAGEMENT_TEXT").format(
        saved_messages_count=saved_messages_count,
        **metrics,
    )
    await query.message.edit_text(text=text, reply_markup=data_management_keyboard())


@router.callback_query(lambda c: c.data.startswith("clear_data"))
async def clear_data(query: CallbackQuery):
    parts = query.data.split(":")
    action = parts[1] if len(parts) > 1 else None

    if action is None:
        # step 1 confirmation
        await query.message.edit_text(
            text=_("CLEAR_DATA_CONFIRM1"),
            reply_markup=confirm_clear_keyboard(1),
        )
        return

    if action == "1":
        await query.message.edit_text(
            text=_("CLEAR_DATA_CONFIRM2"),
            reply_markup=confirm_clear_keyboard(2),
        )
        return

    if action == "2":
        async with create_session() as session:
            user = await get_user(session, id=query.from_user.id)
            await session.execute(
                delete(SavedMessage).where(SavedMessage.connected_user_id == user.id),
            )
            await anonymize_metrics(user.id, session)
            await session.commit()
        await query.message.edit_text(text=_("DATA_CLEARED_OK"), reply_markup=continue_keyboard("data_management"))
        return

    # fallback
    await data_settings(query)
