import uuid

from os import environ
from yookassa import Configuration, Payment

Configuration.account_id = environ.get('YOUKASSA_ACCOUNT_ID', '1115066')
Configuration.secret_key = environ.get('YOUKASSA_SECRET_KEY', 'test_-6tz03bxlzvfvVyFG18IITf2nMsjN24UAhgub1RMvBc')

payment = Payment.create({
    "amount": {
        "value": "100.00",
        "currency": "RUB"
    },
    "confirmation": {
        "type": "redirect",
        "return_url": "https://www.example.com/return_url"
    },
    "capture": True,
    "save_payment_method": True,
    "description": "Заказ №1"
}, uuid.uuid4())

print(payment.json())
