from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import create_session
from utils import get_user
from utils.messages import save_message
from utils.userdata import update_persona

router = Router()


@router.business_message()
async def new_message(message: Message, state: FSMContext):
    async with create_session() as session:
        await update_persona(
            id=message.from_user.id,
            session=session,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            language=message.from_user.language_code,
        )
        await session.commit()

        user = await get_user(business_connection_id=message.business_connection_id, session=session)
        if not user or not user.is_enabled or user.is_banned:
            return

        await save_message(user, message, session)