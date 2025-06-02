# statistics_utils.py

from datetime import datetime, timedelta
from typing import List, Tuple, Optional

import io
import matplotlib
matplotlib.use('Agg')  # Чтобы не требовался X-server
import matplotlib.pyplot as plt
import numpy as np

from database.models import SavedMessage


def filter_messages_by_options(messages: List[SavedMessage], options: dict) -> List[SavedMessage]:
    """
    Фильтрует список сообщений в соответствии с опциями:
      - Период (period)
      - Тип (type_filter) = all / incoming / outgoing
      - Собеседник (interlocutor_id)
    """
    start_date, end_date = get_period_dates(options)

    type_filter = options.get("type_filter", "all")
    interlocutor_id = options.get("interlocutor_id")

    result = []
    for m in messages:
        # Проверяем период
        if start_date and m.created_at < start_date:
            continue
        if end_date and m.created_at > end_date:
            continue

        # Фильтр по типу
        if type_filter == "incoming" and m.outgoing:
            continue
        if type_filter == "outgoing" and not m.outgoing:
            continue

        # Фильтр по собеседнику
        # Предположим, что m.chat_id - это id собеседника.
        if interlocutor_id and m.chat_id != interlocutor_id:
            continue

        result.append(m)
    return result


def get_period_dates(options: dict) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Возвращает кортеж (start_date, end_date) в зависимости от period:
      - day, week, month, all, custom
    """
    now = datetime.utcnow()
    period = options.get("period", "week")

    if period == "day":
        return now - timedelta(days=1), now
    elif period == "week":
        return now - timedelta(days=7), now
    elif period == "month":
        return now - timedelta(days=30), now
    elif period == "all":
        return None, now
    elif period == "custom":
        start_date = options.get("start_date")
        end_date = options.get("end_date")
        # Если пользователь не ввёл даты, fallback на all
        if not start_date or not end_date:
            return None, now
        return start_date, end_date

    # По умолчанию неделя
    return now - timedelta(days=7), now


def calculate_statistics(messages: List[SavedMessage]) -> dict:
    """
    Рассчитывает необходимые метрики:
      1) total_messages
      2) incoming_count / outgoing_count
      3) average_length
      4) топ-5 собеседников
      5) busiest_hour / quietest_hour
      6) average_response_time
      и т.д.
    """
    stats = {
        "total_messages": 0,
        "incoming_count": 0,
        "outgoing_count": 0,
        "average_length": 0.0,
        "top_interlocutors": [],
        "busiest_hour": None,
        "quietest_hour": None,
        "average_response_time": None,
    }
    if not messages:
        return stats

    total = len(messages)
    incoming = sum(1 for m in messages if not m.outgoing)
    outgoing = sum(1 for m in messages if m.outgoing)

    # Средняя длина (считаем для text != None)
    lengths = [len(m.text) for m in messages if m.text]
    avg_length = sum(lengths) / len(lengths) if lengths else 0

    # Топ-5 собеседников (по количеству сообщений)
    # Предполагается, что m.chat_id - идентификатор собеседника.
    from collections import Counter
    counter = Counter([m.chat_id for m in messages if m.chat_id])
    top_5_ids = counter.most_common(5)
    # По-хорошему, надо получить имена этих собеседников из таблицы Persona
    # Но здесь просто вернём (chat_id, count).
    top_5_interlocutors = []
    for uid, cnt in top_5_ids:
        top_5_interlocutors.append((f"User {uid}", cnt))

    # Наибольшая / наименьшая активность по часам
    hour_counter = Counter([m.created_at.hour for m in messages])
    # Если нужно, можно считать отдельно для incoming / outgoing
    if hour_counter:
        busiest_hour, _ = max(hour_counter.items(), key=lambda x: x[1])
        quietest_hour, _ = min(hour_counter.items(), key=lambda x: x[1])
    else:
        busiest_hour = None
        quietest_hour = None

    # Среднее время ответа (упрощённо):
    # Идём по сообщениям в хронологическом порядке,
    # когда видим incoming, смотрим время до ближайшего outgoing.
    messages_sorted = sorted(messages, key=lambda x: x.created_at)
    response_times = []
    last_incoming_time = None
    for m in messages_sorted:
        if not m.outgoing:
            # incoming
            last_incoming_time = m.created_at
        else:
            # outgoing
            if last_incoming_time:
                diff = (m.created_at - last_incoming_time).total_seconds()
                if diff >= 0:
                    response_times.append(diff)
                last_incoming_time = None

    avg_response_time = sum(response_times) / len(response_times) if response_times else None

    # Заполняем статистику
    stats["total_messages"] = total
    stats["incoming_count"] = incoming
    stats["outgoing_count"] = outgoing
    stats["average_length"] = avg_length
    stats["top_interlocutors"] = top_5_interlocutors
    stats["busiest_hour"] = busiest_hour
    stats["quietest_hour"] = quietest_hour
    stats["average_response_time"] = avg_response_time

    return stats



def render_activity_chart(stats: dict, options: dict) -> io.BytesIO:
    """
    Построение графика динамики сообщений (например, по часам или по дням).
    В данном примере возьмём часы из stats["busiest_hour"], но обычно нужен
    массив количества сообщений по каждому дню или часу.
    """
    # Для примера возьмём число сообщений по часам:
    # здесь у нас нет массива в stats по каждому часу, надо собирать вручную.
    # Можно слегка переделать calculate_statistics, чтобы возвращать распределение по часам.

    # Если хотим сделать именно "динамику по дням/неделям", нужно
    # в calculate_statistics посчитать day_counts или подобное.

    # Здесь упрощённо покажем пример: возьмём busiest_hour, quietest_hour
    # и выдумаем распределение для демонстрации.

    # ---- Начало примера ----
    hours = range(24)
    # Для наглядности предположим равномерно, кроме "busiest_hour"
    hour_dist = [10] * 24
    b_hour = stats.get("busiest_hour")
    q_hour = stats.get("quietest_hour")
    if b_hour is not None:
        hour_dist[b_hour] = 30
    if q_hour is not None and q_hour != b_hour:
        hour_dist[q_hour] = 5
    # ---- Конец примера ----

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(hours, hour_dist, color="dodgerblue")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Messages count")
    ax.set_title("Activity by hour")

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def render_in_out_pie(stats: dict, options: dict) -> io.BytesIO:
    """
    Круговая диаграмма входящих/исходящих.
    """
    incoming = stats.get("incoming_count", 0)
    outgoing = stats.get("outgoing_count", 0)

    labels = ["Incoming", "Outgoing"]
    sizes = [incoming, outgoing]
    colors = ["lightskyblue", "lightcoral"]

    fig, ax = plt.subplots()
    ax.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        startangle=140,
        colors=colors
    )
    ax.set_title("Incoming vs Outgoing")

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def render_top_interlocutors_bar(stats: dict, options: dict) -> io.BytesIO:
    """
    Барчарт топ-5 собеседников
    """
    top_5 = stats.get("top_interlocutors", [])
    if not top_5:
        return None

    names = [x[0] for x in top_5]
    counts = [x[1] for x in top_5]

    fig, ax = plt.subplots()
    ax.barh(names, counts, color="green")
    ax.set_xlabel("Messages")
    ax.set_ylabel("Interlocutors")
    ax.set_title("Top-5 Interlocutors")

    # Для более красивого отображения
    plt.gca().invert_yaxis()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def render_heatmap(stats: dict, options: dict) -> io.BytesIO:
    """
    Тепловая карта по часам и дням недели (0..6 x 0..23).
    Для этого нам тоже нужно хранить распределение сообщений в stats.
    Здесь покажем пример, как можно отрисовать.
    """
    # Предположим, что мы в calculate_statistics подсчитали количество сообщений
    # для каждой пары (weekday, hour). Например, stats["heatmap"] = [[...], ..., [...]]
    # Здесь же для демонстрации сделаем рандом.
    import random
    data = np.zeros((7, 24))
    for wd in range(7):
        for h in range(24):
            data[wd, h] = random.randint(0, 20)

    fig, ax = plt.subplots(figsize=(10, 3))
    cax = ax.imshow(data, aspect="auto", cmap="Blues")
    ax.set_title("Heatmap (Day of week x Hour)")
    ax.set_xlabel("Hour")
    ax.set_ylabel("Day of week")

    # Подписи по осям
    ax.set_xticks(range(24))
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])

    fig.colorbar(cax)

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf