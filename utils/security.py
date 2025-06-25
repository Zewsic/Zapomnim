import base64
import hashlib
import hmac
import os
from os import environ
from uuid import UUID, uuid4

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PRIVACY_SECRET_KEY = environ.get('PRIVACY_SECRET_KEY', '').encode()
ENCRYPTION_SALT = environ.get('ENCRYPTION_SALT', '').encode()
PROMO_ENC_DATA = environ.get('PROMO_ENC_DATA',
                             'S$^ED%RF^Tgi7yhu8j9i*H&G6f5d4s^DE%CR&F^VTG&YBH*U)&asasdad%adsa^y').encode()


def generate_privacy_key(connected_user_id: int, chat_id: int, message_id: int):
    payload = f"{connected_user_id}:{chat_id}:{message_id}"
    h_b = hashlib.blake2s(payload.encode(), key=PRIVACY_SECRET_KEY[:32]).digest()
    return base64.urlsafe_b64encode(h_b).rstrip(b"=").decode()


def generate_encryption_data(connected_user_id: int, chat_id: int, message_id: int) -> bytes:
    payload = f"{connected_user_id}:{chat_id}:{message_id}".encode()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32 + 12,
        salt=ENCRYPTION_SALT,
        info=b"EncryptionKey",
        backend=default_backend()
    )
    encryption_data = hkdf.derive(payload)
    return encryption_data


def encrypt_message(encryption_data: bytes, plaintext: str) -> str:
    aesgcm = AESGCM(encryption_data[:32])
    ciphertext = aesgcm.encrypt(encryption_data[32:], plaintext.encode(), None)
    return ciphertext.hex()


def decrypt_message(encryption_data: bytes, ciphertext_hex: str) -> str:
    aesgcm = AESGCM(encryption_data[:32])
    ciphertext = bytes.fromhex(ciphertext_hex)
    plaintext = aesgcm.decrypt(encryption_data[32:], ciphertext, None)
    return plaintext.decode()


def make_promocode(days: int) -> str:
    data = os.urandom(2) + days.to_bytes(2, 'big') + os.urandom(2)
    h = hmac.new(PROMO_ENC_DATA[:32], data, hashlib.sha256).digest()
    code = base64.urlsafe_b64encode(data + h[:4]).rstrip(b"=").decode()
    return code


def check_promocode(code: str) -> int | None:
    try:
        data = base64.urlsafe_b64decode(code + "=" * (-len(code) % 4))
        if len(data) != 10:
            return None
        days = int.from_bytes(data[2:4], 'big')
        signature = data[6:]
        expected_signature = hmac.new(PROMO_ENC_DATA[:32], data[:6], hashlib.sha256).digest()[:4]
        if hmac.compare_digest(signature, expected_signature):
            return days
    except Exception:
        pass
    return None


if __name__ == "__main__":
    for _ in [900]:
        promo = make_promocode(_)
        print(f'# {_} дней\nhttps://t.me/zapomnim_bot?start=promo{promo}\n')