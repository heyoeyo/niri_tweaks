#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import json


def run_command(command_str: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command_str.split(" "), **kwargs)


def get_workspaces_info() -> list[dict]:
    resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_focused_window() -> dict:
    resp = run_command("niri msg --json focused-window", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


# Handle target workspace arg
parser = argparse.ArgumentParser(description="Move to target workspace or jump to start if already on it")
parser.add_argument("workspace", nargs=1, type=int, help="Target workspace")
args = parser.parse_args()
target_wspace = args.workspace[0]

# Get currently focused workspace
curr_wspace = None
for wspace in get_workspaces_info():
    if wspace["is_focused"]:
        curr_wspace = wspace["idx"]
        break

# Jump to target workspace or first/last-column if already on workspace
if curr_wspace != target_wspace:
    run_command(f"niri msg action focus-workspace {target_wspace}")
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
