
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, KeyboardButtonRequestUser, ReplyKeyboardMarkup
from aiogram.utils.i18n import gettext as _


def get_main_stats_keyboard(interlocutor_id: int | None, selected_period: str) -> InlineKeyboardMarkup:
    choose_user_text = _("STATISTICS_PERIOD_ALL_CHATS_BUTTON") if interlocutor_id else _("STATISTICS_PERIOD_SELECT_CHAT_BUTTON")

    def get_period_text(key: str):
        text = _(f"STATISTICS_PERIOD_BUTTON_{key.upper()}")
        if selected_period == key:
            text = f"👉 {text} 👈"
        return text

    kb = [
        [
            InlineKeyboardButton(text=get_period_text("day"), callback_data="stat:period:day"),
            InlineKeyboardButton(text=get_period_text("week"), callback_data="stat:period:week"),
        ],
        [
            InlineKeyboardButton(text=get_period_text("month"), callback_data="stat:period:month"),
            InlineKeyboardButton(text=get_period_text("year"), callback_data="stat:period:year"),
        ],
        [
            InlineKeyboardButton(text=choose_user_text, callback_data="stat:choose_user"),
        ],
        [
            InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def select_user_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(
            text=_("STATISTICS_SELECT_CHAT_BUTTON"),
            request_user=KeyboardButtonRequestUser(request_id=123, user_is_bot=False),
        )],
        [KeyboardButton(
            text=_("BACK_BUTTON"),
        )],
    ], resize_keyboard=True, one_time_keyboard=False)
