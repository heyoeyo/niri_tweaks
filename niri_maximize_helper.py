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
    "-r", "--expel_right", action="store_true", help="Expel stacked widows to the right, instead of left"
)
parser.add_argument(
    "-t",
    "--max_threshold",
    type=float,
    default=0.8,
    help="Threshold used to determine if a window is 'big enough' to be considered maximized",
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
    "-p",
    "--folder_path",
    type=str,
    default="/tmp/niri_maximize_helper",
    help="Folder path used to store window state restoration data (default: '/tmp/niri_maximize_helper')",
)

# For convenience
args = parser.parse_args()
EXPEL_LEFT = not args.expel_right
MAX_ACTION = args.action
MAX_THRESHOLD = args.max_threshold
ENABLE_STACK_RESTORE = not args.disable_restore
ENABLE_VIEW_REALIGN = not args.disable_realign
ENABLE_BREAK_FULLSCREEN = not args.disable_break_fullscreen
STATE_FOLDER_PATH = Path(args.folder_path)


# ---------------------------------------------------------------------------------------------------------------------
# %% Helpers


def run_command(command_str: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command_str.split(" "), **kwargs)


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
    state_folder: Path, window_id: int, is_floating: bool, column_row_index: tuple[int, int], column_count: int
) -> None:
    """Helper used to record window state when 'un-maximizing' from a stacked column"""
    state_folder.mkdir(exist_ok=True)
    tmp_file = state_folder / f"{window_id}.state"
    with open(tmp_file, "w") as outfile:
        json.dump([is_floating, column_row_index, column_count], outfile, separators=(",", ":"))
    return


def read_prior_window_data(state_folder: Path, window_id: int) -> tuple[bool, tuple[int, int], int]:
    """If previously in stacked column, reads prior state. Returns: is_floating, column_row_index, column_count"""
    is_floating, column_row_index, column_count = False, (0, 0), 0
    tmp_file = state_folder / f"{window_id}.state"
    if tmp_file.exists():
        with open(tmp_file, "r") as infile:
            is_floating, column_row_index, column_count = json.load(infile)
        tmp_file.unlink()
    return is_floating, column_row_index, column_count


def get_col_idx(window_info: dict) -> int:
    """Simpler helper to get window column indexing, if possible"""
    colrow = window_info["layout"]["pos_in_scrolling_layout"]
    return colrow[0] if colrow is not None else -1


# ---------------------------------------------------------------------------------------------------------------------
# %% Main code

# Get target window info (or bail if none)
curr_win_info = get_focused_window()
if curr_win_info is None:
    raise SystemExit()
curr_win_id = curr_win_info["id"]
curr_ws_id = curr_win_info["workspace_id"]

# Handle special floating window case
curr_is_floating = curr_win_info["is_floating"]
if curr_is_floating:
    run_command("niri msg action toggle-window-floating")
    run_command(f"niri msg action {MAX_ACTION}")
    record_window_data(STATE_FOLDER_PATH, curr_win_id, curr_is_floating, (0, 0), 0)
    raise SystemExit()

# Figure out the monitor size of the current workspace
all_ws_info = {info["id"]: info for info in get_all_workspaces_info()}
all_monitor_info = get_all_monitor_info()
curr_ws_info = all_ws_info[curr_ws_id]
curr_monitor_info = all_monitor_info[curr_ws_info["output"]]
curr_monitor_w, curr_monitor_h = curr_monitor_info["logical"]["width"], curr_monitor_info["logical"]["height"]

# Get all tiled windows on workspace containing focused window
all_win_info = get_all_windows_info()
all_ws_win_info = (info for info in all_win_info if info["workspace_id"] == curr_ws_id)
tile_win_info = [info for info in all_ws_win_info if not info["is_floating"]]

# Figure out if we're in the target maximized state
# -> (as of 26.04) fullscreen state is independent of maximized state, but we can't distinguish either using IPC
curr_win_w, curr_win_h = curr_win_info["layout"]["window_size"]
w_gap_px, h_gap_px = (curr_monitor_w - curr_win_w), (curr_monitor_h - curr_win_h)
is_fullscreen, in_target_max_state = False, False
if (w_gap_px < 5) and (h_gap_px < 5):
    is_fullscreen = True
    in_target_max_state = MAX_ACTION == "fullscreen-window"
elif (w_gap_px < 5) or (h_gap_px < 5):
    in_target_max_state = MAX_ACTION == "maximize-window-to-edges"
elif (curr_win_w / curr_monitor_w) > MAX_THRESHOLD:
    in_target_max_state = MAX_ACTION == "maximize-column"

# Special feature, break fullscreen state using other max actions
# -> Normally these toggle 'underneath' the fullscreen state, which seems unintuitive...
if ENABLE_BREAK_FULLSCREEN and MAX_ACTION != "fullscreen-window" and is_fullscreen:
    run_command("niri msg action fullscreen-window")
    raise SystemExit()

# Handle un-maxmization
curr_colrow = curr_win_info["layout"]["pos_in_scrolling_layout"]
prev_is_floating, prev_colrow, prev_col_count = read_prior_window_data(STATE_FOLDER_PATH, curr_win_id)
if in_target_max_state:

    # Handle various 'un-maximize' cases
    need_stack_restored = False
    if prev_is_floating:
        run_command("niri msg action toggle-window-floating")

    elif prev_col_count > 1 and ENABLE_STACK_RESTORE:

        # Un-maximize
        run_command(f"niri msg action {MAX_ACTION}")

        # For convenience
        expel_idx_offset = 1 if EXPEL_LEFT else 0
        prev_col_idx, prev_row_idx = prev_colrow
        expected_col_count = prev_col_count - 1
        expected_adj_col_idx = prev_col_idx + (1 if EXPEL_LEFT else 0)

        # If adjacent window count matches previous state, try to move window back into column/row position
        adjacent_col_idx = curr_colrow[0] + (1 if EXPEL_LEFT else -1)
        adjacent_col_count = len([info for info in tile_win_info if get_col_idx(info) == adjacent_col_idx])
        need_stack_restored = adjacent_col_count == expected_col_count and adjacent_col_idx == expected_adj_col_idx
        if need_stack_restored:
            expel_cmd = f"consume-or-expel-window-{'right' if EXPEL_LEFT else 'left'}"
            run_command(f"niri msg action {expel_cmd}")
            num_move_up = max((adjacent_col_count + 1) - prev_row_idx, 0)
            for _ in range(num_move_up):
                run_command("niri msg action move-window-up")
            pass

    else:
        # Case where window was already alone, just toggle max state
        run_command(f"niri msg action {MAX_ACTION}")

    # Special check. If the window ends up as the last column, force re-align to get rid of empty space on right
    if ENABLE_VIEW_REALIGN and not prev_is_floating:

        # Figure out if the window is now in the last-most column
        last_col_idx = max([get_col_idx(info) for info in tile_win_info], default=1)
        curr_col_idx = curr_colrow[0]
        if need_stack_restored:
            last_col_idx -= 1
            curr_col_idx -= 0 if EXPEL_LEFT else 1
        is_unmaxed_in_last_col = curr_col_idx == last_col_idx

        # Toggle focus to force niri to right-align the window
        if is_unmaxed_in_last_col and curr_col_idx > 1:
            run_command("niri msg action focus-column-first")
            run_command(f"niri msg action focus-window --id {curr_win_id}")
        pass

else:
    # Maximization case. Move window out of shared column first, if needed
    curr_col_count = len([info for info in tile_win_info if get_col_idx(info) == curr_colrow[0]])
    if curr_col_count > 1:
        expel_cmd = f"consume-or-expel-window-{'left' if EXPEL_LEFT else 'right'}"
        run_command(f"niri msg action {expel_cmd}")
        record_window_data(STATE_FOLDER_PATH, curr_win_id, curr_is_floating, curr_colrow, curr_col_count)
    run_command(f"niri msg action {MAX_ACTION}")
