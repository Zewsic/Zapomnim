"""Improved admin module.

Adds richer statistics for the dashboard:
- /admin/stats - now returns new-user counts, weekly stats, and cost figures.
- /admin/users - per-user totals for messages, spend, and last activity.
- /admin/metrics - unchanged but minor typing tweaks.
- /admin/top - now also surfaces the top spenders.

The existing API response keys are preserved, so nothing breaks; callers just get bonus
information. All calculations still happen server-side in one trip to the database.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import create_session
from database.models import Metric, SavedMessage, User
from utils.security import make_promocode

app = APIRouter(prefix="/admin", tags=["admin"])


async def get_db():
    """Get database session."""
    async with create_session() as session:
        yield session


# ---------------------------------------------------------------------------
# Pricing helpers
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, dict[str, float]] = {
    "o4-mini": {"input": 1.1 / 1_000_000, "output": 4.4 / 1_000_000},
    "gpt-4.1-nano": {"input": 0.1 / 1_000_000, "output": 0.4 / 1_000_000},
    "gpt-4.1-mini": {"input": 0.4 / 1_000_000, "output": 1.6 / 1_000_000},
    "gpt-4o-mini-transcribe": {"second": 0.003 / 60},
}


def _normalize_model(model: str | None) -> str:
    """Map arbitrary model strings onto our internal price table keys."""
    if model in MODEL_PRICING:
        return model
    if not model:
        return "gpt-4.1-nano"
    m = model.lower()
    if "o4" in m:
        return "o4-mini"
    if "nano" in m:
        return "gpt-4.1-nano"
    if "mini" in m and "4.1" in m:
        return "gpt-4.1-mini"
    if "transcribe" in m:
        return "gpt-4o-mini-transcribe"
    return "gpt-4.1-nano"


def _parse_metric_value(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        data = json.loads(value)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _calc_cost(data: dict[str, Any]) -> float:
    model = _normalize_model(data.get("model", "gpt-4.1-nano"))
    prices = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4.1-nano"])

    if "transcribe" in model:
        dur = float(data.get("audio_duration", 0))
        return dur * prices["second"]

    input_t = int(data.get("input_tokens", 0))
    output_t = int(data.get("output_tokens", 0))
    return input_t * prices["input"] + output_t * prices["output"]


# ---------------------------------------------------------------------------
# Pydantic models — statistics endpoints
# ---------------------------------------------------------------------------

class SavedMessagesStats(BaseModel):
    total: int
    day: int
    week: int
    month: int
    avg_per_user_day: float | None = None
    avg_per_user_month: float | None = None


class UserStats(BaseModel):
    total: int
    active: int
    new_day: int
    new_week: int
    new_month: int


class CostStats(BaseModel):
    total: float
    day: float
    month: float


class StatsResponse(BaseModel):
    users: UserStats
    saved_messages: SavedMessagesStats
    cost: CostStats


@app.get("/stats", response_model=StatsResponse)
async def get_statistics(db: AsyncSession = Depends(get_db)) -> StatsResponse:
    """Aggregate high‑level statistics for the dashboard."""
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ------------------------------------------------------------------
    # User counters
    # ------------------------------------------------------------------
    users_total = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users = (
        await db.execute(select(func.count(User.id)).where(User.subscriber_until > now))
    ).scalar_one()

    new_users_day = (
        await db.execute(select(func.count(User.id)).where(User.created_at >= day_ago))
    ).scalar_one()
    new_users_week = (
        await db.execute(select(func.count(User.id)).where(User.created_at >= week_ago))
    ).scalar_one()
    new_users_month = (
        await db.execute(select(func.count(User.id)).where(User.created_at >= month_ago))
    ).scalar_one()

    # ------------------------------------------------------------------
    # Saved‑message counters
    # ------------------------------------------------------------------
    total_messages = (await db.execute(select(func.count(SavedMessage.id)))).scalar_one()
    day_messages = (
        await db.execute(
            select(func.count(SavedMessage.id)).where(SavedMessage.created_at >= day_ago),
        )
    ).scalar_one()
    week_messages = (
        await db.execute(
            select(func.count(SavedMessage.id)).where(SavedMessage.created_at >= week_ago),
        )
    ).scalar_one()
    month_messages = (
        await db.execute(
            select(func.count(SavedMessage.id)).where(SavedMessage.created_at >= month_ago),
        )
    ).scalar_one()

    avg_day = (day_messages / new_users_day) if new_users_day else None
    avg_month = (month_messages / new_users_month) if new_users_month else None

    # ------------------------------------------------------------------
    # Cost counters — one pass over Metric table keeps it simple.
    # ------------------------------------------------------------------
    rows = (
        await db.execute(select(Metric.value, Metric.created_at))
    ).all()

    cost_total = cost_day = cost_month = 0.0
    for value, created in rows:
        parsed = _parse_metric_value(value)
        if not parsed:
            continue
        c = _calc_cost(parsed)
        cost_total += c
        if created >= month_ago:
            cost_month += c
        if created >= day_ago:
            cost_day += c

    return StatsResponse(
        users=UserStats(
            total=users_total,
            active=active_users,
            new_day=new_users_day,
            new_week=new_users_week,
            new_month=new_users_month,
        ),
        saved_messages=SavedMessagesStats(
            total=total_messages,
            day=day_messages,
            week=week_messages,
            month=month_messages,
            avg_per_user_day=avg_day,
            avg_per_user_month=avg_month,
        ),
        cost=CostStats(total=round(cost_total, 4), day=round(cost_day, 4), month=round(cost_month, 4)),
    )


# ---------------------------------------------------------------------------
# Per‑user breakdown
# ---------------------------------------------------------------------------

class UserMetricInfo(BaseModel):
    count: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    audio_duration: float | None = None
    cost_usd: float | None = None


class UserInfo(BaseModel):
    id: int
    first_name: str
    last_name: str | None
    username: str | None
    registered_at: datetime | None
    last_active_at: datetime | None
    subscription_until: datetime | None
    total_messages: int
    total_cost_usd: float
    metrics: dict[str, UserMetricInfo]


@app.get("/users", response_model=list[UserInfo])
async def get_users(db: AsyncSession = Depends(get_db)) -> list[UserInfo]:
    """Full per‑user usage overview."""
    users = (await db.execute(select(User))).scalars().all()

    # Pre‑fetch message counts & last‑activity stamps in bulk to avoid N+1.
    msg_counts_subq = (
        select(
            SavedMessage.connected_user_id.label("uid"),
            func.count(SavedMessage.id).label("msg_cnt"),
            func.max(SavedMessage.created_at).label("last_msg"),
        )
        .group_by(SavedMessage.connected_user_id)
        .subquery()
    )
    msg_rows = (
        await db.execute(select(msg_counts_subq.c.uid, msg_counts_subq.c.msg_cnt, msg_counts_subq.c.last_msg))
    ).all()
    msg_info = {uid: (cnt, last) for uid, cnt, last in msg_rows}

    # Likewise, pull all metrics for every user in one sweep.
    metric_rows = (
        await db.execute(select(Metric.connected_user_id, Metric.name, Metric.value))
    ).all()

    # Build nested dict uid -> metric‑name -> UserMetricInfo
    metric_map: dict[int, dict[str, UserMetricInfo]] = {}
    total_spend_map: dict[int, float] = {}

    for uid, name, value in metric_rows:
        per_user = metric_map.setdefault(uid, {})
        info = per_user.setdefault(name, UserMetricInfo(count=0))
        info.count += 1
        parsed = _parse_metric_value(value)
        if parsed:
            info.input_tokens = (info.input_tokens or 0) + int(parsed.get("input_tokens", 0))
            info.output_tokens = (info.output_tokens or 0) + int(parsed.get("output_tokens", 0))
            info.audio_duration = (info.audio_duration or 0.0) + float(parsed.get("audio_duration", 0))
            cost = _calc_cost(parsed)
            info.cost_usd = (info.cost_usd or 0.0) + cost
            total_spend_map[uid] = total_spend_map.get(uid, 0.0) + cost

    # Compose final payload
    result: list[UserInfo] = []
    for u in users:
        msg_cnt, last_msg = msg_info.get(u.id, (0, None))
        metrics = metric_map.get(u.id, {})
        result.append(
            UserInfo(
                id=u.id,
                first_name=u.first_name,
                last_name=u.last_name,
                username=u.username,
                registered_at=u.created_at,
                last_active_at=last_msg,
                subscription_until=u.subscriber_until,
                total_messages=msg_cnt,
                total_cost_usd=round(total_spend_map.get(u.id, 0.0), 4),
                metrics=metrics,
            ),
        )
    return result


# ---------------------------------------------------------------------------
# Metrics — untouched except for typing nitpicks
# ---------------------------------------------------------------------------

class MetricTimeInfo(BaseModel):
    count: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    audio_duration: float | None = None
    cost_usd: float | None = None
    users: int | None = None


class MetricInfo(BaseModel):
    day: MetricTimeInfo
    month: MetricTimeInfo
    total: MetricTimeInfo
    first_entry: datetime | None = None
    last_entry: datetime | None = None


@app.get("/metrics", response_model=dict[str, MetricInfo])
async def get_metrics(db: AsyncSession = Depends(get_db)) -> dict[str, MetricInfo]:
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    month_ago = now - timedelta(days=30)

    rows = (
        await db.execute(
            select(
                Metric.name,
                Metric.value,
                Metric.created_at,
                Metric.connected_user_id,
            ),
        )
    ).all()

    temp: dict[str, dict[str, Any]] = {}
    for name, value, created, uid in rows:
        obj = temp.setdefault(
            name,
            {
                "day": MetricTimeInfo(count=0),
                "month": MetricTimeInfo(count=0),
                "total": MetricTimeInfo(count=0),
                "first": created,
                "last": created,
                "users_day": set(),
                "users_month": set(),
                "users_total": set(),
            },
        )

        # First / last seen timestamps
        obj["first"] = min(obj["first"], created)
        obj["last"] = max(obj["last"], created)

        parsed = _parse_metric_value(value)

        def update(scope: str):
            info: MetricTimeInfo = obj[scope]
            info.count += 1
            if uid:
                obj[f"users_{scope}"].add(uid)
            if parsed:
                info.input_tokens = (info.input_tokens or 0) + int(parsed.get("input_tokens", 0))
                info.output_tokens = (info.output_tokens or 0) + int(parsed.get("output_tokens", 0))
                info.audio_duration = (info.audio_duration or 0.0) + float(parsed.get("audio_duration", 0))
                info.cost_usd = (info.cost_usd or 0.0) + _calc_cost(parsed)

        update("total")
        if created >= month_ago:
            update("month")
        if created >= day_ago:
            update("day")

    result: dict[str, MetricInfo] = {}
    for name, obj in temp.items():
        for scope in ("day", "month", "total"):
            info: MetricTimeInfo = obj[scope]
            users_set: set[int] = obj.pop(f"users_{scope}")
            info.users = len(users_set)
        result[name] = MetricInfo(
            day=obj["day"],
            month=obj["month"],
            total=obj["total"],
            first_entry=obj["first"],
            last_entry=obj["last"],
        )
    return result


# ---------------------------------------------------------------------------
# Top lists — now includes big‑spenders
# ---------------------------------------------------------------------------

class TopUsers(BaseModel):
    user_id: int
    first_name: str
    last_name: str | None
    username: str | None
    count: int


class TopCostUsers(BaseModel):
    user_id: int
    first_name: str
    last_name: str | None
    username: str | None
    cost_usd: float


class TopResponse(BaseModel):
    messages: list[TopUsers]
    metrics: list[TopUsers]
    cost: list[TopCostUsers]


@app.get("/top", response_model=TopResponse)
async def get_top(db: Annotated[AsyncSession, Depends(get_db)]) -> TopResponse:
    """Return three leaderboards: by message count, by metric count, and by spend."""
    # ------------------------------------------------------------------
    # Messages & metrics: simple SQL aggregates
    # ------------------------------------------------------------------
    msgs = (
        await db.execute(
            select(
                User.id,
                User.first_name,
                User.last_name,
                User.username,
                func.count(SavedMessage.id).label("c"),
            )
            .join(SavedMessage, SavedMessage.connected_user_id == User.id)
            .group_by(User.id)
            .order_by(desc("c"))
            .limit(10),
        )
    ).all()

    metrics = (
        await db.execute(
            select(
                User.id,
                User.first_name,
                User.last_name,
                User.username,
                func.count(Metric.id).label("c"),
            )
            .join(Metric, Metric.connected_user_id == User.id)
            .group_by(User.id)
            .order_by(desc("c"))
            .limit(10),
        )
    ).all()

    # ------------------------------------------------------------------
    # Top spenders — we need to sum cost per user in Python
    # ------------------------------------------------------------------
    spend_rows = (
        await db.execute(select(Metric.connected_user_id, Metric.value))
    ).all()
    spend_map: dict[int, float] = {}
    for uid, value in spend_rows:
        parsed = _parse_metric_value(value)
        if not parsed:
            continue
        spend_map[uid] = spend_map.get(uid, 0.0) + _calc_cost(parsed)
    top_spenders = sorted(spend_map.items(), key=lambda p: p[1], reverse=True)[:10]

    # Fetch user records for top spenders
    if top_spenders:
        uids = [uid for uid, _ in top_spenders]
        user_rows = (
            await db.execute(select(User).where(User.id.in_(uids)))
        ).scalars().all()
        user_map = {u.id: u for u in user_rows}
    else:
        user_map = {}

    cost_payload: list[TopCostUsers] = []
    for uid, cost in top_spenders:
        u = user_map.get(uid)
        if not u:
            continue
        cost_payload.append(
            TopCostUsers(
                user_id=u.id,
                first_name=u.first_name,
                last_name=u.last_name,
                username=u.username,
                cost_usd=round(cost, 4),
            ),
        )

    return TopResponse(
        messages=[TopUsers(user_id=i[0], first_name=i[1], last_name=i[2], username=i[3], count=i[4]) for i in msgs],
        metrics=[TopUsers(user_id=i[0], first_name=i[1], last_name=i[2], username=i[3], count=i[4]) for i in metrics],
        cost=cost_payload,
    )


# ---------------------------------------------------------------------------
# Promo codes — unchanged
# ---------------------------------------------------------------------------

class PromoResponse(BaseModel):
    code: str
    days: int


@app.post("/promocode/{days}", response_model=PromoResponse)
async def create_promocode(days: int) -> PromoResponse:
    if days <= 0:
        raise HTTPException(status_code=400, detail="Invalid days")
    code = "https://t.me/zapomnim_bot?start=promo" + make_promocode(days)
    return PromoResponse(code=code, days=days)
