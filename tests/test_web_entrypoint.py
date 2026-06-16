from mm_post_bot.web import __main__ as web_entrypoint


def test_web_entrypoint_exposes_callable_run():
    assert callable(web_entrypoint.run)
