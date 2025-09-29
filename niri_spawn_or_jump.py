#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# ---------------------------------------------------------------------------------------------------------------------
# %% Imports

import argparse
import subprocess
import json


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle script args

# Define script arguments
parser = argparse.ArgumentParser(
    description="Script used to spawn or cycle instances of an application with niri",
    epilog="To find the app_id of a window, run this script with no arguments then focus the target window.",
)
parser.add_argument(
    "command",
    nargs="?",
    type=str,
    help="Spawn command used to run an application (e.g. 'firefox' or 'flatpak run app.zen_browser.zen')",
)
parser.add_argument("app_id", nargs="?", type=str, help="Target app-id (only needed if different from the run command)")
parser.add_argument("-b", "--backward", action="store_true", help="Cycle backwards instead of forward")
parser.add_argument("-w", "--workspace", action="store_true", help="Only search on active workspace")
parser.add_argument("--no_floats", action="store_true", help="Don't check for floating windows")
parser.add_argument("--no_tiles", action="store_true", help="Don't check for tiled windows")
parser.add_argument("--no_spawn", action="store_true", help="Never spawn, only jump/cycle instances")
parser.add_argument(
    "--always_spawn", action="store_true", help="Always spawn, no jumping (may be useful for scripting?)"
)

# For convenience
args = parser.parse_args()
COMMAND = args.command
TARGET_APP_ID = args.app_id
CYCLE_FORWARD = not args.backward
ACTIVE_WORKSPACE = args.workspace
NO_FLOATS = args.no_floats
NO_TILES = args.no_tiles
ENABLE_SPAWN = not args.no_spawn
ALWAYS_SPAWN = args.always_spawn

# Sanity checks
assert not (NO_FLOATS and NO_TILES), "Cannot disable checks for floating & tiled windows (enable only one or neither)"
assert not (ALWAYS_SPAWN and not ENABLE_SPAWN), "Cannot always spawn & disable spawning at the same time!"

# Fill in missing app-id
if TARGET_APP_ID is None and COMMAND is not None:
    TARGET_APP_ID = COMMAND.split(" ")[-1] if COMMAND.startswith("flatpak") else COMMAND


# ---------------------------------------------------------------------------------------------------------------------
# %% Helper functions


def run_command(command_str: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command_str.split(" "), **kwargs)


def focus_window(id: int) -> subprocess.CompletedProcess:
    return run_command(f"niri msg action focus-window --id {id}")


def get_focused_window() -> dict:
    resp = run_command("niri msg --json focused-window", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_active_workspaces() -> list[int]:
    resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
    resp.check_returncode()
    resp_list = json.loads(resp.stdout)
    return [wspace_dict["id"] for wspace_dict in resp_list if wspace_dict["is_active"]]


def get_focused_workspace(default_if_missing=1) -> int:
    resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
    resp.check_returncode()
    resp_list = json.loads(resp.stdout)
    focused_wspace_ids = [wspace_dict["id"] for wspace_dict in resp_list if wspace_dict["is_focused"]]
    return focused_wspace_ids[0] if len(focused_wspace_ids) > 0 else default_if_missing


def get_windows_list() -> list[dict]:
    resp = run_command("niri msg --json windows", capture_output=True, text=True)
    resp.check_returncode()  # Raise error if we get bad return code
    return json.loads(resp.stdout)


# ---------------------------------------------------------------------------------------------------------------------
# %% For setup/debugging

enable_appid_inspection = COMMAND is None and TARGET_APP_ID is None
if enable_appid_inspection:
    from time import sleep

    try:
        while True:
            win_dict = get_focused_window()
            print("app-id:", win_dict["app_id"])
            sleep(0.5)

    except KeyboardInterrupt:
        pass

    quit()


# ---------------------------------------------------------------------------------------------------------------------
# %% Main code

# Check if the target app-id is already opened
target_win_list = []
for win_dict in get_windows_list():
    win_app_id = win_dict["app_id"]
    if win_app_id == TARGET_APP_ID:
        target_win_list.append(win_dict)

# Handle script arg modifiers
if ALWAYS_SPAWN:
    target_win_list = []
if ACTIVE_WORKSPACE:
    active_wspace_ids_list = get_active_workspaces()
    target_win_list = [w for w in target_win_list if w["workspace_id"] in active_wspace_ids_list]
if NO_FLOATS:
    target_win_list = [w for w in target_win_list if not w["is_floating"]]
if NO_TILES:
    target_win_list = [w for w in target_win_list if w["is_floating"]]

# Open if no existing window
num_already_open = len(target_win_list)
if num_already_open == 0:
    if ENABLE_SPAWN and COMMAND is not None:
        # Run the command and detach from caller
        subprocess.Popen(
            COMMAND.split(" "),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    quit()

# Jump to the (single) open instance
if num_already_open == 1:
    focus_window(target_win_list[0]["id"])
    quit()


# Helper used to build window positioning format which we'll sort to decide window ordering
# -> Order: workspace_id, column, row, pid, id
# -> Floating windows are given col/row of 0, since it's hard to define otherwise
# -> pid is included to sort among floating windows
# -> id isn't meant for sorting, it's included so we can get back the window id easily after sorting/indexing
make_sortable_position = lambda d: (
    d["workspace_id"],
    *(d["layout"]["pos_in_scrolling_layout"] if not d["is_floating"] else (0, 0)),
    d["pid"],
    d["id"],
)

# Get 'position' of all target windows in a sortable format
target_pos_list = []
for win_dict in target_win_list:
    target_pos_list.append(make_sortable_position(win_dict))

# Figure out the current view position & add to listing if needed
curr_win = get_focused_window()
curr_pos = make_sortable_position(curr_win) if curr_win is not None else (get_focused_workspace(), 0, 0, -1, -1)
if curr_pos not in target_pos_list:
    target_pos_list.append(curr_pos)

# Find current window position in (sorted) list, then move focus to the 'next' entry
target_pos_list.sort()
curr_pos_idx = target_pos_list.index(curr_pos)
next_pos_idx = (curr_pos_idx + (1 if CYCLE_FORWARD else -1)) % len(target_pos_list)
focus_window(target_pos_list[next_pos_idx][-1])
