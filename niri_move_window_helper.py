#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# ---------------------------------------------------------------------------------------------------------------------
# %% Imports

import argparse
import subprocess
import json
from pathlib import Path
from os import environ

# ---------------------------------------------------------------------------------------------------------------------
# %% Handle script args

# Set up defaults
default_folder_path = Path(environ.get("XDG_RUNTIME_DIR", "/tmp")) / "niri_tweaks"
default_pad = 16

# Define script arguments
parser = argparse.ArgumentParser(
    description="Acts like a 'move-window-up/down/left/right' command, also works for floating windows",
)
parser.add_argument(
    "command",
    default="d",
    type=str,
    choices=["l", "r", "u", "d", "left", "right", "up", "down"],
    help="Specify window movement direction",
)
parser.add_argument(
    "-u",
    "--up_command",
    default="move-window-up-or-to-workspace-up",
    choices=[
        "move-window-up-or-to-workspace-up",
        "move-window-up",
        "move-window-to-workspace-up",
        "move-column-to-workspace-up",
    ],
    type=str,
    help="Command to run when moving (tiled) windows up",
)
parser.add_argument(
    "-d",
    "--down_command",
    default="move-window-down-or-to-workspace-down",
    choices=[
        "move-window-down-or-to-workspace-down",
        "move-window-down",
        "move-window-to-workspace-down",
        "move-column-to-workspace-down",
    ],
    type=str,
    help="Command to run when moving (tiled) windows down",
)
parser.add_argument(
    "-l",
    "--left_command",
    default="consume-or-expel-window-left",
    choices=["consume-or-expel-window-left", "swap-window-left", "move-column-left"],
    type=str,
    help="Command to run when moving (tiled) windows left",
)
parser.add_argument(
    "-r",
    "--right_command",
    default="consume-or-expel-window-right",
    choices=["consume-or-expel-window-right", "swap-window-right", "move-column-right"],
    type=str,
    help="Command to run when moving (tiled) windows right",
)
parser.add_argument(
    "-f",
    "--float_layout",
    nargs="+",  # means: 1 or more args
    type=int,
    default=[3, 3, 3],
    help="Number of rows per column for 'tiling' floating windows (default: 3 3 3)",
)
parser.add_argument(
    "-px",
    "--pad_x",
    nargs="+",
    type=int,
    default=[default_pad, default_pad],
    help=f"Amount of left/right padding for floating window placement (default: {default_pad} {default_pad})",
)
parser.add_argument(
    "-py",
    "--pad_y",
    nargs="+",
    type=int,
    default=[0, default_pad],
    help=f"Amount of top/bottom padding for floating window placement (default: 0 {default_pad})",
)
parser.add_argument(
    "-o",
    "--offset_xy",
    nargs=2,
    type=int,
    default=None,
    help="Window positioning offset. Needed to account for discrepancy between niri movement & position reporting",
)
parser.add_argument(
    "-m",
    "--allow_monitor_move",
    action="store_true",
    help="If set, allows windows to be moved to surrounding monitors when moved against workspace boundaries",
)
parser.add_argument(
    "-w",
    "--no_float_wspace",
    action="store_true",
    help="If set, disables the ability to move floating windows up/down workspaces",
)
parser.add_argument(
    "-c",
    "--no_float_scroll",
    action="store_true",
    help="If set, disables the ability for floating windows to scroll when moved against left/right edges",
)
parser.add_argument(
    "-p",
    "--folder_path",
    type=str,
    default=str(default_folder_path),
    help=f"Folder path used to store xyoffset data (default: {default_folder_path})",
)

# For convenience
args = parser.parse_args()
MOVE_COMMAND = args.command
L_CMD = args.left_command
R_CMD = args.right_command
U_CMD = args.up_command
D_CMD = args.down_command
FLOAT_LAYOUT = args.float_layout
XY_OFFSET = args.offset_xy
X_PAD = args.pad_x
Y_PAD = args.pad_y
ENABLE_MONITOR_MOVE = args.allow_monitor_move
ENABLE_FLOAT_MOVE_WORKSPACE = not args.no_float_wspace
ENABLE_FLOAT_SCROLL = not args.no_float_scroll
XYOFFSET_FOLDER_PATH = Path(args.folder_path)

# Handle padding values
if len(X_PAD) == 1:
    X_PAD = [X_PAD[0], X_PAD[0]]
if len(Y_PAD) == 1:
    Y_PAD = [Y_PAD[0], Y_PAD[0]]


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


def get_missing_focused_window() -> dict | None:
    """Helper used to get 'missing' window info, occurs when in overview, for example"""

    # Try to figure out which workspace we're on & get it's 'active window'
    all_wspace_info = get_all_workspaces_info()
    focused_wspace_info = {}
    for info in all_wspace_info:
        if info["is_focused"]:
            focused_wspace_info = info
            break
    active_window_id = focused_wspace_info.get("active_window_id", None)

    # Treat the 'active window' as the focused window
    focused_win_info = None
    for info in get_all_window_info():
        if info["id"] == active_window_id:
            focused_win_info = info
            break

    return focused_win_info


def get_all_window_info() -> list[dict]:
    resp = run_command("niri msg --json windows", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_all_workspaces_info() -> list[dict]:
    resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
    resp.check_returncode()
    return json.loads(resp.stdout)


def get_workspace_index_range(workspace_id: int) -> tuple[int, int, int]:

    # Try to figure out the current workspace index/monitor
    all_wspace_list = get_all_workspaces_info()
    curr_wspace_info = None
    for ws_info in all_wspace_list:
        if ws_info["id"] == workspace_id:
            curr_wspace_info = ws_info
            break
        pass
    if curr_wspace_info is None:
        notify("Error! Unable to determine current workspace...", timeout_ms=2500)
        raise SystemExit()
    curr_wspace_idx = curr_wspace_info["idx"]
    curr_output = curr_wspace_info["output"]

    # Find min/current/max indexing
    all_wspace_idx = [ws_info["idx"] for ws_info in all_wspace_list if ws_info["output"] == curr_output]
    min_wspace_idx = min(all_wspace_idx, default=1)
    max_wspace_idx = max(all_wspace_idx, default=1)

    return min_wspace_idx, curr_wspace_idx, max_wspace_idx


def notify(message: str, timeout_ms: int | None = None) -> None:
    notify_title = f"{Path(__file__).name}"
    subprocess.run(["notify-send", notify_title, message, *([] if timeout_ms is None else ["-t", str(timeout_ms)])])
    return


def write_tmp_data(save_folder: Path, save_name: str, data: tuple | list) -> None:
    """Write temporary (json-friendly) data. Used for storing offsets/window state"""
    save_folder.mkdir(exist_ok=True, parents=True)
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


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle tiled window moves

# Bail if there's no window
win_info = get_focused_window()
if win_info is None:
    win_info = get_missing_focused_window()
    if win_info is None:
        raise SystemExit(0)
is_floating = win_info["is_floating"]

# For convenience
IS_MOVE_LEFT = MOVE_COMMAND in ("l", "left")
IS_MOVE_RIGHT = MOVE_COMMAND in ("r", "right")
IS_MOVE_UP = MOVE_COMMAND in ("u", "up")
IS_MOVE_DOWN = MOVE_COMMAND in ("d", "down")

# Handle movement to other monitors
if ENABLE_MONITOR_MOVE and not is_floating:

    # For convenience
    get_col_idx = lambda info: info["layout"]["pos_in_scrolling_layout"][0]
    get_row_idx = lambda info: info["layout"]["pos_in_scrolling_layout"][1]

    # Get current window positioning
    curr_wsid = win_info["workspace_id"]
    curr_col_idx, curr_row_idx = win_info["layout"]["pos_in_scrolling_layout"]

    # Get info for windows on current workspace
    wins_on_wspace = (info for info in get_all_window_info() if info["workspace_id"] == curr_wsid)
    tile_win_info = [info for info in wins_on_wspace if not info["is_floating"]]
    num_wins_in_col = len([info for info in tile_win_info if get_col_idx(info) == curr_col_idx])

    # Only allow left/right move if window is alone in column
    is_solo_col = num_wins_in_col == 1
    if IS_MOVE_LEFT and is_solo_col:
        is_leftmost_col = curr_col_idx == 1
        if is_leftmost_col:
            niri_action("move-window-to-monitor-left")
            raise SystemExit(0)

    elif IS_MOVE_RIGHT and is_solo_col:
        win_col_idxs_list = [get_col_idx(info) for info in tile_win_info]
        max_col_idx = max(win_col_idxs_list, default=1)
        is_rightmost_col = curr_col_idx == max_col_idx
        if is_rightmost_col:
            niri_action("move-window-to-monitor-right")
            niri_action("move-column-to-first")
            raise SystemExit(0)

    # Get workspace indexing (needed for up/down checks)
    min_ws_idx, curr_ws_idx, max_ws_idx = get_workspace_index_range(curr_wsid)
    if IS_MOVE_UP:
        is_topmost_row = curr_row_idx == 1
        is_topmost_workspace = curr_ws_idx == min_ws_idx
        if is_topmost_row and is_topmost_workspace:
            niri_action("move-window-to-monitor-up")
            raise SystemExit(0)

    elif IS_MOVE_DOWN:
        is_bottommost_row = curr_row_idx == num_wins_in_col
        is_bottommost_workspace = curr_ws_idx >= (max_ws_idx - 1)
        if is_bottommost_row and is_bottommost_workspace:
            niri_action("move-window-to-monitor-down")
            raise SystemExit(0)
    pass

# Handle normal movement of tiled windows
if not is_floating:
    if IS_MOVE_LEFT:
        niri_action(L_CMD)
    elif IS_MOVE_RIGHT:
        niri_action(R_CMD)
    elif IS_MOVE_UP:
        niri_action(U_CMD)
    elif IS_MOVE_DOWN:
        niri_action(D_CMD)
    raise SystemExit(0)


# ---------------------------------------------------------------------------------------------------------------------
# %% Handle missing x/y offsets

is_missing_offset = XY_OFFSET is None
if is_missing_offset:
    tmp_xy_filename = "xyoffsets.info"
    ok_tmp_offsets, tmp_xy_offsets = read_tmp_data(XYOFFSET_FOLDER_PATH, tmp_xy_filename)
    if ok_tmp_offsets and isinstance(tmp_xy_offsets, list):
        XY_OFFSET = tmp_xy_offsets

    elif is_floating:
        # Move (floated) window to (0,0) and read actual position to get offsets
        win_id = win_info["id"]
        niri_action(f"move-floating-window --id {win_id} -x 0 -y 0")
        zeroed_win_info = get_focused_window()
        zeroed_x, zeroed_y = zeroed_win_info["layout"]["tile_pos_in_workspace_view"]
        zeroed_x, zeroed_y = [int(value) for value in (zeroed_x, zeroed_y)]
        XY_OFFSET = (zeroed_x, zeroed_y)

        # Undo effect of zeroing
        orig_x, orig_y = win_info["layout"]["tile_pos_in_workspace_view"]
        orig_x, orig_y = (orig_x - zeroed_x), (orig_y - zeroed_y)
        niri_action(f"move-floating-window --id {win_id} -x {orig_x} -y {orig_y}")

        # Provide feedback to user & store offset for re-use
        msg = ["Missing X/Y offsets!", "To avoid warning on start-up, add flags:", f"-xo {zeroed_x} -yo {zeroed_y}"]
        print(*msg, sep="\n")
        notify("\n".join(msg), timeout_ms=5000)
        write_tmp_data(XYOFFSET_FOLDER_PATH, tmp_xy_filename, XY_OFFSET)
    else:
        notify("Error! Got unexpected tiled window...")
        raise SystemExit()

# For convenience
X_OFFSET, Y_OFFSET = XY_OFFSET


# ---------------------------------------------------------------------------------------------------------------------
# %% Handling floating

# Get monitor size
output_resp = run_command("niri msg --json focused-output", capture_output=True, text=True)
monitor_info = json.loads(output_resp.stdout)
monitor_w, monitor_h = monitor_info["logical"]["width"], monitor_info["logical"]["height"]
x1_pad, x2_pad = X_PAD[0:2]
y1_pad, y2_pad = Y_PAD[0:2]

# Get normalized window position
win_w, win_h = win_info["layout"]["tile_size"]
win_x_px, win_y_px = win_info["layout"]["tile_pos_in_workspace_view"]
max_x_px = max(monitor_w - win_w - x1_pad - x2_pad - X_OFFSET, 1)
max_y_px = max(monitor_h - win_h - y1_pad - y2_pad - Y_OFFSET, 1)

# Handle out-of-bounds left/right
curr_x_norm = (win_x_px - x1_pad - X_OFFSET) / max_x_px
if curr_x_norm > 1.0 or curr_x_norm < 0.0:
    pass
curr_x_norm = min(1.0, max(0, curr_x_norm))

# Handle out-of-bounds up/down
curr_y_norm = (win_y_px - y1_pad - Y_OFFSET) / max_y_px
if curr_y_norm > 1.0 or curr_y_norm < 0.0:
    pass
curr_y_norm = min(1.0, max(0, curr_y_norm))

# Figure out column position
rows_per_column = [n for n in FLOAT_LAYOUT if n > 0]
num_cols = len(rows_per_column)
col_x_norm_list = [idx / (num_cols - 1) for idx, _ in enumerate(rows_per_column)] if num_cols > 1 else [0.5]
curr_col_idx = round(curr_x_norm * (num_cols - 1))

# Find new x/y positioning
new_x_px, new_y_px, num_rows = 0, 0, 1
if IS_MOVE_LEFT or IS_MOVE_RIGHT:

    # Figure out new column position
    new_col_idx = (curr_col_idx - 1) if IS_MOVE_LEFT else (curr_col_idx + 1)
    new_col_idx = max(0, min(new_col_idx, (num_cols - 1)))

    # Snap to closest row position, based on new column position
    num_rows = rows_per_column[new_col_idx]
    new_row_idx = round(curr_y_norm * (num_rows - 1))

    # Try to scroll the workspace if movement doesn't change our position
    if ENABLE_FLOAT_SCROLL and (new_col_idx == curr_col_idx):
        niri_action("focus-tiling")
        if IS_MOVE_LEFT:
            niri_action("focus-column-left")
        elif IS_MOVE_RIGHT:
            niri_action("focus-column-right")
        niri_action("focus-floating")
    pass

else:
    # Figure out which column we're in (e.g. closest-to) for determining row count
    new_col_idx = max(0, min(curr_col_idx, num_cols - 1))

    # Figure out new row position from moving up or down
    num_rows = rows_per_column[new_col_idx]
    max_row_idx = num_rows - 1
    curr_row_idx = round(curr_y_norm * (num_rows - 1))
    new_row_idx = (curr_row_idx - 1) if IS_MOVE_UP else (curr_row_idx + 1)
    new_row_idx = max(0, min(new_row_idx, num_rows - 1))

    # Move up/down workspaces when we bump into top/bottom edges
    if ENABLE_FLOAT_MOVE_WORKSPACE and (new_row_idx == curr_row_idx):

        # Move up/down workspaces and set y-position to 'wrap-around' as we make the move
        if IS_MOVE_UP:
            # Make sure we're not on the first workspace
            # -> Otherwise, we can't move up and wrap-around will look wrong
            wspace_resp = run_command("niri msg --json workspaces", capture_output=True, text=True)
            wspace_info = json.loads(wspace_resp.stdout)
            curr_wsid = win_info["workspace_id"]
            curr_ws_idx = max([ws["idx"] for ws in wspace_info if ws["id"] == curr_wsid], default=1)
            if curr_ws_idx > 1:
                niri_action("move-window-to-workspace-up")
                new_row_idx -= 1
            pass
        elif IS_MOVE_DOWN:
            niri_action("move-window-to-workspace-down")
            new_row_idx += 1
        new_row_idx = new_row_idx % num_rows
    pass

# Compute new xy position based on new grid location
new_x_norm = (new_col_idx / (num_cols - 1)) if num_cols > 1 else 0.5
new_x_px = new_x_norm * max_x_px + x1_pad
new_y_norm = (new_row_idx / (num_rows - 1)) if num_rows > 1 else 0.5
new_y_px = new_y_norm * max_y_px + y1_pad

# Shift window position on-screen
niri_action(f"move-floating-window -x {round(new_x_px)} -y {round(new_y_px)}")
