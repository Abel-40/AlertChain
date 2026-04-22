from pwdlib import PasswordHash
from typing import Dict, Tuple
from datetime import timedelta, datetime
from app.core.config import settings
import jwt
from uuid import uuid4

password_hasher = PasswordHash.recommended()


def hash_password(password: str):
    return password_hasher.hash(password=password)


def verify_password(password: str, password_in_db: str):
    return password_hasher.verify(password=password, hash=password_in_db)


def token_generator(data: Dict, expire: timedelta, key: str, return_jti: bool = False):
    """Generate a JWT and include standard claims: exp, iat, jti, iss, aud.

    If `return_jti` is True, return a tuple `(token, jti)` so callers can store the jti server-side.
    """
    to_encode = data.copy()
    now = datetime.utcnow()
    exp_time = now + expire
    jti = str(uuid4())
    to_encode.update({
        "exp": exp_time,
        "iat": now,
        "jti": jti,
        "iss": settings.JWT_ISS,
        "aud": settings.JWT_AUD,
    })

    token = jwt.encode(to_encode, key=key, algorithm=settings.ALGO)
    if return_jti:
        return token, jti
    return token

