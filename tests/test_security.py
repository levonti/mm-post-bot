from cryptography.fernet import Fernet

from mm_post_bot.security import decrypt_token, encrypt_token, fingerprint_token, hash_message


def test_encrypt_decrypt_roundtrip():
    key = Fernet.generate_key().decode()
    ciphertext = encrypt_token("secret-token", key)

    assert ciphertext != "secret-token"
    assert decrypt_token(ciphertext, key) == "secret-token"


def test_fingerprint_is_stable_and_non_secret():
    first = fingerprint_token("secret-token")
    second = fingerprint_token("secret-token")

    assert first == second
    assert "secret-token" not in first
    assert len(first) == 16


def test_message_hash_is_stable():
    assert hash_message("hello") == hash_message("hello")
    assert hash_message("hello") != hash_message("goodbye")
