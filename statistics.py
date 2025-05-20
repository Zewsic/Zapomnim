from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.i18n import gettext as _
from sqlalchemy import select

from database import create_session
from database.models import SavedMessage
from utils import get_user

router = Router()


DEFAULT_OPTIONS = {
    "period": "week",  # day, week, month, all
    "split": False,
    "format": "text",  # text or graph
}


def _mark(text: str, active: bool) -> str:
    return ("✅ " if active else "") + text


def statistics_keyboard(options: dict) -> InlineKeyboardMarkup:
    period = options.get("period", "week")
    split = options.get("split", False)
    fmt = options.get("format", "text")

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_PERIOD_DAY"), period == "day"),
                callback_data="stat:period:day",
            ),
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_PERIOD_WEEK"), period == "week"),
                callback_data="stat:period:week",
            ),
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_PERIOD_MONTH"), period == "month"),
                callback_data="stat:period:month",
            ),
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_PERIOD_ALL"), period == "all"),
                callback_data="stat:period:all",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_mark(_("STATISTICS_INCOMING") + "/" + _("STATISTICS_OUTGOING"), split),
                callback_data="stat:toggle:split",
            ),
            InlineKeyboardButton(
                text=_("STATISTICS_FORMAT_TEXT") if fmt == "text" else _("STATISTICS_FORMAT_GRAPH"),
                callback_data="stat:toggle:format",
            ),
        ],
        [InlineKeyboardButton(text=_("STATISTICS_SHOW_BUTTON"), callback_data="stat:show")],
        [InlineKeyboardButton(text=_("BACK_BUTTON"), callback_data="menu")],
    ])


def _period_dates(period: str) -> tuple[datetime | None, datetime]:
    now = datetime.utcnow()
    if period == "day":
        return now - timedelta(days=1), now
    if period == "week":
        return now - timedelta(days=7), now
    if period == "month":
        return now - timedelta(days=30), now
    return None, now


@router.callback_query(F.data == "statistics")
async def statistics_menu(callback: CallbackQuery, state: FSMContext):
    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)
        if user.privacy_mode:
            await callback.answer(_("STATISTICS_PRIVATE_ERROR"), show_alert=True)
            return
    data = await state.get_data()
    options = data.get("statistics_options", DEFAULT_OPTIONS.copy())
    await state.update_data(statistics_options=options)
    await callback.message.edit_text(
        _("STATISTICS_TITLE"), reply_markup=statistics_keyboard(options)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("stat:"))
async def statistics_callbacks(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    action = parts[1] if len(parts) > 1 else None
    value = parts[2] if len(parts) > 2 else None

    data = await state.get_data()
    options = data.get("statistics_options", DEFAULT_OPTIONS.copy())

    if action == "period" and value:
        options["period"] = value
    elif action == "toggle" and value:
        if value == "split":
            options["split"] = not options.get("split", False)
        elif value == "format":
            options["format"] = "graph" if options.get("format") == "text" else "text"
    elif action == "show":
        await _show_statistics(callback, options)
        return

    await state.update_data(statistics_options=options)
    await callback.message.edit_text(
        _("STATISTICS_TITLE"), reply_markup=statistics_keyboard(options)
    )
    await callback.answer()


async def _show_statistics(callback: CallbackQuery, options: dict):
    period = options.get("period", "week")
    split = options.get("split", False)
    start, now = _period_dates(period)

    async with create_session() as session:
        user = await get_user(session, id=callback.from_user.id)
        stmt = select(
            SavedMessage.created_at,
            SavedMessage.outgoing,
            SavedMessage.content_type,
        ).where(SavedMessage.connected_user_id == user.id)
        if start:
            stmt = stmt.where(SavedMessage.created_at >= start)
        res = await session.execute(stmt)
        messages = res.all()

    total = len(messages)
    incoming = len([m for m in messages if not m.outgoing])
    outgoing = len([m for m in messages if m.outgoing])

    day_counts: dict[datetime.date, int] = {}
    hours = [0] * 24
    weekdays = [0] * 7
    media_counts = {"photo": 0, "video": 0, "document": 0, "audio": 0, "voice": 0}

    for m in messages:
        dt = m.created_at
        day_counts[dt.date()] = day_counts.get(dt.date(), 0) + 1
        hours[dt.hour] += 1
        weekdays[dt.weekday()] += 1
        ct = m.content_type
        if ct in media_counts:
            media_counts[ct] += 1

    if day_counts:
        active_day_date, active_day_count = max(day_counts.items(), key=lambda x: x[1])
    else:
        active_day_date, active_day_count = None, 0

    lines = [_("STATISTICS_TITLE"), ""]
    lines.append(_("STATISTICS_TOTAL_MESSAGES").format(count=total))
    if split:
        lines.append(_("STATISTICS_INCOMING") + f": {incoming}")
        lines.append(_("STATISTICS_OUTGOING") + f": {outgoing}")
    if active_day_date:
        lines.append(
            _("STATISTICS_MOST_ACTIVE_DAY").format(
                date=active_day_date.strftime("%d.%m.%Y"), count=active_day_count
            )
        )
    lines.append("")
    lines.append(_("STATISTICS_MEDIA_HEADER"))
    lines.append(_("STATISTICS_MEDIA_PHOTO") + f": {media_counts['photo']}")
    lines.append(_("STATISTICS_MEDIA_VIDEO") + f": {media_counts['video']}")
    lines.append(_("STATISTICS_MEDIA_DOCUMENT") + f": {media_counts['document']}")
    lines.append(_("STATISTICS_MEDIA_AUDIO") + f": {media_counts['audio']}")
    lines.append(_("STATISTICS_MEDIA_VOICE") + f": {media_counts['voice']}")

    text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=statistics_keyboard(options))
    await callback.answer()
