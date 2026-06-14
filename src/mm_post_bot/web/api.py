from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ..i18n import translate
from ..services.web_auth import WebSession
from .deps import csrf_token, current_session
from .routes import _session_locale

api_router = APIRouter(prefix="/api/web")

NAV_ITEMS = (
    ("/", "composer", "web.nav.composer"),
    ("/drafts", "drafts", "web.nav.drafts"),
    ("/targets", "targets", "web.nav.targets"),
    ("/audit", "audit", "web.nav.audit"),
)


@api_router.get("/bootstrap")
def bootstrap(
    request: Request,
    session: Annotated[WebSession, Depends(current_session)],
    csrf: Annotated[str, Depends(csrf_token)],
) -> dict[str, object]:
    locale = _session_locale(request, session)
    return {
        "session": {
            "user_id": session.user_id,
            "username": session.username,
        },
        "locale": locale,
        "csrf": csrf,
        "nav": [
            {"href": href, "key": key, "label": translate(locale, label_key)}
            for href, key, label_key in NAV_ITEMS
        ],
    }
