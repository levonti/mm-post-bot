from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from urllib.parse import urlencode

from itsdangerous import BadSignature, URLSafeTimedSerializer

from ..repository import WebLoginTokenRepo

SESSION_SALT = "mm-post-bot-web-session"
CSRF_SALT = "mm-post-bot-web-csrf"


@dataclass(frozen=True, slots=True)
class WebSession:
    user_id: str
    username: str
    csrf_nonce: str


def hash_login_token(raw_token: str) -> str:
    return sha256(raw_token.encode("utf-8")).hexdigest()


def create_login_token(
    *,
    token_repo: WebLoginTokenRepo,
    owner_user_id: str,
    now: datetime,
    ttl_seconds: int,
) -> str:
    raw_token = token_urlsafe(32)
    token_repo.create(
        owner_user_id=owner_user_id,
        token_sha256=hash_login_token(raw_token),
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    return raw_token


def build_login_url(web_base_url: str, raw_token: str) -> str:
    base = web_base_url.rstrip("/")
    return f"{base}/login?{urlencode({'token': raw_token})}"


def sign_session(secret: str, *, user_id: str, username: str, csrf_nonce: str) -> str:
    serializer = URLSafeTimedSerializer(secret, salt=SESSION_SALT)
    return serializer.dumps(
        {
            "user_id": user_id,
            "username": username,
            "csrf_nonce": csrf_nonce,
        }
    )


def load_session(secret: str, cookie_value: str, *, max_age_seconds: int) -> WebSession:
    serializer = URLSafeTimedSerializer(secret, salt=SESSION_SALT)
    payload = serializer.loads(cookie_value, max_age=max_age_seconds)
    if not isinstance(payload, dict):
        raise BadSignature("session payload is not an object")
    user_id = payload.get("user_id")
    username = payload.get("username")
    csrf_nonce = payload.get("csrf_nonce")
    if not isinstance(user_id, str) or not user_id:
        raise BadSignature("session payload is missing user_id")
    if not isinstance(username, str) or not username:
        raise BadSignature("session payload is missing username")
    if not isinstance(csrf_nonce, str) or not csrf_nonce:
        raise BadSignature("session payload is missing csrf_nonce")
    return WebSession(user_id=user_id, username=username, csrf_nonce=csrf_nonce)


def csrf_token_for_session(secret: str, csrf_nonce: str) -> str:
    serializer = URLSafeTimedSerializer(secret, salt=CSRF_SALT)
    return serializer.dumps({"csrf_nonce": csrf_nonce})


def verify_csrf_token(secret: str, csrf_nonce: str, token: str) -> bool:
    serializer = URLSafeTimedSerializer(secret, salt=CSRF_SALT)
    try:
        payload = serializer.loads(token, max_age=24 * 60 * 60)
    except BadSignature:
        return False
    return isinstance(payload, dict) and payload.get("csrf_nonce") == csrf_nonce
