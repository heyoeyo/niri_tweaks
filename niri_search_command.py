#!/usr/bin/env python3

# niri_search_command.py
# This script is meant to help quickly find rarely used Niri commands.
# When called it uses [fuzzel](https://codeberg.org/dnkl/fuzzel) to allow the user
# to select a command.
# Once a command is selected it will be executed. Certain commands require
# additional user input in which case this script will use `fuzzel` a second time
# to query for more information.
# ```kdl
# Mod+Slash { spawn-sh "python3 /path/to/niri_search_command.py"; }
# ```
# Currently this does not support any commandline arguments.

import io
import json
import os
import socket
import subprocess
from typing import Any, ClassVar, Literal, Self, TypeAlias, TypedDict, TypeVar, cast


class Config:
    # Show Pointer in screenshots
    screenshot_show_pointer = True
    # Focus other workspace when moving Windows to it
    move_workspace_focus = True
    # prompt_optional_window_id = False
    prompt_for_optional_args = False


class NiriException(Exception): ...
class FuzzelNothingSelected(Exception): ...
class FuzzelInvalidInput(Exception): ...


def error_msg_exit(message: str):
    """
    Use notify-send to notify the user of any Errors.
    """
    notify_title = "Windowsearch Error!"
    subprocess.run(["notify-send", notify_title, message])
    raise SystemExit(message)


class ActionRequest(TypedDict):
    Action: dict[str, dict]

Request: TypeAlias = ( # noqa: UP040
    ActionRequest
    | Literal["Outputs"]
    | Literal["Windows"]
    | Literal["Version"]
    | Literal["Workspaces"]
    | Literal["Layers"]
    | Literal["KeyboardLayouts"]
    | Literal["FocusedOutput"]
    | Literal["FocusedWindow"]
    | Literal["PickWindow"]
    | Literal["PickColor"]
    | Literal["EventStream"]
    | Literal["ReturnError"]
    | Literal["OverviewState"]
    | Literal["Casts"]
)

# These are just for typechecking
class WindowResponse(TypedDict):
    id: int
    title: None | str
    app_id: None | str
    pid: None | int
    workspace_id: None | int
    is_focused: bool
    is_floating: bool
    is_urgent: bool
    layout: dict
    focus_timestamp: None | Any

class OutputResponse(TypedDict):
    name: str
    make: str
    model: str
    serial: None | str
    physical_size: None | list[int]
    modes: list[dict]
    current_mode: None | int
    is_custom_mode: bool
    vrr_supported: bool
    vrr_enabled: bool
    logical: None | dict
    max_bpc: None | int


class WorkspaceResponse(TypedDict):
    id: int
    idx: int
    name: None | str
    output: None | str
    is_urgent: bool
    is_active: bool
    is_focused: bool
    active_window_id: None | int


class NiriSocket:
    """
    Wrapper class for providing an abstraction around sending requests
    to Niri via sockets.

    Parameters
    ----------
    socket_path: str | None = None
        Path to the Niri socket. None means it will try to read it from
        the NIRI_SOCKET environment variable.
    """

    _sock: socket.socket
    _file: io.TextIOWrapper

    def __init__(self, socket_path: str | None = None) -> None:
        socket_path = socket_path or NiriSocket.get_niri_socket_path()
        # Sanity check
        is_bad_path = socket_path is None or str(socket_path) == ""
        assert not is_bad_path, "Cannot connect to niri, no socket path given..."

        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(socket_path)
        # The File wrapper is not technically needed but provides
        # a more convenient api around reading and writing to the socket.
        self._file = self._sock.makefile("rw")

    # enter and exit are just for using it as a context manager.
    def __enter__(self) -> Self:
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.close()

    def close(self):
        self._file.close()
        self._sock.close()

    @staticmethod
    def get_niri_socket_path() -> str | None:
        return os.environ.get("NIRI_SOCKET")

    def request(self, request: Request) -> dict:
        """
        Send a request to niri. Information about different requests can be found
        in the niri_ipc crate documentation.
        <https://niri-wm.github.io/niri/niri_ipc/enum.Request.html>

        Raises
        ------
        NiriException
            If the attempt to communicate with Niri was unsuccesfull.
        """
        request_body = f"{json.dumps(request)}\n"
        self._file.write(request_body)
        self._file.flush()
        ret = json.loads(self._file.readline())
        success = ret.get("Ok", None)
        if success is None:
            raise NiriException(f"NiriError: {ret.get('Err') or 'Unknown'}")

        return success

    def action(self, action: dict[str, dict]):
        """
        Send an action type request to niri. This is just a convenient
        wrapper around the request function.

        Raises
        ------
        NiriException
            If the attempt to communicate with Niri was unsuccesfull.
        """
        self.request(ActionRequest({"Action": action}))

    def windows(self) -> list[WindowResponse]:
        """
        Get all windows from niri

        Raises
        ------
        NiriException
            If the attempt to communicate with Niri was unsuccesfull.
        """
        return cast(list[WindowResponse], self.request("Windows").get("Windows", []))
        

    def outputs(self) -> dict[str, OutputResponse]:
        """
        Get all Monitors from niri

        Raises
        ------
        NiriException
            If the attempt to communicate with Niri was unsuccesfull.
        """
        return cast(dict[str, OutputResponse], self.request("Outputs").get("Outputs", {}))

    def workspaces(self) -> list[WorkspaceResponse]:
        """
        Get all Workspaces from niri

        Raises
        ------
        NiriException
            If the attempt to communicate with Niri was unsuccesfull.
        """
        return cast(list[WorkspaceResponse],self.request("Workspaces").get("Workspaces", []))

T = TypeVar('T')

class Fuzzel:
    """Allow selection of commands and entering of text via fuzzel."""

    @staticmethod
    def pick(options: dict[str,T], sorted_keys: list[str] | None = None) -> T:
        """Select one of multiple Options.

        Raises
        ------
        FuzzelNothingSelected
        """
        keys = sorted_keys or sorted(options.keys())
        fuzzel = subprocess.run(
            ["fuzzel", "--dmenu"],
            input="\n".join(keys),
            text=True,
            capture_output=True,
        )
        # Nothing was selected
        if (fuzzel.returncode != 0) or (selected := options.get(fuzzel.stdout.strip())) is None:
            raise FuzzelNothingSelected
        return selected

    @staticmethod
    def prompt(args: list[str]) -> str:
        """Enter arbitrary Text.

        Raises
        ------
        FuzzelNothingSelected
        """
        fuzzel = subprocess.run(
            ["fuzzel", "--dmenu"] + args,
            text=True,
            capture_output=True,
        )
        # Nothing was selected
        if fuzzel.returncode != 0:
            raise FuzzelNothingSelected
        return fuzzel.stdout.strip()


# region actions
class NiriAction:
    """
    Abstraction over Niri Actions. Creating a subclass will register
    the subclass as a command.

    Parameters
    ----------
    name: str | None = None
        Name that should be displayed in the fuzzel search.
    command: str | None = None
        The name of the Niri Action how Niri expects it.
    register: bool = True
        Allows not registering a command for extra layers of abstraction.
    """

    name: ClassVar[str]
    command: ClassVar[str]
    registry: ClassVar[dict[str, "NiriAction"]] = {}

    def __init_subclass__(
        cls,
        name: str | None = None,
        command: str | None = None,
        register: bool = True,
        **kwargs,
    ):
        super().__init_subclass__(**kwargs)
        cls.name = name or cls.__name__
        cls.command = command or cls.__name__
        if register:
            cls.registry[cls.name] = cls()

    def get_args(self, niri: NiriSocket) -> dict[str, Any]:
        """Return args

        Raises
        ------
        FuzzelNothingSelected
            If user cancelled the selection while asking for command arguments.
        """
        _ = niri
        return {}


class WindowTargetAction(NiriAction, register=False):
    """Commands that can target a specific Window or the currently selected one."""

    def pick_window(self, niri: NiriSocket) -> int:
        windows = {f"{w.get('title')} ({w.get('id')})":w.get("id") for w in niri.windows()}
        return Fuzzel.pick(windows)

    def get_args(self, niri: NiriSocket) -> dict:
        try:
            wid = self.pick_window(niri) if Config.prompt_for_optional_args else None
        except FuzzelNothingSelected:
            wid = None
        return {
            "id": wid,
        }


class RequiredWindowTargetAction(WindowTargetAction, register=False):
    """Commands that always need a window to target."""

    def get_args(self, niri: NiriSocket) -> dict:
        return {
            "id": self.pick_window(niri),
        }


class MonitorTargetAction(NiriAction, register=False):
    """Commands that can target a specific Monitor."""

    def pick_monitor(self, niri: NiriSocket) -> str:
        mons = {
            f"{out.get('name')}—{out.get('make')}—{out.get('model')} ({mid})":mid
            for mid, out in niri.outputs().items()
        }
        return Fuzzel.pick(mons)

    def get_args(self, niri: NiriSocket) -> dict:
        return {
            "output": self.pick_monitor(niri),
        }


class WorkspaceTargetAction(NiriAction, register=False):
    """Commands that can target a specific Workspace."""
    @staticmethod
    def _format_workspace_name(w: WorkspaceResponse):
        name = w.get('name') or f'Unnamed {w.get("idx")}'
        return f"{name} ({w.get('id')})"

    def pick_workspace(self, niri: NiriSocket) -> int:
        workspaces: dict[str,int] = {
            self._format_workspace_name(w):w.get('id')
            for w in niri.workspaces()
        }
        keys: list[str] = sorted(
            workspaces.keys(),
            key = lambda k: workspaces.get(k,-1)
        )
        return Fuzzel.pick(workspaces,keys)

    def get_args(self, niri: NiriSocket) -> dict:
        return {"reference": {"Id": self.pick_workspace(niri)}}


class WorkspaceFocusAction(NiriAction, register=False):
    """Commands with the `focus` argument."""

    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        return {"focus": Config.move_workspace_focus}


class PowerOffMonitors(NiriAction): ...
class PowerOnMonitors(NiriAction): ...
class ToggleKeyboardShortcutsInhibit(NiriAction): ...
class FocusWindowPrevious(NiriAction): ...
class FocusColumnLeft(NiriAction): ...
class FocusColumnRight(NiriAction): ...
class FocusColumnFirst(NiriAction): ...
class FocusColumnLast(NiriAction): ...
class FocusColumnRightOrFirst(NiriAction): ...
class FocusColumnLeftOrLast(NiriAction): ...
class FocusWindowOrMonitorUp(NiriAction): ...
class FocusWindowOrMonitorDown(NiriAction): ...
class FocusColumnOrMonitorLeft(NiriAction): ...
class FocusColumnOrMonitorRight(NiriAction): ...
class FocusWindowDown(NiriAction): ...
class FocusWindowUp(NiriAction): ...
class FocusWindowDownOrColumnLeft(NiriAction): ...
class FocusWindowDownOrColumnRight(NiriAction): ...
class FocusWindowUpOrColumnLeft(NiriAction): ...
class FocusWindowUpOrColumnRight(NiriAction): ...
class FocusWindowOrWorkspaceDown(NiriAction): ...
class FocusWindowOrWorkspaceUp(NiriAction): ...
class FocusWindowTop(NiriAction): ...
class FocusWindowBottom(NiriAction): ...
class FocusWindowDownOrTop(NiriAction): ...
class FocusWindowUpOrBottom(NiriAction): ...
class MoveColumnLeft(NiriAction): ...
class MoveColumnRight(NiriAction): ...
class MoveColumnToFirst(NiriAction): ...
class MoveColumnToLast(NiriAction): ...
class MoveColumnLeftOrToMonitorLeft(NiriAction): ...
class MoveColumnRightOrToMonitorRight(NiriAction): ...
class MoveWindowDown(NiriAction): ...
class MoveWindowUp(NiriAction): ...
class MoveWindowDownOrToWorkspaceDown(NiriAction): ...
class MoveWindowUpOrToWorkspaceUp(NiriAction): ...
class ConsumeWindowIntoColumn(NiriAction): ...
class ExpelWindowFromColumn(NiriAction): ...
class SwapWindowRight(NiriAction): ...
class SwapWindowLeft(NiriAction): ...
class ToggleColumnTabbedDisplay(NiriAction): ...
class CenterColumn(NiriAction): ...
class CenterVisibleColumns(NiriAction): ...
class FocusWorkspaceDown(NiriAction): ...
class FocusWorkspaceUp(NiriAction): ...
class FocusWorkspacePrevious(NiriAction): ...
class MoveWorkspaceDown(NiriAction): ...
class MoveWorkspaceUp(NiriAction): ...
class FocusMonitorLeft(NiriAction): ...
class FocusMonitorRight(NiriAction): ...
class FocusMonitorDown(NiriAction): ...
class FocusMonitorUp(NiriAction): ...
class FocusMonitorPrevious(NiriAction): ...
class FocusMonitorNext(NiriAction): ...
class MoveWindowToMonitorLeft(NiriAction): ...
class MoveWindowToMonitorRight(NiriAction): ...
class MoveWindowToMonitorDown(NiriAction): ...
class MoveWindowToMonitorUp(NiriAction): ...
class MoveWindowToMonitorPrevious(NiriAction): ...
class MoveWindowToMonitorNext(NiriAction): ...
class MoveColumnToMonitorLeft(NiriAction): ...
class MoveColumnToMonitorRight(NiriAction): ...
class MoveColumnToMonitorDown(NiriAction): ...
class MoveColumnToMonitorUp(NiriAction): ...
class MoveColumnToMonitorPrevious(NiriAction): ...
class MoveColumnToMonitorNext(NiriAction): ...
class SwitchPresetColumnWidth(NiriAction): ...
class SwitchPresetColumnWidthBack(NiriAction): ...
class MaximizeColumn(NiriAction): ...
class ExpandColumnToAvailableWidth(NiriAction): ...
class ShowHotkeyOverlay(NiriAction): ...
class MoveWorkspaceToMonitorLeft(NiriAction): ...
class MoveWorkspaceToMonitorRight(NiriAction): ...
class MoveWorkspaceToMonitorDown(NiriAction): ...
class MoveWorkspaceToMonitorUp(NiriAction): ...
class MoveWorkspaceToMonitorPrevious(NiriAction): ...
class MoveWorkspaceToMonitorNext(NiriAction): ...
class ToggleDebugTint(NiriAction): ...
class DebugToggleOpaqueRegions(NiriAction): ...
class DebugToggleDamage(NiriAction): ...
class FocusFloating(NiriAction): ...
class FocusTiling(NiriAction): ...
class SwitchFocusBetweenFloatingAndTiling(NiriAction): ...
class ClearDynamicCastTarget(NiriAction): ...
class ToggleOverview(NiriAction): ...
class OpenOverview(NiriAction): ...
class CloseOverview(NiriAction): ...


# with arguments
# These two have a confusing name
class FullscreenWindow(WindowTargetAction,name = "ToggleFullscreenWindow"): ...
class ToggleWindowedFullscreen(
    WindowTargetAction,
    name = "ToggleWindowedFullscreen (Fake Fullscreen)"
): ...

class CloseWindow(WindowTargetAction): ...
class FocusWindow(RequiredWindowTargetAction): ...
class ConsumeOrExpelWindowLeft(WindowTargetAction): ...
class ConsumeOrExpelWindowRight(WindowTargetAction): ...
class CenterWindow(WindowTargetAction): ...
class ResetWindowHeight(WindowTargetAction): ...
class SwitchPresetWindowWidth(WindowTargetAction): ...
class SwitchPresetWindowWidthBack(WindowTargetAction): ...
class SwitchPresetWindowHeight(WindowTargetAction): ...
class SwitchPresetWindowHeightBack(WindowTargetAction): ...
class MaximizeWindowToEdges(WindowTargetAction): ...
class ToggleWindowFloating(WindowTargetAction): ...
class MoveWindowToFloating(WindowTargetAction): ...
class MoveWindowToTiling(WindowTargetAction): ...
class ToggleWindowRuleOpacity(WindowTargetAction): ...
class SetDynamicCastWindow(WindowTargetAction): ...
class ToggleWindowUrgent(RequiredWindowTargetAction): ...
class SetWindowUrgent(RequiredWindowTargetAction): ...
class UnsetWindowUrgent(RequiredWindowTargetAction): ...

class MoveWindowToWorkspaceDown(WorkspaceFocusAction): ...
class MoveWindowToWorkspaceUp(WorkspaceFocusAction): ...
class MoveColumnToWorkspaceDown(WorkspaceFocusAction): ...
class MoveColumnToWorkspaceUp(WorkspaceFocusAction): ...
class FocusWorkspace(WorkspaceTargetAction): ...

class FocusMonitor(MonitorTargetAction): ...
# Technically it's optional for this one ...
class SetDynamicCastMonitor(MonitorTargetAction): ...
class MoveColumnToMonitor(MonitorTargetAction): ...

class Quit(NiriAction):
    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        return {"skip_confirmation": False}

class Screenshot(NiriAction):
    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        return {"show_pointer": Config.screenshot_show_pointer, "path": None}

class ScreenshotScreen(NiriAction):
    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        return {
            "write_to_disk": True,
            "show_pointer": Config.screenshot_show_pointer,
            "path": None,
        }

# Window Targets
class ScreenshotWindow(WindowTargetAction):
    def get_args(self, niri: NiriSocket) -> dict:
        try:
            wid = self.pick_window(niri) if Config.prompt_for_optional_args else None
        except FuzzelNothingSelected:
            wid = None
        return {
            "id": wid,
            "write_to_disk": True,
            "show_pointer": Config.screenshot_show_pointer,
            "path": None,
        }
# Workspace Targets
class MoveColumnToWorkspace(WorkspaceTargetAction):
    def get_args(self, niri: NiriSocket) -> dict:
        return {
            "reference": {"Id": self.pick_workspace(niri)},
            "focus": Config.move_workspace_focus,
        }


class MoveWindowToWorkspace(WorkspaceTargetAction):
    def get_args(self, niri: NiriSocket) -> dict:
        return {
            "reference": {"Id": self.pick_workspace(niri)},
            "focus": Config.move_workspace_focus,
            "window_id": None,
        }


class MoveWorkspaceToIndex(WorkspaceTargetAction):
    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        try:

            index = Fuzzel.prompt(["--prompt-only=>", "--mesg", "Enter Index:"])
            return {
                "index": int(index),
                "reference": None,
            }
        except ValueError as e:
            raise FuzzelInvalidInput("Could not parse Fuzzel input to valid index.") from e

# TODO reference could be selectable
class UnsetWorkspaceName(WorkspaceTargetAction):
    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        return {"reference": None}


class SetWorkspaceName(WorkspaceTargetAction):
    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        if name := Fuzzel.prompt(["--prompt-only=>", "--mesg", "Enter WorkspaceName:"]):
            return {
                "reference": None,
                "name": name,
            }
        raise FuzzelNothingSelected


# Monitor Targets
class MoveWindowToMonitor(MonitorTargetAction):
    def get_args(self, niri: NiriSocket) -> dict:
        return {
            "id": None,
            "output": self.pick_monitor(niri),
        }


class MoveWorkspaceToMonitor(MonitorTargetAction, WorkspaceTargetAction):
    def get_args(self, niri: NiriSocket) -> dict:
        try:
            workspace = ({"Id": self.pick_workspace(niri)}
                if Config.prompt_for_optional_args else None)
        except FuzzelNothingSelected:
            workspace = None
        return {
            "reference": workspace,
            "output": self.pick_monitor(niri),
        }


# These commands have args that only take very few inputs, so doing it this way feels more elegant
class SetColumnDisplayTabbed(
    NiriAction, name="SetColumnDisplay — Tabbed", command="SetColumnDisplay"
):
    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        return {"display": "Tabbed"}

class SetColumnDisplayNormal(
    NiriAction, name="SetColumnDisplay — Normal", command="SetColumnDisplay"
):
    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        return {"display": "Normal"}


class SwitchLayoutPrev(
    NiriAction, name="SwitchKeyboardLayout — Previous", command="SwitchLayout"
):
    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        return {"layout": "Prev"}

class SwitchLayoutNext(
    NiriAction, name="SwitchKeyboardLayout — Next", command="SwitchLayout"
):
    def get_args(self, niri: NiriSocket) -> dict:
        _=niri
        return {"layout": "Next"}


# I'm not implementing these as they seem like they would be
# either not useful or feel very clunky...

# "FocusWindowInColumn": {"index": u8}
# "FocusColumn": {"index": usize}
# "MoveColumnToIndex": {"index": usize}
# "SetColumnWidth": {"change": SizeChange}
# "SetWindowWidth": {"id": None,"change": SizeChange}
# "SetWindowHeight": {"id": Option<u64>,"change": SizeChange}
# "MoveFloatingWindow": {"id": Option<u64>,"x": PositionChange,"y": PositionChange}
# "StopCast": {"session_id": u64}
# "LoadConfigFile": {"path": Option<String>}
# endregion


def main():
    try:
        with NiriSocket() as con:
            selected = Fuzzel.pick(NiriAction.registry)
            args = selected.get_args(con)
            con.action({selected.command: args})
    except FuzzelNothingSelected:
        # User cancelled A selection, this was probably intentional
        # and shouldn't result in an error.
        raise SystemExit from None
    except FuzzelInvalidInput as e:
        error_msg_exit(str(e))
    except Exception as e:
        error_msg_exit(str(e))


if __name__ == "__main__":
    main()
