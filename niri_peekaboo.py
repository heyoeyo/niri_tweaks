#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import json


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle script args

parser = argparse.ArgumentParser(description="Pull nearby column into view (floating) or restore floats to column")
parser.add_argument("-x", "--fixed_size", action="store_true", help="Prevent auto resizing of floated windows")
args = parser.parse_args()
ALLOW_FLOAT_RESIZE = not args.fixed_size


# ---------------------------------------------------------------------------------------------------------------------
# %% Helpers


def run_command(command_str: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command_str.split(" "), **kwargs)


def get_windows_list() -> list[dict]:
    resp = run_command("niri msg --json windows", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_workspaces_info() -> list[dict]:
    resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_focused_window() -> dict | None:
    resp = run_command("niri msg --json focused-window", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def niri_focus_window(window_id: int):
    run_command(f"niri msg action focus-window --id {window_id}")
    return


# ---------------------------------------------------------------------------------------------------------------------
# %% Get current windowing info

# Figure out where user is looking, bail if nothing (e.g. empty workspace or overview mode)
user_win = get_focused_window()
if user_win is None:
    quit()

# Figure out what windows we have
all_win_info = get_windows_list()
wspace_win_list = [w for w in all_win_info if w["workspace_id"] == user_win["workspace_id"]]
float_win_list, nonfloat_win_list = [], []
for win_info in wspace_win_list:
    win_list = float_win_list if win_info["is_floating"] else nonfloat_win_list
    win_list.append(win_info)


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle 'need to un-float' case

# If we have floating windows, 'un-peek' them
if len(float_win_list) > 0:
    float_win_list = sorted(float_win_list, key=lambda w: w["layout"]["tile_pos_in_workspace_view"][1])
    for win_idx, target_win in enumerate(float_win_list):
        target_id = target_win["id"]
        run_command(f"niri msg action move-window-to-tiling --id {target_id}")
        # If we have more than 1 window to 'un-peek' assume we need to stack them
        if win_idx > 0:
            run_command(f"niri msg action consume-or-expel-window-right --id {target_id}")

    # Return focus to where user was looking
    if user_win["is_floating"]:
        target_unpeek_id = float_win_list[0]["id"]
        niri_focus_window(target_unpeek_id)
        run_command("niri msg action focus-column-left")
    else:
        niri_focus_window(user_win["id"])
    quit()


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle 'need to float' case

# For sanity. This shouldn't happen if we get here
if user_win["is_floating"]:
    raise RuntimeError("Unexpected error! Trying to float but user is already floating")

# Find windows to float
user_col, user_row = user_win["layout"]["pos_in_scrolling_layout"]
target_peek_col = user_col + 1
peek_win_info = [w for w in nonfloat_win_list if w["layout"]["pos_in_scrolling_layout"][0] == target_peek_col]
if len(peek_win_info) == 0:
    quit()

# Figure out y-positioning of target windows when floated
peek_win_info = sorted(peek_win_info, key=lambda w: w["layout"]["pos_in_scrolling_layout"][1])
target_float_y, csum_y = [], 0
for target_win in peek_win_info:
    target_float_y.append(csum_y)
    csum_y += target_win["layout"]["window_size"][1]

# Float target windows and move to left side of screen
max_row_idx = max(w["layout"]["pos_in_scrolling_layout"][1] for w in peek_win_info)
for win_info, target_y in zip(peek_win_info, target_float_y):
    target_id, (target_w, target_h) = win_info["id"], win_info["layout"]["window_size"]
    niri_focus_window(target_id)
    run_command("niri msg action move-window-to-floating")
    run_command(f"niri msg action move-floating-window -x 0 -y {target_y}")

    # Resize floating windows if needed
    if ALLOW_FLOAT_RESIZE:
        floated_info = get_focused_window()
        float_w, float_h = floated_info["layout"]["window_size"]
        if float_w != target_w:
            run_command(f"niri msg action set-window-width {target_w}")
        if float_h != target_h:
            run_command(f"niri msg action set-window-height {target_h}")
        pass
    pass

# Go back to focusing original window
niri_focus_window(user_win["id"])
