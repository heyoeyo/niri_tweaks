#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# niri_search_window.py
# This script is meant to help quickly navigationg to windows across workspaces. When called it uses [fuzzel](https://codeberg.org/dnkl/fuzzel) to fuzzy search all Niri windows. Once a window is selected Niri will switch to it.
# ```kdl
# Mod+Slash { spawn-sh "python3 /path/to/niri_search_window.py"; }
# ```
# Currently this does not support any commandline arguments.

from dataclasses import dataclass
import io
import socket
import os
import subprocess
import json
import re
from typing import TypedDict, Self, TypeAlias, Literal, Any

#region typechecking helpers

# This is just for getting type hints when creating the requests
# to send to niri With NiriSocket.request and not technically needed.
# It's also missing many of the possible actions since they aren't
# needed by this script.
class Niri:
    _IdField= TypedDict("_IdField",{"id":int})
    _FocusWindow = TypedDict("_FocusWindow",
        {"FocusWindow":_IdField})
    _FocusWindowPrevious= TypedDict("_FocusWindowPrevious",
        {"FocusWindowPrevious":dict})
    Action: TypeAlias = _FocusWindow | _FocusWindowPrevious

    _ActionRequest =  TypedDict("_ActionRequest",
        {"Action":Action})
    _OutputRequest =  TypedDict("_OutputRequest",
        {"Output":dict})
    Request: TypeAlias =\
        Literal["Windows"] | Literal["Version"] |\
        Literal["Outputs"] | Literal["Workspaces"] |\
        Literal["Windows"] | Literal["Layers"] |\
        Literal["KeyboardLayouts"] | Literal["FocusedOutput"] |\
        Literal["FocusedWindow"] | Literal["PickWindow"] |\
        Literal["PickColor"] | Literal["EventStream"] |\
        Literal["ReturnError"] | Literal["OverviewState"] |\
        Literal["Casts"] | _ActionRequest | _OutputRequest

# Typehints for the result of the Windows command.
# Also not technically needed and incomplete
    class Response:
        class Window(TypedDict):
            id: int
            title: str
            add_id: str
            pid: int
            workspace_id: int
            is_focused: bool
            is_floating: bool
            is_urgent: bool
            layout: Any
            focus_timestamp: Any
#endregion

@dataclass
class NiriException(BaseException):
    message: str


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

        self._sock = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self._sock.connect(socket_path)
        # The File wrapper is not technically needed but provides
        # a more convenient api around reading and writing to the socket.
        self._file= self._sock.makefile("rw")

    # enter and exit are just for using it as a context manager.
    def __enter__(self) -> Self:
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.close()

    def close(self):
        self._sock.close()

    def request(self,request: Niri.Request) -> dict:
        """
        Send a request to niri. Information about different requests can be found
        in the niri_ipc crate documentation.
        <https://niri-wm.github.io/niri/niri_ipc/enum.Request.html>

        Raises
        ------
        NiricException
            If the attempt to communicate with Niri was unsuccesfull.
        """
        self._file.write(f"{json.dumps(request)}\n")
        self._file.flush()
        ret = json.loads(self._file.readline())
        success= ret.get("Ok",None)
        if success is None:
            print (ret)
            raise NiriException(f"NiriError: {ret.get("Err") or "Unknown"}")

        return success

    def windows(self) -> list[Niri.Response.Window]:
        """
        Get all windows from niri

        Raises
        ------
        NiricException
            If the attempt to communicate with Niri was unsuccesfull.
        """
        return list(map(
            lambda w: Niri.Response.Window(w),
            self.request("Windows")\
            .get("Windows",{})
        ))

    def action(self,action: Niri.Action):
        """
        Send an action type request to niri. This is just a convenient
        wrapper around the request function.

        Raises
        ------
        NiricException
            If the attempt to communicate with Niri was unsuccesfull.
        """
        self.request({"Action": action})

    @staticmethod
    def get_niri_socket_path() -> str | None:
        return os.environ.get("NIRI_SOCKET")

def error_msg(message: str):
    """
    Use notify-send to notify the user of any Errors.
    """
    notify_title = "Windowsearch Error!"
    subprocess.run(["notify-send", notify_title, message])

def main():
    try:
        with NiriSocket() as con:
            # get all windows and convert them to readable lines for fuzzel
            windows = [
                f"{w.get("title")} ({w.get("id")})" for w in con.windows()
            ]
            if not windows:
                error_msg("Didn't find any windows.")            
            # Allow user to select window via fuzzel
            fuzzel = subprocess.run(
               ["fuzzel","--dmenu"],
               input="\n".join(
                   ["Previous Window"] +
                   windows
               ),
               text=True,
               capture_output=True)
            # Nothing was selected
            if fuzzel.returncode != 0:
                raise SystemExit()
            # Handle the special Previous window action
            if fuzzel.stdout.strip() == "Previous Window":
                print("focusing previous")
                con.action( {"FocusWindowPrevious": {}})
            # If a window was selected get the id and ask niri to switch to it
            elif match := re.match(r"^.* \((\d*)\)$",fuzzel.stdout):
                window_id = int(match.group(1))
                con.action({"FocusWindow": {"id": window_id}})
    except Exception as e:
        error_msg(str(e))

            
if __name__ == "__main__":
    main()
