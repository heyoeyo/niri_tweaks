#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# ---------------------------------------------------------------------------------------------------------------------
# %% Imports

import argparse
import subprocess
import json

# ---------------------------------------------------------------------------------------------------------------------
# %% Handle script args

# Handle target workspace arg
parser = argparse.ArgumentParser(description="Unstack (expel) all stacked windows")
parser.add_argument(
    "-l",
    "--unstack_left",
    action="store_true",
    help="If enabled, unstack to the left when removing windows from a column (default: unstack to the right)",
)
parser.add_argument(
    "-r",
    "--row_height",
    nargs="?",  # means: 0 or 1 arg
    type=float,
    default=-1,
    help="Set with a value to adjust every window height. Set with no value to reset window heights",
)
parser.add_argument(
    "-c",
    "--column_width",
    nargs="?",
    type=float,
    default=-1,
    help="Set with a value to adjust every window width. Set with no value to cycle preset column widths",
)

# For convenience
args = parser.parse_args()
UNSTACK_LEFT = args.unstack_left
ARG_COLUMN_WIDTH = args.column_width
ARG_ROW_HEIGHT = args.row_height

# Handle variable inputs
CYCLE_COLUMN_WIDTH = ARG_COLUMN_WIDTH is None
SET_COLUMN_WIDTH = (not CYCLE_COLUMN_WIDTH) and (ARG_COLUMN_WIDTH > 0)
RESET_ROW_HEIGHT = ARG_ROW_HEIGHT is None
SET_ROW_HEIGHT = (not RESET_ROW_HEIGHT) and (ARG_ROW_HEIGHT > 0)


# ---------------------------------------------------------------------------------------------------------------------
# %% Helpers


def run_command(command_str: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command_str.split(" "), **kwargs)


def get_all_workspaces_info() -> list[dict]:
    resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_all_windows_info() -> list[dict]:
    resp = run_command("niri msg --json windows", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


# ---------------------------------------------------------------------------------------------------------------------
# %% *** Main code ***

# Get current workspace id
curr_wspace_id = -1
for ws_info in get_all_workspaces_info():
    if ws_info["is_focused"]:
        curr_wspace_id = ws_info["id"]
        break

# Get info for all tiled windows
curr_win_info = (win_info for win_info in get_all_windows_info() if win_info["workspace_id"] == curr_wspace_id)
tile_win_info = [win_info for win_info in curr_win_info if not win_info["is_floating"]]

# Order windows for unstacking. Column order can be reversed but rows are always bottom-to-top
get_col_idx = lambda item: item["layout"]["pos_in_scrolling_layout"][0]
get_row_idx = lambda item: item["layout"]["pos_in_scrolling_layout"][1]
get_sort_score = lambda item: (get_col_idx(item) * (1 if UNSTACK_LEFT else -1), get_row_idx(item) * -1)
ordered_win_info = sorted(tile_win_info, key=get_sort_score)

# Iterate over windows and move them out of columns if they are on second row or lower
unstack_cmd = f"niri msg action consume-or-expel-window-{'left' if UNSTACK_LEFT else 'right'}"
for win_info in ordered_win_info:
    target_win_id = win_info["id"]
    if get_row_idx(win_info) > 1:
        run_command(f"{unstack_cmd} --id {target_win_id}")
    if RESET_ROW_HEIGHT:
        run_command(f"niri msg action reset-window-height --id {target_win_id}")
    elif SET_ROW_HEIGHT:
        run_command(f"niri msg action set-window-height --id {target_win_id} {ARG_ROW_HEIGHT}%")
    if CYCLE_COLUMN_WIDTH:
        run_command(f"niri msg action switch-preset-window-width --id {target_win_id}")
    elif SET_COLUMN_WIDTH:
        run_command(f"niri msg action set-window-width --id {target_win_id} {ARG_COLUMN_WIDTH}%")
