import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    BufferedInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.utils.i18n import gettext as _
from sqlalchemy import select, and_

from database import create_session
from database.models import SavedMessage, Persona
from utils import get_user
from utils.statistics import (
    calculate_statistics,
    filter_messages_by_options,
    render_activity_chart,
    render_in_out_pie,
    render_top_interlocutors_bar,
    render_heatmap,
)

router = Router()

# Значения по умолчанию для настроек
DEFAULT_OPTIONS = {
    "period": "week",       # day | week | month | all | custom
    "type_filter": "all",   # all | incoming | outgoing
    "interlocutor_id": None,  # ID собеседника (None = все)
    "graph_type": None,       # None, "activity", "pie", "top_interlocutors", "heatmap"
    "output_format": "text",  # text | graph
    "start_date": None,       # используется для custom периода
    "end_date": None,
}


# -------------------------------------------------------------------
# Вспомогательные функции для формирования клавиатуры
# -------------------------------------------------------------------

def _mark(text: str, active: bool) -> str:
    """
    Префикс "✅ " для выделения текущего выбранного пункта.
    """
    return ("✅ " if active else "") + text


def statistics_main_keyboard(options: dict) -> InlineKeyboardMarkup:
    """
    Основная клавиатура с настройками периода, типа фильтра и форматами вывода.
    """
    period = options.get("period", "week")
    type_filter = options.get("type_filter", "all")
    out_fmt = options.get("output_format", "text")

    # Для наглядности создадим несколько рядов кнопок
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_PERIOD_DAY"), period == "day"),
                callback_data="stat:period:day",
            ),
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_PERIOD_WEEK"), period == "week"),
                callback_data="stat:period:week",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_PERIOD_MONTH"), period == "month"),
                callback_data="stat:period:month",
            ),
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_PERIOD_ALL"), period == "all"),
                callback_data="stat:period:all",
            )
        ],
        [
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_FILTER_ALL"), type_filter == "all"),
                callback_data="stat:type:all"
            ),
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_FILTER_INCOMING"), type_filter == "incoming"),
                callback_data="stat:type:incoming"
            ),
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_FILTER_OUTGOING"), type_filter == "outgoing"),
                callback_data="stat:type:outgoing"
            ),
        ],
        [
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_FORMAT_TEXT"), out_fmt == "text"),
                callback_data="stat:format:text"
            ),
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_FORMAT_GRAPH"), out_fmt == "graph"),
                callback_data="stat:format:graph"
            )
        ],
        [InlineKeyboardButton(text=options.get('interlocutor_id') or _("STATISTICS_CHOOSE_INTERLOCUTOR"), callback_data="stat:choose_interlocutor")],
        [InlineKeyboardButton(text=_("STATISTICS_CHOOSE_CUSTOM_PERIOD"), callback_data="stat:choose_period")],
        [
            InlineKeyboardButton(
                text=_("STATISTICS_NEXT_STEP"),
                callback_data="stat:graphs_menu",
            )
        ],
        [InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="menu")]
    ])
    return kb


def statistics_graphs_keyboard(options: dict) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора конкретного типа графика (или вывод текста).
    """
    graph_type = options.get("graph_type")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_GRAPH_ACTIVITY"), graph_type == "activity"),
                callback_data="stat:graph:activity",
            ),
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_GRAPH_IN_OUT"), graph_type == "pie"),
                callback_data="stat:graph:pie",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_GRAPH_TOP_INTERLOCUTORS"), graph_type == "top_interlocutors"),
                callback_data="stat:graph:top_interlocutors",
            ),
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_GRAPH_HEATMAP"), graph_type == "heatmap"),
                callback_data="stat:graph:heatmap",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_("STATISTICS_SHOW_BUTTON"),
                callback_data="stat:show"
            )
        ],
        [InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="stat:back_to_main")]
    ])
    return kb


# -------------------------------------------------------------------
# Хендлеры
# -------------------------------------------------------------------

@router.callback_query(F.data == "statistics")
async def statistics_menu_handler(callback: CallbackQuery, state: FSMContext):
    """
    Хендлер, вызываемый при переходе в меню "Статистика".
    """
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)
        if user.privacy_mode:
            await callback.answer(_("STATISTICS_PRIVATE_ERROR"), show_alert=True)
            return

    data = await state.get_data()
    options = data.get("statistics_options", DEFAULT_OPTIONS.copy())
    await state.update_data(statistics_options=options)

    await callback.message.delete()
    await callback.message.answer(
        text=_("STATISTICS_TITLE"),
        reply_markup=statistics_main_keyboard(options)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("stat:"))
async def statistics_callback_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обработка нажатий на кнопки клавиатуры статистики.
    """
    parts = callback.data.split(":")  # Пример: ["stat", "period", "day"]
    action = parts[1] if len(parts) > 1 else None
    value = parts[2] if len(parts) > 2 else None

    data = await state.get_data()
    options = data.get("statistics_options", DEFAULT_OPTIONS.copy())

    if action == "period":
        # Устанавливаем предустановленный период
        options["period"] = value
        # Сбрасываем custom-дату, если пользователь выбрал готовый период
        options["start_date"] = None
        options["end_date"] = None

    elif action == "type":
        # Фильтр по типу (all/incoming/outgoing)
        options["type_filter"] = value

    elif action == "format":
        # Формат вывода (текст или график)
        options["output_format"] = value

    elif action == "graphs_menu":
        # Переходим к меню выбора графиков
        await state.update_data(statistics_options=options)
        await callback.message.edit_text(
            text=_("STATISTICS_GRAPH_MENU_TITLE"),
            reply_markup=statistics_graphs_keyboard(options)
        )
        await callback.answer()
        return

    elif action == "graph":
        # Выбираем конкретный тип графика
        options["graph_type"] = value

    elif action == "show":
        # Показать статистику (текст/график)
        await state.update_data(statistics_options=options)
        await show_statistics(callback, options)
        return

    elif action == "back_to_main":
        # Назад к основной клавиатуре
        await state.update_data(statistics_options=options)
        await callback.message.edit_text(
            text=_("STATISTICS_TITLE"),
            reply_markup=statistics_main_keyboard(options)
        )
        await callback.answer()
        return

    elif action == "choose_interlocutor":
        # Переходим к выбору собеседника
        await list_interlocutors(callback, options)
        return

    elif action == "choose_period":
        # Переходим к вводу кастомного периода
        await callback.message.answer(_("STATISTICS_CUSTOM_PERIOD_INSTRUCTION"))
        await callback.answer()
        return

    await state.update_data(statistics_options=options)
    await callback.message.edit_text(
        text=_("STATISTICS_TITLE"),
        reply_markup=statistics_main_keyboard(options)
    )
    await callback.answer()


@router.message(lambda m: m.text and "=>" in m.text)
async def custom_period_handler(message: Message, state: FSMContext):
    """
    Пример: пользователь вводит "2023-04-01 => 2023-04-10"
    """
    data = await state.get_data()
    options = data.get("statistics_options", DEFAULT_OPTIONS.copy())

    try:
        text = message.text.strip()
        start_str, end_str = text.split("=>")
        start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d")
        end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d")

        # Если нужно, можно проверять, чтобы end_date >= start_date
        if start_date > end_date:
            raise ValueError()

        # Устанавливаем кастомный период
        options["period"] = "custom"
        options["start_date"] = start_date
        options["end_date"] = end_date

        await state.update_data(statistics_options=options)
        await message.answer(_("STATISTICS_CUSTOM_PERIOD_SAVED"))
    except Exception as e:
        logging.error(f"Error parsing custom period: {e}")
        await message.answer(_("STATISTICS_CUSTOM_PERIOD_ERROR"))


async def list_interlocutors(callback: CallbackQuery, options: dict):
    """
    Вывод списка собеседников, чтобы пользователь мог выбрать конкретного.
    """
    async with create_session() as session:
        # Получаем список пользователей, с которыми были сообщения
        # Допустим, по connected_user_id - либо, если ваша логика другая, адаптируйте запрос
        # Здесь предполагается, что Persona.id - это chat_id собеседника, 
        # или же вы храните в SavedMessage ещё что-то для идентификации собеседника.

        # Пример: получить всех уникальных chat_id, кроме самого current_user
        # (но это зависит от вашей структуры БД)
        # callback.from_user.id - это id в нашей системе user?
        # Возможно, вам придётся адаптировать логику.

        user_db = await get_user(session, id=callback.from_user.id)
        if not user_db:
            await callback.answer(_("STATISTICS_NO_USERS"), show_alert=True)
            return

        stmt = select(SavedMessage.chat_id).where(
            and_(
                SavedMessage.connected_user_id == user_db.id,
                SavedMessage.chat_id.is_not(None)
            )
        ).group_by(-SavedMessage.id).group_by(SavedMessage.chat_id)

        rows = (await session.execute(stmt)).all()
        interlocutor_ids = [r[0] for r in rows if r[0] is not None]

        # Загружаем записи из таблицы Persona, например:
        if not interlocutor_ids:
            await callback.answer(_("STATISTICS_NO_USERS"), show_alert=True)
            return

        stmt_personas = select(Persona).where(Persona.id.in_(interlocutor_ids))
        personas = (await session.execute(stmt_personas)).scalars().all()

    # Формируем клавиатуру для выбора собеседника
    buttons = []
    for p in personas:
        text_btn = p.full_name
        buttons.append([
            InlineKeyboardButton(
                text=text_btn,
                callback_data=f"stat:set_interlocutor:{p.id}"
            )
        ])

    buttons.append([InlineKeyboardButton(text=_("STATISTICS_ALL_INTERLOCUTORS"), callback_data="stat:set_interlocutor:none")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(_("STATISTICS_CHOOSE_INTERLOCUTOR_PROMPT"), reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("stat:set_interlocutor:"))
async def set_interlocutor_handler(callback: CallbackQuery, state: FSMContext):
    """
    Хендлер для установки выбранного собеседника.
    """
    data = await state.get_data()
    options = data.get("statistics_options", DEFAULT_OPTIONS.copy())

    value = callback.data.split(":")[-1]
    if value == "none":
        options["interlocutor_id"] = None
    else:
        try:
            options["interlocutor_id"] = int(value)
        except ValueError:
            options["interlocutor_id"] = None

    await state.update_data(statistics_options=options)
    await callback.message.edit_text(
        text=_("STATISTICS_TITLE"),
        reply_markup=statistics_main_keyboard(options)
    )
    await callback.answer()


# -------------------------------------------------------------------
# Функция вывода статистики (текст или график)
# -------------------------------------------------------------------

async def show_statistics(callback: CallbackQuery, options: dict):
    """
    В зависимости от output_format формирует текстовый вывод или отправляет график.
    """
    # Готовим данные
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)
        if not user:
            await callback.answer(_("STATISTICS_NO_DATA"), show_alert=True)
            return

        stmt = select(SavedMessage).where(SavedMessage.connected_user_id == user.id)
        messages = (await session.execute(stmt)).scalars().all()

    # Фильтруем сообщения по опциям (период, тип, собеседник)
    messages_filtered = filter_messages_by_options(messages, options)

    if not messages_filtered:
        await callback.message.answer(_("STATISTICS_NO_DATA"))
        await callback.answer()
        return

    # Считаем статистику
    stats = calculate_statistics(messages_filtered)

    # Если пользователь выбрал текстовый формат
    if options.get("output_format") == "text":
        text = build_text_statistics(stats, options)
        await callback.message.answer(text)
        await callback.answer()
        return

    # Если формат - графический
    graph_type = options.get("graph_type")
    if not graph_type:
        # Если пользователь не выбрал конкретный график, можно отдать дефолтный
        graph_type = "activity"  # по умолчанию график активности

    # Генерируем картинку
    image_bytes = None
    if graph_type == "activity":
        image_bytes = render_activity_chart(stats, options)
    elif graph_type == "pie":
        image_bytes = render_in_out_pie(stats, options)
    elif graph_type == "top_interlocutors":
        # Для этого графика (Топ собеседников) нужны дополнительные данные:
        # например, можно запрашивать top-5 собеседников отфильтрованных, если нужно.
        image_bytes = render_top_interlocutors_bar(stats, options)
    elif graph_type == "heatmap":
        image_bytes = render_heatmap(stats, options)

    if image_bytes:
        await callback.message.answer_photo(
            photo=BufferedInputFile(image_bytes.getvalue(), filename='chart.png'),
            caption=_("STATISTICS_GRAPH_GENERATED")
        )
    else:
        await callback.message.answer(_("STATISTICS_UNKNOWN_GRAPH_TYPE"))

    await callback.answer()


def build_text_statistics(stats: dict, options: dict) -> str:
    """
    Формируем человекочитаемый текст со всеми нужными показателями:
      1) Общее кол-во сообщений
      2) Соотношение входящих / исходящих
      3) Средняя длина сообщений
      4) Топ-5 самых активных собеседников
      5) Время самой высокой/низкой активности
      6) Среднее время ответа
      и т.д.
    """
    total = stats.get("total_messages", 0)
    incoming = stats.get("incoming_count", 0)
    outgoing = stats.get("outgoing_count", 0)
    avg_length = stats.get("average_length", 0)
    top_5 = stats.get("top_interlocutors", [])
    busiest_hour = stats.get("busiest_hour")
    quietest_hour = stats.get("quietest_hour")
    avg_response = stats.get("average_response_time")

    lines = []
    lines.append(_("STATISTICS_TITLE"))
    lines.append("")
    lines.append(_("STATISTICS_TOTAL_MESSAGES").format(count=total))
    lines.append(_("STATISTICS_INCOMING") + f": {incoming}")
    lines.append(_("STATISTICS_OUTGOING") + f": {outgoing}")
    lines.append(_("STATISTICS_AVG_LENGTH").format(length=round(avg_length, 2)))

    # Топ собеседников
    lines.append("")
    lines.append(_("STATISTICS_TOP_INTERLOCUTORS"))
    if top_5:
        for i, (p_name, count) in enumerate(top_5, start=1):
            lines.append(f"{i}. {p_name}: {count}")
    else:
        lines.append(_("STATISTICS_NO_DATA"))

    # Часы наибольшей / наименьшей активности
    lines.append("")
    if busiest_hour is not None:
        lines.append(_("STATISTICS_HIGHEST_ACTIVITY").format(hour=busiest_hour))
    if quietest_hour is not None:
        lines.append(_("STATISTICS_LOWEST_ACTIVITY").format(hour=quietest_hour))

    # Среднее время ответа
    if avg_response is not None:
        # Преобразуем секундный формат в что-то удобочитаемое
        # Для примера возьмем формат "X мин. Y сек."
        minutes = int(avg_response // 60)
        seconds = int(avg_response % 60)
        lines.append(_("STATISTICS_AVG_RESPONSE_TIME").format(minutes=minutes, seconds=seconds))

    return "\n".join(lines)