# =============================================================================
# config.py
# Single source of truth: bot token + per-user permissions.
# Add every authorized user here. Anyone not listed is BLOCKED entirely.
# =============================================================================

TOKEN = "8746102400:AAHs01F6zGs8Pdo4POeDGYPbIMMC9gR2dZs"

# ---------------------------------------------------------------------------
# USER_PERMISSIONS
# Key   → Telegram numeric user ID (int)
# Value → user metadata + feature flags
#
# Features:
#   create_folder   – can create new folders
#   continue_folder – can resume existing folders
#   send_receipts   – can send/view receipts
#   accounting      – can see financial analytics
#   admin_panel     – can view per-admin sales reports
# ---------------------------------------------------------------------------
USER_PERMISSIONS: dict = {
    507656596: {
        "name": "hadi",
        "language": "fa",       # "fa" | "en"  (default language)
        "features": {
            "create_folder":   True,
            "continue_folder": True,
            "send_receipts":   True,
            "accounting":      True,
            "admin_panel":     True,
        },
    },
    94732600: {
        "name": "amir arab",
        "language": "en",
        "features": {
            "create_folder":   True,
            "continue_folder": True,
            "send_receipts":   True,
            "accounting":      True,
            "admin_panel":     True,
        },
    },
    # ── Add more users below ───────────────────────────────────────────────
    # 333333333: {
    #     "name": "Viewer",
    #     "language": "en",
    #     "features": {
    #         "create_folder":   False,
    #         "continue_folder": False,
    #         "send_receipts":   True,
    #         "accounting":      True,
    #         "admin_panel":     False,
    #     },
    # },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_allowed(user_id: int) -> bool:
    """Return True only if user_id exists in USER_PERMISSIONS."""
    return user_id in USER_PERMISSIONS


def get_user(user_id: int) -> dict | None:
    return USER_PERMISSIONS.get(user_id)


def has_feature(user_id: int, feature: str) -> bool:
    """Double-checked permission gate used by both UI and execution layers."""
    user = USER_PERMISSIONS.get(user_id)
    if not user:
        return False
    return bool(user.get("features", {}).get(feature, False))


def get_default_language(user_id: int) -> str:
    user = USER_PERMISSIONS.get(user_id)
    return user.get("language", "en") if user else "en"


def get_admin_list() -> list[dict]:
    """Return [{id, name}, ...] for every entry in USER_PERMISSIONS."""
    return [
        {"id": uid, "name": info["name"]}
        for uid, info in USER_PERMISSIONS.items()
    ]
