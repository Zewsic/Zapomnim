# Тип для любой модели, унаследованной от Base
import json
from datetime import datetime
from typing import TypeVar

from sqlalchemy import inspect

from database import Base, RedisSession

T = TypeVar("T", bound=Base)


class CustomEncoder(json.JSONEncoder):
    """Кастомный JSON-энкодер для обработки сложных типов, например, datetime"""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


async def save_to_redis(obj: Base, key_prefix: str = "default") -> "Base":
    """Сохраняет SQLAlchemy ORM объект в Redis в формате JSON.

    Args:
        obj: SQLAlchemy ORM объект, унаследованный от Base
        key_prefix: Префикс ключа в Redis (например, 'message' для 'message:123')

    """
    if not isinstance(obj, Base):
        raise ValueError("Объект должен быть унаследован от Base")

    mapper = inspect(obj.__class__)
    table_name = mapper.tables[0].name
    primary_key = mapper.primary_key[0].name
    key_value = getattr(obj, primary_key)

    data = {c.name: getattr(obj, c.name) for c in mapper.columns}
    json_data = json.dumps(data, cls=CustomEncoder)

    await RedisSession.set(f"{key_prefix}:{table_name}:{key_value}", json_data)
    return obj


async def load_from_redis(model: type[T], key_value: str, key_prefix: str = "default") -> T | None:
    """Загружает SQLAlchemy ORM объект из Redis по ключу.

    Args:
        model: Класс SQLAlchemy модели
        key_prefix: Префикс ключа в Redis
        key_value: Значение первичного ключа

    Returns:
        Объект модели или None, если данные не найдены

    """
    if not issubclass(model, Base):
        raise ValueError("Модель должна быть унаследована от Base")

    mapper = inspect(model)
    table_name = mapper.tables[0].name

    json_data = await RedisSession.get(f"{key_prefix}:{table_name}:{key_value}")

    if json_data is None:
        return None

    data = json.loads(json_data)
    for column in inspect(model).columns:
        if str(column.type) in ("DATETIME", "TIMESTAMP"):
            name = column.name
            if name in data and isinstance(data[name], str):
                try:
                    data[name] = datetime.fromisoformat(data[name])
                except Exception:
                    pass  # можно обработать другие форматы, если нужно
    return model(**data)
