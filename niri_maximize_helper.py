#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# ---------------------------------------------------------------------------------------------------------------------
# %% Imports

import argparse
import subprocess
import json
from pathlib import Path

# ---------------------------------------------------------------------------------------------------------------------
# %% Handle script args

# Define script arguments
parser = argparse.ArgumentParser(description="Maximize windows directly. Handles stacking/unstacking")
parser.add_argument(
    "action",
    nargs="?",  # 0 or 1 arg
    type=str,
    default="maximize-column",
    choices=["maximize-column", "maximize-window-to-edges", "fullscreen-window"],
    help="Set which maximization action to use (default: maximize-column)",
)
parser.add_argument(
    "-r", "--expel_right", action="store_true", help="Expel stacked windows to the right instead of left"
)
parser.add_argument(
    "-d",
    "--disable_restore",
    action="store_true",
    help="If set, windows will not be restored to stacked state on un-maximizing",
)
parser.add_argument(
    "-n",
    "--disable_realign",
    action="store_true",
    help="Disables attempt to re-align the view when un-maximizing the last-most column",
)
parser.add_argument(
    "-b",
    "--disable_break_fullscreen",
    action="store_true",
    help="Disables ability to toggle out of fullscreen using other maximize actions",
)
parser.add_argument(
    "-t",
    "--max_width_threshold",
    type=float,
    default=0.8,
    help="Threshold used to determine if a window is 'wide enough' to be considered a maximized column (default: 0.8)",
)
parser.add_argument(
    "-p",
    "--folder_path",
    type=str,
    default="/tmp/niri_maximize_helper",
    help="Folder path used to store window state restoration data (default: '/tmp/niri_maximize_helper')",
)

# For convenience
args = parser.parse_args()
MAX_ACTION = args.action
EXPEL_LEFT = not args.expel_right
ENABLE_STACK_RESTORE = not args.disable_restore
ENABLE_VIEW_REALIGN = not args.disable_realign
ENABLE_BREAK_FULLSCREEN = not args.disable_break_fullscreen
MAX_WIDTH_THRESHOLD = args.max_width_threshold
STATE_FOLDER_PATH = Path(args.folder_path)


# ---------------------------------------------------------------------------------------------------------------------
# %% Helpers


def run_command(command_str: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command_str.split(" "), **kwargs)


def niri_action(action: str) -> subprocess.CompletedProcess:
    return run_command(f"niri msg action {action}")


def get_all_monitor_info() -> list[tuple[int, int]]:
    resp = run_command("niri msg --json outputs", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_all_workspaces_info() -> list[dict]:
    resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_all_windows_info() -> list[dict]:
    resp = run_command("niri msg --json windows", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_focused_window() -> dict:
    resp = run_command("niri msg --json focused-window", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def record_window_data(
    state_folder: Path,
    window_id: int,
    is_floating: bool,
    column_row_index: tuple[int, int],
    row_count: int,
    workspace_id: int,
) -> None:
    """Helper used to record window state when 'un-maximizing' from a stacked column"""
    state_folder.mkdir(exist_ok=True)
    tmp_file = state_folder / f"{window_id}.state"
    with open(tmp_file, "w") as outfile:
        json.dump([is_floating, column_row_index, row_count, workspace_id], outfile, separators=(",", ":"))
    return


def read_prior_window_data(state_folder: Path, window_id: int) -> tuple[bool, tuple[int, int], int, int]:
    """Reads prior window state. Returns: is_floating, column_row_index, row_count, workspace_id"""
    is_floating, column_row_index, row_count, workspace_id = False, (0, 0), 0, 0
    tmp_file = state_folder / f"{window_id}.state"
    if tmp_file.exists():
        try:
            with open(tmp_file, "r") as infile:
                is_floating, column_row_index, row_count, workspace_id = json.load(infile)
        finally:
            tmp_file.unlink()  # <- This means 'delete'
    return is_floating, column_row_index, row_count, workspace_id


def get_col_idx(window_info: dict) -> int:
    """Simple helper to get window column indexing. Returns -1 if no index (e.g. floating)"""
    colrow = window_info["layout"]["pos_in_scrolling_layout"]
    return colrow[0] if colrow is not None else -1


def get_maximization_state(
    window_info: dict, workspace_id: int, max_width_threshold: float = 0.8
) -> tuple[bool, bool, bool]:
    """
    Helper used to guess the maximization/fullscreen state of a window.
    Note:
        As of niri v26.04 the fullscreen state is actually independent of the
        maximization state and neither is available from the IPC
    Returns: is_fullscreen, is_max_to_edges, is_max_column (only 1 or 0 will be True)
    """

    # Figure out the monitor size of the given workspace
    all_wspace_info = {info["id"]: info for info in get_all_workspaces_info()}
    all_monitor_info = get_all_monitor_info()
    curr_ws_info = all_wspace_info[workspace_id]
    curr_monitor_info = all_monitor_info[curr_ws_info["output"]]
    curr_monitor_w, curr_monitor_h = curr_monitor_info["logical"]["width"], curr_monitor_info["logical"]["height"]

    # Figure out if we're in the target maximized state
    curr_win_w, curr_win_h = window_info["layout"]["window_size"]
    w_gap_px, h_gap_px = (curr_monitor_w - curr_win_w), (curr_monitor_h - curr_win_h)
    is_fullscreen, is_max_to_edges, is_max_column = False, False, False
    if (w_gap_px < 5) and (h_gap_px < 5):
        is_fullscreen = True
    elif (w_gap_px < 5) or (h_gap_px < 5):
        is_max_to_edges = True
    elif (curr_win_w / curr_monitor_w) > max_width_threshold:
        is_max_column = True

    return is_fullscreen, is_max_to_edges, is_max_column


# ---------------------------------------------------------------------------------------------------------------------
# %% Main code

# Get target window info (or bail if none)
curr_win_info = get_focused_window()
if curr_win_info is None:
    raise SystemExit()
curr_win_id = curr_win_info["id"]

# Bail on (impossible?) case where workspace is missing (can happen on window drag, maybe other cases...)
curr_ws_id = curr_win_info["workspace_id"]
if curr_ws_id is None:
    raise ValueError("Cannot handle window with no workspace ID!")

# Handle special floating window case
curr_is_floating = curr_win_info["is_floating"]
if curr_is_floating:
    niri_action("move-window-to-tiling")
    niri_action(MAX_ACTION)
    record_window_data(STATE_FOLDER_PATH, curr_win_id, curr_is_floating, (0, 0), 0, curr_ws_id)
    raise SystemExit()

# Figure out if the window should be considered already maximized
is_fullscreen, is_max_to_edges, is_max_column = get_maximization_state(curr_win_info, curr_ws_id, MAX_WIDTH_THRESHOLD)
is_in_target_max_state = any(
    [
        (is_fullscreen and MAX_ACTION == "fullscreen-window"),
        (is_max_to_edges and MAX_ACTION == "maximize-window-to-edges"),
        (is_max_column and MAX_ACTION == "maximize-column"),
    ]
)

# Special feature, break fullscreen state using other max actions
# -> Normally these toggle 'underneath' the fullscreen state, which seems unintuitive...
if ENABLE_BREAK_FULLSCREEN and is_fullscreen and MAX_ACTION != "fullscreen-window":
    niri_action("fullscreen-window")
    raise SystemExit()

# Handle special case of 'un-maximizing' a previously floating window
prev_is_floating, prev_colrow, prev_row_count, prev_ws_id = read_prior_window_data(STATE_FOLDER_PATH, curr_win_id)
if is_in_target_max_state and prev_is_floating:
    niri_action("move-window-to-floating")
    raise SystemExit()

# Get info for non-floating windows on the same workspace containing focused window
all_win_info = get_all_windows_info()
all_ws_win_info = (info for info in all_win_info if info["workspace_id"] == curr_ws_id)
tile_win_info = [info for info in all_ws_win_info if not info["is_floating"]]

# Handle maximization case. Move window out of shared column first, if needed
curr_colrow = curr_win_info["layout"]["pos_in_scrolling_layout"]
if not is_in_target_max_state:
    curr_row_count = len([info for info in tile_win_info if get_col_idx(info) == curr_colrow[0]])
    if curr_row_count > 1:
        niri_action("consume-or-expel-window-left" if EXPEL_LEFT else "consume-or-expel-window-right")
        record_window_data(STATE_FOLDER_PATH, curr_win_id, curr_is_floating, curr_colrow, curr_row_count, curr_ws_id)
    niri_action(MAX_ACTION)
    raise SystemExit()

# If we're here, we need to handle un-maximize & potential re-stacking into a column
need_stack_restored = False
niri_action(MAX_ACTION)
if ENABLE_STACK_RESTORE and prev_row_count > 1 and prev_ws_id == curr_ws_id:

    # For convenience
    prev_col_idx, prev_row_idx = prev_colrow
    expected_col_idx = prev_col_idx + (1 if EXPEL_LEFT else 0)
    expected_row_count = prev_row_count - 1

    # Re-position window if column index and row count match previous state
    adjacent_col_idx = curr_colrow[0] + (1 if EXPEL_LEFT else -1)
    adjacent_row_count = len([info for info in tile_win_info if get_col_idx(info) == adjacent_col_idx])
    need_stack_restored = (adjacent_col_idx == expected_col_idx) and (adjacent_row_count == expected_row_count)
    if need_stack_restored:
        niri_action("consume-or-expel-window-right" if EXPEL_LEFT else "consume-or-expel-window-left")
        num_move_up = (adjacent_row_count + 1) - prev_row_idx
        for _ in range(num_move_up):
            niri_action("move-window-up")
        pass
    pass

# Special check. If the window ends up as the last column, force re-align to get rid of empty space on right
if ENABLE_VIEW_REALIGN:

    # Figure out if the window is now in the last-most column
    last_col_idx = max([get_col_idx(info) for info in tile_win_info], default=1)
    curr_col_idx = curr_colrow[0]
    if need_stack_restored:
        last_col_idx -= 1
        curr_col_idx -= 0 if EXPEL_LEFT else 1
    is_unmaxed_in_last_col = curr_col_idx == last_col_idx

    # Toggle focus to force niri to right-align the window
    if is_unmaxed_in_last_col and curr_col_idx > 1:
        niri_action("focus-column-first")
        niri_action(f"focus-window --id {curr_win_id}")
    pass
