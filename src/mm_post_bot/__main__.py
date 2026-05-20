from mm_post_bot.config import load_settings
from mm_post_bot.logging import configure_logging


def run() -> None:
    """Console script placeholder until runtime wiring is implemented."""
    settings = load_settings()
    configure_logging(settings.log_level)
    raise SystemExit("Runtime entrypoint will be wired in a later task.")
