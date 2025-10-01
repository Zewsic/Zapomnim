import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

# =========================
#  Lua Token‑Bucket Script
# =========================

TOKEN_BUCKET_LUA = """
--[[
 KEYS[1] = bucket key
 ARGV[1] = capacity
 ARGV[2] = refill_interval_ms
 ARGV[3] = now (ms)

Returns:
  1  — токен выдан, запрос разрешён
  0  — ведро пусто, запрос отвергнут
]]
local capacity = tonumber(ARGV[1])
local interval = tonumber(ARGV[2])
local now      = tonumber(ARGV[3])

local bucket = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(bucket[1]) or capacity
local ts     = tonumber(bucket[2]) or now

-- refill
local delta = math.max(0, now - ts)
local refill = math.floor(delta / interval)
_tokens = math.min(capacity, tokens + refill)
ts = ts + refill * interval

local allowed = 0
if tokens > 0 then
  tokens = tokens - 1
  allowed = 1
end

redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', ts)
-- Авто‑удаление когда ведро неактивно
redis.call('PEXPIRE', KEYS[1], 2 * interval * capacity)
return allowed
"""


@dataclass(slots=True)
class ThrottleConfig:
    """Параметры скользящего окна и бана."""

    capacity: int = 10          # сколько запросов допускается
    window_seconds: int = 1     # размер окна (в секундах)
    ban_attempts: int = 3       # сколько превышений подряд → бан
    ban_ttl_seconds: int = 60   # базовый TTL бана (экспоненциально ×2)


class DistributedThrottleMiddleware(BaseMiddleware):
    """Скользящее окно на Redis + Python (без Lua).

    Для каждого входящего Update:
    1. Генерирует ключ (user‑id, chat‑id, IP и т.п.) — см. `key_factory`.
    2. В одном `pipeline` выполняет 4 команды (см. оглавление).
    3. Если лимит превышен — отправляет `ban_message` и прерывает обработку.

    Parameters
    ----------
    redis : aioredis.Redis
        Подключение к Redis/Cluster/Sentinel (asyncio).
    config : ThrottleConfig | None
        Настройки окна и бана.
    key_factory : Callable[[TelegramObject], str | None] | None
        Функция, возвращающая строковый ключ. Если вернёт None — событие не
        лимитируется.
    ban_message : str | None
        Текст, отправляемый при блокировке. None → ничего не отправлять.

    """

    def __init__(
        self,
        redis: aioredis.Redis,
        config: ThrottleConfig | None = None,
        *,
        key_factory: Callable[[TelegramObject], str | None] | None = None,
        ban_message: str | None = "Слишком часто — отдыхайте ⛔",
    ) -> None:
        self.redis = redis
        self.cfg = config or ThrottleConfig()
        self.key_factory = key_factory or self._default_key
        self.ban_message = ban_message

    # ------------------------------------------------------------
    #  Middleware entry-point
    # ------------------------------------------------------------
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        key = self.key_factory(event)
        if key is None:
            return await handler(event, data)

        # Проверка активного бана
        ban_key = f"ban:{key}"
        if await self.redis.exists(ban_key):
            await self._notify_ban(event)
            return None  # прерываем цепочку

        rate_key = f"sw:{key}"
        now_ms = int(time.time() * 1000)
        window_start = now_ms - self.cfg.window_seconds * 1000
        member = f"{now_ms}-{uuid.uuid4().hex}"

        # Атомарная транзакция MULTI/EXEC
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.zremrangebyscore(rate_key, 0, window_start)
            await pipe.zadd(rate_key, {member: now_ms})
            await pipe.zcard(rate_key)
            await pipe.expire(rate_key, self.cfg.window_seconds * 2)
            removed, _added, count, _ = await pipe.execute()

        if count <= self.cfg.capacity:
            return await handler(event, data)

        # --- Превышен лимит ---
        exceed_key = f"exceed:{key}"
        attempt = await self.redis.incr(exceed_key)
        if attempt == 1:
            await self.redis.expire(exceed_key, self.cfg.window_seconds * 2)
        if attempt >= self.cfg.ban_attempts:
            ttl = self.cfg.ban_ttl_seconds * (2 ** (attempt - self.cfg.ban_attempts))
            await self.redis.setex(ban_key, ttl, 1)
            await self.redis.delete(exceed_key)
        await self._notify_ban(event)
        # Не вызываем handler — цепочка обрывается

    # ------------------------------------------------------------
    #  Helper methods
    # ------------------------------------------------------------
    async def _notify_ban(self, event: TelegramObject) -> None:
        if self.ban_message and type(event) in (Message, CallbackQuery):
            try:
                await event.answer(self.ban_message)
            except Exception:
                pass

    @staticmethod
    def _default_key(event: TelegramObject) -> str | None:
        if isinstance(event, Message):
            return str(event.from_user.id)
        if isinstance(event, CallbackQuery):
            return str(event.from_user.id)
        return None
