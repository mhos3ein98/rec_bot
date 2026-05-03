# =============================================================================
# handlers.py
# All message + callback_query handlers.
#
# Rules enforced:
#  1. Main menu — all 5 buttons ALWAYS visible; permission checked AFTER click.
#  2. Send Only — outputs payment time (HH:MM) ONLY. Strictly nothing else.
#  3. No auto-navigation — bot NEVER redirects to menu automatically.
#     User must press 🔙 BACK manually from every result screen.
#  4. Double permission gate: UI alert + execution block.
# =============================================================================

from __future__ import annotations

import asyncio
import logging
import re
import time
from functools import wraps

from aiogram import F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message, PhotoSize

import storage
from config import get_user, has_feature, is_allowed, get_default_language
from i18n import t
from keyboards import (
    kb_accounting,
    kb_admin_select,
    kb_admins,
    kb_after_save,
    kb_back_to_menu,
    kb_confirm,
    kb_edit_fields,
    kb_folders,
    kb_language,
    kb_main_menu,
    kb_send_mode,
)
from state import (
    Accounting,
    AdminPanel,
    Collect,
    FolderNew,
    FolderPick,
    LangSelect,
    Menu,
    SendMode,
)

logger = logging.getLogger(__name__)
router = Router()


# ===========================================================================
# Interaction Lock & Debounce (Per-User)
# ===========================================================================

_USER_LOCKS: dict[int, asyncio.Lock] = {}
_LAST_CLICKS: dict[int, float] = {}

def interaction_lock(func):
    @wraps(func)
    async def wrapper(cb: CallbackQuery, state: FSMContext, *args, **kwargs):
        uid = cb.from_user.id
        now = time.time()
        
        # 1. Anti-Double Click (Debounce)
        if uid in _LAST_CLICKS and now - _LAST_CLICKS[uid] < 0.8:
            try:
                await cb.answer("Please wait...", show_alert=False)
            except Exception:
                pass
            return
        _LAST_CLICKS[uid] = now
        
        if uid not in _USER_LOCKS:
            _USER_LOCKS[uid] = asyncio.Lock()
            
        if _USER_LOCKS[uid].locked():
            try:
                await cb.answer("Processing...", show_alert=False)
            except Exception:
                pass
            return
            
        # 2. Acquire lock
        async with _USER_LOCKS[uid]:
            # 1. Always acknowledge callback
            try:
                await cb.answer()
            except Exception:
                pass
                
            # 3. Disable old keyboard
            try:
                if cb.message:
                    await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
                
            # 4. Process logic & 5. update UI
            return await func(cb, state, *args, **kwargs)
            
    return wrapper


# ===========================================================================
# Utilities
# ===========================================================================

def _fmt(value: str | int | float) -> str:
    """Format with dot-thousand separators: 6000000 → 6.000.000"""
    try:
        n = int(float(str(value).replace(",", "").replace(".", "")))
        return f"{n:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


def _valid_time(text: str) -> bool:
    return bool(re.fullmatch(r"\d{2}:\d{2}", text.strip()))


async def _lang(state: FSMContext, uid: int) -> str:
    d = await state.get_data()
    return d.get("lang") or storage.get_user_lang(uid) or get_default_language(uid)


def _summary(data: dict, lang: str) -> str:
    receipt_display = (
        t(lang, "receipt_image")
        if data.get("receipt_type") == "image"
        else data.get("receipt_text", "")
    )
    return (
        f"{t(lang,'summary_customer')}: {data.get('customer','')}\n"
        f"{t(lang,'summary_amount')}: {_fmt(data.get('amount',''))}\n"
        f"{t(lang,'summary_volume')}: {data.get('volume','')} GB\n"
        f"{t(lang,'summary_time')}: {data.get('time','')}\n"
        f"{t(lang,'summary_admin')}: {data.get('admin','')}\n"
        f"{t(lang,'summary_receipt')}: {receipt_display}"
    )


async def _show_main_menu(msg: Message, state: FSMContext, uid: int) -> None:
    """Send the main menu. All 5 buttons always present — no filtering."""
    lang = await _lang(state, uid)
    user = get_user(uid)
    name = user["name"] if user else str(uid)
    await state.set_state(Menu.idle)
    await msg.answer(
        t(lang, "welcome", name=name),
        reply_markup=kb_main_menu(lang),
    )


# ===========================================================================
# /start
# ===========================================================================

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext) -> None:
    uid = msg.from_user.id

    if not is_allowed(uid):
        await msg.answer(t("en", "access_denied"))
        return

    stored_lang = storage.get_user_lang(uid)
    if stored_lang:
        await state.update_data(lang=stored_lang)
        await _show_main_menu(msg, state, uid)
        return

    await state.set_state(LangSelect.choosing)
    await msg.answer(t("en", "language_prompt"), reply_markup=kb_language())


# ===========================================================================
# Language selection — one-time only
# ===========================================================================

@router.callback_query(LangSelect.choosing, F.data.startswith("lang:"))
@interaction_lock
async def cb_lang(cb: CallbackQuery, state: FSMContext) -> None:
    uid = cb.from_user.id
    if not is_allowed(uid):
        await cb.message.answer(t("en", "access_denied"))
        return

    lang = cb.data.split(":")[1]
    storage.set_user_lang(uid, lang)
    await state.update_data(lang=lang)
    await cb.message.delete()
    await _show_main_menu(cb.message, state, uid)


# ===========================================================================
# Universal back-to-menu (inline Back button)
# ===========================================================================

@router.callback_query(F.data == "nav:back_to_menu")
@interaction_lock
async def cb_back_to_menu(cb: CallbackQuery, state: FSMContext) -> None:
    uid = cb.from_user.id
    await _show_main_menu(cb.message, state, uid)


# ===========================================================================
# Main menu dispatch — via MenuButton commands OR ReplyKeyboardMarkup text
# ===========================================================================

def _action_from_text(text: str) -> str | None:
    if not text:
        return None
    for lang in ("en", "fa"):
        if text == t(lang, "btn_create_folder"): return "create_folder"
        if text == t(lang, "btn_continue_folder"): return "continue_folder"
        if text == t(lang, "btn_send_receipts"): return "send_receipts"
        if text == t(lang, "btn_accounting"): return "accounting"
        if text == t(lang, "btn_admin_panel"): return "admin_panel"
    return None


@router.message(Command("create", "continue", "send", "accounting", "admins", "menu"))
async def cmd_nav(msg: Message, state: FSMContext) -> None:
    if not msg.text:
        return
    cmd = msg.text.split()[0].split("@")[0] # e.g. "/create"
    action_map = {
        "/create": "create_folder",
        "/continue": "continue_folder",
        "/send": "send_receipts",
        "/accounting": "accounting",
        "/admins": "admin_panel",
        "/menu": "back_to_menu",
    }
    await _handle_nav(msg, state, action_map.get(cmd))


@router.message(lambda msg: _action_from_text(msg.text) is not None)
async def text_nav(msg: Message, state: FSMContext) -> None:
    await _handle_nav(msg, state, _action_from_text(msg.text))


async def _handle_nav(msg: Message, state: FSMContext, action: str | None) -> None:
    if not action:
        return
    uid = msg.from_user.id
    lang = await _lang(state, uid)

    if action == "back_to_menu":
        await _show_main_menu(msg, state, uid)
        return

    if not is_allowed(uid):
        await msg.answer(t(lang, "access_denied"))
        return

    if not has_feature(uid, action):
        await msg.answer(t(lang, "feature_denied"))
        return

    await state.clear()
    await state.update_data(lang=lang)

    if action == "create_folder":
        await state.set_state(FolderNew.waiting_name)
        await msg.answer(t(lang, "ask_folder_name"))

    elif action == "continue_folder":
        folders = storage.list_folders(uid)
        if not folders:
            await msg.answer(t(lang, "no_folders"))
            return
        await state.set_state(FolderPick.picking)
        await state.update_data(pick_mode="continue", lang=lang)
        await msg.answer(
            t(lang, "select_folder"),
            reply_markup=kb_folders(folders, "continue", lang),
        )

    elif action == "send_receipts":
        folders = storage.list_folders(uid)
        if not folders:
            await msg.answer(t(lang, "no_folders"))
            return
        await state.set_state(FolderPick.picking)
        await state.update_data(pick_mode="send", lang=lang)
        await msg.answer(
            t(lang, "select_folder"),
            reply_markup=kb_folders(folders, "send", lang),
        )

    elif action == "accounting":
        folders = storage.list_folders(uid)
        if not folders:
            await msg.answer(t(lang, "no_folders"))
            return
        await state.set_state(FolderPick.picking)
        await state.update_data(pick_mode="accounting", lang=lang)
        await msg.answer(
            t(lang, "select_folder"),
            reply_markup=kb_folders(folders, "accounting", lang),
        )

    elif action == "admin_panel":
        await state.set_state(AdminPanel.picking_admin)
        await state.update_data(lang=lang)
        await msg.answer(
            t(lang, "admin_panel_pick_admin"),
            reply_markup=kb_admins(lang),
        )


# ===========================================================================
# Folder creation
# ===========================================================================

@router.message(FolderNew.waiting_name)
async def msg_folder_name(msg: Message, state: FSMContext) -> None:
    uid  = msg.from_user.id
    lang = await _lang(state, uid)

    if not has_feature(uid, "create_folder"):
        await msg.answer(t(lang, "feature_denied"))
        return

    name = msg.text.strip()
    if not storage.create_folder(uid, name):
        await msg.answer(t(lang, "folder_exists"))
        return

    storage.set_active_folder(uid, name)
    await state.update_data(active_folder=name)
    await state.set_state(Collect.s1_customer)
    await msg.answer(t(lang, "folder_created", name=name), parse_mode="Markdown")
    await msg.answer(t(lang, "step1"), parse_mode="Markdown")


# ===========================================================================
# Folder picker
# ===========================================================================

@router.callback_query(FolderPick.picking, F.data.startswith("continue:"))
@interaction_lock
async def cb_pick_continue(cb: CallbackQuery, state: FSMContext) -> None:
    uid    = cb.from_user.id
    lang   = await _lang(state, uid)
    folder = cb.data.split(":", 1)[1]

    if not has_feature(uid, "continue_folder"):
        await cb.message.answer(t(lang, "feature_denied"))
        return

    storage.set_active_folder(uid, folder)
    await state.update_data(active_folder=folder)
    await state.set_state(Collect.s1_customer)
    await cb.message.answer(t(lang, "folder_resumed", name=folder), parse_mode="Markdown")
    await cb.message.answer(t(lang, "step1"), parse_mode="Markdown")


@router.callback_query(FolderPick.picking, F.data.startswith("send:"))
@interaction_lock
async def cb_pick_send(cb: CallbackQuery, state: FSMContext) -> None:
    uid    = cb.from_user.id
    lang   = await _lang(state, uid)
    folder = cb.data.split(":", 1)[1]

    if not has_feature(uid, "send_receipts"):
        await cb.message.answer(t(lang, "feature_denied"))
        return

    await state.update_data(active_folder=folder)
    await state.set_state(SendMode.picking)
    await cb.message.answer(
        t(lang, "send_mode_prompt"),
        reply_markup=kb_send_mode(lang),
    )


@router.callback_query(FolderPick.picking, F.data.startswith("accounting:"))
@interaction_lock
async def cb_pick_accounting(cb: CallbackQuery, state: FSMContext) -> None:
    uid    = cb.from_user.id
    lang   = await _lang(state, uid)
    folder = cb.data.split(":", 1)[1]

    if not has_feature(uid, "accounting"):
        await cb.message.answer(t(lang, "feature_denied"))
        return

    await state.update_data(active_folder=folder)
    await state.set_state(Accounting.picking_type)
    await cb.message.answer(
        t(lang, "accounting_options"),
        reply_markup=kb_accounting(lang),
    )


# ===========================================================================
# Send Receipts — mode selection → output
# ===========================================================================

@router.callback_query(SendMode.picking, F.data.startswith("sendmode:"))
@interaction_lock
async def cb_send_mode(cb: CallbackQuery, state: FSMContext) -> None:
    uid    = cb.from_user.id
    lang   = await _lang(state, uid)
    mode   = cb.data.split(":")[1]      # "time_only" | "full_report"
    data   = await state.get_data()
    folder = data.get("active_folder", "")

    if not has_feature(uid, "send_receipts"):
        await cb.message.answer(t(lang, "feature_denied"))
        return

    receipts = storage.load_receipts(uid, folder)
    if not receipts:
        await cb.message.answer(t(lang, "no_receipts"))
        return

    # Sort ascending by HH:MM
    sorted_r = sorted(receipts, key=lambda r: r.get("time", ""))

    await cb.message.delete()

    if mode == "time_only":
        await _send_time_only(cb.message, uid, folder, sorted_r)
    else:
        await _send_full_report(cb.message, uid, folder, sorted_r, lang)

    # ── Stay on result screen. Show only BACK. User navigates manually. ──────
    await cb.message.answer(t(lang, "send_done"), reply_markup=kb_back_to_menu(lang))


async def _send_time_only(
    msg: Message,
    uid: int,
    folder: str,
    receipts: list[dict],
) -> None:
    """
    STRICT TIME-ONLY MODE:
    - Image receipt → send image; caption = HH:MM only (nothing else)
    - Text receipt  → send original text; append HH:MM on its own line at end
    No customer, no amount, no volume, no admin, no labels — strictly time.
    """
    for r in receipts:
        time_str = r.get("time", "")

        if r.get("receipt_type") == "image":
            img = storage.get_receipt_image(uid, folder, r["index"])
            if img:
                await msg.answer_photo(
                    FSInputFile(img),
                    caption=time_str,      # ← HH:MM only
                )
            else:
                # Image file missing on disk — send time string as fallback
                await msg.answer(time_str)
        else:
            receipt_text = r.get("receipt_text", "")
            if receipt_text:
                # Original text + HH:MM at the very end
                await msg.answer(f"{receipt_text}\n{time_str}")
            else:
                await msg.answer(time_str)


async def _send_full_report(
    msg: Message,
    uid: int,
    folder: str,
    receipts: list[dict],
    lang: str,
) -> None:
    """Full structured report with all fields and images."""
    for i, r in enumerate(receipts, 1):
        header = t(lang, "receipt_header", folder=folder, index=i)
        body = (
            f"\n{t(lang,'summary_customer')}: {r.get('customer','')}\n"
            f"{t(lang,'summary_amount')}: {_fmt(r.get('amount',''))}\n"
            f"{t(lang,'summary_volume')}: {r.get('volume','')} GB\n"
            f"{t(lang,'summary_time')}: {r.get('time','')}\n"
            f"{t(lang,'summary_admin')}: {r.get('admin','')}"
        )
        text = f"{header}{body}"

        if r.get("receipt_type") == "image":
            img = storage.get_receipt_image(uid, folder, r["index"])
            if img:
                await msg.answer_photo(FSInputFile(img), caption=text, parse_mode="Markdown")
            else:
                await msg.answer(text, parse_mode="Markdown")
        else:
            receipt_text = r.get("receipt_text", "")
            if receipt_text:
                text += f"\n{t(lang,'summary_receipt')}: {receipt_text}"
            await msg.answer(text, parse_mode="Markdown")


# ===========================================================================
# Accounting
# ===========================================================================

@router.callback_query(Accounting.picking_type, F.data.startswith("acct:"))
@interaction_lock
async def cb_acct(cb: CallbackQuery, state: FSMContext) -> None:
    uid    = cb.from_user.id
    lang   = await _lang(state, uid)
    rtype  = cb.data.split(":")[1]
    data   = await state.get_data()
    folder = data.get("active_folder", "")

    if not has_feature(uid, "accounting"):
        await cb.message.answer(t(lang, "feature_denied"))
        return

    if rtype == "volume":
        vol = storage.total_volume(uid, folder)
        result = t(lang, "accounting_volume", volume=int(vol))
    else:
        amt = storage.total_amount(uid, folder)
        result = t(lang, "accounting_amount", amount=_fmt(int(amt)))

    # Show result + BACK button — no auto-redirect
    await cb.message.answer(
        result,
        parse_mode="Markdown",
        reply_markup=kb_back_to_menu(lang),
    )


# ===========================================================================
# Admin Panel
# ===========================================================================

@router.callback_query(AdminPanel.picking_admin, F.data.startswith("admin_pick:"))
@interaction_lock
async def cb_admin_pick(cb: CallbackQuery, state: FSMContext) -> None:
    uid  = cb.from_user.id
    lang = await _lang(state, uid)

    if not has_feature(uid, "admin_panel"):
        await cb.message.answer(t(lang, "feature_denied"))
        return

    parts = cb.data.split(":", 2)
    admin_name = parts[2] if len(parts) == 3 else parts[1]

    folders = storage.list_folders(uid)
    if not folders:
        await cb.message.answer(t(lang, "no_folders"))
        return

    await state.update_data(admin_panel_admin=admin_name)
    await state.set_state(AdminPanel.picking_folder)
    await cb.message.answer(
        t(lang, "admin_panel_pick_folder", admin=admin_name),
        reply_markup=kb_folders(folders, "admin_folder", lang),
        parse_mode="Markdown",
    )


@router.callback_query(AdminPanel.picking_folder, F.data.startswith("admin_folder:"))
@interaction_lock
async def cb_admin_folder(cb: CallbackQuery, state: FSMContext) -> None:
    uid    = cb.from_user.id
    lang   = await _lang(state, uid)
    folder = cb.data.split(":", 1)[1]
    data   = await state.get_data()
    admin  = data.get("admin_panel_admin", "")

    if not has_feature(uid, "admin_panel"):
        await cb.message.answer(t(lang, "feature_denied"))
        return

    vol, count = storage.volume_by_admin(uid, folder, admin)
    result = t(lang, "admin_panel_result",
               admin=admin, folder=folder, volume=int(vol), count=count)

    # Show result + BACK button — no auto-redirect
    await cb.message.answer(
        result,
        parse_mode="Markdown",
        reply_markup=kb_back_to_menu(lang),
    )


# ===========================================================================
# Receipt collection — 7 steps
# ===========================================================================

@router.message(Collect.s1_customer)
async def s1_customer(msg: Message, state: FSMContext) -> None:
    uid  = msg.from_user.id
    lang = await _lang(state, uid)
    await state.update_data(customer=msg.text.strip())
    await state.set_state(Collect.s2_amount)
    await msg.answer(t(lang, "step2"), parse_mode="Markdown")


@router.message(Collect.s2_amount)
async def s2_amount(msg: Message, state: FSMContext) -> None:
    uid  = msg.from_user.id
    lang = await _lang(state, uid)
    raw  = msg.text.strip().replace(",", "").replace(".", "")
    if not raw.isdigit():
        await msg.answer(t(lang, "invalid_amount"))
        return
    await state.update_data(amount=raw)
    await state.set_state(Collect.s3_volume)
    await msg.answer(t(lang, "step3"), parse_mode="Markdown")


@router.message(Collect.s3_volume)
async def s3_volume(msg: Message, state: FSMContext) -> None:
    uid  = msg.from_user.id
    lang = await _lang(state, uid)
    raw  = msg.text.strip()
    if not raw.replace(".", "").isdigit():
        await msg.answer(t(lang, "invalid_volume"))
        return
    await state.update_data(volume=raw)
    await state.set_state(Collect.s4_time)
    await msg.answer(t(lang, "step4"), parse_mode="Markdown")


@router.message(Collect.s4_time)
async def s4_time(msg: Message, state: FSMContext) -> None:
    uid  = msg.from_user.id
    lang = await _lang(state, uid)
    if not _valid_time(msg.text):
        await msg.answer(t(lang, "invalid_time"))
        return
    await state.update_data(time=msg.text.strip())
    await state.set_state(Collect.s5_admin)
    await msg.answer(t(lang, "step5"), reply_markup=kb_admin_select(lang), parse_mode="Markdown")


@router.callback_query(Collect.s5_admin, F.data.startswith("s5_admin:"))
@interaction_lock
async def cb_s5_admin(cb: CallbackQuery, state: FSMContext) -> None:
    uid  = cb.from_user.id
    lang = await _lang(state, uid)
    await state.update_data(admin=cb.data.split(":", 1)[1])
    await state.set_state(Collect.s6_receipt)
    await cb.message.answer(t(lang, "step6"), parse_mode="Markdown")


@router.message(Collect.s5_admin)
async def s5_blocked(msg: Message, state: FSMContext) -> None:
    uid  = msg.from_user.id
    lang = await _lang(state, uid)
    await msg.answer(t(lang, "admin_only_buttons"), reply_markup=kb_admin_select(lang))


@router.message(Collect.s6_receipt, F.photo)
async def s6_photo(msg: Message, state: FSMContext) -> None:
    uid  = msg.from_user.id
    lang = await _lang(state, uid)
    best: PhotoSize = msg.photo[-1]
    await state.update_data(receipt_type="image", receipt_file_id=best.file_id, receipt_text="")
    await _show_confirm(msg, state, lang)


@router.message(Collect.s6_receipt, F.text)
async def s6_text(msg: Message, state: FSMContext) -> None:
    uid  = msg.from_user.id
    lang = await _lang(state, uid)
    await state.update_data(receipt_type="text", receipt_text=msg.text.strip(), receipt_file_id=None)
    await _show_confirm(msg, state, lang)


async def _show_confirm(msg: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Collect.s7_confirm)
    d = await state.get_data()
    await msg.answer(
        f"{t(lang,'step7')}\n\n{_summary(d, lang)}",
        reply_markup=kb_confirm(lang),
        parse_mode="Markdown",
    )


@router.callback_query(Collect.s7_confirm, F.data == "confirm:yes")
@interaction_lock
async def cb_confirm_yes(cb: CallbackQuery, state: FSMContext) -> None:
    uid  = cb.from_user.id
    lang = await _lang(state, uid)
    d    = await state.get_data()
    folder = d.get("active_folder", "")

    image_bytes: bytes | None = None
    if d.get("receipt_type") == "image" and d.get("receipt_file_id"):
        try:
            file = await cb.bot.get_file(d["receipt_file_id"])
            bio  = await cb.bot.download_file(file.file_path)
            image_bytes = bio.read() if hasattr(bio, "read") else bio
        except Exception as exc:
            logger.warning("Image download failed: %s", exc)

    storage.save_receipt(uid, folder, d, image_bytes)
    await state.set_state(Collect.after_save)
    await cb.message.answer(t(lang, "receipt_saved"))
    await cb.message.answer(t(lang, "ask_continue_or_finish"), reply_markup=kb_after_save(lang))


@router.callback_query(Collect.s7_confirm, F.data == "confirm:edit")
@interaction_lock
async def cb_confirm_edit(cb: CallbackQuery, state: FSMContext) -> None:
    uid  = cb.from_user.id
    lang = await _lang(state, uid)
    await state.set_state(Collect.edit_pick)
    await cb.message.answer(t(lang, "edit_pick_field"), reply_markup=kb_edit_fields(lang))


@router.callback_query(Collect.edit_pick, F.data.startswith("ef:"))
@interaction_lock
async def cb_edit_pick(cb: CallbackQuery, state: FSMContext) -> None:
    uid   = cb.from_user.id
    lang  = await _lang(state, uid)
    field = cb.data.split(":")[1]
    await state.update_data(editing_field=field)
    await state.set_state(Collect.edit_value)
    step_map = {
        "customer": "step1", "amount": "step2", "volume": "step3",
        "time":     "step4", "admin":  "step5", "receipt": "step6",
    }
    prompt = t(lang, step_map.get(field, "step1"))
    if field == "admin":
        await cb.message.answer(prompt, reply_markup=kb_admin_select(lang), parse_mode="Markdown")
    else:
        await cb.message.answer(prompt, parse_mode="Markdown")


@router.callback_query(Collect.edit_value, F.data.startswith("s5_admin:"))
@interaction_lock
async def cb_edit_admin(cb: CallbackQuery, state: FSMContext) -> None:
    uid  = cb.from_user.id
    lang = await _lang(state, uid)
    await state.update_data(admin=cb.data.split(":", 1)[1])
    await _return_to_confirm(cb.message, state, lang)


@router.message(Collect.edit_value, F.photo)
async def edit_photo(msg: Message, state: FSMContext) -> None:
    uid  = msg.from_user.id
    lang = await _lang(state, uid)
    d    = await state.get_data()
    if d.get("editing_field") == "receipt":
        best: PhotoSize = msg.photo[-1]
        await state.update_data(receipt_type="image", receipt_file_id=best.file_id, receipt_text="")
    await _return_to_confirm(msg, state, lang)


@router.message(Collect.edit_value, F.text)
async def edit_text_val(msg: Message, state: FSMContext) -> None:
    uid   = msg.from_user.id
    lang  = await _lang(state, uid)
    d     = await state.get_data()
    field = d.get("editing_field", "")
    val   = msg.text.strip()

    if field == "customer":
        await state.update_data(customer=val)
    elif field == "amount":
        raw = val.replace(",", "").replace(".", "")
        if not raw.isdigit():
            await msg.answer(t(lang, "invalid_amount"))
            return
        await state.update_data(amount=raw)
    elif field == "volume":
        if not val.replace(".", "").isdigit():
            await msg.answer(t(lang, "invalid_volume"))
            return
        await state.update_data(volume=val)
    elif field == "time":
        if not _valid_time(val):
            await msg.answer(t(lang, "invalid_time"))
            return
        await state.update_data(time=val)
    elif field == "receipt":
        await state.update_data(receipt_type="text", receipt_text=val, receipt_file_id=None)

    await _return_to_confirm(msg, state, lang)


async def _return_to_confirm(msg: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Collect.s7_confirm)
    d = await state.get_data()
    await msg.answer(
        f"{t(lang,'step7')}\n\n{_summary(d, lang)}",
        reply_markup=kb_confirm(lang),
        parse_mode="Markdown",
    )


@router.callback_query(Collect.after_save, F.data.startswith("after:"))
@interaction_lock
async def cb_after_save(cb: CallbackQuery, state: FSMContext) -> None:
    uid    = cb.from_user.id
    lang   = await _lang(state, uid)
    action = cb.data.split(":")[1]

    if action == "continue":
        await state.set_state(Collect.s1_customer)
        await cb.message.answer(t(lang, "step1"), parse_mode="Markdown")
    else:
        # Finish — show saved confirmation + BACK button. No auto-redirect.
        await cb.message.answer(
            t(lang, "session_finished"),
            parse_mode="Markdown",
            reply_markup=kb_back_to_menu(lang),
        )


# ===========================================================================
# Catch-all fallback
# ===========================================================================

@router.message()
async def fallback(msg: Message, state: FSMContext) -> None:
    uid = msg.from_user.id
    if not is_allowed(uid):
        await msg.answer(t("en", "access_denied"))
        return
    lang = await _lang(state, uid)
    await msg.answer(t(lang, "unknown_command"))
