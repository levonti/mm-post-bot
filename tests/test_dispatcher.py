from typing import cast

from mm_post_bot.commands import CommandContext, dispatch
from mm_post_bot.dispatcher import (
    CommandContextFactory,
    MessageRouter,
    handle_event,
    redact_command_for_log,
)


class _UnusedContextFactory:
    def from_post(self, post, channel_type):
        raise AssertionError("context factory should not be called")


def test_dm_is_command():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "u1", "message": "!help"}, "D") == "!help"


def test_channel_mention_is_command():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    post = {"user_id": "u1", "message": "@postbot !status"}
    assert router.extract_command(post, "O") == "!status"


def test_channel_without_mention_is_ignored():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "u1", "message": "!status"}, "O") is None


def test_self_message_is_ignored():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "mgr", "message": "!help"}, "D") is None


def test_non_command_dm_can_be_draft_body():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "u1", "message": "draft body"}, "D") is None
    post = {"user_id": "u1", "message": "draft body"}
    assert router.extract_draft_body(post, "D") == "draft body"


def test_draft_body_only_in_dm():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_draft_body({"user_id": "u1", "message": "draft body"}, "O") is None


def test_redacts_bot_add_token():
    assert redact_command_for_log("!bot add news secret-token") == "!bot add news [REDACTED]"


async def test_malformed_post_json_is_ignored():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    event = {"event": "posted", "data": {"post": "{bad", "channel_type": "D"}}

    response = await handle_event(
        event,
        router=router,
        context_factory=cast(CommandContextFactory, _UnusedContextFactory()),
    )

    assert response is None


async def test_dispatch_returns_parse_error_for_malformed_shell_syntax():
    response = await dispatch(cast(CommandContext, object()), '!help "unterminated')

    assert response == "Could not parse command: No closing quotation"
