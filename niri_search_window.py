#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass
import io
import socket
import os
import subprocess
import json
import re
from typing import TypedDict, Self, TypeAlias, Literal

#region typechecking helpers
IdField= TypedDict("IdField",{"id":int})
NiriFocusWindowAction = TypedDict("NiriFocusWindowAction",
    {"FocusWindow":IdField})
NiriAction: TypeAlias = NiriFocusWindowAction #TODO

NiriActionRequest =  TypedDict("NiriActionRequest",
    {"Action":NiriAction})
NiriOutputRequest =  TypedDict("NiriOutputRequest",{"Output":dict})
NiriRequest: TypeAlias =\
    Literal["Windows"] |\
    Literal["Version"] |\
    Literal["Outputs"] |\
    Literal["Workspaces"] |\
    Literal["Windows"] |\
    Literal["Layers"] |\
    Literal["KeyboardLayouts"] |\
    Literal["FocusedOutput"] |\
    Literal["FocusedWindow"] |\
    Literal["PickWindow"] |\
    Literal["PickColor"] |\
    Literal["EventStream"] |\
    Literal["ReturnError"] |\
    Literal["OverviewState"] |\
    Literal["Casts"] |\
    NiriActionRequest |\
    NiriOutputRequest

class NiriWindow(TypedDict):
    id: str
    title: str
    add_id: str
    pid: str
    is_floating: bool

#endregion

@dataclass
class NiriException(BaseException):
    message: str

class NiriSocket:
    """helper used to read & write json messages to a niri socket connection"""
    _sock: socket.socket
    _file: io.TextIOWrapper

    def __init__(self, socket_path: str | None = None) -> None:
        socket_path = socket_path or NiriSocket.get_niri_socket_path()
        # Sanity check
        is_bad_path = socket_path is None or str(socket_path) == ""
        assert not is_bad_path, "Cannot connect to niri, no socket path given..."

        self._sock = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self._sock.connect(socket_path)
        self._file= self._sock.makefile("rw")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.close()

    def close(self):
        self._sock.close()

    def request(self,request: NiriRequest) -> dict:
        self._file.write(f"{json.dumps(request)}\n")
        self._file.flush()
        ret = json.loads(self._file.readline())
        success= ret.get("Ok",None)
        if success is None:
            print (ret)
            raise NiriException(f"NiriError: {ret.get("Err") or "Unknown"}")

        return success

    def windows(self) -> list[NiriWindow]:
        return list(map(
            lambda w: NiriWindow(w),
            self.request("Windows")\
            .get("Windows",{})
        ))

    def action(self,action: NiriAction):
        self.request({"Action": action})
        pass

    @staticmethod
    def get_niri_socket_path() -> str | None:
        return os.environ.get("NIRI_SOCKET")

def error_msg(msg: str):
    notify_title = "Windowsearch Error!"
    subprocess.run(["notify-send", notify_title, msg])

def main():
    try:
        with NiriSocket() as con:
            windows = [
                f"{w.get("title")} ({w.get("id")})" for w in con.windows()
            ]
            if not windows:
                error_msg("Didn't find any windows.")            
            fuzzel = subprocess.run(
               ["fuzzel","--dmenu"],
               input="\n".join(windows),
               text=True,
               capture_output=True)
            if match := re.match(r"^.* \((\d*)\)$",fuzzel.stdout):
                window_id = int(match.group(1))
                con.action({"FocusWindow": {"id": window_id}})
    except Exception as e:
        error_msg(str(e))

            
if __name__ == "__main__":
    main()
