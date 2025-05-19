from typing import Optional, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from aiogram.utils.markdown import hblockquote
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User


class SettingsOption:
    """Модель опции для виджета настроек."""

    def __init__(self, option_id: str, name: str, description: str, default: bool):
        self.option_id = option_id
        self.name = name
        self.description = description
        self.default = default


async def settings_widget(
        user: User,
        session: AsyncSession,
        options: List[SettingsOption],
        message_callback: str,
        settings_id: str,
        back_id: str,
        title: str,
        description: str,
        toggle: Optional[str] = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Формирует текст и клавиатуру с настройками.

    :param user: Объект пользователя (User из вашей базы)
    :param session: Асинхронная сессия БД
    :param options: Список опций настроек
    :param message_callback: callback_data текущего сообщения (префикс)
    :param back_id: callback_data для кнопки «Назад»
    :param title: Заголовок виджета (например, "📝 Сохранение отредактированных")
    :param description: Описание виджета (например, "Сохраняет отредактированные сообщения")
    :param toggle: Идентификатор (option_id) опции, которую нужно переключить
    :return: (text, reply_markup) для использования в message.edit_text
    """

    if toggle is not None:
        for opt in options:
            if opt.option_id == toggle:
                current_value = await user.get_bool(
                    f"settings.{settings_id}.{opt.option_id}",
                    session,
                    default=opt.default
                )
                new_value = not current_value
                await user.set_bool(
                    f"settings.{settings_id}.{opt.option_id}",
                    new_value,
                    session
                )
                break

    text_lines = [f"<b>{title}</b>", ""]
    if description:
        text_lines.append(description)
        text_lines.append("")

    for idx, opt in enumerate(options, start=1):
        is_enabled = await user.get_bool(
            f"settings.{settings_id}.{opt.option_id}",
            session,
            default=opt.default
        )
        text_lines.append(
            f"<b>{idx}. {opt.name}</b>:\n{hblockquote(opt.description)}\n"
        )

    text = "\n".join(text_lines).strip()

    buttons = []
    for opt in options:
        is_enabled = await user.get_bool(
            f"settings.{settings_id}.{opt.option_id}",
            session,
            default=opt.default
        )
        label = ("✅ " if is_enabled else "") + opt.name
        callback_data = f"{message_callback}:toggle:{opt.option_id}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=callback_data)])

    buttons.append([InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data=back_id)])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    return text, reply_markup
