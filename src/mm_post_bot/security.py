import hashlib

from cryptography.fernet import Fernet


def encrypt_token(token: str, key: str) -> str:
    return Fernet(key.encode()).encrypt(token.encode()).decode()


def decrypt_token(ciphertext: str, key: str) -> str:
    return Fernet(key.encode()).decrypt(ciphertext.encode()).decode()


def fingerprint_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def hash_message(message: str) -> str:
    return hashlib.sha256(message.encode()).hexdigest()
