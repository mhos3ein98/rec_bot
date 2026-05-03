# =============================================================================
# state.py
# All FSM state groups used by aiogram.
# Each group represents a distinct phase of the conversation.
# =============================================================================

from aiogram.fsm.state import State, StatesGroup


class LangSelect(StatesGroup):
    """One-time language selection on very first /start."""
    choosing = State()


class Menu(StatesGroup):
    """Main menu — idle between actions."""
    idle = State()


class FolderNew(StatesGroup):
    """User is typing a new folder name."""
    waiting_name = State()


class FolderPick(StatesGroup):
    """
    Generic folder picker used by multiple features.
    `mode` stored in FSM data: "continue" | "send" | "accounting" | "admin_folder"
    """
    picking = State()


class SendMode(StatesGroup):
    """User is choosing send mode: time-only vs full report."""
    picking = State()


class Accounting(StatesGroup):
    """User chose a folder and is picking accounting report type."""
    picking_type = State()


class AdminPanel(StatesGroup):
    """Admin panel flow: pick admin → pick folder → show result."""
    picking_admin  = State()
    picking_folder = State()


class Collect(StatesGroup):
    """Seven-step receipt collection."""
    s1_customer  = State()
    s2_amount    = State()
    s3_volume    = State()
    s4_time      = State()
    s5_admin     = State()
    s6_receipt   = State()
    s7_confirm   = State()
    edit_pick    = State()   # choose which field to edit
    edit_value   = State()   # re-enter the chosen field
    after_save   = State()   # continue or finish
