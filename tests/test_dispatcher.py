from mm_post_bot.dispatcher import MessageRouter, redact_command_for_log


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
