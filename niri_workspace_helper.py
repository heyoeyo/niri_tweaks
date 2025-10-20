#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import json


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle script args

# Handle target workspace arg
parser = argparse.ArgumentParser(description="Move to target workspace or toggle overview if already on it")
parser.add_argument(
    "workspace",
    nargs=1,
    type=str,
    help="Workspace index or name, or movement command: 'next', 'prev', 'first' or 'last'",
)
parser.add_argument(
    "-j",
    "--jump",
    action="store_true",
    help="If enabled, jump to first/last column (instead of toggling overview) if already on the target workspace",
)
parser.add_argument("-s", "--skip_empty", action="store_true", help="Skip empty workspaces (with next/prev/first/last)")
parser.add_argument("-w", "--wrap", action="store_true", help="If there is no next/prev workspace, wrap around")
parser.add_argument("-z", "--hidden", nargs="+", help="Hide given workspace(s) when moving. Can list multiple names")


# For convenience
args = parser.parse_args()
TARGET_WORKSPACE_KEY = args.workspace[0]
USE_OVERVIEW_TOGGLE = not args.jump
SKIP_EMPTY = args.skip_empty
ALLOW_WRAP_AROUND = args.wrap
HIDDEN_WSPACES_LIST = args.hidden
HAVE_HIDDEN_WSPACES = HIDDEN_WSPACES_LIST is not None


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


def get_focused_window() -> dict:
    resp = run_command("niri msg --json focused-window", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_first_workspace(workspaces_info_list: list[dict]) -> dict:
    return min(workspaces_info_list, key=lambda ws: ws["idx"])


def get_last_workspace(workspaces_info_list: list[dict]) -> dict:
    return max(workspaces_info_list, key=lambda ws: ws["idx"])


# ---------------------------------------------------------------------------------------------------------------------
# %% Get current workspace info

# Get currently focused workspace
all_wspaces_info = get_all_workspaces_info()
curr_wspace = None
for wspace in all_wspaces_info:
    if wspace["is_focused"]:
        curr_wspace = wspace
        break

# Bail if we can't figure out where we are (shouldn't happen?)
if curr_wspace is None:
    raise RuntimeError("Unable to determine the current workspace!")


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle workspace command cases

# Handle special target cases
if TARGET_WORKSPACE_KEY in ("first", "last", "next", "prev"):

    # Only consider workspaces on the same output and ignore empty/hidden workspaces
    candidate_wspaces_info = [ws for ws in all_wspaces_info if ws["output"] == curr_wspace["output"]]
    if HAVE_HIDDEN_WSPACES:
        candidate_wspaces_info = [ws for ws in candidate_wspaces_info if ws["name"] not in HIDDEN_WSPACES_LIST]
    if SKIP_EMPTY:
        all_wins_info = get_all_windows_info()
        non_empty_wspace_ids = {w["workspace_id"] for w in all_wins_info}
        candidate_wspaces_info = [ws for ws in candidate_wspaces_info if ws["id"] in non_empty_wspace_ids]

    # Sanity check. If we somehow have no candidates, use our current workspace
    if len(candidate_wspaces_info) == 0:
        candidate_wspaces_info = [curr_wspace]

    # Replace command key with actual workspace (let's us re-use index/naming code later on)
    curr_wspace_idx = curr_wspace["idx"]
    target_wspace_info = curr_wspace
    if TARGET_WORKSPACE_KEY == "first":
        target_wspace_info = get_first_workspace(candidate_wspaces_info)

    elif TARGET_WORKSPACE_KEY == "last":
        target_wspace_info = get_last_workspace(candidate_wspaces_info)

    elif TARGET_WORKSPACE_KEY == "next":
        next_wspaces_info = [ws for ws in candidate_wspaces_info if ws["idx"] > curr_wspace_idx]
        if len(next_wspaces_info) == 0:
            next_wspaces_info = [get_first_workspace(candidate_wspaces_info)] if ALLOW_WRAP_AROUND else [curr_wspace]
        target_wspace_info = min(next_wspaces_info, key=lambda ws: ws["idx"])

    elif TARGET_WORKSPACE_KEY == "prev":
        prev_wspaces_info = [ws for ws in candidate_wspaces_info if ws["idx"] < curr_wspace_idx]
        if len(prev_wspaces_info) == 0:
            prev_wspaces_info = [get_last_workspace(candidate_wspaces_info)] if ALLOW_WRAP_AROUND else [curr_wspace]
        target_wspace_info = max(prev_wspaces_info, key=lambda ws: ws["idx"])

    # Workspaces always (?) have a valid index
    TARGET_WORKSPACE_KEY = target_wspace_info["idx"]


# ---------------------------------------------------------------------------------------------------------------------
# %% Main logic

# Focus target workspace or (if focused) toggle overview or jump to first/last column
target_wspace_handle = str(TARGET_WORKSPACE_KEY)
curr_wspace_handle = str(curr_wspace["idx"]) if target_wspace_handle.isdigit() else curr_wspace["name"]
if curr_wspace_handle != target_wspace_handle:
    run_command(f"niri msg action focus-workspace {TARGET_WORKSPACE_KEY}")

elif USE_OVERVIEW_TOGGLE:
    run_command("niri msg action toggle-overview")

else:
    # Drop focus from floating windows (focus first/last doesn't work otherwise)
    curr_win = get_focused_window()
    if curr_win["is_floating"]:
        run_command("niri msg action switch-focus-between-floating-and-tiling")

    # Figure out if the current window is already the first column or not
    curr_colrow = curr_win["layout"]["pos_in_scrolling_layout"]
    curr_col = curr_colrow[0] if curr_colrow is not None else 100
    if curr_col > 1:
        run_command("niri msg action focus-column-first")
    else:
        run_command("niri msg action focus-column-last")
    pass
