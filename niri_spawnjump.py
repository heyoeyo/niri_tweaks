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
parser.add_argument("-p", "--pull", action="store_true", help="If an instance exists, pull it next to focused window")
parser.add_argument(
    "-s",
    "--push",
    action="store_true",
    help="If only 1 instance exists and it's focused, push it to end of workspace (or off, if floating)",
)
parser.add_argument(
    "-t",
    "--scratch",
    type=str,
    help="Auto-enables push/pull. Applications are pushed to a workspace with this name",
)
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
ACTIVE_WORKSPACE_ONLY = args.workspace
ENABLE_PULL = args.pull
ENABLE_PUSH = args.push
SCRATCHPAD = args.scratch
NO_FLOATS = args.no_floats
NO_TILES = args.no_tiles
ENABLE_SPAWN = not args.no_spawn
ALWAYS_SPAWN = args.always_spawn

# Sanity checks
assert not (NO_FLOATS and NO_TILES), "Cannot disable checks for floating & tiled windows (enable only one or neither)"
assert not (ALWAYS_SPAWN and not ENABLE_SPAWN), "Cannot always spawn & disable spawning at the same time!"

# Auto-config for push/pull to scratchpad, if provided
if SCRATCHPAD is not None:
    ENABLE_PULL = True
    ENABLE_PUSH = True
    ACTIVE_WORKSPACE_ONLY = False

# Fill in missing app-id
if TARGET_APP_ID is None and COMMAND is not None:
    TARGET_APP_ID = COMMAND.split(" ")[-1] if COMMAND.startswith("flatpak") else COMMAND
    if Path(TARGET_APP_ID).is_file():
        TARGET_APP_ID = Path(TARGET_APP_ID).stem


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


def get_active_workspace_ids() -> list[int]:
    resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
    resp.check_returncode()
    resp_list = json.loads(resp.stdout)
    return [wspace_dict["id"] for wspace_dict in resp_list if wspace_dict["is_active"]]


def get_focused_workspace_idx(default_if_missing: int = 1) -> int:
    resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
    resp.check_returncode()
    resp_list = json.loads(resp.stdout)
    workspace_idx = default_if_missing
    for wspace_dict in resp_list:
        if wspace_dict["is_focused"]:
            workspace_idx = wspace_dict["idx"]
            break
        pass
    return workspace_idx


def get_windows_list() -> list[dict]:
    resp = run_command("niri msg --json windows", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def check_is_stacked_in_column(target_window_data: dict, all_windows_data: list[dict]) -> bool:
    """Helper used to determine if a window is stacked with 1 or more other windows in a column"""

    # No columns for floating windows so skip checks
    if target_window_data["is_floating"]:
        return False

    # Count how many windows have the same target workspace/column position
    target_wspace_id = target_window_data["workspace_id"]
    target_column = target_window_data["layout"]["pos_in_scrolling_layout"][0]
    num_same_col = 0
    for other_win in all_windows_data:
        if other_win["is_floating"] or other_win["workspace_id"] != target_wspace_id:
            continue
        if other_win["layout"]["pos_in_scrolling_layout"][0] == target_column:
            num_same_col += 1
        if num_same_col > 1:
            break

    return num_same_col > 1


def pull_window(target_window_data: dict, all_windows_data: list[dict]) -> None:
    """Brings a target window toward where the user is currently looking"""

    # For convenience
    target_id = target_window_data["id"]
    orig_win = get_focused_window()
    is_empty_workspace = orig_win is None

    # If we're already focused on window, we don't need to pull it
    orig_id = None if is_empty_workspace else orig_win["id"]
    if orig_id == target_id:
        return

    # Move the target to the current workspace, if needed
    orig_space_id = None if is_empty_workspace else orig_win["workspace_id"]
    if orig_space_id != target_window_data["workspace_id"]:
        orig_space_idx = get_focused_workspace_idx(orig_space_id)
        run_command(f"niri msg action move-window-to-workspace {orig_space_idx} --window-id {target_id}")

    # We'll want the target focused, no matter what we do next...
    focus_window(target_id)

    # We moved the window to the workspace, which is all we can do if it was already empty
    if is_empty_workspace:
        return

    # If we were focusing a floating window, we can't figure out what column to pull to, so do nothing
    if orig_win["is_floating"]:
        return

    # If target is floating, we already moved it to the workspace, so we're done
    # -> Would be nice to position under cursor, but niri IPC doesn't provide this info...?
    if target_window_data["is_floating"]:
        return

    # Un-stack the window before pulling, so we only pull the target (IPC only allows pulling a full column)
    if check_is_stacked_in_column(target_window_data, all_windows_data):
        run_command("niri msg action consume-or-expel-window-left")

    # Move the target window next to where we're looking (if it isn't already there)
    orig_column_idx = orig_win["layout"]["pos_in_scrolling_layout"][0]
    dest_column_idx = orig_column_idx + 1
    target_column_idx = target_window_data["layout"]["pos_in_scrolling_layout"][0]
    if target_column_idx != dest_column_idx:
        run_command(f"niri msg action move-column-to-index {dest_column_idx}")

        # Bit of a hack, since niri IPC doesn't include camera inspection/control
        # We quickly focus the original window to try to force the niri 'camera' to look at
        # both the window we were on and the window we've just pulled.
        # If we don't do this, the camera may pan our original window out of view, which is jarring
        focus_window(orig_id)
        focus_window(target_id)

    return


def push_window(target_window_data: dict, all_windows_data: list[dict], scratchpad_name: str | None = None) -> None:
    """
    Pushs a target window to the end of the current workspace, or to the next workspace if floating.
    If a scratchpad (workspace) name is provided, then push windows to that workspace instead.
    """

    # Push to 'scratchpad' workspace, if provided
    if scratchpad_name is not None:
        id_arg = f"--window-id {target_window_data['id']}"
        run_command(f"niri msg action move-window-to-workspace {id_arg} {scratchpad_name} --focus false")
        return

    # We can't move floats to the end of the workspace, so just push them to the next workspace
    # (not ideal, but if 'pull' is enable, user can quickly bring it back...)
    if target_window_data["is_floating"]:
        run_command("niri msg action move-window-to-workspace-down --focus false")
        return

    # Figure out where look after we push the window
    final_column_idx = max(1, target_window_data["layout"]["pos_in_scrolling_layout"][0] - 1)
    if not target_window_data["is_focused"]:
        orig_win = get_focused_window()
        final_column_idx = orig_win["layout"]["pos_in_scrolling_layout"][0] if orig_win is not None else 1
        focus_window(target_window_data["id"])

    # Un-stack the window before pushing if needed (IPC only allows pushing a full column)
    if check_is_stacked_in_column(target_window_data, all_windows_data):
        run_command("niri msg action consume-or-expel-window-right")

    # Move the target window to the end of the workspace then snap back to where we were looking
    run_command("niri msg action move-column-to-last")
    run_command(f"niri msg action focus-column {final_column_idx}")

    return


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
all_win_list = get_windows_list()
target_win_list = [w for w in all_win_list if str(w["app_id"]).lower() == TARGET_APP_ID.lower()]

# Handle script arg modifiers
if ALWAYS_SPAWN:
    target_win_list = []
if ACTIVE_WORKSPACE_ONLY:
    active_wspace_ids_list = get_active_workspace_ids()
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

# Push/pull/jump to the (single) open instance
if num_already_open == 1:
    target_win = target_win_list[0]
    if target_win["is_focused"] and ENABLE_PUSH:
        push_window(target_win, all_win_list, SCRATCHPAD)
    elif ENABLE_PULL:
        pull_window(target_win, all_win_list)
    else:
        focus_window(target_win["id"])
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
curr_pos = make_sortable_position(curr_win) if curr_win is not None else (get_focused_workspace_idx(), 0, 0, -1, -1)
if curr_pos not in target_pos_list:
    target_pos_list.append(curr_pos)

# Find current window position in (sorted) list, then move focus to the 'next' entry
target_pos_list.sort()
curr_pos_idx = target_pos_list.index(curr_pos)
next_pos_idx = (curr_pos_idx + (1 if CYCLE_FORWARD else -1)) % len(target_pos_list)
focus_window(target_pos_list[next_pos_idx][-1])
