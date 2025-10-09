# Stars Rating Implementation

## Описание, бля

Добавлена поддержка поля `stars_rating` из TL объекта `UserFull` в API бота. Теперь можно сохранять и возвращать информацию о рейтинге пользователя.

## TL Схема

Конструктор из Telegram:
```tl
starsRating#1b0e4f07 flags:# level:int current_level_stars:long stars:long next_level_stars:flags.0?long = StarsRating;
```

## Изменения в базе данных

Добавлены новые поля в модель `User` (файл `database/models.py`):

- `stars_level: int | None` - уровень рейтинга пользователя
- `stars_current_level_stars: int | None` - звёзды на текущем уровне
- `stars_total_stars: int | None` - общее количество звёзд
- `stars_next_level_stars: int | None` - звёзды для следующего уровня (опциональное)

## Изменения в API

### Новая модель данных

Добавлена модель `StarsRating` в `utils/admin_api.py`:

```python
class StarsRating(BaseModel):
    level: int
    current_level_stars: int
    stars: int
    next_level_stars: int | None = None
```

### Изменения в UserInfo

В модель `UserInfo` добавлено поле:
```python
stars_rating: StarsRating | None = None
```

Это поле автоматически заполняется в эндпоинте `/admin/users` если у пользователя есть данные о рейтинге.

## Использование, мать его

### Обновление рейтинга пользователя

Используй функцию `update_user` из `utils/userdata.py`:

```python
from utils.userdata import update_user
from database import create_session

async with create_session() as session:
    # Пример обновления stars_rating из TL UserFull
    user = await update_user(
        id=user_id,
        session=session,
        stars_level=5,
        stars_current_level_stars=1234,
        stars_total_stars=56789,
        stars_next_level_stars=2000,  # Опционально
    )
```

### Получение данных через API

Эндпоинт: `GET /admin/users`

Пример ответа:
```json
{
  "id": 123456789,
  "first_name": "Иван",
  "last_name": "Иванов",
  "username": "ivan",
  "registered_at": "2024-01-01T00:00:00",
  "last_active_at": "2024-01-15T12:00:00",
  "subscription_until": "2024-02-01T00:00:00",
  "total_messages": 100,
  "total_cost_usd": 1.23,
  "metrics": {},
  "stars_rating": {
    "level": 5,
    "current_level_stars": 1234,
    "stars": 56789,
    "next_level_stars": 2000
  }
}
```

Если у пользователя нет данных о рейтинге, поле `stars_rating` будет `null`.

## Интеграция с Telegram

Чтобы получить данные из TL объекта `UserFull`, тебе нужно:

1. Использовать MTProto клиент (например, Telethon или Pyrogram)
2. Получить объект `UserFull` через метод `users.getFullUser`
3. Извлечь поле `stars_rating` из ответа
4. Обновить данные в базе через `update_user`

Пример с Telethon:
```python
from telethon import TelegramClient

async def update_user_stars_rating(user_id: int):
    async with TelegramClient(...) as client:
        user_full = await client(GetFullUserRequest(user_id))
        
        if user_full.full_user.stars_rating:
            rating = user_full.full_user.stars_rating
            
            async with create_session() as session:
                await update_user(
                    id=user_id,
                    session=session,
                    stars_level=rating.level,
                    stars_current_level_stars=rating.current_level_stars,
                    stars_total_stars=rating.stars,
                    stars_next_level_stars=rating.next_level_stars,
                )
```

## Миграция базы данных

После обновления кода нужно создать миграцию для добавления новых полей в таблицу `users`:

```sql
ALTER TABLE users 
ADD COLUMN stars_level INTEGER DEFAULT NULL,
ADD COLUMN stars_current_level_stars BIGINT DEFAULT NULL,
ADD COLUMN stars_total_stars BIGINT DEFAULT NULL,
ADD COLUMN stars_next_level_stars BIGINT DEFAULT NULL;
```

Или используй Alembic для автоматической миграции, если настроен в проекте.

## Готово, сука!

Теперь твой бот может сохранять и возвращать информацию о рейтинге пользователя через API! 🎉
