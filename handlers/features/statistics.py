import traceback
from collections import Counter
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO
from typing import Tuple, Optional, List

from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BufferedInputFile, KeyboardButton, KeyboardButtonRequestUser, \
    ReplyKeyboardMarkup, Message, ChatShared, InlineKeyboardMarkup
from aiogram.utils.markdown import hlink, hbold, hitalic
from aiogram.utils.i18n import gettext as _
from matplotlib import pyplot as plt
from sqlalchemy.ext.asyncio import AsyncSession

from config import StatisticsState
from database import create_session
from database.models import SavedMessage, Persona, Metric
from keyboards.statistics import get_main_stats_keyboard, select_user_keyboard
from utils import get_user
from utils.files import upload_file
from utils.messages import load_encrypted_user_messages
from utils.userdata import get_persona

router = Router()

PERIOD_DAY = "day"
PERIOD_WEEK = "week"
PERIOD_MONTH = "month"
PERIOD_YEAR = "year"


def _get_period_range(period: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    now = datetime.now()
    if period == PERIOD_DAY:  # последние 24 часа
        start = now - timedelta(days=1)
        return start, now
    elif period == PERIOD_WEEK:  # последние 7 дней
        start = now - timedelta(days=7)
        return start, now
    elif period == PERIOD_MONTH:  # последние 30 дней
        start = now - timedelta(days=30)
        return start, now
    elif period == PERIOD_YEAR:  # последние 365 дней
        start = now - timedelta(days=365)
        return start, now
    else:
        return None, now


def calculate_basic_stats(messages: List[SavedMessage]) -> dict:
    total = len(messages)
    incoming = sum(1 for m in messages if not m.outgoing)
    outgoing = total - incoming

    photos = sum(1 for m in messages if m.content_type == 'photo')
    videos = sum(1 for m in messages if m.content_type == 'video')
    voices = sum(1 for m in messages if m.content_type == 'voice')
    video_notes = sum(1 for m in messages if m.content_type == 'video_note')
    stickers = sum(1 for m in messages if m.content_type == 'sticker')

    return {
        "total": total,
        "incoming": incoming,
        "outgoing": outgoing,
        "photos": photos,
        "videos": videos,
        "voices": voices,
        "video_notes": video_notes,
        "stickers": stickers
    }


def build_stats_text(stats: dict) -> str:
    return _("STATISTICS_RESPONSE_TEMPLATE").format(**stats)


def build_time_distribution_line_chart(
        messages: List["SavedMessage"],
        period: str
) -> BytesIO:
    """
    Рисует линейный график распределения сообщений во времени.

    • PERIOD_DAY   – точки каждые 10 минут, подписи по часам «09:00»
    • PERIOD_WEEK  – точки каждые 6 часов, подписи по дням «понедельник»
    • PERIOD_MONTH – точки каждый день, подписи каждые 3 дня «01.02.2025»
    • PERIOD_YEAR  – точки каждую неделю, подписи по месяцам «февраль»
    """
    # -----------------------------------------------------------
    # 1. Подготовка входных данных
    # -----------------------------------------------------------
    messages_sorted = sorted(messages, key=lambda m: m.created_at)
    if len(messages_sorted) == 0:
        first_dt = datetime.now()
    else:
        first_dt = messages_sorted[0].created_at
    day_start = datetime.combine(first_dt.date(), datetime.min.time())

    # -----------------------------------------------------------
    # 2. Вспомогательные функции для бинов и подписей
    # -----------------------------------------------------------
    def _make_bins(total_bins: int,
                   bin_timedelta: timedelta,
                   label_fmt: str,
                   tick_step: int,
                   tick_label_func):
        """Общая заготовка: группируем, возвращаем x-оси, counts и подписи."""
        counter = Counter()
        for m in messages_sorted:
            delta = m.created_at - day_start
            idx = int(delta.total_seconds() // bin_timedelta.total_seconds())
            # В пределах диапазона?
            if 0 <= idx < total_bins:
                counter[idx] += 1

        counts = [counter[i] for i in range(total_bins)]
        x_all = [day_start + i * bin_timedelta for i in range(total_bins)]

        # Текстовые подписи всех точек (нужны для matplotlib, но мы спрячем)
        x_labels_full = [dt.strftime(label_fmt) for dt in x_all]

        # Позиции и текст «основных» тиков
        tick_pos = list(range(0, total_bins, tick_step))
        tick_labels = tick_label_func(x_all, tick_pos)

        return counts, x_labels_full, tick_pos, tick_labels

    # -----------------------------------------------------------
    # 3. Период: сутки
    # -----------------------------------------------------------
    if period == PERIOD_DAY:
        total_bins = 24 * 2  # 48 точки по 30 мин
        bin_td = timedelta(minutes=30)

        counts, x_labels_full, tick_pos, tick_labels = _make_bins(
            total_bins,
            bin_td,
            "%H:%M",
            tick_step=2,  # 6*10 мин = 1 ч
            tick_label_func=lambda x_all, pos: [
                x_all[p].strftime("%H:00") for p in pos
            ]
        )

    # -----------------------------------------------------------
    # 4. Период: неделя
    # -----------------------------------------------------------
    elif period == PERIOD_WEEK:
        weekday_offset = day_start.weekday()  # 0=Mon
        monday_start = day_start - timedelta(days=weekday_offset)
        day_start = monday_start

        total_bins = 7 * 4  # 28 точек по 6 часов
        bin_td = timedelta(hours=6)

        counts, x_labels_full, tick_pos, tick_labels = _make_bins(
            total_bins,
            bin_td,
            "%a %H:%M",  # Mon 00:00
            tick_step=4,  # 4*6 ч = 1 день
            tick_label_func=lambda x_all, pos: [
                _(x_all[p].strftime("%A").upper())
                for p in pos
            ]
        )

    # -----------------------------------------------------------
    # 5. Период: месяц
    # -----------------------------------------------------------
    elif period == PERIOD_MONTH:
        month_start = first_dt.replace(day=1,
                                       hour=0, minute=0, second=0, microsecond=0)
        day_start = month_start
        # Кол-во дней в месяце
        if month_start.month == 12:
            next_month_start = month_start.replace(year=month_start.year + 1,
                                                   month=1)
        else:
            next_month_start = month_start.replace(month=month_start.month + 1)
        num_days = (next_month_start - month_start).days

        total_bins = num_days  # по дню
        bin_td = timedelta(days=1)

        counts, x_labels_full, tick_pos, tick_labels = _make_bins(
            total_bins,
            bin_td,
            "%d.%m.%Y",
            tick_step=3,
            tick_label_func=lambda x_all, pos: [
                x_all[p].strftime("%d.%m.%Y") for p in pos
            ]
        )

    # -----------------------------------------------------------
    # 6. Период: год
    # -----------------------------------------------------------
    elif period == PERIOD_YEAR:
        year_start = first_dt.replace(month=1, day=1,
                                      hour=0, minute=0, second=0, microsecond=0)
        day_start = year_start

        # 52 (иногда 53) недели – сделаем 53 на всякий случай
        total_bins = 53
        bin_td = timedelta(weeks=1)

        MONTH_KEYS = [
            "JANUARY", "FEBRUARY", "MARCH", "APRIL",
            "MAY", "JUNE", "JULY", "AUGUST",
            "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
        ]

        counts, x_labels_full, tick_pos, tick_labels = _make_bins(
            total_bins,
            bin_td,
            "%W",  # номер недели
            tick_step=4,  # ~4 недели ~ месяц
            tick_label_func=lambda x_all, pos: [
                MONTH_KEYS[(x_all[p].month - 1) % 12] for p in pos
            ]
        )

    # -----------------------------------------------------------
    # 7. Неизвестный период – дефолт: точка на каждый день
    # -----------------------------------------------------------
    else:
        total_bins = (messages_sorted[-1].created_at.date()
                      - day_start.date()).days + 1
        bin_td = timedelta(days=1)
        counts, x_labels_full, tick_pos, tick_labels = _make_bins(
            total_bins,
            bin_td,
            "%d.%m.%Y",
            tick_step=max(total_bins // 10, 1),
            tick_label_func=lambda x_all, pos: [
                x_all[p].strftime("%d.%m") for p in pos
            ]
        )

    # -----------------------------------------------------------
    # 8. Рисуем график
    # -----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(range(len(counts)), counts, marker='o')

    ax.set_ylabel(_('STATISTICS_RESPONSE_GRAPH_Y_LABEL'))
    ax.set_title(_("STATISTICS_RESPONSE_GRAPH_TITLE") + _("STATISTICS_PERIOD_BUTTON_" + period.upper()))

    # Тики и подписи согласно расчёту
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_labels, rotation=45, ha="right")

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


async def make_message(bot: Bot, messages: List[SavedMessage], period: str, persona: Optional[Persona],
                       chat_id: int, *, message_id: int = None) -> int:
    stats = calculate_basic_stats(messages)
    text_stats = build_stats_text(stats)

    keyboard = get_main_stats_keyboard(persona, period)

    header = hbold('📊' + (f' {_("STATISTICS_RESPONSE_TITLE")}'
                    if not persona else
                    f" {_('STATISTICS_RESPONSE_SELECTED_USER_TITLE')} {persona.full_name}") + '\n\n')

    if message_id:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=header + text_stats + hitalic(f'\n{_("STATISTICS_RESPONSE_GRAPH_LOADING")}'),
            reply_markup=keyboard
        )
    else:
        message = await bot.send_message(
            chat_id=chat_id,
            text=header + text_stats + hitalic(f'\n{_("STATISTICS_RESPONSE_GRAPH_LOADING")}'),
            reply_markup=keyboard
        )
        message_id = message.message_id

    graph = build_time_distribution_line_chart(messages, period)
    photo_url = await upload_file(graph.getvalue(), 'graph.png')

    header = hlink('📊', photo_url) + hbold((f' {_("STATISTICS_RESPONSE_TITLE")}'
                                      if not persona else
                                      f" {_('STATISTICS_RESPONSE_SELECTED_USER_TITLE')} {persona.full_name}") + '\n\n')

    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=header + text_stats,
        reply_markup=keyboard
    )
    return message_id


@router.callback_query(F.data == "statistics")
async def on_statistics_open(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)
        if not user:
            await callback.answer("Хуйня какая-то", show_alert=True)
            return

        if user.privacy_mode:
            await callback.answer(_("UNAVAILABLE_IN_PRIVACY_MODE"), show_alert=True)
            return

        metric = Metric(
            connected_user_id=user.id if not user.privacy_mode else None,
            name='metrics.statistic',
        )
        session.add(metric)
        await session.commit()

        messages = await load_encrypted_user_messages(session=session, connected_user_id=user.id,
                                                      cutoff=_get_period_range(PERIOD_DAY)[0])

    await state.update_data(
        selected_period=PERIOD_DAY,
        interlocutor_id=None
    )
    session.add(metric)
    await session.commit()

    await make_message(callback.bot, messages, PERIOD_DAY, None, callback.message.chat.id,
                       message_id=None)
    await state.set_state(StatisticsState.main)


@router.callback_query(F.data.startswith("stat:"))
async def on_statistics_callback(callback: CallbackQuery, state: FSMContext):
    """
    Универсальная обработка нажатий на инлайн-кнопки в меню статистики.
    """
    parts = callback.data.split(":")
    # Пример: "stat:period:week" -> parts = ["stat", "period", "week"]
    action = parts[1] if len(parts) > 1 else None
    value = parts[2] if len(parts) > 2 else None

    data = await state.get_data()
    selected_period = data.get('selected_period', PERIOD_DAY)
    interlocutor_id: int = data.get('interlocutor_id', None)

    if action == "period":
        if value not in (PERIOD_DAY, PERIOD_WEEK, PERIOD_MONTH, PERIOD_YEAR):
            return
        selected_period = value

    elif action == "choose_user":
        if interlocutor_id:
            interlocutor_id = None
        else:
            dialog_msg = await callback.message.answer(
                _("STATISTICS_SELECT_CHAT_MESSAGE"),
                reply_markup=select_user_keyboard()
            )

            data["dialog_message_id"] = dialog_msg.message_id
            data["statistics_message_id"] = callback.message.message_id
            await state.update_data(data)
            await state.set_state(StatisticsState.wait_for_dialog)
            return

    await state.update_data({'selected_period': selected_period, "interlocutor_id": interlocutor_id})

    async with create_session() as session:
        messages = await load_encrypted_user_messages(session=session, connected_user_id=callback.from_user.id,
                                                      cutoff=_get_period_range(selected_period)[0],
                                                      chat_id=interlocutor_id)
        persona = await get_persona(session, interlocutor_id) if interlocutor_id else None

    try:
        await make_message(callback.bot, messages, selected_period, persona, callback.message.chat.id,
                           message_id=callback.message.message_id)
    except Exception as e:
        if 'message is not modified' not in str(e):
            print(traceback.format_exc())

    await callback.answer()


@router.message(StateFilter(StatisticsState.wait_for_dialog))
async def on_chat_shared(message: Message, state: FSMContext):
    data = await state.get_data()
    current_state = await state.get_state()

    dialog_message_id = data.get('dialog_message_id', None)
    statistics_message_id: int = data.get('statistics_message_id', None)

    selected_period = data.get('selected_period', PERIOD_DAY)
    interlocutor_id: int = data.get('interlocutor_id', None)

    async with create_session() as session:
        if not message.user_shared:
            await message.delete()
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=dialog_message_id)
            except:
                ...
            await state.update_data({"dialog_message_id": None})
            return

        persona = await get_persona(session, message.user_shared.user_id)
        if persona is None:
            await message.delete()

            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=dialog_message_id,
            )

            dialog_msg = await message.answer(
                _("STATISTICS_SELECT_CHAT_ERROR"),
                reply_markup=select_user_keyboard()
            )

            data["dialog_message_id"] = dialog_msg.message_id
            await state.update_data(data)

            return

        interlocutor_id = persona.id

        messages = await load_encrypted_user_messages(session=session, connected_user_id=message.from_user.id,
                                                      cutoff=_get_period_range(selected_period)[0],
                                                      chat_id=interlocutor_id)
        persona = await get_persona(session, interlocutor_id) if interlocutor_id else None

    await state.update_data({"interlocutor_id": interlocutor_id})

    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=dialog_message_id)
    except:
        ...

    try:
        await message.delete()
        await make_message(message.bot, messages, selected_period, persona, message.chat.id,
                           message_id=statistics_message_id)
    except Exception as e:
        if 'message is not modified' not in str(e):
            print(traceback.format_exc())
