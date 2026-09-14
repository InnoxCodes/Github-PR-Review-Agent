import stat

from cryptography.fernet import Fernet

from app.config import Settings
from app.security import TokenCipher, load_or_create_key, token_hint


def test_tokens_round_trip_and_ciphertext_hides_them():
    cipher = TokenCipher(Fernet.generate_key())

    ciphertext = cipher.encrypt("ghp_abcdefghijklmnop")

    assert "ghp_" not in ciphertext
    assert cipher.decrypt(ciphertext) == "ghp_abcdefghijklmnop"


def test_ciphertext_from_another_key_is_rejected_quietly():
    ciphertext = TokenCipher(Fernet.generate_key()).encrypt("secret")

    assert TokenCipher(Fernet.generate_key()).decrypt(ciphertext) is None


def test_key_file_is_created_owner_only_and_reused(tmp_path):
    settings = Settings(_env_file=None, secret_key_file=tmp_path / "data" / "secret.key")

    first = load_or_create_key(settings)
    mode = stat.S_IMODE((tmp_path / "data" / "secret.key").stat().st_mode)

    assert mode == 0o600
    assert load_or_create_key(settings) == first


def test_explicit_secret_key_wins_over_the_key_file(tmp_path):
    key = Fernet.generate_key().decode()
    settings = Settings(_env_file=None, secret_key=key, secret_key_file=tmp_path / "secret.key")

    assert load_or_create_key(settings) == key.encode()
    assert not (tmp_path / "secret.key").exists()


def test_token_hint_only_reveals_the_last_four_characters_of_long_tokens():
    assert token_hint("ghp_supersecrettoken1234") == "1234"
    assert token_hint("short") is None
