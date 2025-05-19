import base64
import hashlib
from os import environ

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PRIVACY_SECRET_KEY = environ.get('PRIVACY_SECRET_KEY').encode()
ENCRYPTION_SALT = environ.get('ENCRYPTION_SALT').encode()


def generate_privacy_key(connected_user_id: int, chat_id: int, message_id: int):
    payload = f"{connected_user_id}:{chat_id}:{message_id}"
    h_b = hashlib.blake2s(payload.encode(), key=PRIVACY_SECRET_KEY[:32]).digest()
    return base64.urlsafe_b64encode(h_b).rstrip(b"=").decode()


def generate_encryption_data(connected_user_id: int, chat_id: int, message_id: int) -> bytes:
    payload = f"{connected_user_id}:{chat_id}:{message_id}".encode()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32+12,
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