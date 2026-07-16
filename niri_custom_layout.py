#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# ---------------------------------------------------------------------------------------------------------------------
# %% Imports

import argparse
import subprocess
import json
from os.path import basename
from time import sleep

# ---------------------------------------------------------------------------------------------------------------------
# %% Handle script args

# Handle target workspace arg
parser = argparse.ArgumentParser(description="Stack windows into a custom layout")
parser.add_argument(
    "rows_per_column",
    nargs="*",  # means: 0 or more args
    type=int,
    default=[2, 3],
    help="Specify layout using sequence of integers corresponding to rows per column (default: 2 3)",
)
parser.add_argument(
    "-a",
    "--anchor",
    type=str,
    default="left",
    choices=["left", "right", "focused", "l", "r", "f"],
    help="Determines where windows begin stacking from (default: left)",
)
parser.add_argument(
    "-rtl",
    "--right_to_left",
    action="store_true",
    help="If set, stack windows from right-to-left instead of left-to-right",
)
parser.add_argument(
    "-w",
    "--column_width_pcts",
    nargs="*",  # means: 0 or more args
    type=float,
    help="Set column width percents. Can provide values for each column. If flag is set with no values, will use equal sizing",
)
parser.add_argument(
    "-r",
    "--row_height_pcts",
    nargs="+",  # means: 1 or more args
    type=float,
    default=None,
    help="(Advanced) Set custom row height percents. Must provide 1 number for each window in layout. Use 0 for no change",
)
parser.add_argument(
    "-uw",
    "--unstack_width_pct",
    type=float,
    default=None,
    help="Sets the width to use when unstacking windows (no effect if unstacking is disabled/unused)",
)
parser.add_argument(
    "-du",
    "--disable_unstack",
    action="store_true",
    help="Disable unstacking toggle behavior when windows are already in correct layout",
)
parser.add_argument(
    "-rd",
    "--row_resize_delay_ms",
    type=int,
    default=25,
    help="Delay before trying to resize rows (if using custom heights). Needed for sizing to properly take effect",
)
parser.add_argument(
    "-t",
    "--transition_delay_ms",
    type=int,
    default=0,
    help="Set to a value > 0 (e.g. 200) to trigger a screen transition effect to hide layout re-arrangement",
)

# For convenience
args = parser.parse_args()
ROWS_PER_COLUMN = args.rows_per_column
COLUMN_WIDTH_PCTS = args.column_width_pcts
ROW_HEIGHT_PCTS = args.row_height_pcts
UNSTACK_WIDTH_PCT = args.unstack_width_pct
ANCHOR_STR = args.anchor
IS_LEFT_TO_RIGHT = not args.right_to_left
ENABLE_UNSTACK_TOGGLE = not args.disable_unstack
ROW_RESIZE_DELAY_MS = args.row_resize_delay_ms
TRANSITION_DELAY_MS = args.transition_delay_ms

# Special case. If using 1 row in each column, disable unstacking automatically (doesn't make sense to use)
if all(num_rows == 1 for num_rows in ROWS_PER_COLUMN):
    ENABLE_UNSTACK_TOGGLE = False


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


def shift_window_left(window_id: int) -> subprocess.CompletedProcess:
    return run_command(f"niri msg action consume-or-expel-window-left --id {window_id}")


def shift_window_right(window_id: int) -> subprocess.CompletedProcess:
    return run_command(f"niri msg action consume-or-expel-window-right --id {window_id}")


def notify(message: str, exit_script: bool = True) -> None:
    notify_title = f"Error: {basename(__file__)}"
    subprocess.run(["notify-send", notify_title, message])
    if exit_script:
        raise SystemExit()
    return


# ---------------------------------------------------------------------------------------------------------------------
# %% Parse layout info

# Handle widths not set (None) vs. set but with no values (empty list)
NUM_COLUMNS = len(ROWS_PER_COLUMN)
if COLUMN_WIDTH_PCTS is None:
    COLUMN_WIDTH_PCTS = [None]
elif len(COLUMN_WIDTH_PCTS) == 0:
    COLUMN_WIDTH_PCTS = [100 / NUM_COLUMNS]

# For sanity, make sure we get list inputs
COLUMN_WIDTH_PCTS = [COLUMN_WIDTH_PCTS] if isinstance(COLUMN_WIDTH_PCTS, int) else COLUMN_WIDTH_PCTS
ROW_HEIGHT_PCTS = [ROW_HEIGHT_PCTS] if isinstance(ROW_HEIGHT_PCTS, int) else ROW_HEIGHT_PCTS

# Sanity check
NUM_LAYOUT_TILES = sum(ROWS_PER_COLUMN)
if NUM_LAYOUT_TILES < 2:
    notify("Layout must have 2 or more entries!")

# Make sure column widths are set for each column
need_width_adjustment = True
if COLUMN_WIDTH_PCTS is None:
    COLUMN_WIDTH_PCTS = []
    need_width_adjustment = False
elif len(COLUMN_WIDTH_PCTS) == 1:
    COLUMN_WIDTH_PCTS = [COLUMN_WIDTH_PCTS[0]] * NUM_COLUMNS
elif len(COLUMN_WIDTH_PCTS) < NUM_COLUMNS:
    COLUMN_WIDTH_PCTS = list(COLUMN_WIDTH_PCTS) + [None] * (NUM_COLUMNS - len(COLUMN_WIDTH_PCTS))
elif len(COLUMN_WIDTH_PCTS) > NUM_COLUMNS:
    COLUMN_WIDTH_PCTS = COLUMN_WIDTH_PCTS[:NUM_COLUMNS]
    notify(f"Too many column widths! Using: {' '.join(str(W) for W in COLUMN_WIDTH_PCTS)}", exit_script=False)

# Make sure row heights are set for each window
need_height_adjustment = True
if ROW_HEIGHT_PCTS is None:
    need_height_adjustment = False
    ROW_HEIGHT_PCTS = [None] * NUM_LAYOUT_TILES
elif len(ROW_HEIGHT_PCTS) < NUM_LAYOUT_TILES:
    ROW_HEIGHT_PCTS = list(ROW_HEIGHT_PCTS) + [0] * (NUM_LAYOUT_TILES - len(ROW_HEIGHT_PCTS))
    notify(f"Bad row heights! Using: {' '.join(str(H) for H in ROW_HEIGHT_PCTS)}", exit_script=False)
elif len(ROW_HEIGHT_PCTS) > NUM_LAYOUT_TILES:
    ROW_HEIGHT_PCTS = ROW_HEIGHT_PCTS[:NUM_LAYOUT_TILES]
    notify(f"Too many row heights! Using: {' '.join(str(H) for H in ROW_HEIGHT_PCTS)}", exit_script=False)

# Interpret 0 entries as None/no-setting
COLUMN_WIDTH_PCTS = [None if W == 0 else W for W in COLUMN_WIDTH_PCTS]
ROW_HEIGHT_PCTS = [None if H == 0 else H for H in ROW_HEIGHT_PCTS]


# ---------------------------------------------------------------------------------------------------------------------
# %% Get windows requiring layout adjustments

# Get current workspace id
curr_wspace_id, curr_wspace_idx = -1, 0
for ws_info in get_all_workspaces_info():
    if ws_info["is_focused"]:
        curr_wspace_id = ws_info["id"]
        curr_wspace_idx = ws_info["idx"]
        break

# Get info for all tiled windows
curr_win_info = (win_info for win_info in get_all_windows_info() if win_info["workspace_id"] == curr_wspace_id)
tile_win_info = [win_info for win_info in curr_win_info if not win_info["is_floating"]]
if len(tile_win_info) == 0:
    raise SystemExit()

# Get all windows in order, top-to-bottom then left-to-right
get_col_idx = lambda item: item["layout"]["pos_in_scrolling_layout"][0]
get_row_idx = lambda item: item["layout"]["pos_in_scrolling_layout"][1]
get_ltr_sort_score = lambda item: (get_col_idx(item), get_row_idx(item))
ordered_win_info_list = sorted(tile_win_info, key=get_ltr_sort_score)

# Take only the subset of window info needed to form layout
num_windows = len(ordered_win_info_list)
if ANCHOR_STR in ("left", "l"):
    first_slice_idx = 0
    last_slice_idx = NUM_LAYOUT_TILES
elif ANCHOR_STR in ("right", "r"):
    last_slice_idx = num_windows
    first_slice_idx = max(last_slice_idx - NUM_LAYOUT_TILES, 0)
else:
    focused_idxs = [idx for idx, info in enumerate(ordered_win_info_list) if info["is_focused"]]
    first_slice_idx = focused_idxs[0] if len(focused_idxs) == 1 else (0 if IS_LEFT_TO_RIGHT else (num_windows - 1))
    last_slice_idx = first_slice_idx + NUM_LAYOUT_TILES
layout_win_info_list = ordered_win_info_list[first_slice_idx:last_slice_idx]


# ---------------------------------------------------------------------------------------------------------------------
# %% Un-stack non-layout windows

# Hide animations with a transition, if configured
if TRANSITION_DELAY_MS > 0:
    run_command(f"niri msg action do-screen-transition -d {TRANSITION_DELAY_MS}")

# For clarity
leftmost_layout_info = layout_win_info_list[0]
rightmost_layout_info = layout_win_info_list[-1]

# Expel any 'non-layout' windows to the left
left_expel_count = 0
layout_first_col_idx = get_col_idx(leftmost_layout_info)
for win_info in ordered_win_info_list[0:first_slice_idx]:
    if get_col_idx(win_info) < layout_first_col_idx:
        break
    shift_window_left(win_info["id"])
    if left_expel_count > 0:
        # If we already shifted, we need to shift twice to stack additional entries into a shared column
        shift_window_left(win_info["id"])
    left_expel_count += 1

# Update window row & column positioning to account for changes after left expel
if left_expel_count > 0:
    for win_info in layout_win_info_list:
        old_col_idx, old_row_idx = win_info["layout"]["pos_in_scrolling_layout"]
        new_col_idx = old_col_idx + 1
        new_row_idx = old_row_idx if old_col_idx > layout_first_col_idx else old_row_idx - left_expel_count
        win_info["layout"]["pos_in_scrolling_layout"] = [new_col_idx, new_row_idx]

# Expel any 'non-layout' windows to the right
right_expel_count = 0
layout_last_col_idx = get_col_idx(rightmost_layout_info)
for win_info in ordered_win_info_list[last_slice_idx:]:
    if get_col_idx(win_info) > layout_last_col_idx:
        break
    shift_window_right(win_info["id"])
    if right_expel_count > 0:
        # Shift twice to stack additional entries into the same column
        shift_window_right(win_info["id"])
    right_expel_count += 1


# ---------------------------------------------------------------------------------------------------------------------
# %% Re-arrange windows into layout

# For clarity
arrange_order_win_info_list = layout_win_info_list
target_column_idx_seq = range(layout_first_col_idx, layout_first_col_idx + NUM_COLUMNS)
arrange_rows_per_column = ROWS_PER_COLUMN
shift_window_out = shift_window_right
shift_window_in = shift_window_left
if not IS_LEFT_TO_RIGHT:
    # Reverse indexing and window order for right-to-left arrangments
    get_rtl_sort_score = lambda item: (-get_col_idx(item), get_row_idx(item))
    arrange_order_win_info_list = sorted(layout_win_info_list, key=get_rtl_sort_score)
    target_column_idx_seq = range(layout_last_col_idx, layout_last_col_idx - NUM_COLUMNS, -1)
    arrange_rows_per_column = reversed(ROWS_PER_COLUMN)
    shift_window_out = shift_window_left
    shift_window_in = shift_window_right

# Build target (column, row) indexing of 'arrangement ordered' windows
colrow_seq = []
for col_idx, num_rows in zip(target_column_idx_seq, arrange_rows_per_column):
    for row_idx in range(num_rows):
        colrow_seq.append((col_idx, 1 + row_idx))

# Keep track of windows that are already arranged correctly (so we can skip trying to arrange them)
skip_idx = 0
for (targ_col_idx, targ_row_idx), win_info in zip(colrow_seq, arrange_order_win_info_list):
    is_col_match = get_col_idx(win_info) == targ_col_idx
    is_row_match = get_row_idx(win_info) == targ_row_idx
    if not is_col_match or not is_row_match:
        break
    skip_idx += 1

# Create new list of only the windows that need re-arranging
adjust_win_info_list = arrange_order_win_info_list
flat_row_idx_sequence = [row_idx for _, row_idx in colrow_seq]
if skip_idx > 0:
    adjust_win_info_list = arrange_order_win_info_list[skip_idx:]
    flat_row_idx_sequence = flat_row_idx_sequence[skip_idx:]

# Special 'unstack' toggle logic if windows are already in proper layout
no_window_change = len(adjust_win_info_list) == 0
need_unstack_reset = ENABLE_UNSTACK_TOGGLE and no_window_change
if need_unstack_reset:
    adjust_win_info_list = arrange_order_win_info_list
    flat_row_idx_sequence = [0] * len(arrange_order_win_info_list)
    need_unstack_reset = True

# Unstack windows if needed (slightly inefficient but much easier to work with)
for win_info in reversed(adjust_win_info_list):
    if get_row_idx(win_info) > 1:
        shift_window_out(win_info["id"])

# Shift windows into columns as needed to form layout
for target_row_idx, win_info in zip(flat_row_idx_sequence, adjust_win_info_list):
    if target_row_idx > 1:
        shift_window_in(win_info["id"])


# ---------------------------------------------------------------------------------------------------------------------
# %% Adjust width/height

# Prevent attempts to repeat-row-resizing if nothing changed (and we aren't going to unstack)
if no_window_change and not ENABLE_UNSTACK_TOGGLE:
    need_height_adjustment = False

if need_width_adjustment:

    # Flatten column widths into window widths
    win_width_pcts = []
    for num_rows, col_width_pct in zip(ROWS_PER_COLUMN, COLUMN_WIDTH_PCTS):
        win_width_pcts.extend([col_width_pct] * num_rows)
    if need_unstack_reset:
        win_width_pcts = [UNSTACK_WIDTH_PCT] * len(win_width_pcts)

    # Set width of every window, so that we properly handle resets if needed
    for win_info, win_width_pct in zip(layout_win_info_list, win_width_pcts):
        if win_width_pct is None:
            continue
        run_command(f"niri msg action set-window-width --id {win_info['id']} {win_width_pct}%")


if need_height_adjustment:
    # Short delay to allow for windows to stack into correct column, to get correct context for proportioning
    if ROW_RESIZE_DELAY_MS > 0:
        sleep(ROW_RESIZE_DELAY_MS / 1000)
    for win_info, win_height_pct in zip(layout_win_info_list, ROW_HEIGHT_PCTS):
        cmd_str = f"niri msg action set-window-height --id {win_info['id']} {win_height_pct}%"
        if win_height_pct is None or need_unstack_reset:
            cmd_str = f"niri msg action reset-window-height --id {win_info['id']}"
        run_command(cmd_str)
