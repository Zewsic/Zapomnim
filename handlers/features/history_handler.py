from typing import List

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.utils.i18n import gettext as _

from database import create_session
from utils import get_user
from utils.messages import RestoredMessage, load_message_history
from utils.userdata import get_persona

router = Router()


def history_keyboard(chat_id: int, message_id: int, index: int, total: int) -> InlineKeyboardMarkup:
    prev_index = max(0, index - 1)
    next_index = min(total - 1, index + 1)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"history:{chat_id}:{message_id}:{prev_index}"),
            InlineKeyboardButton(text="➡️", callback_data=f"history:{chat_id}:{message_id}:{next_index}")
        ],
        [
            InlineKeyboardButton(text="<<<", callback_data=f"history:{chat_id}:{message_id}:0"),
            InlineKeyboardButton(text="❌", callback_data="history_close"),
            InlineKeyboardButton(text=">>>", callback_data=f"history:{chat_id}:{message_id}:{total - 1}")
        ],
        [
            InlineKeyboardButton(text="📁 Export", callback_data=f"history_export:{chat_id}:{message_id}")
        ]
    ])


async def format_history_message(msg: RestoredMessage, chat_name: str, message_id: int) -> str:
    content_type_str = _(f"EDITED_CONTENT_TYPE_{msg.content_type.value.upper()}")
    return (
        f"<b>📝 {content_type_str} от {msg.persona.hname if msg.persona else 'Unknown'}:</b>\n"
        f"\n"
        f"<blockquote expandable>{msg.text or _('NONE')}</blockquote>\n"
        f"\n"
        f"<i>Чат: {chat_name}, Сообщение #{message_id}</i> "
    )


@router.callback_query(F.data.startswith("history:"))
async def show_history(query: CallbackQuery):
    parts = query.data.split(":")
    chat_id = int(parts[1])
    message_id = int(parts[2])
    index = int(parts[3])

    async with create_session() as session:
        user = await get_user(id=query.from_user.id, session=session)
        if not user:
            await query.answer("Unknown user", show_alert=True)
            return

        history: List[RestoredMessage] = await load_message_history(user.id, chat_id, message_id, session)
        if not history:
            await query.answer("No history")
            return
        total = len(history)
        index = max(0, min(index, total - 1))
        msg = history[index]
        chat = await get_persona(session, chat_id)
        text = format_history_message(msg, chat.hname, message_id)
        await query.message.edit_text(text, reply_markup=history_keyboard(chat_id, message_id, index, total))
        await query.answer()


@router.callback_query(F.data == "history_close")
async def close_history(query: CallbackQuery):
    await query.message.edit_reply_markup(reply_markup=None)
    await query.answer()


@router.callback_query(F.data.startswith("history_export:"))
async def export_history(query: CallbackQuery):
    _, chat_id, message_id = query.data.split(":")
    chat_id = int(chat_id)
    message_id = int(message_id)

    async with create_session() as session:
        user = await get_user(id=query.from_user.id, session=session)
        if not user:
            await query.answer("Unknown user", show_alert=True)
            return
        history = await load_message_history(user.id, chat_id, message_id, session)

    # Placeholder: create empty file
    buf = b""
    file = BufferedInputFile(buf, filename="history.txt")
    await query.message.answer_document(file)
    await query.answer()
