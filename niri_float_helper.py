#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# ---------------------------------------------------------------------------------------------------------------------
# %% Imports

import argparse
import subprocess
import json
from pathlib import Path
from time import sleep

# ---------------------------------------------------------------------------------------------------------------------
# %% Handle script args

# Set up defaults
default_bg_color = "FFFFFF30"
default_border_color = "000000CC"
default_selection_color = "CC0077A0"
default_option_color = "FFFFFF70"
default_border_weight = 4
default_regions = [
    "50% 50% 25% 50%",
    "20 20 35% 45%",
    "20 -20 35% 45%",
    "-20 20 35% 45%",
    "-20 -20 35% 45%",
]

# Define script arguments
parser = argparse.ArgumentParser(description="Script which provides additional functionality when floating windows")
parser.add_argument(
    "regions",
    nargs="*",  # means: 0 or more args
    type=str,
    default=default_regions,
    help="Specify predefined region(s). Format is: 'x y w h'. X/Y can be negative. Use '%%' to scale to display",
)
parser.add_argument(
    "-d",
    "--draw_region",
    action="store_true",
    help="If set, allows for drawing a region directly instead of using predefined regions",
)
parser.add_argument(
    "-r", "--region_printout", action="store_true", help="If set, run slurp and print out region in 'x y w h' format"
)
parser.add_argument(
    "-xo",
    "--x_offset",
    type=int,
    default=None,
    help="Specify x-offset. Required for proper window-move alignment with slurp",
)
parser.add_argument(
    "-yo",
    "--y_offset",
    type=int,
    default=None,
    help="Specify y-offset. Required for proper window-move alignment with slurp",
)
parser.add_argument("-t", "--size_threshold", type=int, default=64, help="Minimum allowed region size")
parser.add_argument(
    "-nw", "--no_restore_width", action="store_true", help="Disables restoration of window width when un-floating"
)
parser.add_argument(
    "-nu", "--no_unfloat", action="store_true", help="Disables ability to 'un-float' window by re-running the command"
)
parser.add_argument(
    "-nr", "--no_refloat", action="store_true", help="Disables ability to 're-float' window by re-running the command"
)
parser.add_argument(
    "-sb",
    "--bg_color",
    type=str,
    default=default_bg_color,
    help=f"Set slurp background color (default: {default_bg_color})",
)
parser.add_argument(
    "-sc",
    "--border_color",
    type=str,
    default=default_border_color,
    help=f"Set slurp border color (default: {default_border_color})",
)
parser.add_argument(
    "-ss",
    "--selection_color",
    type=str,
    default=default_selection_color,
    help=f"Set slurp selection color (default: {default_selection_color})",
)
parser.add_argument(
    "-sB",
    "--option_box_color",
    type=str,
    default=default_option_color,
    help=f"Set slurp option box color (default: {default_option_color})",
)
parser.add_argument(
    "-sw",
    "--border_weight",
    type=int,
    default=default_border_weight,
    help=f"Set slurp border weight (default: {default_border_weight})",
)
parser.add_argument("-sd", "--show_dimensions", action="store_true", help="Enable dimensions on slurp selections")
parser.add_argument(
    "-p",
    "--folder_path",
    type=str,
    default="/tmp/niri_float_helper",
    help="Folder path used to store state data (default: '/tmp/niri_float_helper')",
)


# For convenience
args = parser.parse_args()
REGIONS = args.regions
ENABLE_DRAW = args.draw_region
ENABLE_REGION_PRINTOUT = args.region_printout
X_OFFSET = args.x_offset
Y_OFFSET = args.y_offset
SIZE_THRESHOLD = max(1, args.size_threshold)
ENABLE_WIDTH_RESTORE = not args.no_restore_width
ENABLE_UNFLOAT = not args.no_unfloat
ENABLE_REFLOAT = not args.no_refloat
SLURP_BG_COL = args.bg_color
SLURP_BORDER_COL = args.border_color
SLURP_SELECT_COL = args.selection_color
SLURP_OPTION_COL = args.option_box_color
SLURP_WEIGHT = args.border_weight
SLURP_DIMENSIONS = args.show_dimensions
STATE_FOLDER_PATH = Path(args.folder_path)

# For clarity
X_OFFSET = max(0, X_OFFSET) if X_OFFSET is not None else None
Y_OFFSET = max(0, Y_OFFSET) if Y_OFFSET is not None else None
NEED_REGION_PIXEL_SCALING = any("%" in r_str for r_str in REGIONS)
if ENABLE_DRAW:
    REGIONS = []
    NEED_REGION_PIXEL_SCALING = False
if ENABLE_REGION_PRINTOUT:
    SLURP_DIMENSIONS = True
SLURP_ARGS = (SLURP_BG_COL, SLURP_BORDER_COL, SLURP_SELECT_COL, SLURP_OPTION_COL, SLURP_WEIGHT, SLURP_DIMENSIONS)


# ---------------------------------------------------------------------------------------------------------------------
# %% Helpers


def run_command(command_str: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command_str.split(" "), **kwargs)


def niri_action(action: str) -> subprocess.CompletedProcess:
    return run_command(f"niri msg action {action}")


def get_focused_window() -> dict | None:
    resp = run_command("niri msg --json focused-window", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_focused_workspace() -> dict | None:
    resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
    resp.check_returncode()
    all_wspace_list = json.loads(resp.stdout)

    focused_wspace = None
    for ws_info in all_wspace_list:
        if ws_info["is_focused"]:
            focused_wspace = ws_info
            break
        pass

    return focused_wspace


def get_focused_monitor() -> dict:
    resp = run_command("niri msg --json focused-output", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def run_slurp(
    predefined_regions: list[str],
    bg_color: str = "FFFFFF30",
    border_color: str = "000000CC",
    select_color: str = "CC0077A0",
    option_color: str = "FFFFFF70",
    border_weight: int = 4,
    show_dimensions: bool = False,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Helper used to run slurp to get region coordinates. Returns: (x, y), (w, h)"""

    # Merge regions into a single string for input to slurp
    region_str = "\n".join(predefined_regions)
    use_regions = len(predefined_regions) > 0

    # Build up slurp call
    args = ["slurp", "-b", bg_color, "-c", border_color, "-s", select_color, "-w", str(border_weight)]
    if show_dimensions:
        args.append("-d")
    if use_regions:
        args.extend(("-r", "-B", option_color))

    # Run slurp & bail on cancel (e.g. user presses escape during slurp)
    try:
        raw_result = subprocess.run(args, capture_output=True, text=True, input=region_str)
    except FileNotFoundError:
        notify("Error running 'slurp'\nMay need to be installed!")
        raise SystemExit()
    if raw_result.returncode == 1:
        raise SystemExit()

    # Parse results into more convenient format
    xy_str, wh_str = raw_result.stdout.strip().split(" ")
    x_int, y_int = (int(val) for val in xy_str.split(","))
    w_int, h_int = (int(val) for val in wh_str.split("x"))
    return (x_int, y_int), (w_int, h_int)


def parse_size_str(size_str: str) -> tuple[bool, float]:
    """Helper used to interpret region sizing strings that may be pixel or % values"""
    is_pct = size_str.endswith("%")
    size_float = float(size_str[:-1]) / 100.0 if is_pct else float(size_str)
    return is_pct, size_float


def write_tmp_data(save_folder: Path, save_name: str, data: tuple | list) -> None:
    """Write temporary (json-friendly) data. Used for storing offsets/window state"""
    save_folder.mkdir(exist_ok=True)
    tmp_file = save_folder / save_name
    with open(tmp_file, "w") as outfile:
        json.dump(data, outfile, separators=(",", ":"))
    return


def read_tmp_data(save_folder: Path, load_name: str, delete_on_read: bool = False) -> tuple[bool, list]:
    """Read saved temporary data, used to recover prior offset/window state data"""
    tmp_file = save_folder / load_name
    file_exists, load_data = tmp_file.exists(), None
    if file_exists:
        with open(tmp_file, "r") as infile:
            load_data = json.load(infile)
        if delete_on_read:
            tmp_file.unlink()

    return file_exists, load_data


def notify(message: str) -> None:
    notify_title = f"{Path(__file__).name}"
    subprocess.run(["notify-send", notify_title, message])
    return


# ---------------------------------------------------------------------------------------------------------------------
# %% Region printout

# Meant for debugging. This runs slurp in drawing mode and prints out the 'x y w h' region that is drawn
if ENABLE_REGION_PRINTOUT:
    notify("Draw region to get 'x y w h' format")
    (box_x, box_y), (box_w, box_h) = run_slurp([], *SLURP_ARGS)
    monitor_info = get_focused_monitor()
    monitor_sizing_info = monitor_info["logical"]
    monitor_w, monitor_h = monitor_sizing_info["width"], monitor_sizing_info["height"]
    x_pct, y_pct = 100 * box_x / monitor_w, 100 * box_y / monitor_h
    w_pct, h_pct = 100 * box_w / monitor_w, 100 * box_h / monitor_h

    # Print results
    pixel_output = f"{box_x} {box_y} {box_w} {box_h}"
    pct_output = f"{x_pct:.0f}% {y_pct:.0f}% {w_pct:.0f}% {h_pct:.0f}%"
    print(
        "*** Float region as [x y w h] ***",
        "In pixel units:",
        f"  '{pixel_output}'",
        "As percentanges:",
        f"  '{pct_output}'",
        "Note: Values can be mixed/matched",
        sep="\n",
    )
    raise SystemExit()


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle re-triggers

# Check if user is running command with slurp already opened
if ENABLE_UNFLOAT or ENABLE_REFLOAT:
    is_slurp_running = run_command("pidof slurp", capture_output=True, text=True)
    if is_slurp_running.returncode == 0:
        pid_slurp = is_slurp_running.stdout.strip()
        run_command(f"kill {pid_slurp}")
        sleep(0.05)

        # Check if we have a focused window, now that slurp is not blocking view
        retrigger_win_info = get_focused_window()
        if retrigger_win_info is not None:
            retrigger_id, is_retrigger_floating = retrigger_win_info["id"], retrigger_win_info["is_floating"]
            if ENABLE_UNFLOAT and is_retrigger_floating:
                # Unfloat and try to restore state
                niri_action(f"move-window-to-tiling --id {retrigger_id}")
                prev_exists, prev_wh = read_tmp_data(STATE_FOLDER_PATH, f"{retrigger_id}.state", delete_on_read=True)
                if prev_exists and ENABLE_WIDTH_RESTORE:
                    niri_action(f"set-window-width {prev_wh[0]} --id {retrigger_id}")

            elif ENABLE_REFLOAT and not is_retrigger_floating:
                # Re-float window & record width for restore
                niri_action(f"move-window-to-floating --id {retrigger_id}")
                if ENABLE_WIDTH_RESTORE:
                    rt_win_width, rt_win_height = retrigger_win_info["layout"]["window_size"]
                    write_tmp_data(STATE_FOLDER_PATH, f"{retrigger_id}.state", (rt_win_width, rt_win_height))

        raise SystemExit()


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle missing offsets

# Bail if no window is focused
win_info = get_focused_window()
if win_info is None:
    raise SystemExit()
win_id = win_info["id"]

# Odd detail:
# The niri 'move-floating-window' command uses a co-ordinate system which
# is (potentially) offset from the 'global' screen co-ordinates.
# This leads to a discrepancy between slurp coords (which are global) and niri.
# Fortuneately, niri *does* report the global coords when checking window state,
# which gives us a way to determine the offset, which is what we're doing here.
is_missing_offset = X_OFFSET is None or Y_OFFSET is None
if is_missing_offset:
    tmp_xy_filename = "xyoffsets.info"
    ok_tmp_offsets, tmp_xy_offsets = read_tmp_data(STATE_FOLDER_PATH, tmp_xy_filename)
    if ok_tmp_offsets and isinstance(tmp_xy_offsets, list):
        tmp_x_offset, tmp_y_offset = tmp_xy_offsets
        X_OFFSET = tmp_x_offset if X_OFFSET is None else X_OFFSET
        Y_OFFSET = tmp_y_offset if Y_OFFSET is None else Y_OFFSET
        is_missing_offset = False

    else:
        # Move (floated) window to (0,0) and read actual position to get offsets
        niri_action(f"move-window-to-floating --id {win_id}")
        niri_action(f"move-floating-window --id {win_id} -x 0 -y 0")
        zeroed_win_info = get_focused_window()
        zeroed_x, zeroed_y = zeroed_win_info["layout"]["tile_pos_in_workspace_view"]
        zeroed_x, zeroed_y = [int(value) for value in (zeroed_x, zeroed_y)]
        X_OFFSET = zeroed_x if X_OFFSET is None else X_OFFSET
        Y_OFFSET = zeroed_y if Y_OFFSET is None else Y_OFFSET

        # Undo effect of zeroing, in case user wants to cancel
        orig_is_floating = win_info["is_floating"]
        if orig_is_floating:
            orig_x, orig_y = win_info["layout"]["tile_pos_in_workspace_view"]
            orig_x, orig_y = (orig_x - zeroed_x), (orig_y - zeroed_y)
            niri_action(f"move-floating-window --id {win_id} -x {orig_x} -y {orig_y}")
        else:
            orig_width, _ = win_info["layout"]["window_size"]
            niri_action(f"move-window-to-tiling --id {win_id}")
            niri_action(f"set-window-width {orig_width} --id {win_id}")

        # Provide feedback to user & store offset for re-use
        msg = ["Missing X/Y offsets!", "To avoid warning on start-up, add flags:", f"-xo {zeroed_x} -yo {zeroed_y}"]
        print(*msg, sep="\n")
        notify("\n".join(msg))
        write_tmp_data(STATE_FOLDER_PATH, tmp_xy_filename, (X_OFFSET, Y_OFFSET))


# ---------------------------------------------------------------------------------------------------------------------
# %% Parse regions

# Get monitor sizing if needed for handling regions given as % values
monitor_w, monitor_h = 0, 0
if NEED_REGION_PIXEL_SCALING:
    monitor_info = get_focused_monitor()
    monitor_sizing_info = monitor_info["logical"]
    monitor_w, monitor_h = monitor_sizing_info["width"], monitor_sizing_info["height"]

# Parse region data
slurp_region_strs = []
for region_str in REGIONS:

    # Check inputs are reasonable
    xywh_str = region_str.split(" ")
    if len(xywh_str) != 4:
        notify(f"Error specifying region, expecting 4 entries, got:\n{xywh_str}")
        continue

    # Parse input strings into numbers (given as strings like '470' or '50%')
    x_str, y_str, w_str, h_str = xywh_str
    try:
        is_w_pct, w_float = parse_size_str(w_str)
        is_h_pct, h_float = parse_size_str(h_str)
        is_x_pct, x_float = parse_size_str(x_str)
        is_y_pct, y_float = parse_size_str(y_str)
    except ValueError:
        notify(f"Error parsing region, expected 4 numbers, got:\n{xywh_str}")
        continue

    # Get region w/h, which we need for relative positioning
    w_px = abs(w_float * (monitor_w - X_OFFSET) if is_w_pct else w_float)
    h_px = abs(h_float * (monitor_h - Y_OFFSET) if is_h_pct else h_float)

    # Handle x-positioning
    if is_x_pct:
        xa, xb = X_OFFSET, monitor_w - w_px
        x_pct = 1.0 + x_float if x_float < 0 else x_float
        x_px = xa * (1 - x_pct) + xb * x_pct
    else:
        x_px = (monitor_w - w_px + x_float) if x_float < 0 else (x_float + X_OFFSET)

    # Handle y-positioning
    if is_y_pct:
        ya, yb = Y_OFFSET, monitor_h - h_px
        y_pct = 1.0 + y_float if y_float < 0 else y_float
        y_px = ya * (y_pct) + yb * y_pct
    else:
        y_px = (monitor_h - h_px + y_float) if y_float < 0 else (y_float + Y_OFFSET)

    # Form final slurp-format string
    x_px, y_px, w_px, h_px = (max(0, round(val)) for val in (x_px, y_px, w_px, h_px))
    slurp_region_strs.append(f"{x_px},{y_px} {w_px}x{h_px}")


# ---------------------------------------------------------------------------------------------------------------------
# %% Float-to-region

# Get box selection from slurp
(box_x, box_y), (box_w, box_h) = run_slurp(slurp_region_strs, *SLURP_ARGS)
if box_w < SIZE_THRESHOLD or box_h < SIZE_THRESHOLD:
    notify(f"Error, region is too small!\nwh = ({box_w}, {box_h})")
    raise SystemExit()

# Record window width for restoring on un-float
if not win_info["is_floating"] and ENABLE_WIDTH_RESTORE:
    win_width, win_height = win_info["layout"]["window_size"]
    write_tmp_data(STATE_FOLDER_PATH, f"{win_id}.state", (win_width, win_height))

# Handle float-to-region
x_correct = max(0, box_x - X_OFFSET)
y_correct = max(0, box_y - Y_OFFSET)
niri_action(f"move-floating-window --id {win_id} -x {x_correct} -y {y_correct}")
niri_action(f"move-window-to-floating --id {win_id}")
niri_action(f"set-window-width {box_w} --id {win_id}")
niri_action(f"set-window-height {box_h} --id {win_id}")

# Handle potential workspace change
wspace_info = get_focused_workspace()
if wspace_info["id"] != win_info["workspace_id"]:
    niri_action(f"move-window-to-workspace {wspace_info['idx']} --window-id {win_id}")
