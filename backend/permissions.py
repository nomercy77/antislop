"""Role capabilities for UI discovery; resource authorization stays on the server.

An approved coder's capabilities are computed from current database status on
every authenticated request. Session cookies never encode roles or approval.
"""

ROLE_PERMISSIONS = {
    "submitter": (
        "create_review", "read_own_reviews", "assign_reviewer",
        "request_repository_access", "read_review_messages", "send_review_messages",
    ),
    "coder": ("apply_verification", "read_own_reviews"),
    "team": ("read_verification_queue", "decide_verification"),
}

APPROVED_CODER_PERMISSIONS = (
    "read_assigned_reviews", "browse_opportunities", "read_review_messages", "send_review_messages",
)


def effective_permissions(role: str, verification_status: str | None = None) -> list[str]:
    permissions = list(ROLE_PERMISSIONS.get(role, ()))
    if role == "coder" and verification_status == "approved":
        permissions.extend(APPROVED_CODER_PERMISSIONS)
    return permissions
