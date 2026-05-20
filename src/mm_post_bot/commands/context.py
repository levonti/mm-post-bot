from dataclasses import dataclass

from ..mm_client import MattermostClient
from ..repository import AuditRepo, DraftCaptureRepo, PostDraftRepo, UserBotRepo, UserRepo


@dataclass(frozen=True, slots=True)
class CommandContext:
    caller_user_id: str
    caller_username: str
    channel_id: str
    channel_type: str | None
    user_repo: UserRepo
    user_bot_repo: UserBotRepo
    draft_capture_repo: DraftCaptureRepo
    post_draft_repo: PostDraftRepo
    audit_repo: AuditRepo
    manager_mm: MattermostClient
    manager_user_id: str
    admin_usernames: frozenset[str]
    mm_rest_base: str
    mm_url: str
    token_encryption_key: str
    mm_verify_ssl: bool
