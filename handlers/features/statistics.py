import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

import boto3
import matplotlib
from aiogram.methods import EditMessageReplyMarkup
from sqlalchemy import select

matplotlib.use('Agg')  # Чтобы не требовался X-server
import matplotlib.pyplot as plt

from io import BytesIO

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestUser,
    ChatShared
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# Пример: импорт ваших моделей и ф-ий работы с БД
from database import create_session
from database.models import SavedMessage
from utils import get_user


class Save:
    messages: List[SavedMessage] = []


router = Router()

# -------------------------------------------------------------------
# Константы / настройки
# -------------------------------------------------------------------
# Примерная структура ваших "period"-констант (мы используем их в клавиатуре):
PERIOD_DAY = "day"
PERIOD_WEEK = "week"
PERIOD_MONTH = "month"
PERIOD_YEAR = "year"

# Значения по умолчанию
DEFAULT_OPTIONS = {
    "period": PERIOD_DAY,  # day / week / month / year
    "interlocutor_id": None,  # None = все чаты
}


# Состояния для управления выбором диалога
class StatisticsStates(StatesGroup):
    MAIN = State()  # главное меню статистики
    WAITING_FOR_DIALOG = State()  # когда нажали "Выбрать человека" и ждём ChatShared


# -------------------------------------------------------------------
# Утилита: загрузка картинки в S3 и получение пресайнд-ссылки
# -------------------------------------------------------------------
def upload_chart_to_s3_and_get_url(image_bytes: bytes) -> str:
    """
    Пример функции, которая загружает байты картинки в S3,
    а затем получает presigned URL с истечением ~15 минут (900 секунд).

    ВНИМАНИЕ: здесь вам нужно прописать реальные данные:
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY
    - регион
    - имя бакета
    и т.д.

    Либо используйте profile_name (если работаете из локального окружения).
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id="ВАШ_AWS_KEY",
        aws_secret_access_key="ВАШ_AWS_SECRET",
        region_name="us-east-1"  # пример
    )
    bucket_name = "your-bucket"

    # Генерируем уникальный ключ файла
    chart_key = f"charts/{uuid.uuid4()}.png"

    # Заливаем в S3
    s3.put_object(
        Bucket=bucket_name,
        Key=chart_key,
        Body=image_bytes,
        ContentType="image/png",
        ACL='public-read',  # Или другой, в зависимости от политики

    )

    # Генерируем presigned URL, действительный 900 секунд (15 мин).
    presigned_url = s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': bucket_name,
            'Key': chart_key
        },
        ExpiresIn=900
    )
    return presigned_url


# -------------------------------------------------------------------
# Вспомогательная логика для статистики
# -------------------------------------------------------------------

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


def filter_messages(
        messages: List[SavedMessage],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        interlocutor_id: Optional[int] = None
) -> List[SavedMessage]:
    """
    Фильтруем сообщения по дате и по interlocutor_id (если задан).
    """
    result = []
    for m in messages:
        if start_date and m.created_at < start_date:
            continue
        if end_date and m.created_at > end_date:
            continue
        if interlocutor_id and m.chat_id != interlocutor_id:
            continue
        result.append(m)
    return result


def calculate_basic_stats(messages: List[SavedMessage]) -> dict:
    """
    Подсчитываем:
    - Всего сообщений
    - Входящие/Исходящие
    - Медиа контент (фото, видео, голосовые, видеосообщения, стикеры)
    """
    total = len(messages)
    incoming = sum(1 for m in messages if not m.outgoing)
    outgoing = total - incoming

    # Допустим, в SavedMessage.media_type хранится тип: 'photo', 'video', 'voice',
    # 'video_note', 'sticker' и т.д. Если у вас другая логика — адаптируйте.
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
    """
    Текстовое представление базовой статистики.
    Вы можете оформить под свой вкус.
    """
    lines = []
    lines.append(f"Всего сообщений: {stats['total']}")
    lines.append(f"Входящие: {stats['incoming']}")
    lines.append(f"Исходящие: {stats['outgoing']}")
    lines.append("")
    lines.append("Медиа:")
    lines.append(f"  Фото: {stats['photos']}")
    lines.append(f"  Видео: {stats['videos']}")
    lines.append(f"  Голосовые: {stats['voices']}")
    lines.append(f"  Видеосообщения: {stats['video_notes']}")
    lines.append(f"  Стикеры: {stats['stickers']}")
    return "\n".join(lines)


def build_time_distribution_line_chart(
        messages: List[SavedMessage],
        period: str
) -> BytesIO:
    """
    Строим линейный график распределения сообщений (вход+исход)
    по выбранным единицам времени (часы/дни/месяцы и т.д.).

    Принцип:
      - Если period = 24 часа (day), группируем по часам.
      - Если week / month, группируем по дням (либо для week - по дням, для month - тоже по дням).
      - Если year, группируем по месяцам.
    Для наглядности можно сделать самую простую схему:
      day -> group by hour (0..23)
      week -> group by day (кол-во за каждый из 7 дней)
      month -> group by day (до 30)
      year -> group by month (до 12)

    Подчёркиваю: вы можете расширить логику под минутный шаг и т.д.
    """
    # Сортируем по created_at для удобства
    messages_sorted = sorted(messages, key=lambda m: m.created_at)

    now = datetime.now()
    x_labels = []
    counts = []

    # Подготовим словарь для группировки:
    grouping_counter = Counter()

    if period == PERIOD_DAY:
        # Группируем по часам
        # Собираем все сообщения, группируем: key = hour_of_day
        for m in messages_sorted:
            hour = m.created_at.hour
            grouping_counter[hour] += 1
        # Формируем X от 0 до 23
        x_labels = list(range(24))
        counts = [grouping_counter[h] for h in x_labels]

    elif period in (PERIOD_WEEK, PERIOD_MONTH):
        # Для упрощения: группируем по дате (YYYY-MM-DD)
        # Потом возьмём диапазон дат от min до max
        date_counter = Counter()
        for m in messages_sorted:
            d_str = m.created_at.strftime("%Y-%m-%d")
            date_counter[d_str] += 1

        # Соберём уникальные даты, отсортируем
        unique_dates = sorted(date_counter.keys())
        x_labels = unique_dates
        counts = [date_counter[d] for d in x_labels]

    elif period == PERIOD_YEAR:
        # Группируем по месяцу (YYYY-MM)
        month_counter = Counter()
        for m in messages_sorted:
            ym = m.created_at.strftime("%Y-%m")
            month_counter[ym] += 1
        unique_months = sorted(month_counter.keys())
        x_labels = unique_months
        counts = [month_counter[m] for m in x_labels]
    else:
        # fallback — например, как для week
        date_counter = Counter()
        for m in messages_sorted:
            d_str = m.created_at.strftime("%Y-%m-%d")
            date_counter[d_str] += 1
        unique_dates = sorted(date_counter.keys())
        x_labels = unique_dates
        counts = [date_counter[d] for d in x_labels]

    # Рисуем график
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x_labels, counts, marker='o', color='blue')

    ax.set_xlabel("Временная метка")
    ax.set_ylabel("Кол-во сообщений")
    ax.set_title("Распределение сообщений во времени")

    # Повернём подписи на оси X, если слишком много
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf


# -------------------------------------------------------------------
# Клавиатуры
# -------------------------------------------------------------------
def get_main_stats_keyboard(interlocutor_id: Optional[int]) -> InlineKeyboardMarkup:
    """
    Основная клавиатура под сообщением со статистикой.
    4 периода + кнопка "Выбрать человека/По всем чатам" + "Показать график" + "Назад".
    """
    # Если собеседник выбран, меняем текст кнопки
    choose_user_text = "По всем чатам" if interlocutor_id else "Выбрать человека"

    kb = [
        [
            InlineKeyboardButton(text="24 часа", callback_data="stat:period:day"),
            InlineKeyboardButton(text="7 дней", callback_data="stat:period:week"),
            InlineKeyboardButton(text="30 дней", callback_data="stat:period:month"),
            InlineKeyboardButton(text="Год", callback_data="stat:period:year"),
        ],
        [
            InlineKeyboardButton(text=choose_user_text, callback_data="stat:choose_user")
        ],
        [
            InlineKeyboardButton(text="Показать график", callback_data="stat:show_chart")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="stat:back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# -------------------------------------------------------------------
# Хендлеры
# -------------------------------------------------------------------

@router.callback_query(F.data == "statistics")
async def on_statistics_open(callback: CallbackQuery, state: FSMContext):
    """
    Когда пользователь нажимает кнопку "Статистика" в вашем главном меню.
    Сразу отображаем:
      - кол-во сообщений (вход/исход)
      - статы по медиа
      - инлайн-клавиатура (4 периода, выбрать человека, показать график, назад)
    """
    await callback.answer()  # убираем "часики"

    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)
        if not user:
            await callback.answer("Хуйня какая-то", show_alert=True)
            return

        stmt = select(SavedMessage).where(SavedMessage.connected_user_id == user.id)
        messages = (await session.execute(stmt)).scalars().all()

    # Возьмём период по умолчанию из DEFAULT_OPTIONS
    options = DEFAULT_OPTIONS.copy()

    # Фильтруем (для "здесь и сейчас" — например за 24 часа).
    start, end = _get_period_range(options["period"])
    filtered = filter_messages(messages, start, end, None)

    # Считаем статистику
    stats = calculate_basic_stats(filtered)
    text_stats = build_stats_text(stats)

    # Сохраняем в state
    await state.update_data(
        statistics_options=options,
    )

    Save.messages = messages

    await callback.message.delete()  # удаляем старое меню
    await callback.message.answer(
        text=f"Статистика за 24 часа:\n\n{text_stats}",
        reply_markup=get_main_stats_keyboard(interlocutor_id=None)
    )
    await state.set_state(StatisticsStates.MAIN)


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
    options = data.get("statistics_options", DEFAULT_OPTIONS.copy())
    messages = Save.messages

    if action == "period":
        # Меняем период
        if value in (PERIOD_DAY, PERIOD_WEEK, PERIOD_MONTH, PERIOD_YEAR):
            options["period"] = value

        # Пересчитываем статистику
        start, end = _get_period_range(options["period"])
        filtered = filter_messages(messages, start, end, options["interlocutor_id"])
        stats = calculate_basic_stats(filtered)

        text_stats = build_stats_text(stats)
        await callback.message.edit_text(
            text=f"Статистика за выбранный период:\n\n{text_stats}",
            reply_markup=get_main_stats_keyboard(options["interlocutor_id"])
        )

    elif action == "choose_user":
        # Либо сброс interlocutor_id, либо переходим к выбору
        if options["interlocutor_id"]:
            # Уже выбран — тогда сбрасываем (=> все чаты)
            options["interlocutor_id"] = None
            start, end = _get_period_range(options["period"])
            filtered = filter_messages(messages, start, end, None)
            stats = calculate_basic_stats(filtered)
            text_stats = build_stats_text(stats)

            await callback.message.edit_text(
                text=f"Статистика (по всем чатам):\n\n{text_stats}",
                reply_markup=get_main_stats_keyboard(None)
            )
        else:

            # Отдельное сообщение "Выберите диалог"
            request_chat_btn = KeyboardButton(
                text="Выбрать беседу",
                request_user=KeyboardButtonRequestUser(request_id=123, user_is_bot=False)
            )
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[request_chat_btn]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            dialog_msg = await callback.message.answer(
                "Нажмите кнопку, чтобы выбрать чат:",
                reply_markup=keyboard
            )

            # Сохраним id этого "временного" сообщения и перейдём в состояние WAITING_FOR_DIALOG
            data["dialog_message_id"] = dialog_msg.message_id
            await state.update_data(data)
            await state.set_state(StatisticsStates.WAITING_FOR_DIALOG)

    elif action == "cancel_choose":
        # Нажали "Отмена" вместо выбора чата
        # Просто откатываем клавиатуру обратно и убираем сообщение, если оно есть
        dialog_msg_id = data.get("dialog_message_id")
        if dialog_msg_id:
            try:
                await callback.message.bot.delete_message(
                    chat_id=callback.message.chat.id,
                    message_id=dialog_msg_id
                )
            except:
                pass
            data["dialog_message_id"] = None
            await state.update_data(data)

        # Возвращаем клавиатуру исходного сообщения
        # Надо также вернуть текст статистики (с актуальными параметрами)
        start, end = _get_period_range(options["period"])
        filtered = filter_messages(messages, start, end, options["interlocutor_id"])
        stats = calculate_basic_stats(filtered)
        text_stats = build_stats_text(stats)

        await callback.message.edit_text(
            text=f"Статистика:\n\n{text_stats}",
            reply_markup=get_main_stats_keyboard(options["interlocutor_id"])
        )
        await callback.answer()

    elif action == "show_chart":
        # Пользователь хочет вывести линейный график в виде ссылки
        start, end = _get_period_range(options["period"])
        filtered = filter_messages(messages, start, end, options["interlocutor_id"])

        if not filtered:
            await callback.answer("Нет данных для построения графика.", show_alert=True)
            return

        # Строим линейный график
        chart_bytes = build_time_distribution_line_chart(filtered, options["period"])

        # Загружаем в S3 и получаем presigned URL
        # presigned_url = upload_chart_to_s3_and_get_url(chart_bytes.getvalue())

        # Прячем ссылку за эмодзи (Markdown)
        # chart_link_markdown = f"[🔗]({presigned_url})"

        await callback.message.answer(
            text=f"График (действителен ~15 минут): ",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        await callback.answer()

    elif action == "back":
        # Возврат в предыдущее меню (зависит от вашей логики).
        # Здесь просто уберём сообщение и скажем "назад".
        await callback.message.delete()
        await callback.answer("Возврат назад.")
        # Или вызовите свой главный хендлер меню.

    else:
        await callback.answer("Неизвестная команда.", show_alert=True)

    # Не забудьте обновить state
    await state.update_data(statistics_options=options)


# -------------------------------------------------------------------
# Хендлер, который срабатывает, когда пользователь выбрал чат (ChatShared).
# Функционал появился в Telegram 6.0. Aiogram 3.x поддерживает это событие.
# -------------------------------------------------------------------
# @router.message(F.user_shared)
async def on_chat_shared(message: Message, state: FSMContext):
    """
    Когда пользователь выбирает чат через request_chat_btn,
    приходит объект ChatShared (у него есть chat_id).
    """
    data = await state.get_data()
    current_state = await state.get_state()

    if current_state != StatisticsStates.WAITING_FOR_DIALOG:
        # Игнорируем, если мы не в состоянии ожидания
        return

    # Получаем chat_id
    chat_shared: ChatShared = message.chat_shared
    # ВАЖНО: в aiogram 3.x поле chat_shared может содержать:
    #   chat_shared.chat_id (это именно id выбранного чата,
    #                        если бот админ в целевом чате)
    #   chat_shared.request_id (совпадает с тем, что мы задавали)
    # Будьте внимательны, иногда в зависимости от настроек приватности
    # может вернуться None.
    # Нужно проверить фактическую структуру ChatShared.

    # Часто chat_shared.chat_id — это фактический id канала/группы,
    # но не Persona.id. Нужно сопоставлять с логикой вашей БД.
    # Ниже — упрощённый вариант, где мы считаем, что chat_id
    # совпадает со SavedMessage.chat_id.
    real_chat_id = chat_shared.chat_id  # Настоящий ID чата

    # Сохраняем в options
    options = data.get("statistics_options", DEFAULT_OPTIONS.copy())
    options["interlocutor_id"] = real_chat_id

    data["statistics_options"] = options
    await state.update_data(data)

    # Удаляем "вспомогательное" сообщение (с ReplyKeyboardMarkup)
    dialog_msg_id = data.get("dialog_message_id")
    if dialog_msg_id:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=dialog_msg_id
            )
        except:
            pass
        data["dialog_message_id"] = None
        await state.update_data(data)

    # Возвращаемся к исходному сообщению со статистикой (которое в состоянии MAIN).
    # Чтобы обновить текст/клавиатуру, надо знать message_id того сообщения.
    # Но если мы не сохраняли, то можно просто ответить заново.
    all_messages = data.get("all_messages", [])

    start, end = _get_period_range(options["period"])
    filtered = filter_messages(all_messages, start, end, real_chat_id)
    stats = calculate_basic_stats(filtered)
    text_stats = build_stats_text(stats)

    # Шлём заново (или, если сохранили ID исходного сообщения, редактируем)
    await message.answer(
        text=f"Статистика по выбранному чату:\n\n{text_stats}",
        reply_markup=get_main_stats_keyboard(interlocutor_id=real_chat_id)
    )

    # Убираем состояние
    await state.set_state(StatisticsStates.MAIN)
