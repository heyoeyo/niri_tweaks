#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import json


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle script args

parser = argparse.ArgumentParser(description="Pull nearby column into view (floating) or restore floats to column")
parser.add_argument("-l", "--peek_left", action="store_true", help="Peek from left column (default: peak from right)")
parser.add_argument("-f", "--focus_peeked", action="store_true", help="Focus peeked window (default: focus tiling)")
parser.add_argument(
    "-b", "--both_sides", action="store_true", help="Check both sides when peeking (*side not preserved on un-peek*)"
)
parser.add_argument("-n", "--no_resize", action="store_true", help="Disable auto resizing of floated windows")
parser.add_argument("-x", "--float_x", type=int, default=0, help="x-position of floated windows (default 0)")
parser.add_argument("-y", "--float_y", type=int, default=0, help="y-position of first floated window (default 0)")
parser.add_argument("-g", "--y_gap", type=int, default=0, help="y-gap between multi-floated windows (default 0)")
parser.add_argument(
    "-w", "--max_width_norm", type=float, default=-1, help="Max width of floated windows (value between 0 and 1)"
)
parser.add_argument(
    "-t",
    "--toggle_fullscreen",
    action="store_true",
    help="Toggle fullscreen mode on use. Only enable if intending to use from true fullscreen mode, to make floats visible",
)

# For convenience
args = parser.parse_args()
PEEK_RIGHT = not args.peek_left
FOCUS_PEEKED = args.focus_peeked
ALLOW_FLOAT_RESIZE = not args.no_resize
TARGET_FLOAT_X = args.float_x
TARGET_FLOAT_Y_OFFSET = args.float_y
FLOAT_Y_GAP = args.y_gap
MAX_RESIZE_WIDTH = args.max_width_norm
LIMIT_MAX_WIDTH = MAX_RESIZE_WIDTH > 0
PEEK_BOTHSIDES = args.both_sides
TOGGLE_FULLSCREEN = args.toggle_fullscreen


# ---------------------------------------------------------------------------------------------------------------------
# %% Helpers


def run_command(command_str: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command_str.split(" "), **kwargs)


def get_windows_list() -> list[dict]:
    resp = run_command("niri msg --json windows", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_focused_monitor_info() -> dict:
    resp = run_command("niri msg --json focused-output", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_focused_window() -> dict | None:
    resp = run_command("niri msg --json focused-window", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def niri_focus_window(window_id: int) -> None:
    run_command(f"niri msg action focus-window --id {window_id}")
    return


def niri_action(command: str) -> None:
    run_command(f"niri msg action {command}")
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

# Get monitor size, if possible (not sure if this can fail)
monitor_info = get_focused_monitor_info()
monitor_w = monitor_info.get("logical", {}).get("width", 1920)
monitor_h = monitor_info.get("logical", {}).get("height", 1080)
monitor_area = monitor_w * monitor_h

# Try to figure out if window is fullscreen (IPC doesn't give this info...?) and toggle out
if TOGGLE_FULLSCREEN:
    user_win_w, user_win_h = user_win["layout"]["window_size"]
    user_win_area = user_win_w * user_win_h
    user_win_area_norm = user_win_area / monitor_area
    is_fullscreen = user_win_area_norm > 0.99

    # Switch to maximized state to mimic fullscreen while allowing floats
    if is_fullscreen:
        niri_action("fullscreen-window")  # Confusing: this is a toggle *out* of fullscreen

        # Make sure we're in a maximized state (not indicated by IPC...?) to mimic fullscreen
        user_win = get_focused_window()
        user_win_w, user_win_h = user_win["layout"]["window_size"]
        user_win_area = user_win_w * user_win_h
        user_win_area_norm = user_win_area / monitor_area
        is_maximized = user_win_area_norm > 0.75
        if not is_maximized:
            niri_action("maximize-column")
        pass


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle 'need to un-peek' case

# If we have floating windows, 'un-peek' them
if len(float_win_list) > 0:

    # Make sure focus is where the user is looking, not on floats
    if user_win["is_floating"]:
        niri_action("focus-tiling")

    # Try to stack floats into column while preserving vertical order
    float_win_list = sorted(float_win_list, key=lambda w: w["layout"]["tile_pos_in_workspace_view"][1])
    for win_idx, target_win in enumerate(float_win_list):
        target_id = target_win["id"]
        niri_action(f"move-window-to-tiling --id {target_id}")
        # Strange looking: used to stack multiple floats into 1 column
        if win_idx > 0:
            niri_action(f"consume-or-expel-window-right --id {target_id}")

    # Move un-peeked column to left side if needed
    if not PEEK_RIGHT:
        niri_action("move-column-right")

    # Fullscreen user if needed (used to undo the move to max/non-fullscreen needed for floating windows)
    if TOGGLE_FULLSCREEN:
        niri_action("fullscreen-window")

    quit()


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle 'need to peek' case

# For sanity. This shouldn't happen if we get here
if user_win["is_floating"]:
    raise RuntimeError("Unexpected error! Trying to float but user is already floating")

# Check for windows to peek (i.e. float)
user_col, user_row = user_win["layout"]["pos_in_scrolling_layout"]
have_peekable_wins = False
for attempt_idx in range(2 if PEEK_BOTHSIDES else 1):
    target_peek_col = user_col + 1 if PEEK_RIGHT else user_col - 1
    peek_win_info = [w for w in nonfloat_win_list if w["layout"]["pos_in_scrolling_layout"][0] == target_peek_col]
    have_peekable_wins = len(peek_win_info) > 0
    if have_peekable_wins:
        break
    PEEK_RIGHT = not PEEK_RIGHT

# If we get this far and have nothing to peek, there's nothing more to do
if not have_peekable_wins:
    quit()

# Figure out y-positioning of target windows when floated
peek_win_info = sorted(peek_win_info, key=lambda w: w["layout"]["pos_in_scrolling_layout"][1])
target_float_y, csum_y = [], TARGET_FLOAT_Y_OFFSET
for target_win in peek_win_info:
    target_float_y.append(csum_y)
    csum_y += target_win["layout"]["window_size"][1] + FLOAT_Y_GAP

# Float target windows and move to far side of screen
max_row_idx = max(w["layout"]["pos_in_scrolling_layout"][1] for w in peek_win_info)
for win_info, target_y in zip(peek_win_info, target_float_y):
    target_id = win_info["id"]
    niri_action(f"move-window-to-floating --id {target_id}")

    # Resize floated windows if needed
    target_w, target_h = win_info["layout"]["window_size"]
    if ALLOW_FLOAT_RESIZE:
        target_w = min(target_w, int(monitor_w * MAX_RESIZE_WIDTH)) if LIMIT_MAX_WIDTH else target_w
        niri_focus_window(target_id)
        floated_info = get_focused_window()
        float_w, float_h = floated_info["layout"]["window_size"]
        if float_w != target_w:
            niri_action(f"set-window-width {target_w}")
        if float_h != target_h:
            niri_action(f"set-window-height {target_h}")
        pass

    # Position floated windows on left or right side of screen
    target_x = TARGET_FLOAT_X if PEEK_RIGHT else (monitor_w - target_w - TARGET_FLOAT_X)
    niri_action(f"move-floating-window --id {target_id} -x {target_x} -y {target_y}")

# Set final focus window after peeking
if FOCUS_PEEKED:
    niri_focus_window(peek_win_info[0]["id"])
else:
    niri_focus_window(user_win["id"])
