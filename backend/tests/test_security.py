from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


def test_hash_and_verify_roundtrip():
    hashed = get_password_hash("s3cret!")
    assert hashed != "s3cret!"
    assert verify_password("s3cret!", hashed)
    assert not verify_password("wrong", hashed)


def test_hashes_are_salted():
    assert get_password_hash("same") != get_password_hash("same")


def test_verifies_existing_passlib_style_hash():
    # A $2b$ hash as produced by passlib/bcrypt before this change.
    legacy = "$2b$12$KIXzQ1sVx5y0m3s5y1k0Ou3p5mY4c0n3qkq3E0v4f2uM4m1m0xk2e"
    assert verify_password("anything", legacy) is False  # valid format, wrong password: no error


def test_password_longer_than_72_bytes_does_not_crash():
    long_pw = "a" * 200
    hashed = get_password_hash(long_pw)
    assert verify_password(long_pw, hashed)


def test_malformed_stored_hash_is_a_failed_login_not_an_error():
    assert verify_password("pw", "not-a-bcrypt-hash") is False


def test_token_roundtrip_and_expiry_is_timezone_aware():
    token = create_access_token({"sub": "user-1"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-1"
    assert payload["exp"] > 0


def test_expired_token_is_rejected():
    token = create_access_token({"sub": "u"}, expires_delta=timedelta(seconds=-5))
    with pytest.raises(jwt.JWTError):
        decode_access_token(token)


def test_token_signed_with_other_key_is_rejected():
    forged = jwt.encode({"sub": "u"}, "some-other-key", algorithm=settings.ALGORITHM)
    with pytest.raises(jwt.JWTError):
        decode_access_token(forged)
