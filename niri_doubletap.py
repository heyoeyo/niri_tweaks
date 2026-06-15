#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# ---------------------------------------------------------------------------------------------------------------------
# %% Imports

import argparse
import subprocess
import datetime as dt
from os import utime
from pathlib import Path

# ---------------------------------------------------------------------------------------------------------------------
# %% Handle script args

# Define script arguments
parser = argparse.ArgumentParser(
    description="Script which can run a command when quickly called twice",
    epilog="Works by recording timing in a temporary file and triggering only if two calls occur close in time",
)
parser.add_argument(
    "on_double_tap",
    nargs="?",
    type=str,
    default=None,
    help="A niri action or more general command to run",
)
parser.add_argument("-s", "--on_single_tap", type=str, default=None, help="Command to run on single tap")
parser.add_argument(
    "-r",
    "--reverse_single_tap",
    type=str,
    default=None,
    help="Command to run before double tap (meant to reverse the effect of single tap)",
)
parser.add_argument(
    "-dt",
    "--double_tap_window_ms",
    type=int,
    default=225,
    help="Amount of time (in milliseconds) where a second call is still considered a double tap (default: 225)",
)
parser.add_argument(
    "-lb",
    "--lower_bound_window_ms",
    type=int,
    default=0,
    help="Sets a lower bound, so that double tap cannot be *faster* than this (can produce 'on-hold' behavior)",
)
parser.add_argument("-n", "--not_niri", action="store_true", help="If true, commands are not executed as niri actions")
parser.add_argument(
    "-x",
    "--file_suffix",
    type=str,
    default="0",
    help="Suffix added to timing file. Using a suffix allows for independent double-tap timings to be recorded",
)
parser.add_argument("-notify", "--notify", action="store_true", help="Report time elapsed on call (for debugging)")

# For convenience
args = parser.parse_args()
DOUBLE_TAP_ACTION = args.on_double_tap
SINGLE_TAP_ACTION = args.on_single_tap
REVERSE_ACTION = args.reverse_single_tap
DOUBLE_TAP_WINDOW_MS = args.double_tap_window_ms
LOWBOUND_TAP_WINDOW_MS = args.lower_bound_window_ms
IS_NIRI_ACTION = not args.not_niri
FILE_SUFFIX = args.file_suffix
ENABLE_NOTIFY = args.notify


# ---------------------------------------------------------------------------------------------------------------------
# %% Helpers


def run_command(command_str: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command_str.split(" "), **kwargs)


def niri_action(action: str) -> subprocess.CompletedProcess:
    return run_command(f"niri msg action {action}")


def action_or_command(input_str: str, is_niri_action: bool) -> subprocess.CompletedProcess:
    return niri_action(input_str) if is_niri_action else run_command(input_str)


def notify(message: str) -> None:
    notify_title = f"{Path(__file__).name}"
    subprocess.run(["notify-send", notify_title, message])
    return


# ---------------------------------------------------------------------------------------------------------------------
# %% Main code

# Warning for missing input
if DOUBLE_TAP_ACTION is None:
    notify("Action not set! See:\nniri msg action --help")

# Make sure timing file exists
tmp_file = Path(f"/tmp/niri_doubletap_{FILE_SUFFIX}")
if not tmp_file.exists():
    tmp_file.touch(exist_ok=True)
    utime(tmp_file, (0, 0))
file_sys_stat = tmp_file.stat()
tmp_file.touch()

# Figure out elapsed time
last_time_ms = file_sys_stat.st_mtime_ns // 1_000_000
curr_time_ms = int(dt.datetime.now().timestamp() * 1000)
time_delta_ms = curr_time_ms - last_time_ms
if ENABLE_NOTIFY:
    notify(f"elapsed: {time_delta_ms}")

# Handle action triggers
is_double_tap = LOWBOUND_TAP_WINDOW_MS < time_delta_ms < DOUBLE_TAP_WINDOW_MS
if is_double_tap:
    utime(tmp_file, (file_sys_stat.st_atime, file_sys_stat.st_mtime - (DOUBLE_TAP_WINDOW_MS / 1000)))
    if REVERSE_ACTION is not None:
        action_or_command(REVERSE_ACTION, IS_NIRI_ACTION)
    action_or_command(DOUBLE_TAP_ACTION, IS_NIRI_ACTION)
elif SINGLE_TAP_ACTION is not None:
    action_or_command(SINGLE_TAP_ACTION, IS_NIRI_ACTION)
