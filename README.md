# Telegram Stars payments

This project uses [Telegram Stars](https://core.telegram.org/bots/payments) to sell subscriptions.

Example of creating an invoice link with **aiogram**:

```python
from aiogram.types import LabeledPrice

invoice_link = await bot.create_invoice_link(
    title="Подписка на %(days)d дней",
    description="Доступ ко всем функциям на %(days)d дней",
    payload=f"sub_{user_id}_{days}",
    currency="XTR",
    prices=[LabeledPrice(label="Подписка", amount=int(price * 100))],
    start_parameter=f"sub_{days}"
)
```
