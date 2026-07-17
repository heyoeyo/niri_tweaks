#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# ---------------------------------------------------------------------------------------------------------------------
# %% Imports

import argparse
import json
import os
import subprocess

from pathlib import Path
from time import sleep, perf_counter
from socket import socket, AF_UNIX, SOCK_STREAM
from signal import signal, SIGTERM
from enum import Enum

# Potentially missing lib (requires python v3.11+, but v3.10 is still considered supported!)
HAS_TOML_LIB = True
try:
    import tomllib
except ImportError:
    HAS_TOML_LIB = False


# ---------------------------------------------------------------------------------------------------------------------
# %% Args

# Define script arguments
parser = argparse.ArgumentParser(
    description="Script which makes niri tile windows up to a certain stack height, for a given range of columns",
)
parser.add_argument(
    "-cfg",
    "--config_path",
    type=str,
    default="~/.config/niri/tilemod_config.toml",
    help="Path to .json or .toml config file (default: '~/.config/niri/tilemod_config.toml')",
)
parser.add_argument(
    "-n",
    "--num_stack",
    default=2,
    type=int,
    help="Number of windows to stack in columns (default 2). Use 0 or 1 to disable stacking",
)
parser.add_argument(
    "-b",
    "--column_bounds",
    nargs=2,
    default=[2, 2],
    type=int,
    help="Column start/end range where tiling should occur (default: 2 2), niri indexing starts at 1",
)
parser.add_argument(
    "-rtl",
    "--right_to_left",
    action="store_true",
    help="Open windows in right-to-left order",
)
parser.add_argument(
    "-m",
    "--apply_to_moved_windows",
    action="store_true",
    help="When a window is moved into another workspace, treat it as a newly spawned window",
)
parser.add_argument(
    "--autostack_last_column_only",
    action="store_true",
    help="Only enable auto-stacking when the new window is opened in the last-most column",
)
parser.add_argument(
    "--action_maximize",
    type=str,
    default="MaximizeColumn",
    choices=["MaximizeColumn", "MaximizeWindowToEdges", "FullscreenWindow"],
    help="Set which maximization action to use (default: MaximizeColumn)",
)
parser.add_argument(
    "--no_outer_stack",
    action="store_true",
    help="Disable auto-stacking to the right if column is available (or left, when RTL is enabled)",
)
parser.add_argument(
    "--no_maximize_solos",
    action="store_true",
    help="Disable auto-maximize of first window opened on a workspace",
)
parser.add_argument(
    "--no_maximize_on_close",
    action="store_true",
    help="Disable re-maximize when only one window remains",
)
parser.add_argument(
    "--no_collapse_on_open",
    action="store_true",
    help="Disable collapse of solo maximized window when opening a second window",
)
parser.add_argument(
    "--no_config_reload",
    action="store_true",
    help="Disable ability to reload tiling config by opening the overview",
)
parser.add_argument(
    "-d",
    "--delay_startup_ms",
    default=250,
    type=int,
    help="Number of milliseconds to delay before listening to niri IPC (default: 500)",
)
parser.add_argument("-k", "--config_printout", action="store_true", help="Print out the active config (in terminal)")
parser.add_argument("--notify_unexpected", action="store_true", help="Enable notifications for unexpected behavior")

# Get script configs
args, unknown_args = parser.parse_known_args()
ARG_CONFIG_PATH = Path(args.config_path).expanduser()
ARG_NUM_STACK = args.num_stack
ARG_COLUMN_TILING_BOUNDS = args.column_bounds
ARG_ALLOW_OUTER_STACK = not args.no_outer_stack
ARG_ENABLE_RTL = args.right_to_left
ARG_MAXIMIZE_SOLOS_ON_OPEN = not args.no_maximize_solos
ARG_MAXIMIZE_SOLOS_ON_CLOSE = not args.no_maximize_on_close
ARG_COLLAPSE_SOLOS_ON_OPEN = not args.no_collapse_on_open
ARG_APPLY_TO_MOVED_WINDOWS = args.apply_to_moved_windows
ARG_AUTOSTACK_LAST_ONLY = args.autostack_last_column_only
ARG_ACTION_MAXIMIZE = args.action_maximize
STARTUP_DELAY_MS = args.delay_startup_ms
ENABLE_CONFIG_RELOAD = not args.no_config_reload
RUN_CONFIG_PRINTOUT = args.config_printout
NOTIFY_UNEXPECTED = args.notify_unexpected

# Handle startup delay (prevent listening to niri during potentially busy startup)
if STARTUP_DELAY_MS > 0:
    sleep(STARTUP_DELAY_MS / 1000)


# ---------------------------------------------------------------------------------------------------------------------
# %% Classes


class NiriIPC:
    """Helper used to read/write from niri IPC"""

    def __init__(self, socket_path: str, buffer_size: int = 4096):
        niri_socket = socket(AF_UNIX, SOCK_STREAM)
        niri_socket.connect(socket_path)

        self._writer = niri_socket.makefile("w", buffering=buffer_size)
        self._reader = niri_socket.makefile("r", buffering=buffer_size)
        self._socket = niri_socket
        self._batched_actions_list = []
        self._batched_action_names = []

    def _parse_response(self) -> tuple[bool, dict | str]:

        # Parse 'Ok' response
        resp_str = self._reader.readline()
        resp_dict = json.loads(resp_str)
        resp_data = resp_dict.get("Ok", None)
        is_ok = resp_data is not None
        if is_ok:
            return is_ok, resp_data

        # Handle 'Err' response
        resp_data = resp_dict.get("Err", None)
        return is_ok, resp_data

    def batch_action(self, action: str, **kwargs):
        """Queue up an action, without executing immediately. Use .commit_batch() to execute"""
        action_json_str = json.dumps({"Action": {action: kwargs}}, indent=None, separators=(",", ":"))
        self._batched_actions_list.append(action_json_str)
        self._batched_action_names.append(action)
        return self

    def commit_batch(self) -> list[tuple[str, bool, str]]:

        # Bail if no actions have been batched
        num_actions = len(self._batched_actions_list)
        if num_actions == 0:
            return []

        # Write single (batched) action string
        batched_action_str = "\n".join(self._batched_actions_list)
        batched_names = self._batched_action_names
        self._batched_actions_list = []
        self._batched_action_names = []
        self._writer.write(batched_action_str)
        self._writer.write("\n")
        self._writer.flush()

        # Read response for each batch item
        return [(name, self._parse_response()) for name in batched_names]

    def message(self, message: str) -> tuple[bool, dict | str]:
        self._writer.write(f'"{message}"\n')
        self._writer.flush()
        return self._parse_response()

    def close(self):
        self._writer.close()
        self._reader.close()
        self._socket.close()

    def read_event_stream(self) -> tuple[str, dict]:

        # Try to request event stream
        ok_stream, evt_resp = self.message("EventStream")
        if not ok_stream:
            raise ConnectionError(f"Error starting EventStream\n{evt_resp}")

        # Read responses (delimited by '\n')
        self._writer.close()
        for line in self._reader:
            for evt_message in line.splitlines():
                msg_json = json.loads(evt_message)
                evt_name = tuple(msg_json.keys())[0]
                evt_data = msg_json.get(evt_name, {})
                yield evt_name, evt_data

        return


class WindowSizeState(Enum):
    NOT_MAXIMIZED = 0
    MAX_COLUMN = 1
    MAX_TO_EDGES = 2
    FULLSCREEN = 3


# ---------------------------------------------------------------------------------------------------------------------
# %% Helpers


def get_tiling_config(tiling_configs_dict: dict, workspace_dict: dict, outputs_dict: dict) -> tuple[str, dict]:
    """Helper used to select tiling config. Checks workspace properties before monitor properties!"""

    # Get workspace/monitor-specific config
    match_key, augment_cfg = None, {}
    for section_key, section_properties_dict in (("workspaces", workspace_dict), ("outputs", outputs_dict)):
        for prop_name, property_entries in tiling_configs_dict[section_key].items():
            if prop_name not in section_properties_dict.keys():
                continue
            curr_prop_value = str(section_properties_dict[prop_name])
            if curr_prop_value in property_entries:
                augment_cfg = property_entries[curr_prop_value]
                match_key = f"{section_key}.{prop_name}.{curr_prop_value}"
                break

        # Break outer loop (e.g. if we find a workspace match first, ignore monitor match)
        if match_key is not None:
            break

    # Fill in missing match key
    if match_key is None:
        match_key = "default"

    # Return specific tiling config
    default_cfg = tiling_configs_dict["default"]
    return match_key, {**default_cfg, **augment_cfg}


def load_user_config(config_path: Path, has_tomllib: bool = False, raise_errors: bool = True) -> tuple[bool, dict]:
    """Helper used to load .toml or .json config file, with basic error handling"""

    # Initilize outputs
    ok_config, loaded_config = False, {}

    config_file_ext = config_path.suffix.lower()
    if config_file_ext == ".toml":
        if not has_tomllib:
            notify("Error, no support for .toml config\n(requires python 3.11+)")
            raise ModuleNotFoundError("No support for .toml file (requires python 3.11+). Please use .json instead")
        try:
            with open(config_path, "rb") as in_file:
                loaded_config = tomllib.load(in_file)
            ok_config = True
        except tomllib.TOMLDecodeError as err:
            notify("Error parsing toml config!\nRun in terminal to see more details")
            if raise_errors:
                raise err

    elif config_file_ext == ".json":
        try:
            with open(config_path, "r") as in_file:
                loaded_config = json.load(in_file)
            ok_config = True
        except json.JSONDecodeError as err:
            notify("Error parsing json config!\nRun in terminal to see more details")
            if raise_errors:
                raise err

    return ok_config, loaded_config


def update_working_config(base_config: dict[str, dict], update_config: dict[str, dict]) -> dict[str, dict]:
    """Helper used to update a base config with (potentially sparse) update data"""
    new_config_dict = {}
    for key in base_config.keys():
        new_config_dict[key] = {**base_config[key], **update_config.get(key, {})}
    return new_config_dict


def notify(message: str) -> None:
    notify_title = f"{Path(__file__).name}"
    subprocess.run(["notify-send", notify_title, message])
    return


def get_tiled_workspace_windows(multi_window_dict: dict[int, dict], workspace_id: int) -> dict[int, dict]:
    is_tiled_in_wspace = lambda win_info: win_info["workspace_id"] == workspace_id and not win_info["is_floating"]
    return {win_id: win_info for win_id, win_info in multi_window_dict.items() if is_tiled_in_wspace(win_info)}


def get_focused_id(multi_info_dict: dict[int, dict]) -> int | None:
    focused_id = None
    for data in multi_info_dict.values():
        if data["is_focused"]:
            focused_id = data["id"]
            break
    return focused_id


def get_missing_size_state(
    single_window_dict: dict,
    monitor_info: dict,
    max_w_threshold: float = 0.8,
) -> WindowSizeState:
    """Helper used to guess at missing maximization/fullscreen window state"""

    monitor_w = monitor_info["logical"]["width"]
    monitor_h = monitor_info["logical"]["height"]
    win_w_px, win_h_px = single_window_dict["layout"]["tile_size"]
    gap_w, gap_h = (monitor_w - int(win_w_px)), (monitor_h - int(win_h_px))

    win_state = WindowSizeState.NOT_MAXIMIZED
    if (gap_w < 5) and (gap_h < 5):
        win_state = WindowSizeState.FULLSCREEN
    elif (gap_w < 5) or (gap_h < 5):
        win_state = WindowSizeState.MAX_TO_EDGES
    elif (win_w_px / monitor_w) > max_w_threshold:
        win_state = WindowSizeState.MAX_COLUMN

    return win_state


def get_rows_per_column(multi_window_dict: dict[int, dict]) -> dict[int, int]:
    """Get row count per column as a dictionary for key/value format: {column_index: row_count}"""

    col_count_per_idx = {}
    for win_info in multi_window_dict.values():
        if win_info["is_floating"]:
            continue
        col_idx = win_info["layout"]["pos_in_scrolling_layout"][0]
        if col_idx not in col_count_per_idx.keys():
            col_count_per_idx[col_idx] = 0
        col_count_per_idx[col_idx] += 1

    return col_count_per_idx


def sigterm_to_interrupt(signum, frame):
    raise InterruptedError


# ---------------------------------------------------------------------------------------------------------------------
# %% Parse config

# Define base/default config, based on script args
base_configs_dict = {
    "default": {
        "num_stack": ARG_NUM_STACK,
        "column_bounds": ARG_COLUMN_TILING_BOUNDS,
        "maximize_solos_on_open": ARG_MAXIMIZE_SOLOS_ON_OPEN,
        "maximize_solos_on_close": ARG_MAXIMIZE_SOLOS_ON_CLOSE,
        "collapse_solos_on_open": ARG_COLLAPSE_SOLOS_ON_OPEN,
        "allow_outer_stack": ARG_ALLOW_OUTER_STACK,
        "apply_to_moved_windows": ARG_APPLY_TO_MOVED_WINDOWS,
        "autostack_last_column_only": ARG_AUTOSTACK_LAST_ONLY,
        "right_to_left": ARG_ENABLE_RTL,
        "action_maximize": ARG_ACTION_MAXIMIZE,
        "disabled": False,
    },
    "outputs": {},
    "workspaces": {},
}

# Try to load/parse from config file
last_config_modify_time = 0
all_configs_dict = {**base_configs_dict}
if ARG_CONFIG_PATH.exists():
    last_config_modify_time = ARG_CONFIG_PATH.stat().st_mtime
    _, loaded_config = load_user_config(ARG_CONFIG_PATH, HAS_TOML_LIB, raise_errors=True)
    all_configs_dict = update_working_config(base_configs_dict, loaded_config)
    print("", "Loaded config file:", ARG_CONFIG_PATH, sep="\n")
else:
    print("", "No config file found:", ARG_CONFIG_PATH, "-> Will use default config", sep="\n")


# ---------------------------------------------------------------------------------------------------------------------
# %% Setup

# Set up separate connections for sending commands during event stream
SCRIPTNAME = Path(__file__).name
PATH_SOCKET = os.environ["NIRI_SOCKET"]
if not os.path.exists(PATH_SOCKET):
    raise FileNotFoundError(f"Cannot connect to niri socket: {PATH_SOCKET}")
event_stream_reader = NiriIPC(PATH_SOCKET)
niri = NiriIPC(PATH_SOCKET)
print("", f"({SCRIPTNAME}) - Opened niri IPC connection", sep="\n")

# Check versioning
response_ok, response_version = niri.message("Version")
expected_version = "26.04"
if (not response_ok) or (expected_version not in response_version.get("Version")):
    version_msg = f"Expecting version {expected_version}, got: {response_version.get('Version', None)}"
    if NOTIFY_UNEXPECTED:
        sleep(1)
        notify(version_msg)
    print("", version_msg, sep="\n")

# Initialize global state
is_overview_open: bool = False
focused_win_id: int | None = None
focused_wspace_id: int | None = None
all_win_dict: dict[int, dict] = {}
all_wspace_dict: dict[int, dict] = {}
all_monitor_dict: dict[str, dict] = {}


# ---------------------------------------------------------------------------------------------------------------------
# %% *** IPC listening loop ***

# Convert SIGTERM into python interrupt error for graceful shutdown
signal(SIGTERM, sigterm_to_interrupt)

try:
    # Print out active config and close. Used for debugging
    if RUN_CONFIG_PRINTOUT:
        _, response_focused_output = niri.message("FocusedOutput")
        _, response_workspaces = niri.message("Workspaces")
        curr_wspace_dict = [info for info in response_workspaces["Workspaces"] if info["is_focused"]][0]
        curr_monitor_dict = response_focused_output["FocusedOutput"]
        match_key, config = get_tiling_config(all_configs_dict, curr_wspace_dict, curr_monitor_dict)
        print("", f"Tiling config: {match_key}", sep="\n")
        print(json.dumps(config, indent=2) if not config["disabled"] else "***DISABLED***", flush=True)
        raise KeyboardInterrupt()

    # For all event docs, see: https://niri-wm.github.io/niri/niri_ipc/enum.Event.html
    timestamp_ms = int(1000 * perf_counter())
    for evt_name, evt_data in event_stream_reader.read_event_stream():

        # Uncomment for debugging
        # new_timestamp = int(1000 * perf_counter())
        # time_elapsed_ms, timestamp_ms = (new_timestamp - timestamp_ms), new_timestamp
        # if time_elapsed_ms > 250:
        #     print("", f"Time elapsed (ms): {time_elapsed_ms}", sep="\n", flush=True)
        # print("EVENT:", evt_name, flush=True)
        # print(evt_data)

        # Reset event state
        new_win_dict = None
        closed_win_dict = None
        is_win_move_wspace_event = False

        # Handle events
        if "WindowFocusChanged" == evt_name:
            evt_win_id = evt_data["id"]
            if focused_win_id is not None:
                all_win_dict[focused_win_id]["is_focused"] = False
            if evt_win_id is not None:
                all_win_dict[evt_win_id]["is_focused"] = True
            focused_win_id = evt_win_id

        elif "WindowFocusTimestampChanged" == evt_name:
            # Very noisy event but not needed, so skip it. Usage would look like:
            #   all_win_dict[evt_data["id"]]["focus_timestamp"] = evt_data["focus_timestamp"]
            pass

        elif "WorkspaceActiveWindowChanged" == evt_name:
            # Very noisy event but not needed, so skip it. Usage would look like:
            #   all_wspace_dict[evt_data["workspace_id"]]["active_window_id"] = evt_data["active_window_id"]
            pass

        elif "WindowOpenedOrChanged" == evt_name:
            # Confusing event! This triggers when a new window is opened but...
            # - also triggers if certain window properties change (e.g. title, is_floating, workspace_id)
            # - does NOT trigger for all property changes (e.g. is_focused, layout)
            # - will trigger on drag-start/end with floating windows
            evt_win_data = evt_data["window"]
            evt_win_id = evt_win_data["id"]

            # Check for new window vs. moved window events
            is_new_window = evt_win_id not in all_win_dict.keys()
            if not is_new_window:
                is_win_move_wspace_event = evt_win_data["workspace_id"] != all_win_dict[evt_win_id]["workspace_id"]
            if is_new_window or is_win_move_wspace_event:
                new_win_dict = evt_win_data

            # Update focus, if needed
            if evt_data["window"]["is_focused"]:
                if focused_win_id is not None:
                    all_win_dict[focused_win_id]["is_focused"] = False
                focused_win_id = evt_win_id

            # Record new/updated window data
            all_win_dict[evt_win_id] = evt_win_data

        elif "WindowClosed" == evt_name:
            evt_win_id = evt_data["id"]
            if focused_win_id == evt_win_id:
                focused_win_id = None
            closed_win_dict = all_win_dict.pop(evt_win_id)

        elif "WindowUrgencyChanged" == evt_name:
            all_win_dict[evt_data["id"]]["is_urgent"] = evt_data["urgent"]

        elif "WindowLayoutsChanged" == evt_name:
            for evt_win_id, evt_new_layout in evt_data["changes"]:
                all_win_dict[evt_win_id]["layout"] = evt_new_layout

        elif "WorkspaceActivated" == evt_name:
            if evt_data["focused"]:
                evt_wspace_id = evt_data["id"]
                if focused_wspace_id is not None:
                    all_wspace_dict[focused_wspace_id]["is_focused"] = False
                if evt_wspace_id is not None:
                    all_wspace_dict[evt_wspace_id]["is_focused"] = True
                focused_wspace_id = evt_wspace_id
            pass

        elif "WorkspaceUrgencyChanged" == evt_name:
            all_wspace_dict[evt_data["id"]]["is_urgent"] = evt_data["urgent"]

        elif "OverviewOpenedOrClosed" == evt_name:
            is_overview_open = evt_data["is_open"]

            # Reload config if file has changed
            if ENABLE_CONFIG_RELOAD and ARG_CONFIG_PATH.exists():
                new_config_modify_time = ARG_CONFIG_PATH.stat().st_mtime
                if new_config_modify_time > last_config_modify_time:
                    last_config_modify_time = new_config_modify_time
                    ok_config, loaded_config = load_user_config(ARG_CONFIG_PATH, HAS_TOML_LIB, raise_errors=False)
                    if ok_config:
                        all_configs_dict = update_working_config(base_configs_dict, loaded_config)
                        notify("Config reloaded!")
                pass
            pass

        elif "WorkspacesChanged" == evt_name:
            # Signals re-write of workspace data. Event data format: {"workspaces": [... list of workspace dicts ...]}
            all_wspace_dict = {data["id"]: data for data in evt_data["workspaces"]}
            focused_wspace_id = get_focused_id(all_wspace_dict)

        elif "WindowsChanged" == evt_name:
            # Signals re-write of window data. Event data format: {"windows": [... list of window dicts ...]}
            all_win_dict = {data["id"]: data for data in evt_data["windows"]}
            focused_win_id = get_focused_id(all_win_dict)

        elif "ConfigLoaded" == evt_name:
            # We'll re-read monitor info on config changes (not clear if there is an event for attaching monitors?)
            ok_monitors, outputs_data = niri.message("Outputs")
            if not ok_monitors:
                notify("Error getting monitor data...")
                continue
            all_monitor_dict = outputs_data["Outputs"]

        elif evt_name in (
            "CastStartedOrChanged",
            "CastStopped",
            "CastsChanged",
            "KeyboardLayoutSwitched",
            "KeyboardLayoutsChanged",
            "ScreenshotCaptured",
        ):
            # Do nothing
            pass

        else:
            print("Unknown event:", evt_name)
            if NOTIFY_UNEXPECTED:
                notify("Unknown evemt: {evt_name}")

        # .............................................................................................................
        # %% Window management

        # Handle post-processing after window close
        if closed_win_dict is not None:

            # Ignore closing of floating windows (don't affect tiling)
            if closed_win_dict["is_floating"]:
                continue

            # Get active config
            curr_wspace_id = closed_win_dict["workspace_id"]
            curr_wspace_dict = all_wspace_dict[curr_wspace_id]
            curr_monitor_dict = all_monitor_dict[curr_wspace_dict["output"]]
            _, config = get_tiling_config(all_configs_dict, curr_wspace_dict, curr_monitor_dict)
            if config["disabled"]:
                continue

            # Handle re-maximizing solo windows
            tile_win_dict = get_tiled_workspace_windows(all_win_dict, curr_wspace_id)
            if config["maximize_solos_on_close"] and len(tile_win_dict) == 1:
                solo_id = tuple(tile_win_dict.keys())[0]
                solo_win_size_state = get_missing_size_state(tile_win_dict[solo_id], curr_monitor_dict)
                if solo_win_size_state == WindowSizeState.NOT_MAXIMIZED:
                    if focused_win_id != solo_id:
                        niri.batch_action("FocusWindow", id=solo_id)
                    niri.batch_action(config["action_maximize"])
                    niri.commit_batch()
                pass

        # *** New window event ***
        if new_win_dict is not None:

            # Get window location data
            curr_wspace_id = new_win_dict["workspace_id"]
            if curr_wspace_id is None:  # This happens when dragging windows!
                curr_wspace_id = focused_wspace_id
            curr_wspace_dict = all_wspace_dict[curr_wspace_id]
            curr_monitor_dict = all_monitor_dict[curr_wspace_dict["output"]]

            # Ignore floats or windows that seem to be created with window rules (don't want to interfere)
            new_win_size_state = get_missing_size_state(new_win_dict, curr_monitor_dict)
            is_already_maximized = new_win_size_state != WindowSizeState.NOT_MAXIMIZED
            is_on_another_wspace = curr_wspace_id != focused_wspace_id
            if new_win_dict["is_floating"] or is_already_maximized or is_on_another_wspace:
                continue

            # Get active tiling config (can be different for workspaces/monitors)
            _, config = get_tiling_config(all_configs_dict, curr_wspace_dict, curr_monitor_dict)
            if config["disabled"]:
                continue

            # Skip behavior if the window is 'new' because it moved workspaces, if configured
            if is_win_move_wspace_event and not config["apply_to_moved_windows"]:
                continue

            # Get (tiled-only) windows on workspace of new window, since that's all we care about
            tile_win_dict = get_tiled_workspace_windows(all_win_dict, curr_wspace_id)
            num_tile_wins = len(tile_win_dict)

            # Important note (as of v26.04):
            # When a new window appears, it will report itself as being in row 1 of the
            # column to the right of the current focused window, even if there is already
            # a window there (i.e it will report a duplicated column/row index).
            # For example if we have windows A and B but are focused on A, like: [A-focused] [B]
            # and spawn a window 'C' like: [A] [C-focused] [B], then:
            # [A] has xy: (1,1), [B] *still* has xy: (2,1) and [C] *also* has xy: (2,1)
            # -> This will mess up neighbouring window checks if we're not careful!

            # Get rows per column count on current workspace
            new_win_col_idx = new_win_dict["layout"]["pos_in_scrolling_layout"][0]
            rows_per_column_dict = get_rows_per_column(tile_win_dict)
            rows_per_column_dict[new_win_col_idx] -= 1  # Don't count the new window itself
            if rows_per_column_dict[new_win_col_idx] == 0:
                rows_per_column_dict.pop(new_win_col_idx)

            # Figure out the surrounding column indices
            col_tiling_bounds, num_stack = config["column_bounds"][0:2], config["num_stack"]
            side_col_iter = [(new_win_col_idx - 1, -1)]
            if config["allow_outer_stack"]:
                side_col_iter.append((new_win_col_idx, +1))

            # Adjust column index checks if we're in right-to-left mode
            enable_rtl = config["right_to_left"]
            if enable_rtl:
                if config["allow_outer_stack"]:
                    side_col_iter[1] = (new_win_col_idx - 2, -3)
                max_col_idx = max(rows_per_column_dict.keys(), default=0)
                col_tiling_bounds = [max_col_idx - idx + 1 for idx in col_tiling_bounds]

            # Disable stacking checks if we're not in the last-most column with last-only config
            if config["autostack_last_column_only"]:
                rightmost_col_idx = max(rows_per_column_dict.keys(), default=1)
                is_opened_last_col = (new_win_col_idx > rightmost_col_idx) if not enable_rtl else (new_win_col_idx == 2)
                if not is_opened_last_col:
                    side_col_iter = []

            # Check if we need to shift into another column
            start_colidx, end_colidx = sorted(col_tiling_bounds)
            need_shift_amt = 0
            for side_col_idx, shift_amt in side_col_iter:
                if side_col_idx not in rows_per_column_dict.keys():
                    continue
                if start_colidx <= side_col_idx <= end_colidx and rows_per_column_dict[side_col_idx] < num_stack:
                    need_shift_amt = shift_amt
                    break

            # Handle shifting
            new_win_id = new_win_dict["id"]
            is_focus_on_new_win = focused_win_id == new_win_id
            if need_shift_amt != 0:
                shift_cmd = "ConsumeOrExpelWindowLeft" if need_shift_amt < 0 else "ConsumeOrExpelWindowRight"
                for _ in range(abs(need_shift_amt) - 1):
                    niri.batch_action(shift_cmd, id=new_win_id)
                niri.batch_action(shift_cmd, id=new_win_id)

            elif enable_rtl:
                # Handle right-to-left movement (no stacking)
                if is_focus_on_new_win:
                    niri.batch_action("MoveColumnLeft")
                    niri.batch_action("FocusColumnRight")
                    niri.batch_action("FocusColumnLeft")
                else:
                    niri.batch_action("ConsumeOrExpelWindowLeft", id=new_win_id)
                    niri.batch_action("ConsumeOrExpelWindowLeft", id=new_win_id)

            # Handle solo-window maximization
            if config["maximize_solos_on_open"] and num_tile_wins == 1:
                if new_win_size_state == WindowSizeState.NOT_MAXIMIZED:
                    niri.batch_action("FocusWindow", id=new_win_id)
                    niri.batch_action(config["action_maximize"])
                    if not is_focus_on_new_win:
                        niri.batch_action("FocusWindow", id=focused_win_id)

            # Collapse maximized windows when no longer solo
            if config["collapse_solos_on_open"] and num_tile_wins == 2:
                other_win_id = [win_id for win_id in tile_win_dict.keys() if win_id != new_win_id][0]
                other_win_size_state = get_missing_size_state(tile_win_dict[other_win_id], curr_monitor_dict)
                if other_win_size_state != WindowSizeState.NOT_MAXIMIZED:
                    niri.batch_action("FocusWindow", id=other_win_id)
                    if other_win_size_state == WindowSizeState.MAX_COLUMN:
                        niri.batch_action("MaximizeColumn")
                    elif other_win_size_state == WindowSizeState.MAX_TO_EDGES:
                        niri.batch_action("MaximizeWindowToEdges")
                    # -> Could collapse fullscreen state, but probably not desired...
                    niri.batch_action("FocusWindow", id=focused_win_id)
                pass

            # Trigger all actions & report any errors
            action_responses = niri.commit_batch()
            for name_action, (ok_action, response_msg) in action_responses:
                if not ok_action:
                    notify(f"Action error: {name_action}\n{response_msg}")
                    print("Action error!", action_responses, sep="\n")

            pass

except ConnectionError as err:
    notify(str(err))

except (KeyboardInterrupt, InterruptedError):
    pass

except Exception as err:
    if NOTIFY_UNEXPECTED:
        notify(f"Unexpected error:\n{err}")
    raise err

finally:
    event_stream_reader.close()
    niri.close()
    print("", f"({SCRIPTNAME}) - Closed niri IPC connection", sep="\n")
