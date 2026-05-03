# =============================================================================
# keyboards.py
# All keyboards.
# =============================================================================

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config import get_admin_list
from i18n import t

# ---------------------------------------------------------------------------
# Language selection  (pre-auth — no permissions)
# ---------------------------------------------------------------------------

def kb_language() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇸 English", callback_data="lang:en"),
        InlineKeyboardButton(text="🇮🇷 فارسی",   callback_data="lang:fa"),
    ]])


# ---------------------------------------------------------------------------
# Main menu — Native Telegram ReplyKeyboardMarkup
# ---------------------------------------------------------------------------

def kb_main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn_create_folder")),
                KeyboardButton(text=t(lang, "btn_continue_folder")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_send_receipts")),
                KeyboardButton(text=t(lang, "btn_accounting")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_admin_panel")),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True
    )


# ---------------------------------------------------------------------------
# Folder list
# ---------------------------------------------------------------------------

def kb_folders(folders: list[str], prefix: str, lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=f"📁 {name}", callback_data=f"{prefix}:{name}")]
        for name in folders
    ]
    # Add a back button as well, just in case they want to step back inline
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Send receipts — mode picker
# ---------------------------------------------------------------------------

def kb_send_mode(lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=t(lang, "btn_send_time_only"),   callback_data="sendmode:time_only")],
        [InlineKeyboardButton(text=t(lang, "btn_send_full_report"), callback_data="sendmode:full_report")],
        [InlineKeyboardButton(text=t(lang, "btn_back"),             callback_data="nav:back_to_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Accounting report type
# ---------------------------------------------------------------------------

def kb_accounting(lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=t(lang, "btn_total_volume"), callback_data="acct:volume")],
        [InlineKeyboardButton(text=t(lang, "btn_total_amount"), callback_data="acct:amount")],
        [InlineKeyboardButton(text=t(lang, "btn_back"),         callback_data="nav:back_to_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Generic back-to-menu screen
# ---------------------------------------------------------------------------

def kb_back_to_menu(lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:back_to_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Admin panel — admin list
# ---------------------------------------------------------------------------

def kb_admins(lang: str) -> InlineKeyboardMarkup:
    admins = get_admin_list()
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(
            text=f"🙋 {a['name']}",
            callback_data=f"admin_pick:{a['id']}:{a['name']}",
        )]
        for a in admins
    ]
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="nav:back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Receipt collection keyboards
# ---------------------------------------------------------------------------

def kb_admin_select(lang: str) -> InlineKeyboardMarkup:
    """Step 5 — inline admin buttons only (no free-text)."""
    admins = get_admin_list()
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(
            text=f"🙋 {a['name']}",
            callback_data=f"s5_admin:{a['name']}",
        )]
        for a in admins
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_confirm(lang: str) -> InlineKeyboardMarkup:
    """Step 7 confirm screen."""
    rows: list[list[InlineKeyboardButton]] = [[
        InlineKeyboardButton(text=t(lang, "btn_confirm"), callback_data="confirm:yes"),
        InlineKeyboardButton(text=t(lang, "btn_edit"),    callback_data="confirm:edit"),
    ]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_edit_fields(lang: str) -> InlineKeyboardMarkup:
    """Edit-field picker."""
    fields = [
        ("btn_f_customer", "ef:customer"),
        ("btn_f_amount",   "ef:amount"),
        ("btn_f_volume",   "ef:volume"),
        ("btn_f_time",     "ef:time"),
        ("btn_f_admin",    "ef:admin"),
        ("btn_f_receipt",  "ef:receipt"),
    ]
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=t(lang, lk), callback_data=cb)]
        for lk, cb in fields
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_after_save(lang: str) -> InlineKeyboardMarkup:
    """Continue / Finish after saving a receipt."""
    rows: list[list[InlineKeyboardButton]] = [[
        InlineKeyboardButton(text=t(lang, "btn_add_another"), callback_data="after:continue"),
        InlineKeyboardButton(text=t(lang, "btn_finish"),      callback_data="after:finish"),
    ]]
    return InlineKeyboardMarkup(inline_keyboard=rows)
