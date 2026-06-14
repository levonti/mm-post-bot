from datetime import UTC, datetime, timedelta

from itsdangerous import BadSignature
from test_commands import ctx as _commands_ctx
from test_commands import pg_conn as _commands_pg_conn

from mm_post_bot.services.web_auth import (
    build_login_url,
    create_login_token,
    csrf_token_for_session,
    hash_login_token,
    load_session,
    sign_session,
    verify_csrf_token,
)

ctx = _commands_ctx
pg_conn = _commands_pg_conn


def test_login_token_hash_is_stable_and_secret_is_not_in_hash():
    raw = "raw-token-value"

    digest = hash_login_token(raw)

    assert digest == hash_login_token(raw)
    assert raw not in digest
    assert len(digest) == 64


def test_build_login_url_uses_token_query_param():
    url = build_login_url("https://posts.internal/app/", "abc123")

    assert url == "https://posts.internal/app/login?token=abc123"


def test_create_login_token_stores_hash_and_returns_raw_token(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    now = datetime.now(UTC)

    raw = create_login_token(
        token_repo=ctx.web_login_tokens,
        owner_user_id="alice-id",
        now=now,
        ttl_seconds=300,
    )

    stored = ctx.web_login_tokens.get_usable(hash_login_token(raw), now=now)
    assert stored is not None
    assert stored.owner_user_id == "alice-id"
    assert stored.expires_at >= now + timedelta(seconds=299)


def test_session_sign_and_load_round_trip():
    secret = "s" * 32
    cookie = sign_session(
        secret,
        user_id="alice-id",
        username="alice",
        csrf_nonce="nonce-1",
    )

    session = load_session(secret, cookie, max_age_seconds=60)

    assert session.user_id == "alice-id"
    assert session.username == "alice"
    assert session.csrf_nonce == "nonce-1"


def test_session_rejects_wrong_secret():
    cookie = sign_session(
        "a" * 32,
        user_id="alice-id",
        username="alice",
        csrf_nonce="nonce-1",
    )

    try:
        load_session("b" * 32, cookie, max_age_seconds=60)
    except BadSignature:
        pass
    else:
        raise AssertionError("session signed with another secret should fail")


def test_csrf_token_is_bound_to_session_nonce():
    secret = "s" * 32
    token = csrf_token_for_session(secret, "nonce-1")

    assert verify_csrf_token(secret, "nonce-1", token) is True
    assert verify_csrf_token(secret, "nonce-2", token) is False
