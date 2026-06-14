import uvicorn

from ..config import load_settings
from ..logging import configure_logging
from .app import create_app_from_settings


def run() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        create_app_from_settings(settings),
        host=settings.web_host,
        port=settings.web_port,
    )


if __name__ == "__main__":
    run()
