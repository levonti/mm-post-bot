from dataclasses import dataclass
from typing import Any

from ..i18n import translate
from ..mm_client import MattermostClient
from ..repository import (
    AuditRepo,
    DraftCaptureRepo,
    PostDraftRepo,
    UserBotRepo,
    UserChannelRepo,
    UserPostDefaultRepo,
    UserPreferenceRepo,
    UserRepo,
    WebLoginTokenRepo,
)


@dataclass(frozen=True, slots=True)
class CommandContext:
    caller_user_id: str
    caller_username: str
    channel_id: str
    channel_type: str | None
    user_repo: UserRepo
    user_preference_repo: UserPreferenceRepo
    user_bot_repo: UserBotRepo
    user_channel_repo: UserChannelRepo
    user_post_default_repo: UserPostDefaultRepo
    draft_capture_repo: DraftCaptureRepo
    post_draft_repo: PostDraftRepo
    web_login_token_repo: WebLoginTokenRepo
    audit_repo: AuditRepo
    manager_mm: MattermostClient
    manager_user_id: str
    admin_usernames: frozenset[str]
    mm_rest_base: str
    mm_url: str
    token_encryption_key: str
    mm_verify_ssl: bool
    web_base_url: str
    web_login_token_ttl_seconds: int
    default_locale: str
    locale: str

    def t(self, key: str, **params: Any) -> str:
        return translate(self.locale, key, **params)
