from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy import select, func, delete

from database import create_session
from database.models import SavedMessage
from keyboards.data_management import data_management_keyboard, confirm_clear_keyboard
from utils import get_user

router = Router()


async def _get_message_count(user_id: int, session):
    count = await session.scalar(
        select(func.count()).select_from(SavedMessage).where(SavedMessage.connected_user_id == user_id)
    )
    return count or 0


@router.callback_query(F.data == "data_settings")
async def data_settings(query: CallbackQuery):
    async with create_session() as session:
        user = await get_user(session, id=query.from_user.id)
        count = await _get_message_count(user.id, session)
    text = _("DATA_MANAGEMENT_TEXT").format(count=count)
    await query.message.edit_text(text=text, reply_markup=data_management_keyboard())


@router.callback_query(lambda c: c.data.startswith("clear_data"))
async def clear_data(query: CallbackQuery):
    parts = query.data.split(":")
    action = parts[1] if len(parts) > 1 else None

    if action is None:
        # step 1 confirmation
        await query.message.edit_text(
            text=_("CLEAR_DATA_CONFIRM1"),
            reply_markup=confirm_clear_keyboard(1)
        )
        return

    if action == "1":
        await query.message.edit_text(
            text=_("CLEAR_DATA_CONFIRM2"),
            reply_markup=confirm_clear_keyboard(2)
        )
        return

    if action == "2":
        async with create_session() as session:
            user = await get_user(session, id=query.from_user.id)
            await session.execute(
                delete(SavedMessage).where(SavedMessage.connected_user_id == user.id)
            )
            await session.commit()
            count = await _get_message_count(user.id, session)
        await query.answer(_("DATA_CLEARED_OK"), show_alert=True)
        text = _("DATA_MANAGEMENT_TEXT").format(count=count)
        await query.message.edit_text(text=text, reply_markup=data_management_keyboard())
        return

    # fallback
    await data_settings(query)
